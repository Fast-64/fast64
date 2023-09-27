from dataclasses import dataclass
from ...utility import CData, indent
from ...f3d.f3d_gbi import TextureExportSettings
from ..oot_level_classes import OOTRoomMesh


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

    unk_00: int = 130
    unk_0C: int = 0
    tlut: str = "NULL"
    format: str = "G_IM_FMT_RGBA"
    size: str = "G_IM_SIZ_16b"
    tlutCount: int = 0

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

    unk_0C: int = 0
    tlut: str = "NULL"
    format: str = "G_IM_FMT_RGBA"
    size: str = "G_IM_SIZ_16b"
    tlutCount: int = 0

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

    dl: RoomShapeDLists
    normal: RoomShapeNormal
    single: RoomShapeImageSingle
    multiImg: RoomShapeImageMultiBg
    multi: RoomShapeImageMulti

    def getName(self):
        """Returns the correct room shape name based on the type used"""

        if self.normal is not None:
            return self.normal.name

        if self.single is not None:
            return self.single.name

        if self.multi is not None and self.multiImg is not None:
            return self.multi.name

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
