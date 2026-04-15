/**
 * resolve-entity.js - Smart entity resolution with match/reject transparency.
 *
 * Usage:
 *   node scripts/resolve-entity.js --name "BOYLE STREET SERVICE"
 *   node scripts/resolve-entity.js --name "BOYLE STREET SERVICE" --bn 118814391
 *   node scripts/resolve-entity.js --name "University of Alberta" --threshold 0.6
 *   node scripts/resolve-entity.js --name "Homeward Trust" --bn 834173627 --llm
 *   node scripts/resolve-entity.js --name "Homeward Trust" --llm --provider vertex
 *   node scripts/resolve-entity.js --name "mustard seed society" --bn 119050102 --llm --output results.json
 */
const { pool } = require('../lib/db');
const { EntityResolver } = require('../lib/entity-resolver');
const { reviewWithLLM, mergeResults, availableProviders } = require('../lib/llm-review');

function parseArgs() {
  const args = {};
  for (let i = 2; i < process.argv.length; i++) {
    if (process.argv[i] === '--name' && process.argv[i + 1]) args.name = process.argv[++i];
    else if (process.argv[i] === '--bn' && process.argv[i + 1]) args.bn = process.argv[++i];
    else if (process.argv[i] === '--threshold' && process.argv[i + 1]) args.threshold = parseFloat(process.argv[++i]);
    else if (process.argv[i] === '--llm') args.llm = true;
    else if (process.argv[i] === '--provider' && process.argv[i + 1]) args.provider = process.argv[++i];
    else if (process.argv[i] === '--output' && process.argv[i + 1]) args.output = process.argv[++i];
  }
  return args;
}

function displayDeterministicResults(result) {
  console.log(`\nEntity Resolution: "${result.query}"`);
  if (result.bn) console.log(`BN Anchor: ${result.bn}`);
  console.log(`Core Tokens: [${result.core_tokens.join(', ')}]`);
  console.log('='.repeat(80));

  console.log(`\n  MATCHED (${result.matches.length} results):`);
  console.log(`  ${'Conf'.padStart(6)} ${'Method'.padEnd(16)} ${'Source'.padEnd(14)} Name`);
  console.log('  ' + '-'.repeat(76));
  for (const m of result.matches) {
    const conf = (m.confidence * 100).toFixed(0) + '%';
    const bnInfo = m.bn ? ` [BN:${m.bn}]` : m.details?.bn ? ` [BN:${m.details.bn}]` : '';
    const detail = m.details?.trigram_sim !== undefined
      ? ` (trgm:${(m.details.trigram_sim * 100).toFixed(0)}% tok:${(m.details.token_overlap * 100).toFixed(0)}%)${bnInfo}`
      : bnInfo;
    console.log(`  ${conf.padStart(6)} ${m.method.padEnd(16)} ${m.source.padEnd(14)} ${m.matched_name}${detail}`);
  }

  if (result.rejected.length > 0) {
    const bnRejects = result.rejected.filter(r => r.reason?.startsWith('BN mismatch'));
    const otherRejects = result.rejected.filter(r => !r.reason?.startsWith('BN mismatch'));

    if (bnRejects.length > 0) {
      console.log(`\n  REJECTED BY BN MISMATCH (${bnRejects.length} confirmed different entities):`);
      console.log('  ' + '-'.repeat(76));
      for (const r of bnRejects) {
        console.log(`  ${(r.trigram_sim * 100).toFixed(0).padStart(5)}% trgm  ${r.source.padEnd(14)} ${r.name} [BN:${r.candidate_bn || '?'}]`);
        console.log(`  ${''.padStart(28)} -> ${r.reason}`);
      }
    }

    if (otherRejects.length > 0) {
      console.log(`\n  REJECTED BY TOKEN/TRIGRAM (${otherRejects.length} near-misses):`);
      console.log(`  ${'Trgm'.padStart(6)} ${'Tokens'.padStart(7)} ${'Source'.padEnd(14)} Name -> Reason`);
      console.log('  ' + '-'.repeat(76));
      for (const r of otherRejects) {
        console.log(`  ${(r.trigram_sim * 100).toFixed(0).padStart(5)}% ${(r.token_overlap * 100).toFixed(0).padStart(5)}%  ${r.source.padEnd(14)} ${r.name}`);
        console.log(`  ${''.padStart(28)} -> ${r.reason}`);
      }
    }
  }
}

function displayLLMResults(merged) {
  console.log('\n' + '='.repeat(80));
  console.log('  AI REVIEW (claude-sonnet-4-6)');
  console.log('='.repeat(80));
  console.log(`\n  Summary: ${merged.llm_summary}`);
  console.log(`  Tokens: ${merged.llm_usage?.input_tokens} in / ${merged.llm_usage?.output_tokens} out`);

  console.log(`\n  FINAL MATCHES after AI review (${merged.final_matches.length}):`);
  console.log(`  ${'Final'.padStart(6)} ${'Det'.padStart(5)} ${'LLM'.padStart(5)} ${'Verdict'.padEnd(12)} ${'Source'.padEnd(14)} Name`);
  console.log('  ' + '-'.repeat(78));

  for (const m of merged.final_matches) {
    const final = ((m.final_confidence || m.confidence) * 100).toFixed(0) + '%';
    const det = (m.confidence * 100).toFixed(0) + '%';
    const llm = m.llm_confidence ? (m.llm_confidence * 100).toFixed(0) + '%' : '  - ';
    const verdict = m.llm_verdict || m.method;
    const bnTag = m.bn ? ` [BN:${m.bn}]` : m.details?.bn ? ` [BN:${m.details.bn}]` : '';
    console.log(`  ${final.padStart(6)} ${det.padStart(5)} ${llm.padStart(5)} ${verdict.padEnd(12)} ${m.source.padEnd(14)} ${m.matched_name}${bnTag}`);
    if (m.llm_reasoning) {
      console.log(`  ${''.padStart(46)} ${m.llm_reasoning}`);
    }
  }

  if (merged.reclassified_by_llm.length > 0) {
    console.log(`\n  RECLASSIFIED BY AI (${merged.reclassified_by_llm.length} removed from matches):`);
    console.log('  ' + '-'.repeat(78));
    for (const m of merged.reclassified_by_llm) {
      console.log(`  ${m.source.padEnd(14)} ${m.matched_name}`);
      console.log(`    Was: ${(m.confidence * 100).toFixed(0)}% ${m.method} -> AI: DIFFERENT (${(m.llm_confidence * 100).toFixed(0)}%) - ${m.llm_reasoning}`);
    }
  }

  // Check for promotions from rejected
  const promoted = merged.final_matches.filter(m => m.method === 'llm_promoted');
  if (promoted.length > 0) {
    console.log(`\n  PROMOTED BY AI (${promoted.length} rescued from rejections):`);
    console.log('  ' + '-'.repeat(78));
    for (const m of promoted) {
      console.log(`  ${m.source.padEnd(14)} ${m.matched_name}`);
      console.log(`    Was rejected: ${m.original_rejection_reason}`);
      console.log(`    AI: ${m.llm_verdict} (${(m.llm_confidence * 100).toFixed(0)}%) - ${m.llm_reasoning}`);
    }
  }
}

async function run() {
  const args = parseArgs();
  if (!args.name) {
    console.log('Usage: node scripts/resolve-entity.js --name "Entity Name" [--bn 123456789] [--threshold 0.7] [--llm] [--provider anthropic|vertex] [--output file.json]');
    process.exit(0);
  }

  // Phase 1: Deterministic resolution
  const resolver = new EntityResolver(pool);
  await resolver.initialize();

  const result = await resolver.resolve(args.name, {
    bn: args.bn,
    coreTokenThreshold: args.threshold || 0.7,
  });

  displayDeterministicResults(result);

  // Phase 2: LLM review (if --llm flag)
  if (args.llm) {
    const providers = availableProviders();
    const forced = args.provider || null;
    console.log(`\n  Sending to Claude for AI review...`);
    console.log(`  Available providers: [${providers.join(', ')}]${forced ? ` (forced: ${forced})` : ''}`);

    try {
      const llmResult = await reviewWithLLM(result, {
        forceProvider: forced,
      });

      if (llmResult.error) {
        console.error('\n  LLM Error:', llmResult.error);
        if (llmResult.raw_response) {
          console.error('  Raw:', llmResult.raw_response.slice(0, 300));
        }
      } else {
        const merged = mergeResults(result, llmResult);
        displayLLMResults(merged);

        // Save to file if requested
        if (args.output) {
          const fs = require('fs');
          fs.writeFileSync(args.output, JSON.stringify(merged, null, 2));
          console.log(`\n  Saved to: ${args.output}`);
        }
      }
    } catch (err) {
      console.error('\n  LLM call failed:', err.message);
    }
  }

  await pool.end();
}

run().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
