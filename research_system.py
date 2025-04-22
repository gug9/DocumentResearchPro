import logging
import asyncio
import os
from typing import List, Dict, Any, Optional

from langchain.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
import google.generativeai as genai
from playwright.async_api import async_playwright
from prefect import flow, task
import streamlit as st
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define data models
class ResearchQuestion(BaseModel):
    """Model representing a research question."""
    question: str
    sources: List[str] = Field(default_factory=list, min_items=0, max_items=5)
    importance: int = Field(ge=1, le=5, description="Importance level (1-5)")

class ResearchPlan(BaseModel):
    """Model representing a structured research plan."""
    objective: str
    questions: List[ResearchQuestion] = Field(min_items=1, max_items=10)
    depth: int = Field(ge=1, le=3, description="1=superficial, 3=deep")

class ContentMetadata(BaseModel):
    """Model representing metadata for extracted content."""
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    content_type: Optional[str] = None

class KeyPoint(BaseModel):
    """Model representing a key point extracted from content."""
    text: str
    confidence: float = Field(ge=0.0, le=1.0)

class ContentFinding(BaseModel):
    """Model representing findings from a single source."""
    source: str
    metadata: ContentMetadata
    key_points: List[KeyPoint] = Field(default_factory=list)
    summary: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    raw_content: Optional[str] = None

class ResearchOutput(BaseModel):
    """Model representing the complete output of a research task."""
    objective: str
    findings: List[ContentFinding] = Field(default_factory=list)
    summary: str
    created_at: str


class ResearchSystem:
    def __init__(self):
        """Initialize the research system components."""
        # Initialize DeepSeek Local components via Ollama
        self.planner = ChatOllama(model="deepseek-coder:instruct")
        self.validator = ChatOllama(model="deepseek-coder:instruct")
        self.generator = ChatOllama(model="deepseek-coder:instruct")
        
        # Initialize Google Gemini components
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.research_engine = genai.GenerativeModel(
                model_name="gemini-1.5-pro",
                generation_config={
                    "temperature": 0.4,
                    "top_p": 0.95,
                    "top_k": 40,
                },
                safety_settings={
                    "HARASSMENT": "BLOCK_NONE",
                    "HATE_SPEECH": "BLOCK_NONE"
                }
            )
        else:
            logger.warning("GEMINI_API_KEY not found. Gemini functionality will be disabled.")
            self.research_engine = None
            
        # Initialize infrastructure components
        self.browser = None
        self.plan_parser = PydanticOutputParser(pydantic_object=ResearchPlan)
        
    async def initialize_browser(self):
        """Initialize the browser controller."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        logger.info("Browser initialized")
        
    async def close_browser(self):
        """Close the browser controller."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")
        
    @task
    async def create_research_plan(self, query: str) -> ResearchPlan:
        """Create a structured research plan from a user query."""
        logger.info(f"Creating research plan for: {query}")
        
        # Define the prompt for planning
        planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a research planning system that creates a structured plan.
            Given a research query, create a detailed plan with specific questions and potential sources.
            The output should follow the specified JSON schema."""),
            ("human", f"Research query: {query}\n\nCreate a research plan for this query. {self.plan_parser.get_format_instructions()}")
        ])
        
        # Generate the plan using DeepSeek via Ollama
        plan_chain = planning_prompt | self.planner | self.plan_parser
        research_plan = await plan_chain.ainvoke({})
        
        return research_plan
    
    @task
    async def execute_web_research(self, plan: ResearchPlan) -> List[ContentFinding]:
        """Execute web research based on the research plan."""
        if not self.browser:
            await self.initialize_browser()
            
        findings = []
        
        # Collect content from each source in the plan
        for question in plan.questions:
            for source in question.sources:
                logger.info(f"Researching: {source}")
                
                try:
                    # Navigate to the page
                    page = await self.context.new_page()
                    await page.goto(source, wait_until="networkidle", timeout=30000)
                    
                    # Extract content
                    page_content = await page.content()
                    page_title = await page.title()
                    
                    # Use Gemini for content analysis if available
                    if self.research_engine:
                        try:
                            gemini_response = self.research_engine.generate_content([
                                "Extract the key information from this webpage content relevant to the following question. "
                                f"Question: {question.question}\n\n"
                                f"Content: {page_content[:50000]}",  # Limit content length
                            ])
                            
                            analysis = gemini_response.text
                            
                            # Create metadata
                            metadata = ContentMetadata(
                                title=page_title,
                                url=source,
                                content_type="text"
                            )
                            
                            # Extract key points (simplified version)
                            key_points = [
                                KeyPoint(text=point.strip(), confidence=0.8)
                                for point in analysis.split("\n\n")[:3] if point.strip()
                            ]
                            
                            # Create finding
                            finding = ContentFinding(
                                source=source,
                                metadata=metadata,
                                key_points=key_points,
                                summary=analysis[:500],  # Truncate summary
                                confidence=0.8,
                                raw_content=page_content[:5000]  # Truncate raw content
                            )
                            
                            findings.append(finding)
                            
                        except Exception as e:
                            logger.error(f"Error analyzing content with Gemini: {str(e)}")
                    
                    await page.close()
                    
                except Exception as e:
                    logger.error(f"Error researching {source}: {str(e)}")
                    
        return findings
    
    @task
    async def validate_findings(self, findings: List[ContentFinding]) -> List[ContentFinding]:
        """Validate the research findings."""
        validated_findings = []
        
        for finding in findings:
            # Simple validation check (can be expanded)
            if finding.metadata and finding.key_points and len(finding.key_points) > 0:
                validated_findings.append(finding)
                
        return validated_findings
    
    @task
    async def generate_output(self, plan: ResearchPlan, findings: List[ContentFinding]) -> ResearchOutput:
        """Generate the final research output."""
        from datetime import datetime
        
        # Compile summaries
        summaries = [f.summary for f in findings if f.summary]
        combined_summary = "\n\n".join(summaries)
        
        # Generate an integrated summary using DeepSeek
        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a research synthesis expert. Create a comprehensive summary from the collected findings."),
            ("human", f"Research objective: {plan.objective}\n\nFindings:\n{combined_summary}\n\nCreate a comprehensive summary.")
        ])
        
        summary_chain = summary_prompt | self.generator
        result = await summary_chain.ainvoke({})
        
        # Create the output
        output = ResearchOutput(
            objective=plan.objective,
            findings=findings,
            summary=result.content,
            created_at=datetime.now().isoformat()
        )
        
        return output
    
    @flow
    async def execute_task(self, query: str) -> ResearchOutput:
        """Execute the complete research task."""
        try:
            # Create research plan
            plan = await self.create_research_plan(query)
            
            # Execute research
            findings = await self.execute_web_research(plan)
            
            # Validate findings
            validated = await self.validate_findings(findings)
            
            # Generate output
            output = await self.generate_output(plan, validated)
            
            return output
            
        finally:
            # Clean up
            await self.close_browser()


# Example usage - async main function
async def main():
    query = "How has EU cybersecurity regulation evolved from 2018 to 2023?"
    system = ResearchSystem()
    
    result = await system.execute_task(query)
    print(f"Research completed. Generated a summary of {len(result.summary)} characters with {len(result.findings)} sources.")


if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())