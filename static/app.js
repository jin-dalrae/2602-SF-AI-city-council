// ── State ──
const findings = {};
let lastUpdate = null;

// ── Icons ──
const ICONS = {
    shield: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>`,
    wrench: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>`,
    'dollar-sign': `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`,
    building: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>`,
    bus: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h8m-8 4h8m-4 4v4m-4-4h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>`,
    link: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>`,
};

const SEVERITY_COLORS = {
    critical: { bg: 'bg-red-500/10', text: 'text-red-400', badge: 'bg-red-500' },
    high: { bg: 'bg-orange-500/10', text: 'text-orange-400', badge: 'bg-orange-500' },
    medium: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', badge: 'bg-yellow-500' },
    low: { bg: 'bg-green-500/10', text: 'text-green-400', badge: 'bg-green-500' },
};

// ── SSE Connection ──
function connectSSE() {
    const evtSource = new EventSource('/api/findings');
    const statusEl = document.getElementById('connection-status');

    evtSource.onopen = () => {
        statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-green-500 pulse-dot"></span> Live`;
    };

    evtSource.addEventListener('finding', (e) => {
        const data = JSON.parse(e.data);
        findings[data.agent_name] = data;
        lastUpdate = new Date();
        renderAll();
    });

    evtSource.addEventListener('heartbeat', () => {});

    evtSource.onerror = () => {
        statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-red-500 pulse-dot"></span> Reconnecting...`;
    };
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
        { label: 'Critical Issues', value: agentFindings.filter(f => f.severity === 'critical').length, color: 'text-red-400' },
        { label: 'High Issues', value: agentFindings.filter(f => f.severity === 'high').length, color: 'text-orange-400' },
        { label: 'Collaborations', value: Object.keys(findings).filter(k => k.startsWith('Collaboration:')).length, color: 'text-purple-400' },
        { label: 'Data Points', value: agentFindings.reduce((sum, f) => sum + (f.key_metrics?.length || 0), 0), color: 'text-cyan-400' },
    ];

    bar.innerHTML = stats.map(s => `
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div class="text-2xl font-bold ${s.color}">${s.value}</div>
            <div class="text-xs text-gray-500">${s.label}</div>
        </div>
    `).join('');
}

function renderCards() {
    const grid = document.getElementById('findings-grid');
    const entries = Object.values(findings);

    if (entries.length === 0) return;

    // Sort: collaborations last, then by severity
    const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    entries.sort((a, b) => {
        const aCollab = a.agent_name.startsWith('Collaboration:') ? 1 : 0;
        const bCollab = b.agent_name.startsWith('Collaboration:') ? 1 : 0;
        if (aCollab !== bCollab) return aCollab - bCollab;
        return (severityOrder[a.severity] || 3) - (severityOrder[b.severity] || 3);
    });

    grid.innerHTML = entries.map(f => renderCard(f)).join('');
}

function renderCard(f) {
    const isCollab = f.agent_name.startsWith('Collaboration:');
    const sev = SEVERITY_COLORS[f.severity] || SEVERITY_COLORS.low;
    const icon = ICONS[f.icon] || `<span class="text-lg">${f.icon}</span>`;
    const cardId = f.agent_name.replace(/[^a-zA-Z0-9]/g, '_');

    const metricsHtml = (f.key_metrics || []).map(m =>
        `<div class="bg-gray-800/50 rounded px-2 py-1">
            <div class="text-xs text-gray-500">${m.label}</div>
            <div class="text-sm font-medium">${m.value}</div>
        </div>`
    ).join('');

    const evidenceHtml = (f.evidence || []).slice(0, 3).map(e =>
        `<li class="text-xs text-gray-400">${e}</li>`
    ).join('');

    const newsHtml = (f.news_context || []).length > 0
        ? `<div class="mt-2 border-t border-gray-700 pt-2">
            <p class="text-xs font-medium text-indigo-400 mb-1">Related News:</p>
            ${f.news_context.slice(0, 2).map(n => `<p class="text-xs text-gray-400 mb-1">• ${n}</p>`).join('')}
           </div>`
        : '';

    const neighborhoodsHtml = (f.affected_neighborhoods || []).length > 0
        ? `<div class="flex flex-wrap gap-1 mt-2">
            ${f.affected_neighborhoods.map(n => `<span class="text-xs bg-gray-800 text-gray-400 rounded px-1.5 py-0.5">${n}</span>`).join('')}
           </div>`
        : '';

    const emailBtn = !isCollab
        ? `<button onclick="openEmailModal('${f.agent_name.replace(/'/g, "\\'")}')" class="text-xs bg-indigo-600 hover:bg-indigo-500 rounded px-3 py-1.5 transition">Draft Email</button>`
        : '';

    return `
    <div class="card-enter ${isCollab ? 'collaboration-card' : 'bg-gray-900'} border border-gray-800 rounded-xl overflow-hidden severity-${f.severity}">
        <div class="p-4">
            <!-- Header -->
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-2">
                    <div class="w-8 h-8 ${sev.bg} ${sev.text} rounded-lg flex items-center justify-center">${icon}</div>
                    <div>
                        <h3 class="text-sm font-bold">${f.agent_name}</h3>
                        <p class="text-xs text-gray-500">${f.department}</p>
                    </div>
                </div>
                <span class="text-xs ${sev.badge} rounded-full px-2 py-0.5 font-medium text-white uppercase">${f.severity}</span>
            </div>

            <!-- Issue Title -->
            <h4 class="font-semibold text-sm mb-2">${f.issue_title || 'Analyzing...'}</h4>

            <!-- Summary -->
            <p class="text-xs text-gray-400 mb-3 line-clamp-3">${f.summary || ''}</p>

            <!-- Metrics -->
            ${metricsHtml ? `<div class="grid grid-cols-2 gap-1.5 mb-3">${metricsHtml}</div>` : ''}

            <!-- Details (collapsible) -->
            <details class="group">
                <summary class="text-xs text-indigo-400 cursor-pointer hover:text-indigo-300">View Details</summary>
                <div class="mt-2 space-y-2">
                    ${f.solution ? `<div><p class="text-xs font-medium text-gray-300 mb-1">Recommendation:</p><p class="text-xs text-gray-400">${f.solution}</p></div>` : ''}
                    ${evidenceHtml ? `<div><p class="text-xs font-medium text-gray-300 mb-1">Evidence:</p><ul class="list-disc list-inside space-y-0.5">${evidenceHtml}</ul></div>` : ''}
                    ${newsHtml}
                    ${neighborhoodsHtml}
                </div>
            </details>

            <!-- Footer -->
            <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-800">
                <span class="text-xs text-gray-600">${timeAgo(f.timestamp)}</span>
                ${emailBtn}
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

// ── Email Modal ──
function openEmailModal(agentName) {
    document.getElementById('email-agent-name').value = agentName;
    document.getElementById('email-result').classList.add('hidden');
    document.getElementById('email-modal').classList.remove('hidden');
    document.getElementById('email-modal').classList.add('flex');
}

function closeModal() {
    document.getElementById('email-modal').classList.add('hidden');
    document.getElementById('email-modal').classList.remove('flex');
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
                ngo_name: document.getElementById('email-ngo').value,
                contact_person: document.getElementById('email-contact').value,
                desired_outcome: document.getElementById('email-outcome').value,
                context: document.getElementById('email-context').value,
            }),
        });
        const data = await resp.json();
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

// Close modal on backdrop click
document.getElementById('email-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
});

// ── Init ──
connectSSE();
setInterval(updateTimestamp, 5000);
