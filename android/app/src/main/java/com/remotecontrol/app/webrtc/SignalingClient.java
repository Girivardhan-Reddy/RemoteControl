package com.remotecontrol.app.webrtc;

import android.content.Context;

import com.remotecontrol.app.util.SettingsStore;
import com.remotecontrol.app.util.TokenStore;

import org.json.JSONObject;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

import io.socket.client.IO;
import io.socket.client.Socket;

public class SignalingClient {
    private final Context context;
    private Socket socket;

    public SignalingClient(Context context) {
        this.context = context.getApplicationContext();
    }

    public Socket connect() throws Exception {
        IO.Options options = new IO.Options();
        options.reconnection = true;
        options.reconnectionAttempts = Integer.MAX_VALUE;
        options.reconnectionDelay = 1000;
        options.reconnectionDelayMax = 8000;
        options.transports = new String[]{"websocket", "polling"};
        String token = new TokenStore(context).access();
        if (token != null) {
            options.query = "token=" + URLEncoder.encode(token, StandardCharsets.UTF_8.name());
        }
        socket = IO.socket(new SettingsStore(context).serverUrl(), options);
        socket.connect();
        return socket;
    }

    public JSONObject authenticatedPayload() {
        JSONObject payload = new JSONObject();
        try {
            payload.put("token", new TokenStore(context).access());
        } catch (Exception ignored) {
        }
        return payload;
    }

    public void emit(String event, JSONObject payload) {
        if (socket != null && socket.connected()) {
            socket.emit(event, payload);
        }
    }

    public void close() {
        if (socket != null) {
            socket.disconnect();
            socket.off();
            socket = null;
        }
    }
}
