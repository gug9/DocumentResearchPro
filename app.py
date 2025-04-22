import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List

from flask import Flask, render_template, request, jsonify, session
import traceback

from models import ResearchTask
from planner import ResearchPlanner
from browser_controller import BrowserController
from content_analyzer import ContentAnalyzer
from validators import ContentValidator
from utils import save_research_output, identify_connections

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize components
planner = ResearchPlanner()
browser_controller = None  # Will be initialized for each research task
content_analyzer = ContentAnalyzer()
content_validator = ContentValidator()


@app.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')


@app.route('/api/research/plan', methods=['POST'])
def create_research_plan():
    """
    Create a research plan based on a user prompt.
    
    Expected JSON body:
    {
        "prompt": "User research prompt"
    }
    """
    try:
        data = request.json
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
            
        # Generate research plan
        research_plan = planner.create_research_plan(prompt)
        
        return jsonify({
            "plan": research_plan.dict(),
            "message": "Research plan created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating research plan: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/start', methods=['POST'])
def start_research():
    """
    Start a research task based on a user prompt.
    
    Expected JSON body:
    {
        "prompt": "User research prompt"
    }
    
    Returns a task ID and initial plan.
    """
    try:
        data = request.json
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
            
        # Create a research task
        research_task = planner.create_research_task(prompt)
        
        # Store task ID in session for later reference
        session['task_id'] = str(research_task.task_id)
        
        # Return task details and plan
        return jsonify({
            "task_id": str(research_task.task_id),
            "task": research_task.dict(),
            "message": "Research task started"
        })
        
    except Exception as e:
        logger.error(f"Error starting research: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/execute', methods=['POST'])
def execute_research():
    """
    Execute a research task.
    
    Expected JSON body:
    {
        "task_id": "UUID of research task",
        "sources": ["url1", "url2", ...],
        "depth": 1-3
    }
    
    If task_id is not provided, uses the task ID from the session.
    If sources is not provided, uses the sources from the original task.
    """
    try:
        data = request.json
        
        # Get task ID from request or session
        task_id = data.get('task_id') or session.get('task_id')
        if not task_id:
            return jsonify({"error": "No task ID provided"}), 400
            
        # Create or update task
        sources = data.get('sources', [])
        depth = data.get('depth', 1)
        objective = data.get('objective', "Research task")
        
        task = ResearchTask(
            task_id=task_id,
            objective=objective,
            sources=sources,
            depth=depth,
            status="in_progress"
        )
        
        # Execute research asynchronously
        result = asyncio.run(execute_research_task(task))
        
        # Save results
        file_path = save_research_output(result)
        
        return jsonify({
            "task_id": task_id,
            "result": result,
            "file_path": file_path,
            "message": "Research completed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error executing research: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/results/<task_id>')
def get_research_results(task_id):
    """
    Get results for a research task.
    
    Args:
        task_id: The ID of the research task
    """
    try:
        # In a real implementation, this would load results from storage
        # For this demo, we'll return a placeholder
        return jsonify({
            "task_id": task_id,
            "message": "Results retrieval not implemented in this demo"
        })
        
    except Exception as e:
        logger.error(f"Error getting research results: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/results')
def results_page():
    """Render the results page."""
    # Check if there's a result file path in the query parameters
    task_id = request.args.get('task_id') or session.get('task_id')
    
    if not task_id:
        return render_template('results.html', has_results=False)
    
    # In a real implementation, this would load and display results
    return render_template('results.html', has_results=True, task_id=task_id)


async def execute_research_task(task: ResearchTask) -> Dict[str, Any]:
    """
    Execute a research task using the browser controller.
    
    Args:
        task: The research task to execute
        
    Returns:
        Dictionary with research results
    """
    logger.info(f"Executing research task: {task.task_id}")
    
    # Initialize browser controller
    global browser_controller
    if browser_controller is None:
        browser_controller = BrowserController()
        await browser_controller.initialize()
    
    try:
        # Browse and collect data
        browse_results = await browser_controller.browse(task)
        
        # Process findings
        findings = []
        for finding_data in browse_results.get("findings", []):
            source = finding_data.get("source", "")
            content = finding_data.get("content", "")
            metadata = finding_data.get("metadata", {})
            
            # Analyze content
            finding = content_analyzer.analyze_content(source, content, metadata)
            findings.append(finding.dict())
        
        # Validate findings
        valid_findings, invalid_findings = content_validator.validate_findings(
            [finding for finding in findings if finding.get("confidence", 0) >= 0.4]
        )
        
        # Identify connections between findings
        connections = identify_connections(valid_findings)
        
        # Create output structure
        output = {
            "task_id": str(task.task_id),
            "objective": task.objective,
            "findings": valid_findings,
            "invalid_findings": invalid_findings,
            "connections": connections,
            "errors": browse_results.get("errors", []),
            "timestamp": datetime.now().isoformat(),
            "status": "completed"
        }
        
        return output
        
    except Exception as e:
        logger.error(f"Error in research execution: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "task_id": str(task.task_id),
            "objective": task.objective,
            "findings": [],
            "connections": [],
            "errors": [{"error": str(e)}],
            "timestamp": datetime.now().isoformat(),
            "status": "error"
        }
    finally:
        # Don't close the browser controller here to allow reuse
        pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
