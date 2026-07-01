/* PHASE79_6_5_LAST_CONNECTED_OVERRIDE
   PHASE79_7_POST_SSH_PORT_REFRESH
   PHASE79_8_MULTI_SSH_ACTION
   PHASE79_8_1_MULTI_SSH_UI_RESULT_ORDER
   PHASE79_8_2_PLATFORM_ACTION_GUARD
   Independent renderer loaded after switchmap.js.
   It does not change dashboard layout/search/topology/base SSH submit logic.
*/
(function(){
    if(window.__SWITCHMAP_PHASE79_7_LC_REFRESH_OVERRIDE__) return;
    window.__SWITCHMAP_PHASE79_7_LC_REFRESH_OVERRIDE__ = true;

    var activeButton = null;
    var originalFetch = window.fetch;

    function esc(value){
        return String(value == null ? '' : value).replace(/[&<>"']/g, function(ch){
            return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[ch] || ch;
        });
    }
    function clean(value){
        var s = String(value === 0 ? '0' : (value || '')).trim();
        if(!s) return '';
        var low = s.toLowerCase();
        if(s === '-' || low === 'none' || low === 'null' || low === 'unknown' || low === 'undefined') return '';
        if(s.indexOf('سابقه') !== -1 && s.indexOf('ثبت نشده') !== -1) return '';
        return s;
    }
    function valueOrDash(value){
        var s = clean(value);
        return s || '-';
    }
    function q(root, selector){ return root ? root.querySelector(selector) : null; }
    function qa(root, selector){ return root ? Array.prototype.slice.call(root.querySelectorAll(selector)) : []; }
    function text(root, attrName, name){
        var el = q(root, '[' + attrName + '="' + name + '"]');
        return clean(el ? el.textContent : '');
    }
    function setText(root, attrName, name, value){
        var el = q(root, '[' + attrName + '="' + name + '"]');
        if(el) el.textContent = valueOrDash(value);
    }
    function setHref(root, attrName, name, value){
        var el = q(root, '[' + attrName + '="' + name + '"]');
        if(el && value) el.setAttribute('href', value);
    }
    function data(button, key){
        return button && button.dataset ? clean(button.dataset[key]) : '';
    }
    function neighborFromButton(button){
        var n = [data(button,'neighborDevice'), data(button,'neighborPort')].filter(Boolean).join(' / ');
        return clean(n);
    }
    function lastFromButton(button){
        if(!button || !button.dataset) return null;
        return {
            loaded: Object.prototype.hasOwnProperty.call(button.dataset, 'lastConnectionAvailable'),
            available: data(button,'lastConnectionAvailable') === '1',
            identity: data(button,'lastConnectionIdentity'),
            classification: data(button,'lastConnectionClassification'),
            display_label: data(button,'lastConnectionDisplayLabel'),
            display_source: data(button,'lastConnectionDisplaySource'),
            direct: data(button,'lastConnectionDirect') === '1',
            event_type: data(button,'lastConnectionEventType'),
            observed_at_text: data(button,'lastConnectionObservedAt'),
            source: data(button,'lastConnectionSource'),
            mac: data(button,'lastConnectionMac'),
            ip: data(button,'lastConnectionIp'),
            vlan: data(button,'lastConnectionVlan'),
            status_after: data(button,'lastConnectionStatusAfter')
        };
    }
    function findButtonByPortId(portId){
        if(!portId) return null;
        var buttons = document.querySelectorAll('[data-sm-port-button]');
        for(var i=0;i<buttons.length;i++){
            if(String(buttons[i].dataset.portId || '') === String(portId)) return buttons[i];
        }
        return null;
    }
    function selectedPortId(){
        if(activeButton && activeButton.dataset && activeButton.dataset.portId) return activeButton.dataset.portId;
        var openModal = document.getElementById('dashboard-port-modal');
        var form = openModal ? q(openModal,'.js-dashboard-ssh-form') : null;
        var portInput = q(form,'[name="port_id"]');
        if(portInput && portInput.value) return portInput.value;
        var panel = document.querySelector('[data-sm-port-detail]');
        form = panel ? q(panel,'.js-dashboard-ssh-form') : null;
        portInput = q(form,'[name="port_id"]');
        return portInput ? portInput.value : '';
    }
    function applyPayloadToButton(button, port){
        if(!button || !button.dataset || !port) return;
        if(port.id !== undefined) button.dataset.portId = port.id || button.dataset.portId || '';
        if(port.interface !== undefined){ button.dataset.interface = port.interface || ''; button.dataset.interfaceName = port.interface || ''; button.dataset.portName = port.interface || ''; }
        if(port.status !== undefined){ button.dataset.status = port.status || ''; button.dataset.portStatus = port.status || ''; }
        if(port.state !== undefined) button.dataset.operStatus = port.state || '';
        if(port.mode !== undefined) button.dataset.portMode = port.mode || '';
        if(port.port_mode !== undefined && !button.dataset.mode) button.dataset.mode = port.port_mode || '';
        if(port.access_vlan !== undefined) button.dataset.accessVlan = port.access_vlan || '';
        if(port.vlan !== undefined && !button.dataset.accessVlan) button.dataset.accessVlan = port.vlan || '';
        if(port.native_vlan !== undefined) button.dataset.nativeVlan = port.native_vlan || '';
        if(port.voice_vlan !== undefined) button.dataset.voiceVlan = port.voice_vlan || '';
        if(port.trunk_vlans !== undefined) button.dataset.trunkVlans = port.trunk_vlans || '';
        if(port.poe_summary !== undefined) button.dataset.poeSummary = port.poe_summary || '';
        if(port.mac_count !== undefined) button.dataset.macCount = String(port.mac_count == null ? '' : port.mac_count);
        if(port.neighbor_device !== undefined) button.dataset.neighborDevice = port.neighbor_device || '';
        if(port.neighbor_port !== undefined) button.dataset.neighborPort = port.neighbor_port || '';
        if(port.neighbor_source !== undefined) button.dataset.neighborSource = port.neighbor_source || '';
        if(port.mac_address !== undefined) button.dataset.macAddress = port.mac_address || '';
        if(port.ip_address !== undefined) button.dataset.ipAddress = port.ip_address || '';
        if(port.device !== undefined){ button.dataset.device = port.device || ''; button.dataset.connectedDevice = port.device || ''; }
        if(port.description !== undefined) button.dataset.description = port.description || '';
        if(port.updated_at_text !== undefined) button.dataset.updatedAt = port.updated_at_text || '';
        if(port.snmp_last_poll_text !== undefined) button.dataset.snmpLastPoll = port.snmp_last_poll_text || '';
        if(port.discovery_last_poll_text !== undefined) button.dataset.discoveryLastPoll = port.discovery_last_poll_text || '';
        if(port.edit_url !== undefined) button.dataset.editUrl = port.edit_url || '';
        if(port.map_url !== undefined) button.dataset.mapUrl = port.map_url || '';
        if(port.table_url !== undefined) button.dataset.tableUrl = port.table_url || '';
        var lc = port.last_connection;
        if(lc){
            button.dataset.lastConnectionAvailable = lc.available ? '1' : '0';
            button.dataset.lastConnectionIdentity = lc.identity || '';
            button.dataset.lastConnectionClassification = lc.classification || '';
            button.dataset.lastConnectionDisplayLabel = lc.display_label || lc.identity || '';
            button.dataset.lastConnectionDisplaySource = lc.display_source || lc.source || '';
            button.dataset.lastConnectionDirect = lc.direct ? '1' : '0';
            button.dataset.lastConnectionEventType = lc.event_type || '';
            button.dataset.lastConnectionObservedAt = lc.observed_at_text || lc.last_verified_at_text || '';
            button.dataset.lastConnectionSource = lc.source || lc.neighbor_source || '';
            button.dataset.lastConnectionMac = lc.mac || '';
            button.dataset.lastConnectionIp = lc.ip || '';
            button.dataset.lastConnectionVlan = lc.vlan || '';
            button.dataset.lastConnectionStatusAfter = lc.status_after || '';
        }
        var subtitle = q(button,'.dynamic-port-subtitle') || q(button,'.nexus-port-vlan');
        if(subtitle){
            if(clean(port.port_mode).toLowerCase() === 'trunk') subtitle.textContent = 'T';
            else subtitle.textContent = valueOrDash(port.access_vlan || port.vlan);
        }
        button.setAttribute('title', [port.interface, port.description].filter(clean).join(' - ') || button.getAttribute('title') || '');
    }
    function payloadValue(port, name){
        // PHASE114 FINAL: the backend _port_payload now returns the deterministic
        // visual-policy values for device/ip_address/mac_address/neighbor/
        // neighbor_source, so this override writes classified values (not raw)
        // into the upper Modal/Detail fields. The raw overwrite path is closed.
        if(!port) return '';
        if(name === 'interface') return port.interface;
        if(name === 'status') return port.status;
        if(name === 'port_mode') return port.mode || port.port_mode;
        if(name === 'neighbor'){
            if(port.neighbor !== undefined) return port.neighbor;
            return [port.neighbor_device, port.neighbor_port].filter(clean).join(' / ');
        }
        if(name === 'updated_at') return port.updated_at_text || port.updated_at;
        if(name === 'snmp_last_poll') return port.snmp_last_poll_text;
        if(name === 'discovery_last_poll') return port.discovery_last_poll_text;
        return port[name];
    }
    function updatePanelFields(root, attrName, port){
        if(!root || !port) return;
        var fields = ['interface','status','port_mode','access_vlan','voice_vlan','native_vlan','trunk_vlans','poe_summary','mac_count','device','neighbor','neighbor_source','ip_address','mac_address','description','updated_at','snmp_last_poll','discovery_last_poll'];
        fields.forEach(function(name){ setText(root, attrName, name, payloadValue(port,name)); });
        if(attrName === 'data-field'){
            setText(root, attrName, 'title', 'پورت ' + valueOrDash(port.interface));
            var sub = q(root, '[data-field="subtitle"]');
            if(sub) sub.textContent = [port.switch_name || '', port.switch_ip || ''].filter(clean).join(' · ') || sub.textContent;
        }
        setHref(root, attrName, 'edit_url', port.edit_url);
        setHref(root, attrName, 'map_url', port.map_url);
        setHref(root, attrName, 'table_url', port.table_url);
    }
    function updateVisiblePortFields(port, button){
        var modal = document.getElementById('dashboard-port-modal');
        if(modal && modal.classList.contains('open')) updatePanelFields(modal, 'data-field', port);
        var panel = document.querySelector('[data-sm-port-detail]');
        if(panel) updatePanelFields(panel, 'data-detail', port);
        renderAll(button);
    }
    function buildState(root, attrName, button){
        button = button || activeButton;
        var last = lastFromButton(button);
        if(last && last.loaded && last.available && clean(last.display_label || last.identity)){
            var isCurrent = clean(last.event_type).toLowerCase() === 'current';
            return {
                kind:isCurrent ? 'current' : 'last',
                identity:clean(last.display_label) || clean(last.identity),
                source:clean(last.display_source) || clean(last.source),
                mac:clean(last.mac),
                ip:clean(last.ip),
                vlan:clean(last.vlan),
                seen:clean(last.observed_at_text),
                classification:clean(last.classification),
                direct:last.direct
            };
        }
        if(!last || !last.loaded) return {kind:'loading'};
        return {kind:'none'};
    }
    function renderLastConnected(root, attrName, button){
        if(!root) return;
        var card = q(root, '[data-phase79-lc-card]');
        var body = q(root, '[data-phase79-last-connected]');
        if(!card || !body) return;
        var title = q(card, '.phase79-lc-head strong');
        var badge = q(root, '[' + attrName + '="last_connection_event_type"]');
        var state = buildState(root, attrName, button);
        card.classList.add('phase79-6-5-rendered','phase79-7-rendered');
        if(state.kind === 'loading'){
            if(title) title.textContent = 'Current Connected Device';
            if(badge) badge.textContent = 'Loading';
            body.className = 'phase79-lc-body is-empty phase79-6-5-body phase79-7-body';
            body.innerHTML = '<div class="phase79-lc-empty">Loading classified backend payload...</div>';
            return;
        }
        if(state.kind === 'none'){
            if(title) title.textContent = 'Connection History';
            if(badge) badge.textContent = 'No history';
            body.className = 'phase79-lc-body is-empty phase79-6-5-body phase79-7-body';
            body.innerHTML = '<div class="phase79-lc-empty">سابقه اتصال معتبری برای این پورت ثبت نشده است.</div>';
            return;
        }
        var isCurrent = state.kind === 'current';
        if(title) title.textContent = isCurrent ? 'Current Connected Device' : 'Last Known Device';
        if(badge) badge.textContent = isCurrent ? 'Current' : 'Last known';
        var rows = [];
        function add(label, value){
            var v = clean(value);
            if(!v) return;
            rows.push('<div class="phase79-lc-row"><span class="phase79-lc-label">' + esc(label) + '</span><strong class="phase79-lc-value ltr" title="' + esc(v) + '">' + esc(v) + '</strong></div>');
        }
        add(isCurrent ? 'Device' : 'Last Device', state.identity);
        add('Source', state.source);
        add('MAC', state.mac);
        add('IP', state.ip);
        add('VLAN', state.vlan);
        add(isCurrent ? 'Seen' : 'Last Seen', state.seen);
        body.className = 'phase79-lc-body is-available phase79-6-5-body phase79-7-body';
        body.innerHTML = rows.length ? '<div class="phase79-lc-list">' + rows.join('') + '</div>' : '<div class="phase79-lc-empty">سابقه اتصال معتبری برای این پورت ثبت نشده است.</div>';
    }
    function fixPreview(root, attrName, button){
        if(!root || !button || !button.dataset) return;
        var form = q(root, '.js-dashboard-ssh-form');
        if(!form) return;
        var iface = data(button, 'interface') || data(button,'interfaceName');
        if(!iface) return;
        ['switch_id','switch_ip','port_id','interface','interface_name'].forEach(function(name){
            var el = q(form, '[name="' + name + '"]');
            if(!el) return;
            if(name === 'switch_id') el.value = data(button,'switchId');
            else if(name === 'switch_ip') el.value = data(button,'switchIp');
            else if(name === 'port_id') el.value = data(button,'portId');
            else el.value = iface;
        });
        var pre = q(form, '[data-command-preview]');
        if(pre){
            var lines = String(pre.textContent || '').split(/\r?\n/);
            var changed = false;
            lines = lines.map(function(line){
                if(/^\s*interface\s+/i.test(line)){ changed = true; return 'interface ' + iface; }
                return line;
            });
            if(!changed){ lines = ['configure terminal', 'interface ' + iface, 'end']; }
            pre.textContent = lines.join('\n');
        }
    }
    function renderAll(button){
        var modal = document.getElementById('dashboard-port-modal');
        if(modal && modal.classList.contains('open')){
            renderLastConnected(modal, 'data-field', button);
            fixPreview(modal, 'data-field', button);
            updatePlatformActionAvailability(q(modal, '.js-dashboard-ssh-form'));
        }
        var panel = document.querySelector('[data-sm-port-detail]');
        if(panel){
            renderLastConnected(panel, 'data-detail', button);
            fixPreview(panel, 'data-detail', button);
            updatePlatformActionAvailability(q(panel, '.js-dashboard-ssh-form'));
        }
    }
    function renderPayload(port, options){
        if(!port || !port.id) return;
        var button = findButtonByPortId(port.id) || activeButton;
        if(button){
            activeButton = button;
            applyPayloadToButton(button, port);
        }
        updateVisiblePortFields(port, button);
        if(options && options.form) setInlineResult(options.form, true, options.message || 'عملیات موفق بود؛ اطلاعات پورت به‌روزرسانی شد.');
    }
    function fetchAndRender(buttonOrPortId, options){
        var portId = typeof buttonOrPortId === 'string' || typeof buttonOrPortId === 'number' ? buttonOrPortId : (buttonOrPortId && buttonOrPortId.dataset ? buttonOrPortId.dataset.portId : '');
        if(!portId) return;
        originalFetch('/port/' + encodeURIComponent(portId) + '/payload/', {
            credentials:'same-origin',
            headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}
        }).then(function(response){ return response.json().catch(function(){return null;}); })
          .then(function(payload){
              if(payload && payload.ok && payload.port){ renderPayload(payload.port, options || {}); }
          }).catch(function(){});
    }
    function setInlineResult(form, ok, message){
        if(!form) return;
        var box = ensureMultiResultBox(form) || (form.parentElement ? q(form.parentElement, '[data-role="result"]') : null) || q(form, '[data-role="result"]');
        if(!box) return;
        box.className = 'inline-result phase79-multi-result ' + (ok ? 'ok' : 'fail');
        box.textContent = message || '';
    }
    function ensureMultiResultBox(form){
        if(!form) return null;
        var box = q(form, '[data-phase79-multi-result]');
        if(box) return box;
        box = document.createElement('div');
        box.className = 'inline-result phase79-multi-result';
        box.setAttribute('data-role','result');
        box.setAttribute('data-phase79-multi-result','1');
        var submit = q(form, '[type="submit"]');
        if(submit && submit.parentNode === form) form.insertBefore(box, submit);
        else form.appendChild(box);
        return box;
    }
    function formatActionSummary(items){
        return (items || []).map(function(item, idx){
            var meta = actionByName(item.action);
            var label = item.label || (meta && meta.label) || item.action || 'Action';
            var value = clean(item.value);
            return String(idx + 1) + '. ' + label + (value ? ' = ' + value : '');
        });
    }
    function setMultiResult(form, ok, message, items){
        var box = ensureMultiResultBox(form);
        if(!box) return;
        var lines = formatActionSummary(items);
        box.className = 'inline-result phase79-multi-result ' + (ok ? 'ok' : 'fail');
        box.innerHTML = '<strong>' + esc(message || (ok ? 'عملیات موفق بود.' : 'عملیات خطا داد.')) + '</strong>' + (lines.length ? '<ol>' + lines.map(function(line){ return '<li>' + esc(line.replace(/^\d+\.\s*/,'')) + '</li>'; }).join('') + '</ol>' : '');
    }
    function findFormForPort(portId){
        var forms = document.querySelectorAll('.js-dashboard-ssh-form');
        for(var i=0;i<forms.length;i++){
            var el = q(forms[i], '[name="port_id"]');
            if(el && String(el.value || '') === String(portId)) return forms[i];
        }
        return null;
    }
    function schedule(button){
        if(!button) return;
        activeButton = button;
        Promise.resolve().then(function(){ renderAll(button); });
        window.setTimeout(function(){ renderAll(button); }, 80);
        window.setTimeout(function(){ renderAll(button); }, 250);
        window.setTimeout(function(){ fetchAndRender(button); }, 0);
    }
    function schedulePostSshRefresh(portId, form){
        if(!portId) return;
        var button = findButtonByPortId(portId) || activeButton;
        if(button) activeButton = button;
        window.setTimeout(function(){ fetchAndRender(portId, {form: form || findFormForPort(portId), message:'عملیات موفق بود؛ وضعیت پورت دوباره خوانده شد.'}); }, 900);
        window.setTimeout(function(){ fetchAndRender(portId, {form: form || findFormForPort(portId), message:'عملیات موفق بود؛ اطلاعات پورت به‌روزرسانی شد.'}); }, 2200);
        window.setTimeout(function(){ fetchAndRender(portId, {form: form || findFormForPort(portId), message:'عملیات موفق بود؛ اطلاعات پورت به‌روزرسانی شد.'}); }, 5200);
    }
    function isSshActionUrl(url){
        return /(?:^|\/)(ssh-port-action|port-action|ssh-action)(?:\/|$|\?)/.test(String(url || ''));
    }
    function portIdFromRequest(input, init){
        try{
            if(init && init.body && typeof init.body.get === 'function') return init.body.get('port_id') || '';
        }catch(e){}
        return selectedPortId();
    }
    if(originalFetch){
        window.fetch = function(input, init){
            var url = typeof input === 'string' ? input : (input && input.url ? input.url : '');
            var isSsh = isSshActionUrl(url) && init && String(init.method || '').toUpperCase() === 'POST';
            var portId = isSsh ? portIdFromRequest(input, init) : '';
            var responsePromise = originalFetch.apply(this, arguments);
            if(!isSsh) return responsePromise;
            return responsePromise.then(function(response){
                try{
                    response.clone().json().then(function(payload){
                        if(payload && payload.ok){
                            var form = findFormForPort(portId || (payload.port && payload.port.id));
                            if(payload.port && payload.port.id){ renderPayload(payload.port, {form: form, message:'عملیات موفق بود؛ در حال به‌روزرسانی وضعیت پورت ...'}); }
                            schedulePostSshRefresh((payload.port && payload.port.id) || portId, form);
                        }
                    }).catch(function(){});
                }catch(e){}
                return response;
            });
        };
    }
    document.addEventListener('DOMContentLoaded', function(){
        document.addEventListener('click', function(event){
            var btn = event.target.closest('[data-sm-port-button]');
            if(btn) schedule(btn);
        }, true);
        document.addEventListener('submit', function(event){
            var form = event.target && event.target.classList && event.target.classList.contains('js-dashboard-ssh-form') ? event.target : null;
            if(!form) return;
            var portInput = q(form, '[name="port_id"]');
            var portId = portInput ? portInput.value : '';
            var btn = findButtonByPortId(portId);
            if(btn) activeButton = btn;
        }, true);
        prepareMultiForms();
        document.addEventListener('click', function(event){
            var up = event.target.closest && event.target.closest('[data-phase79-order-up]');
            var down = event.target.closest && event.target.closest('[data-phase79-order-down]');
            if(up || down){
                event.preventDefault();
                event.stopPropagation();
                moveMultiRow(event.target.closest('[data-phase79-multi-row]'), up ? -1 : 1);
            }
        }, true);
        document.addEventListener('change', function(event){
            if(event.target.closest && event.target.closest('[data-phase79-multi-box]')) updateMultiPreview(event.target.closest('form'));
        }, true);
        document.addEventListener('input', function(event){
            if(event.target.closest && event.target.closest('[data-phase79-multi-box]')) updateMultiPreview(event.target.closest('form'));
        }, true);
        document.addEventListener('submit', function(event){
            var form = event.target && event.target.classList && event.target.classList.contains('js-dashboard-ssh-form') ? event.target : null;
            if(!form) return;
            var checkedCount = form.querySelectorAll('[data-phase79-multi-action]:checked').length;
            var items = selectedMultiItems(form);
            if(checkedCount && !items.length){
                event.preventDefault();
                event.stopImmediatePropagation();
                setMultiResult(form, false, 'Actionهای انتخاب‌شده روی این مدل سوییچ پشتیبانی نمی‌شوند.');
                updateMultiPreview(form);
                return;
            }
            if(!items.length) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            form.dataset.phase79MultiSubmitCapture = 'phase79-8-multi-submit-capture';
            submitMultiForm(form, items);
        }, true);
        var preselect = new URLSearchParams(window.location.search).get('port');
        if(preselect){
            var btn = findButtonByPortId(preselect);
            if(btn) schedule(btn);
        }
    });


    // PHASE79_8_2_PLATFORM_ACTION_GUARD
    var PHASE79_NEXUS_UNSUPPORTED = {poe_auto:true, poe_never:true, set_voice_vlan:true, remove_voice_vlan:true};
    function currentSwitchText(form){
        var portIdEl = form ? q(form, '[name="port_id"]') : null;
        var button = (portIdEl && portIdEl.value ? findButtonByPortId(portIdEl.value) : null) || activeButton;
        var root = form ? (form.closest('#dashboard-port-modal') || form.closest('[data-sm-port-detail]') || document) : document;
        var bits = [];
        if(button && button.dataset){
            bits.push(button.dataset.switchName || '');
            bits.push(button.dataset.switchModel || '');
            bits.push(button.dataset.switchVendor || '');
            bits.push(button.dataset.interface || button.dataset.interfaceName || '');
        }
        var subtitle = root ? (q(root, '[data-field="subtitle"]') || q(root, '.page-subtitle') || q(root, '.modal-subtitle')) : null;
        if(subtitle) bits.push(subtitle.textContent || '');
        var h = root ? (q(root, 'h1') || q(root, 'h2') || q(root, 'h3')) : null;
        if(h) bits.push(h.textContent || '');
        return bits.join(' ').toLowerCase();
    }
    function isNexusForm(form){
        return /(nexus|nx-os|nxos|n3k|n5k|n7k|n9k)/i.test(currentSwitchText(form));
    }
    function unsupportedReason(form, action){
        if(isNexusForm(form) && PHASE79_NEXUS_UNSUPPORTED[action]){
            return 'این Action روی Cisco Nexus پشتیبانی نمی‌شود.';
        }
        return '';
    }
    function updatePlatformActionAvailability(form){
        if(!form) return;
        var isNexus = isNexusForm(form);
        qa(form, '[data-phase79-multi-row]').forEach(function(row){
            var cb = q(row, '[data-phase79-multi-action]');
            if(!cb) return;
            var reason = unsupportedReason(form, cb.value);
            row.classList.toggle('is-platform-disabled', !!reason);
            row.setAttribute('title', reason || '');
            cb.disabled = !!reason;
            if(reason) cb.checked = false;
            var valueInput = q(row, '[data-phase79-multi-value]');
            if(valueInput) valueInput.disabled = !!reason;
            var note = q(row, '[data-phase79-platform-note]');
            if(reason && !note){
                note = document.createElement('small');
                note.setAttribute('data-phase79-platform-note','1');
                note.className = 'phase79-platform-note';
                note.textContent = 'Nexus unsupported';
                row.appendChild(note);
            }else if(!reason && note){
                note.remove();
            }
        });
        var select = q(form, '.js-ssh-action-select');
        if(select){
            Array.prototype.slice.call(select.options || []).forEach(function(opt){
                var reason = unsupportedReason(form, opt.value);
                opt.disabled = !!reason;
                opt.hidden = !!reason && isNexus;
            });
            if(select.options[select.selectedIndex] && select.options[select.selectedIndex].disabled){
                var first = Array.prototype.slice.call(select.options).find(function(opt){ return opt.value && !opt.disabled; });
                if(first) select.value = first.value;
            }
        }
    }

    // PHASE79_8_MULTI_SSH_ACTION
    var MULTI_ACTIONS = [
        {action:'set_access_vlan', label:'Access VLAN', needsValue:true, placeholder:'100'},
        {action:'set_description', label:'Description', needsValue:true, placeholder:'PC-Accounting-01'},
        {action:'clear_description', label:'Clear Description'},
        {action:'set_voice_vlan', label:'Voice VLAN', needsValue:true, placeholder:'20', risky:true},
        {action:'remove_voice_vlan', label:'Remove Voice VLAN', risky:true},
        {action:'shutdown', label:'Shutdown', risky:true},
        {action:'no_shutdown', label:'No Shutdown'},
        {action:'poe_auto', label:'PoE Auto'},
        {action:'poe_never', label:'PoE Off', risky:true},
        {action:'force_trunk', label:'Force Trunk', risky:true, force:true},
        {action:'add_trunk_vlan', label:'Add Trunk VLAN', needsValue:true, placeholder:'100', risky:true, force:true},
        {action:'remove_trunk_vlan', label:'Remove Trunk VLAN', needsValue:true, placeholder:'100', risky:true, force:true}
    ];
    function actionByName(action){
        for(var i=0;i<MULTI_ACTIONS.length;i++){ if(MULTI_ACTIONS[i].action === action) return MULTI_ACTIONS[i]; }
        return null;
    }
    function selectedMultiItems(form){
        var items = [];
        if(!form) return items;
        updatePlatformActionAvailability(form);
        form.querySelectorAll('[data-phase79-multi-action]:checked').forEach(function(cb){
            if(cb.disabled || unsupportedReason(form, cb.value)) return;
            var meta = actionByName(cb.value);
            if(!meta) return;
            var row = cb.closest('[data-phase79-multi-row]');
            var valueInput = row ? row.querySelector('[data-phase79-multi-value]') : null;
            items.push({action: cb.value, value: valueInput ? String(valueInput.value || '').trim() : ''});
        });
        return items;
    }
    function multiNeedsValueMissing(form, items){
        for(var i=0;i<items.length;i++){
            var meta = actionByName(items[i].action);
            if(meta && meta.needsValue && !items[i].value) return meta.label;
        }
        return '';
    }
    function multiRequiresForce(items){
        return items.some(function(item){ var meta = actionByName(item.action); return !!(meta && meta.force); });
    }
    function multiRequiresConfirmed(items){
        return items.some(function(item){ var meta = actionByName(item.action); return !!(meta && meta.risky); });
    }
    function multiPreviewLines(form){
        var ifaceInput = form ? (q(form,'[name="interface"]') || q(form,'[name="interface_name"]')) : null;
        var iface = ifaceInput && ifaceInput.value ? ifaceInput.value : '<interface>';
        var items = selectedMultiItems(form);
        if(!items.length) return null;
        var lines = ['configure terminal'];
        items.forEach(function(item){
            var meta = actionByName(item.action);
            if(!meta) return;
            lines.push('interface ' + iface);
            if(item.action === 'set_access_vlan'){ lines.push('switchport mode access'); lines.push('switchport access vlan ' + (item.value || '<vlan>')); }
            else if(item.action === 'set_description'){ lines.push('description ' + (item.value || '<description>')); }
            else if(item.action === 'clear_description'){ lines.push('no description'); }
            else if(item.action === 'set_voice_vlan'){ lines.push('switchport mode access'); lines.push('switchport voice vlan ' + (item.value || '<vlan>')); }
            else if(item.action === 'remove_voice_vlan'){ lines.push('no switchport voice vlan'); }
            else if(item.action === 'shutdown'){ lines.push('shutdown'); }
            else if(item.action === 'no_shutdown'){ lines.push('no shutdown'); }
            else if(item.action === 'poe_auto'){ lines.push('power inline auto'); }
            else if(item.action === 'poe_never'){ lines.push('power inline never'); }
            else if(item.action === 'force_trunk'){ lines.push('switchport mode trunk'); }
            else if(item.action === 'add_trunk_vlan'){ lines.push('switchport mode trunk'); lines.push('switchport trunk allowed vlan add ' + (item.value || '<vlan-list>')); }
            else if(item.action === 'remove_trunk_vlan'){ lines.push('switchport trunk allowed vlan remove ' + (item.value || '<vlan-list>')); }
        });
        lines.push('end');
        return lines;
    }
    function updateMultiPreview(form){
        updatePlatformActionAvailability(form);
        refreshMultiRowOrder(form);
        var lines = multiPreviewLines(form);
        var preview = form ? q(form, '[data-command-preview]') : null;
        if(lines && preview) preview.textContent = lines.join('\n');
        var badge = form ? q(form, '[data-phase79-multi-count]') : null;
        if(badge) badge.textContent = String(selectedMultiItems(form).length);
    }
    function refreshMultiRowOrder(form){
        if(!form) return;
        var rows = qa(form, '[data-phase79-multi-row]');
        rows.forEach(function(row, idx){
            var order = q(row, '[data-phase79-order-num]');
            if(order) order.textContent = String(idx + 1);
            row.classList.toggle('is-selected', !!q(row, '[data-phase79-multi-action]:checked'));
        });
    }
    function moveMultiRow(row, direction){
        if(!row || !row.parentNode) return;
        if(direction < 0){
            var prev = row.previousElementSibling;
            if(prev) row.parentNode.insertBefore(row, prev);
        }else{
            var next = row.nextElementSibling;
            if(next) row.parentNode.insertBefore(next, row);
        }
        updateMultiPreview(row.closest('form'));
    }
    function injectMultiUi(form){
        if(!form || form.dataset.phase79MultiReady === '1') return;
        form.dataset.phase79MultiReady = '1';
        form.dataset.multiActionUrl = '/ssh-port-multi-action/';
        var anchor = q(form, '[data-command-preview]');
        if(!anchor) return;
        var previewBox = anchor.closest ? anchor.closest('.command-preview-box') : null;
        var wrap = document.createElement('div');
        wrap.className = 'phase79-multi-ssh-box phase79-8-1-multi-box';
        wrap.setAttribute('data-phase79-multi-box','1');
        wrap.innerHTML = '<div class="phase79-multi-head"><strong>Multi SSH Actions</strong><span><b data-phase79-multi-count>0</b> selected</span></div>' +
            '<div class="phase79-multi-hint">ترتیب اجرا از بالا به پایین است. با ↑ و ↓ ترتیب را عوض کن.</div>' +
            '<div class="phase79-multi-list">' + MULTI_ACTIONS.map(function(item, idx){
                var value = item.needsValue ? '<input class="input phase79-multi-value" data-phase79-multi-value placeholder="' + esc(item.placeholder || '') + '">' : '<span class="phase79-multi-no-value">-</span>';
                return '<div class="phase79-multi-row" data-phase79-multi-row>' +
                    '<span class="phase79-order-num" data-phase79-order-num>' + (idx + 1) + '</span>' +
                    '<label class="phase79-multi-check"><input type="checkbox" data-phase79-multi-action value="' + esc(item.action) + '"> ' + esc(item.label) + '</label>' +
                    value +
                    '<span class="phase79-order-controls"><button type="button" data-phase79-order-up title="Move up">↑</button><button type="button" data-phase79-order-down title="Move down">↓</button></span>' +
                    '</div>';
            }).join('') + '</div><div class="field-help">اگر هیچ گزینه‌ای انتخاب نشود، همان Action تکی اجرا می‌شود.</div>';
        if(previewBox && previewBox.parentNode === form) form.insertBefore(wrap, previewBox);
        else anchor.parentNode.insertBefore(wrap, anchor);
        ensureMultiResultBox(form);
        updatePlatformActionAvailability(form);
        refreshMultiRowOrder(form);
    }
    function prepareMultiForms(){
        document.querySelectorAll('.js-dashboard-ssh-form').forEach(function(form){ injectMultiUi(form); });
    }
    function submitMultiForm(form, items){
        var username = q(form,'[name="username"]');
        var password = q(form,'[name="password"]');
        var portId = q(form,'[name="port_id"]');
        if(!username || !username.value.trim() || !password || !password.value.trim()){
            setMultiResult(form, false, 'Username و Password لازم است.');
            return;
        }
        if(!portId || !portId.value){
            setMultiResult(form, false, 'ابتدا یک پورت را انتخاب کن.');
            return;
        }
        var missing = multiNeedsValueMissing(form, items);
        if(missing){
            setMultiResult(form, false, 'Value برای ' + missing + ' لازم است.', items);
            return;
        }
        var forceInput = q(form,'[name="force"]');
        var confirmedInput = q(form,'[name="confirmed"]');
        if(multiRequiresForce(items) && !(forceInput && forceInput.checked)){
            setMultiResult(form, false, 'برای عملیات Trunk/Uplink تیک Force لازم است.', items);
            return;
        }
        if(multiRequiresConfirmed(items) && !(confirmedInput && confirmedInput.checked)){
            setMultiResult(form, false, 'برای عملیات حساس تیک تأیید نهایی لازم است.', items);
            return;
        }
        var submit = q(form,'[type="submit"]');
        if(submit) submit.disabled = true;
        setMultiResult(form, true, 'در حال اجرای Multi SSH ...', items);
        var fd = new FormData(form);
        fd.set('ssh_username', username.value);
        fd.set('ssh_password', password.value);
        fd.set('ajax','1');
        fd.set('actions_json', JSON.stringify(items));
        originalFetch('/ssh-port-multi-action/', {
            method:'POST', body:fd, credentials:'same-origin',
            headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}
        }).then(function(response){
            return response.json().catch(function(){return {ok:false,error:'پاسخ سرور معتبر نیست.'};}).then(function(data){ return {response:response, data:data}; });
        }).then(function(result){
            if(result.response.ok && result.data && result.data.ok){
                if(result.data.port && result.data.port.id) renderPayload(result.data.port, {form:form, message:'Multi SSH موفق بود؛ وضعیت پورت در حال به‌روزرسانی است.'});
                schedulePostSshRefresh((result.data.port && result.data.port.id) || portId.value, form);
                setMultiResult(form, true, result.data.message || 'Multi SSH با موفقیت انجام شد.', result.data.actions || items);
            }else{
                setMultiResult(form, false, (result.data && (result.data.error || result.data.message)) || 'Multi SSH خطا داد.', items);
            }
        }).catch(function(error){
            setMultiResult(form, false, 'ارتباط با سرور برقرار نشد: ' + error, items);
        }).finally(function(){ if(submit) submit.disabled = false; });
    }

})();
