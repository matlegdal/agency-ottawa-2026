/**
 * llm-review.js - Standalone AI-assisted entity review.
 *
 * Takes a JSON file of resolver results (or piped stdin) and sends them
 * to Claude for contextual judgment on ambiguous matches.
 *
 * Usage:
 *   node scripts/llm-review.js --input results.json
 *   node scripts/llm-review.js --input results.json --output reviewed.json
 *   cat results.json | node scripts/llm-review.js
 */
const fs = require('fs');
const path = require('path');
const { reviewWithLLM, mergeResults } = require('../lib/llm-review');

function parseArgs() {
  const args = {};
  for (let i = 2; i < process.argv.length; i++) {
    if (process.argv[i] === '--input' && process.argv[i + 1]) args.input = process.argv[++i];
    else if (process.argv[i] === '--output' && process.argv[i + 1]) args.output = process.argv[++i];
  }
  return args;
}

async function run() {
  const args = parseArgs();
  let resolverResult;

  if (args.input) {
    const raw = fs.readFileSync(args.input, 'utf8');
    resolverResult = JSON.parse(raw);
  } else {
    // Read from stdin
    const chunks = [];
    for await (const chunk of process.stdin) chunks.push(chunk);
    resolverResult = JSON.parse(Buffer.concat(chunks).toString());
  }

  console.log(`\nSending to Claude for AI review: "${resolverResult.query}"`);
  console.log(`  ${resolverResult.matches?.length || 0} matches, ${resolverResult.rejected?.length || 0} rejected`);
  console.log('  Calling claude-sonnet-4-6...\n');

  const llmResult = await reviewWithLLM(resolverResult);

  if (llmResult.error) {
    console.error('LLM Error:', llmResult.error);
    console.error('Raw response:', llmResult.raw_response?.slice(0, 500));
    process.exit(1);
  }

  const merged = mergeResults(resolverResult, llmResult);

  // Display results
  console.log(`LLM Summary: ${merged.llm_summary}`);
  console.log(`Tokens: ${merged.llm_usage?.input_tokens} in / ${merged.llm_usage?.output_tokens} out`);
  console.log('='.repeat(80));

  console.log(`\n  FINAL MATCHES (${merged.final_matches.length}):`);
  console.log(`  ${'Final'.padStart(6)} ${'Det'.padStart(5)} ${'LLM'.padStart(5)} ${'Verdict'.padEnd(10)} ${'Source'.padEnd(14)} Name`);
  console.log('  ' + '-'.repeat(76));

  for (const m of merged.final_matches) {
    const final = ((m.final_confidence || m.confidence) * 100).toFixed(0) + '%';
    const det = (m.confidence * 100).toFixed(0) + '%';
    const llm = m.llm_confidence ? (m.llm_confidence * 100).toFixed(0) + '%' : '  - ';
    const verdict = m.llm_verdict || m.method;
    console.log(`  ${final.padStart(6)} ${det.padStart(5)} ${llm.padStart(5)} ${verdict.padEnd(10)} ${m.source.padEnd(14)} ${m.matched_name}`);
    if (m.llm_reasoning) {
      console.log(`  ${''.padStart(44)} ${m.llm_reasoning}`);
    }
  }

  if (merged.reclassified_by_llm.length > 0) {
    console.log(`\n  RECLASSIFIED BY LLM (${merged.reclassified_by_llm.length} removed from matches):`);
    console.log('  ' + '-'.repeat(76));
    for (const m of merged.reclassified_by_llm) {
      console.log(`  ${m.source.padEnd(14)} ${m.matched_name}`);
      console.log(`    Was: ${(m.confidence * 100).toFixed(0)}% ${m.method} -> LLM: DIFFERENT (${(m.llm_confidence * 100).toFixed(0)}%) - ${m.llm_reasoning}`);
    }
  }

  // Save to file if requested
  if (args.output) {
    fs.writeFileSync(args.output, JSON.stringify(merged, null, 2));
    console.log(`\nSaved to: ${args.output}`);
  }

  // Always output JSON to stdout for piping
  if (!process.stdout.isTTY) {
    process.stdout.write(JSON.stringify(merged, null, 2));
  }
}

run().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
