from .....utility import CData, indent
from ....oot_level_classes import OOTRoom


def cmdEchoSettings(room, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_ECHO_SETTINGS(" + str(room.echo) + "),\n"
    return cmd


def cmdRoomBehaviour(room, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_ROOM_BEHAVIOR("
        + ", ".join(
            (
                str(room.roomBehaviour),
                str(room.linkIdleMode),
                ("true" if room.showInvisibleActors else "false"),
                ("true" if room.disableWarpSongs else "false"),
            )
        )
        + "),\n"
    )
    return cmd


def cmdSkyboxDisables(room, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_SKYBOX_DISABLES("
        + ("true" if room.disableSkybox else "false")
        + ", "
        + ("true" if room.disableSunMoon else "false")
        + "),\n"
    )
    return cmd


def cmdTimeSettings(room, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_TIME_SETTINGS("
        + ", ".join(
            (
                str(room.timeHours),
                str(room.timeMinutes),
                str(room.timeSpeed),
            )
        )
        + "),\n"
    )
    return cmd


def cmdWindSettings(room, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_WIND_SETTINGS("
        + ", ".join(
            (
                str(room.windVector[0]),
                str(room.windVector[1]),
                str(room.windVector[2]),
                str(room.windStrength),
            )
        )
        + "),\n"
    )
    return cmd


def cmdMesh(room, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_ROOM_SHAPE(&" + room.mesh.headerName() + "),\n"
    return cmd


def cmdObjectList(room: OOTRoom, headerIndex: int, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_OBJECT_LIST("
        + room.getObjectLengthDefineName(headerIndex)
        + ", "
        + str(room.objectListName(headerIndex))
        + "),\n"
    )
    return cmd


def cmdActorList(room: OOTRoom, headerIndex: int, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_ACTOR_LIST("
        + room.getActorLengthDefineName(headerIndex)
        + ", "
        + str(room.actorListName(headerIndex))
        + "),\n"
    )
    return cmd


def ootRoomCommandsToC(room, headerIndex):
    commands = []
    if room.hasAlternateHeaders():
        commands.append(room.cmdAltHeaders(room.roomName(), room.alternateHeadersName(), headerIndex, len(commands)))
    commands.append(cmdEchoSettings(room, headerIndex, len(commands)))
    commands.append(cmdRoomBehaviour(room, headerIndex, len(commands)))
    commands.append(cmdSkyboxDisables(room, headerIndex, len(commands)))
    commands.append(cmdTimeSettings(room, headerIndex, len(commands)))
    if room.setWind:
        commands.append(cmdWindSettings(room, headerIndex, len(commands)))
    commands.append(cmdMesh(room, headerIndex, len(commands)))
    if len(room.objectIDList) > 0:
        commands.append(cmdObjectList(room, headerIndex, len(commands)))
    if len(room.actorList) > 0:
        commands.append(cmdActorList(room, headerIndex, len(commands)))
    commands.append(room.cmdEndMarker(room.roomName(), headerIndex, len(commands)))

    data = CData()

    # data.header = ''.join([command.header for command in commands]) +'\n'
    data.header = "extern SceneCmd " + room.roomName() + "_header" + format(headerIndex, "02") + "[];\n"

    data.source = "SceneCmd " + room.roomName() + "_header" + format(headerIndex, "02") + "[] = {\n"
    data.source += "".join([command.source for command in commands])
    data.source += "};\n\n"

    return data
