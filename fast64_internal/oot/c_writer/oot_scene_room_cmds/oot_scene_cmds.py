from ....utility import PluginError

from ...oot_level_classes import OOTScene
from ....utility import CData
from ...oot_utility import indent
from .oot_common_cmds import cmdAltHeaders, cmdEndMarker


def cmdSoundSettings(scene: OOTScene):
    """Returns C-converted sound settings command"""
    return f"SCENE_CMD_SOUND_SETTINGS({scene.audioSessionPreset}, {scene.nightSeq}, {scene.musicSeq})"


def cmdRoomList(scene: OOTScene):
    """Returns C-converted room list command"""
    return f"SCENE_CMD_ROOM_LIST({len(scene.rooms)}, {scene.roomListName()})"


def cmdTransiActorList(scene: OOTScene, headerIndex: int):
    """Returns C-converted transition actors list command"""
    return f"SCENE_CMD_TRANSITION_ACTOR_LIST({len(scene.transitionActorList)}, {scene.transitionActorListName(headerIndex)})"


def cmdMiscSettings(scene: OOTScene):
    """Returns C-converted misc settings command"""
    return f"SCENE_CMD_MISC_SETTINGS({scene.cameraMode}, {scene.mapLocation})"


def cmdColHeader(scene: OOTScene):
    """Returns C-converted collision header command"""
    return f"SCENE_CMD_COL_HEADER(&{scene.collision.headerName()})"


def cmdEntranceList(scene: OOTScene, headerIndex: int):
    """Returns C-converted entrance list command"""
    # ``NULL`` if there's no list since this command expects an address
    entranceListName = scene.entranceListName(headerIndex) if len(scene.entranceList) > 0 else "NULL"
    return f"SCENE_CMD_ENTRANCE_LIST({entranceListName})"


def cmdSpecialFiles(scene: OOTScene):
    """Returns C-converted special files command"""
    # special files are the Navi hint mode and the scene's global object ID
    return f"SCENE_CMD_SPECIAL_FILES({scene.naviCup}, {scene.globalObject})\n"


def cmdPathList(scene: OOTScene):
    """Returns C-converted paths list command"""
    return f"SCENE_CMD_PATH_LIST({scene.pathListName()})"


def cmdSpawnList(scene: OOTScene, headerIndex: int):
    """Returns C-converted spawns list command"""
    # ``NULL`` if there's no list since this command expects an address
    spawnPosName = scene.startPositionsName(headerIndex) if startPosNumber > 0 else "NULL"
    startPosNumber = len(scene.startPositions)
    return f"SCENE_CMD_SPAWN_LIST({startPosNumber}, {spawnPosName})"


def cmdSkyboxSettings(scene: OOTScene):
    """Returns C-converted spawns list command"""
    return f"SCENE_CMD_SKYBOX_SETTINGS({scene.skyboxID}, {scene.skyboxCloudiness}, {scene.skyboxLighting})"


def cmdExitList(scene: OOTScene, headerIndex: int):
    """Returns C-converted exit list command"""
    return f"SCENE_CMD_EXIT_LIST({scene.exitListName(headerIndex)})"


def cmdLightSettingList(scene: OOTScene, headerIndex: int):
    """Returns C-converted light settings list command"""
    lightCount = len(scene.lights)
    lightSettingsName = scene.lightListName(headerIndex) if lightCount > 0 else "NULL"
    return f"SCENE_CMD_ENV_LIGHT_SETTINGS({lightCount}, {lightSettingsName})"


def cmdCutsceneData(scene: OOTScene, headerIndex: int):
    """Returns C-converted cutscene data command"""
    if scene.csWriteType == "Embedded":
        csDataName = scene.cutsceneDataName(headerIndex)
    elif scene.csWriteType == "Object":
        if scene.csWriteObject is not None:
            csDataName = scene.csWriteObject.name  # ``csWriteObject`` type: ``OOTCutscene``
        else:
            raise PluginError("OoT Level to C: ``scene.csWriteObject`` is None!")
    elif scene.csWriteType == "Custom":
        csDataName = scene.csWriteCustom

    return f"SCENE_CMD_CUTSCENE_DATA({csDataName})"


def getSceneCommandsList(scene: OOTScene, headerIndex: int):
    """Returns every scene commands converted to C code."""
    sceneCmdList: list[str] = []

    if scene.hasAlternateHeaders():
        sceneCmdList.append(cmdAltHeaders(scene.alternateHeadersName()))

    sceneCmdList.append(cmdSoundSettings(scene))
    sceneCmdList.append(cmdRoomList(scene))

    if len(scene.transitionActorList) > 0:
        sceneCmdList.append(cmdTransiActorList(scene, headerIndex))

    sceneCmdList.append(cmdMiscSettings(scene))
    sceneCmdList.append(cmdColHeader(scene))
    sceneCmdList.append(cmdEntranceList(scene, headerIndex))
    sceneCmdList.append(cmdSpecialFiles(scene))

    if len(scene.pathList) > 0:
        sceneCmdList.append(cmdPathList(scene))

    sceneCmdList.append(cmdSpawnList(scene, headerIndex))
    sceneCmdList.append(cmdSkyboxSettings(scene))

    if len(scene.exitList) > 0:
        sceneCmdList.append(cmdExitList(scene, headerIndex))

    sceneCmdList.append(cmdLightSettingList(scene, headerIndex))

    if scene.writeCutscene:
        sceneCmdList.append(cmdCutsceneData(scene, headerIndex))

    sceneCmdList.append(cmdEndMarker())

    return sceneCmdList


def ootSceneCommandsToC(scene: OOTScene, headerIndex: int):
    """Converts every scene commands to C code."""
    sceneCmdData = CData()
    sceneCmdName = f"SCmdBase {scene.sceneHeaderName(headerIndex)}[]"
    sceneCmdList = getSceneCommandsList(scene, headerIndex)

    # .h
    sceneCmdData.header = f"extern {sceneCmdName};\n"

    # .c
    sceneCmdData.source = (
        sceneCmdName + " = {\n" + ",\n".join([indent + sceneCmd for sceneCmd in sceneCmdList]) + "};\n\n"
    )

    return sceneCmdData
