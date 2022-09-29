from os import path
from dataclasses import dataclass
from .oot_getters import getXMLRoot
from .oot_data import OoT_BaseElement


@dataclass
class OoT_ActorElement(OoT_BaseElement):
    category: str
    tiedObjects: list[str]


class OoT_ActorData:
    """Everything related to OoT Actors"""

    def __init__(self):
        # general actor list
        self.actorList: list[OoT_ActorElement] = []

        # Path to the ``ActorList.xml`` file
        actorXML = path.dirname(path.abspath(__file__)) + "/xml/ActorList.xml"
        for actor in getXMLRoot(actorXML).iterfind("Actor"):
            tiedObjects = []
            objKey = actor.get("ObjectKey")
            if objKey is not None: # actors don't always use an object
                tiedObjects = objKey.split(",")
            self.actorList.append(
                OoT_ActorElement(
                    actor.attrib["ID"],
                    actor.attrib["Key"],
                    actor.attrib["Name"],
                    actor.attrib["Category"],
                    tiedObjects,
                )
            )
        self.actorsByKey = {actor.key: actor for actor in self.actorList}
        self.actorsByID = {actor.id: actor for actor in self.actorList}
        # list of tuples used by Blender's enum properties
        self.ootEnumActorID = [("Custom", "Custom Actor", "Custom")]

        for actor in self.actorList:
            self.ootEnumActorID.append((actor.id, actor.name, actor.id))