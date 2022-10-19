from .....utility import CData
from ....oot_level_classes import OOTRoom
from ...data import indent


def getEchoSettingsCmd(outRoom: OOTRoom):
    """Returns C-converted room echo settings command"""
    return f"SCENE_CMD_ECHO_SETTINGS({outRoom.echo})"


def getRoomBehaviorCmd(outRoom: OOTRoom):
    """Returns C-converted room room behavior command"""
    showInvisibleActors = "true" if outRoom.showInvisibleActors else "false"
    disableWarpSongs = "true" if outRoom.disableWarpSongs else "false"
    return f"SCENE_CMD_ROOM_BEHAVIOR({outRoom.roomBehaviour}, {outRoom.linkIdleMode}, {showInvisibleActors}, {disableWarpSongs})"


def getSkyboxDisablesCmd(outRoom: OOTRoom):
    """Returns C-converted room skybox state command"""
    disableSkybox = "true" if outRoom.disableSkybox else "false"
    disableSunMoon = "true" if outRoom.disableSunMoon else "false"
    return f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})"


def getTimeSettingsCmd(outRoom: OOTRoom):
    """Returns C-converted room time settings command"""
    return f"SCENE_CMD_TIME_SETTINGS({outRoom.timeHours}, {outRoom.timeMinutes}, {outRoom.timeSpeed})"


def getWindSettingsCmd(outRoom: OOTRoom):
    """Returns C-converted room wind settings command"""
    return f"SCENE_CMD_WIND_SETTINGS({outRoom.windVector[0]}, {outRoom.windVector[1]}, {outRoom.windVector[2]}, {outRoom.windStrength})"


def getRoomShapeCmd(outRoom: OOTRoom):
    """Returns C-converted room mesh command"""
    return f"SCENE_CMD_ROOM_SHAPE(&{outRoom.mesh.headerName()})"


def getObjectListCmd(outRoom: OOTRoom, layerIndex: int):
    """Returns C-converted room object list command"""
    return f"SCENE_CMD_OBJECT_LIST({len(outRoom.objectIDList)}, {outRoom.getObjectListName(layerIndex)})"


def getActorListCmd(outRoom: OOTRoom, layerIndex: int):
    """Returns C-converted room actor list command"""
    return f"SCENE_CMD_ACTOR_LIST({len(outRoom.actorList)}, {outRoom.getActorListName(layerIndex)})"


def getRoomCommandsEntries(outRoom: OOTRoom, layerIndex: int):
    """Returns every room commands converted to C code."""
    roomCmdList: list[str] = []

    if outRoom.hasAltLayers():
        roomCmdList.append(outRoom.getAltLayersListCmd(outRoom.getAltLayersListName()))

    roomCmdList.append(getEchoSettingsCmd(outRoom))
    roomCmdList.append(getRoomBehaviorCmd(outRoom))
    roomCmdList.append(getSkyboxDisablesCmd(outRoom))
    roomCmdList.append(getTimeSettingsCmd(outRoom))

    if outRoom.setWind:
        roomCmdList.append(getWindSettingsCmd(outRoom))

    roomCmdList.append(getRoomShapeCmd(outRoom))

    if len(outRoom.objectIDList) > 0:
        roomCmdList.append(getObjectListCmd(outRoom, layerIndex))

    if len(outRoom.actorList) > 0:
        roomCmdList.append(getActorListCmd(outRoom, layerIndex))

    roomCmdList.append(outRoom.getEndMarkerCmd())

    return roomCmdList


def convertRoomCommands(outRoom: OOTRoom, layerIndex: int):
    """Converts every room commands to C code."""
    roomCmdData = CData()
    roomCmdName = f"SCmdBase {outRoom.getRoomLayerName(layerIndex)}[]"
    roomCmdList = getRoomCommandsEntries(outRoom, layerIndex)

    # .h
    roomCmdData.header = f"extern {roomCmdName};\n"

    # .c
    roomCmdData.source = roomCmdName + " = {\n" + ",\n".join([indent + roomCmd for roomCmd in roomCmdList]) + "};\n\n"

    return roomCmdData
