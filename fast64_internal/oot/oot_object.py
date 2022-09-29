from ..utility import ootGetSceneOrRoomHeader

from .data.oot_data import OoT_Data
from .oot_scene_room import OOTRoom
from bpy.types import Object


def addMissingObjectToProp(roomObj: Object, headerIndex: int, objectKey: str):
    """Add the missing object to the room empty object OoT object list"""
    if roomObj is not None:
        roomProp = ootGetSceneOrRoomHeader(roomObj, headerIndex, True)
        if roomProp is not None:
            collection = roomProp.objectList
            collection.add()
            collection.move(len(collection) - 1, (headerIndex + 1))
            collection[-1].objectKey = objectKey


def addMissingObjectsToList(roomObj: Object, room: OOTRoom, ootData: OoT_Data, headerIndex: int):
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


def addRoomHeadersObjects(roomObj: Object, room: OOTRoom, ootData: OoT_Data):
    """Adds missing objects for alternate room headers"""
    sceneLayers = [room, room.childNightHeader, room.adultDayHeader, room.adultNightHeader]
    for i, layer in enumerate(sceneLayers):
        if layer is not None:
            addMissingObjectsToList(roomObj, layer, ootData, i)
    for i in range(len(room.cutsceneHeaders)):
        addMissingObjectsToList(roomObj, room.cutsceneHeaders[i], ootData, i + 4)
