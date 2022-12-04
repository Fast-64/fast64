from .....utility import CData, indent
from .....f3d.f3d_gbi import ScrollMethod, TextureExportSettings
from ....oot_f3d_writer import OOTGfxFormatter
from ....oot_level_classes import OOTScene, OOTLight
from .scene_pathways import getPathData
from .actor import getTransitionActorList, getSpawnActorList, getSpawnList
from .scene_commands import getSceneCommandList


##################
# Light Settings #
##################
def getColorValues(vector: tuple[int, int, int]):
    return ", ".join(f"{v:5}" for v in vector)


def getDirectionValues(vector: tuple[int, int, int]):
    return ", ".join(f"{v - 0x100 if v > 0x7F else v:5}" for v in vector)


def getLightSettingsEntry(light: OOTLight, lightMode: str, isLightingCustom: bool, index: int):
    vectors = [
        (light.ambient, "Ambient Color", getColorValues),
        (light.diffuseDir0, "Diffuse0 Direction", getDirectionValues),
        (light.diffuse0, "Diffuse0 Color", getColorValues),
        (light.diffuseDir1, "Diffuse1 Direction", getDirectionValues),
        (light.diffuse1, "Diffuse1 Color", getColorValues),
        (light.fogColor, "Fog Color", getColorValues),
    ]

    fogData = [
        (light.getBlendFogNear(), "Blend Rate & Fog Near"),
        (f"{light.fogFar}", "Fog Far"),
    ]

    lightDescs = ["Dawn", "Day", "Dusk", "Night"]

    if not isLightingCustom and lightMode == "LIGHT_MODE_TIME":
        # @TODO: Improve the lighting system.
        # Currently Fast64 assumes there's only 4 possible settings for "Time of Day" lighting.
        # This is not accurate and more complicated,
        # for now we are doing ``index % 4`` to avoid having an OoB read in the list
        # but this will need to be changed the day the lighting system is updated.
        lightDesc = f"// {lightDescs[index % 4]} Lighting\n"
    else:
        isIndoor = not isLightingCustom and lightMode == "LIGHT_MODE_SETTINGS"
        lightDesc = f"// {'Indoor' if isIndoor else 'Custom'} No. {index + 1} Lighting\n"

    lightData = (
        (indent + lightDesc)
        + (indent + "{\n")
        + "".join(indent * 2 + f"{'{ ' + vecToC(vector) + ' },':26} // {desc}\n" for vector, desc, vecToC in vectors)
        + "".join(indent * 2 + f"{fogValue + ',':26} // {fogDesc}\n" for fogValue, fogDesc in fogData)
        + (indent + "},\n")
    )

    return lightData


def getLightSettings(outScene: OOTScene, headerIndex: int):
    lightSettingsData = CData()
    lightName = f"LightSettings {outScene.lightListName(headerIndex)}[{len(outScene.lights)}]"

    # .h
    lightSettingsData.header = f"extern {lightName};\n"

    # .c
    lightSettingsData.source = (
        (lightName + " = {\n")
        + "".join(
            getLightSettingsEntry(light, outScene.skyboxLighting, outScene.isSkyboxLightingCustom, i)
            for i, light in enumerate(outScene.lights)
        )
        + "};\n\n"
    )

    return lightSettingsData


########
# Mesh #
########
# Writes the textures and material setup displaylists that are shared between multiple rooms (is written to the scene)
def getSceneModel(outScene: OOTScene, textureExportSettings: TextureExportSettings) -> CData:
    return outScene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex)).all()


#############
# Exit List #
#############
def getExitList(outScene: OOTScene, headerIndex: int):
    exitList = CData()
    listName = f"u16 {outScene.exitListName(headerIndex)}[{len(outScene.exitList)}]"

    # .h
    exitList.header = f"extern {listName};\n"

    # .c
    exitList.source = (
        (listName + " = {\n")
        # @TODO: use the enum name instead of the raw index
        + "\n".join(indent + f"{exitEntry.index}," for exitEntry in outScene.exitList)
        + "\n};\n\n"
    )

    return exitList


#############
# Room List #
#############
def getRoomList(outScene: OOTScene):
    roomList = CData()
    listName = f"RomFile {outScene.roomListName()}[]"

    # generating segment rom names for every room
    segNames = []
    for i in range(len(outScene.rooms)):
        roomName = outScene.rooms[i].roomName()
        segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

    # .h
    roomList.header += f"extern {listName};\n"

    if not outScene.write_dummy_room_list:
        # Write externs for rom segments
        roomList.header += "".join(
            f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames
        )

    # .c
    roomList.source = listName + " = {\n"

    if outScene.write_dummy_room_list:
        roomList.source = (
            "// Dummy room list\n" + roomList.source + ((indent + "{ NULL, NULL },\n") * len(outScene.rooms))
        )
    else:
        roomList.source += (
            " },\n".join(indent + "{ " + f"(u32){startName}, (u32){stopName}" for startName, stopName in segNames)
            + " },\n"
        )

    roomList.source += "};\n\n"
    return roomList


################
# Scene Header #
################
def getHeaderData(header: OOTScene, headerIndex: int):
    headerData = CData()

    # Write the spawn position list data
    if len(header.startPositions) > 0:
        headerData.append(getSpawnActorList(header, headerIndex))

    # Write the transition actor list data
    if len(header.transitionActorList) > 0:
        headerData.append(getTransitionActorList(header, headerIndex))

    # Write the entrance list
    if len(header.entranceList) > 0:
        headerData.append(getSpawnList(header, headerIndex))

    # Write the exit list
    if len(header.exitList) > 0:
        headerData.append(getExitList(header, headerIndex))

    # Write the light data
    if len(header.lights) > 0:
        headerData.append(getLightSettings(header, headerIndex))

    # Write the path data, if used
    if len(header.pathList) > 0:
        headerData.append(getPathData(header, headerIndex))

    return headerData


def getSceneData(outScene: OOTScene):
    sceneC = CData()

    headers = [
        (outScene.childNightHeader, "Child Night"),
        (outScene.adultDayHeader, "Adult Day"),
        (outScene.adultNightHeader, "Adult Night"),
    ]

    for i, csHeader in enumerate(outScene.cutsceneHeaders):
        headers.append((csHeader, f"Cutscene No. {i + 1}"))

    altHeaderPtrs = "\n".join(
        indent + f"{curHeader.sceneName()}_header{i:02},"
        if curHeader is not None
        else indent + "NULL,"
        if i < 4
        else ""
        for i, (curHeader, headerDesc) in enumerate(headers, 1)
    )

    headers.insert(0, (outScene, "Child Day (Default)"))
    for i, (curHeader, headerDesc) in enumerate(headers):
        if curHeader is not None:
            sceneC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
            sceneC.append(getSceneCommandList(curHeader, i))

            if i == 0:
                if outScene.hasAlternateHeaders():
                    altHeaderListName = f"SceneCmd* {outScene.alternateHeadersName()}[]"
                    sceneC.header += f"extern {altHeaderListName};\n"
                    sceneC.source += altHeaderListName + " = {\n" + altHeaderPtrs + "\n};\n\n"

                # Write the room segment list
                sceneC.append(getRoomList(outScene))

            sceneC.append(getHeaderData(curHeader, i))

    return sceneC
