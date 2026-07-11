package com.remotecontrol.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.widget.EditText;
import android.widget.Button;
import android.widget.Toast;
import android.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.remotecontrol.app.R;
import com.remotecontrol.app.api.ApiClient;
import com.remotecontrol.app.model.Device;
import com.remotecontrol.app.model.Session;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class DeviceListActivity extends AppCompatActivity {
    private DeviceAdapter adapter;

    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_device_list);
        RecyclerView recycler = findViewById(R.id.deviceRecycler);
        adapter = new DeviceAdapter(new DeviceAdapter.Listener() {
            public void connect(Device device) { DeviceListActivity.this.connect(device); }
            public void pair(Device device) { DeviceListActivity.this.pair(device); }
        });
        recycler.setLayoutManager(new LinearLayoutManager(this));
        recycler.setAdapter(adapter);
        Button refresh = findViewById(R.id.refreshButton);
        Button settings = findViewById(R.id.settingsButton);
        refresh.setOnClickListener(v -> loadDevices());
        settings.setOnClickListener(v -> startActivity(new Intent(this, SettingsActivity.class)));
        loadDevices();
    }

    private void loadDevices() {
        ApiClient.create(this).devices().enqueue(new Callback<Device.DeviceListResponse>() {
            public void onResponse(Call<Device.DeviceListResponse> call, Response<Device.DeviceListResponse> response) {
                if (response.isSuccessful() && response.body() != null) adapter.setDevices(response.body().devices);
                else Toast.makeText(DeviceListActivity.this, "Failed to load devices", Toast.LENGTH_LONG).show();
            }
            public void onFailure(Call<Device.DeviceListResponse> call, Throwable t) {
                Toast.makeText(DeviceListActivity.this, t.getMessage(), Toast.LENGTH_LONG).show();
            }
        });
    }

    private void connect(Device device) {
        ApiClient.create(this).createSession(new Session.CreateSessionRequest(device.id)).enqueue(new Callback<Session>() {
            public void onResponse(Call<Session> call, Response<Session> response) {
                if (response.isSuccessful() && response.body() != null) {
                    Intent intent = new Intent(DeviceListActivity.this, RemoteDesktopActivity.class);
                    intent.putExtra("session_id", response.body().id);
                    startActivity(intent);
                } else Toast.makeText(DeviceListActivity.this, "Connection failed", Toast.LENGTH_LONG).show();
            }
            public void onFailure(Call<Session> call, Throwable t) { Toast.makeText(DeviceListActivity.this, t.getMessage(), Toast.LENGTH_LONG).show(); }
        });
    }

    private void pair(Device device) {
        EditText input = new EditText(this);
        input.setHint("Pairing code");
        new AlertDialog.Builder(this)
                .setTitle("Pair " + device.name)
                .setView(input)
                .setPositiveButton("Pair", (dialog, which) -> ApiClient.create(this).pairDevice(device.id, new Device.PairRequest(input.getText().toString())).enqueue(new Callback<Device>() {
                    public void onResponse(Call<Device> call, Response<Device> response) {
                        if (response.isSuccessful()) {
                            Toast.makeText(DeviceListActivity.this, "Device paired", Toast.LENGTH_LONG).show();
                            loadDevices();
                        } else {
                            Toast.makeText(DeviceListActivity.this, "Pairing failed", Toast.LENGTH_LONG).show();
                        }
                    }
                    public void onFailure(Call<Device> call, Throwable t) {
                        Toast.makeText(DeviceListActivity.this, t.getMessage(), Toast.LENGTH_LONG).show();
                    }
                }))
                .setNegativeButton("Cancel", null)
                .show();
    }
}
