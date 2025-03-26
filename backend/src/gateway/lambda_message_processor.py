from fastapi import APIRouter, Request, Response
import json
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

@router.post("/process-message")
async def process_message(request: Request):
    """Process WebSocket messages sent from Lambda"""
    try:
        # Parse the request body
        data = await request.json()
        
        # Extract message details
        client_id = data.get("clientId")
        connection_id = data.get("connectionId")
        message = data.get("message", {})
        
        logger.info(f"Processing message from Lambda: {client_id}, {connection_id}, {message}")
        
        # Handle different message commands
        command = message.get("command")
        
        if command == "text_query":
            text = message.get("text", "")
            # Import voice assistants here to avoid circular imports
            from src.main import voice_assistants
            
            # Create voice assistant if needed
            if client_id not in voice_assistants:
                # This is where you'd initialize the voice assistant
                # For now, return an error message
                return {
                    "response": {
                        "type": "error",
                        "text": "Voice assistant not initialized. Please reconnect."
                    }
                }
            
            # Process the query
            assistant = voice_assistants[client_id]
            await assistant.process_text_query(text)
            
            # Return empty response - actual response will be sent by the assistant
            return {"success": True}
        
        elif command == "audio_data":
            # Process audio data
            audio = message.get("audio")
            
            # Import voice assistants
            from src.main import voice_assistants
            
            if client_id in voice_assistants:
                assistant = voice_assistants[client_id]
                
                # Convert base64 to bytes
                import base64
                try:
                    audio_bytes = base64.b64decode(audio.split(",")[1] if "," in audio else audio)
                    await assistant.process_audio_data(audio_bytes)
                    return {"success": True}
                except Exception as e:
                    logger.error(f"Error processing audio data: {str(e)}")
                    return {
                        "response": {
                            "type": "error",
                            "text": f"Error processing audio: {str(e)}"
                        }
                    }
            else:
                return {
                    "response": {
                        "type": "error",
                        "text": "Voice assistant not initialized"
                    }
                }
        
        elif command == "toggle_listen":
            # Process toggle listen
            listening = message.get("listening", False)
            logger.info(f"Setting listening state to {listening}")
            return {"success": True}
        
        elif command == "toggle_mute":
            # Process toggle mute
            from src.main import voice_assistants
            muted = message.get("muted", False)
            
            if client_id in voice_assistants:
                voice_assistants[client_id].is_muted = muted
                return {"success": True}
            else:
                return {
                    "response": {
                        "type": "error",
                        "text": "Voice assistant not initialized"
                    }
                }
        
        elif command == "interrupt_speech":
            # Process interrupt speech
            from src.main import voice_assistants
            
            if client_id in voice_assistants:
                voice_assistants[client_id].is_interrupted = True
                return {"success": True}
            else:
                return {
                    "response": {
                        "type": "error",
                        "text": "Voice assistant not initialized"
                    }
                }
        
        else:
            return {
                "response": {
                    "type": "error",
                    "text": f"Unknown command: {command}"
                }
            }
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "response": {
                "type": "error",
                "text": "Server error processing message"
            }
        }