from ....utility import CData, PluginError

from ...oot_level_classes import OOTScene
from ...oot_utility import indent


def cmdSoundSettings(scene: OOTScene):
    """Returns C-converted sound settings command"""
    soundSettingsCmd = CData()
    soundSettingsCmd.source = (
        indent + f"SCENE_CMD_SOUND_SETTINGS({scene.audioSessionPreset}, {scene.nightSeq}, {scene.musicSeq}),\n"
    )
    return soundSettingsCmd


def cmdRoomList(scene: OOTScene):
    """Returns C-converted room list command"""
    roomListCmd = CData()
    roomListCmd.source = indent + f"SCENE_CMD_ROOM_LIST({len(scene.rooms)}, {scene.roomListName()}),\n"
    return roomListCmd


def cmdTransiActorList(scene: OOTScene, headerIndex: int):
    """Returns C-converted transition actors list command"""
    transActorListCmd = CData()
    transActorListCmd.source = (
        indent
        + f"SCENE_CMD_TRANSITION_ACTOR_LIST({len(scene.transitionActorList)}, {scene.transitionActorListName(headerIndex)}),\n"
    )
    return transActorListCmd


def cmdMiscSettings(scene: OOTScene):
    """Returns C-converted misc settings command"""
    cmd = CData()
    cmd.source = indent + f"SCENE_CMD_MISC_SETTINGS({scene.cameraMode}, {scene.mapLocation}),\n"
    return cmd


def cmdColHeader(scene: OOTScene):
    """Returns C-converted collision header command"""
    colHeaderCmd = CData()
    colHeaderCmd.source = indent + f"SCENE_CMD_COL_HEADER(&{scene.collision.headerName()}),\n"
    return colHeaderCmd


def cmdEntranceList(scene: OOTScene, headerIndex: int):
    """Returns C-converted entrance list command"""
    entranceListCmd = CData()

    # ``NULL`` if there's no list since this command expects an address
    entranceListName = scene.entranceListName(headerIndex) if len(scene.entranceList) > 0 else "NULL"

    entranceListCmd.source = indent + f"SCENE_CMD_ENTRANCE_LIST({entranceListName}),\n"
    return entranceListCmd


def cmdSpecialFiles(scene: OOTScene):
    """Returns C-converted special files command"""
    # special files are the Navi hint mode and the scene's global object ID
    specialFilesCmd = CData()
    specialFilesCmd.source = indent + f"SCENE_CMD_SPECIAL_FILES({scene.naviCup}, {scene.globalObject})\n"
    return specialFilesCmd


def cmdPathList(scene: OOTScene):
    """Returns C-converted paths list command"""
    pathListCmd = CData()
    pathListCmd.source = indent + f"SCENE_CMD_PATH_LIST({scene.pathListName()}),\n"
    return pathListCmd


def cmdSpawnList(scene: OOTScene, headerIndex: int):
    """Returns C-converted spawns list command"""
    spawnListCmd = CData()
    startPosNumber = len(scene.startPositions)

    # ``NULL`` if there's no list since this command expects an address
    spawnPosName = scene.startPositionsName(headerIndex) if startPosNumber > 0 else "NULL"
    spawnListCmd.source = indent + f"SCENE_CMD_SPAWN_LIST({startPosNumber}, {spawnPosName}),\n"
    return spawnListCmd


def cmdSkyboxSettings(scene: OOTScene):
    """Returns C-converted spawns list command"""
    skySettingsCmd = CData()
    skySettingsCmd.source = (
        indent + f"SCENE_CMD_SKYBOX_SETTINGS({scene.skyboxID}, {scene.skyboxCloudiness}, {scene.skyboxLighting}),\n"
    )
    return skySettingsCmd


def cmdExitList(scene: OOTScene, headerIndex: int):
    """Returns C-converted exit list command"""
    exitListCmd = CData()
    exitListCmd.source = indent + f"SCENE_CMD_EXIT_LIST({scene.exitListName(headerIndex)}),\n"
    return exitListCmd


def cmdLightSettingList(scene: OOTScene, headerIndex: int):
    """Returns C-converted light settings list command"""
    lightSettingListCmd = CData()
    lightCount = len(scene.lights)
    lightSettingsName = scene.lightListName(headerIndex) if lightCount > 0 else "NULL"

    lightSettingListCmd.source = indent + f"SCENE_CMD_ENV_LIGHT_SETTINGS({lightCount}, {lightSettingsName}),\n"
    return lightSettingListCmd


def cmdCutsceneData(scene: OOTScene, headerIndex: int):
    """Returns C-converted cutscene data command"""
    csDataCmd = CData()

    if scene.csWriteType == "Embedded":
        csDataName = scene.cutsceneDataName(headerIndex)
    elif scene.csWriteType == "Object":
        if scene.csWriteObject is not None:
            csDataName = scene.csWriteObject.name  # ``csWriteObject`` type: ``OOTCutscene``
        else:
            raise PluginError("OoT Level to C: ``scene.csWriteObject`` is None!")
    elif scene.csWriteType == "Custom":
        csDataName = scene.csWriteCustom

    csDataCmd.source = indent + f"SCENE_CMD_CUTSCENE_DATA({csDataName}),\n"
    return csDataCmd
