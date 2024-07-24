import bpy
import os
import shutil

from ..utility import PluginError, toAlnum, indent
from ..f3d.f3d_gbi import (
    SPDisplayList,
    SPEndDisplayList,
    GfxListTag,
    GfxList,
)
from ..f3d.occlusion_planes.exporter import OcclusionPlaneCandidatesList


class OOTBGImage:
    def __init__(self, name: str, image: bpy.types.Image, otherModeFlags: str):
        self.name = name
        self.image = image
        self.otherModeFlags = otherModeFlags

    def getFilename(self) -> str:
        return f"{self.name}.jpg"

    def singlePropertiesC(self, tabDepth: int) -> str:
        return (indent * tabDepth) + (indent * tabDepth).join(
            (
                f"{self.name},\n",
                f"0x00000000,\n",  # (``unk_0C`` in decomp)
                "NULL,\n",
                f"{self.image.size[0]}, {self.image.size[1]},\n",
                f"G_IM_FMT_RGBA, G_IM_SIZ_16b,\n",  # RGBA16
                f"{self.otherModeFlags}, 0x0000",
            )
        )

    def multiPropertiesC(self, tabDepth: int, cameraIndex: int) -> str:
        return (indent * tabDepth) + f"0x0082, {cameraIndex},\n" + self.singlePropertiesC(tabDepth) + "\n"


class OOTRoomMesh:
    def __init__(self, roomName, roomShape, model):
        self.roomName = roomName
        self.roomShape = roomShape
        self.meshEntries: list[OOTRoomMeshGroup] = []
        self.model = model
        self.bgImages: list[OOTBGImage] = []

    def terminateDLs(self):
        for entry in self.meshEntries:
            entry.DLGroup.terminateDLs()

    def headerName(self):
        return str(self.roomName) + "_shapeHeader"

    def entriesName(self):
        return str(self.roomName) + (
            "_shapeDListEntry" if self.roomShape != "ROOM_SHAPE_TYPE_CULLABLE" else "_shapeCullableEntry"
        )

    def addMeshGroup(self, cullGroup):
        meshGroup = OOTRoomMeshGroup(cullGroup, self.model.DLFormat, self.roomName, len(self.meshEntries))
        self.meshEntries.append(meshGroup)
        return meshGroup

    def currentMeshGroup(self):
        return self.meshEntries[-1]

    def removeUnusedEntries(self):
        newList = []
        for meshEntry in self.meshEntries:
            if not meshEntry.DLGroup.isEmpty():
                newList.append(meshEntry)
        self.meshEntries = newList

    def copyBgImages(self, exportPath: str):
        jpegCompatibility = False  # maybe delete some code later if jpeg compatibility improves
        for bgImage in self.bgImages:
            image = bgImage.image
            imageFileName = bgImage.getFilename()
            if jpegCompatibility:
                isPacked = image.packed_file is not None
                if not isPacked:
                    image.pack()
                oldpath = image.filepath
                oldFormat = image.file_format
                try:
                    image.filepath = bpy.path.abspath(os.path.join(exportPath, imageFileName))
                    image.file_format = "JPEG"
                    image.save()
                    if not isPacked:
                        image.unpack()
                    image.filepath = oldpath
                    image.file_format = oldFormat
                except Exception as e:
                    image.filepath = oldpath
                    image.file_format = oldFormat
                    raise Exception(str(e))
            else:
                filepath = bpy.path.abspath(os.path.join(exportPath, imageFileName))
                shutil.copy(bpy.path.abspath(image.filepath), filepath)

    def getMultiBgStructName(self):
        return self.roomName + "BgImage"


class OOTDLGroup:
    def __init__(self, name, DLFormat):
        self.opaque = None
        self.transparent = None
        self.DLFormat = DLFormat
        self.name = toAlnum(name)

    def addDLCall(self, displayList, drawLayer):
        if drawLayer == "Opaque":
            if self.opaque is None:
                self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, self.DLFormat)
            self.opaque.commands.append(SPDisplayList(displayList))
        elif drawLayer == "Transparent":
            if self.transparent is None:
                self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, self.DLFormat)
            self.transparent.commands.append(SPDisplayList(displayList))
        else:
            raise PluginError("Unhandled draw layer: " + str(drawLayer))

    def terminateDLs(self):
        if self.opaque is not None:
            self.opaque.commands.append(SPEndDisplayList())

        if self.transparent is not None:
            self.transparent.commands.append(SPEndDisplayList())

    def createDLs(self):
        if self.opaque is None:
            self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, self.DLFormat)
        if self.transparent is None:
            self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, self.DLFormat)

    def isEmpty(self):
        return self.opaque is None and self.transparent is None


class OOTRoomMeshGroup:
    def __init__(self, cullGroup, DLFormat, roomName, entryIndex):
        self.cullGroup = cullGroup
        self.roomName = roomName
        self.entryIndex = entryIndex

        self.DLGroup = OOTDLGroup(self.entryName(), DLFormat)

    def entryName(self):
        return self.roomName + "_entry_" + str(self.entryIndex)
