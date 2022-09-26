from .oot_getters import getRoot, getEnumList
from os import path

# Note: "object" in this context refers to an OoT Object file (like ``gameplay_keep``)


class OoT_ObjectData:
    """Everything related to OoT objects"""

    from dataclasses import dataclass

    @dataclass
    class OoT_Object:
        id: str
        key: str
        name: str

    def __init__(self):
        # Path to the ``ObjectList.xml`` file
        self.objectXML: str

        # general object list
        self.objectList: list[self.OoT_Object] = []

        # list of tuples used by Blender's enum properties
        self.ootEnumObjectID: list[tuple] = []
        self.ootEnumObjectIDLegacy: list[tuple] = []  # for old blends

        self.initObjectLists()

    def initObjectLists(self):
        """Reads the XML and make a list of the useful data to keep"""
        self.objectXML = path.dirname(path.abspath(__file__)) + "/xml/ObjectList.xml"
        for obj in getRoot(self.objectXML).iterfind("Object"):
            self.objectList.append(self.OoT_Object(obj.attrib["ID"], obj.attrib["Key"], obj.attrib["Name"]))
        self.ootEnumObjectID, self.ootEnumObjectIDLegacy = getEnumList(self.objectList, "Custom Object")

    def upgradeObjectInit(self, obj, objectList):
        """Object upgrade logic"""
        if obj.data is None and obj.ootEmptyType == "Room":
            for i in range(len(obj.objectList)):
                obj.objectList[i].objectIDLegacy = obj.objectList[i].objectID
                for object in objectList:
                    if obj.objectList[i].objectIDLegacy == object.id:
                        obj.objectList[i].objectID = object.key

            obj.fast64.oot.version = obj.fast64.oot.cur_version

        for childObj in obj.children:
            self.upgradeObjectInit(childObj, objectList)

    def addMissingObjectToUI(self, roomObj, headerIndex, objectID, csHeaderIndex):
        """Add the missing object to the room empty object OoT object list"""
        if roomObj is not None:
            if headerIndex == 0:
                roomProp = roomObj.ootRoomHeader
            elif headerIndex == 1:
                roomProp = roomObj.ootAlternateRoomHeaders.childNightHeader
            elif headerIndex == 2:
                roomProp = roomObj.ootAlternateRoomHeaders.adultDayHeader
            elif headerIndex == 3:
                roomProp = roomObj.ootAlternateRoomHeaders.adultNightHeader
            elif csHeaderIndex is not None:
                roomProp = roomObj.ootAlternateRoomHeaders.cutsceneHeaders[csHeaderIndex]
            if roomProp is not None:
                collection = roomProp.objectList
                collection.add()
                collection.move(len(collection) - 1, (headerIndex + 1))
                collection[-1].objectID = objectID

    def addMissingObjectsToList(self, roomObj, room, actorList, headerIndex, csHeaderIndex):
        """Adds missing objects to the object list"""
        if len(room.actorList) > 0:
            for roomActor in room.actorList:
                for actor in actorList:
                    if actor.id == roomActor.actorID and not (actor.key == "player") and actor.tiedObjects is not None:
                        for obj in actor.tiedObjects.split(","):
                            if not (obj in room.objectList) and not (obj.startswith("obj_gameplay")):
                                room.objectList.append(obj)
                                self.addMissingObjectToUI(roomObj, headerIndex, obj, csHeaderIndex)

    def addAltHeadersObjects(self, roomObj, room, actorList):
        """Adds missing objects for alternate room headers"""
        if room.childNightHeader is not None:
            self.addMissingObjectsToList(roomObj, room.childNightHeader, actorList, 1, None)
        if room.adultDayHeader is not None:
            self.addMissingObjectsToList(roomObj, room.adultDayHeader, actorList, 2, None)
        if room.adultNightHeader is not None:
            self.addMissingObjectsToList(roomObj, room.adultNightHeader, actorList, 3, None)
        for i in range(len(room.cutsceneHeaders)):
            self.addMissingObjectsToList(roomObj, room.cutsceneHeaders[i], actorList, 4, i)
