from fastapi import APIRouter, Request, Response
from src.websocket.connection import ConnectionManager
import json
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ws-gateway")

# Store connection manager instances by connection ID
connection_managers: Dict[str, ConnectionManager] = {}

# Store message queues for each connection
message_queues: Dict[str, asyncio.Queue] = {}

# Store client_id to connection_id mapping
client_id_mapping: Dict[str, str] = {}

'''
@router.post("/connect")
async def handle_connect(request: Request):
    """Handle WebSocket connection requests from API Gateway"""
    try:
        logger.info(f"Received connect request: {request.headers}")
        # Try to get the body, but gracefully handle if it fails
        try:
            body = await request.json()
            logger.info(f"Connect request body: {body}")
        except:
            body = {}
            logger.warning("Could not parse request body in connect")
        
        connection_id = body.get("connectionId", request.headers.get("connectionid"))
        
        if not connection_id:
            logger.error("Missing connectionId in connect request")
            return Response(status_code=400, content="Missing connectionId")
        
        # Extract client_id from query parameters
        query_params = request.query_params
        client_id = query_params.get("client_id", f"client-{connection_id[:8]}")
        
        # Create message queue for this connection
        message_queues[connection_id] = asyncio.Queue()
        
        # Store client_id mapping
        client_id_mapping[client_id] = connection_id
        
        logger.info(f"New connection from API Gateway: {connection_id} (client: {client_id})")
        
        return {"statusCode": 200, "body": "Connected"}
    except Exception as e:
        logger.error(f"Error in handle_connect: {str(e)}")
        return Response(status_code=500, content=f"Error: {str(e)}")
'''

@router.post("/connect")
async def handle_connect(request: Request):
    """Handle WebSocket connection requests from API Gateway"""
    try:
        # Log full request for debugging
        logger.info(f"Connect request received: {request.headers}")
        
        # Safely parse body
        try:
            body = await request.json()
            logger.info(f"Connect request body: {body}")
        except Exception as e:
            logger.error(f"Error parsing connect request body: {str(e)}")
            body = {}
            
        # Get connection ID
        connection_id = body.get("connectionId")
        
        if not connection_id:
            logger.error("Missing connectionId in connect request")
            return Response(status_code=400, content="Missing connectionId")
        
        # Extract query params
        query_params = {}
        if "queryStringParameters" in body and body["queryStringParameters"]:
            query_params = body["queryStringParameters"]
            
        client_id = query_params.get("client_id", f"client-{connection_id[:8]}")
        
        # Log the connection
        logger.info(f"New connection: ID={connection_id}, client={client_id}")
        
        # Create message queue for this connection
        message_queues[connection_id] = asyncio.Queue()
        
        # Store client_id mapping
        client_id_mapping[client_id] = connection_id
        
        return {"statusCode": 200, "body": "Connected"}
    except Exception as e:
        logger.error(f"Error handling connect: {str(e)}")
        return Response(status_code=500, content=f"Error: {str(e)}")


@router.post("/disconnect")
async def handle_disconnect(request: Request):
    """Handle WebSocket disconnection requests from API Gateway"""
    body = await request.json()
    connection_id = body.get("connectionId")
    
    if not connection_id:
        return Response(status_code=400, content="Missing connectionId")
    
    # Clean up resources
    if connection_id in message_queues:
        del message_queues[connection_id]
    
    # Remove client_id mapping
    for client_id, conn_id in list(client_id_mapping.items()):
        if conn_id == connection_id:
            del client_id_mapping[client_id]
    
    logger.info(f"Connection closed from API Gateway: {connection_id}")
    
    return {"statusCode": 200, "body": "Disconnected"}


@router.post("/message")
async def handle_message(request: Request):
    """Handle WebSocket messages from API Gateway"""
    body = await request.json()
    connection_id = body.get("connectionId")
    message_body = body.get("body", {})
    
    if not connection_id:
        return Response(status_code=400, content="Missing connectionId")
    
    # Process the message similar to how we handle WebSocket messages
    # Extract client_id and command
    client_id = None
    for c_id, conn_id in client_id_mapping.items():
        if conn_id == connection_id:
            client_id = c_id
            break
    
    if not client_id:
        logger.error(f"No client_id found for connection {connection_id}")
        return {"statusCode": 400, "body": "Invalid client"}
    
    # Process the message based on command
    command = message_body.get("command")
    if command == "text_query":
        # Handle text query
        text = message_body.get("text", "")
        # Forward to your existing text query handler
        await process_text_query(client_id, text)
    elif command == "audio_data":
        # Handle audio data
        audio = message_body.get("audio")
        # Forward to your existing audio handler
        await process_audio_data(client_id, audio)
    elif command == "toggle_listen":
        # Handle toggle listen
        listening = message_body.get("listening", False)
        # Forward to your existing handler
        await process_toggle_listen(client_id, listening)
    elif command == "toggle_mute":
        # Handle toggle mute
        muted = message_body.get("muted", False)
        # Forward to your existing handler
        await process_toggle_mute(client_id, muted)
    elif command == "interrupt_speech":
        # Handle interrupt speech
        await process_interrupt_speech(client_id)
    
    return {"statusCode": 200, "body": "Message processed"}


# Function to send a message back to the client through API Gateway
async def send_to_client(connection_id: str, message: Dict[str, Any]):
    """Send a message to the client through API Gateway"""
    import boto3
    
    # Initialize boto3 client for API Gateway Management API
    api_gateway_management = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=f"https://5nu02h2v13.execute-api.eu-west-2.amazonaws.com/production",
        #endpoint_url=f"https://5nu02h2v13.execute-api.eu-west-2.amazonaws.com/production/@connections",
        #endpoint_url=f"wss://5nu02h2v13.execute-api.eu-west-2.amazonaws.com/production/",
    )
    
    try:
        # Send the message
        api_gateway_management.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode('utf-8')
        )
        logger.info(f"Message sent to connection {connection_id}")
    except Exception as e:
        logger.error(f"Error sending message to connection {connection_id}: {str(e)}")
        # Remove stale connections
        if "GoneException" in str(e):
            if connection_id in message_queues:
                del message_queues[connection_id]


# Implement handlers that connect to your existing voice assistant logic
async def process_text_query(client_id: str, text: str):
    """Process a text query from the client"""
    # This function should integrate with your existing voice assistant logic
    from src.main import voice_assistants
    
    if client_id in voice_assistants:
        await voice_assistants[client_id].process_text_query(text)

async def process_audio_data(client_id: str, audio_data: str):
    """Process audio data from the client"""
    # This function should integrate with your existing voice assistant logic
    from src.main import voice_assistants
    
    if client_id in voice_assistants:
        # Convert base64 to bytes if needed
        import base64
        
        if isinstance(audio_data, str) and audio_data.startswith("data:audio"):
            # Handle data URL format
            audio_bytes = base64.b64decode(audio_data.split(",")[1])
        elif isinstance(audio_data, str):
            # Handle plain base64
            audio_bytes = base64.b64decode(audio_data)
        else:
            audio_bytes = audio_data
            
        await voice_assistants[client_id].process_audio_data(audio_bytes)

async def process_toggle_listen(client_id: str, is_listening: bool):
    """Process toggle listen command"""
    # Integrate with your existing handler
    
async def process_toggle_mute(client_id: str, is_muted: bool):
    """Process toggle mute command"""
    # Integrate with your existing handler
    from src.main import voice_assistants
    
    if client_id in voice_assistants:
        voice_assistants[client_id].is_muted = is_muted

async def process_interrupt_speech(client_id: str):
    """Process interrupt speech command"""
    # Integrate with your existing handler
    from src.main import voice_assistants
    
    if client_id in voice_assistants:
        voice_assistants[client_id].is_interrupted = True