from bpy.types import Object
from ..utility import ootGetSceneOrRoomHeader
from .constants import oot_data
from .exporter.room.header import RoomHeader


def addMissingObjectToProp(roomObj: Object, headerIndex: int, objectKey: str):
    """Add the missing object to the room empty object OoT object list"""
    if roomObj is not None:
        roomProp = ootGetSceneOrRoomHeader(roomObj, headerIndex, True)
        if roomProp is not None:
            objectList = roomProp.objectList
            objectList.add()
            objectList[-1].objectKey = objectKey


def addMissingObjectsToRoomHeader(roomObj: Object, curHeader: RoomHeader, headerIndex: int):
    """Adds missing objects to the object list"""
    if len(curHeader.actors.actorList) > 0:
        for roomActor in curHeader.actors.actorList:
            actor = oot_data.actorData.actorsByID.get(roomActor.id)
            if actor is not None and actor.key != "player" and len(actor.tiedObjects) > 0:
                for objKey in actor.tiedObjects:
                    if objKey not in ["obj_gameplay_keep", "obj_gameplay_field_keep", "obj_gameplay_dangeon_keep"]:
                        objID = oot_data.objectData.objectsByKey[objKey].id
                        if not (objID in curHeader.objects.objectList):
                            curHeader.objects.objectList.append(objID)
                            addMissingObjectToProp(roomObj, headerIndex, objKey)


def addMissingObjectsToAllRoomHeaders(roomObj: Object, headers: list[RoomHeader]):
    """
    Adds missing objects (required by actors) to all headers of a room,
    both to the roomObj empty and the exported room
    """
    for i, curHeader in enumerate(headers):
        if curHeader is not None:
            addMissingObjectsToRoomHeader(roomObj, curHeader, i)
