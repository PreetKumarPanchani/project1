'use client';

import { useState, useEffect, useRef } from 'react';
import TapToSpeak from './TapToSpeak';
import SqlDisplay from './SqlDisplay';
import ResultsTable from './ResultsTable';
import ExampleQueries from './ExampleQueries';

import { useWebSocket } from '@/lib/useWebSocket';
import { useAudioRecording } from '@/lib/useAudioRecording';
import { useAudioPlayback } from '@/lib/useAudioPlayback';

const ChatInterface = () => {
  // State management for UI
  const [inputText, setInputText] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [sqlQuery, setSqlQuery] = useState('');
  const [queryResults, setQueryResults] = useState([]);
  const [isActivated, setIsActivated] = useState(false);
  
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  
  // Initialize WebSocket connection
  const { 
    isConnected, 
    status, 
    messages: wsMessages, 
    sendMessage 
  } = useWebSocket();
  
  // Audio playback management
  const { 
    isPlaying, 
    interruptPlayback, 
    startPcmStream, 
    endPcmStream, 
    processPcmChunk 
  } = useAudioPlayback();
  
  // Add state for example queries section collapse
  const [examplesCollapsed, setExamplesCollapsed] = useState(false);
  
  // Handle audio data from microphone
  const handleAudioData = (base64Audio) => {
    if (isConnected) {
      sendMessage({
        command: 'audio_data',
        audio: base64Audio
      });
    }
  };
  
  // Audio recording management
  const { 
    isRecording, 
    toggleRecording 
  } = useAudioRecording(handleAudioData);
  
  // Handle sending text query to backend
  const sendTextQuery = (text) => {
    if (!text || !isConnected) return;
    
    // If AI is speaking, interrupt it first
    if (isPlaying) {
      interruptPlayback();
      sendMessage({ command: 'interrupt_speech' });
    }
    
    // Add user message to chat
    addMessage('user', text);
    
    // Send text to backend
    sendMessage({
      command: 'text_query',
      text
    });
    
    // Clear input
    setInputText('');
  };
  
  // Add a message to the chat
  const addMessage = (role, content, isError = false) => {
    setChatMessages(prev => [
      ...prev, 
      { role, content, isError, timestamp: new Date() }
    ]);
  };
  
  // Handle form submission
  const handleSubmit = (e) => {
    e.preventDefault();
    sendTextQuery(inputText);
  };
  
  // Handle example query selection
  const handleExampleQuery = (query) => {
    setInputText(query);
    sendTextQuery(query);
  };
  
  // Handle interrupt button click
  const handleInterrupt = () => {
    if (isPlaying) {
      interruptPlayback();
      sendMessage({ command: 'interrupt_speech' });
    }
  };
  
  // Toggle examples section
  const toggleExamples = () => {
    setExamplesCollapsed(prev => !prev);
  };
  
  // Process WebSocket messages
  useEffect(() => {
    if (!wsMessages || wsMessages.length === 0) return;
    
    // Process only the most recent message
    const latestMessage = wsMessages[wsMessages.length - 1];
    
    switch (latestMessage.type) {
      case 'transcription':
        addMessage('user', latestMessage.text);
        break;
        
      case 'response':
        addMessage('assistant', latestMessage.text);
        break;
        
      case 'status':
        if (latestMessage.text.includes('activated')) {
          setIsActivated(true);
        } else if (latestMessage.text.includes('deactivated')) {
          setIsActivated(false);
        }
        break;
        
      case 'error':
        addMessage('system', latestMessage.text, true);
        break;
        
      case 'results':
        setQueryResults(latestMessage.data || []);
        break;
        
      case 'sql':
        setSqlQuery(latestMessage.query || '');
        break;
        
      case 'audio_stream_start':
        startPcmStream(latestMessage.sampleRate);
        break;
        
      case 'audio_stream_end':
        endPcmStream();
        break;
        
      case 'audio_chunk':
        if (latestMessage.format === 'pcm') {
          processPcmChunk(latestMessage.data);
        }
        break;
        
      default:
        console.log('Unhandled message type:', latestMessage.type);
    }
  }, [wsMessages, startPcmStream, endPcmStream, processPcmChunk]);
  
  // Auto scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages]);
  
  return (
    <div className="chat-interface">
      <header className="chat-header">
        <h2></h2>
        <div className="status-badge">
          Status: {status}
        </div>
      </header>
      
      {/* Central tap to speak button */}
      <TapToSpeak 
        isRecording={isRecording} 
        toggleRecording={toggleRecording} 
        disabled={!isConnected}
      />
      
      {/* Messages container with fixed height */}
      <div className="messages-container fixed-height" ref={messagesContainerRef}>
        {chatMessages.length === 0 ? (
          <div className="message system">
            <div className="message-content">
              AI Assistant Ready, Say or Type your Query.
            </div>
          </div>
        ) : (
          chatMessages.map((msg, idx) => (
            <div 
              key={idx} 
              className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}
            >
              <div className="message-content">
                {msg.content}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      
      {/* SQL query display (if available) */}
      {sqlQuery && <SqlDisplay query={sqlQuery} />}
      
      {/* Results table (if available) */}
      {queryResults.length > 0 && <ResultsTable results={queryResults} />}
      
      {/* Text input and controls */}
      <form onSubmit={handleSubmit} className="input-container">
        <input
          type="text"
          className="query-input"
          placeholder="Type your query here..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={!isConnected}
        />
        <div className="button-group">
          <button 
            type="submit" 
            className="send-button"
            disabled={!isConnected || !inputText.trim()}
          >
            <i className="bi bi-send"></i>
            Send
          </button>
          <button
            type="button"
            className="interrupt-button"
            onClick={handleInterrupt}
            disabled={!isPlaying}
          >
            <i className="bi bi-x-circle"></i>
            Interrupt
          </button>
        </div>
      </form>
      
      {/* Collapsible Example queries section */}
      <div className="examples-section">
        <div className="examples-header" onClick={toggleExamples}>
          <h4>Example Queries</h4>
          <button className="toggle-button">
            <i className={`bi ${examplesCollapsed ? 'bi-chevron-down' : 'bi-chevron-up'}`}></i>
          </button>
        </div>
        
        {!examplesCollapsed && (
          <ExampleQueries onSelectQuery={handleExampleQuery} />
        )}
      </div>
    </div>
  );
};

export default ChatInterface;