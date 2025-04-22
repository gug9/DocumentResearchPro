import logging
import asyncio
import os
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import trafilatura
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrowserConfig(BaseModel):
    """Configuration for the browser controller."""
    headless: bool = True
    timeout: int = 30000  # 30 seconds
    user_agent: Optional[str] = None
    viewport_width: int = 1280
    viewport_height: int = 800
    locale: str = "en-US"
    download_path: Optional[str] = None


class PlaywrightCluster:
    """Headless browser cluster for web scraping and content extraction using Playwright."""
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        """Initialize the browser controller."""
        self.config = config or BrowserConfig()
        self.playwright = None
        self.browser = None
        self.context = None
        self.download_path = self.config.download_path or tempfile.mkdtemp()
        os.makedirs(self.download_path, exist_ok=True)
        logger.info(f"Download path set to: {self.download_path}")
        
    async def initialize(self):
        """Initialize the browser cluster."""
        if self.browser:
            return  # Already initialized
            
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless
            )
            
            # Create a context with specified options
            self.context = await self.browser.new_context(
                viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height},
                locale=self.config.locale,
                user_agent=self.config.user_agent,
                accept_downloads=True
            )
            
            logger.info("Browser cluster initialized")
            
        except Exception as e:
            logger.error(f"Error initializing browser: {str(e)}")
            raise
    
    async def close(self):
        """Close the browser cluster."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.context = None
        self.browser = None
        self.playwright = None
        logger.info("Browser cluster closed")
    
    async def new_page(self) -> Page:
        """Create a new page in the browser context."""
        if not self.context:
            await self.initialize()
        return await self.context.new_page()
    
    async def navigate(self, url: str) -> Tuple[Optional[Page], bool]:
        """Navigate to a URL and return the page and success status."""
        try:
            page = await self.new_page()
            logger.info(f"Navigating to: {url}")
            
            response = await page.goto(
                url,
                wait_until="networkidle", 
                timeout=self.config.timeout
            )
            
            if not response or response.status >= 400:
                logger.warning(f"Failed to navigate to {url}: status code {response.status if response else 'unknown'}")
                await page.close()
                return None, False
                
            logger.info(f"Successfully navigated to {url}")
            return page, True
            
        except Exception as e:
            logger.error(f"Error navigating to {url}: {str(e)}")
            if 'page' in locals():
                await page.close()
            return None, False
    
    async def extract_content(self, page: Page) -> Dict[str, Any]:
        """Extract content from a page using trafilatura and Playwright."""
        try:
            # Get basic page information
            url = page.url
            title = await page.title()
            
            # Get the page HTML
            html = await page.content()
            
            # Extract main content using trafilatura
            extracted_text = trafilatura.extract(html)
            
            # Fallback to basic extraction if trafilatura fails
            if not extracted_text:
                logger.warning(f"Trafilatura extraction failed for {url}, using fallback extraction")
                extracted_text = await page.evaluate('''
                    () => {
                        // Simple content extraction script
                        const article = document.querySelector('article');
                        if (article) return article.innerText;
                        
                        // Fallback to main content areas
                        const content = document.querySelector('main, #content, .content, [role="main"]');
                        if (content) return content.innerText;
                        
                        // Fallback to body text, excluding common non-content elements
                        const body = document.body;
                        const elementsToRemove = [
                            'header', 'nav', 'aside', 'footer', 'script', 'style',
                            '[role="banner"]', '[role="navigation"]', '[role="complementary"]',
                            '[role="contentinfo"]', '.sidebar', '.navigation', '.menu', '.ad', '.ads'
                        ];
                        
                        // Create a clone of the body to manipulate
                        const clone = body.cloneNode(true);
                        
                        // Remove non-content elements
                        elementsToRemove.forEach(selector => {
                            const elements = clone.querySelectorAll(selector);
                            elements.forEach(el => el.remove());
                        });
                        
                        return clone.innerText;
                    }
                ''')
            
            # Try to extract author information
            author = await page.evaluate('''
                () => {
                    // Common author selectors
                    const authorSelectors = [
                        'meta[name="author"]',
                        'meta[property="article:author"]',
                        '.author', '.byline', '.article-author',
                        '[rel="author"]', '[itemprop="author"]'
                    ];
                    
                    for (const selector of authorSelectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            if (element.tagName === 'META') return element.getAttribute('content');
                            return element.textContent.trim();
                        }
                    }
                    
                    return null;
                }
            ''')
            
            # Try to extract date information
            date = await page.evaluate('''
                () => {
                    // Common date selectors
                    const dateSelectors = [
                        'meta[name="date"]',
                        'meta[property="article:published_time"]',
                        'time', '.date', '.published', 
                        '[itemprop="datePublished"]'
                    ];
                    
                    for (const selector of dateSelectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            if (element.tagName === 'META') return element.getAttribute('content');
                            if (element.tagName === 'TIME') {
                                if (element.hasAttribute('datetime')) return element.getAttribute('datetime');
                                return element.textContent.trim();
                            }
                            return element.textContent.trim();
                        }
                    }
                    
                    return null;
                }
            ''')
            
            # Compile the results
            result = {
                "content": extracted_text,
                "metadata": {
                    "title": title,
                    "url": url,
                    "author": author,
                    "date": date,
                    "content_type": "text"
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return {
                "content": f"Error extracting content: {str(e)}",
                "metadata": {
                    "title": await page.title() if page else "Error",
                    "url": page.url if page else "",
                    "content_type": "error"
                }
            }
    
    async def search_text(self, page: Page, text: str) -> List[str]:
        """Search for text in a page and return surrounding context."""
        try:
            return await page.evaluate(f'''
                () => {{
                    const searchText = "{text}".toLowerCase();
                    const textNodes = [];
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        {{ acceptNode: node => node.textContent.toLowerCase().includes(searchText) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT }}
                    );
                    
                    while (walker.nextNode()) {{
                        const node = walker.currentNode;
                        const parent = node.parentNode;
                        
                        // Skip if parent is script, style, etc.
                        if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME'].includes(parent.tagName)) continue;
                        
                        // Get the text content and its context
                        const fullText = node.textContent;
                        const lowerText = fullText.toLowerCase();
                        const index = lowerText.indexOf(searchText);
                        
                        if (index >= 0) {{
                            // Extract context (up to 50 chars before and after)
                            const start = Math.max(0, index - 50);
                            const end = Math.min(fullText.length, index + searchText.length + 50);
                            const context = fullText.substring(start, end);
                            
                            textNodes.push(context);
                        }}
                    }}
                    
                    return textNodes;
                }}
            ''')
        except Exception as e:
            logger.error(f"Error searching text: {str(e)}")
            return []
    
    async def extract_tables(self, page: Page) -> List[Dict[str, Any]]:
        """Extract tables from a page."""
        try:
            return await page.evaluate('''
                () => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    return tables.map(table => {
                        const caption = table.querySelector('caption')?.textContent || '';
                        
                        // Extract headers
                        const headerRow = table.querySelector('thead tr');
                        const headers = headerRow 
                            ? Array.from(headerRow.querySelectorAll('th')).map(th => th.textContent.trim())
                            : [];
                            
                        // Extract rows
                        const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => {
                            return Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim());
                        });
                        
                        return {
                            caption,
                            headers,
                            rows
                        };
                    });
                }
            ''')
        except Exception as e:
            logger.error(f"Error extracting tables: {str(e)}")
            return []
    
    async def download_pdf(self, page: Page, pdf_link: str) -> Optional[str]:
        """Download a PDF from a link."""
        try:
            # Create a download listener
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp_path = tmp.name
                
            # Navigate to the PDF and wait for download
            async with page.expect_download() as download_info:
                await page.goto(pdf_link)
                
            download = await download_info.value
            
            # Save to the temporary file
            await download.save_as(tmp_path)
            logger.info(f"PDF downloaded to {tmp_path}")
            
            return tmp_path
            
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")
            return None
    
    async def take_screenshot(self, page: Page, path: Optional[str] = None) -> Optional[str]:
        """Take a screenshot of the page."""
        try:
            if not path:
                # Create a temporary file for the screenshot
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    path = tmp.name
            
            await page.screenshot(path=path, full_page=True)
            logger.info(f"Screenshot saved to {path}")
            
            return path
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            return None
    
    async def execute_javascript(self, page: Page, script: str) -> Any:
        """Execute JavaScript on the page."""
        try:
            return await page.evaluate(script)
        except Exception as e:
            logger.error(f"Error executing JavaScript: {str(e)}")
            return None


# Example usage
async def test_browser():
    try:
        # Create browser controller with custom configuration
        config = BrowserConfig(
            headless=True,
            timeout=60000,  # 1 minute
            viewport_width=1920,
            viewport_height=1080
        )
        browser = PlaywrightCluster(config)
        
        # Initialize browser
        await browser.initialize()
        
        # Navigate to a URL
        page, success = await browser.navigate("https://www.enisa.europa.eu/topics/cybersecurity-policy/")
        
        if success:
            # Extract content
            content = await browser.extract_content(page)
            print(f"Title: {content['metadata']['title']}")
            print(f"Content length: {len(content['content'])}")
            
            # Search for specific text
            results = await browser.search_text(page, "cybersecurity")
            print(f"Found {len(results)} mentions of 'cybersecurity'")
            
            # Extract tables
            tables = await browser.extract_tables(page)
            print(f"Found {len(tables)} tables")
            
            # Take a screenshot
            screenshot_path = await browser.take_screenshot(page)
            print(f"Screenshot saved to: {screenshot_path}")
            
            # Close the page
            await page.close()
            
        # Close the browser
        await browser.close()
        
    except Exception as e:
        logger.error(f"Error in browser test: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_browser())