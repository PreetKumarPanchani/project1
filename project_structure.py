import os

# Create the main project directory
os.makedirs('src', exist_ok=True)

# Create the subdirectories
subdirs = ['config', 'database', 'nlp', 'query', 'utils', 'web']
for subdir in subdirs:
    os.makedirs(os.path.join('src', subdir))

# Create the __init__.py files
for subdir in subdirs:
    with open(os.path.join('src', subdir, '__init__.py'), 'w') as f:
        pass


# Create the app_text_v1.py file
with open(os.path.join('src/app', 'app_text_v1.py'), 'w') as f:
    pass


# Create the individual files
files = [
    ('config', 'config_manager.py'),
    ('database', 'db_executor.py'),
    ('database', 'db_manager.py'),
    ('nlp', 'query_matcher.py'),
    ('nlp', 'groq_pattern_matcher.py'),
    ('query', 'query_mappings.py'),
    ('utils', 'logger.py'),
    ('app', 'main.py'),
    ('speech_text_speech_system',  'openai_tts_voice_assistant.py'),
    ('speech_text_speech_system',  'voice_assistant_pyttsx3.py'),
    

]


for subdir, file in files:
    with open(os.path.join('src', subdir, file), 'w') as f:
        pass