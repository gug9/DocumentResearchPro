import logging
import os
import asyncio
from typing import Dict, Any, List
from pydantic import BaseModel
from langchain.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RicercaTask(BaseModel):
    """Task di ricerca da eseguire in parallelo."""
    id: str
    domanda: str
    priorita: int
    fonti_suggerite: List[str]

class DeepSeekPlanner:
    def __init__(self):
        try:
            self.model = ChatOllama(
                model="deepseek-r1:7b",
                temperature=0.3,
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            )
            self.available = True
        except Exception as e:
            logger.warning(f"Impossibile inizializzare DeepSeek: {str(e)}")
            self.available = False
            self.model = None

    async def crea_piano_ricerca(self, prompt_utente: str) -> List[RicercaTask]:
        """Genera task di ricerca paralleli basati sul prompt dell'utente."""
        system_prompt = """Sei un esperto pianificatore di ricerca. 
        Data una domanda in italiano, genera 3-5 task di ricerca paralleli
        che insieme forniscano una risposta completa. Per ogni task, specifica:
        - Una domanda specifica da ricercare
        - La priorità (1-5)
        - Fonti suggerite dove cercare (URL o tipi di fonti)"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Domanda: {prompt_utente}\nGenera i task di ricerca necessari.")
        ]

        response = await self.model.agenerate([messages])
        # Elabora la risposta e genera i task...
        return []  # TODO: Implementare la logica di parsing

class DeepSeekSynthesizer:
    def __init__(self):
        self.model = ChatOllama(
            model="deepseek-r1:7b",
            temperature=0.2,
            base_url="http://localhost:11434"
        )

    async def sintetizza_risultati(self, prompt_originale: str, risultati: List[Dict[str, Any]]) -> str:
        """Sintetizza i risultati delle ricerche in un documento strutturato."""
        system_prompt = """Sei un esperto di sintesi documentale.
        Analizza i risultati delle ricerche parallele e crea un documento
        strutturato in capitoli, mantenendo traccia delle fonti e
        verificando la coerenza delle informazioni."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Prompt originale: {prompt_originale}\nRisultati: {risultati}")
        ]

        response = await self.model.agenerate([messages])
        return response.generations[0][0].text


class DeepSeekModels:
    """Class to manage DeepSeek model configurations."""
    # Default model settings
    PLANNER = "deepseek-r1:7b"
    VALIDATOR = "deepseek-r1:7b"
    GENERATOR = "deepseek-r1:7b"
    
    @staticmethod
    def get_model_params(model_name: str, temperature: float = 0.3) -> Dict[str, Any]:
        """Get parameters for a specific model."""
        return {
            "model": model_name,
            "temperature": temperature,
            "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            "request_timeout": 120,
        }


class DeepSeekValidator:
    """DeepSeek-based content validator."""
    
    def __init__(self, model_name: str = DeepSeekModels.VALIDATOR, temperature: float = 0.1):
        """Initialize with a specific model."""
        self.chat_model = ChatOllama(**DeepSeekModels.get_model_params(model_name, temperature))
        logger.info(f"Initialized DeepSeekValidator with model: {model_name}")
        
    async def validate_content(self, content: str, criteria: List[str]) -> Tuple[bool, str]:
        """Validate content against specific criteria."""
        try:
            # Define the system message for validation
            system_message = SystemMessage(
                content="""You are a content validation system that evaluates text against specific criteria.
                For each content, determine if it meets the criteria and provide a brief explanation.
                Output a clear YES or NO decision followed by your reasoning."""
            )
            
            # Define the criteria as a formatted string
            criteria_text = "\n".join([f"- {c}" for c in criteria])
            
            # Define the human message with content and criteria
            human_message = HumanMessage(
                content=f"""Please validate the following content against these criteria:
                
                CRITERIA:
                {criteria_text}
                
                CONTENT:
                {content[:5000]}  # Limit content length
                
                Does this content meet the criteria? Respond with YES or NO followed by a brief explanation."""
            )
            
            # Create the prompt
            messages = [system_message, human_message]
            
            # Generate the validation
            response = await self.chat_model.agenerate([messages])
            response_text = response.generations[0][0].text
            
            # Parse the response
            is_valid = response_text.strip().upper().startswith("YES")
            explanation = response_text.strip()
            
            return is_valid, explanation
            
        except Exception as e:
            logger.error(f"Error validating content: {str(e)}")
            return False, f"Validation error: {str(e)}"

class DeepSeekGenerator:
    """DeepSeek-based document generator."""
    
    def __init__(self, model_name: str = DeepSeekModels.GENERATOR, temperature: float = 0.5):
        """Initialize with a specific model."""
        self.chat_model = ChatOllama(**DeepSeekModels.get_model_params(model_name, temperature))
        logger.info(f"Initialized DeepSeekGenerator with model: {model_name}")
        
    async def generate_summary(self, objective: str, findings: List[Dict[str, Any]]) -> str:
        """Generate a comprehensive summary from findings."""
        try:
            # Extract key information from findings
            summaries = []
            for i, finding in enumerate(findings):
                source = finding.get("source", "Unknown source")
                key_points = finding.get("key_points", [])
                key_points_text = "\n".join([f"  - {p.get('text', '')}" for p in key_points])
                
                summary = f"Source {i+1}: {source}\n{key_points_text}"
                summaries.append(summary)
                
            all_summaries = "\n\n".join(summaries)
            
            # Define the system message for summary generation
            system_message = SystemMessage(
                content="""You are a research synthesis expert. Create a comprehensive summary from the collected findings.
                Focus on creating a coherent narrative that addresses the research objective.
                Include key insights, patterns, and conclusions supported by the research.
                Organize the information logically and maintain academic rigor."""
            )
            
            # Define the human message with the objective and findings
            human_message = HumanMessage(
                content=f"""Research objective: {objective}
            
            Findings:
            {all_summaries[:10000]}  # Limit content length
            
            Create a comprehensive research summary that addresses the objective. 
            Structure your summary with clear sections and highlight the most important insights."""
            )
            
            # Create the prompt
            messages = [system_message, human_message]
            
            # Generate the summary
            response = await self.chat_model.agenerate([messages])
            response_text = response.generations[0][0].text
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Error generating summary: {str(e)}"
            
    async def generate_document(self, title: str, summary: str, findings: List[Dict[str, Any]]) -> str:
        """Generate a full research document."""
        try:
            # Extract sources for citations
            sources = [finding.get("source", "") for finding in findings]
            sources_text = "\n".join([f"- {s}" for s in sources])
            
            # Define the system message for document generation
            system_message = SystemMessage(
                content="""You are a document generation expert. Create a formal research document from the provided summary and findings.
                Include proper sections: Introduction, Methodology, Findings, Discussion, Conclusion, and References.
                The document should be well-structured and follow academic writing conventions."""
            )
            
            # Define the human message with content for the document
            human_message = HumanMessage(
                content=f"""Title: {title}
            
            Summary: 
            {summary}
            
            Sources:
            {sources_text}
            
            Generate a complete research document with proper sections and formatting. Include citations to the sources where appropriate."""
            )
            
            # Create the prompt
            messages = [system_message, human_message]
            
            # Generate the document
            response = await self.chat_model.agenerate([messages])
            response_text = response.generations[0][0].text
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating document: {str(e)}")
            return f"Error generating document: {str(e)}"

# Example usage (This section remains largely unchanged, but we'll adapt it slightly to use the new classes)
async def test_deepseek():
    # Test the planner
    from research_system import ResearchPlan # Assuming this import is still valid
    planner = DeepSeekPlanner()
    #parser = PydanticOutputParser(pydantic_object=ResearchPlan)  # This line might need adjustment depending on ResearchPlan
    #plan = await planner.create_plan("How has EU cybersecurity regulation evolved from 2018 to 2023?", parser)
    #print(f"Plan created with {len(plan.questions)} questions")

    # Test the validator
    validator = DeepSeekValidator()
    is_valid, explanation = await validator.validate_content(
        "The NIS2 Directive was adopted in 2022 as a key component of the EU's cybersecurity strategy.", 
        ["Contains factual information", "Relates to EU cybersecurity", "Mentions specific regulations"]
    )
    print(f"Content is valid: {is_valid} - {explanation}")
    
    # Test the synthesizer (new)
    synthesizer = DeepSeekSynthesizer()
    synthesized_result = await synthesizer.sintetizza_risultati(
        "Evolution of EU cybersecurity regulation",
        [{"source": "https://example.com", "key_points": [{"text": "NIS2 was adopted in 2022"}]}]
    )
    print(f"Synthesized result: {synthesized_result[:100]}...")
    
    # Test the generator
    generator = DeepSeekGenerator()
    summary = await generator.generate_summary(
        "Evolution of EU cybersecurity regulation",
        [{"source": "https://example.com", "key_points": [{"text": "NIS2 was adopted in 2022"}]}]
    )
    print(f"Summary generated: {summary[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_deepseek())