#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PAGES_DIR = path.join(ROOT, 'static', 'js', 'pages');
const OUT_DIR = path.join(ROOT, 'docs', 'qa');

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8');
}

function lineOf(content, index) {
  return content.slice(0, index).split('\n').length;
}

function parseButtons(content, pageName, filePath) {
  const rows = [];
  const buttonRegex = /<button\b([\s\S]*?)>([\s\S]*?)<\/button>/g;
  let match;
  let ordinal = 0;
  while ((match = buttonRegex.exec(content)) !== null) {
    const attrs = match[1] || '';
    const label = (match[2] || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    const idMatch = attrs.match(/\bid="([^"]+)"/);
    const dataActionMatch = attrs.match(/\bdata-action="([^"]+)"/);
    const dataQuickMatch = attrs.match(/\bdata-quick-action="([^"]+)"/);
    const dataIntelligenceMatch = attrs.match(/\bdata-intelligence-action="([^"]+)"/);
    const dataWorkspaceMatch = attrs.match(/\bdata-ai-workspace-action="([^"]+)"/);
    const selector = idMatch
      ? `#${idMatch[1]}`
      : dataQuickMatch
        ? `[data-quick-action="${dataQuickMatch[1]}"]`
        : dataIntelligenceMatch
          ? `[data-intelligence-action="${dataIntelligenceMatch[1]}"]`
          : dataWorkspaceMatch
            ? `[data-ai-workspace-action="${dataWorkspaceMatch[1]}"]`
            : dataActionMatch
              ? `[data-action="${dataActionMatch[1]}"]`
              : `button:nth-of-type(${++ordinal})`;

    rows.push({
      page: pageName,
      control_selector: selector,
      control_label: label || '(unlabeled button)',
      trigger_type: 'click',
      expected_downstream_behavior:
        'Control should trigger workflow side effect (request, navigation, modal/state change, or feedback message).',
      endpoints: [],
      success_criteria:
        'Observable post-click effect detected and no unhandled runtime failure.',
      failure_criteria:
        'Unhandled error, missing effect for implemented control, or control present without workflow binding.',
      evidence_requirements:
        'Captured selector, label, browser, observed requests, hash/state delta, and status.',
      source_file: path.relative(ROOT, filePath).replace(/\\/g, '/'),
      source_line: lineOf(content, match.index),
      status: 'not_run',
    });
  }
  return rows;
}

function inferEndpoints(content) {
  const endpoints = new Set();
  const apiRegex = /API\.[a-zA-Z0-9_]+\(([\s\S]*?)\)/g;
  const fetchRegex = /fetch\(([`'"])(\/[^`'"]+)\1/g;
  let m;
  while ((m = fetchRegex.exec(content)) !== null) endpoints.add(m[2]);
  while ((m = apiRegex.exec(content)) !== null) {
    const args = m[1] || '';
    const literalPath = args.match(/([`'"])(\/[^`'"]+)\1/);
    if (literalPath) endpoints.add(literalPath[2]);
  }
  return [...endpoints].sort();
}

function buildInventory() {
  const files = fs.readdirSync(PAGES_DIR).filter((f) => f.endsWith('.js'));
  const inventory = [];

  for (const file of files) {
    const filePath = path.join(PAGES_DIR, file);
    const content = read(filePath);
    const page = path.basename(file, '.js');
    const pageRows = parseButtons(content, page, filePath);
    const endpoints = inferEndpoints(content);
    pageRows.forEach((row) => {
      row.endpoints = endpoints;
    });
    inventory.push(...pageRows);
  }

  inventory.sort((a, b) => {
    if (a.page !== b.page) return a.page.localeCompare(b.page);
    if (a.control_selector !== b.control_selector) return a.control_selector.localeCompare(b.control_selector);
    return a.source_line - b.source_line;
  });

  return inventory;
}

function writeOutputs(inventory) {
  ensureDir(OUT_DIR);
  const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Riyadh' }).format(new Date());
  const payload = {
    generated_at: new Date().toISOString(),
    generated_by: 'scripts/build_ui_workflow_inventory.js',
    total_actions: inventory.length,
    actions: inventory,
  };
  const dated = path.join(OUT_DIR, `ui-workflow-inventory-${date}.json`);
  const latest = path.join(OUT_DIR, 'ui-workflow-inventory-latest.json');
  fs.writeFileSync(dated, JSON.stringify(payload, null, 2));
  fs.writeFileSync(latest, JSON.stringify(payload, null, 2));
  console.log(`Inventory written: ${path.relative(ROOT, dated)}`);
  console.log(`Inventory updated: ${path.relative(ROOT, latest)}`);
}

function main() {
  const inventory = buildInventory();
  writeOutputs(inventory);
}

main();
