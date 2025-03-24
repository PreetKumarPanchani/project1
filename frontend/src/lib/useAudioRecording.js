'use client';

import { useState, useCallback, useRef, useEffect } from 'react';

export function useAudioRecording(onAudioData) {
  const [isRecording, setIsRecording] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  
  // Convert ArrayBuffer to base64
  const arrayBufferToBase64 = useCallback((buffer) => {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    
    return window.btoa(binary);
  }, []);
  
  // Process audio blob and convert to base64
  const processAudioBlob = useCallback((audioBlob) => {
    const reader = new FileReader();
    reader.readAsArrayBuffer(audioBlob);
    reader.onloadend = () => {
      const audioData = reader.result;
      const base64audio = arrayBufferToBase64(audioData);
      
      if (onAudioData) {
        onAudioData(base64audio);
      }
    };
  }, [arrayBufferToBase64, onAudioData]);
  
  // Start recording from microphone
  const startRecording = useCallback(() => {
    if (isRecording || !navigator.mediaDevices) return;
    
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        setIsRecording(true);
        setIsListening(true);
        audioChunksRef.current = [];
        streamRef.current = stream;
        
        // Configure media recorder with optimal settings
        const options = { mimeType: 'audio/webm' };
        const mediaRecorder = new MediaRecorder(stream, options);
        mediaRecorderRef.current = mediaRecorder;
        
        // Handle audio data
        mediaRecorder.addEventListener('dataavailable', event => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        });
        
        // Process audio when a chunk is complete
        mediaRecorder.addEventListener('stop', () => {
          if (audioChunksRef.current.length > 0) {
            const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
            processAudioBlob(audioBlob);
            audioChunksRef.current = [];
            
            // Restart recording automatically if still listening
            if (isListening && mediaRecorderRef.current) {
              try {
                mediaRecorderRef.current.start(1000); // Collect in 1 second chunks
              } catch (error) {
                console.error('Error restarting recorder:', error);
              }
            } else {
              // Stop all tracks when no longer listening
              if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
              }
            }
          }
        });
        
        // Start recording
        mediaRecorder.start(1000); // Collect in 1 second chunks
      })
      .catch(error => {
        console.error('Error accessing microphone:', error);
        setIsRecording(false);
        setIsListening(false);
      });
  }, [isRecording, isListening, processAudioBlob]);
  
  // Stop recording
  const stopRecording = useCallback(() => {
    setIsListening(false);
    setIsRecording(false);
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (error) {
        console.error('Error stopping recorder:', error);
      }
    }
    
    // Ensure we clean up the stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  }, []);
  
  // Toggle recording state
  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);
  
  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);
  
  return {
    isRecording,
    isListening,
    toggleRecording,
    startRecording,
    stopRecording
  };
}