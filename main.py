import os
import base64
import html
import re
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
import motor.motor_asyncio
from bson import ObjectId
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Creating a FastAPI app
app = FastAPI(
    title="Multimedia Game Assets API",
    description="API for storing and retrieving multimedia game assets including sprites, audio files, and player scores",
    version="1.0.0"
)

# Getting MongoDB connection string from environment variables
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
if not MONGO_CONNECTION_STRING:
    raise ValueError("No MongoDB connection string found. Please check your .env file.")

# Connecting to MongoDB Atlas
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_CONNECTION_STRING)
db = client.multimedia_db


# Defines the models
class PlayerScore(BaseModel):
    """Model for player score data."""
    player_name: str
    score: int
    game_level: Optional[str] = "default"


# Helper functions
def sanitize_input(value: Optional[str]) -> Optional[str]:
    """
    Sanitize user input to prevent NoSQL injection attacks.
    """
    if value is None:
        return None

    # Escape HTML special characters to prevent XSS
    value = html.escape(value)

    # Removes the MongoDB operators to prevent NoSQL injection
    value = re.sub(r'\$', '', value)

    return value


def object_id_to_str(obj):
    """Convert MongoDB ObjectId to string for JSON serialization."""
    if isinstance(obj, dict):
        for key in obj:
            if isinstance(obj[key], ObjectId):
                obj[key] = str(obj[key])
            elif isinstance(obj[key], dict) or isinstance(obj[key], list):
                obj[key] = object_id_to_str(obj[key])
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, ObjectId):
                obj[i] = str(item)
            elif isinstance(item, dict) or isinstance(item, list):
                obj[i] = object_id_to_str(item)
    return obj


# Health check endpoint
@app.get("/")
async def health_check():
    """Check if the API is running."""
    return {"status": "healthy", "message": "API is running"}


# Sprite endpoints
@app.post("/upload_sprite")
async def upload_sprite(file: UploadFile = File(...)):
    """
    Upload a sprite image file.
    """
    try:
        # Read file content
        content = await file.read()

        # Create sprite document with Base64 encoded content
        # Using the simple schema from Appendix B
        sprite_doc = {
            "filename": file.filename,
            "content": base64.b64encode(content).decode("utf-8")
        }

        # Insert into database
        result = await db.sprites.insert_one(sprite_doc)

        return {"message": "Sprite uploaded", "id": str(result.inserted_id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading sprite: {str(e)}")


@app.get("/sprites")
async def get_sprites():
    """
    Get a list of available sprites (metadata only, no content).
    """
    try:
        # Query sprites collection to exclude content field to reduce response size
        cursor = db.sprites.find({}, {"content": 0})

        # Convert cursor to list
        sprites = await cursor.to_list(length=100)

        # Convert ObjectId to string
        sprites = object_id_to_str(sprites)

        return {"sprites": sprites}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sprites: {str(e)}")


@app.get("/sprites/{sprite_id}")
async def get_sprite(sprite_id: str):
    """
    Get a specific sprite by ID, including its content.
    """
    try:
        # Converting string ID to ObjectId
        try:
            oid = ObjectId(sprite_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid sprite ID format")

        # Query database
        sprite = await db.sprites.find_one({"_id": oid})

        # Checking if sprite exists
        if not sprite:
            raise HTTPException(status_code=404, detail="Sprite not found")

        # Convert ObjectId to string for JSON serialization
        sprite = object_id_to_str(sprite)

        return sprite

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sprite: {str(e)}")


# Audio endpoints
@app.post("/upload_audio")
async def upload_audio(file: UploadFile = File(...)):
    """
    Upload an audio file.
    """
    try:
        # Read file content
        content = await file.read()

        # Creates the audio document with Base64 encoded content
        audio_doc = {
            "filename": file.filename,
            "content": base64.b64encode(content).decode("utf-8")
        }

        # Inserting into the database
        result = await db.audio.insert_one(audio_doc)

        return {"message": "Audio file uploaded", "id": str(result.inserted_id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading audio: {str(e)}")


@app.get("/audio")
async def get_audio_files():
    """
    Get a list of available audio files (metadata only, no content).
    """
    try:
        # Query audio collection to exclude the content field to reduce response size
        cursor = db.audio.find({}, {"content": 0})

        # Converting cursor to list
        audio_files = await cursor.to_list(length=100)

        # Converting ObjectId to string
        audio_files = object_id_to_str(audio_files)

        return {"audio_files": audio_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio files: {str(e)}")


@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """
    Get a specific audio file by ID, including its content.
    """
    try:
        # Converting string ID to ObjectId
        try:
            oid = ObjectId(audio_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid audio ID format")

        # Query database
        audio = await db.audio.find_one({"_id": oid})

        # Checks if  the audio exists
        if not audio:
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Converting ObjectId to string for JSON serialization
        audio = object_id_to_str(audio)

        return audio

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio file: {str(e)}")


# Player score endpoints
@app.post("/player_score")
async def add_score(score: PlayerScore):
    """
    Add a new player score to the database.
    """
    try:
        # Sanitizes inputs to prevent injection
        player_name = sanitize_input(score.player_name)

        # Creates the  score document
        score_doc = {
            "player_name": player_name,
            "score": score.score
        }

        # Inserting into the database
        result = await db.scores.insert_one(score_doc)

        return {"message": "Score recorded", "id": str(result.inserted_id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording score: {str(e)}")


@app.get("/player_scores")
async def get_scores():
    """
    Get player scores.
    """
    try:
        # Query scores collection
        cursor = db.scores.find()

        # Converting cursor to list
        scores = await cursor.to_list(length=100)

        # Converting ObjectId to string
        scores = object_id_to_str(scores)

        return {"scores": scores}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving scores: {str(e)}")


# Database initialization to create indexes for better a performance
@app.on_event("startup")
async def startup_event():
    """Initialize database indexes on startup."""
    # Sprites collection indexes
    await db.sprites.create_index("filename")

    # Audio collection indexes
    await db.audio.create_index("filename")

    # Scores collection indexes
    await db.scores.create_index("player_name")

    print("Database indexes initialized")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)