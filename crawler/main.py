import asyncio
import logging
import os
import pandas as pd
from dotenv import load_dotenv
from typing import Callable, Tuple, List
from storage.storage import StorageProvider
from storage.mongo import MongoStorage
from browser.crawler import ParallelCrawler
from browser.webkit import ParallelWebKitCrawler
from browser.device import DEVICES

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Orchestrator")

# Load environment variables
load_dotenv()

# Constants
URL_CSV = "top-10k.csv"
MAX_RETRIES = 3
PAGE_SLEEP_BEFORE_COLLECTION = 20 # seconds
PAGE_SLEEP_AFTER_COLLECTION = 3 # seconds

# Device configuration
DEVICE = "safari_desktop"

# Concurrency and resource control
MAX_URL_WORKERS = 8
HARD_URL_TIMEOUT = 900 # hard timeout per url seconds = 15min
URL_BATCH_SIZE = 500 # urls to process per batch

# Data output
DATABASE_NAME = "webkit_crawler"
MONGO_URI = os.getenv("MONGO_URI", "")

# Crawl state names
ANONYMOUS_ONE = "crawl_webkit_1"
ANONYMOUS_TWO = "crawl_webkit_2"

async def read_urls_from_csv(filepath: str) -> List[str]:
    df = pd.read_csv(filepath, header=None)
    raw_urls = df[1].tolist()

    urls = [f"https://{url}" if not url.startswith("http://") and not url.startswith("https://") else url for url in raw_urls]
    return urls

async def crawl_with_retries(function: Callable, **kwargs) -> Tuple[bool, dict]:
    for attempt in range(1, MAX_RETRIES + 1):

        data = await function(**kwargs)
        url = kwargs.get("url", "unknown URL")

        if data["status"] == "success":
            logger.info(f"Successfully crawled {url} on attempt {attempt}/{MAX_RETRIES}.")
            return True, data
        
        # failed
        error_message = data.get("error", "Unknown Error")
        logger.warning(f"Crawl attempt {attempt}/{MAX_RETRIES} failed for {url}. Error: {error_message}")

        # check if reason is BlockedAccess, then we dont retry
        reason = data.get("reason", "")
        if reason == "BlockedAccess":
            logger.error(f"Access blocked for {url}. Not retrying further.")
            return False, data

        if attempt < MAX_RETRIES:
            wait_time = 2 ** attempt 
            logger.info(f"Retrying crawl for {url} in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
        else:
            logger.error(f"Max attempts reached for crawl: {url}. Giving up.")

    # all attempts failed, return error data
    return False, data

async def process_pipeline(url, crawler: ParallelCrawler, storage: StorageProvider):

    # 1. Anonymous crawl
    logger.info(f"1. Anonymous crawl for {url}")
    success, data = await crawl_with_retries(
        crawler.scrape_anonymous,
        url=url,
    )
    await storage.save_result(ANONYMOUS_ONE, url, data)
    if not success:
        return # break pipeline

    # 2. Anonymous crawl
    logger.info(f"2. Anonymous crawl for {url}")
    success, data = await crawl_with_retries(
        crawler.scrape_anonymous,
        url=url,
    )
    await storage.save_result(ANONYMOUS_TWO, url, data)
    if not success:
        return # break pipeline

    # Finished
    logger.info(f"Completed full pipeline for {url}")

async def process_pipeline_with_semaphore(url: str, crawler: ParallelCrawler, storage: StorageProvider, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            return await asyncio.wait_for(
                process_pipeline(url, crawler, storage),
                timeout=HARD_URL_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout while processing pipeline for {url}")
            return {"status": "failed", "url": url, "error": "HardTimeout"}
        except Exception as e:
            logger.error(f"Error while processing pipeline for {url}: {e}")
            return {"status": "failed", "url": url, "error": str(e)}

async def process_batch(storage: StorageProvider, semaphore: asyncio.Semaphore, batch_urls: list):
    logger.info(f"Processing batch of {len(batch_urls)} URLs.")

    # Init crawler
    logger.info("Initializing web crawler.")
    crawler = ParallelWebKitCrawler(
        device=DEVICES[DEVICE],
        headless=True,
        sleep_before_collection=PAGE_SLEEP_BEFORE_COLLECTION,
        sleep_after_collection=PAGE_SLEEP_AFTER_COLLECTION,
        minimal_logging=False
    )
    await crawler.load_stealth_script("browser/stealth_webkit.js")
    await crawler.start_browser()

    try:
        tasks = [process_pipeline_with_semaphore(url, crawler, storage, semaphore) for url in batch_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
            
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error during scraping process: {result}")

    except Exception as e:
        logger.error(f"Critical error: {e}")

    finally:
        # Cleanup
        logger.info(f"Batch complete. Closing browser resources.")
        await crawler.close_browser()

async def main():

    # read URLs
    urls = await read_urls_from_csv(URL_CSV)
    # urls = [url for url in urls if url not in exclude_urls]
    logger.info(f"Read {len(urls)} URLs from CSV.")

    # define semaphore for parallelism
    semaphore = asyncio.Semaphore(MAX_URL_WORKERS)
    logger.info(f"Using max {MAX_URL_WORKERS} concurrent URL workers.")

    # init storage
    logger.info("Initializing storage system.")
    storage = MongoStorage(
        connection_string=MONGO_URI,
        db_name=DATABASE_NAME
    )
    await storage.initialize()

    # Process URLs in batches
    for i in range(0, len(urls), URL_BATCH_SIZE):
        batch_urls = urls[i : i + URL_BATCH_SIZE]
        batch_num = (i // URL_BATCH_SIZE) + 1
        logger.info(f"Starting batch {batch_num} with {len(batch_urls)} URLs.")

        # process batch
        await process_batch(storage=storage, semaphore=semaphore, batch_urls=batch_urls)

        # sleep between batches to reduce load
        logger.info(f"Batch {batch_num} complete. Sleeping for 30 seconds before next batch.")
        await asyncio.sleep(30)

    logger.info("Scraping complete. Cleaning up resources.")
    await storage.close()


if __name__ == "__main__":
    asyncio.run(main())