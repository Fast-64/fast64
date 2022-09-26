from os import path
from dataclasses import dataclass
from .oot_getters import getXMLRoot, getEnumList
from .oot_data import OoT_BaseElement


@dataclass
class OoT_ActorElement(OoT_BaseElement):
    category: str
    tiedObjects: str


class OoT_ActorData:
    """Everything related to OoT Actors"""

    def __init__(self):
        # general actor list
        self.actorList: list[OoT_ActorElement] = []

        # Path to the ``ActorList.xml`` file
        actorXML = path.dirname(path.abspath(__file__)) + "/xml/ActorList.xml"
        for actor in getXMLRoot(actorXML).iterfind("Actor"):
            self.actorList.append(
                OoT_ActorElement(
                    actor.attrib["ID"],
                    actor.attrib["Key"],
                    actor.attrib["Name"],
                    actor.attrib["Category"],
                    actor.get("ObjectKey"),  # actors doesn't always use an object
                )
            )
        # list of tuples used by Blender's enum properties
        # ``ootEnumActorIDLegacy`` is there for compatibility with older blends
        self.ootEnumActorID, self.ootEnumActorIDLegacy = getEnumList(self.actorList, "Custom Actor")
