from ..utility import PluginError


drawLayers = {"Unused": [0, 3], "Solid": 1, "Decal": 2, "AlphaTest": 4, "Blend": 5, "BlendBehind": 6}

GEO_BRANCH_STORE = 0x00
GEO_END = 0x01
GEO_BRANCH = 0x02
GEO_RETURN = 0x03
GEO_NODE_OPEN = 0x04
GEO_NODE_CLOSE = 0x05
GEO_SET_RENDER_AREA = 0x08
GEO_SET_ORTHO = 0x09
GEO_SET_CAMERA_FRUSTRUM = 0x0A
GEO_START = 0x0B
GEO_SET_Z_BUF = 0x0C
GEO_SET_RENDER_RANGE = 0x0D
GEO_SWITCH = 0x0E
GEO_CAMERA = 0x0F
GEO_TRANSLATE_ROTATE = 0x10
GEO_TRANSLATE = 0x11
GEO_ROTATE = 0x12
GEO_LOAD_DL_W_OFFSET = 0x13
GEO_BILLBOARD = 0x14
GEO_LOAD_DL = 0x15
GEO_START_W_SHADOW = 0x16
GEO_SETUP_OBJ_RENDER = 0x17
GEO_CALL_ASM = 0x18
GEO_SET_BG = 0x19
GEO_HELD_OBJECT = 0x1C
GEO_NOP = [0x1A, 0x1E, 0x1F]
GEO_SCALE = 0x1D
GEO_START_W_RENDERAREA = 0x20

startCommands = [GEO_START, GEO_START_W_SHADOW, GEO_START_W_RENDERAREA]

nodeGroupCmds = [
    GEO_START,
    GEO_SWITCH,
    GEO_TRANSLATE_ROTATE,
    GEO_TRANSLATE,
    GEO_ROTATE,
    GEO_LOAD_DL_W_OFFSET,
    GEO_BILLBOARD,
    GEO_START_W_SHADOW,
    GEO_SCALE,
    GEO_START_W_RENDERAREA,
]

nodeDeformCmds = [
    GEO_TRANSLATE_ROTATE,
    GEO_TRANSLATE,
    GEO_ROTATE,
    GEO_LOAD_DL_W_OFFSET,
    GEO_BILLBOARD,
    GEO_LOAD_DL,
    GEO_SCALE,
]

nodeDeformCmdsBoneGroups = ["TranslateRotate", "Translate", "Rotate", "Billboard", "DisplayList", "Scale"]

nodeCmds = [
    GEO_NODE_OPEN,
    # GEO_START,
    # GEO_START_W_SHADOW,
    # GEO_START_W_RENDERAREA,
    GEO_LOAD_DL,
    GEO_LOAD_DL_W_OFFSET,
    GEO_BRANCH,
    # GEO_SWITCH,
    # GEO_SCALE,
    # GEO_TRANSLATE_ROTATE
]

geoCmdStatic = {
    0x04: [0x01, 0x03, 0x04, 0x05, 0x09, 0x0B, 0x0C, 0x17, 0x20],
    0x08: [0x00, 0x02, 0x0D, 0x0E, 0x12, 0x14, 0x15, 0x16, 0x18, 0x19],
    0x0C: [0x08, 0x13, 0x1C],
    0x14: [0x0F],
}


def getGeoLayoutCmdLength(byte0, byte1):
    for length, cmdList in geoCmdStatic.items():
        if byte0 in cmdList:
            return length

    # handle variable length
    if byte0 in [0x0A]:
        return 0x08 if byte1 == 0 else 0x0C
    else:
        raise PluginError("Unhandled geolayout command: " + hex(byte0))
