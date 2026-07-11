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

public class RegisterActivity extends AppCompatActivity {
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_register);
        EditText name = findViewById(R.id.name);
        EditText email = findViewById(R.id.email);
        EditText password = findViewById(R.id.password);
        Button register = findViewById(R.id.registerButton);
        register.setOnClickListener(v -> ApiClient.create(this).register(new AuthModels.RegisterRequest(name.getText().toString(), email.getText().toString(), password.getText().toString())).enqueue(new Callback<AuthModels.AuthResponse>() {
            public void onResponse(Call<AuthModels.AuthResponse> call, Response<AuthModels.AuthResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    new TokenStore(RegisterActivity.this).save(response.body().access_token, response.body().refresh_token);
                    startActivity(new Intent(RegisterActivity.this, DeviceListActivity.class));
                    finish();
                } else {
                    Toast.makeText(RegisterActivity.this, "Registration failed", Toast.LENGTH_LONG).show();
                }
            }
            public void onFailure(Call<AuthModels.AuthResponse> call, Throwable t) {
                Toast.makeText(RegisterActivity.this, t.getMessage(), Toast.LENGTH_LONG).show();
            }
        }));
    }
}
