import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

from models import ContentFinding, ContentMetadata, KeyPoint

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """
    Analyzer for content extracted from web pages.
    
    This module is responsible for:
    1. Extracting metadata from content
    2. Identifying key points in text
    3. Generating summaries
    4. Calculating confidence scores
    """
    
    def __init__(self):
        """Initialize the ContentAnalyzer."""
        logger.debug("Initializing ContentAnalyzer")
    
    def extract_metadata(self, text: str, url: str, existing_metadata: Optional[ContentMetadata] = None) -> ContentMetadata:
        """
        Extract or enhance metadata from content.
        
        Args:
            text: The text content to analyze
            url: The source URL
            existing_metadata: Optional existing metadata to enhance
            
        Returns:
            ContentMetadata object with extracted information
        """
        logger.debug(f"Extracting metadata from content from {url}")
        
        # Start with existing metadata or create new
        metadata = existing_metadata or ContentMetadata(url=url)
        
        # Extract title if not already present
        if not metadata.title or metadata.title == "Error extracting content":
            # Try to find a title pattern
            title_match = re.search(r'^(.+?)(?:\n|$)', text)
            if title_match:
                metadata.title = title_match.group(1).strip()
            
            # Limit title length
            if metadata.title and len(metadata.title) > 100:
                metadata.title = metadata.title[:97] + "..."
        
        # Extract date if not already present
        if not metadata.date:
            # Look for common date patterns
            date_patterns = [
                r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',  # DD/MM/YYYY or similar
                r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})\b',  # DD Month YYYY
                r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{2,4})\b',  # Month DD, YYYY
                r'\b(\d{4}-\d{2}-\d{2})\b'  # YYYY-MM-DD
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, text, re.IGNORECASE)
                if date_match:
                    try:
                        date_str = date_match.group(1)
                        # Simplified handling - in a real app, we'd use a more robust date parser
                        metadata.date = datetime.strptime(date_str, "%Y-%m-%d")
                    except (ValueError, TypeError):
                        # If parsing fails, just continue
                        pass
                    
                    if metadata.date:
                        break
        
        # Extract author if not already present
        if not metadata.author:
            # Look for common author patterns
            author_patterns = [
                r'(?:By|Author|Written by)[:\s]+([A-Z][a-zA-Z\s\-.]+)',
                r'@([a-zA-Z0-9_]+)'  # Social media handle
            ]
            
            for pattern in author_patterns:
                author_match = re.search(pattern, text)
                if author_match:
                    metadata.author = author_match.group(1).strip()
                    break
        
        # Ensure content_type is set
        if not metadata.content_type:
            metadata.content_type = "text"
        
        return metadata
    
    def _is_key_point_candidate(self, sentence: str) -> bool:
        """
        Determine if a sentence is likely to be a key point.
        
        Args:
            sentence: The sentence to evaluate
            
        Returns:
            Boolean indicating if the sentence is a key point candidate
        """
        # Sentences that are too short are usually not key points
        if len(sentence.split()) < 5:
            return False
            
        # Sentences that are too long are usually not concise key points
        if len(sentence.split()) > 50:
            return False
            
        # Sentences with certain markers are more likely to be key points
        indicators = [
            "important", "significant", "key", "main", "critical", "essential", 
            "crucial", "primary", "major", "fundamental", "vital"
        ]
        
        for indicator in indicators:
            if indicator in sentence.lower():
                return True
                
        # Check for numerical information which often indicates key statistics
        if re.search(r'\b\d+(?:\.\d+)?%\b', sentence):  # Percentage
            return True
            
        if re.search(r'\b(?:increased|decreased|grew|reduced) by\b', sentence.lower()):  # Change indicator
            return True
            
        # Default score based on sentence length (medium length sentences are preferred)
        words = sentence.split()
        return 10 <= len(words) <= 30
    
    def identify_key_points(self, text: str, count: int = 3) -> List[KeyPoint]:
        """
        Identify key points in the text.
        
        Args:
            text: The text to analyze
            count: Number of key points to extract
            
        Returns:
            List of KeyPoint objects
        """
        logger.debug(f"Identifying key points in content (target: {count})")
        
        # Split text into sentences
        # This is a simple splitter - a real implementation would use a more robust approach
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        key_points = []
        
        # Score each sentence based on key indicators
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if self._is_key_point_candidate(sentence):
                # Calculate a simple confidence score
                # In a real implementation, this would use NLP techniques
                words = sentence.split()
                length_factor = min(1.0, max(0.3, len(words) / 30))  # Prefer medium length sentences
                
                # Higher confidence for sentences with specific indicators
                confidence = 0.5 * length_factor
                
                # Boost confidence based on position (earlier in text)
                position_factor = 1.0 - (sentences.index(sentence) / len(sentences))
                confidence += 0.2 * position_factor
                
                # Boost confidence for sentences with key terms
                key_terms = ["framework", "cybersecurity", "policy", "regulation", "directive", 
                             "strategy", "implementation", "requirement", "compliance"]
                
                for term in key_terms:
                    if term in sentence.lower():
                        confidence += 0.05
                
                # Cap confidence at 1.0
                confidence = min(1.0, confidence)
                
                key_points.append(KeyPoint(text=sentence, confidence=confidence))
        
        # Sort by confidence and return top 'count'
        key_points.sort(key=lambda kp: kp.confidence, reverse=True)
        return key_points[:count]
    
    def generate_summary(self, text: str, max_words: int = 50) -> str:
        """
        Generate a short summary of the text.
        
        Args:
            text: The text to summarize
            max_words: Maximum number of words in the summary
            
        Returns:
            A summary string
        """
        logger.debug(f"Generating summary (max words: {max_words})")
        
        # This is a very simplified extractive summarization approach
        # A real implementation would use more sophisticated NLP techniques
        
        # Split text into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        if not sentences:
            return ""
            
        # Score sentences based on position, length and keywords
        scored_sentences = []
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Calculate score based on position (first sentences are more important)
            position_score = 1.0 - (i / len(sentences))
            
            # Calculate score based on length (medium length sentences are preferred)
            words = sentence.split()
            length_score = min(1.0, max(0.3, len(words) / 25))
            
            # Calculate score based on keywords
            keywords = ["framework", "cybersecurity", "policy", "key", "main", "important", 
                        "significant", "EU", "European", "directive", "regulation"]
                        
            keyword_score = 0.0
            for keyword in keywords:
                if keyword.lower() in sentence.lower():
                    keyword_score += 0.1
            
            # Combine scores
            total_score = (0.4 * position_score) + (0.3 * length_score) + (0.3 * min(1.0, keyword_score))
            
            scored_sentences.append((sentence, total_score))
        
        # Sort sentences by score
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        # Build summary by adding sentences until max_words is reached
        summary = []
        word_count = 0
        
        for sentence, _ in scored_sentences:
            sentence_words = sentence.split()
            if word_count + len(sentence_words) <= max_words:
                summary.append(sentence)
                word_count += len(sentence_words)
            else:
                break
        
        # If we couldn't build a summary, just truncate the text
        if not summary:
            words = text.split()
            return " ".join(words[:max_words])
        
        return " ".join(summary)
    
    def calculate_content_confidence(self, content: str, metadata: ContentMetadata) -> float:
        """
        Calculate a confidence score for the content quality.
        
        Args:
            content: The text content
            metadata: Content metadata
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        logger.debug("Calculating content confidence")
        
        if not content:
            return 0.0
            
        score = 0.5  # Start with a neutral score
        
        # Length factor: longer content generally has more information
        words = content.split()
        if len(words) < 50:
            score -= 0.2
        elif len(words) > 300:
            score += 0.1
        
        # Metadata completeness
        if metadata.title:
            score += 0.05
        if metadata.author:
            score += 0.05
        if metadata.date:
            score += 0.05
            
            # Recent content is preferred
            if metadata.date and metadata.date.year >= datetime.now().year - 3:
                score += 0.1
        
        # Domain credibility
        credible_domains = [
            "europa.eu", "enisa.europa.eu", "ec.europa.eu", "europarl.europa.eu",
            "gov", "edu", "org", "consilium.europa.eu"
        ]
        
        if metadata.url:
            for domain in credible_domains:
                if domain in metadata.url:
                    score += 0.15
                    break
        
        # Content quality indicators
        quality_indicators = [
            # References and sources
            r'\b(?:reference|bibliography|source|cite|cited)\b',
            # Tables, figures
            r'\btable\s+\d+|\bfigure\s+\d+',
            # Technical terms related to cybersecurity
            r'\b(?:cybersecurity|framework|directive|regulation|NIS|GDPR|ENISA)\b'
        ]
        
        for indicator in quality_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                score += 0.05
        
        # Cap the score between 0.0 and 1.0
        return max(0.0, min(1.0, score))
    
    def analyze_content(self, source: str, content: str, metadata: Optional[ContentMetadata] = None) -> ContentFinding:
        """
        Analyze content and create a ContentFinding.
        
        Args:
            source: The source URL
            content: The text content to analyze
            metadata: Optional existing metadata
            
        Returns:
            ContentFinding object with analysis results
        """
        logger.info(f"Analyzing content from: {source}")
        
        if not content:
            logger.warning(f"Empty content from source: {source}")
            return ContentFinding(
                source=source,
                metadata=ContentMetadata(url=source, content_type="error"),
                key_points=[],
                summary="No content available to analyze.",
                confidence=0.0
            )
        
        # Extract or enhance metadata
        enhanced_metadata = self.extract_metadata(content, source, metadata)
        
        # Identify key points (default 3)
        key_points = self.identify_key_points(content, count=3)
        
        # Generate summary
        summary = self.generate_summary(content, max_words=50)
        
        # Calculate confidence score
        confidence = self.calculate_content_confidence(content, enhanced_metadata)
        
        # Create the ContentFinding
        finding = ContentFinding(
            source=source,
            metadata=enhanced_metadata,
            key_points=key_points,
            summary=summary,
            confidence=confidence,
            raw_content=content[:10000] if content else None  # Limit raw content size
        )
        
        logger.debug(f"Content analysis complete for {source} (confidence: {confidence:.2f})")
        return finding
