from .....utility import CData, PluginError
from ....oot_level_classes import OOTScene
from ...data import indent


def getSoundSettingsCmd(outScene: OOTScene):
    """Returns C-converted sound settings command"""
    return f"SCENE_CMD_SOUND_SETTINGS({outScene.audioSessionPreset}, {outScene.nightSeq}, {outScene.musicSeq})"


def getRoomListCmd(outScene: OOTScene):
    """Returns C-converted room list command"""
    return f"SCENE_CMD_ROOM_LIST({len(outScene.rooms)}, {outScene.getRoomListName()})"


def getTransActorListCmd(outScene: OOTScene, layerIndex: int):
    """Returns C-converted transition actors list command"""
    cmdArgs = f"{len(outScene.transitionActorList)}, {outScene.getTransActorListName(layerIndex)}"
    return f"SCENE_CMD_TRANSITION_ACTOR_LIST({cmdArgs})"


def getMiscSettingsCmd(outScene: OOTScene):
    """Returns C-converted misc settings command"""
    return f"SCENE_CMD_MISC_SETTINGS({outScene.cameraMode}, {outScene.mapLocation})"


def getColHeaderCmd(outScene: OOTScene):
    """Returns C-converted collision header command"""
    return f"SCENE_CMD_COL_HEADER(&{outScene.collision.headerName()})"


def getSpawnListCmd(outScene: OOTScene, layerIndex: int):
    """Returns C-converted entrance list command"""
    # ``NULL`` if there's no list since this command expects an address
    getSpawnListName = outScene.getSpawnListName(layerIndex) if len(outScene.entranceList) > 0 else "NULL"
    return f"SCENE_CMD_ENTRANCE_LIST({getSpawnListName})"


def getSpecialFilesCmd(outScene: OOTScene):
    """Returns C-converted special files command"""
    # special files are the Navi hint mode and the scene's global object ID
    return f"SCENE_CMD_SPECIAL_FILES({outScene.naviCup}, {outScene.globalObject})"


def getPathListCmd(outScene: OOTScene, layerIndex: int):
    """Returns C-converted paths list command"""
    return f"SCENE_CMD_PATH_LIST({outScene.getPathListName(layerIndex)})"


def getPlayerEntryListCmd(outScene: OOTScene, layerIndex: int):
    """Returns C-converted spawns list command"""
    # ``NULL`` if there's no list since this command expects an address
    startPosNumber = len(outScene.startPositions)
    spawnPosName = outScene.getPlayerEntryListName(layerIndex) if startPosNumber > 0 else "NULL"
    return f"SCENE_CMD_SPAWN_LIST({startPosNumber}, {spawnPosName})"


def getSkyboxSettingsCmd(outScene: OOTScene):
    """Returns C-converted spawns list command"""
    return f"SCENE_CMD_SKYBOX_SETTINGS({outScene.skyboxID}, {outScene.skyboxCloudiness}, {outScene.skyboxLighting})"


def getExitListCmd(outScene: OOTScene, layerIndex: int):
    """Returns C-converted exit list command"""
    return f"SCENE_CMD_EXIT_LIST({outScene.getExitListName(layerIndex)})"


def getLightSettingsCmd(outScene: OOTScene, layerIndex: int):
    """Returns C-converted light settings list command"""
    lightCount = len(outScene.lights)
    lightSettingsName = outScene.getLightSettingsListName(layerIndex) if lightCount > 0 else "NULL"
    return f"SCENE_CMD_ENV_LIGHT_SETTINGS({lightCount}, {lightSettingsName})"


def getCutsceneDataCmd(outScene: OOTScene, layerIndex: int):
    """Returns C-converted cutscene data command"""
    if outScene.csWriteType == "Embedded":
        csDataName = outScene.getCutsceneDataName(layerIndex)
    elif outScene.csWriteType == "Object":
        if outScene.csWriteObject is not None:
            csDataName = outScene.csWriteObject.name  # ``csWriteObject`` type: ``OOTCutscene``
        else:
            raise PluginError("OoT Level to C: ``outScene.csWriteObject`` is None!")
    elif outScene.csWriteType == "Custom":
        csDataName = outScene.csWriteCustom

    return f"SCENE_CMD_CUTSCENE_DATA({csDataName})"


def getSceneCommandsEntries(outScene: OOTScene, layerIndex: int):
    """Returns every scene commands converted to C code."""
    sceneCmdList: list[str] = []

    if outScene.hasAltLayers():
        sceneCmdList.append(outScene.getAltLayersListCmd(outScene.getAltLayersListName()))

    sceneCmdList.append(getSoundSettingsCmd(outScene))
    sceneCmdList.append(getRoomListCmd(outScene))

    if len(outScene.transitionActorList) > 0:
        sceneCmdList.append(getTransActorListCmd(outScene, layerIndex))

    sceneCmdList.append(getMiscSettingsCmd(outScene))
    sceneCmdList.append(getColHeaderCmd(outScene))
    sceneCmdList.append(getSpawnListCmd(outScene, layerIndex))
    sceneCmdList.append(getSpecialFilesCmd(outScene))

    if layerIndex == 0:
        # Note: this will be moved out of the if statement
        # whenever Fast64 handles the different layers for paths
        if len(outScene.pathList) > 0:
            sceneCmdList.append(getPathListCmd(outScene, layerIndex))

    sceneCmdList.append(getPlayerEntryListCmd(outScene, layerIndex))
    sceneCmdList.append(getSkyboxSettingsCmd(outScene))

    if len(outScene.exitList) > 0:
        sceneCmdList.append(getExitListCmd(outScene, layerIndex))

    sceneCmdList.append(getLightSettingsCmd(outScene, layerIndex))

    if outScene.writeCutscene:
        sceneCmdList.append(getCutsceneDataCmd(outScene, layerIndex))

    sceneCmdList.append(outScene.getEndMarkerCmd())

    return sceneCmdList


def convertSceneCommands(outScene: OOTScene, layerIndex: int):
    """Converts every scene commands to C code."""
    sceneCmdData = CData()
    sceneCmdName = f"SCmdBase {outScene.getSceneLayerName(layerIndex)}[]"
    sceneCmdList = getSceneCommandsEntries(outScene, layerIndex)

    # .h
    sceneCmdData.header = f"extern {sceneCmdName};\n"

    # .c
    sceneCmdData.source = (
        sceneCmdName + " = {\n" + ",\n".join([indent + sceneCmd for sceneCmd in sceneCmdList]) + "};\n\n"
    )

    return sceneCmdData
