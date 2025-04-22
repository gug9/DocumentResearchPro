import asyncio
import logging
import os
from datetime import datetime

from models import ResearchTask
from planner import ResearchPlanner
from browser_controller import BrowserController
from content_analyzer import ContentAnalyzer
from validators import ContentValidator
from utils import save_research_output, identify_connections, setup_logging
from app import app  # Import the Flask app for Gunicorn

# Configure logging
setup_logging("DEBUG")
logger = logging.getLogger(__name__)


async def main():
    """
    Main function to demonstrate the research workflow.
    """
    logger.info("Starting document research system")
    
    try:
        # Initialize components
        planner = ResearchPlanner()
        browser_controller = BrowserController()
        content_analyzer = ContentAnalyzer()
        content_validator = ContentValidator()
        
        # Example prompt
        prompt = "Confronto framework cybersecurity UE 2018-2023"
        logger.info(f"Processing research prompt: {prompt}")
        
        # Create research task
        task = planner.create_research_task(prompt)
        logger.info(f"Created task: {task.task_id}")
        logger.info(f"Research depth: {task.depth}")
        logger.info(f"Sources: {task.sources}")
        
        # Initialize browser
        await browser_controller.initialize()
        
        # Browse and collect data
        logger.info("Starting browsing and data collection")
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
            
            # Log key points
            logger.info(f"Key points from {source}:")
            for i, kp in enumerate(finding.key_points):
                logger.info(f"  {i+1}. {kp.text} (confidence: {kp.confidence:.2f})")
        
        # Validate findings
        valid_findings, invalid_findings = content_validator.validate_findings(
            [finding for finding in findings if finding.get("confidence", 0) >= 0.4]
        )
        
        # Identify connections
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
        
        # Save results
        file_path = save_research_output(output)
        logger.info(f"Research results saved to: {file_path}")
        
        # Print summary
        logger.info(f"Research complete. Found {len(valid_findings)} valid sources and {len(connections)} connections.")
        
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}", exc_info=True)
    finally:
        # Close browser
        if browser_controller:
            await browser_controller.close()


if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())
