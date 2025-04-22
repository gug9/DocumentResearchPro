import logging
import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO") -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    level = level_map.get(log_level.upper(), logging.INFO)
    
    # Configure the root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Logging configured with level: {log_level}")


def save_research_output(output: Dict[str, Any], directory: str = "research_results") -> str:
    """
    Save research output to a JSON file.
    
    Args:
        output: Research output data
        directory: Directory to save the file
        
    Returns:
        Path to the saved file
    """
    # Create directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create filename with timestamp and task ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = output.get("task_id", "unknown")
    filename = f"{timestamp}_{task_id}.json"
    file_path = os.path.join(directory, filename)
    
    # Save the file
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str)
    
    logger.info(f"Research output saved to {file_path}")
    return file_path


def load_research_output(file_path: str) -> Dict[str, Any]:
    """
    Load research output from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Research output data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Research output loaded from {file_path}")
        return data
    except Exception as e:
        logger.error(f"Error loading research output: {str(e)}")
        return {}


def identify_connections(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identify connections between different findings.
    
    Args:
        findings: List of content findings
        
    Returns:
        List of connection descriptions
    """
    logger.info(f"Identifying connections between {len(findings)} findings")
    
    connections = []
    
    # This is a simplified implementation
    # In a real-world scenario, this would use more sophisticated NLP techniques
    
    # Compare each pair of findings
    for i, finding1 in enumerate(findings):
        for j, finding2 in enumerate(findings):
            if i >= j:  # Skip self-comparisons and duplicates
                continue
                
            source1 = finding1.get("source", "")
            source2 = finding2.get("source", "")
            
            # Check for contradictions
            # This is a very simplified approach
            contradicting_terms = [
                ("increase", "decrease"),
                ("growth", "decline"),
                ("positive", "negative"),
                ("support", "oppose"),
                ("agree", "disagree"),
                ("benefit", "harm"),
                ("advantage", "disadvantage")
            ]
            
            content1 = finding1.get("summary", "") or ""
            content2 = finding2.get("summary", "") or ""
            
            # Check for contradictions
            for term1, term2 in contradicting_terms:
                if (term1 in content1.lower() and term2 in content2.lower()) or \
                   (term1 in content2.lower() and term2 in content1.lower()):
                    connections.append({
                        "source": source1,
                        "target": source2,
                        "relation": "contrasto",
                        "strength": 0.7,
                        "description": f"Contrasting views on {term1}/{term2}"
                    })
                    break
            
            # Check for support/reinforcement
            # Count common key terms as indicator of supporting information
            common_terms = set()
            for key_point1 in finding1.get("key_points", []):
                kp_text1 = key_point1.get("text", "").lower() if isinstance(key_point1, dict) else ""
                for key_point2 in finding2.get("key_points", []):
                    kp_text2 = key_point2.get("text", "").lower() if isinstance(key_point2, dict) else ""
                    
                    # Extract significant terms (nouns, proper nouns)
                    words1 = re.findall(r'\b[A-Za-z]{4,}\b', kp_text1)
                    words2 = re.findall(r'\b[A-Za-z]{4,}\b', kp_text2)
                    
                    # Find common significant terms
                    for word in words1:
                        if word in words2 and len(word) > 4:
                            common_terms.add(word)
            
            # If enough common terms, consider it a supporting connection
            if len(common_terms) >= 3:
                connections.append({
                    "source": source1,
                    "target": source2,
                    "relation": "supporto",
                    "strength": min(1.0, 0.4 + (len(common_terms) * 0.1)),
                    "description": f"Supporting information on: {', '.join(list(common_terms)[:3])}"
                })
    
    logger.info(f"Identified {len(connections)} connections")
    return connections


def get_browser_capabilities() -> Dict[str, bool]:
    """
    Check and return available browser capabilities.
    
    Returns:
        Dictionary of browser capabilities
    """
    capabilities = {
        "pdf_download": True,
        "javascript_execution": True,
        "table_extraction": True,
        "headless": True
    }
    
    # In a real implementation, this would check for actual dependencies
    # For this demonstration, we assume all capabilities are available
    
    logger.debug(f"Browser capabilities: {capabilities}")
    return capabilities


def extract_domain(url: str) -> str:
    """
    Extract the domain from a URL.
    
    Args:
        url: The URL to process
        
    Returns:
        Domain name
    """
    domain_pattern = re.compile(r'https?://(?:www\.)?([^/]+)')
    match = domain_pattern.search(url)
    
    if match:
        return match.group(1)
    return url


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string to be used as a filename.
    
    Args:
        filename: The string to sanitize
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    sanitized = re.sub(r'[\\/*?:"<>|]', '', filename)
    # Replace spaces and other characters with underscores
    sanitized = re.sub(r'[\s\t\n\r]+', '_', sanitized)
    # Limit length
    sanitized = sanitized[:100]
    
    return sanitized
