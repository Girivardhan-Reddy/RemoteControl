package com.remotecontrol.app.ui;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import com.remotecontrol.app.R;
import com.remotecontrol.app.model.Device;
import java.util.ArrayList;
import java.util.List;

public class DeviceAdapter extends RecyclerView.Adapter<DeviceAdapter.Holder> {
    public interface Listener {
        void connect(Device device);
        void pair(Device device);
    }
    private final Listener listener;
    private final List<Device> devices = new ArrayList<>();

    public DeviceAdapter(Listener listener) { this.listener = listener; }
    public void setDevices(List<Device> values) { devices.clear(); if (values != null) devices.addAll(values); notifyDataSetChanged(); }

    @NonNull public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_device, parent, false);
        return new Holder(view);
    }
    public void onBindViewHolder(@NonNull Holder holder, int position) {
        Device device = devices.get(position);
        holder.name.setText(device.name);
        holder.status.setText(device.status + (device.is_paired ? " - paired" : " - needs pairing"));
        holder.details.setText(device.hostname + " / " + device.platform + "\nID: " + device.id);
        holder.connect.setEnabled(device.is_paired ? "online".equals(device.status) : true);
        holder.connect.setText(device.is_paired ? "Connect" : "Pair");
        holder.connect.setOnClickListener(v -> {
            if (device.is_paired) listener.connect(device);
            else listener.pair(device);
        });
    }
    public int getItemCount() { return devices.size(); }

    static class Holder extends RecyclerView.ViewHolder {
        TextView name;
        TextView status;
        TextView details;
        Button connect;
        Holder(View itemView) {
            super(itemView);
            name = itemView.findViewById(R.id.deviceName);
            status = itemView.findViewById(R.id.deviceStatus);
            details = itemView.findViewById(R.id.deviceDetails);
            connect = itemView.findViewById(R.id.connectButton);
        }
    }
}
