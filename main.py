import os
import base64
import html
import re
import datetime
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import motor.motor_asyncio
from bson import ObjectId
from dotenv import load_dotenv

# Loading .env file
load_dotenv()

# Creating the FastAPI app
app = FastAPI(
    title="Multimedia Game Assets API",
    description="API for storing and retrieving multimedia game assets including sprites, audio files, and player scores",
    version="1.0.0"
)

# Adding CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gets the MongoDB connection string from environment variables
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
if not MONGO_CONNECTION_STRING:
    raise ValueError("No MongoDB connection string found. Please check your .env file.")

# Connects to MongoDB Atlas with timeouts optimized for Vercel (which is 10s limit) and retryWrites enabled
try:
    client = motor.motor_asyncio.AsyncIOMotorClient(
        MONGO_CONNECTION_STRING,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        maxPoolSize=10,
        retryWrites=True
    )
    # Forces a connection to test it works
    client.admin.command('ismaster')
    print("MongoDB connection successful")
except Exception as e:
    print(f"MongoDB connection error: {e}")
    # letting the app start anyway but operations will fail if DB is unreachable
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

# Helper functions
def sanitize_input(value: Optional[str]) -> Optional[str]:
    """
    Sanitize user input to prevent NoSQL injection and XSS attacks.
    This function applies multiple layers of security filters.
    """
    if value is None:
        return None

    # Escape HTML special characters to prevent XSS
    value = html.escape(value)

    # Removes the MongoDB operators to prevent NoSQL injection
    value = re.sub(r'\$', '', value)

    # Removes other potential NoSQL injection patterns
    value = re.sub(r'[\{\}]', '', value)  # Remove curly braces
    value = re.sub(r'[\[\]]', '', value)  # Remove square brackets

    # Removes common JavaScript injection patterns
    value = re.sub(r'<script', '<blocked', value, flags=re.IGNORECASE)

    # Limits the string length to prevent abuse
    max_length = 500  # Reasonable limit for text fields
    if len(value) > max_length:
        value = value[:max_length]

    return value

def validate_object_id(id_str: str) -> ObjectId:
    """
    Validate and convert a string ID to MongoDB ObjectId.
    Raises an HTTPException if the ID is invalid.

    This is a security measure to prevent injection attacks via malformed IDs.
    """
    try:
        if not id_str or not ObjectId.is_valid(id_str):
            raise ValueError("Invalid ID format")
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

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

async def init_db():
    """Initialize database indexes and security settings."""
    try:
        # Sprites collection indexes
        await db.sprites.create_index("filename")
        await db.sprites.create_index("metadata.tags")

        # Audio collection indexes
        await db.audio.create_index("filename")
        await db.audio.create_index("metadata.tags")

        # Scores collection indexes
        await db.scores.create_index("player_name")
        await db.scores.create_index([("score", -1)])  # Descending for high scores
        await db.scores.create_index("timestamp")

        # Security logs collection for tracking access patterns
        await db.security_logs.create_index("timestamp")
        await db.security_logs.create_index("action")

        # Logging successful initialization
        print("Database indexes and security settings initialized")

        # Creating a security log entry
        await db.security_logs.insert_one({
            "action": "initialize",
            "timestamp": datetime.datetime.now(),
            "message": "Database initialization completed successfully"
        })
    except Exception as e:
        print(f"Error initializing database: {e}")

# Initializing the database on startup
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
            # Sanitizes the inputs to prevent injections
            tags = sanitize_input(tags)
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Sanitizes the description
        if description:
            description = sanitize_input(description)

        # Creating the sprite documents
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

        # Handles the file storage based on the size
        if file_size < GRIDFS_THRESHOLD:
            # Store directly in the document
            sprite_doc["content"] = base64.b64encode(content).decode("utf-8")
        else:
            # For simplicity here, I'll just note that it would use GridFS
            # NEED TO CHANGE LATER maybe prob not
            raise HTTPException(
                status_code=413,
                detail="File too large for direct storage. GridFS implementation required."
            )

        # Inserting into the database
        result = await db.sprites.insert_one(sprite_doc)

        # Logs the upload for security tracking
        await db.security_logs.insert_one({
            "action": "upload",
            "resource_type": "sprite",
            "resource_id": str(result.inserted_id),
            "timestamp": datetime.datetime.now()
        })

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
        # Generates a unique error ID for tracking
        error_id = str(ObjectId())
        # Logs the error
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "sprite_upload",
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database at least it will print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error uploading sprite. Error ID: {error_id}"
        )

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
            # Sanitizes the input to prevent injection
            tag = sanitize_input(tag)
            query["metadata.tags"] = tag

        # Query sprites collection to exclude content field to reduce response size
        cursor = db.sprites.find(query, {"content": 0}).skip(skip).limit(limit)

        # Converting the cursor to list and format for response
        sprites = await cursor.to_list(length=limit)

        # Gets the total count for pagination
        total_count = await db.sprites.count_documents(query)

        # Converting ObjectId to string
        sprites = object_id_to_str(sprites)

        # Logs the access for security tracking
        await db.security_logs.insert_one({
            "action": "list",
            "resource_type": "sprites",
            "count": len(sprites),
            "query_params": {"limit": limit, "skip": skip, "tag": tag},
            "timestamp": datetime.datetime.now()
        })

        return {
            "sprites": sprites,
            "count": len(sprites),
            "total": total_count,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        # Generating a unique error ID for tracking
        error_id = str(ObjectId())
        # Log the error
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "sprites_list",
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving sprites. Error ID: {error_id}"
        )

@app.get("/sprites/{sprite_id}")
async def get_sprite(sprite_id: str, include_content: bool = Query(True)):
    """
    Get a specific sprite by ID, optionally including its content.

    - sprite_id: The ID of the sprite to retrieve
    - include_content: Whether to include the file content (Base64 encoded)
    """
    try:
        # Validates and converts string ID to ObjectId
        oid = validate_object_id(sprite_id)

        # Builds the projection to optimize for Vercel by limiting data returned
        projection = None if include_content else {"content": 0}

        #Using a timeout to prevent long-running queries
        # This should help with the Vercel timeout issue   CHECK HERE
        sprite = await db.sprites.find_one(
            {"_id": oid},
            projection
        )

        # Checking if sprite exists
        if not sprite:
            #Logging access to non-existent resources
            await db.security_logs.insert_one({
                "action": "access_attempt",
                "resource_type": "sprite",
                "resource_id": sprite_id,
                "timestamp": datetime.datetime.now(),
                "message": "Attempt to access non-existent sprite"
            })
            raise HTTPException(status_code=404, detail="Sprite not found")

        # Converting the ObjectId to string for JSON serialization
        sprite = object_id_to_str(sprite)

        # Logs the access for security tracking
        await db.security_logs.insert_one({
            "action": "retrieve",
            "resource_type": "sprite",
            "resource_id": sprite_id,
            "include_content": include_content,
            "timestamp": datetime.datetime.now()
        })

        return sprite

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        #Logs unexpected errors but does not expose details to client
        error_id = str(ObjectId())
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "sprite",
                "resource_id": sprite_id,
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving sprite. Error ID: {error_id}"
        )

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
        # Reading file contents
        content = await file.read()
        file_size = len(content)

        # Checks the size of the file
        if file_size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE / (1024 * 1024)}MB."
            )

        # Prepares the tags
        tag_list = []
        if tags:
            # Sanitizes the inputs to prevent injection
            tags = sanitize_input(tags)
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Sanitizes the description
        if description:
            description = sanitize_input(description)

        # Creating the audio document
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

        # Handles the file storage based on its size
        if file_size < GRIDFS_THRESHOLD:
            # Store directly in the document
            audio_doc["content"] = base64.b64encode(content).decode("utf-8")
        else:
            # For simplicity here, I'll just note that it would use GridFS
            # NEED TO CHANGE LATER maybe prob not
            raise HTTPException(
                status_code=413,
                detail="File too large for direct storage. GridFS implementation required."
            )

        # Inserting into the database
        result = await db.audio.insert_one(audio_doc)

        # Logging the upload for security tracking
        await db.security_logs.insert_one({
            "action": "upload",
            "resource_type": "audio",
            "resource_id": str(result.inserted_id),
            "timestamp": datetime.datetime.now()
        })

        return {
            "message": "Audio uploaded successfully",
            "id": str(result.inserted_id),
            "filename": file.filename,
            "size": file_size,
            "tags": tag_list
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Generates a unique error ID for tracking
        error_id = str(ObjectId())
        # Logs the error
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "audio_upload",
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error uploading audio. Error ID: {error_id}"
        )

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
        # Builds the query
        query = {}
        if tag:
            # Sanitizes the input to prevent injections
            tag = sanitize_input(tag)
            query["metadata.tags"] = tag

        # Querys the audio collection to exclude content field to reduce response size
        cursor = db.audio.find(query, {"content": 0}).skip(skip).limit(limit)

        # Converts the cursor to list and format for responses
        audio_files = await cursor.to_list(length=limit)

        # Gets the total count for pagination
        total_count = await db.audio.count_documents(query)

        # Converts the ObjectId to string
        audio_files = object_id_to_str(audio_files)

        # Logging the access for security tracking
        await db.security_logs.insert_one({
            "action": "list",
            "resource_type": "audio",
            "count": len(audio_files),
            "query_params": {"limit": limit, "skip": skip, "tag": tag},
            "timestamp": datetime.datetime.now()
        })

        return {
            "audio_files": audio_files,
            "count": len(audio_files),
            "total": total_count,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        # Generates a unique error ID for tracking
        error_id = str(ObjectId())
        # Logs the error
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "audio_list",
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving audio files. Error ID: {error_id}"
        )

@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str, include_content: bool = Query(True)):
    """
    Get a specific audio file by ID, optionally including its content.

    - audio_id: The ID of the audio file to retrieve
    - include_content: Whether to include the file content (Base64 encoded)
    """
    try:
        # Validates and converts the string ID to ObjectId
        oid = validate_object_id(audio_id)

        # Building projection
        projection = None if include_content else {"content": 0}

        # Querys database
        audio = await db.audio.find_one({"_id": oid}, projection)

        # Checks if audio exists
        if not audio:
            # Logs access to non-existent resource
            await db.security_logs.insert_one({
                "action": "access_attempt",
                "resource_type": "audio",
                "resource_id": audio_id,
                "timestamp": datetime.datetime.now(),
                "message": "Attempt to access non-existent audio"
            })
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Converting ObjectId to string for JSON serialization
        audio = object_id_to_str(audio)

        # Logs the access for security tracking
        await db.security_logs.insert_one({
            "action": "retrieve",
            "resource_type": "audio",
            "resource_id": audio_id,
            "include_content": include_content,
            "timestamp": datetime.datetime.now()
        })

        return audio

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Generates a unique error ID for tracking
        error_id = str(ObjectId())
        # Logs the error
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "audio",
                "resource_id": audio_id,
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving audio. Error ID: {error_id}"
        )

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
        # Sanitizes the inputs to prevent injection
        player_name = sanitize_input(score.player_name)
        game_level = sanitize_input(score.game_level)

        # Creates score documents
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

        # Inserts into the database
        result = await db.scores.insert_one(score_doc)

        # Logs the score submission for security tracking
        await db.security_logs.insert_one({
            "action": "submit",
            "resource_type": "score",
            "resource_id": str(result.inserted_id),
            "player": player_name,
            "timestamp": datetime.datetime.now()
        })

        return {
            "message": "Score recorded successfully",
            "id": str(result.inserted_id),
            "player_name": player_name,
            "score": score.score,
            "game_level": game_level
        }

    except Exception as e:
        # Generates a unique error ID for tracking
        error_id = str(ObjectId())
        # Log the error
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "score_submit",
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error recording score. Error ID: {error_id}"
        )

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
        # Builds the query
        query = {}

        if player_name:
            # Sanitizes the input to prevent injections
            player_name = sanitize_input(player_name)
            query["player_name"] = player_name

        if game_level:
            # Sanitizes the input to prevent injections
            game_level = sanitize_input(game_level)
            query["game_level"] = game_level

        # Sets up the sort option
        sort_option = [(sort_by, order)]

        # Query for the scores collection
        cursor = db.scores.find(query).skip(skip).sort(sort_option).limit(limit)

        # Converts the cursor to list
        scores = await cursor.to_list(length=limit)

        # Gets the total count for pagination
        total_count = await db.scores.count_documents(query)

        # Formating the scores for response
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

        # Logs the access for security tracking
        await db.security_logs.insert_one({
            "action": "list",
            "resource_type": "scores",
            "count": len(formatted_scores),
            "query_params": {
                "limit": limit,
                "skip": skip,
                "sort_by": sort_by,
                "order": order,
                "player_name": player_name,
                "game_level": game_level
            },
            "timestamp": datetime.datetime.now()
        })

        return {
            "scores": formatted_scores,
            "count": len(formatted_scores),
            "total": total_count,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        # Generates a unique error ID for tracking
        error_id = str(ObjectId())
        # Logs the errors
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "scores_list",
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving scores. Error ID: {error_id}"
        )

@app.get("/player_scores/{score_id}")
async def get_score(score_id: str):
    """
    Get a specific score by ID.

    - score_id: The ID of the score to retrieve
    """
    try:
        # Validates and convert string ID to ObjectId
        oid = validate_object_id(score_id)

        # Query database
        score = await db.scores.find_one({"_id": oid})

        # Checking if score exists
        if not score:
            # Logs the access to non-existent resource
            await db.security_logs.insert_one({
                "action": "access_attempt",
                "resource_type": "score",
                "resource_id": score_id,
                "timestamp": datetime.datetime.now(),
                "message": "Attempt to access non-existent score"
            })
            raise HTTPException(status_code=404, detail="Score not found")

        # Formats the score for response
        formatted_score = {
            "id": str(score["_id"]),
            "player_name": score["player_name"],
            "score": score["score"],
            "timestamp": score["timestamp"].isoformat(),
            "game_level": score["game_level"],
            "metadata": score.get("metadata", {})
        }

        # Logs the access for security tracking
        await db.security_logs.insert_one({
            "action": "retrieve",
            "resource_type": "score",
            "resource_id": score_id,
            "timestamp": datetime.datetime.now()
        })

        return formatted_score

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Generates a unique error ID for tracking
        error_id = str(ObjectId())
        # Logging the error
        try:
            await db.security_logs.insert_one({
                "action": "error",
                "error_id": error_id,
                "resource_type": "score",
                "resource_id": score_id,
                "timestamp": datetime.datetime.now(),
                "error_details": str(e)
            })
        except:
            # If it can't log to the database it will at least print to console
            print(f"Error logging to database: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving score. Error ID: {error_id}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
