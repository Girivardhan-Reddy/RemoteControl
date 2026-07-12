package com.remotecontrol.app.webrtc;

import android.content.Context;
import android.util.Log;

import org.webrtc.*;
import org.json.JSONObject;
import org.json.JSONException;

import io.socket.client.IO;
import io.socket.client.Socket;
import io.socket.emitter.Emitter;

import java.net.URISyntaxException;

/**
 * Handles WebRTC signaling via Socket.IO connection to Flask backend.
 * Manages authentication, connection lifecycle, and exchange of
 * SDP offers, SDP answers, and ICE candidates.
 * 
 * Backend expectations:
 * - controller_join expects: {token, session_id}
 * - webrtc_offer expects: {token, device_id, offer}
 * - webrtc_answer expects: {token, device_id, answer, controller_sid}
 * - webrtc_ice_candidate expects: {token, device_id, candidate, target, target_sid}
 */
public class SignalingClient {
    private static final String TAG = "SignalingClient";

    private final Context context;
    private final String serverUrl;
    private final String token;
    private Socket socket;
    private WebRTCManager webRTCManager;

    // Connection state
    private boolean isConnected = false;
    private String sessionId;
    private String deviceId;
    private String agentSid;
    private String controllerSid;

    // Callback for signaling events
    private SignalingCallback callback;

    /**
     * Interface for signaling events callbacks
     */
    public interface SignalingCallback {
        void onConnected();
        void onDisconnected();
        void onError(String error);
        void onSessionJoined(String deviceId, String agentSid);
        void onOfferReceived(String deviceId, SessionDescription sdp);
        void onAnswerReceived(String deviceId, SessionDescription sdp);
        void onIceCandidateReceived(String deviceId, IceCandidate iceCandidate);
    }

    /**
     * Constructor for SignalingClient
     * @param context Android application context
     * @param serverUrl Flask backend URL (e.g., "https://your-server.com")
     * @param token JWT authentication token
     */
    public SignalingClient(Context context, String serverUrl, String token) {
        this.context = context;
        this.serverUrl = serverUrl;
        this.token = token;
    }

    /**
     * Set callback for signaling events
     */
    public void setCallback(SignalingCallback callback) {
        this.callback = callback;
    }

    /**
     * Set WebRTC manager for processing signaling messages
     */
    public void setWebRTCManager(WebRTCManager manager) {
        this.webRTCManager = manager;
    }

    /**
     * Connect to Flask Socket.IO backend and register event handlers
     */
    public void connect() {
        try {
            // Configure Socket.IO connection options
            IO.Options options = new IO.Options();
            options.reconnection = true;
            options.reconnectionAttempts = Integer.MAX_VALUE;
            options.reconnectionDelay = 1000;
            options.reconnectionDelayMax = 6000;
            options.transports = new String[]{"websocket", "polling"};
            options.timeout = 10000;

            // Connect to server
            socket = IO.socket(serverUrl, options);
            
            // Register connection event handlers
            socket.on(Socket.EVENT_CONNECT, onConnect);
            socket.on(Socket.EVENT_DISCONNECT, onDisconnect);
            socket.on(Socket.EVENT_CONNECT_ERROR, onConnectError);

            // Register WebRTC signaling event handlers
            socket.on("webrtc_offer", onOfferReceived);
            socket.on("webrtc_answer", onAnswerReceived);
            socket.on("webrtc_ice_candidate", onIceCandidateReceived);
            
            // Session management events
            socket.on("join_accepted", onJoinAccepted);
            socket.on("controller_connected", onControllerConnected);
            socket.on("agent_disconnected", onAgentDisconnected);

            // Error handling
            socket.on("error", onError);

            socket.connect();
            Log.d(TAG, "Connecting to signaling server: " + serverUrl);

        } catch (URISyntaxException e) {
            Log.e(TAG, "Invalid server URL: " + e.getMessage());
            if (callback != null) {
                callback.onError("Invalid server URL: " + e.getMessage());
            }
        }
    }

    /**
     * Join a remote session for a specific session
     * Matches backend's controller_join handler expecting:
     * {token, session_id}
     * 
     * @param sessionId Session ID to join
     */
    public void joinSession(String sessionId) {
        this.sessionId = sessionId;
        Log.d(TAG, "Joining session: " + sessionId);

        try {
            JSONObject payload = new JSONObject();
            payload.put("token", token);
            payload.put("session_id", sessionId);
            
            socket.emit("controller_join", payload);
            Log.d(TAG, "controller_join emitted with session_id: " + sessionId);
            
        } catch (JSONException e) {
            Log.e(TAG, "Error creating join payload: " + e.getMessage());
            if (callback != null) {
                callback.onError("Failed to join session: " + e.getMessage());
            }
        }
    }

    /**
     * Send WebRTC offer to remote device
     * Matches backend's webrtc_offer handler expecting:
     * {token, device_id, offer}
     * 
     * @param deviceId Target device ID
     * @param sdp Local session description (offer)
     */
    public void sendOffer(String deviceId, SessionDescription sdp) {
        if (socket == null || !socket.connected()) {
            Log.e(TAG, "Cannot send offer - not connected");
            return;
        }

        try {
            JSONObject offerData = new JSONObject();
            offerData.put("token", token);
            offerData.put("device_id", deviceId);

            JSONObject offer = new JSONObject();
            offer.put("type", sdp.type.canonicalForm());
            offer.put("sdp", sdp.description);

            offerData.put("offer", offer);
            
            socket.emit("webrtc_offer", offerData);
            Log.d(TAG, "WebRTC offer sent to device: " + deviceId);
            
        } catch (JSONException e) {
            Log.e(TAG, "Error creating offer payload: " + e.getMessage());
            if (callback != null) {
                callback.onError("Failed to send offer: " + e.getMessage());
            }
        }
    }

    /**
     * Send ICE candidate to remote device
     * Matches backend's webrtc_ice_candidate handler expecting:
     * {token, device_id, candidate, target, target_sid}
     * 
     * @param deviceId Target device ID
     * @param iceCandidate Local ICE candidate
     */
    public void sendIceCandidate(String deviceId, IceCandidate iceCandidate) {
        if (socket == null || !socket.connected()) {
            Log.e(TAG, "Cannot send ICE candidate - not connected");
            return;
        }

        try {
            JSONObject candidateData = new JSONObject();
            candidateData.put("token", token);
            candidateData.put("device_id", deviceId);

            JSONObject candidate = new JSONObject();
            candidate.put("candidate", iceCandidate.sdp);
            candidate.put("sdpMid", iceCandidate.sdpMid);
            candidate.put("sdpMLineIndex", iceCandidate.sdpMLineIndex);

            candidateData.put("candidate", candidate);
            candidateData.put("target", "agent");
            candidateData.put("target_sid", agentSid);

            socket.emit("webrtc_ice_candidate", candidateData);
            Log.d(TAG, "ICE candidate sent to agent: " + agentSid);
            
        } catch (JSONException e) {
            Log.e(TAG, "Error creating ICE candidate payload: " + e.getMessage());
            if (callback != null) {
                callback.onError("Failed to send ICE candidate: " + e.getMessage());
            }
        }
    }

    /**
     * Send WebRTC answer to controller (used when agent sends offer)
     * Matches backend's webrtc_answer handler expecting:
     * {token, device_id, answer, controller_sid}
     * 
     * @param deviceId Device ID
     * @param sdp Local session description (answer)
     * @param controllerSid Target controller session ID
     */
    public void sendAnswer(String deviceId, SessionDescription sdp, String controllerSid) {
        if (socket == null || !socket.connected()) {
            Log.e(TAG, "Cannot send answer - not connected");
            return;
        }

        try {
            JSONObject answerData = new JSONObject();
            answerData.put("token", token);
            answerData.put("device_id", deviceId);

            JSONObject answer = new JSONObject();
            answer.put("type", sdp.type.canonicalForm());
            answer.put("sdp", sdp.description);

            answerData.put("answer", answer);
            answerData.put("controller_sid", controllerSid);
            
            socket.emit("webrtc_answer", answerData);
            Log.d(TAG, "WebRTC answer sent to controller: " + controllerSid);
            
        } catch (JSONException e) {
            Log.e(TAG, "Error creating answer payload: " + e.getMessage());
            if (callback != null) {
                callback.onError("Failed to send answer: " + e.getMessage());
            }
        }
    }

    /**
     * Disconnect from signaling server and clean up
     */
    public void disconnect() {
        Log.d(TAG, "Disconnecting from signaling server");
        
        if (socket != null) {
            // Remove all listeners to prevent memory leaks
            socket.off(Socket.EVENT_CONNECT);
            socket.off(Socket.EVENT_DISCONNECT);
            socket.off(Socket.EVENT_CONNECT_ERROR);
            socket.off("webrtc_offer");
            socket.off("webrtc_answer");
            socket.off("webrtc_ice_candidate");
            socket.off("join_accepted");
            socket.off("controller_connected");
            socket.off("agent_disconnected");
            socket.off("error");
            
            socket.disconnect();
            socket = null;
        }
        
        isConnected = false;
        sessionId = null;
        agentSid = null;
        controllerSid = null;
    }

    /**
     * Get the Socket.IO socket instance (for direct access if needed)
     */
    public Socket getSocket() {
        return socket;
    }

    /**
     * Get the current agent session ID
     */
    public String getAgentSid() {
        return agentSid;
    }

    /**
     * Get the current controller session ID
     */
    public String getControllerSid() {
        return controllerSid;
    }

    /**
     * Check if connected to signaling server
     */
    public boolean isConnected() {
        return isConnected && socket != null && socket.connected();
    }

    // Socket.IO event handlers

    /**
     * Handle successful connection to backend
     */
    private final Emitter.Listener onConnect = args -> {
        Log.d(TAG, "Connected to signaling server, SID: " + socket.id());
        isConnected = true;
        controllerSid = socket.id();
        
        if (callback != null) {
            callback.onConnected();
        }
    };

    /**
     * Handle disconnection from backend
     */
    private final Emitter.Listener onDisconnect = args -> {
        String reason = args.length > 0 ? args[0].toString() : "Unknown";
        Log.d(TAG, "Disconnected from signaling server: " + reason);
        isConnected = false;
        
        if (callback != null) {
            callback.onDisconnected();
        }
    };

    /**
     * Handle connection errors
     */
    private final Emitter.Listener onConnectError = args -> {
        String error = args.length > 0 ? args[0].toString() : "Connection error";
        Log.e(TAG, "Connection error: " + error);
        isConnected = false;
        
        if (callback != null) {
            callback.onError("Connection failed: " + error);
        }
    };

    /**
     * Handle join_accepted event from backend
     * Backend sends: {status: "success", device_id, agent_sid}
     */
    private final Emitter.Listener onJoinAccepted = args -> {
        Log.d(TAG, "Join accepted for session");
        
        try {
            JSONObject response = (JSONObject) args[0];
            String status = response.optString("status");
            
            if ("success".equals(status)) {
                deviceId = response.optString("device_id");
                agentSid = response.optString("agent_sid");
                
                Log.d(TAG, "Session joined successfully - Device: " + deviceId + 
                      ", Agent SID: " + agentSid);
                
                if (callback != null) {
                    callback.onSessionJoined(deviceId, agentSid);
                }
            } else {
                String message = response.optString("message", "Unknown error");
                Log.e(TAG, "Session join failed: " + message);
                
                if (callback != null) {
                    callback.onError("Failed to join session: " + message);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error processing join response: " + e.getMessage());
            if (callback != null) {
                callback.onError("Invalid join response: " + e.getMessage());
            }
        }
    };

    /**
     * Handle controller_connected event from backend
     * Backend notifies that a new controller has connected
     */
    private final Emitter.Listener onControllerConnected = args -> {
        try {
            JSONObject data = (JSONObject) args[0];
            String newControllerSid = data.optString("controller_sid");
            String connectedDeviceId = data.optString("device_id");
            
            Log.d(TAG, "Controller connected - SID: " + newControllerSid + 
                      ", Device: " + connectedDeviceId);
            
        } catch (Exception e) {
            Log.e(TAG, "Error processing controller connected: " + e.getMessage());
        }
    };

    /**
     * Handle agent_disconnected event from backend
     * Backend notifies that the agent has disconnected
     */
    private final Emitter.Listener onAgentDisconnected = args -> {
        try {
            JSONObject data = (JSONObject) args[0];
            String disconnectedDeviceId = data.optString("device_id");
            
            Log.w(TAG, "Agent disconnected for device: " + disconnectedDeviceId);
            
            if (disconnectedDeviceId.equals(deviceId)) {
                // Our agent disconnected
                if (callback != null) {
                    callback.onDisconnected();
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error processing agent disconnected: " + e.getMessage());
        }
    };

    /**
     * Handle incoming WebRTC offer from agent
     * Backend forwards: {offer: {type, sdp}, device_id, controller_sid}
     */
    private final Emitter.Listener onOfferReceived = args -> {
        try {
            JSONObject data = (JSONObject) args[0];
            JSONObject offerObj = data.getJSONObject("offer");

            SessionDescription sdp = new SessionDescription(
                    SessionDescription.Type.fromCanonicalForm(offerObj.getString("type")),
                    offerObj.getString("sdp")
            );

            String remoteDeviceId = data.getString("device_id");
            String remoteControllerSid = data.optString("controller_sid");
            
            Log.d(TAG, "Received WebRTC offer from device: " + remoteDeviceId + 
                      ", Controller: " + remoteControllerSid);

            // Store controller SID if provided
            if (remoteControllerSid != null) {
                controllerSid = remoteControllerSid;
            }

            if (callback != null) {
                callback.onOfferReceived(remoteDeviceId, sdp);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error processing received offer: " + e.getMessage());
            if (callback != null) {
                callback.onError("Invalid offer received: " + e.getMessage());
            }
        }
    };

    /**
     * Handle incoming WebRTC answer from agent
     * Backend forwards: {answer: {type, sdp}, device_id, agent_sid}
     */
    private final Emitter.Listener onAnswerReceived = args -> {
        try {
            JSONObject data = (JSONObject) args[0];
            JSONObject answerObj = data.getJSONObject("answer");

            SessionDescription sdp = new SessionDescription(
                    SessionDescription.Type.fromCanonicalForm(answerObj.getString("type")),
                    answerObj.getString("sdp")
            );

            String remoteDeviceId = data.getString("device_id");
            String remoteAgentSid = data.optString("agent_sid");
            
            Log.d(TAG, "Received WebRTC answer from device: " + remoteDeviceId + 
                      ", Agent: " + remoteAgentSid);

            // Update agent SID if provided
            if (remoteAgentSid != null) {
                agentSid = remoteAgentSid;
            }

            // Forward answer to WebRTC manager
            if (webRTCManager != null) {
                webRTCManager.handleAnswer(sdp);
            }

            if (callback != null) {
                callback.onAnswerReceived(remoteDeviceId, sdp);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error processing received answer: " + e.getMessage());
            if (callback != null) {
                callback.onError("Invalid answer received: " + e.getMessage());
            }
        }
    };

    /**
     * Handle incoming ICE candidate from remote peer
     * Backend forwards: {candidate: {candidate, sdpMid, sdpMLineIndex}, 
     *                    device_id, target, from_sid}
     */
    private final Emitter.Listener onIceCandidateReceived = args -> {
        try {
            JSONObject data = (JSONObject) args[0];
            JSONObject candidateObj = data.getJSONObject("candidate");

            IceCandidate iceCandidate = new IceCandidate(
                    candidateObj.getString("sdpMid"),
                    candidateObj.getInt("sdpMLineIndex"),
                    candidateObj.getString("candidate")
            );

            String remoteDeviceId = data.getString("device_id");
            String target = data.optString("target");
            String fromSid = data.optString("from_sid");
            
            Log.d(TAG, "Received ICE candidate from: " + fromSid + 
                      ", Target: " + target + ", Device: " + remoteDeviceId);

            // Forward ICE candidate to WebRTC manager
            if (webRTCManager != null) {
                webRTCManager.addIceCandidate(iceCandidate);
            }

            if (callback != null) {
                callback.onIceCandidateReceived(remoteDeviceId, iceCandidate);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error processing ICE candidate: " + e.getMessage());
            if (callback != null) {
                callback.onError("Invalid ICE candidate: " + e.getMessage());
            }
        }
    };

    /**
     * Handle general error events from backend
     */
    private final Emitter.Listener onError = args -> {
        String error = args.length > 0 ? args[0].toString() : "Unknown error";
        Log.e(TAG, "Server error: " + error);
        
        if (callback != null) {
            callback.onError(error);
        }
    };
}