/* =================================================================
   AI DIAGNOSIS PAGE — full chat UI
   Exposes: window.AIDiagPage
   ================================================================= */

window.AIDiagPage = (() => {
  /* ---- State ------------------------------------------------ */
  let _state = {
    provider: 'openrouter',
    model: null,
    goal: 'balanced',
    conversationId: null,
    contextRunId: null,
    contextStrategyName: null,
    contextTimeframe: null,
    streaming: false,
    evtSource: null,
    streamController: null,
    providers: null,
    loopEnabled: false,
    loopBusy: false,
    loopId: null,
    loopStream: null,
    lastApplied: null,
    pendingRerunPrompt: false,
    loopToken: 0,
  };

  /* ---- DOM refs (populated in init) ------------------------ */
  let _el = {};

  /* ---- Markdown renderer ----------------------------------- */
  function _collectCodeBlockHints(rawText) {
    const hints = [];
    const src = String(rawText || '');
    const rx = /```([A-Za-z0-9_-]*)\n?([\s\S]*?)```/g;
    let match;
    let idx = 0;
    while ((match = rx.exec(src)) !== null) {
      const before = src.slice(Math.max(0, match.index - 500), match.index);
      const after = src.slice(rx.lastIndex, rx.lastIndex + 160);
      const beforeMatches = [...before.matchAll(/\b([A-Za-z0-9_-]+\.py)\b/g)];
      const afterMatch = after.match(/\b([A-Za-z0-9_-]+\.py)\b/);
      const filename = beforeMatches.length
        ? beforeMatches[beforeMatches.length - 1][1]
        : (afterMatch ? afterMatch[1] : '');
      hints[idx] = {
        lang: String(match[1] || '').toLowerCase(),
        filename,
      };
      idx += 1;
    }
    return hints;
  }

  function _renderMarkdown(text, opts = {}) {
    const assistantMessageId = opts.assistantMessageId || '';
    const codeHints = _collectCodeBlockHints(text);
    let codeIdx = 0;
    let html = text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const hint = codeHints[codeIdx] || {};
      const blockIndex = codeIdx;
      codeIdx += 1;
      const label = lang || hint.lang || 'code';
      const escaped = code.trim();
      const filename = hint.filename || '';
      const isPython = /^python|py$/i.test(label);
      const actions = [
        '<button class="cmd-block__action" data-action="copy">copy</button>',
        `<button class="cmd-block__action" data-action="diff"${isPython ? '' : ' style="display:none"'}>diff</button>`,
        `<button class="cmd-block__action cmd-block__action--apply" data-action="apply"${isPython ? '' : ' style="display:none"'}>apply</button>`,
      ].join('');
      return `<div class="cmd-block" data-code-block-index="${blockIndex}" data-assistant-message-id="${_escHtml(assistantMessageId)}" data-inferred-filename="${_escHtml(filename)}" data-code-lang="${_escHtml(String(label).toLowerCase())}">
        <div class="cmd-block__label">
          <span>${_escHtml(label)}${filename ? ` · ${_escHtml(filename)}` : ''}</span>
          <span class="cmd-block__actions">${actions}</span>
        </div>
        <pre>${escaped}</pre>
      </div>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Unordered lists
    html = html.replace(/^[\*\-] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/gs, m => `<ul>${m}</ul>`);

    // Ordered lists
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

    // Paragraphs (double newline)
    const parts = html.split(/\n\n+/);
    html = parts.map(p => {
      p = p.trim();
      if (!p) return '';
      if (/^<(h[1-3]|ul|ol|div|pre|li)/.test(p)) return p;
      return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');

    return html;
  }

  function _escHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ---- Evolution state ------------------------------------ */
  let _evo = {
    loopId: null,
    evtSource: null,
    activeTab: 'config',   // 'config' | 'running' | 'results'
    generations: [],       // accumulated generation events
    maxGenerations: 3,
    originalSource: null,  // source code before mutation (for diff)
  };

  /* ---- Build layout HTML ----------------------------------- */
  function _buildLayout() {
    return `
<div class="ai-layout" id="ai-layout">

  <!-- Overlay for mobile sidebar -->
  <div class="ai-sidebar-overlay" id="ai-sidebar-overlay"></div>

  <!-- ---- Sidebar ----------------------------------------- -->
  <aside class="ai-sidebar" id="ai-sidebar">
    <div class="ai-sidebar__header">
      <span class="ai-sidebar__title">Conversations</span>
      <button class="ai-new-chat-btn" id="ai-new-chat">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        New
      </button>
    </div>
    <div class="ai-conv-list" id="ai-conv-list">
      <div class="ai-sidebar-empty">No conversations yet</div>
    </div>
  </aside>

  <!-- ---- Main -------------------------------------------- -->
  <div class="ai-main">

    <!-- Header bar -->
    <div class="ai-header">
      <button class="ai-hamburger" id="ai-hamburger" title="Toggle sidebar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>

      <!-- Provider toggle -->
      <div class="ai-provider-toggle" id="ai-provider-toggle">
        <button class="ai-provider-btn" data-provider="ollama" id="ai-btn-ollama">Ollama</button>
        <button class="ai-provider-btn active" data-provider="openrouter" id="ai-btn-openrouter">OpenRouter</button>
      </div>

      <!-- Model select -->
      <select class="ai-model-select" id="ai-model-select">
        <option value="">Loading models…</option>
      </select>

      <!-- Goal select -->
      <select class="ai-goal-select" id="ai-goal-select">
        <option value="balanced">Balanced</option>
        <option value="maximize_profit">Maximize Profit</option>
        <option value="reduce_drawdown">Reduce Drawdown</option>
        <option value="improve_win_rate">Improve Win Rate</option>
      </select>

      <!-- Deep Analyse button -->
      <button class="ai-deep-analyse-btn" id="ai-deep-analyse-btn" disabled title="Inject a backtest first">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          <line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
        </svg>
        Deep Analyse
      </button>

      <!-- Evolve Strategy button -->
      <button class="ai-evolve-btn" id="ai-evolve-btn" disabled title="Inject a backtest first">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
        </svg>
        Evolve Strategy
      </button>
    </div>

    <!-- Provider warning bar -->
    <div class="ai-provider-warning" id="ai-provider-warning"></div>

    <!-- Context bar -->
    <div class="ai-context-bar hidden" id="ai-context-bar">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--violet);flex-shrink:0">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <span style="color:var(--text-muted)">Context:</span>
      <span class="ai-context-badge" id="ai-context-badge"></span>
      <button class="ai-context-clear" id="ai-context-clear">clear</button>
      <button class="ai-loop-btn" id="ai-loop-toggle">Start Loop</button>
      <button class="ai-inject-btn" id="ai-inject-btn" style="margin-left:auto">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/>
        </svg>
        Inject latest backtest
      </button>
    </div>

    <!-- Hidden inject button shown in empty state too -->
    <div id="ai-inject-bar-hidden" style="display:none">
      <button class="ai-inject-btn" id="ai-inject-btn2">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/>
        </svg>
        Inject latest backtest
      </button>
    </div>

    <!-- Message thread -->
    <div class="ai-thread" id="ai-thread">
      <div class="ai-thread-empty" id="ai-thread-empty">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <h3>AI Strategy Analyst</h3>
        <p>Ask about your trading strategy, inject a backtest for context, or choose a goal to get targeted recommendations.</p>
        <button class="ai-inject-btn" id="ai-inject-btn3" style="margin-top:var(--space-2)">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/>
          </svg>
          Inject latest backtest
        </button>
      </div>
    </div>

    <!-- Input bar -->
    <div class="ai-input-bar">
      <div class="ai-input-row">
        <textarea
          class="ai-textarea"
          id="ai-textarea"
          placeholder="Ask about your strategy…"
          rows="1"
        ></textarea>
        <button class="ai-send-btn" id="ai-send-btn" disabled title="Send">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
        <button class="ai-stop-btn" id="ai-stop-btn" style="display:none" title="Stop">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="4" y="4" width="16" height="16" rx="2"/>
          </svg>
        </button>
      </div>
      <div class="ai-status-line" id="ai-status-line"></div>
    </div>

  </div><!-- /ai-main -->

</div><!-- /ai-layout -->

<!-- Deep Analysis Panel -->
<div class="ai-deep-panel" id="ai-deep-panel">
  <div class="ai-deep-panel__header">
    <span class="ai-deep-panel__title">Deep Analysis</span>
    <button class="ai-deep-panel__close" id="ai-deep-panel-close">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
  <div class="ai-deep-panel__body" id="ai-deep-panel-body">
    <div class="ai-deep-panel__loading">
      <div class="ai-deep-panel__loading-spinner"></div>
      <span>Loading analysis…</span>
    </div>
  </div>
</div>

<!-- Evolution Panel -->
<div class="evo-panel" id="evo-panel">
  <div class="evo-panel__header">
    <span class="evo-panel__title">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2">
        <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
      </svg>
      Evolve Strategy
    </span>
    <button class="evo-panel__close" id="evo-panel-close">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
  <div class="evo-tabs">
    <button class="evo-tab active" id="evo-tab-config" data-tab="config">Configure</button>
    <button class="evo-tab" id="evo-tab-running" data-tab="running">Running</button>
    <button class="evo-tab" id="evo-tab-results" data-tab="results">Results</button>
  </div>
  <div class="evo-panel__body" id="evo-panel-body"></div>
</div>

<!-- Code Diff Modal -->
<div class="evo-diff-overlay" id="evo-diff-overlay">
  <div class="evo-diff-modal">
    <div class="evo-diff-modal__header">
      <span class="evo-diff-modal__title" id="evo-diff-title">Code Diff</span>
      <button class="evo-diff-modal__close" id="evo-diff-close">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
    <div class="evo-diff-cols">
      <div class="evo-diff-col">
        <div class="evo-diff-col__label evo-diff-col__label--original">Original</div>
        <div class="evo-diff-scroll"><div class="evo-diff" id="evo-diff-original"></div></div>
      </div>
      <div class="evo-diff-col">
        <div class="evo-diff-col__label evo-diff-col__label--mutated">Mutated</div>
        <div class="evo-diff-scroll"><div class="evo-diff" id="evo-diff-mutated"></div></div>
      </div>
    </div>
  </div>
</div>

<!-- Toast -->
<div class="evo-toast" id="evo-toast"></div>
    `;
  }

  /* ---- Populate DOM refs ----------------------------------- */
  function _cacheRefs() {
    const $ = (id) => document.getElementById(id);
    _el = {
      layout:          $('ai-layout'),
      sidebar:         $('ai-sidebar'),
      sidebarOverlay:  $('ai-sidebar-overlay'),
      hamburger:       $('ai-hamburger'),
      newChat:         $('ai-new-chat'),
      convList:        $('ai-conv-list'),
      providerToggle:  $('ai-provider-toggle'),
      btnOllama:       $('ai-btn-ollama'),
      btnOpenRouter:   $('ai-btn-openrouter'),
      modelSelect:     $('ai-model-select'),
      goalSelect:      $('ai-goal-select'),
      deepAnalyseBtn:  $('ai-deep-analyse-btn'),
      providerWarning: $('ai-provider-warning'),
      contextBar:      $('ai-context-bar'),
      contextBadge:    $('ai-context-badge'),
      contextClear:    $('ai-context-clear'),
      loopToggle:      $('ai-loop-toggle'),
      injectBtn:       $('ai-inject-btn'),
      injectBtn2:      $('ai-inject-btn2'),
      injectBtn3:      $('ai-inject-btn3'),
      thread:          $('ai-thread'),
      threadEmpty:     $('ai-thread-empty'),
      textarea:        $('ai-textarea'),
      sendBtn:         $('ai-send-btn'),
      stopBtn:         $('ai-stop-btn'),
      statusLine:      $('ai-status-line'),
      deepPanel:       $('ai-deep-panel'),
      deepPanelBody:   $('ai-deep-panel-body'),
      deepPanelClose:  $('ai-deep-panel-close'),
      // Evolution
      evolveBtn:       $('ai-evolve-btn'),
      evoPanel:        $('evo-panel'),
      evoPanelClose:   $('evo-panel-close'),
      evoPanelBody:    $('evo-panel-body'),
      evoTabConfig:    $('evo-tab-config'),
      evoTabRunning:   $('evo-tab-running'),
      evoTabResults:   $('evo-tab-results'),
      evoDiffOverlay:  $('evo-diff-overlay'),
      evoDiffClose:    $('evo-diff-close'),
      evoDiffOriginal: $('evo-diff-original'),
      evoDiffMutated:  $('evo-diff-mutated'),
      evoDiffTitle:    $('evo-diff-title'),
      evoToast:        $('evo-toast'),
    };
  }

  /* ---- Load providers --------------------------------------- */
  async function _loadProviders() {
    try {
      const data = await fetch('/ai/providers').then(r => r.json());
      // Support {providers: {ollama,openrouter}} and {ollama,openrouter} formats
      _state.providers = data.providers || data;
      _updateProviderUI();
    } catch (e) {
      _setStatus('Could not load providers');
    }
  }

  function _updateProviderUI() {
    const p = _state.providers;
    if (!p) return;

    // Support both {providers: {ollama,openrouter}} and {ollama,openrouter} formats
    const ollama = p.ollama;
    const openrouter = p.openrouter;

    // Update Ollama button
    if (!ollama.available) {
      _el.btnOllama.textContent = 'Ollama (offline)';
      _el.btnOllama.classList.add('offline');
    } else {
      _el.btnOllama.textContent = 'Ollama';
      _el.btnOllama.classList.remove('offline');
    }

    // Update OpenRouter button
    if (!openrouter.available) {
      _el.btnOpenRouter.textContent = 'OpenRouter (no key)';
      _el.btnOpenRouter.classList.add('no-key');
    } else {
      _el.btnOpenRouter.classList.remove('no-key');
    }

    // Auto-switch to Ollama if OpenRouter unavailable but Ollama available
    if (!openrouter.available && ollama.available) {
      _state.provider = 'ollama';
      _el.btnOllama.classList.add('active');
      _el.btnOpenRouter.classList.remove('active');
    }

    _updateModelDropdown();
  }

  function _updateModelDropdown() {
    const p = _state.providers;
    if (!p) return;

    const models = _state.provider === 'ollama'
      ? (p.ollama?.models || [])
      : (p.openrouter?.models || []);

    _el.modelSelect.innerHTML = '';

    if (models.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = _state.provider === 'ollama' ? 'No Ollama models' : 'No models available';
      _el.modelSelect.appendChild(opt);
      _el.sendBtn.disabled = true;
      return;
    }

    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name || m.id;
      _el.modelSelect.appendChild(opt);
    });

    const selectedId = _state.model;
    const matched = selectedId && models.some(m => m.id === selectedId);
    _state.model = matched ? selectedId : models[0].id;
    _el.modelSelect.value = _state.model;
    _checkSendReady();
  }

  /* ---- Load conversations ---------------------------------- */
  async function _loadConversations() {
    try {
      const convs = await fetch('/ai/threads').then(r => r.json());
      _renderConvList(convs);
    } catch (e) {
      /* silently ignore */
    }
  }

  function _renderConvList(convs) {
    if (!convs || convs.length === 0) {
      _el.convList.innerHTML = '<div class="ai-sidebar-empty">No conversations yet</div>';
      return;
    }
    _el.convList.innerHTML = convs.map(c => {
      const cid = c.conversation_id || c.id;
      const title = c.title || c.strategy_name || 'Chat';
      const preview = c.preview || '';
      return `
      <div class="ai-conv-item ${cid === _state.conversationId ? 'active' : ''}" data-conv-id="${cid}">
        <span class="ai-conv-item__name">${_escHtml(title)}</span>
        ${preview ? `<span class="ai-conv-item__preview">${_escHtml(preview)}</span>` : ''}
        <button class="ai-conv-delete" data-conv-id="${cid}" title="Delete">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
          </svg>
        </button>
      </div>
    `;
    }).join('');
  }

  /* ---- Switch conversation --------------------------------- */
  async function _switchConversation(convId) {
    _closeLoopStream();
    _state.conversationId = convId;
    _el.thread.innerHTML = '';

    // Mark active in sidebar
    document.querySelectorAll('.ai-conv-item').forEach(el => {
      el.classList.toggle('active', el.dataset.convId === convId);
    });

    try {
      const conv = await fetch(`/ai/threads/${convId}`).then(r => r.json());
      if (conv) {
        // Restore thread-level state so resumed chats keep their original context.
        _state.goal = conv.goal_id || _state.goal || 'balanced';
        _state.provider = conv.provider || _state.provider || 'openrouter';
        _state.model = conv.model || _state.model || null;
        _state.contextRunId = conv.context_run_id || null;
        _state.loopEnabled = false;
        _state.loopBusy = false;
        _state.pendingRerunPrompt = false;
        _state.loopId = null;
        _state.loopToken += 1;
        _state.contextStrategyName = null;
        _state.contextTimeframe = null;

        if (_el.goalSelect) _el.goalSelect.value = _state.goal;
        if (_el.btnOllama) _el.btnOllama.classList.toggle('active', _state.provider === 'ollama');
        if (_el.btnOpenRouter) _el.btnOpenRouter.classList.toggle('active', _state.provider === 'openrouter');
        _updateModelDropdown();
        _updateContextBar();
        _el.deepAnalyseBtn.disabled = !_state.contextRunId;
        if (_el.evolveBtn) _el.evolveBtn.disabled = !_state.contextRunId;

        (conv.messages || []).forEach(m => _appendMessage(m.role, m.content, m.meta, m.id));
      }
    } catch (e) {
      _setStatus('Could not load conversation');
    }

    _scrollThread();
  }

  /* ---- New chat -------------------------------------------- */
  function _newChat() {
    _closeLoopStream();
    _state.conversationId = null;
    _state.loopEnabled = false;
    _state.loopBusy = false;
    _state.pendingRerunPrompt = false;
    _state.loopId = null;
    _state.loopToken += 1;
    _el.thread.innerHTML = '';
    _showEmpty(true);
    document.querySelectorAll('.ai-conv-item').forEach(el => el.classList.remove('active'));
    _updateLoopButton();
    _el.textarea.focus();
  }

  /* ---- Inject backtest ------------------------------------- */
  async function _injectLatestBacktest() {
    try {
      const runsResp = await fetch('/runs').then(r => r.json());
      const runs = runsResp?.runs || runsResp || [];
      const completed = (runs || []).filter(r => r.status === 'done' || r.status === 'completed');
      if (!completed.length) {
        _setStatus('No completed backtests found');
        return;
      }
      const latest = completed[0];
      _state.contextRunId = latest.run_id || latest.id;
      _state.contextStrategyName = latest.strategy || latest.id;
      _state.contextTimeframe = latest.timeframe || '';
      _updateContextBar();
      _el.deepAnalyseBtn.disabled = false;

      // Pre-fetch original strategy source for diff
      try {
        const srcResp = await fetch(`/strategies/${encodeURIComponent(_state.contextStrategyName)}/source`);
        if (srcResp.ok) _evo.originalSource = await srcResp.text();
      } catch (_) {}
    } catch (e) {
      _setStatus('Could not fetch backtest runs');
    }
  }

  function _updateContextBar() {
    const active = !!_state.contextRunId;
    _el.contextBar.classList.toggle('hidden', !active);

    if (active) {
      const strat = _state.contextStrategyName || _state.contextRunId;
      const tf = _state.contextTimeframe ? ` · ${_state.contextTimeframe}` : '';
      _el.contextBadge.textContent = `${strat}${tf}`;
    }

    if (_el.evolveBtn) _el.evolveBtn.disabled = !active;
    _updateLoopButton();
  }

  function _updateLoopButton() {
    if (!_el.loopToggle) return;
    const active = !!_state.contextRunId;
    _el.loopToggle.disabled = !active || _state.loopBusy;
    if (_state.loopBusy) {
      _el.loopToggle.textContent = 'Loop Busy...';
      _el.loopToggle.classList.add('active');
      return;
    }
    _el.loopToggle.textContent = _state.loopEnabled ? 'Stop Loop' : 'Start Loop';
    _el.loopToggle.classList.toggle('active', _state.loopEnabled);
  }

  function _closeLoopStream() {
    if (_state.loopStream) {
      try { _state.loopStream.close(); } catch (_) {}
      _state.loopStream = null;
    }
  }

  function _clearContext() {
    _closeLoopStream();
    _state.contextRunId = null;
    _state.contextStrategyName = null;
    _state.contextTimeframe = null;
    _updateContextBar();
    _state.loopEnabled = false;
    _state.loopBusy = false;
    _state.pendingRerunPrompt = false;
    _state.loopId = null;
    _el.deepAnalyseBtn.disabled = true;
    if (_el.evolveBtn) _el.evolveBtn.disabled = true;
  }

  function _formatTraceDuration(ms) {
    if (!ms && ms !== 0) return '';
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
  }

  function _formatStepCount(stepCount) {
    return `${stepCount} ${stepCount === 1 ? 'step' : 'steps'}`;
  }

  function _humanRole(role) {
    return String(role || 'step').replace(/_/g, ' ');
  }

  function _shortModel(modelId) {
    if (!modelId) return '';
    const tail = String(modelId).split('/').pop() || String(modelId);
    return tail.replace(/:free$/i, '');
  }

  function _traceLabel(evt) {
    const labels = {
      classifier_decision: 'Classifier Decision',
      pipeline_selected: 'Pipeline Selected',
      step_start: `Started ${_humanRole(evt.role)}`,
      step_complete: evt.role === 'judge' ? 'Judge Completed' : `Completed ${_humanRole(evt.role)}`,
      final: 'Completed',
    };
    return labels[evt.event_type] || evt.event_type || 'Step';
  }

  function _tracePreview(evt) {
    if (evt.event_type === 'final') return '';
    if (evt.event_type === 'step_complete' && evt.role !== 'judge') return '';

    if (evt.event_type === 'classifier_decision') {
      const pipeline = evt.pipeline_type || evt.classification?.recommended_pipeline;
      const complexity = evt.classification?.complexity;
      if (pipeline || complexity) {
        return `Pipeline: ${pipeline || 'simple'}${complexity ? ` · Complexity: ${complexity}` : ''}`;
      }
    }

    if (evt.event_type === 'pipeline_selected' && evt.pipeline_type) {
      return `Selected pipeline: ${evt.pipeline_type}`;
    }

    return evt.output_preview || '';
  }

  function _renderTraceItem(evt) {
    const label = _traceLabel(evt);
    const model = evt.model_id ? _escHtml(_shortModel(evt.model_id)) : '';
    const provider = evt.provider ? _escHtml(evt.provider) : '';
    const duration = _formatTraceDuration(evt.duration_ms);
    const previewText = _tracePreview(evt);
    const preview = previewText ? `<div class="ai-thinking-item__preview">${_escHtml(previewText)}</div>` : '';
    const chain = evt.fallback_chain?.length ? `<span class="ai-thinking-item__chip">fallback</span>` : '';
    const attempt = evt.attempt_count && evt.attempt_count > 1 ? `<span class="ai-thinking-item__chip">${evt.attempt_count} attempts</span>` : '';
    return `
      <div class="ai-thinking-item ai-thinking-item--${evt.event_type || 'step'}">
        <div class="ai-thinking-item__row">
          <span class="ai-thinking-item__title">${_escHtml(label)}</span>
          ${provider ? `<span class="ai-thinking-item__meta">${provider}</span>` : ''}
          ${model ? `<span class="ai-thinking-item__meta">${model}</span>` : ''}
          ${duration ? `<span class="ai-thinking-item__meta">${duration}</span>` : ''}
          ${chain}
          ${attempt}
        </div>
        ${preview}
      </div>
    `;
  }

  function _renderThinkingPanel(trace, open = false) {
    if (!trace || !trace.length) return '';
    const stepCount = trace.filter(evt => evt.event_type === 'step_complete').length;
    return `
      <div class="ai-thinking ${open ? 'open' : ''}">
        <button class="ai-thinking__toggle" type="button" aria-expanded="${open ? 'true' : 'false'}">
          <span class="ai-thinking__title">Thinking</span>
          <span class="ai-thinking__summary">${_formatStepCount(stepCount)}</span>
          <span class="ai-thinking__chevron" aria-hidden="true">▾</span>
        </button>
        <div class="ai-thinking__body">
          <div class="ai-thinking__list">${trace.map(_renderTraceItem).join('')}</div>
        </div>
      </div>
    `;
  }

  /* ---- Message rendering ----------------------------------- */
  function _appendMessage(role, content, meta, messageId = null) {
    // Hide empty state
    _showEmpty(false);

    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    const div = document.createElement('div');
    div.className = `ai-message ai-message--${role}`;
    div.dataset.role = role;
    if (messageId) div.dataset.messageId = messageId;

    let headerHtml = '';
    if (role === 'assistant') {
      const pipelineType = meta?.pipeline_type || 'simple';
      const model = meta?.model ? `<span style="color:var(--text-disabled)">${_escHtml(meta.model.split('/').pop())}</span>` : '';
      const duration = meta?.duration_ms ? `<span style="color:var(--text-disabled)">${(meta.duration_ms/1000).toFixed(1)}s</span>` : '';
      headerHtml = `
        <div class="ai-message__header">
          <span class="ai-pipeline-badge ai-pipeline-badge--${pipelineType}">${pipelineType}</span>
          ${model}
          ${duration}
          <span>${time}</span>
        </div>`;
    } else {
      headerHtml = `<div class="ai-message__header"><span>${time}</span></div>`;
    }

    const bubbleContent = role === 'assistant'
      ? _renderMarkdown(content, { assistantMessageId: messageId || '' })
      : `<p>${_escHtml(content).replace(/\n/g, '<br>')}</p>`;
    const trace = meta?.pipeline?.trace || meta?.trace || [];
    const thinkingHtml = role === 'assistant' ? _renderThinkingPanel(trace) : '';

    div.innerHTML = `
      ${headerHtml}
      <div class="ai-message__bubble">${bubbleContent}</div>
      ${thinkingHtml}
    `;

    _el.thread.appendChild(div);
    return div;
  }

  function _showEmpty(show) {
    if (_el.threadEmpty) {
      _el.threadEmpty.style.display = show ? '' : 'none';
    }
  }

  /* ---- Streaming ------------------------------------------- */
  async function _sendMessage(overrideText = null, opts = {}) {
    const text = (overrideText ?? _el.textarea.value).trim();
    if (!text || _state.streaming) return;

    if (overrideText === null) {
      _el.textarea.value = '';
      _resizeTextarea();
    }
    _state.streaming = true;
    _el.sendBtn.style.display = 'none';
    _el.stopBtn.style.display = '';
    _setStatus('');

    _appendMessage('user', text, opts.userMeta || {});
    _scrollThread();

    // Create assistant bubble for streaming
    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'ai-message ai-message--assistant';
    const headerDiv = document.createElement('div');
    headerDiv.className = 'ai-message__header';
    headerDiv.innerHTML = `
      <span class="ai-pipeline-badge ai-pipeline-badge--simple" id="ai-streaming-badge">simple</span>
      <span id="ai-streaming-model" style="color:var(--text-disabled)"></span>
    `;
    const bubble = document.createElement('div');
    bubble.className = 'ai-message__bubble';
    bubble.innerHTML = '<span class="ai-streaming-cursor"></span>';
    const thinking = document.createElement('div');
    thinking.className = 'ai-thinking open';
    thinking.innerHTML = `
      <button class="ai-thinking__toggle" type="button" aria-expanded="true">
        <span class="ai-thinking__title">Thinking</span>
        <span class="ai-thinking__summary">starting...</span>
        <span class="ai-thinking__chevron" aria-hidden="true">▾</span>
      </button>
      <div class="ai-thinking__body">
        <div class="ai-thinking__list"></div>
      </div>
    `;
    const thinkingList = thinking.querySelector('.ai-thinking__list');
    const thinkingSummary = thinking.querySelector('.ai-thinking__summary');
    assistantDiv.appendChild(headerDiv);
    assistantDiv.appendChild(bubble);
    assistantDiv.appendChild(thinking);
    _el.thread.appendChild(assistantDiv);
    _scrollThread();

    let fullText = '';
    let finalPipeline = null;
    let finalAssistantMessageId = null;
    let aborted = false;
    let traceEvents = [];

    const renderTrace = () => {
      if (!thinkingList || !thinkingSummary) return;
      thinkingList.innerHTML = traceEvents.map(_renderTraceItem).join('');
      const stepCount = traceEvents.filter(evt => evt.event_type === 'step_complete').length;
      thinkingSummary.textContent = stepCount ? _formatStepCount(stepCount) : `${traceEvents.length} events`;
    };

    const body = JSON.stringify({
      message: text,
      thread_id: _state.conversationId,
      conversation_id: _state.conversationId,
      provider: _state.provider,
      model: _state.model || undefined,
      goal_id: _state.goal || 'balanced',
      context_run_id: _state.contextRunId || undefined,
    });

    const controller = new AbortController();
    _state.streamController = controller;

    _el.stopBtn.onclick = () => {
      aborted = true;
      controller.abort();
      _finishStream(assistantDiv, bubble, headerDiv, fullText, null, null);
    };

    try {
      const resp = await fetch('/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal: controller.signal,
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      if (!resp.body) {
        throw new Error('AI stream did not return a response body');
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));

            if (evt.event_type && evt.event_type !== 'final') {
              traceEvents.push(evt);
              renderTrace();
            }

            if (evt.event_type === 'classifier_decision' || evt.event_type === 'pipeline_selected') {
              const badge = document.getElementById('ai-streaming-badge');
              if (badge) {
                const pipelineType = evt.pipeline_type || 'simple';
                badge.className = `ai-pipeline-badge ai-pipeline-badge--${pipelineType}`;
                badge.textContent = pipelineType;
              }
              if (evt.pipeline_type) _setStatus(`Pipeline: ${evt.pipeline_type}...`);
            }

            if (evt.status === 'judging') _setStatus('Judging analyst arguments...');
            if (evt.status === 'generating_code') _setStatus('Generating code...');
            if (evt.status === 'validating_code') _setStatus('Validating code...');
            if (evt.status === 'explaining') _setStatus('Explaining changes...');

            if (evt.status === 'classified') {
              const badge = document.getElementById('ai-streaming-badge');
              if (badge) {
                badge.className = `ai-pipeline-badge ai-pipeline-badge--${evt.pipeline_type}`;
                badge.textContent = evt.pipeline_type;
              }
              _setStatus(`Pipeline: ${evt.pipeline_type}…`);
            }

            if (evt.status === 'reasoning') _setStatus('Reasoning…');
            if (evt.status === 'composing') _setStatus('Composing response…');

            if (evt.delta) {
              fullText += evt.delta;
              bubble.innerHTML = _renderMarkdown(fullText) + '<span class="ai-streaming-cursor"></span>';
              _scrollThread();
            }

            if (evt.error) {
              bubble.innerHTML = `<span style="color:var(--red)">${_escHtml(evt.error)}</span>`;
              _finishStream(assistantDiv, bubble, headerDiv, '', null, null);
              aborted = true;
              break;
            }

            if (evt.done && !evt.delta) {
              if (evt.thread_id || evt.conversation_id) {
                _state.conversationId = evt.thread_id || evt.conversation_id;
              }
              const pipeline = evt.pipeline || {};
              finalPipeline = pipeline || null;
              finalAssistantMessageId = evt.assistant_message_id || null;
              if (pipeline.trace?.length) {
                traceEvents = pipeline.trace;
                renderTrace();
              }
              const finalText = evt.fullText || fullText;
              if (!finalText) {
                bubble.innerHTML = '<span style="color:var(--amber)">No response received from the AI provider.</span>';
                _finishStream(assistantDiv, bubble, headerDiv, '', null, null);
              } else {
                _finishStream(assistantDiv, bubble, headerDiv, finalText, pipeline, finalAssistantMessageId);
              }
              await _loadConversations();
              aborted = true; // prevent double-finish
              break;
            }
          } catch (_) {}
        }
        if (aborted) break;
      }
    } catch (e) {
      if (!aborted) {
        bubble.innerHTML = `<span style="color:var(--red)">Connection error: ${_escHtml(e.message)}</span>`;
        _finishStream(assistantDiv, bubble, headerDiv, '', null, null);
      }
    }

    if (!aborted) {
      _finishStream(assistantDiv, bubble, headerDiv, fullText, null, null);
    }
    return {
      fullText,
      pipeline: finalPipeline,
      assistantMessageId: finalAssistantMessageId,
    };
  }

  function _finishStream(assistantDiv, bubble, headerDiv, finalText, pipeline, assistantMessageId) {
    // Remove streaming cursor
    const cursor = bubble.querySelector('.ai-streaming-cursor');
    if (cursor) cursor.remove();

    if (finalText) {
      bubble.innerHTML = _renderMarkdown(finalText, { assistantMessageId: assistantMessageId || '' });
      if (assistantMessageId && assistantDiv) {
        assistantDiv.dataset.messageId = assistantMessageId;
      }
    }

    // Update header with final info
    if (pipeline) {
      const badge = headerDiv.querySelector('[id="ai-streaming-badge"]');
      const modelSpan = headerDiv.querySelector('[id="ai-streaming-model"]');
      if (badge) {
        badge.id = '';
        badge.className = `ai-pipeline-badge ai-pipeline-badge--${pipeline.pipeline_type || 'simple'}`;
        badge.textContent = pipeline.pipeline_type || 'simple';
      }
      if (modelSpan) {
        modelSpan.id = '';
        const finalStep = (pipeline.steps || []).slice().reverse().find(step => step.role !== 'classifier') || {};
        const modelName = (finalStep.model_id || '').split('/').pop();
        const totalMs = pipeline.total_duration_ms || pipeline.duration_ms || 0;
        const dur = totalMs ? ` · ${(totalMs/1000).toFixed(1)}s` : '';
        modelSpan.textContent = `${modelName}${dur}`;
      }
    }

    _state.streaming = false;
    _state.streamController = null;
    _el.sendBtn.style.display = '';
    _el.stopBtn.style.display = 'none';
    _setStatus('');
    _checkSendReady();
    _scrollThread();
  }

  /* ---- Deep Analysis panel --------------------------------- */
  async function _openDeepPanel() {
    if (!_state.contextRunId) return;
    _el.deepPanel.classList.add('open');
    // If evo panel is already open, push it left to avoid overlap
    if (_el.evoPanel && _el.evoPanel.classList.contains('open')) {
      _el.evoPanel.classList.add('evo-panel--offset');
    }
    _el.deepPanelBody.innerHTML = `
      <div class="ai-deep-panel__loading">
        <div class="ai-deep-panel__loading-spinner"></div>
        <span>Running deep analysis…</span>
      </div>
    `;

    try {
      const result = await fetch(`/ai/analyze/${_state.contextRunId}`, { method: 'POST' })
        .then(r => r.json());
      _renderDeepPanel(result);
    } catch (e) {
      _el.deepPanelBody.innerHTML = `<div style="color:var(--red);padding:var(--space-4)">Analysis failed: ${_escHtml(e.message)}</div>`;
    }
  }

  function _renderDeepPanel(data) {
    const health = data.health_score || {};
    const score = Math.round(health.total || 0);
    const maxScore = 100;
    const circumference = 251.2;
    const offset = circumference - (score / maxScore) * circumference;
    const color = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--amber)' : 'var(--red)';

    const strengths = (data.strengths || []).slice(0, 6);
    const weaknesses = (data.weaknesses || []).slice(0, 6);
    const params = data.parameter_recommendations || [];
    const narrative = data.narrative || {};

    _el.deepPanelBody.innerHTML = `
      <!-- Health Score Ring -->
      <div class="ai-health-ring-wrap">
        <div class="ai-health-ring">
          <svg width="96" height="96" viewBox="0 0 96 96">
            <circle class="ai-health-ring__track" cx="48" cy="48" r="40"/>
            <circle class="ai-health-ring__fill" cx="48" cy="48" r="40"
              style="stroke:${color}; stroke-dashoffset:${offset}"/>
          </svg>
          <div class="ai-health-ring__label">
            <span class="ai-health-ring__score">${score}</span>
            <span class="ai-health-ring__max">/ ${maxScore}</span>
          </div>
        </div>
        <span class="ai-health-label">Strategy Health Score</span>
      </div>

      ${strengths.length ? `
      <div class="ai-analysis-section">
        <div class="ai-analysis-section__head">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Strengths
        </div>
        <div class="ai-analysis-section__body">
          ${strengths.map(s => `<div class="ai-strength-item">${_escHtml(typeof s === 'string' ? s : s.finding || '')}</div>`).join('')}
        </div>
      </div>` : ''}

      ${weaknesses.length ? `
      <div class="ai-analysis-section">
        <div class="ai-analysis-section__head">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
          Weaknesses
        </div>
        <div class="ai-analysis-section__body">
          ${weaknesses.map(w => `<div class="ai-weakness-item">${_escHtml(typeof w === 'string' ? w : w.finding || '')}</div>`).join('')}
        </div>
      </div>` : ''}

      ${params.length ? `
      <div class="ai-analysis-section">
        <div class="ai-analysis-section__head">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--violet)" stroke-width="2">
            <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
          </svg>
          Parameter Recommendations
        </div>
        <div class="ai-analysis-section__body">
          ${params.slice(0, 8).map(p => `
            <div class="ai-param-rec">
              <span class="ai-param-rec__name">${_escHtml(p.parameter || p.name || '')}</span>
              <span class="ai-param-rec__value">${_escHtml(p.suggestion || p.value || '')}</span>
            </div>
          `).join('')}
        </div>
      </div>` : ''}

      ${narrative.summary ? `
      <div class="ai-analysis-section">
        <div class="ai-analysis-section__head">Summary</div>
        <div class="ai-analysis-section__body">
          <div class="ai-narrative-text">${_escHtml(narrative.summary)}</div>
        </div>
      </div>` : ''}

      ${narrative.whats_working ? `
      <div class="ai-analysis-section">
        <div class="ai-analysis-section__head">What's Working</div>
        <div class="ai-analysis-section__body">
          <div class="ai-narrative-text">${_escHtml(narrative.whats_working)}</div>
        </div>
      </div>` : ''}

      ${narrative.whats_not ? `
      <div class="ai-analysis-section">
        <div class="ai-analysis-section__head">What's Not Working</div>
        <div class="ai-analysis-section__body">
          <div class="ai-narrative-text">${_escHtml(narrative.whats_not)}</div>
        </div>
      </div>` : ''}

      ${narrative.next_steps ? `
      <div class="ai-analysis-section">
        <div class="ai-analysis-section__head">Next Steps</div>
        <div class="ai-analysis-section__body">
          <div class="ai-narrative-text">${_escHtml(narrative.next_steps)}</div>
        </div>
      </div>` : ''}
    `;
  }

  /* ---- Helpers --------------------------------------------- */
  function _setStatus(msg) {
    if (!_el.statusLine) return;
    if (msg) {
      _el.statusLine.innerHTML = `<div class="ai-status-spinner"></div><span>${_escHtml(msg)}</span>`;
    } else {
      _el.statusLine.innerHTML = '';
    }
  }

  function _scrollThread() {
    if (_el.thread) {
      _el.thread.scrollTop = _el.thread.scrollHeight;
    }
  }

  function _resizeTextarea() {
    const ta = _el.textarea;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }

  function _checkSendReady() {
    if (!_el.sendBtn || !_el.textarea) return;
    const hasText = (_el.textarea.value || '').trim().length > 0;
    const hasModel = !!_state.model || !!_el.modelSelect?.value;
    _el.sendBtn.disabled = !hasText || _state.streaming;
  }

  function _idemKey(prefix = 'k') {
    return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  }

  function _durationSuffix(evt) {
    const ms = Number(evt?.duration_ms || 0);
    if (!ms) return '';
    return ms >= 1000 ? ` (${(ms / 1000).toFixed(1)}s)` : ` (${ms}ms)`;
  }

  function _strategyFromFilename(filename) {
    const raw = String(filename || '').trim();
    if (!raw) return '';
    return raw.toLowerCase().endsWith('.py') ? raw.slice(0, -3) : raw;
  }

  function _renderLoopTable(rows) {
    const safeRows = Array.isArray(rows) ? rows : [];
    if (!safeRows.length) return '_No result rows available._';
    const lines = [
      '| Section | Metric | Before | After | Delta |',
      '|---|---|---:|---:|---:|',
      ...safeRows.map((r) => `| ${r.section || ''} | ${r.metric || ''} | ${r.before ?? ''} | ${r.after ?? ''} | ${r.delta ?? ''} |`),
    ];
    return ['```text', ...lines, '```'].join('\n');
  }

  function _renderLoopFileChanges(fileChanges) {
    const py = fileChanges?.strategy_py || {};
    const js = fileChanges?.strategy_json || {};
    const snippet = [];
    const pyPreview = Array.isArray(py.diff_preview) ? py.diff_preview.slice(0, 40) : [];
    const jsonPreview = Array.isArray(js.diff_preview) ? js.diff_preview.slice(0, 40) : [];
    if (pyPreview.length) snippet.push(`# ${py.path || 'strategy.py'}\n${pyPreview.join('\n')}`);
    if (jsonPreview.length) snippet.push(`# ${js.path || 'strategy.json'}\n${jsonPreview.join('\n')}`);
    const body = snippet.length ? `\n\n\`\`\`diff\n${snippet.join('\n\n')}\n\`\`\`` : '';
    return `- \`.py\`: **${py.changed ? 'changed' : 'unchanged'}**\n- \`.json\`: **${js.changed ? 'changed' : 'unchanged'}**${body}`;
  }

  function _renderLoopTests(testResults) {
    const tests = Array.isArray(testResults) ? testResults : [];
    if (!tests.length) return '_No tests were captured._';
    const rows = [
      '| Test | OK | Code | Duration (ms) |',
      '|---|---|---:|---:|',
      ...tests.map((t) => `| ${t.name || ''} | ${t.ok ? 'yes' : 'no'} | ${t.code ?? ''} | ${t.duration_ms ?? ''} |`),
    ];
    const snippets = tests
      .slice(0, 3)
      .map((t) => {
        const out = String(t.stderr || t.stdout || '(no output)').slice(0, 500);
        return `### ${t.name || 'test'}\n\`\`\`text\n${out}\n\`\`\``;
      })
      .join('\n\n');
    return `${['```text', ...rows, '```'].join('\n')}\n\n${snippets}`;
  }

  async function _confirmLoopRerun(loopId, confirm) {
    await fetch(`/ai/loop/${encodeURIComponent(loopId)}/confirm-rerun`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: !!confirm, idempotency_key: _idemKey('confirm') }),
    });
  }

  async function _stopLoopRemote() {
    if (_state.loopId) {
      try {
        await fetch(`/ai/loop/${encodeURIComponent(_state.loopId)}/stop`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ idempotency_key: _idemKey('stop') }),
        });
      } catch (_) {}
    }
    _closeLoopStream();
    _state.loopBusy = false;
    _state.loopEnabled = false;
    _state.loopId = null;
    _updateLoopButton();
  }

  function _handleLoopEvent(evt) {
    const step = String(evt.step || '');
    if (step === 'loop_started') {
      const planned = (evt.planned_steps || []).map((s, i) => `${i + 1}. ${s}`).join('\n');
      _appendMessage('assistant', `Loop started${_durationSuffix(evt)}.\n\nPlanned workflow:\n${planned || '1. apply\n2. validate\n3. rerun\n4. compare\n5. test\n6. report'}`, { auto_loop: true });
      return;
    }
    if (step === 'apply_done') {
      const applyResult = evt.apply_result || {};
      _state.lastApplied = applyResult;
      _appendMessage('assistant', `Applied update to **${applyResult.strategy || evt.strategy || 'strategy'}**${_durationSuffix(evt)}.\n\n${_renderLoopFileChanges(evt.file_changes || applyResult.file_changes || {})}`, { auto_loop: true });
      return;
    }
    if (step === 'ai_validate_done') {
      _appendMessage('assistant', `Validation complete${_durationSuffix(evt)}:\n\n${evt.validation_text || '_No validation text._'}`, { auto_loop: true });
      if (_state.loopEnabled && _state.loopId === evt.loop_id) {
        _state.pendingRerunPrompt = true;
        const confirm = window.confirm('Loop validation finished. Run rerun now?');
        _state.pendingRerunPrompt = false;
        _confirmLoopRerun(evt.loop_id, confirm).catch(() => Toast.error('Could not send rerun confirmation'));
      }
      return;
    }
    if (step === 'rerun_started') {
      _appendMessage('assistant', `Rerun started${_durationSuffix(evt)}.\n\n\`\`\`json\n${JSON.stringify(evt.rerun_request || {}, null, 2)}\n\`\`\``, { auto_loop: true });
      return;
    }
    if (step === 'rerun_done') {
      _appendMessage('assistant', `Rerun finished${_durationSuffix(evt)} with status **${evt.status || 'unknown'}** (run_id: \`${evt.run_id || 'n/a'}\`).`, { auto_loop: true });
      return;
    }
    if (step === 'result_diff') {
      _appendMessage('assistant', `Result delta summary${_durationSuffix(evt)}:\n\n${_renderLoopTable(evt.table_rows)}`, { auto_loop: true });
      return;
    }
    if (step === 'file_diff') {
      _appendMessage('assistant', `File delta summary:\n\n${_renderLoopFileChanges(evt.file_changes || {})}`, { auto_loop: true });
      return;
    }
    if (step === 'tests_done') {
      _appendMessage('assistant', `Validation test pack${_durationSuffix(evt)}:\n\n${_renderLoopTests(evt.test_results)}`, { auto_loop: true });
      return;
    }
    if (step === 'cycle_done') {
      if (evt.run_id) {
        _state.contextRunId = evt.run_id;
        if (_state.lastApplied?.strategy) _state.contextStrategyName = _state.lastApplied.strategy;
        _updateContextBar();
      }
      const reportLinks = evt.report_download_url
        ? `\n\n[Download Report](${evt.report_download_url}) · [View Report](${evt.report_url || '#'})`
        : (evt.md_report_path ? `\n\nReport: \`${evt.md_report_path}\`` : '');
      const metrics = evt.metrics?.summary || {};
      const metricsLine = Object.keys(metrics).length
        ? `\n\nLatency metrics captured for ${Object.keys(metrics).length} steps.`
        : '';
      _appendMessage('assistant', `Cycle completed.\n\n${evt.message || 'Review complete.'}${reportLinks}${metricsLine}`, { auto_loop: true });
      _state.loopBusy = false;
      _state.loopId = null;
      _closeLoopStream();
      _updateLoopButton();
      return;
    }
    if (step === 'loop_stopped') {
      _appendMessage('assistant', `Loop stopped.\n\n${evt.message || 'Stopped by user.'}`, { auto_loop: true });
      _state.loopBusy = false;
      _state.loopEnabled = false;
      _state.loopId = null;
      _closeLoopStream();
      _updateLoopButton();
      return;
    }
    if (step === 'loop_failed') {
      _appendMessage('assistant', `Loop failed:\n\n${evt.message || 'Unknown error.'}`, { auto_loop: true });
      _state.loopBusy = false;
      _state.loopId = null;
      _closeLoopStream();
      _updateLoopButton();
    }
  }

  async function _startLoopFromBlock({ assistantMessageId, blockIndex, fallbackStrategy }) {
    if (!_state.conversationId) throw new Error('No active thread');
    if (!_state.contextRunId) throw new Error('Inject backtest context first');
    if (_state.loopBusy) throw new Error('Loop is already running');

    const payload = {
      thread_id: _state.conversationId,
      assistant_message_id: assistantMessageId,
      code_block_index: blockIndex,
      fallback_strategy: fallbackStrategy || undefined,
      context_run_id: _state.contextRunId,
      provider: _state.provider || 'openrouter',
      model: _state.model || undefined,
      goal_id: _state.goal || 'balanced',
      idempotency_key: _idemKey('start'),
      rollback_on_regression: true,
      stop_rules: {
        min_profit_delta: 0,
        max_drawdown_increase: 0,
        require_tests_pass: true,
      },
    };
    const res = await fetch('/ai/loop/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.loop_id) throw new Error(data.detail || `Loop start failed: HTTP ${res.status}`);

    _state.loopBusy = true;
    _state.loopId = data.loop_id;
    _updateLoopButton();
    _appendMessage('assistant', 'Loop started in semi-auto mode.\n\nI will apply code, validate with AI, wait for your rerun confirmation, rerun backtest, compare results, diff files, run tests, and write a markdown audit report.', { auto_loop: true });

    _closeLoopStream();
    const es = new EventSource(`/ai/loop/${encodeURIComponent(data.loop_id)}/stream`);
    _state.loopStream = es;
    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        _handleLoopEvent(evt);
        if (evt.done) {
          try { es.close(); } catch (_) {}
          if (_state.loopStream === es) _state.loopStream = null;
        }
      } catch (_) {}
    };
    es.onerror = () => {
      try { es.close(); } catch (_) {}
      if (_state.loopStream === es) _state.loopStream = null;
      if (_state.loopBusy) {
        _state.loopBusy = false;
        _state.loopId = null;
        _updateLoopButton();
        Toast.error('Loop stream disconnected');
      }
    };
  }

  async function _handleCodeAction(action, blockEl) {
    if (!blockEl) return;
    const pre = blockEl.querySelector('pre');
    const code = pre ? pre.textContent : '';
    const codeLang = String(blockEl.dataset.codeLang || '');
    const assistantMessageId = blockEl.dataset.assistantMessageId || '';
    const blockIndex = Number(blockEl.dataset.codeBlockIndex || -1);
    const inferredFilename = blockEl.dataset.inferredFilename || '';

    if (action === 'copy') {
      if (!code) return;
      await navigator.clipboard.writeText(code);
      Toast.success('Code copied');
      return;
    }

    if (action === 'diff') {
      if (!/^python|py$/i.test(codeLang)) return;
      const strategyHint = _strategyFromFilename(inferredFilename) || _state.contextStrategyName || '';
      if (!strategyHint) {
        Toast.error('Cannot open diff: no strategy file inferred');
        return;
      }
      const resp = await fetch(`/strategies/${encodeURIComponent(strategyHint)}/source`);
      if (!resp.ok) {
        Toast.error(`Cannot load current source for ${strategyHint}.py`);
        return;
      }
      const currentSrc = await resp.text();
      _el.evoDiffTitle.textContent = `Code Diff — ${strategyHint}.py (chat proposal)`;
      _renderCodeDiff(currentSrc, code);
      _el.evoDiffOverlay.classList.add('open');
      return;
    }

    if (action === 'apply') {
      if (!/^python|py$/i.test(codeLang)) return;
      if (!_state.conversationId) {
        Toast.error('No active thread yet. Send a chat message first.');
        return;
      }
      const fallbackStrategy = _state.contextStrategyName || _strategyFromFilename(inferredFilename) || undefined;
      if (_state.loopEnabled) {
        await _startLoopFromBlock({
          assistantMessageId,
          blockIndex,
          fallbackStrategy,
        });
        return;
      }
      const payload = {
        thread_id: _state.conversationId,
        assistant_message_id: assistantMessageId,
        code_block_index: blockIndex,
        fallback_strategy: fallbackStrategy,
      };
      const res = await fetch('/ai/chat/apply-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        Toast.error(data.detail || `Apply failed: HTTP ${res.status}`);
        return;
      }
      _state.lastApplied = data;
      Toast.success(`Applied to ${data.strategy}.py`);
    }
  }

  /* ---- Evolution panel ------------------------------------ */

  function _openEvolutionPanel() {
    _el.evoPanel.classList.add('open');
    // If deep analysis panel is also open, offset evo panel to avoid overlap
    if (_el.deepPanel && _el.deepPanel.classList.contains('open')) {
      _el.evoPanel.classList.add('evo-panel--offset');
    } else {
      _el.evoPanel.classList.remove('evo-panel--offset');
    }
    _evoSwitchTab('config');
    _renderEvoConfig();
  }

  function _evoSwitchTab(tab) {
    _evo.activeTab = tab;
    ['config', 'running', 'results'].forEach(t => {
      document.getElementById(`evo-tab-${t}`)?.classList.toggle('active', t === tab);
    });
    if (tab === 'config')   _renderEvoConfig();
    if (tab === 'running')  _renderEvoRunning();
    if (tab === 'results')  _renderEvoResults();
  }

  /* ---- Config tab ----------------------------------------- */

  function _renderEvoConfig() {
    const strat = _state.contextStrategyName || 'strategy';
    _el.evoPanelBody.innerHTML = `
      <div class="evo-config-form">
        <div class="evo-field">
          <label class="evo-label">Goal</label>
          <select class="evo-select" id="evo-goal-select">
            <option value="">Auto (AI decides)</option>
            <option value="lower_drawdown">Lower Drawdown</option>
            <option value="higher_win_rate">Higher Win Rate</option>
            <option value="higher_profit">Higher Profit</option>
            <option value="more_trades">More Trades</option>
            <option value="cut_losers">Cut Losers</option>
            <option value="lower_risk">Lower Risk</option>
            <option value="scalping">Scalping</option>
            <option value="swing_trading">Swing Trading</option>
            <option value="compound_growth">Compound Growth</option>
          </select>
        </div>
        <div class="evo-field">
          <label class="evo-label">Max Generations</label>
          <input class="evo-input" type="number" id="evo-max-gen" min="1" max="5" value="3">
        </div>
        <div class="evo-field">
          <label class="evo-label">Provider</label>
          <select class="evo-select" id="evo-provider-select">
            <option value="openrouter" ${_state.provider === 'openrouter' ? 'selected' : ''}>OpenRouter</option>
            <option value="ollama" ${_state.provider === 'ollama' ? 'selected' : ''}>Ollama</option>
          </select>
        </div>
        <div class="evo-field">
          <label class="evo-label">Model (optional override)</label>
          <select class="evo-select" id="evo-model-select">
            <option value="">Same as chat</option>
          </select>
        </div>
        <p style="font-size:var(--text-xs);color:var(--text-muted);margin:0">
          Evolving <strong style="color:var(--text-secondary)">${_escHtml(strat)}</strong>
          from run <code style="font-size:10px">${_escHtml(_state.contextRunId || '')}</code>.
          Each generation mutates the strategy, runs a backtest, and keeps the best result.
        </p>
        <button class="evo-start-btn" id="evo-start-btn">Start Evolution</button>
      </div>
    `;

    // Populate model dropdown from current provider models
    const modelSel = document.getElementById('evo-model-select');
    const provSel  = document.getElementById('evo-provider-select');
    const _fillModels = () => {
      const prov = provSel.value;
      const models = prov === 'ollama'
        ? (_state.providers?.ollama?.models || [])
        : (_state.providers?.openrouter?.models || []);
      modelSel.innerHTML = '<option value="">Same as chat</option>';
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name || m.id;
        if (m.id === _state.model) opt.selected = true;
        modelSel.appendChild(opt);
      });
    };
    _fillModels();
    provSel.addEventListener('change', _fillModels);

    document.getElementById('evo-start-btn').addEventListener('click', async () => {
      const goalId    = document.getElementById('evo-goal-select').value || null;
      const maxGen    = parseInt(document.getElementById('evo-max-gen').value, 10) || 3;
      const provider  = document.getElementById('evo-provider-select').value;
      const model     = document.getElementById('evo-model-select').value || null;
      await _startEvolution({ goalId, maxGen, provider, model });
    });
  }

  /* ---- Start evolution ------------------------------------ */

  async function _startEvolution({ goalId, maxGen, provider, model }) {
    if (!_state.contextRunId) return;

    const startBtn = document.getElementById('evo-start-btn');
    if (startBtn) { startBtn.disabled = true; startBtn.textContent = 'Starting…'; }

    try {
      const resp = await fetch('/evolution/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_id: _state.contextRunId,
          goal_id: goalId,
          max_generations: maxGen,
          provider,
          model,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const { loop_id } = await resp.json();
      _evo.loopId = loop_id;
      _evo.maxGenerations = maxGen;
      _evo.generations = [];

      // Capture original source for diff
      _evo.originalSource = null;
      try {
        const versResp = await fetch(`/evolution/versions/${encodeURIComponent(_state.contextStrategyName || '')}`);
        // We'll fetch source lazily when diff is opened
      } catch (_) {}

      _evoSwitchTab('running');
      _listenEvolutionStream(loop_id, maxGen);
    } catch (e) {
      if (startBtn) { startBtn.disabled = false; startBtn.textContent = 'Start Evolution'; }
      _showEvoToast(`Failed to start: ${e.message}`, true);
    }
  }

  /* ---- Running tab ---------------------------------------- */

  function _renderEvoRunning() {
    _el.evoPanelBody.innerHTML = `
      <div class="evo-progress-wrap" id="evo-progress-wrap">
        <div class="evo-progress-label">
          <span id="evo-progress-text">Generation 0 / ${_evo.maxGenerations}</span>
          <span id="evo-progress-pct">0%</span>
        </div>
        <div class="evo-progress-track">
          <div class="evo-progress-fill" id="evo-progress-fill" style="width:0%"></div>
        </div>
      </div>
      <div id="evo-gen-cards"></div>
    `;

    // Re-render any already-received generations
    _evo.generations.forEach(evt => _renderGenerationCard(evt));
  }

  /* ---- SSE stream listener -------------------------------- */

  function _listenEvolutionStream(loopId, maxGen) {
    let buffer = '';
    const ctrl = new AbortController();
    _evo.evtSource = ctrl;

    fetch(`/evolution/stream/${loopId}`, { signal: ctrl.signal })
      .then(resp => {
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();

        const pump = () => reader.read().then(({ done, value }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const evt = JSON.parse(line.slice(6));
              _handleEvoEvent(evt, maxGen);
            } catch (_) {}
          }
          pump();
        }).catch(() => {});

        pump();
      })
      .catch(() => {});
  }

  function _handleEvoEvent(evt, maxGen) {
    const step = evt.step;

    if (step === 'comparing') {
      _evo.generations.push(evt);
      const gen = evt.generation || _evo.generations.length;
      _updateEvoProgress(gen, maxGen);
      if (_evo.activeTab === 'running') _renderGenerationCard(evt);
    }

    if (step === 'analyzing' || step === 'mutating' || step === 'backtesting') {
      _updateActiveGenStep(evt);
    }

    if (step === 'done' || evt.done) {
      if (_evo.activeTab === 'running') {
        setTimeout(() => _evoSwitchTab('results'), 1200);
      }
    }

    if (step === 'error') {
      _showEvoToast(`Evolution error: ${evt.message}`, true);
    }
  }

  function _updateEvoProgress(gen, maxGen) {
    const pct = Math.round((gen / maxGen) * 100);
    const fill = document.getElementById('evo-progress-fill');
    const text = document.getElementById('evo-progress-text');
    const pctEl = document.getElementById('evo-progress-pct');
    if (fill) fill.style.width = pct + '%';
    if (text) text.textContent = `Generation ${gen} / ${maxGen}`;
    if (pctEl) pctEl.textContent = pct + '%';
  }

  // Track the "in-progress" card for live step updates
  let _activeGenCard = null;

  function _updateActiveGenStep(evt) {
    if (_evo.activeTab !== 'running') return;
    const container = document.getElementById('evo-gen-cards');
    if (!container) return;

    const gen = evt.generation;
    let card = container.querySelector(`[data-gen="${gen}"]`);
    if (!card) {
      card = document.createElement('div');
      card.className = 'evo-gen-card';
      card.dataset.gen = gen;
      card.innerHTML = `
        <div class="evo-gen-card__head">
          <span>Generation ${gen} of ${_evo.maxGenerations}</span>
          <span style="color:#8b5cf6;font-size:10px">🔄 Live</span>
        </div>
        <div class="evo-gen-card__body" id="evo-card-body-${gen}">
          <div class="evo-step evo-step--pending" id="evo-step-analyzing-${gen}">
            <span class="evo-step__icon"></span><span>Analyzing backtest…</span>
          </div>
          <div class="evo-step evo-step--pending" id="evo-step-mutating-${gen}">
            <span class="evo-step__icon"></span><span>AI mutating strategy code…</span>
          </div>
          <div class="evo-step evo-step--pending" id="evo-step-backtesting-${gen}">
            <span class="evo-step__icon"></span><span>Running backtest…</span>
          </div>
          <div class="evo-step evo-step--pending" id="evo-step-comparing-${gen}">
            <span class="evo-step__icon"></span><span>Comparing results…</span>
          </div>
        </div>
      `;
      container.appendChild(card);
    }

    const stepMap = { analyzing: 'analyzing', mutating: 'mutating', backtesting: 'backtesting' };
    const stepKey = stepMap[evt.step];
    if (stepKey) {
      // Mark previous steps done
      const order = ['analyzing', 'mutating', 'backtesting', 'comparing'];
      const idx = order.indexOf(stepKey);
      order.slice(0, idx).forEach(s => {
        const el = document.getElementById(`evo-step-${s}-${gen}`);
        if (el) { el.className = 'evo-step evo-step--done'; }
      });
      const el = document.getElementById(`evo-step-${stepKey}-${gen}`);
      if (el) {
        el.className = 'evo-step evo-step--running';
        const label = el.querySelector('span:last-child');
        if (label && evt.message) label.textContent = evt.message;
      }
    }
  }

  /* ---- Render a completed generation card ----------------- */

  function _renderGenerationCard(evt) {
    const container = document.getElementById('evo-gen-cards');
    if (!container) return;

    const gen = evt.generation;
    const accepted = evt.accepted;
    const fitBefore = (evt.fitness_before || 0).toFixed(1);
    const fitAfter  = (evt.fitness_after  || 0).toFixed(1);
    const delta     = evt.delta || '0';
    const deltaNum  = parseFloat(delta);
    const deltaClass = deltaNum > 0 ? 'pos' : deltaNum < 0 ? 'neg' : 'zero';
    const badgeClass = accepted ? 'accepted' : 'rejected';
    const badgeText  = accepted ? 'ACCEPTED' : 'REJECTED';
    const changes    = evt.changes_summary || '';
    const newRunId   = evt.new_run_id || '';
    const versionName = evt.version_name || '';

    // Replace live card if it exists, otherwise append
    let card = container.querySelector(`[data-gen="${gen}"]`);
    if (!card) {
      card = document.createElement('div');
      card.dataset.gen = gen;
      container.appendChild(card);
    }
    card.className = 'evo-gen-card';

    const barWidth = Math.min(parseFloat(fitAfter), 100).toFixed(1);

    card.innerHTML = `
      <div class="evo-gen-card__head">
        <span>Generation ${gen} of ${_evo.maxGenerations}</span>
        <span class="evo-badge evo-badge--${badgeClass}">${badgeText}</span>
      </div>
      <div class="evo-gen-card__body">
        <div class="evo-step evo-step--done"><span class="evo-step__icon"></span><span>Analyzed backtest</span></div>
        <div class="evo-step evo-step--done"><span class="evo-step__icon"></span><span>AI mutated strategy code</span></div>
        <div class="evo-step evo-step--done"><span class="evo-step__icon"></span><span>Ran backtest on ${_escHtml(versionName)}</span></div>
        <div class="evo-step evo-step--done"><span class="evo-step__icon"></span><span>Compared results</span></div>

        <div class="evo-fitness-row">
          <div class="evo-fitness-numbers">
            <span>${fitBefore}</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            <span>${fitAfter}</span>
          </div>
          <span class="evo-fitness-delta evo-fitness-delta--${deltaClass}">(${delta})</span>
          <div class="evo-fitness-bar-wrap">
            <div class="evo-fitness-bar" style="width:${barWidth}%"></div>
          </div>
        </div>

        ${changes ? `<div class="evo-changes">&ldquo;${_escHtml(changes)}&rdquo;</div>` : ''}

        <div class="evo-card-actions">
          ${versionName ? `<button class="evo-link" onclick="window.AIDiagPage._openDiff('${_escHtml(versionName)}')">View Code Diff</button>` : ''}
          ${newRunId ? `<button class="evo-link" onclick="window.location.hash='results/${_escHtml(newRunId)}'">View Backtest</button>` : ''}
        </div>
      </div>
    `;
  }

  /* ---- Results tab ---------------------------------------- */

  async function _renderEvoResults() {
    if (!_evo.loopId) {
      _el.evoPanelBody.innerHTML = '<p style="color:var(--text-muted);font-size:var(--text-sm)">No evolution run yet.</p>';
      return;
    }

    _el.evoPanelBody.innerHTML = '<div style="color:var(--text-muted);font-size:var(--text-sm)">Loading results…</div>';

    try {
      const data = await fetch(`/evolution/run/${_evo.loopId}`).then(r => r.json());
      const session = data.session || {};
      const gens = data.generations || [];

      const bestFitness = (session.best_fitness || 0).toFixed(1);
      const bestVersion = session.best_version || '—';
      const initialFitness = gens.length ? (gens[0].fitness_before || 0).toFixed(1) : '—';
      const totalDelta = gens.length ? ((session.best_fitness || 0) - (gens[0].fitness_before || 0)).toFixed(1) : '0';
      const totalDeltaNum = parseFloat(totalDelta);
      const deltaClass = totalDeltaNum > 0 ? 'pos' : totalDeltaNum < 0 ? 'neg' : 'zero';

      // Find best generation index
      let bestGen = 1;
      gens.forEach(g => { if (g.version_name === session.best_version) bestGen = g.generation; });

      const rows = gens.map(g => {
        const acc = g.accepted;
        const badge = acc ? 'accepted' : 'rejected';
        const label = acc ? 'Accepted' : 'Rejected';
        const d = (g.delta || 0).toFixed(1);
        const dNum = parseFloat(d);
        const dc = dNum > 0 ? 'pos' : dNum < 0 ? 'neg' : 'zero';
        return `
          <tr>
            <td>${g.generation}</td>
            <td style="font-family:var(--font-mono);font-size:10px">${_escHtml(g.version_name || '—')}</td>
            <td>${(g.fitness_after || 0).toFixed(1)}</td>
            <td class="evo-fitness-delta evo-fitness-delta--${dc}">${dNum > 0 ? '+' : ''}${d}</td>
            <td><span class="evo-badge evo-badge--${badge}">${label}</span></td>
          </tr>
        `;
      }).join('');

      _el.evoPanelBody.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3)">
          <div class="evo-summary-card">
            <div class="evo-summary-card__title">Best Version</div>
            <div class="evo-summary-card__value" style="font-size:var(--text-sm);font-family:var(--font-mono)">${_escHtml(bestVersion)}</div>
          </div>
          <div class="evo-summary-card">
            <div class="evo-summary-card__title">Fitness</div>
            <div class="evo-summary-card__value">${initialFitness} → ${bestFitness}</div>
            <div class="evo-summary-card__sub evo-fitness-delta evo-fitness-delta--${deltaClass}">${totalDeltaNum >= 0 ? '+' : ''}${totalDelta}</div>
          </div>
        </div>

        <table class="evo-results-table">
          <thead>
            <tr>
              <th>Gen</th><th>Version</th><th>Fitness</th><th>Δ</th><th>Status</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>

        ${session.best_version ? `
        <button class="evo-accept-best-btn" id="evo-accept-best-btn">
          Accept Best Version (${_escHtml(bestVersion)})
        </button>` : ''}
      `;

      const acceptBtn = document.getElementById('evo-accept-best-btn');
      if (acceptBtn) {
        acceptBtn.addEventListener('click', () => _acceptBestVersion(bestGen, bestVersion));
      }
    } catch (e) {
      _el.evoPanelBody.innerHTML = `<div style="color:var(--red)">Failed to load results: ${_escHtml(e.message)}</div>`;
    }
  }

  async function _acceptBestVersion(generation, versionName) {
    if (!_evo.loopId) return;
    const btn = document.getElementById('evo-accept-best-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Applying…'; }
    try {
      const resp = await fetch(`/evolution/accept/${_evo.loopId}/${generation}`, { method: 'POST' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      _showEvoToast(`✓ ${data.accepted} has been applied as ${data.applied_to}`);
      _el.evoPanel.classList.remove('open');
    } catch (e) {
      if (btn) { btn.disabled = false; btn.textContent = `Accept Best Version (${versionName})`; }
      _showEvoToast(`Failed: ${e.message}`, true);
    }
  }

  /* ---- Code diff modal ------------------------------------ */

  async function _openDiff(versionName) {
    _el.evoDiffTitle.textContent = `Code Diff — ${versionName}`;
    _el.evoDiffOriginal.textContent = 'Loading…';
    _el.evoDiffMutated.textContent  = 'Loading…';
    _el.evoDiffOverlay.classList.add('open');

    try {
      // Fetch mutated source from strategies dir via versions endpoint
      const stratName = _state.contextStrategyName || '';

      // Original: fetch from the base strategy file via a simple text fetch
      // We don't have a direct source endpoint, so we use the versions list
      // and fall back to showing the mutated code only if original unavailable.
      const [versionsResp, mutatedResp] = await Promise.all([
        fetch(`/evolution/versions/${encodeURIComponent(stratName)}`).then(r => r.json()).catch(() => []),
        fetch(`/strategies/${encodeURIComponent(versionName)}/source`).then(r => r.ok ? r.text() : null).catch(() => null),
      ]);

      const originalSrc = _evo.originalSource || '(Original source not available)';
      const mutatedSrc  = mutatedResp || '(Mutated source not available)';

      _renderCodeDiff(originalSrc, mutatedSrc);
    } catch (e) {
      _el.evoDiffOriginal.textContent = 'Error loading source.';
      _el.evoDiffMutated.textContent  = 'Error loading source.';
    }
  }

  function _renderCodeDiff(original, mutated) {
    const origLines = original.split('\n');
    const mutLines  = mutated.split('\n');
    const maxLen    = Math.max(origLines.length, mutLines.length);

    const origHtml = [];
    const mutHtml  = [];

    for (let i = 0; i < maxLen; i++) {
      const o = origLines[i] !== undefined ? origLines[i] : '';
      const m = mutLines[i]  !== undefined ? mutLines[i]  : '';

      if (o === m) {
        origHtml.push(`<span class="evo-diff__line evo-diff__line--same">${_escHtml(o)}</span>`);
        mutHtml.push( `<span class="evo-diff__line evo-diff__line--same">${_escHtml(m)}</span>`);
      } else {
        origHtml.push(`<span class="evo-diff__line evo-diff__line--removed">${_escHtml(o)}</span>`);
        mutHtml.push( `<span class="evo-diff__line evo-diff__line--added">${_escHtml(m)}</span>`);
      }
    }

    _el.evoDiffOriginal.innerHTML = origHtml.join('');
    _el.evoDiffMutated.innerHTML  = mutHtml.join('');
  }

  /* ---- Toast ---------------------------------------------- */

  function _showEvoToast(msg, isError = false) {
    const t = _el.evoToast;
    if (!t) return;
    t.textContent = msg;
    t.style.borderColor = isError ? 'var(--red)' : 'var(--border)';
    t.style.color = isError ? '#ef4444' : 'var(--text-primary)';
    t.classList.add('visible');
    setTimeout(() => t.classList.remove('visible'), 3500);
  }

  /* ---- Bind events ----------------------------------------- */
  function _bindEvents() {
    // Provider buttons
    _el.providerToggle.addEventListener('click', e => {
      const btn = e.target.closest('[data-provider]');
      if (!btn) return;
      const prov = btn.dataset.provider;
      const p = _state.providers;

      if (prov === 'ollama' && p && !p.ollama.available) {
        return; // offline, don't switch
      }
      if (prov === 'openrouter' && p && !p.openrouter.available) {
        _el.providerWarning.textContent = 'Set OPENROUTER_API_KEYS (or OPENROUTER_API_KEY) in Secrets to enable OpenRouter.';
        _el.providerWarning.classList.add('visible');
        setTimeout(() => _el.providerWarning.classList.remove('visible'), 4000);
        return;
      }

      _state.provider = prov;
      _el.btnOllama.classList.toggle('active', prov === 'ollama');
      _el.btnOpenRouter.classList.toggle('active', prov === 'openrouter');
      _el.providerWarning.classList.remove('visible');
      _updateModelDropdown();
    });

    // Model select
    _el.modelSelect.addEventListener('change', () => {
      _state.model = _el.modelSelect.value;
      _checkSendReady();
    });

    // Goal select
    _el.goalSelect.addEventListener('change', () => {
      _state.goal = _el.goalSelect.value;
    });

    // Textarea
    _el.textarea.addEventListener('input', () => {
      _resizeTextarea();
      _checkSendReady();
    });
    _el.textarea.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
        e.preventDefault();
        if (!_el.sendBtn.disabled) _sendMessage();
      }
      if (e.key === 'Escape') {
        _el.textarea.value = '';
        _resizeTextarea();
        _checkSendReady();
      }
    });

    // Send button
    _el.sendBtn.addEventListener('click', () => _sendMessage());

    // New chat
    _el.newChat.addEventListener('click', _newChat);

    // Conversation list (delegated)
    _el.convList.addEventListener('click', e => {
      const deleteBtn = e.target.closest('.ai-conv-delete');
      if (deleteBtn) {
        e.stopPropagation();
        const id = deleteBtn.dataset.convId;
        fetch(`/ai/threads/${id}`, { method: 'DELETE' }).then(() => {
          if (_state.conversationId === id) _newChat();
          _loadConversations();
        });
        return;
      }
      const item = e.target.closest('.ai-conv-item');
      if (item) {
        _switchConversation(item.dataset.convId);
        // close mobile sidebar
        _el.sidebar.classList.remove('mobile-open');
        _el.sidebarOverlay.classList.remove('active');
      }
    });

    _el.thread.addEventListener('click', e => {
      const actionBtn = e.target.closest('.cmd-block__action');
      if (actionBtn) {
        const block = actionBtn.closest('.cmd-block');
        const action = actionBtn.dataset.action;
        _handleCodeAction(action, block).catch(err => {
          Toast.error(`Code action failed: ${err.message || err}`);
        });
        return;
      }
      const toggle = e.target.closest('.ai-thinking__toggle');
      if (!toggle) return;
      const panel = toggle.closest('.ai-thinking');
      if (!panel) return;
      panel.classList.toggle('open');
      toggle.setAttribute('aria-expanded', panel.classList.contains('open') ? 'true' : 'false');
    });

    // Inject buttons
    const injectHandler = () => _injectLatestBacktest();
    if (_el.injectBtn) _el.injectBtn.addEventListener('click', injectHandler);
    if (_el.injectBtn2) _el.injectBtn2.addEventListener('click', injectHandler);
    if (_el.injectBtn3) _el.injectBtn3.addEventListener('click', injectHandler);

    // Clear context
    _el.contextClear.addEventListener('click', _clearContext);
    if (_el.loopToggle) {
      _el.loopToggle.addEventListener('click', async () => {
        if (!_state.contextRunId) return;
        if (_state.loopEnabled) {
          await _stopLoopRemote();
          Toast.info('Loop stopped');
        } else {
          if (_state.loopBusy) return;
          _state.loopEnabled = true;
          _state.loopToken += 1;
          Toast.success('Loop enabled');
          _appendMessage(
            'assistant',
            'Loop is armed. Click **apply** on a strategy code block to start the narrated cycle.',
            { auto_loop: true }
          );
        }
        _updateLoopButton();
      });
    }

    // Deep Analyse button
    _el.deepAnalyseBtn.addEventListener('click', _openDeepPanel);

    // Deep panel close
    _el.deepPanelClose.addEventListener('click', () => {
      _el.deepPanel.classList.remove('open');
      // If evo panel was offset, remove offset now
      if (_el.evoPanel) _el.evoPanel.classList.remove('evo-panel--offset');
    });

    // Evolve button
    _el.evolveBtn.addEventListener('click', _openEvolutionPanel);

    // Evolution panel close
    _el.evoPanelClose.addEventListener('click', () => {
      _el.evoPanel.classList.remove('open');
      _el.evoPanel.classList.remove('evo-panel--offset');
    });

    // Evolution tabs
    [_el.evoTabConfig, _el.evoTabRunning, _el.evoTabResults].forEach(btn => {
      if (btn) btn.addEventListener('click', () => _evoSwitchTab(btn.dataset.tab));
    });

    // Diff modal close
    _el.evoDiffClose.addEventListener('click', () => {
      _el.evoDiffOverlay.classList.remove('open');
    });
    _el.evoDiffOverlay.addEventListener('click', e => {
      if (e.target === _el.evoDiffOverlay) _el.evoDiffOverlay.classList.remove('open');
    });

    // Mobile hamburger
    _el.hamburger.addEventListener('click', () => {
      const open = _el.sidebar.classList.toggle('mobile-open');
      _el.sidebarOverlay.classList.toggle('active', open);
    });

    _el.sidebarOverlay.addEventListener('click', () => {
      _el.sidebar.classList.remove('mobile-open');
      _el.sidebarOverlay.classList.remove('active');
    });
  }

  /* ---- Init ------------------------------------------------- */
  function init() {
    const el = DOM.$('[data-view="ai-diagnosis"]');
    if (!el) return;

    DOM.setHTML(el, _buildLayout());
    _cacheRefs();
    _updateLoopButton();
    _bindEvents();

    // Initial loads
    _loadProviders();
    _loadConversations();

    // Page fill handled by CSS #page-ai-diagnosis.page-view.active
  }

  function refresh() {
    _loadConversations();
  }

  return { init, refresh, _openDiff };
})();
