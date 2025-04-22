"""
Main entry point for the Advanced Research System Flask application.
"""
import os
import logging
import json
import asyncio
from datetime import datetime
from functools import wraps
from typing import Dict, Any, List, Optional, Union
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app for compatibility with gunicorn
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "advanced-research-system-secret")

# Import research system components
try:
    # Import adapter for model access
    from model_adapter import ModelAdapter
    
    # Import main components
    from planner import ResearchPlanner, ResearchPlan
    from executor import ResearchExecutor, ResearchTask
    from validator import ContentValidator
    from generator import DocumentGenerator
    from orchestrator import ResearchOrchestrator
    
    research_initialized = True
    logger.info("Research system components imported successfully")
except ImportError as e:
    logger.warning(f"Could not import research system components: {e}")
    research_initialized = False

# Check for Gemini API key
if os.environ.get("GEMINI_API_KEY"):
    logger.info("Gemini API key found in environment variables")
    gemini_api_configured = True
else:
    logger.warning("Gemini API key not found in environment variables")
    gemini_api_configured = False

# Global orchestrator instance
orchestrator = None

def get_orchestrator():
    """Get or initialize the research orchestrator."""
    global orchestrator
    if orchestrator is None and research_initialized:
        try:
            orchestrator = ResearchOrchestrator()
            logger.info("Research orchestrator initialized")
        except Exception as e:
            logger.error(f"Error initializing research orchestrator: {e}")
    return orchestrator

def async_route(f):
    """Decorator to handle async route functions."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@app.route('/')
def index():
    """Render the main application page."""
    # Check Ollama availability
    ollama_status = {"available": False}
    if research_initialized:
        try:
            model_adapter = ModelAdapter()
            ollama_status = model_adapter.check_ollama_installation()
        except Exception as e:
            logger.error(f"Error checking Ollama status: {e}")
    
    return render_template('index.html', 
                          gemini_configured=gemini_api_configured,
                          ollama_status=ollama_status)

@app.route('/api/check-system-status')
def check_system_status():
    """Check the status of the research system components."""
    if not research_initialized:
        return jsonify({
            "status": "error",
            "message": "Research system components not initialized",
            "gemini_configured": gemini_api_configured,
            "ollama_available": False
        })
    
    try:
        # Check status using the model adapter
        model_adapter = ModelAdapter()
        status = model_adapter.check_ollama_installation()
        
        return jsonify({
            "status": "ok",
            "gemini_configured": status["gemini_available"],
            "ollama_available": status["ollama_available"],
            "ollama_models": status["models_available"] if status["ollama_available"] else [],
            "deepseek_available": status["deepseek_available"] if status["ollama_available"] else False
        })
    except Exception as e:
        logger.error(f"Error checking system status: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "gemini_configured": gemini_api_configured
        })

@app.route('/api/create-plan', methods=['POST'])
def create_research_plan():
    """Create a research plan based on a user prompt."""
    if not request.is_json:
        return jsonify({"error": "Expected JSON request"}), 400
    
    data = request.json
    prompt = data.get('prompt')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    if not research_initialized:
        return jsonify({"error": "Research system not initialized"}), 500
    
    try:
        # Create plan
        planner = ResearchPlanner()
        plan = planner.create_research_plan(prompt)
        
        # Store in session (usando model_dump invece di json())
        session['plan'] = plan.model_dump()
        session['prompt'] = prompt
        
        return jsonify({
            "plan_id": plan.task_id,
            "plan": plan.model_dump()
        })
    except Exception as e:
        logger.error(f"Error creating research plan: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/start-research', methods=['POST'])
@async_route
async def start_research():
    """Start a complete research workflow based on a user prompt."""
    if not request.is_json:
        return jsonify({"error": "Expected JSON request"}), 400
    
    data = request.json
    prompt = data.get('prompt')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    orchestrator = get_orchestrator()
    if not orchestrator:
        return jsonify({"error": "Research orchestrator not initialized"}), 500
    
    try:
        # Start the workflow
        document = await orchestrator.execute_research_workflow(prompt)
        
        return jsonify({
            "status": "completed",
            "document_id": document.document_id,
            "title": document.metadata.title,
            "sections": len(document.sections),
            "word_count": document.metadata.word_count
        })
    except Exception as e:
        logger.error(f"Error executing research: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/research-status/<research_id>')
def get_research_status(research_id):
    """Get the status of a research workflow."""
    orchestrator = get_orchestrator()
    if not orchestrator:
        return jsonify({"error": "Research orchestrator not initialized"}), 500
    
    status = orchestrator.get_research_status(research_id)
    if "error" in status:
        return jsonify(status), 404
    
    return jsonify(status)

@app.route('/api/active-research')
def list_active_research():
    """List all active research workflows."""
    orchestrator = get_orchestrator()
    if not orchestrator:
        return jsonify({"error": "Research orchestrator not initialized"}), 500
    
    research_list = orchestrator.list_active_research()
    return jsonify({"research": research_list})

@app.route('/api/document/<document_id>')
def get_document(document_id):
    """Get a generated document."""
    try:
        with open(f"documents/{document_id}.json", "r") as f:
            document = json.load(f)
        return jsonify(document)
    except FileNotFoundError:
        return jsonify({"error": f"Document {document_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error retrieving document: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/document/<document_id>/markdown')
def get_document_markdown(document_id):
    """Get a document in markdown format."""
    try:
        with open(f"documents/{document_id}.md", "r") as f:
            markdown = f.read()
        
        return jsonify({
            "document_id": document_id,
            "markdown": markdown
        })
    except FileNotFoundError:
        return jsonify({"error": f"Document {document_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error retrieving document markdown: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/documents')
def list_documents():
    """List all available documents."""
    try:
        documents = []
        
        # Check if directory exists
        if not os.path.exists("documents"):
            return jsonify({"documents": []})
        
        # List JSON files
        for filename in os.listdir("documents"):
            if filename.endswith(".json"):
                document_id = filename[:-5]  # Remove .json extension
                try:
                    with open(f"documents/{filename}", "r") as f:
                        document = json.load(f)
                    
                    # Extract basic metadata
                    documents.append({
                        "document_id": document_id,
                        "title": document.get("metadata", {}).get("title", "Untitled"),
                        "created_at": document.get("generated_at", "Unknown"),
                        "word_count": document.get("metadata", {}).get("word_count", 0)
                    })
                except Exception as e:
                    logger.error(f"Error reading document {filename}: {e}")
        
        return jsonify({"documents": documents})
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/results')
def results_page():
    """Render the results page."""
    document_id = request.args.get('document_id')
    
    if not document_id:
        return redirect(url_for('index'))
    
    return render_template('results.html', document_id=document_id)

@app.route('/api/set-gemini-key', methods=['POST'])
def set_gemini_key():
    """Set the Gemini API key."""
    if not request.is_json:
        return jsonify({"error": "Expected JSON request"}), 400
    
    data = request.json
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({"error": "No API key provided"}), 400
    
    # Set in environment
    os.environ['GEMINI_API_KEY'] = api_key
    global gemini_api_configured
    gemini_api_configured = True
    
    # Reinitialize orchestrator
    global orchestrator
    orchestrator = None  # Will be reinitialized on next use
    
    return jsonify({"status": "API key set successfully"})

@app.errorhandler(404)
def page_not_found(e):
    # Return custom 404 page
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))