from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, CData, toAlnum, indent
from ....f3d.f3d_gbi import TextureExportSettings
from ...oot_level_classes import OOTRoomMesh
from ...oot_level_classes import OOTBGImage
from ...room.properties import OOTRoomHeaderProperty


@dataclass
class RoomShapeImageBase:
    """This class defines the basic informations shared by other image classes"""

    name: str
    type: str
    amountType: str  # ROOM_SHAPE_IMAGE_AMOUNT_SINGLE/_MULTI
    entryArrayName: str


@dataclass
class RoomShapeDListsEntry:
    """This class defines a display list pointer entry"""

    opaPtr: str
    xluPtr: str

    def getEntryC(self):
        return f"{self.opaPtr}, {self.xluPtr}"


@dataclass
class RoomShapeImageMultiBgEntry:
    """This class defines an image entry for the multiple image mode"""

    bgCamIndex: int
    imgName: str
    width: int
    height: int
    otherModeFlags: str

    unk_00: int = field(init=False, default=130)
    unk_0C: int = field(init=False, default=0)
    tlut: str = field(init=False, default="NULL")
    format: str = field(init=False, default="G_IM_FMT_RGBA")
    size: str = field(init=False, default="G_IM_SIZ_16b")
    tlutCount: int = field(init=False, default=0)

    def getEntryC(self):
        return (
            indent
            + "{\n"
            + f",\n{indent * 2}".join(
                [
                    f"0x{self.unk_00:04X}, {self.bgCamIndex}",
                    f"{self.imgName}",
                    f"0x{self.unk_0C:08X}",
                    f"{self.tlut}",
                    f"{self.width}, {self.height}",
                    f"{self.format}, {self.size}",
                    f"{self.otherModeFlags}, 0x{self.tlutCount:04X},",
                ]
            )
            + indent
            + " },\n"
        )


@dataclass
class RoomShapeImageMultiBg:
    """This class defines the multiple background image array"""

    name: str
    entries: list[RoomShapeImageMultiBgEntry]

    @staticmethod
    def new(name: str, mesh: OOTRoomMesh):
        entries: list[RoomShapeImageMultiBgEntry] = []
        for i, bgImg in enumerate(mesh.bgImages):
            entries.append(
                RoomShapeImageMultiBgEntry(
                    i, bgImg.name, bgImg.image.size[0], bgImg.image.size[1], bgImg.otherModeFlags
                )
            )
        return RoomShapeImageMultiBg(name, entries)

    def getC(self):
        infoData = CData()
        listName = f"RoomShapeImageMultiBgEntry {self.name}[{len(self.entries)}]"

        # .h
        infoData.header = f"extern {listName};\n"

        # .c
        infoData.source = listName + " = {\n" + f"".join(elem.getEntryC() for elem in self.entries) + "};\n\n"

        return infoData


@dataclass
class RoomShapeDLists:
    """This class defines the display list pointer array (or variable)"""

    name: str
    isArray: bool
    entries: list[RoomShapeDListsEntry]

    @staticmethod
    def new(name: str, isArray: bool, mesh: OOTRoomMesh):
        entries: list[RoomShapeDListsEntry] = []
        for meshGrp in mesh.meshEntries:
            entries.append(
                RoomShapeDListsEntry(
                    meshGrp.DLGroup.opaque.name if meshGrp.DLGroup.opaque is not None else "NULL",
                    meshGrp.DLGroup.transparent.name if meshGrp.DLGroup.transparent is not None else "NULL",
                )
            )
        return RoomShapeDLists(name, isArray, entries)

    def getC(self):
        infoData = CData()
        listName = f"RoomShapeDListsEntry {self.name}" + f"[{len(self.entries)}]" if self.isArray else ""

        # .h
        infoData.header = f"extern {listName};\n"

        # .c
        infoData.source = (
            (listName + " = {\n")
            + (
                indent + f",\n{indent}".join("{ " + elem.getEntryC() + " }" for elem in self.entries)
                if self.isArray
                else indent + self.entries[0].getEntryC()
            )
            + "\n};\n\n"
        )

        return infoData


@dataclass
class RoomShapeImageSingle(RoomShapeImageBase):
    """This class defines a room shape using only one image"""

    imgName: str
    width: int
    height: int
    otherModeFlags: str

    unk_0C: int = field(init=False, default=0)
    tlut: str = field(init=False, default="NULL")
    format: str = field(init=False, default="G_IM_FMT_RGBA")
    size: str = field(init=False, default="G_IM_SIZ_16b")
    tlutCount: int = field(init=False, default=0)

    def getC(self):
        """Returns the single background image mode variable"""

        infoData = CData()
        listName = f"RoomShapeImageSingle {self.name}"

        # .h
        infoData.header = f"extern {listName};\n"

        # .c
        infoData.source = (listName + " = {\n") + f",\n{indent}".join(
            [
                "{ " + f"{self.type}, {self.amountType}, &{self.entryArrayName}" + " }",
                f"{self.imgName}",
                f"0x{self.unk_0C:08X}",
                f"{self.tlut}",
                f"{self.width}, {self.height}",
                f"{self.format}, {self.size}",
                f"{self.otherModeFlags}, 0x{self.tlutCount:04X}",
            ]
        )

        return infoData


@dataclass
class RoomShapeImageMulti(RoomShapeImageBase):
    """This class defines a room shape using multiple images"""

    bgEntryArrayName: str

    def getC(self):
        """Returns the multiple background image mode variable"""

        infoData = CData()
        listName = f"RoomShapeImageSingle {self.name}"

        # .h
        infoData.header = f"extern {listName};\n"

        # .c
        infoData.source = (listName + " = {\n") + f",\n{indent}".join(
            [
                "{ " + f"{self.type}, {self.amountType}, &{self.entryArrayName}" + " }",
                f"ARRAY_COUNT({self.bgEntryArrayName})",
                f"{self.bgEntryArrayName}",
            ]
        )

        return infoData


@dataclass
class RoomShapeNormal:
    """This class defines a normal room shape"""

    name: str
    type: str
    entryArrayName: str

    def getC(self):
        """Returns the C data for the room shape"""

        infoData = CData()
        listName = f"RoomShapeNormal {self.name}"

        # .h
        infoData.header = f"extern {listName};\n"

        # .c
        numEntries = f"ARRAY_COUNT({self.entryArrayName})"
        infoData.source = (
            (listName + " = {\n" + indent)
            + f",\n{indent}".join(
                [f"{self.type}", numEntries, f"{self.entryArrayName}", f"{self.entryArrayName} + {numEntries}"]
            )
            + "\n};\n\n"
        )

        return infoData


@dataclass
class RoomShape:
    """This class hosts every type of room shape"""

    dl: Optional[RoomShapeDLists]
    normal: Optional[RoomShapeNormal]
    single: Optional[RoomShapeImageSingle]
    multiImg: Optional[RoomShapeImageMultiBg]
    multi: Optional[RoomShapeImageMulti]

    @staticmethod
    def new(type: str, props: OOTRoomHeaderProperty, mesh: OOTRoomMesh, sceneName: str, roomName: str):
        name = f"{roomName}_shapeHeader"
        dlName = f"{roomName}_shapeDListEntry"
        normal = None
        single = None
        multiImg = None
        multi = None

        match type:
            case "ROOM_SHAPE_TYPE_NORMAL":
                normal = RoomShapeNormal(name, type, dlName)
            case "ROOM_SHAPE_TYPE_IMAGE":
                for bgImage in props.bgImageList:
                    if bgImage.image is None:
                        raise PluginError(
                            'A room is has room shape "Image" but does not have an image set in one of its BG images.'
                        )
                    mesh.bgImages.append(
                        OOTBGImage(
                            toAlnum(sceneName + "_bg_" + bgImage.image.name),
                            bgImage.image,
                            bgImage.otherModeFlags,
                        )
                    )

                if len(mesh.bgImages) > 1:
                    multiImg = RoomShapeImageMultiBg.new(f"{roomName}_shapeMultiBg", mesh)
                    multi = RoomShapeImageMulti(name, type, "ROOM_SHAPE_IMAGE_AMOUNT_MULTI", dlName, multiImg.name)
                else:
                    bgImg = mesh.bgImages[0]
                    single = RoomShapeImageSingle(
                        name,
                        type,
                        "ROOM_SHAPE_IMAGE_AMOUNT_SINGLE",
                        dlName,
                        bgImg.name,
                        bgImg.image.size[0],
                        bgImg.image.size[1],
                        bgImg.otherModeFlags,
                    )
            case _:
                raise PluginError(f"ERROR: Room Shape not supported: {type}")
        return RoomShape(RoomShapeDLists.new(dlName, normal is not None, mesh), normal, single, multiImg, multi)

    def getName(self):
        """Returns the correct room shape name based on the type used"""

        if self.normal is not None:
            return self.normal.name
        elif self.single is not None:
            return self.single.name
        elif self.multi is not None and self.multiImg is not None:
            return self.multi.name
        else:
            raise PluginError("ERROR: Name not found!")

    def getCmd(self):
        """Returns the room shape room command"""

        return indent + f"SCENE_CMD_ROOM_SHAPE(&{self.getName()}),\n"

    def getRoomShapeBgImgDataC(self, roomMesh: OOTRoomMesh, textureSettings: TextureExportSettings):
        """Returns the image data for image room shapes"""

        dlData = CData()

        bitsPerValue = 64
        for bgImage in roomMesh.bgImages:
            # .h
            dlData.header += f"extern u{bitsPerValue} {bgImage.name}[];\n"

            # .c
            dlData.source += (
                # This is to force 8 byte alignment
                (f"Gfx {bgImage.name}_aligner[] = " + "{ gsSPEndDisplayList() };\n" if bitsPerValue != 64 else "")
                + (f"u{bitsPerValue} {bgImage.name}[SCREEN_WIDTH * SCREEN_HEIGHT / 4]" + " = {\n")
                + f'#include "{textureSettings.includeDir + bgImage.getFilename()}.inc.c"'
                + "\n};\n\n"
            )

        return dlData

    def getRoomShapeC(self):
        """Returns the C data for the room shape"""

        shapeData = CData()

        if self.normal is not None:
            shapeData.append(self.normal.getC())

        if self.single is not None:
            shapeData.append(self.single.getC())

        if self.multi is not None and self.multiImg is not None:
            shapeData.append(self.multi.getC())
            shapeData.append(self.multiImg.getC())

        shapeData.append(self.dl.getC())
        return shapeData
