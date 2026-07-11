package com.remotecontrol.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Switch;
import androidx.appcompat.app.AppCompatActivity;
import com.remotecontrol.app.R;
import com.remotecontrol.app.util.SettingsStore;
import com.remotecontrol.app.util.TokenStore;

public class SettingsActivity extends AppCompatActivity {
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_settings);
        SettingsStore settings = new SettingsStore(this);
        EditText server = findViewById(R.id.serverUrl);
        Switch dark = findViewById(R.id.darkMode);
        Button save = findViewById(R.id.saveButton);
        Button logout = findViewById(R.id.logoutButton);
        server.setText(settings.serverUrl());
        dark.setChecked(settings.darkMode());
        save.setOnClickListener(v -> {
            settings.setServerUrl(server.getText().toString());
            settings.setDarkMode(dark.isChecked());
            finish();
        });
        logout.setOnClickListener(v -> {
            new TokenStore(this).clear();
            startActivity(new Intent(this, LoginActivity.class));
            finish();
        });
    }
}
