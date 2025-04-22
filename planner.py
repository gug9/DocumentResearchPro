import json
import logging
from typing import List, Dict, Any

from models import ResearchPlan, ResearchQuestion, ResearchTask

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ResearchPlanner:
    """
    Planner module that converts user prompts into structured research plans.
    
    This module is responsible for:
    1. Analyzing user prompts to identify key research areas
    2. Generating specific research questions
    3. Identifying reliable sources for each question
    4. Determining appropriate research depth
    """
    
    def __init__(self):
        """Initialize the ResearchPlanner."""
        logger.debug("Initializing ResearchPlanner")
    
    def _extract_topics(self, prompt: str) -> List[str]:
        """
        Extract main topics from the user prompt.
        
        Args:
            prompt: The user's research prompt
            
        Returns:
            A list of main topics identified in the prompt
        """
        # This is a simplified implementation
        # In a real-world scenario, this could use NLP techniques
        
        # Basic topic extraction based on common keywords
        topics = []
        prompt_lower = prompt.lower()
        
        # Example topic identification logic
        if "cybersecurity" in prompt_lower or "cyber security" in prompt_lower:
            topics.append("cybersecurity")
        
        if "framework" in prompt_lower:
            topics.append("frameworks")
            
        if "eu" in prompt_lower or "europe" in prompt_lower or "european" in prompt_lower:
            topics.append("european union")
            
        # Extract years if mentioned
        import re
        years = re.findall(r'\b20\d\d\b', prompt)
        if years:
            topics.append(f"years {'-'.join(years)}")
            
        # If no specific topics were identified, use generic approach
        if not topics:
            # Split by common punctuation and get longer phrases
            segments = re.split(r'[.,;:]', prompt)
            topics = [s.strip() for s in segments if len(s.strip()) > 15][:3]
            
        logger.debug(f"Extracted topics: {topics}")
        return topics
    
    def _generate_questions(self, topics: List[str], prompt: str) -> List[Dict[str, Any]]:
        """
        Generate research questions based on identified topics.
        
        Args:
            topics: List of identified topics
            prompt: Original user prompt
            
        Returns:
            List of questions with potential sources
        """
        questions = []
        
        # Generate questions based on the provided example
        if "cybersecurity" in topics or "frameworks" in topics:
            questions.append({
                "question": "What are the main cybersecurity frameworks adopted by the EU?",
                "sources": [
                    "https://www.enisa.europa.eu/topics/cybersecurity-policy/",
                    "https://digital-strategy.ec.europa.eu/en/policies/cybersecurity"
                ]
            })
            
            questions.append({
                "question": "How have EU cybersecurity frameworks evolved over time?",
                "sources": [
                    "https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2017)614643",
                    "https://www.consilium.europa.eu/en/policies/cybersecurity/"
                ]
            })
            
            questions.append({
                "question": "What are the key differences between current and previous EU cybersecurity frameworks?",
                "sources": [
                    "https://www.enisa.europa.eu/publications/",
                    "https://ec.europa.eu/digital-single-market/en/cybersecurity"
                ]
            })
        else:
            # Generic question generation based on the prompt
            # This is a simplified approach - in a real system, this would use more sophisticated NLP
            base_questions = [
                f"What are the main developments in {prompt}?",
                f"What are the key components of {prompt}?",
                f"How has {prompt} evolved in recent years?"
            ]
            
            for q in base_questions:
                questions.append({
                    "question": q,
                    "sources": [
                        f"https://scholar.google.com/scholar?q={'+'.join(q.split())}",
                        f"https://www.google.com/search?q={'+'.join(q.split())}"
                    ]
                })
                
        logger.debug(f"Generated {len(questions)} research questions")
        return questions
    
    def _determine_depth(self, prompt: str) -> int:
        """
        Determine the appropriate research depth based on the complexity of the prompt.
        
        Args:
            prompt: The user's research prompt
            
        Returns:
            Research depth level (1-3)
        """
        # Simple heuristic for depth determination
        words = prompt.split()
        
        if len(words) < 10:
            return 1  # Brief prompt suggests superficial research
        elif len(words) > 20 or "detailed" in prompt.lower() or "comprehensive" in prompt.lower():
            return 3  # Long or explicitly detailed prompt suggests deep research
        else:
            return 2  # Medium depth for average prompts
    
    def create_research_plan(self, prompt: str) -> ResearchPlan:
        """
        Create a structured research plan from a user prompt.
        
        Args:
            prompt: The user's research prompt
            
        Returns:
            A structured ResearchPlan object
        """
        logger.info(f"Creating research plan for prompt: {prompt}")
        
        # Extract topics from the prompt
        topics = self._extract_topics(prompt)
        
        # Generate research questions with potential sources
        question_data = self._generate_questions(topics, prompt)
        
        # Convert to ResearchQuestion objects
        questions = [
            ResearchQuestion(question=q["question"], sources=q["sources"])
            for q in question_data
        ]
        
        # Determine appropriate research depth
        depth = self._determine_depth(prompt)
        
        # Create and return the research plan
        plan = ResearchPlan(questions=questions, depth=depth)
        logger.info(f"Created research plan with {len(questions)} questions and depth {depth}")
        
        return plan
    
    def create_research_task(self, prompt: str) -> ResearchTask:
        """
        Create a research task from a user prompt.
        
        Args:
            prompt: The user's research prompt
            
        Returns:
            A ResearchTask object
        """
        # First create a research plan
        plan = self.create_research_plan(prompt)
        
        # Extract all sources from the plan
        sources = []
        for question in plan.questions:
            sources.extend(question.sources)
        
        # Remove duplicates while preserving order
        unique_sources = []
        for source in sources:
            if source not in unique_sources:
                unique_sources.append(source)
        
        # Create and return the research task
        task = ResearchTask(
            objective=prompt,
            sources=unique_sources[:5],  # Limit to top 5 sources
            depth=plan.depth,
            status="ready"
        )
        
        logger.info(f"Created research task with ID {task.task_id}")
        return task
