from ..utility import ootGetSceneOrRoomHeader

from .data.oot_data import OoT_Data
from .oot_level_classes import OOTRoom
from bpy.types import Object


def addMissingObjectToProp(roomObj: Object, headerIndex: int, objectKey: str):
    """Add the missing object to the room empty object OoT object list"""
    if roomObj is not None:
        roomProp = ootGetSceneOrRoomHeader(roomObj, headerIndex, True)
        if roomProp is not None:
            objectList = roomProp.objectList
            objectList.add()
            objectList[-1].objectKey = objectKey


def addMissingObjectsToRoomHeader(roomObj: Object, room: OOTRoom, ootData: OoT_Data, headerIndex: int):
    """Adds missing objects to the object list"""
    if len(room.actorList) > 0:
        for roomActor in room.actorList:
            actor = ootData.actorData.actorsByID.get(roomActor.actorID)
            if actor is not None and actor.key != "player" and len(actor.tiedObjects) > 0:
                for objKey in actor.tiedObjects:
                    if objKey not in ["obj_gameplay_keep", "obj_gameplay_field_keep", "obj_gameplay_dangeon_keep"]:
                        objID = ootData.objectData.objectsByKey[objKey].id
                        if not (objID in room.objectIDList):
                            room.objectIDList.append(objID)
                            addMissingObjectToProp(roomObj, headerIndex, objKey)


def addMissingObjectsToAllRoomHeaders(roomObj: Object, room: OOTRoom, ootData: OoT_Data):
    """
    Adds missing objects (required by actors) to all headers of a room,
    both to the roomObj empty and the exported room
    """
    sceneLayers = [room, room.childNightHeader, room.adultDayHeader, room.adultNightHeader]
    for i, layer in enumerate(sceneLayers):
        if layer is not None:
            addMissingObjectsToRoomHeader(roomObj, layer, ootData, i)
    for i in range(len(room.cutsceneHeaders)):
        addMissingObjectsToRoomHeader(roomObj, room.cutsceneHeaders[i], ootData, i + 4)
