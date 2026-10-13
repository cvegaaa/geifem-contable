"""Cliente async de MongoDB (API async oficial de PyMongo)."""
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from config import settings

_client: AsyncMongoClient | None = None


def get_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(settings.mongo_uri, tz_aware=True)
    return _client


def get_db() -> AsyncDatabase:
    return get_client()[settings.db_name]


async def cerrar_cliente() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
