package com.remotecontrol.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.remotecontrol.app.R;
import com.remotecontrol.app.api.ApiClient;
import com.remotecontrol.app.model.AuthModels;
import com.remotecontrol.app.util.TokenStore;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class LoginActivity extends AppCompatActivity {
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_login);
        if (new TokenStore(this).access() != null) {
            startActivity(new Intent(this, DeviceListActivity.class));
            finish();
        }
        EditText email = findViewById(R.id.email);
        EditText password = findViewById(R.id.password);
        Button login = findViewById(R.id.loginButton);
        Button register = findViewById(R.id.registerButton);
        login.setOnClickListener(v -> ApiClient.create(this).login(new AuthModels.LoginRequest(email.getText().toString(), password.getText().toString())).enqueue(new AuthCallback()));
        register.setOnClickListener(v -> startActivity(new Intent(this, RegisterActivity.class)));
    }

    private class AuthCallback implements Callback<AuthModels.AuthResponse> {
        public void onResponse(Call<AuthModels.AuthResponse> call, Response<AuthModels.AuthResponse> response) {
            if (response.isSuccessful() && response.body() != null) {
                new TokenStore(LoginActivity.this).save(response.body().access_token, response.body().refresh_token);
                startActivity(new Intent(LoginActivity.this, DeviceListActivity.class));
                finish();
            } else {
                Toast.makeText(LoginActivity.this, "Login failed", Toast.LENGTH_LONG).show();
            }
        }
        public void onFailure(Call<AuthModels.AuthResponse> call, Throwable t) {
            Toast.makeText(LoginActivity.this, t.getMessage(), Toast.LENGTH_LONG).show();
        }
    }
}
