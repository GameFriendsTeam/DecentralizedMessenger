package ru.gmp.dm;

import org.apache.logging.log4j.*;
import ru.gmp.dm.network.Network;

import java.awt.*;
import java.io.*;

public class Main {
    private static final Logger LOGGER = LogManager.getLogger(Main.class);
    private final Window window;
    private Network network = null;

    public static void main(String[] args) {
        Main main = new Main(args);
        main.start();
    }

    private Main(String[] args) {
        try {
            Window.WOR wor = new Window.WOR(new Frame());
            wor.join();

            String addr = wor.getIP();
            String name = wor.getUsername();

            network = new Network(this, addr, 1414, true);
            network.getClient().setUsername(name);

        } catch (Exception e) {
            Main.getLogger().error(e);
            Main.getLogger().error(e.getStackTrace());
        }

        window = new Window(this);
    }
    public void stop() {
        window.stop();
        network.stop();
        System.exit(0);
    }

    public void start() {
        window.start();
        network.start();
    }

    public static Logger getLogger() { return LOGGER; }
    public Window getWindow() { return window; }
    public Network getNetwork() { return network; }
}