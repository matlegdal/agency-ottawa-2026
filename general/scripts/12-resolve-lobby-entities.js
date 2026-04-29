/**
 * 12-resolve-lobby-entities.js — Deterministic-only resolution of lobby clients
 * to general.entities / entity_source_links. NO Splink, NO LLM.
 *
 * Why a separate stage: lobby was loaded after the main resolution pipeline
 * and uses its own (incompatible) name normalizer. Re-normalizing with
 * general.norm_name() and routing through the same matchCascade as AB lifts
 * the lobby↔entity match rate from 0% to ~17.5% deterministically.
 *
 * Pattern follows phase3 (AB) in 04-resolve-entities.js:
 *   1. Add a gnorm_name column to lobby tables (UPPER, general.norm_name).
 *   2. Insert one entity_resolution_log row per distinct gnorm_name.
 *   3. matchCascade: exact_name → normalized → trade_name → pipe_split.
 *   4. batchCreate: anything still pending becomes a new lobby_only entity.
 *   5. Augment matched entities with the lobby alternate name + dataset_sources.
 *   6. Populate entity_source_links one row per registration / communication.
 *
 * After this stage, the verifier probe collapses to:
 *   SELECT * FROM general.entity_source_links
 *    WHERE entity_id = $1 AND source_schema = 'lobby';
 *
 * Idempotent and resumable: every step is guarded by an existence check and
 * uses ON CONFLICT DO NOTHING.
 *
 * Usage:
 *   node scripts/12-resolve-lobby-entities.js
 *   node scripts/12-resolve-lobby-entities.js --skip-comms   # registrations only
 *   node scripts/12-resolve-lobby-entities.js --reset        # drop everything lobby-related, then run
 */

const db = require('../lib/db');

const BATCH = 50000;

function ts() { return new Date().toISOString().slice(11, 19); }
function log(step, msg) { console.log(`[${ts()}] [LOBBY] ${step ? step + ': ' : ''}${msg}`); }
function logC(step, label, count, t0) {
  log(step, `${label}: ${count.toLocaleString()} (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
}

function parseArgs() {
  const args = { skipComms: false, reset: false };
  for (const a of process.argv.slice(2)) {
    if (a === '--skip-comms') args.skipComms = true;
    else if (a === '--reset') args.reset = true;
  }
  return args;
}

// ═══════════════════════════════════════════════════════════════
//  STEP 1 — Add gnorm_name columns and populate
// ═══════════════════════════════════════════════════════════════

async function ensureGnormColumns(client) {
  const t0 = Date.now();
  log('schema', 'Ensuring gnorm_name columns exist');

  await client.query(`
    ALTER TABLE lobby.lobby_registrations  ADD COLUMN IF NOT EXISTS gnorm_name TEXT;
    ALTER TABLE lobby.lobby_communications ADD COLUMN IF NOT EXISTS gnorm_name TEXT;
  `);

  // Populate where missing. Idempotent — only touches NULL rows.
  const r1 = await client.query(`
    UPDATE lobby.lobby_registrations
       SET gnorm_name = NULLIF(general.norm_name(client_name_en), '')
     WHERE gnorm_name IS NULL AND client_name_en IS NOT NULL
  `);
  log('schema', `lobby_registrations.gnorm_name populated: ${r1.rowCount.toLocaleString()}`);

  const r2 = await client.query(`
    UPDATE lobby.lobby_communications
       SET gnorm_name = NULLIF(general.norm_name(client_name_en), '')
     WHERE gnorm_name IS NULL AND client_name_en IS NOT NULL
  `);
  log('schema', `lobby_communications.gnorm_name populated: ${r2.rowCount.toLocaleString()}`);

  // Index for the cascade join.
  await client.query(`
    CREATE INDEX IF NOT EXISTS idx_lobby_reg_gnorm  ON lobby.lobby_registrations  (gnorm_name);
    CREATE INDEX IF NOT EXISTS idx_lobby_com_gnorm  ON lobby.lobby_communications (gnorm_name);
  `);

  logC('schema', 'Done', r1.rowCount + r2.rowCount, t0);
}

// ═══════════════════════════════════════════════════════════════
//  STEP 2 — Extract distinct names into entity_resolution_log
// ═══════════════════════════════════════════════════════════════

async function extractNames(client, table) {
  const t0 = Date.now();
  const existing = (await client.query(
    `SELECT COUNT(*)::int AS cnt FROM general.entity_resolution_log
      WHERE source_schema = 'lobby' AND source_table = $1`, [table]
  )).rows[0].cnt;

  if (existing > 0) {
    log(table, `Already extracted: ${existing.toLocaleString()}. Skipping insert.`);
    return existing;
  }

  // source_name is the canonical-cased gnorm_name (UPPER, regex-stripped).
  // matchCascade in 04-resolve-entities.js uses UPPER comparisons, so storing
  // the already-normalized form keeps the cascade indexed and avoids per-row
  // recomputation.
  const ext = await client.query(`
    INSERT INTO general.entity_resolution_log (source_schema, source_table, source_name, record_count)
    SELECT 'lobby', $1, gnorm_name, COUNT(*)
      FROM lobby.${table}
     WHERE gnorm_name IS NOT NULL AND LENGTH(gnorm_name) >= 3
     GROUP BY gnorm_name
    ON CONFLICT (source_schema, source_table, source_name) DO NOTHING
  `, [table]);

  logC(table, 'Extracted distinct names', ext.rowCount, t0);
  return ext.rowCount;
}

// ═══════════════════════════════════════════════════════════════
//  STEP 3 — Match cascade (mirrors matchCascade in 04-resolve-entities.js)
// ═══════════════════════════════════════════════════════════════

async function matchCascade(client, table) {
  // 1. Exact name (source_name is already UPPER-cased by general.norm_name)
  let t1 = Date.now();
  const exactRes = await client.query(`
    UPDATE general.entity_resolution_log rl SET
      status = 'matched', entity_id = e.id,
      match_confidence = 0.95, match_method = 'exact_name', updated_at = NOW()
    FROM general.entities e
    WHERE rl.source_schema = 'lobby' AND rl.source_table = $1
      AND rl.status = 'pending' AND e.merged_into IS NULL
      AND UPPER(e.canonical_name) = rl.source_name
  `, [table]);
  logC(table, 'Exact matched', exactRes.rowCount, t1);

  // 2. Normalized match — source_name is already general.norm_name(client_name_en),
  //    so we compare against e.norm_canonical directly without recomputing.
  t1 = Date.now();
  const normRes = await client.query(`
    UPDATE general.entity_resolution_log rl SET
      status = 'matched', entity_id = e.id,
      match_confidence = 0.90, match_method = 'normalized', updated_at = NOW()
    FROM general.entities e
    WHERE rl.source_schema = 'lobby' AND rl.source_table = $1
      AND rl.status = 'pending' AND e.merged_into IS NULL
      AND rl.source_name = e.norm_canonical
  `, [table]);
  logC(table, 'Normalized matched', normRes.rowCount, t1);

  // 3. Trade-name match (rare in lobby data but cheap to run; lobby's
  //    client_name_en occasionally carries "X trade name of Y" tails that
  //    general.norm_name strips before insert, so this catches the residue).
  t1 = Date.now();
  const tradeRes = await client.query(`
    UPDATE general.entity_resolution_log rl SET
      status = 'matched', entity_id = e.id,
      match_confidence = 0.88, match_method = 'trade_name', updated_at = NOW()
    FROM general.entities e
    WHERE rl.source_schema = 'lobby' AND rl.source_table = $1
      AND rl.status = 'pending' AND e.merged_into IS NULL
      AND rl.source_name LIKE '%TRADE NAME OF%'
      AND general.norm_name(split_part(rl.source_name, 'TRADE NAME OF', 2)) = e.norm_canonical
      AND general.norm_name(split_part(rl.source_name, 'TRADE NAME OF', 2)) != ''
  `, [table]);
  logC(table, 'Trade-name matched', tradeRes.rowCount, t1);

  return exactRes.rowCount + normRes.rowCount + tradeRes.rowCount;
}

// ═══════════════════════════════════════════════════════════════
//  STEP 4 — Create new entities for whatever is still pending
// ═══════════════════════════════════════════════════════════════

async function batchCreate(client, table) {
  let total = 0;
  const t0 = Date.now();

  while (true) {
    const res = await client.query(`
      WITH batch AS (
        SELECT id, source_name
          FROM general.entity_resolution_log
         WHERE source_schema = 'lobby' AND source_table = $1 AND status = 'pending'
         LIMIT ${BATCH}
      ),
      new_ents AS (
        INSERT INTO general.entities
          (canonical_name, entity_type, norm_canonical, source_count, dataset_sources, confidence, status)
        SELECT b.source_name, 'lobby_only', b.source_name, 1, ARRAY['lobby'], 0.70, 'draft'
          FROM batch b
        RETURNING id, canonical_name
      )
      UPDATE general.entity_resolution_log rl SET
        status = 'created', entity_id = ne.id, match_confidence = 1.0,
        match_method = 'new_entity', updated_at = NOW()
      FROM new_ents ne
      WHERE rl.id IN (SELECT id FROM batch)
        AND rl.source_name = ne.canonical_name
    `, [table]);

    if (res.rowCount === 0) break;
    total += res.rowCount;
    log(table, `  batch: +${res.rowCount.toLocaleString()} (total: ${total.toLocaleString()})`);
  }
  logC(table, 'New entities created', total, t0);
  return total;
}

// ═══════════════════════════════════════════════════════════════
//  STEP 5 — Augment matched entities with lobby alt names + sources
// ═══════════════════════════════════════════════════════════════

async function augment(client, table) {
  const t0 = Date.now();
  const aug = await client.query(`
    UPDATE general.entities e SET
      alternate_names = (
        SELECT array_agg(DISTINCT n)
          FROM unnest(array_cat(e.alternate_names, ARRAY[rl.source_name])) AS n
      ),
      dataset_sources = CASE WHEN 'lobby' = ANY(e.dataset_sources)
                             THEN e.dataset_sources
                             ELSE array_append(e.dataset_sources, 'lobby') END,
      source_count = e.source_count + 1,
      updated_at = NOW()
    FROM general.entity_resolution_log rl
    WHERE rl.source_schema = 'lobby' AND rl.source_table = $1
      AND rl.status = 'matched'
      AND rl.entity_id IS NOT NULL
      AND e.id = rl.entity_id
      AND NOT ('lobby' = ANY(e.dataset_sources))
  `, [table]);
  logC(table, 'Augmented', aug.rowCount, t0);
}

// ═══════════════════════════════════════════════════════════════
//  STEP 6 — Source links (one row per registration / communication)
// ═══════════════════════════════════════════════════════════════

async function buildSourceLinks(client, table, pkCol) {
  const t0 = Date.now();

  const existing = (await client.query(
    `SELECT COUNT(*)::int AS cnt FROM general.entity_source_links
      WHERE source_schema = 'lobby' AND source_table = $1`, [table]
  )).rows[0].cnt;
  if (existing > 0) {
    log(table, `Source links already populated: ${existing.toLocaleString()}. Skipping.`);
    return existing;
  }

  const sl = await client.query(`
    INSERT INTO general.entity_source_links
      (entity_id, source_schema, source_table, source_pk, source_name,
       match_confidence, match_method, link_status)
    SELECT rl.entity_id, 'lobby', $1,
           jsonb_build_object('${pkCol}', t.${pkCol}),
           t.client_name_en,
           rl.match_confidence, rl.match_method,
           CASE WHEN rl.match_confidence >= 0.85 THEN 'confirmed' ELSE 'tentative' END
      FROM general.entity_resolution_log rl
      JOIN lobby.${table} t ON t.gnorm_name = rl.source_name
     WHERE rl.source_schema = 'lobby' AND rl.source_table = $1
       AND rl.status IN ('matched', 'created')
       AND rl.entity_id IS NOT NULL
    ON CONFLICT DO NOTHING
  `, [table]);

  logC(table, 'Source links inserted', sl.rowCount, t0);
  return sl.rowCount;
}

// ═══════════════════════════════════════════════════════════════
//  RESET (--reset only) — clear lobby resolution state
// ═══════════════════════════════════════════════════════════════

async function reset(client) {
  log('reset', 'Clearing lobby source links and resolution log');

  // Drop source links.
  const sl = await client.query(`
    DELETE FROM general.entity_source_links WHERE source_schema = 'lobby'
  `);
  log('reset', `entity_source_links: -${sl.rowCount.toLocaleString()}`);

  // Drop new entities created exclusively by the lobby pass.
  // Safe because lobby_only entities have dataset_sources = {lobby} and no
  // other sources have been linked to them yet (they were created here).
  const ents = await client.query(`
    DELETE FROM general.entities
     WHERE entity_type = 'lobby_only'
       AND dataset_sources = ARRAY['lobby']::text[]
       AND id NOT IN (SELECT entity_id FROM general.entity_source_links WHERE entity_id IS NOT NULL)
  `);
  log('reset', `entities (lobby_only): -${ents.rowCount.toLocaleString()}`);

  // For lobby rows that had matched into pre-existing entities, undo augmentation.
  const aug = await client.query(`
    UPDATE general.entities e SET
      dataset_sources = array_remove(e.dataset_sources, 'lobby'),
      source_count = GREATEST(0, e.source_count - 1),
      updated_at = NOW()
    FROM general.entity_resolution_log rl
    WHERE rl.source_schema = 'lobby'
      AND rl.status IN ('matched', 'created')
      AND rl.entity_id IS NOT NULL
      AND e.id = rl.entity_id
      AND 'lobby' = ANY(e.dataset_sources)
  `);
  log('reset', `entities (augmentation rolled back): -${aug.rowCount.toLocaleString()}`);

  // Drop the resolution log entries.
  const rl = await client.query(`
    DELETE FROM general.entity_resolution_log WHERE source_schema = 'lobby'
  `);
  log('reset', `entity_resolution_log: -${rl.rowCount.toLocaleString()}`);
}

// ═══════════════════════════════════════════════════════════════
//  SUMMARY
// ═══════════════════════════════════════════════════════════════

async function printSummary(client) {
  const r = await client.query(`
    SELECT match_method, COUNT(*) AS n
      FROM general.entity_resolution_log
     WHERE source_schema = 'lobby'
     GROUP BY 1 ORDER BY 2 DESC
  `);
  log('summary', 'Resolution by method:');
  for (const row of r.rows) console.log(`             ${row.match_method.padEnd(12)} ${Number(row.n).toLocaleString()}`);

  const sl = await client.query(`
    SELECT source_table, COUNT(*) AS n
      FROM general.entity_source_links
     WHERE source_schema = 'lobby'
     GROUP BY 1 ORDER BY 1
  `);
  log('summary', 'Source links by table:');
  for (const row of sl.rows) console.log(`             ${row.source_table.padEnd(24)} ${Number(row.n).toLocaleString()}`);

  const cov = await client.query(`
    SELECT COUNT(DISTINCT entity_id) AS entities_with_lobby
      FROM general.entity_source_links WHERE source_schema = 'lobby'
  `);
  log('summary', `Distinct entities with lobby footprint: ${Number(cov.rows[0].entities_with_lobby).toLocaleString()}`);
}

// ═══════════════════════════════════════════════════════════════
//  MAIN
// ═══════════════════════════════════════════════════════════════

async function main() {
  const args = parseArgs();
  const client = await db.getClient();
  try {
    if (args.reset) {
      await reset(client);
      log('reset', 'Reset complete. Re-run without --reset to repopulate.');
      return;
    }

    log('main', 'Starting lobby entity resolution (deterministic only)');
    await ensureGnormColumns(client);

    const tables = ['lobby_registrations'];
    if (!args.skipComms) tables.push('lobby_communications');

    for (const table of tables) {
      log(table, `── ${table} ──`);
      await extractNames(client, table);
      await matchCascade(client, table);
      await batchCreate(client, table);
      await augment(client, table);

      // PK column is reg_id for registrations, comlog_id for communications.
      const pkCol = table === 'lobby_registrations' ? 'reg_id' : 'comlog_id';
      await buildSourceLinks(client, table, pkCol);
    }

    await printSummary(client);
    log('main', 'Done.');
  } catch (err) {
    console.error('FATAL:', err);
    process.exitCode = 1;
  } finally {
    client.release();
    await db.end();
  }
}

main();
