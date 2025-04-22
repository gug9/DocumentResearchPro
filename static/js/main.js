document.addEventListener('DOMContentLoaded', function() {
    // Initialize Feather icons
    feather.replace();
    
    // Initialize interface elements
    setupFormHandlers();
    setupResultsPage();
});

/**
 * Setup form handlers for the index page
 */
function setupFormHandlers() {
    const researchForm = document.getElementById('researchForm');
    const planButton = document.getElementById('planButton');
    const startButton = document.getElementById('startButton');
    const planCard = document.getElementById('planCard');
    const progressCard = document.getElementById('progressCard');
    const editPlanButton = document.getElementById('editPlanButton');
    const executePlanButton = document.getElementById('executePlanButton');
    const cancelButton = document.getElementById('cancelButton');
    
    // Skip if these elements aren't present (probably on the results page)
    if (!researchForm) return;
    
    // Generate research plan button
    if (planButton) {
        planButton.addEventListener('click', function() {
            const prompt = document.getElementById('prompt').value;
            
            if (!prompt) {
                alert('Please enter a research objective.');
                return;
            }
            
            // Show loading state
            planButton.disabled = true;
            planButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';
            
            // API call to create research plan
            fetch('/api/research/plan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prompt })
            })
            .then(response => response.json())
            .then(data => {
                // Reset button state
                planButton.disabled = false;
                planButton.innerHTML = '<i data-feather="clipboard"></i> Generate Research Plan';
                feather.replace();
                
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                
                // Display the plan
                displayResearchPlan(data.plan);
                planCard.style.display = 'block';
                
                // Scroll to plan card
                planCard.scrollIntoView({ behavior: 'smooth' });
            })
            .catch(error => {
                console.error('Error:', error);
                planButton.disabled = false;
                planButton.innerHTML = '<i data-feather="clipboard"></i> Generate Research Plan';
                feather.replace();
                alert('Error generating research plan. Please try again.');
            });
        });
    }
    
    // Start research button
    if (startButton) {
        startButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            const prompt = document.getElementById('prompt').value;
            const depth = document.querySelector('input[name="depth"]:checked').value;
            
            if (!prompt) {
                alert('Please enter a research objective.');
                return;
            }
            
            // Show loading state
            startButton.disabled = true;
            startButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Starting...';
            
            // API call to start research
            fetch('/api/research/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    prompt,
                    depth: parseInt(depth, 10)
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                    startButton.disabled = false;
                    startButton.innerHTML = '<i data-feather="play"></i> Start Research';
                    feather.replace();
                    return;
                }
                
                // Store task ID
                const taskId = data.task_id;
                
                // Execute the research task
                executeResearch(taskId, data.task);
            })
            .catch(error => {
                console.error('Error:', error);
                startButton.disabled = false;
                startButton.innerHTML = '<i data-feather="play"></i> Start Research';
                feather.replace();
                alert('Error starting research. Please try again.');
            });
        });
    }
    
    // Edit plan button
    if (editPlanButton) {
        editPlanButton.addEventListener('click', function() {
            // Hide plan card and re-enable form
            planCard.style.display = 'none';
            document.getElementById('prompt').focus();
        });
    }
    
    // Execute plan button
    if (executePlanButton) {
        executePlanButton.addEventListener('click', function() {
            // Get the task data from the HTML data attribute
            const taskDataElement = document.getElementById('planContent');
            if (!taskDataElement || !taskDataElement.dataset.task) {
                alert('No task data available. Please generate a plan first.');
                return;
            }
            
            try {
                const taskData = JSON.parse(taskDataElement.dataset.task);
                executeResearch(taskData.task_id, taskData);
            } catch (e) {
                console.error('Error parsing task data:', e);
                alert('Error executing plan. Please try again.');
            }
        });
    }
    
    // Cancel button
    if (cancelButton) {
        cancelButton.addEventListener('click', function() {
            if (confirm('Are you sure you want to cancel the research?')) {
                // Reset UI
                progressCard.style.display = 'none';
                startButton.disabled = false;
                startButton.innerHTML = '<i data-feather="play"></i> Start Research';
                feather.replace();
                
                // In a real app, we would call an API to cancel the task
            }
        });
    }
}

/**
 * Display a research plan in the UI
 */
function displayResearchPlan(plan) {
    const planContentElement = document.getElementById('planContent');
    if (!planContentElement) return;
    
    // Store the plan data for later use
    planContentElement.dataset.task = JSON.stringify(plan);
    
    // Create HTML for the plan
    let html = `
        <h4>Research Questions</h4>
        <ol class="list-group list-group-numbered mb-4">
    `;
    
    plan.questions.forEach(question => {
        html += `
            <li class="list-group-item bg-dark d-flex justify-content-between align-items-start">
                <div class="ms-2 me-auto">
                    <div class="fw-bold">${question.question}</div>
                    <div class="small text-muted mt-1">
                        <strong>Sources:</strong>
                        <ul class="mb-0">
        `;
        
        question.sources.forEach(source => {
            html += `<li><a href="${source}" target="_blank">${source}</a></li>`;
        });
        
        html += `
                        </ul>
                    </div>
                </div>
            </li>
        `;
    });
    
    html += `
        </ol>
        <div class="d-flex align-items-center">
            <div class="me-3">
                <strong>Research Depth:</strong>
            </div>
            <div class="progress flex-grow-1" style="height: 24px;">
                <div class="progress-bar bg-info" role="progressbar" style="width: ${plan.depth * 33.33}%" 
                    aria-valuenow="${plan.depth}" aria-valuemin="0" aria-valuemax="3">
                    Level ${plan.depth}
                </div>
            </div>
        </div>
    `;
    
    planContentElement.innerHTML = html;
}

/**
 * Execute a research task and update the UI with progress
 */
function executeResearch(taskId, task) {
    // Show progress card and hide plan card
    const progressCard = document.getElementById('progressCard');
    const planCard = document.getElementById('planCard');
    const researchForm = document.getElementById('researchForm');
    
    if (progressCard) progressCard.style.display = 'block';
    if (planCard) planCard.style.display = 'none';
    
    // Disable form controls
    if (researchForm) {
        Array.from(researchForm.elements).forEach(element => {
            element.disabled = true;
        });
    }
    
    // Update progress indicators
    const progressBar = document.getElementById('researchProgress');
    const currentStatus = document.getElementById('currentStatus');
    const elapsedTime = document.getElementById('elapsedTime');
    
    if (progressBar) progressBar.style.width = '10%';
    if (currentStatus) currentStatus.textContent = 'Initializing research...';
    
    // Start timer
    let seconds = 0;
    const timer = setInterval(() => {
        seconds++;
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        if (elapsedTime) elapsedTime.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }, 1000);
    
    // Update status every few seconds to simulate progress
    const statusUpdates = [
        { time: 2, status: 'Setting up browser controller...', progress: 20 },
        { time: 4, status: 'Analyzing research objectives...', progress: 30 },
        { time: 6, status: 'Browsing source websites...', progress: 40 },
        { time: 10, status: 'Extracting content from sources...', progress: 60 },
        { time: 15, status: 'Analyzing extracted content...', progress: 70 },
        { time: 20, status: 'Identifying key points...', progress: 80 },
        { time: 25, status: 'Creating content connections...', progress: 90 },
        { time: 30, status: 'Generating final report...', progress: 95 }
    ];
    
    const statusTimers = [];
    
    statusUpdates.forEach(update => {
        const timer = setTimeout(() => {
            if (progressBar) progressBar.style.width = `${update.progress}%`;
            if (currentStatus) currentStatus.textContent = update.status;
        }, update.time * 1000);
        statusTimers.push(timer);
    });
    
    // Call the API to execute the research
    fetch('/api/research/execute', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            task_id: taskId,
            objective: task.objective,
            sources: task.sources,
            depth: task.depth
        })
    })
    .then(response => response.json())
    .then(data => {
        // Clear all timers
        clearInterval(timer);
        statusTimers.forEach(t => clearTimeout(t));
        
        if (data.error) {
            if (currentStatus) currentStatus.textContent = 'Error: ' + data.error;
            if (progressBar) {
                progressBar.style.width = '100%';
                progressBar.classList.remove('bg-info', 'progress-bar-animated');
                progressBar.classList.add('bg-danger');
            }
            setTimeout(() => {
                alert('Error executing research: ' + data.error);
                // Re-enable form
                if (researchForm) {
                    Array.from(researchForm.elements).forEach(element => {
                        element.disabled = false;
                    });
                }
                if (progressCard) progressCard.style.display = 'none';
            }, 1000);
            return;
        }
        
        // Update UI to show completion
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.classList.remove('progress-bar-animated');
        }
        if (currentStatus) currentStatus.textContent = 'Research completed successfully!';
        
        // Redirect to results page
        setTimeout(() => {
            window.location.href = `/results?task_id=${taskId}`;
        }, 1500);
    })
    .catch(error => {
        console.error('Error:', error);
        
        // Clear all timers
        clearInterval(timer);
        statusTimers.forEach(t => clearTimeout(t));
        
        // Show error state
        if (currentStatus) currentStatus.textContent = 'Error: Failed to execute research';
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.classList.remove('bg-info', 'progress-bar-animated');
            progressBar.classList.add('bg-danger');
        }
        
        setTimeout(() => {
            alert('Error executing research. Please try again.');
            // Re-enable form
            if (researchForm) {
                Array.from(researchForm.elements).forEach(element => {
                    element.disabled = false;
                });
            }
            if (progressCard) progressCard.style.display = 'none';
        }, 1000);
    });
}

/**
 * Setup handlers for the results page
 */
function setupResultsPage() {
    const taskIdElement = document.getElementById('taskId');
    if (!taskIdElement) return; // Not on the results page
    
    const taskId = taskIdElement.textContent.replace('Task ID: ', '').trim();
    
    // Load mock results (in a real app, we would fetch from the server)
    const mockResults = {
        task_id: taskId,
        objective: "Confronto framework cybersecurity UE 2018-2023",
        findings: [
            {
                source: "https://www.enisa.europa.eu/topics/cybersecurity-policy/",
                metadata: {
                    title: "EU Cybersecurity Policy",
                    author: "ENISA",
                    date: "2022-05-15",
                    url: "https://www.enisa.europa.eu/topics/cybersecurity-policy/",
                    content_type: "text"
                },
                key_points: [
                    {
                        text: "The NIS2 Directive significantly enhances the cybersecurity framework established by its predecessor.",
                        confidence: 0.92
                    },
                    {
                        text: "EU cybersecurity frameworks now include more sectors and impose stricter reporting requirements.",
                        confidence: 0.87
                    },
                    {
                        text: "Between 2018 and 2023, the EU has adopted a more comprehensive risk-based approach to cybersecurity.",
                        confidence: 0.79
                    }
                ],
                summary: "The EU cybersecurity policy landscape has evolved significantly since 2018, with the introduction of the NIS2 Directive and a stronger focus on critical infrastructure protection.",
                confidence: 0.88
            },
            {
                source: "https://digital-strategy.ec.europa.eu/en/policies/cybersecurity",
                metadata: {
                    title: "Cybersecurity Policies",
                    author: "European Commission",
                    date: "2023-02-10",
                    url: "https://digital-strategy.ec.europa.eu/en/policies/cybersecurity",
                    content_type: "text"
                },
                key_points: [
                    {
                        text: "The EU Cybersecurity Act of 2019 created a permanent mandate for ENISA and established a certification framework.",
                        confidence: 0.94
                    },
                    {
                        text: "The EU Cybersecurity Strategy for the Digital Decade was adopted in December 2020.",
                        confidence: 0.91
                    },
                    {
                        text: "Funding for cybersecurity research and innovation has increased by 300% between 2018 and 2023.",
                        confidence: 0.85
                    }
                ],
                summary: "The European Commission has significantly expanded its cybersecurity policy framework between 2018 and 2023, introducing new legislation and increasing funding for research and innovation.",
                confidence: 0.93
            },
            {
                source: "https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2017)614643",
                metadata: {
                    title: "Evolution of EU Cybersecurity Framework",
                    author: "European Parliament Think Tank",
                    date: "2021-11-30",
                    url: "https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2017)614643",
                    content_type: "text"
                },
                key_points: [
                    {
                        text: "The 2018 framework focused primarily on critical infrastructure, while the 2023 approach extends to all businesses of medium size and larger.",
                        confidence: 0.89
                    },
                    {
                        text: "Penalties for non-compliance have increased significantly, with fines up to €10 million or 2% of global turnover by 2023.",
                        confidence: 0.86
                    },
                    {
                        text: "Cross-border cooperation mechanisms have been formalized and strengthened between 2018 and 2023.",
                        confidence: 0.82
                    }
                ],
                summary: "The European Parliament has analyzed the evolution of the EU cybersecurity framework, documenting a shift from a sector-specific approach to a comprehensive framework with stronger enforcement mechanisms.",
                confidence: 0.84
            }
        ],
        connections: [
            {
                source: "https://www.enisa.europa.eu/topics/cybersecurity-policy/",
                target: "https://digital-strategy.ec.europa.eu/en/policies/cybersecurity",
                relation: "supporto",
                strength: 0.85,
                description: "Both sources confirm the expansion of the EU cybersecurity framework and increased scope of regulated entities."
            },
            {
                source: "https://digital-strategy.ec.europa.eu/en/policies/cybersecurity",
                target: "https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2017)614643",
                relation: "supporto",
                strength: 0.78,
                description: "Both sources document the significant increase in penalties and enforcement mechanisms for cybersecurity compliance."
            }
        ],
        timestamp: "2023-11-20T14:30:45",
        status: "completed"
    };

    // Display results
    displayResults(mockResults);
}

/**
 * Display research results in the UI
 */
function displayResults(results) {
    // Basic information
    document.getElementById('objectiveText').textContent = results.objective;
    document.getElementById('sourcesCount').textContent = results.findings.length;
    
    // Count total key points
    let totalKeyPoints = 0;
    results.findings.forEach(finding => {
        totalKeyPoints += finding.key_points.length;
    });
    document.getElementById('keyPointsCount').textContent = totalKeyPoints;
    document.getElementById('connectionsCount').textContent = results.connections.length;
    
    // Confidence chart
    const ctx = document.getElementById('confidenceChart').getContext('2d');
    const confidenceScores = results.findings.map(f => ({
        label: new URL(f.source).hostname.replace('www.', ''),
        value: f.confidence
    }));
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: confidenceScores.map(c => c.label),
            datasets: [{
                label: 'Confidence Score',
                data: confidenceScores.map(c => c.value),
                backgroundColor: 'rgba(23, 162, 184, 0.6)',
                borderColor: 'rgb(23, 162, 184)',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1.0
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
    
    // Display findings
    const findingsContainer = document.getElementById('findingsContainer');
    const findingTemplate = document.getElementById('findingTemplate');
    const keyPointTemplate = document.getElementById('keyPointTemplate');
    
    if (findingsContainer && findingTemplate && keyPointTemplate) {
        findingsContainer.innerHTML = '';
        
        results.findings.forEach(finding => {
            const findingElement = findingTemplate.content.cloneNode(true);
            
            // Set finding details
            findingElement.querySelector('.finding-title').textContent = finding.metadata.title;
            findingElement.querySelector('.finding-confidence').textContent = `Confidence: ${(finding.confidence * 100).toFixed(0)}%`;
            findingElement.querySelector('.finding-source').textContent = `Source: ${new URL(finding.source).hostname}`;
            
            // Format and display date if available
            if (finding.metadata.date) {
                const date = new Date(finding.metadata.date);
                findingElement.querySelector('.finding-date').textContent = `Date: ${date.toLocaleDateString()}`;
            } else {
                findingElement.querySelector('.finding-date').style.display = 'none';
            }
            
            // Display author if available
            if (finding.metadata.author) {
                findingElement.querySelector('.finding-author').textContent = `Author: ${finding.metadata.author}`;
            } else {
                findingElement.querySelector('.finding-author').style.display = 'none';
            }
            
            // Set summary
            findingElement.querySelector('.finding-summary').textContent = finding.summary;
            
            // Add key points
            const keyPointsList = findingElement.querySelector('.finding-key-points');
            finding.key_points.forEach(keyPoint => {
                const keyPointElement = keyPointTemplate.content.cloneNode(true);
                keyPointElement.querySelector('.key-point-text').textContent = keyPoint.text;
                keyPointElement.querySelector('.key-point-confidence').textContent = `${(keyPoint.confidence * 100).toFixed(0)}%`;
                keyPointsList.appendChild(keyPointElement);
            });
            
            findingsContainer.appendChild(findingElement);
        });
    }
    
    // Display connections
    const connectionsContainer = document.getElementById('connectionsContainer');
    const connectionTemplate = document.getElementById('connectionTemplate');
    
    if (connectionsContainer && connectionTemplate) {
        connectionsContainer.innerHTML = '';
        
        if (results.connections.length === 0) {
            connectionsContainer.innerHTML = `
                <div class="alert alert-info">
                    No significant connections were identified between the sources.
                </div>
            `;
            return;
        }
        
        results.connections.forEach(connection => {
            const connectionElement = connectionTemplate.content.cloneNode(true);
            
            // Set connection attributes
            const connectionCard = connectionElement.querySelector('.connection-card');
            connectionCard.setAttribute('data-relation', connection.relation);
            
            // Set connection details
            connectionElement.querySelector('.connection-relation').textContent = `Relationship: ${connection.relation.charAt(0).toUpperCase() + connection.relation.slice(1)}`;
            connectionElement.querySelector('.connection-strength').textContent = `Strength: ${(connection.strength * 100).toFixed(0)}%`;
            
            // Set source and target
            const sourceUrl = new URL(connection.source);
            const targetUrl = new URL(connection.target);
            connectionElement.querySelector('.connection-source').textContent = sourceUrl.hostname.replace('www.', '');
            connectionElement.querySelector('.connection-target').textContent = targetUrl.hostname.replace('www.', '');
            
            // Set description
            connectionElement.querySelector('.connection-description').textContent = connection.description;
            
            connectionsContainer.appendChild(connectionElement);
        });
        
        // Initialize Feather icons again for the new elements
        feather.replace();
    }
    
    // Set up export buttons
    document.getElementById('exportJson')?.addEventListener('click', () => {
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(results, null, 2));
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", `research_${results.task_id}.json`);
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    });
    
    document.getElementById('exportCsv')?.addEventListener('click', () => {
        // Generate CSV for findings
        let csv = 'Source,Title,Confidence,Summary\n';
        
        results.findings.forEach(finding => {
            const row = [
                `"${finding.source}"`,
                `"${finding.metadata.title}"`,
                finding.confidence,
                `"${finding.summary.replace(/"/g, '""')}"`
            ];
            csv += row.join(',') + '\n';
        });
        
        const dataStr = "data:text/csv;charset=utf-8," + encodeURIComponent(csv);
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", `research_${results.task_id}.csv`);
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    });
}
