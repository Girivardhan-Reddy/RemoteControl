package com.remotecontrol.app.api;

import com.remotecontrol.app.model.AuthModels;
import com.remotecontrol.app.model.Device;
import com.remotecontrol.app.model.Session;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.DELETE;
import retrofit2.http.GET;
import retrofit2.http.POST;
import retrofit2.http.Path;

public interface ApiService {
    @POST("auth/login")
    Call<AuthModels.AuthResponse> login(@Body AuthModels.LoginRequest request);

    @POST("auth/register")
    Call<AuthModels.AuthResponse> register(@Body AuthModels.RegisterRequest request);

    @GET("devices")
    Call<Device.DeviceListResponse> devices();

    @POST("connect/sessions")
    Call<Session> createSession(@Body Session.CreateSessionRequest request);

    @DELETE("connect/sessions/{id}")
    Call<Session> endSession(@Path("id") String id);
}
