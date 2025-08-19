package ru.gmp.dm.client;

import java.io.*;
import java.net.*;

import org.json.JSONObject;
import ru.gmp.dm.network.Packet;

public class Client {
    private final boolean serverClient;
    private boolean started = false;
    private final Socket socket;

    private String targetAddr;
    private int targetPort;

    private PrintWriter out;
    private BufferedReader in;

    private String username;

    public Client(String addr, int port) throws IOException {
        this.socket = new Socket();
        this.serverClient = false;
        this.targetAddr = addr;
        this.targetPort = port;
    }

    public Client(Socket socket, boolean serverClient) throws IOException {
        this.socket = socket;
        this.serverClient = serverClient;
        initStreams();
    }

    public void setUsername(String username) { this.username = username; }
    public String getUsername() { return username; }

    private void initStreams() throws IOException {
        if (socket != null) {
            this.out = new PrintWriter(socket.getOutputStream(), true);
            this.in = new BufferedReader(new InputStreamReader(socket.getInputStream()));
        }
    }

    public void send(Packet packet) throws Exception {
        if (socket == null || socket.isClosed()) throw new IOException("Client socket is closed");
        if (out == null) initStreams();

        out.println(packet.toString());
    }

    public Packet read() throws Exception {
        if (socket == null || socket.isClosed()) throw new IOException("Client socket is closed");
        if (in == null) initStreams();

        try {

            String rawPacket = in.readLine();
            if (rawPacket == null || rawPacket.isEmpty()) return null;

            return Packet.encode(new JSONObject(rawPacket));
        } catch (Exception e) {
            return null;
        }
    }

    public void keepAlive() {
        try {
            socket.setKeepAlive(true);
        } catch (SocketException ignored) {
        }
    }

    public void start() {
        if (serverClient) return;
        try {
            socket.connect(new InetSocketAddress(targetAddr, targetPort));
            started = true;
            initStreams();
            passMessage(Packet.encode(username, "Identify", "Server")); // Отправка пакета идентификации
        } catch (Exception ignored) {
        }
    }

    public void stop() {
        try {
            if (out != null) out.close();
            if (in != null) in.close();
            if (socket != null && !socket.isClosed()) socket.close();

            started = false;
        } catch (IOException ignored) {
        }
    }

    public boolean isStarted() { return started; }

    public void passMessage(Packet packet) throws Exception {
        if (socket == null || socket.isClosed()) throw new IOException("Client socket is closed");
        packet.addData("passed", true);
        send(packet);
    }
}