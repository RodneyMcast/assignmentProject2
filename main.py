import os
import base64
import datetime
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from pydantic import BaseModel, Field
import motor.motor_asyncio
from dotenv import load_dotenv
from bson import ObjectId

# Loading .env file
load_dotenv()

# Creates FastAPI app
app = FastAPI(
    title="Multimedia Game Assets API",
    description="API for storing and retrieving multimedia game assets including sprites, audio files, and player scores",
    version="1.0.0"
)

# Getting MongoDB connection string from .env
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
if not MONGO_CONNECTION_STRING:
    raise ValueError("No MongoDB connection string found. Please check your .env file.")

# Connects to MongoDB Atlas
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_CONNECTION_STRING)
db = client.multimedia_db

# GridFS size threshold (being 16MB to 512KB buffer)
GRIDFS_THRESHOLD = 16 * 1024 * 1024 - 512 * 1024


# Helper function to help converting ObjectId to string
def object_id_to_str(obj):
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


# Defines models
class PlayerScore(BaseModel):
    player_name: str
    score: int
    game_level: Optional[str] = "default"


class ScoreResponse(BaseModel):
    id: str
    player_name: str
    score: int
    timestamp: str
    game_level: str


class MetadataTags(BaseModel):
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class FileMetadata(BaseModel):
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None


# Health check endpoint
@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "API is running"}


# Sprite endpoints
@app.post("/upload_sprite")
async def upload_sprite(file: UploadFile = File(...), metadata: Optional[str] = None):
    """
    Upload a sprite image file.

    - For files < 16MB: Stored directly in the database as Base64
    - For files >= 16MB: Stored using GridFS

    Metadata can be provided as a JSON string.
    """
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)

        # Create sprite document
        sprite_doc = {
            "filename": file.filename,
            "contentType": file.content_type or "image/png",
            "uploadDate": datetime.datetime.now(),
            "size": file_size,
            "metadata": {
                "tags": ["sprite"],
                "description": f"Sprite image: {file.filename}"
            }
        }

        # Parsing metadata if provided
        if metadata:
            import json
            try:
                metadata_dict = json.loads(metadata)
                sprite_doc["metadata"].update(metadata_dict)
            except json.JSONDecodeError:
                pass

        # Handles file storage based on size
        if file_size < GRIDFS_THRESHOLD:
            # Stores directly in the document
            sprite_doc["content"] = base64.b64encode(content).decode("utf-8")
        else:
            # NOTE THIS IS A SIMULATION REMEMBER TO CHANGE
            sprite_doc["gridfs_id"] = None  # Placeholder
            raise HTTPException(status_code=413, detail="File too large. GridFS implementation required.")

        # Inserts into the database
        result = await db.sprites.insert_one(sprite_doc)

        return {
            "message": "Sprite uploaded successfully",
            "id": str(result.inserted_id),
            "filename": file.filename,
            "size": file_size
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading sprite: {str(e)}")


@app.get("/sprites")
async def get_sprites(limit: int = Query(10, ge=1, le=100)):
    """Get a list of available sprites (metadata only, no content)."""
    try:
        # Query sprites collection, excluding content field to reduce response size
        cursor = db.sprites.find({}, {"content": 0}).limit(limit)

        # Convert cursor to list and format for response
        sprites = await cursor.to_list(length=limit)

        # Convert ObjectId to string
        sprites = object_id_to_str(sprites)

        return {"sprites": sprites, "count": len(sprites)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sprites: {str(e)}")


@app.get("/sprites/{sprite_id}")
async def get_sprite(sprite_id: str):
    """Get a specific sprite by ID, including its content."""
    try:
        # Converting string ID to ObjectId
        from bson.objectid import ObjectId
        oid = ObjectId(sprite_id)

        # Query database
        sprite = await db.sprites.find_one({"_id": oid})

        # Checks if sprite actually exists
        if not sprite:
            raise HTTPException(status_code=404, detail="Sprite not found")

        # Converting ObjectId to string for JSON serialization
        sprite = object_id_to_str(sprite)

        return sprite

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sprite: {str(e)}")


# Audio endpoints
@app.post("/upload_audio")
async def upload_audio(file: UploadFile = File(...), metadata: Optional[str] = None):
    """
    Upload an audio file.

    - For files < 16MB: Stored directly in the database as Base64
    - For files >= 16MB: Stored using GridFS

    Metadata can be provided as a JSON string.
    """
    try:
        # Reads file contents
        content = await file.read()
        file_size = len(content)

        # Creating audio document
        audio_doc = {
            "filename": file.filename,
            "contentType": file.content_type or "audio/wav",
            "uploadDate": datetime.datetime.now(),
            "size": file_size,
            "metadata": {
                "tags": ["audio"],
                "description": f"Audio file: {file.filename}"
            }
        }

        # Parsing metadata if provided
        if metadata:
            import json
            try:
                metadata_dict = json.loads(metadata)
                audio_doc["metadata"].update(metadata_dict)
            except json.JSONDecodeError:
                pass

        # Handles file storage based on the size
        if file_size < GRIDFS_THRESHOLD:
            # Stores directly in the document
            audio_doc["content"] = base64.b64encode(content).decode("utf-8")
        else:
            # NOTE THIS IS A SIMULATION REMEMBER TO CHANGE
            audio_doc["gridfs_id"] = None  # Placeholder
            raise HTTPException(status_code=413, detail="File too large. GridFS implementation required.")

        # Inserts into database
        result = await db.audio.insert_one(audio_doc)

        return {
            "message": "Audio uploaded successfully",
            "id": str(result.inserted_id),
            "filename": file.filename,
            "size": file_size
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading audio: {str(e)}")


@app.get("/audio")
async def get_audio_files(limit: int = Query(10, ge=1, le=100)):
    """Get a list of available audio files (metadata only, no content)."""
    try:
        # Queries audio collection, excluding content field to reduce response size
        cursor = db.audio.find({}, {"content": 0}).limit(limit)

        # Converting cursor to list and format for response
        audio_files = await cursor.to_list(length=limit)

        # Converting ObjectId to string
        audio_files = object_id_to_str(audio_files)

        return {"audio_files": audio_files, "count": len(audio_files)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio files: {str(e)}")


@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """Get a specific audio file by ID, including its content."""
    try:
        # Converting string ID to ObjectId
        from bson.objectid import ObjectId
        oid = ObjectId(audio_id)

        # Query database
        audio = await db.audio.find_one({"_id": oid})

        # Checks if audio actually exists
        if not audio:
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Converting ObjectId to string for JSON serialization
        audio = object_id_to_str(audio)

        return audio

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio file: {str(e)}")


# Player score endpoints
@app.post("/player_score")
async def add_score(score: PlayerScore):
    """Add a new player score to the database."""
    try:
        # Creating score document
        score_doc = {
            "player_name": score.player_name,
            "score": score.score,
            "timestamp": datetime.datetime.now(),
            "game_level": score.game_level,
            "metadata": {
                "platform": "web",
                "game_version": "1.0"
            }
        }

        # Inserts into the database
        result = await db.scores.insert_one(score_doc)

        return {
            "message": "Score recorded successfully",
            "id": str(result.inserted_id),
            "player_name": score.player_name,
            "score": score.score
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording score: {str(e)}")


@app.get("/player_scores")
async def get_scores(
        limit: int = Query(10, ge=1, le=100),
        sort_by: str = Query("score", regex="^(score|timestamp)$"),
        order: int = Query(-1, ge=-1, le=1)
):
    """
    Get player scores, with options for sorting and limiting.

    - sort_by: 'score' or 'timestamp'
    - order: 1 for ascending, -1 for descending
    """
    try:
        # Sets up sort option
        sort_option = [(sort_by, order)]

        # Query scores collection
        cursor = db.scores.find().sort(sort_option).limit(limit)

        # Converts cursor to list and format for response
        scores = await cursor.to_list(length=limit)

        # Converting ObjectId to string and format dates
        formatted_scores = []
        for score in scores:
            formatted_score = {
                "id": str(score["_id"]),
                "player_name": score["player_name"],
                "score": score["score"],
                "timestamp": score["timestamp"].isoformat(),
                "game_level": score["game_level"]
            }
            formatted_scores.append(formatted_score)

        return {"scores": formatted_scores, "count": len(formatted_scores)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving scores: {str(e)}")



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)