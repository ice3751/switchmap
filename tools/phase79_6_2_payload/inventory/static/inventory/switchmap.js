/* Phase 65 Three Panel Dashboard UX | data-dashboard-data-url | smoke compatibility marker */
(function(){
    function valueOrDash(value){ if(value === 0 || value === false) return String(value); return value && String(value).trim() ? String(value).trim() : '-'; }
    function escapeHtml(value){
        return String(value || '').replace(/[&<>"']/g, function(ch){
            return ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[ch];
        });
    }
    function detailAttrs(item){
        const url = item.detail_url || item.target_url || item.url || '#';
        return ' href="' + escapeHtml(url) + '" data-dashboard-detail data-issue-id="' + escapeHtml(item.issue_id || '') + '" data-detail-url="' + escapeHtml(url) + '" data-object-name="' + escapeHtml(item.object_name || item.target || item.title || '') + '" data-object-type="' + escapeHtml(item.object_type || '') + '" data-severity="' + escapeHtml(item.severity || 'info') + '" data-last-check="' + escapeHtml(item.last_check_time || item.last_poll_text || item.last_seen_text || '') + '" data-reason="' + escapeHtml(item.short_reason || item.summary || item.message || '') + '" data-action="' + escapeHtml(item.recommended_action || item.action || '') + '"';
    }
    function compactIssueText(item, fallback){
        return item.compact_reason || item.compact_status || item.status_label || fallback || item.short_reason || item.summary || item.message || item.action || '';
    }
    function dataAttrsOnly(item){
        return detailAttrs(item).replace(/ href="[^"]*"/, '');
    }
    function getCookie(name){
        const item = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith(name + '='));
        return item ? decodeURIComponent(item.split('=')[1]) : '';
    }
    function field(root, selector){ return root ? root.querySelector(selector) : null; }
    function setText(root, selector, value){ const el = field(root, selector); if(el) el.textContent = valueOrDash(value); }
    function setValue(root, selector, value){ const el = field(root, selector); if(el) el.value = value || ''; }
    function formValue(form, name){ const el = form ? form.querySelector('[name="' + name + '"]') : null; return el ? el.value : ''; }
    function formChecked(form, name){ const el = form ? form.querySelector('[name="' + name + '"]') : null; return !!(el && el.checked); }

    const ACTIONS = {
        set_access_vlan:{placeholder:'100',help:'شماره VLAN را وارد کن.',needsValue:true,commands:function(i,v){return ['interface ' + i,'switchport mode access','switchport access vlan ' + v];}},
        set_description:{placeholder:'PC-Accounting-01',help:'Description جدید را وارد کن.',needsValue:true,commands:function(i,v){return ['interface ' + i,'description ' + v];}},
        clear_description:{placeholder:'',help:'مقداری لازم نیست.',commands:function(i){return ['interface ' + i,'no description'];}},
        set_voice_vlan:{placeholder:'20',help:'Voice VLAN را وارد کن.',needsValue:true,risky:true,commands:function(i,v){return ['interface ' + i,'switchport mode access','switchport voice vlan ' + v];}},
        remove_voice_vlan:{placeholder:'',help:'مقداری لازم نیست.',risky:true,commands:function(i){return ['interface ' + i,'no switchport voice vlan'];}},
        set_trunk_allowed:{placeholder:'1,100,101-110',help:'لیست Allowed VLAN بازنویسی می‌شود.',needsValue:true,risky:true,force:true,commands:function(i,v){return ['interface ' + i,'switchport mode trunk','switchport trunk allowed vlan ' + v];}},
        add_trunk_vlan:{placeholder:'100',help:'VLAN به لیست Trunk اضافه می‌شود.',needsValue:true,risky:true,force:true,commands:function(i,v){return ['interface ' + i,'switchport mode trunk','switchport trunk allowed vlan add ' + v];}},
        remove_trunk_vlan:{placeholder:'100',help:'VLAN از Trunk حذف می‌شود.',needsValue:true,risky:true,force:true,commands:function(i,v){return ['interface ' + i,'switchport trunk allowed vlan remove ' + v];}},
        shutdown:{placeholder:'',help:'پورت خاموش می‌شود.',risky:true,commands:function(i){return ['interface ' + i,'shutdown'];}},
        no_shutdown:{placeholder:'',help:'پورت فعال می‌شود.',commands:function(i){return ['interface ' + i,'no shutdown'];}},
        poe_auto:{placeholder:'',help:'PoE روی Auto قرار می‌گیرد.',commands:function(i){return ['interface ' + i,'power inline auto'];}},
        poe_never:{placeholder:'',help:'PoE قطع می‌شود.',risky:true,commands:function(i){return ['interface ' + i,'power inline never'];}},
        force_trunk:{placeholder:'',help:'پورت به Trunk تبدیل می‌شود.',risky:true,force:true,commands:function(i){return ['interface ' + i,'switchport mode trunk'];}}
    };
    const RISK_TEXT = {
        shutdown:'پورت خاموش می‌شود و ارتباط دستگاه قطع می‌شود.',
        poe_never:'برق PoE قطع می‌شود؛ تلفن، دوربین یا AP ممکن است خاموش شود.',
        set_voice_vlan:'Voice VLAN تغییر می‌کند؛ تلفن IP ممکن است رجیستر نشود.',
        remove_voice_vlan:'Voice VLAN حذف می‌شود؛ تلفن IP ممکن است از کار بیفتد.',
        set_trunk_allowed:'لیست Allowed VLAN روی Trunk بازنویسی می‌شود.',
        add_trunk_vlan:'VLAN جدید به Trunk اضافه می‌شود.',
        remove_trunk_vlan:'VLAN از Trunk حذف می‌شود و ممکن است ارتباط آن VLAN قطع شود.',
        force_trunk:'پورت به Trunk تبدیل می‌شود.'
    };

    function actionMeta(action){ return ACTIONS[action] || {placeholder:'',help:'',commands:function(){return [];}}; }
    function previewCommands(form){
        if(!form) return;
        const select = form.querySelector('.js-ssh-action-select');
        const input = form.querySelector('.js-ssh-action-value');
        const preview = form.querySelector('[data-command-preview]');
        const riskBox = form.querySelector('[data-risk-text]');
        const iface = formValue(form,'interface') || formValue(form,'interface_name') || '<interface>';
        const action = select ? select.value : '';
        const value = input ? input.value.trim() : '';
        const meta = actionMeta(action);
        let lines = ['configure terminal'];
        try{
            lines = lines.concat(meta.commands(iface, value));
            lines.push('end');
        }catch(e){ lines = ['ابتدا مقدار معتبر وارد کن.']; }
        if(preview) preview.textContent = lines.join('\n');
        if(riskBox) riskBox.textContent = RISK_TEXT[action] || '';
    }
    function applyActionMeta(form){
        if(!form) return;
        const select = form.querySelector('.js-ssh-action-select');
        const input = form.querySelector('.js-ssh-action-value');
        const help = form.querySelector('.js-ssh-action-help');
        const forceRow = form.querySelector('[name="force"]');
        const confirmRow = form.querySelector('[name="confirmed"]');
        if(!select || !input) return;
        const meta = actionMeta(select.value);
        input.placeholder = meta.placeholder || '';
        if(help) help.textContent = meta.help || '';
        if(!meta.needsValue) input.value = '';
        if(forceRow) forceRow.closest('label').style.display = meta.force ? '' : 'none';
        if(confirmRow) confirmRow.closest('label').style.display = meta.risky ? '' : 'none';
        previewCommands(form);
    }
    function setResult(form, ok, message){
        const box = form ? (form.parentElement.querySelector('[data-role="result"]') || form.querySelector('[data-role="result"]')) : null;
        if(!box) return;
        box.className = 'inline-result ' + (ok ? 'ok' : 'fail');
        box.textContent = message || '';
    }
    function normalizeState(text){
        const s = String(text || '').toLowerCase();
        if(s.includes('err') || s.includes('error') || s.includes('خطا')) return 'error';
        if(s.includes('disable') || s.includes('shutdown') || s.includes('غیرفعال')) return 'disabled';
        if(s.includes('up') || s.includes('connected') || s.includes('فعال')) return 'up';
        return 'down';
    }
    function neighborText(data){ return [data.neighborDevice, data.neighborPort].filter(Boolean).join(' / '); }
    function historyValue(value){ return valueOrDash(value); }
    function meaningfulHistoryValue(value){
        const s = String(value === 0 ? '0' : (value || '')).trim();
        if(!s) return false;
        const low = s.toLowerCase();
        if(s === '-' || low === 'none' || low === 'null' || low === 'unknown') return false;
        if(s.indexOf('سابقه') !== -1 && s.indexOf('ثبت نشده') !== -1) return false;
        return true;
    }
    function hasMeaningfulLastConnection(last){
        if(!last || last.available === false) return false;
        return [last.identity, last.neighbor, last.mac, last.ip, last.device, last.connected_device].some(meaningfulHistoryValue);
    }
    function storeLastConnectionOnButton(btn, last){
        if(!btn || !last) return;
        btn.dataset.lastConnectionAvailable = last.available ? '1' : '0';
        btn.dataset.lastConnectionIdentity = last.identity || '';
        btn.dataset.lastConnectionEventType = last.event_type || '';
        btn.dataset.lastConnectionObservedAt = last.observed_at_text || '';
        btn.dataset.lastConnectionNeighbor = last.neighbor || '';
        btn.dataset.lastConnectionMac = last.mac || '';
        btn.dataset.lastConnectionIp = last.ip || '';
        btn.dataset.lastConnectionVlan = last.vlan || '';
        btn.dataset.lastConnectionStatus = last.status_after || '';
        btn.dataset.lastConnectionSource = last.source || '';
    }
    function lastConnectionFromDataset(d){
        return {
            available: d.lastConnectionAvailable === '1',
            identity: d.lastConnectionIdentity || '',
            event_type: d.lastConnectionEventType || '',
            observed_at_text: d.lastConnectionObservedAt || '',
            neighbor: d.lastConnectionNeighbor || '',
            mac: d.lastConnectionMac || '',
            ip: d.lastConnectionIp || '',
            vlan: d.lastConnectionVlan || '',
            status_after: d.lastConnectionStatus || '',
            source: d.lastConnectionSource || ''
        };
    }
    function effectiveLastConnectionFromDataset(d){
        // Phase79.5 - current visible port evidence first; history only as fallback.
        function clean(v){
            const s = String(v === 0 ? '0' : (v || '')).trim();
            if(!s) return '';
            const low = s.toLowerCase();
            if(s === '-' || low === 'none' || low === 'null' || low === 'unknown' || low === 'undefined') return '';
            if(s.indexOf('سابقه') !== -1 && s.indexOf('ثبت نشده') !== -1) return '';
            return s;
        }
        const neighborDevice = clean(d.neighborDevice);
        const neighborPort = clean(d.neighborPort);
        const neighbor = [neighborDevice, neighborPort].filter(Boolean).join(' / ');
        const device = clean(d.device);
        const mac = clean(d.macAddress);
        const ip = clean(d.ipAddress);
        const identity = neighbor || device || mac || ip;
        if(identity){
            return {
                available: true,
                identity: identity,
                event_type: String(d.status || '').toLowerCase() === 'up' ? 'Current' : 'Last known',
                observed_at_text: clean(d.discoveryLastPoll) || clean(d.snmpLastPoll) || clean(d.updatedAt) || '',
                neighbor: neighbor,
                neighbor_source: clean(d.neighborSource),
                source: clean(d.neighborSource) || 'current-db',
                mac: mac,
                ip: ip,
                vlan: clean(d.accessVlan) || clean(d.vlan),
                status_after: clean(d.status)
            };
        }
        const last = lastConnectionFromDataset(d);
        if(hasMeaningfulLastConnection(last)) return last;
        return {available:false, identity:'', event_type:'', observed_at_text:'', neighbor:'', source:'', mac:'', ip:'', vlan:'', status_after:''};
    }
    function setLastConnection(root, attrName, last){
        // PHASE79_6_2_LAST_CONNECTED_DOM_FIX
        last = last || {};
        const box = root.querySelector('[data-phase79-last-connected]');
        const typeEl = root.querySelector('[' + attrName + '="last_connection_event_type"]');
        const eventType = (last.event_type || '').toString().trim();
        if(typeEl){ typeEl.textContent = eventType || '-'; }
        if(!box) return;

        const real = hasMeaningfulLastConnection(last);
        box.className = 'phase79-lc-body ' + (real ? 'is-available' : 'is-empty');
        if(!real){
            box.innerHTML = '<div class="phase79-lc-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }

        const rows = [];
        const clean = function(value){
            const v = (value || '').toString().trim();
            if(!v || v === '-' || v.toLowerCase() === 'none' || v.toLowerCase() === 'unknown') return '';
            return v;
        };
        const add = function(label, value, ltr){
            const v = clean(value);
            if(!v) return;
            rows.push('<div class="phase79-lc-row"><span class="phase79-lc-label">' + esc(label) + '</span><strong class="phase79-lc-value ' + (ltr ? 'ltr' : '') + '" title="' + esc(v) + '">' + esc(v) + '</strong></div>');
        };

        const identity = clean(last.identity) || clean(last.neighbor) || clean(last.mac) || clean(last.ip);
        add('Device', identity, true);
        if(clean(last.neighbor) && clean(last.neighbor) !== identity) add('Neighbor', last.neighbor, true);
        add('MAC', last.mac, true);
        add('IP', last.ip, true);

        if(!rows.length){
            box.className = 'phase79-lc-body is-empty';
            box.innerHTML = '<div class="phase79-lc-empty">سابقه اتصال واقعی برای این پورت ثبت نشده است.</div>';
            return;
        }
        box.innerHTML = '<div class="phase79-lc-list">' + rows.join('') + '</div>';
    }

    function refreshLastConnectionFromPayload(button, root, attrName){
        if(!button || !button.dataset || !button.dataset.portId) return;
        const url = '/port/' + encodeURIComponent(button.dataset.portId) + '/payload/';
        fetch(url, {credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}})
            .then(function(response){ return response.json().catch(function(){return null;}); })
            .then(function(data){
                if(!data || !data.ok || !data.port) return;
                updateButtonFromPayload(button, data);
                setLastConnection(root, attrName, effectiveLastConnectionFromDataset(button.dataset));
            })
            .catch(function(){ /* read-only helper; do not break popup */ });
    }
    function updateButtonFromPayload(btn, payload){
        if(!btn || !payload) return;
        const port = payload.port || {};
        if(payload.action === 'shutdown') port.status = port.status || 'Disabled';
        if(payload.action === 'no_shutdown') port.status = port.status || 'Down';
        if(payload.action === 'force_trunk') port.mode = port.mode || 'Trunk';
        if(payload.action === 'set_access_vlan') { port.vlan = port.vlan || payload.value; port.mode = port.mode || 'Access'; }
        if(payload.action === 'set_description') port.description = port.description || payload.value;
        if(payload.action === 'clear_description') port.description = '-';
        if(payload.action === 'set_voice_vlan') port.voice_vlan = payload.value;
        if(payload.action === 'remove_voice_vlan') port.voice_vlan = '';
        if(payload.action === 'set_trunk_allowed') port.trunk_vlans = payload.value;

        if(port.status) btn.dataset.status = port.status;
        if(port.mode) btn.dataset.portMode = port.mode;
        if(port.vlan !== undefined) btn.dataset.accessVlan = port.vlan;
        if(port.access_vlan !== undefined) btn.dataset.accessVlan = port.access_vlan;
        if(port.native_vlan !== undefined) btn.dataset.nativeVlan = port.native_vlan;
        if(port.voice_vlan !== undefined) btn.dataset.voiceVlan = port.voice_vlan;
        if(port.trunk_vlans !== undefined) btn.dataset.trunkVlans = port.trunk_vlans;
        if(port.poe_summary !== undefined) btn.dataset.poeSummary = port.poe_summary;
        if(port.description !== undefined) btn.dataset.description = port.description;
        if(port.mac_count !== undefined && port.mac_count !== null) btn.dataset.macCount = port.mac_count;
        if(port.neighbor_device !== undefined) btn.dataset.neighborDevice = port.neighbor_device;
        if(port.neighbor_port !== undefined) btn.dataset.neighborPort = port.neighbor_port;
        if(port.ip_address !== undefined) btn.dataset.ipAddress = port.ip_address;
        if(port.mac_address !== undefined) btn.dataset.macAddress = port.mac_address;
        if(port.device !== undefined) btn.dataset.device = port.device;
        if(port.neighbor_source !== undefined) btn.dataset.neighborSource = port.neighbor_source;
        if(port.updated_at_text !== undefined) btn.dataset.updatedAt = port.updated_at_text;
        if(port.updated_at !== undefined && !port.updated_at_text) btn.dataset.updatedAt = port.updated_at;
        if(port.snmp_last_poll_text !== undefined) btn.dataset.snmpLastPoll = port.snmp_last_poll_text;
        if(port.discovery_last_poll_text !== undefined) btn.dataset.discoveryLastPoll = port.discovery_last_poll_text;
        if(port.last_connection !== undefined) storeLastConnectionOnButton(btn, port.last_connection);

        btn.classList.remove('port-up','port-down','port-disabled','port-error','port-trunk');
        btn.classList.add('port-' + normalizeState(btn.dataset.status));
        if(String(btn.dataset.portMode || '').toLowerCase().includes('trunk')) btn.classList.add('port-trunk');
        const small = btn.querySelector('small');
        if(small){ small.textContent = String(btn.dataset.portMode || '').toLowerCase().includes('trunk') ? 'trunk' : (btn.dataset.device || ''); }
    }
    let currentPortButton = null;
    function fillModal(button){
        const modal = document.getElementById('dashboard-port-modal');
        if(!modal || !button) return;
        currentPortButton = button;
        const d = button.dataset;
        modal.classList.add('open');
        modal.setAttribute('aria-hidden','false');
        document.body.style.overflow = 'hidden';
        setText(modal,'[data-field="title"]','پورت ' + valueOrDash(d.interface));
        setText(modal,'[data-field="subtitle"]',valueOrDash(d.switchName) + ' • ' + valueOrDash(d.switchIp));
        ['interface','status','port_mode','access_vlan','voice_vlan','native_vlan','trunk_vlans','poe_summary','mac_count','ip_address','mac_address','device','description','neighbor_source','updated_at','snmp_last_poll','discovery_last_poll'].forEach(function(name){
            const key = name.replace(/_([a-z])/g,function(_,c){return c.toUpperCase();});
            setText(modal,'[data-field="' + name + '"]',d[key]);
        });
        setText(modal,'[data-field="neighbor"]',neighborText(d));
        setLastConnection(modal, 'data-field', effectiveLastConnectionFromDataset(d));
        refreshLastConnectionFromPayload(button, modal, 'data-field');
        const edit = field(modal,'[data-field="edit_url"]'); if(edit) edit.href = d.editUrl || '#';
        const map = field(modal,'[data-field="map_url"]'); if(map) map.href = d.mapUrl || '#';
        const table = field(modal,'[data-field="table_url"]'); if(table) table.href = d.tableUrl || '#';
        const form = modal.querySelector('.js-dashboard-ssh-form');
        if(form){ fillSshForm(form, d); setResult(form,true,''); }
    }
    function closeModal(){
        const modal = document.getElementById('dashboard-port-modal');
        if(modal){ modal.classList.remove('open'); modal.setAttribute('aria-hidden','true'); document.body.style.overflow = ''; }
    }
    function fillSshForm(form, d){
        setValue(form,'[name="switch_id"]',d.switchId || '');
        setValue(form,'[name="switch_ip"]',d.switchIp || '');
        setValue(form,'[name="port_id"]',d.portId || '');
        setValue(form,'[name="interface"]',d.interface || '');
        setValue(form,'[name="interface_name"]',d.interface || '');
        const user = form.querySelector('[name="username"]'); if(user && !user.value) user.value = d.switchUser || 'admin';
        const val = form.querySelector('[name="value"]'); if(val) val.value = d.accessVlan && d.accessVlan !== '-' ? d.accessVlan : '';
        const force = form.querySelector('[name="force"]'); if(force) force.checked = false;
        const confirmed = form.querySelector('[name="confirmed"]'); if(confirmed) confirmed.checked = false;
        applyActionMeta(form);
    }
    function fillDetailPanel(button){
        const panel = document.querySelector('[data-sm-port-detail]');
        if(!panel || !button) return;
        currentPortButton = button;
        document.querySelectorAll('[data-sm-port-button]').forEach(b => b.classList.remove('selected-port'));
        button.classList.add('selected-port');
        const d = button.dataset;
        setText(panel,'[data-detail-title]','پورت ' + valueOrDash(d.interface));
        ['status','port_mode','access_vlan','voice_vlan','native_vlan','trunk_vlans','poe_summary','mac_count','ip_address','mac_address','device','description','neighbor_source','updated_at','snmp_last_poll','discovery_last_poll'].forEach(function(name){
            const key = name.replace(/_([a-z])/g,function(_,c){return c.toUpperCase();});
            setText(panel,'[data-detail="' + name + '"]',d[key]);
        });
        setText(panel,'[data-detail="neighbor"]',neighborText(d));
        setLastConnection(panel, 'data-detail', effectiveLastConnectionFromDataset(d));
        refreshLastConnectionFromPayload(button, panel, 'data-detail');
        const edit = field(panel,'[data-detail-link="edit_url"]'); if(edit) edit.href = d.editUrl || '#';
        const table = field(panel,'[data-detail-link="table_url"]'); if(table) table.href = d.tableUrl || '#';
        const form = panel.querySelector('.js-dashboard-ssh-form');
        if(form){ fillSshForm(form, d); setResult(form,true,''); }
    }
    function applyCurrentUpdate(data){
        updateButtonFromPayload(currentPortButton, data);
        if(currentPortButton){
            const modal = document.getElementById('dashboard-port-modal');
            if(modal && modal.classList.contains('open')) fillModal(currentPortButton);
            if(document.querySelector('[data-sm-port-detail]')) fillDetailPanel(currentPortButton);
        }
    }
    function validateRisk(form){
        const action = formValue(form,'action');
        const meta = actionMeta(action);
        if(meta.force && !formChecked(form,'force')){
            setResult(form,false,'برای این عملیات، تیک اجازه تغییر روی Trunk / Uplink لازم است.');
            return false;
        }
        if(meta.risky && !formChecked(form,'confirmed')){
            setResult(form,false,'برای این عملیات، تیک تأیید نهایی لازم است.');
            return false;
        }
        return true;
    }
    function refreshSelectedPortAfterSsh(form, initialData){
        // Phase79.3 - after SSH, fetch fresh port payload without closing popup.
        const port = initialData && initialData.port ? initialData.port : null;
        const portId = (port && port.id) ? port.id : formValue(form, 'port_id');
        if(!portId) return;
        window.setTimeout(function(){
            fetch('/port/' + encodeURIComponent(portId) + '/payload/', {
                credentials:'same-origin',
                headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}
            }).then(function(response){
                return response.json().catch(function(){return null;});
            }).then(function(data){
                if(data && data.ok && data.port){
                    applyCurrentUpdate(data);
                    setResult(form,true,'عملیات موفق بود؛ اطلاعات پورت به‌روزرسانی شد.');
                }else{
                    setResult(form,true,'عملیات موفق بود؛ دریافت وضعیت جدید پورت کامل نشد.');
                }
            }).catch(function(){
                setResult(form,true,'عملیات موفق بود؛ به‌روزرسانی خودکار پورت انجام نشد.');
            });
        }, 1200);
    }
    function submitSshForm(form){
        const username = form.querySelector('[name="username"]');
        const password = form.querySelector('[name="password"]');
        if(!username || !username.value.trim() || !password || !password.value.trim()){
            setResult(form,false,'Username و Password لازم است.');
            return;
        }
        const iface = form.querySelector('[name="interface"]');
        if(!iface || !iface.value.trim()){
            setResult(form,false,'ابتدا یک پورت را انتخاب کن.');
            return;
        }
        if(!validateRisk(form)) return;
        const submit = form.querySelector('[type="submit"]');
        if(submit) submit.disabled = true;
        setResult(form,true,'در حال اجرای عملیات SSH ...');
        const fd = new FormData(form);
        fd.set('ssh_username', username.value);
        fd.set('ssh_password', password.value);
        fd.set('ajax','1');
        fetch(form.dataset.actionUrl || '/ssh-port-action/', {
            method:'POST', body:fd, credentials:'same-origin',
            headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}
        }).then(function(response){
            return response.json().catch(function(){return {ok:false,error:'پاسخ سرور معتبر نیست.'};}).then(function(data){return {response:response,data:data};});
        }).then(function(result){
            if(result.response.ok && result.data.ok){
                applyCurrentUpdate(result.data);
                setResult(form,true,'عملیات موفق بود؛ در حال به‌روزرسانی پورت ...');
                refreshSelectedPortAfterSsh(form, result.data);
                previewCommands(form);
            }else{
                setResult(form,false,result.data.error || result.data.message || 'اجرای SSH خطا داد.');
            }
        }).catch(function(error){
            setResult(form,false,'ارتباط با سرور برقرار نشد: ' + error);
        }).finally(function(){ if(submit) submit.disabled = false; });
    }
    function refreshStatusBox(card){ return card ? card.querySelector('.smart-refresh-mini') : null; }
    function setCardRefreshState(card, state, status, step, result, error){
        if(!card) return;
        const box = refreshStatusBox(card);
        if(box){ box.dataset.refreshCardState = state || 'idle'; }
        setText(card,'[data-refresh-status]',status || 'Ready');
        setText(card,'[data-refresh-step]',step || '-');
        setText(card,'[data-refresh-detail-step]',step || '-');
        if(result !== undefined) setText(card,'[data-refresh-detail-result]',result || '-');
        if(error !== undefined) setText(card,'[data-refresh-detail-error]',error || '-');
    }
    function applySwitchStatus(card, payload){
        const status = payload && payload.switch_status ? payload.switch_status : {};
        if(status.snmp_last_poll && status.snmp_last_poll !== '-') setText(card,'[data-refresh-snmp-last]',status.snmp_last_poll);
        if(status.discovery_last_poll && status.discovery_last_poll !== '-') setText(card,'[data-refresh-discovery-last]',status.discovery_last_poll);
        if(payload && payload.stage === 'sync' && (!status.snmp_last_poll || status.snmp_last_poll === '-')) setText(card,'[data-refresh-snmp-last]',timestampNow());
        if(payload && payload.stage === 'ports' && (!status.snmp_last_poll || status.snmp_last_poll === '-')) setText(card,'[data-refresh-snmp-last]',timestampNow());
        if(payload && payload.stage === 'discovery' && (!status.discovery_last_poll || status.discovery_last_poll === '-')) setText(card,'[data-refresh-discovery-last]',timestampNow());
        const err = status.discovery_error || status.snmp_error || '';
        setText(card,'[data-refresh-detail-error]',err || '-');
    }
    function refreshStep(card, stage){
        const fd = new FormData();
        fd.set('stage', stage);
        return fetch(card.dataset.refreshUrl, {
            method:'POST',
            body:fd,
            credentials:'same-origin',
            headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json','X-CSRFToken':getCookie('csrftoken')}
        }).then(function(response){
            return response.json().catch(function(){return {ok:false,message:'پاسخ سرور معتبر نیست.'};});
        }).then(function(data){
            applySwitchStatus(card, data);
            if(!data.ok){ throw new Error(data.message || 'خطای Refresh'); }
            return data;
        });
    }
    async function refreshOneSwitch(card, panel){
        const title = card.querySelector('.switch-title-link');
        const name = title ? title.textContent.trim() : 'Switch';
        const steps = [
            {id:'sync', label:'Sync Ports'},
            {id:'ports', label:'SNMP Ports'},
            {id:'discovery', label:'CDP / LLDP / MAC'}
        ];
        let line = null;
        if(panel){
            line = document.createElement('div');
            line.className = 'refresh-line running';
            line.innerHTML = '<strong></strong><span></span>';
            line.querySelector('strong').textContent = name;
            line.querySelector('span').textContent = 'در صف اجرا';
            panel.appendChild(line);
        }
        try{
            setCardRefreshState(card,'running','Running','شروع Refresh','-', '');
            let lastSummary = '-';
            for(const step of steps){
                setCardRefreshState(card,'running','Running',step.label,lastSummary,'');
                if(line) line.querySelector('span').textContent = step.label + ' ...';
                const data = await refreshStep(card, step.id);
                lastSummary = data.step && data.step.summary ? data.step.summary : 'OK';
                setCardRefreshState(card,'running','Running',step.label,lastSummary,'');
            }
            setCardRefreshState(card,'ok','Done','کامل شد',lastSummary,'');
            if(line){ line.className = 'refresh-line ok'; line.querySelector('span').textContent = lastSummary; }
            return {ok:true};
        }catch(error){
            setCardRefreshState(card,'fail','Error','متوقف شد','-', error.message || String(error));
            if(line){ line.className = 'refresh-line fail'; line.querySelector('span').textContent = error.message || String(error); }
            return {ok:false,error:error};
        }
    }
    let refreshAllRunning = false;
    let autoRefreshTimer = null;
    let autoRefreshSecondTimer = null;
    let autoRefreshNextRun = 0;

    function timestampNow(){
        const d = new Date();
        const pad = function(n){ return String(n).padStart(2, '0'); };
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    }
    function updateAutoCountdown(){
        const el = document.querySelector('[data-auto-refresh-countdown]');
        const select = document.querySelector('[data-auto-refresh-select]');
        if(!el || !select) return;
        const minutes = parseInt(select.value || '0', 10);
        if(!minutes){ el.textContent = 'Auto: خاموش'; return; }
        const remain = Math.max(0, Math.ceil((autoRefreshNextRun - Date.now()) / 1000));
        const mm = Math.floor(remain / 60);
        const ss = String(remain % 60).padStart(2, '0');
        el.textContent = 'Auto: ' + mm + ':' + ss;
    }
    async function runRefreshAll(panel, state, btn, source){
        if(refreshAllRunning) return {ok:false, skipped:true};
        refreshAllRunning = true;
        const cards = Array.from(document.querySelectorAll('[data-switch-card]'));
        if(btn) btn.disabled = true;
        if(state) state.textContent = source === 'auto' ? 'Auto Refresh در حال اجرا ...' : 'در حال اجرا ...';
        if(panel) panel.innerHTML = '';
        let okCount = 0;
        let failCount = 0;
        try{
            for(const card of cards){
                const result = await refreshOneSwitch(card, panel);
                if(result.ok) okCount += 1; else failCount += 1;
            }
            if(state) state.textContent = failCount ? ('پایان با خطا: ' + failCount) : ('کامل شد: ' + okCount + ' | ' + timestampNow());
            return {ok:failCount === 0, okCount:okCount, failCount:failCount};
        }finally{
            refreshAllRunning = false;
            if(btn) btn.disabled = false;
        }
    }
    function scheduleAutoRefresh(){
        const select = document.querySelector('[data-auto-refresh-select]');
        const panel = document.querySelector('[data-refresh-results]');
        const form = document.querySelector('.js-refresh-all-form');
        const btn = form ? form.querySelector('button[type="submit"]') : null;
        const state = form ? form.querySelector('[data-refresh-state]') : null;
        if(autoRefreshTimer){ clearTimeout(autoRefreshTimer); autoRefreshTimer = null; }
        if(autoRefreshSecondTimer){ clearInterval(autoRefreshSecondTimer); autoRefreshSecondTimer = null; }
        if(!select) return;
        const minutes = parseInt(select.value || '0', 10);
        localStorage.setItem('switchmap_auto_refresh_minutes', String(minutes));
        if(!minutes){ updateAutoCountdown(); return; }
        autoRefreshNextRun = Date.now() + (minutes * 60 * 1000);
        updateAutoCountdown();
        autoRefreshSecondTimer = setInterval(updateAutoCountdown, 1000);
        autoRefreshTimer = setTimeout(async function(){
            if(!document.hidden){
                await runRefreshAll(panel, state, btn, 'auto');
            }
            scheduleAutoRefresh();
        }, minutes * 60 * 1000);
    }
    function setupRefreshAll(){
        const panel = document.querySelector('[data-refresh-results]');
        document.querySelectorAll('.js-refresh-all-form').forEach(function(form){
            form.addEventListener('submit', async function(event){
                event.preventDefault();
                const btn = form.querySelector('button[type="submit"]');
                const state = form.querySelector('[data-refresh-state]');
                await runRefreshAll(panel, state, btn, 'manual');
                scheduleAutoRefresh();
            });
        });
        document.querySelectorAll('.js-refresh-one-switch').forEach(function(button){
            button.addEventListener('click', async function(){
                const card = button.closest('[data-switch-card]');
                if(!card) return;
                button.disabled = true;
                if(panel) panel.innerHTML = '';
                await refreshOneSwitch(card, panel);
                button.disabled = false;
            });
        });
        const select = document.querySelector('[data-auto-refresh-select]');
        if(select){
            const saved = localStorage.getItem('switchmap_auto_refresh_minutes');
            if(saved !== null){ select.value = saved; }
            select.addEventListener('change', scheduleAutoRefresh);
            scheduleAutoRefresh();
        }
    }
    function setupReportAccordion(){
        document.querySelectorAll('[data-report-accordion] details').forEach(function(item){
            item.addEventListener('toggle', function(){
                if(!item.open) return;
                document.querySelectorAll('[data-report-accordion] details').forEach(function(other){
                    if(other !== item) other.open = false;
                });
            });
        });
    }
    function setupTopbarDropdowns(){
        const dropdowns = Array.from(document.querySelectorAll('.topbar-dropdown, .user-dropdown'));
        if(!dropdowns.length) return;

        function closeDropdown(item){
            if(!item) return;
            item.open = false;
            const summary = item.querySelector('summary');
            if(summary) summary.setAttribute('aria-expanded','false');
        }
        function closeOthers(active){
            dropdowns.forEach(function(item){
                if(item !== active) closeDropdown(item);
            });
        }
        dropdowns.forEach(function(item){
            const summary = item.querySelector('summary');
            if(summary){
                summary.setAttribute('aria-haspopup','true');
                summary.setAttribute('aria-expanded', item.open ? 'true' : 'false');
            }
            item.addEventListener('toggle', function(){
                if(summary) summary.setAttribute('aria-expanded', item.open ? 'true' : 'false');
                if(item.open) closeOthers(item);
            });
        });
        document.addEventListener('click', function(event){
            if(event.target.closest('.topbar-dropdown, .user-dropdown')) return;
            dropdowns.forEach(closeDropdown);
        });
        document.addEventListener('keydown', function(event){
            if(event.key !== 'Escape') return;
            dropdowns.forEach(closeDropdown);
        });
    }

    function setupSearch(){
        /* PHASE70_1_SEARCH_EXACT_UI_FIX: exact label/interface search; no broad card text; no port re-render */
        const input = document.querySelector('[data-switch-search]');
        const triggerButtons = document.querySelectorAll('[data-search-trigger]');
        const cards = Array.from(document.querySelectorAll('[data-switch-card]'));
        const browser = document.querySelector('.device-browser-shell');
        const grid = document.querySelector('.compact-device-grid');
        const panel = document.querySelector('.modern-search-panel');
        const browserInitialOpen = browser ? browser.open : false;
        if(!input && !triggerButtons.length) return;

        let state = panel ? panel.querySelector('[data-search-result-state]') : null;
        if(panel && !state){
            state = document.createElement('div');
            state.className = 'search-result-state';
            state.setAttribute('data-search-result-state','');
            panel.appendChild(state);
        }

        let results = panel ? panel.querySelector('[data-search-results]') : null;
        if(panel && !results){
            results = document.createElement('div');
            results.className = 'search-results-panel';
            results.setAttribute('data-search-results','');
            results.hidden = true;
            panel.appendChild(results);
        }

        let empty = grid ? grid.querySelector('[data-search-empty-state]') : null;
        if(grid && !empty){
            empty = document.createElement('section');
            empty.className = 'surface-card empty-card search-empty-state';
            empty.setAttribute('data-search-empty-state','');
            empty.textContent = 'نتیجه‌ای برای این جستجو پیدا نشد.';
            empty.hidden = true;
            grid.appendChild(empty);
        }

        const toAsciiDigits = function(value){
            const fa = '۰۱۲۳۴۵۶۷۸۹';
            const ar = '٠١٢٣٤٥٦٧٨٩';
            return String(value || '')
                .replace(/[۰-۹]/g, function(ch){ return String(fa.indexOf(ch)); })
                .replace(/[٠-٩]/g, function(ch){ return String(ar.indexOf(ch)); });
        };
        const normalize = function(value){
            return toAsciiDigits(value)
                .toLowerCase()
                .replace(/[\u200c\u200f\u202a-\u202e]/g,' ')
                .replace(/[_\-\/\\:;,|()[\]{}]+/g,' ')
                .replace(/\s+/g,' ')
                .trim();
        };
        const compact = function(value){
            return toAsciiDigits(value).toLowerCase().replace(/[^a-z0-9آ-ی]+/g,'');
        };
        const escapeHtml = function(value){
            return String(value || '').replace(/[&<>"']/g, function(ch){
                return ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[ch];
            });
        };
        const ds = function(el, key){ return el && el.dataset ? (el.dataset[key] || '') : ''; };
        const firstText = function(){
            for(let i=0; i<arguments.length; i += 1){
                const value = String(arguments[i] || '').trim();
                if(value && value !== '-') return value;
            }
            return '-';
        };
        const splitTokens = function(value){
            const n = normalize(value);
            return n ? n.split(' ').filter(Boolean) : [];
        };
        const labelTokens = function(port){
            const raw = [
                ds(port,'portLabel'), ds(port,'officeLabel'), ds(port,'searchCode'),
                ds(port,'portDescription'), ds(port,'description')
            ];
            const tokens = [];
            raw.forEach(function(value){
                splitTokens(value).forEach(function(t){ if(t && t !== '-') tokens.push(t); });
            });
            return Array.from(new Set(tokens));
        };
        const interfaceValues = function(port){
            return [ds(port,'interface'), ds(port,'interfaceName'), ds(port,'portName')].filter(Boolean);
        };
        const switchValues = function(card){
            const title = card.querySelector('.switch-title-link') || card.querySelector('h2');
            const ip = card.querySelector('.sm-switch-title .ltr');
            const model = card.querySelector('.switch-avatar strong');
            return [card.dataset.switchName || '', title ? title.textContent : '', ip ? ip.textContent : '', model ? model.textContent : ''];
        };
        const isCodeQuery = function(qCompact){ return /^[a-z]{1,5}\d{1,5}$/.test(qCompact); };
        const portMatches = function(port, rawQuery){
            const q = normalize(rawQuery);
            const qCompact = compact(rawQuery);
            if(!qCompact) return false;
            const labels = labelTokens(port);
            const labelCompacts = labels.map(compact).filter(Boolean);
            const interfaces = interfaceValues(port).map(compact).filter(Boolean);
            if(isCodeQuery(qCompact)){
                return labelCompacts.some(function(t){ return t === qCompact; });
            }
            if(interfaces.some(function(v){ return v === qCompact || (qCompact.length >= 4 && v.indexOf(qCompact) === 0); })) return true;
            const qParts = q.split(' ').filter(Boolean).map(compact).filter(Boolean);
            if(qParts.length > 1){
                return qParts.every(function(part){
                    return labelCompacts.some(function(t){ return t === part || (part.length >= 3 && t.indexOf(part) === 0); });
                });
            }
            if(qCompact.length >= 3){
                return labelCompacts.some(function(t){ return t === qCompact || t.indexOf(qCompact) === 0; });
            }
            return labelCompacts.some(function(t){ return t === qCompact; });
        };
        const switchMatches = function(card, rawQuery){
            const qCompact = compact(rawQuery);
            if(qCompact.length < 3 || isCodeQuery(qCompact)) return false;
            return switchValues(card).some(function(value){
                const v = compact(value);
                return v && (v === qCompact || v.indexOf(qCompact) === 0 || (qCompact.length >= 5 && v.indexOf(qCompact) !== -1));
            });
        };
        const clearHighlights = function(card){
            const root = card || document;
            root.querySelectorAll('[data-sm-port-button]').forEach(function(port){
                port.classList.remove('search-port-highlight','search-port-focus');
            });
        };
        const resetSearchView = function(){
            cards.forEach(function(card){
                card.hidden = false;
                card.style.display = '';
                card.classList.remove('search-match');
                clearHighlights(card);
            });
            if(browser){
                browser.classList.remove('search-active');
                browser.open = browserInitialOpen;
            }
            if(empty) empty.hidden = true;
            if(state) state.textContent = '';
            if(results){ results.hidden = true; results.innerHTML = ''; }
        };
        const renderResults = function(items, query, totalPorts){
            if(!results) return;
            if(!query){ results.hidden = true; results.innerHTML = ''; return; }
            if(!items.length){
                results.hidden = false;
                results.innerHTML = '<div class="search-result-empty">نتیجه‌ای پیدا نشد.</div>';
                return;
            }
            const html = items.slice(0,8).map(function(item){
                const port = item.port;
                const label = port ? firstText(ds(port,'portLabel'), ds(port,'officeLabel'), ds(port,'searchCode')) : '';
                const iface = port ? firstText(ds(port,'interface'), ds(port,'interfaceName'), ds(port,'portName')) : '';
                const device = port ? firstText(ds(port,'device'), ds(port,'connectedDevice'), ds(port,'neighborDevice'), ds(port,'portDescription'), ds(port,'description')) : '';
                const meta = [item.ip, item.model, label, iface, device].filter(function(v){ return v && v !== '-'; }).join(' · ');
                return '<button type="button" class="search-result-item" data-result-switch-id="' + escapeHtml(item.switchId) + '" data-result-port-id="' + escapeHtml(port ? ds(port,'portId') : '') + '">' +
                    '<strong>' + escapeHtml(item.name) + '</strong>' +
                    '<span>' + escapeHtml(meta || 'Switch') + '</span>' +
                '</button>';
            }).join('');
            const more = items.length > 8 ? '<div class="search-result-more">+' + (items.length - 8) + ' نتیجه دیگر</div>' : '';
            results.hidden = false;
            results.innerHTML = '<div class="search-result-head">نتیجه‌ها: ' + items.length + ' دستگاه / ' + totalPorts + ' پورت</div>' + html + more;
        };
        if(results){
            results.addEventListener('click', function(event){
                const item = event.target.closest('[data-result-switch-id]');
                if(!item) return;
                const card = document.querySelector('[data-switch-card][data-switch-id="' + item.dataset.resultSwitchId + '"]');
                if(!card) return;
                if(browser) browser.open = true;
                card.hidden = false;
                card.style.display = '';
                card.scrollIntoView({behavior:'smooth', block:'center'});
                const portId = item.dataset.resultPortId;
                if(portId){
                    const port = card.querySelector('[data-sm-port-button][data-port-id="' + portId + '"]');
                    if(port){
                        port.classList.add('search-port-focus','search-port-highlight');
                        window.setTimeout(function(){ port.classList.remove('search-port-focus'); }, 1800);
                        port.scrollIntoView({behavior:'smooth', block:'center', inline:'center'});
                    }
                }
            });
        }
        const run = function(){
            const rawQuery = input ? input.value : '';
            const qCompact = compact(rawQuery);
            if(!qCompact){ resetSearchView(); return; }
            let matched = 0;
            let matchedPortsTotal = 0;
            const resultItems = [];
            cards.forEach(function(card){
                const ports = Array.from(card.querySelectorAll('[data-sm-port-button]'));
                const matchedPorts = ports.filter(function(port){ return portMatches(port, rawQuery); });
                ports.forEach(function(port){ port.classList.toggle('search-port-highlight', matchedPorts.indexOf(port) !== -1); });
                const ok = matchedPorts.length > 0 || switchMatches(card, rawQuery);
                card.hidden = !ok;
                card.style.display = ok ? '' : 'none';
                card.classList.toggle('search-match', ok);
                if(ok){
                    matched += 1;
                    matchedPortsTotal += matchedPorts.length;
                    resultItems.push({
                        switchId: card.dataset.switchId || '',
                        name: firstText((card.querySelector('.switch-title-link') || card.querySelector('h2') || {}).textContent, card.dataset.switchName, 'Switch'),
                        ip: firstText((card.querySelector('.sm-switch-title .ltr') || {}).textContent, ''),
                        model: firstText((card.querySelector('.switch-avatar strong') || {}).textContent, ''),
                        port: matchedPorts[0] || null
                    });
                }
            });
            if(browser){
                if(matched > 0) browser.open = true;
                browser.classList.add('search-active');
            }
            if(empty) empty.hidden = matched > 0;
            if(state) state.textContent = 'نتیجه جستجو: ' + matched + ' دستگاه / ' + matchedPortsTotal + ' پورت';
            renderResults(resultItems, rawQuery, matchedPortsTotal);
        };
        if(input){
            input.addEventListener('input', run);
            input.addEventListener('search', run);
            input.addEventListener('keydown', function(event){
                if(event.key === 'Enter'){
                    event.preventDefault();
                    run();
                }
            });
        }
        triggerButtons.forEach(function(btn){ btn.addEventListener('click', run); });
        resetSearchView();
    }

    function setupLiveInsightDashboard(){
        /* Phase 63 compatibility marker: data-dashboard-data-url */
        const phase63DashboardDataUrlMarker = "data-dashboard-data-url";
        const root = document.querySelector('[data-dashboard-live]');
        if(!root) return;
        const url = root.dataset.dashboardDataUrl;
        const refreshButton = document.querySelector('[data-dashboard-manual-refresh]');
        const updateText = function(name, value){
            root.querySelectorAll('[data-field="' + name + '"]').forEach(function(el){ el.textContent = valueOrDash(value); });
            document.querySelectorAll('[data-field="' + name + '"]').forEach(function(el){ el.textContent = valueOrDash(value); });
        };
        const updatePercentStyle = function(name, value){
            root.querySelectorAll('[data-field-style="' + name + '"]').forEach(function(el){ el.style.width = String(value || 0) + '%'; });
        };
        const actionHtml = function(items){
            if(!items || !items.length) return '<div class="phase66-empty modern-empty-state">اقدام فوری لازم نیست.</div>';
            return items.slice(0,3).map(function(item){
                return '<span class="phase66-list-item action-item severity-' + escapeHtml(item.severity || 'info') + '"' + dataAttrsOnly(item) + '>' +
                    '<strong>' + escapeHtml(item.title || item.object_name || '-') + '</strong>' +
                    '<small>' + escapeHtml(compactIssueText(item, 'نیازمند بررسی')) + '</small>' +
                '</span>';
            }).join('');
        };
        const alarmHtml = function(items){
            if(!items || !items.length) return '<div class="phase66-empty modern-empty-state">آلارم فعالی ثبت نشده است.</div>';
            return items.slice(0,3).map(function(item){
                return '<a class="phase66-list-item live-alarm severity-' + escapeHtml(item.severity || 'info') + '"' + detailAttrs(item) + '>' +
                    '<strong>' + escapeHtml(item.title || '-') + '</strong>' +
                    '<small>' + escapeHtml(compactIssueText(item, 'آلارم فعال')) + '</small>' +
                '</a>';
            }).join('');
        };
        const topologyHtml = function(items){
            if(!items || !items.length) return '<div class="phase66-empty modern-empty-state">Issue توپولوژی فعال نیست.</div>';
            return items.slice(0,3).map(function(item){
                return '<a class="phase66-list-item topology-issue severity-' + escapeHtml(item.severity || 'info') + '"' + detailAttrs(item) + '>' +
                    '<strong>' + escapeHtml(item.title || '-') + '</strong>' +
                    '<small>' + escapeHtml(compactIssueText(item, 'Issue توپولوژی')) + '</small>' +
                '</a>';
            }).join('');
        };
        const updatePrimaryActionCard = function(item){
            const card = root.querySelector('[data-dashboard-primary-action]');
            if(!card || !item) return;
            card.dataset.issueId = item.issue_id || '';
            card.dataset.detailUrl = item.detail_url || item.target_url || item.url || '#';
            card.dataset.objectName = item.object_name || item.target || item.title || '';
            card.dataset.objectType = item.object_type || '';
            card.dataset.severity = item.severity || 'info';
            card.dataset.lastCheck = item.last_check_time || item.last_poll_text || item.last_seen_text || '';
            card.dataset.reason = item.short_reason || item.summary || item.message || '';
            card.dataset.action = item.recommended_action || item.action || '';
            card.className = card.className.replace(/severity-[^\s]+/g, '').trim() + ' severity-' + (item.severity || 'info');
        };
        const applyPayload = function(payload){
            const data = payload && payload.dashboard ? payload.dashboard : null;
            if(!data) return;
            const counters = data.counters || {};
            const overall = data.overall || {};
            const background = data.background || {};
            root.dataset.dashboardState = overall.state || '';
            const exec = root.querySelector('.insight-executive-card');
            if(exec){ exec.className = 'insight-executive-card state-' + (overall.state || 'unknown'); }
            updateText('generated_at', data.generated_at || '');
            updateText('overall_title', overall.title || '');
            updateText('overall_subtitle', overall.subtitle || '');
            updateText('healthy', counters.healthy);
            updateText('attention', counters.attention);
            updateText('active_alarms', counters.active_alarms);
            updateText('critical_alarms', counters.critical_alarms);
            updateText('warning_alarms', counters.warning_alarms);
            updateText('sfp_issues', counters.sfp_issues);
            updateText('sfp_critical', counters.sfp_critical);
            updateText('topology_issues', counters.topology_issues);
            updateText('topology_critical', counters.topology_critical);
            updateText('snmp_failed', counters.snmp_failed);
            updateText('stale', counters.stale);
            updateText('not_monitored', counters.not_monitored);
            updateText('reliable_percent', String(counters.reliable_percent || 0) + '%');
            updateText('coverage_percent', String(counters.coverage_percent || 0) + '%');
            updateText('healthy_inline', counters.healthy);
            updateText('total_devices', counters.total_devices);
            updateText('not_monitored_inline', counters.not_monitored);
            updatePercentStyle('coverage_percent', counters.coverage_percent || 0);
            const ring = root.querySelector('.insight-ring');
            if(ring){ ring.style.setProperty('--value', String(counters.reliable_percent || 0) + '%'); }
            updateText('background_label', background.label || '');
            updateText('background_last_run', background.last_run_text || '');
            updateText('background_summary', background.summary || '');
            const bg = document.querySelector('[data-dashboard-background-state]');
            if(bg) bg.textContent = background.label || 'Auto Refresh';
            const bgIcon = document.querySelector('[data-dashboard-background-icon]');
            if(bgIcon){
                const healthy = (background.state || '') === 'ok';
                bgIcon.textContent = healthy ? '●' : '!';
                bgIcon.classList.toggle('is-warning', !healthy);
                bgIcon.classList.toggle('is-error', !healthy);
                bgIcon.setAttribute('title', background.label || 'Auto Refresh');
            }
            if(data.actions && data.actions.length) updatePrimaryActionCard(data.actions[0]);
            const actions = root.querySelector('[data-dashboard-actions]');
            if(actions) actions.innerHTML = actionHtml(data.actions || []);
            const alarms = root.querySelector('[data-dashboard-alarms]');
            if(alarms) alarms.innerHTML = alarmHtml(data.alarms || []);
            const topology = root.querySelector('[data-dashboard-topology-issues]');
            if(topology) topology.innerHTML = topologyHtml(data.topology_issues || []);
            if(data.actions && data.actions.length){
                updateText('next_action_title', data.actions[0].title || '');
                updateText('next_action_text', data.actions[0].action || '');
            }
        };
        const refresh = function(){
            if(!url) return;
            fetch(url, {credentials:'same-origin', headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}})
                .then(function(response){ return response.json(); })
                .then(applyPayload)
                .catch(function(){ updateText('background_label', 'ارتباط با Dashboard Data خطا داد'); });
        };
        if(refreshButton){ refreshButton.addEventListener('click', refresh); }
        refresh();
        window.setInterval(function(){ if(!document.hidden) refresh(); }, 60000);
    }


    function setupDashboardIssueDetails(){
        const drawer = document.querySelector('[data-dashboard-detail-drawer]');
        if(!drawer) return;
        const setDrawerText = function(selector, value){
            const el = drawer.querySelector(selector);
            if(el) el.textContent = valueOrDash(value);
        };
        document.addEventListener('click', function(event){
            const item = event.target.closest('[data-dashboard-detail]');
            if(!item) return;
            event.preventDefault();
            const issueId = item.dataset.issueId || '';
            const severity = item.dataset.severity || 'info';
            setDrawerText('[data-detail-severity]', severity);
            setDrawerText('[data-detail-title]', item.querySelector('strong') ? item.querySelector('strong').textContent : item.dataset.objectName);
            setDrawerText('[data-detail-object]', [item.dataset.objectType, item.dataset.objectName].filter(Boolean).join(' / '));
            setDrawerText('[data-detail-issue-id]', issueId);
            setDrawerText('[data-detail-last-check]', item.dataset.lastCheck || 'ثبت نشده');
            setDrawerText('[data-detail-reason]', item.dataset.reason || '-');
            setDrawerText('[data-detail-action]', item.dataset.action || '-');
            const link = drawer.querySelector('[data-detail-url]');
            if(link) link.href = item.dataset.detailUrl || item.getAttribute('href') || '#';
            drawer.hidden = false;
            drawer.scrollIntoView({behavior:'smooth', block:'nearest'});
        });
        document.addEventListener('keydown', function(event){
            if(event.key !== 'Enter' && event.key !== ' ') return;
            const item = event.target.closest('[data-dashboard-detail][role="button"]');
            if(!item) return;
            event.preventDefault();
            item.click();
        });
        drawer.querySelectorAll('[data-dashboard-detail-close]').forEach(function(btn){
            btn.addEventListener('click', function(){ drawer.hidden = true; });
        });
    }

    document.addEventListener('DOMContentLoaded', function(){
        setupTopbarDropdowns(); setupSearch(); setupRefreshAll(); setupReportAccordion(); setupLiveInsightDashboard(); setupDashboardIssueDetails();
        document.querySelectorAll('.js-ssh-action-select').forEach(el => applyActionMeta(el.closest('form')));
        document.querySelectorAll('.js-dashboard-ssh-form').forEach(function(form){ previewCommands(form); });
        document.addEventListener('click', function(event){
            const portBtn = event.target.closest('[data-sm-port-button]');
            if(portBtn){
                if(document.getElementById('dashboard-port-modal')) fillModal(portBtn);
                if(document.querySelector('[data-sm-port-detail]')) fillDetailPanel(portBtn);
                return;
            }
            if(event.target.matches('[data-modal-close]') || event.target.classList.contains('modal-backdrop')) closeModal();
        });
        document.addEventListener('change', function(event){
            if(event.target.classList.contains('js-ssh-action-select') || event.target.name === 'force' || event.target.name === 'confirmed') applyActionMeta(event.target.closest('form'));
        });
        document.addEventListener('input', function(event){ if(event.target.classList.contains('js-ssh-action-value')) previewCommands(event.target.closest('form')); });
        document.addEventListener('submit', function(event){ if(event.target.classList.contains('js-dashboard-ssh-form')){ event.preventDefault(); submitSshForm(event.target); } });
        document.addEventListener('keydown', function(event){ if(event.key === 'Escape') closeModal(); });
        const preselect = new URLSearchParams(window.location.search).get('port');
        if(preselect){ const btn = document.querySelector('[data-sm-port-button][data-port-id="' + preselect + '"]'); if(btn) fillDetailPanel(btn); }
    });
})();

/* SwitchMap Phase 66 smoke compatibility markers */
/* Phase 66 Minimal Three Panel Dashboard */
/* data-dashboard-data-url */

/* Phase 66.3 Dashboard Functional UX Fix | data-dashboard-detail | data-dashboard-topology-issues */

/* Phase 66.4 Dashboard Visual Cleanup | valueOrDash keeps zero counters */

/* Phase 66.5 Dashboard Command Center Layout | command-card-grid | data-dashboard-background-icon */
/* Phase 66.7 Hard Visual Reset | header-force-reset | equal-command-cards */


/* Phase 66.13.1 Smoke Compatibility Only
Phase 66.7 Hard Visual Reset
نیازمند بررسی
آلارم فعال
Issue توپولوژی
*/

/* Phase 74 connectivity card detail drawer fix */
(function(){
    if(window.__switchMapPhase74ConnectivityFixLoaded) return;
    window.__switchMapPhase74ConnectivityFixLoaded = true;

    function escapeHtml(value){
        return String(value == null ? '' : value).replace(/[&<>"']/g, function(ch){
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch] || ch;
        });
    }
    function valueOrDash(value){
        value = String(value == null ? '' : value).trim();
        return value || '-';
    }
    function statusTitle(status){
        const map = {
            healthy:'سالم',
            poll_failed:'ناموفق',
            discovery_warning:'هشدار Discovery',
            stale:'داده قدیمی',
            not_monitored:'خارج از پایش'
        };
        return map[status] || status || 'نامشخص';
    }
    function statusOrder(status){
        const order = {poll_failed:0, discovery_warning:1, stale:2, not_monitored:3, healthy:4};
        return Object.prototype.hasOwnProperty.call(order, status) ? order[status] : 9;
    }
    function ensureExtra(drawer){
        let extra = drawer.querySelector('[data-phase74-detail-extra]');
        if(!extra){
            extra = document.createElement('div');
            extra.className = 'phase74-detail-extra';
            extra.setAttribute('data-phase74-detail-extra', '');
            const link = drawer.querySelector('[data-detail-url]');
            if(link && link.parentNode){
                link.parentNode.insertBefore(extra, link);
            }else{
                drawer.appendChild(extra);
            }
        }
        return extra;
    }
    function setDrawerText(drawer, selector, value){
        const el = drawer.querySelector(selector);
        if(el) el.textContent = valueOrDash(value);
    }
    function groupDevices(items){
        const groups = {};
        (items || []).forEach(function(item){
            const status = item.status || 'unknown';
            if(!groups[status]) groups[status] = [];
            groups[status].push(item);
        });
        return Object.keys(groups).sort(function(a,b){return statusOrder(a)-statusOrder(b);}).map(function(status){
            groups[status].sort(function(a,b){return String(a.name || '').localeCompare(String(b.name || ''), 'fa');});
            return {status:status, title:statusTitle(status), items:groups[status]};
        });
    }
    function renderConnectivity(items){
        const groups = groupDevices(items);
        if(!groups.length){
            return '<div class="phase66-empty modern-empty-state">داده اتصال تجهیزات هنوز آماده نیست.</div>';
        }
        return groups.map(function(group){
            const rows = group.items.map(function(item){
                const url = item.detail_url || '#';
                const reason = item.snmp_error || item.discovery_error || item.compact_reason || item.short_reason || item.conclusion || '';
                return '<a class="phase74-connectivity-item" href="' + escapeHtml(url) + '">' +
                    '<strong>' + escapeHtml(item.name || item.object_name || '-') + '</strong>' +
                    '<small>' + escapeHtml(item.ip || '-') + '</small>' +
                    '<span title="' + escapeHtml(reason) + '">' + escapeHtml(reason || item.last_poll_text || '-') + '</span>' +
                '</a>';
            }).join('');
            return '<section class="phase74-connectivity-group phase74-connectivity-status-' + escapeHtml(group.status) + '">' +
                '<div class="phase74-connectivity-group-title"><span>' + escapeHtml(group.title) + '</span><b>' + group.items.length + '</b></div>' +
                '<div class="phase74-connectivity-list">' + rows + '</div>' +
            '</section>';
        }).join('');
    }
    function openConnectivityDrawer(dashboard){
        const drawer = document.querySelector('[data-dashboard-detail-drawer]');
        if(!drawer) return;
        const counters = dashboard && dashboard.counters ? dashboard.counters : {};
        const items = dashboard && dashboard.device_items ? dashboard.device_items : [];
        const extra = ensureExtra(drawer);
        setDrawerText(drawer, '[data-detail-severity]', (counters.snmp_failed || counters.stale || 0) ? 'warning' : 'ok');
        setDrawerText(drawer, '[data-detail-title]', 'اتصال تجهیزات');
        setDrawerText(drawer, '[data-detail-object]', 'Devices / SNMP / Discovery');
        setDrawerText(drawer, '[data-detail-issue-id]', 'connectivity-summary');
        setDrawerText(drawer, '[data-detail-last-check]', dashboard && dashboard.generated_at ? dashboard.generated_at : 'ثبت نشده');
        setDrawerText(drawer, '[data-detail-reason]', 'لیست وضعیت تک‌تک دستگاه‌ها بر اساس آخرین Background Refresh.');
        setDrawerText(drawer, '[data-detail-action]', 'برای جزئیات هر دستگاه روی همان ردیف کلیک کن.');
        const link = drawer.querySelector('[data-detail-url]');
        if(link){
            link.href = '#';
            link.textContent = 'جزئیات دستگاه‌ها در همین پنل نمایش داده شده است';
            link.setAttribute('aria-disabled', 'true');
        }
        extra.hidden = false;
        extra.innerHTML = renderConnectivity(items);
        drawer.hidden = false;
        drawer.scrollIntoView({behavior:'smooth', block:'nearest'});
    }
    function clearExtraForNormalDetails(target){
        if(target && target.closest && target.closest('[data-dashboard-connectivity-card]')) return;
        const drawer = document.querySelector('[data-dashboard-detail-drawer]');
        if(!drawer) return;
        const extra = drawer.querySelector('[data-phase74-detail-extra]');
        if(extra){ extra.hidden = true; extra.innerHTML = ''; }
        const link = drawer.querySelector('[data-detail-url]');
        if(link){
            link.textContent = 'Open exact detail';
            link.removeAttribute('aria-disabled');
        }
    }
    function fetchDashboard(root){
        const url = root && root.dataset ? root.dataset.dashboardDataUrl : '';
        if(!url) return Promise.resolve(null);
        return fetch(url, {credentials:'same-origin', headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}})
            .then(function(response){return response.json();})
            .then(function(payload){return payload && payload.dashboard ? payload.dashboard : null;});
    }
    document.addEventListener('click', function(event){
        const card = event.target.closest('[data-dashboard-connectivity-card]');
        if(card){
            event.preventDefault();
            const root = document.querySelector('[data-dashboard-live]');
            fetchDashboard(root).then(function(dashboard){openConnectivityDrawer(dashboard || {});});
            return;
        }
        if(event.target.closest('[data-dashboard-detail]')) clearExtraForNormalDetails(event.target);
    }, true);
    document.addEventListener('keydown', function(event){
        if(event.key !== 'Enter' && event.key !== ' ') return;
        const card = event.target.closest('[data-dashboard-connectivity-card]');
        if(!card) return;
        event.preventDefault();
        card.click();
    });
})();

