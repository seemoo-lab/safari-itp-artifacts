import logging
import motor.motor_asyncio
from storage.storage import StorageProvider
from datetime import datetime, timezone
from typing import List

class MongoStorage(StorageProvider):

    def __init__(self, connection_string: str, db_name: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        self.db = self.client[db_name]
        self.collections = {}
        self.initialized = False
        self.logger = logging.getLogger("MongoStorage")

    async def initialize(self):
        try:
            await self.client.admin.command('ping')
            self.initialized = True
            self.logger.info("MongoStorage: Successfully connected to MongoDB.")
        except Exception as e:
            self.logger.error(f"MongoStorage: Connection to MongoDB failed: {e}")
            raise e

    async def _get_collection(self, collection_name: str):

        if collection_name in self.collections:
            return self.collections[collection_name]

        self.collections[collection_name] = self.db[collection_name]
        await self.collections[collection_name].create_index("url", unique=True)
        self.logger.debug("Database initialized with indices.")
        return self.collections[collection_name]

    async def save_result(self, collection_name: str, url: str, data: dict):
        if not self.initialized:
            raise Exception("MongoStorage: Database not initialized. Call initialize() before saving results.")

        data["timestamp"] = datetime.now(timezone.utc)
        collection = await self._get_collection(collection_name)

        try:
            await collection.update_one(
                {"url": url}, 
                {"$set": data}, 
                upsert=True
            )
            self.logger.debug(f"Data upserted for {url}")
        except Exception as e:
            self.logger.error(f"Database write failed for {url}: {e}")

    async def stream_results(self, collection_name: str, attributes: List[str]):
        collection = await self._get_collection(collection_name)
        projection = {attr: 1 for attr in attributes}
        projection["_id"] = 0
        async for item in collection.find({}, projection):
            yield item

    async def close(self):
        self.client.close()
        self.logger.info("Database connection closed.")