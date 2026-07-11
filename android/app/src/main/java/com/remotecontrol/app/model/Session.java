package com.remotecontrol.app.model;

public class Session {
    public String id;
    public String user_id;
    public String device_id;
    public String status;

    public static class CreateSessionRequest {
        public String device_id;
        public CreateSessionRequest(String deviceId) { this.device_id = deviceId; }
    }
}
