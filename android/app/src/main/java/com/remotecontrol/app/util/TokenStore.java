package com.remotecontrol.app.util;

import android.content.Context;
import android.content.SharedPreferences;

public class TokenStore {
    private final SharedPreferences prefs;

    public TokenStore(Context context) {
        prefs = context.getSharedPreferences("remote_control_auth", Context.MODE_PRIVATE);
    }

    public void save(String access, String refresh) {
        prefs.edit().putString("access", access).putString("refresh", refresh).apply();
    }

    public String access() { return prefs.getString("access", null); }
    public String refresh() { return prefs.getString("refresh", null); }
    public void clear() { prefs.edit().clear().apply(); }
}
