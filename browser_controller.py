import asyncio
import logging
import os
import re
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import trafilatura

from models import ResearchTask, ContentMetadata

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BrowserController:
    """
    Controller class for headless web browsing using Playwright.
    
    This module is responsible for:
    1. Opening web pages
    2. Searching text within pages
    3. Extracting content from web pages
    4. Downloading documents
    5. Extracting data tables
    """
    
    def __init__(self):
        """Initialize the BrowserController."""
        logger.debug("Initializing BrowserController")
        self.browser = None
        self.context = None
    
    async def initialize(self) -> None:
        """
        Initialize the browser and context for headless browsing.
        """
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        logger.debug("Browser and context initialized")
    
    async def close(self) -> None:
        """
        Close the browser and context.
        """
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.debug("Browser and context closed")
    
    async def open_url(self, url: str) -> Tuple[Page, bool]:
        """
        Open a URL in a new page.
        
        Args:
            url: The URL to open
            
        Returns:
            A tuple of (Page object, success boolean)
        """
        if not self.context:
            await self.initialize()
            
        logger.info(f"Opening URL: {url}")
        
        try:
            page = await self.context.new_page()
            response = await page.goto(url, wait_until='networkidle', timeout=30000)
            
            if not response:
                logger.error(f"Failed to load {url}: No response")
                await page.close()
                return None, False
                
            if response.status >= 400:
                logger.error(f"Failed to load {url}: Status code {response.status}")
                await page.close()
                return None, False
                
            logger.debug(f"Successfully loaded {url}")
            return page, True
            
        except Exception as e:
            logger.error(f"Error opening {url}: {str(e)}")
            return None, False
    
    async def search_text(self, page: Page, text: str) -> List[str]:
        """
        Search for text in a page and return surrounding context.
        
        Args:
            page: The page to search in
            text: The text to search for
            
        Returns:
            List of text snippets containing the search text
        """
        logger.info(f"Searching for text: '{text}'")
        
        try:
            # Find all instances of the text
            search_regex = re.escape(text)
            matches = await page.evaluate(f'''() => {{
                const matches = [];
                const textNodes = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null, false
                );
                let node;
                
                while (node = textNodes.nextNode()) {{
                    const content = node.textContent;
                    if (content.match(/{search_regex}/i)) {{
                        // Get parent element to capture more context
                        let parent = node.parentElement;
                        // Try to get a paragraph or larger context
                        while (parent && !['P', 'DIV', 'SECTION', 'ARTICLE'].includes(parent.tagName)) {{
                            parent = parent.parentElement;
                        }}
                        
                        matches.push(parent ? parent.textContent.trim() : content.trim());
                    }}
                }}
                return matches;
            }}''')
            
            logger.debug(f"Found {len(matches)} matches for '{text}'")
            return matches
            
        except Exception as e:
            logger.error(f"Error searching for text '{text}': {str(e)}")
            return []
    
    async def extract_content(self, page: Page) -> Dict[str, Any]:
        """
        Extract content from a page.
        
        Args:
            page: The page to extract content from
            
        Returns:
            Dictionary containing extracted content and metadata
        """
        logger.info(f"Extracting content from page: {page.url}")
        
        try:
            # Get basic page metadata
            title = await page.title()
            url = page.url
            
            # Extract author and date using common patterns
            author = await page.evaluate('''() => {
                // Try common author selectors
                const selectors = [
                    'meta[name="author"]',
                    'meta[property="article:author"]',
                    '.author', 
                    '.byline',
                    '[itemprop="author"]',
                    '.entry-author'
                ];
                
                for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (el) {
                        if (el.tagName === 'META') return el.content;
                        return el.textContent.trim();
                    }
                }
                return null;
            }''')
            
            date = await page.evaluate('''() => {
                // Try common date selectors
                const selectors = [
                    'meta[name="date"]',
                    'meta[property="article:published_time"]',
                    'time',
                    '.date', 
                    '.published',
                    '[itemprop="datePublished"]'
                ];
                
                for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (el) {
                        if (el.tagName === 'META') return el.content;
                        if (el.tagName === 'TIME' && el.getAttribute('datetime')) return el.getAttribute('datetime');
                        return el.textContent.trim();
                    }
                }
                return null;
            }''')
            
            # Get page content using trafilatura for better content extraction
            html_content = await page.content()
            
            # Use trafilatura to extract the main content
            # This provides better content extraction than just grabbing all text
            text_content = trafilatura.extract(html_content)
            
            if not text_content:
                # Fallback to basic text extraction if trafilatura fails
                text_content = await page.evaluate('''() => {
                    // Remove script and style elements
                    const elements = document.querySelectorAll('script, style, header, footer, nav, aside');
                    for (const el of elements) {
                        el.remove();
                    }
                    
                    // Get main content area
                    const mainContent = document.querySelector('main, article, .content, #content, .article');
                    if (mainContent) {
                        return mainContent.textContent.trim();
                    }
                    
                    // Fallback to body text
                    return document.body.textContent.trim();
                }''')
            
            # Create metadata object
            metadata = ContentMetadata(
                title=title,
                author=author,
                date=date,  # This will be validated by pydantic
                url=url,
                content_type="text"
            )
            
            logger.debug(f"Successfully extracted content from {url}")
            
            return {
                "content": text_content,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return {
                "content": "",
                "metadata": ContentMetadata(
                    title="Error extracting content",
                    url=page.url,
                    content_type="error"
                ),
                "error": str(e)
            }
    
    async def extract_tables(self, page: Page) -> List[Dict[str, Any]]:
        """
        Extract tables from a page.
        
        Args:
            page: The page to extract tables from
            
        Returns:
            List of extracted tables as dictionaries
        """
        logger.info(f"Extracting tables from page: {page.url}")
        
        try:
            tables = await page.evaluate('''() => {
                const results = [];
                const tables = document.querySelectorAll('table');
                
                tables.forEach((table, tableIndex) => {
                    const rows = table.querySelectorAll('tr');
                    if (rows.length === 0) return;
                    
                    const headerRow = rows[0].querySelectorAll('th');
                    const hasHeader = headerRow.length > 0;
                    
                    // Extract headers
                    let headers = [];
                    if (hasHeader) {
                        headerRow.forEach(th => {
                            headers.push(th.textContent.trim());
                        });
                    } else {
                        // If no header row, use column numbers
                        const firstRow = rows[0].querySelectorAll('td');
                        headers = Array.from({length: firstRow.length}, (_, i) => `Column ${i+1}`);
                    }
                    
                    // Extract data rows
                    const data = [];
                    const startIndex = hasHeader ? 1 : 0;
                    
                    for (let i = startIndex; i < rows.length; i++) {
                        const row = rows[i];
                        const cells = row.querySelectorAll('td');
                        const rowData = {};
                        
                        cells.forEach((cell, cellIndex) => {
                            if (cellIndex < headers.length) {
                                rowData[headers[cellIndex]] = cell.textContent.trim();
                            }
                        });
                        
                        if (Object.keys(rowData).length > 0) {
                            data.push(rowData);
                        }
                    }
                    
                    // Add table to results
                    results.push({
                        id: tableIndex,
                        headers: headers,
                        data: data,
                        rowCount: data.length,
                        columnCount: headers.length
                    });
                });
                
                return results;
            }''')
            
            logger.debug(f"Extracted {len(tables)} tables from {page.url}")
            return tables
            
        except Exception as e:
            logger.error(f"Error extracting tables: {str(e)}")
            return []
    
    async def download_pdf(self, page: Page, pdf_link: str) -> Optional[str]:
        """
        Download a PDF from a link.
        
        Args:
            page: The current page
            pdf_link: The URL to the PDF
            
        Returns:
            Path to the downloaded PDF file, or None if download failed
        """
        logger.info(f"Downloading PDF from: {pdf_link}")
        
        try:
            # Parse the URL to get a reasonable filename
            parsed_url = urlparse(pdf_link)
            path_parts = parsed_url.path.split('/')
            filename = path_parts[-1] if path_parts[-1] else f"document_{hash(pdf_link)}.pdf"
            
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            
            # Create a temporary directory for downloads
            os.makedirs('downloads', exist_ok=True)
            download_path = os.path.join('downloads', filename)
            
            # Navigate to the PDF URL
            pdf_page = await self.context.new_page()
            
            # Setup download listener
            async with pdf_page.expect_download() as download_info:
                await pdf_page.goto(pdf_link, timeout=60000)
                
                # Wait for the download to start
                download = await download_info.value
                
                # Save the downloaded file
                await download.save_as(download_path)
                
                logger.debug(f"PDF downloaded to {download_path}")
                await pdf_page.close()
                
                return download_path
                
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")
            return None
    
    async def browse(self, task: ResearchTask) -> Dict[str, Any]:
        """
        Execute a research browsing task.
        
        Args:
            task: The research task to execute
            
        Returns:
            Dictionary containing results of the browsing task
        """
        logger.info(f"Starting browsing task: {task.task_id}")
        
        if not self.context:
            await self.initialize()
        
        results = {
            "task_id": str(task.task_id),
            "objective": task.objective,
            "findings": [],
            "errors": []
        }
        
        for source in task.sources:
            logger.info(f"Processing source: {source}")
            
            try:
                # Open the page
                page, success = await self.open_url(source)
                
                if not success:
                    results["errors"].append({
                        "source": source,
                        "error": "Failed to open URL"
                    })
                    continue
                    
                # Extract content
                content_result = await self.extract_content(page)
                
                # Extract tables if needed
                tables = []
                if task.depth >= 2:  # For medium to deep research, extract tables
                    tables = await self.extract_tables(page)
                
                # Add extracted data to findings
                finding = {
                    "source": source,
                    "content": content_result["content"],
                    "metadata": content_result["metadata"],
                    "tables": tables
                }
                
                results["findings"].append(finding)
                await page.close()
                
            except Exception as e:
                logger.error(f"Error processing source {source}: {str(e)}")
                results["errors"].append({
                    "source": source,
                    "error": str(e)
                })
        
        logger.info(f"Completed browsing task: {task.task_id}")
        return results
