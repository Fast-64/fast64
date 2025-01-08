import bpy
from ..game_data import game_data

from bpy.types import Object
from ..utility import ootGetSceneOrRoomHeader
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
        game_data.z64.update(bpy.context, None)

        for roomActor in curHeader.actors.actorList:
            actor = game_data.z64.actorData.actorsByID.get(roomActor.id)
            if actor is not None and actor.key != "player" and len(actor.tiedObjects) > 0:
                for objKey in actor.tiedObjects:
                    if objKey.replace("obj_", "") not in {"gameplay_keep", "gameplay_field_keep", "gameplay_dangeon_keep"}:
                        objID = game_data.z64.objectData.objects_by_key[objKey].id
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
