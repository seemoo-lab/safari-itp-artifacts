import json
from datetime import datetime
from typing import AsyncIterator, List


class JsonlExporter:
    def __init__(self, attributes: List[str]):
        self.attributes = attributes

    async def export(self, documents: AsyncIterator[dict], output_file: str) -> int:
        count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            async for item in documents:
                filtered = self._filter_item(item)
                f.write(json.dumps(filtered, default=self._json_default) + "\n")
                count += 1
        return count

    def _filter_item(self, item: dict) -> dict:
        result = {key: item[key] for key in self.attributes if key in item}
        if "timestamp" in result:
            result["timestamp"] = self._flatten_timestamp(result["timestamp"])
        return result

    @staticmethod
    def _flatten_timestamp(value):
        if isinstance(value, dict) and "$date" in value:
            return value["$date"]
        return value

    @staticmethod
    def _json_default(value):
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value)} is not JSON serializable")