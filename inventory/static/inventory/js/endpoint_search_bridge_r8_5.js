(function () {
  'use strict';

  const MARKER = 'PHASE112R8_5_ENDPOINT_DASHBOARD_SEARCH_BRIDGE';
  if (window.__switchMapEndpointBridgeR85) return;
  window.__switchMapEndpointBridgeR85 = true;

  const cfg = {
    minChars: 2,
    limit: 8,
    debounceMs: 280,
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
      if (el && el.tagName === 'INPUT') return el;
    }
    const inputs = Array.from(document.querySelectorAll('input'));
    return inputs.find(function (el) {
      const text = ((el.placeholder || '') + ' ' + (el.id || '') + ' ' + (el.name || '') + ' ' + (el.className || '')).toLowerCase();
      return text.includes('search') || text.includes('جستجو') || text.includes('port') || text.includes('switch');
    }) || null;
  }

  function ensureStyles() {
    if (qs('#endpoint-search-bridge-r8-5-style')) return;
    const style = document.createElement('style');
    style.id = 'endpoint-search-bridge-r8-5-style';
    style.textContent = `
      .endpoint-search-bridge-r8-5 { direction: rtl; margin-top: 8px; position: relative; z-index: 30; }
      .endpoint-search-bridge-r8-5[hidden] { display: none !important; }
      .endpoint-search-bridge-r8-5-box { border: 1px solid rgba(15,23,42,.12); background: rgba(255,255,255,.98); border-radius: 14px; box-shadow: 0 14px 40px rgba(15,23,42,.12); overflow: hidden; max-width: 760px; }
      .endpoint-search-bridge-r8-5-head { display:flex; align-items:center; justify-content:space-between; gap:10px; padding: 10px 12px; font-size: 12px; color: #475569; background: rgba(248,250,252,.95); border-bottom: 1px solid rgba(15,23,42,.08); }
      .endpoint-search-bridge-r8-5-title { font-weight: 800; color: #0f172a; }
      .endpoint-search-bridge-r8-5-open { color:#2563eb; text-decoration:none; font-weight:700; white-space:nowrap; }
      .endpoint-search-bridge-r8-5-list { max-height: 310px; overflow:auto; }
      .endpoint-search-bridge-r8-5-row { display:grid; grid-template-columns: minmax(110px,1.1fr) minmax(135px,1.15fr) minmax(70px,.55fr) minmax(150px,1.2fr) minmax(120px,1fr); gap:8px; align-items:center; padding: 9px 12px; color:#0f172a; text-decoration:none; border-bottom: 1px solid rgba(15,23,42,.06); font-size: 12px; }
      .endpoint-search-bridge-r8-5-row:hover { background: rgba(37,99,235,.06); }
      .endpoint-search-bridge-r8-5-main { font-weight: 800; direction:ltr; text-align:left; }
      .endpoint-search-bridge-r8-5-mac { direction:ltr; text-align:left; color:#334155; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
      .endpoint-search-bridge-r8-5-chip { justify-self:start; border-radius: 999px; padding:3px 8px; background:#eff6ff; color:#1d4ed8; font-weight:700; }
      .endpoint-search-bridge-r8-5-muted { color:#64748b; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .endpoint-search-bridge-r8-5-empty { padding: 12px; color:#64748b; font-size:12px; }
      @media (max-width: 900px) { .endpoint-search-bridge-r8-5-row { grid-template-columns: 1fr 1fr; } .endpoint-search-bridge-r8-5-chip { justify-self:stretch; text-align:center; } }
    `;
    document.head.appendChild(style);
  }

  function makePanel(input) {
    let panel = qs('#endpoint-search-bridge-r8-5');
    if (panel) return panel;
    panel = document.createElement('div');
    panel.id = 'endpoint-search-bridge-r8-5';
    panel.className = 'endpoint-search-bridge-r8-5';
    panel.setAttribute('data-marker', MARKER);
    panel.hidden = true;
    panel.innerHTML = '<div class="endpoint-search-bridge-r8-5-box"><div class="endpoint-search-bridge-r8-5-head"><span class="endpoint-search-bridge-r8-5-title">نتایج Endpoint</span><a class="endpoint-search-bridge-r8-5-open" href="/endpoints/">مشاهده همه</a></div><div class="endpoint-search-bridge-r8-5-list"></div></div>';
    const wrapper = input.closest('.search, .search-box, .toolbar, .dashboard-toolbar, form, .card, .panel') || input.parentElement;
    if (wrapper && wrapper.parentNode) {
      wrapper.parentNode.insertBefore(panel, wrapper.nextSibling);
    } else {
      input.insertAdjacentElement('afterend', panel);
    }
    return panel;
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

  function render(panel, query, rows) {
    const list = qs('.endpoint-search-bridge-r8-5-list', panel);
    const open = qs('.endpoint-search-bridge-r8-5-open', panel);
    open.href = cfg.endpointsUrl + '?q=' + encodeURIComponent(query);
    panel.hidden = false;
    if (!rows.length) {
      list.innerHTML = '<div class="endpoint-search-bridge-r8-5-empty">Endpoint مطابق پیدا نشد.</div>';
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
      return '<a class="endpoint-search-bridge-r8-5-row" href="' + enc(href) + '">' +
        '<span class="endpoint-search-bridge-r8-5-main">' + enc(safe(ip)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-mac">' + enc(safe(mac)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-chip">VLAN ' + enc(safe(vlan)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-muted">' + enc(safe(sw)) + ' / ' + enc(safe(port)) + '</span>' +
        '<span class="endpoint-search-bridge-r8-5-muted">' + enc(safe(type)) + '</span>' +
      '</a>';
    }).join('');
  }

  function start() {
    ensureStyles();
    const input = findSearchInput();
    if (!input) return;
    const panel = makePanel(input);
    let timer = null;
    let seq = 0;
    input.addEventListener('input', function () {
      const q = (input.value || '').trim();
      clearTimeout(timer);
      if (q.length < cfg.minChars) {
        panel.hidden = true;
        return;
      }
      timer = setTimeout(function () {
        const mySeq = ++seq;
        fetch(cfg.apiUrl + '?q=' + encodeURIComponent(q) + '&limit=' + cfg.limit, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
          .then(function (res) {
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return res.json();
          })
          .then(function (data) {
            if (mySeq !== seq) return;
            render(panel, q, normalizeRows(data));
          })
          .catch(function () {
            panel.hidden = true;
          });
      }, cfg.debounceMs);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
