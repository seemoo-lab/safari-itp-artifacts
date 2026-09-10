import asyncio
import logging
import time
import tldextract
from abc import ABC, abstractmethod
from functools import partial
from http.cookies import SimpleCookie
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from browser.device import DeviceConfig
from utils.dns_utils import resolve_domain_rr


class ParallelCrawler(ABC):

    playwright: any
    browser: any

    def __init__(
        self,
        device: DeviceConfig,
        headless: bool = True,
        sleep_before_collection: int = 0,
        sleep_after_collection: int = 0,
        minimal_logging: bool = True,
    ):
        self.headless = headless
        self.sleep_before_collection = sleep_before_collection
        self.sleep_after_collection = sleep_after_collection
        self.minimal_logging = minimal_logging
        self.playwright = None
        self.browser = None

        self.page_load_idle_timeout = 30_000  # ms

        self.user_agent = device.user_agent
        self.viewport_config = device.viewport
        self.is_mobile = device.is_mobile
        self.device_scale_factor = device.device_scale_factor
        self.locale = device.locale
        self.timezone_id = device.timezone_id

        self.stealth_script = ""

        self.shared_extractor = tldextract.TLDExtract(cache_dir=".tld_cache")
        self.shared_extractor("example.com")  # warm up cache

        self._dns_cache = {}
        self._dns_cache_lock = asyncio.Lock()

        self.logger = logging.getLogger("Crawler")

    async def _resolve_dns(self, fqdn: str) -> dict:
        async with self._dns_cache_lock:
            if fqdn not in self._dns_cache:
                async def perform_lookup():
                    return {
                        "A": await asyncio.to_thread(resolve_domain_rr, fqdn, "A"),
                        "AAAA": await asyncio.to_thread(resolve_domain_rr, fqdn, "AAAA"),
                        "CNAME": await asyncio.to_thread(resolve_domain_rr, fqdn, "CNAME"),
                    }
                self._dns_cache[fqdn] = asyncio.create_task(perform_lookup())
                
        return await self._dns_cache[fqdn]

    async def _collect_page_metrics(self, context, page) -> dict:
        return {"cookies": await context.cookies()}

    async def _enrich_cookie_metadata(self, cookies: list, server_cookies: list):
        server_cookie_map = {c['name']: c['setBy'] for c in server_cookies}
        for cookie in cookies:
            cookie_name = cookie['name']
            is_server = cookie.get('httpOnly') or cookie_name in server_cookie_map
            cookie['setVia'] = 'server' if is_server else 'client'
            if cookie_name in server_cookie_map:
                cookie['setBy'] = server_cookie_map[cookie_name]

    async def _verify_not_blocked(self, page):
        title = (await page.title()).strip()
        if title in ["Just a moment...", "Access Denied", "Blocked"]:
            raise ValueError(f"Access blocked: {title}")

    def _extract_cookies_from_list(self, headers_list, server_cookies: list, url: str):
        for header in headers_list:
            if header['name'].lower() != 'set-cookie':
                continue
            try:
                parser = SimpleCookie()
                parser.load(header['value'])
                for name in parser.keys():
                    server_cookies.append({"name": name, "setBy": url})
            except Exception:
                continue

    def _merge_headers(self, source_headers, target_header_list):
        for header in source_headers:
            name_lo = header['name'].lower()
            val = header['value']

            if name_lo == 'set-cookie':
                parser = SimpleCookie()
                parser.load(val)
                for c_name, morsel in parser.items():
                    clean_val = morsel.OutputString().replace("Set-Cookie: ", "", 1)
                    existing = next(
                        (item for item in target_header_list
                         if item['name'].lower() == 'set-cookie'
                         and item['value'].split('=')[0] == c_name),
                        None,
                    )
                    if existing:
                        existing['value'] = clean_val
                    else:
                        target_header_list.append({'name': 'set-cookie', 'value': clean_val})
                continue

            existing = next((item for item in target_header_list if item['name'].lower() == name_lo), None)
            if existing:
                existing['value'] = val
            else:
                target_header_list.append({'name': name_lo, 'value': val})

    async def _handle_response(self, response, headers_log: list, server_cookies: list, target_domain: str):
        try:
            headers = await response.headers_array()
            if not any(h['name'].lower() == 'set-cookie' for h in headers):
                return

            reg_domain = self.shared_extractor(response.url).registered_domain
            if reg_domain != target_domain:
                return  # only track first-party cookies

            self._extract_cookies_from_list(headers, server_cookies, response.url)

            is_main_document = (
                response.frame == response.frame.page.main_frame
                and response.request.resource_type == "document"
            )
            if is_main_document:
                self._merge_headers(headers, headers_log)

        except Exception as e:
            error_msg = str(e)
            if "Target page, context or browser has been closed" not in error_msg:
                self.logger.error(f"Response error {response.url}: {error_msg}")

    async def _process_loaded_url(self, request) -> dict:
        try:
            if request.url.startswith(("blob:", "data:", "localhost")):
                return {"url": request.url, "error": "Unsupported URL scheme"}

            post_data = None
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    post_data = request.post_data
                except Exception:
                    pass

            domain = self.shared_extractor(request.url).fqdn

            return {
                "url": request.url,
                "dns": await self._resolve_dns(domain),
                "resource_type": request.resource_type,
                "method": request.method,
                "headers": await request.headers_array(),
                "post_data": post_data,
                "redirect_from": request.redirected_from.url if request.redirected_from else None,
                "redirect_to": request.redirected_to.url if request.redirected_to else None,
            }
        except Exception as e:
            error_msg = str(e)
            if "Target page, context or browser has been closed" not in error_msg:
                self.logger.warning(f"Error processing loaded URL: {error_msg}")
            return {"url": request.url or "unknown", "error": error_msg}

    async def _core_scrape(
        self,
        url: str,
        view_port: dict = None,
        sleep_before: int = None,
        sleep_after: int = None,
    ) -> dict:
        sleep_before = sleep_before if sleep_before is not None else self.sleep_before_collection
        sleep_after = sleep_after if sleep_after is not None else self.sleep_after_collection

        context = await self.browser.new_context(
            user_agent=self.user_agent,
            viewport=view_port if view_port is not None else self.viewport_config,
            locale=self.locale,
            timezone_id=self.timezone_id,
            java_script_enabled=True,
            bypass_csp=True,
            is_mobile=self.is_mobile,
            device_scale_factor=self.device_scale_factor if self.is_mobile else None,
        )

        page = await context.new_page()

        if self.stealth_script:
            await page.add_init_script(self.stealth_script)

        loaded_urls = []

        async def on_request(req):
            if not page.is_closed() or (req.frame and req.frame.page and not req.frame.page.is_closed()):
                loaded_urls.append(await self._process_loaded_url(req))

        if not self.minimal_logging:
            page.on("request", on_request)

        server_cookies = []
        server_headers = []
        page.on(
            "response",
            partial(
                self._handle_response,
                headers_log=server_headers,
                server_cookies=server_cookies,
                target_domain=self.shared_extractor(url).registered_domain,
            ),
        )

        start_time = time.perf_counter()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.page_load_idle_timeout)

            if sleep_before > 0:
                self.logger.debug(f"Sleeping for {sleep_before} seconds...")
                await asyncio.sleep(sleep_before)

            await self._verify_not_blocked(page)

            data = await self._collect_page_metrics(context, page)
            await self._enrich_cookie_metadata(data['cookies'], server_cookies)

            time_taken_ms = (time.perf_counter() - start_time) * 1000
            self.logger.info(f"Time taken for {url}: {time_taken_ms:.2f} ms.")

            final_state = {
                "status": "success",
                "url": url,
                "currentUrl": page.url,
                "http_status_code": response.status if response else -1,  # -1 = unknown
                "time_taken_ms": round(time_taken_ms, 2),
                "cookies": data['cookies'],
                "serverHeaders": server_headers,
            }

            if not self.minimal_logging:
                final_state['dns'] = await self._resolve_dns(self.shared_extractor(url).fqdn)
                final_state['loaded_urls'] = loaded_urls

            if sleep_after > 0:
                self.logger.debug(f"Sleeping for {sleep_after} seconds for late-loading resources...")
                await asyncio.sleep(sleep_after)

            return final_state

        except PlaywrightTimeoutError as e:
            self.logger.error(f"Timeout on {url}: {e}")
            return {"status": "failed", "url": url, "error": "TimeoutError", "reason": "Timeout", "details": str(e)}
        except PlaywrightError as e:
            reason = self._handle_playwright_error(e)
            return {"status": "failed", "url": url, "error": "PlaywrightError", "reason": reason, "details": str(e)}
        except ValueError as e:
            self.logger.error(f"Value error on {url}: {e}")
            return {"status": "failed", "url": url, "error": "ValueError", "reason": "BlockedAccess", "details": str(e)}
        except Exception as e:
            self.logger.error(f"Error on {url}: {e}")
            return {"status": "failed", "url": url, "error": str(e)}
        finally:
            await page.close()
            await context.close()

    @abstractmethod
    async def start_browser(self):
        raise NotImplementedError()

    async def load_stealth_script(self, script_path: str):
        try:
            with open(script_path, 'r') as file:
                self.stealth_script = file.read()
            self.logger.info("Stealth script loaded.")
        except Exception as e:
            self.logger.error(f"Failed to load stealth script: {e}")
            self.stealth_script = ""

    async def scrape_anonymous(self, url: str) -> dict:
        self.logger.info(f"Scraping (anonymous): {url}")
        return await self._core_scrape(url=url)

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Browser closed.")