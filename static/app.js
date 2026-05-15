// ── State ──
const findings = {};
let lastUpdate = null;
let selectedKey = null;
let currentDraft = null;
let historicalCount = 0;
let isRunning = true;
let currentPage = 1;
const itemsPerPage = 20;
let totalAgents = 9;
const brainLogs = [];
const findingTimestamps = []; // For 24h sparkline.

// ── Auth ──
const TOKEN_KEY = 'aiCityCouncil.apiToken';
const getApiToken = () => localStorage.getItem(TOKEN_KEY) || '';
const authHeaders = () => {
    const tok = getApiToken();
    return tok ? { Authorization: `Bearer ${tok}` } : {};
};
async function authedFetch(url, opts = {}) {
    const headers = { ...(opts.headers || {}), ...authHeaders() };
    const resp = await fetch(url, { ...opts, headers });
    if (resp.status === 401 || resp.status === 403) {
        const entered = window.prompt('API token required. Paste your API_AUTH_TOKEN:');
        if (entered) {
            localStorage.setItem(TOKEN_KEY, entered.trim());
            return fetch(url, { ...opts, headers: { ...(opts.headers || {}), ...authHeaders() } });
        }
    }
    return resp;
}
function setApiToken() {
    const current = getApiToken();
    const entered = window.prompt('Set API token (leave blank to clear):', current);
    if (entered === null) return;
    if (entered.trim() === '') localStorage.removeItem(TOKEN_KEY);
    else localStorage.setItem(TOKEN_KEY, entered.trim());
}
window.setApiToken = setApiToken;

// ── Helpers ──
const sanitize = (str) => {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
};
const esc = (str) => sanitize(str);
const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
const severityClass = (s) => `sev-${(s || 'low').toLowerCase()}`;
const severityTextClass = (s) => `sev-text-${(s || 'low').toLowerCase()}`;

function timeAgo(ts) {
    if (!ts) return '—';
    const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
    if (diff < 60) return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return `${Math.floor(diff / 86400)}d`;
}
function utcClock() {
    const d = new Date();
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')} ${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')}:${String(d.getUTCSeconds()).padStart(2,'0')} UTC`;
}
function metricFor(f) {
    if (f.raw_counts && typeof f.raw_counts === 'object') {
        const entries = Object.entries(f.raw_counts);
        if (entries.length) {
            const [, v] = entries[0];
            return String(v);
        }
    }
    const km = f.key_metrics || [];
    if (km.length) {
        const m = km[0];
        return `${m.value ?? ''}${m.label ? ` ${m.label}` : ''}`.trim() || '—';
    }
    return '—';
}
const isCollab = (f) => (f.agent_name || '').startsWith('Collaboration:');
const keyFor = (f) => f.issue_title ? `${f.agent_name}:${f.issue_title}` : f.agent_name;

// ── SSE Connection ──
function connectSSE() {
    const evtSource = new EventSource('/api/findings');

    evtSource.onopen = () => updateConnectionState(true);
    evtSource.addEventListener('finding', (e) => {
        const data = JSON.parse(e.data);
        const key = keyFor(data);
        const isNew = !(key in findings);
        findings[key] = data;
        lastUpdate = new Date();
        if (isNew && data.timestamp) findingTimestamps.push(new Date(data.timestamp).getTime());
        renderAll();
    });
    evtSource.addEventListener('brain', (e) => showBrainMessage(JSON.parse(e.data)));
    evtSource.addEventListener('heartbeat', () => {});
    evtSource.onerror = () => updateConnectionState(false);
}

async function startAgents() {
    const btn = document.getElementById('btn-start');
    btn.disabled = true;
    try {
        const resp = await authedFetch('/api/agents/start', { method: 'POST' });
        const data = await resp.json();
        if (data.success || data.message === 'Already running') isRunning = true;
        else alert('Failed to start agents: ' + data.message);
        updateConnectionState(true);
    } catch (err) {
        console.error('Start error:', err);
    } finally {
        btn.disabled = false;
        syncAgentStatus();
    }
}

async function stopAgents() {
    const btn = document.getElementById('btn-stop');
    btn.disabled = true;
    try {
        const resp = await authedFetch('/api/agents/stop', { method: 'POST' });
        const data = await resp.json();
        if (data.success || data.message === 'Not running') isRunning = false;
        else alert('Failed to stop agents: ' + data.message);
        updateConnectionState(true);
    } catch (err) {
        console.error('Stop error:', err);
    } finally {
        btn.disabled = false;
        syncAgentStatus();
    }
}

function updateConnectionState(connected) {
    const dot = document.getElementById('status-dot');
    const label = document.getElementById('status-label');
    if (!connected) {
        dot.style.background = 'var(--sev-critical)';
        dot.style.boxShadow = '0 0 8px var(--sev-critical)';
        dot.style.animation = 'none';
        label.textContent = 'OFFLINE';
        return;
    }
    if (isRunning) {
        dot.style.background = 'var(--accent)';
        dot.style.boxShadow = '0 0 8px var(--accent)';
        dot.style.animation = 'heartbeat 1.6s ease-in-out infinite';
        label.textContent = 'LIVE';
    } else {
        dot.style.background = 'var(--sev-medium)';
        dot.style.boxShadow = '0 0 8px var(--sev-medium)';
        dot.style.animation = 'none';
        label.textContent = 'STANDBY';
    }
    document.getElementById('btn-start').disabled = isRunning;
    document.getElementById('btn-stop').disabled = !isRunning;
}

async function syncAgentStatus() {
    try {
        const resp = await fetch('/api/agents/status');
        const data = await resp.json();
        isRunning = data.is_running;
        historicalCount = data.historical_count || historicalCount;
        const agents = data.agents || {};
        const running = Object.values(agents).filter(a => (a.status || '').includes('RUNNING')).length;
        totalAgents = Object.keys(agents).length || totalAgents;
        document.getElementById('status-agents').textContent = `${running}/${totalAgents}`;
        renderAgentRoster(agents);
        updateConnectionState(true);
    } catch (err) {
        console.error('Status sync error:', err);
    }
}

async function loadHistory() {
    try {
        const resp = await fetch('/api/findings/history?limit=1000');
        const data = await resp.json();
        if (data.history) {
            data.history.forEach(f => {
                const key = keyFor(f);
                findings[key] = f;
                if (f.timestamp) findingTimestamps.push(new Date(f.timestamp).getTime());
            });
            renderAll();
        }
    } catch (err) {
        console.error('History load error:', err);
    }
}

// ── Rendering ──
function renderAll() {
    renderSeverityRibbon();
    renderSparkline();
    renderFindings();
    renderTopBarCounts();
}

function renderTopBarCounts() {
    document.getElementById('status-findings').textContent = Object.keys(findings).filter(k => !k.startsWith('_')).length;
}

function renderSeverityRibbon() {
    const ribbon = document.getElementById('severity-ribbon');
    const values = Object.values(findings).filter(f => !isCollab(f));
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    values.forEach(f => {
        const s = (f.severity || 'low').toLowerCase();
        if (s in counts) counts[s]++;
    });
    const total = Math.max(1, values.length);
    const segments = [
        { key: 'critical', color: 'var(--sev-critical)' },
        { key: 'high', color: 'var(--sev-high)' },
        { key: 'medium', color: 'var(--sev-medium)' },
        { key: 'low', color: 'var(--sev-low)' },
    ];
    ribbon.innerHTML = segments.map(s => `
        <div class="flex items-center gap-2 flex-1 min-w-0">
            <span class="mono text-[11px] uppercase" style="color: ${s.color}; min-width: 56px">${s.key} ${counts[s.key]}</span>
            <div class="flex-1 rounded" style="background: var(--border); height: 4px; overflow: hidden">
                <div class="severity-ribbon-segment" style="background: ${s.color}; width: ${(counts[s.key] / total) * 100}%"></div>
            </div>
        </div>
    `).join('');
}

function renderSparkline() {
    const el = document.getElementById('sparkline');
    const totalEl = document.getElementById('sparkline-total');
    const buckets = new Array(24).fill(0); // last 24 hours, 1h buckets.
    const now = Date.now();
    let total = 0;
    findingTimestamps.forEach(t => {
        const age = (now - t) / 3600000;
        if (age >= 0 && age < 24) {
            buckets[23 - Math.floor(age)]++;
            total++;
        }
    });
    const max = Math.max(1, ...buckets);
    el.innerHTML = buckets.map(v => {
        const h = Math.max(2, Math.round((v / max) * 20));
        return `<span style="height:${h}px"></span>`;
    }).join('');
    totalEl.textContent = `${total} / 24h`;
}

function renderFindings() {
    const container = document.getElementById('findings-rows');
    const all = Object.entries(findings).filter(([k]) => !k.startsWith('_'));
    if (!all.length) return;

    // Sort: collaborations last, then by severity, then by timestamp desc.
    all.sort(([, a], [, b]) => {
        const ca = isCollab(a) ? 1 : 0;
        const cb = isCollab(b) ? 1 : 0;
        if (ca !== cb) return ca - cb;
        const sa = SEVERITY_ORDER[(a.severity || 'low').toLowerCase()] ?? 3;
        const sb = SEVERITY_ORDER[(b.severity || 'low').toLowerCase()] ?? 3;
        if (sa !== sb) return sa - sb;
        return new Date(b.timestamp || 0) - new Date(a.timestamp || 0);
    });

    const totalPages = Math.max(1, Math.ceil(all.length / itemsPerPage));
    if (currentPage > totalPages) currentPage = totalPages;
    const start = (currentPage - 1) * itemsPerPage;
    const page = all.slice(start, start + itemsPerPage);

    container.innerHTML = page.map(([key, f]) => renderRow(key, f)).join('');
    renderPagination(totalPages);
}

function renderRow(key, f) {
    const sev = (f.severity || 'low').toLowerCase();
    const isSel = selectedKey === key;
    const collab = isCollab(f);
    const metric = metricFor(f);
    const sevBars = `<span class="sev-bar ${severityClass(sev)}"><span></span><span></span><span></span></span>`;
    return `
    <div class="row ${collab ? 'row-collab' : ''} ${isSel ? 'is-selected' : ''} row-enter grid grid-cols-[42px_180px_1fr_160px_90px] gap-3 px-3 py-2.5 cursor-pointer items-center"
         data-key="${esc(key)}"
         onclick="openDetailPanel('${esc(key)}')">
        <div>${sevBars}</div>
        <div class="truncate">
            <div class="text-[13px] font-medium" style="color: var(--text)">${sanitize(f.agent_name)}</div>
            <div class="label mt-0.5">${sanitize(f.department || '')}</div>
        </div>
        <div class="truncate">
            <div class="text-[13px]" style="color: var(--text)">${sanitize(f.issue_title || 'Analyzing…')}</div>
            <div class="text-[11px] truncate" style="color: var(--text-3)">${sanitize((f.summary || '').slice(0, 140))}</div>
        </div>
        <div class="hidden md:block mono text-[11px] truncate ${severityTextClass(sev)}">${sanitize(metric)}</div>
        <div class="hidden md:block mono text-[11px] text-right" style="color: var(--text-3)">${timeAgo(f.timestamp)}</div>
    </div>`;
}

function renderPagination(totalPages) {
    const c = document.getElementById('pagination-container');
    if (totalPages <= 1) { c.innerHTML = ''; return; }
    let html = `<button class="btn" onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>‹</button>`;
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
            html += `<button class="btn ${currentPage === i ? 'btn-primary' : ''}" onclick="changePage(${i})">${i}</button>`;
        } else if (i === currentPage - 2 || i === currentPage + 2) {
            html += `<span class="px-1 mono" style="color: var(--text-4)">…</span>`;
        }
    }
    html += `<button class="btn" onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>›</button>`;
    c.innerHTML = html;
}
function changePage(n) {
    currentPage = n;
    renderFindings();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Agent roster ──
function renderAgentRoster(agents) {
    const el = document.getElementById('agent-roster');
    const entries = Object.entries(agents);
    document.getElementById('agent-roster-count').textContent =
        `${entries.filter(([, a]) => (a.status || '').includes('RUNNING')).length}/${entries.length}`;
    if (!entries.length) {
        el.innerHTML = `<div class="text-[11px] py-3 px-1" style="color: var(--text-3)">No agents reported yet.</div>`;
        return;
    }
    el.innerHTML = entries.map(([name, a]) => {
        const status = a.status || '';
        let dot = '<span style="background: var(--text-4)"></span>';
        if (status.includes('RUNNING')) dot = '<span class="live-dot"></span>';
        else if (status.includes('ERROR')) dot = '<span style="background: var(--sev-critical); box-shadow: 0 0 6px var(--sev-critical)"></span>';
        else if (status.includes('STOPPED')) dot = '<span style="background: var(--sev-medium)"></span>';
        else if (status.includes('WAITING')) dot = '<span style="background: var(--sev-medium); opacity: 0.6"></span>';
        return `
        <div class="flex items-center gap-2 px-1.5 py-1.5 rounded" style="color: var(--text-2)">
            <span class="inline-block w-1.5 h-1.5 rounded-full" style="background: var(--text-4)">${dot}</span>
            <span class="text-[12px] flex-1 truncate" style="color: var(--text)">${sanitize(name)}</span>
            <span class="mono text-[10px]" style="color: var(--text-3)">${sanitize((status.replace(/[^A-Z]/g, '') || '—').slice(0, 4))}</span>
        </div>`;
    }).join('');
}

// ── Brain feed (terminal log) ──
function showBrainMessage(data) {
    brainLogs.unshift(data);
    if (brainLogs.length > 80) brainLogs.pop();
    document.getElementById('brain-count').textContent = brainLogs.length;
    const feed = document.getElementById('brain-feed');
    feed.innerHTML = brainLogs.map((log, idx) => {
        const ts = log.timestamp ? new Date(log.timestamp) : new Date();
        const time = `${String(ts.getHours()).padStart(2,'0')}:${String(ts.getMinutes()).padStart(2,'0')}:${String(ts.getSeconds()).padStart(2,'0')}`;
        const flash = idx === 0 ? 'brain-flash' : '';
        return `
        <div class="brain-line ${flash}">
            <span class="ts">${time}</span>
            <span class="agent">${sanitize((log.agent_name || 'SYSTEM').toUpperCase().slice(0, 22))}</span>
            › <span class="msg">${sanitize(log.message || '')}</span>${log.thought ? `<div class="ts pl-12 italic">${sanitize(log.thought)}</div>` : ''}
        </div>`;
    }).join('');
}

// ── Detail side panel ──
function openDetailPanel(key) {
    const f = findings[key];
    if (!f) return;
    selectedKey = key;
    document.querySelectorAll('#findings-rows .row').forEach(r =>
        r.classList.toggle('is-selected', r.dataset.key === key));

    const sev = (f.severity || 'low').toLowerCase();
    document.getElementById('detail-sev-bar').className = `sev-bar ${severityClass(sev)}`;
    document.getElementById('detail-agent').textContent = f.agent_name || '—';
    document.getElementById('detail-dept').textContent = `${f.department || ''} · ${timeAgo(f.timestamp)} ago · ${sev.toUpperCase()}`;

    const metricsHtml = (f.key_metrics || []).map(m => `
        <div class="panel rounded p-2.5">
            <div class="label mb-1">${sanitize(m.label || m.metric || 'Metric')}</div>
            <div class="mono text-sm font-semibold ${severityTextClass(sev)}">${sanitize(m.value)}</div>
        </div>
    `).join('');

    const evidenceHtml = (f.evidence || []).map(e => `
        <li class="text-[12px] pl-3 py-1 border-l mb-1" style="color: var(--text-2); border-color: var(--border-3)">
            ${sanitize(typeof e === 'string' ? e : e.finding || e.description || JSON.stringify(e))}
        </li>
    `).join('');

    const officialsHtml = (f.officials || []).map(o => `
        <div class="panel rounded p-2.5 flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold mono"
                 style="background: var(--bg-3); color: var(--accent-2); border: 1px solid var(--border-2)">
                ${sanitize((o.name || '?').charAt(0))}
            </div>
            <div class="min-w-0 flex-1">
                <div class="text-[13px] font-medium truncate">${sanitize(o.name || '')}</div>
                <div class="label">${sanitize(o.title || '')}</div>
            </div>
            ${o.email ? `<a href="mailto:${sanitize(o.email)}" class="mono text-[10px]" style="color: var(--accent-2)">${sanitize(o.email)}</a>` : ''}
        </div>
    `).join('');

    const newsHtml = (f.news_context || []).map(n => `
        <div class="text-[12px] pl-3 py-1 border-l mb-1" style="color: var(--text-2); border-color: var(--sev-medium)">
            ${sanitize(n)}
        </div>
    `).join('');

    const rawHeadlinesHtml = (f.raw_headlines || []).map(h => `
        <div class="text-[12px] mb-1" style="color: var(--text-3)">› ${sanitize(h)}</div>
    `).join('');

    const trendingHtml = (f.trending_topics || []).map(t =>
        `<span class="mono text-[11px] px-2 py-0.5 rounded" style="background: var(--bg-3); color: var(--accent-2); border: 1px solid var(--border-2)">#${sanitize(t)}</span>`
    ).join('');

    const neighborhoodsHtml = (f.affected_neighborhoods || []).map(n =>
        `<span class="mono text-[11px] px-2 py-0.5 rounded" style="background: var(--bg-3); color: var(--text-2); border: 1px solid var(--border-2)">${sanitize(n)}</span>`
    ).join('');

    const updatesHtml = (f.status_updates || []).slice().reverse().map(u => `
        <div class="pl-3 py-1.5 mb-1.5 border-l" style="border-color: var(--accent)">
            <div class="mono text-[10px]" style="color: var(--text-4)">${timeAgo(u.timestamp)} ago</div>
            <div class="text-[12px]" style="color: var(--text-2)">${sanitize(u.note)}</div>
        </div>
    `).join('');

    const traitsHtml = (f.traits || []).map(t =>
        `<span class="mono text-[10px] px-2 py-0.5 rounded" style="background: var(--bg-3); color: var(--text-2); border: 1px solid var(--border-2)">${sanitize(t)}</span>`
    ).join('');

    document.getElementById('detail-content').innerHTML = `
        <div class="panel rounded p-3 mb-4">
            <div class="text-[14px] font-semibold mb-1">${sanitize(f.issue_title || 'Analysis in progress')}</div>
            <p class="text-[12px]" style="color: var(--text-2)">${sanitize(f.summary || '')}</p>
        </div>

        ${updatesHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Timeline (${(f.status_updates || []).length})</div>
            <div>${updatesHtml}</div>
        </section>` : ''}

        ${metricsHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Key Metrics</div>
            <div class="grid grid-cols-2 gap-2">${metricsHtml}</div>
        </section>` : ''}

        ${f.solution ? `
        <section class="mb-4">
            <div class="label mb-2">Recommendation</div>
            <div class="panel rounded p-3 text-[12px]" style="border-color: var(--accent); color: var(--text)">
                ${sanitize(f.solution)}
            </div>
        </section>` : ''}

        ${evidenceHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Evidence</div>
            <ul>${evidenceHtml}</ul>
        </section>` : ''}

        ${trendingHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Trending</div>
            <div class="flex flex-wrap gap-1">${trendingHtml}</div>
        </section>` : ''}

        ${neighborhoodsHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Affected Areas</div>
            <div class="flex flex-wrap gap-1">${neighborhoodsHtml}</div>
        </section>` : ''}

        ${newsHtml ? `
        <section class="mb-4">
            <div class="label mb-2">News Context</div>
            <div>${newsHtml}</div>
        </section>` : ''}

        ${rawHeadlinesHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Source Headlines</div>
            <div class="panel rounded p-3 max-h-48 overflow-y-auto">${rawHeadlinesHtml}</div>
        </section>` : ''}

        ${f.recalled_memories && f.recalled_memories.length ? `
        <section class="mb-4">
            <div class="label mb-2">Recalled Memory</div>
            <div class="panel rounded p-3 space-y-1">
                ${f.recalled_memories.map(m => `<div class="text-[11px] italic" style="color: var(--text-3)">"${sanitize(m)}"</div>`).join('')}
            </div>
        </section>` : ''}

        ${f.verified_context ? `
        <section class="mb-4">
            <div class="label mb-2">World Verification · You.com</div>
            <div class="panel rounded p-3 text-[11px]" style="color: var(--text-2); border-color: var(--sev-low)">
                ${sanitize(f.verified_context)}
            </div>
        </section>` : ''}

        ${traitsHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Agent Traits</div>
            <div class="flex flex-wrap gap-1">${traitsHtml}</div>
        </section>` : ''}

        ${officialsHtml ? `
        <section class="mb-4">
            <div class="label mb-2">Contact Officials</div>
            <div class="space-y-2">${officialsHtml}</div>
        </section>` : ''}

        ${!isCollab(f) ? `
        <div class="sticky bottom-0 panel border-t hairline -mx-4 px-4 py-3 flex gap-2" style="background: var(--bg-2)">
            <button class="btn btn-primary flex-1" onclick="openEmailModal('${esc(key)}')">Draft email (e)</button>
            <button class="btn" onclick="copyToClipboard()">Copy</button>
            <button class="btn" onclick="shareFinding('${esc(key)}')">Link</button>
        </div>` : ''}
    `;

    document.getElementById('detail-panel').classList.add('is-open');
    document.getElementById('detail-backdrop').classList.add('is-open');
}

function closeDetailPanel() {
    document.getElementById('detail-panel').classList.remove('is-open');
    document.getElementById('detail-backdrop').classList.remove('is-open');
}

function shareFinding(key) {
    const url = new URL(window.location.href);
    url.searchParams.set('issue', key);
    navigator.clipboard.writeText(url.toString());
}

function copyToClipboard() {
    if (!selectedKey || !findings[selectedKey]) return;
    const f = findings[selectedKey];
    const text = `${f.agent_name} — ${f.issue_title}
Severity: ${f.severity}

${f.summary}

Recommendation: ${f.solution || 'N/A'}

Key Metrics:
${(f.key_metrics || []).map(m => `- ${m.label || m.metric}: ${m.value}`).join('\n')}`.trim();
    navigator.clipboard.writeText(text);
}

// ── Email modal ──
function openEmailModal(key) {
    const f = findings[key];
    if (!f) return;
    document.getElementById('email-agent-name').value = key;
    document.getElementById('email-result').classList.add('hidden');
    document.getElementById('email-outcome').value = f.solution ? f.solution.slice(0, 200) : '';
    document.getElementById('email-modal').classList.add('is-open');
}
function closeModal() {
    document.getElementById('email-modal').classList.remove('is-open');
}
window.closeModal = closeModal;
window.openEmailModal = openEmailModal;

document.getElementById('email-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.textContent = 'Generating…';
    btn.disabled = true;
    try {
        const resp = await authedFetch('/api/email/draft', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_name: document.getElementById('email-agent-name').value,
                citizen_name: document.getElementById('email-citizen').value,
                desired_outcome: document.getElementById('email-outcome').value,
                include_admin: document.getElementById('email-to-admin').checked,
            }),
        });
        const result = await resp.json();
        if (result.error && !result.email_draft) throw new Error(result.error);
        const data = result.email_draft;
        currentDraft = data;
        document.getElementById('email-result-to').textContent = `TO: ${(data.to || []).join(', ')}`;
        document.getElementById('email-result-subject').textContent = data.subject;
        document.getElementById('email-result-body').textContent = data.body;
        document.getElementById('email-result').classList.remove('hidden');
    } catch (err) {
        alert('Error generating email: ' + err.message);
    } finally {
        btn.textContent = 'Generate draft';
        btn.disabled = false;
    }
});

document.getElementById('btn-send-email').addEventListener('click', async (e) => {
    if (!currentDraft) return;
    const btn = e.target.closest('button');
    btn.textContent = 'Sending…';
    btn.disabled = true;
    try {
        const recipients = (currentDraft.to || []).join(', ');
        const resp = await authedFetch('/api/email/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                recipient_email: recipients,
                subject: currentDraft.subject,
                body: currentDraft.body,
            }),
        });
        const result = await resp.json();
        if (result.success) {
            btn.textContent = 'Sent ✓';
            setTimeout(() => closeModal(), 1500);
        } else {
            throw new Error(result.error || 'Failed to send');
        }
    } catch (err) {
        alert('Send error: ' + err.message);
        btn.textContent = 'Send via Composio';
        btn.disabled = false;
    }
});

// ── Help modal ──
function showHelp() { document.getElementById('help-modal').classList.add('is-open'); }
function closeHelp() { document.getElementById('help-modal').classList.remove('is-open'); }
window.showHelp = showHelp;
window.closeHelp = closeHelp;

// ── Keyboard shortcuts ──
function getVisibleKeys() {
    return Array.from(document.querySelectorAll('#findings-rows .row')).map(r => r.dataset.key);
}
function moveSelection(delta) {
    const keys = getVisibleKeys();
    if (!keys.length) return;
    let idx = keys.indexOf(selectedKey);
    idx = idx === -1 ? 0 : Math.max(0, Math.min(keys.length - 1, idx + delta));
    selectedKey = keys[idx];
    document.querySelectorAll('#findings-rows .row').forEach(r =>
        r.classList.toggle('is-selected', r.dataset.key === selectedKey));
    const el = document.querySelector(`#findings-rows .row[data-key="${CSS.escape(selectedKey)}"]`);
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

document.addEventListener('keydown', (e) => {
    const inField = ['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName);
    if (inField) return;

    if (e.key === 'Escape') {
        closeModal();
        closeHelp();
        closeDetailPanel();
        return;
    }
    if (e.key === '?') { e.preventDefault(); showHelp(); return; }
    if (e.key === 'j') { e.preventDefault(); moveSelection(1); return; }
    if (e.key === 'k') { e.preventDefault(); moveSelection(-1); return; }
    if (e.key === 'Enter' || e.key === 'o') { if (selectedKey) openDetailPanel(selectedKey); return; }
    if (e.key === 'e') { if (selectedKey) openEmailModal(selectedKey); return; }
    if (e.key === 'r') { e.preventDefault(); loadHistory(); return; }
    if (e.key === 't') { e.preventDefault(); setApiToken(); return; }
    if (e.key === 's' && !e.shiftKey) { e.preventDefault(); startAgents(); return; }
    if (e.key === 'S' && e.shiftKey) { e.preventDefault(); stopAgents(); return; }
});

// ── Init ──
function tickClock() {
    document.getElementById('status-clock').textContent = utcClock();
}
tickClock();
setInterval(tickClock, 1000);

connectSSE();
loadHistory();
syncAgentStatus();
setInterval(syncAgentStatus, 15000);
setInterval(() => { renderSparkline(); renderFindings(); }, 30000);
