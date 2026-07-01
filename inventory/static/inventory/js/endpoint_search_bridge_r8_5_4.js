(function () {
  'use strict';

  const MARKER = 'PHASE112R8_5_4_ENDPOINT_SEARCH_FORCE_UI_BRIDGE';
  if (window.__switchMapEndpointBridgeR854) return;
  window.__switchMapEndpointBridgeR854 = true;

  const state = {
    apiUrl: '/endpoints/api/search/',
    endpointsUrl: '/endpoints/',
    minChars: 2,
    limit: 8,
    timer: null,
    lastValue: '',
    lastInput: null,
    lastSeq: 0
  };

  function safeText(v) {
    return (v === undefined || v === null || v === '') ? '—' : String(v);
  }

  function htmlEscape(v) {
    return safeText(v).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function value(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== '') return row[k];
    }
    return '';
  }

  function normalizeRows(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    if (data && Array.isArray(data.endpoints)) return data.endpoints;
    if (data && Array.isArray(data.items)) return data.items;
    return [];
  }

  function isLikelyDashboardSearchInput(input) {
    if (!input || input.tagName !== 'INPUT') return false;
    if (input.offsetParent === null) return false;
    const t = [
      input.id || '',
      input.name || '',
      input.className || '',
      input.placeholder || '',
      input.getAttribute('aria-label') || '',
      input.getAttribute('data-dashboard-search') || '',
      input.getAttribute('data-switch-search') || '',
      input.getAttribute('data-quick-search') || ''
    ].join(' ').toLowerCase();
    if (t.includes('search') || t.includes('جستجو') || t.includes('quick') || t.includes('switch') || t.includes('port')) return true;
    const rect = input.getBoundingClientRect();
    return rect.width >= 180 && rect.top < 260;
  }

  function visibleSearchInputs() {
    return Array.from(document.querySelectorAll('input')).filter(isLikelyDashboardSearchInput);
  }

  function activeSearchInput() {
    const active = document.activeElement;
    if (isLikelyDashboardSearchInput(active)) return active;
    const inputs = visibleSearchInputs();
    if (!inputs.length) return null;
    const withValue = inputs.find(function (x) { return (x.value || '').trim().length >= state.minChars; });
    return withValue || inputs[0];
  }

  function ensureStyle() {
    if (document.getElementById('endpoint-force-bridge-r8-5-4-style')) return;
    const st = document.createElement('style');
    st.id = 'endpoint-force-bridge-r8-5-4-style';
    st.textContent = `
      .endpoint-force-bridge-r8-5-4 {
        direction: rtl;
        border-top: 1px solid rgba(37,99,235,.16);
        background: #ffffff;
      }
      .endpoint-force-bridge-r8-5-4-head {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        padding:8px 12px;
        background: rgba(239,246,255,.95);
        color:#1d4ed8;
        font-size:12px;
        font-weight:900;
      }
      .endpoint-force-bridge-r8-5-4-head a {
        color:#2563eb;
        text-decoration:none;
        font-size:11px;
        font-weight:900;
        white-space:nowrap;
      }
      .endpoint-force-bridge-r8-5-4-row {
        display:grid;
        grid-template-columns: minmax(115px,1fr) minmax(130px,1fr) minmax(66px,.45fr) minmax(135px,1fr) minmax(112px,.85fr);
        gap:8px;
        align-items:center;
        padding:8px 12px;
        border-top:1px solid rgba(15,23,42,.06);
        color:#0f172a;
        text-decoration:none;
        font-size:12px;
      }
      .endpoint-force-bridge-r8-5-4-row:hover { background:rgba(37,99,235,.06); }
      .endpoint-force-bridge-r8-5-4-ip,
      .endpoint-force-bridge-r8-5-4-mac {
        direction:ltr;
        text-align:left;
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      }
      .endpoint-force-bridge-r8-5-4-ip { font-weight:900; }
      .endpoint-force-bridge-r8-5-4-mac { color:#334155; }
      .endpoint-force-bridge-r8-5-4-chip {
        border-radius:999px;
        background:#eff6ff;
        color:#1d4ed8;
        font-weight:900;
        padding:3px 8px;
        text-align:center;
        white-space:nowrap;
      }
      .endpoint-force-bridge-r8-5-4-muted {
        color:#64748b;
        overflow:hidden;
        white-space:nowrap;
        text-overflow:ellipsis;
      }
      .endpoint-force-bridge-r8-5-4-panel {
        position:fixed;
        z-index:2147483640;
        max-width:min(860px, calc(100vw - 24px));
        border:1px solid rgba(37,99,235,.24);
        border-radius:14px;
        overflow:hidden;
        background:#fff;
        box-shadow:0 20px 60px rgba(15,23,42,.22);
      }
      .endpoint-force-bridge-r8-5-4-panel[hidden] { display:none !important; }
      @media (max-width:900px) {
        .endpoint-force-bridge-r8-5-4-row { grid-template-columns:1fr 1fr; }
      }
    `;
    document.head.appendChild(st);
  }

  function dropdownCandidates(input) {
    const arr = [];
    const rect = input.getBoundingClientRect();
    document.querySelectorAll('div,section,ul,nav').forEach(function (el) {
      if (!el || el.offsetParent === null) return;
      const r = el.getBoundingClientRect();
      if (r.width < 220 || r.height < 20) return;
      const nearX = Math.abs((r.left + r.width / 2) - (rect.left + rect.width / 2)) < 480;
      const below = r.top >= rect.bottom - 8 && r.top < rect.bottom + 160;
      const text = (el.innerText || '').trim();
      const looksResult = text.includes('نتیجه') || text.includes('پیدا نشد') || text.includes('دستگاه') || text.includes('پورت');
      if (nearX && below && looksResult) arr.push(el);
    });
    arr.sort(function (a, b) {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      return (ar.top - br.top) || (br.width - ar.width);
    });
    return arr;
  }

  function ensureFloatingPanel(input) {
    let panel = document.getElementById('endpoint-force-bridge-r8-5-4-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'endpoint-force-bridge-r8-5-4-panel';
      panel.className = 'endpoint-force-bridge-r8-5-4-panel';
      panel.setAttribute('data-marker', MARKER);
      panel.hidden = true;
      document.body.appendChild(panel);
    }
    const r = input.getBoundingClientRect();
    const width = Math.max(520, Math.min(860, r.width + 360, window.innerWidth - 24));
    const left = Math.max(12, Math.min(window.innerWidth - width - 12, r.right - width));
    panel.style.left = left + 'px';
    panel.style.top = (r.bottom + 46) + 'px';
    panel.style.width = width + 'px';
    return panel;
  }

  function buildHtml(query, rows, count) {
    const openHref = state.endpointsUrl + '?q=' + encodeURIComponent(query);
    let out = '<div class="endpoint-force-bridge-r8-5-4" data-marker="' + MARKER + '">' +
      '<div class="endpoint-force-bridge-r8-5-4-head"><span>نتایج Endpoint: ' + htmlEscape(count) + ' مورد</span><a href="' + htmlEscape(openHref) + '">مشاهده کامل</a></div>';
    if (!rows.length) {
      out += '<div class="endpoint-force-bridge-r8-5-4-row"><span class="endpoint-force-bridge-r8-5-4-muted">Endpoint مطابق پیدا نشد.</span></div></div>';
      return out;
    }
    out += rows.map(function (row) {
      const ip = value(row, ['ip', 'ip_address', 'last_ip']);
      const mac = value(row, ['mac', 'mac_address']);
      const vlan = value(row, ['vlan', 'vlan_id']);
      const sw = value(row, ['switch', 'switch_name', 'device', 'device_name']);
      const port = value(row, ['port', 'port_name', 'interface', 'interface_name']);
      const type = value(row, ['connection_type', 'type']);
      const href = state.endpointsUrl + '?q=' + encodeURIComponent(ip || mac || query);
      return '<a class="endpoint-force-bridge-r8-5-4-row" href="' + htmlEscape(href) + '">' +
        '<span class="endpoint-force-bridge-r8-5-4-ip">' + htmlEscape(ip) + '</span>' +
        '<span class="endpoint-force-bridge-r8-5-4-mac">' + htmlEscape(mac) + '</span>' +
        '<span class="endpoint-force-bridge-r8-5-4-chip">VLAN ' + htmlEscape(vlan) + '</span>' +
        '<span class="endpoint-force-bridge-r8-5-4-muted">' + htmlEscape(sw) + ' / ' + htmlEscape(port || '—') + '</span>' +
        '<span class="endpoint-force-bridge-r8-5-4-muted">' + htmlEscape(type) + '</span>' +
      '</a>';
    }).join('');
    out += '</div>';
    return out;
  }

  function injectResults(input, query, rows, count) {
    ensureStyle();
    const html = buildHtml(query, rows, count);

    // First choice: inject into the existing quick-search dropdown.
    const candidates = dropdownCandidates(input);
    if (candidates.length) {
      const box = candidates[0];
      const old = box.querySelector('.endpoint-force-bridge-r8-5-4');
      if (old) old.remove();
      box.insertAdjacentHTML('beforeend', html);
      const panel = document.getElementById('endpoint-force-bridge-r8-5-4-panel');
      if (panel) panel.hidden = true;
      return;
    }

    // Fallback: forced floating panel.
    const panel = ensureFloatingPanel(input);
    panel.innerHTML = html;
    panel.hidden = false;
  }

  function hideForcedPanel() {
    const panel = document.getElementById('endpoint-force-bridge-r8-5-4-panel');
    if (panel) panel.hidden = true;
    document.querySelectorAll('.endpoint-force-bridge-r8-5-4').forEach(function (el) {
      const parent = el.parentElement;
      if (parent && parent.id !== 'endpoint-force-bridge-r8-5-4-panel') el.remove();
    });
  }

  function searchNow(input) {
    const q = (input && input.value || '').trim();
    state.lastInput = input;
    state.lastValue = q;
    clearTimeout(state.timer);

    if (!q || q.length < state.minChars) {
      hideForcedPanel();
      return;
    }

    const seq = ++state.lastSeq;
    state.timer = setTimeout(function () {
      fetch(state.apiUrl + '?q=' + encodeURIComponent(q) + '&limit=' + state.limit + '&_=' + Date.now(), {
        method: 'GET',
        credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
      })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (seq !== state.lastSeq) return;
        const rows = normalizeRows(data);
        const count = data && data.count !== undefined ? data.count : rows.length;
        injectResults(input, q, rows, count);
      })
      .catch(function () {
        // Keep old search behavior untouched.
      });
    }, 180);
  }

  function bindInput(input) {
    if (!input || input.dataset.endpointForceBridgeR854 === '1') return;
    input.dataset.endpointForceBridgeR854 = '1';
    ['input', 'keyup', 'change', 'search', 'paste'].forEach(function (evt) {
      input.addEventListener(evt, function () { searchNow(input); }, true);
    });
    input.addEventListener('focus', function () { searchNow(input); }, true);
  }

  function bindAll() {
    visibleSearchInputs().forEach(bindInput);
    const input = activeSearchInput();
    if (input && (input.value || '').trim().length >= state.minChars) searchNow(input);
  }

  function start() {
    ensureStyle();
    bindAll();
    setInterval(bindAll, 900);
    document.addEventListener('input', function (e) {
      if (isLikelyDashboardSearchInput(e.target)) {
        bindInput(e.target);
        searchNow(e.target);
      }
    }, true);
    document.addEventListener('keyup', function (e) {
      if (isLikelyDashboardSearchInput(e.target)) {
        bindInput(e.target);
        searchNow(e.target);
      }
    }, true);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') hideForcedPanel();
    }, true);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();