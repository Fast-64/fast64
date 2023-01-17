from .....utility import CData, indent
from ....oot_level_classes import OOTRoom


def getEchoSettingsCmd(outRoom: OOTRoom):
    return indent + f"SCENE_CMD_ECHO_SETTINGS({outRoom.echo})"


def getRoomBehaviourCmd(outRoom: OOTRoom):
    showInvisibleActors = "true" if outRoom.showInvisibleActors else "false"
    disableWarpSongs = "true" if outRoom.disableWarpSongs else "false"

    return (
        (indent + "SCENE_CMD_ROOM_BEHAVIOR(")
        + ", ".join([outRoom.roomBehaviour, outRoom.linkIdleMode, showInvisibleActors, disableWarpSongs])
        + ")"
    )


def getSkyboxDisablesCmd(outRoom: OOTRoom):
    disableSkybox = "true" if outRoom.disableSkybox else "false"
    disableSunMoon = "true" if outRoom.disableSunMoon else "false"

    return indent + f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})"


def getTimeSettingsCmd(outRoom: OOTRoom):
    return indent + f"SCENE_CMD_TIME_SETTINGS({outRoom.timeHours}, {outRoom.timeMinutes}, {outRoom.timeSpeed})"


def getWindSettingsCmd(outRoom: OOTRoom):
    return (
        indent
        + f"SCENE_CMD_WIND_SETTINGS({', '.join(f'{dir}' for dir in outRoom.windVector)}, {outRoom.windStrength}),\n"
    )


def getRoomShapeCmd(outRoom: OOTRoom):
    return indent + f"SCENE_CMD_ROOM_SHAPE(&{outRoom.mesh.headerName()})"


def getObjectListCmd(outRoom: OOTRoom, headerIndex: int):
    return (
        indent + "SCENE_CMD_OBJECT_LIST("
    ) + f"{outRoom.getObjectLengthDefineName(headerIndex)}, {outRoom.objectListName(headerIndex)}),\n"


def getActorListCmd(outRoom: OOTRoom, headerIndex: int):
    return (
        indent + "SCENE_CMD_ACTOR_LIST("
    ) + f"{outRoom.getActorLengthDefineName(headerIndex)}, {outRoom.actorListName(headerIndex)}),\n"


def getRoomCommandList(outRoom: OOTRoom, headerIndex: int):
    cmdListData = CData()
    listName = f"SceneCmd {outRoom.roomName()}_header{headerIndex:02}"

    getCmdFuncList = [
        getEchoSettingsCmd,
        getRoomBehaviourCmd,
        getSkyboxDisablesCmd,
        getTimeSettingsCmd,
        getRoomShapeCmd,
    ]

    roomCmdData = (
        (outRoom.getAltHeaderListCmd(outRoom.alternateHeadersName()) if outRoom.hasAlternateHeaders() else "")
        + (",\n".join(getCmd(outRoom) for getCmd in getCmdFuncList) + ",\n")
        + (getWindSettingsCmd(outRoom) if outRoom.setWind else "")
        + (getObjectListCmd(outRoom, headerIndex) if len(outRoom.objectIDList) > 0 else "")
        + (getActorListCmd(outRoom, headerIndex) if len(outRoom.actorList) > 0 else "")
        + outRoom.getEndCmd()
    )

    # .h
    cmdListData.header = f"extern {listName}[];\n"

    # .c
    cmdListData.source = f"{listName}[]" + " = {\n" + roomCmdData + "};\n\n"

    return cmdListData
