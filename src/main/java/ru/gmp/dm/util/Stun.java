package ru.gmp.dm.util;
public class Stun {
}
/*
import org.ice4j.Transport;
import org.ice4j.TransportAddress;
import org.ice4j.ice.*;
import org.ice4j.ice.harvest.StunCandidateHarvester;
import org.ice4j.socket.IceSocketWrapper;
import ru.gmp.dm.Main;

import java.net.InetAddress;
import java.net.InetSocketAddress;

public class Stun {
    private int localPost;
    private InetAddress localAddr;

    private String publicIP;
    private int publicPort;

    private Main main;

    public Stun(Main main, InetAddress localAddr, int localPort) {
        this.main = main;

        Agent agent = new Agent();

        agent.addCandidateHarvester(new StunCandidateHarvester(
                new TransportAddress("stun.l.google.com", 19302, Transport.UDP)));
        agent.addCandidateHarvester(new StunCandidateHarvester(
                new TransportAddress("stun1.l.google.com", 19302,Transport.UDP)));

        agent.add
    }
}
*/