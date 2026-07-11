package com.remotecontrol.app.ui;

import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import com.remotecontrol.app.R;
import com.remotecontrol.app.util.SettingsStore;
import com.remotecontrol.app.util.TokenStore;
import org.json.JSONObject;
import io.socket.client.IO;
import io.socket.client.Socket;

public class FileManagerActivity extends AppCompatActivity {
    private Socket socket;
    private String sessionId;
    private TextView output;

    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_file_manager);
        sessionId = getIntent().getStringExtra("session_id");
        EditText path = findViewById(R.id.pathInput);
        output = findViewById(R.id.fileOutput);
        Button browse = findViewById(R.id.browseButton);
        browse.setOnClickListener(v -> sendBrowse(path.getText().toString()));
        connectSocket();
    }

    private void connectSocket() {
        try {
            socket = IO.socket(new SettingsStore(this).serverUrl());
            socket.on(Socket.EVENT_CONNECT, args -> {
                try {
                    JSONObject payload = new JSONObject();
                    payload.put("token", new TokenStore(this).access());
                    payload.put("session_id", sessionId);
                    socket.emit("controller_join", payload);
                } catch (Exception e) {
                    runOnUiThread(() -> output.setText(e.getMessage()));
                }
            });
            socket.on("agent_event", args -> runOnUiThread(() -> output.setText(args[0].toString())));
            socket.connect();
        } catch (Exception e) {
            output.setText(e.getMessage());
        }
    }

    private void sendBrowse(String path) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("session_id", sessionId);
            payload.put("type", "files");
            payload.put("action", "browse");
            payload.put("path", path);
            socket.emit("remote_command", payload);
        } catch (Exception e) {
            output.setText(e.getMessage());
        }
    }

    protected void onDestroy() {
        if (socket != null) socket.disconnect();
        super.onDestroy();
    }
}
