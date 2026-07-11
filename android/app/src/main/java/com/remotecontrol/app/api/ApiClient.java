package com.remotecontrol.app.api;

import android.content.Context;
import com.remotecontrol.app.util.SettingsStore;
import com.remotecontrol.app.util.TokenStore;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class ApiClient {
    public static ApiService create(Context context) {
        TokenStore tokenStore = new TokenStore(context);
        OkHttpClient client = new OkHttpClient.Builder().addInterceptor(chain -> {
            Request original = chain.request();
            Request.Builder builder = original.newBuilder();
            String token = tokenStore.access();
            if (token != null && !token.isEmpty()) {
                builder.header("Authorization", "Bearer " + token);
            }
            return chain.proceed(builder.build());
        }).build();
        String base = new SettingsStore(context).serverUrl();
        if (!base.endsWith("/")) {
            base += "/";
        }
        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl(base + "api/v1/")
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build();
        return retrofit.create(ApiService.class);
    }
}
