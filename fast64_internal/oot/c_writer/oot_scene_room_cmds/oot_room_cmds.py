from ...oot_level_classes import OOTRoom
from ....utility import CData
from ...oot_utility import indent
from .oot_common_cmds import cmdAltHeaders, cmdEndMarker


def cmdEchoSettings(room: OOTRoom):
    """Returns C-converted room echo settings command"""
    return f"SCENE_CMD_ECHO_SETTINGS({room.echo})"


def cmdRoomBehaviour(room: OOTRoom):
    """Returns C-converted room room behavior command"""
    showInvisibleActors = "true" if room.showInvisibleActors else "false"
    disableWarpSongs = "true" if room.disableWarpSongs else "false"
    return (
        f"SCENE_CMD_ROOM_BEHAVIOR({room.roomBehaviour}, {room.linkIdleMode}, {showInvisibleActors}, {disableWarpSongs})"
    )


def cmdSkyboxDisables(room: OOTRoom):
    """Returns C-converted room skybox state command"""
    disableSkybox = "true" if room.disableSkybox else "false"
    disableSunMoon = "true" if room.disableSunMoon else "false"
    return f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})"


def cmdTimeSettings(room: OOTRoom):
    """Returns C-converted room time settings command"""
    return f"SCENE_CMD_TIME_SETTINGS({room.timeHours}, {room.timeMinutes}, {room.timeSpeed})"


def cmdWindSettings(room: OOTRoom):
    """Returns C-converted room wind settings command"""
    return f"SCENE_CMD_WIND_SETTINGS({room.windVector[0]}, {room.windVector[1]}, {room.windVector[2]}, {room.windStrength})"


def cmdMesh(room: OOTRoom):
    """Returns C-converted room mesh command"""
    return f"SCENE_CMD_ROOM_SHAPE(&{room.mesh.headerName()})"


def cmdObjectList(room: OOTRoom, headerIndex: int):
    """Returns C-converted room object list command"""
    return f"SCENE_CMD_OBJECT_LIST({len(room.objectIDList)}, {room.objectListName(headerIndex)})"


def cmdActorList(room: OOTRoom, headerIndex: int):
    """Returns C-converted room actor list command"""
    return f"SCENE_CMD_ACTOR_LIST({len(room.actorList)}, {room.actorListName(headerIndex)})"


def getRoomCommandsList(room: OOTRoom, headerIndex: int):
    """Returns every room commands converted to C code."""
    roomCmdList: list[str] = []

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

    if len(room.actorList) > 0:
        roomCmdList.append(cmdActorList(room, headerIndex))

    roomCmdList.append(cmdEndMarker())

    return roomCmdList


def ootRoomCommandsToC(room: OOTRoom, headerIndex: int):
    """Converts every room commands to C code."""
    roomCmdData = CData()
    roomCmdName = f"SCmdBase {room.roomHeaderName(headerIndex)}[]"
    roomCmdList = getRoomCommandsList(room, headerIndex)

    # .h
    roomCmdData.header = f"extern {roomCmdName};\n"

    # .c
    roomCmdData.source = roomCmdName + " = {\n" + ",\n".join([indent + roomCmd for roomCmd in roomCmdList]) + "};\n\n"

    return roomCmdData
