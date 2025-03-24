'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [status, setStatus] = useState('Initializing...');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [messages, setMessages] = useState([]);
  const socketRef = useRef(null);
  
  const maxReconnectAttempts = 5;
  const reconnectInterval = 3000; // 3 seconds
  
  // Function to establish WebSocket connection
  const connect = useCallback(() => {
    // Generate a unique client ID
    const clientId = 'client-' + Math.random().toString(36).substring(2, 9);
      

    // Extract just the hostname from environment variables
    const getHostFromUrl = (urlString) => {
      if (!urlString) return '';
      try {
        // If it already contains protocol, parse it with URL
        if (urlString.includes('://')) {
          return new URL(urlString).host;
        }
        // Otherwise, it's already a host
        return urlString;
      } catch (e) {
        console.error('Error parsing URL:', e);
        return urlString;
      }
    };
    
    // Get clean hostname without protocol
    const apiHost = getHostFromUrl(process.env.NEXT_PUBLIC_WS_HOST) || 
                    getHostFromUrl(process.env.NEXT_PUBLIC_API_URL) || 
                    'localhost:8001';
    
    // Determine WebSocket protocol (ws or wss)
    const wsProtocol = typeof window !== 'undefined' && 
      window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    
    // Construct WebSocket URL using clean hostname
    const wsUrl = typeof window !== 'undefined' ? 
      `${wsProtocol}//${apiHost}/ws/${clientId}` : 
      '';
    
    console.log("Clean hostname:", apiHost);
    console.log("Connecting to WebSocket URL:", wsUrl);
    

    // IMPORTANT: Connect directly to the backend WebSocket server, bypassing Next.js
    // This is critical for WebSockets to work properly
    //const wsUrl = typeof window !== 'undefined' ? 
    //  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//localhost:8001/ws/${clientId}` : 
    //  '';
    
    // Close existing socket if open
    if (socketRef.current && 
        (socketRef.current.readyState === WebSocket.OPEN || 
         socketRef.current.readyState === WebSocket.CONNECTING)) {
      socketRef.current.close();
    }
    
    if (!wsUrl) return; // Don't attempt to connect if URL is empty
    
    try {
      console.log("Connecting to WebSocket URL:", wsUrl);
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;
      
      socket.onopen = () => {
        console.log("WebSocket connection established");
        setIsConnected(true);
        setStatus('Connected');
        setReconnectAttempts(0);
      };
      
      socket.onclose = (event) => {
        console.log("WebSocket connection closed", event);
        setIsConnected(false);
        
        // Only attempt reconnection if this wasn't a clean close
        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
          const newAttempts = reconnectAttempts + 1;
          setReconnectAttempts(newAttempts);
          setStatus(`Reconnecting (${newAttempts}/${maxReconnectAttempts})...`);
          
          // Schedule reconnection
          setTimeout(connect, reconnectInterval);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          setStatus('Connection failed');
        } else {
          setStatus('Disconnected');
        }
      };
      
      socket.onerror = (error) => {
        console.error("WebSocket error:", error);
        setStatus('Connection error');
      };
      
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setStatus('Connection error');
    }
  }, [reconnectAttempts]);
  
  // Handle incoming WebSocket messages
  const handleMessage = useCallback((data) => {
    // Add message to state for use in components
    setMessages(prevMessages => [...prevMessages, data]);
  }, []);
  
  // Send a message through WebSocket
  const sendMessage = useCallback((message) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);
  
  // Connect on component mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Add a small delay to ensure window is fully loaded
      const timer = setTimeout(() => {
        connect();
      }, 100);
      
      // Cleanup on unmount
      return () => {
        clearTimeout(timer);
        if (socketRef.current) {
          socketRef.current.close();
        }
      };
    }
  }, [connect]);
  
  return {
    isConnected,
    status,
    messages,
    sendMessage,
    connect,
    socket: socketRef.current,
  };
}

/*
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [status, setStatus] = useState('Initializing...');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [messages, setMessages] = useState([]);
  const socketRef = useRef(null);
  
  const maxReconnectAttempts = 5;
  const reconnectInterval = 3000; // 3 seconds
  
  // Function to establish WebSocket connection
  const connect = useCallback(() => {
    // Generate a unique client ID
    const clientId = 'client-' + Math.random().toString(36).substring(2, 9);
    
    // Determine WebSocket protocol (ws or wss)
    const protocol = typeof window !== 'undefined' && 
      window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    

    // Construct WebSocket URL
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8001';
    //const wsUrl = `${protocol}${host}/ws/${clientId}`;
    

    const wsUrl = typeof window !== 'undefined' ? 
    `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//localhost:8001/ws/${clientId}` :
    '';

    // Close existing socket if open
    if (socketRef.current && 
        (socketRef.current.readyState === WebSocket.OPEN || 
         socketRef.current.readyState === WebSocket.CONNECTING)) {
      socketRef.current.close();
    }
    
    try {
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;
      
      socket.onopen = () => {
        setIsConnected(true);
        setStatus('Connected');
        setReconnectAttempts(0);
      };
      
      socket.onclose = (event) => {
        setIsConnected(false);
        
        // Only attempt reconnection if this wasn't a clean close
        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
          const newAttempts = reconnectAttempts + 1;
          setReconnectAttempts(newAttempts);
          setStatus(`Reconnecting (${newAttempts}/${maxReconnectAttempts})...`);
          
          // Schedule reconnection
          setTimeout(connect, reconnectInterval);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          setStatus('Connection failed');
        } else {
          setStatus('Disconnected');
        }
      };
      
      socket.onerror = () => {
        setStatus('Connection error');
      };
      
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setStatus('Connection error');
    }
  }, [reconnectAttempts]);
  
  // Handle incoming WebSocket messages
  const handleMessage = useCallback((data) => {
    // Add message to state for use in components
    setMessages(prevMessages => [...prevMessages, data]);
  }, []);
  
  // Send a message through WebSocket
  const sendMessage = useCallback((message) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);
  
  // Connect on component mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      connect();
      
      // Cleanup on unmount
      return () => {
        if (socketRef.current) {
          socketRef.current.close();
        }
      };
    }
  }, [connect]);
  
  return {
    isConnected,
    status,
    messages,
    sendMessage,
    connect,
    socket: socketRef.current,
  };
}

*/