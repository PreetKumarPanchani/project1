document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const messagesContainer = document.getElementById('messages');
    const textInput = document.getElementById('text-input');
    const sendButton = document.getElementById('send-button');
    const listenButton = document.getElementById('listen-button');
    const recordingIndicator = document.getElementById('recording-indicator');
    //const toggleMuteButton = document.getElementById('toggle-mute');
    const statusIndicator = document.getElementById('status-indicator');
    const sqlContainer = document.getElementById('sql-container');
    const sqlQuery = document.getElementById('sql-query');
    const sqlResultsContainer = document.getElementById('sql-results');
    const audioPlayer = document.getElementById('audio-player');
    const exampleQueries = document.querySelectorAll('.example-query');
    
    // Create the interrupt button if it doesn't exist
    let interruptButton;
    if (!document.getElementById('interrupt-button')) {
        interruptButton = document.createElement('button');
        interruptButton.id = 'interrupt-button';
        interruptButton.className = 'btn btn-danger';
        interruptButton.innerHTML = '<i class="bi bi-x-circle"></i> Interrupt';
        interruptButton.disabled = true;
        // Insert after the mute button
        //toggleMuteButton.parentNode.appendChild(interruptButton);
    } else {
        interruptButton = document.getElementById('interrupt-button');
    }
    
    // Audio recording variables
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let isListening = false;
    let isMuted = false;
    let isActivated = false;
    let isAssistantSpeaking = false;
    let reconnectAttempts = 0;
    let maxReconnectAttempts = 5;
    let reconnectInterval = 3000; // 3 seconds

    let audioContext = null;
    let pcmPlayer = null;
    let isReceivingPcm = false;
    let pcmSampleRate = 24000;
    let pcmQueue = [];
    let isProcessingPcm = false;
    
    // WebSocket setup
    const clientId = 'client-' + Math.random().toString(36).substring(2, 9);
    let socket;
    
    // Connect to WebSocket with better error handling
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${protocol}${window.location.host}/ws/${clientId}`;
        
        // Close existing socket if open
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
            socket.close();
        }
        
        socket = new WebSocket(wsUrl);
        
        socket.onopen = function(e) {
            //addSystemMessage('Connected to server');

            setStatus('Connected');
            reconnectAttempts = 0; // Reset counter on successful connection
            
            // Setup audio after WebSocket connection
            setupAudioRecording();
            setupAudioControls();
        };
        
        socket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            handleSocketMessage(data);
        };
        
        socket.onclose = function(event) {
            // Only attempt reconnection if this wasn't a clean close
            if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                setStatus(`Reconnecting (${reconnectAttempts}/${maxReconnectAttempts})...`, 'reconnecting');
                
                // Hide the message about connection loss from the chat
                setTimeout(connectWebSocket, reconnectInterval);
            } else if (reconnectAttempts >= maxReconnectAttempts) {
                setStatus('Connection failed');
                addSystemMessage('Could not reconnect to server. Please reload the page.');
            } else if (event.wasClean) {
                setStatus('Disconnected');
                addSystemMessage(`Connection closed cleanly.`);
            }
            
            // Stop recording if active
            if (isRecording) {
                stopRecording();
            }
            
            // Disable controls when disconnected
            disableControls();
        };
        
        socket.onerror = function(error) {
            console.error('WebSocket error:', error);
            // Don't display generic error messages to the user
            setStatus('Connection error');
        };
    }
    
    // Setup audio controls
    function setupAudioControls() {
        // Set up audio player events
        audioPlayer.onplay = function() {
            isAssistantSpeaking = true;
            interruptButton.disabled = false;
        };
        
        audioPlayer.onended = function() {
            isAssistantSpeaking = false;
            interruptButton.disabled = true;
        };
        
        audioPlayer.onpause = function() {
            isAssistantSpeaking = false;
            interruptButton.disabled = true;
        };
        
        // Setup interrupt button
        interruptButton.addEventListener('click', interruptSpeech);
        
        // Ensure mute button is correctly set up
        //toggleMuteButton.innerHTML = isMuted ? 
        //    '<i class="bi bi-volume-mute"></i> Unmute Assistant' : 
        //    '<i class="bi bi-volume-up"></i> Mute Assistant';
    }

    // Disable controls when disconnected
    function disableControls() {
        listenButton.disabled = true;
        sendButton.disabled = true;
        interruptButton.disabled = true;
        textInput.disabled = true;
    }
    
    // Re-enable controls when connected
    function enableControls() {
        listenButton.disabled = false;
        sendButton.disabled = false;
        textInput.disabled = false;
        // Interrupt button is only enabled during speech
    }



    // Initialize Web Audio API
    function initAudioContext() {
        try {
            if (!audioContext) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                console.log("Audio context initialized with sample rate:", audioContext.sampleRate);
            }
            return true;
        } catch (e) {
            console.error("Failed to initialize audio context:", e);
            return false;
        }
    }

    // Start PCM playback stream
    function startPcmStream(sampleRate) {
        if (!initAudioContext()) return false;
        
        pcmSampleRate = sampleRate || 24000;
        isReceivingPcm = true;
        pcmQueue = [];
        isProcessingPcm = false;
        
        // Update UI
        isAssistantSpeaking = true;
        interruptButton.disabled = false;
        
        console.log("PCM stream started with sample rate:", pcmSampleRate);
        return true;
    }

    // End PCM playback stream
    function endPcmStream() {
        isReceivingPcm = false;
        
        // Process any remaining queued data
        if (pcmQueue.length > 0 && !isProcessingPcm) {
            processPcmQueue();
        }
        
        console.log("PCM stream ended");
    }

    // Process PCM audio chunk
    function processPcmChunk(base64data) {
        if (isMuted || !isReceivingPcm) return;
        
        try {
            // Convert base64 to ArrayBuffer
            const binaryString = atob(base64data);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            // Queue the data
            pcmQueue.push(bytes);
            
            // Process queue if not already processing
            if (!isProcessingPcm) {
                processPcmQueue();
            }
        } catch (e) {
            console.error("Error processing PCM chunk:", e);
        }
    }

    // Process PCM queue
    async function processPcmQueue() {
        if (pcmQueue.length === 0 || isProcessingPcm || !audioContext) return;
        
        isProcessingPcm = true;
        
        try {
            // Get next chunk
            const pcmData = pcmQueue.shift();
            
            // Convert PCM data (16-bit signed little-endian) to audio buffer
            const audioBuffer = convertPcmToAudioBuffer(pcmData);
            
            // Play the buffer
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            source.start(0);
            
            // Wait for it to finish before processing next chunk
            // Use approximation: duration = samples / sampleRate
            const durationMs = (audioBuffer.length / audioBuffer.sampleRate) * 1000;
            
            // For very short chunks, don't wait
            if (durationMs > 20) {
                await new Promise(resolve => setTimeout(resolve, durationMs - 15));
            }
            
            // Process next chunk if available
            isProcessingPcm = false;
            if (pcmQueue.length > 0 && isReceivingPcm) {
                processPcmQueue();
            } else if (pcmQueue.length === 0 && !isReceivingPcm) {
                // End of stream and no more data
                isAssistantSpeaking = false;
                interruptButton.disabled = true;
            }
        } catch (e) {
            console.error("Error playing PCM audio:", e);
            isProcessingPcm = false;
            
            // Try to continue with next chunk
            if (pcmQueue.length > 0) {
                processPcmQueue();
            }
        }
    }

    // Convert PCM data to AudioBuffer
    function convertPcmToAudioBuffer(pcmData) {
        const numSamples = pcmData.length / 2; // 16-bit = 2 bytes per sample
        const audioBuffer = audioContext.createBuffer(1, numSamples, pcmSampleRate);
        const channelData = audioBuffer.getChannelData(0);
        
        // OpenAI PCM format is 16-bit signed little-endian
        let offset = 0;
        for (let i = 0; i < numSamples; i++) {
            // Convert 16-bit PCM to float
            const sample = (pcmData[offset] & 0xff) | ((pcmData[offset + 1] & 0xff) << 8);
            // Handle signed integers (convert to -1.0 to 1.0 range)
            channelData[i] = (sample >= 0x8000) ? -1 + ((sample & 0x7fff) / 0x8000) : sample / 0x7fff;
            offset += 2;
        }
        
        return audioBuffer;
    }

    // Interrupt speech (updated for PCM)
    function interruptSpeech() {
        if (isAssistantSpeaking) {
            // Stop traditional audio
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            
            // Stop PCM streaming
            isReceivingPcm = false;
            pcmQueue = [];
            isProcessingPcm = false;
            
            // Update state
            isAssistantSpeaking = false;
            interruptButton.disabled = true;
            
            // Notify the server of interruption
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    command: 'interrupt_speech'
                }));
            }
        }
    }

    
    // Handle interrupt button click
    //function interruptSpeech() {
    //    if (isAssistantSpeaking) {
    //        // Stop the audio playback
    //        audioPlayer.pause();
    //        audioPlayer.currentTime = 0;
    //        isAssistantSpeaking = false;
    //        interruptButton.disabled = true;
    //        
    //        // Notify the server of interruption
    //        if (socket && socket.readyState === WebSocket.OPEN) {
    //            socket.send(JSON.stringify({
    //                command: 'interrupt_speech'
    //            }));
    //        }
    //        //addSystemMessage('Speech interrupted');
    //    }
    // }
    
    // Setup audio recording
    function setupAudioRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            addSystemMessage('Voice input is not supported in your browser');
            listenButton.disabled = true;
            return;
        }
        
        // Enable button
        listenButton.disabled = false;
        
        // Setup listen button
        listenButton.addEventListener('click', toggleRecording);
    }
    
    // Toggle recording state
    function toggleRecording() {
        if (isRecording) {
            stopRecording();
        } else {
            // If assistant is speaking, interrupt first
            if (isAssistantSpeaking) {
                interruptSpeech();
            }
            startRecording();
        }
    }
    
    // Start audio recording
    function startRecording() {
        if (isRecording) return;
        
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                isRecording = true;
                isListening = true;
                audioChunks = [];
                
                // Update UI
                listenButton.innerHTML = '<i class="bi bi-mic-mute"></i> Stop Listening';
                listenButton.classList.remove('btn-success');
                listenButton.classList.add('btn-danger');
                recordingIndicator.style.display = 'inline';
                
                // Notify server
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({
                        command: 'toggle_listen',
                        listening: true
                    }));
                }
                
                // Configure media recorder
                const options = { mimeType: 'audio/webm' };
                mediaRecorder = new MediaRecorder(stream);
                
                mediaRecorder.addEventListener('dataavailable', event => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                });
                
                // Process audio when stopped
                mediaRecorder.addEventListener('stop', () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    processAudioBlob(audioBlob);
                    audioChunks = [];
                    
                    // Restart recording automatically if still listening
                    if (isListening) {
                        mediaRecorder.start(1000);  // Collect in 1 second chunks
                    } else {
                        // Stop all tracks
                        stream.getTracks().forEach(track => track.stop());
                    }
                });
                
                // Start recording
                mediaRecorder.start(1000);  // Collect in 1 second chunks
                setStatus('Listening...');
            })
            .catch(error => {
                addSystemMessage(`Error accessing microphone: ${error.message}`);
                isRecording = false;
                isListening = false;
                updateRecordingUI();
            });
    }
    
    // Stop audio recording
    function stopRecording() {
        isListening = false;
        isRecording = false;
        
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        
        // Update UI
        updateRecordingUI();
        
        // Notify server
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                command: 'toggle_listen',
                listening: false
            }));
        }
        
        setStatus('Connected');
    }
    
    // Update recording UI elements
    function updateRecordingUI() {
        listenButton.innerHTML = '<i class="bi bi-mic"></i> Start Listening';
        listenButton.classList.remove('btn-danger');
        listenButton.classList.add('btn-success');
        recordingIndicator.style.display = 'none';
    }
    
    // Process and send audio data
    function processAudioBlob(audioBlob) {
        // If assistant is speaking, this may be an interruption
        if (isAssistantSpeaking) {
            interruptSpeech();
        }
        
        // Convert to WAV for better compatibility
        const reader = new FileReader();
        reader.readAsArrayBuffer(audioBlob);
        reader.onloadend = () => {
            const audioData = reader.result;
            
            // Send to server if connected
            if (socket && socket.readyState === WebSocket.OPEN) {
                // Convert array buffer to base64
                const base64audio = arrayBufferToBase64(audioData);
                
                socket.send(JSON.stringify({
                    command: 'audio_data',
                    audio: base64audio
                }));
            }
        };
    }
    
    // Convert ArrayBuffer to base64
    function arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        const len = bytes.byteLength;
        
        for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        
        return window.btoa(binary);
    }
    
    // Handle incoming WebSocket messages
    function handleSocketMessage(data) {
        switch (data.type) {
            case 'transcription':
                addUserMessage(data.text);
                break;
                
            case 'response':
                addAssistantMessage(data.text);
                break;
                
            case 'status':
                setStatus(data.text);
                
                // Update activation state based on status
                if (data.text.includes('activated')) {
                    isActivated = true;
                } else if (data.text.includes('deactivated')) {
                    isActivated = false;
                } else if (data.text.includes('interrupted')) {
                    isAssistantSpeaking = false;
                    interruptButton.disabled = true;
                }
                break;
                
            case 'error':
                // Be more selective about which errors we display to the user
                if (data.text.includes('database') || data.text.includes('query')) {
                    addSystemMessage(`Error: ${data.text}`);
                } else {
                    console.error('Error from server:', data.text);
                }
                break;
                
            case 'results':
                displayResults(data.data);
                break;
                
            case 'sql':
                displaySqlQuery(data.query);
                break;
                
            case 'audio':
                if (!isMuted) {
                    playAudio(data.data);
                } else {
                    console.log('Audio muted - not playing');
                    // Even if muted, update UI state
                    isAssistantSpeaking = false;
                    interruptButton.disabled = true;
                }
                break;
    


            case 'audio_stream_start':
                // Start audio stream
                if (data.format === 'pcm') {
                    startPcmStream(data.sampleRate);
                } else {
                    // For other formats, just update UI
                    isAssistantSpeaking = true;
                    interruptButton.disabled = false;
                }
                break;
                
            case 'audio_stream_end':
                // End audio stream
                if (isReceivingPcm) {
                    endPcmStream();
                }
                break;
                
            case 'audio_chunk':
                // Handle different audio formats
                if (!isMuted) {
                    if (data.format === 'pcm') {
                        processPcmChunk(data.data);
                    } else {
                        // Default to MP3 chunk handling
                        playAudioChunk(data.data);
                    }
                }
                break;
                
            default:
                console.log('Unknown message type:', data);
        }
    }
    
    // Add message to chat
    function addUserMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `<div class="message-content">${message}</div>`;
        appendMessage(messageDiv);
    }
    
    function addAssistantMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `<div class="message-content">${message}</div>`;
        appendMessage(messageDiv);
    }
    
    function addSystemMessage(message) {
        // Skip specific system messages we don't want to show 
        if (message.toLowerCase().includes('connection lost. will try to reconnect') ||
            message.toLowerCase().includes('connection error: undefined') ||
            message.toLowerCase() === 'connected to server' ||
            message.toLowerCase() === 'speech interrupted' ||
            message.toLowerCase().includes('interrupted')) {
            console.log('Suppressed system message:', message);
            return;
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';
        messageDiv.innerHTML = `<div class="message-content">${message}</div>`;
        appendMessage(messageDiv);
    }
    
    function appendMessage(messageDiv) {
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Update status indicator
    function setStatus(status, cssClass = '') {
        statusIndicator.textContent = status;
        
        // Reset all classes
        statusIndicator.classList.remove('bg-secondary', 'bg-success', 'bg-danger', 'bg-warning', 'bg-info', 'reconnecting');
        
        // Add reconnecting animation if specified
        if (cssClass === 'reconnecting') {
            statusIndicator.classList.add('reconnecting');
        }
        
        // Add appropriate class based on status
        if (status.includes('Listening') || status.includes('activated')) {
            statusIndicator.classList.add('bg-success');
        } else if (status.includes('Error') || status.includes('error')) {
            statusIndicator.classList.add('bg-danger');
        } else if (status.includes('Connected')) {
            statusIndicator.classList.add('bg-info');
            enableControls();
        } else if (status.includes('Disconnected') || status.includes('Reconnecting')) {
            statusIndicator.classList.add('bg-warning');
        } else {
            statusIndicator.classList.add('bg-secondary');
        }
    }
    
    // Display SQL query
    function displaySqlQuery(query) {
        // Basic SQL syntax highlighting
        const keywords = ['SELECT', 'FROM', 'WHERE', 'ORDER BY', 'GROUP BY', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN', 'ON', 'AS', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS NULL', 'IS NOT NULL', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'HAVING', 'LIMIT', 'OFFSET', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TABLE', 'VIEW', 'INDEX', 'DISTINCT', 'ASC', 'DESC'];
        
        // Replace SQL keywords with highlighted spans
        let highlightedQuery = query;
        keywords.forEach(keyword => {
            // Use regex to match whole words only and case insensitive
            const regex = new RegExp('\\b' + keyword + '\\b', 'gi');
            highlightedQuery = highlightedQuery.replace(regex, match => {
                return `<span class="keyword">${match}</span>`;
            });
        });
        
        // Highlight numbers
        highlightedQuery = highlightedQuery.replace(/\b\d+\b/g, '<span class="number">$&</span>');
        
        // Highlight strings (text between quotes)
        highlightedQuery = highlightedQuery.replace(/'([^']*)'/g, '\'<span class="string">$1</span>\'');
        
        sqlQuery.innerHTML = highlightedQuery;
        sqlContainer.style.display = 'block';
    }
    
    // Display query results with scrollable table
    function displayResults(results) {
        if (!results || results.length === 0) {
            sqlResultsContainer.style.display = 'none';
            return;
        }
        
        // Create table container for scrolling
        const tableContainer = document.createElement('div');
        tableContainer.className = 'table-responsive-container';
        
        // Create table
        const table = document.createElement('table');
        table.className = 'table table-striped';
        
        // Create header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        Object.keys(results[0]).forEach(key => {
            const th = document.createElement('th');
            th.textContent = key;
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create body
        const tbody = document.createElement('tbody');
        
        results.forEach(row => {
            const tr = document.createElement('tr');
            
            Object.values(row).forEach(value => {
                const td = document.createElement('td');
                td.textContent = value;
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        
        // Add table to container
        tableContainer.appendChild(table);
        
        // Clear and update container
        sqlResultsContainer.innerHTML = '<h5 class="text-light" >Results:</h5>';
        sqlResultsContainer.appendChild(tableContainer);
        sqlResultsContainer.style.display = 'block';
    }
    
    // Play audio received from server
    function playAudio(audioDataUrl) {
        if (isMuted) {
            console.log('Audio muted - not playing');
            return;
        }
        
        try {
            // Reset interrupted state
            isAssistantSpeaking = true;
            interruptButton.disabled = false;
            
            audioPlayer.src = audioDataUrl;
            audioPlayer.play().catch(e => {
                console.error('Error playing audio:', e);
                isAssistantSpeaking = false;
                interruptButton.disabled = true;
            });
        } catch (error) {
            console.error('Error setting audio source:', error);
            isAssistantSpeaking = false;
            interruptButton.disabled = true;
        }
    }
    
    // Send text query
    function sendTextQuery(text) {
        if (!text) return;
        
        if (socket && socket.readyState === WebSocket.OPEN) {
            // If assistant is speaking, interrupt first
            if (isAssistantSpeaking) {
                interruptSpeech();
            }
            
            socket.send(JSON.stringify({
                command: 'text_query',
                text: text
            }));
            
            textInput.value = '';
        } else {
            addSystemMessage('Not connected to server');
        }
    }
    
    // Toggle mute with improved state handling
    function toggleMute() {
        isMuted = !isMuted;
        
        //toggleMuteButton.innerHTML = isMuted ? 
        //    '<i class="bi bi-volume-mute"></i> Unmute Assistant' : 
        //    '<i class="bi bi-volume-up"></i> Mute Assistant';
        
        // If currently speaking and we mute, stop playback
        if (isMuted && isAssistantSpeaking) {
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            isAssistantSpeaking = false;
            interruptButton.disabled = true;
        }
        
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                command: 'toggle_mute',
                muted: isMuted
            }));
        }
        
        addSystemMessage(isMuted ? 'Assistant muted' : 'Assistant unmuted');
    }
    
    // UI Event Listeners
    sendButton.addEventListener('click', function() {
        const text = textInput.value.trim();
        if (text) {
            addUserMessage(text);
            sendTextQuery(text);
        }
    });
    
    textInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const text = textInput.value.trim();
            if (text) {
                addUserMessage(text);
                sendTextQuery(text);
            }
        }
    });
    
    //toggleMuteButton.addEventListener('click', toggleMute);
    
    // Example queries
    exampleQueries.forEach(query => {
        query.addEventListener('click', function() {
            const text = this.textContent;
            textInput.value = text;
            addUserMessage(text);
            sendTextQuery(text);
        });
    });

    
    // Initial connection
    connectWebSocket();
});