package com.remotecontrol.app.webrtc;

import android.content.Context;
import android.util.Log;
import android.view.View;

import org.webrtc.EglBase;
import org.webrtc.RendererCommon;
import org.webrtc.SurfaceViewRenderer;

/**
 * Manages video rendering for remote desktop display.
 * Supports multiple resolutions (720p, 1080p, 1440p) with
 * hardware-accelerated rendering for optimal performance.
 */
public class VideoRenderer {
    private static final String TAG = "VideoRenderer";

    // Supported video resolutions
    public enum Resolution {
        HD_720(1280, 720),
        FULL_HD_1080(1920, 1080),
        QHD_1440(2560, 1440);

        final int width;
        final int height;

        Resolution(int width, int height) {
            this.width = width;
            this.height = height;
        }
    }

    private final Context context;
    private final EglBase eglBase;
    private SurfaceViewRenderer surfaceViewRenderer;
    private Resolution currentResolution = Resolution.FULL_HD_1080;

    // Rendering optimization flags
    private boolean hardwareAccelerationEnabled = true;
    private boolean frameDroppingEnabled = true;

    /**
     * Constructor for VideoRenderer
     * @param context Android application context
     * @param eglBase EGL base context for OpenGL rendering
     */
    public VideoRenderer(Context context, EglBase eglBase) {
        this.context = context;
        this.eglBase = eglBase;
    }

    /**
     * Initialize the SurfaceViewRenderer for video display
     * @param surfaceViewRenderer Pre-configured SurfaceViewRenderer from layout
     * @return The initialized SurfaceViewRenderer
     */
    public SurfaceViewRenderer initialize(SurfaceViewRenderer surfaceViewRenderer) {
        this.surfaceViewRenderer = surfaceViewRenderer;
        Log.d(TAG, "Initializing video renderer");

        // Initialize renderer with EGL context
        surfaceViewRenderer.init(eglBase.getEglBaseContext(), null);

        // Configure for optimal remote desktop display
        configureRenderer(currentResolution);

        // Enable hardware acceleration for better performance
        surfaceViewRenderer.setEnableHardwareScaler(hardwareAccelerationEnabled);

        // Set z-order to be on top of other views
        surfaceViewRenderer.setZOrderOnTop(true);
        surfaceViewRenderer.setZOrderMediaOverlay(true);

        Log.d(TAG, "Video renderer initialized with resolution: " +
                currentResolution.width + "x" + currentResolution.height);
        return surfaceViewRenderer;
    }

    /**
     * Configure renderer for specific resolution and performance settings
     * @param resolution Desired video resolution
     */
    private void configureRenderer(Resolution resolution) {
        if (surfaceViewRenderer == null) {
            Log.w(TAG, "SurfaceViewRenderer not initialized");
            return;
        }

        // Set scaling type for proper aspect ratio handling
        surfaceViewRenderer.setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT);

        // Enable mirroring if needed (typically false for remote desktop)
        surfaceViewRenderer.setMirror(false);

        // Configure frame dropping for smooth playback
        if (frameDroppingEnabled) {
            // Allow dropping frames to maintain low latency
            surfaceViewRenderer.setFpsReduction(0.2f); // Allow up to 20% FPS reduction
        }

        // Set initial frame size
        surfaceViewRenderer.setSizeHint(resolution.width, resolution.height);

        currentResolution = resolution;
        Log.d(TAG, "Renderer configured: " + resolution.width + "x" + resolution.height);
    }

    /**
     * Switch video resolution dynamically
     * @param resolution New resolution to use
     */
    public void setResolution(Resolution resolution) {
        if (resolution != currentResolution) {
            Log.d(TAG, "Switching resolution from " +
                    currentResolution.width + "x" + currentResolution.height +
                    " to " + resolution.width + "x" + resolution.height);
            configureRenderer(resolution);
        }
    }

    /**
     * Get current video resolution
     */
    public Resolution getCurrentResolution() {
        return currentResolution;
    }

    /**
     * Enable or disable hardware acceleration
     * @param enabled True to enable hardware acceleration
     */
    public void setHardwareAcceleration(boolean enabled) {
        this.hardwareAccelerationEnabled = enabled;
        if (surfaceViewRenderer != null) {
            surfaceViewRenderer.setEnableHardwareScaler(enabled);
        }
        Log.d(TAG, "Hardware acceleration " + (enabled ? "enabled" : "disabled"));
    }

    /**
     * Enable or disable frame dropping for smoother playback
     * @param enabled True to allow frame dropping
     */
    public void setFrameDropping(boolean enabled) {
        this.frameDroppingEnabled = enabled;
        Log.d(TAG, "Frame dropping " + (enabled ? "enabled" : "disabled"));
    }

    /**
     * Clear the video display
     */
    public void clearFrame() {
        if (surfaceViewRenderer != null) {
            surfaceViewRenderer.clearImage();
        }
    }

    /**
     * Get the SurfaceViewRenderer for attaching video tracks
     * @return The SurfaceViewRenderer instance
     */
    public SurfaceViewRenderer getSurfaceViewRenderer() {
        return surfaceViewRenderer;
    }

    /**
     * Get the View for layout management
     * @return The SurfaceViewRenderer as a View
     */
    public View getView() {
        return surfaceViewRenderer;
    }

    /**
     * Update renderer layout when surface size changes
     * @param width New width in pixels
     * @param height New height in pixels
     */
    public void onLayoutChange(int width, int height) {
        if (surfaceViewRenderer != null) {
            surfaceViewRenderer.setSizeHint(width, height);
            Log.d(TAG, "Layout changed: " + width + "x" + height);
        }
    }

    /**
     * Pause video rendering when activity is not visible
     */
    public void pause() {
        if (surfaceViewRenderer != null) {
            surfaceViewRenderer.setVisibility(View.INVISIBLE);
            Log.d(TAG, "Video renderer paused");
        }
    }

    /**
     * Resume video rendering when activity becomes visible
     */
    public void resume() {
        if (surfaceViewRenderer != null) {
            surfaceViewRenderer.setVisibility(View.VISIBLE);
            Log.d(TAG, "Video renderer resumed");
        }
    }

    /**
     * Release renderer resources
     */
    public void release() {
        Log.d(TAG, "Releasing video renderer");
        if (surfaceViewRenderer != null) {
            surfaceViewRenderer.release();
            surfaceViewRenderer = null;
        }
    }

    /**
     * Get renderer statistics for debugging
     * @return String with renderer information
     */
    public String getStats() {
        if (surfaceViewRenderer == null) {
            return "Renderer not initialized";
        }

        return String.format(
                "Renderer Stats:\n" +
                        "  Resolution: %dx%d\n" +
                        "  Hardware Acceleration: %b\n" +
                        "  Frame Dropping: %b\n" +
                        "  Visibility: %s",
                currentResolution.width,
                currentResolution.height,
                hardwareAccelerationEnabled,
                frameDroppingEnabled,
                surfaceViewRenderer.getVisibility() == View.VISIBLE ? "Visible" : "Hidden"
        );
    }

    /**
     * Optimize rendering for low latency (gaming mode)
     * Reduces buffering and prioritizes fast frame delivery
     */
    public void enableLowLatencyMode() {
        if (surfaceViewRenderer != null) {
            // Configure for minimum latency
            surfaceViewRenderer.setFpsReduction(0.0f); // No FPS reduction
            surfaceViewRenderer.setEnableHardwareScaler(true);
            setFrameDropping(true); // Drop old frames to stay current

            // Set scaling to fill for better perceived performance
            surfaceViewRenderer.setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FILL);

            Log.d(TAG, "Low latency mode enabled");
        }
    }

    /**
     * Optimize rendering for smooth scrolling (desktop mode)
     * Prioritizes smooth frame delivery over minimal latency
     */
    public void enableSmoothMode() {
        if (surfaceViewRenderer != null) {
            // Configure for smooth playback
            surfaceViewRenderer.setFpsReduction(0.1f); // Slight FPS reduction for smoothness
            surfaceViewRenderer.setEnableHardwareScaler(true);
            setFrameDropping(false); // Don't drop frames for smooth scrolling

            // Set scaling for best quality
            surfaceViewRenderer.setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT);

            Log.d(TAG, "Smooth mode enabled");
        }
    }
}