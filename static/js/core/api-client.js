/* =================================================================
   API CLIENT — fetch wrapper + named endpoint helpers
   Exposes: window.API
   ================================================================= */

window.API = (() => {
  const BASE = window.location.origin;

  const logApiError = (method, path, detail) => {
    window.UILog?.error?.('API request failed', { method, path, detail });
  };

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
      logApiError(method, path, detail);
      throw new Error(detail);
    }
    return res.json();
  }

  const get   = (path)        => request('GET',    path);
  const getText = async (path) => {
    const res = await fetch(`${BASE}${path}`, { method: 'GET' });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch {}
      logApiError('GET', path, detail);
      throw new Error(detail);
    }
    return res.text();
  };
  const post  = (path, body)  => request('POST',   path, body);
  const del   = (path)        => request('DELETE', path);
  const patch = (path, body)  => request('PATCH',  path, body);

  /* ---- Health ------------------------------------------------ */
  const health = () => get('/healthz');

  /* ---- Strategies ------------------------------------------- */
  const getStrategies      = ()       => get('/strategies');
  const getStrategyParams  = (name)   => get(`/strategies/${encodeURIComponent(name)}/params`);
  const getStrategySource  = (name)   => getText(`/strategies/${encodeURIComponent(name)}/source`);
  const saveStrategyParams = (name, parameters) =>
    post(`/strategies/${encodeURIComponent(name)}/params`, { parameters });
  const saveStrategySource = (name, source) =>
    post(`/strategies/${encodeURIComponent(name)}/source`, { source });

  /* ---- Pairs ------------------------------------------------- */
  const getPairs = (exchange = 'binance', timeframe = null) => {
    let url = `/pairs?exchange=${encodeURIComponent(exchange)}`;
    if (timeframe) url += `&timeframe=${encodeURIComponent(timeframe)}`;
    return get(url);
  };

  /* ---- Config ----------------------------------------------- */
  const getConfig       = ()        => get('/config');
  const patchConfig     = (body)    => patch('/config', body);

  /* ---- Backtest runs ---------------------------------------- */
  const getRuns         = ()        => get('/runs');
  const getActivity     = (limit = 100) => get(`/activity?limit=${encodeURIComponent(limit)}`);
  const getRun          = (id)      => get(`/runs/${id}`);
  const getRunRaw       = (id)      => get(`/runs/${id}/raw`);
  const getResultMetrics = ()       => get('/result-metrics');
  const applyRunConfig  = (id)      => post(`/runs/${id}/apply-config`, {});
  const applyStrategySuggestion = (id, body) => post(`/runs/${id}/apply-suggestion`, body);
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

  /* ---- App Settings --------------------------------------- */
  const getSettings  = ()     => get('/settings');
  const saveSettings = (body) => post('/settings', body);
  const testOpenRouterKey = (apiKey) => post('/settings/test-openrouter-key', { api_key: apiKey });

  /* ---- Compare ---------------------------------------------- */
  const compareRuns    = (body)      => post('/compare', body);

  return {
    request, get, getText, post, del, patch,
    health,
    getStrategies, getStrategyParams, getStrategySource, saveStrategyParams, saveStrategySource,
    getPairs,
    getConfig, patchConfig,
    getRuns, getActivity, getRun, getRunRaw, getResultMetrics, applyRunConfig, applyStrategySuggestion, startBacktest, deleteRun, getLastConfig,
    downloadData, getDownload, dataCoverage,
    getHyperoptRuns, getHyperoptRun, startHyperopt, deleteHyperoptRun,
    getLossFunctions, getHyperoptSpaces, applyHyperoptParams,
    getPresets, savePreset, deletePreset,
    compareRuns,
    getSettings, saveSettings, testOpenRouterKey,
  };
})();



