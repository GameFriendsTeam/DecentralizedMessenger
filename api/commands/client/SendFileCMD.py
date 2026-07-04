from pathlib import Path
from api.Packet import Packet
from api.commands.Command import Command
from api.commands.CommandSender import CommandSender
from api.utils.Encryption import FileEncryption
import __main__
from api.utils.Other import bytes_to_base64



class SendFileCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        file_path = ""
        try:
            import tkinter as tk
            from tkinter import filedialog
            tk.Tk().withdraw()

            file_path = filedialog.askopenfilename(
                initialdir="/",
                title="Select a file",
                filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
            )

        except Exception as e:
            print(e)
            print("Enter file path manually.")
            file_path = input("File path: ")

        if file_path == "":
            return

        # get current encryption object
        encript = cs.get_encript(__main__.current_getter)
        if not encript:
            print("Encryption is not activated")
            return

        fe = FileEncryption()
        key = fe.getKey()
        ed = fe.encrypt(file_path)
        path_obj = Path(file_path)
        
        with open(str(path_obj.with_suffix(".key")), "wb") as f:
            f.write(key)

        nonce, ciphertext = encript.encrypt_message(key)
        cs.transmit(Packet({
            "content": "/sf",
            "type": "key2file",
            "from": cs.getUsername(),
            "to": __main__.current_getter,
            "encrypted": [bytes_to_base64(nonce), bytes_to_base64(ciphertext)]
        }), True)
        status0, _enc = cs.read()

        nonce, ciphertext = encript.encrypt_message(path_obj.name.encode("utf-8"))
        cs.transmit(Packet({
            "content": "/sf",
            "type": "filedata",
            "from": cs.getUsername(),
            "to": __main__.current_getter,
            "encrypted": bytes_to_base64(ed),
            "filename": [bytes_to_base64(nonce), bytes_to_base64(ciphertext)]
        }), True)
        status1, _enc = cs.read()
        print(status0)
        print(status1)