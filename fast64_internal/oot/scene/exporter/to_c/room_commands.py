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


def getOcclusionPlaneCandidatesListCmd(outRoom: OOTRoom):
    return (
        indent
        + f"SCENE_CMD_OCCLUSION_PLANE_CANDIDATES_LIST({len(outRoom.occlusion_planes.planes)}, {outRoom.occlusion_planes.name})"
    )


def getRoomShapeCmd(outRoom: OOTRoom):
    return indent + f"SCENE_CMD_ROOM_SHAPE(&{outRoom.mesh.headerName()})"


def getObjectListCmd(outRoom: OOTRoom, headerIndex: int):
    return (
        indent + "SCENE_CMD_OBJECT_LIST("
    ) + f"{outRoom.getObjectLengthDefineName(headerIndex)}, {outRoom.objectListName(headerIndex)})"


def getActorListCmd(outRoom: OOTRoom, headerIndex: int):
    return (
        indent + "SCENE_CMD_ACTOR_LIST("
    ) + f"{outRoom.getActorLengthDefineName(headerIndex)}, {outRoom.actorListName(headerIndex)})"


def getRoomCommandList(outRoom: OOTRoom, headerIndex: int):
    cmdListData = CData()
    declarationBase = f"SceneCmd {outRoom.roomName()}_header{headerIndex:02}"

    getCmdFunc1ArgList = [
        getEchoSettingsCmd,
        getRoomBehaviourCmd,
        getSkyboxDisablesCmd,
        getTimeSettingsCmd,
        getRoomShapeCmd,
    ]

    getCmdFunc2ArgList = []

    if outRoom.setWind:
        getCmdFunc1ArgList.append(getWindSettingsCmd)

    if len(outRoom.occlusion_planes.planes) > 0:
        getCmdFunc1ArgList.append(getOcclusionPlaneCandidatesListCmd)

    if len(outRoom.objectIDList) > 0:
        getCmdFunc2ArgList.append(getObjectListCmd)

    if len(outRoom.actorList) > 0:
        getCmdFunc2ArgList.append(getActorListCmd)

    roomCmdData = (
        (outRoom.getAltHeaderListCmd(outRoom.alternateHeadersName()) if outRoom.hasAlternateHeaders() else "")
        + "".join(getCmd(outRoom) + ",\n" for getCmd in getCmdFunc1ArgList)
        + "".join(getCmd(outRoom, headerIndex) + ",\n" for getCmd in getCmdFunc2ArgList)
        + outRoom.getEndCmd()
    )

    # .h
    cmdListData.header = f"extern {declarationBase}[];\n"

    # .c
    cmdListData.source = f"{declarationBase}[]" + " = {\n" + roomCmdData + "};\n\n"

    return cmdListData
