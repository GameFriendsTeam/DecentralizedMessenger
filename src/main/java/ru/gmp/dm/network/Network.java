package ru.gmp.dm.network;

import org.json.JSONObject;
import ru.gmp.dm.Main;
import ru.gmp.dm.client.Client;
import ru.gmp.dm.server.Server;

import java.io.IOException;

public class Network {

    private final boolean serverEnable;

    private final Server server;
    private final Client client;

    private final Main main;


    public Network(Main main, String nextAddr, int port, boolean serverEnable) throws IOException {
        this.serverEnable = serverEnable;

        server = new Server(this, port);
        client = new Client(nextAddr, port);

        client.keepAlive();

        this.main = main;
    }


    public void PassPacket(Packet packet) throws Exception {
        client.passMessage(packet);
    }

    public void stop() {
        server.stop();
        client.stop();
    }
    public void start() {
        server.start();
        client.start();
        try {
            client.passMessage(Packet.encode(client.getUsername(), "Identify", "Server"));
        } catch (Exception e) {
            Main.getLogger().error("Failed to identify client: ", e);
        }
        new Thread(() -> handleRead(client)).start();
    }

    private void handleRead(Client client) {
        try {
            Packet packet;

            while ((packet = client.read()) != null) {
                JSONObject data = new JSONObject(packet);
                if (data.isEmpty()) continue;

                main.getWindow().addMessage(data.getString("fromUser")+": "+data.getString("content"));
            }
        } catch (Exception e) {
            Main.getLogger().error(e);
            e.printStackTrace();
        }
    }

    public boolean isServerEnable() { return serverEnable; }

    public Server getServer() { return server; }
    public Client getClient() { return client; }
    public Main getMain() { return main; }
}
