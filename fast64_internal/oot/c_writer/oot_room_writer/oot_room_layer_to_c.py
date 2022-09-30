from ....utility import CData
from ...oot_level_classes import OOTRoom
from ...oot_utility import indent

from ..oot_scene_room_cmds.oot_room_cmds import ootRoomCommandsToC
from .oot_object_to_c import ootObjectListToC
from .oot_actor_to_c import ootActorListToC


def ootGetRoomLayerData(room: OOTRoom, headerIndex: int):
    """Returns a room layer's data"""
    layerData = CData()

    if len(room.objectIDList) > 0:
        layerData.append(ootObjectListToC(room, headerIndex))

    if len(room.actorList) > 0:
        layerData.append(ootActorListToC(None, room, headerIndex))

    return layerData


def ootGetRoomAltHeaderEntries(roomLayers: list[OOTRoom]):
    """Returns the layers headers array names"""
    return "\n".join(
        [
            f"{indent + layer.roomName()}_header{i:02}," if layer is not None else indent + "NULL," if i < 4 else ""
            for i, layer in enumerate(roomLayers)
        ]
    )


def ootRoomLayersToC(room: OOTRoom):
    """Returns the rooms file data"""
    layerInfo = CData()  # array of pointers to invidual layers
    layerData = CData()  # the data of each layer
    altLayerName = f"SCmdBase* {room.alternateHeadersName()}[]"
    roomLayers = [room, room.childNightHeader, room.adultDayHeader, room.adultNightHeader]
    roomLayers.extend(room.cutsceneHeaders)
    altLayerArray = altLayerName + " = {\n" + ootGetRoomAltHeaderEntries(roomLayers) + "\n};\n\n"

    # .h
    layerInfo.header = f"extern {altLayerName};\n"

    # .c
    for i, layer in enumerate(roomLayers):
        if layer is not None:
            layerData.append(ootRoomCommandsToC(layer, i))
            if i == 0:
                layerData.source += altLayerArray
            layerData.append(ootGetRoomLayerData(layer, i))

    roomLayerData = layerInfo
    roomLayerData.append(layerData)
    return roomLayerData
