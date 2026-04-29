/**
 * 00-unzip.js — Unzip the OPEN_DATA_SPLIT bundle into data/xml/.
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const RAW_DIR = path.join(__dirname, '..', 'data', 'raw');
const XML_DIR = path.join(__dirname, '..', 'data', 'xml');
const ZIP = 'OPEN_DATA_SPLIT.zip';
const SENTINEL = 'codes.xml';

function main() {
  fs.mkdirSync(XML_DIR, { recursive: true });
  const zipPath = path.join(RAW_DIR, ZIP);
  const sentinelPath = path.join(XML_DIR, SENTINEL);

  if (!fs.existsSync(zipPath)) {
    console.error(`✗ Missing ${ZIP}. Drop it into CORP/data/raw/ first.`);
    process.exit(1);
  }
  if (fs.existsSync(sentinelPath)) {
    console.log(`✓ ${ZIP} already extracted.`);
    return;
  }

  console.log(`→ Extracting ${ZIP}…`);
  execFileSync('unzip', ['-o', '-q', zipPath, '-d', XML_DIR], { stdio: 'inherit' });
  console.log('  done.');
}

main();
