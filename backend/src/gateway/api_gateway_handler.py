from fastapi import APIRouter, Request, Response
import json
import logging
import asyncio
from typing import Dict, Any
import boto3
import os
import time


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ws-gateway")

# Store client_id to connection_id mapping
client_id_mapping: Dict[str, str] = {}

# Store connection managers by client_id
voice_assistants_by_client = {}


@router.post("/connect")
async def handle_connect(request: Request):
    """Handle WebSocket connection requests from API Gateway"""
    try:
        # Log full request for debugging
        logger.info(f"Connect request headers: {request.headers}")
        
        # Get the request body
        try:
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')
            logger.info(f"Connect request raw body: {body_str}")
            
            # Parse the body as JSON
            body = json.loads(body_str) if body_str else {}
            logger.info(f"Connect request parsed body: {body}")
        except Exception as e:
            logger.error(f"Error parsing connect request body: {str(e)}")
            body = {}
            
        # CRITICAL: Get connection ID from the correct location
        connection_id = body.get("connectionId")
        if not connection_id:
            logger.error("Missing connectionId in connect request")
            return Response(
                content=json.dumps({"message": "Missing connectionId"}),
                media_type="application/json",
                status_code=400
            )
        
        # Extract query parameters - IMPORTANT: match the template structure
        query_params = {}
        if "queryStringParameters" in body and body["queryStringParameters"]:
            query_params = body["queryStringParameters"]
            
        client_id = query_params.get("client_id", f"client-{connection_id[:8]}")
        
        # Log the connection
        logger.info(f"New connection: ID={connection_id}, client={client_id}")
        
        # Store client_id mapping
        client_id_mapping[client_id] = connection_id
        
        # CRITICAL: Return the EXACT format API Gateway expects
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({"message": "Connected"})
        }
    except Exception as e:
        logger.error(f"Error handling connect: {str(e)}")
        return Response(
            content=json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=500
        )
    

@router.post("/disconnect")
async def handle_disconnect(request: Request):
    """Handle WebSocket disconnection requests from API Gateway"""
    try:
        body = await request.json()
        connection_id = body.get("connectionId")
        
        if not connection_id:
            return Response(
                content=json.dumps({"error": "Missing connectionId"}),
                media_type="application/json",
                status_code=400
            )
        

        
        # Find client_id for this connection
        client_id = None
        for c_id, conn_id in list(client_id_mapping.items()):
            if conn_id == connection_id:
                client_id = c_id
                del client_id_mapping[c_id]
                break
        
        # Clean up voice assistant if it exists
        if client_id and client_id in voice_assistants_by_client:
            del voice_assistants_by_client[client_id]
        
        logger.info(f"API Gateway WebSocket connection closed: {connection_id}")
        
        return {
            "statusCode": 200, 
            "body": json.dumps({"message": "Disconnected"}),
            "headers": {
                "Content-Type": "application/json"
            }
        }
    except Exception as e:
        logger.error(f"Error handling disconnect: {str(e)}")
        return Response(
            content=json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=500
        )


@router.post("/message")
async def handle_message(request: Request):
    """Handle WebSocket messages from API Gateway with improved error handling"""
    try:
        # Log raw request first for debugging
        logger.info(f"Message request headers: {request.headers}")
        
        # Get raw body for debugging
        raw_body = await request.body()
        logger.info(f"Message raw body: {raw_body.decode('utf-8', errors='replace')}")
        
        # Parse the body
        try:
            body = await request.json()
            logger.info(f"Message parsed body: {body}")
        except Exception as e:
            logger.error(f"Error parsing message body: {str(e)}")
            return Response(
                content=json.dumps({"error": "Invalid JSON in request body"}),
                media_type="application/json",
                status_code=400
            )
        
        # Get connection ID
        connection_id = body.get("connectionId")
        if not connection_id:
            logger.error("Missing connectionId in message request")
            return Response(
                content=json.dumps({"error": "Missing connectionId"}),
                media_type="application/json",
                status_code=400
            )
        
        # Parse the actual message body
        message_body = {}
        if "body" in body:
            try:
                if isinstance(body["body"], str):
                    message_body = json.loads(body["body"])
                else:
                    message_body = body["body"]
                logger.info(f"Parsed message content: {message_body}")
            except Exception as e:
                logger.error(f"Error parsing message content: {str(e)}")
                message_body = {}
        
        # Handle special case for ping command
        if message_body.get("command") == "ping":
            # Find client_id for this connection
            client_id = None
            for c_id, conn_id in client_id_mapping.items():
                if conn_id == connection_id:
                    client_id = c_id
                    break
            
            # Send a pong response
            logger.info(f"Responding to ping from connection {connection_id}")
            if client_id:
                try:
                    await send_to_client(connection_id, {
                        "type": "pong",
                        "timestamp": message_body.get("timestamp", 0),
                        "serverTime": int(time.time() * 1000)
                    })
                    logger.info(f"Pong sent to {connection_id}")
                except Exception as e:
                    logger.error(f"Error sending pong: {str(e)}")
        
        # Find client_id for this connection
        client_id = None
        for c_id, conn_id in client_id_mapping.items():
            if conn_id == connection_id:
                client_id = c_id
                break
        
        if not client_id:
            logger.error(f"No client_id found for connection {connection_id}")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid client"})
            }
        
        # Process the message based on command
        command = message_body.get("command")
        logger.info(f"Received command '{command}' from client {client_id}")
        
        # Import voice assistants here to avoid circular imports
        from src.main import voice_assistants
        
        if client_id in voice_assistants:
            assistant = voice_assistants[client_id]
            
            try:
                if command == "text_query":
                    text = message_body.get("text", "")
                    await assistant.process_text_query(text)
                elif command == "audio_data":
                    audio = message_body.get("audio")
                    # Convert base64 to bytes
                    import base64
                    try:
                        audio_bytes = base64.b64decode(audio.split(",")[1] if "," in audio else audio)
                        await assistant.process_audio_data(audio_bytes)
                    except Exception as e:
                        logger.error(f"Error processing audio data: {str(e)}")
                elif command == "toggle_listen":
                    listening = message_body.get("listening", False)
                    logger.info(f"Setting listening state to {listening}")
                    # Handle toggle listen if needed
                elif command == "toggle_mute":
                    muted = message_body.get("muted", False)
                    logger.info(f"Setting mute state to {muted}")
                    assistant.is_muted = muted
                elif command == "interrupt_speech":
                    logger.info(f"Interrupting speech for client {client_id}")
                    assistant.is_interrupted = True
            except Exception as e:
                logger.error(f"Error processing command {command}: {str(e)}")
        else:
            logger.warning(f"No voice assistant found for client {client_id}")
        
        # CRITICAL: Return the EXACT format API Gateway expects
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Message processed"})
        }
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response(
            content=json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=500
        )
    
    
async def send_to_client(connection_id: str, message: Dict[str, Any]):
    """Send a message to the client through API Gateway Management API with improved error handling"""
    try:
        import boto3
        import json
        import time
        import os
        
        # Log what we're about to send
        logger.info(f"Sending message to connection {connection_id}: {message}")

        # Get API Gateway endpoint from environment or use hardcoded one
        # Remove the wss:// or https:// and /production from the endpoint
        #endpoint_url = os.environ.get("API_GATEWAY_WEBSOCKET_ENDPOINT", 
        #                            "https://5nu02h2v13.execute-api.eu-west-2.amazonaws.com/production")
        
        #if endpoint_url.startswith(("wss://", "https://")):
        #    endpoint_url = endpoint_url.split("://")[1]
        
        #if "/production" in endpoint_url:
        #    endpoint_url = endpoint_url.split("/production")[0]
        
        # Ensure we have the correct format
        #endpoint_url = f"https://{endpoint_url}/production"
        
        #endpoint_url = "https://5nu02h2v13.execute-api.eu-west-2.amazonaws.com/production"
                
        endpoint_url = os.environ.get("API_GATEWAY_WEBSOCKET_ENDPOINT", 
                                    "https://5nu02h2v13.execute-api.eu-west-2.amazonaws.com/production")

        # Standardize to https://
        if endpoint_url.startswith("wss://"):
            endpoint_url = "https://" + endpoint_url[6:]
        elif not endpoint_url.startswith("https://"):
            endpoint_url = "https://" + endpoint_url

        # Ensure it ends with /production
        if not endpoint_url.endswith("/production"):
            if "/production" in endpoint_url:
                # Extract the base URL without the stage
                base_url = endpoint_url.split("/production")[0]
                endpoint_url = f"{base_url}/production"
            else:
                endpoint_url = f"{endpoint_url}/production"

        logger.info(f"Using API Gateway Management API endpoint: {endpoint_url}")
        
        # Initialize API Gateway Management client
        api_gateway_management = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url,
            region_name=os.environ.get("AWS_REGION", "eu-west-2"),
            # Use AWS credentials from environment or instance profile
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            #aws_session_token=os.environ.get("AWS_SESSION_TOKEN")
        )
        
        # Convert message to JSON string and encode as bytes
        message_bytes = json.dumps(message).encode('utf-8')
        
        # Use asyncio to run the API call in a thread pool
        import asyncio
        try:
            await asyncio.to_thread(
                api_gateway_management.post_to_connection,
                ConnectionId=connection_id,
                Data=message_bytes
            )
            logger.info(f"Message successfully sent to connection {connection_id}")
            return True
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error sending message to connection {connection_id}: {error_message}")
            
            # Handle specific error cases
            if "GoneException" in error_message:
                logger.warning(f"Connection {connection_id} is gone. Removing from mappings.")
                # Remove stale connections
                for client_id, conn_id in list(client_id_mapping.items()):
                    if conn_id == connection_id:
                        del client_id_mapping[client_id]
                        break
            elif "ForbiddenException" in error_message:
                logger.error("ForbiddenException: Check IAM permissions for execute-api:ManageConnections")
            elif "AccessDeniedException" in error_message:
                logger.error("AccessDeniedException: Check IAM permissions and role assumption")
            elif "NotFoundException" in error_message:
                logger.error(f"NotFoundException: API Gateway endpoint {endpoint_url} not found")
            
            return False
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
        
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