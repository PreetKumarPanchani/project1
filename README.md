# Natural Language to Database Query System

AI system that converts natural language queries to database queries and provides informative responses.

Install rye online and then run the following commands to create the venv and install the dependencies

rye sync

### Cross-platform activation

**For Windows:**
.\.venv\Scripts\activate

**For Unix or MacOS:**
.venv/bin/activate

**Run the Application:Using Rye**


```bash
cd src/

rye run chainlit run C:\Users\preet\Downloads\Liquid_SCM\Code\nl_to_db_query_v1\src\app_text_v1.py
rye run chainlit run C:\Users\preet\Downloads\Liquid_SCM\Code\nl_to_db_query_v1\src\app\main1.py

# To run the particular python code
rye run python C:\Users\preet\Downloads\Liquid_SCM\Code\nl_to_db_query_v1\src\nlp\query_matcher.py
rye run python C:\Users\preet\Downloads\Liquid_SCM\Code\nl_to_db_query_v1\src\database\db_manager_aws.py

# To remove a specific library or dependencies
rye remove <library_name>

# Remove the virtual environment
rd /s /q .venv

# Remove the lock files (optional)
del requirements.lock
del requirements-dev.lock
```


### Speech-to-Text (Whisper API):

Only when user click the "Start Listening" button and until user click "Stop Listening"
During this period, audio is sent to the server in 1-second chunks. Each chunk gets processed by Whisper API on the server side. This continues until user manually stop recording


### Text-to-Speech (TTS API):

Only when the assistant responds to user with voice, the streaming implementation sends the text to TTS API. Audio is streamed back in small chunks for immediate playback
