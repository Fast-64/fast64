from .....utility import CData
from ....oot_level_classes import OOTRoom
from ...data import indent
from .commands import convertRoomCommands
from .object import convertObjectList
from .actor import convertActorList


def getRoomLayerData(outRoom: OOTRoom, layerIndex: int):
    """Returns a room layer's actor and object list"""
    layerData = CData()

    if len(outRoom.objectIDList) > 0:
        layerData.append(convertObjectList(outRoom, layerIndex))

    if len(outRoom.actorList) > 0:
        layerData.append(convertActorList(None, outRoom, layerIndex))

    return layerData


def getRoomLayerPtrEntries(roomLayers: list[OOTRoom]):
    """Returns the layers headers array names"""
    return "\n".join(
        [
            f"{indent + roomLayers[i].roomName()}_layer{i:02},"
            if roomLayers[i] is not None
            else indent + "NULL,"
            if i < 4
            else ""
            for i in range(1, len(roomLayers))
        ]
    )


def convertRoomLayers(outRoom: OOTRoom):
    """Returns the rooms file data"""
    layerInfo = CData()  # array of pointers to invidual layers
    layerData = CData()  # the data of each layer
    roomLayers = [outRoom, outRoom.childNightHeader, outRoom.adultDayHeader, outRoom.adultNightHeader]
    roomLayers.extend(outRoom.cutsceneHeaders)

    if outRoom.hasAltLayers():
        altLayerName = f"SCmdBase* {outRoom.getAltLayersListName()}[]"
        altLayerArray = altLayerName + " = {\n" + getRoomLayerPtrEntries(roomLayers) + "\n};\n\n"

        # .h
        layerInfo.header = f"extern {altLayerName};\n"

    # .c
    for i, layer in enumerate(roomLayers):
        if layer is not None:
            layerData.append(convertRoomCommands(layer, i))
            if i == 0 and outRoom.hasAltLayers():
                layerData.source += altLayerArray
            layerData.append(getRoomLayerData(layer, i))

    roomLayerData = layerInfo
    roomLayerData.append(layerData)
    return roomLayerData
