from dataclasses import dataclass
from ....utility import CData, indent


@dataclass
class Vertex:
    """This class defines a vertex data"""

    pos: tuple[int, int, int]

    def getEntryC(self):
        """Returns a vertex entry"""

        return indent + "{ " + ", ".join(f"{p:6}" for p in self.pos) + " },"


@dataclass
class Vertices:
    """This class defines the array of vertices"""

    name: str
    vertexList: list[Vertex]

    def getC(self):
        vertData = CData()
        listName = f"Vec3s {self.name}[{len(self.vertexList)}]"

        # .h
        vertData.header = f"extern {listName};\n"

        # .c
        vertData.source = (
            (listName + " = {\n") + "\n".join(vertex.getEntryC() for vertex in self.vertexList) + "\n};\n\n"
        )

        return vertData
