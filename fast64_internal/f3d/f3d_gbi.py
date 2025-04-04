# Macros are all copied over from gbi.h
from __future__ import annotations

from typing import Sequence, Union, Tuple
from dataclasses import dataclass, fields, field
import bpy, os, enum, copy
from ..utility import *

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .f3d_material import TextureProperty


class ScrollMethod(enum.Enum):
    Vertex = 1
    Tile = 2
    Ignore = 3


class DLFormat(enum.Enum):
    Static = 1
    Dynamic = 2


class GfxListTag(enum.IntFlag):
    Geometry = 1
    Material = 2
    MaterialRevert = 4
    Draw = 4
    NoExport = 16

    @property
    def Export(self):
        return not self & GfxListTag.NoExport


class GfxTag(enum.Flag):
    TileScroll0 = enum.auto()
    TileScroll1 = enum.auto()


class GfxMatWriteMethod(enum.Enum):
    WriteAll = 1
    WriteDifferingAndRevert = 2


enumTexScroll = [
    ("None", "None", "None"),
    ("Linear", "Linear", "Linear"),
    ("Sine", "Sine", "Sine"),
    ("Noise", "Noise", "Noise"),
]

dlTypeEnum = [
    ("STATIC", "Static", "Static"),
    ("MATERIAL", "Dynamic Material", "Dynamic Material"),
    ("PROCEDURAL", "Procedural", "Procedural"),
]

# 1-8 for F3DEX2 etc., 1-10 for F3DEX3
lightIndex = {f"LIGHT_{n}": n for n in range(1, 11)}

# tuple of max buffer size, max load count.
vertexBufferSize = {
    "F3D": (16, 16),
    "F3DEX/LX": (32, 32),
    "F3DLX.Rej": (64, 32),
    "F3DLP.Rej": (80, 32),
    "F3DEX2/LX2": (32, 32),
    "F3DEX2.Rej/LX2.Rej": (64, 64),
    "F3DEX3": (56, 56),
    "T3D": (70, 70),
}

sm64_default_draw_layers = {
    "0": ("G_RM_ZB_OPA_SURF", "G_RM_NOOP2"),
    "1": ("G_RM_AA_ZB_OPA_SURF", "G_RM_NOOP2"),
    "2": ("G_RM_AA_ZB_OPA_DECAL", "G_RM_NOOP2"),
    "3": ("G_RM_AA_ZB_OPA_INTER", "G_RM_NOOP2"),
    "4": ("G_RM_AA_ZB_TEX_EDGE", "G_RM_NOOP2"),
    "5": ("G_RM_AA_ZB_XLU_SURF", "G_RM_NOOP2"),
    "6": ("G_RM_AA_ZB_XLU_DECAL", "G_RM_NOOP2"),
    "7": ("G_RM_AA_ZB_XLU_INTER", "G_RM_NOOP2"),
}

oot_default_draw_layers = {
    "Opaque": ("G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2"),
    "Transparent": ("G_RM_AA_ZB_XLU_SURF", "G_RM_AA_ZB_XLU_SURF2"),
    "Overlay": ("G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2"),
}

default_draw_layers = {
    "SM64": sm64_default_draw_layers,
    "OOT": oot_default_draw_layers,
}

CCMUXDict = {
    "COMBINED": 0,
    "TEXEL0": 1,
    "TEXEL1": 2,
    "PRIMITIVE": 3,
    "SHADE": 4,
    "ENVIRONMENT": 5,
    "CENTER": 6,
    "SCALE": 6,
    "COMBINED_ALPHA": 7,
    "TEXEL0_ALPHA": 8,
    "TEXEL1_ALPHA": 9,
    "PRIMITIVE_ALPHA": 10,
    "SHADE_ALPHA": 11,
    "ENV_ALPHA": 12,
    "LOD_FRACTION": 13,
    "PRIM_LOD_FRAC": 14,
    "NOISE": 7,
    "K4": 7,
    "K5": 15,
    "1": 6,
    "0": 31,
}

ACMUXDict = {
    "COMBINED": 0,
    "TEXEL0": 1,
    "TEXEL1": 2,
    "PRIMITIVE": 3,
    "SHADE": 4,
    "ENVIRONMENT": 5,
    "LOD_FRACTION": 0,
    "PRIM_LOD_FRAC": 6,
    "1": 6,
    "0": 7,
}


def isUcodeF3DEX1(F3D_VER: str) -> bool:
    return F3D_VER in {"F3DLP.Rej", "F3DLX.Rej", "F3DEX/LX"}


def isUcodeF3DEX2(F3D_VER: str) -> bool:
    return F3D_VER in {"F3DEX2.Rej/LX2.Rej", "F3DEX2/LX2"}


def isUcodeF3DEX3(F3D_VER: str) -> bool:
    return F3D_VER == "F3DEX3"


def is_ucode_t3d(UCODE_VER: str) -> bool:
    return UCODE_VER == "T3D"


def is_ucode_f3d(UCODE_VER: str) -> bool:
    return UCODE_VER not in {"T3D", "RDPQ"}


class F3D:
    """NOTE: do not initialize this class manually! use get_F3D_GBI so that the single instance is cached from the microcode type."""

    def __init__(self, F3D_VER):
        self.F3D_VER = F3D_VER
        F3DEX_GBI = self.F3DEX_GBI = isUcodeF3DEX1(F3D_VER)
        F3DEX_GBI_2 = self.F3DEX_GBI_2 = isUcodeF3DEX2(F3D_VER)
        F3DEX_GBI_3 = self.F3DEX_GBI_3 = isUcodeF3DEX3(F3D_VER)
        F3DLP_GBI = self.F3DLP_GBI = self.F3DEX_GBI
        self.F3D_OLD_GBI = not (F3DEX_GBI or F3DEX_GBI_2 or F3DEX_GBI_3)
        self.F3D_GBI = is_ucode_f3d(F3D_VER)

        # F3DEX2 is F3DEX1 and F3DEX3 is F3DEX2, but F3DEX3 is not F3DEX1
        if F3DEX_GBI_2:
            F3DEX_GBI = self.F3DEX_GBI = True
        elif F3DEX_GBI_3:
            F3DEX_GBI_2 = self.F3DEX_GBI_2 = True

        if F3D_VER in vertexBufferSize:
            self.vert_buffer_size = vertexBufferSize[F3D_VER][0]
            self.vert_load_size = vertexBufferSize[F3D_VER][1]
        else:
            self.vert_buffer_size = self.vert_load_size = None

        self.G_MAX_LIGHTS = 9 if F3DEX_GBI_3 else 7
        self.G_INPUT_BUFFER_CMDS = 21

        if F3DEX_GBI_2:
            self.G_NOOP = 0x00
            self.G_RDPHALF_2 = 0xF1
            self.G_SETOTHERMODE_H = 0xE3
            self.G_SETOTHERMODE_L = 0xE2
            self.G_RDPHALF_1 = 0xE1
            self.G_SPNOOP = 0xE0
            self.G_ENDDL = 0xDF
            self.G_DL = 0xDE
            self.G_LOAD_UCODE = 0xDD
            self.G_MOVEMEM = 0xDC
            self.G_MOVEWORD = 0xDB
            self.G_MTX = 0xDA
            self.G_GEOMETRYMODE = 0xD9
            self.G_POPMTX = 0xD8
            self.G_TEXTURE = 0xD7
            self.G_DMA_IO = 0xD6

            self.G_VTX = 0x01
            self.G_MODIFYVTX = 0x02
            self.G_CULLDL = 0x03
            self.G_BRANCH_Z = 0x04
            self.G_TRI1 = 0x05
            self.G_TRI2 = 0x06
            self.G_QUAD = 0x07

            if F3DEX_GBI_3:
                self.G_TRISTRIP = 0x08
                self.G_TRIFAN = 0x09
                self.G_LIGHTTORDP = 0x0A
            else:
                self.G_SPECIAL_1 = 0xD5
                self.G_SPECIAL_2 = 0xD4
                self.G_SPECIAL_3 = 0xD3
                self.G_LINE3D = 0x08

        else:
            # DMA commands
            self.G_SPNOOP = 0  # handle 0 gracefully
            self.G_MTX = 1
            self.G_RESERVED0 = 2  # not implemeted
            self.G_MOVEMEM = 3  # move a block of memory (up to 4 words) to dmem
            self.G_VTX = 4
            self.G_RESERVED1 = 5  # not implemeted
            self.G_DL = 6
            self.G_RESERVED2 = 7  # not implemeted
            self.G_RESERVED3 = 8  # not implemeted
            self.G_SPRITE2D_BASE = 9  # sprite command

            # IMMEDIATE commands
            self.G_IMMFIRST = -65
            self.G_TRI1 = self.G_IMMFIRST - 0
            self.G_CULLDL = self.G_IMMFIRST - 1
            self.G_POPMTX = self.G_IMMFIRST - 2
            self.G_MOVEWORD = self.G_IMMFIRST - 3
            self.G_TEXTURE = self.G_IMMFIRST - 4
            self.G_SETOTHERMODE_H = self.G_IMMFIRST - 5
            self.G_SETOTHERMODE_L = self.G_IMMFIRST - 6
            self.G_ENDDL = self.G_IMMFIRST - 7
            self.G_SETGEOMETRYMODE = self.G_IMMFIRST - 8
            self.G_CLEARGEOMETRYMODE = self.G_IMMFIRST - 9
            self.G_LINE3D = self.G_IMMFIRST - 10
            self.G_RDPHALF_1 = self.G_IMMFIRST - 11
            self.G_RDPHALF_2 = self.G_IMMFIRST - 12
            if F3DEX_GBI or F3DLP_GBI:
                self.G_MODIFYVTX = self.G_IMMFIRST - 13
                self.G_TRI2 = self.G_IMMFIRST - 14
                self.G_BRANCH_Z = self.G_IMMFIRST - 15
                self.G_LOAD_UCODE = self.G_IMMFIRST - 16
            else:
                self.G_RDPHALF_CONT = self.G_IMMFIRST - 13

            # We are overloading 2 of the immediate commands
            # to keep the byte alignment of dmem the same

            self.G_SPRITE2D_SCALEFLIP = self.G_IMMFIRST - 1
            self.G_SPRITE2D_DRAW = self.G_IMMFIRST - 2

            # RDP commands
            self.G_NOOP = 0xC0

        # RDP commands
        self.G_SETCIMG = 0xFF  #  -1
        self.G_SETZIMG = 0xFE  #  -2
        self.G_SETTIMG = 0xFD  #  -3
        self.G_SETCOMBINE = 0xFC  #  -4
        self.G_SETENVCOLOR = 0xFB  #  -5
        self.G_SETPRIMCOLOR = 0xFA  #  -6
        self.G_SETBLENDCOLOR = 0xF9  #  -7
        self.G_SETFOGCOLOR = 0xF8  #  -8
        self.G_SETFILLCOLOR = 0xF7  #  -9
        self.G_FILLRECT = 0xF6  # -10
        self.G_SETTILE = 0xF5  # -11
        self.G_LOADTILE = 0xF4  # -12
        self.G_LOADBLOCK = 0xF3  # -13
        self.G_SETTILESIZE = 0xF2  # -14
        self.G_LOADTLUT = 0xF0  # -16
        self.G_RDPSETOTHERMODE = 0xEF  # -17
        self.G_SETPRIMDEPTH = 0xEE  # -18
        self.G_SETSCISSOR = 0xED  # -19
        self.G_SETCONVERT = 0xEC  # -20
        self.G_SETKEYR = 0xEB  # -21
        self.G_SETKEYGB = 0xEA  # -22
        self.G_RDPFULLSYNC = 0xE9  # -23
        self.G_RDPTILESYNC = 0xE8  # -24
        self.G_RDPPIPESYNC = 0xE7  # -25
        self.G_RDPLOADSYNC = 0xE6  # -26
        self.G_TEXRECTFLIP = 0xE5  # -27
        self.G_TEXRECT = 0xE4  # -28

        self.G_TRI_FILL = 0xC8  # fill triangle:            11001000
        self.G_TRI_SHADE = 0xCC  # shade triangle:           11001100
        self.G_TRI_TXTR = 0xCA  # texture triangle:         11001010
        self.G_TRI_SHADE_TXTR = 0xCE  # shade, texture triangle:  11001110
        self.G_TRI_FILL_ZBUFF = 0xC9  # fill, zbuff triangle:     11001001
        self.G_TRI_SHADE_ZBUFF = 0xCD  # shade, zbuff triangle:    11001101
        self.G_TRI_TXTR_ZBUFF = 0xCB  # texture, zbuff triangle:  11001011
        self.G_TRI_SHADE_TXTR_ZBUFF = 0xCF  # shade, txtr, zbuff trngl: 11001111

        # masks to build RDP triangle commands
        self.G_RDP_TRI_FILL_MASK = 0x08
        self.G_RDP_TRI_SHADE_MASK = 0x04
        self.G_RDP_TRI_TXTR_MASK = 0x02
        self.G_RDP_TRI_ZBUFF_MASK = 0x01

        # gets added to RDP command, in order to test for addres fixup
        self.G_RDP_ADDR_FIXUP = 3  # |RDP cmds| <= this, do addr fixup
        self.G_RDP_TEXRECT_CHECK = (-1 * self.G_TEXRECTFLIP) & 0xFF

        self.G_DMACMDSIZ = 128
        self.G_IMMCMDSIZ = 64
        self.G_RDPCMDSIZ = 64

        # Coordinate shift values, number of bits of fraction
        self.G_TEXTURE_IMAGE_FRAC = 2
        self.G_TEXTURE_SCALE_FRAC = 16
        self.G_SCALE_FRAC = 8
        self.G_ROTATE_FRAC = 16

        self.G_MAXFBZ = 0x3FFF  # 3b exp, 11b mantissa

        # G_MTX: parameter flags

        if F3DEX_GBI_2:
            self.G_MTX_MODELVIEW = 0x00  # matrix types
            self.G_MTX_PROJECTION = 0x04
            self.G_MTX_MUL = 0x00  # concat or load
            self.G_MTX_LOAD = 0x02
            self.G_MTX_NOPUSH = 0x00  # push or not
            self.G_MTX_PUSH = 0x01
        else:
            self.G_MTX_MODELVIEW = 0x00  # matrix types
            self.G_MTX_PROJECTION = 0x01
            self.G_MTX_MUL = 0x00  # concat or load
            self.G_MTX_LOAD = 0x02
            self.G_MTX_NOPUSH = 0x00  # push or not
            self.G_MTX_PUSH = 0x04

        self.G_ZBUFFER = 0x00000001
        self.G_SHADE = 0x00000004  # enable Gouraud interp
        # rest of low byte reserved for setup ucode
        if F3DEX_GBI_2:
            self.G_TEXTURE_ENABLE = 0x00000000  # Ignored
            self.G_SHADING_SMOOTH = 0x00200000  # flat or smooth shaded
            self.G_CULL_FRONT = 0x00000200
            self.G_CULL_BACK = 0x00000400
            self.G_CULL_BOTH = 0x00000600  # To make code cleaner
        else:
            self.G_TEXTURE_ENABLE = 0x00000002  # Microcode use only
            self.G_SHADING_SMOOTH = 0x00000200  # flat or smooth shaded
            self.G_CULL_FRONT = 0x00001000
            self.G_CULL_BACK = 0x00002000
            self.G_CULL_BOTH = 0x00003000  # To make code cleaner
        self.G_FOG = 0x00010000
        self.G_LIGHTING = 0x00020000
        self.G_TEXTURE_GEN = 0x00040000
        self.G_TEXTURE_GEN_LINEAR = 0x00080000
        self.G_LOD = 0x00100000  # NOT IMPLEMENTED
        if F3DEX_GBI or F3DLP_GBI:
            self.G_CLIPPING = 0x00800000
        else:
            self.G_CLIPPING = 0x00000000

        if F3DEX_GBI_3:
            self.G_AMBOCCLUSION = 0x00000040
            self.G_ATTROFFSET_Z_ENABLE = 0x00000080
            self.G_ATTROFFSET_ST_ENABLE = 0x00000100
            self.G_PACKED_NORMALS = 0x00000800
            self.G_LIGHTTOALPHA = 0x00001000
            self.G_LIGHTING_SPECULAR = 0x00002000
            self.G_FRESNEL_COLOR = 0x00004000
            self.G_FRESNEL_ALPHA = 0x00008000
            self.G_LIGHTING_POSITIONAL = 0x00400000  # Ignored, always on

        self.allGeomModeFlags = {
            "G_ZBUFFER",
            "G_TEXTURE_ENABLE",
            "G_SHADE",
            "G_CULL_FRONT",
            "G_CULL_BACK",
            "G_CULL_BOTH",
            "G_FOG",
            "G_LIGHTING",
            "G_TEXTURE_GEN",
            "G_TEXTURE_GEN_LINEAR",
            "G_LOD",
            "G_SHADING_SMOOTH",
            "G_LIGHTING_POSITIONAL",
            "G_CLIPPING",
        }
        if F3DEX_GBI_3:
            self.allGeomModeFlags |= {
                "G_AMBOCCLUSION",
                "G_ATTROFFSET_Z_ENABLE",
                "G_ATTROFFSET_ST_ENABLE",
                "G_PACKED_NORMALS",
                "G_LIGHTTOALPHA",
                "G_LIGHTING_SPECULAR",
                "G_FRESNEL_COLOR",
                "G_FRESNEL_ALPHA",
            }

        self.G_FOG_H = self.G_FOG / 0x10000
        self.G_LIGHTING_H = self.G_LIGHTING / 0x10000
        self.G_TEXTURE_GEN_H = self.G_TEXTURE_GEN / 0x10000
        self.G_TEXTURE_GEN_LINEAR_H = self.G_TEXTURE_GEN_LINEAR / 0x10000
        self.G_LOD_H = self.G_LOD / 0x10000  # NOT IMPLEMENTED
        if F3DEX_GBI or F3DLP_GBI:
            self.G_CLIPPING_H = self.G_CLIPPING / 0x10000

        # Need these defined for Sprite Microcode
        self.G_TX_LOADTILE = 7
        self.G_TX_RENDERTILE = 0

        self.G_TX_NOMIRROR = 0
        self.G_TX_WRAP = 0
        self.G_TX_MIRROR = 0x1
        self.G_TX_CLAMP = 0x2
        self.G_TX_NOMASK = 0
        self.G_TX_NOLOD = 0

        self.G_TX_VARS = {
            "G_TX_NOMIRROR": 0,
            "G_TX_WRAP": 0,
            "G_TX_MIRROR": 1,
            "G_TX_CLAMP": 2,
            "G_TX_NOMASK": 0,
            "G_TX_NOLOD": 0,
        }

        # G_SETIMG fmt: set image formats
        self.G_IM_FMT_RGBA = 0
        self.G_IM_FMT_YUV = 1
        self.G_IM_FMT_CI = 2
        self.G_IM_FMT_IA = 3
        self.G_IM_FMT_I = 4

        self.G_IM_FMT_VARS = {
            "0": 0,
            "G_IM_FMT_RGBA": 0,
            "G_IM_FMT_YUV": 1,
            "G_IM_FMT_CI": 2,
            "G_IM_FMT_IA": 3,
            "G_IM_FMT_I": 4,
        }

        # G_SETIMG siz: set image pixel size
        self.G_IM_SIZ_4b = 0
        self.G_IM_SIZ_8b = 1
        self.G_IM_SIZ_16b = 2
        self.G_IM_SIZ_32b = 3
        self.G_IM_SIZ_DD = 5

        self.G_IM_SIZ_4b_BYTES = 0
        self.G_IM_SIZ_4b_TILE_BYTES = self.G_IM_SIZ_4b_BYTES
        self.G_IM_SIZ_4b_LINE_BYTES = self.G_IM_SIZ_4b_BYTES

        self.G_IM_SIZ_8b_BYTES = 1
        self.G_IM_SIZ_8b_TILE_BYTES = self.G_IM_SIZ_8b_BYTES
        self.G_IM_SIZ_8b_LINE_BYTES = self.G_IM_SIZ_8b_BYTES

        self.G_IM_SIZ_16b_BYTES = 2
        self.G_IM_SIZ_16b_TILE_BYTES = self.G_IM_SIZ_16b_BYTES
        self.G_IM_SIZ_16b_LINE_BYTES = self.G_IM_SIZ_16b_BYTES

        self.G_IM_SIZ_32b_BYTES = 4
        self.G_IM_SIZ_32b_TILE_BYTES = 2
        self.G_IM_SIZ_32b_LINE_BYTES = 2

        self.G_IM_SIZ_4b_LOAD_BLOCK = self.G_IM_SIZ_16b
        self.G_IM_SIZ_8b_LOAD_BLOCK = self.G_IM_SIZ_16b
        self.G_IM_SIZ_16b_LOAD_BLOCK = self.G_IM_SIZ_16b
        self.G_IM_SIZ_32b_LOAD_BLOCK = self.G_IM_SIZ_32b

        self.G_IM_SIZ_4b_SHIFT = 2
        self.G_IM_SIZ_8b_SHIFT = 1
        self.G_IM_SIZ_16b_SHIFT = 0
        self.G_IM_SIZ_32b_SHIFT = 0

        self.G_IM_SIZ_4b_INCR = 3
        self.G_IM_SIZ_8b_INCR = 1
        self.G_IM_SIZ_16b_INCR = 0
        self.G_IM_SIZ_32b_INCR = 0

        self.G_IM_SIZ_VARS = {
            "0": 0,
            "G_IM_SIZ_4b": 0,
            "G_IM_SIZ_8b": 1,
            "G_IM_SIZ_16b": 2,
            "G_IM_SIZ_32b": 3,
            "G_IM_SIZ_DD": 5,
            "G_IM_SIZ_4b_BYTES": 0,
            "G_IM_SIZ_4b_TILE_BYTES": self.G_IM_SIZ_4b_BYTES,
            "G_IM_SIZ_4b_LINE_BYTES": self.G_IM_SIZ_4b_BYTES,
            "G_IM_SIZ_8b_BYTES": 1,
            "G_IM_SIZ_8b_TILE_BYTES": self.G_IM_SIZ_8b_BYTES,
            "G_IM_SIZ_8b_LINE_BYTES": self.G_IM_SIZ_8b_BYTES,
            "G_IM_SIZ_16b_BYTES": 2,
            "G_IM_SIZ_16b_TILE_BYTES": self.G_IM_SIZ_16b_BYTES,
            "G_IM_SIZ_16b_LINE_BYTES": self.G_IM_SIZ_16b_BYTES,
            "G_IM_SIZ_32b_BYTES": 4,
            "G_IM_SIZ_32b_TILE_BYTES": 2,
            "G_IM_SIZ_32b_LINE_BYTES": 2,
            "G_IM_SIZ_4b_LOAD_BLOCK": self.G_IM_SIZ_16b,
            "G_IM_SIZ_8b_LOAD_BLOCK": self.G_IM_SIZ_16b,
            "G_IM_SIZ_16b_LOAD_BLOCK": self.G_IM_SIZ_16b,
            "G_IM_SIZ_32b_LOAD_BLOCK": self.G_IM_SIZ_32b,
            "G_IM_SIZ_4b_SHIFT": 2,
            "G_IM_SIZ_8b_SHIFT": 1,
            "G_IM_SIZ_16b_SHIFT": 0,
            "G_IM_SIZ_32b_SHIFT": 0,
            "G_IM_SIZ_4b_INCR": 3,
            "G_IM_SIZ_8b_INCR": 1,
            "G_IM_SIZ_16b_INCR": 0,
            "G_IM_SIZ_32b_INCR": 0,
        }

        # G_SETCOMBINE: color combine modes

        # Color combiner constants:
        self.G_CCMUX_COMBINED = 0
        self.G_CCMUX_TEXEL0 = 1
        self.G_CCMUX_TEXEL1 = 2
        self.G_CCMUX_PRIMITIVE = 3
        self.G_CCMUX_SHADE = 4
        self.G_CCMUX_ENVIRONMENT = 5
        self.G_CCMUX_CENTER = 6
        self.G_CCMUX_SCALE = 6
        self.G_CCMUX_COMBINED_ALPHA = 7
        self.G_CCMUX_TEXEL0_ALPHA = 8
        self.G_CCMUX_TEXEL1_ALPHA = 9
        self.G_CCMUX_PRIMITIVE_ALPHA = 10
        self.G_CCMUX_SHADE_ALPHA = 11
        self.G_CCMUX_ENV_ALPHA = 12
        self.G_CCMUX_LOD_FRACTION = 13
        self.G_CCMUX_PRIM_LOD_FRAC = 14
        self.G_CCMUX_NOISE = 7
        self.G_CCMUX_K4 = 7
        self.G_CCMUX_K5 = 15
        self.G_CCMUX_1 = 6
        self.G_CCMUX_0 = 31

        self.CCMUXDict = CCMUXDict

        self.ACMUXDict = ACMUXDict

        # Alpha combiner constants:
        self.G_ACMUX_COMBINED = 0
        self.G_ACMUX_TEXEL0 = 1
        self.G_ACMUX_TEXEL1 = 2
        self.G_ACMUX_PRIMITIVE = 3
        self.G_ACMUX_SHADE = 4
        self.G_ACMUX_ENVIRONMENT = 5
        self.G_ACMUX_LOD_FRACTION = 0
        self.G_ACMUX_PRIM_LOD_FRAC = 6
        self.G_ACMUX_1 = 6
        self.G_ACMUX_0 = 7

        # typical CC cycle 1 modes
        self.G_CC_PRIMITIVE = "0", "0", "0", "PRIMITIVE", "0", "0", "0", "PRIMITIVE"
        self.G_CC_SHADE = "0", "0", "0", "SHADE", "0", "0", "0", "SHADE"

        self.G_CC_MODULATEI = "TEXEL0", "0", "SHADE", "0", "0", "0", "0", "SHADE"
        self.G_CC_MODULATEIDECALA = "TEXEL0", "0", "SHADE", "0", "0", "0", "0", "TEXEL0"
        self.G_CC_MODULATEIFADE = "TEXEL0", "0", "SHADE", "0", "0", "0", "0", "ENVIRONMENT"

        self.G_CC_MODULATERGB = self.G_CC_MODULATEI
        self.G_CC_MODULATERGBDECALA = self.G_CC_MODULATEIDECALA
        self.G_CC_MODULATERGBFADE = self.G_CC_MODULATEIFADE

        self.G_CC_MODULATEIA = "TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"
        self.G_CC_MODULATEIFADEA = "TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "ENVIRONMENT", "0"

        self.G_CC_MODULATEFADE = "TEXEL0", "0", "SHADE", "0", "ENVIRONMENT", "0", "TEXEL0", "0"

        self.G_CC_MODULATERGBA = self.G_CC_MODULATEIA
        self.G_CC_MODULATERGBFADEA = self.G_CC_MODULATEIFADEA

        self.G_CC_MODULATEI_PRIM = "TEXEL0", "0", "PRIMITIVE", "0", "0", "0", "0", "PRIMITIVE"
        self.G_CC_MODULATEIA_PRIM = "TEXEL0", "0", "PRIMITIVE", "0", "TEXEL0", "0", "PRIMITIVE", "0"
        self.G_CC_MODULATEIDECALA_PRIM = "TEXEL0", "0", "PRIMITIVE", "0", "0", "0", "0", "TEXEL0"

        self.G_CC_MODULATERGB_PRIM = self.G_CC_MODULATEI_PRIM
        self.G_CC_MODULATERGBA_PRIM = self.G_CC_MODULATEIA_PRIM
        self.G_CC_MODULATERGBDECALA_PRIM = self.G_CC_MODULATEIDECALA_PRIM

        self.G_CC_FADE = "SHADE", "0", "ENVIRONMENT", "0", "SHADE", "0", "ENVIRONMENT", "0"
        self.G_CC_FADEA = "TEXEL0", "0", "ENVIRONMENT", "0", "TEXEL0", "0", "ENVIRONMENT", "0"

        self.G_CC_DECALRGB = "0", "0", "0", "TEXEL0", "0", "0", "0", "SHADE"
        self.G_CC_DECALRGBA = "0", "0", "0", "TEXEL0", "0", "0", "0", "TEXEL0"
        self.G_CC_DECALFADE = "0", "0", "0", "TEXEL0", "0", "0", "0", "ENVIRONMENT"

        self.G_CC_DECALFADEA = "0", "0", "0", "TEXEL0", "TEXEL0", "0", "ENVIRONMENT", "0"

        self.G_CC_BLENDI = "ENVIRONMENT", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"
        self.G_CC_BLENDIA = "ENVIRONMENT", "SHADE", "TEXEL0", "SHADE", "TEXEL0", "0", "SHADE", "0"
        self.G_CC_BLENDIDECALA = "ENVIRONMENT", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"

        self.G_CC_BLENDRGBA = "TEXEL0", "SHADE", "TEXEL0_ALPHA", "SHADE", "0", "0", "0", "SHADE"
        self.G_CC_BLENDRGBDECALA = "TEXEL0", "SHADE", "TEXEL0_ALPHA", "SHADE", "0", "0", "0", "TEXEL0"
        self.G_CC_BLENDRGBFADEA = "TEXEL0", "SHADE", "TEXEL0_ALPHA", "SHADE", "0", "0", "0", "ENVIRONMENT"

        self.G_CC_ADDRGB = "TEXEL0", "0", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"
        self.G_CC_ADDRGBDECALA = "TEXEL0", "0", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"
        self.G_CC_ADDRGBFADE = "TEXEL0", "0", "TEXEL0", "SHADE", "0", "0", "0", "ENVIRONMENT"

        self.G_CC_REFLECTRGB = "ENVIRONMENT", "0", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"
        self.G_CC_REFLECTRGBDECALA = "ENVIRONMENT", "0", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"

        self.G_CC_HILITERGB = "PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"
        self.G_CC_HILITERGBA = "PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "PRIMITIVE", "SHADE", "TEXEL0", "SHADE"
        self.G_CC_HILITERGBDECALA = "PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"

        self.G_CC_SHADEDECALA = "0", "0", "0", "SHADE", "0", "0", "0", "TEXEL0"
        self.G_CC_SHADEFADEA = "0", "0", "0", "SHADE", "0", "0", "0", "ENVIRONMENT"

        self.G_CC_BLENDPE = "PRIMITIVE", "ENVIRONMENT", "TEXEL0", "ENVIRONMENT", "TEXEL0", "0", "SHADE", "0"
        self.G_CC_BLENDPEDECALA = "PRIMITIVE", "ENVIRONMENT", "TEXEL0", "ENVIRONMENT", "0", "0", "0", "TEXEL0"

        # oddball modes
        self._G_CC_BLENDPE = "ENVIRONMENT", "PRIMITIVE", "TEXEL0", "PRIMITIVE", "TEXEL0", "0", "SHADE", "0"
        self._G_CC_BLENDPEDECALA = "ENVIRONMENT", "PRIMITIVE", "TEXEL0", "PRIMITIVE", "0", "0", "0", "TEXEL0"
        self._G_CC_TWOCOLORTEX = "PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"

        # used for 1-cycle sparse mip-maps, primitive color has color of lowest LOD
        self._G_CC_SPARSEST = (
            "PRIMITIVE",
            "TEXEL0",
            "LOD_FRACTION",
            "TEXEL0",
            "PRIMITIVE",
            "TEXEL0",
            "LOD_FRACTION",
            "TEXEL0",
        )
        self.G_CC_TEMPLERP = (
            "TEXEL1",
            "TEXEL0",
            "PRIM_LOD_FRAC",
            "TEXEL0",
            "TEXEL1",
            "TEXEL0",
            "PRIM_LOD_FRAC",
            "TEXEL0",
        )

        # typical CC cycle 1 modes, usually followed by other cycle 2 modes
        self.G_CC_TRILERP = "TEXEL1", "TEXEL0", "LOD_FRACTION", "TEXEL0", "TEXEL1", "TEXEL0", "LOD_FRACTION", "TEXEL0"
        self.G_CC_INTERFERENCE = "TEXEL0", "0", "TEXEL1", "0", "TEXEL0", "0", "TEXEL1", "0"

        self.G_CC_1CYUV2RGB = "TEXEL0", "K4", "K5", "TEXEL0", "0", "0", "0", "SHADE"
        self.G_CC_YUV2RGB = "TEXEL1", "K4", "K5", "TEXEL1", "0", "0", "0", "0"

        # typical CC cycle 2 modes
        self.G_CC_PASS2 = "0", "0", "0", "COMBINED", "0", "0", "0", "COMBINED"
        self.G_CC_MODULATEI2 = "COMBINED", "0", "SHADE", "0", "0", "0", "0", "SHADE"
        self.G_CC_MODULATEIA2 = "COMBINED", "0", "SHADE", "0", "COMBINED", "0", "SHADE", "0"
        self.G_CC_MODULATERGB2 = self.G_CC_MODULATEI2
        self.G_CC_MODULATERGBA2 = self.G_CC_MODULATEIA2
        self.G_CC_MODULATEI_PRIM2 = "COMBINED", "0", "PRIMITIVE", "0", "0", "0", "0", "PRIMITIVE"
        self.G_CC_MODULATEIA_PRIM2 = "COMBINED", "0", "PRIMITIVE", "0", "COMBINED", "0", "PRIMITIVE", "0"
        self.G_CC_MODULATERGB_PRIM2 = self.G_CC_MODULATEI_PRIM2
        self.G_CC_MODULATERGBA_PRIM2 = self.G_CC_MODULATEIA_PRIM2
        self.G_CC_DECALRGB2 = "0", "0", "0", "COMBINED", "0", "0", "0", "SHADE"

        self.G_CC_DECALRGBA2 = "COMBINED", "SHADE", "COMBINED_ALPHA", "SHADE", "0", "0", "0", "SHADE"
        self.G_CC_BLENDI2 = "ENVIRONMENT", "SHADE", "COMBINED", "SHADE", "0", "0", "0", "SHADE"
        self.G_CC_BLENDIA2 = "ENVIRONMENT", "SHADE", "COMBINED", "SHADE", "COMBINED", "0", "SHADE", "0"
        self.G_CC_CHROMA_KEY2 = "TEXEL0", "CENTER", "SCALE", "0", "0", "0", "0", "0"
        self.G_CC_HILITERGB2 = "ENVIRONMENT", "COMBINED", "TEXEL0", "COMBINED", "0", "0", "0", "SHADE"
        self.G_CC_HILITERGBA2 = (
            "ENVIRONMENT",
            "COMBINED",
            "TEXEL0",
            "COMBINED",
            "ENVIRONMENT",
            "COMBINED",
            "TEXEL0",
            "COMBINED",
        )
        self.G_CC_HILITERGBDECALA2 = "ENVIRONMENT", "COMBINED", "TEXEL0", "COMBINED", "0", "0", "0", "TEXEL0"
        self.G_CC_HILITERGBPASSA2 = "ENVIRONMENT", "COMBINED", "TEXEL0", "COMBINED", "0", "0", "0", "COMBINED"

        # G_SETOTHERMODE_L sft: shift count

        self.G_MDSFT_ALPHACOMPARE = G_MDSFT_ALPHACOMPARE = 0
        self.G_MDSFT_ZSRCSEL = G_MDSFT_ZSRCSEL = 2
        self.G_MDSFT_RENDERMODE = G_MDSFT_RENDERMODE = 3
        self.G_MDSFT_BLENDER = G_MDSFT_BLENDER = 16

        # G_SETOTHERMODE_H sft: shift count

        self.G_MDSFT_BLENDMASK = G_MDSFT_BLENDMASK = 0  # unsupported
        self.G_MDSFT_ALPHADITHER = G_MDSFT_ALPHADITHER = 4
        self.G_MDSFT_RGBDITHER = G_MDSFT_RGBDITHER = 6

        self.G_MDSFT_COMBKEY = G_MDSFT_COMBKEY = 8
        self.G_MDSFT_TEXTCONV = G_MDSFT_TEXTCONV = 9
        self.G_MDSFT_TEXTFILT = G_MDSFT_TEXTFILT = 12
        self.G_MDSFT_TEXTLUT = G_MDSFT_TEXTLUT = 14
        self.G_MDSFT_TEXTLOD = G_MDSFT_TEXTLOD = 16
        self.G_MDSFT_TEXTDETAIL = G_MDSFT_TEXTDETAIL = 17
        self.G_MDSFT_TEXTPERSP = G_MDSFT_TEXTPERSP = 19
        self.G_MDSFT_CYCLETYPE = G_MDSFT_CYCLETYPE = 20
        self.G_MDSFT_COLORDITHER = G_MDSFT_COLORDITHER = 22  # unsupported in HW 2.0
        self.G_MDSFT_PIPELINE = G_MDSFT_PIPELINE = 23

        # G_SETOTHERMODE_H gPipelineMode
        self.G_PM_1PRIMITIVE = 1 << G_MDSFT_PIPELINE
        self.G_PM_NPRIMITIVE = 0 << G_MDSFT_PIPELINE

        # G_SETOTHERMODE_H gSetCycleType
        self.G_CYC_1CYCLE = 0 << G_MDSFT_CYCLETYPE
        self.G_CYC_2CYCLE = 1 << G_MDSFT_CYCLETYPE
        self.G_CYC_COPY = 2 << G_MDSFT_CYCLETYPE
        self.G_CYC_FILL = 3 << G_MDSFT_CYCLETYPE

        # G_SETOTHERMODE_H gSetTexturePersp
        self.G_TP_NONE = 0 << G_MDSFT_TEXTPERSP
        self.G_TP_PERSP = 1 << G_MDSFT_TEXTPERSP

        # G_SETOTHERMODE_H gSetTextureDetail
        self.G_TD_CLAMP = 0 << G_MDSFT_TEXTDETAIL
        self.G_TD_SHARPEN = 1 << G_MDSFT_TEXTDETAIL
        self.G_TD_DETAIL = 2 << G_MDSFT_TEXTDETAIL

        # G_SETOTHERMODE_H gSetTextureLOD
        self.G_TL_TILE = 0 << G_MDSFT_TEXTLOD
        self.G_TL_LOD = 1 << G_MDSFT_TEXTLOD

        # G_SETOTHERMODE_H gSetTextureLUT
        self.G_TT_NONE = 0 << G_MDSFT_TEXTLUT
        self.G_TT_RGBA16 = 2 << G_MDSFT_TEXTLUT
        self.G_TT_IA16 = 3 << G_MDSFT_TEXTLUT

        # G_SETOTHERMODE_H gSetTextureFilter
        self.G_TF_POINT = 0 << G_MDSFT_TEXTFILT
        self.G_TF_AVERAGE = 3 << G_MDSFT_TEXTFILT
        self.G_TF_BILERP = 2 << G_MDSFT_TEXTFILT

        # G_SETOTHERMODE_H gSetTextureConvert
        self.G_TC_CONV = 0 << G_MDSFT_TEXTCONV
        self.G_TC_FILTCONV = 5 << G_MDSFT_TEXTCONV
        self.G_TC_FILT = 6 << G_MDSFT_TEXTCONV

        # G_SETOTHERMODE_H gSetCombineKey
        self.G_CK_NONE = 0 << G_MDSFT_COMBKEY
        self.G_CK_KEY = 1 << G_MDSFT_COMBKEY

        # G_SETOTHERMODE_H gSetColorDither
        self.G_CD_MAGICSQ = 0 << G_MDSFT_RGBDITHER
        self.G_CD_BAYER = 1 << G_MDSFT_RGBDITHER
        self.G_CD_NOISE = 2 << G_MDSFT_RGBDITHER
        self.G_CD_DISABLE = 3 << G_MDSFT_RGBDITHER
        self.G_CD_ENABLE = self.G_CD_NOISE

        # G_SETOTHERMODE_H gSetAlphaDither
        self.G_AD_PATTERN = 0 << G_MDSFT_ALPHADITHER
        self.G_AD_NOTPATTERN = 1 << G_MDSFT_ALPHADITHER
        self.G_AD_NOISE = 2 << G_MDSFT_ALPHADITHER
        self.G_AD_DISABLE = 3 << G_MDSFT_ALPHADITHER

        # G_SETOTHERMODE_L gSetAlphaCompare
        self.G_AC_NONE = 0 << G_MDSFT_ALPHACOMPARE
        self.G_AC_THRESHOLD = 1 << G_MDSFT_ALPHACOMPARE
        self.G_AC_DITHER = 3 << G_MDSFT_ALPHACOMPARE

        # G_SETOTHERMODE_L gSetDepthSource
        self.G_ZS_PIXEL = 0 << G_MDSFT_ZSRCSEL
        self.G_ZS_PRIM = 1 << G_MDSFT_ZSRCSEL

        # G_SETOTHERMODE_L gSetRenderMode
        self.AA_EN = AA_EN = 0x8
        self.Z_CMP = Z_CMP = 0x10
        self.Z_UPD = Z_UPD = 0x20
        self.IM_RD = IM_RD = 0x40
        self.CLR_ON_CVG = CLR_ON_CVG = 0x80
        self.CVG_DST_CLAMP = CVG_DST_CLAMP = 0
        self.CVG_DST_WRAP = CVG_DST_WRAP = 0x100
        self.CVG_DST_FULL = CVG_DST_FULL = 0x200
        self.CVG_DST_SAVE = CVG_DST_SAVE = 0x300
        self.ZMODE_OPA = ZMODE_OPA = 0
        self.ZMODE_INTER = ZMODE_INTER = 0x400
        self.ZMODE_XLU = ZMODE_XLU = 0x800
        self.ZMODE_DEC = ZMODE_DEC = 0xC00
        self.CVG_X_ALPHA = CVG_X_ALPHA = 0x1000
        self.ALPHA_CVG_SEL = ALPHA_CVG_SEL = 0x2000
        self.FORCE_BL = FORCE_BL = 0x4000
        self.TEX_EDGE = TEX_EDGE = 0x0000  # used to be 0x8000

        self.G_BL_CLR_IN = G_BL_CLR_IN = 0
        self.G_BL_CLR_MEM = G_BL_CLR_MEM = 1
        self.G_BL_CLR_BL = G_BL_CLR_BL = 2
        self.G_BL_CLR_FOG = G_BL_CLR_FOG = 3
        self.G_BL_1MA = G_BL_1MA = 0
        self.G_BL_A_MEM = G_BL_A_MEM = 1
        self.G_BL_A_IN = G_BL_A_IN = 0
        self.G_BL_A_FOG = G_BL_A_FOG = 1
        self.G_BL_A_SHADE = G_BL_A_SHADE = 2
        self.G_BL_1 = G_BL_1 = 2
        self.G_BL_0 = G_BL_0 = 3

        self.cvgDstDict = {
            CVG_DST_CLAMP: "CVG_DST_CLAMP",
            CVG_DST_WRAP: "CVG_DST_WRAP",
            CVG_DST_FULL: "CVG_DST_FULL",
            CVG_DST_SAVE: "CVG_DST_SAVE",
        }

        self.zmodeDict = {
            ZMODE_OPA: "ZMODE_OPA",
            ZMODE_INTER: "ZMODE_INTER",
            ZMODE_XLU: "ZMODE_XLU",
            ZMODE_DEC: "ZMODE_DEC",
        }

        self.blendColorDict = {
            G_BL_CLR_IN: "G_BL_CLR_IN",
            G_BL_CLR_MEM: "G_BL_CLR_MEM",
            G_BL_CLR_BL: "G_BL_CLR_BL",
            G_BL_CLR_FOG: "G_BL_CLR_FOG",
        }

        self.blendAlphaDict = {
            G_BL_A_IN: "G_BL_A_IN",
            G_BL_A_FOG: "G_BL_A_FOG",
            G_BL_A_SHADE: "G_BL_A_SHADE",
            G_BL_0: "G_BL_0",
        }

        self.blendMixDict = {
            G_BL_1MA: "G_BL_1MA",
            G_BL_A_MEM: "G_BL_A_MEM",
            G_BL_1: "G_BL_1",
            G_BL_0: "G_BL_0",
        }

        def GBL_c1(m1a, m1b, m2a, m2b):
            return (m1a) << 30 | (m1b) << 26 | (m2a) << 22 | (m2b) << 18

        def GBL_c2(m1a, m1b, m2a, m2b):
            return (m1a) << 28 | (m1b) << 24 | (m2a) << 20 | (m2b) << 16

        def RM_AA_ZB_OPA_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_RA_ZB_OPA_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_ZB_XLU_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | IM_RD
                | CVG_DST_WRAP
                | CLR_ON_CVG
                | FORCE_BL
                | ZMODE_XLU
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_OPA_DECAL(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | IM_RD
                | CVG_DST_WRAP
                | ALPHA_CVG_SEL
                | ZMODE_DEC
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_RA_ZB_OPA_DECAL(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | CVG_DST_WRAP
                | ALPHA_CVG_SEL
                | ZMODE_DEC
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_ZB_XLU_DECAL(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | IM_RD
                | CVG_DST_WRAP
                | CLR_ON_CVG
                | FORCE_BL
                | ZMODE_DEC
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_OPA_INTER(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_CLAMP
                | ALPHA_CVG_SEL
                | ZMODE_INTER
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_RA_ZB_OPA_INTER(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | CVG_DST_CLAMP
                | ALPHA_CVG_SEL
                | ZMODE_INTER
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_ZB_XLU_INTER(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | IM_RD
                | CVG_DST_WRAP
                | CLR_ON_CVG
                | FORCE_BL
                | ZMODE_INTER
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_XLU_LINE(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | IM_RD
                | CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | FORCE_BL
                | ZMODE_XLU
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_DEC_LINE(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | IM_RD
                | CVG_DST_SAVE
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | FORCE_BL
                | ZMODE_DEC
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_TEX_EDGE(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | ZMODE_OPA
                | TEX_EDGE
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_ZB_TEX_INTER(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | ZMODE_INTER
                | TEX_EDGE
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_ZB_SUB_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_FULL
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_ZB_PCL_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | self.G_AC_DITHER
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_OPA_TERR(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_TEX_TERR(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | ZMODE_OPA
                | TEX_EDGE
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_ZB_SUB_TERR(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | Z_CMP
                | Z_UPD
                | IM_RD
                | CVG_DST_FULL
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_OPA_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_RA_OPA_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_XLU_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_WRAP
                | CLR_ON_CVG
                | FORCE_BL
                | ZMODE_OPA
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_XLU_LINE(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | FORCE_BL
                | ZMODE_OPA
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_DEC_LINE(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_FULL
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | FORCE_BL
                | ZMODE_OPA
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_TEX_EDGE(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | ZMODE_OPA
                | TEX_EDGE
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_SUB_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_FULL
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_AA_PCL_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | self.G_AC_DITHER
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_OPA_TERR(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_CLAMP
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_TEX_TERR(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | ZMODE_OPA
                | TEX_EDGE
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_AA_SUB_TERR(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                AA_EN
                | IM_RD
                | CVG_DST_FULL
                | ZMODE_OPA
                | ALPHA_CVG_SEL
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_ZB_OPA_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                Z_CMP
                | Z_UPD
                | CVG_DST_FULL
                | ALPHA_CVG_SEL
                | ZMODE_OPA
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_ZB_XLU_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                Z_CMP
                | IM_RD
                | CVG_DST_FULL
                | FORCE_BL
                | ZMODE_XLU
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_ZB_OPA_DECAL(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                Z_CMP
                | CVG_DST_FULL
                | ALPHA_CVG_SEL
                | ZMODE_DEC
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_A_MEM)
            )

        def RM_ZB_XLU_DECAL(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                Z_CMP
                | IM_RD
                | CVG_DST_FULL
                | FORCE_BL
                | ZMODE_DEC
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_ZB_CLD_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                Z_CMP
                | IM_RD
                | CVG_DST_SAVE
                | FORCE_BL
                | ZMODE_XLU
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_ZB_OVL_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                Z_CMP
                | IM_RD
                | CVG_DST_SAVE
                | FORCE_BL
                | ZMODE_DEC
                | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)
            )

        def RM_ZB_PCL_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                Z_CMP
                | Z_UPD
                | CVG_DST_FULL
                | ZMODE_OPA
                | self.G_AC_DITHER
                | func(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1)
            )

        def RM_OPA_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return CVG_DST_CLAMP | FORCE_BL | ZMODE_OPA | func(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1)

        def RM_XLU_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return IM_RD | CVG_DST_FULL | FORCE_BL | ZMODE_OPA | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)

        def RM_TEX_EDGE(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                CVG_DST_CLAMP
                | CVG_X_ALPHA
                | ALPHA_CVG_SEL
                | FORCE_BL
                | ZMODE_OPA
                | TEX_EDGE
                | AA_EN
                | func(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1)
            )

        def RM_CLD_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return IM_RD | CVG_DST_SAVE | FORCE_BL | ZMODE_OPA | func(G_BL_CLR_IN, G_BL_A_IN, G_BL_CLR_MEM, G_BL_1MA)

        def RM_PCL_SURF(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return (
                CVG_DST_FULL | FORCE_BL | ZMODE_OPA | self.G_AC_DITHER | func(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1)
            )

        def RM_ADD(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return IM_RD | CVG_DST_SAVE | FORCE_BL | ZMODE_OPA | func(G_BL_CLR_IN, G_BL_A_FOG, G_BL_CLR_MEM, G_BL_1)

        def RM_NOOP(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return func(0, 0, 0, 0)

        def RM_VISCVG(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return IM_RD | FORCE_BL | func(G_BL_CLR_IN, G_BL_0, G_BL_CLR_BL, G_BL_A_MEM)

        # for rendering to an 8-bit framebuffer
        def RM_OPA_CI(clk):
            func = GBL_c1 if clk == 1 else GBL_c2
            return CVG_DST_CLAMP | ZMODE_OPA | func(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1)

        self.G_RM_AA_ZB_OPA_SURF = RM_AA_ZB_OPA_SURF(1)
        self.G_RM_AA_ZB_OPA_SURF2 = RM_AA_ZB_OPA_SURF(2)
        self.G_RM_AA_ZB_XLU_SURF = RM_AA_ZB_XLU_SURF(1)
        self.G_RM_AA_ZB_XLU_SURF2 = RM_AA_ZB_XLU_SURF(2)
        self.G_RM_AA_ZB_OPA_DECAL = RM_AA_ZB_OPA_DECAL(1)
        self.G_RM_AA_ZB_OPA_DECAL2 = RM_AA_ZB_OPA_DECAL(2)
        self.G_RM_AA_ZB_XLU_DECAL = RM_AA_ZB_XLU_DECAL(1)
        self.G_RM_AA_ZB_XLU_DECAL2 = RM_AA_ZB_XLU_DECAL(2)
        self.G_RM_AA_ZB_OPA_INTER = RM_AA_ZB_OPA_INTER(1)
        self.G_RM_AA_ZB_OPA_INTER2 = RM_AA_ZB_OPA_INTER(2)
        self.G_RM_AA_ZB_XLU_INTER = RM_AA_ZB_XLU_INTER(1)
        self.G_RM_AA_ZB_XLU_INTER2 = RM_AA_ZB_XLU_INTER(2)
        self.G_RM_AA_ZB_XLU_LINE = RM_AA_ZB_XLU_LINE(1)
        self.G_RM_AA_ZB_XLU_LINE2 = RM_AA_ZB_XLU_LINE(2)
        self.G_RM_AA_ZB_DEC_LINE = RM_AA_ZB_DEC_LINE(1)
        self.G_RM_AA_ZB_DEC_LINE2 = RM_AA_ZB_DEC_LINE(2)
        self.G_RM_AA_ZB_TEX_EDGE = RM_AA_ZB_TEX_EDGE(1)
        self.G_RM_AA_ZB_TEX_EDGE2 = RM_AA_ZB_TEX_EDGE(2)
        self.G_RM_AA_ZB_TEX_INTER = RM_AA_ZB_TEX_INTER(1)
        self.G_RM_AA_ZB_TEX_INTER2 = RM_AA_ZB_TEX_INTER(2)
        self.G_RM_AA_ZB_SUB_SURF = RM_AA_ZB_SUB_SURF(1)
        self.G_RM_AA_ZB_SUB_SURF2 = RM_AA_ZB_SUB_SURF(2)
        self.G_RM_AA_ZB_PCL_SURF = RM_AA_ZB_PCL_SURF(1)
        self.G_RM_AA_ZB_PCL_SURF2 = RM_AA_ZB_PCL_SURF(2)
        self.G_RM_AA_ZB_OPA_TERR = RM_AA_ZB_OPA_TERR(1)
        self.G_RM_AA_ZB_OPA_TERR2 = RM_AA_ZB_OPA_TERR(2)
        self.G_RM_AA_ZB_TEX_TERR = RM_AA_ZB_TEX_TERR(1)
        self.G_RM_AA_ZB_TEX_TERR2 = RM_AA_ZB_TEX_TERR(2)
        self.G_RM_AA_ZB_SUB_TERR = RM_AA_ZB_SUB_TERR(1)
        self.G_RM_AA_ZB_SUB_TERR2 = RM_AA_ZB_SUB_TERR(2)

        self.G_RM_RA_ZB_OPA_SURF = RM_RA_ZB_OPA_SURF(1)
        self.G_RM_RA_ZB_OPA_SURF2 = RM_RA_ZB_OPA_SURF(2)
        self.G_RM_RA_ZB_OPA_DECAL = RM_RA_ZB_OPA_DECAL(1)
        self.G_RM_RA_ZB_OPA_DECAL2 = RM_RA_ZB_OPA_DECAL(2)
        self.G_RM_RA_ZB_OPA_INTER = RM_RA_ZB_OPA_INTER(1)
        self.G_RM_RA_ZB_OPA_INTER2 = RM_RA_ZB_OPA_INTER(2)

        self.G_RM_AA_OPA_SURF = RM_AA_OPA_SURF(1)
        self.G_RM_AA_OPA_SURF2 = RM_AA_OPA_SURF(2)
        self.G_RM_AA_XLU_SURF = RM_AA_XLU_SURF(1)
        self.G_RM_AA_XLU_SURF2 = RM_AA_XLU_SURF(2)
        self.G_RM_AA_XLU_LINE = RM_AA_XLU_LINE(1)
        self.G_RM_AA_XLU_LINE2 = RM_AA_XLU_LINE(2)
        self.G_RM_AA_DEC_LINE = RM_AA_DEC_LINE(1)
        self.G_RM_AA_DEC_LINE2 = RM_AA_DEC_LINE(2)
        self.G_RM_AA_TEX_EDGE = RM_AA_TEX_EDGE(1)
        self.G_RM_AA_TEX_EDGE2 = RM_AA_TEX_EDGE(2)
        self.G_RM_AA_SUB_SURF = RM_AA_SUB_SURF(1)
        self.G_RM_AA_SUB_SURF2 = RM_AA_SUB_SURF(2)
        self.G_RM_AA_PCL_SURF = RM_AA_PCL_SURF(1)
        self.G_RM_AA_PCL_SURF2 = RM_AA_PCL_SURF(2)
        self.G_RM_AA_OPA_TERR = RM_AA_OPA_TERR(1)
        self.G_RM_AA_OPA_TERR2 = RM_AA_OPA_TERR(2)
        self.G_RM_AA_TEX_TERR = RM_AA_TEX_TERR(1)
        self.G_RM_AA_TEX_TERR2 = RM_AA_TEX_TERR(2)
        self.G_RM_AA_SUB_TERR = RM_AA_SUB_TERR(1)
        self.G_RM_AA_SUB_TERR2 = RM_AA_SUB_TERR(2)

        self.G_RM_RA_OPA_SURF = RM_RA_OPA_SURF(1)
        self.G_RM_RA_OPA_SURF2 = RM_RA_OPA_SURF(2)

        self.G_RM_ZB_OPA_SURF = RM_ZB_OPA_SURF(1)
        self.G_RM_ZB_OPA_SURF2 = RM_ZB_OPA_SURF(2)
        self.G_RM_ZB_XLU_SURF = RM_ZB_XLU_SURF(1)
        self.G_RM_ZB_XLU_SURF2 = RM_ZB_XLU_SURF(2)
        self.G_RM_ZB_OPA_DECAL = RM_ZB_OPA_DECAL(1)
        self.G_RM_ZB_OPA_DECAL2 = RM_ZB_OPA_DECAL(2)
        self.G_RM_ZB_XLU_DECAL = RM_ZB_XLU_DECAL(1)
        self.G_RM_ZB_XLU_DECAL2 = RM_ZB_XLU_DECAL(2)
        self.G_RM_ZB_CLD_SURF = RM_ZB_CLD_SURF(1)
        self.G_RM_ZB_CLD_SURF2 = RM_ZB_CLD_SURF(2)
        self.G_RM_ZB_OVL_SURF = RM_ZB_OVL_SURF(1)
        self.G_RM_ZB_OVL_SURF2 = RM_ZB_OVL_SURF(2)
        self.G_RM_ZB_PCL_SURF = RM_ZB_PCL_SURF(1)
        self.G_RM_ZB_PCL_SURF2 = RM_ZB_PCL_SURF(2)

        self.G_RM_OPA_SURF = RM_OPA_SURF(1)
        self.G_RM_OPA_SURF2 = RM_OPA_SURF(2)
        self.G_RM_XLU_SURF = RM_XLU_SURF(1)
        self.G_RM_XLU_SURF2 = RM_XLU_SURF(2)
        self.G_RM_CLD_SURF = RM_CLD_SURF(1)
        self.G_RM_CLD_SURF2 = RM_CLD_SURF(2)
        self.G_RM_TEX_EDGE = RM_TEX_EDGE(1)
        self.G_RM_TEX_EDGE2 = RM_TEX_EDGE(2)
        self.G_RM_PCL_SURF = RM_PCL_SURF(1)
        self.G_RM_PCL_SURF2 = RM_PCL_SURF(2)
        self.G_RM_ADD = RM_ADD(1)
        self.G_RM_ADD2 = RM_ADD(2)
        self.G_RM_NOOP = RM_NOOP(1)
        self.G_RM_NOOP2 = RM_NOOP(2)
        self.G_RM_VISCVG = RM_VISCVG(1)
        self.G_RM_VISCVG2 = RM_VISCVG(2)
        self.G_RM_OPA_CI = RM_OPA_CI(1)
        self.G_RM_OPA_CI2 = RM_OPA_CI(2)

        self.G_RM_FOG_SHADE_A = GBL_c1(G_BL_CLR_FOG, G_BL_A_SHADE, G_BL_CLR_IN, G_BL_1MA)
        self.G_RM_FOG_PRIM_A = GBL_c1(G_BL_CLR_FOG, G_BL_A_FOG, G_BL_CLR_IN, G_BL_1MA)
        self.G_RM_PASS = GBL_c1(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1)

        self.rendermodePresetsWithoutFlags = {
            "G_RM_NOOP",
            "G_RM_NOOP2",
            "G_RM_FOG_SHADE_A",
            "G_RM_FOG_PRIM_A",
            "G_RM_PASS",
        }

        # G_SETCONVERT: K0-5

        self.G_CV_K0 = 175
        self.G_CV_K1 = -43
        self.G_CV_K2 = -89
        self.G_CV_K3 = 222
        self.G_CV_K4 = 114
        self.G_CV_K5 = 42

        # G_SETSCISSOR: interlace mode

        self.G_SC_NON_INTERLACE = 0
        self.G_SC_ODD_INTERLACE = 3
        self.G_SC_EVEN_INTERLACE = 2

        # flags to inhibit pushing of the display list (on branch)
        self.G_DL_PUSH = 0x00
        self.G_DL_NOPUSH = 0x01

        if F3DEX_GBI_3:
            self.G_NORMALS_MODE_FAST = 0x00
            self.G_NORMALS_MODE_AUTO = 0x01
            self.G_NORMALS_MODE_MANUAL = 0x02

            self.G_ALPHA_COMPARE_CULL_DISABLE = 0
            self.G_ALPHA_COMPARE_CULL_BELOW = 1
            self.G_ALPHA_COMPARE_CULL_ABOVE = -1

        # Some structs here

        self.G_MAXZ = 0x03FF  # 10 bits of integer screen-Z precision

        # more structs here

        """
		MOVEMEM indices
		
		Each of these indexes an entry in a dmem table
		which points to a 1-4 word block of dmem in
		which to store a 1-4 word DMA.
		"""

        if F3DEX_GBI_2:
            # 0,4 are reserved by G_MTX
            self.G_MV_MMTX = 2
            self.G_MV_PMTX = 6
            self.G_MV_VIEWPORT = 8
            self.G_MV_LIGHT = 10
            if not F3DEX_GBI_3:
                self.G_MV_POINT = 12
                self.G_MV_MATRIX = 14  # NOTE: this is in moveword table
                self.G_MVO_LOOKATX = 0 * 24
                self.G_MVO_LOOKATY = 1 * 24
                self.G_MVO_L0 = 2 * 24
                self.G_MVO_L1 = 3 * 24
                self.G_MVO_L2 = 4 * 24
                self.G_MVO_L3 = 5 * 24
                self.G_MVO_L4 = 6 * 24
                self.G_MVO_L5 = 7 * 24
                self.G_MVO_L6 = 8 * 24
                self.G_MVO_L7 = 9 * 24
        else:
            self.G_MV_VIEWPORT = 0x80
            self.G_MV_LOOKATY = 0x82
            self.G_MV_LOOKATX = 0x84
            self.G_MV_L0 = 0x86
            self.G_MV_L1 = 0x88
            self.G_MV_L2 = 0x8A
            self.G_MV_L3 = 0x8C
            self.G_MV_L4 = 0x8E
            self.G_MV_L5 = 0x90
            self.G_MV_L6 = 0x92
            self.G_MV_L7 = 0x94
            self.G_MV_TXTATT = 0x96
            self.G_MV_MATRIX_1 = 0x9E  # NOTE: this is in moveword table
            self.G_MV_MATRIX_2 = 0x98
            self.G_MV_MATRIX_3 = 0x9A
            self.G_MV_MATRIX_4 = 0x9C

        """
		MOVEWORD indices
		
		Each of these indexes an entry in a dmem table
		which points to a word in dmem in dmem where
		an immediate word will be stored.
		"""

        if F3DEX_GBI_3:
            self.G_MW_FX = 0x00
        else:
            self.G_MW_MATRIX = 0x00  # NOTE: also used by movemem
        self.G_MW_NUMLIGHT = 0x02
        if not F3DEX_GBI_3:
            self.G_MW_CLIP = 0x04
        self.G_MW_SEGMENT = 0x06
        self.G_MW_FOG = 0x08
        self.G_MW_LIGHTCOL = 0x0A
        if not F3DEX_GBI_3:
            if F3DEX_GBI_2:
                self.G_MW_FORCEMTX = 0x0C
            else:
                self.G_MW_POINTS = 0x0C
            self.G_MW_PERSPNORM = 0x0E

        if F3DEX_GBI_3:
            self.G_MW_HALFWORD_FLAG = 0x8000

        # These are offsets from the address in the dmem table

        self.G_MWO_NUMLIGHT = 0x00
        self.G_MWO_CLIP_RNX = 0x04
        self.G_MWO_CLIP_RNY = 0x0C
        self.G_MWO_CLIP_RPX = 0x14
        self.G_MWO_CLIP_RPY = 0x1C
        self.G_MWO_SEGMENT_0 = 0x00
        self.G_MWO_SEGMENT_1 = 0x01
        self.G_MWO_SEGMENT_2 = 0x02
        self.G_MWO_SEGMENT_3 = 0x03
        self.G_MWO_SEGMENT_4 = 0x04
        self.G_MWO_SEGMENT_5 = 0x05
        self.G_MWO_SEGMENT_6 = 0x06
        self.G_MWO_SEGMENT_7 = 0x07
        self.G_MWO_SEGMENT_8 = 0x08
        self.G_MWO_SEGMENT_9 = 0x09
        self.G_MWO_SEGMENT_A = 0x0A
        self.G_MWO_SEGMENT_B = 0x0B
        self.G_MWO_SEGMENT_C = 0x0C
        self.G_MWO_SEGMENT_D = 0x0D
        self.G_MWO_SEGMENT_E = 0x0E
        self.G_MWO_SEGMENT_F = 0x0F
        self.G_MWO_FOG = 0x00
        self.G_MWO_aLIGHT_1 = 0x00
        self.G_MWO_bLIGHT_1 = 0x04

        if F3DEX_GBI_3:
            self.G_MWO_aLIGHT_2 = 0x10
            self.G_MWO_bLIGHT_2 = 0x14
            self.G_MWO_aLIGHT_3 = 0x20
            self.G_MWO_bLIGHT_3 = 0x24
            self.G_MWO_aLIGHT_4 = 0x30
            self.G_MWO_bLIGHT_4 = 0x34
            self.G_MWO_aLIGHT_5 = 0x40
            self.G_MWO_bLIGHT_5 = 0x44
            self.G_MWO_aLIGHT_6 = 0x50
            self.G_MWO_bLIGHT_6 = 0x54
            self.G_MWO_aLIGHT_7 = 0x60
            self.G_MWO_bLIGHT_7 = 0x64
            self.G_MWO_aLIGHT_8 = 0x70
            self.G_MWO_bLIGHT_8 = 0x74
            self.G_MWO_aLIGHT_9 = 0x80
            self.G_MWO_bLIGHT_9 = 0x84
            self.G_MWO_aLIGHT_10 = 0x90
            self.G_MWO_bLIGHT_10 = 0x94
        elif F3DEX_GBI_2:
            self.G_MWO_aLIGHT_2 = 0x18
            self.G_MWO_bLIGHT_2 = 0x1C
            self.G_MWO_aLIGHT_3 = 0x30
            self.G_MWO_bLIGHT_3 = 0x34
            self.G_MWO_aLIGHT_4 = 0x48
            self.G_MWO_bLIGHT_4 = 0x4C
            self.G_MWO_aLIGHT_5 = 0x60
            self.G_MWO_bLIGHT_5 = 0x64
            self.G_MWO_aLIGHT_6 = 0x78
            self.G_MWO_bLIGHT_6 = 0x7C
            self.G_MWO_aLIGHT_7 = 0x90
            self.G_MWO_bLIGHT_7 = 0x94
            self.G_MWO_aLIGHT_8 = 0xA8
            self.G_MWO_bLIGHT_8 = 0xAC
        else:
            self.G_MWO_aLIGHT_2 = 0x20
            self.G_MWO_bLIGHT_2 = 0x24
            self.G_MWO_aLIGHT_3 = 0x40
            self.G_MWO_bLIGHT_3 = 0x44
            self.G_MWO_aLIGHT_4 = 0x60
            self.G_MWO_bLIGHT_4 = 0x64
            self.G_MWO_aLIGHT_5 = 0x80
            self.G_MWO_bLIGHT_5 = 0x84
            self.G_MWO_aLIGHT_6 = 0xA0
            self.G_MWO_bLIGHT_6 = 0xA4
            self.G_MWO_aLIGHT_7 = 0xC0
            self.G_MWO_bLIGHT_7 = 0xC4
            self.G_MWO_aLIGHT_8 = 0xE0
            self.G_MWO_bLIGHT_8 = 0xE4

        if not F3DEX_GBI_3:
            self.G_MWO_MATRIX_XX_XY_I = 0x00
            self.G_MWO_MATRIX_XZ_XW_I = 0x04
            self.G_MWO_MATRIX_YX_YY_I = 0x08
            self.G_MWO_MATRIX_YZ_YW_I = 0x0C
            self.G_MWO_MATRIX_ZX_ZY_I = 0x10
            self.G_MWO_MATRIX_ZZ_ZW_I = 0x14
            self.G_MWO_MATRIX_WX_WY_I = 0x18
            self.G_MWO_MATRIX_WZ_WW_I = 0x1C
            self.G_MWO_MATRIX_XX_XY_F = 0x20
            self.G_MWO_MATRIX_XZ_XW_F = 0x24
            self.G_MWO_MATRIX_YX_YY_F = 0x28
            self.G_MWO_MATRIX_YZ_YW_F = 0x2C
            self.G_MWO_MATRIX_ZX_ZY_F = 0x30
            self.G_MWO_MATRIX_ZZ_ZW_F = 0x34
            self.G_MWO_MATRIX_WX_WY_F = 0x38
            self.G_MWO_MATRIX_WZ_WW_F = 0x3C

        self.G_MWO_POINT_RGBA = 0x10
        self.G_MWO_POINT_ST = 0x14
        self.G_MWO_POINT_XYSCREEN = 0x18
        self.G_MWO_POINT_ZSCREEN = 0x1C

        if F3DEX_GBI_3:
            self.G_MWO_AO_AMBIENT = 0x00
            self.G_MWO_AO_DIRECTIONAL = 0x02
            self.G_MWO_AO_POINT = 0x04
            self.G_MWO_PERSPNORM = 0x06
            self.G_MWO_FRESNEL_SCALE = 0x0C
            self.G_MWO_FRESNEL_OFFSET = 0x0E
            self.G_MWO_ATTR_OFFSET_S = 0x10
            self.G_MWO_ATTR_OFFSET_T = 0x12
            self.G_MWO_ATTR_OFFSET_Z = 0x14
            self.G_MWO_ALPHA_COMPARE_CULL = 0x16
            self.G_MWO_NORMALS_MODE = 0x18

        # Texturing macros

        # These are also defined defined above for Sprite Microcode
        self.G_TX_LOADTILE = 7
        self.G_TX_RENDERTILE = 0

        self.G_TX_NOMIRROR = 0
        self.G_TX_WRAP = 0
        self.G_TX_MIRROR = 0x1
        self.G_TX_CLAMP = 0x2
        self.G_TX_NOMASK = 0
        self.G_TX_NOLOD = 0

        """
		Dxt is the inverse of the number of 64-bit words in a line of
		the texture being loaded using the load_block command.  If
		there are any 1's to the right of the 11th fractional bit,
		dxt should be rounded up.  The following macros accomplish
		this.  The 4b macros are a special case since 4-bit textures
		are loaded as 8-bit textures.  Dxt is fixed point 1.11. RJM
		"""
        self.G_TX_DXT_FRAC = 11

        """
		For RCP 2.0, the maximum number of texels that can be loaded
		using a load_block command is 2048.  In order to load the total
		4kB of Tmem, change the texel size when loading to be G_IM_SIZ_16b,
		then change the tile to the proper texel size after the load.
		The g*DPLoadTextureBlock macros already do this, so this change
		will be transparent if you use these macros.  If you use
		the g*DPLoadBlock macros directly, you will need to handle this
		tile manipulation yourself.  RJM.
		"""

        self.G_TX_LDBLK_MAX_TXL = 2047

        if not F3DEX_GBI_3:
            # Clipping Macros
            self.FR_NEG_FRUSTRATIO_1 = 0x00000001
            self.FR_POS_FRUSTRATIO_1 = 0x0000FFFF
            self.FR_NEG_FRUSTRATIO_2 = 0x00000002
            self.FR_POS_FRUSTRATIO_2 = 0x0000FFFE
            self.FR_NEG_FRUSTRATIO_3 = 0x00000003
            self.FR_POS_FRUSTRATIO_3 = 0x0000FFFD
            self.FR_NEG_FRUSTRATIO_4 = 0x00000004
            self.FR_POS_FRUSTRATIO_4 = 0x0000FFFC
            self.FR_NEG_FRUSTRATIO_5 = 0x00000005
            self.FR_POS_FRUSTRATIO_5 = 0x0000FFFB
            self.FR_NEG_FRUSTRATIO_6 = 0x00000006
            self.FR_POS_FRUSTRATIO_6 = 0x0000FFFA

        self.G_BZ_PERSP = 0
        self.G_BZ_ORTHO = 1

        # Lighting Macros
        if F3DEX_GBI_3:
            self.numLights = {f"NUMLIGHTS_{n}": n for n in range(10)}
        else:
            self.numLights = {f"NUMLIGHTS_{n}": (1 if n == 0 else n) for n in range(8)}

    def GBL_c1(self, m1a, m1b, m2a, m2b):
        return (m1a) << 30 | (m1b) << 26 | (m2a) << 22 | (m2b) << 18

    def GBL_c2(self, m1a, m1b, m2a, m2b):
        return (m1a) << 28 | (m1b) << 24 | (m2a) << 20 | (m2b) << 16

    # macros for command parsing
    def GDMACMD(self, x):
        return x

    def GIMMCMD(self, x):
        return self.G_IMMFIRST - (x)

    def GRDPCMD(self, x):
        return 0xFF - (x)

    def GPACK_RGBA5551(self, r, g, b, a):
        return (((r) << 8) & 0xF800) | (((g) << 3) & 0x7C0) | (((b) >> 2) & 0x3E) | ((a) & 0x1)

    def GPACK_ZDZ(self, z, dz):
        return (z) << 2 | (dz)

    def TXL2WORDS(self, txls, b_txl):
        return int(max(1, ((txls) * (b_txl) / 8)))

    def CALC_DXT(self, width, b_txl):
        return int(((1 << self.G_TX_DXT_FRAC) + self.TXL2WORDS(width, b_txl) - 1) / self.TXL2WORDS(width, b_txl))

    def TXL2WORDS_4b(self, txls):
        return int(max(1, ((txls) / 16)))

    def CALC_DXT_4b(self, width):
        return int(((1 << self.G_TX_DXT_FRAC) + self.TXL2WORDS_4b(width) - 1) / self.TXL2WORDS_4b(width))

    def NUML(self, n):
        if self.F3DEX_GBI_3:
            return n * 0x10
        nVal = self.numLights[n]
        return ((nVal) * 24) if self.F3DEX_GBI_2 else (((nVal) + 1) * 32 + 0x80000000)

    def getLightMWO_a(self, n):
        if n.startswith("G_MWO_aLIGHT_") and hasattr(self, n):
            return getattr(self, n)
        else:
            raise PluginError("Invalid G_MWO_a value for lights: " + n)

    def getLightMWO_b(self, n):
        if n.startswith("G_MWO_bLIGHT_") and hasattr(self, n):
            return getattr(self, n)
        else:
            raise PluginError("Invalid G_MWO_b value for lights: " + n)

    def _DLHINTVALUE(self, count: int) -> int:
        remainderCommands = count % self.G_INPUT_BUFFER_CMDS
        if not self.F3DEX_GBI_3 or count == 0 or remainderCommands == 0:
            return 0
        return (self.G_INPUT_BUFFER_CMDS - remainderCommands) << 3


g_F3D = {
    "GBI": None,
    "f3d_type": None,
}


def get_cached_F3D_GBI(f3d_type: str) -> F3D:
    """Get constructed/cached F3D class"""
    if g_F3D["GBI"] is None or f3d_type != g_F3D["f3d_type"]:
        g_F3D["f3d_type"] = f3d_type
        g_F3D["GBI"] = F3D(f3d_type)
    return g_F3D["GBI"]


def get_F3D_GBI() -> F3D:
    """Gets cached F3D class and automatically supplies params"""
    return get_cached_F3D_GBI(bpy.context.scene.f3d_type)


def _SHIFTL(value, amount, mask):
    return (int(value) & ((1 << mask) - 1)) << amount


MTX_SIZE = 64
VTX_SIZE = 16
GFX_SIZE = 8
VP_SIZE = 16  # it's 16 bytes but vanilla GBI has only one s64 for alignment, not two
LIGHT_SIZE = 16
AMBIENT_SIZE = 8
HILITE_SIZE = 16  # 8 in F3DEX3, but this variable is not used in fast64


class ExportCData:
    def __init__(self, staticData, dynamicData, textureData):
        self.staticData = staticData
        self.dynamicData = dynamicData
        self.textureData = textureData

    def all(self):
        data = CData()
        data.append(self.staticData)
        data.append(self.dynamicData)
        data.append(self.textureData)
        return data


class TextureExportSettings:
    def __init__(self, texCSeparate, savePNG, includeDir, exportPath):
        self.texCSeparate = texCSeparate
        self.savePNG = savePNG
        self.includeDir = includeDir
        self.exportPath = exportPath


#  SetTileSize Scroll Data
class FSetTileSizeScrollField:
    def __init__(self):
        self.s = 0
        self.t = 0
        self.interval = 1


def tile_func(direction: str, speed: int, cmd_num: int):
    if speed == 0 or speed is None:
        return None

    func = f"shift_{direction}"

    if speed < 0:
        func += "_down"

    return f"\t{func}(mat, {cmd_num}, PACK_TILESIZE(0, {abs(speed)}));"


def get_sts_interval_vars(tex_num: str):
    return f"interval_{tex_num}", f"cur_interval_{tex_num}"


def get_tex_sts_code(
    variableName: str, tex: FSetTileSizeScrollField, cmd_num: int
) -> Tuple[list[str], list[Tuple[str, float]]]:
    variables = []
    # create func calls
    lines = [
        tile_func("s", tex.s, cmd_num),
        tile_func("t", tex.t, cmd_num),
    ]
    # filter lines
    lines = [func for func in lines if func]
    # add interval logic if needed
    if len(lines) and tex.interval > 1:
        # get interval and variable for tracking interval
        interval, cur_interval = get_sts_interval_vars(variableName)
        # pass each var and its value to variables
        variables.extend([(interval, tex.interval), (cur_interval, tex.interval)])

        # indent again for if statement
        lines = [("\t" + func) for func in lines]

        lines = [
            f"\n\tif (--{cur_interval} <= 0) {{",
            *lines,
            f"\t\t{cur_interval} = {interval};",
            "\t}",
        ]
    return variables, lines


def get_tile_scroll_code(
    variableName: str, scrollData: "FScrollData", textureIndex: int, commandIndex: int
) -> Tuple[str, str]:
    scrollInfo: FSetTileSizeScrollField = getattr(scrollData, f"tile_scroll_tex{textureIndex}")
    if scrollInfo.s or scrollInfo.t:
        variables = []
        lines = []
        static_variables, tex_lines = get_tex_sts_code(variableName, scrollInfo, commandIndex)

        for variable, val in static_variables:
            variables.append(f"\tstatic int {variable} = {val};")

        lines.extend(tex_lines)

        variables_str = "\n".join([line for line in variables if line]) + "\n"
        lines_str = "\n".join([line for line in lines if line]) + "\n"

        return variables_str, lines_str
    else:
        return "", ""


def vertexScrollTemplate(
    fScrollData, name, count, absFunc, signFunc, cosFunc, randomFloatFunc, randomSignFunc, segToVirtualFunc
):
    scrollDataFields = fScrollData.fields[0]
    if scrollDataFields[0].animType == "None" and scrollDataFields[1].animType == "None":
        return ""
    data = [
        "void scroll_" + name + "() {",
        "\tint i = 0;",
        f"\tint count = {count};",
    ]
    variables = ""
    currentVars = ""
    deltaCalculate = ""
    checkOverflow = ""
    scrolling = ""
    increaseCurrentDelta = ""
    for i in range(2):
        field = "XYZ"[i]
        axis = ["width", "height"][i]
        if scrollDataFields[i].animType != "None":
            data.append(f"\tint {axis} = {fScrollData.dimensions[i]} * 0x20;")
            currentVars += "\tstatic int current" + field + " = 0;\n\tint delta" + field + ";\n"
            checkOverflow += "\n".join(
                (
                    "\tif (" + absFunc + "(current" + field + ") > " + axis + ") {",
                    (
                        f"\t\tdelta{field} -= (int)(absi(current{field}) / {axis}) "
                        f"* {axis} * {signFunc}(delta{field});"
                    ),
                    "\t}",
                    "",
                )
            )
            scrolling += f"\t\tvertices[i].n.tc[{i}] += delta{field};\n"
            increaseCurrentDelta += f"\tcurrent{field} += delta{field};"
            if scrollDataFields[i].animType == "Linear":
                deltaCalculate += f"\tdelta{field} = (int)({scrollDataFields[i].speed} * 0x20) % {axis};\n"
            elif scrollDataFields[i].animType == "Sine":
                currentVars += "\n".join(
                    (
                        "\tstatic int time" + field + ";",
                        "\tfloat amplitude" + field + " = " + str(scrollDataFields[i].amplitude) + ";",
                        "\tfloat frequency" + field + " = " + str(scrollDataFields[i].frequency) + ";",
                        "\tfloat offset" + field + " = " + str(scrollDataFields[i].offset) + ";",
                        "",
                    )
                )
                deltaCalculate += (
                    "\tdelta"
                    + field
                    + " = (int)(amplitude"
                    + field
                    + " * frequency"
                    + field
                    + " * "
                    + cosFunc
                    + "((frequency"
                    + field
                    + " * time"
                    + field
                    + " + offset"
                    + field
                    + ") * (1024 * 16 - 1) / 6.28318530718) * 0x20);\n"
                )
                # Conversion from s10.5 to u16
                # checkOverflow += '\tif (frequency' + field + ' * current' + field + ' / 2 > 6.28318530718) {\n' +\
                # 	'\t\tcurrent' + field + ' -= 6.28318530718 * 2 / frequency' + field + ';\n\t}\n'
                increaseCurrentDelta += "\ttime" + field + " += 1;"
            elif scrollDataFields[i].animType == "Noise":
                deltaCalculate += (
                    "\tdelta"
                    + field
                    + " = (int)("
                    + str(scrollDataFields[i].noiseAmplitude)
                    + " * 0x20 * "
                    + randomFloatFunc
                    + "() * "
                    + randomSignFunc
                    + "()) % "
                    + axis
                    + ";\n"
                )
            else:
                raise PluginError("Unhandled scroll type: " + str(scrollDataFields[i].animType))
    return "\n".join(
        (
            "\n".join(data),
            variables,
            currentVars + "\tVtx *vertices = " + segToVirtualFunc + "(" + name + ");",
            "",
            deltaCalculate,
            checkOverflow,
            "\tfor (i = 0; i < count; i++) {",
            scrolling + "\t}",
            increaseCurrentDelta,
            "}",
            "",
            "",
        )
    )


class GfxFormatter:
    def __init__(self, scrollMethod: ScrollMethod, texArrayBitSize: int, seg2virtFuncName: Union[str, None]):
        self.scrollMethod: ScrollMethod = scrollMethod
        self.texArrayBitSize = texArrayBitSize
        self.seg2virtFuncName = seg2virtFuncName

    def gfxScrollToC(self, gfxList: "GfxList", f3d: F3D) -> CScrollData:
        """
        Handles writing code that executes static Gfx scrolling (ex. tile scrolling.)
        If you want a game-specific formatter that ignores all static gfx scrolling,
        simply leaving processGfxScrollCommand() un-overriden will achieve this.
        Don't override this directly, see processGfxScrollCommand().
        If you do, make sure to add function names to returned CScrollData.functionCalls.
        """
        funcName = f"scroll_gfx_{gfxList.name}"
        func = f"void {funcName}()"

        data = CScrollData()
        data.functionCalls.append(funcName)
        data.header += f"extern {func};\n"
        data.source += f"{func} {{\n"

        variables = ""
        code = ""
        dataIndex = 0

        # Since some commands are actually multiple commands in one, we have to use the command size and divide by GFX_SIZE.
        for command in gfxList.commands:
            gfxVariables, gfxCode = self.processGfxScrollCommand(dataIndex // GFX_SIZE, command, gfxList.name)
            variables += gfxVariables
            code += gfxCode
            dataIndex += command.size(f3d)
        gfxScrollCode = variables + code

        if gfxScrollCode == "":
            return CScrollData()
        else:
            if self.seg2virtFuncName is not None:
                data.source += f"\tGfx *mat = {self.seg2virtFuncName}({gfxList.name});\n"
            else:
                data.source += f"\tGfx *mat = {gfxList.name};\n"
            data.source += gfxScrollCode
            data.source += f"\n}};\n\n"
            return data

    def processGfxScrollCommand(self, commandIndex: int, command: "GbiMacro", gfxListName: str) -> Tuple[str, str]:
        """
        Returns a tuple of [variable declarations, code], since in C all variables must be declared at the top.
        Handles a single command for Gfx scrolling.
        Override this per game to handle/filter specific scrolling methods.
        Note that the display list pointer to reference is named "mat", as seen in GfxFormatter.gfxScrollToC().
        This is because the segmented_to_virtual() function is called on the actual DL pointer, as defined in self.seg2virtFuncName.
        """
        tags: GfxTag = command.tags
        fMaterial: FMaterial = command.fMaterial
        return "", ""

    def vertexScrollToC(self, fMaterial: FMaterial, vtxListName: str, vtxCount: int) -> CScrollData:
        """
        Handles writing code that executes vertex scrolling.
        Make sure to add function names to returned CScrollData.functionCalls.
        """
        return CScrollData()

    def drawToC(self, f3d: F3D, gfxList: "GfxList") -> CData:
        """
        Called for building the entry point DL for drawing a model.
        """
        return gfxList.to_c(f3d)


class Vtx:
    def __init__(self, position, uv, colorOrNormal, packedNormal=0):
        self.position = position
        self.uv = uv
        self.colorOrNormal = colorOrNormal
        self.packedNormal = packedNormal

    def to_binary(self):
        signX = 1 if self.uv[0] >= 0 else -1
        signY = 1 if self.uv[1] >= 0 else -1
        uv = [self.uv[0] % (signX * 2**15), self.uv[1] % (signY * 2**15)]
        return (
            self.position[0].to_bytes(2, "big", signed=True)
            + self.position[1].to_bytes(2, "big", signed=True)
            + self.position[2].to_bytes(2, "big", signed=True)
            + self.packedNormal.to_bytes(2, "big", signed=True)
            + uv[0].to_bytes(2, "big", signed=True)
            + uv[1].to_bytes(2, "big", signed=True)
            + bytearray(self.colorOrNormal)
        )

    def to_c(self):
        def spc(x):
            return "{" + ", ".join([str(a) for a in x]) + "}"

        flag = "0" if self.packedNormal == 0 else f"{self.packedNormal:#06x}"
        return "{{ " + ", ".join([spc(self.position), flag, spc(self.uv), spc(self.colorOrNormal)]) + " }}"


class VtxList:
    def __init__(self, name):
        self.vertices = []
        self.name = name
        self.startAddress = 0

    def set_addr(self, startAddress):
        startAddress = get64bitAlignedAddr(startAddress)
        self.startAddress = startAddress
        print("VtxList " + self.name + ": " + str(startAddress) + ", " + str(self.size()))
        return startAddress, startAddress + self.size()

    def save_binary(self, romfile):
        romfile.seek(self.startAddress)
        romfile.write(self.to_binary())

    def size(self):
        return len(self.vertices) * VTX_SIZE

    def to_binary(self):
        data = bytearray(0)
        for vert in self.vertices:
            data.extend(vert.to_binary())
        return data

    def to_c(self):
        data = CData()
        data.header = f"extern Vtx {self.name}[{len(self.vertices)}];\n"
        data.source = f"Vtx {self.name}[{len(self.vertices)}] = {{\n"
        for vert in self.vertices:
            data.source += f"\t{vert.to_c()},\n"
        data.source += "};\n\n"
        return data


class GfxList:
    def __init__(self, name, tag, DLFormat):
        self.commands: list[GbiMacro] = []
        self.name: str = name
        self.startAddress: int = 0
        self.tag: GfxListTag = tag
        self.DLFormat: "DLFormat" = DLFormat

    def set_addr(self, startAddress, f3d):
        startAddress = get64bitAlignedAddr(startAddress)
        self.startAddress = startAddress
        print(f"GfxList {self.name}: {str(startAddress)}, {str(self.size(f3d))}")
        return startAddress, startAddress + self.size(f3d)

    def save_binary(self, romfile, f3d, segments):
        print(f"GfxList {self.name}: {str(self.startAddress)}, {str(self.size(f3d))}")
        romfile.seek(self.startAddress)
        romfile.write(self.to_binary(f3d, segments))

    def size(self, f3d):
        return sum([command.size(f3d) for command in self.commands])

    # Size, including display lists called with SPDisplayList
    def size_total(self, f3d):
        def use_siz_tot(command):
            return isinstance(command, SPDisplayList) and command.displayList.DLFormat != DLFormat.Static

        return sum(
            [
                command.displayList.size_total(f3d) if use_siz_tot(command) else command.size(f3d)
                for command in self.commands
            ]
        )

    def get_ptr_addresses(self, f3d):
        ptrs = []
        address = self.startAddress
        for command in self.commands:
            if type(command) in F3DClassesWithPointers:
                for offset in command.get_ptr_offsets(f3d):
                    ptrs.append(address + offset)
            address += command.size(f3d)
        return ptrs

    def to_binary(self, f3d, segments):
        data = bytearray(0)
        for command in self.commands:
            data.extend(command.to_binary(f3d, segments))
        return data

    def to_c_static(self):
        data = f"Gfx {self.name}[] = {{\n"
        for command in self.commands:
            data += f"\t{command.to_c(True)},\n"
        data += "};\n\n"
        return data

    def to_c_dynamic(self):
        data = f"Gfx* {self.name}(Gfx* glistp) {{\n"
        for command in self.commands:
            data += f"\t{command.to_c(False)};\n"
        data += "\treturn glistp;\n}\n\n"
        return data

    def to_c(self, f3d):
        data = CData()
        if self.DLFormat == DLFormat.Static:
            data.header = f"extern Gfx {self.name}[];\n"
            data.source = self.to_c_static()
        elif self.DLFormat == DLFormat.Dynamic:
            data.header = f"Gfx* {self.name}(Gfx* glistp);\n"
            data.source = self.to_c_dynamic()
        else:
            raise PluginError("Invalid GfxList format: " + str(self.DLFormat))
        return data


class FFogData:
    def __init__(self, position=(985, 1000), color=(0, 0, 0, 1)):
        self.position = tuple(position)
        self.color = (round(color[0], 8), round(color[1], 8), round(color[2], 8), round(color[3], 8))

    def __eq__(self, other):
        return tuple(self.position) == tuple(other.position) and tuple(self.color) == tuple(other.color)

    def makeKey(self):
        return (self.position, self.color)

    def requiresKey(self, material):
        return material.set_fog and material.use_global_fog


class FAreaData:
    def __eq__(self, other):
        return self.fog_data == other.fog_data

    def __init__(self, fog_data):
        self.fog_data = fog_data

    def makeKey(self):
        return self.fog_data.makeKey()

    def requiresKey(self, material):
        return self.fog_data and self.fog_data.requiresKey(material)


class FGlobalData:
    def __init__(self):
        # dict of area index : FAreaData
        self.area_data = {}
        self.current_area_index = 1

    def addAreaData(self, areaIndex: int, areaData: FAreaData):
        if areaIndex in self.area_data:
            raise ValueError("Error: Detected repeat FAreaData.")
        self.area_data[areaIndex] = areaData
        self.current_area_index = areaIndex

    def getCurrentAreaData(self):
        if len(self.area_data) == 0:
            return None
        else:
            return self.area_data[self.current_area_index]

    def getCurrentAreaKey(self, material):
        if len(self.area_data) == 0:
            return None
        # No need to have area specific variants of a material if they don't use global fog.
        # Without this, a non-global-fog material used across areas will have redefined duplicate light names.
        elif not self.area_data[self.current_area_index].requiresKey(material):
            return None
        else:
            return self.area_data[self.current_area_index].makeKey()


class FImageKey:
    def __init__(
        self, image: bpy.types.Image, texFormat: str, palFormat: str, imagesSharingPalette: list[bpy.types.Image] = []
    ):
        self.image = image
        self.texFormat = texFormat
        self.palFormat = palFormat
        self.imagesSharingPalette = tuple(imagesSharingPalette)

    def __hash__(self) -> int:
        return hash((self.image, self.texFormat, self.palFormat, self.imagesSharingPalette))

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, FImageKey):
            return False
        return (
            self.image == __o.image
            and self.texFormat == __o.texFormat
            and self.palFormat == __o.palFormat
            and self.imagesSharingPalette == __o.imagesSharingPalette
        )


def getImageKey(texProp: "TextureProperty", useList) -> FImageKey:
    return FImageKey(texProp.tex, texProp.tex_format, texProp.ci_format, useList)


class FPaletteKey:
    def __init__(self, palFormat: str, imagesSharingPalette: list[bpy.types.Image] = []):
        self.palFormat = palFormat
        self.imagesSharingPalette = tuple(imagesSharingPalette)

    def __hash__(self) -> int:
        return hash((self.palFormat, self.imagesSharingPalette))

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, FPaletteKey):
            return False
        return self.palFormat == __o.palFormat and self.imagesSharingPalette == __o.imagesSharingPalette


class FModel:
    def __init__(
        self,
        name: str,
        DLFormat: "DLFormat",
        matWriteMethod: GfxMatWriteMethod,
    ):
        self.name = name  # used for texture prefixing
        # dict of light name : Lights
        self.lights: dict[str, Lights] = {}
        # dict of (texture, (texture format, palette format)) : FImage
        self.textures: dict[Union[FImageKey, FPaletteKey], FImage] = {}
        # dict of (material, drawLayer, FAreaData): (FMaterial, (width, height))
        self.materials: dict[Tuple[bpy.types.Material, str, FAreaData], Tuple[FMaterial, Tuple[int, int]]] = {}
        # dict of body part name : FMesh
        self.meshes: dict[str, FMesh] = {}
        # GfxList
        self.materialRevert: Union[GfxList, None] = None
        # F3D library
        self.f3d: F3D = get_F3D_GBI()
        if not self.f3d.F3D_GBI:
            raise PluginError(
                f"Current microcode {self.f3d.F3D_VER} is not part of the f3d family of microcodes, fast64 cannot export it"
            )
        # array of FModel
        self.subModels: list[FModel] = []
        self.parentModel: Union[FModel, None] = None

        # dict of name : FLODGroup
        self.LODGroups: dict[str, FLODGroup] = {}
        self.DLFormat: "DLFormat" = DLFormat
        self.matWriteMethod: GfxMatWriteMethod = matWriteMethod
        self.no_light_direction = False
        self.global_data: FGlobalData = FGlobalData()
        self.texturesSavedLastExport: int = 0  # hacky

    def processTexRefNonCITextures(self, fMaterial: FMaterial, material: bpy.types.Material, index: int):
        """
        For non CI textures that use a texture reference, process additional textures that will possibly be loaded here.
        Returns:
            - a list of images which are referenced (normally just the texture
              image), for creating image / palette keys
            - an object containing info about the additional textures, or None
        """
        texProp = getattr(material.f3d_mat, f"tex{index}")
        imDependencies = [] if texProp.tex is None else [texProp.tex]
        return imDependencies, None

    def writeTexRefNonCITextures(self, obj, texFmt: str):
        """
        Write data for non-CI textures which were previously processed.
        obj is the object returned by processTexRefNonCITextures.
        """
        pass

    def processTexRefCITextures(self, fMaterial: FMaterial, material: bpy.types.Material, index: int) -> "FImage":
        """
        For CI textures that use a texture reference, process additional textures that will possibly be loaded here.
        Returns:
            - a list of images which are referenced (normally just the texture
              image), for creating image / palette keys
            - an object containing info about the additional textures, or None
            - the palette to use (or None)
        """
        texProp = getattr(material.f3d_mat, f"tex{index}")
        imDependencies = [] if texProp.tex is None else [texProp.tex]
        return imDependencies, None, None

    def writeTexRefCITextures(
        self,
        obj,
        fMaterial: "FMaterial",
        imagesSharingPalette: list[bpy.types.Image],
        pal: list[int],
        texFmt: str,
        palFmt: str,
    ):
        """
        Write data for CI textures which were previously processed.
        obj is the object returned by processTexRefCITextures.
        """
        pass

    # Called before SPEndDisplayList
    def onMaterialCommandsBuilt(self, fMaterial, material, drawLayer):
        fMaterial.material.commands.extend(fMaterial.mat_only_DL.commands)
        fMaterial.material.commands.extend(fMaterial.texture_DL.commands)
        return

    def getDrawLayerV3(self, obj):
        return None

    def getRenderMode(self, drawLayer):
        return None

    def addLODGroup(self, name, position, alwaysRenderFarthest):
        if name in self.LODGroups:
            raise PluginError("Duplicate LOD group: " + str(name))
        lod = FLODGroup(name, position, alwaysRenderFarthest, self.DLFormat)
        self.LODGroups[name] = lod
        return lod

    def addSubModel(self, subModel):
        self.subModels.append(subModel)
        subModel.parentModel = self
        return subModel

    def addTexture(self, key, value, fMaterial):
        fMaterial.usedImages.append(key)
        self.textures[key] = value

    def addLight(self, key, value, fMaterial):
        fMaterial.usedLights.append(key)
        self.lights[key] = value

    def addMesh(self, name, namePrefix, drawLayer, isSkinned, contextObj):
        meshName = getFMeshName(name, namePrefix, drawLayer, isSkinned)
        checkUniqueBoneNames(self, meshName, name)
        self.meshes[meshName] = FMesh(meshName, self.DLFormat)

        self.onAddMesh(self.meshes[meshName], contextObj)

        return self.meshes[meshName]

    def onAddMesh(self, fMesh, contextObj):
        return

    def addMaterial(self, materialName):
        fMaterial = FMaterial(materialName, self.DLFormat)
        self.onMaterialAdd(fMaterial)
        return fMaterial

    def onMaterialAdd(self, fMaterial):
        return

    def endDraw(self, fMesh, contextObj):
        fMesh.draw.commands.append(SPEndDisplayList())

    def getTextureAndHandleShared(self, imageKey):
        # Check if texture is in self
        if imageKey in self.textures:
            return self.textures[imageKey]

        if self.parentModel is not None:
            # Check if texture is in parent
            if imageKey in self.parentModel.textures:
                return self.parentModel.textures[imageKey]

            # Check if texture is in siblings
            for subModel in self.parentModel.subModels:
                if imageKey in subModel.textures:
                    fImage = subModel.textures.pop(imageKey)
                    self.parentModel.textures[imageKey] = fImage
                    return fImage
            return None
        else:
            return None

    def getLightAndHandleShared(self, lightName):
        # Check if light is in self
        if lightName in self.lights:
            return self.lights[lightName]

        if self.parentModel is not None:
            # Check if light is in parent
            if lightName in self.parentModel.lights:
                return self.parentModel.lights[lightName]

            # Check if light is in siblings
            for subModel in self.parentModel.subModels:
                if lightName in subModel.lights:
                    light = subModel.lights.pop(lightName)
                    self.parentModel.lights[lightName] = light
                    return light
        else:
            return None

    def getMaterialAndHandleShared(self, materialKey):
        # Check if material is in self
        if materialKey in self.materials:
            return self.materials[materialKey]

        if self.parentModel is not None:
            # Check if material is in parent
            if materialKey in self.parentModel.materials:
                return self.parentModel.materials[materialKey]

            # Check if material is in siblings
            for subModel in self.parentModel.subModels:
                if materialKey in subModel.materials:
                    materialItem = subModel.materials.pop(materialKey)
                    self.parentModel.materials[materialKey] = materialItem

                    # If material is in sibling, handle the material's textures as well.
                    for imageKey in materialItem[0].usedImages:
                        fImage = self.getTextureAndHandleShared(imageKey)
                        if fImage is None:
                            raise PluginError("Error: If a material exists, its textures should exist too.")

                    for lightName in materialItem[0].usedLights:
                        light = self.getLightAndHandleShared(lightName)
                        if light is None:
                            raise PluginError("Error: If a material exists, its lights should exist too.")
                    return materialItem
        else:
            return None

    def getAllMaterials(self):
        materials = {}
        materials.update(self.materials)
        for subModel in self.subModels:
            materials.update(subModel.getAllMaterials())
        return materials

    def get_ptr_addresses(self, f3d):
        addresses = []
        for name, lod in self.LODGroups.items():
            addresses.extend(lod.get_ptr_addresses(f3d))
        for name, mesh in self.meshes.items():
            addresses.extend(mesh.get_ptr_addresses(f3d))
        for materialKey, (fMaterial, texDimensions) in self.materials.items():
            addresses.extend(fMaterial.get_ptr_addresses(f3d))
        if self.materialRevert is not None:
            addresses.extend(self.materialRevert.get_ptr_addresses(f3d))
        return addresses

    def set_addr(self, startAddress):
        addrRange = (startAddress, startAddress)
        startAddrSet = False
        for name, lod in self.LODGroups.items():
            addrRange = lod.set_addr(addrRange[1], self.f3d)
            if not startAddrSet:
                startAddrSet = True
                startAddress = addrRange[0]
        # Important to set mesh groups first, so that
        # export address corrseponds to drawing start.
        for name, mesh in self.meshes.items():
            addrRange = mesh.set_addr(addrRange[1], self.f3d)
            if not startAddrSet:
                startAddrSet = True
                startAddress = addrRange[0]
        for name, light in self.lights.items():
            addrRange = light.set_addr(addrRange[1])
            if not startAddrSet:
                startAddrSet = True
                startAddress = addrRange[0]
        for _, fImage in self.textures.items():
            addrRange = fImage.set_addr(addrRange[1])
            if not startAddrSet:
                startAddrSet = True
                startAddress = addrRange[0]
        for materialKey, (fMaterial, texDimensions) in self.materials.items():
            addrRange = fMaterial.set_addr(addrRange[1], self.f3d)
            if not startAddrSet:
                startAddrSet = True
                startAddress = addrRange[0]
        if self.materialRevert is not None:
            addrRange = self.materialRevert.set_addr(addrRange[1], self.f3d)
            if not startAddrSet:
                startAddrSet = True
                startAddress = addrRange[0]
        for subModel in self.subModels:
            addrRange = subModel.set_addr(addrRange[1])
            if not startAddrSet:
                startAddrSet = True
                startAddress = addrRange[0]
        return startAddress, addrRange[1]

    def save_binary(self, romfile, segments):
        for name, light in self.lights.items():
            light.save_binary(romfile)
        for _, fImage in self.textures.items():
            fImage.save_binary(romfile)
        for materialKey, (fMaterial, texDimensions) in self.materials.items():
            fMaterial.save_binary(romfile, self.f3d, segments)
        for name, mesh in self.meshes.items():
            mesh.save_binary(romfile, self.f3d, segments)
        for name, lod in self.LODGroups.items():
            lod.save_binary(romfile, self.f3d, segments)
        if self.materialRevert is not None:
            self.materialRevert.save_binary(romfile, self.f3d, segments)
        for subModel in self.subModels:
            subModel.save_binary(romfile, segments)

    def to_c_lights(self):
        data = CData()
        for name, light in self.lights.items():
            data.append(light.to_c())
        return data

    def to_c_textures(self, texCSeparate, savePNG, texDir, texArrayBitSize):
        # since decomp is linux, don't use os.path.join
        # on windows this results in '\', which is incorrect (should be '/')
        if len(texDir) > 0 and texDir[-1] != "/":
            texDir += "/"
        data = CData()
        for _, fImage in self.textures.items():
            if savePNG:
                data.append(fImage.to_c_tex_separate(texDir, texArrayBitSize))
            else:
                data.append(fImage.to_c(texArrayBitSize))
        return data

    def to_c_materials(self, gfxFormatter):
        data = CData()
        for materialKey, (fMaterial, texDimensions) in self.materials.items():
            data.append(fMaterial.to_c(self.f3d))
        return data

    def to_c_material_revert(self, gfxFormatter):
        data = CData()
        if self.materialRevert is not None:
            data.append(self.materialRevert.to_c(self.f3d))
        return data

    def to_c(self, textureExportSettings: TextureExportSettings, gfxFormatter: GfxFormatter):
        texCSeparate = textureExportSettings.texCSeparate
        savePNG = textureExportSettings.savePNG
        texDir = textureExportSettings.includeDir

        staticData = CData()
        dynamicData = CData()
        texC = CData()

        # Source
        staticData.append(self.to_c_lights())

        texData = self.to_c_textures(texCSeparate, savePNG, texDir, gfxFormatter.texArrayBitSize)
        staticData.header += texData.header
        if texCSeparate:
            texC.source += texData.source
        else:
            staticData.source += texData.source

        dynamicData.append(self.to_c_materials(gfxFormatter))

        for name, lod in self.LODGroups.items():
            lodStatic, lodDynamic = lod.to_c(self.f3d, gfxFormatter)
            staticData.append(lodStatic)
            dynamicData.append(lodDynamic)

        for name, mesh in self.meshes.items():
            meshStatic, meshDynamic = mesh.to_c(self.f3d, gfxFormatter)
            staticData.append(meshStatic)
            dynamicData.append(meshDynamic)

        dynamicData.append(self.to_c_material_revert(gfxFormatter))

        if savePNG:
            self.texturesSavedLastExport = self.save_textures(textureExportSettings.exportPath)

        self.freePalettes()
        return ExportCData(staticData, dynamicData, texC)

    def to_c_scroll(self, funcName: str, gfxFormatter: GfxFormatter) -> CScrollData:
        data = CScrollData()
        vertexScrollData = self.to_c_vertex_scroll(gfxFormatter)
        if len(vertexScrollData.functionCalls) > 0:
            data.append(vertexScrollData)

        gfxScrollData = self.to_c_gfx_scroll(gfxFormatter)
        if len(gfxScrollData.functionCalls) > 0:
            data.append(gfxScrollData)

        data.topLevelScrollFunc = f"scroll_{funcName}"
        data.source += f"void {data.topLevelScrollFunc}() {{\n"
        for scrollFunc in data.functionCalls:
            data.source += f"\t{scrollFunc}();\n"
        data.source += f"}};\n"

        data.header += f"extern void {data.topLevelScrollFunc}();\n"
        return data

    def to_c_vertex_scroll(self, gfxFormatter: GfxFormatter) -> CScrollData:
        data = CScrollData()
        for _, mesh in self.meshes.items():
            mesh: FMesh
            for triGroup in mesh.triangleGroups:
                data.append(
                    gfxFormatter.vertexScrollToC(
                        triGroup.fMaterial, triGroup.vertexList.name, len(triGroup.vertexList.vertices)
                    )
                )

        return data

    def to_c_gfx_scroll(self, gfxFormatter: GfxFormatter) -> CScrollData:
        data = CScrollData()
        for fMaterial, _ in self.materials.values():
            fMaterial: FMaterial
            if fMaterial.material.tag.Export:
                data.append(gfxFormatter.gfxScrollToC(fMaterial.material, self.f3d))
        for fMesh in self.meshes.values():
            fMesh: FMesh
            data.append(gfxFormatter.gfxScrollToC(fMesh.draw, self.f3d))
        return data

    def save_textures(self, exportPath):
        # TODO: Saving texture should come from FImage
        texturesSaved = 0
        for imageKey, fImage in self.textures.items():
            if isinstance(imageKey, FPaletteKey):
                continue
            imageKey: FImageKey

            # remove '.inc.c'
            imageFileName = fImage.filename[:-6] + ".png"

            image = imageKey.image
            isPacked = image.packed_file is not None
            if not isPacked:
                image.pack()
            oldpath = image.filepath
            try:
                image.filepath = bpy.path.abspath(os.path.join(exportPath, imageFileName))
                image.save()
                texturesSaved += 1
                if not isPacked:
                    image.unpack()
            except Exception as e:
                image.filepath = oldpath
                raise Exception(str(e))
            image.filepath = oldpath
        return texturesSaved

    def freePalettes(self):
        pass


class FTexRect(FModel):
    def __init__(self, name, matWriteMethod):
        self.draw = GfxList(name, GfxListTag.Draw, DLFormat.Dynamic)
        FModel.__init__(self, name, DLFormat, matWriteMethod)

    def to_c(self, savePNG, texDir, gfxFormatter):
        staticData = CData()
        dynamicData = CData()
        # since decomp is linux, don't use os.path.join
        # on windows this results in '\', which is incorrect (should be '/')
        if texDir[-1] != "/":
            texDir += "/"
        for _, fImage in self.textures.items():
            if savePNG:
                staticData.append(fImage.to_c_tex_separate(texDir, gfxFormatter.texArrayBitSize))
            else:
                staticData.append(fImage.to_c(gfxFormatter.texArrayBitSize))
        dynamicData.append(self.draw.to_c(self.f3d))
        return ExportCData(staticData, dynamicData, CData())


class FLODGroup:
    def __init__(self, name, position, alwaysRenderFarthest, DLFormat):
        self.name = name
        self.DLFormat = DLFormat
        self.lodEntries = []  # list of tuple(z, DL)
        self.alwaysRenderFarthest = alwaysRenderFarthest

        self.vertexList = VtxList(self.get_vtx_name())
        self.vertexList.vertices.append(Vtx(position, [0, 0], [0, 0, 0, 0]))

        self.draw = None
        self.subdraws = []
        self.drawCommandsBuilt = False

    def add_lod(self, displayList, zValue):
        if displayList is not None:
            self.lodEntries.append((abs(int(round(zValue))), displayList))

    def get_dl_name(self):
        return self.name + "_lod"

    def get_vtx_name(self):
        return self.name + "_vtx"

    def get_ptr_addresses(self, f3d):
        addresses = self.draw.get_ptr_addresses(f3d)
        for displayList in self.subdraws:
            if displayList is not None:
                addresses.extend(displayList.get_ptr_addresses(f3d))
        return addresses

    def set_addr(self, startAddress, f3d):
        self.create_data()
        addrRange = self.draw.set_addr(startAddress, f3d)
        for displayList in self.subdraws:
            if displayList is not None:
                addrRange = displayList.set_addr(addrRange[1], f3d)
        addrRange = self.vertexList.set_addr(addrRange[1])
        return startAddress, addrRange[1]

    def save_binary(self, romfile, f3d, segments):
        self.draw.save_binary(romfile, f3d, segments)
        for displayList in self.subdraws:
            if displayList is not None:
                displayList.save_binary(romfile, f3d, segments)
        self.vertexList.save_binary(romfile)

    def to_c(self, f3d, gfxFormatter):
        self.create_data()

        staticData = CData()
        dynamicData = CData()
        staticData.append(self.vertexList.to_c())
        for displayList in self.subdraws:
            if displayList is not None:
                dynamicData.append(displayList.to_c(f3d))
        dynamicData.append(self.draw.to_c(f3d))
        return staticData, dynamicData

    def create_data(self):
        if self.drawCommandsBuilt:
            return

        self.drawCommandsBuilt = True
        self.draw = GfxList(self.get_dl_name(), GfxListTag.Draw, self.DLFormat)

        index = 0
        self.draw.commands.append(SPVertex(self.vertexList, 0, 1, index))

        sortedList = sorted(self.lodEntries, key=lambda tup: tup[0])
        hasAnyDLs = False
        for item in sortedList:
            # If no DLs are called, we still need an empty DL to preserve LOD.
            if len(item[1].commands) < 2:
                DL = item[1]
                self.subdraws.append(DL)
            # If one DL is called, we can just call it directly.
            elif len(item[1].commands) == 2:  # branch DL, then end DL:
                DL = item[1].commands[0].displayList
                hasAnyDLs = True
            # If more DLs are called, we have to use a sub DL.
            else:
                DL = item[1]
                self.subdraws.append(DL)
                hasAnyDLs = True

            self.draw.commands.append(SPBranchLessZraw(DL, index, item[0]))

        if len(sortedList) > 0:
            lastCmd = self.draw.commands[-1]
            if self.alwaysRenderFarthest:
                self.draw.commands.remove(lastCmd)
                self.draw.commands.append(SPBranchList(lastCmd.dl))

        if not hasAnyDLs:
            self.draw.commands.clear()
            self.subdraws.clear()

        self.draw.commands.append(SPEndDisplayList())


class FMesh:
    def __init__(self, name, DLFormat):
        self.name = name
        # GfxList
        self.draw = GfxList(name, GfxListTag.Draw, DLFormat)
        # list of FTriGroup
        self.triangleGroups: list[FTriGroup] = []
        # VtxList
        self.cullVertexList = None
        # dict of (override Material, specified Material to override,
        # overrideType, draw layer) : GfxList
        self.drawMatOverrides = {}
        self.DLFormat = DLFormat

        # Used to avoid consecutive calls to the same material if unnecessary
        self.currentFMaterial = None

    def add_material_call(self, fMaterial):
        sameMaterial = self.currentFMaterial is fMaterial
        if not sameMaterial:
            self.currentFMaterial = fMaterial
            self.draw.commands.append(SPDisplayList(fMaterial.material))
        else:
            lastCommand = self.draw.commands[-1]
            if isinstance(lastCommand, SPDisplayList) and lastCommand.displayList == fMaterial.revert:
                self.draw.commands.remove(lastCommand)

    def add_cull_vtx(self):
        self.cullVertexList = VtxList(self.name + "_vtx_cull")

    def get_ptr_addresses(self, f3d):
        addresses = self.draw.get_ptr_addresses(f3d)
        for triGroup in self.triangleGroups:
            addresses.extend(triGroup.get_ptr_addresses(f3d))
        for materialTuple, drawOverride in self.drawMatOverrides.items():
            addresses.extend(drawOverride.get_ptr_addresses(f3d))
        return addresses

    def tri_group_new(self, fMaterial):
        # Always static DL
        triGroup = FTriGroup(self.name, len(self.triangleGroups), fMaterial)
        self.triangleGroups.append(triGroup)
        return triGroup

    def set_addr(self, startAddress, f3d):
        addrRange = self.draw.set_addr(startAddress, f3d)
        startAddress = addrRange[0]
        for triGroup in self.triangleGroups:
            addrRange = triGroup.set_addr(addrRange[1], f3d)
        if self.cullVertexList is not None:
            addrRange = self.cullVertexList.set_addr(addrRange[1])
        for materialTuple, drawOverride in self.drawMatOverrides.items():
            addrRange = drawOverride.set_addr(addrRange[1], f3d)
        return startAddress, addrRange[1]

    def save_binary(self, romfile, f3d, segments):
        self.draw.save_binary(romfile, f3d, segments)
        for triGroup in self.triangleGroups:
            triGroup.save_binary(romfile, f3d, segments)
        if self.cullVertexList is not None:
            self.cullVertexList.save_binary(romfile)
        for materialTuple, drawOverride in self.drawMatOverrides.items():
            drawOverride.save_binary(romfile, f3d, segments)

    def to_c(self, f3d, gfxFormatter):
        staticData = CData()
        if self.cullVertexList is not None:
            staticData.append(self.cullVertexList.to_c())
        for triGroup in self.triangleGroups:
            staticData.append(triGroup.to_c(f3d, gfxFormatter))
        dynamicData = gfxFormatter.drawToC(f3d, self.draw)
        for materialTuple, drawOverride in self.drawMatOverrides.items():
            dynamicData.append(drawOverride.to_c(f3d))
        return staticData, dynamicData


class FTriGroup:
    def __init__(self, name, index, fMaterial):
        self.fMaterial = fMaterial
        self.vertexList = VtxList(name + "_vtx_" + str(index))
        self.triList = GfxList(name + "_tri_" + str(index), GfxListTag.Geometry, DLFormat.Static)
        self.celTriLists = []
        self.celTriListBaseName = f"{name}_tri_{index}_cel"

    def add_cel_tri_list(self):
        ret = GfxList(f"{self.celTriListBaseName}{len(self.celTriLists)}", GfxListTag.Geometry, DLFormat.Static)
        self.celTriLists.append(ret)
        return ret

    def get_ptr_addresses(self, f3d):
        return self.triList.get_ptr_addresses(f3d)

    def set_addr(self, startAddress, f3d):
        addrRange = (startAddress, startAddress)
        if self.triList.tag.Export:
            addrRange = self.triList.set_addr(startAddress, f3d)
        addrRange = self.vertexList.set_addr(addrRange[1])
        return startAddress, addrRange[1]

    def save_binary(self, romfile, f3d, segments):
        for celTriList in self.celTriLists:
            celTriList.save_binary(romfile, f3d, segments)
        if self.triList.tag.Export:
            self.triList.save_binary(romfile, f3d, segments)
        self.vertexList.save_binary(romfile)

    def to_c(self, f3d, gfxFormatter):
        data = CData()
        data.append(self.vertexList.to_c())
        for celTriList in self.celTriLists:
            data.append(celTriList.to_c(f3d))
        if self.triList.tag.Export:
            data.append(self.triList.to_c(f3d))
        return data


class FScrollDataField:
    def __init__(self):
        self.animType = "None"
        self.speed = 0

        self.amplitude = 0
        self.frequency = 0
        self.offset = 0

        self.noiseAmplitude = 0


class FScrollData:
    def __init__(self):
        self.fields = [[FScrollDataField(), FScrollDataField()], [FScrollDataField(), FScrollDataField()]]
        self.dimensions = [0, 0]
        self.tile_scroll_tex0 = FSetTileSizeScrollField()
        self.tile_scroll_tex1 = FSetTileSizeScrollField()


def get_f3d_mat_from_version(material: bpy.types.Material):
    return material.f3d_mat if material.mat_ver > 3 else material


class FMaterial:
    def __init__(self, name, DLFormat):
        self.material = GfxList(f"mat_{name}", GfxListTag.Material, DLFormat)
        self.mat_only_DL = GfxList(f"mat_only_{name}", GfxListTag.Material, DLFormat)
        self.texture_DL = GfxList(f"tex_{name}", GfxListTag.Material, DLFormat.Static)
        self.revert = GfxList(f"mat_revert_{name}", GfxListTag.MaterialRevert, DLFormat.Static)
        self.DLFormat = DLFormat
        self.scrollData = FScrollData()

        # Used for keeping track of shared resources in FModel hierarchy
        self.usedImages = []  # array of (image, texFormat, paletteType) = imageKey
        self.usedLights = []  # array of light names
        # Used for tile scrolling
        self.tileSizeCommands = {}  # dict of {texIndex : DPSetTileSize}

        # For saveMeshWithLargeTexturesByFaces
        self.largeTexFmt = None
        self.isTexLarge = [False, False]
        self.largeTexAddr = [0, 0]
        self.largeTexWords = 0
        self.imageKey = [None, None]
        self.texPaletteIndex = [0, 0]

    def getScrollData(self, material, dimensions):
        self.getScrollDataField(material, 0, 0)
        self.getScrollDataField(material, 0, 1)
        self.getScrollDataField(material, 1, 0)
        self.getScrollDataField(material, 1, 1)
        self.scrollData.dimensions = dimensions
        self.getSetTileSizeScrollData(material)

    def getScrollDataField(self, material, texIndex, fieldIndex):
        UVanim0 = material.f3d_mat.UVanim0 if material.mat_ver > 3 else material.UVanim
        UVanim1 = material.f3d_mat.UVanim1 if material.mat_ver > 3 else material.UVanim_tex1

        if texIndex == 0:
            field = getattr(UVanim0, "xyz"[fieldIndex])
        elif texIndex == 1:
            field = getattr(UVanim1, "xyz"[fieldIndex])
        else:
            raise PluginError("Invalid texture index.")

        scrollField = self.scrollData.fields[texIndex][fieldIndex]

        scrollField.animType = field.animType
        scrollField.speed = field.speed
        scrollField.amplitude = field.amplitude
        scrollField.frequency = field.frequency
        scrollField.offset = field.offset

        scrollField.noiseAmplitude = field.noiseAmplitude

    def getSetTileSizeScrollData(self, material):
        tex0 = get_f3d_mat_from_version(material).tex0
        tex1 = get_f3d_mat_from_version(material).tex1

        self.scrollData.tile_scroll_tex0.s = tex0.tile_scroll.s
        self.scrollData.tile_scroll_tex0.t = tex0.tile_scroll.t
        self.scrollData.tile_scroll_tex0.interval = tex0.tile_scroll.interval
        self.scrollData.tile_scroll_tex1.s = tex1.tile_scroll.s
        self.scrollData.tile_scroll_tex1.t = tex1.tile_scroll.t
        self.scrollData.tile_scroll_tex1.interval = tex1.tile_scroll.interval

    def get_ptr_addresses(self, f3d):
        addresses = self.material.get_ptr_addresses(f3d)
        if self.revert is not None and self.revert.tag.Export:
            addresses.extend(self.revert.get_ptr_addresses(f3d))
        return addresses

    def set_addr(self, startAddress, f3d):
        addrRange = (startAddress, startAddress)
        if self.material.tag.Export:
            addrRange = self.material.set_addr(addrRange[1], f3d)
        if self.revert is not None and self.revert.tag.Export:
            addrRange = self.revert.set_addr(addrRange[1], f3d)
        return startAddress, addrRange[1]

    def save_binary(self, romfile, f3d, segments):
        if self.material.tag.Export:
            self.material.save_binary(romfile, f3d, segments)
        if self.revert is not None and self.revert.tag.Export:
            self.revert.save_binary(romfile, f3d, segments)

    def to_c(self, f3d):
        data = CData()
        if self.material.tag.Export:
            data.append(self.material.to_c(f3d))
        if self.revert is not None and self.revert.tag.Export:
            data.append(self.revert.to_c(f3d))
        return data


# viewport
# NOTE: unfinished
class Vp:
    def __init__(self, scale, translation):
        self.startAddress = 0


class Light:
    def __init__(self, color: Sequence, normal: Sequence):
        self.color: Sequence = color
        self.normal: Sequence = normal

    def __eq__(self, other):
        if not isinstance(other, Light):
            return False
        return self.color == other.color and self.normal == other.normal

    def __hash__(self):
        return hash((self.color[:], self.normal[:]))

    def to_binary(self):
        return bytearray(self.color + [0x00] + self.color + [0x00] + self.normal + [0x00] + [0x00] * 4)

    def to_c(self):
        return ", ".join([f"0x{a:X}" for a in (*self.color, *self.normal)])


class Ambient:
    def __init__(self, color: Sequence):
        self.color: Sequence = color

    def __eq__(self, other):
        if not isinstance(other, Ambient):
            return False
        return self.color == other.color

    def __hash__(self):
        return hash(self.color[:])

    def to_binary(self):
        return bytearray(self.color + [0x00] + self.color + [0x00])

    def to_c(self):
        return ", ".join([f"0x{a:X}" for a in self.color])


class Hilite:
    def __init__(self, name, x1, y1, x2, y2):
        self.name = name
        self.startAddress = 0
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def fields(self):
        return self.x1, self.y1, self.x2, self.y2

    def to_binary(self):
        return b"".join(a.to_bytes(4, "big") for a in self.fields)

    def to_c(self):
        return f"Hilite {self.name} = {{{', '.join(str(a) for a in self.fields)}}}"


class Lights:
    def __init__(self, name, f3d):
        self.name = name
        self.f3d = f3d
        self.startAddress = 0
        self.a = None
        self.l = []

    def set_addr(self, startAddress):
        startAddress = get64bitAlignedAddr(startAddress)
        self.startAddress = startAddress
        print(f"Lights {self.name}: {str(startAddress)}, {str(self.size())}")
        return (startAddress, startAddress + self.size())

    def save_binary(self, romfile):
        romfile.seek(self.startAddress)
        romfile.write(self.to_binary())

    def size(self):
        if self.f3d.F3DEX_GBI_3:
            count = len(self.l)
        else:
            count = max(len(self.l), 1)
        return count * LIGHT_SIZE + AMBIENT_SIZE

    def getLightPointer(self, i):
        if self.f3d.F3DEX_GBI_3:
            return self.startAddress + i * LIGHT_SIZE
        else:
            return self.startAddress + AMBIENT_SIZE + i * LIGHT_SIZE

    def getAmbientPointer(self):
        if self.f3d.F3DEX_GBI_3:
            return self.startAddress + len(self.l) * LIGHT_SIZE
        else:
            return self.startAddress

    def to_binary(self):
        ambientData = self.a.to_binary()
        data = bytes()
        if len(self.l) == 0 and not self.f3d.F3DEX_GBI_3:
            data += Light([0, 0, 0], [0, 0, 0]).to_binary()
        else:
            for i in range(len(self.l)):
                data += self.l[i].to_binary()
        if self.f3d.F3DEX_GBI_3:
            data = data + ambientData
        else:
            data = ambientData + data
        return data

    def to_c(self):
        data = CData()
        data.header = f"extern Lights{str(len(self.l))} {self.name};\n"
        data.source = f"Lights{str(len(self.l))} {self.name} = gdSPDefLights{str(len(self.l))}(\n"
        data.source += "\t" + self.a.to_c()
        for light in self.l:
            data.source += ",\n\t" + light.to_c()
        data.source += ");\n\n"
        return data


class LookAt:
    # F3DEX3 TODO: update this
    def __init__(self, name, f3d):
        self.name = name
        self.f3d = f3d
        self.startAddress = 0
        self.l = []  # 2 lights

    def to_binary(self):
        return self.l[0].to_binary() + self.l[1].to_binary()

    def to_c(self):
        # {{}} => lookat, light array,
        # {{}} => light, light_t
        def spc(x):
            return ", ".join(str(c) for c in x)

        return (
            f"LookAt {self.name} = {{{{"
            + "{{{"
            + spc(self.l[0].color)
            + "}, 0, "
            + "{"
            + spc(self.l[0].normal)
            + "}, 0 }}"
            + "{{{"
            + spc(self.l[1].color)
            + "}, 0, "
            + "{"
            + spc(self.l[1].normal)
            + "}, 0}}"
            + "}}\n"
        )


# A palette is just a RGBA16 texture with width = 1.
@dataclass
class FImage:
    name: str
    fmt: str
    bitSize: str
    width: int
    height: int
    filename: str
    data: bytearray = field(init=False, compare=False, default_factory=bytearray)
    startAddress: int = field(init=False, compare=False, default=0)
    isLargeTexture: bool = field(init=False, compare=False, default=False)
    converted: bool = field(init=False, compare=False, default=False)

    @property
    def aligner_name(self):
        return f"{self.name}_aligner"

    def size(self):
        return len(self.data)

    def to_binary(self):
        return self.data

    def to_c(self, texArrayBitSize):
        return self.to_c_helper(self.to_c_data(texArrayBitSize), texArrayBitSize)

    def to_c_tex_separate(self, texPath, texArrayBitSize):
        return self.to_c_helper('#include "' + texPath + self.filename + '"', texArrayBitSize)

    def to_c_helper(self, texData, bitsPerValue):
        code = CData()
        code.header = f"extern u{str(bitsPerValue)} {self.name}[];\n"

        # This is to force 8 byte alignment
        if bitsPerValue != 64:
            code.source = f"Gfx {self.aligner_name}[] = {{gsSPEndDisplayList()}};\n"
        code.source += f"u{str(bitsPerValue)} {self.name}[] = {{\n\t"
        code.source += texData
        code.source += "\n};\n\n"
        return code

    def to_c_data(self, bitsPerValue):
        if not self.converted:
            raise PluginError(
                "Error: Trying to write texture data to C, but haven't actually converted the image file to bytes yet."
            )

        bytesPerValue = int(bitsPerValue / 8)
        numValues = int(len(self.data) / bytesPerValue)
        remainderCount = len(self.data) - numValues * bytesPerValue
        digits = 2 + 2 * bytesPerValue

        code = "".join(
            [
                format(
                    int.from_bytes(self.data[i * bytesPerValue : (i + 1) * bytesPerValue], "big"),
                    "#0" + str(digits) + "x",
                )
                + ", "
                + ("\n\t" if i % 8 == 7 else "")
                for i in range(numValues)
            ]
        )

        if remainderCount > 0:
            start = numValues * bytesPerValue
            end = (numValues + 1) * bytesPerValue
            code += format(
                int.from_bytes(self.data[start:end], "big") << (8 * (bytesPerValue - remainderCount)),
                "#0" + str(digits) + "x",
            )

        return code

    def set_addr(self, startAddress):
        startAddress = get64bitAlignedAddr(startAddress)
        self.startAddress = startAddress
        print("Image " + self.name + ": " + str(startAddress) + ", " + str(self.size()))
        return startAddress, startAddress + self.size()

    def save_binary(self, romfile):
        romfile.seek(self.startAddress)
        romfile.write(self.to_binary())


# second arg of Dma is a pointer.
def gsDma0p(c, s, l):
    words = _SHIFTL(c, 24, 8) | _SHIFTL(l, 0, 24), int(s)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsDma1p(c, s, l, p):
    words = _SHIFTL(c, 24, 8) | _SHIFTL(p, 16, 8) | _SHIFTL(l, 0, 16), int(s)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsDma2p(c, adrs, length, idx, ofs):
    words = _SHIFTL(c, 24, 8) | _SHIFTL((length - 1) / 8, 19, 5) | _SHIFTL(ofs / 8, 8, 8) | _SHIFTL(idx, 0, 8), int(
        adrs
    )
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsSPNoOp(f3d):
    return gsDma0p(f3d.G_SPNOOP, 0, 0)


# base class for gbi macros
@dataclass(unsafe_hash=True)
class GbiMacro:
    _segptrs = False
    _ptr_amp = False
    _hex = 0  # If nonzero, write int values as hex with specified digits

    tags = GfxTag(0)
    """
    Type: GfxTag. The tags' current use is to determine how to write gfx scrolling code for this given command.
    This is an enum flag, so it can be composed of multiple tag values. Use "|=" when adding flags.
    This is unannotated and will not be considered when calculating the hash.
    """

    fMaterial = None
    """
    Type: FMaterial. The material that contains scroll info for this command. This member exists in case a material command is moved out of its original display list.
    That would cause an issue for scrolling that modifies static DLs, which requires the command's index into its current display list.
    For example, inling material commands.
    This is unannotated and will not be considered when calculating the hash.
    """

    def get_ptr_offsets(self, f3d):
        return [4]

    def getargs(self, static):
        return (self.getattr_virtual(getattr(self, field.name), static) for field in fields(self))

    def getattr_virtual(self, field, static):
        if hasattr(field, "name"):
            if self._segptrs and not static and bpy.context.scene.gameEditorMode == "Homebrew":
                return f"segmented_to_virtual({field.name})"
            if self._ptr_amp:
                return f"&{field.name}"
            else:
                return field.name
        if hasattr(field, "__iter__") and type(field) is not str:
            return " | ".join(field) if len(field) else "0"
        if self._hex > 0 and isinstance(field, int):
            temp = field if field >= 0 else (1 << (self._hex * 4)) + field
            return f"{temp:#0{self._hex + 2}x}"  # + 2 for the 0x part
        return str(field)

    def to_c(self, static=True):
        if static:
            return f"g{'s'*static}{type(self).__name__}({', '.join( self.getargs(static) )})"
        else:
            args = ["glistp++"] + list(self.getargs(static))
            return f"g{'s'*static}{type(self).__name__}({', '.join( args )})"

    def size(self, f3d):
        return GFX_SIZE


@dataclass(unsafe_hash=True)
class SPMatrix(GbiMacro):
    matrix: int
    param: int

    def to_binary(self, f3d, segments):
        matPtr = int(self.matrix, 16)
        if f3d.F3DEX_GBI_2:
            return gsDma2p(f3d.G_MTX, matPtr, MTX_SIZE, self.param ^ f3d.G_MTX_PUSH, 0)
        else:
            return gsDma1p(f3d.G_MTX, matPtr, MTX_SIZE, self.param)


# TODO: Divide vertlist into sections
# Divide mesh drawing by materials into separate gfx


@dataclass(unsafe_hash=True)
class SPVertex(GbiMacro):
    # v = seg pointer, n = count, v0  = ?
    vertList: VtxList
    offset: int
    count: int
    index: int
    _segptrs = True  # call segmented_to_virtual in to_c method

    def to_binary(self, f3d, segments):
        vertPtr = int.from_bytes(
            encodeSegmentedAddr(self.vertList.startAddress + self.offset * VTX_SIZE, segments), "big"
        )

        if f3d.F3DEX_GBI_2:
            words = (
                _SHIFTL(f3d.G_VTX, 24, 8) | _SHIFTL(self.count, 12, 8) | _SHIFTL(self.index + self.count, 1, 7),
                vertPtr,
            )

            return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")

        elif f3d.F3DEX_GBI or f3d.F3DLP_GBI:
            return gsDma1p(f3d.G_VTX, vertPtr, (self.count << 10) | (VTX_SIZE * self.count - 1), self.index * 2)

        else:
            return gsDma1p(f3d.G_VTX, vertPtr, VTX_SIZE * self.count, (self.count - 1) << 4 | self.index)

    def to_c(self, static=True):
        header = "gsSPVertex(" if static else "gSPVertex(glistp++, "
        if not static and bpy.context.scene.gameEditorMode == "Homebrew":
            header += "segmented_to_virtual(" + self.vertList.name + " + " + str(self.offset) + ")"
        else:
            header += self.vertList.name + " + " + str(self.offset)
        return header + ", " + str(self.count) + ", " + str(self.index) + ")"


@dataclass(unsafe_hash=True)
class SPViewport(GbiMacro):
    # v = seg pointer, n = count, v0  = ?
    viewport: Vp
    _ptr_amp = True  # add an ampersand to names

    def to_binary(self, f3d, segments):
        vpPtr = int.from_bytes(encodeSegmentedAddr(self.viewport.startAddress, segments), "big")

        if f3d.F3DEX_GBI_2:
            return gsDma2p(f3d.G_MOVEMEM, vpPtr, VP_SIZE, f3d.G_MV_VIEWPORT, 0)
        else:
            return gsDma1p(f3d.G_MOVEMEM, vpPtr, VP_SIZE, f3d.G_MV_VIEWPORT)


# F3DEX3 TODO: Encoding of hints (and generation of the hint values)


@dataclass(unsafe_hash=True)
class SPDisplayList(GbiMacro):
    displayList: GfxList

    def to_binary(self, f3d, segments):
        dlPtr = int.from_bytes(encodeSegmentedAddr(self.displayList.startAddress, segments), "big")
        return gsDma1p(f3d.G_DL, dlPtr, 0, f3d.G_DL_PUSH)

    def to_c(self, static=True):
        if static:
            return "gsSPDisplayList(" + self.displayList.name + ")"
        elif self.displayList.DLFormat == DLFormat.Static:
            header = "gSPDisplayList(glistp++, "
            if bpy.context.scene.gameEditorMode == "Homebrew":
                return header + "segmented_to_virtual(" + self.displayList.name + "))"
            else:
                return header + self.displayList.name + ")"
        else:
            return "glistp = " + self.displayList.name + "(glistp)"


@dataclass(unsafe_hash=True)
class SPBranchList(GbiMacro):
    displayList: GfxList
    _ptr_amp = True  # add an ampersand to names

    def to_binary(self, f3d, segments):
        dlPtr = int.from_bytes(encodeSegmentedAddr(self.displayList.startAddress, segments), "big")
        return gsDma1p(f3d.G_DL, dlPtr, 0, f3d.G_DL_NOPUSH)


@dataclass(unsafe_hash=True)
class SPEndDisplayList(GbiMacro):
    def to_binary(self, f3d, segments):
        words = _SHIFTL(f3d.G_ENDDL, 24, 8), 0
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


# SPSprite2DBase


# RSP short command (no DMA required) macros
def gsImmp0(c):
    words = _SHIFTL((c), 24, 8), 0
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsImmp1(c, p0):
    words = _SHIFTL((c), 24, 8), int(p0)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsImmp2(c, p0, p1):
    words = _SHIFTL((c), 24, 8), _SHIFTL((p0), 16, 16) | _SHIFTL((p1), 8, 8)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsImmp3(c, p0, p1, p2):
    words = _SHIFTL((c), 24, 8), (_SHIFTL((p0), 16, 16) | _SHIFTL((p1), 8, 8) | _SHIFTL((p2), 0, 8))
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


# last arg of Immp21 is a pointer.
def gsImmp21(c, p0, p1, dat):
    words = _SHIFTL((c), 24, 8) | _SHIFTL((p0), 8, 16) | _SHIFTL((p1), 0, 8), int(dat)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsMoveWd(index, offset, data, f3d):
    if f3d.F3DEX_GBI_3:
        offset &= 0xFFF
    if f3d.F3DEX_GBI_2:
        return gsDma1p(f3d.G_MOVEWORD, data, offset, index)
    else:
        return gsImmp21(f3d.G_MOVEWORD, offset, index, data)


def gsMoveHalfwd(index, offset, data, f3d):
    if not f3d.F3DEX_GBI_3:
        raise PluginError("gsMoveHalfwd requires F3DEX3 microcode")
    return gsDma1p(f3d.G_MOVEWORD, data, (offset & 0xFFF) | f3d.G_MW_HALFWORD_FLAG, index)


# SPSprite2DScaleFlip
# SPSprite2DDraw

# Note: the SP1Triangle() and line macros multiply the vertex indices
# by 10, this is an optimization for the microcode.


def _gsSP1Triangle_w1(v0, v1, v2):
    return _SHIFTL((v0) * 2, 16, 8) | _SHIFTL((v1) * 2, 8, 8) | _SHIFTL((v2) * 2, 0, 8)


def _gsSP1Triangle_w1f(v0, v1, v2, flag, f3d):
    if f3d.F3DLP_GBI or f3d.F3DEX_GBI:
        if flag == 0:
            return _gsSP1Triangle_w1(v0, v1, v2)
        elif flag == 1:
            return _gsSP1Triangle_w1(v1, v2, v0)
        else:
            return _gsSP1Triangle_w1(v2, v0, v1)
    else:
        return _SHIFTL((flag), 24, 8) | _SHIFTL((v0) * 10, 16, 8) | _SHIFTL((v1) * 10, 8, 8) | _SHIFTL((v2) * 10, 0, 8)


def _gsSPLine3D_w1(v0, v1, wd):
    return _SHIFTL((v0) * 2, 16, 8) | _SHIFTL((v1) * 2, 8, 8) | _SHIFTL((wd), 0, 8)


def _gsSPLine3D_w1f(v0, v1, wd, flag, f3d):
    if f3d.F3DLP_GBI or f3d.F3DEX_GBI:
        if flag == 0:
            return _gsSPLine3D_w1(v0, v1, wd)
        else:
            return _gsSPLine3D_w1(v1, v0, wd)
    else:
        return _SHIFTL((flag), 24, 8) | _SHIFTL((v0) * 10, 16, 8) | _SHIFTL((v1) * 10, 8, 8) | _SHIFTL((wd), 0, 8)


def _gsSP1Quadrangle_w1f(v0, v1, v2, v3, flag):
    if flag == 0:
        return _gsSP1Triangle_w1(v0, v1, v2)
    elif flag == 1:
        return _gsSP1Triangle_w1(v1, v2, v3)
    elif flag == 2:
        return _gsSP1Triangle_w1(v2, v3, v0)
    else:
        return _gsSP1Triangle_w1(v3, v0, v1)


def _gsSP1Quadrangle_w2f(v0, v1, v2, v3, flag):
    if flag == 0:
        return _gsSP1Triangle_w1(v0, v2, v3)
    elif flag == 1:
        return _gsSP1Triangle_w1(v1, v3, v0)
    elif flag == 1:
        return _gsSP1Triangle_w1(v2, v0, v1)
    else:
        return _gsSP1Triangle_w1(v3, v1, v2)


@dataclass(unsafe_hash=True)
class SP1Triangle(GbiMacro):
    v0: int
    v1: int
    v2: int
    flag: int

    def to_binary(self, f3d, segments):
        if f3d.F3DEX_GBI_2:
            words = _SHIFTL(f3d.G_TRI1, 24, 8) | _gsSP1Triangle_w1f(self.v0, self.v1, self.v2, self.flag, f3d), 0
        else:
            words = _SHIFTL(f3d.G_TRI1, 24, 8), _gsSP1Triangle_w1f(self.v0, self.v1, self.v2, self.flag, f3d)

        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPLine3D(GbiMacro):
    v0: int
    v1: int
    flag: int

    def to_binary(self, f3d, segments):
        if f3d.F3DEX_GBI_3:
            raise PluginError("SPLine3D is removed in F3DEX3")
        elif f3d.F3DEX_GBI_2:
            words = _SHIFTL(f3d.G_LINE3D, 24, 8) | _gsSPLine3D_w1f(self.v0, self.v1, 0, self.flag, f3d), 0
        else:
            words = _SHIFTL(f3d.G_LINE3D, 24, 8), _gsSPLine3D_w1f(self.v0, self.v1, 0, self.flag, f3d)
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPLineW3D(GbiMacro):
    v0: int
    v1: int
    wd: int
    flag: int

    def to_binary(self, f3d, segments):
        if f3d.F3DEX_GBI_3:
            raise PluginError("SPLineW3D is removed in F3DEX3")
        elif f3d.F3DEX_GBI_2:
            words = _SHIFTL(f3d.G_LINE3D, 24, 8) | _gsSPLine3D_w1f(self.v0, self.v1, self.wd, self.flag, f3d), 0
        else:
            words = _SHIFTL(f3d.G_LINE3D, 24, 8), _gsSPLine3D_w1f(self.v0, self.v1, self.wd, self.flag, f3d)
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


# SP1Quadrangle


@dataclass(unsafe_hash=True)
class SP2Triangles(GbiMacro):
    v00: int
    v01: int
    v02: int
    flag0: int
    v10: int
    v11: int
    v12: int
    flag1: int

    def to_binary(self, f3d, segments):
        if f3d.F3DLP_GBI or f3d.F3DEX_GBI:
            words = (
                _SHIFTL(f3d.G_TRI2, 24, 8) | _gsSP1Triangle_w1f(self.v00, self.v01, self.v02, self.flag0, f3d)
            ), _gsSP1Triangle_w1f(self.v10, self.v11, self.v12, self.flag1, f3d)
        else:
            raise PluginError("SP2Triangles not available in Fast3D.")

        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


# F3DEX3 TODO: Encoding of _g*SP5Triangles commands (SPTriangleStrip, SPTriangleFan)
# and support for these in export including tri reordering


@dataclass(unsafe_hash=True)
class SPCullDisplayList(GbiMacro):
    vstart: int
    vend: int

    def to_binary(self, f3d, segments):
        if f3d.F3DLP_GBI or f3d.F3DEX_GBI:
            words = _SHIFTL(f3d.G_CULLDL, 24, 8) | _SHIFTL((self.vstart) * 2, 0, 16), _SHIFTL((self.vend) * 2, 0, 16)
        else:
            words = _SHIFTL(f3d.G_CULLDL, 24, 8) | ((0x0F & (self.vstart)) * 40), ((0x0F & ((self.vend) + 1)) * 40)
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPSegment(GbiMacro):
    segment: int
    base: int

    def to_binary(self, f3d, segments):
        return gsMoveWd(f3d.G_MW_SEGMENT, (self.segment) * 4, self.base, f3d)

    def to_c(self, static=True):
        header = "gsSPSegment(" if static else "gSPSegment(glistp++, "
        return header + str(self.segment) + ", " + "0x" + format(self.base, "X") + ")"


@dataclass(unsafe_hash=True)
class SPClipRatio(GbiMacro):
    ratio: int

    def to_binary(self, f3d, segments):
        if f3d.F3DEX_GBI_3:
            return gsSPNoOp(f3d)

        # These values are supposed to be flipped.
        shortRatioPos = int.from_bytes((-self.ratio).to_bytes(2, "big", signed=True), "big", signed=False)
        shortRatioNeg = int.from_bytes(self.ratio.to_bytes(2, "big", signed=True), "big", signed=False)

        return (
            gsMoveWd(f3d.G_MW_CLIP, f3d.G_MWO_CLIP_RNX, shortRatioNeg, f3d)
            + gsMoveWd(f3d.G_MW_CLIP, f3d.G_MWO_CLIP_RNY, shortRatioNeg, f3d)
            + gsMoveWd(f3d.G_MW_CLIP, f3d.G_MWO_CLIP_RPX, shortRatioPos, f3d)
            + gsMoveWd(f3d.G_MW_CLIP, f3d.G_MWO_CLIP_RPY, shortRatioPos, f3d)
        )

    def size(self, f3d):
        return GFX_SIZE * 4


# SPInsertMatrix
# SPForceMatrix


@dataclass(unsafe_hash=True)
class SPAmbOcclusionAmb(GbiMacro):
    amb: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAmbOcclusionAmb requires F3DEX3 microcode")
        return gsMoveHalfwd(f3d.G_MW_FX, f3d.G_MWO_AO_AMBIENT, self.amb, f3d)


@dataclass(unsafe_hash=True)
class SPAmbOcclusionDir(GbiMacro):
    dir: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAmbOcclusionDir requires F3DEX3 microcode")
        return gsMoveHalfwd(f3d.G_MW_FX, f3d.G_MWO_AO_DIRECTIONAL, self.dir, f3d)


@dataclass(unsafe_hash=True)
class SPAmbOcclusionPoint(GbiMacro):
    point: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAmbOcclusionPoint requires F3DEX3 microcode")
        return gsMoveHalfwd(f3d.G_MW_FX, f3d.G_MWO_AO_POINT, self.point, f3d)


@dataclass(unsafe_hash=True)
class SPAmbOcclusionAmbDir(GbiMacro):
    amb: int
    dir: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAmbOcclusionAmbDir requires F3DEX3 microcode")
        return gsMoveWd(f3d.G_MW_FX, f3d.G_MWO_AO_AMBIENT, (_SHIFTL(self.amb, 16, 16) | _SHIFTL(self.dir, 0, 16)), f3d)


@dataclass(unsafe_hash=True)
class SPAmbOcclusionDirPoint(GbiMacro):
    dir: int
    point: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAmbOcclusionDirPoint requires F3DEX3 microcode")
        return gsMoveWd(
            f3d.G_MW_FX, f3d.G_MWO_AO_DIRECTIONAL, (_SHIFTL(self.dir, 16, 16) | _SHIFTL(self.point, 0, 16)), f3d
        )


@dataclass(unsafe_hash=True)
class SPAmbOcclusion(GbiMacro):
    amb: int
    dir: int
    point: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAmbOcclusion requires F3DEX3 microcode")
        return SPAmbOcclusionAmbDir(self.amb, self.dir).to_binary(f3d, segments) + SPAmbOcclusionPoint(
            self.point
        ).to_binary(f3d, segments)

    def size(self, f3d):
        return GFX_SIZE * 2


@dataclass(unsafe_hash=True)
class SPFresnelScale(GbiMacro):
    scale: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPFresnelScale requires F3DEX3 microcode")
        return gsMoveHalfwd(f3d.G_MW_FX, f3d.G_MWO_FRESNEL_SCALE, self.scale, f3d)


@dataclass(unsafe_hash=True)
class SPFresnelOffset(GbiMacro):
    offset: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPFresnelOffset requires F3DEX3 microcode")
        return gsMoveHalfwd(f3d.G_MW_FX, f3d.G_MWO_FRESNEL_OFFSET, self.offset, f3d)


@dataclass(unsafe_hash=True)
class SPFresnel(GbiMacro):
    scale: int
    offset: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPFresnel requires F3DEX3 microcode")
        return gsMoveWd(
            f3d.G_MW_FX, f3d.G_MWO_FRESNEL_SCALE, (_SHIFTL(self.scale, 16, 16) | _SHIFTL(self.offset, 0, 16)), f3d
        )


@dataclass(unsafe_hash=True)
class SPAttrOffsetST(GbiMacro):
    s: int
    t: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAttrOffsetST requires F3DEX3 microcode")
        return gsMoveWd(f3d.G_MW_FX, f3d.G_MWO_ATTR_OFFSET_S, (_SHIFTL(self.s, 16, 16) | _SHIFTL(self.t, 0, 16)), f3d)


@dataclass(unsafe_hash=True)
class SPAttrOffsetZ(GbiMacro):
    z: int
    _hex = 4

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAttrOffsetZ requires F3DEX3 microcode")
        return gsMoveWd(f3d.G_MW_FX, f3d.G_MWO_ATTR_OFFSET_Z, (_SHIFTL(self.z, 16, 16)), f3d)


@dataclass(unsafe_hash=True)
class SPAlphaCompareCull(GbiMacro):
    mode: str
    thresh: int

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAlphaCompareCull requires F3DEX3 microcode")
        if self.mode == "G_ALPHA_COMPARE_CULL_DISABLE":
            modeVal = f3d.G_ALPHA_COMPARE_CULL_DISABLE
        elif self.mode == "G_ALPHA_COMPARE_CULL_BELOW":
            modeVal = f3d.G_ALPHA_COMPARE_CULL_BELOW
        elif self.mode == "G_ALPHA_COMPARE_CULL_ABOVE":
            modeVal = f3d.G_ALPHA_COMPARE_CULL_ABOVE
        return gsMoveHalfwd(
            f3d.G_MW_FX, f3d.G_MWO_ALPHA_COMPARE_CULL, (_SHIFTL(modeVal, 8, 8) | _SHIFTL(self.thresh, 0, 8)), f3d
        )


@dataclass(unsafe_hash=True)
class SPNormalsMode(GbiMacro):
    mode: str

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPNormalsMode requires F3DEX3 microcode")
        if self.mode == "G_NORMALS_MODE_FAST":
            modeVal = f3d.G_NORMALS_MODE_FAST
        elif self.mode == "G_NORMALS_MODE_AUTO":
            modeVal = f3d.G_NORMALS_MODE_AUTO
        elif self.mode == "G_NORMALS_MODE_MANUAL":
            modeVal = f3d.G_NORMALS_MODE_MANUAL
        return gsMoveHalfwd(f3d.G_MW_FX, f3d.G_MWO_NORMALS_MODE, modeVal & 0xFF, f3d)


# SPMITMatrix (F3DEX3)


@dataclass(unsafe_hash=True)
class SPModifyVertex(GbiMacro):
    vtx: int
    where: int
    val: int

    def to_binary(self, f3d, segments):
        if f3d.F3DLP_GBI or f3d.F3DEX_GBI:
            words = (
                _SHIFTL(f3d.G_MODIFYVTX, 24, 8) | _SHIFTL((self.where), 16, 8) | _SHIFTL((self.vtx) * 2, 0, 16),
                self.val,
            )
            return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")
        else:
            return gsMoveWd(f3d.G_MW_POINTS, (self.vtx) * 40 + (self.where), self.val, f3d)


# LOD commands?
# SPBranchLessZ


@dataclass(unsafe_hash=True)
class SPBranchLessZraw(GbiMacro):
    dl: GfxList
    vtx: int
    zval: int

    def to_binary(self, f3d, segments):
        dlPtr = int.from_bytes(encodeSegmentedAddr(self.dl.startAddress, segments), "big")

        words0 = _SHIFTL(f3d.G_RDPHALF_1, 24, 8), dlPtr
        words1 = (
            _SHIFTL(f3d.G_BRANCH_Z, 24, 8) | _SHIFTL((self.vtx) * 5, 12, 12) | _SHIFTL((self.vtx) * 2, 0, 12),
            self.zval,
        )

        return (
            words0[0].to_bytes(4, "big")
            + words0[1].to_bytes(4, "big")
            + words1[0].to_bytes(4, "big")
            + words1[1].to_bytes(4, "big")
        )

    def size(self, f3d):
        return GFX_SIZE * 2


# SPLoadUcode (RSP)

# SPDma_io
# SPDmaRead
# SPDmaRead
# SPDmaWrite
# SPDmaWrite


@dataclass(unsafe_hash=True)
class SPNumLights(GbiMacro):
    # n is macro name (string)
    n: str

    def to_binary(self, f3d, segments):
        return gsMoveWd(f3d.G_MW_NUMLIGHT, f3d.G_MWO_NUMLIGHT, f3d.NUML(self.n), f3d)


@dataclass(unsafe_hash=True)
class SPLight(GbiMacro):
    # n is macro name (string)
    light: int  # start address of light
    n: str
    _segptrs = True  # call segmented_to_virtual in to_c method
    _size = LIGHT_SIZE

    def to_binary(self, f3d, segments):
        lightPtr = int.from_bytes(encodeSegmentedAddr(self.light, segments), "big")
        idx = lightIndex[self.n]
        if f3d.F3DEX_GBI_2:
            if f3d.F3DEX_GBI_3:
                offset = (idx - 1) * 0x10 + 0x10
            else:
                offset = idx * 24 + 24
            data = gsDma2p(f3d.G_MOVEMEM, lightPtr, self._size, f3d.G_MV_LIGHT, offset)
        else:
            data = gsDma1p(f3d.G_MOVEMEM, lightPtr, self._size, (idx - 1) * 2 + f3d.G_MV_L0)
        return data


@dataclass(unsafe_hash=True)
class SPAmbient(SPLight):
    _size = AMBIENT_SIZE

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPAmbient requires F3DEX3 microcode")
        return super().to_binary(f3d, segments)


@dataclass(unsafe_hash=True)
class SPLightColor(GbiMacro):
    # n is macro name (string)
    n: str
    col: Sequence[int]

    def color_to_int(self):
        return self.col[0] * 0x1000000 + self.col[1] * 0x10000 + self.col[2] * 0x100 + 0xFF

    def to_binary(self, f3d, segments):
        return gsMoveWd(f3d.G_MW_LIGHTCOL, f3d.getLightMWO_a(self.n), self.color_to_int(), f3d) + gsMoveWd(
            f3d.G_MW_LIGHTCOL, f3d.getLightMWO_b(self.n), self.col, f3d
        )

    def to_c(self, static=True):
        header = "gsSPLightColor(" if static else "gSPLightColor(glistp++, "
        return header + f"{self.n}, 0x" + format(self.color_to_int(), "08X") + ")"

    def size(self, _f3d):
        return GFX_SIZE * 2


@dataclass(unsafe_hash=True)
class SPSetLights(GbiMacro):
    lights: Lights

    def get_ptr_offsets(self, f3d):
        if f3d.F3DEX_GBI_3:
            return [12]
        offsets = []
        if len(self.lights.l) == 0:
            offsets = [12, 20]
        else:
            lightNum = len(self.lights.l)
            for i in range(lightNum):
                offsets.append((i + 1) * 8 + 4)
            offsets.append((lightNum + 1) * 8 + 4)
        return offsets

    def to_binary(self, f3d, segments):
        n = len(self.lights.l)
        data = SPNumLights(f"NUMLIGHTS_{n}").to_binary(f3d, segments)
        if f3d.F3DEX_GBI_3:
            data += gsDma2p(
                f3d.G_MOVEMEM, self.lights.startAddress, len(self.lights.l) * 0x10 + 8, f3d.G_MV_LIGHT, 0x10
            )
        elif len(self.lights.l) == 0:
            # The light does not exist in python, but is added in
            # when converted to binary, making this address valid.
            data += SPLight(self.lights.getLightPointer(0), "LIGHT_1").to_binary(f3d, segments)
            data += SPLight(self.lights.getAmbientPointer(), "LIGHT_2").to_binary(f3d, segments)
        else:
            for i in range(len(self.lights.l)):
                data += SPLight(self.lights.getLightPointer(i), "LIGHT_" + str(i + 1)).to_binary(f3d, segments)
            data += SPLight(self.lights.getAmbientPointer(), "LIGHT_" + str(n + 1)).to_binary(f3d, segments)
        return data

    def to_c(self, static=True):
        n = len(self.lights.l)
        header = f"gsSPSetLights{n}(" if static else f"gSPSetLights{n}(glistp++, "
        if not static and bpy.context.scene.gameEditorMode == "Homebrew":
            header += f"(*(Lights{n}*) segmented_to_virtual(&{self.lights.name}))"
        else:
            header += self.lights.name
        return header + ")"

    def size(self, f3d):
        if f3d.F3DEX_GBI_3:
            return GFX_SIZE * 2
        else:
            return GFX_SIZE * (2 + max(len(self.lights.l), 1))


# F3DEX3 TODO: SPCameraWorld

# Reflection/Hiliting Macros


def gsSPLookAtX(l, f3d):
    if f3d.F3DEX_GBI_2:
        return gsDma2p(f3d.G_MOVEMEM, l, LIGHT_SIZE, f3d.G_MV_LIGHT, f3d.G_MVO_LOOKATX)
    else:
        return gsDma1p(f3d.G_MOVEMEM, l, LIGHT_SIZE, f3d.G_MV_LOOKATX)


def gsSPLookAtY(l, f3d):
    if f3d.F3DEX_GBI_2:
        return gsDma2p(f3d.G_MOVEMEM, l, LIGHT_SIZE, f3d.G_MV_LIGHT, f3d.G_MVO_LOOKATY)
    else:
        return gsDma1p(f3d.G_MOVEMEM, l, LIGHT_SIZE, f3d.G_MV_LOOKATY)


@dataclass(unsafe_hash=True)
class SPLookAt(GbiMacro):
    la: LookAt
    _ptr_amp = True  # add an ampersand to names

    def to_binary(self, f3d, segments):
        lookAtPtr = int.from_bytes(encodeSegmentedAddr(self.la.startAddress, segments), "big")
        if f3d.F3DEX_GBI_3:
            return gsDma2p(f3d.G_MOVEMEM, lookAtPtr, 8, f3d.G_MV_LIGHT, 8)
        else:
            return gsSPLookAtX(lookAtPtr, f3d) + gsSPLookAtY(lookAtPtr + 16, f3d)


@dataclass(unsafe_hash=True)
class DPSetHilite1Tile(GbiMacro):
    tile: int
    hilite: Hilite
    width: int
    height: int
    _ptr_amp = True  # add an ampersand to names

    def to_binary(self, f3d, segments):
        return DPSetTileSize(
            self.tile,
            self.hilite.x1 & 0xFFF,
            self.hilite.y1 & 0xFFF,
            ((self.width - 1) * 4 + self.hilite.x1) & 0xFFF,
            ((self.height - 1) * 4 + self.hilite.y1) & 0xFFF,
        ).to_binary(f3d, segments)


@dataclass(unsafe_hash=True)
class DPSetHilite2Tile(GbiMacro):
    tile: int
    hilite: Hilite
    width: int
    height: int
    _ptr_amp = True  # add an ampersand to names

    def to_binary(self, f3d, segments):
        return DPSetTileSize(
            self.tile,
            self.hilite.x2 & 0xFFF,
            self.hilite.y2 & 0xFFF,
            ((self.width - 1) * 4 + self.hilite.x2) & 0xFFF,
            ((self.height - 1) * 4 + self.hilite.y2) & 0xFFF,
        ).to_binary(f3d, segments)


@dataclass(unsafe_hash=True)
class SPFogFactor(GbiMacro):
    fm: int
    fo: int

    def to_binary(self, f3d, segments):
        return gsMoveWd(f3d.G_MW_FOG, f3d.G_MWO_FOG, (_SHIFTL(self.fm, 16, 16) | _SHIFTL(self.fo, 0, 16)), f3d)


class SPFogPosition(GbiMacro):
    def __init__(self, minVal, maxVal):
        self.minVal = int(round(minVal))
        self.maxVal = int(round(maxVal))

    def to_binary(self, f3d, segments):
        return gsMoveWd(
            f3d.G_MW_FOG,
            f3d.G_MWO_FOG,
            (
                _SHIFTL((128000 / ((self.maxVal) - (self.minVal))), 16, 16)
                | _SHIFTL(((500 - (self.minVal)) * 256 / ((self.maxVal) - (self.minVal))), 0, 16)
            ),
            f3d,
        )

    def to_c(self, static=True):
        header = "gsSPFogPosition(" if static else "gSPFogPosition(glistp++, "
        return header + str(self.minVal) + ", " + str(self.maxVal) + ")"


@dataclass(unsafe_hash=True)
class SPTexture(GbiMacro):
    s: int
    t: int
    level: int
    tile: int
    on: int

    def to_binary(self, f3d, segments):
        if f3d.F3DEX_GBI_2:
            words = (
                _SHIFTL(f3d.G_TEXTURE, 24, 8)
                | _SHIFTL((self.level), 11, 3)
                | _SHIFTL((self.tile), 8, 3)
                | _SHIFTL((self.on), 1, 7)
            ), (_SHIFTL((self.s), 16, 16) | _SHIFTL((self.t), 0, 16))
        else:
            words = (
                _SHIFTL(f3d.G_TEXTURE, 24, 8)
                | _SHIFTL((self.level), 11, 3)
                | _SHIFTL((self.tile), 8, 3)
                | _SHIFTL((self.on), 0, 8)
            ), (_SHIFTL((self.s), 16, 16) | _SHIFTL((self.t), 0, 16))

        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


# SPTextureL


@dataclass(unsafe_hash=True)
class SPPerspNormalize(GbiMacro):
    s: int

    def to_binary(self, f3d, segments):
        if f3d.F3DEX_GBI_3:
            return gsMoveHalfwd(f3d.G_MW_FX, f3d.G_MWO_PERSPNORM, (self.s), f3d)
        else:
            return gsMoveWd(f3d.G_MW_PERSPNORM, 0, (self.s), f3d)


# SPPopMatrixN
# SPPopMatrix


def gsSPGeometryMode_F3DEX_GBI_2(c, s, f3d):
    words = (_SHIFTL(f3d.G_GEOMETRYMODE, 24, 8) | _SHIFTL(~c, 0, 24)), s
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsSPGeometryMode_Non_F3DEX_GBI_2(word, f3d):
    words = _SHIFTL(f3d.G_SETGEOMETRYMODE, 24, 8), word
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def geoFlagListToWord(flagList, f3d):
    word = 0
    for name in flagList:
        if name in f3d.allGeomModeFlags:
            word += getattr(f3d, name)
        else:
            try:  # Try to cast name to an int instead, if this fails raise an explicit error
                word += int(name, 0)
            except ValueError as e:
                raise PluginError("Invalid geometry mode flag " + name) from e

    return word


@dataclass(unsafe_hash=True)
class SPGeometryMode(GbiMacro):
    clearFlagList: list
    setFlagList: list

    def to_binary(self, f3d, segments):
        if f3d.F3DEX_GBI_2:
            wordClear = geoFlagListToWord(self.clearFlagList, f3d)
            wordSet = geoFlagListToWord(self.setFlagList, f3d)

            return gsSPGeometryMode_F3DEX_GBI_2(wordClear, wordSet, f3d)
        else:
            raise PluginError("GeometryMode only available in F3DEX_GBI_2.")


@dataclass(unsafe_hash=True)
class SPSetGeometryMode(GbiMacro):
    flagList: list

    def to_binary(self, f3d, segments):
        word = geoFlagListToWord(self.flagList, f3d)
        if f3d.F3DEX_GBI_2:
            return gsSPGeometryMode_F3DEX_GBI_2(0, word, f3d)
        else:
            words = _SHIFTL(f3d.G_SETGEOMETRYMODE, 24, 8), word
            return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPClearGeometryMode(GbiMacro):
    flagList: list

    def to_binary(self, f3d, segments):
        word = geoFlagListToWord(self.flagList, f3d)
        if f3d.F3DEX_GBI_2:
            return gsSPGeometryMode_F3DEX_GBI_2(word, 0, f3d)
        else:
            words = _SHIFTL(f3d.G_CLEARGEOMETRYMODE, 24, 8), word
            return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPLoadGeometryMode(GbiMacro):
    flagList: list

    def to_binary(self, f3d, segments):
        word = geoFlagListToWord(self.flagList, f3d)
        if f3d.F3DEX_GBI_2:
            return gsSPGeometryMode_F3DEX_GBI_2(-1, word, f3d)
        else:
            raise PluginError("LoadGeometryMode only available in F3DEX_GBI_2.")


def gsSPSetOtherMode(cmd, sft, length, data, f3d):
    if f3d.F3DEX_GBI_2:
        words = _SHIFTL(cmd, 24, 8) | _SHIFTL(32 - (sft) - (length), 8, 8) | _SHIFTL((length) - 1, 0, 8), data
    else:
        words = _SHIFTL(cmd, 24, 8) | _SHIFTL(sft, 8, 8) | _SHIFTL(length, 0, 8), (data)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPSetOtherMode(GbiMacro):
    cmd: str
    sft: int
    length: int
    flagList: list

    def to_binary(self, f3d, segments):
        data = 0
        for flag in self.flagList:
            data |= getattr(f3d, str(flag), flag)
        cmd = getattr(f3d, str(self.cmd), self.cmd)
        sft = getattr(f3d, str(self.sft), self.sft)
        return gsSPSetOtherMode(cmd, sft, self.length, data, f3d)


@dataclass(unsafe_hash=True)
class DPPipelineMode(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_PM_1PRIMITIVE":
            modeVal = f3d.G_PM_1PRIMITIVE
        elif self.mode == "G_PM_NPRIMITIVE":
            modeVal = f3d.G_PM_NPRIMITIVE
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_PIPELINE, 1, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetCycleType(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_CYC_1CYCLE":
            modeVal = f3d.G_CYC_1CYCLE
        elif self.mode == "G_CYC_2CYCLE":
            modeVal = f3d.G_CYC_2CYCLE
        elif self.mode == "G_CYC_COPY":
            modeVal = f3d.G_CYC_COPY
        elif self.mode == "G_CYC_FILL":
            modeVal = f3d.G_CYC_FILL
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_CYCLETYPE, 2, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetTexturePersp(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_TP_NONE":
            modeVal = f3d.G_TP_NONE
        elif self.mode == "G_TP_PERSP":
            modeVal = f3d.G_TP_PERSP
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_TEXTPERSP, 1, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetTextureDetail(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_TD_CLAMP":
            modeVal = f3d.G_TD_CLAMP
        elif self.mode == "G_TD_SHARPEN":
            modeVal = f3d.G_TD_SHARPEN
        elif self.mode == "G_TD_DETAIL":
            modeVal = f3d.G_TD_DETAIL
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_TEXTDETAIL, 2, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetTextureLOD(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_TL_TILE":
            modeVal = f3d.G_TL_TILE
        elif self.mode == "G_TL_LOD":
            modeVal = f3d.G_TL_LOD
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_TEXTLOD, 1, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetTextureLUT(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_TT_NONE":
            modeVal = f3d.G_TT_NONE
        elif self.mode == "G_TT_RGBA16":
            modeVal = f3d.G_TT_RGBA16
        elif self.mode == "G_TT_IA16":
            modeVal = f3d.G_TT_IA16
        else:
            print("Invalid LUT mode " + str(self.mode))
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_TEXTLUT, 2, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetTextureFilter(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_TF_POINT":
            modeVal = f3d.G_TF_POINT
        elif self.mode == "G_TF_AVERAGE":
            modeVal = f3d.G_TF_AVERAGE
        elif self.mode == "G_TF_BILERP":
            modeVal = f3d.G_TF_BILERP
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_TEXTFILT, 2, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetTextureConvert(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_TC_CONV":
            modeVal = f3d.G_TC_CONV
        elif self.mode == "G_TC_FILTCONV":
            modeVal = f3d.G_TC_FILTCONV
        elif self.mode == "G_TC_FILT":
            modeVal = f3d.G_TC_FILT
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_TEXTCONV, 3, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetCombineKey(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_CK_NONE":
            modeVal = f3d.G_CK_NONE
        elif self.mode == "G_CK_KEY":
            modeVal = f3d.G_CK_KEY
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_COMBKEY, 1, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetColorDither(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_CD_MAGICSQ":
            modeVal = f3d.G_CD_MAGICSQ
        elif self.mode == "G_CD_BAYER":
            modeVal = f3d.G_CD_BAYER
        elif self.mode == "G_CD_NOISE":
            modeVal = f3d.G_CD_NOISE
        elif self.mode == "G_CD_DISABLE":
            modeVal = f3d.G_CD_DISABLE
        elif self.mode == "G_CD_ENABLE":
            modeVal = f3d.G_CD_ENABLE
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_RGBDITHER, 2, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetAlphaDither(GbiMacro):
    # mode is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_AD_PATTERN":
            modeVal = f3d.G_AD_PATTERN
        elif self.mode == "G_AD_NOTPATTERN":
            modeVal = f3d.G_AD_NOTPATTERN
        elif self.mode == "G_AD_NOISE":
            modeVal = f3d.G_AD_NOISE
        elif self.mode == "G_AD_DISABLE":
            modeVal = f3d.G_AD_DISABLE
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_H, f3d.G_MDSFT_ALPHADITHER, 2, modeVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetAlphaCompare(GbiMacro):
    # mask is a string
    mode: str

    def to_binary(self, f3d, segments):
        if self.mode == "G_AC_NONE":
            maskVal = f3d.G_AC_NONE
        elif self.mode == "G_AC_THRESHOLD":
            maskVal = f3d.G_AC_THRESHOLD
        elif self.mode == "G_AC_DITHER":
            maskVal = f3d.G_AC_DITHER
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_L, f3d.G_MDSFT_ALPHACOMPARE, 2, maskVal, f3d)


@dataclass(unsafe_hash=True)
class DPSetDepthSource(GbiMacro):
    # src is a string
    src: str

    def to_binary(self, f3d, segments):
        if self.src == "G_ZS_PIXEL":
            srcVal = f3d.G_ZS_PIXEL
        elif self.src == "G_ZS_PRIM":
            srcVal = f3d.G_ZS_PRIM
        return gsSPSetOtherMode(f3d.G_SETOTHERMODE_L, f3d.G_MDSFT_ZSRCSEL, 1, srcVal, f3d)


def renderFlagListToWord(flagList, f3d):
    word = 0
    for name in flagList:
        word += getattr(f3d, name)

    return word


def GBL_c1(m1a, m1b, m2a, m2b):
    return (m1a) << 30 | (m1b) << 26 | (m2a) << 22 | (m2b) << 18


def GBL_c2(m1a, m1b, m2a, m2b):
    return (m1a) << 28 | (m1b) << 24 | (m2a) << 20 | (m2b) << 16


@dataclass(unsafe_hash=True)
class DPSetRenderMode(GbiMacro):
    # bl0-3 are string for each blender enum
    def __init__(self, flagList, blendList):
        self.flagList = flagList
        self.use_preset = blendList is None
        if not self.use_preset:
            self.bl00 = blendList[0]
            self.bl01 = blendList[1]
            self.bl02 = blendList[2]
            self.bl03 = blendList[3]
            self.bl10 = blendList[4]
            self.bl11 = blendList[5]
            self.bl12 = blendList[6]
            self.bl13 = blendList[7]

    def getGBL_c(self, f3d):
        bl00 = getattr(f3d, self.bl00)
        bl01 = getattr(f3d, self.bl01)
        bl02 = getattr(f3d, self.bl02)
        bl03 = getattr(f3d, self.bl03)
        bl10 = getattr(f3d, self.bl10)
        bl11 = getattr(f3d, self.bl11)
        bl12 = getattr(f3d, self.bl12)
        bl13 = getattr(f3d, self.bl13)
        return GBL_c1(bl00, bl01, bl02, bl03) | GBL_c2(bl10, bl11, bl12, bl13)

    def to_binary(self, f3d, segments):
        flagWord = renderFlagListToWord(self.flagList, f3d)

        if not self.use_preset:
            return gsSPSetOtherMode(
                f3d.G_SETOTHERMODE_L, f3d.G_MDSFT_RENDERMODE, 29, flagWord | self.getGBL_c(f3d), f3d
            )
        else:
            return gsSPSetOtherMode(f3d.G_SETOTHERMODE_L, f3d.G_MDSFT_RENDERMODE, 29, flagWord, f3d)

    def to_c(self, static=True):
        data = "gsDPSetRenderMode(" if static else "gDPSetRenderMode(glistp++, "

        if not self.use_preset:
            data += (
                "GBL_c1("
                + self.bl00
                + ", "
                + self.bl01
                + ", "
                + self.bl02
                + ", "
                + self.bl03
                + ") | GBL_c2("
                + self.bl10
                + ", "
                + self.bl11
                + ", "
                + self.bl12
                + ", "
                + self.bl13
                + "), "
            )
            for name in self.flagList:
                data += name + " | "
            return data[:-3] + ")"
        else:
            if len(self.flagList) != 2:
                raise PluginError("For a rendermode preset, only two fields should be used.")
            data += self.flagList[0] + ", " + self.flagList[1] + ")"
            return data


def gsSetImage(cmd, fmt, siz, width, i):
    words = _SHIFTL(cmd, 24, 8) | _SHIFTL(fmt, 21, 3) | _SHIFTL(siz, 19, 2) | _SHIFTL((width) - 1, 0, 12), i
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


# DPSetColorImage
# DPSetDepthImage


@dataclass(unsafe_hash=True)
class DPSetTextureImage(GbiMacro):
    fmt: str
    siz: str
    width: int
    image: FImage
    _segptrs = True  # calls segmented_to_virtual on name when needed

    def to_binary(self, f3d, segments):
        fmt = f3d.G_IM_FMT_VARS[self.fmt]
        siz = f3d.G_IM_SIZ_VARS[self.siz]
        imagePtr = int.from_bytes(encodeSegmentedAddr(self.image.startAddress, segments), "big")
        return gsSetImage(f3d.G_SETTIMG, fmt, siz, self.width, imagePtr)


def gsDPSetCombine(muxs0, muxs1, f3d):
    words = _SHIFTL(f3d.G_SETCOMBINE, 24, 8) | _SHIFTL(muxs0, 0, 24), muxs1
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def GCCc0w0(saRGB0, mRGB0, saA0, mA0):
    return _SHIFTL((saRGB0), 20, 4) | _SHIFTL((mRGB0), 15, 5) | _SHIFTL((saA0), 12, 3) | _SHIFTL((mA0), 9, 3)


def GCCc1w0(saRGB1, mRGB1):
    return _SHIFTL((saRGB1), 5, 4) | _SHIFTL((mRGB1), 0, 5)


def GCCc0w1(sbRGB0, aRGB0, sbA0, aA0):
    return _SHIFTL((sbRGB0), 28, 4) | _SHIFTL((aRGB0), 15, 3) | _SHIFTL((sbA0), 12, 3) | _SHIFTL((aA0), 9, 3)


def GCCc1w1(sbRGB1, saA1, mA1, aRGB1, sbA1, aA1):
    return (
        _SHIFTL((sbRGB1), 24, 4)
        | _SHIFTL((saA1), 21, 3)
        | _SHIFTL((mA1), 18, 3)
        | _SHIFTL((aRGB1), 6, 3)
        | _SHIFTL((sbA1), 3, 3)
        | _SHIFTL((aA1), 0, 3)
    )


@dataclass(unsafe_hash=True)
class DPSetCombineMode(GbiMacro):
    # all strings
    a0: str
    b0: str
    c0: str
    d0: str
    Aa0: str
    Ab0: str
    Ac0: str
    Ad0: str

    a1: str
    b1: str
    c1: str
    d1: str
    Aa1: str
    Ab1: str
    Ac1: str
    Ad1: str

    def to_binary(self, f3d, segments):
        words = _SHIFTL(f3d.G_SETCOMBINE, 24, 8) | _SHIFTL(
            GCCc0w0(CCMUXDict[self.a0], CCMUXDict[self.c0], ACMUXDict[self.Aa0], ACMUXDict[self.Ac0])
            | GCCc1w0(CCMUXDict[self.a1], CCMUXDict[self.c1]),
            0,
            24,
        ), GCCc0w1(CCMUXDict[self.b0], CCMUXDict[self.d0], ACMUXDict[self.Ab0], ACMUXDict[self.Ad0]) | GCCc1w1(
            CCMUXDict[self.b1],
            ACMUXDict[self.Aa1],
            ACMUXDict[self.Ac1],
            CCMUXDict[self.d1],
            ACMUXDict[self.Ab1],
            ACMUXDict[self.Ad1],
        )
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")

    def to_c(self, static=True):
        if static:
            return f"gsDPSetCombineLERP({', '.join( self.getargs(static) )})"
        else:
            return f"gDPSetCombineLERP(glistp++, {', '.join( self.getargs(static) )})"


def gsDPSetColor(c, d):
    words = _SHIFTL(c, 24, 8), d
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def sDPRGBColor(cmd, r, g, b, a):
    return gsDPSetColor(cmd, (_SHIFTL(r, 24, 8) | _SHIFTL(g, 16, 8) | _SHIFTL(b, 8, 8) | _SHIFTL(a, 0, 8)))


@dataclass(unsafe_hash=True)
class DPSetEnvColor(GbiMacro):
    r: int
    g: int
    b: int
    a: int

    def to_binary(self, f3d, segments):
        return sDPRGBColor(f3d.G_SETENVCOLOR, self.r, self.g, self.b, self.a)


@dataclass(unsafe_hash=True)
class DPSetBlendColor(GbiMacro):
    r: int
    g: int
    b: int
    a: int

    def to_binary(self, f3d, segments):
        return sDPRGBColor(f3d.G_SETBLENDCOLOR, self.r, self.g, self.b, self.a)


@dataclass(unsafe_hash=True)
class DPSetFogColor(GbiMacro):
    r: int
    g: int
    b: int
    a: int

    def to_binary(self, f3d, segments):
        return sDPRGBColor(f3d.G_SETFOGCOLOR, self.r, self.g, self.b, self.a)


@dataclass(unsafe_hash=True)
class DPSetFillColor(GbiMacro):
    d: int

    def to_binary(self, f3d, segments):
        return gsDPSetColor(f3d.G_SETFILLCOLOR, self.d)


@dataclass(unsafe_hash=True)
class DPSetPrimDepth(GbiMacro):
    z: int = 0
    dz: int = 0

    def to_binary(self, f3d, segments):
        return gsDPSetColor(f3d.G_SETPRIMDEPTH, _SHIFTL(self.z, 16, 16) | _SHIFTL(self.dz, 0, 16))


@dataclass(unsafe_hash=True)
class DPSetPrimColor(GbiMacro):
    m: int
    l: int
    r: int
    g: int
    b: int
    a: int

    def to_binary(self, f3d, segments):
        words = (_SHIFTL(f3d.G_SETPRIMCOLOR, 24, 8) | _SHIFTL(self.m, 8, 8) | _SHIFTL(self.l, 0, 8)), (
            _SHIFTL(self.r, 24, 8) | _SHIFTL(self.g, 16, 8) | _SHIFTL(self.b, 8, 8) | _SHIFTL(self.a, 0, 8)
        )
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPLightToRDP(GbiMacro):
    light: int
    alpha: int
    word0: int  # word0 of the command to write, which is word1 of this command

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPLightToRDP requires F3DEX3 microcode")
        word = _SHIFTL(f3d.G_LIGHTTORDP, 24, 8) | _SHIFTL(self.light * 0x10, 8, 8) | _SHIFTL(self.alpha, 0, 8)
        return word.to_bytes(4, "big") + self.word0.to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class SPLightToPrimColor(GbiMacro):
    light: int
    alpha: int
    m: int
    l: int

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPLightToPrimColor requires F3DEX3 microcode")
        word0 = _SHIFTL(f3d.G_SETPRIMCOLOR, 24, 8) | _SHIFTL(self.m, 8, 8) | _SHIFTL(self.l, 0, 8)
        return SPLightToRDP(self.light, self.alpha, word0).to_binary(f3d, segments)


@dataclass(unsafe_hash=True)
class SPLightToFogColor(GbiMacro):
    light: int
    alpha: int

    def to_binary(self, f3d, segments):
        if not f3d.F3DEX_GBI_3:
            raise PluginError("SPLightToFogColor requires F3DEX3 microcode")
        word0 = _SHIFTL(f3d.G_SETFOGCOLOR, 24, 8)
        return SPLightToRDP(self.light, self.alpha, word0).to_binary(f3d, segments)


@dataclass(unsafe_hash=True)
class DPSetOtherMode(GbiMacro):
    mode0: list
    mode1: list

    def to_binary(self, f3d, segments):
        mode0 = mode1 = 0
        for mode in self.mode0:
            mode0 |= getattr(f3d, str(mode), mode)
        for mode in self.mode1:
            mode1 |= getattr(f3d, str(mode), mode)
        words = _SHIFTL(f3d.G_RDPSETOTHERMODE, 24, 8) | _SHIFTL(mode0, 0, 24), mode1
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsDPLoadTileGeneric(c, tile, uls, ult, lrs, lrt):
    words = _SHIFTL(c, 24, 8) | _SHIFTL(uls, 12, 12) | _SHIFTL(ult, 0, 12), _SHIFTL(tile, 24, 3) | _SHIFTL(
        lrs, 12, 12
    ) | _SHIFTL(lrt, 0, 12)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class DPSetTileSize(GbiMacro):
    tile: int
    uls: int
    ult: int
    lrs: int
    lrt: int

    def to_binary(self, f3d, segments):
        return gsDPLoadTileGeneric(f3d.G_SETTILESIZE, self.tile, self.uls, self.ult, self.lrs, self.lrt)

    def is_LOADTILE(self, f3d):
        return self.tile == f3d.G_TX_LOADTILE


@dataclass(unsafe_hash=True)
class DPLoadTile(GbiMacro):
    tile: int
    uls: int
    ult: int
    lrs: int
    lrt: int

    def to_binary(self, f3d, segments):
        return gsDPLoadTileGeneric(f3d.G_LOADTILE, self.tile, self.uls, self.ult, self.lrs, self.lrt)


@dataclass(unsafe_hash=True)
class DPSetTile(GbiMacro):
    fmt: str
    siz: str
    line: int
    tmem: int
    tile: int
    palette: int
    cmt: list
    maskt: int
    shiftt: int
    cms: list
    masks: int
    shifts: int

    def to_binary(self, f3d, segments):
        cms = f3d.G_TX_VARS[self.cms[0]] + f3d.G_TX_VARS[self.cms[1]]
        cmt = f3d.G_TX_VARS[self.cmt[0]] + f3d.G_TX_VARS[self.cmt[1]]

        words = (
            _SHIFTL(f3d.G_SETTILE, 24, 8)
            | _SHIFTL(f3d.G_IM_FMT_VARS[self.fmt], 21, 3)
            | _SHIFTL(f3d.G_IM_SIZ_VARS[self.siz], 19, 2)
            | _SHIFTL(self.line, 9, 9)
            | _SHIFTL(self.tmem, 0, 9)
        ), (
            _SHIFTL(self.tile, 24, 3)
            | _SHIFTL(self.palette, 20, 4)
            | _SHIFTL(cmt, 18, 2)
            | _SHIFTL(self.maskt, 14, 4)
            | _SHIFTL(self.shiftt, 10, 4)
            | _SHIFTL(cms, 8, 2)
            | _SHIFTL(self.masks, 4, 4)
            | _SHIFTL(self.shifts, 0, 4)
        )
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")

    def is_LOADTILE(self, f3d):
        return self.tile == f3d.G_TX_LOADTILE


@dataclass(unsafe_hash=True)
class DPLoadBlock(GbiMacro):
    tile: int
    uls: int
    ult: int
    lrs: int
    dxt: int

    def to_binary(self, f3d, segments):
        words = (_SHIFTL(f3d.G_LOADBLOCK, 24, 8) | _SHIFTL(self.uls, 12, 12) | _SHIFTL(self.ult, 0, 12)), (
            _SHIFTL(self.tile, 24, 3)
            | _SHIFTL((min(self.lrs, f3d.G_TX_LDBLK_MAX_TXL)), 12, 12)
            | _SHIFTL(self.dxt, 0, 12)
        )
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class DPLoadTLUTCmd(GbiMacro):
    tile: int
    count: int

    def to_binary(self, f3d, segments):
        words = _SHIFTL(f3d.G_LOADTLUT, 24, 8), _SHIFTL((self.tile), 24, 3) | _SHIFTL((self.count), 14, 10)
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class DPLoadTextureBlock(GbiMacro):
    timg: FImage
    fmt: str
    siz: str
    width: int
    height: int
    pal: int
    cms: list
    cmt: list
    masks: int
    maskt: int
    shifts: int
    shiftt: int
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage(self.fmt, self.siz + "_LOAD_BLOCK", 1, self.timg).to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz + "_LOAD_BLOCK",
                0,
                0,
                f3d.G_TX_LOADTILE,
                0,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadBlock(
                f3d.G_TX_LOADTILE,
                0,
                0,
                (
                    ((self.width) * (self.height) + f3d.G_IM_SIZ_VARS[self.siz + "_INCR"])
                    >> f3d.G_IM_SIZ_VARS[self.siz + "_SHIFT"]
                )
                - 1,
                f3d.CALC_DXT(self.width, f3d.G_IM_SIZ_VARS[self.siz + "_BYTES"]),
            ).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz,
                ((((self.width) * f3d.G_IM_SIZ_VARS[self.siz + "_LINE_BYTES"]) + 7) >> 3),
                0,
                f3d.G_TX_RENDERTILE,
                self.pal,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPSetTileSize(
                f3d.G_TX_RENDERTILE,
                0,
                0,
                ((self.width) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
                ((self.height) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 7


@dataclass(unsafe_hash=True)
class DPLoadTextureBlockYuv(GbiMacro):
    timg: FImage
    fmt: str
    siz: str
    width: int
    height: int
    pal: int
    cms: list
    cmt: list
    masks: int
    maskt: int
    shifts: int
    shiftt: int
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage(self.fmt, self.siz + "_LOAD_BLOCK", 1, self.timg).to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz + "_LOAD_BLOCK",
                0,
                0,
                f3d.G_TX_LOADTILE,
                0,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadBlock(
                f3d.G_TX_LOADTILE,
                0,
                0,
                (
                    ((self.width) * (self.height) + f3d.G_IM_SIZ_VARS[self.siz + "_INCR"])
                    >> f3d.G_IM_SIZ_VARS[self.siz + "_SHIFT"]
                )
                - 1,
                f3d.CALC_DXT(self.width, f3d.G_IM_SIZ_VARS[self.siz + "_BYTES"]),
            ).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz,
                ((((self.width) * 1) + 7) >> 3),
                0,
                f3d.G_TX_RENDERTILE,
                self.pal,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPSetTileSize(
                f3d.G_TX_RENDERTILE,
                0,
                0,
                ((self.width) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
                ((self.height) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 7


# gsDPLoadTextureBlockS
# gsDPLoadMultiBlockS
# gsDPLoadTextureBlockYuvS


@dataclass(unsafe_hash=True)
class _DPLoadTextureBlock(GbiMacro):
    timg: FImage
    tmem: int
    fmt: str
    siz: str
    width: int
    height: int
    pal: int
    cms: list
    cmt: list
    masks: int
    maskt: int
    shifts: int
    shiftt: int
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage(self.fmt, self.siz + "_LOAD_BLOCK", 1, self.timg).to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz + "_LOAD_BLOCK",
                0,
                self.tmem,
                f3d.G_TX_LOADTILE,
                0,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadBlock(
                f3d.G_TX_LOADTILE,
                0,
                0,
                (
                    ((self.width) * (self.height) + f3d.G_IM_SIZ_VARS[self.siz + "_INCR"])
                    >> f3d.G_IM_SIZ_VARS[self.siz + "_SHIFT"]
                )
                - 1,
                f3d.CALC_DXT(self.width, f3d.G_IM_SIZ_VARS[self.siz + "_BYTES"]),
            ).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz,
                ((((self.width) * f3d.G_IM_SIZ_VARS[self.siz + "_LINE_BYTES"]) + 7) >> 3),
                self.tmem,
                f3d.G_TX_RENDERTILE,
                self.pal,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPSetTileSize(
                f3d.G_TX_RENDERTILE,
                0,
                0,
                ((self.width) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
                ((self.height) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 7


# _gsDPLoadTextureBlockTile
# gsDPLoadMultiBlock
# gsDPLoadMultiBlockS


@dataclass(unsafe_hash=True)
class DPLoadTextureBlock_4b(GbiMacro):
    timg: FImage
    fmt: str
    siz: str
    width: int
    height: int
    pal: int
    cms: list
    cmt: list
    masks: int
    maskt: int
    shifts: int
    shiftt: int
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage(self.fmt, "G_IM_SIZ_16b", 1, self.timg).to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                "G_IM_SIZ_16b",
                0,
                0,
                f3d.G_TX_LOADTILE,
                0,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadBlock(
                f3d.G_TX_LOADTILE, 0, 0, (((self.width) * (self.height) + 3) >> 2) - 1, f3d.CALC_DXT_4b(self.width)
            ).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                "G_IM_SIZ_4b",
                (((self.width >> 1) + 7) >> 3),
                0,
                f3d.G_TX_RENDERTILE,
                self.pal,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPSetTileSize(
                f3d.G_TX_RENDERTILE,
                0,
                0,
                ((self.width) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
                ((self.height) - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 7


# gsDPLoadTextureBlock_4bS
# gsDPLoadMultiBlock_4b
# gsDPLoadMultiBlock_4bS
# _gsDPLoadTextureBlock_4b


@dataclass(unsafe_hash=True)
class DPLoadTextureTile(GbiMacro):
    timg: FImage
    fmt: str
    siz: str
    width: int
    height: int
    uls: int
    ult: int
    lrs: int
    lrt: int
    pal: int
    cms: list
    cmt: list
    masks: int
    maskt: int
    shifts: int
    shiftt: int
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage(self.fmt, self.siz, self.width, self.timg).to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz,
                (((self.lrs - self.uls + 1) * f3d.G_IM_SIZ_VARS[self.siz + "_TILE_BYTES"] + 7) >> 3),
                0,
                f3d.G_TX_LOADTILE,
                0,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadTile(
                f3d.G_TX_LOADTILE,
                (self.uls) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.ult) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.lrs) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.lrt) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                self.siz,
                ((((self.lrs - self.uls + 1) * f3d.G_IM_SIZ_VARS[self.siz + "_LINE_BYTES"]) + 7) >> 3),
                0,
                f3d.G_TX_RENDERTILE,
                self.pal,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPSetTileSize(
                f3d.G_TX_RENDERTILE,
                (self.uls) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.ult) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.lrs) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.lrt) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 7


# gsDPLoadMultiTile


@dataclass(unsafe_hash=True)
class DPLoadTextureTile_4b(GbiMacro):
    timg: FImage
    fmt: str
    siz: str
    width: int
    height: int
    uls: int
    ult: int
    lrs: int
    lrt: int
    pal: int
    cms: list
    cmt: list
    masks: int
    maskt: int
    shifts: int
    shiftt: int
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage(self.fmt, "G_IM_SIZ_8b", self.width >> 1, self.timg).to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                "G_IM_SIZ_8b",
                ((((self.lrs - self.uls + 1) >> 1) + 7) >> 3),
                0,
                f3d.G_TX_LOADTILE,
                0,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadTile(
                f3d.G_TX_LOADTILE,
                (self.uls) << (f3d.G_TEXTURE_IMAGE_FRAC - 1),
                (self.ult) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.lrs) << (f3d.G_TEXTURE_IMAGE_FRAC - 1),
                (self.lrt) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
            + DPSetTile(
                self.fmt,
                "G_IM_SIZ_4b",
                ((((self.lrs - self.uls + 1) >> 1) + 7) >> 3),
                0,
                f3d.G_TX_RENDERTILE,
                self.pal,
                self.cmt,
                self.maskt,
                self.shiftt,
                self.cms,
                self.masks,
                self.shifts,
            ).to_binary(f3d, segments)
            + DPSetTileSize(
                f3d.G_TX_RENDERTILE,
                (self.uls) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.ult) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.lrs) << f3d.G_TEXTURE_IMAGE_FRAC,
                (self.lrt) << f3d.G_TEXTURE_IMAGE_FRAC,
            ).to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 7


# gsDPLoadMultiTile_4b


@dataclass(unsafe_hash=True)
class DPLoadTLUT_pal16(GbiMacro):
    pal: int
    dram: FImage  # pallete object
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage("G_IM_FMT_RGBA", "G_IM_SIZ_16b", 1, self.dram).to_binary(f3d, segments)
            + DPTileSync().to_binary(f3d, segments)
            + DPSetTile(
                "0", "0", 0, (256 + (((self.pal) & 0xF) * 16)), f3d.G_TX_LOADTILE, 0, 0, 0, 0, 0, 0, 0
            ).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadTLUTCmd(f3d.G_TX_LOADTILE, 15).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 6


@dataclass(unsafe_hash=True)
class DPLoadTLUT_pal256(GbiMacro):
    dram: FImage  # pallete object
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage("G_IM_FMT_RGBA", "G_IM_SIZ_16b", 1, self.dram).to_binary(f3d, segments)
            + DPTileSync().to_binary(f3d, segments)
            + DPSetTile("0", "0", 0, 256, f3d.G_TX_LOADTILE, 0, 0, 0, 0, 0, 0, 0).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadTLUTCmd(f3d.G_TX_LOADTILE, 255).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 6


@dataclass(unsafe_hash=True)
class DPLoadTLUT(GbiMacro):
    count: int
    tmemaddr: int
    dram: FImage  # pallete object
    _ptr_amp = True  # adds & to name of image

    def to_binary(self, f3d, segments):
        return (
            DPSetTextureImage("G_IM_FMT_RGBA", "G_IM_SIZ_16b", 1, self.dram).to_binary(f3d, segments)
            + DPTileSync().to_binary(f3d, segments)
            + DPSetTile("0", "0", 0, self.tmemaddr, f3d.G_TX_LOADTILE, 0, 0, 0, 0, 0, 0, 0).to_binary(f3d, segments)
            + DPLoadSync().to_binary(f3d, segments)
            + DPLoadTLUTCmd(f3d.G_TX_LOADTILE, self.count - 1).to_binary(f3d, segments)
            + DPPipeSync().to_binary(f3d, segments)
        )

    def size(self, f3d):
        return GFX_SIZE * 6


# gsDPSetScissor
# gsDPSetScissorFrac

# gsDPFillRectangle


@dataclass(unsafe_hash=True)
class DPSetConvert(GbiMacro):
    k0: int
    k1: int
    k2: int
    k3: int
    k4: int
    k5: int

    def to_binary(self, f3d, segments):
        words = (
            _SHIFTL(f3d.G_SETCONVERT, 24, 8) | _SHIFTL(self.k0, 13, 9) | _SHIFTL(self.k1, 4, 9) | _SHIFTL(self.k2, 5, 4)
        ), (_SHIFTL(self.k2, 27, 5) | _SHIFTL(self.k3, 18, 9) | _SHIFTL(self.k4, 9, 9) | _SHIFTL(self.k5, 0, 9))
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class DPSetKeyR(GbiMacro):
    cR: int
    sR: int
    wR: int

    def to_binary(self, f3d, segments):
        words = _SHIFTL(f3d.G_SETKEYR, 24, 8), _SHIFTL(self.wR, 16, 12) | _SHIFTL(self.cR, 8, 8) | _SHIFTL(
            self.sR, 0, 8
        )
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


@dataclass(unsafe_hash=True)
class DPSetKeyGB(GbiMacro):
    cG: int
    sG: int
    wG: int
    cB: int
    sB: int
    wB: int

    def to_binary(self, f3d, segments):
        words = (_SHIFTL(f3d.G_SETKEYGB, 24, 8) | _SHIFTL(self.wG, 12, 12) | _SHIFTL(self.wB, 0, 12)), (
            _SHIFTL(self.cG, 24, 8) | _SHIFTL(self.sG, 16, 8) | _SHIFTL(self.cB, 8, 8) | _SHIFTL(self.sB, 0, 8)
        )
        return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsDPNoParam(cmd):
    words = _SHIFTL(cmd, 24, 8), 0
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


def gsDPParam(cmd, param):
    words = _SHIFTL(cmd, 24, 8), (param)
    return words[0].to_bytes(4, "big") + words[1].to_bytes(4, "big")


# gsDPTextureRectangle
# gsDPTextureRectangleFlip


@dataclass(unsafe_hash=True)
class SPTextureRectangle(GbiMacro):
    xl: int
    yl: int
    xh: int
    yh: int
    tile: int
    s: int
    t: int
    dsdx: int = 4 << 10
    dtdy: int = 1 << 10

    def to_binary(self, f3d, segments):
        words = (
            (_SHIFTL(f3d.G_TEXRECT, 24, 8) | _SHIFTL(self.xh, 12, 12) | _SHIFTL(self.yh, 0, 12)),
            (_SHIFTL(self.tile, 24, 3) | _SHIFTL(self.xl, 12, 12) | _SHIFTL(self.yl, 0, 12)),
            gsImmp1(f3d.G_RDPHALF_1, (_SHIFTL(self.s, 16, 16) | _SHIFTL(self.t, 0, 16))),
            gsImmp1(f3d.G_RDPHALF_2, (_SHIFTL(self.dsdx, 16, 16) | _SHIFTL(self.dtdy, 0, 16))),
        )

        return (
            words[0].to_bytes(4, "big")
            + words[1].to_bytes(4, "big")
            + words[2].to_bytes(4, "big")
            + words[3].to_bytes(4, "big")
        )

    def size(self, f3d):
        return GFX_SIZE * 2


@dataclass(unsafe_hash=True)
class SPScisTextureRectangle(GbiMacro):
    xl: int
    yl: int
    xh: int
    yh: int
    tile: int
    s: int
    t: int
    dsdx: int = 4 << 10
    dtdy: int = 1 << 10

    def to_binary(self, f3d, segments):
        raise PluginError("SPScisTextureRectangle not implemented for binary.")

    def size(self, f3d):
        return GFX_SIZE * 2


# gsSPTextureRectangleFlip
# gsDPWord


@dataclass(unsafe_hash=True)
class DPFullSync(GbiMacro):
    def to_binary(self, f3d, segments):
        return gsDPNoParam(f3d.G_RDPFULLSYNC)


@dataclass(unsafe_hash=True)
class DPTileSync(GbiMacro):
    def to_binary(self, f3d, segments):
        return gsDPNoParam(f3d.G_RDPTILESYNC)


@dataclass(unsafe_hash=True)
class DPPipeSync(GbiMacro):
    def to_binary(self, f3d, segments):
        return gsDPNoParam(f3d.G_RDPPIPESYNC)


@dataclass(unsafe_hash=True)
class DPLoadSync(GbiMacro):
    def to_binary(self, f3d, segments):
        return gsDPNoParam(f3d.G_RDPLOADSYNC)


F3DClassesWithPointers = [
    SPVertex,
    SPDisplayList,
    SPViewport,
    SPBranchList,
    SPLight,
    SPSetLights,
    SPLookAt,
    DPSetTextureImage,
    DPLoadTextureBlock,
    DPLoadTextureBlockYuv,
    _DPLoadTextureBlock,
    DPLoadTextureBlock_4b,
    DPLoadTextureTile,
    DPLoadTextureTile_4b,
    DPLoadTLUT_pal16,
    DPLoadTLUT_pal256,
    DPLoadTLUT,
]
