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
            

        if client_id not in voice_assistants:
            from src.websocket.connection import ConnectionManager
            from src.voice.assistant import VoiceAssistant
            
            # Create a dummy websocket for Lambda-initiated assistants
            class DummyWebSocket:
                def __init__(self):
                    self.scope = {"path": f"/ws/{client_id}"}
                    
                async def send_json(self, data):
                    # Messages will be sent via Lambda instead
                    pass
            
            # Create new connection manager or reuse existing one
            connection_manager = ConnectionManager()
            
            # Initialize voice assistant
            voice_assistant = VoiceAssistant(
                connection_manager=connection_manager,
                websocket=DummyWebSocket()
            )
            
            # Store and start the assistant
            voice_assistants[client_id] = voice_assistant
            await voice_assistant.start()
            
            logger.info(f"Created new voice assistant for client {client_id}")
            
                    
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