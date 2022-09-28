from ....utility import CData

from ...oot_level_classes import OOTRoom
from ...oot_utility import indent


def cmdEchoSettings(room: OOTRoom):
    """Returns C-converted room echo settings command"""
    echoSettingsCmd = CData()
    echoSettingsCmd.source = indent + f"SCENE_CMD_ECHO_SETTINGS({room.echo}),\n"
    return echoSettingsCmd


def cmdRoomBehaviour(room: OOTRoom):
    """Returns C-converted room room behavior command"""
    roomBehaviorCmd = CData()
    showInvisibleActors = "true" if room.showInvisibleActors else "false"
    disableWarpSongs = "true" if room.disableWarpSongs else "false"

    roomBehaviorCmd.source = (
        indent
        + f"SCENE_CMD_ROOM_BEHAVIOR({room.roomBehaviour}, {room.linkIdleMode}, {showInvisibleActors}, {disableWarpSongs}),\n"
    )
    return roomBehaviorCmd


def cmdSkyboxDisables(room: OOTRoom):
    """Returns C-converted room skybox state command"""
    skyboxDisableCmd = CData()
    disableSkybox = "true" if room.disableSkybox else "false"
    disableSunMoon = "true" if room.disableSunMoon else "false"

    skyboxDisableCmd.source = indent + f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon}),\n"
    return skyboxDisableCmd


def cmdTimeSettings(room: OOTRoom):
    """Returns C-converted room time settings command"""
    timeSettingsCmd = CData()
    timeSettingsCmd.source = (
        indent + f"SCENE_CMD_TIME_SETTINGS({room.timeHours}, {room.timeMinutes}, {room.timeSpeed}),\n"
    )
    return timeSettingsCmd


def cmdWindSettings(room: OOTRoom):
    """Returns C-converted room wind settings command"""
    windSettingsCmd = CData()
    windSettingsCmd.source = (
        indent
        + f"SCENE_CMD_WIND_SETTINGS({room.windVector[0]}, {room.windVector[1]}, {room.windVector[2]}, {room.windStrength}),\n"
    )
    return windSettingsCmd


def cmdMesh(room: OOTRoom):
    """Returns C-converted room mesh command"""
    meshCmd = CData()
    meshCmd.source = indent + f"SCENE_CMD_ROOM_SHAPE(&{room.mesh.headerName()}),\n"
    return meshCmd


def cmdObjectList(room: OOTRoom, headerIndex: int):
    """Returns C-converted room object list command"""
    objListCmd = CData()
    objListCmd.source = (
        indent + f"SCENE_CMD_OBJECT_LIST({len(room.objectIDList)}, {room.objectListName(headerIndex)}),\n"
    )
    return objListCmd


def cmdActorList(room: OOTRoom, headerIndex: int):
    """Returns C-converted room actor list command"""
    actorListCmd = CData()
    actorListCmd.source = (
        indent + f"SCENE_CMD_ACTOR_LIST({len(room.actorIDList)}, {room.actorListName(headerIndex)}),\n"
    )
    return actorListCmd
