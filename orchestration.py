import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from prefect.deployments import Deployment
from research_system import ResearchSystem, ResearchPlan, ContentFinding

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
async def create_research_plan_task(query: str) -> ResearchPlan:
    """Task to create a research plan."""
    log = get_run_logger()
    log.info(f"Creating research plan for: {query}")
    
    system = ResearchSystem()
    plan = await system.create_research_plan(query)
    
    log.info(f"Research plan created with {len(plan.questions)} questions")
    return plan

@task
async def execute_web_research_task(plan: ResearchPlan) -> List[ContentFinding]:
    """Task to execute web research."""
    log = get_run_logger()
    log.info(f"Executing web research for plan with {len(plan.questions)} questions")
    
    system = ResearchSystem()
    try:
        await system.initialize_browser()
        findings = await system.execute_web_research(plan)
        log.info(f"Web research completed with {len(findings)} findings")
        return findings
    finally:
        await system.close_browser()

@task
async def validate_findings_task(findings: List[ContentFinding]) -> List[ContentFinding]:
    """Task to validate findings."""
    log = get_run_logger()
    log.info(f"Validating {len(findings)} findings")
    
    system = ResearchSystem()
    validated = await system.validate_findings(findings)
    
    log.info(f"Validation complete: {len(validated)} valid findings")
    return validated

@task
async def generate_output_task(plan: ResearchPlan, findings: List[ContentFinding]) -> Dict[str, Any]:
    """Task to generate the final output."""
    log = get_run_logger()
    log.info(f"Generating final output for {len(findings)} findings")
    
    system = ResearchSystem()
    output = await system.generate_output(plan, findings)
    
    log.info(f"Output generated with summary length: {len(output.summary)}")
    return output.dict()

@flow(name="Research Flow")
async def research_flow(query: str) -> Dict[str, Any]:
    """Main research flow."""
    log = get_run_logger()
    log.info(f"Starting research flow for query: {query}")
    
    # Execute tasks in sequence
    plan = await create_research_plan_task(query)
    findings = await execute_web_research_task(plan)
    validated_findings = await validate_findings_task(findings)
    output = await generate_output_task(plan, validated_findings)
    
    log.info("Research flow completed successfully")
    return output

# Create a deployment of the research flow (for scheduling and UI)
def create_deployment():
    deployment = Deployment.build_from_flow(
        flow=research_flow,
        name="scheduled-research",
        version="1.0",
        work_queue_name="research",
        schedule=None,  # Can be configured for scheduled execution
    )
    deployment.apply()
    
    logger.info("Deployment created successfully")
    return deployment

async def run_research_ad_hoc(query: str) -> Dict[str, Any]:
    """Run research flow directly (ad-hoc)."""
    logger.info(f"Running ad-hoc research for: {query}")
    result = await research_flow(query)
    return result

if __name__ == "__main__":
    # Example usage
    query = "How has EU cybersecurity regulation evolved from 2018 to 2023?"
    result = asyncio.run(run_research_ad_hoc(query))
    print(f"Research completed. Output: {result}")

    # Uncomment to create a deployment
    # create_deployment()