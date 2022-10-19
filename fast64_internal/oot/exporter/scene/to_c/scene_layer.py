from .....utility import CData
from ....oot_level_classes import OOTScene
from ...data import indent
from ...room.to_c import convertActorList
from .room_list import convertRoomList
from .commands import convertSceneCommands
from .pathways import convertPathList
from .light_settings import convertLightSettings
from .transition_actor import convertTransActorList
from .spawn_exit import convertSpawnList, convertExitList


def getSceneLayerData(outScene: OOTScene, layerIndex: int):
    """Returns a scene layer's data"""
    layerData = CData()

    # Write the start position list
    if len(outScene.startPositions) > 0:
        layerData.append(convertActorList(outScene, None, layerIndex))

    # Write the transition actor list data
    if len(outScene.transitionActorList) > 0:
        layerData.append(convertTransActorList(outScene, layerIndex))

    # Write the room segment list
    if layerIndex == 0:
        layerData.append(convertRoomList(outScene))

        # Write the path list

        # Note: this will be moved out of the if statement
        # whenever Fast64 handles the different layers for paths
        if len(outScene.pathList) > 0:
            layerData.append(convertPathList(outScene, layerIndex))

    # Write the entrance list
    if len(outScene.entranceList) > 0:
        layerData.append(convertSpawnList(outScene, layerIndex))

    # Write the exit list
    if len(outScene.exitList) > 0:
        layerData.append(convertExitList(outScene, layerIndex))

    # Write the light data
    if len(outScene.lights) > 0:
        layerData.append(convertLightSettings(outScene, layerIndex))

    return layerData


def getSceneLayerPtrEntries(sceneLayers: list[OOTScene]):
    """Returns the layers headers array names"""
    return "\n".join(
        [
            f"{indent + sceneLayers[i].sceneName()}_layer{i:02},"
            if sceneLayers[i] is not None
            else indent + "NULL,"
            if i < 4
            else ""
            for i in range(1, len(sceneLayers))
        ]
    )


def convertSceneLayers(outScene: OOTScene):
    """Returns the scene file data"""
    layerInfo = CData()  # array of pointers to invidual layers
    layerData = CData()  # the data of each layer
    sceneLayers = [outScene, outScene.childNightHeader, outScene.adultDayHeader, outScene.adultNightHeader]
    sceneLayers.extend(outScene.cutsceneHeaders)

    if outScene.hasAltLayers():
        altLayerName = f"SCmdBase* {outScene.getAltLayersListName()}[]"
        altLayerArray = altLayerName + " = {\n" + getSceneLayerPtrEntries(sceneLayers) + "\n};\n\n"

        # .h
        layerInfo.header = f"extern {altLayerName};\n"

    # .c
    for i, layer in enumerate(sceneLayers):
        if layer is not None:
            layerData.append(convertSceneCommands(layer, i))
            if i == 0 and outScene.hasAltLayers():
                layerData.source += altLayerArray
            layerData.append(getSceneLayerData(layer, i))

    sceneLayerData = layerInfo
    sceneLayerData.append(layerData)
    return sceneLayerData
