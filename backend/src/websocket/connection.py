import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        """Connect a new client"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total connections: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        """Disconnect a client"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Remaining connections: {len(self.active_connections)}")
        
    '''
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            if isinstance(message, dict):
                await websocket.send_json(message)
            else:
                await websocket.send_text(str(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    '''

'''            
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket, client_id: Optional[str] = None):
        """Send a message to a specific client"""
        try:
            # Direct WebSocket connection (existing code)
            if isinstance(message, dict):
                await websocket.send_json(message)
            else:
                await websocket.send_text(str(message))
                
            # If client_id is provided, also send through API Gateway
            if client_id:
                # Import here to avoid circular imports
                from src.gateway.api_gateway_handler import send_to_client, client_id_mapping
                
                if client_id in client_id_mapping:
                    connection_id = client_id_mapping[client_id]
                    await send_to_client(connection_id, message)

        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            
'''

async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket, client_id: Optional[str] = None):
    """Send a message to a specific client"""
    try:
        # Direct WebSocket connection
        if isinstance(message, dict):
            await websocket.send_json(message)
        else:
            await websocket.send_text(str(message))
            
        # If client_id is provided, try gateway (but avoid circular imports)
        if client_id:
            # Import dynamically to avoid circular imports
            import sys
            if 'src.gateway.api_gateway_handler' in sys.modules:
                gateway_module = sys.modules['src.gateway.api_gateway_handler']
                if hasattr(gateway_module, 'client_id_mapping') and hasattr(gateway_module, 'send_to_client'):
                    if client_id in gateway_module.client_id_mapping:
                        connection_id = gateway_module.client_id_mapping[client_id]
                        await gateway_module.send_to_client(connection_id, message)
                        
    except Exception as e:
        logger.error(f"Error sending personal message: {e}")



    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients"""
        for connection in self.active_connections:
            try:
                if isinstance(message, dict):
                    await connection.send_json(message)
                else:
                    await connection.send_text(str(message))
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")




# Test function
def test_connection_manager():
    """Simple test for ConnectionManager"""
    manager = ConnectionManager()
    logger.info(f"ConnectionManager initialized with {len(manager.active_connections)} connections")
    return manager