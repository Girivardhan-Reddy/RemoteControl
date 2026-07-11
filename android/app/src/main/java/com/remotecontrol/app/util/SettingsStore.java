package com.remotecontrol.app.util;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.appcompat.app.AppCompatDelegate;
import com.remotecontrol.app.R;

public class SettingsStore {
    private final Context context;
    private final SharedPreferences prefs;

    public SettingsStore(Context context) {
        this.context = context;
        this.prefs = context.getSharedPreferences("remote_control_settings", Context.MODE_PRIVATE);
    }

    public String serverUrl() {
        return prefs.getString("server_url", context.getString(R.string.server_url));
    }

    public void setServerUrl(String url) {
        prefs.edit().putString("server_url", url).apply();
    }

    public boolean darkMode() {
        return prefs.getBoolean("dark_mode", false);
    }

    public void setDarkMode(boolean enabled) {
        prefs.edit().putBoolean("dark_mode", enabled).apply();
        AppCompatDelegate.setDefaultNightMode(enabled ? AppCompatDelegate.MODE_NIGHT_YES : AppCompatDelegate.MODE_NIGHT_NO);
    }
}
