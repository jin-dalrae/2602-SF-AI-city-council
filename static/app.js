// ── State ──
const findings = {};
let lastUpdate = null;
let selectedFinding = null;
let isRunning = true;

// ── Icons ──
const ICONS = {
    shield: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>`,
    wrench: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>`,
    'dollar-sign': `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`,
    building: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>`,
    bus: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h8m-8 4h8m-4 4v4m-4-4h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>`,
    link: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>`,
    '📰': `<span class="text-lg">📰</span>`,
};

const SEVERITY_COLORS = {
    critical: { bg: 'bg-red-500/10', text: 'text-red-400', badge: 'bg-red-500', border: 'border-red-500' },
    urgent: { bg: 'bg-red-500/10', text: 'text-red-400', badge: 'bg-red-500', border: 'border-red-500' },
    high: { bg: 'bg-orange-500/10', text: 'text-orange-400', badge: 'bg-orange-500', border: 'border-orange-500' },
    moderate: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', badge: 'bg-yellow-500', border: 'border-yellow-500' },
    medium: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', badge: 'bg-yellow-500', border: 'border-yellow-500' },
    low: { bg: 'bg-green-500/10', text: 'text-green-400', badge: 'bg-green-500', border: 'border-green-500' },
    improving: { bg: 'bg-blue-500/10', text: 'text-blue-400', badge: 'bg-blue-500', border: 'border-blue-500' },
};

// ── SSE Connection ──
function connectSSE() {
    const evtSource = new EventSource('/api/findings');
    const statusEl = document.getElementById('connection-status');

    evtSource.onopen = () => {
        updateUIState(true);
    };

    evtSource.addEventListener('finding', (e) => {
        const data = JSON.parse(e.data);
        findings[data.agent_name] = data;
        lastUpdate = new Date();
        renderAll();
    });

    evtSource.addEventListener('brain', (e) => {
        const data = JSON.parse(e.data);
        showBrainMessage(data);
    });

    evtSource.addEventListener('heartbeat', () => { });

    evtSource.onerror = () => {
        statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-red-500 pulse-dot"></span> Offline`;
    };
}

async function startAgents() {
    const btn = document.getElementById('btn-start');
    btn.disabled = true;
    try {
        const resp = await fetch('/api/agents/start', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            isRunning = true;
            updateUIState();
        }
    } catch (err) {
        console.error('Start error:', err);
    } finally {
        btn.disabled = false;
    }
}

async function stopAgents() {
    const btn = document.getElementById('btn-stop');
    btn.disabled = true;
    try {
        const resp = await fetch('/api/agents/stop', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            isRunning = false;
            updateUIState();
        }
    } catch (err) {
        console.error('Stop error:', err);
    } finally {
        btn.disabled = false;
    }
}

function updateUIState(connected = true) {
    const statusEl = document.getElementById('connection-status');
    const startBtn = document.getElementById('btn-start');
    const stopBtn = document.getElementById('btn-stop');

    if (!connected) {
        statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-red-500"></span> Disconnected`;
        return;
    }

    if (isRunning) {
        statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-green-500 pulse-dot"></span> Live Monitoring`;
        startBtn.classList.add('opacity-30', 'cursor-not-allowed');
        stopBtn.classList.remove('opacity-30', 'cursor-not-allowed');
    } else {
        statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-yellow-500"></span> Standby`;
        stopBtn.classList.add('opacity-30', 'cursor-not-allowed');
        startBtn.classList.remove('opacity-30', 'cursor-not-allowed');
    }
}

async function syncAgentStatus() {
    try {
        const resp = await fetch('/api/agents/status');
        const data = await resp.json();
        const prev = isRunning;
        isRunning = data.is_running;
        if (prev !== isRunning) updateUIState();
    } catch (err) {
        console.error('Status sync error:', err);
    }
}

// ── Rendering ──
function renderAll() {
    renderStatsBar();
    renderCards();
    updateTimestamp();
}

function renderStatsBar() {
    const bar = document.getElementById('stats-bar');
    const agentFindings = Object.values(findings).filter(f => !f.agent_name.startsWith('Collaboration:'));
    const stats = [
        { label: 'Active Agents', value: agentFindings.length, color: 'text-indigo-400' },
        { label: 'Urgent Issues', value: agentFindings.filter(f => f.severity === 'critical' || f.severity === 'urgent').length, color: 'text-red-400' },
        { label: 'Moderate Issues', value: agentFindings.filter(f => f.severity === 'high' || f.severity === 'moderate' || f.severity === 'medium').length, color: 'text-orange-400' },
        { label: 'Collaborations', value: Object.keys(findings).filter(k => k.startsWith('Collaboration:')).length, color: 'text-purple-400' },
        { label: 'Data Points', value: agentFindings.reduce((sum, f) => sum + (f.key_metrics?.length || 0), 0), color: 'text-cyan-400' },
    ];

    bar.innerHTML = stats.map(s => `
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center hover:border-indigo-500 hover:bg-gray-800/50 transition cursor-pointer group"
             onclick="showStatsModal('${s.label}')">
            <div class="text-2xl font-bold ${s.color} group-hover:scale-110 transition-transform">${s.value}</div>
            <div class="text-xs text-gray-500 group-hover:text-gray-300 transition">${s.label}</div>
        </div>
    `).join('');
}

function renderCards() {
    const grid = document.getElementById('findings-grid');
    const entries = Object.values(findings);

    if (entries.length === 0) return;

    // Sort: collaborations last, then by severity
    const severityOrder = { critical: 0, urgent: 0, high: 1, moderate: 2, medium: 2, low: 3, improving: 4 };
    entries.sort((a, b) => {
        const aCollab = a.agent_name.startsWith('Collaboration:') ? 1 : 0;
        const bCollab = b.agent_name.startsWith('Collaboration:') ? 1 : 0;
        if (aCollab !== bCollab) return aCollab - bCollab;
        return (severityOrder[a.severity] || 3) - (severityOrder[b.severity] || 3);
    });

    grid.innerHTML = entries.map(f => renderCard(f)).join('');
}

let brainLogs = [];

function showBrainMessage(data) {
    const feed = document.getElementById('brain-feed');
    const countEl = document.getElementById('brain-count');

    brainLogs.unshift(data);
    if (brainLogs.length > 50) brainLogs.pop();

    countEl.textContent = brainLogs.length;

    const html = brainLogs.map((log, idx) => `
        <div class="${idx === 0 ? 'brain-flash' : ''} bg-gray-800/40 border border-gray-700/50 rounded-lg p-3 card-enter">
            <div class="flex items-center gap-2 mb-1">
                <span class="text-lg">${log.icon || '🤖'}</span>
                <span class="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">${log.agent_name}</span>
                <span class="text-[10px] text-gray-500 ml-auto">${new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <p class="text-xs text-gray-200 font-medium leading-relaxed">${log.message}</p>
            ${log.thought ? `<p class="text-[10px] text-gray-500 mt-1 italic border-l border-gray-700 pl-2">"${log.thought}"</p>` : ''}
        </div>
    `).join('');

    feed.innerHTML = html;
}

function renderCard(f) {
    const isCollab = f.agent_name.startsWith('Collaboration:');
    const sev = SEVERITY_COLORS[f.severity] || SEVERITY_COLORS.low;
    const icon = ICONS[f.icon] || `<span class="text-lg">${f.icon || '📊'}</span>`;
    const cardId = f.agent_name.replace(/[^a-zA-Z0-9]/g, '_');

    const traitsHtml = (f.traits || []).map(t =>
        `<span class="text-[10px] bg-indigo-900/40 text-indigo-300 border border-indigo-800/50 rounded-full px-2 py-0.5">${t}</span>`
    ).join('');

    const metricsHtml = (f.key_metrics || []).slice(0, 4).map(m =>
        `<div class="bg-gray-800/50 rounded px-2 py-1.5 hover:bg-gray-800 transition">
            <div class="text-xs text-gray-500">${m.label || m.metric || 'Metric'}</div>
            <div class="text-sm font-medium">${m.value}</div>
        </div>`
    ).join('');

    const officialsHtml = (f.officials || []).length > 0
        ? `<div class="mt-2">
            <p class="text-xs font-medium text-gray-400 mb-1">Contact Officials:</p>
            ${f.officials.slice(0, 2).map(o => `
                <div class="text-xs text-gray-500 mb-1">
                    <span class="text-indigo-400">${o.name}</span> - ${o.title}
                    ${o.email ? `<br><a href="mailto:${o.email}" class="text-blue-400 hover:underline">${o.email}</a>` : ''}
                </div>
            `).join('')}
           </div>`
        : '';

    const evidenceHtml = (f.evidence || []).slice(0, 3).map(e =>
        `<li class="text-xs text-gray-400">${typeof e === 'string' ? e : e.finding || e.description || JSON.stringify(e)}</li>`
    ).join('');

    const newsHtml = (f.news_context || []).length > 0
        ? `<div class="mt-3 border-t border-gray-700 pt-2">
            <p class="text-xs font-medium text-indigo-400 mb-1">📰 Related News (${f.news_context.length}):</p>
            ${f.news_context.slice(0, 3).map(n => `<p class="text-xs text-gray-400 mb-1">• ${n.substring(0, 120)}${n.length > 120 ? '...' : ''}</p>`).join('')}
           </div>`
        : '';

    const trendingHtml = (f.trending_topics || []).length > 0
        ? `<div class="flex flex-wrap gap-1 mt-2">
            ${f.trending_topics.map(t => `<span class="text-xs bg-indigo-900/50 text-indigo-300 rounded px-2 py-0.5">#${t}</span>`).join('')}
           </div>`
        : '';

    const neighborhoodsHtml = (f.affected_neighborhoods || []).length > 0
        ? `<div class="flex flex-wrap gap-1 mt-2">
            <span class="text-xs text-gray-500">Areas: </span>
            ${f.affected_neighborhoods.map(n => `<span class="text-xs bg-gray-800 text-gray-400 rounded px-1.5 py-0.5">${n}</span>`).join('')}
           </div>`
        : '';

    return `
    <div class="card-enter ${isCollab ? 'collaboration-card' : 'bg-gray-900'} border ${sev.border || 'border-gray-800'} rounded-xl overflow-hidden hover:shadow-lg hover:shadow-${sev.badge?.replace('bg-', '')}/10 transition-all duration-300 cursor-pointer group"
         onclick="openDetailModal('${f.agent_name.replace(/'/g, "\\'")}')">
        <div class="p-4">
            <!-- Header -->
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-2">
                    <div class="w-9 h-9 ${sev.bg} ${sev.text} rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform">${icon}</div>
                    <div>
                        <h3 class="text-sm font-bold group-hover:text-indigo-400 transition">${f.agent_name}</h3>
                        <p class="text-xs text-gray-500">${f.department}</p>
                    </div>
                </div>
                <span class="text-xs ${sev.badge} rounded-full px-2 py-0.5 font-medium text-white uppercase animate-pulse">${f.severity}</span>
            </div>

            <!-- Traits -->
            ${traitsHtml ? `<div class="flex flex-wrap gap-1 mb-3">${traitsHtml}</div>` : ''}

            <!-- Issue Title -->
            <h4 class="font-semibold text-sm mb-2 group-hover:text-white transition">${f.issue_title || 'Analyzing...'}</h4>

            <!-- Summary -->
            <p class="text-xs text-gray-400 mb-3 line-clamp-2">${f.summary || ''}</p>

            <!-- Metrics -->
            ${metricsHtml ? `<div class="grid grid-cols-2 gap-1.5 mb-3">${metricsHtml}</div>` : ''}

            <!-- Trending Topics (for news agent) -->
            ${trendingHtml}

            <!-- Footer -->
            <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-800">
                <span class="text-xs text-gray-600">${timeAgo(f.timestamp)}</span>
                <div class="flex gap-2">
                    <button class="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded px-3 py-1.5 transition" onclick="event.stopPropagation(); shareFinding('${f.agent_name.replace(/'/g, "\\'")}')">
                        Share Finding
                    </button>
                    <button class="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded px-3 py-1.5 transition" onclick="event.stopPropagation(); openDetailModal('${f.agent_name.replace(/'/g, "\\'")}')">
                        View Details
                    </button>
                    ${!isCollab ? `<button onclick="event.stopPropagation(); openEmailModal('${f.agent_name.replace(/'/g, "\\'")}')" class="text-xs bg-indigo-600 hover:bg-indigo-500 rounded px-3 py-1.5 transition font-medium">Share Report</button>` : ''}
                </div>
            </div>
        </div>
    </div>`;
}

function timeAgo(ts) {
    if (!ts) return '';
    const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
}

function updateTimestamp() {
    const el = document.getElementById('last-updated');
    if (lastUpdate) {
        el.textContent = `Updated ${timeAgo(lastUpdate.toISOString())}`;
    }
}

// ── Detail Modal ──
function openDetailModal(agentName) {
    const f = findings[agentName];
    if (!f) return;

    selectedFinding = f;
    const modal = document.getElementById('detail-modal');
    const sev = SEVERITY_COLORS[f.severity] || SEVERITY_COLORS.low;
    const icon = ICONS[f.icon] || `<span class="text-2xl">${f.icon || '📊'}</span>`;

    // Build detailed content
    const metricsHtml = (f.key_metrics || []).map(m =>
        `<div class="bg-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">${m.label || m.metric || 'Metric'}</div>
            <div class="text-lg font-bold ${sev.text}">${m.value}</div>
        </div>`
    ).join('');

    const evidenceHtml = (f.evidence || []).map(e =>
        `<li class="text-sm text-gray-300 mb-2 pl-2 border-l-2 border-indigo-500">
            ${typeof e === 'string' ? e : e.finding || e.description || JSON.stringify(e)}
        </li>`
    ).join('');

    const officialsHtml = (f.officials || []).map(o => `
        <div class="bg-gray-800 rounded-lg p-3 flex items-start gap-3">
            <div class="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center text-white font-bold">
                ${o.name.charAt(0)}
            </div>
            <div>
                <div class="font-medium text-white">${o.name}</div>
                <div class="text-xs text-gray-400">${o.title}${o.department ? ` • ${o.department}` : ''}</div>
                ${o.email ? `<a href="mailto:${o.email}" class="text-xs text-indigo-400 hover:underline">${o.email}</a>` : ''}
            </div>
        </div>
    `).join('');

    const newsHtml = (f.news_context || []).map(n => `
        <div class="text-sm text-gray-300 mb-2 pl-3 border-l-2 border-yellow-500">
            ${n}
        </div>
    `).join('');

    const rawHeadlinesHtml = (f.raw_headlines || []).map(h => `
        <div class="text-sm text-gray-400 mb-1">• ${h}</div>
    `).join('');

    const neighborhoodsHtml = (f.affected_neighborhoods || []).map(n =>
        `<span class="text-sm bg-gray-800 text-gray-300 rounded-lg px-3 py-1">${n}</span>`
    ).join('');

    const trendingHtml = (f.trending_topics || []).map(t =>
        `<span class="text-sm bg-indigo-900/50 text-indigo-300 rounded-lg px-3 py-1">#${t}</span>`
    ).join('');

    document.getElementById('detail-content').innerHTML = `
        <!-- Header -->
        <div class="flex items-start justify-between mb-6">
            <div class="flex items-center gap-4">
                <div class="w-14 h-14 ${sev.bg} ${sev.text} rounded-xl flex items-center justify-center text-2xl">${icon}</div>
                <div>
                    <h2 class="text-xl font-bold">${f.agent_name}</h2>
                    <p class="text-sm text-gray-400">${f.department} • ${timeAgo(f.timestamp)}</p>
                </div>
            </div>
            <span class="text-sm ${sev.badge} rounded-full px-3 py-1 font-medium text-white uppercase">${f.severity}</span>
        </div>
        
        <!-- Issue Title -->
        <div class="bg-gray-800/50 rounded-xl p-4 mb-6">
            <h3 class="text-lg font-bold mb-2">${f.issue_title || 'Analysis in Progress'}</h3>
            <p class="text-gray-300">${f.summary || 'Gathering data...'}</p>
        </div>
        
        <!-- Metrics Grid -->
        ${metricsHtml ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">Key Metrics</h4>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">${metricsHtml}</div>
        </div>` : ''}
        
        <!-- Trending Topics -->
        ${trendingHtml ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">Trending Topics</h4>
            <div class="flex flex-wrap gap-2">${trendingHtml}</div>
        </div>` : ''}
        
        <!-- Recommendation -->
        ${f.solution ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">💡 Recommendation</h4>
            <div class="bg-indigo-900/20 border border-indigo-800 rounded-xl p-4">
                <p class="text-gray-300">${f.solution}</p>
            </div>
        </div>` : ''}
        
        <!-- Evidence -->
        ${evidenceHtml ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">📋 Evidence & Data</h4>
            <ul class="space-y-1">${evidenceHtml}</ul>
        </div>` : ''}

        <!-- Recalled Memories (Continual Learning) -->
        ${f.recalled_memories && f.recalled_memories.length > 0 ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-indigo-400 uppercase mb-3 text-xs flex items-center gap-2">
                <span>🧠 Recalled Episodic Memory</span>
                <span class="text-[10px] bg-indigo-900 px-1.5 py-0.5 rounded-full">Continual Learning</span>
            </h4>
            <div class="bg-indigo-900/10 border border-indigo-800/30 rounded-xl p-3 space-y-2">
                ${f.recalled_memories.map(m => `<p class="text-xs text-gray-400 italic">"Matches past pattern: ${m}"</p>`).join('')}
            </div>
        </div>` : ''}

        <!-- World Verification (You.com) -->
        ${f.verified_context ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-green-400 uppercase mb-3 text-xs flex items-center gap-2">
                <span>🌐 World Verification</span>
                <span class="text-[10px] bg-green-900/50 text-green-300 px-1.5 py-0.5 rounded-full">via You.com</span>
            </h4>
            <div class="bg-green-900/5 border border-green-800/30 rounded-xl p-3">
                <p class="text-xs text-gray-400 line-clamp-3">${f.verified_context}</p>
            </div>
        </div>` : ''}
        
        <!-- News Context -->
        ${newsHtml ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">📰 Related News</h4>
            <div class="space-y-2">${newsHtml}</div>
        </div>` : ''}
        
        <!-- Raw Headlines (for news agent) -->
        ${rawHeadlinesHtml ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">🗞️ Source Headlines</h4>
            <div class="bg-gray-800/50 rounded-xl p-4 max-h-48 overflow-y-auto">${rawHeadlinesHtml}</div>
        </div>` : ''}
        
        <!-- Affected Neighborhoods -->
        ${neighborhoodsHtml ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">📍 Affected Areas</h4>
            <div class="flex flex-wrap gap-2">${neighborhoodsHtml}</div>
        </div>` : ''}
        
        <!-- Officials -->
        ${officialsHtml ? `
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-400 uppercase mb-3">👤 Contact Officials</h4>
            <div class="grid gap-3">${officialsHtml}</div>
        </div>` : ''}
        
        <!-- Actions -->
        <div class="flex gap-3 pt-4 border-t border-gray-800">
            <button onclick="closeDetailModal(); openEmailModal('${f.agent_name.replace(/'/g, "\\'")}')" 
                    class="flex-1 bg-indigo-600 hover:bg-indigo-500 rounded-xl py-3 font-medium transition">
                ✉️ Draft Email to Officials
            </button>
            <button onclick="copyToClipboard()" 
                    class="bg-gray-800 hover:bg-gray-700 rounded-xl px-4 py-3 transition" title="Copy to clipboard">
                📋
            </button>
        </div>
    `;

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';
}

function closeDetailModal() {
    const modal = document.getElementById('detail-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.body.style.overflow = '';
    selectedFinding = null;
}

function shareFinding(agentName) {
    const f = findings[agentName];
    if (!f) return;
    const url = new URL(window.location.href);
    url.searchParams.set('agent', agentName);
    const shareUrl = url.toString();

    navigator.clipboard.writeText(shareUrl).then(() => {
        const btn = event.target;
        const originalText = btn.textContent;
        btn.textContent = 'Copied Link!';
        setTimeout(() => btn.textContent = originalText, 2000);
    });
}

function copyToClipboard() {
    if (!selectedFinding) return;
    const f = selectedFinding;
    const url = new URL(window.location.href);
    url.searchParams.set('agent', f.agent_name);

    const text = `
${f.agent_name} - ${f.issue_title}
Severity: ${f.severity}
Link: ${url.toString()}

${f.summary}

Recommendation: ${f.solution || 'N/A'}

Key Metrics:
${(f.key_metrics || []).map(m => `- ${m.label || m.metric}: ${m.value}`).join('\n')}
    `.trim();

    navigator.clipboard.writeText(text).then(() => {
        alert('Copied full discovery to clipboard!');
    });
}

// ── Stats Modal ──
async function showStatsModal(label) {
    const modal = document.getElementById('detail-modal');
    const content = document.getElementById('detail-content');
    let html = '';

    if (label === 'Active Agents') {
        try {
            const resp = await fetch('/api/agents/status');
            const data = await resp.json();
            const agents = data.agents || {};

            html = `
                <div class="mb-6">
                    <h2 class="text-xl font-bold flex items-center gap-2">
                        <span class="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-sm text-white font-bold">🤖</span>
                        Active Agent Status
                    </h2>
                    <p class="text-xs text-gray-500 mt-1">Real-time status of all marathon-mode agents</p>
                </div>
                <div class="space-y-3">
                    ${Object.entries(agents).map(([name, status]) => `
                        <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-800">
                            <div class="flex items-center justify-between mb-2">
                                <span class="font-bold text-white">${name}</span>
                                <span class="text-xs px-2 py-1 rounded-full font-medium ${status.status.includes('RUNNING') ? 'bg-green-500/10 text-green-400' :
                    status.status.includes('ERROR') ? 'bg-red-500/10 text-red-400' : 'bg-gray-700 text-gray-400'
                }">${status.status}</span>
                            </div>
                            <p class="text-xs text-gray-400">${status.details || 'Operational'}</p>
                            <p class="text-[10px] text-gray-600 mt-2">Last loop: ${timeAgo(status.updated_at)}</p>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch (err) {
            html = `<p class="text-red-400 p-4">Error loading agent status: ${err.message}</p>`;
        }
    } else if (label === 'Urgent Issues' || label === 'Moderate Issues') {
        const isUrgent = label === 'Urgent Issues';
        const filtered = Object.values(findings).filter(f => {
            if (f.agent_name.startsWith('Collaboration:') || f.department === 'News & Media') return false;
            return isUrgent ? (f.severity === 'critical' || f.severity === 'urgent') :
                (f.severity === 'high' || f.severity === 'moderate' || f.severity === 'medium');
        });

        html = `
            <div class="mb-6">
                <h2 class="text-xl font-bold flex items-center gap-2">
                    <span class="w-8 h-8 ${isUrgent ? 'bg-red-600' : 'bg-orange-600'} rounded-lg flex items-center justify-center text-sm text-white font-bold">⚠️</span>
                    ${label}
                </h2>
                <p class="text-xs text-gray-500 mt-1">Aggregated detections across all departments</p>
            </div>
            <div class="space-y-3">
                ${filtered.length ? filtered.map(f => `
                    <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-800 cursor-pointer hover:border-gray-600 group transition" onclick="openDetailModal('${f.agent_name.replace(/'/g, "\\'")}')">
                        <div class="flex items-center justify-between mb-1">
                            <span class="text-xs font-bold text-indigo-400 uppercase">${f.agent_name}</span>
                            <span class="text-[10px] text-gray-600">${timeAgo(f.timestamp)}</span>
                        </div>
                        <h3 class="text-sm font-semibold text-white mb-1 group-hover:text-indigo-400 transition">${f.issue_title}</h3>
                        <p class="text-xs text-gray-400 line-clamp-2">${f.summary}</p>
                    </div>
                `).join('') : '<p class="text-gray-500 text-center py-10">No issues currently flagged in this category.</p>'}
            </div>
        `;
    } else if (label === 'Collaborations') {
        const collabs = Object.values(findings).filter(f => f.agent_name.startsWith('Collaboration:'));
        html = `
            <div class="mb-6">
                <h2 class="text-xl font-bold flex items-center gap-2">
                    <span class="w-8 h-8 bg-purple-600 rounded-lg flex items-center justify-center text-sm text-white font-bold">🔗</span>
                    Cross-Agency Collaborations
                </h2>
                <p class="text-xs text-gray-500 mt-1">Joint analysis automatically triggered by overlapping datasets</p>
            </div>
            <div class="space-y-3">
                ${collabs.length ? collabs.map(f => `
                    <div class="bg-gray-800/50 rounded-xl p-4 border border-gray-800 cursor-pointer hover:border-gray-600 group transition" onclick="openDetailModal('${f.agent_name.replace(/'/g, "\\'")}')">
                         <div class="flex items-center justify-between mb-1">
                            <span class="text-[10px] text-gray-600">${timeAgo(f.timestamp)}</span>
                        </div>
                        <h3 class="text-sm font-semibold text-white mb-1 group-hover:text-purple-400 transition">${f.agent_name.replace('Collaboration: ', '')}</h3>
                        <p class="text-xs text-gray-400 line-clamp-2">${f.issue_title}</p>
                    </div>
                `).join('') : `
                    <div class="text-center py-10">
                        <div class="text-4xl mb-4">🤝</div>
                        <p class="text-gray-500">No active collaborations. Agents are currently cross-referencing datasets for overlaps.</p>
                    </div>
                `}
            </div>
        `;
    } else if (label === 'Data Points') {
        const agentFindings = Object.values(findings).filter(f => !f.agent_name.startsWith('Collaboration:') && f.department !== 'News & Media');
        html = `
            <div class="mb-6">
                <h2 class="text-xl font-bold flex items-center gap-2">
                    <span class="w-8 h-8 bg-cyan-600 rounded-lg flex items-center justify-center text-sm text-white font-bold">📊</span>
                    Key Civic Metrics
                </h2>
                <p class="text-xs text-gray-500 mt-1">Real-time data points extracted from the latest SF Open Data harvests</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                ${agentFindings.flatMap(f => (f.key_metrics || []).map(m => `
                    <div class="bg-gray-800/50 rounded-xl p-3 border border-gray-800 hover:border-cyan-500 transition cursor-default">
                        <div class="flex justify-between items-start mb-1">
                            <div class="text-[10px] text-indigo-400 font-bold uppercase tracking-wider">${f.agent_name}</div>
                        </div>
                        <div class="text-xs text-gray-400 font-medium">${m.label || m.metric}</div>
                        <div class="text-xl font-bold text-white">${m.value}</div>
                    </div>
                `)).join('')}
            </div>
            ${agentFindings.length === 0 ? '<p class="text-gray-500 text-center py-10">Waiting for agents to extract first metrics...</p>' : ''}
        `;
    }

    content.innerHTML = html;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';
}

// ── Email Modal ──
function openEmailModal(agentName) {
    const f = findings[agentName];
    if (!f) return;

    document.getElementById('email-agent-name').value = agentName;
    document.getElementById('email-outcome').value = f.solution || '';
    document.getElementById('email-result').classList.add('hidden');
    document.getElementById('email-modal').classList.remove('hidden');
    document.getElementById('email-modal').classList.add('flex');
    document.body.style.overflow = 'hidden';

    // Auto-trigger the first draft for the citizen
    const form = document.getElementById('email-form');
    // We use a slight delay to ensure modal is visible, or just call the event handler
    form.dispatchEvent(new Event('submit'));
}

function closeModal() {
    document.getElementById('email-modal').classList.add('hidden');
    document.getElementById('email-modal').classList.remove('flex');
    document.body.style.overflow = '';
}

document.getElementById('email-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.textContent = 'Generating...';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/email/draft', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_name: document.getElementById('email-agent-name').value,
                citizen_name: document.getElementById('email-citizen').value,
                desired_outcome: document.getElementById('email-outcome').value,
                include_admin: document.getElementById('email-to-admin').checked
            }),
        });
        const result = await resp.json();
        const data = result.email_draft;
        document.getElementById('email-result-to').textContent = `To: ${(data.to || []).join(', ')}`;
        document.getElementById('email-result-subject').textContent = `Subject: ${data.subject}`;
        document.getElementById('email-result-body').textContent = data.body;
        document.getElementById('email-result').classList.remove('hidden');
    } catch (err) {
        alert('Error generating email: ' + err.message);
    } finally {
        btn.textContent = 'Generate Email Draft';
        btn.disabled = false;
    }
});

// Close modals on backdrop click
document.getElementById('email-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
});

document.getElementById('detail-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeDetailModal();
});

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeDetailModal();
    }
});

// ── Init ──
connectSSE();
syncAgentStatus();
setInterval(updateTimestamp, 5000);
setInterval(syncAgentStatus, 10000);
