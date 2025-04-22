import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from playwright.async_api import Page, Response, Browser, BrowserContext
from models import ResearchTask, ContentMetadata
from browser_controller import BrowserController


class TestBrowserController(unittest.TestCase):
    """Tests for the BrowserController class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.browser_controller = BrowserController()
        
        # Create a test task
        self.test_task = ResearchTask(
            objective="Test research task",
            sources=["https://example.com"],
            depth=1,
            status="ready"
        )
    
    @patch('browser_controller.async_playwright')
    async def test_initialize(self, mock_playwright):
        """Test the initialize method."""
        # Setup mocks
        mock_playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
        
        mock_chromium = AsyncMock()
        mock_playwright_instance.chromium = mock_chromium
        
        mock_browser = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        
        mock_context = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        
        # Call the method
        await self.browser_controller.initialize()
        
        # Check that the browser was launched
        mock_playwright.return_value.start.assert_called_once()
        mock_chromium.launch.assert_called_once_with(headless=True)
        mock_browser.new_context.assert_called_once()
        
        # Check that the browser and context were saved
        self.assertEqual(self.browser_controller.browser, mock_browser)
        self.assertEqual(self.browser_controller.context, mock_context)
    
    async def test_close(self):
        """Test the close method."""
        # Setup mocks
        self.browser_controller.context = AsyncMock()
        self.browser_controller.browser = AsyncMock()
        
        # Call the method
        await self.browser_controller.close()
        
        # Check that close was called on both objects
        self.browser_controller.context.close.assert_called_once()
        self.browser_controller.browser.close.assert_called_once()
    
    @patch.object(BrowserController, 'initialize')
    async def test_open_url_success(self, mock_initialize):
        """Test the open_url method with a successful response."""
        # Setup mocks
        self.browser_controller.context = AsyncMock()
        mock_page = AsyncMock()
        self.browser_controller.context.new_page = AsyncMock(return_value=mock_page)
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_page.goto = AsyncMock(return_value=mock_response)
        
        # Call the method
        page, success = await self.browser_controller.open_url("https://example.com")
        
        # Check results
        self.assertEqual(page, mock_page)
        self.assertTrue(success)
        mock_page.goto.assert_called_once_with("https://example.com", wait_until='networkidle', timeout=30000)
    
    @patch.object(BrowserController, 'initialize')
    async def test_open_url_failure(self, mock_initialize):
        """Test the open_url method with a failed response."""
        # Setup mocks
        self.browser_controller.context = AsyncMock()
        mock_page = AsyncMock()
        self.browser_controller.context.new_page = AsyncMock(return_value=mock_page)
        
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_page.goto = AsyncMock(return_value=mock_response)
        
        # Call the method
        page, success = await self.browser_controller.open_url("https://example.com/notfound")
        
        # Check results
        self.assertIsNone(page)
        self.assertFalse(success)
        mock_page.close.assert_called_once()
    
    @patch.object(BrowserController, 'initialize')
    async def test_open_url_error(self, mock_initialize):
        """Test the open_url method with an exception."""
        # Setup mocks
        self.browser_controller.context = AsyncMock()
        mock_page = AsyncMock()
        self.browser_controller.context.new_page = AsyncMock(return_value=mock_page)
        
        mock_page.goto = AsyncMock(side_effect=Exception("Test error"))
        
        # Call the method
        page, success = await self.browser_controller.open_url("https://example.com")
        
        # Check results
        self.assertIsNone(page)
        self.assertFalse(success)
    
    async def test_search_text(self):
        """Test the search_text method."""
        # Setup mocks
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=["Sample text context"])
        
        # Call the method
        results = await self.browser_controller.search_text(mock_page, "sample")
        
        # Check results
        self.assertEqual(results, ["Sample text context"])
        mock_page.evaluate.assert_called_once()
    
    async def test_extract_content(self):
        """Test the extract_content method."""
        # Setup mocks
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(return_value="Test Title")
        mock_page.url = "https://example.com"
        mock_page.evaluate = AsyncMock(side_effect=[
            "Test Author",  # First call for author
            "2023-01-01",   # Second call for date
            "Test content"  # Third call as fallback if trafilatura fails
        ])
        mock_page.content = AsyncMock(return_value="<html><body>Test content</body></html>")
        
        # Patch trafilatura.extract to return None (forcing fallback)
        with patch('browser_controller.trafilatura.extract', return_value=None):
            # Call the method
            result = await self.browser_controller.extract_content(mock_page)
        
        # Check results
        self.assertIn("content", result)
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"].title, "Test Title")
        self.assertEqual(result["metadata"].author, "Test Author")
        self.assertEqual(result["metadata"].url, "https://example.com")
    
    @patch.object(BrowserController, 'initialize')
    @patch.object(BrowserController, 'open_url')
    @patch.object(BrowserController, 'extract_content')
    async def test_browse(self, mock_extract_content, mock_open_url, mock_initialize):
        """Test the browse method."""
        # Setup mocks
        mock_page = AsyncMock()
        mock_open_url.return_value = (mock_page, True)
        
        mock_extract_content.return_value = {
            "content": "Test content",
            "metadata": ContentMetadata(
                title="Test Title",
                url="https://example.com",
                content_type="text"
            )
        }
        
        # Call the method
        self.browser_controller.context = AsyncMock()  # Needed to avoid initialize call
        result = await self.browser_controller.browse(self.test_task)
        
        # Check results
        self.assertIn("task_id", result)
        self.assertIn("objective", result)
        self.assertIn("findings", result)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["source"], "https://example.com")
        self.assertEqual(result["findings"][0]["content"], "Test content")


if __name__ == '__main__':
    asyncio.run(unittest.main())
