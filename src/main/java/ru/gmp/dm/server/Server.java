package ru.gmp.dm.server;

import ru.gmp.dm.Main;
import ru.gmp.dm.client.Client;
import ru.gmp.dm.network.Network;
import ru.gmp.dm.network.Packet;

import java.io.*;
import java.net.*;
import java.util.*;

public class Server {
    private final Map<String, Client> clients = Collections.synchronizedMap(new HashMap<>());

    private boolean enable = false;
    private ServerSocket socket;

    private final Network parent;

    public Server(Network parent, int port) {
        this.parent = parent;
        try {
            socket = new ServerSocket(port);
        } catch (IOException e) {
            Main.getLogger().error("Failed to start server: ", e);
            e.printStackTrace();
        }
    }

    public void start() {
        enable = true;
        new Thread(() -> {
            while (enable) {
                try {
                    Socket client = socket.accept();
                    Client clientHandler = new Client(client, true);

                    Packet firstPacket = clientHandler.read();
                    if (firstPacket == null) {
                        clientHandler.stop();
                        continue;
                    }
                    if (firstPacket.getContent().equals("Identify") &&
                        firstPacket.getToUser().equals("Server")) {
                        String username = firstPacket.getFromUser();
                        clientHandler.setUsername(username);
                        clients.put(username, clientHandler);
                    }

                    new Thread(() -> handleClient(clientHandler)).start();
                } catch (Exception e) {
                    if (enable) {
                        Main.getLogger().error("Error accepting client: ", e);
                        e.printStackTrace();
                    }
                }
            }
        }).start();
    }

    public void stop() {
        enable = false;
        try {
            if (socket != null && !socket.isClosed()) {
                socket.close();
            }
            synchronized (clients) {
                for (Client client : clients.values()) {
                    if (client.isStarted()) client.stop();
                }
                clients.clear();
            }
        } catch (IOException e) {
            Main.getLogger().error("Error stopping server: ", e);
            e.printStackTrace();
        }
    }

    private void handleClient(Client client) {
        try {
            client.keepAlive();

            Packet packet;
            while ((packet = read(client)) != null) {

                if (packet.getToUser().equals("Server") && packet.getContent().equals("Identify")) {
                    client.setUsername(packet.getFromUser());
                    clients.put(client.getUsername(), client);
                    continue;
                }

                if (client.getUsername() == null) {
                    String newUsername = packet.getFromUser();
                    client.setUsername(newUsername);
                    clients.put(newUsername, client);
                }

                if (clients.containsKey(packet.getToUser())) {
                    passMessage(packet);
                } else {
                    passMessage(
                            Packet.encode(
                                    "Server",
                                    "User not found: " + packet.getToUser(),
                                    client.getUsername()
                            )
                    );
                }
            }
        } catch (Exception e) {
            Main.getLogger().error("Error handling client: ", e);
        } finally {
            client.stop();
            clients.remove(client.getUsername());
        }
    }

    public static void send(Client client, Packet packet) throws Exception {
        if (client == null) return;

        if (packet.getToUser().equals(packet.getFromUser())) return;

        client.send(packet);
    }
    public void send(String username, Packet packet) throws Exception {
        Client client = clients.get(username);
        if (client == null) return;

        send(client, packet);
    }


    public static Packet read(Client client) throws Exception {
        if (client == null) return null;
        return client.read();
    }
    public Packet read(String username) throws Exception {
        Client client = clients.get(username);
        if (client == null) return null;
        return read(client);
    }


    public Map<String, Client> getClients() { return clients; }
    public Client getClient(String username) { return clients.get(username); }

    public void passMessage(Packet packet) throws Exception {
        String username = packet.getToUser();
        if (clients.get(username) == null) {
            parent.PassPacket(packet);
        }
        send(username, packet);
    }
}