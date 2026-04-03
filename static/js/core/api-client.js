/* =================================================================
   API CLIENT — fetch wrapper + named endpoint helpers
   Exposes: window.API
   ================================================================= */

window.API = (() => {
  const BASE = window.location.origin;

  async function request(method, path, body = undefined) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(`${BASE}${path}`, opts);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch {}
      throw new Error(detail);
    }
    return res.json();
  }

  const get  = (path)        => request('GET',    path);
  const post = (path, body)  => request('POST',   path, body);
  const del  = (path)        => request('DELETE', path);

  /* ---- Health ------------------------------------------------ */
  const health = () => get('/healthz');

  /* ---- Strategies ------------------------------------------- */
  const getStrategies      = ()       => get('/strategies');
  const getStrategyParams  = (name)   => get(`/strategies/${encodeURIComponent(name)}/params`);

  /* ---- Pairs ------------------------------------------------- */
  const getPairs = (exchange = 'binance', timeframe = null) => {
    let url = `/pairs?exchange=${encodeURIComponent(exchange)}`;
    if (timeframe) url += `&timeframe=${encodeURIComponent(timeframe)}`;
    return get(url);
  };

  /* ---- Backtest runs ---------------------------------------- */
  const getRuns         = ()        => get('/runs');
  const getRun          = (id)      => get(`/runs/${id}`);
  const startBacktest   = (body)    => post('/run', body);
  const deleteRun       = (id)      => del(`/runs/${id}`);
  const getLastConfig   = ()        => get('/last-config');

  /* ---- Download data ---------------------------------------- */
  const downloadData    = (body)    => post('/download-data', body);
  const getDownload     = (id)      => get(`/download-data/${id}`);
  const dataCoverage    = (body)    => post('/data-coverage', body);

  /* ---- Hyperopt runs ---------------------------------------- */
  const getHyperoptRuns      = ()        => get('/hyperopt/runs');
  const getHyperoptRun       = (id)      => get(`/hyperopt/runs/${id}`);
  const startHyperopt        = (body)    => post('/hyperopt/run', body);
  const deleteHyperoptRun    = (id)      => del(`/hyperopt/runs/${id}`);
  const getLossFunctions     = ()        => get('/hyperopt/loss-functions');
  const getHyperoptSpaces    = ()        => get('/hyperopt/spaces');
  const applyHyperoptParams  = (body)    => post('/hyperopt/apply-params', body);

  /* ---- Presets ---------------------------------------------- */
  const getPresets     = ()          => get('/presets');
  const savePreset     = (body)      => post('/presets', body);
  const deletePreset   = (name)      => del(`/presets/${encodeURIComponent(name)}`);

  /* ---- Compare ---------------------------------------------- */
  const compareRuns    = (body)      => post('/compare', body);

  return {
    request, get, post, del,
    health,
    getStrategies, getStrategyParams,
    getPairs,
    getRuns, getRun, startBacktest, deleteRun, getLastConfig,
    downloadData, getDownload, dataCoverage,
    getHyperoptRuns, getHyperoptRun, startHyperopt, deleteHyperoptRun,
    getLossFunctions, getHyperoptSpaces, applyHyperoptParams,
    getPresets, savePreset, deletePreset,
    compareRuns,
  };
})();
