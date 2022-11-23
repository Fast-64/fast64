from .....utility import CData, indent
from .....f3d.f3d_gbi import ScrollMethod, TextureExportSettings
from ....oot_f3d_writer import OOTGfxFormatter
from .scene_pathways import ootPathListToC
from .actor import ootTransitionActorListToC, ootStartPositionListToC, ootEntranceListToC
from .scene_commands import ootSceneCommandsToC


##################
# Light Settings #
##################
def ootVectorToC(vector):
    return f"0x{vector[0]:02X}, 0x{vector[1]:02X}, 0x{vector[2]:02X}"


def ootLightToC(light):
    return (
        indent
        + "{ "
        + ", ".join(
            (
                ootVectorToC(light.ambient),
                ootVectorToC(light.diffuseDir0),
                ootVectorToC(light.diffuse0),
                ootVectorToC(light.diffuseDir1),
                ootVectorToC(light.diffuse1),
                ootVectorToC(light.fogColor),
                light.getBlendFogShort(),
                f"0x{light.fogFar:04X}",
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


########
# Mesh #
########
def ootSceneMeshToC(scene, textureExportSettings: TextureExportSettings):
    exportData = scene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))
    return exportData.all()


# Writes the textures and material setup displaylists that are shared between multiple rooms (is written to the scene)
def ootSceneTexturesToC(scene, textureExportSettings: TextureExportSettings):
    sceneTextures = CData()
    sceneTextures.append(ootSceneMeshToC(scene, textureExportSettings))
    return sceneTextures


#############
# Exit List #
#############
def ootExitListToC(scene, headerIndex):
    data = CData()
    data.header = "extern u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "];\n"
    data.source = "u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "] = {\n"
    for exitEntry in scene.exitList:
        data.source += indent + str(exitEntry.index) + ",\n"
    data.source += "};\n\n"
    return data


#############
# Room List #
#############
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
        data.source += indent + "{0, 0},\n" * len(scene.rooms)
        data.source += "};\n\n"
    else:
        # Write externs for rom segments
        for i in range(len(scene.rooms)):
            data.source += ootRoomExternToC(scene.rooms[i])
        data.source += "\n"

        data.source += "RomFile " + scene.roomListName() + "[] = {\n"

        for i in range(len(scene.rooms)):
            data.source += indent + ootRoomListEntryToC(scene.rooms[i])
        data.source += "};\n\n"

    return data


################
# Scene Header #
################
def ootAlternateSceneMainToC(scene):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SceneCmd* " + scene.alternateHeadersName() + "[];\n"
    altHeader.source = "SceneCmd* " + scene.alternateHeadersName() + "[] = {\n"

    if scene.childNightHeader is not None:
        altHeader.source += indent + scene.sceneName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.childNightHeader, 1))
    else:
        altHeader.source += indent + "0,\n"

    if scene.adultDayHeader is not None:
        altHeader.source += indent + scene.sceneName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultDayHeader, 2))
    else:
        altHeader.source += indent + "0,\n"

    if scene.adultNightHeader is not None:
        altHeader.source += indent + scene.sceneName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultNightHeader, 3))
    else:
        altHeader.source += indent + "0,\n"

    for i in range(len(scene.cutsceneHeaders)):
        altHeader.source += indent + scene.sceneName() + "_header" + format(i + 4, "02") + ",\n"
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
