from ....utility import CData
from ...oot_level_classes import OOTScene
from ...oot_utility import indent

from .oot_scene_cmds import ootSceneCommandsToC
from ..oot_room_writer.oot_actor_to_c import ootActorListToC
from ..oot_room_writer.oot_room_list_to_c import ootRoomListHeaderToC
from ..oot_scene_writer.oot_path_to_c import ootPathListToC
from ..oot_scene_writer.oot_light_to_c import ootLightSettingsToC
from ..oot_scene_writer.oot_trans_actor_to_c import ootTransitionActorListToC
from ..oot_scene_writer.oot_entrance_exit_to_c import ootEntranceListToC, ootExitListToC


def ootGetSceneLayerData(scene: OOTScene, headerIndex: int):
    """Returns a scene layer's data"""
    layerData = CData()

    # Write the start position list
    if len(scene.startPositions) > 0:
        layerData.append(ootActorListToC(scene, None, headerIndex))

    # Write the transition actor list data
    if len(scene.transitionActorList) > 0:
        layerData.append(ootTransitionActorListToC(scene, headerIndex))

    # Write the room segment list
    if headerIndex == 0:
        layerData.append(ootRoomListHeaderToC(scene))

    # Write the path list
    if len(scene.pathList) > 0:
        layerData.append(ootPathListToC(scene))

    # Write the entrance list
    if len(scene.entranceList) > 0:
        layerData.append(ootEntranceListToC(scene, headerIndex))

    # Write the exit list
    if len(scene.exitList) > 0:
        layerData.append(ootExitListToC(scene, headerIndex))

    # Write the light data
    if len(scene.lights) > 0:
        layerData.append(ootLightSettingsToC(scene, headerIndex))

    return layerData


def ootGetSceneAltHeaderEntries(sceneLayers: list[OOTScene]):
    """Returns the layers headers array names"""
    return "\n".join(
        [
            f"{indent + sceneLayers[i].sceneName()}_header{i:02},"
            if sceneLayers[i] is not None
            else indent + "NULL,"
            if i < 4
            else ""
            for i in range(1, len(sceneLayers))
        ]
    )


def ootSceneLayersToC(scene: OOTScene):
    """Returns the scene file data"""
    layerInfo = CData()  # array of pointers to invidual layers
    layerData = CData()  # the data of each layer
    sceneLayers = [scene, scene.childNightHeader, scene.adultDayHeader, scene.adultNightHeader]
    sceneLayers.extend(scene.cutsceneHeaders)

    if scene.hasAlternateHeaders():
        altLayerName = f"SCmdBase* {scene.alternateHeadersName()}[]"
        altLayerArray = altLayerName + " = {\n" + ootGetSceneAltHeaderEntries(sceneLayers) + "\n};\n\n"

        # .h
        layerInfo.header = f"extern {altLayerName};\n"

    # .c
    for i, layer in enumerate(sceneLayers):
        if layer is not None:
            layerData.append(ootSceneCommandsToC(layer, i))
            if i == 0 and scene.hasAlternateHeaders():
                layerData.source += altLayerArray
            layerData.append(ootGetSceneLayerData(layer, i))

    sceneLayerData = layerInfo
    sceneLayerData.append(layerData)
    return sceneLayerData
