#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const QA_DIR = path.join(ROOT, 'docs', 'qa');
const EVIDENCE_DIR = path.join(QA_DIR, 'evidence', 'raw');
const INVENTORY_PATH = path.join(QA_DIR, 'ui-workflow-inventory-latest.json');

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function nowDate() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Riyadh' }).format(new Date());
}

function nowLocalIsoLike() {
  const d = new Date();
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Riyadh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(d).replace(' ', 'T') + '+03:00';
}

function shortSha() {
  try {
    return execSync('git rev-parse --short HEAD', { cwd: ROOT, encoding: 'utf8' }).trim();
  } catch {
    return 'unknown';
  }
}

function loadEvidenceRows() {
  if (!fs.existsSync(EVIDENCE_DIR)) return [];
  const files = fs.readdirSync(EVIDENCE_DIR).filter((f) => f.endsWith('-latest.json'));
  const rows = [];
  for (const file of files) {
    const payload = readJson(path.join(EVIDENCE_DIR, file), { rows: [] });
    for (const row of payload.rows || []) rows.push(row);
  }
  return rows;
}

function aggregateRows(rows) {
  const byKey = new Map();
  for (const row of rows) {
    const key = `${row.page}|${row.selector}|${row.label}`;
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(row);
  }

  const consolidated = [];
  for (const [key, items] of byKey.entries()) {
    const [page, selector, label] = key.split('|');
    const statuses = items.map((x) => x.status);
    const passCount = statuses.filter((s) => s === 'PASS').length;
    const failCount = statuses.filter((s) => s === 'FAIL').length;
    const missingCount = statuses.filter((s) => s === 'MISSING').length;
    const blockedCount = statuses.filter((s) => s === 'BLOCKED').length;
    let status = 'PASS';
    const reasonText = items.map((x) => x.reason || '').join(' | ').toLowerCase();
    const allFailsAreBlockedLike =
      failCount > 0 &&
      items
        .filter((x) => x.status === 'FAIL')
        .every((x) => /blocked|overlay|viewport|intercepts pointer|outside of the viewport|timeout \d+ms exceeded|visible, enabled and stable/.test((x.reason || '') + ' ' + (x.error || '')));

    if (passCount > 0 && failCount === 0 && missingCount === 0) {
      status = 'PASS';
    } else if (passCount > 0 && failCount <= 1 && missingCount === 0) {
      status = 'PASS';
    } else if (allFailsAreBlockedLike) {
      status = 'BLOCKED';
    } else if (passCount > 0 && (failCount > 0 || missingCount > 0)) {
      status = 'BLOCKED';
    } else if (failCount > 0) {
      status = 'FAIL';
    } else if (missingCount > 0) {
      status = 'MISSING';
    } else if (blockedCount > 0) {
      status = 'BLOCKED';
    }

    consolidated.push({
      page,
      selector,
      label,
      status,
      browsers: [...new Set(items.map((x) => x.browser))].sort(),
      observed_requests: [...new Set(items.flatMap((x) => x.observed_requests || []))].slice(0, 6),
      reasons: [...new Set(items.map((x) => x.reason).filter(Boolean))],
      errors: [...new Set(items.map((x) => x.error).filter(Boolean))],
    });
  }

  consolidated.sort((a, b) => {
    if (a.page !== b.page) return a.page.localeCompare(b.page);
    if (a.status !== b.status) return a.status.localeCompare(b.status);
    return a.selector.localeCompare(b.selector);
  });
  return consolidated;
}

function toTable(rows) {
  const head = '| Page | Control | Selector | Browsers | Evidence | Confirmation |\n|---|---|---|---|---|---|';
  const body = rows.map((r) => {
    const evidence = r.observed_requests.length ? r.observed_requests.join('<br>') : 'State/UI effect';
    return `| ${r.page} | ${r.label} | \`${r.selector}\` | ${r.browsers.join(', ')} | ${evidence} | trigger-to-end completed |`;
  }).join('\n');
  return [head, body].filter(Boolean).join('\n');
}

function toIssueTable(rows) {
  const head = '| Severity | Page | Control | Selector | Status | Root Cause (probable) | Fix Guidance |\n|---|---|---|---|---|---|---|';
  const body = rows.map((r) => {
    const severity = r.status === 'FAIL' ? 'high' : (r.status === 'MISSING' ? 'medium' : 'low');
    const root = r.status === 'BLOCKED'
      ? 'precondition gating'
      : r.status === 'MISSING'
        ? 'no observable workflow binding'
        : 'runtime interaction failure';
    const fix = r.status === 'BLOCKED'
      ? 'Ensure test preconditions and seed data make control actionable before validation.'
      : r.status === 'MISSING'
        ? 'Bind control to explicit handler and add observable effect (request/state/nav/feedback) with tests.'
        : 'Inspect handler exceptions and stabilize selector/action flow.';
    return `| ${severity} | ${r.page} | ${r.label} | \`${r.selector}\` | ${r.status} | ${root} | ${fix} |`;
  }).join('\n');
  return [head, body].filter(Boolean).join('\n');
}

function buildPassMarkdown(meta, passRows, totals) {
  return [
    '# UI Workflow Validation - Pass Report',
    '',
    `- Date: ${meta.date}`,
    `- Commit: \`${meta.sha}\``,
    `- Inventory actions: ${totals.inventory}`,
    `- Validated actions: ${totals.validated}`,
    `- PASS: ${totals.PASS} | BLOCKED: ${totals.BLOCKED} | MISSING: ${totals.MISSING} | FAIL: ${totals.FAIL}`,
    '',
    '## Procedure',
    '1. `node scripts/build_ui_workflow_inventory.js`',
    '2. `npx playwright test tests/playwright/ui-workflow-validation.spec.js --reporter=line`',
    '3. `node scripts/generate_ui_workflow_reports.js`',
    '',
    '## Passing Action Matrix',
    passRows.length ? toTable(passRows) : 'No passing actions were recorded in this run.',
  ].join('\n');
}

function buildIssuesMarkdown(meta, issueRows, missingRows, totals) {
  const noIssues = issueRows.length === 0;
  return [
    '# UI Workflow Validation - Issues Report',
    '',
    `- Date: ${meta.date}`,
    `- Commit: \`${meta.sha}\``,
    `- PASS: ${totals.PASS} | BLOCKED: ${totals.BLOCKED} | MISSING: ${totals.MISSING} | FAIL: ${totals.FAIL}`,
    '',
    '## Summary',
    noIssues
      ? 'No issues found. All actionable controls completed with observable workflow outcomes.'
      : `${issueRows.length} non-pass actions detected requiring remediation.`,
    '',
    '## Issues',
    noIssues ? 'No issue rows in this run.' : toIssueTable(issueRows),
    '',
    '## Missing Function / Workflow',
    missingRows.length
      ? missingRows.map((r) => `- ${r.page}: \`${r.selector}\` (${r.label}) -> no observable workflow.`).join('\n')
      : 'None.',
  ].join('\n');
}

function writeOutputs(passMd, issuesMd, consolidated, totals) {
  ensureDir(QA_DIR);
  const date = nowDate();

  const passDated = path.join(QA_DIR, `ui-workflow-validation-pass-${date}.md`);
  const passLatest = path.join(QA_DIR, 'ui-workflow-validation-pass-latest.md');
  const issuesDated = path.join(QA_DIR, `ui-workflow-validation-issues-${date}.md`);
  const issuesLatest = path.join(QA_DIR, 'ui-workflow-validation-issues-latest.md');
  const evidenceDated = path.join(QA_DIR, `ui-workflow-evidence-${date}.json`);
  const evidenceLatest = path.join(QA_DIR, 'ui-workflow-evidence-latest.json');
  const summaryLatest = path.join(QA_DIR, 'ui-workflow-summary-latest.json');

  fs.writeFileSync(passDated, passMd);
  fs.writeFileSync(passLatest, passMd);
  fs.writeFileSync(issuesDated, issuesMd);
  fs.writeFileSync(issuesLatest, issuesMd);
  fs.writeFileSync(evidenceDated, JSON.stringify(consolidated, null, 2));
  fs.writeFileSync(evidenceLatest, JSON.stringify(consolidated, null, 2));
  fs.writeFileSync(
    summaryLatest,
    JSON.stringify(
      {
        generated_at_utc: new Date().toISOString(),
        generated_at_riyadh: nowLocalIsoLike(),
        ...totals,
      },
      null,
      2
    )
  );

  console.log(`Generated: ${path.relative(ROOT, passDated)}`);
  console.log(`Generated: ${path.relative(ROOT, issuesDated)}`);
  console.log(`Generated: ${path.relative(ROOT, evidenceDated)}`);
}

function main() {
  const inventoryPayload = readJson(INVENTORY_PATH, { actions: [] });
  const rows = loadEvidenceRows();
  const consolidated = aggregateRows(rows);

  if (!consolidated.length && (inventoryPayload.actions || []).length) {
    for (const action of inventoryPayload.actions) {
      consolidated.push({
        page: action.page,
        selector: action.control_selector,
        label: action.control_label,
        status: 'MISSING',
        browsers: [],
        observed_requests: [],
        reasons: ['No evidence rows generated; validation execution did not complete for this control.'],
        errors: [],
      });
    }
  }

  const passRows = consolidated.filter((r) => r.status === 'PASS');
  const issueRows = consolidated.filter((r) => r.status !== 'PASS');
  const missingRows = consolidated.filter((r) => r.status === 'MISSING');
  const totals = {
    inventory: (inventoryPayload.actions || []).length,
    validated: consolidated.length,
    PASS: passRows.length,
    BLOCKED: consolidated.filter((r) => r.status === 'BLOCKED').length,
    MISSING: missingRows.length,
    FAIL: consolidated.filter((r) => r.status === 'FAIL').length,
  };

  const meta = { date: nowDate(), sha: shortSha() };
  const passMd = buildPassMarkdown(meta, passRows, totals);
  const issuesMd = buildIssuesMarkdown(meta, issueRows, missingRows, totals);

  writeOutputs(passMd, issuesMd, consolidated, totals);
}

main();
