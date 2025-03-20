import uvicorn
import asyncio
import logging
import json
import base64
import os
from typing import List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime

from src.websocket.connection import ConnectionManager
from src.voice.assistant import VoiceAssistant
from src.utils.logger import setup_logger

# Setup logging
logger = setup_logger(name="main", level="INFO")

# Initialize FastAPI app
app = FastAPI(title="DB Assistant")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and Setup templates
# Update these paths
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# Initialize WebSocket connection manager
connection_manager = ConnectionManager()

# Initialize voice assistant instances for each client
voice_assistants = {}


@app.get("/")
async def get_index(request: Request):
    """Serve the main page"""
    return templates.TemplateResponse("index.html", {"request": request})



@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication"""
    await connection_manager.connect(websocket)
    
    try:
        # Initialize voice assistant for this connection
        voice_assistant = VoiceAssistant(
            connection_manager=connection_manager,
            websocket=websocket
        )
        
        # Store assistant for this client
        voice_assistants[client_id] = voice_assistant
        
        # Start the voice assistant
        await voice_assistant.start()
        
        # Send ready message
        await connection_manager.send_personal_message(
            {"type": "status", "text": "Assistant ready. Say 'Agent' to activate."}, 
            websocket
        )
        
        # Listen for commands from the client
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            
            if command == "text_query":
                query = data.get("text", "")
                if query:
                    await voice_assistant.process_text_query(query)
                    
            elif command == "audio_data":
                # Process audio data from browser
                audio_data = data.get("audio")
                if audio_data:
                    # Convert base64 to bytes if needed
                    if isinstance(audio_data, str) and audio_data.startswith("data:audio"):
                        # Handle data URL format
                        audio_bytes = base64.b64decode(audio_data.split(",")[1])
                    elif isinstance(audio_data, str):
                        # Handle plain base64
                        audio_bytes = base64.b64decode(audio_data)
                    else:
                        audio_bytes = audio_data
                        
                    await voice_assistant.process_audio_data(audio_bytes)
                    
            elif command == "toggle_listen":
                is_listening = data.get("listening", False)
                await connection_manager.send_personal_message(
                    {"type": "status", "text": f"{'Listening' if is_listening else 'Stopped listening'}"}, 
                    websocket
                )
                
            elif command == "toggle_mute":
                is_muted = data.get("muted", False)
                voice_assistant.is_muted = is_muted
                await connection_manager.send_personal_message(
                    {"type": "status", "text": f"{'Assistant muted' if is_muted else 'Assistant unmuted'}"}, 
                    websocket
                )
                
            elif command == "interrupt_speech":
                # New command to handle interruption from client
                logger.info(f"Client {client_id} requested speech interruption")
                voice_assistant.is_interrupted = True
                await connection_manager.send_personal_message(
                    {"type": "status", "text": "Speech interrupted"}, 
                    websocket
                )
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        
    finally:
        # Clean up
        if client_id in voice_assistants:
            await voice_assistants[client_id].stop()
            del voice_assistants[client_id]
            
        connection_manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    """Runs when the server starts"""
    logger.info("Server is starting up")
    

@app.on_event("shutdown")
async def shutdown_event():
    """Runs when the server shuts down"""
    logger.info("Server is shutting down")
    for client_id, assistant in list(voice_assistants.items()):
        await assistant.stop()
    voice_assistants.clear()


# Function to test the FastAPI app
def test_app():
    """Simple test function for the FastAPI app"""
    logger.info("Starting test server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    test_app()