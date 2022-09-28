from ..oot_f3d_writer import *
from ..oot_level_writer import *
from ..oot_collision import *
from ..oot_cutscene import *


def cmdEndMarker():
    """Returns the end marker command, common to scenes and rooms"""
    # ``SCENE_CMD_END`` defines the end of scene commands
    endCmd = CData()
    endCmd.source = indent + "SCENE_CMD_END(),\n"
    return endCmd


# Scene Commands
def cmdSoundSettings(scene: OOTScene):
    """Returns C-converted sound settings command"""
    soundSettingsCmd = CData()
    soundSettingsCmd.source = (
        "\tSCENE_CMD_SOUND_SETTINGS("
        + ", ".join(
            (
                # @bug: ``OOTScene`` type in argument but it doesn't contain ``audioSessionPreset``
                str(scene.audioSessionPreset),
                str(scene.nightSeq),
                str(scene.musicSeq),
            )
        )
        + "),\n"
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


# Room Commands
def cmdAltHeaders(name, altName, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_ALTERNATE_HEADER_LIST(" + altName + "),\n"
    return cmd


def cmdEchoSettings(room, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_ECHO_SETTINGS(" + str(room.echo) + "),\n"
    return cmd


def cmdRoomBehaviour(room, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_ROOM_BEHAVIOR("
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
        "\tSCENE_CMD_SKYBOX_DISABLES("
        + ("true" if room.disableSkybox else "false")
        + ", "
        + ("true" if room.disableSunMoon else "false")
        + "),\n"
    )
    return cmd


def cmdTimeSettings(room, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_TIME_SETTINGS("
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
        "\tSCENE_CMD_WIND_SETTINGS("
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
    cmd.source = "\tSCENE_CMD_ROOM_SHAPE(&" + room.mesh.headerName() + "),\n"
    return cmd


def cmdObjectList(room, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_OBJECT_LIST(" + str(len(room.objectList)) + ", " + str(room.objectListName(header)) + "),\n"
    )
    return cmd


def cmdActorList(room, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_ACTOR_LIST(" + str(len(room.actorList)) + ", " + str(room.actorListName(header)) + "),\n"
    return cmd


def ootObjectListToC(room, headerIndex):
    data = CData()
    data.header = "extern s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectList)) + "];\n"
    data.source = "s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectList)) + "] = {\n"
    for objectItem in room.objectList:
        data.source += "\t" + objectItem + ",\n"
    data.source += "};\n\n"
    return data


def ootActorToC(actor):
    return (
        "{ "
        + ", ".join(
            (
                str(actor.actorID),
                str(int(round(actor.position[0]))),
                str(int(round(actor.position[1]))),
                str(int(round(actor.position[2]))),
                *(
                    (
                        actor.rotOverride[0],
                        actor.rotOverride[1],
                        actor.rotOverride[2],
                    )
                    if actor.rotOverride is not None
                    else (
                        str(int(round(actor.rotation[0]))),
                        str(int(round(actor.rotation[1]))),
                        str(int(round(actor.rotation[2]))),
                    )
                ),
                str(actor.actorParam),
            )
        )
        + " },\n"
    )


def ootActorListToC(room, headerIndex):
    data = CData()
    data.header = "extern ActorEntry " + room.actorListName(headerIndex) + "[" + str(len(room.actorList)) + "];\n"
    data.source = "ActorEntry " + room.actorListName(headerIndex) + "[" + str(len(room.actorList)) + "] = {\n"
    for actor in room.actorList:
        data.source += "\t" + ootActorToC(actor)
    data.source += "};\n\n"
    return data


def ootMeshEntryToC(meshEntry, roomShape):
    opaqueName = meshEntry.DLGroup.opaque.name if meshEntry.DLGroup.opaque is not None else "0"
    transparentName = meshEntry.DLGroup.transparent.name if meshEntry.DLGroup.transparent is not None else "0"
    data = "{ "
    if roomShape == "ROOM_SHAPE_TYPE_IMAGE":
        raise PluginError("Pre-Rendered rooms not supported.")
    elif roomShape == "ROOM_SHAPE_TYPE_CULLABLE":
        data += (
            "{ "
            + f"{meshEntry.cullGroup.position[0]}, {meshEntry.cullGroup.position[1]}, {meshEntry.cullGroup.position[2]}"
            + " }, "
        )
        data += str(meshEntry.cullGroup.cullDepth) + ", "
    data += (
        (opaqueName if opaqueName != "0" else "NULL")
        + ", "
        + (transparentName if transparentName != "0" else "NULL")
        + " },\n"
    )

    return data


def ootRoomMeshToC(room, textureExportSettings):
    mesh = room.mesh
    if len(mesh.meshEntries) == 0:
        raise PluginError("Error: Room " + str(room.index) + " has no mesh children.")

    meshHeader = CData()
    meshHeader.header = f"extern {ootRoomShapeStructs[mesh.roomShape]} {mesh.headerName()};\n"
    meshHeader.source = (
        "\n".join(
            (
                ootRoomShapeStructs[mesh.roomShape] + " " + mesh.headerName() + " = {",
                indent + mesh.roomShape + ",",
                indent + "ARRAY_COUNT(" + mesh.entriesName() + ")" + ",",
                indent + mesh.entriesName() + ",",
                indent + mesh.entriesName() + " + ARRAY_COUNT(" + mesh.entriesName() + ")",
                "};",
            )
        )
        + "\n\n"
    )

    meshEntries = CData()
    meshEntries.header = (
        f"extern {ootRoomShapeEntryStructs[mesh.roomShape]} {mesh.entriesName()}[{str(len(mesh.meshEntries))}];\n"
    )
    meshEntries.source = (
        f"{ootRoomShapeEntryStructs[mesh.roomShape]} {mesh.entriesName()}[{str(len(mesh.meshEntries))}] = " + "{\n"
    )
    meshData = CData()
    for entry in mesh.meshEntries:
        meshEntries.source += "\t" + ootMeshEntryToC(entry, mesh.roomShape)
        if entry.DLGroup.opaque is not None:
            meshData.append(entry.DLGroup.opaque.to_c(mesh.model.f3d))
        if entry.DLGroup.transparent is not None:
            meshData.append(entry.DLGroup.transparent.to_c(mesh.model.f3d))
    meshEntries.source += "};\n\n"
    exportData = mesh.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))

    meshData.append(exportData.all())
    meshHeader.append(meshEntries)

    return meshHeader, meshData


def ootRoomCommandsToC(room, headerIndex):
    commands = []
    if room.hasAlternateHeaders():
        commands.append(cmdAltHeaders(room.roomName(), room.alternateHeadersName(), headerIndex, len(commands)))
    commands.append(cmdEchoSettings(room, headerIndex, len(commands)))
    commands.append(cmdRoomBehaviour(room, headerIndex, len(commands)))
    commands.append(cmdSkyboxDisables(room, headerIndex, len(commands)))
    commands.append(cmdTimeSettings(room, headerIndex, len(commands)))
    if room.setWind:
        commands.append(cmdWindSettings(room, headerIndex, len(commands)))
    commands.append(cmdMesh(room, headerIndex, len(commands)))
    if len(room.objectList) > 0:
        commands.append(cmdObjectList(room, headerIndex, len(commands)))
    if len(room.actorList) > 0:
        commands.append(cmdActorList(room, headerIndex, len(commands)))
    commands.append(cmdEndMarker())

    data = CData()

    # data.header = ''.join([command.header for command in commands]) +'\n'
    data.header = "extern SCmdBase " + room.roomName() + "_header" + format(headerIndex, "02") + "[];\n"

    data.source = "SCmdBase " + room.roomName() + "_header" + format(headerIndex, "02") + "[] = {\n"
    data.source += "".join([command.source for command in commands])
    data.source += "};\n\n"

    return data


def ootAlternateRoomMainToC(scene, room):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SCmdBase* " + room.alternateHeadersName() + "[];\n"
    altHeader.source = "SCmdBase* " + room.alternateHeadersName() + "[] = {\n"

    if room.childNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.childNightHeader, 1))
    else:
        altHeader.source += "\t0,\n"

    if room.adultDayHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultDayHeader, 2))
    else:
        altHeader.source += "\t0,\n"

    if room.adultNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultNightHeader, 3))
    else:
        altHeader.source += "\t0,\n"

    for i in range(len(room.cutsceneHeaders)):
        altHeader.source += "\t" + room.roomName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootRoomMainToC(scene, room, headerIndex):
    roomMainC = CData()

    if room.hasAlternateHeaders():
        altHeader, altData = ootAlternateRoomMainToC(scene, room)
    else:
        altHeader = CData()
        altData = CData()

    roomMainC.append(ootRoomCommandsToC(room, headerIndex))
    roomMainC.append(altHeader)
    if len(room.objectList) > 0:
        roomMainC.append(ootObjectListToC(room, headerIndex))
    if len(room.actorList) > 0:
        roomMainC.append(ootActorListToC(room, headerIndex))
    roomMainC.append(altData)

    return roomMainC


def ootSceneCommandsToC(scene: OOTScene, headerIndex: int):
    commands = []
    if scene.hasAlternateHeaders():
        commands.append(cmdAltHeaders(scene.sceneName(), scene.alternateHeadersName(), headerIndex, len(commands)))

    commands.append(cmdSoundSettings(scene))
    commands.append(cmdRoomList(scene))

    if len(scene.transitionActorList) > 0:
        commands.append(cmdTransiActorList(scene, headerIndex))

    commands.append(cmdMiscSettings(scene))
    commands.append(cmdColHeader(scene))
    commands.append(cmdEntranceList(scene, headerIndex))
    commands.append(cmdSpecialFiles(scene))

    if len(scene.pathList) > 0:
        commands.append(cmdPathList(scene))

    commands.append(cmdSpawnList(scene, headerIndex))
    commands.append(cmdSkyboxSettings(scene))

    if len(scene.exitList) > 0:
        commands.append(cmdExitList(scene, headerIndex))

    commands.append(cmdLightSettingList(scene, headerIndex))

    if scene.writeCutscene:
        commands.append(cmdCutsceneData(scene, headerIndex))

    commands.append(cmdEndMarker())

    data = CData()

    # data.header = ''.join([command.header for command in commands]) +'\n'
    data.header = "extern SCmdBase " + scene.sceneName() + "_header" + format(headerIndex, "02") + "[];\n"

    data.source = "SCmdBase " + scene.sceneName() + "_header" + format(headerIndex, "02") + "[] = {\n"
    data.source += "".join([command.source for command in commands])
    data.source += "};\n\n"

    return data


def ootStartPositionListToC(scene, headerIndex):
    data = CData()
    data.header = "extern ActorEntry " + scene.startPositionsName(headerIndex) + "[];\n"
    data.source = "ActorEntry " + scene.startPositionsName(headerIndex) + "[] = {\n"
    for i in range(len(scene.startPositions)):
        data.source += "\t" + ootActorToC(scene.startPositions[i])
    data.source += "};\n\n"
    return data


def ootTransitionActorToC(transActor):
    return (
        "{ "
        + ", ".join(
            (
                str(transActor.frontRoom),
                str(transActor.frontCam),
                str(transActor.backRoom),
                str(transActor.backCam),
                str(transActor.actorID),
                str(int(round(transActor.position[0]))),
                str(int(round(transActor.position[1]))),
                str(int(round(transActor.position[2]))),
                str(int(round(transActor.rotationY))),
                str(transActor.actorParam),
            )
        )
        + " },\n"
    )


def ootTransitionActorListToC(scene, headerIndex):
    data = CData()
    data.header = (
        "extern TransitionActorEntry "
        + scene.transitionActorListName(headerIndex)
        + "["
        + str(len(scene.transitionActorList))
        + "];\n"
    )
    data.source = (
        "TransitionActorEntry "
        + scene.transitionActorListName(headerIndex)
        + "["
        + str(len(scene.transitionActorList))
        + "] = {\n"
    )
    for transActor in scene.transitionActorList:
        data.source += "\t" + ootTransitionActorToC(transActor)
    data.source += "};\n\n"
    return data


def ootRoomExternToC(room):
    return ("extern u8 _" + room.roomName() + "SegmentRomStart[];\n") + (
        "extern u8 _" + room.roomName() + "SegmentRomEnd[];\n"
    )


def ootRoomListEntryToC(room):
    return "{ (u32)_" + room.roomName() + "SegmentRomStart, (u32)_" + room.roomName() + "SegmentRomEnd },\n"


def ootRoomListHeaderToC(scene):
    data = CData()

    data.header += "extern RomFile " + scene.roomListName() + "[];\n"

    if scene.write_dummy_room_list:
        data.source += "// Dummy room list\n"
        data.source += "RomFile " + scene.roomListName() + "[] = {\n"
        data.source += "\t{0, 0},\n" * len(scene.rooms)
        data.source += "};\n\n"
    else:
        # Write externs for rom segments
        for i in range(len(scene.rooms)):
            data.source += ootRoomExternToC(scene.rooms[i])
        data.source += "\n"

        data.source += "RomFile " + scene.roomListName() + "[] = {\n"

        for i in range(len(scene.rooms)):
            data.source += "\t" + ootRoomListEntryToC(scene.rooms[i])
        data.source += "};\n\n"

    return data


def ootEntranceToC(entrance):
    return "{ " + str(entrance.startPositionIndex) + ", " + str(entrance.roomIndex) + " },\n"


def ootEntranceListToC(scene, headerIndex):
    data = CData()
    data.header = "extern EntranceEntry " + scene.entranceListName(headerIndex) + "[];\n"
    data.source = "EntranceEntry " + scene.entranceListName(headerIndex) + "[] = {\n"
    for entrance in scene.entranceList:
        data.source += "\t" + ootEntranceToC(entrance)
    data.source += "};\n\n"
    return data


def ootExitListToC(scene, headerIndex):
    data = CData()
    data.header = "extern u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "];\n"
    data.source = "u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "] = {\n"
    for exitEntry in scene.exitList:
        data.source += "\t" + str(exitEntry.index) + ",\n"
    data.source += "};\n\n"
    return data


def ootVectorToC(vector):
    return "0x{:02X}, 0x{:02X}, 0x{:02X}".format(vector[0], vector[1], vector[2])


def ootLightToC(light):
    return (
        "\t{ "
        + ", ".join(
            (
                ootVectorToC(light.ambient),
                ootVectorToC(light.diffuseDir0),
                ootVectorToC(light.diffuse0),
                ootVectorToC(light.diffuseDir1),
                ootVectorToC(light.diffuse1),
                ootVectorToC(light.fogColor),
                light.getBlendFogShort(),
                "0x{:04X}".format(light.fogFar),
            )
        )
        + " },\n"
    )


def ootLightSettingsToC(scene, useIndoorLighting, headerIndex):
    data = CData()
    lightArraySize = len(scene.lights)
    data.header = "extern LightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "];\n"
    data.source = "LightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "] = {\n"
    for light in scene.lights:
        data.source += ootLightToC(light)
    data.source += "};\n\n"
    return data


def ootPathToC(path):
    data = CData()
    data.header = "extern Vec3s " + path.pathName() + "[];\n"
    data.source = "Vec3s " + path.pathName() + "[] = {\n"
    for point in path.points:
        data.source += (
            "\t"
            + "{ "
            + str(int(round(point[0])))
            + ", "
            + str(int(round(point[1])))
            + ", "
            + str(int(round(point[2])))
            + " },\n"
        )
    data.source += "};\n\n"

    return data


def ootPathListToC(scene):
    data = CData()
    data.header = "extern Path " + scene.pathListName() + "[" + str(len(scene.pathList)) + "];\n"
    data.source = "Path " + scene.pathListName() + "[" + str(len(scene.pathList)) + "] = {\n"
    pathData = CData()
    for i in range(len(scene.pathList)):
        path = scene.pathList[i]
        data.source += "\t" + "{ " + str(len(path.points)) + ", " + path.pathName() + " },\n"
        pathData.append(ootPathToC(path))
    data.source += "};\n\n"
    pathData.append(data)
    return pathData


def ootSceneMeshToC(scene, textureExportSettings):
    exportData = scene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))
    return exportData.all()


def ootSceneIncludes(scene):
    data = CData()
    data.source += '#include "ultra64.h"\n'
    data.source += '#include "z64.h"\n'
    data.source += '#include "macros.h"\n'
    data.source += '#include "' + scene.sceneName() + '.h"\n\n'
    data.source += '#include "segment_symbols.h"\n'
    data.source += '#include "command_macros_base.h"\n'
    data.source += '#include "z64cutscene_commands.h"\n'
    data.source += '#include "variables.h"\n'
    data.source += "\n"
    return data


def ootAlternateSceneMainToC(scene):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SCmdBase* " + scene.alternateHeadersName() + "[];\n"
    altHeader.source = "SCmdBase* " + scene.alternateHeadersName() + "[] = {\n"

    if scene.childNightHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.childNightHeader, 1))
    else:
        altHeader.source += "\t0,\n"

    if scene.adultDayHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultDayHeader, 2))
    else:
        altHeader.source += "\t0,\n"

    if scene.adultNightHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultNightHeader, 3))
    else:
        altHeader.source += "\t0,\n"

    for i in range(len(scene.cutsceneHeaders)):
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootSceneMainToC(scene, headerIndex):
    sceneMainC = CData()

    if headerIndex == 0:
        # Check if this is the first time the function is being called, we do not want to write this data multiple times
        roomHeaderData = ootRoomListHeaderToC(scene)
        if len(scene.pathList) > 0:
            pathData = ootPathListToC(scene)
        else:
            pathData = CData()
    else:
        # The function has already been called (and is being called for another scene header), so we can make this data be a blank string
        roomHeaderData = CData()
        pathData = CData()

    if scene.hasAlternateHeaders():
        # Gets the alternate data for the scene's main c file
        altHeader, altData = ootAlternateSceneMainToC(scene)
    else:
        # Since the scene does not use alternate headers, this data can just be a blank string
        altHeader = CData()
        altData = CData()

    # Write the scene header
    sceneMainC.append(ootSceneCommandsToC(scene, headerIndex))

    # Write alternate scene headers
    sceneMainC.append(altHeader)

    # Write the spawn position list data
    if len(scene.startPositions) > 0:
        sceneMainC.append(ootStartPositionListToC(scene, headerIndex))

    # Write the transition actor list data
    if len(scene.transitionActorList) > 0:
        sceneMainC.append(ootTransitionActorListToC(scene, headerIndex))

    # Write the room segment list
    sceneMainC.append(roomHeaderData)

    # Write the entrance list
    if len(scene.entranceList) > 0:
        sceneMainC.append(ootEntranceListToC(scene, headerIndex))

    # Write the exit list
    if len(scene.exitList) > 0:
        sceneMainC.append(ootExitListToC(scene, headerIndex))

    # Write the light data
    if len(scene.lights) > 0:
        sceneMainC.append(ootLightSettingsToC(scene, scene.skyboxLighting == "0x01", headerIndex))

    # Write the path data, if used
    sceneMainC.append(pathData)

    # Write the data from alternate headers
    sceneMainC.append(altData)

    return sceneMainC


# Writes the textures and material setup displaylists that are shared between multiple rooms (is written to the scene)
def ootSceneTexturesToC(scene, textureExportSettings):
    sceneTextures = CData()
    sceneTextures.append(ootSceneMeshToC(scene, textureExportSettings))
    return sceneTextures


# Writes the collision data for a scene
def ootSceneCollisionToC(scene):
    sceneCollisionC = CData()
    sceneCollisionC.append(ootCollisionToC(scene.collision))
    return sceneCollisionC


# scene is either None or an OOTScene. This can either be the main scene itself,
# or one of the alternate / cutscene headers.
def ootGetCutsceneC(scene, headerIndex):
    if scene is not None and scene.writeCutscene:
        if scene.csWriteType == "Embedded":
            return [ootCutsceneDataToC(scene, scene.cutsceneDataName(headerIndex))]
        elif scene.csWriteType == "Object":
            return [ootCutsceneDataToC(scene.csWriteObject, scene.csWriteObject.name)]
    return []


def ootSceneCutscenesToC(scene):
    sceneCutscenes = ootGetCutsceneC(scene, 0)
    sceneCutscenes.extend(ootGetCutsceneC(scene.childNightHeader, 1))
    sceneCutscenes.extend(ootGetCutsceneC(scene.adultDayHeader, 2))
    sceneCutscenes.extend(ootGetCutsceneC(scene.adultNightHeader, 3))

    for i in range(len(scene.cutsceneHeaders)):
        sceneCutscenes.extend(ootGetCutsceneC(scene.cutsceneHeaders[i], i + 4))
    for ec in scene.extraCutscenes:
        sceneCutscenes.append(ootCutsceneDataToC(ec, ec.name))

    return sceneCutscenes


def ootLevelToC(scene, textureExportSettings):
    levelC = OOTLevelC()

    levelC.sceneMainC = ootSceneMainToC(scene, 0)
    levelC.sceneTexturesC = ootSceneTexturesToC(scene, textureExportSettings)
    levelC.sceneCollisionC = ootSceneCollisionToC(scene)
    levelC.sceneCutscenesC = ootSceneCutscenesToC(scene)

    for i in range(len(scene.rooms)):
        levelC.roomMainC[scene.rooms[i].roomName()] = ootRoomMainToC(scene, scene.rooms[i], 0)
        meshHeader, meshData = ootRoomMeshToC(scene.rooms[i], textureExportSettings)
        levelC.roomMeshInfoC[scene.rooms[i].roomName()] = meshHeader
        levelC.roomMeshC[scene.rooms[i].roomName()] = meshData
    return levelC


class OOTLevelC:
    def sceneTexturesIsUsed(self):
        return len(self.sceneTexturesC.source) > 0

    def sceneCutscenesIsUsed(self):
        return len(self.sceneCutscenesC) > 0

    def __init__(self):
        # Main header file for both the scene and room(s)
        self.header = CData()
        # Files for the scene segment
        self.sceneMainC = CData()
        self.sceneTexturesC = CData()
        self.sceneCollisionC = CData()
        self.sceneCutscenesC = []
        # Files for room segments
        self.roomMainC = {}
        self.roomMeshInfoC = {}
        self.roomMeshC = {}
