'use client';

import { useState, useCallback, useRef, useEffect } from 'react';

export function useAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  
  // References for audio handling
  const audioContextRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const pcmQueueRef = useRef([]);
  const isReceivingPcmRef = useRef(false);
  const isProcessingPcmRef = useRef(false);
  const pcmSampleRateRef = useRef(24000);
  
  // Initialize Web Audio API context
  const initAudioContext = useCallback(() => {
    try {
      if (!audioContextRef.current && typeof window !== 'undefined') {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
        console.log("Audio context initialized with sample rate:", audioContextRef.current.sampleRate);
      }
      return true;
    } catch (e) {
      console.error('Failed to initialize audio context:', e);
      return false;
    }
  }, []);
  
  // Play standard audio from URL
  const playAudio = useCallback((audioDataUrl) => {
    if (isMuted || !audioPlayerRef.current) return;
    
    try {
      audioPlayerRef.current.src = audioDataUrl;
      audioPlayerRef.current.play()
        .then(() => setIsPlaying(true))
        .catch(e => {
          console.error('Error playing audio:', e);
          setIsPlaying(false);
        });
    } catch (error) {
      console.error('Error setting audio source:', error);
      setIsPlaying(false);
    }
  }, [isMuted]);
  
  // Start PCM audio stream
  const startPcmStream = useCallback((sampleRate = 24000) => {
    if (isMuted) return false;
    if (!initAudioContext()) return false;
    
    pcmSampleRateRef.current = sampleRate;
    isReceivingPcmRef.current = true;
    pcmQueueRef.current = [];
    isProcessingPcmRef.current = false;
    
    // Update UI state
    setIsPlaying(true);
    console.log("PCM stream started with sample rate:", pcmSampleRateRef.current);
    return true;
  }, [isMuted, initAudioContext]);
  
  // End PCM audio stream
  const endPcmStream = useCallback(() => {
    isReceivingPcmRef.current = false;
    
    // Process any remaining queued data
    if (pcmQueueRef.current.length > 0 && !isProcessingPcmRef.current) {
      processPcmQueue();
    }
    
    console.log("PCM stream ended");
  }, []);
  
  // Convert PCM data to AudioBuffer
  const convertPcmToAudioBuffer = useCallback((pcmData) => {
    if (!audioContextRef.current) return null;
    
    const numSamples = pcmData.length / 2; // 16-bit = 2 bytes per sample
    const audioBuffer = audioContextRef.current.createBuffer(1, numSamples, pcmSampleRateRef.current);
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
  }, []);
  
  // Process PCM queue
  const processPcmQueue = useCallback(async () => {
    if (pcmQueueRef.current.length === 0 || isProcessingPcmRef.current || !audioContextRef.current) return;
    
    isProcessingPcmRef.current = true;
    
    try {
      // Get next chunk
      const pcmData = pcmQueueRef.current.shift();
      
      // Convert PCM data to audio buffer
      const audioBuffer = convertPcmToAudioBuffer(pcmData);
      if (!audioBuffer) {
        isProcessingPcmRef.current = false;
        return;
      }
      
      // Play the buffer
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      
      // Create a promise to detect when the chunk finishes playing
      const playbackPromise = new Promise(resolve => {
        source.onended = resolve;
        // Fallback timeout (slightly longer than chunk duration)
        const durationMs = (audioBuffer.length / audioBuffer.sampleRate) * 1000;
        setTimeout(resolve, durationMs + 50);
      });
      
      // Start playing
      source.start(0);
      
      // Wait for it to finish
      await playbackPromise;
      
      // Process next chunk if available
      isProcessingPcmRef.current = false;
      if (pcmQueueRef.current.length > 0) {
        processPcmQueue();
      } else if (pcmQueueRef.current.length === 0 && !isReceivingPcmRef.current) {
        // Playback ended
        setIsPlaying(false);
      }
    } catch (e) {
      console.error('Error playing PCM audio:', e);
      isProcessingPcmRef.current = false;
      
      // Try to continue with next chunk
      if (pcmQueueRef.current.length > 0) {
        processPcmQueue();
      }
    }
  }, [convertPcmToAudioBuffer]);
  
  // Process and queue PCM audio chunk
  const processPcmChunk = useCallback((base64data) => {
    if (isMuted || !isReceivingPcmRef.current) return;
    
    try {
      // Convert base64 to ArrayBuffer
      const binaryString = atob(base64data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      
      // Queue the data
      pcmQueueRef.current.push(bytes);
      
      // Process queue if not already processing
      if (!isProcessingPcmRef.current) {
        processPcmQueue();
      }
    } catch (e) {
      console.error('Error processing PCM chunk:', e);
    }
  }, [isMuted, processPcmQueue]);
  
  // Interrupt any ongoing playback
  const interruptPlayback = useCallback(() => {
    if (isPlaying) {
      // Stop traditional audio
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
      }
      
      // Stop PCM streaming
      isReceivingPcmRef.current = false;
      pcmQueueRef.current = [];
      isProcessingPcmRef.current = false;
      
      setIsPlaying(false);
      return true;
    }
    return false;
  }, [isPlaying]);
  
  // Toggle mute state
  const toggleMute = useCallback(() => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);
    
    // If currently playing and we mute, stop playback
    if (newMuted && isPlaying) {
      interruptPlayback();
    }
    
    return newMuted;
  }, [isMuted, isPlaying, interruptPlayback]);
  
  // Set up audio element on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Create a hidden audio element for normal audio playback
      const audioElement = document.createElement('audio');
      audioElement.style.display = 'none';
      document.body.appendChild(audioElement);
      audioPlayerRef.current = audioElement;
      
      // Setup audio element event handlers
      audioElement.onplay = () => setIsPlaying(true);
      audioElement.onended = () => setIsPlaying(false);
      audioElement.onpause = () => setIsPlaying(false);
      
      // Initialize Web Audio API (needed for PCM)
      initAudioContext();
      
      return () => {
        if (audioElement.parentNode) {
          document.body.removeChild(audioElement);
        }
      };
    }
  }, [initAudioContext]);
  
  return {
    isPlaying,
    isMuted,
    playAudio,
    toggleMute,
    interruptPlayback,
    startPcmStream,
    endPcmStream,
    processPcmChunk
  };
}