package com.remotecontrol.app.webrtc;

import android.content.Context;

import org.webrtc.DefaultVideoDecoderFactory;
import org.webrtc.DefaultVideoEncoderFactory;
import org.webrtc.EglBase;
import org.webrtc.MediaConstraints;
import org.webrtc.PeerConnection;
import org.webrtc.PeerConnectionFactory;
import org.webrtc.RendererCommon;
import org.webrtc.SessionDescription;
import org.webrtc.SurfaceViewRenderer;

import java.util.ArrayList;
import java.util.List;

public class WebRTCManager {
    public interface Listener {
        void onLocalOffer(SessionDescription offer);
        void onStatus(String status);
    }

    private final EglBase eglBase;
    private final PeerConnectionFactory factory;
    private PeerConnection peerConnection;
    private Listener listener;

    public WebRTCManager(Context context) {
        eglBase = EglBase.create();
        PeerConnectionFactory.initialize(
                PeerConnectionFactory.InitializationOptions.builder(context)
                        .setFieldTrials("WebRTC-H264HighProfile/Enabled/")
                        .createInitializationOptions()
        );
        factory = PeerConnectionFactory.builder()
                .setVideoDecoderFactory(new DefaultVideoDecoderFactory(eglBase.getEglBaseContext()))
                .setVideoEncoderFactory(new DefaultVideoEncoderFactory(eglBase.getEglBaseContext(), true, true))
                .createPeerConnectionFactory();
    }

    public void attachRenderer(SurfaceViewRenderer renderer) {
        renderer.init(eglBase.getEglBaseContext(), null);
        renderer.setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT);
        renderer.setEnableHardwareScaler(true);
    }

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    public PeerConnection createPeerConnection(PeerConnection.Observer observer) {
        List<PeerConnection.IceServer> iceServers = new ArrayList<>();
        iceServers.add(PeerConnection.IceServer.builder("stun:stun.l.google.com:19302").createIceServer());
        PeerConnection.RTCConfiguration config = new PeerConnection.RTCConfiguration(iceServers);
        config.bundlePolicy = PeerConnection.BundlePolicy.MAXBUNDLE;
        config.rtcpMuxPolicy = PeerConnection.RtcpMuxPolicy.REQUIRE;
        config.continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_CONTINUALLY;
        peerConnection = factory.createPeerConnection(config, observer);
        return peerConnection;
    }

    public void createOffer(org.webrtc.SdpObserver observer) {
        if (peerConnection != null) {
            peerConnection.createOffer(observer, new MediaConstraints());
        }
    }

    public void close() {
        if (peerConnection != null) {
            peerConnection.close();
            peerConnection = null;
        }
        factory.dispose();
        eglBase.release();
    }
}
