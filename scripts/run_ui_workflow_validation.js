#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const SUMMARY_PATH = path.join(ROOT, 'docs', 'qa', 'ui-workflow-summary-latest.json');

function run(cmd, args) {
  console.log(`\n> ${cmd} ${args.join(' ')}`);
  const res = spawnSync(cmd, args, {
    cwd: ROOT,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  return res.status || 0;
}

function readSummary() {
  try {
    return JSON.parse(fs.readFileSync(SUMMARY_PATH, 'utf8'));
  } catch {
    return null;
  }
}

function main() {
  const stepInventory = run('node', ['scripts/build_ui_workflow_inventory.js']);
  const stepValidation = run('npx', ['playwright', 'test', 'tests/playwright/ui-workflow-validation.spec.js', '--reporter=line']);
  const stepRegression = run('npx', [
    'playwright',
    'test',
    'tests/playwright/ui-layout.spec.js',
    'tests/playwright/visual-regression.spec.js',
    'tests/playwright/backtesting-intelligence-rerun.spec.js',
    '--reporter=line',
  ]);
  const stepReports = run('node', ['scripts/generate_ui_workflow_reports.js']);

  const summary = readSummary();
  const statusFailures = summary ? (summary.FAIL + summary.MISSING) : 1;
  const shouldFail = stepInventory !== 0 || stepValidation !== 0 || stepRegression !== 0 || stepReports !== 0 || statusFailures > 0;

  if (summary) {
    console.log('\nValidation summary:');
    console.log(JSON.stringify(summary, null, 2));
  }

  if (shouldFail) {
    console.error('\nUI workflow validation completed with failures/missing workflows.');
    process.exit(1);
  }

  console.log('\nUI workflow validation completed successfully.');
}

main();
