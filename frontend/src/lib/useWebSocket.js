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
  
  // Function to establish WebSocket connection with better debugging
  const connect = useCallback(() => {
    // Generate a unique client ID
    const clientId = 'client-' + Math.random().toString(36).substring(2, 9);

    // Get the WebSocket URL from environment variables
    const apiGateway = process.env.NEXT_PUBLIC_WS_GATEWAY || '';

    if (!apiGateway) {
      console.error('WebSocket Gateway URL not configured');
      setStatus('Configuration error');
      return;
    }
    
    // Construct the WebSocket URL with client ID as a query parameter
    const wsUrl = `${apiGateway}?client_id=${clientId}`;
    
    console.log("[WebSocket] Connecting to API Gateway:", wsUrl);
    console.log("[WebSocket] Environment:", {
      WS_GATEWAY: process.env.NEXT_PUBLIC_WS_GATEWAY,
      API_URL: process.env.NEXT_PUBLIC_API_URL,
      WS_HOST: process.env.NEXT_PUBLIC_WS_HOST
    });

    // Close existing socket if open
    if (socketRef.current && 
        (socketRef.current.readyState === WebSocket.OPEN || 
         socketRef.current.readyState === WebSocket.CONNECTING)) {
      console.log("[WebSocket] Closing existing connection");
      socketRef.current.close();
    }
    
    try {
      console.log("[WebSocket] Creating new WebSocket instance");
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;
      
      socket.onopen = (event) => {
        console.log("[WebSocket] Connection established successfully", event);
        setIsConnected(true);
        setStatus('Connected');
        setReconnectAttempts(0);
        
        // Send an initial ping to test the connection
        try {
          console.log("[WebSocket] Sending initial ping");
          socket.send(JSON.stringify({ command: "ping", timestamp: Date.now() }));
        } catch (e) {
          console.error("[WebSocket] Error sending initial ping:", e);
        }
      };
      
      socket.onclose = (event) => {
        console.log("[WebSocket] Connection closed", {
          wasClean: event.wasClean,
          code: event.code,
          reason: event.reason,
          type: event.type
        });
        
        setIsConnected(false);
        
        // Add detailed error information based on close code
        let closeReason = "Unknown reason";
        switch(event.code) {
          case 1000: closeReason = "Normal closure"; break;
          case 1001: closeReason = "Going away"; break;
          case 1002: closeReason = "Protocol error"; break;
          case 1003: closeReason = "Unsupported data"; break;
          case 1005: closeReason = "No status received"; break;
          case 1006: closeReason = "Abnormal closure - check server logs"; break;
          case 1007: closeReason = "Invalid frame payload data"; break;
          case 1008: closeReason = "Policy violation"; break;
          case 1009: closeReason = "Message too big"; break;
          case 1010: closeReason = "Mandatory extension missing"; break;
          case 1011: closeReason = "Internal server error"; break;
          case 1012: closeReason = "Service restart"; break;
          case 1013: closeReason = "Try again later"; break;
          case 1014: closeReason = "Bad gateway"; break;
          case 1015: closeReason = "TLS handshake failure"; break;
        }
        
        console.log("[WebSocket] Close reason:", closeReason);
        
        // Only attempt reconnection if this wasn't a clean close
        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
          const newAttempts = reconnectAttempts + 1;
          setReconnectAttempts(newAttempts);
          setStatus(`Reconnecting (${newAttempts}/${maxReconnectAttempts})...`);
          
          // Schedule reconnection
          console.log(`[WebSocket] Scheduling reconnection attempt ${newAttempts}/${maxReconnectAttempts}`);
          setTimeout(connect, reconnectInterval);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          console.log("[WebSocket] Maximum reconnection attempts reached");
          setStatus(`Connection failed (${closeReason})`);
        } else {
          setStatus(`Disconnected (${closeReason})`);
        }
      };
      
      socket.onerror = (error) => {
        console.error("[WebSocket] Error:", error);
        setStatus('Connection error');
      };
      
      socket.onmessage = (event) => {
        console.log("[WebSocket] Message received:", event.data);
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (error) {
          console.error('[WebSocket] Error parsing message:', error, event.data);
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      setStatus('Connection error');
    }
  }, [reconnectAttempts]);
  
  // Handle incoming WebSocket messages
  const handleMessage = useCallback((data) => {
    console.log("[WebSocket] Processing message:", data);
    // Add message to state for use in components
    setMessages(prevMessages => [...prevMessages, data]);
  }, []);
  
  // Send a message through WebSocket
  const sendMessage = useCallback((message) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      console.log("[WebSocket] Sending message:", message);
      socketRef.current.send(JSON.stringify(message));
      return true;
    }
    console.warn("[WebSocket] Cannot send message - not connected");
    return false;
  }, []);
  
  // Connect on component mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      console.log("[WebSocket] Component mounted, initializing connection");
      // Add a small delay to ensure window is fully loaded
      const timer = setTimeout(() => {
        connect();
      }, 100);
      
      // Cleanup on unmount
      return () => {
        console.log("[WebSocket] Component unmounting, cleaning up");
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