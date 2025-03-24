# Multimedia Game Assets API

A RESTful API for storing and retrieving game multimedia assets using MongoDB Atlas.

## Environment Setup (Task 1)

- **Python 3.11**: Programming language
- **FastAPI**: Web framework for building APIs
- **Uvicorn**: ASGI server implementation
- **Motor**: Asynchronous MongoDB driver
- **MongoDB Atlas**: Cloud database service

Setup instructions:
1. Create a virtual environment: `python -m venv .venv`
2. Activate it: `.venv\Scripts\activate` (Windows)
3. Install all dependencies: `pip install -r requirements.txt`
4. Create a .env file to store Environment variables (the users personal MongoDB credentials)

## Database Schema Design (Task 2)

The database uses three collections: Sprites, Audio, Scores

### Sprites Collection
- `_id`: Unique identifier
- `filename`: Original filename
- `content`: Base64 encoded image data

### Audio Collection
- `_id`: Unique identifier
- `filename`: Original filename
- `content`: Base64 encoded audio data

### Scores Collection
- `_id`: Unique identifier
- `player_name`: Name of the player
- `score`: Numerical score value

## API Endpoints (Task 3)

### Sprites
- `POST /upload_sprite`: Uploads a sprite image
- `GET /sprites`: Gets the list of all sprites (INFO: without content)
- `GET /sprites/{sprite_id}`: Gets the specific sprite by ID

### Audio
- `POST /upload_audio`: Uploads an audio file
- `GET /audio`: Gets the list of all audio files (INFO: without content)
- `GET /audio/{audio_id}`: Gets the specific audio file by ID

### Player Scores
- `POST /player_score`: Submits a player score
- `GET /player_scores`: Gets all  the player scores

## Security Measures (Task 4)

1. **Secure Credentials**
   - MongoDB connection string stored in environment variables
   - Sensitive data never hardcoded

2. **NoSQL Injection Prevention**
   - Input sanitization is used for all user-supplied data
   - Removal of MongoDB operators ($) from input strings for Nosql injection prevention 
   - Parameter validation

## Folder Structure

- `main.py`: Main application file with all API endpoints.
- `db_init.py`: Initializes the MongoDB database and sets up schemas and indexes.
- `db_populate.py`: Loads some sample data from folders to help test the API.
- `assets/`: Folder that contains sample sprites, audio, and player score data.
- `.env`: Environment variables (the users personal MongoDB credentials)
- `requirements.txt`: Python dependencies for the project.
- `render.yaml`: Deployment config for Render.

## Deployment

The project is deployed to Render.com. It uses Python 3.11 and installs dependencies from `requirements.txt`
Once deployed, the API can be tested via the built-in Swagger documentation at `/docs`.
