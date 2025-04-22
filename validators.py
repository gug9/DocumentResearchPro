import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from models import ContentFinding

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ContentValidator:
    """
    Validator for content quality and relevance.
    
    This module is responsible for:
    1. Validating content quality
    2. Verifying content relevance to research objectives
    3. Checking content freshness
    """
    
    def __init__(self):
        """Initialize the ContentValidator."""
        logger.debug("Initializing ContentValidator")
    
    def validate_content(self, content: str) -> bool:
        """
        Validate if content meets quality criteria.
        
        Args:
            content: The content to validate
            
        Returns:
            Boolean indicating if content passes validation
        """
        logger.debug("Validating content quality")
        
        if not content or len(content.strip()) < 100:
            logger.warning("Content validation failed: content too short")
            return False
            
        # Check for references section
        has_references = bool(re.search(r'\b(?:References|Bibliography|Sources|Citations)\b', content, re.IGNORECASE))
        
        # Check for minimum length
        has_sufficient_length = len(content.split()) > 300
        
        # Check for recency (mentions of recent years)
        current_year = datetime.now().year
        recent_years = [str(y) for y in range(current_year-5, current_year+1)]
        has_recent_content = any(year in content for year in recent_years)
        
        # Count passing checks
        checks_passed = sum([has_references, has_sufficient_length, has_recent_content])
        
        valid = checks_passed >= 2
        logger.debug(f"Content validation result: {valid} (passed {checks_passed}/3 checks)")
        
        return valid
    
    def extract_year(self, content: str) -> Optional[int]:
        """
        Extract the most recent year mentioned in content.
        
        Args:
            content: The content to analyze
            
        Returns:
            The most recent year mentioned, or None if no years found
        """
        # Extract years from text (assuming 4-digit format)
        year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', content)
        
        if not year_matches:
            return None
            
        # Convert to integers and find the most recent year
        years = [int(y) for y in year_matches]
        years.sort(reverse=True)
        
        # Sanity check - reject future years beyond next year
        current_year = datetime.now().year
        valid_years = [y for y in years if y <= current_year + 1]
        
        return valid_years[0] if valid_years else None
    
    def validate_findings(self, findings: List[ContentFinding], min_confidence: float = 0.5) -> Tuple[List[ContentFinding], List[ContentFinding]]:
        """
        Validate a list of findings and separate into valid and invalid.
        
        Args:
            findings: List of ContentFinding objects to validate
            min_confidence: Minimum confidence threshold
            
        Returns:
            Tuple of (valid_findings, invalid_findings)
        """
        logger.info(f"Validating {len(findings)} findings (min confidence: {min_confidence})")
        
        valid_findings = []
        invalid_findings = []
        
        for finding in findings:
            # Check minimum confidence
            if finding.confidence < min_confidence:
                logger.debug(f"Finding from {finding.source} rejected: low confidence ({finding.confidence:.2f})")
                invalid_findings.append(finding)
                continue
                
            # Check if it has key points
            if not finding.key_points:
                logger.debug(f"Finding from {finding.source} rejected: no key points")
                invalid_findings.append(finding)
                continue
                
            # Check content validity if raw_content is available
            if finding.raw_content and not self.validate_content(finding.raw_content):
                logger.debug(f"Finding from {finding.source} rejected: failed content validation")
                invalid_findings.append(finding)
                continue
                
            # Check recency if date is available
            if (finding.metadata.date and 
                finding.metadata.date.year < datetime.now().year - 5):
                logger.debug(f"Finding from {finding.source} rejected: too old ({finding.metadata.date.year})")
                invalid_findings.append(finding)
                continue
                
            # If it passed all checks, it's valid
            valid_findings.append(finding)
            logger.debug(f"Finding from {finding.source} accepted (confidence: {finding.confidence:.2f})")
        
        logger.info(f"Validation complete: {len(valid_findings)} valid, {len(invalid_findings)} invalid")
        return valid_findings, invalid_findings
    
    def intelligent_truncate(self, text: str, max_length: int) -> str:
        """
        Intelligently truncate text to a maximum length.
        
        Args:
            text: The text to truncate
            max_length: Maximum length in characters
            
        Returns:
            Truncated text
        """
        if not text or len(text) <= max_length:
            return text
            
        # Try to truncate at sentence boundary
        truncated = text[:max_length]
        last_sentence_end = max(
            truncated.rfind('.'), 
            truncated.rfind('!'), 
            truncated.rfind('?')
        )
        
        if last_sentence_end > max_length * 0.7:  # If we can keep at least 70% of the text
            return text[:last_sentence_end + 1] + '...'
            
        # Fallback to truncating at word boundary
        last_space = truncated.rfind(' ')
        if last_space > 0:
            return text[:last_space] + '...'
            
        # Last resort: hard truncation
        return truncated + '...'
