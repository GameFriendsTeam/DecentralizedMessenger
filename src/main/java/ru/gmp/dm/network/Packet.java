package ru.gmp.dm.network;

import org.json.JSONArray;
import org.json.JSONObject;

public class Packet {
    private final JSONObject payload;
    private JSONObject additionalData = new JSONObject();

    private Packet(JSONObject payload) {
        this.payload = payload;
    }
    private Packet(String fromUser, String content, String toUser, JSONObject additionalData) {
        this.payload = new JSONObject();
        this.payload.put("fromUser", fromUser);
        this.payload.put("content", content);
        this.payload.put("toUser", toUser);
        if (additionalData != null) this.additionalData = additionalData;
        this.payload.put("additionalData", additionalData);
    }
    public void addData(String K, Object V) {
        this.additionalData.put(K, V);
    }

    private Packet(String fromUser, String content, String toUser) { this(fromUser, content, toUser, null); }


    public static Packet encode(JSONObject payload) { return new Packet(payload); }
    public static Packet encode(String fromUser, String content, String toUser) { return new Packet(fromUser, content, toUser); }
    public static Packet encode(String fromUser, String content, String toUser, JSONObject additionalData) { return new Packet(fromUser, content, toUser, additionalData); }

    public static JSONObject decode(Packet packet) { return packet.payload; }

    public String getFromUser() { return payload.optString("fromUser", "Unknown"); }
    public String getContent() { return payload.optString("content", ""); }
    public String getToUser() { return payload.optString("toUser", "Unknown"); }
    public Object getData(String K) { return additionalData.opt(K); }

    public String toString() { return payload.toString(); }
}
