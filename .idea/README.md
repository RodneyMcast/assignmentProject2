# Multimedia Game Assets API

This project is a RESTful API for storing and retrieving multimedia game assets including sprites (images), audio files, and player scores using FastAPI and MongoDB Atlas.

## Development Environment Setup

This project uses Python with the following dependencies:
- FastAPI For Modern and a fast web framework for building APIs
- Uvicorn ASGI server for running FastAPI applications
- Motor So we have Asynchronous MongoDB driver
- Pydanticso So that Data validation and settings management
- python-dotenv For managing the environment variables
- python-multipart0 For handling file uploads
- pymongo For MongoDB access

### Setup Instructions

1. Create a virtual environment:
```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate