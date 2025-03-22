"""
Database initialization script for the multimedia game assets API.
This script sets up the MongoDB collections and indexes.
"""

import os
import asyncio
import motor.motor_asyncio
from dotenv import load_dotenv

# Loads the .env
load_dotenv()

# Gets MongoDB connection string
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
if not MONGO_CONNECTION_STRING:
    raise ValueError("No MongoDB connection string found. Please check your .env file.")


async def init_database():
    """Initialize the MongoDB database with collections and indexes."""

    # Connecting to MongoDB
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_CONNECTION_STRING)
    db = client.multimedia_db

    print("Connected to MongoDB Atlas")

    # Creating collections if they don't exist

    # Defines validation schemas
    sprite_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["filename", "contentType", "uploadDate"],
            "properties": {
                "filename": {"bsonType": "string"},
                "contentType": {"bsonType": "string"},
                "uploadDate": {"bsonType": "date"},
                "size": {"bsonType": "int"},
                "content": {"bsonType": ["string", "binData"]},
                "metadata": {"bsonType": "object"},
                "gridfs_id": {"bsonType": "objectId"}
            }
        }
    }

    audio_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["filename", "contentType", "uploadDate"],
            "properties": {
                "filename": {"bsonType": "string"},
                "contentType": {"bsonType": "string"},
                "uploadDate": {"bsonType": "date"},
                "size": {"bsonType": "int"},
                "content": {"bsonType": ["string", "binData"]},
                "metadata": {"bsonType": "object"},
                "gridfs_id": {"bsonType": "objectId"}
            }
        }
    }

    scores_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["player_name", "score", "timestamp"],
            "properties": {
                "player_name": {"bsonType": "string"},
                "score": {"bsonType": "int"},
                "timestamp": {"bsonType": "date"},
                "game_level": {"bsonType": "string"},
                "metadata": {"bsonType": "object"}
            }
        }
    }

    # Creating collections with validation
    try:
        # Checks if collections already exist
        collections = await db.list_collection_names()

        # Creates sprites collection if it doesn't exist
        if "sprites" not in collections:
            await db.create_collection("sprites", validator=sprite_schema)
            print("Created sprites collection")
        else:
            print("Sprites collection already exists")

        # Creates audio collection if it doesn't exist
        if "audio" not in collections:
            await db.create_collection("audio", validator=audio_schema)
            print("Created audio collection")
        else:
            print("Audio collection already exists")

        # Creates scores collection if it doesn't exist
        if "scores" not in collections:
            await db.create_collection("scores", validator=scores_schema)
            print("Created scores collection")
        else:
            print("Scores collection already exists")

        # Creating indexes
        # Sprites collection indexes
        await db.sprites.create_index("filename")
        await db.sprites.create_index("metadata.tags")
        print("Created indexes for sprites collection")

        # Audio collection indexes
        await db.audio.create_index("filename")
        await db.audio.create_index("metadata.tags")
        print("Created indexes for audio collection")

        # Scores collection indexes
        await db.scores.create_index("player_name")
        await db.scores.create_index("score", -1)  # Descending for high scores
        await db.scores.create_index("timestamp")
        print("Created indexes for scores collection")

        print("Database initialization completed successfully!")

    except Exception as e:
        print(f"An error occurred during database initialization: {e}")

    finally:
        # Close the connection
        client.close()
        print("MongoDB connection closed")


if __name__ == "__main__":

    asyncio.run(init_database())