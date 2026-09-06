import logging
from typing import List, Type

from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings

logger = logging.getLogger("devops_monitor")

client: AsyncIOMotorClient | None = None
db = None


async def init_db(document_models: List[Type[Document]]):
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]
    await init_beanie(database=db, document_models=document_models)
    logger.info("Database connected to %s", settings.DATABASE_NAME)
    return db


async def close_db():
    global client
    if client:
        client.close()
        client = None
    logger.info("Database connection closed")


async def ping_database() -> bool:
    if not client:
        return False
    try:
        await client.admin.command("ping")
        return True
    except Exception:
        return False


def get_db():
    return db
