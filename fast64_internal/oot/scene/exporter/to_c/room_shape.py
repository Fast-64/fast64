from .....utility import CData, PluginError, indent
from .....f3d.f3d_gbi import ScrollMethod, TextureExportSettings
from ....oot_f3d_writer import OOTGfxFormatter
from ....oot_constants import ootRoomShapeStructs, ootRoomShapeEntryStructs, ootEnumRoomShapeType
from ....oot_level_classes import OOTRoom, OOTRoomMeshGroup, OOTRoomMesh


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
            meshEntries.source += indent + ootMeshEntryToC(entry, mesh.roomShape)
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
