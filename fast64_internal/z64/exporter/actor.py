from ...utility import indent

# this file is not inside the room folder since the scene data can have actors too


class Actor:
    """Defines an Actor"""

    def __init__(self):
        self.name = str()
        self.id = str()
        self.pos: list[int] = []
        self.rot = str()
        self.params = str()

    def getActorEntry(self):
        """Returns a single actor entry"""

        posData = "{ " + ", ".join(f"{round(p)}" for p in self.pos) + " }"
        rotData = "{ " + self.rot + " }"

        actorInfos = [self.id, posData, rotData, self.params]
        infoDescs = ["Actor ID", "Position", "Rotation", "Parameters"]

        return (
            indent
            + (f"// {self.name}\n" + indent if self.name != "" else "")
            + "{\n"
            + ",\n".join((indent * 2) + f"/* {desc:10} */ {info}" for desc, info in zip(infoDescs, actorInfos))
            + ("\n" + indent + "},\n")
        )
