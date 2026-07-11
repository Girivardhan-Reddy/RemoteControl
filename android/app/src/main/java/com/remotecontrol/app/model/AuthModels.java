package com.remotecontrol.app.model;

public final class AuthModels {
    private AuthModels() {}

    public static class LoginRequest {
        public String email;
        public String password;
        public LoginRequest(String email, String password) { this.email = email; this.password = password; }
    }

    public static class RegisterRequest {
        public String name;
        public String email;
        public String password;
        public RegisterRequest(String name, String email, String password) { this.name = name; this.email = email; this.password = password; }
    }

    public static class AuthResponse {
        public String access_token;
        public String refresh_token;
        public String token_type;
        public User user;
    }

    public static class User {
        public String id;
        public String email;
        public String name;
        public String role;
    }
}
