package ru.gmp.dm;

import ru.gmp.dm.network.Packet;
import java.awt.*;
import java.awt.event.*;

public class Window extends Frame {
    private final TextField targetNameF;
    private final TextArea history;
    private final TextField input;

    public Window(Main main) {
        setTitle("DecentralizedMessenger");
        setSize(900, 650);
        setLocationRelativeTo(null);
        setLayout(new FlowLayout());

        addWindowListener(new WindowAdapter() {
            public void windowClosing(WindowEvent e) {
                dispose();
                main.stop();
            }
        });

        history = new TextArea(30, 80);
        input = new TextField(20);
        targetNameF = new TextField(20);

        add(history);
        add(input);
        add(targetNameF);

        input.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                String inputText = input.getText();
                String targetName = targetNameF.getText();

                if (inputText.isEmpty() || targetName.isEmpty()) return;

                Main.getLogger().info("User input: {}", inputText);

                long id = 0;
                String selfName = main.getNetwork().getClient().getUsername();

                try {
                    main.getNetwork().getClient().passMessage(
                            Packet.encode(
                                    selfName,
                                    inputText,
                                    targetName
                            )
                    );
                    input.setText("");
                    addMessage(selfName+": "+inputText);
                } catch (Exception ex) {
                    Main.getLogger().error(ex);
                    Main.getLogger().error(ex.getStackTrace());
                }
            }
        });
    }
    public void start() { setVisible(true); }
    public void stop() { setVisible(false); }

    public void addMessage(String message) {
        if (history == null) return;

        history.append(message + "\n");
    }
}
