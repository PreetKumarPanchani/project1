FROM python:3.10-slim

WORKDIR /app

# Install minimal dependencies needed for audio processing
# Note: We don't need pyaudio/portaudio as we're not capturing audio on the server
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    #portaudio19-dev \
    #python3-pyaudio \
    # Add any other system dependencies you need
    #&& apt-get clean && \   
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Ensure static and template directories exist
#RUN mkdir -p static/css static/js templates

# Expose port for FastAPI with WebSockets
EXPOSE 8001

# Set environment variables
#ENV FRONTEND_CHOICE=new
#ENV PYTHONPATH=

# Start the FastAPI app with uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]