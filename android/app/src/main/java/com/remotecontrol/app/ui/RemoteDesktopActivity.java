package com.remotecontrol.app.ui;

import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.util.Base64;
import android.view.MotionEvent;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.remotecontrol.app.R;
import com.remotecontrol.app.util.SettingsStore;
import com.remotecontrol.app.util.TokenStore;
import org.json.JSONObject;
import io.socket.client.IO;
import io.socket.client.Socket;

public class RemoteDesktopActivity extends AppCompatActivity {
    private Socket socket;
    private String sessionId;
    private ImageView screen;

    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_remote_desktop);
        sessionId = getIntent().getStringExtra("session_id");
        screen = findViewById(R.id.screenView);
        Button keyboard = findViewById(R.id.keyboardButton);
        Button clipboard = findViewById(R.id.clipboardButton);
        Button files = findViewById(R.id.filesButton);
        Button power = findViewById(R.id.powerButton);
        keyboard.setOnClickListener(v -> showKeyboardDialog());
        clipboard.setOnClickListener(v -> showClipboardDialog());
        files.setOnClickListener(v -> startActivity(new Intent(this, FileManagerActivity.class).putExtra("session_id", sessionId)));
        power.setOnClickListener(v -> showPowerDialog());
        screen.setOnTouchListener((v, event) -> {
            if (event.getAction() == MotionEvent.ACTION_MOVE || event.getAction() == MotionEvent.ACTION_DOWN) {
                sendMouseMove((int) event.getX(), (int) event.getY());
            }
            if (event.getAction() == MotionEvent.ACTION_UP) sendMouseAction("left_click");
            return true;
        });
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
                    socket.emit("remote_command", command("screen_start"));
                } catch (Exception e) { show(e.getMessage()); }
            });
            socket.on("agent_frame", args -> runOnUiThread(() -> renderFrame((JSONObject) args[0])));
            socket.on("agent_event", args -> show(args[0].toString()));
            socket.connect();
        } catch (Exception e) {
            show(e.getMessage());
        }
    }

    private void renderFrame(JSONObject frame) {
        try {
            byte[] bytes = Base64.decode(frame.getString("image"), Base64.DEFAULT);
            Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
            screen.setImageBitmap(bitmap);
        } catch (Exception e) { show(e.getMessage()); }
    }

    private JSONObject command(String type) {
        JSONObject object = new JSONObject();
        try {
            object.put("session_id", sessionId);
            object.put("type", type);
        } catch (Exception ignored) {}
        return object;
    }

    private void send(String event, JSONObject payload) {
        if (socket != null && socket.connected()) socket.emit(event, payload);
    }

    private void showKeyboardDialog() {
        EditText input = new EditText(this);
        new AlertDialog.Builder(this).setTitle("Type Text").setView(input).setPositiveButton("Send", (dialog, which) -> sendKeyboardText(input.getText().toString())).setNegativeButton("Cancel", null).show();
    }

    private void showClipboardDialog() {
        EditText input = new EditText(this);
        new AlertDialog.Builder(this).setTitle("Clipboard Text").setView(input).setPositiveButton("Set", (dialog, which) -> sendClipboardSet(input.getText().toString())).setNegativeButton("Get", (dialog, which) -> send("remote_command", command("clipboard_get"))).show();
    }

    private void showPowerDialog() {
        String[] actions = {"lock", "sleep", "hibernate", "restart", "shutdown"};
        new AlertDialog.Builder(this).setTitle("Power").setItems(actions, (dialog, which) -> sendPower(actions[which])).show();
    }

    private void sendMouseMove(int x, int y) {
        JSONObject payload = command("mouse");
        try {
            payload.put("action", "move");
            payload.put("x", x);
            payload.put("y", y);
            send("remote_command", payload);
        } catch (Exception e) { show(e.getMessage()); }
    }

    private void sendMouseAction(String action) {
        JSONObject payload = command("mouse");
        try {
            payload.put("action", action);
            send("remote_command", payload);
        } catch (Exception e) { show(e.getMessage()); }
    }

    private void sendKeyboardText(String text) {
        JSONObject payload = command("keyboard");
        try {
            payload.put("action", "type");
            payload.put("text", text);
            send("remote_command", payload);
        } catch (Exception e) { show(e.getMessage()); }
    }

    private void sendClipboardSet(String text) {
        JSONObject payload = command("clipboard_set");
        try {
            payload.put("text", text);
            send("remote_command", payload);
        } catch (Exception e) { show(e.getMessage()); }
    }

    private void sendPower(String action) {
        JSONObject payload = command("power");
        try {
            payload.put("action", action);
            send("remote_command", payload);
        } catch (Exception e) { show(e.getMessage()); }
    }

    private void show(String message) {
        runOnUiThread(() -> Toast.makeText(this, message, Toast.LENGTH_SHORT).show());
    }

    protected void onDestroy() {
        if (socket != null) {
            send("remote_command", command("screen_stop"));
            socket.disconnect();
        }
        super.onDestroy();
    }
}
