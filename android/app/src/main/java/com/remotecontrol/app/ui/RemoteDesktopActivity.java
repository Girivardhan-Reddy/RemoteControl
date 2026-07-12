package com.remotecontrol.app.ui;

import android.app.AlertDialog;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.util.Base64;
import android.view.MotionEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.remotecontrol.app.R;
import com.remotecontrol.app.util.SettingsStore;
import com.remotecontrol.app.util.TokenStore;

import org.webrtc.*;
import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

import io.socket.client.IO;
import io.socket.client.Socket;

public class RemoteDesktopActivity extends AppCompatActivity {
    private static final long LONG_PRESS_MS = 520;
    private static final long MOVE_THROTTLE_MS = 45;

    private Socket socket;
    private String sessionId;
    private SurfaceViewRenderer remoteView;
    private int remoteWidth = 1;
    private int remoteHeight = 1;
    private float downX;
    private float downY;
    private long downAtMs;
    private long lastMoveAtMs;

    // WebRTC components
    private PeerConnectionFactory peerConnectionFactory;
    private PeerConnection peerConnection;
    private EglBase eglBase;
    private VideoTrack remoteVideoTrack;
    private AudioTrack remoteAudioTrack;
    private String deviceId;
    private String agentSid;

    // STUN/TURN servers
    private static final List<PeerConnection.IceServer> ICE_SERVERS = new ArrayList<>();

    static {
        ICE_SERVERS.add(PeerConnection.IceServer.builder("stun:stun.l.google.com:19302").createIceServer());
        // Add your TURN server here for better connectivity
        // ICE_SERVERS.add(PeerConnection.IceServer.builder("turn:your-turn-server.com:3478")
        //     .setUsername("username")
        //     .setPassword("password")
        //     .createIceServer());
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        setContentView(R.layout.activity_remote_desktop);

        sessionId = getIntent().getStringExtra("session_id");
        deviceId = getIntent().getStringExtra("device_id");

        // Initialize WebRTC components
        initializeWebRTC();

        // Initialize SurfaceViewRenderer
        remoteView = findViewById(R.id.remoteView);
        remoteView.init(eglBase.getEglBaseContext(), null);
        remoteView.setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT);
        remoteView.setEnableHardwareScaler(true);
        remoteView.setOnTouchListener(this::handleScreenTouch);

        Button keyboard = findViewById(R.id.keyboardButton);
        keyboard.setOnClickListener(v -> showKeyboardDialog());

        connectSocket();
    }

    private void initializeWebRTC() {
        // Initialize EGL context
        eglBase = EglBase.create();

        // Initialize PeerConnectionFactory
        PeerConnectionFactory.InitializationOptions initializationOptions =
                PeerConnectionFactory.InitializationOptions.builder(this)
                        .setFieldTrials("WebRTC-H264HighProfile/Enabled/")
                        .createInitializationOptions();
        PeerConnectionFactory.initialize(initializationOptions);

        PeerConnectionFactory.Options options = new PeerConnectionFactory.Options();
        peerConnectionFactory = PeerConnectionFactory.builder()
                .setOptions(options)
                .setVideoDecoderFactory(new DefaultVideoDecoderFactory(eglBase.getEglBaseContext()))
                .setVideoEncoderFactory(new DefaultVideoEncoderFactory(eglBase.getEglBaseContext(), true, true))
                .createPeerConnectionFactory();
    }

    private void createPeerConnection() {
        PeerConnection.RTCConfiguration rtcConfig = new PeerConnection.RTCConfiguration(ICE_SERVERS);
        rtcConfig.iceTransportsType = PeerConnection.IceTransportsType.ALL;
        rtcConfig.tcpCandidatePolicy = PeerConnection.TcpCandidatePolicy.ENABLED;
        rtcConfig.bundlePolicy = PeerConnection.BundlePolicy.MAXBUNDLE;
        rtcConfig.rtcpMuxPolicy = PeerConnection.RtcpMuxPolicy.REQUIRE;
        rtcConfig.continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_CONTINUALLY;
        rtcConfig.keyType = PeerConnection.KeyType.ECDSA;

        peerConnection = peerConnectionFactory.createPeerConnection(rtcConfig, new PeerConnectionObserver());
    }

    private void startWebRTC() {
        if (peerConnection == null) {
            createPeerConnection();
        }

        // Create and send offer
        peerConnection.createOffer(new SdpObserver(), new MediaConstraints());
    }

    private class PeerConnectionObserver implements PeerConnection.Observer {
        @Override
        public void onIceCandidate(IceCandidate iceCandidate) {
            // Send ICE candidate to agent
            try {
                JSONObject candidateData = new JSONObject();
                candidateData.put("token", new TokenStore(RemoteDesktopActivity.this).access());
                candidateData.put("device_id", deviceId);
                
                JSONObject candidate = new JSONObject();
                candidate.put("candidate", iceCandidate.sdp);
                candidate.put("sdpMid", iceCandidate.sdpMid);
                candidate.put("sdpMLineIndex", iceCandidate.sdpMLineIndex);
                
                candidateData.put("candidate", candidate);
                candidateData.put("target", "agent");
                candidateData.put("target_sid", agentSid);

                send("webrtc_ice_candidate", candidateData);
            } catch (Exception e) {
                show("Error sending ICE candidate: " + e.getMessage());
            }
        }

        @Override
        public void onIceCandidatesRemoved(IceCandidate[] iceCandidates) {
            // Handle removed candidates if needed
        }

        @Override
        public void onSignalingChange(PeerConnection.SignalingState signalingState) {
            // Handle signaling state changes
        }

        @Override
        public void onIceConnectionChange(PeerConnection.IceConnectionState iceConnectionState) {
            runOnUiThread(() -> {
                if (iceConnectionState == PeerConnection.IceConnectionState.CONNECTED) {
                    show("Remote connection established");
                } else if (iceConnectionState == PeerConnection.IceConnectionState.DISCONNECTED ||
                        iceConnectionState == PeerConnection.IceConnectionState.FAILED) {
                    show("Remote connection lost");
                }
            });
        }

        @Override
        public void onIceConnectionReceivingChange(boolean b) {
            // Handle receiving state change
        }

        @Override
        public void onIceGatheringChange(PeerConnection.IceGatheringState iceGatheringState) {
            // Handle ICE gathering state
        }

        @Override
        public void onAddStream(MediaStream mediaStream) {
            runOnUiThread(() -> {
                // Handle remote video stream
                if (!mediaStream.videoTracks.isEmpty()) {
                    remoteVideoTrack = mediaStream.videoTracks.get(0);
                    remoteVideoTrack.addSink(remoteView);
                    
                    // Get video dimensions
                    remoteVideoTrack.setEnabled(true);
                    show("Video stream received");
                }

                // Handle remote audio stream
                if (!mediaStream.audioTracks.isEmpty()) {
                    remoteAudioTrack = mediaStream.audioTracks.get(0);
                    remoteAudioTrack.setEnabled(true);
                    show("Audio stream received");
                }
            });
        }

        @Override
        public void onRemoveStream(MediaStream mediaStream) {
            runOnUiThread(() -> {
                // Remove video track
                if (remoteVideoTrack != null) {
                    remoteVideoTrack.removeSink(remoteView);
                    remoteVideoTrack = null;
                }

                // Remove audio track
                if (remoteAudioTrack != null) {
                    remoteAudioTrack.setEnabled(false);
                    remoteAudioTrack = null;
                }

                show("Remote stream removed");
            });
        }

        @Override
        public void onDataChannel(DataChannel dataChannel) {
            // Handle data channel if needed for clipboard, etc.
        }

        @Override
        public void onRenegotiationNeeded() {
            // Handle renegotiation
        }

        @Override
        public void onAddTrack(RtpReceiver rtpReceiver, MediaStream[] mediaStreams) {
            // Handle individual track additions
            for (MediaStream stream : mediaStreams) {
                onAddStream(stream);
            }
        }
    }

    private class SdpObserver implements org.webrtc.SdpObserver {
        @Override
        public void onCreateSuccess(SessionDescription sessionDescription) {
            peerConnection.setLocalDescription(new SdpObserver() {
                @Override
                public void onSetSuccess() {
                    // Send offer to agent
                    try {
                        JSONObject offerData = new JSONObject();
                        offerData.put("token", new TokenStore(RemoteDesktopActivity.this).access());
                        offerData.put("device_id", deviceId);
                        
                        JSONObject offer = new JSONObject();
                        offer.put("type", sessionDescription.type.canonicalForm());
                        offer.put("sdp", sessionDescription.description);
                        
                        offerData.put("offer", offer);
                        offerData.put("controller_sid", socket.id());

                        send("webrtc_offer", offerData);
                    } catch (Exception e) {
                        show("Error sending offer: " + e.getMessage());
                    }
                }

                @Override
                public void onCreateSuccess(SessionDescription sdp) {}

                @Override
                public void onSetFailure(String error) {
                    show("Failed to set local description: " + error);
                }

                @Override
                public void onCreateFailure(String error) {
                    show("Failed to set local description: " + error);
                }
            }, sessionDescription);
        }

        @Override
        public void onSetSuccess() {
            // Handle answer from agent
        }

        @Override
        public void onCreateFailure(String error) {
            show("Failed to create offer: " + error);
        }

        @Override
        public void onSetFailure(String error) {
            show("Failed to set remote description: " + error);
        }
    }

    private void connectSocket() {
        try {
            IO.Options options = new IO.Options();
            options.reconnection = true;
            options.reconnectionAttempts = Integer.MAX_VALUE;
            options.reconnectionDelay = 1000;
            options.reconnectionDelayMax = 6000;
            options.transports = new String[]{"websocket", "polling"};
            String token = new TokenStore(this).access();
            if (token != null) {
                options.query = "token=" + URLEncoder.encode(token, StandardCharsets.UTF_8.name());
            }

            socket = IO.socket(new SettingsStore(this).serverUrl(), options);
            socket.on(Socket.EVENT_CONNECT, args -> joinController());
            socket.on("join_accepted", args -> handleJoinAccepted(args[0]));
            
            // WebRTC signaling handlers
            socket.on("webrtc_answer", args -> handleWebRTCAnswer(args[0]));
            socket.on("webrtc_ice_candidate", args -> handleIceCandidate(args[0]));
            
            // Handle controller disconnected
            socket.on("controller_disconnected", args -> show("Controller disconnected"));
            
            socket.on("agent_event", args -> handleAgentEvent(args.length > 0 ? args[0] : null));
            socket.on("error", args -> show(args.length > 0 ? args[0].toString() : "Remote session error"));
            
            socket.connect();
        } catch (Exception e) {
            show(e.getMessage());
        }
    }

    private void joinController() {
        try {
            JSONObject payload = new JSONObject();
            payload.put("token", new TokenStore(this).access());
            payload.put("device_id", deviceId);
            socket.emit("controller_join", payload);
        } catch (Exception e) {
            show(e.getMessage());
        }
    }

    private void handleJoinAccepted(Object data) {
        runOnUiThread(() -> {
            try {
                JSONObject response = (JSONObject) data;
                if (response.optString("status").equals("success")) {
                    agentSid = response.optString("agent_sid");
                    show("Connected to remote device");
                    startWebRTC();
                }
            } catch (Exception e) {
                show("Error starting session: " + e.getMessage());
            }
        });
    }

    private void handleWebRTCAnswer(Object data) {
        try {
            JSONObject answerData = (JSONObject) data;
            JSONObject answer = answerData.getJSONObject("answer");
            
            SessionDescription sdp = new SessionDescription(
                    SessionDescription.Type.fromCanonicalForm(answer.getString("type")),
                    answer.getString("sdp")
            );
            
            if (peerConnection != null) {
                peerConnection.setRemoteDescription(new SdpObserver() {
                    @Override
                    public void onSetSuccess() {
                        show("WebRTC connection established");
                    }

                    @Override
                    public void onSetFailure(String error) {
                        show("Failed to set remote description: " + error);
                    }

                    @Override
                    public void onCreateSuccess(SessionDescription sdp) {}

                    @Override
                    public void onCreateFailure(String error) {}
                }, sdp);
            }
        } catch (Exception e) {
            show("Error handling answer: " + e.getMessage());
        }
    }

    private void handleIceCandidate(Object data) {
        try {
            JSONObject candidateData = (JSONObject) data;
            JSONObject candidate = candidateData.getJSONObject("candidate");
            
            IceCandidate iceCandidate = new IceCandidate(
                    candidate.getString("sdpMid"),
                    candidate.getInt("sdpMLineIndex"),
                    candidate.getString("candidate")
            );
            
            if (peerConnection != null) {
                peerConnection.addIceCandidate(iceCandidate);
            }
        } catch (Exception e) {
            show("Error adding ICE candidate: " + e.getMessage());
        }
    }

    private boolean handleScreenTouch(View view, MotionEvent event) {
        int[] point = mapTouchToRemote(event.getX(), event.getY());
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = event.getX();
                downY = event.getY();
                downAtMs = System.currentTimeMillis();
                sendMouseMove(point[0], point[1]);
                return true;
            case MotionEvent.ACTION_MOVE:
                long now = System.currentTimeMillis();
                if (now - lastMoveAtMs >= MOVE_THROTTLE_MS) {
                    sendMouseMove(point[0], point[1]);
                    lastMoveAtMs = now;
                }
                return true;
            case MotionEvent.ACTION_UP:
                sendMouseMove(point[0], point[1]);
                long pressMs = System.currentTimeMillis() - downAtMs;
                float deltaX = Math.abs(event.getX() - downX);
                float deltaY = Math.abs(event.getY() - downY);
                if (pressMs >= LONG_PRESS_MS && deltaX < 22 && deltaY < 22) {
                    sendMouseAction("right_click");
                } else if (deltaX < 28 && deltaY < 28) {
                    sendMouseAction("left_click");
                }
                return true;
            default:
                return true;
        }
    }

    private int[] mapTouchToRemote(float touchX, float touchY) {
        float viewWidth = Math.max(1, remoteView.getWidth());
        float viewHeight = Math.max(1, remoteView.getHeight());
        if (remoteWidth <= 1 || remoteHeight <= 1) {
            remoteWidth = Math.max(1, remoteView.getWidth());
            remoteHeight = Math.max(1, remoteView.getHeight());
        }
        float scale = Math.min(viewWidth / remoteWidth, viewHeight / remoteHeight);
        float shownWidth = remoteWidth * scale;
        float shownHeight = remoteHeight * scale;
        float offsetX = (viewWidth - shownWidth) / 2f;
        float offsetY = (viewHeight - shownHeight) / 2f;
        float normalizedX = clamp((touchX - offsetX) / shownWidth, 0f, 1f);
        float normalizedY = clamp((touchY - offsetY) / shownHeight, 0f, 1f);
        return new int[]{
                Math.round(normalizedX * (remoteWidth - 1)),
                Math.round(normalizedY * (remoteHeight - 1))
        };
    }

    private float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }

    private JSONObject command(String type) {
        JSONObject object = new JSONObject();
        try {
            object.put("token", new TokenStore(this).access());
            object.put("session_id", sessionId);
            object.put("type", type);
            object.put("device_id", deviceId);
        } catch (Exception ignored) {
        }
        return object;
    }

    private void send(String event, JSONObject payload) {
        if (socket != null && socket.connected()) {
            socket.emit(event, payload);
        }
    }

    private void showKeyboardDialog() {
        EditText input = new EditText(this);
        input.setSingleLine(false);
        input.setMinLines(2);
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Keyboard")
                .setView(input)
                .setPositiveButton("Send", (d, which) -> sendKeyboardText(input.getText().toString()))
                .setNegativeButton("Cancel", null)
                .create();
        dialog.setOnShowListener(d -> {
            input.requestFocus();
            dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
            InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            if (imm != null) {
                imm.showSoftInput(input, InputMethodManager.SHOW_IMPLICIT);
            }
        });
        dialog.show();
    }

    private void sendMouseMove(int x, int y) {
        JSONObject payload = command("mouse");
        try {
            payload.put("action", "move");
            payload.put("x", x);
            payload.put("y", y);
            send("remote_command", payload);
        } catch (Exception e) {
            show(e.getMessage());
        }
    }

    private void sendMouseAction(String action) {
        JSONObject payload = command("mouse");
        try {
            payload.put("action", action);
            send("remote_command", payload);
        } catch (Exception e) {
            show(e.getMessage());
        }
    }

    private void sendKeyboardText(String text) {
        if (text == null || text.isEmpty()) {
            return;
        }
        JSONObject payload = command("keyboard");
        try {
            payload.put("action", "type");
            payload.put("text", text);
            send("remote_command", payload);
        } catch (Exception e) {
            show(e.getMessage());
        }
    }

    private void handleAgentEvent(Object event) {
        if (event == null) {
            return;
        }
        String value = event.toString();
        if (value.contains("\"ok\":false") || value.contains("error")) {
            show(value);
        }
    }

    private void show(String message) {
        runOnUiThread(() -> Toast.makeText(this, message, Toast.LENGTH_SHORT).show());
    }

    @Override
    protected void onDestroy() {
        // Clean up WebRTC
        if (peerConnection != null) {
            peerConnection.close();
            peerConnection = null;
        }
        if (peerConnectionFactory != null) {
            peerConnectionFactory.dispose();
            peerConnectionFactory = null;
        }
        if (remoteView != null) {
            remoteView.release();
        }
        if (eglBase != null) {
            eglBase.release();
        }

        // Clean up Socket.IO
        if (socket != null) {
            send("remote_command", command("screen_stop"));
            socket.disconnect();
            socket.off();
        }
        super.onDestroy();
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Pause video rendering when activity is not visible
        if (remoteVideoTrack != null) {
            remoteVideoTrack.setEnabled(false);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Resume video rendering when activity becomes visible
        if (remoteVideoTrack != null) {
            remoteVideoTrack.setEnabled(true);
        }
    }
}





