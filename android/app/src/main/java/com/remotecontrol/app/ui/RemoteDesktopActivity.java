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
import io.socket.client.IO;
import io.socket.client.Socket;
import org.json.JSONObject;

public class RemoteDesktopActivity extends AppCompatActivity {
    private static final long LONG_PRESS_MS = 520;
    private static final long MOVE_THROTTLE_MS = 45;

    private Socket socket;
    private String sessionId;
    private ImageView screen;
    private int remoteWidth = 1;
    private int remoteHeight = 1;
    private float downX;
    private float downY;
    private long downAtMs;
    private long lastMoveAtMs;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        setContentView(R.layout.activity_remote_desktop);

        sessionId = getIntent().getStringExtra("session_id");
        screen = findViewById(R.id.screenView);
        Button keyboard = findViewById(R.id.keyboardButton);
        keyboard.setOnClickListener(v -> showKeyboardDialog());
        screen.setOnTouchListener(this::handleScreenTouch);
        connectSocket();
    }

    private void connectSocket() {
        try {
            IO.Options options = new IO.Options();
            options.reconnection = true;
            options.reconnectionAttempts = Integer.MAX_VALUE;
            options.reconnectionDelay = 1000;
            options.reconnectionDelayMax = 6000;
            options.transports = new String[]{"websocket", "polling"};

            socket = IO.socket(new SettingsStore(this).serverUrl(), options);
            socket.on(Socket.EVENT_CONNECT, args -> joinController());
            socket.on("controller_joined", args -> send("remote_command", command("screen_start")));
            socket.on("agent_frame", args -> runOnUiThread(() -> renderFrame((JSONObject) args[0])));
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
            payload.put("session_id", sessionId);
            socket.emit("controller_join", payload);
        } catch (Exception e) {
            show(e.getMessage());
        }
    }

    private void renderFrame(JSONObject frame) {
        try {
            remoteWidth = Math.max(1, frame.optInt("width", frame.optInt("image_width", remoteWidth)));
            remoteHeight = Math.max(1, frame.optInt("height", frame.optInt("image_height", remoteHeight)));
            byte[] bytes = Base64.decode(frame.getString("image"), Base64.DEFAULT);
            Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
            screen.setImageBitmap(bitmap);
        } catch (Exception e) {
            show(e.getMessage());
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
        float viewWidth = Math.max(1, screen.getWidth());
        float viewHeight = Math.max(1, screen.getHeight());
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
            object.put("session_id", sessionId);
            object.put("type", type);
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
        if (socket != null) {
            send("remote_command", command("screen_stop"));
            socket.disconnect();
            socket.off();
        }
        super.onDestroy();
    }
}
