// Funzioni JavaScript per il Sistema di Ricerca Avanzata

document.addEventListener('DOMContentLoaded', function() {
    // Gestione della modalità esperto
    const modeToggle = document.getElementById('modeToggle');
    const advancedOptions = document.getElementById('advancedOptions');
    
    if (modeToggle && advancedOptions) {
        modeToggle.addEventListener('change', function() {
            advancedOptions.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // Gestione delle fonti
    const addSourceButton = document.getElementById('addSource');
    const sourcesList = document.getElementById('sourcesList');
    
    if (addSourceButton && sourcesList) {
        // Aggiunge una nuova fonte
        addSourceButton.addEventListener('click', function() {
            const sourceItem = document.createElement('div');
            sourceItem.className = 'source-item';
            sourceItem.innerHTML = `
                <input type="text" class="form-control source-input" placeholder="URL (opzionale)">
                <button type="button" class="btn btn-outline-danger btn-sm remove-source">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            `;
            sourcesList.appendChild(sourceItem);
            
            // Aggiungi evento per rimuovere la fonte
            const removeButton = sourceItem.querySelector('.remove-source');
            removeButton.addEventListener('click', function() {
                sourcesList.removeChild(sourceItem);
            });
        });
        
        // Aggiungi evento per i pulsanti di rimozione esistenti
        document.querySelectorAll('.remove-source').forEach(button => {
            button.addEventListener('click', function() {
                const sourceItem = this.closest('.source-item');
                sourcesList.removeChild(sourceItem);
            });
        });
    }
    
    // Pulsante per avviare la ricerca
    const startResearchButton = document.getElementById('startResearch');
    const researchForm = document.getElementById('researchForm');
    const researchResults = document.getElementById('researchResults');
    const researchPrompt = document.getElementById('researchPrompt');
    
    if (startResearchButton && researchForm && researchResults && researchPrompt) {
        startResearchButton.addEventListener('click', function() {
            const prompt = researchPrompt.value.trim();
            
            if (prompt === '') {
                alert('Inserisci una richiesta di ricerca prima di procedere.');
                return;
            }
            
            // Raccoglie le fonti se sono state specificate
            const sources = [];
            if (advancedOptions && advancedOptions.style.display !== 'none') {
                document.querySelectorAll('.source-input').forEach(input => {
                    const source = input.value.trim();
                    if (source) {
                        sources.push(source);
                    }
                });
            }
            
            // Raccoglie la profondità di ricerca se specificata
            let depth = 2; // Default
            const depthSelect = document.getElementById('researchDepth');
            if (depthSelect) {
                depth = parseInt(depthSelect.value);
            }
            
            // Mostra il pannello dei risultati con indicatori di caricamento
            researchResults.style.display = 'block';
            document.getElementById('researchProgress').style.width = '10%';
            document.getElementById('researchStatus').textContent = 'In corso...';
            document.getElementById('statusMessages').innerHTML = '<div class="mb-2">Creazione del piano di ricerca...</div>';
            
            // Prima fase: crea un piano di ricerca
            createResearchPlan(prompt)
                .then(plan => {
                    // Aggiorna l'UI con il piano
                    updateResearchPlan(plan);
                    
                    // Aggiorna lo stato
                    document.getElementById('researchProgress').style.width = '30%';
                    document.getElementById('statusMessages').innerHTML += '<div class="mb-2">Piano di ricerca creato. Avvio esecuzione...</div>';
                    
                    // Seconda fase: esegui la ricerca
                    return executeResearch(plan.task_id, sources, depth);
                })
                .then(result => {
                    // Aggiorna lo stato
                    document.getElementById('researchProgress').style.width = '100%';
                    document.getElementById('researchStatus').className = 'badge bg-success';
                    document.getElementById('researchStatus').textContent = 'Completato';
                    document.getElementById('statusMessages').innerHTML += '<div class="mb-2">Ricerca completata!</div>';
                    
                    // Reindirizza alla pagina dei risultati
                    window.location.href = `/results?task_id=${result.task_id}`;
                })
                .catch(error => {
                    console.error('Error during research:', error);
                    document.getElementById('researchStatus').className = 'badge bg-danger';
                    document.getElementById('researchStatus').textContent = 'Errore';
                    document.getElementById('statusMessages').innerHTML += `<div class="mb-2 text-danger">Errore: ${error.message}</div>`;
                });
        });
    }
    
    // Pulsante per salvare l'API key
    const saveApiKeyButton = document.getElementById('saveApiKey');
    const geminiApiKeyInput = document.getElementById('geminiApiKey');
    
    if (saveApiKeyButton && geminiApiKeyInput) {
        saveApiKeyButton.addEventListener('click', function() {
            const apiKey = geminiApiKeyInput.value.trim();
            
            if (apiKey === '') {
                alert('Inserisci una API key valida prima di salvare.');
                return;
            }
            
            // Invia la API key al server
            fetch('/api/set-gemini-key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ api_key: apiKey })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status) {
                    // Aggiorna lo stato dell'API key nell'UI
                    const apiStatus = document.getElementById('apiStatus');
                    if (apiStatus) {
                        apiStatus.className = 'status-indicator status-completed';
                    }
                    
                    const geminiStatus = document.getElementById('geminiStatus');
                    if (geminiStatus) {
                        geminiStatus.innerHTML = '<span class="badge bg-success">Configurato</span>';
                    }
                    
                    // Chiudi il modal
                    bootstrap.Modal.getInstance(document.getElementById('apiKeyModal')).hide();
                }
            })
            .catch(error => {
                console.error('Error saving API key:', error);
                alert('Errore nel salvataggio della API key. Riprova più tardi.');
            });
        });
    }
    
    // Controlla lo stato di Ollama
    checkOllamaStatus();
});

// Funzione per creare un piano di ricerca
function createResearchPlan(prompt) {
    return fetch('/api/start-research', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: prompt })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Errore nella creazione del piano di ricerca');
        }
        return response.json();
    });
}

// Funzione per eseguire la ricerca
function executeResearch(taskId, sources, depth) {
    return fetch('/api/execute-research', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            task_id: taskId,
            sources: sources,
            depth: depth
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Errore nell\'esecuzione della ricerca');
        }
        return response.json();
    });
}

// Funzione per aggiornare l'UI con il piano di ricerca
function updateResearchPlan(plan) {
    const researchObjective = document.getElementById('researchObjective');
    const researchQuestions = document.getElementById('researchQuestions');
    const planDepth = document.getElementById('planDepth');
    
    if (researchObjective && researchQuestions && planDepth) {
        // Imposta l'obiettivo
        researchObjective.textContent = plan.plan.objective || 'Obiettivo non specificato';
        
        // Imposta la profondità
        planDepth.textContent = `Profondità: ${plan.plan.depth}`;
        
        // Imposta le domande di ricerca
        researchQuestions.innerHTML = '';
        if (plan.plan.questions && plan.plan.questions.length > 0) {
            const questionsList = document.createElement('ol');
            questionsList.className = 'list-group list-group-numbered';
            
            plan.plan.questions.forEach(question => {
                const item = document.createElement('li');
                item.className = 'list-group-item';
                
                const questionText = document.createElement('div');
                questionText.className = 'fw-bold mb-2';
                questionText.textContent = question.question;
                
                item.appendChild(questionText);
                
                if (question.sources && question.sources.length > 0) {
                    const sourcesTitle = document.createElement('div');
                    sourcesTitle.className = 'fw-light small mb-1';
                    sourcesTitle.textContent = 'Fonti suggerite:';
                    item.appendChild(sourcesTitle);
                    
                    const sourcesList = document.createElement('ul');
                    sourcesList.className = 'list-unstyled small ms-3';
                    
                    question.sources.forEach(source => {
                        const sourceItem = document.createElement('li');
                        sourceItem.innerHTML = `<a href="${source}" target="_blank" class="source-link">${source}</a>`;
                        sourcesList.appendChild(sourceItem);
                    });
                    
                    item.appendChild(sourcesList);
                }
                
                questionsList.appendChild(item);
            });
            
            researchQuestions.appendChild(questionsList);
        } else {
            researchQuestions.textContent = 'Nessuna domanda di ricerca definita.';
        }
    }
}

// Funzione per controllare lo stato di Ollama
function checkOllamaStatus() {
    const ollamaStatus = document.getElementById('ollamaStatus');
    
    if (ollamaStatus) {
        // Nota: in Replit Ollama non è disponibile, quindi impostiamo sempre non disponibile
        ollamaStatus.innerHTML = '<span class="badge bg-danger">Non disponibile in Replit</span>';
        
        // In un ambiente reale, potremmo fare una richiesta al server:
        /*
        fetch('/api/check-ollama-status')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'running') {
                    ollamaStatus.innerHTML = '<span class="badge bg-success">Attivo</span>';
                } else {
                    ollamaStatus.innerHTML = '<span class="badge bg-danger">Non attivo</span>';
                }
            })
            .catch(error => {
                console.error('Error checking Ollama status:', error);
                ollamaStatus.innerHTML = '<span class="badge bg-danger">Errore</span>';
            });
        */
    }
}