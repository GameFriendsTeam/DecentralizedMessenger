from api.commands.Command import Command


class CommandManager:
    _cmds: dict[str, Command] = {}
    def __init__(self):
        self._cmds = {}

    def registerCMD(self, name: str, cmd: Command):
        self._cmds[name] = cmd

    def registerCMDs(self, cmds: dict[str, Command]):
        for name, cmd in cmds.items():
            self.registerCMD(name, cmd)

    def getCMD(self, name: str, default = None) -> Command | None:
        return self._cmds.get(name, default)
    
    def getCMDs(self) -> dict[str, Command]:
        return self._cmds