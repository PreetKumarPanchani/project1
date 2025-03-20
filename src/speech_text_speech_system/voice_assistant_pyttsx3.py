import speech_recognition as sr
from faster_whisper import WhisperModel
import pyttsx3
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
import os
from dotenv import load_dotenv
logger = setup_logger(name="voice_assistant", level="INFO")

class VoiceAssistant:
    def __init__(self):
        self.wake_word = "sql agent"
        self.is_listening = False
        self.is_speaking = False
        self.is_activated = False
        self.is_interrupted = False
        self.speech_lock = threading.Lock()
        self.current_utterance = None
        
        # Initialize components
        self.setup_components()
        
    def setup_components(self):
        """Set up all required components"""
        try:
            # Speech recognition setup
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 2500
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.6
            self.mic = sr.Microphone()

            # Initialize TTS with event handlers
            self.setup_tts()

            # Whisper model setup
            self.whisper_model = WhisperModel(
                "base",
                device="cpu",
                compute_type="int8"
            )

            # Database components
            self.setup_database()
            
        except Exception as e:
            logger.error(f"Setup error: {e}")
            raise

    def setup_tts(self):
        """Set up TTS with event handlers"""
        try:
            # Initialize main TTS engine
            self.tts_engine = pyttsx3.init()
            
            # Configure properties
            self.tts_engine.setProperty('rate', 175)
            self.tts_engine.setProperty('volume', 1.0)
            
            # Set up event handlers
            self.tts_engine.connect('started-utterance', self.on_start_utterance)
            self.tts_engine.connect('finished-utterance', self.on_finish_utterance)
            self.tts_engine.connect('started-word', self.on_word)
            
            # Select voice
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if "zira" in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            # Initialize speech state
            self.speech_lock = threading.Lock()
            self.is_speaking = False
            self.is_interrupted = False
            
            # Test TTS
            self.tts_engine.say("System initialized")
            self.tts_engine.runAndWait()
            
        except Exception as e:
            logger.error(f"TTS setup error: {e}")
            raise

    def on_start_utterance(self, name):
        """Handler for utterance start"""
        self.is_speaking = True
        self.current_utterance = name
        logger.debug(f"Started speaking: {name}")

    def on_finish_utterance(self, name, completed):
        """Handler for utterance finish"""
        self.is_speaking = False
        self.current_utterance = None
        logger.debug(f"Finished speaking: {name}, completed: {completed}")
        
        if not completed:
            logger.info("Speech was interrupted")
            self.is_interrupted = True

    def on_word(self, name, location, length):
        """Handler for word events - check for interrupts"""
        if self.is_interrupted:
            try:
                self.tts_engine.stop()
            except:
                pass
            return
            
        # Check for interruption every few words
        if location % 3 == 0:
            try:
                with self.mic as source:
                    audio = self.recognizer.listen(source, timeout=0.1, phrase_time_limit=0.5)
                    if audio:
                        self.is_interrupted = True
                        try:
                            self.tts_engine.stop()
                        except:
                            pass
                        self._process_audio(audio)
            except (sr.WaitTimeoutError, sr.RequestError):
                pass

    def speak(self, text: str):
        """Speak text with interruption support"""
        try:
            if not text:
                return

            logger.info(f"Speaking: {text}")
            print(f"\nAssistant: {text}")

            with self.speech_lock:
                if self.is_speaking:
                    try:
                        self.tts_engine.stop()
                    except:
                        pass
                    time.sleep(0.1)

                self.is_speaking = True
                self.is_interrupted = False

                # Split into sentences
                sentences = text.split('. ')
                for i, sentence in enumerate(sentences):
                    if self.is_interrupted:
                        break

                    if sentence.strip():
                        try:
                            # Clean sentence
                            clean_sentence = sentence.strip() + '.'
                            
                            # Speak sentence
                            self.tts_engine.say(clean_sentence)
                            self.tts_engine.runAndWait()
                            
                            # Small pause between sentences
                            if not self.is_interrupted and i < len(sentences) - 1:
                                time.sleep(0.1)
                                
                        except Exception as e:
                            logger.error(f"Error speaking sentence: {e}")
                            continue

        except Exception as e:
            logger.error(f"Speech error: {e}")
        finally:
            self.is_speaking = False
            self.is_interrupted = False

    def _process_audio(self, audio):
        """Process audio with improved error handling"""
        temp_file = "temp_audio.wav"
        try:
            # Write audio to temp file
            with open(temp_file, "wb") as f:
                f.write(audio.get_wav_data())
            
            # Transcribe with Whisper
            segments, _ = self.whisper_model.transcribe(
                temp_file,
                beam_size=5,
                language='en'
            )
            
            text = " ".join([segment.text for segment in segments]).lower().strip()
            if not text:
                return

            logger.info(f"Transcribed: {text}")
            print(f"\nYou said: {text}")

            # Handle wake word and queries
            if not self.is_activated:
                if self.wake_word in text:
                    self.is_activated = True
                    query = text.split(self.wake_word, 1)[-1].strip()
                    if query:
                        self._handle_query(query)
                    else:
                        self.speak("Yes, how can I help you with the database?")
            else:
                self._handle_query(text)

        except Exception as e:
            logger.error(f"Processing error: {e}")
        finally:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

    def _handle_query(self, query: str):
        """Handle query with improved error handling"""
        try:
            # Deactivate if user says "stop" or "exit"
            if query in ["stop", "exit", "quit", "goodbye"]:
                self.is_activated = False
                self.speak("Assistant deactivated. Say 'SQL Agent' to wake me up again.")
                return

            print(f"\nProcessing query: {query}")
            
            sql_query = self.query_matcher.match_query(query, method='text', threshold=0.8)
            
            if sql_query:
                print(f"Executing SQL: {sql_query}")
                results = self.db_executor.execute_query(sql_query)
                
                if results:
                    response = self._format_results(query, results)
                    self.speak(response)
                    self.print_results_table(results)
                else:
                    self.speak("I found no results for your query.")
            else:
                response = (
                    "Show all customers"
                    "Show orders by status"
                    "Show popular product"
                    "Count customers"
                    "Show recent orders"
                    "Status/value by order id (e.g. 'Status of Order 40')"
                    "Please ask information about the database."
                )
                self.speak(response)

        except Exception as e:
            logger.error(f"Query handling error: {str(e)}")
            self.speak("I encountered an error processing your request. Please try again.")

    def _format_results(self, query: str, results: list) -> str:
        """Format results into natural language"""
        try:
            count = len(results)
            if "user" in query:
                active_count = sum(1 for r in results if r.get('status') == 'active')
                return f"I found {count} users, {active_count} of them are active. Here are the details."
            elif "order" in query:
                total_amount = sum(float(r.get('total_amount', 0)) for r in results)
                return f"I found {count} orders with a total value of ${total_amount:.2f}."
            elif "product" in query:
                categories = set(r.get('category_name') for r in results if r.get('category_name'))
                return f"I found {count} products across {len(categories)} categories."
            return f"I found {count} results for your query."
        except Exception as e:
            logger.error(f"Result formatting error: {str(e)}")
            return f"I found {len(results)} results."

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

    def start(self):
        """Start the voice assistant"""
        logger.info("Starting voice assistant...")
        print("\nStarting SQL Voice Assistant...")
        
        self.is_listening = True
        self.speak("AI Query Assistant is ready. Say 'Agent' to start.")
        
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        

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
                    status = "Activated" if self.is_activated else "Waiting for 'SQL Agent'"
                    print(f"\nListening... ({status})")
                    
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=8)
                    self._process_audio(audio)
                    
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Listening error: {e}")
                    continue

    def stop(self):
        """Stop the voice assistant"""
        self.is_listening = False
        if self.is_speaking:
            try:
                self.tts_engine.stop()
            except:
                pass
        self.db_executor.close()
        print("\nGoodbye!")
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

