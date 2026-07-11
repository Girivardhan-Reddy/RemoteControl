package com.remotecontrol.app.model;

import java.util.List;

public class Device {
    public String id;
    public String name;
    public String hostname;
    public String platform;
    public String status;
    public boolean is_paired;

    public static class DeviceListResponse {
        public List<Device> devices;
    }
}
