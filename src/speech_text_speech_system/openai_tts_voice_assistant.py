import speech_recognition as sr
from faster_whisper import WhisperModel
import torch
import threading
import queue
import time
from typing import Optional, List, Dict, Any
import logging
from src.nlp.query_matcher import QueryMatcher
from src.query.query_mappings import QueryMappings
#from src.database.db_executor import PostgresExecutor
from src.database.db_executor_aws import AWSPostgresExecutor
from src.config.config_manager import ConfigManager
from src.utils.logger import setup_logger
from tabulate import tabulate
import pyaudio
from openai import OpenAI
import numpy as np
import os
from dotenv import load_dotenv
from groq import Groq

logger = setup_logger(name="voice_assistant", level="INFO")

class VoiceAssistant:
    def __init__(self):
        # Initialize attributes first
        self.wake_word = "Agent"
        self.is_listening = False
        self.is_speaking = False
        self.is_interrupted = False
        self.speech_lock = threading.Lock()
        self.is_activated = False
        self.response_queue = queue.Queue()
        
        # Initialize audio components
        self.pyaudio_instance = None
        self.audio_stream = None
        
        # Load environment variables
        load_dotenv()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Setup components after initialization
        self.setup_components()

    def setup_components(self):
        """Set up components with improved audio handling"""
        try:
            # Speech recognition setup
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 2500
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.6
            self.mic = sr.Microphone()

            # Whisper model setup
            self.whisper_model = WhisperModel(
                "base",
                device="cpu",
                compute_type="int8",
                num_workers=2,
                cpu_threads=2
            )

            # Initialize PyAudio with error checking
            try:
                self.pyaudio_instance = pyaudio.PyAudio()
                # Test audio output
                test_stream = self.pyaudio_instance.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=24000,
                    output=True,
                    frames_per_buffer=2048
                )
                test_stream.close()
            except Exception as e:
                logger.error(f"PyAudio initialization error: {e}")
                raise

            # Database components
            self.setup_database()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Setup error: {str(e)}")
            raise

    def setup_database(self):
        """Set up database components"""
        try:
            self.config_manager = ConfigManager()
            self.query_mappings = QueryMappings()
            self.query_matcher = QueryMatcher(self.query_mappings)
            #self.db_executor = PostgresExecutor(self.config_manager)
            self.db_executor = AWSPostgresExecutor(self.config_manager.aws_pg_config)
        except Exception as e:
            logger.error(f"Database setup error: {str(e)}")
            raise

    def speak(self, text: str):
        """Speak text using OpenAI TTS with improved error handling"""
        try:
            if not text:
                return

            logger.info(f"Speaking: {text}")
            print(f"\nAssistant: {text}")

            # Create and start speech thread
            speech_thread = threading.Thread(
                target=self._speak_thread,
                args=(text,),
                daemon=True
            )
            speech_thread.start()

        except Exception as e:
            logger.error(f"Speech error: {e}")
            self.is_speaking = False

    def _speak_thread(self, text: str):
        """Thread for speaking text using OpenAI TTS with better streaming"""
        audio_stream = None
        try:
            with self.speech_lock:
                self.is_speaking = True
                self.is_interrupted = False

                # Create a new PyAudio instance for this thread
                pa = pyaudio.PyAudio()
                audio_stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=24000,
                    output=True,
                    frames_per_buffer=2048,
                    start=False  # Don't start until we have data
                )

                # Start the stream
                audio_stream.start_stream()

                try:
                    # Generate speech with OpenAI streaming
                    with self.openai_client.audio.speech.with_streaming_response.create(
                        model="tts-1",
                        voice="onyx",
                        response_format="pcm",
                        input=text,
                        speed=1.0
                    ) as response:
                        # Process audio in chunks
                        for chunk in response.iter_bytes(chunk_size=2048):
                            if self.is_interrupted:
                                logger.info("Speech interrupted")
                                break

                            if chunk and len(chunk) > 0:
                                audio_stream.write(chunk)
                                time.sleep(0.01)  # Small pause for smoother playback

                except Exception as e:
                    logger.error(f"OpenAI TTS error: {e}")
                    raise

        except Exception as e:
            logger.error(f"Speech thread error: {e}")
        finally:
            # Cleanup
            self.is_speaking = False
            if audio_stream is not None:
                try:
                    if audio_stream.is_active():
                        audio_stream.stop_stream()
                    audio_stream.close()
                except Exception as e:
                    logger.error(f"Error closing audio stream: {e}")
            
            # Clean up PyAudio instance
            if 'pa' in locals():
                try:
                    pa.terminate()
                except Exception as e:
                    logger.error(f"Error terminating PyAudio: {e}")

    def cleanup_audio(self):
        """Clean up audio resources"""
        try:
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except:
                    pass
                self.audio_stream = None
        except Exception as e:
            logger.error(f"Audio cleanup error: {e}")

    def _process_audio(self, audio):
        """Process audio with better interruption handling"""
        try:
            # Convert audio to text
            text = None
            
            # Try Google Speech Recognition first
            try:
                text = self.recognizer.recognize_google(audio)
                logger.debug(f"Google Speech Recognition: {text}")
            except (sr.UnknownValueError, sr.RequestError):
                # Fallback to Whisper
                with open("temp_audio.wav", "wb") as f:
                    f.write(audio.get_wav_data())
                
                segments, _ = self.whisper_model.transcribe(
                    "temp_audio.wav",
                    beam_size=5,
                    language='en'
                )
                text = " ".join([segment.text for segment in segments]).lower().strip()
                
                try:
                    os.remove("temp_audio.wav")
                except:
                    pass

            if not text:
                return

            logger.info(f"Transcribed: {text}")
            print(f"\nYou said: {text}")

            # Handle interruption
            if self.is_speaking:
                self.is_interrupted = True
                time.sleep(0.2)  # Wait for speech to stop

            # Process the command
            if not self.is_activated:
                if self.wake_word.lower() in text.lower():
                    self.is_activated = True
                    query = text.split(self.wake_word.lower(), 1)[-1].strip()
                    if query:
                        self._handle_query(query)
                    else:
                        self.speak("Yes, how can I help you with the database?")
            else:
                if "stop" in text or "exit" in text or "quit" in text:
                    self.is_activated = False
                    self.speak("Assistant deactivated. Say 'Agent' to wake me up again.")
                else:
                    self._handle_query(text)
        except Exception as e:
            logger.error(f"Audio processing error: {e}")

    def _handle_query(self, query: str):
        """Handle database queries and generate responses"""
        try:
            print(f"\nProcessing query: {query}")
            
            # Match query to SQL
            sql_query = self.query_matcher.match_query(query, method='text', threshold=0.8)
            
            if sql_query:
                print(f"Executing SQL: {sql_query}")
                results = self.db_executor.execute_query(sql_query)
                
                if results:
                    # Generate response using Groq
                    table =self.print_results_table(results)
                    response = self.generate_response(query, table)
                    self.speak(response)
                    
                else:
                    self.speak("I found no results for your query.")
            else:
                self._handle_non_sql_query_predefined(query)

        except Exception as e:
            logger.error(f"Query handling error: {str(e)}")
            self.speak("I encountered an error processing your request. Please try again.")


    def generate_response(self, query: str, results: list) -> str:
        """Generate natural language response using Groq"""
        try:
            # Format results for better context
            context = self._format_results_context(results)
            
            # Create prompt for Groq
            messages = [
                {
                    "role": "system",
                    "content": "You are a SQL database assistant. Generate natural, conversational summaries of query results based on the User Input."
                },
                {
                    "role": "user",
                    "content": f"""
                    Query: {query}
                    Results: {context}
                    
                    Please provide a concise but informative summary of these results based on the Query in a conversational tone.
                    Focus on the key insights and numbers that would be most relevant to the user based on the Query.
                    If there are no results, say "I found no data related to your query.
                    Don't include any information about the sql query, just the results based on the user query or user input.
                    Keep the explanation under 3 sentences. If there is not enough information, dont make up information, just include the information that is there.
                    Make it concise, clear and easy to understand and informative.
                    """
                }
            ]

            
            # Get completion from Groq
            completion = self.groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=messages,
                temperature=0.7,
                #max_tokens=150
            )
            
            response = completion.choices[0].message.content
            logger.info(f"Groq response: {response}")  # Log the response
            return response

        except Exception as e:
            logger.error(f"Response generation error: {e}")
            logger.exception("Full traceback:")
            return self._format_fallback_response(query, results)

    def _format_results_context(self, results: list) -> str:
        """Format results for OpenAI context"""
        try:
            summary = {
                "total_count": len(results),
                "sample_fields": list(results[0].keys()) if results else [],
                "sample_data": results[:3] if results else []
            }
            return str(summary)
        except Exception as e:
            logger.error(f"Context formatting error: {str(e)}")
            return str(results)

    def _format_fallback_response(self, query: str, results: list) -> str:
        """Generate fallback response if Groq fails"""
        count = len(results)
        if "user" in query:
            active_count = sum(1 for r in results if r.get('status') == 'active')
            return f"I found {count} users, {active_count} of them are active."
        elif "order" in query:
            total_amount = sum(float(r.get('total_amount', 0)) for r in results)
            return f"I found {count} orders with a total value of ${total_amount:.2f}."
        elif "product" in query:
            categories = set(r.get('category_name') for r in results if r.get('category_name'))
            return f"I found {count} products across {len(categories)} categories."
        return f"I found {count} results for your query."

    def print_results_table(self, results: List[Dict[str, Any]]) -> None:
        """Print results in a formatted table"""
        if not results:
            print("\nNo results found.")
            return

        try:
            # Get headers from first result
            headers = list(results[0].keys())
            
            # Format data for tabulate
            table_data = []
            for row in results:
                formatted_row = []
                for header in headers:
                    value = row[header]
                    if isinstance(value, (float, int)):
                        formatted_row.append(f"{value:,.2f}" if isinstance(value, float) else f"{value:,}")
                    else:
                        formatted_row.append(str(value))
                table_data.append(formatted_row)

            # Print table using tabulate
            print("\nResults:")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            
        except Exception as e:
            logger.error(f"Error printing results table: {str(e)}")
            print("\nError displaying results table.")



    def _handle_non_sql_query(self, query: str):
        """Handle non-SQL queries with OpenAI"""
        try:
        

            # Create prompt for Groq
            messages = [
                {
                    "role": "system",
                    "content": "You are a SQL database assistant. Generate natural, conversational responses to user queries."
                },
                {
                    "role": "user",
                    "content": f"""You are a SQL database assistant. The user asked: "{query}"
                    Explain what kinds of database queries you can help with and provide examples.
                    Some examples are:
                    "I can help you query the database for:\n"
                    "- User information (e.g., 'show all users')\n"
                    "- Order information (e.g., 'show recent orders')\n"
                    "- Product information (e.g., 'show all products')\n"
                    "Please try queries related to the database."

                    Keep the response friendly and concise.

                    """
                }
            ]
            # Create prompt for non-SQL queries
            
            # Get completion from OpenAI
            #completion = self.openai_client.chat.completions.create(
            #    model="gpt-3.5-turbo",
            #    messages=[prompt],
            #    temperature=0.7,
            #    max_tokens=150
            #)

            
            completion = self.groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=messages,
                temperature=0.2,
            )
            
            self.speak(completion.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Non-SQL query handling error: {str(e)}")
              

            fallback_response = (
                "I can help you query the database for:\n"
                "- Customer information (e.g., 'show all customers')\n"
                "- Order information (e.g., 'show recent orders')\n"
                "- Show popular product\n"
                "- Count customers\n"
                "- Show recent orders\n"
                "- Status/value by order id (e.g. 'Status of Order 40')\n"
                "Please ask information about the database."
            ) 
            self.speak(fallback_response)
        
    def _handle_non_sql_query_predefined(self, query: str):
        """Handle non-SQL queries with fallback response"""
        try:
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
                  
            self.speak(fallback_response)
        except Exception as e:
            logger.error(f"Fallback response error: {str(e)}")
            self.speak("I encountered an error processing your request. Please try again.") 
    

    def start(self):
        """Start the voice assistant with improved error handling"""
        logger.info("Starting voice assistant...")
        print("\nStarting AI Query Assistant...")
        
        self.is_listening = True
        
        try:
            with self.mic as source:
                logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            self.speak("AI Query Assistant is ready. Say 'Agent' to start.")
            
            print("\nExample queries:")
            print("- 'show all customers'")
            print("- 'show recent orders'")
            print("- 'status/value by order id'")
            print("- 'show popular product'")
            print("- 'count customers'")
            print("- 'show recent orders'")
            print("You can interrupt me anytime by speaking.")
            
            while self.is_listening:
                try:
                    with self.mic as source:
                        status = "Activated" if self.is_activated else "Waiting for 'Agent'"
                        print(f"\nListening... ({status})")
                        
                        # Use shorter timeout for more responsive interruption
                        audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=8)
                        
                        if not self.is_speaking:
                            self._process_audio(audio)
                        else:
                            # Check for interruption
                            try:
                                text = self.recognizer.recognize_google(audio, show_all=False)
                                if text:
                                    self.is_interrupted = True
                                    self._process_audio(audio)
                            except:
                                pass
                            
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Listening error: {e}")
                    continue

        except KeyboardInterrupt:
            print("\nStopping...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the voice assistant"""
        self.is_listening = False
        self.cleanup_audio()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
        self.db_executor.close()
        self.speak("Goodbye!")
        logger.info("Voice assistant stopped.")
    
    

def main():
    """Main entry point"""
    assistant = None
    try:
        assistant = VoiceAssistant()
        assistant.start()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        if assistant:
            assistant.stop()

if __name__ == "__main__":
    main()
