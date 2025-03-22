import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
import motor.motor_asyncio
from dotenv import load_dotenv

# Loading environments variables from .env file
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Multimedia Game Assets API",
    description="API for storing and retrieving multimedia game asset like sprites, audio files, and the player scores",
    version="1.0.0"
)

# Getting MongoDB connection string from .env
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
if not MONGO_CONNECTION_STRING:
    raise ValueError("No MongoDB connection string found. Please check your .env file.")

# Connecting to MongoDB Atlas
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_CONNECTION_STRING)
db = client.multimedia_db

# Defining player score models
class PlayerScore(BaseModel):
    player_name: str
    score: int

# Health check endpoint
@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "API is running"}

# Placeholder for upload_sprite endpoint
@app.post("/upload_sprite")
async def upload_sprite(file: UploadFile = File(...)):
    # This is a placeholder for the actual implementation
    return {"message": "Sprite upload endpoint - NOT DONE"}

# Placeholder for upload_audio endpoint
@app.post("/upload_audio")
async def upload_audio(file: UploadFile = File(...)):
    # This is a placeholder for the actual implementation
    return {"message": "Audio upload endpoint - NOT DONE"}

# Placeholder for player_score endpoint
@app.post("/player_score")
async def add_score(score: PlayerScore):
    # This is a placeholder for the actual implementation
    return {"message": "Player score endpoint - NOT DONE"}

# Run the server if this file is executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)