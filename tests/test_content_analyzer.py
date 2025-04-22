import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from content_analyzer import ContentAnalyzer
from models import ContentMetadata, ContentFinding, KeyPoint


class TestContentAnalyzer(unittest.TestCase):
    """Tests for the ContentAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = ContentAnalyzer()
        self.test_text = """
        EU Cybersecurity Framework Evolution
        By John Smith
        January 15, 2022
        
        The European Union has significantly strengthened its cybersecurity framework between 2018 and 2023.
        
        One of the most important changes was the introduction of the NIS2 Directive, which expanded the scope of regulated entities.
        
        The penalties for non-compliance have increased dramatically, with fines reaching up to €10 million or 2% of global turnover.
        
        Cross-border cooperation mechanisms have been formalized and strengthened to ensure consistent implementation across member states.
        
        References:
        1. European Commission (2020). Cybersecurity Strategy for the Digital Decade.
        2. ENISA (2021). Threat Landscape Report.
        """
        self.test_url = "https://example.eu/cybersecurity-framework"
    
    def test_extract_metadata_new(self):
        """Test extracting metadata from content without existing metadata."""
        metadata = self.analyzer.extract_metadata(self.test_text, self.test_url)
        
        # Check that metadata was properly extracted
        self.assertEqual(metadata.title, "EU Cybersecurity Framework Evolution")
        self.assertEqual(metadata.author, "John Smith")
        self.assertEqual(metadata.url, self.test_url)
        self.assertEqual(metadata.content_type, "text")
        
        # Check that date was parsed correctly
        self.assertIsNotNone(metadata.date)
        if metadata.date:
            self.assertEqual(metadata.date.year, 2022)
            self.assertEqual(metadata.date.month, 1)
            self.assertEqual(metadata.date.day, 15)
    
    def test_extract_metadata_existing(self):
        """Test enhancing existing metadata."""
        existing_metadata = ContentMetadata(
            title="Old Title",
            url=self.test_url,
            content_type="text"
        )
        
        metadata = self.analyzer.extract_metadata(self.test_text, self.test_url, existing_metadata)
        
        # Title should not be overwritten since it was already set
        self.assertEqual(metadata.title, "Old Title")
        
        # Author and date should be extracted
        self.assertEqual(metadata.author, "John Smith")
        self.assertIsNotNone(metadata.date)
    
    def test_identify_key_points(self):
        """Test the identify_key_points method."""
        key_points = self.analyzer.identify_key_points(self.test_text)
        
        # Should extract 3 key points by default
        self.assertEqual(len(key_points), 3)
        
        # Check that the key points are KeyPoint objects
        for point in key_points:
            self.assertIsInstance(point, KeyPoint)
            self.assertTrue(point.text)
            self.assertTrue(0.0 <= point.confidence <= 1.0)
        
        # Test with custom count
        key_points = self.analyzer.identify_key_points(self.test_text, count=2)
        self.assertEqual(len(key_points), 2)
    
    def test_is_key_point_candidate(self):
        """Test the _is_key_point_candidate method."""
        # Short sentences should not be candidates
        short_sentence = "This is short."
        self.assertFalse(self.analyzer._is_key_point_candidate(short_sentence))
        
        # Very long sentences should not be candidates
        long_sentence = "This is a very long sentence. " * 10
        self.assertFalse(self.analyzer._is_key_point_candidate(long_sentence))
        
        # Sentences with indicators should be candidates
        indicator_sentence = "The most important feature of the framework is its scope."
        self.assertTrue(self.analyzer._is_key_point_candidate(indicator_sentence))
        
        # Sentences with percentages should be candidates
        percentage_sentence = "Compliance increased by 25% after implementation."
        self.assertTrue(self.analyzer._is_key_point_candidate(percentage_sentence))
    
    def test_generate_summary(self):
        """Test the generate_summary method."""
        summary = self.analyzer.generate_summary(self.test_text)
        
        # Summary should not be empty
        self.assertTrue(summary)
        
        # Summary should respect word limit
        self.assertLessEqual(len(summary.split()), 50)
        
        # Test with custom word limit
        summary = self.analyzer.generate_summary(self.test_text, max_words=20)
        self.assertLessEqual(len(summary.split()), 20)
    
    def test_calculate_content_confidence(self):
        """Test the calculate_content_confidence method."""
        metadata = ContentMetadata(
            title="EU Cybersecurity Framework",
            author="John Smith",
            date=datetime.now(),
            url="https://europa.eu/cybersecurity",
            content_type="text"
        )
        
        confidence = self.analyzer.calculate_content_confidence(self.test_text, metadata)
        
        # Confidence should be between 0 and 1
        self.assertTrue(0.0 <= confidence <= 1.0)
        
        # Check factors that should increase confidence
        # 1. Credible domain
        self.assertGreater(
            self.analyzer.calculate_content_confidence(self.test_text, metadata),
            self.analyzer.calculate_content_confidence(self.test_text, ContentMetadata(url="https://example.com"))
        )
        
        # 2. Content with references
        text_with_references = self.test_text + "\n\nReferences\n1. Test reference"
        self.assertGreater(
            self.analyzer.calculate_content_confidence(text_with_references, metadata),
            self.analyzer.calculate_content_confidence("Short text with no references", metadata)
        )
    
    def test_analyze_content(self):
        """Test the analyze_content method."""
        finding = self.analyzer.analyze_content(self.test_url, self.test_text)
        
        # Check that the finding is properly structured
        self.assertIsInstance(finding, ContentFinding)
        self.assertEqual(finding.source, self.test_url)
        self.assertIsNotNone(finding.metadata)
        self.assertTrue(finding.key_points)
        self.assertIsNotNone(finding.summary)
        self.assertTrue(0.0 <= finding.confidence <= 1.0)
        self.assertEqual(finding.raw_content, self.test_text)
        
        # Test with empty content
        empty_finding = self.analyzer.analyze_content(self.test_url, "")
        self.assertEqual(empty_finding.confidence, 0.0)
        self.assertFalse(empty_finding.key_points)
        self.assertEqual(empty_finding.source, self.test_url)


if __name__ == '__main__':
    unittest.main()
