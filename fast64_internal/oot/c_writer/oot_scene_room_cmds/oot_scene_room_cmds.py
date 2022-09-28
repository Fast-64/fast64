from ....utility import CData
from ...oot_utility import indent

from ...oot_level_classes import OOTScene, OOTRoom
from .oot_scene_cmds import (
    cmdSoundSettings,
    cmdRoomList,
    cmdTransiActorList,
    cmdMiscSettings,
    cmdColHeader,
    cmdEntranceList,
    cmdSpecialFiles,
    cmdPathList,
    cmdSpawnList,
    cmdSkyboxSettings,
    cmdExitList,
    cmdLightSettingList,
    cmdCutsceneData,
)
from .oot_room_cmds import (
    cmdEchoSettings,
    cmdRoomBehaviour,
    cmdSkyboxDisables,
    cmdTimeSettings,
    cmdWindSettings,
    cmdMesh,
    cmdObjectList,
    cmdActorList,
)


# Common Commands


def cmdAltHeaders(altHeaderName: str):
    altHeaderCmd = CData()
    altHeaderCmd.source = indent + f"SCENE_CMD_ALTERNATE_HEADER_LIST({altHeaderName}),\n"
    return altHeaderCmd


def cmdEndMarker():
    """Returns the end marker command, common to scenes and rooms"""
    # ``SCENE_CMD_END`` defines the end of scene commands
    endCmd = CData()
    endCmd.source = indent + "SCENE_CMD_END(),\n"
    return endCmd


# Getters


def getSceneCommandsList(scene: OOTScene, headerIndex: int):
    sceneCmdList: list[CData] = []

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


def getRoomCommandsList(room: OOTRoom, headerIndex: int):
    roomCmdList: list[CData] = []

    if room.hasAlternateHeaders():
        roomCmdList.append(cmdAltHeaders(room.alternateHeadersName()))

    roomCmdList.append(cmdEchoSettings(room))
    roomCmdList.append(cmdRoomBehaviour(room))
    roomCmdList.append(cmdSkyboxDisables(room))
    roomCmdList.append(cmdTimeSettings(room))

    if room.setWind:
        roomCmdList.append(cmdWindSettings(room))

    roomCmdList.append(cmdMesh(room))

    if len(room.objectIDList) > 0:
        roomCmdList.append(cmdObjectList(room, headerIndex))

    if len(room.actorIDList) > 0:
        roomCmdList.append(cmdActorList(room, headerIndex))

    roomCmdList.append(cmdEndMarker())

    return roomCmdList
