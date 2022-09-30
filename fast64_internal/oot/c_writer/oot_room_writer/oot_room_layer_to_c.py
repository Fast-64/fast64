from ....utility import CData
from ...oot_scene_room import OOTRoom
from ...oot_utility import indent

from ..oot_scene_room_cmds.oot_room_cmds import ootRoomCommandsToC
from .oot_object_to_c import ootObjectListToC
from .oot_actor_to_c import ootActorListToC


def ootGetRoomLayerData(room: OOTRoom, headerIndex: int):
    """Returns a room layer's data"""
    layerData = ootRoomCommandsToC(room, headerIndex)

    if len(room.objectIDList) > 0:
        layerData.append(ootObjectListToC(room, headerIndex))

    if len(room.actorList) > 0:
        layerData.append(ootActorListToC(None, room, headerIndex))

    return layerData


def ootGetAltHeaderEntries(roomLayers: list[OOTRoom]):
    """Returns the layers headers array names"""
    return "\n".join(
        [
            f"{indent + layer.roomName()}_header{i:02}," if layer is not None else indent + "NULL," if i < 4 else ""
            for i, layer in enumerate(roomLayers)
        ]
    )


def ootRoomLayersToC(room: OOTRoom):
    layerInfo = CData()  # array of pointers to invidual layers
    layerData = CData()  # the data of each layer
    roomLayerName = f"SCmdBase* {room.alternateHeadersName()}[]"
    roomLayers = [room, room.childNightHeader, room.adultDayHeader, room.adultNightHeader]
    roomLayers.extend(room.cutsceneHeaders)

    # .h
    layerInfo.header = f"extern {roomLayerName};\n"

    # .c
    layerInfo.source = roomLayerName + " = {\n" + ootGetAltHeaderEntries(roomLayers) + "\n};\n\n"

    for i, layer in enumerate(roomLayers):
        if layer is not None:
            layerData.append(ootGetRoomLayerData(layer, i))

    roomLayerData = layerInfo
    roomLayerData.append(layerData)
    return roomLayerData
