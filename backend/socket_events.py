import jwt
import datetime
import os
import logging
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room
from supabase import create_client, Client
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "your-secret-key")

def init_socket_events(socketio: SocketIO):
    
    def authenticate(token):
        """Authenticate and return user data from JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def verify_device(device_id, user_id):
        """Verify if the device belongs to the authenticated user."""
        try:
            response = supabase.table("devices")\
                .select("*")\
                .eq("id", device_id)\
                .eq("user_id", user_id)\
                .execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Device verification error: {e}")
            return False

    # Active sessions and peer mapping
    active_sessions = {}  # device_id -> [controller_sids]
    peer_connections = {}  # session_key -> {agent_sid, controller_sid}
    
    @socketio.on("connect")
    def handle_connect():
        """Handle client connection with authentication."""
        token = request.args.get("token")
        if not token:
            emit("error", {"message": "Authentication required"})
            return False
        
        user_data = authenticate(token)
        if not user_data:
            emit("error", {"message": "Invalid or expired token"})
            return False
        
        logger.info(f"Client connected: {user_data.get('sub')}")
        
    @socketio.on("agent_connect")
    def handle_agent_connect(data):
        """Handle agent registration and device association."""
        try:
            token = data.get("token")
            device_id = data.get("device_id")
            
            if not token or not device_id:
                emit("error", {"message": "Missing token or device_id"})
                return
            
            user_data = authenticate(token)
            if not user_data:
                emit("error", {"message": "Authentication failed"})
                return
            
            user_id = user_data.get("sub")
            
            # Verify device ownership
            if not verify_device(device_id, user_id):
                emit("error", {"message": "Device not found or unauthorized"})
                return
            
            # Update device status
            supabase.table("devices").update({
                "status": "online",
                "last_seen": datetime.datetime.utcnow().isoformat()
            }).eq("id", device_id).execute()
            
            # Join agent room
            agent_room = f"agent_{device_id}"
            join_room(agent_room)
            
            # Store session info
            session_id = request.sid
            if device_id not in active_sessions:
                active_sessions[device_id] = {"agent_sid": session_id, "controllers": []}
            else:
                active_sessions[device_id]["agent_sid"] = session_id
            
            emit("agent_connected", {
                "status": "success",
                "device_id": device_id,
                "message": "Agent registered successfully"
            })
            
            logger.info(f"Agent connected for device: {device_id}")
            
        except Exception as e:
            logger.error(f"Agent connection error: {e}")
            emit("error", {"message": "Failed to register agent"})
    
    @socketio.on("controller_join")
    def handle_controller_join(data):
        """Handle controller requesting access to a device."""
        try:
            token = data.get("token")
            device_id = data.get("device_id")
            
            if not token or not device_id:
                emit("error", {"message": "Missing token or device_id"})
                return
            
            user_data = authenticate(token)
            if not user_data:
                emit("error", {"message": "Authentication failed"})
                return
            
            user_id = user_data.get("sub")
            
            # Verify device ownership
            if not verify_device(device_id, user_id):
                emit("error", {"message": "Device not found or unauthorized"})
                return
            
            # Check if agent is online
            if device_id not in active_sessions or not active_sessions[device_id].get("agent_sid"):
                emit("error", {"message": "Device agent is offline"})
                return
            
            # Add controller to session
            controller_sid = request.sid
            if device_id in active_sessions:
                active_sessions[device_id]["controllers"].append(controller_sid)
            
            # Join controller room
            controller_room = f"controller_{device_id}_{request.sid}"
            join_room(controller_room)
            
            # Notify agent of new controller
            agent_sid = active_sessions[device_id]["agent_sid"]
            emit("controller_connected", {
                "controller_sid": controller_sid,
                "device_id": device_id
            }, room=agent_sid)
            
            # Send success response to controller
            emit("join_accepted", {
                "status": "success",
                "device_id": device_id,
                "agent_sid": agent_sid
            })
            
            logger.info(f"Controller joined for device: {device_id}")
            
        except Exception as e:
            logger.error(f"Controller join error: {e}")
            emit("error", {"message": "Failed to join session"})
    
    @socketio.on("agent_heartbeat")
    def handle_agent_heartbeat(data):
        """Handle agent heartbeat for connection monitoring."""
        try:
            device_id = data.get("device_id")
            if not device_id:
                return
            
            # Update last heartbeat timestamp
            supabase.table("devices").update({
                "last_heartbeat": datetime.datetime.utcnow().isoformat(),
                "status": "online"
            }).eq("id", device_id).execute()
            
            logger.debug(f"Heartbeat received for device: {device_id}")
            
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
    
    # ============================================================
    # WebRTC Signaling Events (New)
    # ============================================================
    
    @socketio.on("webrtc_offer")
    def handle_webrtc_offer(data):
        """Relay WebRTC offer from controller to agent."""
        try:
            token = data.get("token")
            device_id = data.get("device_id")
            offer = data.get("offer")
            
            if not all([token, device_id, offer]):
                emit("error", {"message": "Missing required WebRTC offer parameters"})
                return
            
            # Authenticate the controller
            user_data = authenticate(token)
            if not user_data:
                emit("error", {"message": "Authentication failed"})
                return
            
            user_id = user_data.get("sub")
            
            # Verify device ownership
            if not verify_device(device_id, user_id):
                emit("error", {"message": "Device not found or unauthorized"})
                return
            
            # Check if agent is online
            if device_id not in active_sessions or not active_sessions[device_id].get("agent_sid"):
                emit("error", {"message": "Device agent is offline"})
                return
            
            # Forward offer to agent
            agent_sid = active_sessions[device_id]["agent_sid"]
            emit("webrtc_offer", {
                "offer": offer,
                "controller_sid": request.sid,
                "device_id": device_id
            }, room=agent_sid)
            
            logger.info(f"WebRTC offer forwarded to device: {device_id}")
            
        except Exception as e:
            logger.error(f"WebRTC offer error: {e}")
            emit("error", {"message": "Failed to process WebRTC offer"})
    
    @socketio.on("webrtc_answer")
    def handle_webrtc_answer(data):
        """Relay WebRTC answer from agent to controller."""
        try:
            token = data.get("token")
            device_id = data.get("device_id")
            answer = data.get("answer")
            controller_sid = data.get("controller_sid")
            
            if not all([token, device_id, answer, controller_sid]):
                emit("error", {"message": "Missing required WebRTC answer parameters"})
                return
            
            # Authenticate the agent
            user_data = authenticate(token)
            if not user_data:
                emit("error", {"message": "Authentication failed"})
                return
            
            user_id = user_data.get("sub")
            
            # Verify device ownership
            if not verify_device(device_id, user_id):
                emit("error", {"message": "Device not found or unauthorized"})
                return
            
            # Forward answer to controller
            emit("webrtc_answer", {
                "answer": answer,
                "device_id": device_id,
                "agent_sid": request.sid
            }, room=controller_sid)
            
            logger.info(f"WebRTC answer forwarded to controller for device: {device_id}")
            
        except Exception as e:
            logger.error(f"WebRTC answer error: {e}")
            emit("error", {"message": "Failed to process WebRTC answer"})
    
    @socketio.on("webrtc_ice_candidate")
    def handle_webrtc_ice_candidate(data):
        """Exchange ICE candidates between peers."""
        try:
            token = data.get("token")
            device_id = data.get("device_id")
            candidate = data.get("candidate")
            target = data.get("target")  # "agent" or "controller"
            target_sid = data.get("target_sid")
            
            if not all([token, device_id, candidate, target, target_sid]):
                emit("error", {"message": "Missing required ICE candidate parameters"})
                return
            
            # Authenticate the sender
            user_data = authenticate(token)
            if not user_data:
                emit("error", {"message": "Authentication failed"})
                return
            
            user_id = user_data.get("sub")
            
            # Verify device ownership
            if not verify_device(device_id, user_id):
                emit("error", {"message": "Device not found or unauthorized"})
                return
            
            # Forward ICE candidate to target peer
            emit("webrtc_ice_candidate", {
                "candidate": candidate,
                "device_id": device_id,
                "from_sid": request.sid,
                "target": target
            }, room=target_sid)
            
            logger.debug(f"ICE candidate exchanged for device: {device_id}, target: {target}")
            
        except Exception as e:
            logger.error(f"ICE candidate error: {e}")
            emit("error", {"message": "Failed to exchange ICE candidate"})
    
    # ============================================================
    # Remote Control Commands (Keep these on Socket.IO)
    # ============================================================
    
    @socketio.on("remote_command")
    def handle_remote_command(data):
        """Relay remote control commands to agent."""
        try:
            token = data.get("token")
            device_id = data.get("device_id")
            command = data.get("command")
            params = data.get("params", {})
            
            if not all([token, device_id, command]):
                emit("error", {"message": "Missing remote command parameters"})
                return
            
            # Authenticate the controller
            user_data = authenticate(token)
            if not user_data:
                emit("error", {"message": "Authentication failed"})
                return
            
            user_id = user_data.get("sub")
            
            # Verify device ownership
            if not verify_device(device_id, user_id):
                emit("error", {"message": "Device not found or unauthorized"})
                return
            
            # Check if agent is online
            if device_id not in active_sessions or not active_sessions[device_id].get("agent_sid"):
                emit("error", {"message": "Device agent is offline"})
                return
            
            # Forward command to agent
            agent_sid = active_sessions[device_id]["agent_sid"]
            emit("execute_command", {
                "command": command,
                "params": params,
                "controller_sid": request.sid
            }, room=agent_sid)
            
            logger.info(f"Remote command sent to device: {device_id}")
            
        except Exception as e:
            logger.error(f"Remote command error: {e}")
            emit("error", {"message": "Failed to send remote command"})
    
    @socketio.on("agent_event")
    def handle_agent_event(data):
        """Handle events from agent (mouse, keyboard, clipboard, etc.)"""
        try:
            token = data.get("token")
            device_id = data.get("device_id")
            event_type = data.get("event_type")
            event_data = data.get("event_data", {})
            controller_sid = data.get("controller_sid")
            
            if not all([token, device_id, event_type]):
                emit("error", {"message": "Missing agent event parameters"})
                return
            
            # Authenticate the agent
            user_data = authenticate(token)
            if not user_data:
                emit("error", {"message": "Authentication failed"})
                return
            
            user_id = user_data.get("sub")
            
            # Verify device ownership
            if not verify_device(device_id, user_id):
                emit("error", {"message": "Device not found or unauthorized"})
                return
            
            # Forward event to specific controller or all controllers
            if controller_sid:
                emit("device_event", {
                    "event_type": event_type,
                    "event_data": event_data,
                    "device_id": device_id
                }, room=controller_sid)
            else:
                # Broadcast to all controllers for this device
                if device_id in active_sessions:
                    for ctrl_sid in active_sessions[device_id]["controllers"]:
                        emit("device_event", {
                            "event_type": event_type,
                            "event_data": event_data,
                            "device_id": device_id
                        }, room=ctrl_sid)
            
            logger.debug(f"Agent event processed: {event_type} for device: {device_id}")
            
        except Exception as e:
            logger.error(f"Agent event error: {e}")
            emit("error", {"message": "Failed to process agent event"})
    
    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle client disconnection and cleanup."""
        try:
            session_id = request.sid
            
            # Clean up active sessions
            for device_id, session_data in list(active_sessions.items()):
                if session_data["agent_sid"] == session_id:
                    # Agent disconnected
                    supabase.table("devices").update({
                        "status": "offline",
                        "last_seen": datetime.datetime.utcnow().isoformat()
                    }).eq("id", device_id).execute()
                    
                    # Notify all controllers
                    for ctrl_sid in session_data["controllers"]:
                        emit("agent_disconnected", {
                            "device_id": device_id
                        }, room=ctrl_sid)
                    
                    # Remove session
                    del active_sessions[device_id]
                    logger.info(f"Agent disconnected for device: {device_id}")
                    
                elif session_id in session_data["controllers"]:
                    # Controller disconnected
                    session_data["controllers"].remove(session_id)
                    
                    # Notify agent
                    if session_data.get("agent_sid"):
                        emit("controller_disconnected", {
                            "controller_sid": session_id
                        }, room=session_data["agent_sid"])
                    
                    logger.info(f"Controller disconnected from device: {device_id}")
            
        except Exception as e:
            logger.error(f"Disconnect error: {e}")