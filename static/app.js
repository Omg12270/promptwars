/**
 * App Frontend Logic — Multi-Agent Interview Panel Simulator
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let agents = [];
    let selectedCandidate = 'a';
    let currentJobId = null;
    let eventSource = null;
    let criteriaTags = [];

    // DOM Elements
    const agentsGrid = document.getElementById('agents-grid');
    const candidateCards = document.querySelectorAll('.candidate-card');
    const runBtn = document.getElementById('btn-run');
    const apiKeyInput = document.getElementById('api-key-input');
    
    // API Key - Load from local storage
    const savedKey = localStorage.getItem('groq_api_key');
    if (savedKey) {
        apiKeyInput.value = savedKey;
    }
    apiKeyInput.addEventListener('change', (e) => {
        localStorage.setItem('groq_api_key', e.target.value);
    });

    // Candidate Selection
    candidateCards.forEach(card => {
        card.addEventListener('click', () => {
            candidateCards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedCandidate = card.dataset.candidate;
        });
    });

    // Load Agents
    async function fetchAgents() {
        try {
            const response = await fetch('/api/agents');
            agents = await response.json();
            renderAgents();
        } catch (error) {
            showToast('Failed to load agents', 'error');
        }
    }

    // Render Agents Grid
    function renderAgents() {
        agentsGrid.innerHTML = '';
        
        agents.forEach(agent => {
            const card = document.createElement('div');
            card.className = 'glass-card agent-card';
            card.style.setProperty('--agent-color', agent.color);
            
            let strictnessDots = '';
            for (let i = 1; i <= 10; i++) {
                strictnessDots += `<div class="strictness-dot ${i <= agent.strictness ? 'active' : ''}"></div>`;
            }

            let criteriaTagsHtml = agent.evaluation_criteria.slice(0, 4).map(c => 
                `<span class="criterion-tag">${c}</span>`
            ).join('');
            if (agent.evaluation_criteria.length > 4) {
                criteriaTagsHtml += `<span class="criterion-tag">+${agent.evaluation_criteria.length - 4} more</span>`;
            }

            card.innerHTML = `
                <div class="agent-card__header">
                    <div class="agent-card__icon">${agent.icon}</div>
                    <div class="agent-card__name">${agent.name}</div>
                    <div class="agent-card__actions">
                        <button class="agent-card__btn btn-edit-agent" data-id="${agent.id}">⚙️</button>
                    </div>
                </div>
                <div class="agent-card__role">${agent.role}</div>
                <div class="agent-card__criteria">${criteriaTagsHtml}</div>
                <div class="agent-card__footer">
                    <div class="strictness-display">
                        Strictness <div class="strictness-bar">${strictnessDots}</div>
                    </div>
                    <div class="weight-display">Wt: ${agent.weight.toFixed(1)}</div>
                </div>
            `;
            agentsGrid.appendChild(card);
        });

        // Add Agent Button
        const addCard = document.createElement('div');
        addCard.className = 'glass-card add-agent-card';
        addCard.innerHTML = `
            <div class="add-agent-card__icon">+</div>
            <div class="add-agent-card__text">Create Custom Agent</div>
        `;
        addCard.addEventListener('click', openAddAgentModal);
        agentsGrid.appendChild(addCard);

        // Bind Edit Buttons
        document.querySelectorAll('.btn-edit-agent').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.dataset.id;
                const agent = agents.find(a => a.id === id);
                if (agent) openEditAgentModal(agent);
            });
        });
    }

    // Modal Logic
    const modal = document.getElementById('agent-modal');
    const agentForm = document.getElementById('agent-form');
    
    // Sliders
    const strictnessSlider = document.getElementById('agent-strictness');
    const strictnessVal = document.getElementById('strictness-val');
    strictnessSlider.addEventListener('input', (e) => strictnessVal.textContent = e.target.value);
    
    const weightSlider = document.getElementById('agent-weight');
    const weightVal = document.getElementById('weight-val');
    weightSlider.addEventListener('input', (e) => weightVal.textContent = parseFloat(e.target.value).toFixed(1));

    // Color presets
    const colorPicker = document.getElementById('agent-color');
    document.querySelectorAll('.color-preset').forEach(preset => {
        preset.addEventListener('click', (e) => {
            const color = e.target.dataset.color;
            colorPicker.value = color;
            document.querySelectorAll('.color-preset').forEach(p => p.classList.remove('active'));
            e.target.classList.add('active');
        });
    });
    colorPicker.addEventListener('input', () => {
        document.querySelectorAll('.color-preset').forEach(p => p.classList.remove('active'));
    });

    // Criteria Tags
    const criteriaInput = document.getElementById('criteria-input');
    const criteriaTagsContainer = document.getElementById('criteria-tags');

    function renderCriteriaTags() {
        // Remove existing tags
        document.querySelectorAll('.form-tag').forEach(t => t.remove());
        
        // Add new tags
        criteriaTags.forEach((tag, idx) => {
            const span = document.createElement('span');
            span.className = 'form-tag';
            span.innerHTML = `
                ${tag}
                <span class="form-tag__remove" data-idx="${idx}">×</span>
            `;
            criteriaTagsContainer.insertBefore(span, criteriaInput);
        });

        // Bind removes
        document.querySelectorAll('.form-tag__remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                criteriaTags.splice(idx, 1);
                renderCriteriaTags();
            });
        });
    }

    criteriaInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const val = criteriaInput.value.trim();
            if (val && !criteriaTags.includes(val)) {
                criteriaTags.push(val);
                criteriaInput.value = '';
                renderCriteriaTags();
            }
        }
    });

    // Open Add Modal
    function openAddAgentModal() {
        document.getElementById('modal-title').textContent = 'Create Custom Agent';
        document.getElementById('agent-id').value = 'custom_' + Date.now();
        document.getElementById('agent-is-default').value = 'false';
        document.getElementById('agent-name').value = '';
        document.getElementById('agent-icon').value = '🤖';
        document.getElementById('agent-role').value = '';
        document.getElementById('agent-prompt').value = '';
        document.getElementById('agent-color').value = '#3b82f6';
        
        strictnessSlider.value = 5;
        strictnessVal.textContent = '5';
        weightSlider.value = 1.0;
        weightVal.textContent = '1.0';
        
        criteriaTags = [];
        renderCriteriaTags();

        document.getElementById('btn-delete-agent').style.display = 'none';
        document.getElementById('btn-reset-agent').style.display = 'none';
        
        modal.classList.add('active');
    }

    // Open Edit Modal
    function openEditAgentModal(agent) {
        document.getElementById('modal-title').textContent = 'Edit Agent';
        document.getElementById('agent-id').value = agent.id;
        document.getElementById('agent-is-default').value = agent.is_default;
        document.getElementById('agent-name').value = agent.name;
        document.getElementById('agent-icon').value = agent.icon;
        document.getElementById('agent-role').value = agent.role;
        document.getElementById('agent-prompt').value = agent.system_prompt;
        document.getElementById('agent-color').value = agent.color;
        
        strictnessSlider.value = agent.strictness;
        strictnessVal.textContent = agent.strictness;
        weightSlider.value = agent.weight;
        weightVal.textContent = agent.weight.toFixed(1);
        
        criteriaTags = [...agent.evaluation_criteria];
        renderCriteriaTags();

        if (!agent.is_default && !agent.id.match(/^(technical|hr_culture|hiring_manager|skeptic)$/)) {
            document.getElementById('btn-delete-agent').style.display = 'block';
            document.getElementById('btn-reset-agent').style.display = 'none';
        } else if (!agent.is_default) {
            // Modified default agent
            document.getElementById('btn-delete-agent').style.display = 'none';
            document.getElementById('btn-reset-agent').style.display = 'block';
        } else {
            // Unmodified default agent
            document.getElementById('btn-delete-agent').style.display = 'none';
            document.getElementById('btn-reset-agent').style.display = 'none';
        }
        
        modal.classList.add('active');
    }

    // Close Modal
    function closeModal() {
        modal.classList.remove('active');
    }
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('btn-cancel-agent').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    // Save Agent
    agentForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const agentData = {
            id: document.getElementById('agent-id').value,
            name: document.getElementById('agent-name').value,
            icon: document.getElementById('agent-icon').value,
            role: document.getElementById('agent-role').value,
            system_prompt: document.getElementById('agent-prompt').value,
            color: document.getElementById('agent-color').value,
            strictness: parseInt(strictnessSlider.value),
            weight: parseFloat(weightSlider.value),
            evaluation_criteria: criteriaTags,
            is_default: document.getElementById('agent-is-default').value === 'true'
        };

        try {
            const res = await fetch('/api/agents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(agentData)
            });
            if (res.ok) {
                showToast('Agent saved successfully', 'success');
                closeModal();
                fetchAgents();
            }
        } catch (err) {
            showToast('Failed to save agent', 'error');
        }
    });

    // Delete Agent
    document.getElementById('btn-delete-agent').addEventListener('click', async () => {
        const id = document.getElementById('agent-id').value;
        if (confirm('Are you sure you want to delete this custom agent?')) {
            try {
                const res = await fetch(`/api/agents/${id}`, { method: 'DELETE' });
                if (res.ok) {
                    showToast('Agent deleted', 'success');
                    closeModal();
                    fetchAgents();
                }
            } catch (err) {
                showToast('Failed to delete agent', 'error');
            }
        }
    });

    // Reset Agent
    document.getElementById('btn-reset-agent').addEventListener('click', async () => {
        const id = document.getElementById('agent-id').value;
        try {
            const res = await fetch(`/api/agents/${id}/reset`, { method: 'POST' });
            if (res.ok) {
                showToast('Agent reset to defaults', 'success');
                closeModal();
                fetchAgents();
            }
        } catch (err) {
            showToast('Failed to reset agent', 'error');
        }
    });

    // ─── Pipeline Execution ──────────────────────────────────────────────────

    runBtn.addEventListener('click', async () => {
        const apiKey = apiKeyInput.value.trim();
        if (!apiKey) {
            showToast('Please enter a Groq API Key', 'error');
            apiKeyInput.focus();
            return;
        }

        // Setup UI
        runBtn.disabled = true;
        runBtn.innerHTML = '<span class="spinner"></span> Starting...';
        document.getElementById('pipeline-section').classList.add('active');
        document.getElementById('results-section').classList.remove('active');
        
        // Reset pipeline steps
        document.querySelectorAll('.pipeline-step').forEach(s => {
            s.classList.remove('active', 'completed', 'error');
        });
        document.getElementById('event-log').innerHTML = '';

        try {
            // Start Job
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: apiKey,
                    candidate: selectedCandidate,
                    agent_ids: agents.map(a => a.id)
                })
            });

            const data = await res.json();
            if (data.error) throw new Error(data.error);
            
            currentJobId = data.job_id;
            connectSSE(currentJobId);
            
        } catch (err) {
            showToast(err.message || 'Failed to start pipeline', 'error');
            resetRunBtn();
        }
    });

    function connectSSE(jobId) {
        if (eventSource) eventSource.close();
        
        eventSource = new EventSource(`/api/status/${jobId}`);
        
        eventSource.onmessage = (e) => {
            const event = JSON.parse(e.data);
            handlePipelineEvent(event);
        };

        eventSource.onerror = () => {
            eventSource.close();
            resetRunBtn();
            showToast('Connection to server lost', 'error');
        };
    }

    function handlePipelineEvent(event) {
        const { type, message, data, status } = event;

        // Log all events
        if (message) {
            const logEl = document.getElementById('event-log');
            const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
            
            const entry = document.createElement('div');
            entry.className = 'event-log__entry';
            entry.innerHTML = `<span class="event-log__time">[${time}]</span> ${message}`;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }

        // Handle specific stages
        if (type === 'stage') {
            const stage = data.stage;
            document.querySelectorAll('.pipeline-step').forEach(s => s.classList.remove('active'));
            
            if (stage === 'profile') {
                document.getElementById('step-profile').classList.add('active');
            } else if (stage === 'evaluation') {
                document.getElementById('step-profile').classList.replace('active', 'completed');
                document.getElementById('step-evaluation').classList.add('active');
            } else if (stage === 'debate') {
                document.getElementById('step-evaluation').classList.replace('active', 'completed');
                document.getElementById('step-debate').classList.add('active');
            } else if (stage === 'decision') {
                document.getElementById('step-debate').classList.replace('active', 'completed');
                document.getElementById('step-decision').classList.add('active');
            }
        }

        if (type === 'result') {
            renderResults(data);
        }

        if (type === 'done') {
            eventSource.close();
            resetRunBtn();
            if (status === 'completed') {
                document.getElementById('step-decision').classList.replace('active', 'completed');
                showToast('Evaluation completed successfully!', 'success');
                document.getElementById('results-section').classList.add('active');
                
                // Scroll to results
                setTimeout(() => {
                    document.getElementById('results-section').scrollIntoView({ behavior: 'smooth' });
                }, 100);
            }
        }

        if (type === 'error') {
            eventSource.close();
            resetRunBtn();
            document.querySelectorAll('.pipeline-step.active').forEach(s => s.classList.replace('active', 'error'));
        }
    }

    function resetRunBtn() {
        runBtn.disabled = false;
        runBtn.innerHTML = 'Start Evaluation Pipeline';
    }

    // ─── Results Rendering ───────────────────────────────────────────────────

    // Tabs
    const tabs = document.querySelectorAll('.results-tab');
    const panels = document.querySelectorAll('.results-panel');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.target).classList.add('active');
        });
    });

    function renderResults(result) {
        renderFinalDecision(result.final_decision, result.profile);
        renderEvaluations(result.evaluations);
        renderDebate(result.debate);
        renderProfile(result.profile);
    }

    function getRecClass(rec) {
        return `rec--${rec}`;
    }

    function getScoreClass(score) {
        if (score >= 8) return 'eval-card__score--high';
        if (score >= 6) return 'eval-card__score--mid';
        return 'eval-card__score--low';
    }

    function renderFinalDecision(decision, profile) {
        const container = document.getElementById('final-decision-content');
        const formattedRec = decision.final_recommendation.replace(/_/g, ' ');
        
        let factorsHtml = '';
        if (decision.reasoning.key_factors_for?.length) {
            factorsHtml += `<div class="factors-column">
                <div class="factors-column__title">👍 Key Factors FOR Hiring</div>
                ${decision.reasoning.key_factors_for.map(f => `
                    <div class="factor-item factor-item--for">
                        <div class="factor-item__title">${f.factor}</div>
                        <div class="factor-item__evidence">"${f.evidence}"</div>
                        <div class="factor-item__agents">Agents: ${f.supporting_agents.join(', ')}</div>
                    </div>
                `).join('')}
            </div>`;
        }
        
        if (decision.reasoning.key_factors_against?.length) {
            factorsHtml += `<div class="factors-column">
                <div class="factors-column__title">👎 Key Factors AGAINST Hiring</div>
                ${decision.reasoning.key_factors_against.map(f => `
                    <div class="factor-item factor-item--against">
                        <div class="factor-item__title">${f.factor}</div>
                        <div class="factor-item__evidence">"${f.evidence}"</div>
                        <div class="factor-item__agents">Agents: ${f.supporting_agents.join(', ')}</div>
                    </div>
                `).join('')}
            </div>`;
        }

        let disagreementsHtml = '';
        if (decision.unresolved_disagreements?.length) {
            disagreementsHtml = `
                <div class="disagreements">
                    <h3 class="factors-column__title" style="color: var(--accent-amber)">⚠️ Unresolved Disagreements</h3>
                    ${decision.unresolved_disagreements.map(d => `
                        <div class="disagreement-item">
                            <div class="disagreement-item__topic">${d.topic}</div>
                            ${d.positions.map(p => `
                                <div class="disagreement-position">
                                    <span class="disagreement-position__agent">${p.agent}:</span>
                                    <span class="disagreement-position__stance">${p.position}</span>
                                </div>
                            `).join('')}
                            <div style="margin-top: 8px; font-size: 12px; color: var(--text-muted)">
                                Impact: ${d.impact_on_decision}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        container.innerHTML = `
            <h2>${profile.name}</h2>
            <p style="color: var(--text-secondary); margin-bottom: 32px;">${profile.current_title}</p>
            
            <div class="final-decision__recommendation ${getRecClass(decision.final_recommendation)}">
                ${formattedRec}
            </div>
            
            <div class="final-decision__score ${getScoreClass(decision.overall_score)}">
                ${decision.overall_score}
            </div>
            
            <div class="final-decision__confidence">
                Confidence: ${(decision.confidence * 100).toFixed(0)}%
                <div class="confidence-bar">
                    <div class="confidence-bar__fill" style="width: ${decision.confidence * 100}%"></div>
                </div>
            </div>
            
            <div class="final-decision__methodology">
                <strong>Synthesis Methodology:</strong><br>
                ${decision.decision_methodology}
            </div>

            <div class="final-decision__factors">
                ${factorsHtml}
            </div>
            
            ${disagreementsHtml}
        `;
    }

    function renderEvaluations(evals) {
        const container = document.getElementById('evaluations-content');
        container.innerHTML = evals.map(ev => `
            <div class="glass-card eval-card" style="--agent-color: ${ev.agent_color || 'var(--accent-blue)'}">
                <div class="eval-card__header">
                    <div style="font-size: 32px;">${ev.agent_icon || '🤖'}</div>
                    <div style="flex: 1;">
                        <h3 style="font-size: 16px;">${ev.agent_name}</h3>
                        <div class="eval-card__recommendation ${getRecClass(ev.recommendation)}" style="display: inline-block; margin-top: 4px;">
                            ${ev.recommendation.replace(/_/g, ' ')}
                        </div>
                    </div>
                    <div class="eval-card__score ${getScoreClass(ev.overall_score)}">
                        ${ev.overall_score}
                    </div>
                </div>
                
                <div class="eval-card__summary">
                    ${ev.summary}
                </div>
                
                <ul class="eval-card__criteria-list">
                    ${ev.criteria_scores.map(c => `
                        <li class="eval-card__criteria-item" title="${c.reasoning}">
                            <div class="criteria-name">${c.criterion}</div>
                            <div class="criteria-bar"><div class="criteria-bar__fill" style="width: ${c.score * 10}%; background: var(--agent-color, var(--accent-blue))"></div></div>
                            <div class="criteria-score">${c.score}/10</div>
                        </li>
                    `).join('')}
                </ul>
                
                <div class="eval-card__evidence">
                    ${ev.key_strengths.slice(0, 2).map(s => `
                        <div class="evidence-item evidence-item--strength">
                            <div class="evidence-item__label">👍 ${s.strength}</div>
                            <div class="evidence-item__quote">"${s.evidence}"</div>
                        </div>
                    `).join('')}
                    
                    ${ev.key_concerns.slice(0, 2).map(c => `
                        <div class="evidence-item evidence-item--concern">
                            <div class="evidence-item__label">🚩 ${c.concern}</div>
                            <div class="evidence-item__quote">"${c.evidence}"</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    }

    function renderDebate(debate) {
        const container = document.getElementById('debate-content');
        let html = '';

        debate.rounds.forEach((round, rIdx) => {
            html += `<div class="debate-round">
                <div class="debate-round__title">Debate Round ${rIdx + 1}</div>
            `;
            
            round.forEach(msg => {
                const agent = agents.find(a => a.id === msg.agent_id) || { color: '#3b82f6', icon: '🤖' };
                
                html += `
                    <div class="debate-message" style="--agent-color: ${agent.color}">
                        <div class="debate-message__header">
                            <span style="font-size: 20px;">${agent.icon}</span>
                            <span class="debate-message__agent">${msg.agent_name}</span>
                        </div>
                        <div class="debate-message__responses">
                            ${msg.responses.map(r => `
                                <div class="debate-response">
                                    <div class="debate-response__target">
                                        Responding to ${r.responding_to}
                                        <span class="debate-response__action action--${r.action}">${r.action}</span>
                                    </div>
                                    <div class="debate-response__text">
                                        <strong>Point:</strong> "${r.their_point}"<br>
                                        <strong>Response:</strong> ${r.your_response}<br>
                                        <em>Evidence: "${r.evidence}"</em>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                `;

                if (msg.opinion_changed) {
                    const cd = msg.change_details;
                    html += `
                        <div class="opinion-change">
                            <div class="opinion-change__badge">★ Opinion Changed</div>
                            <div class="opinion-change__scores">Score: ${cd.previous_score} → ${cd.new_score}</div>
                            <div class="opinion-change__reason">
                                <strong>Reason:</strong> ${cd.reason_for_change}<br>
                                <em>Evidence: "${cd.convincing_evidence}"</em>
                            </div>
                        </div>
                    `;
                }

                html += `</div>`; // end debate-message
            });
            html += `</div>`; // end debate-round
        });

        container.innerHTML = html;
    }

    function renderProfile(profile) {
        const container = document.getElementById('profile-content');
        
        const jsonStr = JSON.stringify(profile, null, 2);
        // Use marked if available to render nice markdown, else raw text
        container.innerHTML = `
            <div style="padding: 24px;">
                <h3 style="margin-bottom: 16px;">Extracted Profile Data</h3>
                <pre style="background: var(--bg-secondary); padding: 16px; border-radius: var(--radius-md); overflow-x: auto; font-family: var(--font-mono); font-size: 13px; color: var(--text-primary); border: 1px solid var(--border-glass);"><code>${jsonStr}</code></pre>
            </div>
        `;
    }

    // Utilities
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'error') icon = '❌';
        
        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(16px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Init
    fetchAgents();
});
