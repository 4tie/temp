/* =================================================================
   RESULT EXPLORER — shared detailed backtest result modal
   Exposes: window.ResultExplorer
   ================================================================= */

window.ResultExplorer = (() => {
  const _PENDING_STRATEGY_RERUN_KEY = '4tie_pending_strategy_intelligence_rerun';
  const PAGE_SIZE = 25;
  const DEFAULT_SORTS = {
    trades: { key: 'closeTimestamp', dir: -1, filter: '', page: 1 },
    per_pair: { key: 'profit_total_pct', dir: -1, filter: '' },
    exit_reason_summary: { key: 'profit_total_pct', dir: -1, filter: '' },
    results_per_enter_tag: { key: 'profit_total_pct', dir: -1, filter: '' },
    mix_tag_stats: { key: 'profit_total_pct', dir: -1, filter: '' },
    left_open_trades: { key: 'profit_total_pct', dir: -1, filter: '' },
  };

  let _modal = null;
  let _body = null;
  let _title = null;
  let _state = {
    runId: null,
    detail: null,
    raw: null,
    activeTab: 'overview',
    tables: _cloneSorts(),
  };

  function _cloneSorts() {
    return Object.fromEntries(
      Object.entries(DEFAULT_SORTS).map(([key, value]) => [key, { ...value }])
    );
  }

  function _ensureModal() {
    if (_modal) return;
    _modal = Modal.make({
      id: 'result-explorer-modal',
      title: 'Result Explorer',
      body: '<div class="result-explorer__loading">Loading…</div>',
      className: 'modal--result-explorer',
      dialogClass: 'result-explorer-modal__dialog',
      bodyClass: 'result-explorer-modal__body',
    });
    _body = _modal.querySelector('.modal__body');
    _title = _modal.querySelector('.modal__title');
  }

  async function open(runId) {
    if (!runId) return;
    _ensureModal();
    _state = {
      runId,
      detail: null,
      raw: null,
      activeTab: 'overview',
      tables: _cloneSorts(),
    };

    DOM.setText(_title, `Result Explorer: ${FMT.truncate(runId, 28)}`);
    DOM.setHTML(_body, '<div class="result-explorer__loading">Loading run details…</div>');
    Modal.open(_modal);

    try {
      const [detail, raw] = await Promise.all([
        API.getRun(runId),
        API.getRunRaw(runId).catch(() => null),
      ]);
      _state.detail = detail;
      _state.raw = raw || {
        run_id: runId,
        raw_artifact_missing: true,
        artifact: detail?.results?.raw_artifact || { available: false },
        payload: detail?.results || {},
        data_source: 'parsed_results',
      };
      _render();
    } catch (err) {
      DOM.setHTML(
        _body,
        `<div class="empty-state">Failed to load result explorer.<br>${_esc(err.message)}</div>`
      );
    }
  }

  function _render() {
    const detail = _state.detail || {};
    const results = detail.results || {};
    const meta = detail.meta || {};
    const intelligence = results.strategy_intelligence || {};
    const intelligenceSummary = intelligence.summary || {};
    const displayStrategy = meta.display_strategy || meta.strategy || results.display_strategy || results.strategy_name || 'Run';
    const displayVersion = meta.display_version || meta.strategy_version || results.display_version || null;
    const summary = results.summary || {};
    const profitPct = intelligenceSummary.net_profit_pct ?? FMT.resultProfitPercent(summary);
    const winRate = FMT.resultWinRate(summary.winRate ?? summary.win_rate);
    const drawdownPct = FMT.resultDrawdownPercent(summary.maxDrawdown ?? summary.max_drawdown_pct);
    const tradesPerDay = intelligenceSummary.trades_per_day;
    const profitFactor = intelligenceSummary.profit_factor ?? summary.profitFactor ?? summary.profit_factor;
    const winRateTone = FMT.toneWinRate(winRate);
    const drawdownTone = FMT.toneDrawdown(drawdownPct);
    const profitFactorTone = FMT.toneRatio(profitFactor, 1);

    DOM.setText(
      _title,
      `${displayVersion ? `${displayStrategy} · ${displayVersion}` : displayStrategy} · ${FMT.truncate(_state.runId, 30)}`
    );

    DOM.setHTML(
      _body,
      `
        <div class="result-explorer" data-tab-group>
          <div class="result-explorer__hero">
            <div class="result-explorer__hero-main">
              <div class="result-explorer__hero-title">${_esc(displayVersion ? `${displayStrategy} · ${displayVersion}` : displayStrategy)}</div>
              <div class="result-explorer__hero-meta">
                <span>${_esc(meta.timeframe || summary.timeframe || '—')}</span>
                <span>${_esc(meta.exchange || '—')}</span>
                <span>${_esc(meta.timerange || results.run_metadata?.timerange || '—')}</span>
                <span>${_esc(_state.runId || '—')}</span>
              </div>
              <div style="margin-top:8px">
                <button class="btn btn--secondary btn--sm" data-action="apply-config">Apply Run Config</button>
                <button class="btn btn--primary btn--sm" data-action="improve-rerun" style="margin-left:8px">Improve & Re-run</button>
              </div>
            </div>
            <div class="result-explorer__hero-stats">
              ${_heroStat('Net P/L', intelligenceSummary.net_profit_abs != null ? FMT.currency(intelligenceSummary.net_profit_abs) : _formatPct(profitPct), _toneFromNumber(intelligenceSummary.net_profit_abs ?? profitPct))}
              ${_heroStat('Profit %', _formatPct(profitPct), _toneFromNumber(profitPct))}
              ${_heroStat('Trades', FMT.integer(summary.totalTrades))}
              ${_heroStat('Trades / Day', tradesPerDay != null ? FMT.number(tradesPerDay, 2) : '—')}
              ${_heroStat('Win Rate', _formatPct(winRate, 1, false), winRateTone)}
              ${_heroStat('Drawdown', _formatPct(drawdownPct, 1, false), drawdownTone)}
              ${_heroStat('Profit Factor', FMT.number(profitFactor, 2), profitFactorTone)}
            </div>
          </div>

          <div class="result-explorer__tabs" role="tablist">
            ${_tabButton('overview', 'Overview')}
            ${_tabButton('intelligence', 'Intelligence')}
            ${_tabButton('charts', 'Charts')}
            ${_tabButton('trades', 'Trades')}
            ${_tabButton('per-pair', 'Per Pair')}
            ${_tabButton('tags', 'Tags & Exits')}
            ${_tabButton('periods', 'Periods')}
            ${_tabButton('diagnostics', 'Diagnostics')}
            ${_tabButton('warnings', 'Data Integrity Warnings')}
            ${_tabButton('raw', 'Raw')}
          </div>

          <section class="tab-panel" data-tab-panel="overview">${_renderOverviewTab(detail)}</section>
          <section class="tab-panel" data-tab-panel="intelligence">${_renderIntelligenceTab(detail)}</section>
          <section class="tab-panel" data-tab-panel="charts">${_renderChartsTab(results)}</section>
          <section class="tab-panel" data-tab-panel="trades">${_renderTradesTab(results)}</section>
          <section class="tab-panel" data-tab-panel="per-pair">${_renderPerPairTab(results)}</section>
          <section class="tab-panel" data-tab-panel="tags">${_renderTagsTab(results)}</section>
          <section class="tab-panel" data-tab-panel="periods">${_renderPeriodsTab(results)}</section>
          <section class="tab-panel" data-tab-panel="diagnostics">${_renderDiagnosticsTab(detail)}</section>
          <section class="tab-panel" data-tab-panel="warnings">${_renderWarningsTab(detail)}</section>
          <section class="tab-panel" data-tab-panel="raw">${_renderRawTab()}</section>
        </div>
      `
    );

    Tabs.init(_body.querySelector('[data-tab-group]'));
    _activateTab(_state.activeTab);
    _bind();
  }

  function _bind() {
    const tabsWrap = _body.querySelector('.result-explorer__tabs');
    if (tabsWrap) {
      DOM.on(tabsWrap, 'wheel', (event) => {
        // Make mouse-wheel usable for the horizontal tab strip.
        if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
        event.preventDefault();
        tabsWrap.scrollLeft += event.deltaY;
      }, { passive: false });
    }

    _body.querySelectorAll('[data-tab]').forEach((el) => {
      DOM.on(el, 'click', () => {
        _state.activeTab = el.dataset.tab || 'overview';
      });
    });

    _body.querySelectorAll('[data-table-sort]').forEach((el) => {
      DOM.on(el, 'click', () => {
        const [table, key] = (el.dataset.tableSort || '').split(':');
        if (!table || !key) return;
        const state = _state.tables[table];
        if (!state) return;
        if (state.key === key) state.dir *= -1;
        else state.key = key, state.dir = -1;
        if (table === 'trades') state.page = 1;
        _render();
      });
    });

    _body.querySelectorAll('[data-table-filter]').forEach((el) => {
      DOM.on(el, 'input', () => {
        const table = el.dataset.tableFilter;
        const state = _state.tables[table];
        if (!state) return;
        state.filter = el.value || '';
        if (table === 'trades') state.page = 1;
        _render();
      });
    });

    _body.querySelectorAll('[data-trades-page]').forEach((el) => {
      DOM.on(el, 'click', () => {
        const state = _state.tables.trades;
        state.page = Math.max(1, state.page + parseInt(el.dataset.tradesPage, 10));
        _render();
      });
    });

    const copyRaw = _body.querySelector('[data-action="copy-raw"]');
    if (copyRaw) {
      DOM.on(copyRaw, 'click', async () => {
        try {
          await navigator.clipboard.writeText(_rawJson());
          Toast.success('Raw JSON copied.');
        } catch {
          Toast.error('Copy failed.');
        }
      });
    }

    const applyConfig = _body.querySelector('[data-action="apply-config"]');
    if (applyConfig) {
      DOM.on(applyConfig, 'click', async () => {
        try {
          const res = await API.applyRunConfig(_state.runId);
          if (res.warnings?.length) {
            Toast.warning(`Config applied with warnings: ${res.warnings.join(' | ')}`);
          } else {
            Toast.success('Run config applied.');
          }
        } catch (err) {
          Toast.error('Failed to apply run config: ' + err.message);
        }
      });
    }

    const improveRerun = _body.querySelector('[data-action="improve-rerun"]');
    if (improveRerun) {
      DOM.on(improveRerun, 'click', () => {
        if (!_state.runId) return;
        try {
          sessionStorage.setItem(_PENDING_STRATEGY_RERUN_KEY, JSON.stringify({
            runId: _state.runId,
            intelligence: _state.detail?.results?.strategy_intelligence || null,
          }));
        } catch {}
        if (AppState.get('activePage') === 'backtesting') {
          window.BacktestPage?.refresh?.();
        } else {
          window.App?.navigate?.('backtesting');
        }
      });
    }
  }

  function _renderOverviewTab(detail) {
    const results = detail.results || {};
    const meta = detail.meta || {};
    const summary = results.summary || {};
    const balance = results.balance_metrics || {};
    const risk = results.risk_metrics || {};
    const run = results.run_metadata || {};
    const config = results.config_snapshot || {};
    const performance = [
      ['Total Profit %', _formatPct(FMT.resultProfitPercent(summary), 2), FMT.toneProfit(FMT.resultProfitPercent(summary))],
      ['Profit (abs)', FMT.currency(summary.totalProfit), FMT.toneProfit(summary.totalProfit)],
      ['Avg Profit %', _formatPct(summary.avgProfitPct, 2, false), FMT.toneProfit(summary.avgProfitPct)],
      ['Profit Factor', FMT.number(summary.profitFactor, 3), FMT.toneRatio(summary.profitFactor, 1)],
      ['Win Rate', _formatPct(FMT.resultWinRate(summary.winRate), 1, false), FMT.toneWinRate(summary.winRate)],
      ['CAGR', _formatPct(summary.cagr, 2, false), FMT.toneProfit(summary.cagr)],
      ['Calmar', FMT.number(summary.calmarRatio, 3), FMT.toneRatio(summary.calmarRatio, 1)],
      ['Sortino', FMT.number(summary.sortinoRatio, 3), FMT.toneRatio(summary.sortinoRatio, 1)],
      ['Sharpe', FMT.number(summary.sharpeRatio, 3), FMT.toneRatio(summary.sharpeRatio, 1)],
      ['SQN', FMT.number(summary.sqn, 3), FMT.toneRatio(summary.sqn, 1)],
      ['Expectancy', FMT.number(summary.expectancy, 4), FMT.toneProfit(summary.expectancy)],
      ['Expectancy Ratio', FMT.number(summary.expectancyRatio, 3), FMT.toneRatio(summary.expectancyRatio, 1)],
    ];

    const wallet = [
      ['Starting Balance', _formatCurrencyOrNA(balance.starting_balance)],
      ['Final Balance', _formatCurrencyOrNA(balance.final_balance), FMT.toneProfit((balance.final_balance ?? 0) - (balance.starting_balance ?? 0))],
      ['Wallet Config', _formatCurrencyOrNA(balance.dry_run_wallet)],
      ['Long Profit', `${_formatCurrencyOrNA(balance.profit_total_long_abs)} / ${_formatPct(balance.profit_total_long_pct)}`, FMT.toneProfit(balance.profit_total_long_abs)],
      ['Short Profit', `${_formatCurrencyOrNA(balance.profit_total_short_abs)} / ${_formatPct(balance.profit_total_short_pct)}`, FMT.toneProfit(balance.profit_total_short_abs)],
      ['Trading Volume', _formatCurrencyOrNA(summary.tradingVolume)],
      ['Avg Stake', _formatCurrencyOrNA(summary.avgStakeAmount)],
      ['Stake Amount', _esc(summary.stakeAmount || '—')],
      ['Stake Currency', _esc(summary.stakeCurrency || '—')],
      ['Market Change', _formatPct(summary.marketChange, 2, false), FMT.toneProfit(summary.marketChange)],
    ];

    const riskCards = [
      ['Max Drawdown', _formatPct(FMT.resultDrawdownPercent(summary.maxDrawdown), 2, false), FMT.toneDrawdown(summary.maxDrawdown)],
      ['Max Drawdown (abs)', FMT.currency(summary.maxDrawdownAbs), 'red'],
      ['Max Relative Drawdown', _formatPct(risk.max_relative_drawdown, 2, false), FMT.toneDrawdown(risk.max_relative_drawdown)],
      ['Drawdown Start', FMT.ts(risk.drawdown_start), 'red'],
      ['Drawdown End', FMT.ts(risk.drawdown_end), 'red'],
      ['Drawdown Duration', _esc(risk.drawdown_duration || '—'), 'red'],
      ['Max Consecutive Wins', FMT.integer(risk.max_consecutive_wins), 'green'],
      ['Max Consecutive Losses', FMT.integer(risk.max_consecutive_losses), 'red'],
      ['Best Day', `${_formatPct(summary.bestDayPct, 2, false)} / ${FMT.currency(summary.bestDayAbs)}`, FMT.toneProfit(summary.bestDayPct)],
      ['Worst Day', `${_formatPct(summary.worstDayPct, 2, false)} / ${FMT.currency(summary.worstDayAbs)}`, 'red'],
      ['Winning Days', FMT.integer(summary.winningDays), 'green'],
      ['Losing Days', FMT.integer(summary.losingDays), 'red'],
    ];

    const runtime = [
      ['Run ID', _esc(_state.runId)],
      ['Strategy', _esc(meta.display_strategy || meta.strategy || run.strategy_name || '—')],
      ['Strategy Version', _esc(meta.display_version || meta.strategy_version || results.display_version || '—')],
      ['Strategy Class', _esc(meta.strategy_class || '—')],
      ['Exchange', _esc(meta.exchange || '—')],
      ['Timeframe', _esc(run.timeframe || meta.timeframe || '—')],
      ['Timerange', _esc(run.timerange || meta.timerange || '—')],
      ['Backtest Start', FMT.ts(run.backtest_start || summary.backtestStart)],
      ['Backtest End', FMT.ts(run.backtest_end || summary.backtestEnd)],
      ['Run Started', FMT.ts(meta.started_at)],
      ['Run Completed', FMT.ts(meta.completed_at)],
      ['Trades / Day', FMT.number(run.trades_per_day, 2)],
      ['Backtest Days', FMT.integer(run.backtest_days)],
      ['Long Trades', FMT.integer(summary.tradeCountLong)],
      ['Short Trades', FMT.integer(summary.tradeCountShort)],
      ['Best Pair', _esc(_pairLabel(summary.bestPair) || '—')],
      ['Worst Pair', _esc(_pairLabel(summary.worstPair) || '—')],
    ];

    const behavior = [
      ['Stoploss', _formatPct(config.stoploss, 2, false)],
      ['Trailing Stop', _bool(config.trailing_stop)],
      ['Trailing Positive', _formatPct(config.trailing_stop_positive, 2, false)],
      ['Trailing Offset', _formatPct(config.trailing_stop_positive_offset, 2, false)],
      ['Exit Signal', _bool(config.use_exit_signal)],
      ['Exit Profit Only', _bool(config.exit_profit_only)],
      ['Exit Offset', _formatPct(config.exit_profit_offset, 2, false)],
      ['Ignore ROI On Entry', _bool(config.ignore_roi_if_entry_signal)],
      ['Custom Stoploss', _bool(config.use_custom_stoploss)],
      ['Protections', _bool(config.enable_protections)],
      ['ROI Table', _jsonMini(config.minimal_roi || {})],
      ['Pairlist', _jsonMini(config.pairlist || [])],
    ];

    return `
      <div class="result-explorer__section">
        <div class="section-heading">Performance</div>
        <div class="detail-grid">${performance.map(([k, v, t]) => _detailItem(k, v, t)).join('')}</div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Wallet & Exposure</div>
        <div class="detail-grid">${wallet.map(([k, v, t]) => _detailItem(k, v, t)).join('')}</div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Risk</div>
        <div class="detail-grid">${riskCards.map(([k, v, t]) => _detailItem(k, v, t)).join('')}</div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Run Metadata</div>
        <div class="detail-grid">${runtime.map(([k, v]) => _detailItem(k, v)).join('')}</div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Strategy Runtime Settings</div>
        <div class="detail-grid">${behavior.map(([k, v]) => _detailItem(k, v)).join('')}</div>
      </div>
    `;
  }

  function _renderWarningsTab(detail) {
    const diagnostics = (detail?.results || {}).diagnostics || {};
    const allWarnings = diagnostics.integrity_warnings || diagnostics.warnings || [];
    const warnings = allWarnings.filter((warning) => {
      const text = String(warning || '').toLowerCase();
      return text.includes('missing metric') || text.includes('corrected metric mismatch');
    });

    if (!warnings.length) {
      return '<div class="empty-state">No data integrity warnings for this run.</div>';
    }

    return `
      <div class="result-explorer__section">
        <div class="section-heading">Data Integrity Warnings</div>
        <div class="result-explorer__list">
          ${warnings.map((warning) => `<div class="result-explorer__list-item">${_esc(warning)}</div>`).join('')}
        </div>
      </div>
    `;
  }

  function _renderChartsTab(results) {
    const daily = results.daily_profit || results.equity_curve || [];
    const cumulativeSeries = daily.map((row) => ({ label: row.date, value: row.cumulative || 0 }));
    const dailySeries = daily.map((row) => ({ label: row.date, value: row.profit || 0 }));
    const drawdownSeries = _buildDrawdownSeries(cumulativeSeries);
    const monthSeries = ((results.periodic_breakdown || {}).month || []).map((row) => ({
      label: row.date,
      value: row.profit_abs || 0,
    }));

    return `
      <div class="result-explorer__chart-grid">
        ${_chartCard('Cumulative Profit', _lineChart(cumulativeSeries, { color: 'var(--violet)' }), _seriesMeta(cumulativeSeries))}
        ${_chartCard('Daily Profit', _barChart(dailySeries), _seriesMeta(dailySeries))}
        ${_chartCard('Drawdown', _lineChart(drawdownSeries, { color: 'var(--red)', area: false }), _seriesMeta(drawdownSeries))}
        ${_chartCard('Monthly Aggregate', _barChart(monthSeries), _seriesMeta(monthSeries))}
      </div>
    `;
  }

  function _renderTradesTab(results) {
    const state = _state.tables.trades;
    const trades = _filteredTrades(results.trades || [], state.filter);
    const sorted = _sortRows(trades, state.key, state.dir);
    const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
    const page = Math.min(state.page, totalPages);
    _state.tables.trades.page = page;
    const start = (page - 1) * PAGE_SIZE;
    const pageRows = sorted.slice(start, start + PAGE_SIZE);

    return `
      <div class="result-explorer__table-tools">
        <input class="form-input" type="text" placeholder="Filter trades by pair, tag, exit, direction…" value="${_esc(state.filter)}" data-table-filter="trades">
        <div class="result-explorer__table-meta">${sorted.length} trade(s)</div>
      </div>
      ${_table(
        [
          ['pair', 'Pair'],
          ['direction', 'Dir'],
          ['openDate', 'Open'],
          ['closeDate', 'Close'],
          ['duration', 'Duration'],
          ['stakeAmount', 'Stake'],
          ['profitPct', 'Profit %'],
          ['profit', 'Profit'],
          ['minRate', 'MAE'],
          ['maxRate', 'MFE'],
          ['exitReason', 'Exit'],
        ],
        pageRows.map((trade) => [
          `<span class="font-mono">${_esc(trade.pair)}</span>`,
          _esc(trade.direction || 'long'),
          FMT.ts(trade.openDate),
          FMT.ts(trade.closeDate),
          _esc(trade.duration || '—'),
          FMT.currency(trade.stakeAmount),
          `<span class="text-${_toneFromNumber(trade.profitPct)}">${_formatPct(trade.profitPct)}</span>`,
          `<span class="text-${_toneFromNumber(trade.profit)}">${FMT.currency(trade.profit)}</span>`,
          FMT.number(trade.minRate, 4),
          FMT.number(trade.maxRate, 4),
          _esc(trade.exitReason || '—'),
        ]),
        'trades'
      )}
      <div class="result-explorer__pager">
        <button class="btn btn--secondary btn--sm" data-trades-page="-1" ${page <= 1 ? 'disabled' : ''}>Prev</button>
        <span>Page ${page} / ${totalPages}</span>
        <button class="btn btn--secondary btn--sm" data-trades-page="1" ${page >= totalPages ? 'disabled' : ''}>Next</button>
      </div>
    `;
  }

  function _renderPerPairTab(results) {
    const state = _state.tables.per_pair;
    const filter = (state.filter || '').trim().toLowerCase();
    const rows = (results.per_pair || []).filter((row) => !filter || String(row.pair || '').toLowerCase().includes(filter));
    const sorted = _sortRows(rows, state.key, state.dir);

    return `
      <div class="result-explorer__table-tools">
        <input class="form-input" type="text" placeholder="Filter pairs…" value="${_esc(state.filter)}" data-table-filter="per_pair">
        <div class="result-explorer__table-meta">${sorted.length} pair row(s)</div>
      </div>
      ${_table(
        [
          ['pair', 'Pair'],
          ['trades', 'Trades'],
          ['profit_total_pct', 'Profit %'],
          ['profit_total_abs', 'Profit'],
          ['winrate', 'Win Rate'],
          ['max_drawdown', 'Drawdown'],
          ['profit_factor', 'Factor'],
          ['expectancy', 'Expectancy'],
          ['sharpe', 'Sharpe'],
          ['duration_avg', 'Avg Duration'],
        ],
        sorted.map((row) => [
          `<span class="font-mono">${_esc(row.pair)}</span>`,
          FMT.integer(row.trades),
          `<span class="text-${_toneFromNumber(row.profit_total_pct)}">${_formatPct(row.profit_total_pct)}</span>`,
          `<span class="text-${_toneFromNumber(row.profit_total_abs)}">${FMT.currency(row.profit_total_abs)}</span>`,
          `<span class="text-${FMT.toneWinRate(row.winrate)}">${_formatPct(row.winrate, 1, false)}</span>`,
          `<span class="text-${FMT.toneDrawdown(row.max_drawdown)}">${_formatPct(row.max_drawdown, 1, false)}</span>`,
          `<span class="text-${FMT.toneRatio(row.profit_factor, 1)}">${FMT.number(row.profit_factor, 3)}</span>`,
          `<span class="text-${FMT.toneProfit(row.expectancy)}">${FMT.number(row.expectancy, 4)}</span>`,
          `<span class="text-${FMT.toneRatio(row.sharpe, 1)}">${FMT.number(row.sharpe, 3)}</span>`,
          _esc(row.duration_avg || '—'),
        ]),
        'per_pair'
      )}
    `;
  }

  function _renderTagsTab(results) {
    return `
      ${_statsSection('Exit Reason Summary', 'exit_reason_summary', results.exit_reason_summary || [])}
      ${_statsSection('Enter Tag Summary', 'results_per_enter_tag', results.results_per_enter_tag || [])}
      ${_statsSection('Mixed Tag Summary', 'mix_tag_stats', results.mix_tag_stats || [])}
      ${_statsSection('Left Open Trades', 'left_open_trades', results.left_open_trades || [])}
    `;
  }

  function _renderPeriodsTab(results) {
    const periodic = results.periodic_breakdown || {};
    const periodKeys = ['day', 'week', 'month', 'year', 'weekday'].filter((key) => Array.isArray(periodic[key]) && periodic[key].length);
    if (!periodKeys.length) {
      return '<div class="empty-state">No periodic breakdown data available for this run.</div>';
    }

    const chartKey = periodKeys.includes('month') ? 'month' : periodKeys[0];
    const chartSeries = (periodic[chartKey] || []).map((row) => ({
      label: row.date,
      value: row.profit_abs || 0,
    }));

    return `
      <div class="result-explorer__section">
        <div class="section-heading">${_esc(chartKey)} Aggregate</div>
        ${_chartCard(`${_esc(chartKey)} profit`, _barChart(chartSeries), _seriesMeta(chartSeries))}
      </div>
      ${periodKeys.map((key) => _periodTable(key, periodic[key] || [])).join('')}
    `;
  }

  function _renderDiagnosticsTab(detail) {
    const results = detail.results || {};
    const meta = detail.meta || {};
    const diagnostics = results.diagnostics || {};
    const rawArtifact = diagnostics.raw_artifact || results.raw_artifact || {};
    const warnings = diagnostics.warnings || results.warnings || [];
    const command = Array.isArray(meta.command) ? meta.command.join(' ') : '';

    return `
      <div class="result-explorer__section">
        <div class="section-heading">Diagnostics</div>
        <div class="detail-grid">
          ${_detailItem('Rejected Signals', FMT.integer(diagnostics.rejected_signals))}
          ${_detailItem('Canceled Entry Orders', FMT.integer(diagnostics.canceled_entry_orders))}
          ${_detailItem('Canceled Trade Entries', FMT.integer(diagnostics.canceled_trade_entries))}
          ${_detailItem('Replaced Entry Orders', FMT.integer(diagnostics.replaced_entry_orders))}
          ${_detailItem('Timed Out Entry Orders', FMT.integer(diagnostics.timedout_entry_orders))}
          ${_detailItem('Timed Out Exit Orders', FMT.integer(diagnostics.timedout_exit_orders))}
          ${_detailItem('Raw Artifact', rawArtifact.available ? _esc(rawArtifact.file_name || 'available') : 'Unavailable')}
          ${_detailItem('Artifact Source', _esc(_state.raw?.data_source || '—'))}
        </div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Warnings</div>
        ${warnings.length ? `<div class="result-explorer__list">${warnings.map((warning) => `<div class="result-explorer__list-item">${_esc(warning)}</div>`).join('')}</div>` : '<div class="empty-state">No warnings recorded.</div>'}
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Locks</div>
        ${_jsonPanel(diagnostics.locks || [], 'No locks recorded.')}
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Run Metadata</div>
        ${_jsonPanel(meta, 'No metadata available.')}
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Command</div>
        ${command ? `<pre class="result-explorer__json">${_esc(command)}</pre>` : '<div class="empty-state">No command recorded.</div>'}
      </div>
    `;
  }

  function _intelligenceComparisonRows(comparison) {
    if (Array.isArray(comparison?.highlights) && comparison.highlights.length) {
      return comparison.highlights;
    }
    if (!comparison?.metrics) return [];
    return ['profit_percent', 'win_rate', 'profit_factor', 'max_drawdown']
      .map((key) => comparison.metrics[key])
      .filter(Boolean);
  }

  function _intelligenceSuggestionGroups(intelligence) {
    const groups = intelligence?.suggestion_groups || {};
    const suggestions = Array.isArray(intelligence?.suggestions) ? intelligence.suggestions : [];
    const quickParams = Array.isArray(groups.quick_params)
      ? groups.quick_params
      : suggestions.filter((item) => item?.auto_applicable);
    const manualGuidance = Array.isArray(groups.manual_guidance)
      ? groups.manual_guidance
      : suggestions.filter((item) => !item?.auto_applicable);
    return { quickParams, manualGuidance };
  }

  function _visibleIntelligenceIssues(diagnosis) {
    const primary = diagnosis?.primary || {};
    const issues = Array.isArray(diagnosis?.issues) ? diagnosis.issues : [];
    return issues.filter((issue) => {
      if (!issue) return false;
      const sameId = primary.id && issue.id && String(primary.id) === String(issue.id);
      const sameTitle = primary.title && issue.title && String(primary.title) === String(issue.title);
      return !sameId && !sameTitle;
    });
  }

  function _metricSnapshotText(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return '';
    const parts = [];
    if (FMT.toNumber(snapshot.total_trades) != null) parts.push(`${FMT.integer(snapshot.total_trades)} trades`);
    if (FMT.toNumber(snapshot.win_rate_pct) != null) parts.push(`${_formatPct(snapshot.win_rate_pct, 1, false)} win rate`);
    if (FMT.toNumber(snapshot.profit_factor) != null) parts.push(`Profit factor ${FMT.number(snapshot.profit_factor, 2)}`);
    if (FMT.toNumber(snapshot.total_profit_pct) != null) parts.push(`${_formatPct(snapshot.total_profit_pct)} return`);
    if (FMT.toNumber(snapshot.max_drawdown_pct) != null) parts.push(`${_formatPct(snapshot.max_drawdown_pct, 1, false)} max drawdown`);
    return parts.join(' · ');
  }

  function _renderIntelligenceTab(detail) {
    const results = detail.results || {};
    const intelligence = results.strategy_intelligence || {};
    const diagnosis = intelligence.diagnosis || {};
    const primary = diagnosis.primary || {};
    const issues = _visibleIntelligenceIssues(diagnosis);
    const { quickParams, manualGuidance } = _intelligenceSuggestionGroups(intelligence);
    const comparison = intelligence.comparison_to_parent || {};
    const comparisonRows = _intelligenceComparisonRows(comparison);
    const primaryEvidence = primary.evidence || 'No metric-backed evidence was captured.';
    const primaryMetrics = _metricSnapshotText(primary.metric_snapshot);
    const secondaryIssues = Array.isArray(diagnosis.secondary_issues) ? diagnosis.secondary_issues : [];

    if (!issues.length && !quickParams.length && !manualGuidance.length && !primary.title) {
      return '<div class="empty-state">No strategy intelligence is available for this run yet.</div>';
    }

    return `
      <div class="result-explorer__section">
        <div class="section-heading">Primary Diagnosis</div>
        <div class="detail-grid">
          ${_detailItem('Issue', _esc(primary.title || '—'), _severityTone(primary.severity))}
          ${_detailItem('Severity', _esc(primary.severity || '—'), _severityTone(primary.severity))}
          ${_detailItem('Confidence', _esc(primary.confidence || '—'))}
          ${_detailItem('Why It Matters', _esc(primary.explanation || '—'))}
        </div>
        <div class="result-explorer__stack" style="margin-top:12px">
          <article class="result-explorer__insight-card result-explorer__insight-card--${_severityTone(primary.severity)}">
            <div class="result-explorer__insight-title">Metric Evidence</div>
            <div class="result-explorer__insight-body">${_esc(primaryEvidence)}</div>
            ${primaryMetrics ? `<div class="result-explorer__insight-meta">${_esc(primaryMetrics)}</div>` : ''}
            ${primary.confidence_note ? `<div class="result-explorer__insight-meta">${_esc(primary.confidence_note)}</div>` : ''}
          </article>
        </div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Detected Issues</div>
        <div class="result-explorer__stack">
          ${issues.length ? issues.map((issue) => `
            <article class="result-explorer__insight-card result-explorer__insight-card--${_severityTone(issue.severity)}">
              <div class="result-explorer__insight-title">${_esc(issue.title || 'Issue')}</div>
              <div class="result-explorer__insight-body">${_esc(issue.explanation || issue.evidence || '')}</div>
              ${issue.evidence ? `<div class="result-explorer__insight-meta">Metric evidence: ${_esc(issue.evidence)}</div>` : ''}
            </article>
          `).join('') : '<div class="empty-state">No secondary issues were detected beyond the primary diagnosis.</div>'}
          ${secondaryIssues.length ? secondaryIssues.slice(0, 3).map((item) => `
            <article class="result-explorer__insight-card result-explorer__insight-card--amber">
              <div class="result-explorer__insight-title">Secondary Issue</div>
              <div class="result-explorer__insight-body">${_esc(item)}</div>
            </article>
          `).join('') : ''}
        </div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Quick Parameter Actions</div>
        <div class="result-explorer__stack">
          ${quickParams.length ? quickParams.map((item) => `
            <article class="result-explorer__insight-card">
              <div class="result-explorer__insight-title">${_esc(item.title || 'Suggestion')}</div>
              <div class="result-explorer__insight-body">${_esc(item.description || '')}</div>
              <div class="result-explorer__insight-meta">${_esc(`Quick Params can apply ${item.parameter} = ${item.suggested_value}`)}</div>
              ${item.evidence ? `<div class="result-explorer__insight-meta">Metric evidence: ${_esc(item.evidence)}</div>` : ''}
            </article>
          `).join('') : '<div class="empty-state">No direct quick-parameter changes were identified for this run.</div>'}
        </div>
      </div>
      <div class="result-explorer__section">
        <div class="section-heading">Manual Guidance</div>
        <div class="result-explorer__stack">
          ${manualGuidance.length ? manualGuidance.map((item) => `
            <article class="result-explorer__insight-card">
              <div class="result-explorer__insight-title">${_esc(item.title || 'Suggestion')}</div>
              <div class="result-explorer__insight-body">${_esc(item.description || '')}</div>
              <div class="result-explorer__insight-meta">${_esc('Manual guidance only. No strategy code will be changed automatically.')}</div>
              ${item.evidence ? `<div class="result-explorer__insight-meta">Metric evidence: ${_esc(item.evidence)}</div>` : ''}
            </article>
          `).join('') : '<div class="empty-state">No manual follow-up guidance was generated for this run.</div>'}
        </div>
      </div>
      ${comparisonRows.length ? `
        <div class="result-explorer__section">
          <div class="section-heading">Compared To Parent Run</div>
          <div class="detail-grid">
            ${comparisonRows.map((row) => _detailItem(
              row.label,
              row.diff == null
                ? '—'
                : (row.format === 'currency'
                  ? FMT.currency(row.diff)
                  : row.format === 'integer'
                    ? `${row.diff > 0 ? '+' : ''}${FMT.integer(row.diff)}`
                    : row.format === 'ratio'
                      ? `${row.diff > 0 ? '+' : ''}${FMT.number(row.diff, 2)}`
                      : FMT.pct(row.diff, 1, true)),
              row.diff == null ? '' : (row.higher_is_better === false ? _toneFromNumber(-row.diff) : _toneFromNumber(row.diff))
            )).join('')}
          </div>
        </div>
      ` : ''}
    `;
  }

  function _renderRawTab() {
    const raw = _state.raw || {};
    const artifact = raw.artifact || {};
    const notice = raw.raw_artifact_missing
      ? '<div class="result-explorer__notice">Raw artifact unavailable for this run. Showing normalized parsed JSON instead.</div>'
      : `<div class="result-explorer__notice result-explorer__notice--ok">Raw artifact loaded from ${_esc(artifact.file_name || 'artifact')}.</div>`;

    return `
      <div class="result-explorer__table-tools">
        <div class="result-explorer__table-meta">${_esc(raw.data_source || 'unknown')}</div>
        <button class="btn btn--secondary btn--sm" data-action="copy-raw">Copy JSON</button>
      </div>
      ${notice}
      <pre class="result-explorer__json">${_esc(_rawJson())}</pre>
    `;
  }

  function _periodTable(label, rows) {
    return `
      <div class="result-explorer__section">
        <div class="section-heading">${_esc(label)}</div>
        ${_table(
          [
            ['date', 'Period'],
            ['trades', 'Trades'],
            ['wins', 'Wins'],
            ['losses', 'Losses'],
            ['draws', 'Draws'],
            ['win_rate', 'Win Rate'],
            ['profit_abs', 'Profit'],
            ['profit_factor', 'Factor'],
            ['cumulative_profit', 'Cumulative'],
          ],
          rows.map((row) => [
            _esc(row.date || '—'),
            FMT.integer(row.trades),
            FMT.integer(row.wins),
            FMT.integer(row.losses),
            FMT.integer(row.draws),
            _formatPct(row.win_rate, 1, false),
            `<span class="text-${_toneFromNumber(row.profit_abs)}">${FMT.currency(row.profit_abs)}</span>`,
            FMT.number(row.profit_factor, 3),
            FMT.currency(row.cumulative_profit),
          ])
        )}
      </div>
    `;
  }

  function _statsSection(title, key, rows) {
    const state = _state.tables[key];
    const filter = (state.filter || '').trim().toLowerCase();
    const filtered = rows.filter((row) => !filter || String(row.label || row.key || '').toLowerCase().includes(filter));
    const sorted = _sortRows(filtered, state.key, state.dir);

    return `
      <div class="result-explorer__section">
        <div class="section-heading">${_esc(title)}</div>
        <div class="result-explorer__table-tools">
          <input class="form-input" type="text" placeholder="Filter ${_esc(title).toLowerCase()}…" value="${_esc(state.filter)}" data-table-filter="${key}">
          <div class="result-explorer__table-meta">${sorted.length} row(s)</div>
        </div>
        ${_table(
          [
            ['label', 'Label'],
            ['trades', 'Trades'],
            ['profit_total_pct', 'Profit %'],
            ['profit_total_abs', 'Profit'],
            ['winrate', 'Win Rate'],
            ['profit_factor', 'Factor'],
            ['expectancy', 'Expectancy'],
            ['sharpe', 'Sharpe'],
            ['duration_avg', 'Avg Duration'],
          ],
          sorted.map((row) => [
            _esc(row.label || '—'),
            FMT.integer(row.trades),
            `<span class="text-${_toneFromNumber(row.profit_total_pct)}">${_formatPct(row.profit_total_pct)}</span>`,
            `<span class="text-${_toneFromNumber(row.profit_total_abs)}">${FMT.currency(row.profit_total_abs)}</span>`,
            `<span class="text-${FMT.toneWinRate(row.winrate)}">${_formatPct(row.winrate, 1, false)}</span>`,
            `<span class="text-${FMT.toneRatio(row.profit_factor, 1)}">${FMT.number(row.profit_factor, 3)}</span>`,
            `<span class="text-${FMT.toneProfit(row.expectancy)}">${FMT.number(row.expectancy, 4)}</span>`,
            `<span class="text-${FMT.toneRatio(row.sharpe, 1)}">${FMT.number(row.sharpe, 3)}</span>`,
            _esc(row.duration_avg || '—'),
          ]),
          key
        )}
      </div>
    `;
  }

  function _table(columns, rows, sortKey = null) {
    return `
      <div class="result-explorer__table-wrap">
        <table class="data-table data-table--sm">
          <thead>
            <tr>
              ${columns.map(([key, label]) => {
                if (!sortKey) return `<th>${_esc(label)}</th>`;
                const state = _state.tables[sortKey];
                const active = state?.key === key;
                return `<th class="sortable ${active ? 'sorted' : ''}" data-table-sort="${sortKey}:${key}">${_esc(label)}${active ? (state.dir === 1 ? ' ▲' : ' ▼') : ''}</th>`;
              }).join('')}
            </tr>
          </thead>
          <tbody>
            ${rows.length ? rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('') : `<tr><td colspan="${columns.length}" class="text-muted">No rows.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  function _filteredTrades(rows, filter) {
    const q = (filter || '').trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((trade) => {
      const haystack = [
        trade.pair,
        trade.direction,
        trade.enter_tag,
        trade.exitReason,
        trade.exit_reason,
      ].join(' ').toLowerCase();
      return haystack.includes(q);
    });
  }

  function _sortRows(rows, key, dir) {
    return [...rows].sort((a, b) => {
      const va = _rowValue(a, key);
      const vb = _rowValue(b, key);
      if (va === null && vb === null) return 0;
      if (va === null) return dir;
      if (vb === null) return -dir;
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  }

  function _rowValue(row, key) {
    const value = row?.[key];
    if (value === undefined || value === null || value === '') return null;
    if (typeof value === 'number') return value;
    const parsed = parseFloat(value);
    if (!Number.isNaN(parsed) && String(value).trim() !== '') return parsed;
    return String(value).toLowerCase();
  }

  function _buildDrawdownSeries(points) {
    if (!points.length) return [];
    let peak = -Infinity;
    return points.map((point) => {
      const value = Number(point.value) || 0;
      peak = Math.max(peak, value);
      return { label: point.label, value: peak - value };
    });
  }

  function _lineChart(points, opts = {}) {
    if (!points.length) return '<div class="empty-state">No chart data.</div>';
    const color = opts.color || 'var(--violet)';
    const area = opts.area !== false;
    const width = 760;
    const height = 220;
    const padX = 16;
    const padY = 20;
    const values = points.map((point) => Number(point.value) || 0);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const step = points.length > 1 ? (width - padX * 2) / (points.length - 1) : 0;
    const coords = points.map((point, idx) => {
      const value = Number(point.value) || 0;
      const x = padX + step * idx;
      const y = height - padY - ((value - min) / range) * (height - padY * 2);
      return { x, y, value, label: point.label };
    });
    const linePath = coords.map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ');
    const areaPath = `${linePath} L ${coords[coords.length - 1].x.toFixed(2)} ${(height - padY).toFixed(2)} L ${coords[0].x.toFixed(2)} ${(height - padY).toFixed(2)} Z`;
    return `
      <svg class="result-explorer__chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="chart">
        <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" class="result-explorer__chart-axis"></line>
        ${area ? `<path d="${areaPath}" fill="${color}" opacity="0.14"></path>` : ''}
        <path d="${linePath}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></path>
      </svg>
    `;
  }

  function _barChart(points) {
    if (!points.length) return '<div class="empty-state">No chart data.</div>';
    const width = 760;
    const height = 220;
    const padX = 16;
    const padY = 20;
    const values = points.map((point) => Number(point.value) || 0);
    const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 1);
    const baseline = height / 2;
    const barWidth = Math.max(4, (width - padX * 2) / Math.max(points.length, 1) - 2);
    return `
      <svg class="result-explorer__chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="bar chart">
        <line x1="${padX}" y1="${baseline}" x2="${width - padX}" y2="${baseline}" class="result-explorer__chart-axis"></line>
        ${points.map((point, idx) => {
          const value = Number(point.value) || 0;
          const scaled = (Math.abs(value) / maxAbs) * ((height / 2) - padY);
          const x = padX + idx * ((width - padX * 2) / Math.max(points.length, 1));
          const y = value >= 0 ? baseline - scaled : baseline;
          const fill = value >= 0 ? 'var(--green)' : 'var(--red)';
          return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${scaled.toFixed(2)}" rx="2" fill="${fill}" opacity="0.88"></rect>`;
        }).join('')}
      </svg>
    `;
  }

  function _seriesMeta(points) {
    if (!points.length) return 'No data';
    const first = points[0]?.label || '—';
    const last = points[points.length - 1]?.label || '—';
    const values = points.map((point) => Number(point.value) || 0);
    const min = Math.min(...values);
    const max = Math.max(...values);
    return `${_esc(first)} to ${_esc(last)} · min ${FMT.number(min, 2)} · max ${FMT.number(max, 2)}`;
  }

  function _tabButton(id, label) {
    return `<button type="button" class="result-explorer__tab" data-tab="${id}">${_esc(label)}</button>`;
  }

  function _heroStat(label, value, tone = '') {
    return `
      <div class="result-explorer__hero-stat ${tone ? `result-explorer__hero-stat--${tone}` : ''}">
        <span class="result-explorer__hero-label">${_esc(label)}</span>
        <span class="result-explorer__hero-value ${tone ? `text-${tone}` : ''}">${value}</span>
      </div>
    `;
  }

  function _chartCard(title, chart, meta) {
    return `
      <div class="result-explorer__chart-card">
        <div class="result-explorer__chart-head">
          <span class="result-explorer__chart-title">${_esc(title)}</span>
          <span class="result-explorer__chart-meta">${meta}</span>
        </div>
        <div class="result-explorer__chart-body">${chart}</div>
      </div>
    `;
  }

  function _detailItem(label, value, tone = '') {
    return `
      <div class="detail-item result-explorer__metric-card ${tone ? `result-explorer__metric-card--${tone}` : ''}">
        <span class="detail-label">${_esc(label)}</span>
        <span class="${tone ? `text-${tone}` : ''}">${value}</span>
      </div>
    `;
  }

  function _severityTone(value) {
    const severity = String(value || '').toLowerCase();
    if (severity === 'critical' || severity === 'high') return 'red';
    if (severity === 'warning' || severity === 'medium') return 'amber';
    if (severity === 'ok' || severity === 'low') return 'green';
    return '';
  }

  function _jsonMini(value) {
    const text = JSON.stringify(value);
    return text && text.length <= 40 ? _esc(text) : `<span class="text-muted">${_esc(FMT.truncate(text || '—', 40))}</span>`;
  }

  function _jsonPanel(value, emptyText) {
    if (!value || (Array.isArray(value) && !value.length) || (typeof value === 'object' && !Array.isArray(value) && !Object.keys(value).length)) {
      return `<div class="empty-state">${_esc(emptyText)}</div>`;
    }
    return `<pre class="result-explorer__json">${_esc(JSON.stringify(value, null, 2))}</pre>`;
  }

  function _rawJson() {
    try {
      return JSON.stringify(_state.raw?.payload || {}, null, 2);
    } catch {
      return '{}';
    }
  }

  function _activateTab(id) {
    const tabs = [..._body.querySelectorAll('[data-tab]')];
    const panels = [..._body.querySelectorAll('[data-tab-panel]')];
    tabs.forEach((tab) => {
      const active = tab.dataset.tab === id;
      tab.classList.toggle('tab--active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    panels.forEach((panel) => {
      const active = panel.dataset.tabPanel === id;
      panel.classList.toggle('tab-panel--active', active);
      panel.hidden = !active;
    });
    _scrollTabIntoView(id);
  }

  function _scrollTabIntoView(id) {
    const tab = _body.querySelector(`[data-tab="${id}"]`);
    if (!tab || typeof tab.scrollIntoView !== 'function') return;
    tab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }

  function _formatPct(value, decimals = 2, showSign = true) {
    const numeric = FMT.toNumber ? FMT.toNumber(value) : parseFloat(value);
    if (numeric === null || Number.isNaN(numeric)) return 'N/A';
    return FMT.pct(numeric, decimals, showSign);
  }

  function _formatCurrencyOrNA(value) {
    const numeric = FMT.toNumber ? FMT.toNumber(value) : parseFloat(value);
    if (numeric === null || Number.isNaN(numeric)) return 'N/A';
    return FMT.currency(numeric);
  }

  function _toneFromNumber(value) {
    const numeric = parseFloat(value);
    if (!Number.isFinite(numeric)) return '';
    if (numeric > 0) return 'green';
    if (numeric < 0) return 'red';
    return 'muted';
  }

  function _bool(value) {
    if (value === true) return 'Yes';
    if (value === false) return 'No';
    return '—';
  }

  function _pairLabel(value) {
    if (!value) return '';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.filter(Boolean).join(' -> ');
    if (typeof value === 'object') {
      return value.key || value.pair || value.label || value.name || '';
    }
    return String(value);
  }

  function _esc(value) {
    const div = document.createElement('div');
    div.textContent = String(value ?? '');
    return div.innerHTML;
  }

  return { open };
})();
