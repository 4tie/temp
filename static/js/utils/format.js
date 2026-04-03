/* =================================================================
   FORMAT — number, date, duration, and string helpers
   Exposes: window.FMT
   ================================================================= */

window.FMT = (() => {

  function pct(value, decimals = 2, showSign = true) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    const n = parseFloat(value);
    const sign = showSign && n > 0 ? '+' : '';
    return `${sign}${n.toFixed(decimals)}%`;
  }

  function currency(value, decimals = 2, symbol = '$') {
    if (value === null || value === undefined || isNaN(value)) return '—';
    const n = parseFloat(value);
    return `${symbol}${Math.abs(n).toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`;
  }

  function number(value, decimals = 4) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    return parseFloat(value).toLocaleString('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimals,
    });
  }

  function integer(value) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    return parseInt(value, 10).toLocaleString('en-US');
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

  return { pct, currency, number, integer, ts, tsShort, duration, truncate, statusColor, statusLabel };
})();
