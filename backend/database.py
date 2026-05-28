from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

client: AsyncIOMotorClient = None
db = None

async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.MONGO_DB]
    # Create indexes
    await db.tasks.create_index("created_at")
    await db.tasks.create_index("status")
    await db.videos.create_index("task_id")
    await db.detections.create_index("task_id")
    await db.detections.create_index("video_id")
    await db.detections.create_index([("task_id", 1), ("chainage", 1)])
    print(f"Connected to MongoDB: {settings.MONGO_DB}")

async def close_db():
    global client
    if client:
        client.close()

def get_db():
    return db
