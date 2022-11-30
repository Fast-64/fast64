from .....utility import CData, indent
from ....oot_level_classes import OOTScene
from ....oot_utility import getCustomProperty


def getSoundSettingsCmd(outScene: OOTScene):
    return indent + f"SCENE_CMD_SOUND_SETTINGS({outScene.audioSessionPreset}, {outScene.nightSeq}, {outScene.musicSeq})"


def getRoomListCmd(outScene: OOTScene):
    return indent + f"SCENE_CMD_ROOM_LIST({len(outScene.rooms)}, {outScene.roomListName()})"


def getTransActorListCmd(outScene: OOTScene, headerIndex: int):
    return (
        indent + "SCENE_CMD_TRANSITION_ACTOR_LIST("
    ) + f"{len(outScene.transitionActorList)}, {outScene.transitionActorListName(headerIndex)})"


def getMiscSettingsCmd(outScene: OOTScene):
    return indent + f"SCENE_CMD_MISC_SETTINGS({outScene.cameraMode}, {outScene.mapLocation})"


def getColHeaderCmd(outScene: OOTScene):
    return indent + f"SCENE_CMD_COL_HEADER(&{outScene.collision.headerName()})"


def getSpawnListCmd(outScene: OOTScene, headerIndex: int):
    return (
        indent + "SCENE_CMD_ENTRANCE_LIST("
    ) + f"{outScene.entranceListName(headerIndex) if len(outScene.entranceList) > 0 else 'NULL'})"


def getSpecialFilesCmd(outScene: OOTScene):
    return indent + f"SCENE_CMD_SPECIAL_FILES({outScene.naviCup}, {outScene.globalObject})"


def getPathListCmd(outScene: OOTScene, headerIndex: int):
    return indent + f"SCENE_CMD_PATH_LIST({outScene.pathListName(headerIndex)})"


def getSpawnActorListCmd(outScene: OOTScene, headerIndex: int):
    return (
        (indent + "SCENE_CMD_SPAWN_LIST(")
        + f"{len(outScene.startPositions)}, "
        + f"{outScene.startPositionsName(headerIndex) if len(outScene.startPositions) > 0 else 'NULL'})"
    )


def getSkyboxSettingsCmd(outScene: OOTScene):
    return (
        indent
        + f"SCENE_CMD_SKYBOX_SETTINGS({outScene.skyboxID}, {outScene.skyboxCloudiness}, {outScene.skyboxLighting})"
    )


def getExitListCmd(outScene: OOTScene, headerIndex: int):
    return indent + f"SCENE_CMD_EXIT_LIST({outScene.exitListName(headerIndex)})"


def getLightSettingsCmd(outScene: OOTScene, headerIndex: int):
    return (
        indent + "SCENE_CMD_ENV_LIGHT_SETTINGS("
    ) + f"{len(outScene.lights)}, {outScene.lightListName(headerIndex) if len(outScene.lights) > 0 else 'NULL'})"


def getCutsceneDataCmd(outScene: OOTScene, headerIndex: int):
    match outScene.csWriteType:
        case "Embedded":
            csDataName = outScene.cutsceneDataName(headerIndex)
        case "Object":
            csDataName = outScene.csWriteObject.name
        case _:
            csDataName = outScene.csWriteCustom

    return f"SCENE_CMD_CUTSCENE_DATA({csDataName})"


def getSceneCommandList(outScene: OOTScene, headerIndex: int):
    cmdListData = CData()
    listName = f"SceneCmd {outScene.sceneName()}_header{headerIndex:02}"

    getCmdFunc1ArgList = [
        getSoundSettingsCmd,
        getRoomListCmd,
        getMiscSettingsCmd,
        getColHeaderCmd,
        getSpecialFilesCmd,
        getSkyboxSettingsCmd,
    ]

    getCmdFunc2ArgList = [getSpawnListCmd, getSpawnActorListCmd, getLightSettingsCmd]

    if len(outScene.transitionActorList) > 0:
        getCmdFunc2ArgList.append(getTransActorListCmd)

    if len(outScene.pathList) > 0:
        getCmdFunc2ArgList.append(getPathListCmd)

    if len(outScene.exitList) > 0:
        getCmdFunc2ArgList.append(getExitListCmd)

    if outScene.writeCutscene:
        getCmdFunc2ArgList.append(getCutsceneDataCmd)

    sceneCmdData = (
        (outScene.getAltHeaderListCmd(outScene.alternateHeadersName()) if outScene.hasAlternateHeaders() else "")
        + (",\n".join(getCmd(outScene) for getCmd in getCmdFunc1ArgList) + ",\n")
        + (",\n".join(getCmd(outScene, headerIndex) for getCmd in getCmdFunc2ArgList) + ",\n")
        + outScene.getEndCmd()
    )

    # .h
    cmdListData.header = f"extern {listName}[]" + ";\n"

    # .c
    cmdListData.source = f"{listName}[]" + " = {\n" + sceneCmdData + "};\n\n"

    return cmdListData
