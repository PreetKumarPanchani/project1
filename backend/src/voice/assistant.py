import asyncio
import json
import logging
import base64
import os
import io
import tempfile
import time
import threading
from typing import Optional, List, Dict, Any, Union
from openai import AsyncOpenAI
from groq import AsyncGroq
import numpy as np
from tabulate import tabulate
from dotenv import load_dotenv

from src.nlp.query_matcher_aws import QueryMatcherAWS
from src.query.query_mappings import QueryMappings
from src.database.db_executor_aws import AWSPostgresExecutor
from src.config.config_manager import ConfigManager
from src.utils.logger import setup_logger

import boto3
import json


# Setup logging
logger = setup_logger(name="voice_assistant", level="INFO")



class VoiceAssistant:
    def __init__(self, connection_manager, websocket):
        """
        Initialize voice assistant with WebSocket support
        
        Args:
            connection_manager: WebSocket connection manager
            websocket: WebSocket for this client
        """
        # WebSocket
        self.connection_manager = connection_manager
        self.websocket = websocket
        
        # State
        self.wake_word = "Agent"
        self.is_activated = True   # When dont using wake word, assistant must be activated , else it will be deactivated in the starting 
        self.is_muted = False
        self.is_speaking = False
        self.is_interrupted = False
        self.speech_lock = threading.Lock()  # Added lock for better speech handling
        
        # Load environment variables
        load_dotenv()
        
        # Initialize API clients
        self.openai_client = AsyncOpenAI()
        self.groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Setup components
        self.setup_components()

    def setup_components(self):
        """Set up database components"""
        try:
            self.config_manager = ConfigManager()
            self.query_mappings = QueryMappings()
            self.query_matcher = QueryMatcherAWS(self.query_mappings)
            self.db_executor = AWSPostgresExecutor(self.config_manager.aws_pg_config)
            logger.info("All components initialized successfully")
        except Exception as e:
            logger.error(f"Setup error: {str(e)}")
            raise

    async def start(self):
        """Start the voice assistant"""
        logger.info("Starting voice assistant")
        #await self.connection_manager.send_personal_message(
        #    {"type": "status", "text": "Assistant ready"}, 
        #    self.websocket
        #)
        await self.send_message_to_client({"type": "status", "text": "Assistant ready"})
        return True

    async def process_audio_data(self, audio_data: bytes):
        """
        Process audio data from browser
        
        Args:
            audio_data: Raw audio bytes from WebSocket
        """
        try:
            # Create a temporary WAV file for the audio data
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(audio_data)
            
            # Send audio to Whisper for transcription
            try:
                with open(temp_path, "rb") as audio_file:
                    transcription = await self.openai_client.audio.transcriptions.create(
                        file=audio_file,
                        model="whisper-1",
                        language="en",
                    )
                    text = transcription.text
            finally:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
                
            if not text:
                return
                
            # Process the transcribed text
            logger.info(f"Transcribed: {text}")
            
            # Send transcription to client
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "transcription", "text": text},
            ##    self.websocket
            ##)
            await self.send_message_to_client({"type": "transcription", "text": text})
            
            # Check for interruption first
            if self.is_speaking:
                logger.info("Detected speech during speaking - interrupting")
                self.is_interrupted = True
                
                # Send interruption status to client
                ##await self.connection_manager.send_personal_message(
                ##    {"type": "status", "text": "Speech interrupted"},
                ##    self.websocket
                ##)
                await self.send_message_to_client({"type": "status", "text": "Speech interrupted"})
                
                # Give a moment for speech to stop
                await asyncio.sleep(0.2)
                
                # Wait for speaking flag to be cleared
                wait_count = 0
                while self.is_speaking and wait_count < 10:
                    await asyncio.sleep(0.1)
                    wait_count += 1
                
                logger.info(f"Speech interrupted, waited: {wait_count * 0.1}s")
            
            # Now process the transcription
            await self._process_transcription(text)
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "error", "text": f"Audio processing error: {str(e)}"},
            ##    self.websocket
            ##)
            await self.send_message_to_client({"type": "error", "text": f"Audio processing error: {str(e)}"})

    async def _process_transcription(self, text: str):
        """Process transcribed text with wake word detection"""
        text = text.lower().strip()
        
        # Check for deactivation words
        # Commented out as we're now using UI buttons for control
        """
        if self.is_activated and any(word in text for word in ["stop", "exit", "quit"]):
            self.is_activated = False
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "status", "text": "Assistant deactivated. Say 'Agent' to wake me up again."},
            ##    self.websocket
            ##)
            await self.send_message_to_client({"type": "status", "text": "Assistant deactivated. Say 'Agent' to wake me up again."})
            await self.speak("Assistant deactivated. Say 'Agent' to wake me up again.")
            return
        """
        
        # Check for wake word
        # Commented out as we're now using UI buttons for activation
        """
        if not self.is_activated and self.wake_word.lower() in text:
            self.is_activated = True
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "status", "text": "Assistant activated! Ready for query."},
            ##    self.websocket
            ##)
            await self.send_message_to_client({"type": "status", "text": "Assistant activated! Ready for query."})
            
            # Extract any query that came after the wake word
            query = text.split(self.wake_word.lower(), 1)[-1].strip()
            if query:
                await self._handle_query(query)
            else:
                await self.speak("Yes, how can I help you with the database?")
            return
        """
        
        # Process query when activated
        if self.is_activated:
            await self._handle_query(text)

    async def process_text_query(self, query: str):
        """Process a text query from the UI"""
        logger.info(f"Processing text query: {query}")
        
        # Always interrupt any ongoing speech first
        if self.is_speaking:
            self.is_interrupted = True
            await asyncio.sleep(0.2)  # Small delay to allow speech to stop
        
        # Commented out wake word detection - always consider activated
        """
        # If not activated and not the wake word, activate first
        if not self.is_activated and self.wake_word.lower() not in query.lower():
            self.is_activated = True
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "status", "text": "Assistant activated! Processing your query..."},
            ##    self.websocket
            ##)
            await self.send_message_to_client({"type": "status", "text": "Assistant activated! Processing your query..."})
        
        # If it contains the wake word, extract the actual query
        if self.wake_word.lower() in query.lower():
            query = query.split(self.wake_word.lower(), 1)[-1].strip()
        """
        
        # Always consider activated for UI queries
        self.is_activated = True
        
        # Process the query
        if query:
            await self._handle_query(query)
        else:
            await self.speak("Yes, how can I help you with the database?")

    async def _handle_query(self, query: str):
        """Handle database queries and generate responses"""
        try:
            logger.info(f"Processing query: {query}")
            
            # Match query to SQL with parameters
            sql_query, params = await self.query_matcher.match_query(
                query,
                method='text',
                threshold=0.7
            )
            
            if sql_query:
                logger.info(f"Executing SQL: {sql_query}")
                ##await self.connection_manager.send_personal_message(
                ##    {"type": "sql", "query": sql_query},
                ##    self.websocket
                ##)
                await self.send_message_to_client({"type": "sql", "query": sql_query})
                
                # Execute query with parameters
                try:
                    if params:
                        results = self.db_executor.execute_query(sql_query, tuple(params.values()))
                    else:
                        results = self.db_executor.execute_query(sql_query)
                        
                    if results:
                        # Send results to client
                        ##await self.connection_manager.send_personal_message(
                        ##    {"type": "results", "data": results},
                        ##    self.websocket
                        ##)
                        await self.send_message_to_client({"type": "results", "data": results})
                        
                        # Generate natural language response
                        response = await self.generate_response(query, results)
                        await self.speak(response)
                    else:
                        await self.speak("I found no results for your query.")
                        
                except Exception as e:
                    logger.error(f"Database error: {e}")
                    ##await self.connection_manager.send_personal_message(
                    ##    {"type": "error", "text": f"Database error: {str(e)}"},
                    ##    self.websocket
                    ##)
                    await self.send_message_to_client({"type": "error", "text": f"Database error: {str(e)}"})
                    await self.speak(f"I encountered a database error: {str(e)}")
            else:
                await self._handle_non_sql_query(query)

        except Exception as e:
            logger.error(f"Query handling error: {str(e)}")
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "error", "text": f"Query error: {str(e)}"},
            ##    self.websocket
            ##)

            await self.send_message_to_client({"type": "error", "text": f"Query error: {str(e)}"})
            await self.speak("I encountered an error processing your request. Please try again.")



    async def speak(self, text: str):
        """Generate speech using OpenAI TTS with PCM streaming for minimum latency"""
        if not text:
            return

        logger.info(f"Speaking: {text}")
            
        # Always send text response to browser regardless of mute state
        ##await self.connection_manager.send_personal_message(
        ##    {"type": "response", "text": text},
        ##    self.websocket
        ##)
        await self.send_message_to_client({"type": "response", "text": text})

        
        # Reset interruption flag before starting speech
        self.is_interrupted = False
        
        # Skip audio generation if muted
        if self.is_muted:
            logger.info("Assistant is muted - skipping audio generation")
            return
        
        try:
            # Mark as speaking before generating audio
            self.is_speaking = True
            
            # Send signal that streaming is starting
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "audio_stream_start", "format": "pcm", "sampleRate": 24000},
            ##    self.websocket
            ##)

            await self.send_message_to_client({"type": "audio_stream_start", "format": "pcm", "sampleRate": 24000})
            
            # Use streaming response with PCM format for lowest latency
            async with self.openai_client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="onyx",
                input=text,
                response_format="pcm"  # Use PCM format for lowest latency
            ) as response:
                
                
                # Process audio in chunks as they arrive - use larger chunks for more stability
                async for chunk in response.iter_bytes(chunk_size=1024):
                    # Check for interruption after each chunk
                    if self.is_interrupted:
                        logger.info("Speech streaming interrupted")
                        break
                    
                    if chunk:
                        # Send PCM chunk to the client
                        chunk_base64 = base64.b64encode(chunk).decode('utf-8')
                        ##await self.connection_manager.send_personal_message(
                        ##    {"type": "audio_chunk", "data": chunk_base64, "format": "pcm"},
                        ##    self.websocket
                        ##)
                        await self.send_message_to_client({"type": "audio_chunk", "data": chunk_base64, "format": "pcm"})
                        
                '''

                # Use much smaller chunks (1KB instead of 8KB)
                async for chunk in response.iter_bytes(chunk_size=1024):  # Significantly reduced
                    if self.is_interrupted:
                        logger.info("Speech streaming interrupted")
                        break
                    
                    if chunk:
                        # Send PCM chunk to the client with sequence numbers
                        chunk_id = str(int(time.time() * 1000))  # Use timestamp as ID
                        chunk_base64 = base64.b64encode(chunk).decode('utf-8')
                        await self.send_message_to_client({
                            "type": "audio_chunk", 
                            "data": chunk_base64, 
                            "format": "pcm",
                            "chunk_id": chunk_id  # Add sequence identifier
                        })
                        
                        # Add a small delay to prevent overwhelming Lambda
                        await asyncio.sleep(0.03)
            
                '''

                # No need for fallback with PCM as it's being played in real-time
                    
        except Exception as e:
            logger.error(f"TTS error: {e}")
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "error", "text": f"Speech generation error: {str(e)}"},
            ##    self.websocket
            ##)
            await self.send_message_to_client({"type": "error", "text": f"Speech generation error: {str(e)}"})
        finally:
            # Always mark as not speaking when done
            self.is_speaking = False
    
            await asyncio.sleep(0.1)

            
            # Signal end of stream
            ##await self.connection_manager.send_personal_message(
            ##    {"type": "audio_stream_end"},
            ##    self.websocket
            ##)
            await self.send_message_to_client({"type": "audio_stream_end"})

    async def generate_response(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Generate natural language response using Groq"""
        try:
            context = {
                "total_count": len(results),
                "sample_fields": list(results[0].keys()) if results else [],
                "sample_data": results[:3] if results else []
            }
            
            messages = [
                {
                    "role": "system",
                    "content": "You are a SQL database assistant. Generate natural, conversational summaries of query results."
                },
                {
                    "role": "user",
                    "content": f"""
                    Query: {query}
                    Results: {context}
                    
                    Please provide a concise but informative summary of these results in a conversational tone.
                    Focus on the key insights and numbers that would be most relevant to the user.
                    Keep the response under 3 sentences.
                    """
                }
            ]
            
            completion = await self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.2
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return f"I found {len(results)} results matching your query."

    async def _handle_non_sql_query(self, query: str):
        """Handle queries that don't match any SQL patterns"""
        fallback_response = (
            "I can help you query the database for:\n"
            "- Show all customers\n"
            "- Show orders by status\n"
            "- Show popular product\n"
            "- Count customers\n"
            "- Show recent orders\n"
            "- Status/value by order id (e.g. 'Status of Order 40')\n"
            "Please ask information about the database."
        )
        
        await self.speak(fallback_response)

    async def stop(self):
        """Stop the voice assistant and clean up"""
        # Set flags to stop any ongoing operations
        self.is_activated = False
        self.is_speaking = False
        self.is_interrupted = True
        
        # Wait a moment for operations to complete
        await asyncio.sleep(0.2)
        
        # Close database connection
        try:
            self.db_executor.close()
        except:
            pass
            
        logger.info("Voice assistant stopped")
        ##await self.connection_manager.send_personal_message(
        ##    {"type": "status", "text": "Assistant stopped"},
        ##    self.websocket
        ##)
        await self.send_message_to_client({"type": "status", "text": "Assistant stopped"})
        

    # Send message to client using Lambda
    async def send_message_to_client(self, message, client_id=None):
        """Send message to client using Lambda"""
        try:
            # Use provided client_id or try to extract it
            if not client_id:
                # Try to get from WebSocket scope path
                if hasattr(self.websocket, "scope") and "path" in self.websocket.scope:
                    path = self.websocket.scope["path"]
                    if path.startswith("/ws/"):
                        client_id = path.split("/ws/")[1]
                
                
                # If still no client_id, try to find it in the client_id_mapping
                if not client_id:
                    # Import dynamically to avoid circular imports
                    import sys
                    if 'src.gateway.api_gateway_handler' in sys.modules:
                        gateway_module = sys.modules['src.gateway.api_gateway_handler']
                        if hasattr(gateway_module, 'client_id_mapping'):
                            # Look for the connection ID that matches this websocket
                            for c_id, conn_id in gateway_module.client_id_mapping.items():
                                # This is an approximation since we don't have a direct way to match
                                client_id = c_id
                                break
                
            if not client_id:
                logger.error("No client_id found for WebSocket - message cannot be sent")
                # Try to send via direct WebSocket as fallback
                if hasattr(self.websocket, "send_json"):
                    try:
                        await self.websocket.send_json(message)
                        logger.info("Sent message via direct WebSocket as fallback")
                        return True
                    except Exception as ws_err:
                        logger.error(f"Fallback WebSocket send failed: {str(ws_err)}")
                return False
        

            
            # Initialize Lambda client
            lambda_client = boto3.client('lambda', region_name='eu-west-2')
            
            # Prepare payload for Lambda
            payload = {
                'clientId': client_id,
                'message': message
            }
            
            # Invoke Lambda function
            response = lambda_client.invoke(
                FunctionName='websocket-send-message',
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            # Process response
            result = json.loads(response['Payload'].read().decode())
            if result.get('statusCode') == 200:
                return True
            else:
                logger.error(f"Error from Lambda: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message via Lambda: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
        