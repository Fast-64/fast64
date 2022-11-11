from ...utility import CData, PluginError
from ...f3d.f3d_gbi import ScrollMethod, TextureExportSettings
from ..oot_f3d_writer import OOTGfxFormatter
from ..oot_collision import ootCollisionToC
from ..oot_cutscene import ootCutsceneDataToC
from ..oot_utility import indent
from ..oot_constants import ootRoomShapeStructs, ootRoomShapeEntryStructs, ootEnumRoomShapeType
from ..oot_level_classes import OOTRoom, OOTRoomMeshGroup, OOTRoomMesh


def cmdName(name, header, index):
    return name + "_header" + format(header, "02") + "_cmd" + format(index, "02")


# Scene Commands
def cmdSoundSettings(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_SOUND_SETTINGS("
        + ", ".join(
            (
                str(scene.audioSessionPreset),
                str(scene.nightSeq),
                str(scene.musicSeq),
            )
        )
        + "),\n"
    )
    return cmd


def cmdRoomList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_ROOM_LIST(" + str(len(scene.rooms)) + ", " + scene.roomListName() + "),\n"
    return cmd


def cmdTransiActorList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_TRANSITION_ACTOR_LIST("
        + str(len(scene.transitionActorList))
        + ", "
        + scene.transitionActorListName(header)
        + "),\n"
    )
    return cmd


def cmdMiscSettings(scene, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_MISC_SETTINGS(" + str(scene.cameraMode) + ", " + str(scene.mapLocation) + "),\n"
    return cmd


def cmdColHeader(scene, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_COL_HEADER(&" + scene.collision.headerName() + "),\n"
    return cmd


def cmdEntranceList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_ENTRANCE_LIST("
        + (scene.entranceListName(header) if len(scene.entranceList) > 0 else "NULL")
        + "),\n"
    )
    return cmd


def cmdSpecialFiles(scene, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_SPECIAL_FILES(" + str(scene.naviCup) + ", " + str(scene.globalObject) + "),\n"
    return cmd


def cmdPathList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_PATH_LIST(" + scene.pathListName(header) + "),\n"
    return cmd


def cmdSpawnList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_SPAWN_LIST("
        + str(len(scene.startPositions))
        + ", "
        + (scene.startPositionsName(header) if len(scene.startPositions) > 0 else "NULL")
        + "),\n"
    )
    return cmd


def cmdSkyboxSettings(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_SKYBOX_SETTINGS("
        + ", ".join(
            (
                str(scene.skyboxID),
                str(scene.skyboxCloudiness),
                str(scene.skyboxLighting),
            )
        )
        + "),\n"
    )
    return cmd


def cmdExitList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_EXIT_LIST(" + scene.exitListName(header) + "),\n"
    return cmd


def cmdLightSettingList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        "\tSCENE_CMD_ENV_LIGHT_SETTINGS("
        + str(len(scene.lights))
        + ", "
        + (scene.lightListName(header) if len(scene.lights) > 0 else "NULL")
        + "),\n"
    )
    return cmd


def cmdCutsceneData(scene, header, cmdCount):
    cmd = CData()
    if scene.csWriteType == "Embedded":
        csname = scene.cutsceneDataName(header)
    elif scene.csWriteType == "Object":
        csname = scene.csWriteObject.name
    elif scene.csWriteType == "Custom":
        csname = scene.csWriteCustom
    cmd.source = "\tSCENE_CMD_CUTSCENE_DATA(" + csname + "),\n"
    return cmd


def cmdEndMarker(name, header, cmdCount):
    cmd = CData()
    cmd.source = "\tSCENE_CMD_END(),\n"
    return cmd


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


def ootMeshEntryToC(meshEntry: OOTRoomMeshGroup, roomShape: str):
    opaqueName = meshEntry.DLGroup.opaque.name if meshEntry.DLGroup.opaque is not None else "0"
    transparentName = meshEntry.DLGroup.transparent.name if meshEntry.DLGroup.transparent is not None else "0"
    data = "{ "
    if roomShape == "ROOM_SHAPE_TYPE_CULLABLE":
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


# Texture files must be saved separately.
def ootBgImagesToC(roomMesh: OOTRoomMesh, textureSettings: TextureExportSettings):
    code = CData()

    if len(roomMesh.bgImages) > 1:
        code.header += f"extern BgImage {roomMesh.getMultiBgStructName()}[];\n"
        code.source += f"BgImage {roomMesh.getMultiBgStructName()}[] = {{"
        for i in range(len(roomMesh.bgImages)):
            bgImage = roomMesh.bgImages[i]
            code.source += f"\t{{\n"
            code.source += bgImage.multiPropertiesC(2, i)
            code.source += f"\t}},\n"
        code.source += f"}};\n\n"

    bitsPerValue = 64
    for bgImage in roomMesh.bgImages:
        code.header += "extern u" + str(bitsPerValue) + " " + bgImage.name + "[];\n"

        # This is to force 8 byte alignment
        if bitsPerValue != 64:
            code.source += "Gfx " + bgImage.name + "_aligner[] = {gsSPEndDisplayList()};\n"
        code.source += "u" + str(bitsPerValue) + " " + bgImage.name + "[SCREEN_WIDTH * SCREEN_HEIGHT / 4] = {\n\t"
        code.source += '#include "' + textureSettings.includeDir + bgImage.getFilename() + '.inc.c"'
        code.source += "\n};\n\n"
    return code


def ootRoomMeshToC(room: OOTRoom, textureExportSettings: TextureExportSettings):
    mesh = room.mesh
    if len(mesh.meshEntries) == 0:
        raise PluginError("Error: Room " + str(room.index) + " has no mesh children.")

    meshHeader = CData()
    meshEntries = CData()
    meshData = CData()

    shapeTypeIdx = [value[0] for value in ootEnumRoomShapeType].index(mesh.roomShape)
    meshEntryType = ootRoomShapeEntryStructs[shapeTypeIdx]
    structName = ootRoomShapeStructs[shapeTypeIdx]
    roomShapeImageFormat = "Multi" if len(mesh.bgImages) > 1 else "Single"
    if mesh.roomShape == "ROOM_SHAPE_TYPE_IMAGE":
        structName += roomShapeImageFormat
    meshHeader.header = f"extern {structName} {mesh.headerName()};\n"

    if mesh.roomShape != "ROOM_SHAPE_TYPE_IMAGE":
        meshHeader.source = (
            "\n".join(
                (
                    f"{structName} {mesh.headerName()} = {{",
                    indent + mesh.roomShape + ",",
                    indent + "ARRAY_COUNT(" + mesh.entriesName() + ")" + ",",
                    indent + mesh.entriesName() + ",",
                    indent + mesh.entriesName() + " + ARRAY_COUNT(" + mesh.entriesName() + ")",
                    "};",
                )
            )
            + "\n\n"
        )

        meshData = CData()
        meshEntries = CData()

        arrayText = "[" + str(len(mesh.meshEntries)) + "]"
        meshEntries.header = f"extern {meshEntryType} {mesh.entriesName()}{arrayText};\n"
        meshEntries.source = f"{meshEntryType} {mesh.entriesName()}{arrayText} = {{\n"

        for entry in mesh.meshEntries:
            meshEntries.source += "\t" + ootMeshEntryToC(entry, mesh.roomShape)
            if entry.DLGroup.opaque is not None:
                meshData.append(entry.DLGroup.opaque.to_c(mesh.model.f3d))
            if entry.DLGroup.transparent is not None:
                meshData.append(entry.DLGroup.transparent.to_c(mesh.model.f3d))

        meshEntries.source += "};\n\n"

    else:
        # type 1 only allows 1 room
        entry = mesh.meshEntries[0]
        roomShapeImageFormatValue = (
            "ROOM_SHAPE_IMAGE_AMOUNT_SINGLE" if roomShapeImageFormat == "Single" else "ROOM_SHAPE_IMAGE_AMOUNT_MULTI"
        )

        meshHeader.source += f"{structName} {mesh.headerName()} = {{\n"
        meshHeader.source += f"\t{{1, {roomShapeImageFormatValue}, &{mesh.entriesName()},}},\n"

        if roomShapeImageFormat == "Single":
            meshHeader.source += mesh.bgImages[0].singlePropertiesC(1) + "\n};\n\n"
        else:
            meshHeader.source += f"\t{len(mesh.bgImages)}, {mesh.getMultiBgStructName()},\n}};\n\n"

        meshEntries.header = f"extern {meshEntryType} {mesh.entriesName()};\n"
        meshEntries.source = (
            f"{meshEntryType} {mesh.entriesName()} = {ootMeshEntryToC(entry, mesh.roomShape)[:-2]};\n\n"
        )

        if entry.DLGroup.opaque is not None:
            meshData.append(entry.DLGroup.opaque.to_c(mesh.model.f3d))
        if entry.DLGroup.transparent is not None:
            meshData.append(entry.DLGroup.transparent.to_c(mesh.model.f3d))

    exportData = mesh.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))

    meshData.append(exportData.all())
    meshData.append(ootBgImagesToC(room.mesh, textureExportSettings))
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
    commands.append(cmdEndMarker(room.roomName(), headerIndex, len(commands)))

    data = CData()

    # data.header = ''.join([command.header for command in commands]) +'\n'
    data.header = "extern SceneCmd " + room.roomName() + "_header" + format(headerIndex, "02") + "[];\n"

    data.source = "SceneCmd " + room.roomName() + "_header" + format(headerIndex, "02") + "[] = {\n"
    data.source += "".join([command.source for command in commands])
    data.source += "};\n\n"

    return data


def ootAlternateRoomMainToC(scene, room):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SceneCmd* " + room.alternateHeadersName() + "[];\n"
    altHeader.source = "SceneCmd* " + room.alternateHeadersName() + "[] = {\n"

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


def ootSceneCommandsToC(scene, headerIndex):
    commands = []
    if scene.hasAlternateHeaders():
        commands.append(cmdAltHeaders(scene.sceneName(), scene.alternateHeadersName(), headerIndex, len(commands)))
    commands.append(cmdSoundSettings(scene, headerIndex, len(commands)))
    commands.append(cmdRoomList(scene, headerIndex, len(commands)))
    if len(scene.transitionActorList) > 0:
        commands.append(cmdTransiActorList(scene, headerIndex, len(commands)))
    commands.append(cmdMiscSettings(scene, headerIndex, len(commands)))
    commands.append(cmdColHeader(scene, headerIndex, len(commands)))
    commands.append(cmdEntranceList(scene, headerIndex, len(commands)))
    commands.append(cmdSpecialFiles(scene, headerIndex, len(commands)))
    if len(scene.pathList) > 0:
        commands.append(cmdPathList(scene, headerIndex, len(commands)))
    commands.append(cmdSpawnList(scene, headerIndex, len(commands)))
    commands.append(cmdSkyboxSettings(scene, headerIndex, len(commands)))
    if len(scene.exitList) > 0:
        commands.append(cmdExitList(scene, headerIndex, len(commands)))
    commands.append(cmdLightSettingList(scene, headerIndex, len(commands)))
    if scene.writeCutscene:
        commands.append(cmdCutsceneData(scene, headerIndex, len(commands)))
    commands.append(cmdEndMarker(scene.sceneName(), headerIndex, len(commands)))

    data = CData()

    # data.header = ''.join([command.header for command in commands]) +'\n'
    data.header = "extern SceneCmd " + scene.sceneName() + "_header" + format(headerIndex, "02") + "[];\n"

    data.source = "SceneCmd " + scene.sceneName() + "_header" + format(headerIndex, "02") + "[] = {\n"
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


def ootPathToC(path, headerIndex: int, index: int):
    data = CData()
    data.header = "extern Vec3s " + path.pathName(headerIndex, index) + "[];\n"
    data.source = "Vec3s " + path.pathName(headerIndex, index) + "[] = {\n"
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


def ootPathListToC(scene, headerIndex: int):
    data = CData()
    data.header = "extern Path " + scene.pathListName(headerIndex) + "[" + str(len(scene.pathList)) + "];\n"
    data.source = "Path " + scene.pathListName(headerIndex) + "[" + str(len(scene.pathList)) + "] = {\n"
    pathData = CData()

    # Parse in alphabetical order of names
    sortedPathList = sorted(scene.pathList, key=lambda x: x.objName.lower())
    for i in range(len(sortedPathList)):
        path = sortedPathList[i]
        data.source += "\t" + "{ " + str(len(path.points)) + ", " + path.pathName(headerIndex, i) + " },\n"
        pathData.append(ootPathToC(path, headerIndex, i))
    data.source += "};\n\n"
    pathData.append(data)
    return pathData


def ootSceneMeshToC(scene, textureExportSettings: TextureExportSettings):
    exportData = scene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))
    return exportData.all()


def ootSceneIncludes(scene):
    data = CData()
    data.source += '#include "ultra64.h"\n'
    data.source += '#include "z64.h"\n'
    data.source += '#include "macros.h"\n'
    data.source += '#include "' + scene.sceneName() + '.h"\n'

    # Not used if all header declarations are in scene.h
    # for i in range(len(scene.rooms)):
    #    data.source += f'#include "{scene.rooms[i].roomName()}.h"\n'

    data.source += '#include "segment_symbols.h"\n'
    data.source += '#include "command_macros_base.h"\n'
    data.source += '#include "z64cutscene_commands.h"\n'
    data.source += '#include "variables.h"\n'
    data.source += "\n"
    return data


def ootAlternateSceneMainToC(scene):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SceneCmd* " + scene.alternateHeadersName() + "[];\n"
    altHeader.source = "SceneCmd* " + scene.alternateHeadersName() + "[] = {\n"

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
    else:
        # The function has already been called (and is being called for another scene header), so we can make this data be a blank string
        roomHeaderData = CData()

    if len(scene.pathList) > 0:
        pathData = ootPathListToC(scene, headerIndex)
    else:
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
        sceneMainC.append(ootLightSettingsToC(scene, scene.skyboxLighting == "true", headerIndex))

    # Write the path data, if used
    sceneMainC.append(pathData)

    # Write the data from alternate headers
    sceneMainC.append(altData)

    return sceneMainC


# Writes the textures and material setup displaylists that are shared between multiple rooms (is written to the scene)
def ootSceneTexturesToC(scene, textureExportSettings: TextureExportSettings):
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


def ootLevelToC(scene, textureExportSettings: TextureExportSettings):
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
