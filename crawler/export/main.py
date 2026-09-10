import asyncio
import logging
import os
from dotenv import load_dotenv
from storage.mongo import MongoStorage
from storage.jsonl_export import JsonlExporter


# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("JsonlExporter")

# Load environment variables
load_dotenv()

# Data output
DATABASE_NAME = "webkit_crawler"
MONGO_URI = os.getenv("MONGO_URI", "")
OUTPUT_DIR = "results"

# Crawl state names
ANONYMOUS_ONE = "crawl_webkit_1"
ANONYMOUS_TWO = "crawl_webkit_2"

# Attributes to keep in exported Jsonl
KEEP_KEYS = [
    "url",
    "details",
    "error",
    "reason",
    "status",
    "timestamp",
    "cookies",
    "currentUrl",
    "dns",
    "http_status_code",
    "loaded_urls",
]


async def main():

    # init storage
    logger.info("Initializing storage system.")
    storage = MongoStorage(
        connection_string=MONGO_URI,
        db_name=DATABASE_NAME
    )
    await storage.initialize()

    # prepare output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # init exporter
    logger.info("Initializing exporter.")
    exporter = JsonlExporter(attributes=KEEP_KEYS)

    output_path_one = os.path.join(OUTPUT_DIR, f"{ANONYMOUS_ONE}.jsonl")
    count_one = await exporter.export(storage.stream_results(ANONYMOUS_ONE, KEEP_KEYS), output_path_one)
    logger.info(f"Exported {count_one} documents to {ANONYMOUS_ONE}.jsonl")

    output_path_two = os.path.join(OUTPUT_DIR, f"{ANONYMOUS_TWO}.jsonl")
    count_two = await exporter.export(storage.stream_results(ANONYMOUS_TWO, KEEP_KEYS), output_path_two)
    logger.info(f"Exported {count_two} documents to {ANONYMOUS_TWO}.jsonl")

    logger.info("Completed. Cleaning up resources.")
    await storage.close()


if __name__ == "__main__":
    asyncio.run(main())