(function(){
    function valueOrDash(value){ return value && String(value).trim() ? String(value).trim() : '-'; }
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
                setResult(form,true,'عملیات موفق بود.');
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
    function setupSearch(){
        const input = document.querySelector('[data-switch-search]');
        const triggerButtons = document.querySelectorAll('[data-search-trigger]');
        const cards = Array.from(document.querySelectorAll('[data-switch-card]'));
        const browser = document.querySelector('.device-browser-shell');
        const grid = document.querySelector('.compact-device-grid');
        const panel = document.querySelector('.modern-search-panel');
        if(!input && !triggerButtons.length) return;

        let state = panel ? panel.querySelector('[data-search-result-state]') : null;
        if(panel && !state){
            state = document.createElement('div');
            state.className = 'search-result-state';
            state.setAttribute('data-search-result-state','');
            panel.appendChild(state);
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

        const normalize = function(value){
            return String(value || '').toLowerCase().replace(/\s+/g,' ').trim();
        };
        const run = function(){
            const q = normalize(input ? input.value : '');
            const terms = q ? q.split(' ').filter(Boolean) : [];
            let matched = 0;

            cards.forEach(function(card){
                const haystack = normalize(card.getAttribute('data-search') || card.textContent || '');
                const ok = !terms.length || terms.every(function(term){ return haystack.includes(term); });
                card.hidden = !ok;
                card.style.display = ok ? '' : 'none';
                if(ok) matched += 1;
            });

            if(browser){
                if(terms.length){
                    browser.open = true;
                    browser.classList.add('search-active');
                }else{
                    browser.classList.remove('search-active');
                }
            }
            if(empty) empty.hidden = !terms.length || matched > 0;
            if(state){
                state.textContent = terms.length ? ('نتیجه جستجو: ' + matched + ' دستگاه') : '';
            }
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
        run();
    }
    document.addEventListener('DOMContentLoaded', function(){
        setupSearch(); setupRefreshAll(); setupReportAccordion();
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
