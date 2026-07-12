package com.remotecontrol.app.webrtc;

import android.content.Context;
import android.util.Log;

import org.webrtc.*;
import org.json.JSONObject;
import org.json.JSONArray;

import java.util.ArrayList;
import java.util.List;

/**
 * Manages WebRTC peer connection, media streaming, and signaling.
 * Handles initialization of PeerConnectionFactory, creation of peer connections,
 * and processing of SDP offers/answers and ICE candidates.
 */
public class WebRTCManager {
    private static final String TAG = "WebRTCManager";

    // STUN/TURN server configuration for NAT traversal
    private static final List<PeerConnection.IceServer> ICE_SERVERS = new ArrayList<>();

    static {
        // Google's public STUN server for basic NAT traversal
        ICE_SERVERS.add(PeerConnection.IceServer.builder("stun:stun.l.google.com:19302")
                .createIceServer());

        // Add your own TURN server here for better connectivity in restricted networks
        // ICE_SERVERS.add(PeerConnection.IceServer.builder("turn:your-turn-server.com:3478")
        //     .setUsername("username")
        //     .setPassword("password")
        //     .createIceServer());
    }

    // Core WebRTC components
    private final Context context;
    private final SignalingClient signalingClient;
    private PeerConnectionFactory peerConnectionFactory;
    private PeerConnection peerConnection;
    private EglBase eglBase;

    // Video renderer for remote desktop display
    private VideoRenderer videoRenderer;

    // Media tracks
    private VideoTrack remoteVideoTrack;
    private AudioTrack remoteAudioTrack;

    // Connection state tracking
    private boolean isConnected = false;
    private String deviceId;

    // WebRTC event callbacks
    private WebRTCCallback callback;

    /**
     * Interface for WebRTC events callbacks to the main activity
     */
    public interface WebRTCCallback {
        void onRemoteStreamAdded(MediaStream stream);
        void onRemoteStreamRemoved(MediaStream stream);
        void onConnectionEstablished();
        void onConnectionFailed(String error);
        void onConnectionClosed();
    }

    /**
     * Constructor for WebRTCManager
     * @param context Android application context
     * @param signalingClient Signaling client for WebRTC signaling
     */
    public WebRTCManager(Context context, SignalingClient signalingClient) {
        this.context = context;
        this.signalingClient = signalingClient;
        this.signalingClient.setWebRTCManager(this);
    }

    /**
     * Set callback for WebRTC events
     */
    public void setCallback(WebRTCCallback callback) {
        this.callback = callback;
    }

    /**
     * Set video renderer for displaying remote desktop
     */
    public void setVideoRenderer(VideoRenderer renderer) {
        this.videoRenderer = renderer;
    }

    /**
     * Initialize WebRTC components including EGL context and PeerConnectionFactory
     */
    public void initialize() {
        Log.d(TAG, "Initializing WebRTC components");

        // Initialize EGL context for hardware-accelerated rendering
        eglBase = EglBase.create();

        // Initialize PeerConnectionFactory with custom options
        PeerConnectionFactory.InitializationOptions initializationOptions =
                PeerConnectionFactory.InitializationOptions.builder(context)
                        .setFieldTrials("WebRTC-H264HighProfile/Enabled/" +
                                "WebRTC-AdjustOpusBitrate/Enabled/" +
                                "WebRTC-SupportVP9/Enabled/")
                        .createInitializationOptions();
        PeerConnectionFactory.initialize(initializationOptions);

        // Configure factory options for optimal performance
        PeerConnectionFactory.Options factoryOptions = new PeerConnectionFactory.Options();
        factoryOptions.disableEncryption = false;
        factoryOptions.disableNetworkMonitor = false;

        peerConnectionFactory = PeerConnectionFactory.builder()
                .setOptions(factoryOptions)
                .setVideoDecoderFactory(new DefaultVideoDecoderFactory(eglBase.getEglBaseContext()))
                .setVideoEncoderFactory(new DefaultVideoEncoderFactory(
                        eglBase.getEglBaseContext(), true, true))
                .createPeerConnectionFactory();

        Log.d(TAG, "WebRTC components initialized successfully");
    }

    /**
     * Start WebRTC connection to remote device
     * @param deviceId ID of the remote device to connect to
     */
    public void startConnection(String deviceId) {
        this.deviceId = deviceId;
        Log.d(TAG, "Starting WebRTC connection to device: " + deviceId);

        createPeerConnection();
        createOffer();
    }

    /**
     * Create RTCPeerConnection with optimal configuration for remote desktop
     */
    private void createPeerConnection() {
        if (peerConnectionFactory == null) {
            Log.e(TAG, "PeerConnectionFactory not initialized");
            return;
        }

        // Configure peer connection for low-latency remote desktop
        PeerConnection.RTCConfiguration rtcConfig = new PeerConnection.RTCConfiguration(ICE_SERVERS);

        // Optimize for low latency
        rtcConfig.iceTransportsType = PeerConnection.IceTransportsType.ALL;
        rtcConfig.tcpCandidatePolicy = PeerConnection.TcpCandidatePolicy.ENABLED;
        rtcConfig.bundlePolicy = PeerConnection.BundlePolicy.MAXBUNDLE;
        rtcConfig.rtcpMuxPolicy = PeerConnection.RtcpMuxPolicy.REQUIRE;
        rtcConfig.continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_CONTINUALLY;
        rtcConfig.keyType = PeerConnection.KeyType.ECDSA;

        // Optimize for video streaming
        rtcConfig.sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN;
        rtcConfig.enableDtlsSrtp = true;

        // Create peer connection with observer
        peerConnection = peerConnectionFactory.createPeerConnection(rtcConfig,
                new PeerConnectionObserver());

        Log.d(TAG, "Peer connection created with optimized configuration");
    }

    /**
     * Create and send SDP offer to remote device
     */
    private void createOffer() {
        if (peerConnection == null) {
            Log.e(TAG, "Peer connection not created");
            return;
        }

        // Create offer with constraints for video and audio
        MediaConstraints constraints = new MediaConstraints();
        constraints.mandatory.add(new MediaConstraints.KeyValuePair("OfferToReceiveVideo", "true"));
        constraints.mandatory.add(new MediaConstraints.KeyValuePair("OfferToReceiveAudio", "true"));

        peerConnection.createOffer(new SdpObserver() {
            @Override
            public void onCreateSuccess(SessionDescription sessionDescription) {
                Log.d(TAG, "SDP offer created successfully");
                setLocalDescription(sessionDescription);
            }

            @Override
            public void onSetSuccess() {
                // Handle when remote description is set
            }

            @Override
            public void onCreateFailure(String error) {
                Log.e(TAG, "Failed to create SDP offer: " + error);
                if (callback != null) {
                    callback.onConnectionFailed("Failed to create offer: " + error);
                }
            }

            @Override
            public void onSetFailure(String error) {
                Log.e(TAG, "Failed to set SDP: " + error);
            }
        }, constraints);
    }

    /**
     * Set local description and send offer via signaling
     */
    private void setLocalDescription(SessionDescription sdp) {
        if (peerConnection == null) return;

        peerConnection.setLocalDescription(new SdpObserver() {
            @Override
            public void onCreateSuccess(SessionDescription sdp) {}

            @Override
            public void onSetSuccess() {
                Log.d(TAG, "Local description set successfully");
                // Send offer via signaling client
                signalingClient.sendOffer(deviceId, peerConnection.getLocalDescription());
            }

            @Override
            public void onCreateFailure(String error) {
                Log.e(TAG, "Failed to create local description: " + error);
            }

            @Override
            public void onSetFailure(String error) {
                Log.e(TAG, "Failed to set local description: " + error);
                if (callback != null) {
                    callback.onConnectionFailed("Failed to set local description: " + error);
                }
            }
        }, sdp);
    }

    /**
     * Handle incoming SDP answer from remote device
     * @param sdp Session description received from signaling
     */
    public void handleAnswer(SessionDescription sdp) {
        if (peerConnection == null) {
            Log.e(TAG, "Peer connection not available for answer");
            return;
        }

        Log.d(TAG, "Handling SDP answer from remote device");

        peerConnection.setRemoteDescription(new SdpObserver() {
            @Override
            public void onCreateSuccess(SessionDescription sdp) {}

            @Override
            public void onSetSuccess() {
                Log.d(TAG, "Remote description set successfully from answer");
                isConnected = true;
                if (callback != null) {
                    callback.onConnectionEstablished();
                }
            }

            @Override
            public void onCreateFailure(String error) {
                Log.e(TAG, "Failed to create remote description: " + error);
            }

            @Override
            public void onSetFailure(String error) {
                Log.e(TAG, "Failed to set remote description: " + error);
                if (callback != null) {
                    callback.onConnectionFailed("Failed to set remote description: " + error);
                }
            }
        }, sdp);
    }

    /**
     * Add ICE candidate received from signaling
     * @param iceCandidate ICE candidate for NAT traversal
     */
    public void addIceCandidate(IceCandidate iceCandidate) {
        if (peerConnection == null) {
            Log.e(TAG, "Peer connection not available for ICE candidate");
            return;
        }

        Log.d(TAG, "Adding ICE candidate");

        peerConnection.addIceCandidate(iceCandidate, new AddIceObserver() {
            @Override
            public void onAddSuccess() {
                Log.d(TAG, "ICE candidate added successfully");
            }

            @Override
            public void onAddFailure(String error) {
                Log.e(TAG, "Failed to add ICE candidate: " + error);
            }
        });
    }

    /**
     * Stop WebRTC connection and cleanup resources
     */
    public void stopConnection() {
        Log.d(TAG, "Stopping WebRTC connection");

        // Remove video rendering
        if (remoteVideoTrack != null && videoRenderer != null) {
            remoteVideoTrack.removeSink(videoRenderer.getSurfaceViewRenderer());
            remoteVideoTrack = null;
        }

        // Disable audio
        if (remoteAudioTrack != null) {
            remoteAudioTrack.setEnabled(false);
            remoteAudioTrack = null;
        }

        // Close peer connection
        if (peerConnection != null) {
            peerConnection.close();
            peerConnection = null;
        }

        isConnected = false;

        if (callback != null) {
            callback.onConnectionClosed();
        }
    }

    /**
     * Release all WebRTC resources
     */
    public void dispose() {
        Log.d(TAG, "Disposing WebRTC resources");
        stopConnection();

        if (peerConnectionFactory != null) {
            peerConnectionFactory.dispose();
            peerConnectionFactory = null;
        }

        if (eglBase != null) {
            eglBase.release();
            eglBase = null;
        }
    }

    /**
     * Check if WebRTC connection is established
     */
    public boolean isConnected() {
        return isConnected;
    }

    /**
     * Get the remote video track
     */
    public VideoTrack getRemoteVideoTrack() {
        return remoteVideoTrack;
    }

    /**
     * Observer for PeerConnection events
     */
    private class PeerConnectionObserver implements PeerConnection.Observer {
        @Override
        public void onIceCandidate(IceCandidate iceCandidate) {
            Log.d(TAG, "New ICE candidate generated");
            // Send ICE candidate to remote device via signaling
            signalingClient.sendIceCandidate(deviceId, iceCandidate);
        }

        @Override
        public void onIceCandidatesRemoved(IceCandidate[] iceCandidates) {
            Log.d(TAG, "ICE candidates removed");
        }

        @Override
        public void onSignalingChange(PeerConnection.SignalingState signalingState) {
            Log.d(TAG, "Signaling state changed: " + signalingState);
        }

        @Override
        public void onIceConnectionChange(PeerConnection.IceConnectionState iceConnectionState) {
            Log.d(TAG, "ICE connection state: " + iceConnectionState);

            switch (iceConnectionState) {
                case CONNECTED:
                    Log.d(TAG, "ICE connection established");
                    break;
                case DISCONNECTED:
                    Log.w(TAG, "ICE connection disconnected");
                    break;
                case FAILED:
                    Log.e(TAG, "ICE connection failed");
                    if (callback != null) {
                        callback.onConnectionFailed("ICE connection failed");
                    }
                    break;
                case CLOSED:
                    Log.d(TAG, "ICE connection closed");
                    break;
            }
        }

        @Override
        public void onIceConnectionReceivingChange(boolean receiving) {
            Log.d(TAG, "ICE receiving state: " + receiving);
        }

        @Override
        public void onIceGatheringChange(PeerConnection.IceGatheringState iceGatheringState) {
            Log.d(TAG, "ICE gathering state: " + iceGatheringState);
        }

        @Override
        public void onAddStream(MediaStream mediaStream) {
            Log.d(TAG, "Remote stream added");
            handleRemoteStream(mediaStream);
        }

        @Override
        public void onRemoveStream(MediaStream mediaStream) {
            Log.d(TAG, "Remote stream removed");
            if (callback != null) {
                callback.onRemoteStreamRemoved(mediaStream);
            }
        }

        @Override
        public void onDataChannel(DataChannel dataChannel) {
            Log.d(TAG, "Data channel created: " + dataChannel.label());
            // Could be used for clipboard, file transfer, etc.
        }

        @Override
        public void onRenegotiationNeeded() {
            Log.d(TAG, "Renegotiation needed");
        }

        @Override
        public void onAddTrack(RtpReceiver rtpReceiver, MediaStream[] mediaStreams) {
            Log.d(TAG, "Remote track added");
            for (MediaStream stream : mediaStreams) {
                handleRemoteStream(stream);
            }
        }
    }

    /**
     * Handle incoming media stream from remote device
     */
    private void handleRemoteStream(MediaStream stream) {
        // Handle video track
        if (!stream.videoTracks.isEmpty()) {
            remoteVideoTrack = stream.videoTracks.get(0);
            remoteVideoTrack.setEnabled(true);

            // Attach video to renderer
            if (videoRenderer != null) {
                remoteVideoTrack.addSink(videoRenderer.getSurfaceViewRenderer());
            }

            Log.d(TAG, "Remote video track added and attached to renderer");
        }

        // Handle audio track
        if (!stream.audioTracks.isEmpty()) {
            remoteAudioTrack = stream.audioTracks.get(0);
            remoteAudioTrack.setEnabled(true);
            Log.d(TAG, "Remote audio track added and enabled");
        }

        if (callback != null) {
            callback.onRemoteStreamAdded(stream);
        }
    }

    /**
     * Custom observer for adding ICE candidates
     */
    private static class AddIceObserver implements org.webrtc.AddIceObserver {
        @Override
        public void onAddSuccess() {
            Log.d(TAG, "ICE candidate added successfully");
        }

        @Override
        public void onAddFailure(String error) {
            Log.e(TAG, "Failed to add ICE candidate: " + error);
        }
    }
}