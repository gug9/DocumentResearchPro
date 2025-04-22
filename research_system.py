import logging
import asyncio
import os
import json
from typing import List, Dict, Any, Optional

from langchain_community.tools import DuckDuckGoSearchRun, WikipediaQueryRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper, WikipediaAPIWrapper

# Fix: Update to langchain_ollama to fix the deprecation warning
try:
    from langchain_ollama import ChatOllama
except ImportError:
    # Fallback if not installed
    from langchain_community.chat_models import ChatOllama
    logging.warning("Using deprecated ChatOllama from langchain_community. Please install langchain_ollama.")

from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
import google.generativeai as genai
from playwright.async_api import async_playwright
from prefect import flow, task
from prefect.tasks import NO_CACHE
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
        self.planner = ChatOllama(model="deepseek-r1:7b")
        self.validator = ChatOllama(model="deepseek-r1:7b")
        self.generator = ChatOllama(model="deepseek-r1:7b")

        # Initialize search tools
        self.search_tool = DuckDuckGoSearchRun(api_wrapper=DuckDuckGoSearchAPIWrapper())
        self.wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        
        # Initialize Google Gemini components
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.research_engine = genai.GenerativeModel(
                #model_name="gemini-1.5-pro",
                model_name="gemma-3-27b-it",
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
    
    async def perform_search(self, query: str) -> List[str]:
        """
        Esegue ricerche utilizzando tool di LangChain e restituisce risultati pertinenti.
        
        Args:
            query: La query di ricerca
            
        Returns:
            Lista di URL o testi pertinenti
        """
        logger.info(f"Performing search for: {query}")
        
        try:
            # Esegui ricerca con DuckDuckGo
            search_results = self.search_tool.run(query)
            
            # Esegui ricerca su Wikipedia
            wiki_results = self.wiki_tool.run(query)
            
            # Estrai URL dai risultati di DuckDuckGo
            # Il formato di output di DuckDuckGo è un testo con URL e snippet
            # Dobbiamo estrarre gli URL
            import re
            
            # Pattern regex per trovare URL
            url_pattern = re.compile(r'https?://[^\s\)]+')
            urls = url_pattern.findall(search_results)
            
            # Aggiungi una versione URL-friendly della query di Wikipedia
            urls.append(f"https://it.wikipedia.org/wiki/{query.replace(' ', '_')}")
            
            # Limita a massimo 5 URL
            return urls[:5]
            
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            # Fallback a un URL di ricerca base
            return [f"https://duckduckgo.com/?q={query.replace(' ', '+')}"]
        
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

    def fix_json_structure(self, json_data):
        """Fix common JSON structure issues from LLM responses."""
        try:
            if isinstance(json_data, str):
                # Try to parse the string as JSON
                json_data = json.loads(json_data)
            
            # Fix objective field if it's an object instead of a string
            if isinstance(json_data.get('objective'), dict) and 'title' in json_data['objective']:
                json_data['objective'] = json_data['objective']['title']
            
            # Fix depth field if it's an object instead of an int
            if isinstance(json_data.get('depth'), dict) and 'value' in json_data['depth']:
                json_data['depth'] = json_data['depth']['value']
            
            # Fix questions structure
            if 'questions' in json_data and isinstance(json_data['questions'], list):
                fixed_questions = []
                for q in json_data['questions']:
                    fixed_q = {}
                    
                    # Copy question text
                    if 'question' in q:
                        fixed_q['question'] = q['question']
                    
                    # Convert single source to list of sources
                    if 'source' in q and isinstance(q['source'], str):
                        fixed_q['sources'] = [q['source']]
                    elif 'sources' in q:
                        fixed_q['sources'] = q['sources']
                    else:
                        fixed_q['sources'] = []
                    
                    # Fix importance field if missing or if it's an object
                    if 'importance' not in q:
                        fixed_q['importance'] = 3  # Default importance
                    elif isinstance(q['importance'], dict) and 'value' in q['importance']:
                        fixed_q['importance'] = q['importance']['value']
                    else:
                        fixed_q['importance'] = q['importance']
                    
                    fixed_questions.append(fixed_q)
                
                json_data['questions'] = fixed_questions
            
            return json_data
        except Exception as e:
            logger.error(f"Error fixing JSON structure: {str(e)}")
            return json_data
        
    @task
    async def create_research_plan(self, query: str) -> ResearchPlan:
        """Create a structured research plan from a user query."""
        logger.info(f"Creating research plan for: {query}")
        
        # Define explicit format instructions - ESCAPE CURLY BRACES
        format_instructions = """
        La tua risposta deve essere un oggetto JSON valido con la seguente struttura:
        {{
        "objective": "L'obiettivo principale della ricerca come stringa",
        "questions": [
            {{
            "question": "Domanda di ricerca specifica e dettagliata",
            "importance": 3
            }}
        ],
        "depth": 2
        }}
        
        Note:
        - "objective" deve essere una semplice stringa che descrive l'obiettivo generale
        - "questions" deve essere un array di 3-5 domande ben formulate
        - Ogni domanda deve essere specifica, dettagliata e focalizzata su un aspetto particolare
        - Ogni domanda deve avere "question" e "importance" (intero da 1-5)
        - "depth" deve essere un intero da 1-3 (1=superficiale, 3=approfondita)
        - Non includere il campo "sources", verrà aggiunto automaticamente dal sistema
        """
        
        # Define the prompt for planning
        planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """Sei un esperto pianificatore di ricerche che crea piani strutturati.
            Data una query di ricerca, il tuo compito è sviluppare un piano dettagliato con domande specifiche.
            Le tue domande guideranno una ricerca approfondita su Internet.
            
            Rispondi in italiano e formula 3-5 domande chiave che:
            1. Coprino diversi aspetti rilevanti della query
            2. Siano sufficientemente specifiche da guidare una ricerca mirata
            3. Affrontino sia aspetti generali che dettagli specifici
            4. Si prestino a trovare informazioni fattuali e verificabili
            5. Siano formulate in modo neutrale e oggettivo
            
            IMPORTANTE: Non includere fonti o URL nel piano - le risorse verranno identificate automaticamente 
            in una fase successiva tramite un sistema di ricerca separato.
            """),
            ("human", f"Query di ricerca: {query}\n\nCrea un piano di ricerca per questa query con domande mirate. {format_instructions}")
        ])
        
        try:
            # Generate the plan using DeepSeek via Ollama - without parser
            plan_chain = planning_prompt | self.planner
            result = await plan_chain.ainvoke({})
            
            # Extract the JSON content from the response
            content = result.content
            
            # Look for JSON block in case the model wrapped it with other text
            json_match = None
            if "{" in content and "}" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                json_match = content[start:end]
            
            try:
                if json_match:
                    json_data = json.loads(json_match)
                else:
                    json_data = json.loads(content)
                
                # Fix common JSON structure issues
                fixed_json = self.fix_json_structure(json_data)
                
                # Per ogni domanda, aggiungiamo fonti basate sul risultato di ricerca
                if "questions" in fixed_json and isinstance(fixed_json["questions"], list):
                    for i, question in enumerate(fixed_json["questions"]):
                        # Genera una query di ricerca basata sulla domanda
                        search_query = f"{fixed_json['objective']} {question['question']}"
                        
                        # Esegui la ricerca effettiva
                        sources = await self.perform_search(search_query)
                        
                        # Aggiungi le fonti alla domanda
                        fixed_json["questions"][i]["sources"] = sources
                
                # Now try to parse with Pydantic
                research_plan = ResearchPlan(**fixed_json)
                logger.info("Successfully parsed research plan")
                return research_plan
                
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Error parsing research plan JSON: {str(e)}")
                logger.error(f"Raw response: {content}")
                
                # Create a simple fallback plan if there's an error
                fallback_sources = await self.perform_search(query)
                fallback_plan = ResearchPlan(
                    objective=query,
                    questions=[
                        ResearchQuestion(
                            question=query,
                            sources=fallback_sources,
                            importance=3
                        )
                    ],
                    depth=1
                )
                return fallback_plan
                
        except Exception as e:
            logger.error(f"Error creating research plan: {str(e)}")
            # Create a simple fallback plan if there's an error
            fallback_sources = await self.perform_search(query)
            fallback_plan = ResearchPlan(
                objective=query,
                questions=[
                    ResearchQuestion(
                        question=query,
                        sources=fallback_sources,
                        importance=3
                    )
                ],
                depth=1
            )
            return fallback_plan
    
    # Add NO_CACHE to tasks that use self or other non-serializable resources
    @task(cache_policy=NO_CACHE)
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
    
    @task(cache_policy=NO_CACHE)
    async def validate_findings(self, findings: List[ContentFinding]) -> List[ContentFinding]:
        """Validate the research findings."""
        validated_findings = []
        
        for finding in findings:
            # Simple validation check (can be expanded)
            if finding.metadata and finding.key_points and len(finding.key_points) > 0:
                validated_findings.append(finding)
                
        return validated_findings
    
    @task(cache_policy=NO_CACHE)
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
            
        except Exception as e:
            logger.error(f"Error running research task: {str(e)}")
            # Create a minimal error output
            from datetime import datetime
            return ResearchOutput(
                objective=query,
                findings=[],
                summary=f"Research could not be completed due to an error: {str(e)}",
                created_at=datetime.now().isoformat()
            )
        finally:
            # Clean up
            await self.close_browser()


# Example usage - async main function
async def main():
    query = "How has EU cybersecurity regulation evolved from 2018 to 2023?"
    system = ResearchSystem()
    
    try:
        result = await system.execute_task(query)
        print(f"Research completed. Generated a summary of {len(result.summary)} characters with {len(result.findings)} sources.")
    except Exception as e:
        print(f"Error running research task: {str(e)}")


if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())