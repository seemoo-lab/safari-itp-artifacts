from browser.crawler import ParallelCrawler
from browser.device import DeviceConfig
from playwright.async_api import async_playwright, Error as PlaywrightError
    
class ParallelWebKitCrawler(ParallelCrawler):

    def __init__(self, device: DeviceConfig, headless: bool = True, sleep_before_collection: int = 0, sleep_after_collection: int = 0, save_indexed_db: bool = True, **kwargs):
        super().__init__(device, headless, sleep_before_collection, sleep_after_collection, **kwargs) 
    
    async def start_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.webkit.launch(headless=self.headless)
        self.logger.info("Browser started.")

    def _handle_playwright_error(self, e: PlaywrightError) -> str:
        reason = "Unknown"
        if "hostname could not be found" in str(e): # A server with the specified hostname could not be found.
            reason = "DNSLookupFailed"
        elif "Could not connect to the server" in str(e): # Could not connect to the server.
            reason = "ConnectionRefused"
        elif "certificate for this server is invalid" in str(e): # The certificate for this server is invalid.
            reason = "InvalidCertificate"
        elif "204 No Content" in str(e):
            reason = "NoContent"
        elif "TLS error caused the secure connection to fail" in str(e):
            reason = "TLSError"
        elif "too many HTTP redirects" in str(e):
            reason = "TooManyRedirects"
        elif "Download is starting" in str(e):
            reason = "FileDownload"
        return reason
