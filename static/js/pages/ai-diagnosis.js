/* =================================================================
   AI DIAGNOSIS PAGE — full chat UI
   Exposes: window.AIDiagPage
   ================================================================= */

window.AIDiagPage = (() => {
  /* ---- State ------------------------------------------------ */
  let _state = {
    provider: 'openrouter',
    model: null,
    goal: 'auto',
    conversationId: null,
    contextRunId: null,
    contextStrategyName: null,
    contextTimeframe: null,
    streaming: false,
    evtSource: null,
    streamController: null,
    providers: null,
  };

  /* ---- DOM refs (populated in init) ------------------------ */
  let _el = {};

  /* ---- Markdown renderer ----------------------------------- */
  function _renderMarkdown(text) {
    let html = text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const label = lang || 'code';
      const escaped = code.trim();
      return `<div class="cmd-block">
        <div class="cmd-block__label">
          <span>${_escHtml(label)}</span>
          <button class="cmd-block__copy" onclick="navigator.clipboard.writeText(this.closest('.cmd-block').querySelector('pre').textContent)">copy</button>
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
        <option value="auto">Goal: Auto</option>
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

      <!-- Deep Analyse button -->
      <button class="ai-deep-analyse-btn" id="ai-deep-analyse-btn" disabled title="Inject a backtest first">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          <line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
        </svg>
        Deep Analyse
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

    _state.model = models[0].id;
    _el.modelSelect.value = _state.model;
    _checkSendReady();
  }

  /* ---- Load conversations ---------------------------------- */
  async function _loadConversations() {
    try {
      const convs = await fetch('/ai/conversations').then(r => r.json());
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
    _state.conversationId = convId;
    _el.thread.innerHTML = '';

    // Mark active in sidebar
    document.querySelectorAll('.ai-conv-item').forEach(el => {
      el.classList.toggle('active', el.dataset.convId === convId);
    });

    try {
      const conv = await fetch(`/ai/conversations/${convId}`).then(r => r.json());
      if (conv && conv.messages) {
        conv.messages.forEach(m => _appendMessage(m.role, m.content, m.meta));
      }
    } catch (e) {
      _setStatus('Could not load conversation');
    }

    _scrollThread();
  }

  /* ---- New chat -------------------------------------------- */
  function _newChat() {
    _state.conversationId = null;
    _el.thread.innerHTML = '';
    _showEmpty(true);
    document.querySelectorAll('.ai-conv-item').forEach(el => el.classList.remove('active'));
    _el.textarea.focus();
  }

  /* ---- Inject backtest ------------------------------------- */
  async function _injectLatestBacktest() {
    try {
      const runs = await fetch('/runs').then(r => r.json());
      const completed = (runs || []).filter(r => r.status === 'done' || r.status === 'completed');
      if (!completed.length) {
        _setStatus('No completed backtests found');
        return;
      }
      const latest = completed[0];
      _state.contextRunId = latest.id;
      _state.contextStrategyName = latest.strategy || latest.id;
      _state.contextTimeframe = latest.timeframe || '';
      _updateContextBar();
      _el.deepAnalyseBtn.disabled = false;
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
  }

  function _clearContext() {
    _state.contextRunId = null;
    _state.contextStrategyName = null;
    _state.contextTimeframe = null;
    _updateContextBar();
    _el.deepAnalyseBtn.disabled = true;
  }

  /* ---- Message rendering ----------------------------------- */
  function _appendMessage(role, content, meta) {
    // Hide empty state
    _showEmpty(false);

    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    const div = document.createElement('div');
    div.className = `ai-message ai-message--${role}`;
    div.dataset.role = role;

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
      ? _renderMarkdown(content)
      : `<p>${_escHtml(content).replace(/\n/g, '<br>')}</p>`;

    div.innerHTML = `
      ${headerHtml}
      <div class="ai-message__bubble">${bubbleContent}</div>
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
  async function _sendMessage() {
    const text = _el.textarea.value.trim();
    if (!text || _state.streaming) return;

    _el.textarea.value = '';
    _resizeTextarea();
    _state.streaming = true;
    _el.sendBtn.style.display = 'none';
    _el.stopBtn.style.display = '';
    _setStatus('');

    _appendMessage('user', text);
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
    assistantDiv.appendChild(headerDiv);
    assistantDiv.appendChild(bubble);
    _el.thread.appendChild(assistantDiv);
    _scrollThread();

    let fullText = '';
    let aborted = false;

    const body = JSON.stringify({
      message: text,
      conversation_id: _state.conversationId,
      provider: _state.provider,
      model: _state.model || undefined,
      goal_id: _state.goal !== 'auto' ? _state.goal : undefined,
      context_run_id: _state.contextRunId || undefined,
    });

    const controller = new AbortController();
    _state.streamController = controller;

    _el.stopBtn.onclick = () => {
      aborted = true;
      controller.abort();
      _finishStream(bubble, headerDiv, fullText, null);
    };

    try {
      const resp = await fetch('/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal: controller.signal,
      });

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

            if (evt.done && !evt.delta) {
              if (evt.conversation_id) {
                _state.conversationId = evt.conversation_id;
              }
              const pipeline = evt.pipeline || {};
              _finishStream(bubble, headerDiv, evt.fullText || fullText, pipeline);
              await _loadConversations();
              aborted = true; // prevent double-finish
              break;
            }

            if (evt.error) {
              bubble.innerHTML = `<span style="color:var(--red)">${_escHtml(evt.error)}</span>`;
              _finishStream(bubble, headerDiv, '', null);
              aborted = true;
              break;
            }
          } catch (_) {}
        }
        if (aborted) break;
      }
    } catch (e) {
      if (!aborted) {
        bubble.innerHTML = `<span style="color:var(--red)">Connection error: ${_escHtml(e.message)}</span>`;
        _finishStream(bubble, headerDiv, '', null);
      }
    }

    if (!aborted) {
      _finishStream(bubble, headerDiv, fullText, null);
    }
  }

  function _finishStream(bubble, headerDiv, finalText, pipeline) {
    // Remove streaming cursor
    const cursor = bubble.querySelector('.ai-streaming-cursor');
    if (cursor) cursor.remove();

    if (finalText) {
      bubble.innerHTML = _renderMarkdown(finalText);
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
        const modelName = (pipeline.model || '').split('/').pop();
        const dur = pipeline.duration_ms ? ` · ${(pipeline.duration_ms/1000).toFixed(1)}s` : '';
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
        _el.providerWarning.textContent = 'Set OPENROUTER_API_KEY in Secrets to enable OpenRouter.';
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
    _el.sendBtn.addEventListener('click', _sendMessage);

    // New chat
    _el.newChat.addEventListener('click', _newChat);

    // Conversation list (delegated)
    _el.convList.addEventListener('click', e => {
      const deleteBtn = e.target.closest('.ai-conv-delete');
      if (deleteBtn) {
        e.stopPropagation();
        const id = deleteBtn.dataset.convId;
        fetch(`/ai/conversations/${id}`, { method: 'DELETE' }).then(() => {
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

    // Inject buttons
    const injectHandler = () => _injectLatestBacktest();
    if (_el.injectBtn) _el.injectBtn.addEventListener('click', injectHandler);
    if (_el.injectBtn2) _el.injectBtn2.addEventListener('click', injectHandler);
    if (_el.injectBtn3) _el.injectBtn3.addEventListener('click', injectHandler);

    // Clear context
    _el.contextClear.addEventListener('click', _clearContext);

    // Deep Analyse button
    _el.deepAnalyseBtn.addEventListener('click', _openDeepPanel);

    // Deep panel close
    _el.deepPanelClose.addEventListener('click', () => {
      _el.deepPanel.classList.remove('open');
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
    _bindEvents();

    // Initial loads
    _loadProviders();
    _loadConversations();

    // Page fill handled by CSS #page-ai-diagnosis.page-view.active
  }

  function refresh() {
    _loadConversations();
  }

  return { init, refresh };
})();
