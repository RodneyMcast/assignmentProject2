"""
Database Essentials Home Assignment - Multimedia Game Assets API
This script creates a RESTful API for storing and retrieving game assets.
"""

import os
import base64
import json
import html
import re
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Form
from pydantic import BaseModel, Field
import motor.motor_asyncio
from bson import ObjectId
from dotenv import load_dotenv

# Loading .env
load_dotenv()

# Creates the FastAPI app
app = FastAPI(
    title="Multimedia Game Assets API",
    description="API for storing and retrieving multimedia game assets including sprites, audio files, and player scores",
    version="1.0.0"
)

# Getting MongoDB connection string from .env file
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
if not MONGO_CONNECTION_STRING:
    raise ValueError("No MongoDB connection string found. Please check your .env file.")

# Connecting to MongoDB Atlas
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_CONNECTION_STRING)
db = client.multimedia_db

# Constants
GRIDFS_THRESHOLD = 16 * 1024 * 1024 - 512 * 1024  # 16MB - 512KB buffer
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB


# Defining models
class PlayerScore(BaseModel):
    """Model for player score data."""
    player_name: str
    score: int
    game_level: Optional[str] = "default"


# Useful helper functions
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


def sanitize_input(value: Optional[str]) -> Optional[str]:
    """Sanitize user input to prevent NoSQL injection and XSS attacks."""
    if value is None:
        return None

    # Escape HTML special characters to prevent XSS
    value = html.escape(value)

    # Removes the MongoDB operators to prevent NoSQL injections
    value = re.sub(r'\$', '', value)

    return value


async def init_db():
    """Initialize database indexes."""
    # Sprites collection indexes
    await db.sprites.create_index("filename")
    await db.sprites.create_index("metadata.tags")

    # Audio collection indexes
    await db.audio.create_index("filename")
    await db.audio.create_index("metadata.tags")

    # Scores collection indexes
    await db.scores.create_index("player_name")
    await db.scores.create_index([("score", -1)])  # It's in descending for high scores
    await db.scores.create_index("timestamp")

    print("Database indexes initialized")


# Initializes the database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connections and indexes on startup."""
    await init_db()


# Health check endpoint
@app.get("/")
async def health_check():
    """Check if the API is running."""
    return {"status": "healthy", "message": "API is running"}


# Sprite endpoints
@app.post("/upload_sprite")
async def upload_sprite(
        file: UploadFile = File(...),
        tags: Optional[str] = Form(None),
        description: Optional[str] = Form(None)
):
    """
    Upload a sprite image file.

    - For files < 16MB: Stored directly in the database as Base64
    - For files >= 16MB: Not supported in this version

    Tags can be provided as a comma-separated string.
    """
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)

        # Check file size
        if file_size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE / (1024 * 1024)}MB."
            )

        # Prepares the tags
        tag_list = []
        if tags:
            # Sanitizes input to prevent injections
            tags = sanitize_input(tags)
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Sanitizes the descriptions
        if description:
            description = sanitize_input(description)

        # Creates the sprite documents
        sprite_doc = {
            "filename": file.filename,
            "contentType": file.content_type or "image/png",
            "uploadDate": datetime.datetime.now(),
            "size": file_size,
            "metadata": {
                "tags": tag_list or ["sprite"],
                "description": description or f"Sprite image: {file.filename}"
            }
        }

        # Handles the files storage based on its size
        if file_size < GRIDFS_THRESHOLD:
            # Store directly in the document
            sprite_doc["content"] = base64.b64encode(content).decode("utf-8")
        else:
            # For simplicity here, I'll just note that it would use GridFS
            # NEED TO CHANGE LATER
            raise HTTPException(
                status_code=413,
                detail="File too large for direct storage. GridFS implementation required."
            )

        # Inserting into the database
        result = await db.sprites.insert_one(sprite_doc)

        return {
            "message": "Sprite uploaded successfully",
            "id": str(result.inserted_id),
            "filename": file.filename,
            "size": file_size,
            "tags": tag_list
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading sprite: {str(e)}")


@app.get("/sprites")
async def get_sprites(
        limit: int = Query(10, ge=1, le=100),
        skip: int = Query(0, ge=0),
        tag: Optional[str] = Query(None)
):
    """
    Get a list of available sprites (metadata only, no content).

    - limit: Maximum number of sprites to return (1-100)
    - skip: Number of sprites to skip (pagination)
    - tag: Filter sprites by tag
    """
    try:
        # Building query
        query = {}
        if tag:
            # Sanitizes the input to prevent injections
            tag = sanitize_input(tag)
            query["metadata.tags"] = tag

        # Query sprites collection to exclude content field to reduce response size
        cursor = db.sprites.find(query, {"content": 0}).skip(skip).limit(limit)

        # Converts the cursor to list and format for responses
        sprites = await cursor.to_list(length=limit)

        # Gets the total count for pagination
        total_count = await db.sprites.count_documents(query)

        # Converting ObjectId to string
        sprites = object_id_to_str(sprites)

        return {
            "sprites": sprites,
            "count": len(sprites),
            "total": total_count,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sprites: {str(e)}")


@app.get("/sprites/{sprite_id}")
async def get_sprite(sprite_id: str, include_content: bool = Query(True)):
    """
    Get a specific sprite by ID, optionally including its content.

    - sprite_id: The ID of the sprite to retrieve
    - include_content: Whether to include the file content (Base64 encoded)
    """
    try:
        # Converting string ID to ObjectId
        try:
            oid = ObjectId(sprite_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid sprite ID format")

        # Builds projection
        projection = None if include_content else {"content": 0}

        # Query database
        sprite = await db.sprites.find_one({"_id": oid}, projection)

        # Checks if sprite actually exists
        if not sprite:
            raise HTTPException(status_code=404, detail="Sprite not found")

        # Converting ObjectId to string for JSON serialization
        sprite = object_id_to_str(sprite)

        return sprite

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sprite: {str(e)}")


# Audio endpoints
@app.post("/upload_audio")
async def upload_audio(
        file: UploadFile = File(...),
        tags: Optional[str] = Form(None),
        description: Optional[str] = Form(None)
):
    """
    Upload an audio file.

    - For files < 16MB: Stored directly in the database as Base64
    - For files >= 16MB: Not supported in this version

    Tags can be provided as a comma-separated string.
    """
    try:
        # Reads the file contents
        content = await file.read()
        file_size = len(content)

        # Checks the file size
        if file_size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE / (1024 * 1024)}MB."
            )

        # Prepares the tags
        tag_list = []
        if tags:
            # Sanitizes the input to prevent injections
            tags = sanitize_input(tags)
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Sanitizes the description
        if description:
            description = sanitize_input(description)

        # Creates the audio documents
        audio_doc = {
            "filename": file.filename,
            "contentType": file.content_type or "audio/wav",
            "uploadDate": datetime.datetime.now(),
            "size": file_size,
            "metadata": {
                "tags": tag_list or ["audio"],
                "description": description or f"Audio file: {file.filename}"
            }
        }

        # Handles file storage based on actual size
        if file_size < GRIDFS_THRESHOLD:
            # Store directly in the document
            audio_doc["content"] = base64.b64encode(content).decode("utf-8")
        else:
            # For simplicity here I'll just note that it would use GridFS
            # NEED TO CHANGE LATER
            raise HTTPException(
                status_code=413,
                detail="File too large for direct storage. GridFS implementation required."
            )

        # Inserting into the database
        result = await db.audio.insert_one(audio_doc)

        return {
            "message": "Audio uploaded successfully",
            "id": str(result.inserted_id),
            "filename": file.filename,
            "size": file_size,
            "tags": tag_list
        }

    except HTTPException:
        # Re-raises HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading audio: {str(e)}")


@app.get("/audio")
async def get_audio_files(
        limit: int = Query(10, ge=1, le=100),
        skip: int = Query(0, ge=0),
        tag: Optional[str] = Query(None)
):
    """
    Get a list of available audio files (metadata only, no content).

    - limit: Maximum number of audio files to return (1-100)
    - skip: Number of audio files to skip (pagination)
    - tag: Filter audio files by tag
    """
    try:
        # Building query
        query = {}
        if tag:
            # Sanitizes the input to prevent injections
            tag = sanitize_input(tag)
            query["metadata.tags"] = tag

        # Query audio collection to exclude contents field to reduce response size
        cursor = db.audio.find(query, {"content": 0}).skip(skip).limit(limit)

        # Converts the cursor to list and format for responses
        audio_files = await cursor.to_list(length=limit)

        # Getting the total count for pagination
        total_count = await db.audio.count_documents(query)

        # Converting ObjectId to string
        audio_files = object_id_to_str(audio_files)

        return {
            "audio_files": audio_files,
            "count": len(audio_files),
            "total": total_count,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio files: {str(e)}")


@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str, include_content: bool = Query(True)):
    """
    Get a specific audio file by ID, optionally including its content.

    - audio_id: The ID of the audio file to retrieve
    - include_content: Whether to include the file content (Base64 encoded)
    """
    try:
        # Converting string ID to ObjectId
        try:
            oid = ObjectId(audio_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid audio ID format")

        # Building projection
        projection = None if include_content else {"content": 0}

        # Query database
        audio = await db.audio.find_one({"_id": oid}, projection)

        # Checks if audio actually exists
        if not audio:
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Converting ObjectId to string for JSON serialization
        audio = object_id_to_str(audio)

        return audio

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio file: {str(e)}")


# Player score endpoints
@app.post("/player_score")
async def add_score(score: PlayerScore):
    """
    Add a new player score to the database.

    - player_name: Name of the player
    - score: Numerical score value
    - game_level: Optional game level identifier
    """
    try:
        # Sanitizes the inputs to prevent injections
        player_name = sanitize_input(score.player_name)
        game_level = sanitize_input(score.game_level)

        # Creating the score documents
        score_doc = {
            "player_name": player_name,
            "score": score.score,
            "timestamp": datetime.datetime.now(),
            "game_level": game_level,
            "metadata": {
                "platform": "web",
                "game_version": "1.0"
            }
        }

        # Inserts into database
        result = await db.scores.insert_one(score_doc)

        return {
            "message": "Score recorded successfully",
            "id": str(result.inserted_id),
            "player_name": player_name,
            "score": score.score,
            "game_level": game_level
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording score: {str(e)}")


@app.get("/player_scores")
async def get_scores(
        limit: int = Query(10, ge=1, le=100),
        skip: int = Query(0, ge=0),
        sort_by: str = Query("score", pattern="^(score|timestamp)$"),  # Fixed regex warning
        order: int = Query(-1, ge=-1, le=1),
        player_name: Optional[str] = Query(None),
        game_level: Optional[str] = Query(None)
):
    """
    Get player scores, with options for sorting, filtering, and pagination.

    - limit: Maximum number of scores to return (1-100)
    - skip: Number of scores to skip (pagination)
    - sort_by: Field to sort by ('score' or 'timestamp')
    - order: Sort order (1 for ascending, -1 for descending)
    - player_name: Filter scores by player name
    - game_level: Filter scores by game level
    """
    try:
        # Building the query
        query = {}

        if player_name:
            # Sanitizes the input to prevent injections
            player_name = sanitize_input(player_name)
            query["player_name"] = player_name

        if game_level:
            # Sanitizes the  input to prevent injections
            game_level = sanitize_input(game_level)
            query["game_level"] = game_level

        # Setting up sort option
        sort_option = [(sort_by, order)]

        # Query scores collection
        cursor = db.scores.find(query).skip(skip).sort(sort_option).limit(limit)

        # Converting cursor to list
        scores = await cursor.to_list(length=limit)

        # Getting the total count for pagination
        total_count = await db.scores.count_documents(query)

        # Formats the scores for response
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

        return {
            "scores": formatted_scores,
            "count": len(formatted_scores),
            "total": total_count,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving scores: {str(e)}")


@app.get("/player_scores/{score_id}")
async def get_score(score_id: str):
    """
    Get a specific score by ID.

    - score_id: The ID of the score to retrieve
    """
    try:
        # Converting string ID to ObjectId
        try:
            oid = ObjectId(score_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid score ID format")

        # Query database
        score = await db.scores.find_one({"_id": oid})

        # Checks if score actually exists
        if not score:
            raise HTTPException(status_code=404, detail="Score not found")

        # Formats the score for responses
        formatted_score = {
            "id": str(score["_id"]),
            "player_name": score["player_name"],
            "score": score["score"],
            "timestamp": score["timestamp"].isoformat(),
            "game_level": score["game_level"],
            "metadata": score.get("metadata", {})
        }

        return formatted_score

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving score: {str(e)}")



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)