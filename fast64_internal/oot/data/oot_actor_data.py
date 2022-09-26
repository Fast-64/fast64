class OoT_ActorData:
    """Everything related to OoT Actors"""

    from dataclasses import dataclass

    @dataclass
    class OoT_Actor:
        id: str
        key: str
        name: str
        category: str
        tiedObjects: str

    def __init__(self):
        # Path to the ``ActorList.xml`` file
        self.actorXML: str

        # general actor list
        self.actorList: list[self.OoT_Actor] = []

        # list of tuples used by Blender's enum properties
        self.ootEnumActorID: list[tuple] = []
        self.ootEnumActorIDLegacy: list[tuple] = []  # for old blends

        self.initActorLists()

    def initActorLists(self):
        """Reads the XML and make a list of the useful data to keep"""
        from .oot_data import OoT_Common
        from os import path

        self.actorXML = path.dirname(path.abspath(__file__)) + "/xml/ActorList.xml"
        for actor in OoT_Common.getters.getRoot(self.actorXML).iterfind("Actor"):
            self.actorList.append(
                self.OoT_Actor(
                    actor.attrib["ID"],
                    actor.attrib["Key"],
                    actor.attrib["Name"],
                    actor.attrib["Category"],
                    actor.get("ObjectKey"),  # actors doesn't always use an object
                )
            )
        self.ootEnumActorID, self.ootEnumActorIDLegacy = OoT_Common.getters.getEnumList(self.actorList, "Custom Actor")
