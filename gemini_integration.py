import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
import google.generativeai as genai
from google.ai.generativelanguage import Content
from PIL import Image
import base64
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiIntegration:
    """Integration with Google's Gemini Pro models."""
    
    #def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-pro"):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemma-3-27b-it"):
        """Initialize the Gemini integration."""
        # Use provided API key or environment variable
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("No Gemini API key provided. Functionality will be limited.")
            self.model = None
            return
            
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Set up model
        self.model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": 0.4,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            },
            safety_settings={
                "HARASSMENT": "BLOCK_NONE",
                "HATE_SPEECH": "BLOCK_NONE"
            }
        )
        
        logger.info(f"Initialized Gemini integration with model: {model_name}")
        
    async def generate_text(self, prompt: str) -> Dict[str, Any]:
        """Generate text from a prompt."""
        if not self.model:
            return {
                "error": "Gemini API not configured.",
                "response": None,
                "model": "gemini"
            }
            
        try:
            # Use asyncio to run in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            return f"Error: {str(e)}"
            
    async def extract_content_from_html(self, html_content: str, objective: str) -> Dict[str, Any]:
        """Extract relevant content from HTML based on research objective."""
        if not self.model:
            return {"error": "Gemini API not configured."}
            
        try:
            prompt = f"""
            You are a web research assistant tasked with extracting relevant information from HTML content.
            Please analyze the following HTML content and extract information that is relevant to this research objective:
            
            OBJECTIVE: {objective}
            
            Extract the following:
            1. Main title of the page
            2. Author information if available
            3. Publication date if available
            4. The most relevant paragraphs related to the research objective
            5. Key points (maximum 5) related to the research objective
            
            For your analysis, ignore navigation menus, advertisements, footers, and other irrelevant elements.
            Format your response as clearly separated sections.
            
            HTML CONTENT:
            {html_content[:50000]}  # Limiting content length
            """
            
            # Use asyncio to run in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )
            
            # Process the response text into a structured format
            text_response = response.text
            
            # Simple parsing of the text response into sections
            sections = text_response.split("\n\n")
            
            # Extract key information
            title = ""
            author = ""
            date = ""
            content = ""
            key_points = []
            
            for section in sections:
                if section.startswith("1. Main title"):
                    title = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("2. Author"):
                    author = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("3. Publication date"):
                    date = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("4. Most relevant paragraphs"):
                    content = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("5. Key points"):
                    points_text = section.split(":", 1)[1].strip() if ":" in section else ""
                    # Extract individual points
                    for point in points_text.split("\n"):
                        if point.strip() and ("-" in point or "•" in point or any(f"{i}." in point for i in range(1, 6))):
                            # Remove bullet points or numbers
                            clean_point = point.strip()
                            for prefix in ["-", "•", "1.", "2.", "3.", "4.", "5."]:
                                if clean_point.startswith(prefix):
                                    clean_point = clean_point[len(prefix):].strip()
                            key_points.append({"text": clean_point, "confidence": 0.8})
            
            return {
                "title": title,
                "author": author,
                "date": date,
                "content": content,
                "key_points": key_points
            }
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return {"error": str(e)}
            
    async def analyze_image(self, image_data: Union[bytes, str, Image.Image], prompt: str) -> str:
        """Analyze an image with a specific prompt."""
        if not self.model:
            return "Error: Gemini API not configured."
            
        try:
            # Prepare the image for the model
            if isinstance(image_data, str):
                # If it's a base64 string
                if image_data.startswith("data:image"):
                    # Extract the base64 data after the comma
                    image_data = image_data.split(",", 1)[1]
                # Decode base64 to bytes
                image_bytes = base64.b64decode(image_data)
                img = Image.open(io.BytesIO(image_bytes))
            elif isinstance(image_data, bytes):
                # If it's already bytes
                img = Image.open(io.BytesIO(image_data))
            elif isinstance(image_data, Image.Image):
                # If it's already a PIL Image
                img = image_data
            else:
                return "Error: Unsupported image format."
                
            # Use asyncio to run in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content([prompt, img])
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            return f"Error: {str(e)}"
            
    async def research_topic(self, topic: str, depth: int = 2) -> Dict[str, Any]:
        """Research a topic and provide structured information."""
        if not self.model:
            return {"error": "Gemini API not configured."}
            
        try:
            depth_desc = {
                1: "basic overview with fundamental information",
                2: "detailed analysis with important context and key developments",
                3: "comprehensive research with in-depth analysis and multiple perspectives"
            }.get(depth, "detailed analysis")
            
            prompt = f"""
            You are a research assistant tasked with providing a {depth_desc} on the following topic:
            
            TOPIC: {topic}
            
            Please provide:
            1. A clear definition or explanation of the topic
            2. Key aspects or components of the topic
            3. Historical context or development (if relevant)
            4. Current state or latest developments
            5. Different perspectives or approaches (if relevant)
            6. Practical applications or implications
            7. Recommendations for further research
            8. Suggested reliable sources for further information
            
            Structure your response with clear headings and organized information.
            Depth level: {depth}/3
            """
            
            # Use asyncio to run in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )
            
            # Process the response
            sections = response.text.split("\n\n")
            
            # Extract key components
            overview = sections[0] if sections else ""
            
            # Extract potential sources
            sources = []
            for section in sections:
                if any(keyword in section.lower() for keyword in ["source", "reference", "further reading"]):
                    # Extract URLs
                    import re
                    urls = re.findall(r'https?://[^\s\)]+', section)
                    sources.extend(urls)
            
            return {
                "topic": topic,
                "depth": depth,
                "overview": overview,
                "content": response.text,
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"Error researching topic: {str(e)}")
            return {"error": str(e)}
            
    async def analyze_pdf_content(self, pdf_text: str, objective: str) -> Dict[str, Any]:
        """Analyze extracted PDF text content based on research objective."""
        if not self.model:
            return {"error": "Gemini API not configured."}
            
        try:
            prompt = f"""
            You are a research assistant tasked with analyzing PDF document content.
            Please analyze the following extracted text from a PDF and extract information that is relevant to this research objective:
            
            OBJECTIVE: {objective}
            
            Extract the following:
            1. Title or main topic of the document
            2. Author information if available
            3. Publication details if available
            4. The most relevant sections related to the research objective
            5. Key findings or insights (maximum 5) related to the research objective
            6. Statistical information or data points if relevant
            
            Format your response as clearly separated sections.
            
            PDF CONTENT:
            {pdf_text[:50000]}  # Limiting content length
            """
            
            # Use asyncio to run in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )
            
            # Process the response text into a structured format
            text_response = response.text
            
            # Parse sections similar to HTML extraction
            sections = text_response.split("\n\n")
            
            # Extract key information
            title = ""
            author = ""
            publication = ""
            content = ""
            key_findings = []
            stats = []
            
            for section in sections:
                if section.startswith("1. Title"):
                    title = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("2. Author"):
                    author = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("3. Publication"):
                    publication = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("4. Relevant sections"):
                    content = section.split(":", 1)[1].strip() if ":" in section else ""
                elif section.startswith("5. Key findings"):
                    findings_text = section.split(":", 1)[1].strip() if ":" in section else ""
                    # Extract individual findings
                    for finding in findings_text.split("\n"):
                        if finding.strip() and ("-" in finding or "•" in finding or any(f"{i}." in finding for i in range(1, 6))):
                            # Remove bullet points or numbers
                            clean_finding = finding.strip()
                            for prefix in ["-", "•", "1.", "2.", "3.", "4.", "5."]:
                                if clean_finding.startswith(prefix):
                                    clean_finding = clean_finding[len(prefix):].strip()
                            key_findings.append({"text": clean_finding, "confidence": 0.8})
                elif section.startswith("6. Statistical"):
                    stats_text = section.split(":", 1)[1].strip() if ":" in section else ""
                    # Extract individual stats
                    for stat in stats_text.split("\n"):
                        if stat.strip():
                            stats.append(stat.strip())
            
            return {
                "title": title,
                "author": author,
                "publication": publication,
                "content": content,
                "key_findings": key_findings,
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"Error analyzing PDF content: {str(e)}")
            return {"error": str(e)}


# Example usage
async def test_gemini():
    # Get API key from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment. Test will fail.")
        return
        
    # Initialize Gemini integration
    gemini = GeminiIntegration(api_key=api_key)
    
    # Test text generation
    result = await gemini.generate_text("Explain the importance of cybersecurity in three sentences.")
    print(f"Text generation result: {result}")
    
    # Test topic research
    research = await gemini.research_topic("EU Cybersecurity Framework", depth=1)
    print(f"Research topic result: {research.get('overview', '')[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_gemini())