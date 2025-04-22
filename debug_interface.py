
from flask import Flask, render_template_string, jsonify
import logging
from orchestrator import ResearchOrchestrator
import json
import os
from datetime import datetime

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Template HTML
DEBUG_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Debug Interface</title>
    <style>
        body { font-family: sans-serif; margin: 20px; }
        .error { color: red; }
        .success { color: green; }
        pre { background: #f4f4f4; padding: 10px; }
        .card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>Debug Interface</h1>
    
    <div class="card">
        <h2>Test Query</h2>
        <form id="queryForm">
            <textarea name="query" rows="4" style="width: 100%">Come è cambiata la regolamentazione UE sulla cybersecurity dal 2018 al 2023?</textarea>
            <button type="submit">Esegui Ricerca</button>
        </form>
    </div>

    <div class="card">
        <h2>Stato Sistema</h2>
        <pre id="systemStatus">{{ system_status | tojson(indent=2) }}</pre>
    </div>

    <div class="card">
        <h2>Ultimi Documenti</h2>
        <pre id="documents">{{ documents | tojson(indent=2) }}</pre>
    </div>

    <script>
        document.getElementById('queryForm').onsubmit = async (e) => {
            e.preventDefault();
            const query = e.target.query.value;
            
            try {
                const response = await fetch('/execute_research', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query})
                });
                
                const result = await response.json();
                alert(result.message);
                location.reload();
            } catch (error) {
                alert('Errore: ' + error);
            }
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    # Get system status
    orchestrator = ResearchOrchestrator()
    system_status = {
        'active_research': orchestrator.list_active_research()
    }
    
    # Get recent documents
    documents = []
    if os.path.exists('documents'):
        for filename in os.listdir('documents'):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join('documents', filename)) as f:
                        doc = json.load(f)
                        documents.append(doc)
                except Exception as e:
                    logger.error(f"Error loading document {filename}: {str(e)}")
    
    return render_template_string(
        DEBUG_TEMPLATE,
        system_status=system_status,
        documents=documents
    )

@app.route('/execute_research', methods=['POST'])
def execute_research():
    from flask import request
    import asyncio
    
    query = request.json.get('query')
    if not query:
        return jsonify({'error': 'Query mancante'}), 400
    
    try:
        orchestrator = ResearchOrchestrator()
        document = asyncio.run(orchestrator.execute_research_workflow(query))
        
        return jsonify({
            'message': f'Ricerca completata. Document ID: {document.document_id}',
            'document_id': document.document_id
        })
    except Exception as e:
        logger.error(f"Error in research execution: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
