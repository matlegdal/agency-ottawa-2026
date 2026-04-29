/**
 * 00-unzip.js — Unzip the OCL bundles into data/csv/.
 *
 * Idempotent: skips when the expected CSVs already exist. Uses the system
 * `unzip` (preinstalled on macOS and most Linux dev images).
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const RAW_DIR = path.join(__dirname, '..', 'data', 'raw');
const CSV_DIR = path.join(__dirname, '..', 'data', 'csv');

const BUNDLES = [
  {
    zip: 'registrations_enregistrements_ocl_cal.zip',
    sentinel: 'Registration_PrimaryExport.csv',
  },
  {
    zip: 'communications_ocl_cal.zip',
    sentinel: 'Communication_PrimaryExport.csv',
  },
];

function main() {
  fs.mkdirSync(CSV_DIR, { recursive: true });

  for (const { zip, sentinel } of BUNDLES) {
    const zipPath = path.join(RAW_DIR, zip);
    const sentinelPath = path.join(CSV_DIR, sentinel);

    if (!fs.existsSync(zipPath)) {
      console.error(`✗ Missing ${zip}. Drop the OCL zips into LOBBY/data/raw/ first.`);
      process.exit(1);
    }
    if (fs.existsSync(sentinelPath)) {
      console.log(`✓ ${zip} already extracted (found ${sentinel}).`);
      continue;
    }

    console.log(`→ Extracting ${zip}…`);
    execFileSync('unzip', ['-o', '-q', zipPath, '-d', CSV_DIR], { stdio: 'inherit' });
    console.log(`  done.`);
  }
}

main();
