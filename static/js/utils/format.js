/* =================================================================
   FORMAT — number, date, duration, and string helpers
   Exposes: window.FMT
   ================================================================= */

window.FMT = (() => {
  function toNumber(value) {
    if (value === null || value === undefined || value === '') return null;
    const n = parseFloat(value);
    return Number.isFinite(n) ? n : null;
  }

  function pct(value, decimals = 2, showSign = true) {
    const n = toNumber(value);
    if (n === null) return '—';
    const sign = showSign && n > 0 ? '+' : '';
    return `${sign}${n.toFixed(decimals)}%`;
  }

  function pctRatio(value, decimals = 2, showSign = true) {
    const n = toNumber(value);
    if (n === null) return '—';
    return pct(n * 100, decimals, showSign);
  }

  function currency(value, decimals = 2, symbol = '$') {
    if (value === null || value === undefined || isNaN(value)) return '—';
    const n = parseFloat(value);
    const sign = n < 0 ? '-' : '';
    return `${sign}${symbol}${Math.abs(n).toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`;
  }

  function number(value, decimals = 4) {
    const n = toNumber(value);
    if (n === null) return '—';
    return n.toLocaleString('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimals,
    });
  }

  function integer(value) {
    const n = toNumber(value);
    if (n === null) return '—';
    return parseInt(n, 10).toLocaleString('en-US');
  }

  function resultProfitPercent(metrics = {}) {
    const raw = toNumber(
      metrics.profit_percent ?? metrics.profit_total_pct ?? metrics.totalProfitPct ?? metrics.profit_pct
    );
    const ratio = toNumber(metrics.profit_total);
    const absProfit = toNumber(metrics.profit_total_abs ?? metrics.totalProfit ?? metrics.profit_abs);
    const starting = toNumber(metrics.starting_balance ?? metrics.startingBalance);
    const ending = toNumber(metrics.final_balance ?? metrics.finalBalance);

    let derived = null;
    if (starting && ending !== null) derived = ((ending - starting) / starting) * 100;
    else if (starting && absProfit !== null) derived = (absProfit / starting) * 100;
    else if (ratio !== null) derived = ratio * 100;

    if (raw === null) return derived;
    if (derived === null) {
      if (Math.abs(raw) > 1000 && Math.abs(raw / 100) <= 1000) return raw / 100;
      return raw;
    }

    const tolerance = Math.max(0.5, Math.abs(derived) * 0.05);
    if (Math.abs(raw - derived) <= tolerance) return raw;
    if (Math.abs(raw / 100 - derived) <= tolerance) return raw / 100;
    if (Math.abs(raw) > Math.max(250, Math.abs(derived) * 3 + 25)) return derived;
    return raw;
  }

  function resultWinRate(value) {
    const raw = toNumber(value);
    if (raw === null) return null;
    if (Math.abs(raw) <= 1) return raw * 100;
    if (Math.abs(raw) > 100 && Math.abs(raw / 100) <= 100) return raw / 100;
    return raw;
  }

  function resultDrawdownPercent(value) {
    const raw = toNumber(value);
    if (raw === null) return null;
    if (Math.abs(raw) <= 1) return Math.abs(raw) * 100;
    if (Math.abs(raw) > 100 && Math.abs(raw / 100) <= 100) return Math.abs(raw / 100);
    return Math.abs(raw);
  }

  function toneSigned(value, positive = 'green', negative = 'red', zero = 'muted') {
    const n = toNumber(value);
    if (n === null) return zero;
    if (n > 0) return positive;
    if (n < 0) return negative;
    return zero;
  }

  function toneProfit(value) {
    return toneSigned(value, 'green', 'red', 'muted');
  }

  function toneWinRate(value) {
    const n = resultWinRate(value);
    if (n === null) return 'muted';
    if (n >= 55) return 'green';
    if (n >= 45) return 'amber';
    return 'red';
  }

  function toneRatio(value, goodThreshold = 1) {
    const n = toNumber(value);
    if (n === null) return 'muted';
    if (n >= goodThreshold) return 'green';
    if (n > 0) return 'amber';
    return 'red';
  }

  function toneDrawdown(value) {
    const n = resultDrawdownPercent(value);
    if (n === null) return 'muted';
    if (n <= 0) return 'muted';
    if (n >= 20) return 'red';
    return 'amber';
  }

  function ts(value) {
    if (!value) return '—';
    try {
      const d = new Date(value);
      if (isNaN(d.getTime())) return value;
      return d.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return value; }
  }

  function tsShort(value) {
    if (!value) return '—';
    try {
      const d = new Date(value);
      if (isNaN(d.getTime())) return value;
      return d.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
      });
    } catch { return value; }
  }

  function duration(ms) {
    if (!ms || isNaN(ms)) return '—';
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ${s % 60}s`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }

  function truncate(str, length = 40) {
    if (!str) return '';
    return str.length > length ? str.slice(0, length) + '…' : str;
  }

  function statusColor(status) {
    switch ((status || '').toLowerCase()) {
      case 'running':   return 'amber';
      case 'completed': return 'green';
      case 'failed':    return 'red';
      case 'cancelled': return 'muted';
      default:          return 'muted';
    }
  }

  function statusLabel(status) {
    if (!status) return 'Unknown';
    return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
  }

  return {
    toNumber,
    pct, pctRatio, currency, number, integer,
    resultProfitPercent, resultWinRate, resultDrawdownPercent,
    toneSigned, toneProfit, toneWinRate, toneRatio, toneDrawdown,
    ts, tsShort, duration, truncate, statusColor, statusLabel
  };
})();
