"""
Database population script for the multimedia game assets API.
This script loads sample data from the assets folder and populates the MongoDB collections.
"""

import os
import json
import base64
import asyncio
import datetime
from pathlib import Path
import motor.motor_asyncio
from dotenv import load_dotenv
import mimetypes

# Loading the .env
load_dotenv()

# Get MongoDB connection string
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
if not MONGO_CONNECTION_STRING:
    raise ValueError("No MongoDB connection string found. Please check your .env file.")

# Define paths
ASSETS_DIR = Path("assets")
SPRITES_DIR = ASSETS_DIR / "sprites"
SOUNDS_DIR = ASSETS_DIR / "sounds"
PLAYER_SCORE_FILE = ASSETS_DIR / "playerScore.json"

# GridFS size threshold (from 16MB to 512KB buffer)
GRIDFS_THRESHOLD = 16 * 1024 * 1024 - 512 * 1024


async def populate_database():
    """Populate the MongoDB database with sample data from the assets folder."""

    # Connecting to MongoDB
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_CONNECTION_STRING)
    db = client.multimedia_db

    print("Connected to MongoDB Atlas")

    try:
        # 1. Populates sprites collection
        await populate_sprites(db)

        # 2. Populates audio collection
        await populate_audio(db)

        # 3. Populates scores collection
        await populate_scores(db)

        print("Database population completed successfully!")

    except Exception as e:
        print(f"An error occurred during database population: {e}")

    finally:
        # Closing the connection
        client.close()
        print("MongoDB connection closed")


async def populate_sprites(db):
    """Populate the sprites collection with image files from the sprites folder."""

    print("Populating sprites collection...")

    # Getting lists of sprite files
    sprite_files = list(SPRITES_DIR.glob("*.png"))

    # Skips if no sprites file is found
    if not sprite_files:
        print("No sprite files found in the sprites folder.")
        return

    # Process each sprite file
    count = 0
    for sprite_file in sprite_files[:5]:  # Limit to first 5 for testing
        # Get file details
        filename = sprite_file.name
        file_size = sprite_file.stat().st_size
        content_type = mimetypes.guess_type(sprite_file)[0] or "image/png"

        # Reads the file contents
        with open(sprite_file, "rb") as f:
            file_content = f.read()

        # Creates the document
        sprite_doc = {
            "filename": filename,
            "contentType": content_type,
            "uploadDate": datetime.datetime.now(),
            "size": file_size,
            "metadata": {
                "tags": ["sample", "sprite"],
                "description": f"Sample sprite from {filename}"
            }
        }

        # Handles file storage based on the size
        if file_size < GRIDFS_THRESHOLD:
            # Stores it directly in the document
            sprite_doc["content"] = base64.b64encode(file_content).decode("utf-8")
        else:
            #check here 
            sprite_doc["gridfs_id"] = None  # Placeholder
            print(f"File {filename} is too large for direct storage and would use GridFS")

        # Inserts into the database
        result = await db.sprites.insert_one(sprite_doc)
        print(f"Inserted sprite {filename} with ID {result.inserted_id}")
        count += 1

    print(f"Added {count} sprites to the database")


async def populate_audio(db):
    """Populate the audio collection with sound files from the sounds folder."""

    print("Populating audio collection...")

    # Getting list of audio the files
    audio_files = list(SOUNDS_DIR.glob("*.wav"))

    # Skips it if no audio files found
    if not audio_files:
        print("No audio files found in the sounds folder.")
        return

    # Process each audio file
    count = 0
    for audio_file in audio_files[:3]:  # Limit to first 3 for testing
        # Gets the files details
        filename = audio_file.name
        file_size = audio_file.stat().st_size
        content_type = mimetypes.guess_type(audio_file)[0] or "audio/wav"

        # Reading the file contents (specifically for small files only)
        if file_size < GRIDFS_THRESHOLD:
            with open(audio_file, "rb") as f:
                file_content = f.read()

        # Creates the documents
        audio_doc = {
            "filename": filename,
            "contentType": content_type,
            "uploadDate": datetime.datetime.now(),
            "size": file_size,
            "metadata": {
                "tags": ["sample", "audio"],
                "description": f"Sample audio from {filename}"
            }
        }

        # Handles the file storage based on size
        if file_size < GRIDFS_THRESHOLD:
            # Stores directly in the document
            audio_doc["content"] = base64.b64encode(file_content).decode("utf-8")
        else:
            #Check here
            audio_doc["gridfs_id"] = None  # Placeholder
            print(f"File {filename} is too large for direct storage and would use GridFS")

        # Inserts into database
        result = await db.audio.insert_one(audio_doc)
        print(f"Inserted audio {filename} with ID {result.inserted_id}")
        count += 1

    print(f"Added {count} audio files to the database")


async def populate_scores(db):
    """Populate the scores collection with data from the playerScore.json file."""

    print("Populating scores collection...")

    # Skips if the player score file doesn't exist
    if not PLAYER_SCORE_FILE.exists():
        print("Player score file not found.")
        return

    # Reads player score data
    with open(PLAYER_SCORE_FILE, "r") as f:
        player_scores = json.load(f)

    # Process each player score
    count = 0
    for score_data in player_scores:
        # Creating document
        score_doc = {
            "player_name": score_data["player_name"],
            "score": score_data["score"],
            "timestamp": datetime.datetime.now(),
            "game_level": "default",
            "metadata": {
                "platform": "web",
                "game_version": "1.0"
            }
        }

        # Inserts into the database
        result = await db.scores.insert_one(score_doc)
        print(f"Inserted score for {score_data['player_name']} with ID {result.inserted_id}")
        count += 1

    print(f"Added {count} player scores to the database")


if __name__ == "__main__":

    asyncio.run(populate_database())