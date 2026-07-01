(function () {
  'use strict';

  const MARKER = 'PHASE112R8_5_3_ENDPOINT_DASHBOARD_SEARCH_BRIDGE_EXACT_IP_FIX';
  window.__switchMapEndpointBridgeR85 = true;
  if (window.__switchMapEndpointBridgeR853) return;
  window.__switchMapEndpointBridgeR853 = true;

  const cfg = {
    minChars: 2,
    limit: 8,
    debounceMs: 250,
    apiUrl: '/endpoints/api/search/',
    endpointsUrl: '/endpoints/'
  };

  function qs(sel, root) { return (root || document).querySelector(sel); }

  function findSearchInput() {
    const selectors = [
      '[data-dashboard-search]',
      '[data-switch-search]',
      '[data-quick-search]',
      '#quickSearch',
      '#quick-search',
      '#switchSearch',
      '#switch-search',
      'input[name="q"]',
      'input[type="search"]'
    ];
    for (const sel of selectors) {
      const el = qs(sel);
      if (el && el.tagName === 'INPUT' && el.offsetParent !== null) return el;
    }
    const inputs = Array.from(document.querySelectorAll('input')).filter(function (el) { return el.offsetParent !== null; });
    return inputs.find(function (el) {
      const text = ((el.placeholder || '') + ' ' + (el.id || '') + ' ' + (el.name || '') + ' ' + (el.className || '')).toLowerCase();
      return text.includes('search') || text.includes('جستجو') || text.includes('port') || text.includes('switch');
    }) || null;
  }

  function ensureStyles() {
    if (qs('#endpoint-search-bridge-r8-5-3-style')) return;
    const style = document.createElement('style');
    style.id = 'endpoint-search-bridge-r8-5-3-style';
    style.textContent = `
      .endpoint-search-bridge-r8-5-3 {
        direction: rtl;
        position: fixed;
        z-index: 2147483000;
        max-width: min(820px, calc(100vw - 24px));
      }
      .endpoint-search-bridge-r8-5-3[hidden] { display: none !important; }
      .endpoint-search-bridge-r8-5-3-box {
        border: 1px solid rgba(37,99,235,.22);
        background: rgba(255,255,255,.99);
        border-radius: 14px;
        box-shadow: 0 18px 55px rgba(15,23,42,.18);
        overflow: hidden;
      }
      .endpoint-search-bridge-r8-5-3-head {
        display:flex; align-items:center; justify-content:space-between; gap:10px;
        padding: 9px 12px;
        font-size: 12px;
        color: #475569;
        background: rgba(239,246,255,.95);
        border-bottom: 1px solid rgba(37,99,235,.16);
      }
      .endpoint-search-bridge-r8-5-3-title { font-weight: 900; color:#1d4ed8; }
      .endpoint-search-bridge-r8-5-3-open { color:#2563eb; text-decoration:none; font-weight:800; white-space:nowrap; }
      .endpoint-search-bridge-r8-5-3-list { max-height: 320px; overflow:auto; }
      .endpoint-search-bridge-r8-5-3-row {
        display:grid;
        grid-template-columns: minmax(115px,1fr) minmax(130px,1fr) minmax(70px,.5fr) minmax(150px,1.1fr) minmax(115px,.9fr);
        gap:8px; align-items:center;
        padding: 9px 12px;
        color:#0f172a; text-decoration:none;
        border-bottom: 1px solid rgba(15,23,42,.06);
        font-size: 12px;
      }
      .endpoint-search-bridge-r8-5-3-row:hover { background: rgba(37,99,235,.07); }
      .endpoint-search-bridge-r8-5-3-main { font-weight:900; direction:ltr; text-align:left; }
      .endpoint-search-bridge-r8-5-3-mac { direction:ltr; text-align:left; color:#334155; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
      .endpoint-search-bridge-r8-5-3-chip { justify-self:start; border-radius: 999px; padding:3px 8px; background:#eff6ff; color:#1d4ed8; font-weight:800; }
      .endpoint-search-bridge-r8-5-3-muted { color:#64748b; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .endpoint-search-bridge-r8-5-3-empty { padding: 12px; color:#64748b; font-size:12px; }
      @media (max-width: 900px) {
        .endpoint-search-bridge-r8-5-3-row { grid-template-columns: 1fr 1fr; }
        .endpoint-search-bridge-r8-5-3-chip { justify-self:stretch; text-align:center; }
      }
    `;
    document.head.appendChild(style);
  }

  function makePanel() {
    let panel = qs('#endpoint-search-bridge-r8-5-3');
    if (panel) return panel;
    panel = document.createElement('div');
    panel.id = 'endpoint-search-bridge-r8-5-3';
    panel.className = 'endpoint-search-bridge-r8-5-3';
    panel.setAttribute('data-marker', MARKER);
    panel.hidden = true;
    panel.innerHTML = '<div class="endpoint-search-bridge-r8-5-3-box"><div class="endpoint-search-bridge-r8-5-3-head"><span class="endpoint-search-bridge-r8-5-3-title">نتایج Endpoint</span><a class="endpoint-search-bridge-r8-5-3-open" href="/endpoints/">مشاهده همه</a></div><div class="endpoint-search-bridge-r8-5-3-list"></div></div>';
    document.body.appendChild(panel);
    return panel;
  }

  function positionPanel(panel, input) {
    const r = input.getBoundingClientRect();
    const width = Math.max(420, Math.min(820, r.width + 300, window.innerWidth - 24));
    const left = Math.max(12, Math.min(window.innerWidth - width - 12, r.right - width));
    panel.style.top = (r.bottom + 6) + 'px';
    panel.style.left = left + 'px';
    panel.style.width = width + 'px';
  }

  function safe(v) { return (v === null || v === undefined || v === '') ? '—' : String(v); }
  function enc(v) { return String(v || '').replace(/[&<>'"]/g, function (c) { return ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]); }); }

  function normalizeRows(payload) {
    if (Array.isArray(payload)) return payload;
    if (payload && Array.isArray(payload.results)) return payload.results;
    if (payload && Array.isArray(payload.endpoints)) return payload.endpoints;
    if (payload && Array.isArray(payload.items)) return payload.items;
    return [];
  }

  function value(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== '') return row[k];
    }
    return '';
  }

  function render(panel, input, query, rows, count) {
    positionPanel(panel, input);
    const list = qs('.endpoint-search-bridge-r8-5-3-list', panel);
    const open = qs('.endpoint-search-bridge-r8-5-3-open', panel);
    const title = qs('.endpoint-search-bridge-r8-5-3-title', panel);
    open.href = cfg.endpointsUrl + '?q=' + encodeURIComponent(query);
    title.textContent = 'نتایج Endpoint: ' + (count !== undefined ? count : rows.length) + ' مورد';
    panel.hidden = false;
    if (!rows.length) {
      list.innerHTML = '<div class="endpoint-search-bridge-r8-5-3-empty">Endpoint مطابق پیدا نشد.</div>';
      return;
    }
    list.innerHTML = rows.map(function (r) {
      const ip = value(r, ['ip', 'ip_address', 'last_ip']);
      const mac = value(r, ['mac', 'mac_address']);
      const vlan = value(r, ['vlan', 'vlan_id']);
      const sw = value(r, ['switch', 'switch_name', 'device', 'device_name']);
      const port = value(r, ['port', 'port_name', 'interface', 'interface_name']);
      const type = value(r, ['connection_type', 'type']);
      const href = cfg.endpointsUrl + '?q=' + encodeURIComponent(ip || mac || query);
      return '<a class="endpoint-search-bridge-r8-5-3-row" href="' + enc(href) + '">' +
        '<span class="endpoint-search-bridge-r8-5-3-main">' + enc(safe(ip)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-3-mac">' + enc(safe(mac)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-3-chip">VLAN ' + enc(safe(vlan)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-3-muted">' + enc(safe(sw)) + ' / ' + enc(safe(port)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-3-muted">' + enc(safe(type)) + '</span>' +
      '</a>';
    }).join('');
  }

  function start() {
    ensureStyles();
    const input = findSearchInput();
    if (!input) return;
    const panel = makePanel();
    let timer = null;
    let seq = 0;

    function run() {
      const q = (input.value || '').trim();
      clearTimeout(timer);
      if (q.length < cfg.minChars) {
        panel.hidden = true;
        return;
      }
      timer = setTimeout(function () {
        const mySeq = ++seq;
        positionPanel(panel, input);
        fetch(cfg.apiUrl + '?q=' + encodeURIComponent(q) + '&limit=' + cfg.limit + '&_=' + Date.now(), {
          credentials: 'same-origin',
          headers: {'Accept': 'application/json'}
        })
          .then(function (res) {
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return res.json();
          })
          .then(function (data) {
            if (mySeq !== seq) return;
            const rows = normalizeRows(data);
            render(panel, input, q, rows, data && data.count);
          })
          .catch(function () {
            panel.hidden = true;
          });
      }, cfg.debounceMs);
    }

    ['input', 'keyup', 'change', 'search'].forEach(function (evt) { input.addEventListener(evt, run); });
    window.addEventListener('resize', function () { if (!panel.hidden) positionPanel(panel, input); });
    window.addEventListener('scroll', function () { if (!panel.hidden) positionPanel(panel, input); }, true);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') panel.hidden = true; });
    setTimeout(run, 500);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();