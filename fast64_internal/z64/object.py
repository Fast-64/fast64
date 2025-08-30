from bpy.types import Object
from ..utility import ootGetSceneOrRoomHeader
from ..game_data import game_data
from .exporter.room.header import RoomHeader


def add_missing_object_to_prop(room_obj: Object, header_index: int, object_key: str):
    """Adds the given object key to the room object's object list in its OOT header."""
    if not room_obj:
        return

    room_prop = ootGetSceneOrRoomHeader(room_obj, header_index, True)
    if not room_prop:
        return

    new_obj = room_prop.objectList.add()
    new_obj.objectKey = object_key


def add_missing_objects_to_room_header(room_obj: Object, header: RoomHeader, header_index: int):
    """Adds any missing objects required by the room's actors to the header and room object."""
    if not header.actors.actorList:
        return

    excluded_keys = {
        "obj_gameplay_keep",
        "obj_gameplay_field_keep",
        "obj_gameplay_dangeon_keep"
    }

    existing_object_ids = set(header.objects.objectList)

    for room_actor in header.actors.actorList:
        actor = game_data.z64.actors.actorsByID.get(room_actor.id)
        if not actor or actor.key == "player":
            continue

        for object_key in actor.tiedObjects:
            if object_key in excluded_keys:
                continue

            obj_data = game_data.z64.objects.objects_by_key.get(object_key)
            if not obj_data:
                continue

            obj_id = obj_data.id
            if obj_id not in existing_object_ids:
                header.objects.objectList.append(obj_id)
                existing_object_ids.add(obj_id)
                add_missing_object_to_prop(room_obj, header_index, object_key)


def add_missing_objects_to_all_room_headers(room_obj: Object, headers: list[RoomHeader]):
    """Adds missing objects required by actors to all room headers and the corresponding Blender object."""
    for index, header in enumerate(headers):
        if header:
            add_missing_objects_to_room_header(room_obj, header, index)