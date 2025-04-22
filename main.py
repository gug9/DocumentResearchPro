"""
Main entry point for the Advanced Research System Flask application.
"""
import os
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app for compatibility with gunicorn
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "advanced-research-system-secret")

# Import components after Flask initialization
try:
    from research_system import ResearchSystem, ResearchPlan, ContentFinding, ResearchOutput
    research_initialized = True
except ImportError as e:
    logger.warning(f"Could not import research system components: {e}")
    research_initialized = False

# Check for API keys and display appropriate warnings
if os.environ.get("GEMINI_API_KEY"):
    logger.info("Gemini API key found in environment variables")
    gemini_api_configured = True
else:
    logger.warning("Gemini API key not found in environment variables")
    gemini_api_configured = False

# Global research system instance
research_system = None

def get_research_system():
    """Get or initialize the research system."""
    global research_system
    if research_system is None and research_initialized:
        try:
            research_system = ResearchSystem()
            logger.info("Research system initialized")
        except Exception as e:
            logger.error(f"Error initializing research system: {e}")
    return research_system

@app.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html', 
                          gemini_configured=gemini_api_configured)

@app.route('/api/create-plan', methods=['POST'])
async def create_research_plan():
    """Create a research plan based on a user prompt."""
    if not request.is_json:
        return jsonify({"error": "Expected JSON request"}), 400
    
    data = request.json
    prompt = data.get('prompt')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    system = get_research_system()
    if not system:
        return jsonify({"error": "Research system not initialized"}), 500
    
    try:
        # Run in an async executor
        plan = await system.create_research_plan(prompt)
        return jsonify({
            "plan": json.loads(plan.json())
        })
    except Exception as e:
        logger.error(f"Error creating research plan: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/start-research', methods=['POST'])
async def start_research():
    """Start a research task based on a user prompt."""
    if not request.is_json:
        return jsonify({"error": "Expected JSON request"}), 400
    
    data = request.json
    prompt = data.get('prompt')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    system = get_research_system()
    if not system:
        return jsonify({"error": "Research system not initialized"}), 500
    
    try:
        # Create a plan first
        plan = await system.create_research_plan(prompt)
        
        # Store plan in session
        session['plan'] = json.loads(plan.json())
        session['task_id'] = str(datetime.now().strftime("%Y%m%d_%H%M%S"))
        
        return jsonify({
            "task_id": session['task_id'],
            "plan": session['plan']
        })
    except Exception as e:
        logger.error(f"Error starting research: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/execute-research', methods=['POST'])
async def execute_research():
    """Execute a research task."""
    if not request.is_json:
        return jsonify({"error": "Expected JSON request"}), 400
    
    data = request.json
    task_id = data.get('task_id', session.get('task_id'))
    sources = data.get('sources')
    depth = data.get('depth', 2)
    
    if not task_id:
        return jsonify({"error": "No task ID provided"}), 400
    
    system = get_research_system()
    if not system:
        return jsonify({"error": "Research system not initialized"}), 500
    
    # Get plan from session or create a new one
    plan_dict = session.get('plan')
    if not plan_dict:
        return jsonify({"error": "No research plan in session"}), 400
    
    try:
        # Convert plan dict back to object
        plan = ResearchPlan(**plan_dict)
        
        # If sources were provided, update the plan
        if sources:
            for question in plan.questions:
                question.sources = sources
        
        # Update depth if provided
        if depth:
            plan.depth = depth
        
        # Execute research
        findings = await system.execute_web_research(plan)
        
        # Validate findings
        validated = await system.validate_findings(findings)
        
        # Generate output
        output = await system.generate_output(plan, validated)
        
        # Save results to file for later retrieval
        filename = f"research_results/{task_id}.json"
        os.makedirs("research_results", exist_ok=True)
        with open(filename, "w") as f:
            f.write(output.json())
        
        return jsonify({
            "task_id": task_id,
            "status": "completed",
            "result_path": filename
        })
    except Exception as e:
        logger.error(f"Error executing research: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/results/<task_id>')
def get_research_results(task_id):
    """Get results for a research task."""
    filename = f"research_results/{task_id}.json"
    
    try:
        with open(filename, "r") as f:
            results = json.load(f)
        return jsonify(results)
    except FileNotFoundError:
        return jsonify({"error": f"No results found for task {task_id}"}), 404
    except Exception as e:
        logger.error(f"Error retrieving results: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/results')
def results_page():
    """Render the results page."""
    task_id = request.args.get('task_id')
    if not task_id:
        return redirect(url_for('index'))
    
    return render_template('results.html', task_id=task_id)

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
    
    # Reinitialize research system
    global research_system
    research_system = None  # Will be reinitialized on next use
    
    return jsonify({"status": "API key set successfully"})

@app.errorhandler(404)
def page_not_found(e):
    # Return custom 404 page
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))