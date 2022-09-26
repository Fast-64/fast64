from dataclasses import dataclass
from .oot_getters import getRoot, getEnumList
from os import path


@dataclass
class OoT_Actor:
    id: str
    key: str
    name: str
    category: str
    tiedObjects: str


class OoT_ActorData:
    """Everything related to OoT Actors"""

    def __init__(self):
        # Path to the ``ActorList.xml`` file
        self.actorXML: str

        # general actor list
        self.actorList: list[OoT_Actor] = []

        # list of tuples used by Blender's enum properties
        self.ootEnumActorID: list[tuple] = []
        self.ootEnumActorIDLegacy: list[tuple] = []  # for old blends

        self.actorXML = path.dirname(path.abspath(__file__)) + "/xml/ActorList.xml"
        for actor in getRoot(self.actorXML).iterfind("Actor"):
            self.actorList.append(
                OoT_Actor(
                    actor.attrib["ID"],
                    actor.attrib["Key"],
                    actor.attrib["Name"],
                    actor.attrib["Category"],
                    actor.get("ObjectKey"),  # actors doesn't always use an object
                )
            )
        self.ootEnumActorID, self.ootEnumActorIDLegacy = getEnumList(self.actorList, "Custom Actor")
