import copy
from .sm64_constants import mainLevelLoadScriptSegment, loadSegmentAddresses

from ..utility import (
    PluginError,
    decodeSegmentedAddr,
    writeVectorToShorts,
    writeFloatToShort,
    readVectorFromShorts,
    readEulerVectorFromShorts,
    writeEulerVectorToShorts,
    readFloatFromShort,
    readEulerFloatFromShort,
    writeEulerFloatToShort,
)

from .sm64_level_constants import (
    L_END,
    L_JUMP,
    L_PUSH,
    L_POP,
    L_NOOP,
    L_LOAD_ROM_SEG,
    L_LOAD_MIO0_SEG,
    L_LOAD_MIO0_TEX,
    L_AREA_START,
    L_AREA_END,
    L_LOAD_POLY_WO_GEO,
    L_LOAD_POLY_W_GEO,
    L_PLACE_OBJECT,
    L_WARP_CONNECT,
    L_WARP_PAINTING,
    L_WARP_AREA,
    L_SET_DEFAULT_MARIO_POS,
    L_LOAD_COLLISION,
    L_SHOW_DIALOG,
    L_SET_DEFAULT_TERRAIN,
    L_NOOP2,
    L_SET_MUSIC_SCREEN,
    L_SET_MUSIC_LEVEL,
    L_PLACE_MACRO_OBJECT,
    L_JET_STREAM,
)


def parseLevelAtPointer(romfile, pointerAddress):
    segmentData = parseCommonSegmentLoad(romfile)

    romfile.seek(pointerAddress)
    command = romfile.read(16)
    segment = command[3]
    segmentStart = int.from_bytes(command[4:8], "big")
    segmentEnd = int.from_bytes(command[8:12], "big")

    segmentData[segment] = (segmentStart, segmentEnd)

    startAddress = decodeSegmentedAddr(command[12:16], segmentData)

    parsedLevel = parseLevel(romfile, startAddress, segmentData)
    for segment, interval in parsedLevel.segmentData.items():
        print("Segment " + format(segment, "#04x") + ": " + hex(interval[0]) + " - " + hex(interval[1]))

    return parsedLevel


def parseCommonSegmentLoad(romfile):
    segmentData = copy.deepcopy(mainLevelLoadScriptSegment)
    for segment, pointer in loadSegmentAddresses.items():
        romfile.seek(pointer)
        command = romfile.read(12)

        segment = command[3]
        segmentStart = int.from_bytes(command[4:8], "big")
        segmentEnd = int.from_bytes(command[8:12], "big")

        segmentData[segment] = (segmentStart, segmentEnd)

    return segmentData


# second byte = command length
def parseLevel(romfile, startAddress, segmentData):
    currentAddress = startAddress

    romfile.seek(currentAddress)
    currentCmd = romfile.read(2)
    romfile.seek(currentAddress)  # second seek is because reading moves read pointer forward
    currentCmd = romfile.read(currentCmd[1])
    # currentAddress += currentCmd[1]

    scriptStack = [currentAddress]
    currentLevel = SM64_Level()
    currentLevel.segmentData = segmentData
    currentArea = currentLevel.nonArea

    # Note that this is only applicable for specific levels,
    # accessed through a jump table in the main level script.
    while len(scriptStack) > 0 and currentCmd[0] is not L_END:
        # print(bytesToHex(currentCmd) + " at " + hex(currentAddress))

        if currentCmd[0] == L_JUMP:
            currentAddress = decodeSegmentedAddr(currentCmd[4:8], segmentData)

        elif currentCmd[0] == L_PUSH:
            scriptStack.append(currentAddress)
            # print([hex(value) for value in scriptStack])
            currentAddress = decodeSegmentedAddr(currentCmd[4:8], segmentData)

        elif currentCmd[0] == L_POP:
            currentAddress = scriptStack.pop()
            romfile.seek(currentAddress)
            currentCmd = romfile.read(2)
            romfile.seek(currentAddress)
            currentCmd = romfile.read(currentCmd[1])
            currentAddress += currentCmd[1]
            # print([hex(value) for value in scriptStack])

        elif currentCmd[0] == L_NOOP or currentCmd[0] == L_NOOP2:
            pass

        elif currentCmd[0] == L_LOAD_ROM_SEG or currentCmd[0] == L_LOAD_MIO0_SEG or currentCmd[0] == L_LOAD_MIO0_TEX:
            segmentData[currentCmd[3]] = [
                int.from_bytes(currentCmd[4:8], "big"),
                int.from_bytes(currentCmd[8:12], "big"),
            ]

        elif currentCmd[0] == L_AREA_START:
            if currentArea is not currentLevel.nonArea:
                raise PluginError("Nested areas not supported.")
            else:
                currentArea = SM64_Area(currentAddress, currentCmd)

        elif currentCmd[0] == L_AREA_END:
            currentLevel.areas.append(currentArea)
            currentArea = currentLevel.nonArea

        elif currentCmd[0] == L_LOAD_POLY_W_GEO or currentCmd[0] == L_LOAD_POLY_WO_GEO:
            polygonData = SM64_Geometry(currentCmd, currentAddress)
            currentLevel.geometry.append(polygonData)

        elif currentCmd[0] == L_PLACE_OBJECT:
            newObj = SM64_Object(currentCmd, currentAddress)
            currentArea.objects.append(newObj)

        elif currentCmd[0] == L_WARP_CONNECT or currentCmd[0] == L_WARP_PAINTING:
            warp = SM64_Warp(currentCmd, currentAddress)
            currentArea.warps.append(warp)

        elif currentCmd[0] == L_WARP_AREA:
            areaWarp = SM64_Area_Warp(currentCmd, currentAddress)
            currentArea.areaWarps.append(areaWarp)

        elif currentCmd[0] == L_SET_DEFAULT_MARIO_POS:
            marioPos = SM64_MarioStart(currentCmd, currentAddress)
            currentLevel.marioStartPosition = marioPos

        elif currentCmd[0] == L_LOAD_COLLISION:
            col = SM64_Collider(currentCmd, currentAddress)
            currentArea.collider = col

        elif currentCmd[0] == L_SHOW_DIALOG:
            dialog = SM64_Dialog_ID(currentCmd, currentAddress)
            currentArea.startDialogID = dialog

        elif currentCmd[0] == L_SET_DEFAULT_TERRAIN:
            terrain = SM64_Default_Terrain(currentCmd, currentAddress)
            currentArea.defaultTerrainType = terrain

        elif currentCmd[0] == L_SET_MUSIC_LEVEL:
            music = SM64_Music_Level(currentCmd, currentAddress)
            currentArea.music = music

        elif currentCmd[0] == L_PLACE_MACRO_OBJECT:
            macroObj = SM64_Macro_Object(currentCmd, currentAddress)
            currentArea.macroObjects.append(macroObj)

        elif currentCmd[0] == L_JET_STREAM:
            jetStream = SM64_Jet_Stream(currentCmd, currentAddress)
            currentArea.jetStreams.append(jetStream)

        else:
            print("Unhandled command: " + hex(currentCmd[0]))

        if currentCmd[0] != L_PUSH and currentCmd[0] != L_JUMP and currentCmd[0] != L_POP:
            currentAddress += currentCmd[1]
        romfile.seek(currentAddress)
        currentCmd = romfile.read(2)
        romfile.seek(currentAddress)
        currentCmd = romfile.read(currentCmd[1])
        # currentAddress += currentCmd[1]

    return currentLevel


class SM64_Level:
    def __init__(self):
        self.segmentData = {}
        self.geometry = []
        self.areas = []
        self.marioStartPosition = None
        self.nonArea = SM64_Area(0, [0x00, 0x00, 0x00, 0x00])


class SM64_Area:
    def __init__(self, startAddress, command):
        self.objects = []
        self.warps = []
        self.areaWarps = []
        self.collider = None
        self.macroObjects = []
        self.startDialogID = None
        self.music = None
        self.defaultTerrainType = None
        self.marioStart = None
        self.startAddress = startAddress
        self.areaNum = command[2]
        self.geoAddress = command[4:8]
        self.jetStreams = []


class SM64_Music_Screen:
    def __init__(self, command=None, address=None):
        if command is None:
            self.seqNum = None
            self.params = None
        else:
            self.seqNum = command[5]
            self.params = command[2:5]
            self.address = address

    def to_microcode(self):
        command = bytearray(8)
        command[0] = L_SET_MUSIC_SCREEN
        command[1] = 8
        command[2:5] = self.params
        command[5] = self.seqNum

        return command


class SM64_Music_Level:
    def __init__(self, command=None, address=None):
        if command is None:
            self.seqNum = None
        else:
            self.seqNum = command[3]
            self.address = address

    def to_microcode(self):
        command = bytearray(8)
        command[0] = L_SET_MUSIC_LEVEL
        command[1] = 4
        command[3] = self.seqNum

        return command


class SM64_Geometry:
    def __init__(self, command=None, address=None):
        if command is None:
            self.geoCmd = None
            self.drawLayer = None
            self.modelID = None
            self.geoAddress = None
        else:
            self.geoCmd = command[0]
            self.drawLayer = command[2] >> 4
            self.modelID = command[3]
            self.geoAddress = command[4:8]
            self.address = address

            # print('Level geo: ' + hex(int.from_bytes(self.geoAddress, 'big')))

    def to_microcode(self):
        command = bytearray(8)
        command[0] = self.geoCmd
        command[1] = 8
        command[2] = self.drawLayer << 4
        command[3] = self.modelID
        command[4:8] = self.collisionAddress

        return command


class SM64_Collider:
    def __init__(self, command=None, address=None):
        if command is None:
            self.collisionAddress = None
            self.address = None
        else:
            self.collisionAddress = command[4:8]
            self.address = address

    def to_microcode(self):
        command = bytearray(8)
        command[0] = L_LOAD_COLLISION
        command[1] = 8
        command[4:8] = self.collisionAddress

        return command


class SM64_Dialog_ID:
    def __init__(self, command=None, address=None):
        if command is None:
            self.ID = None
            self.address = None
        else:
            self.ID = command[3]
            self.address = address

    def to_microcode(self):
        command = bytearray(8)
        command[0] = L_SHOW_DIALOG
        command[1] = 4
        command[3] = self.ID

        return command


class SM64_Default_Terrain:
    def __init__(self, command=None, address=None):
        if command is None:
            self.terrainType = None
            self.address = None
        else:
            self.terrainType = command[3]
            self.address = address

    def to_microcode(self):
        command = bytearray(8)
        command[0] = L_SET_DEFAULT_TERRAIN
        command[1] = 4
        command[3] = self.terrainType

        return command


class SM64_Object:
    def __init__(self, command=None, address=None):
        if command is None:
            self.mask = None
            self.modelID = None
            self.position = [0, 0, 0]
            self.rotation = [0, 0, 0]
            self.behaviourParams = None
            self.behaviourAddress = None
        else:
            self.mask = command[2]
            self.modelID = command[3]
            self.position = readVectorFromShorts(command, 4)
            self.rotation = readEulerVectorFromShorts(command, 10)
            self.behaviourParams = command[16:20]
            self.behaviourAddress = command[20:24]
            self.address = address

    def to_microcode(self):
        command = bytearray(24)
        command[0] = L_PLACE_OBJECT
        command[1] = 0x18
        command[2] = self.mask
        command[3] = self.modelID
        writeVectorToShorts(command, 4, self.position)
        writeEulerVectorToShorts(command, 10, self.rotation)
        command[16:20] = self.behaviourParams
        command[20:24] = self.behaviourAddress

        return command


class SM64_Macro_Object:
    def __init__(self, command=None, address=None):
        if command is None:
            self.objPlacementListPointer = None
            # self.objectID = None
            # self.position = [0,0,0]
        else:
            self.objPlacementListPointer = command[4:8]
            self.address = address

    def to_microcode(self):
        command = bytearray(8)
        command[0] = L_PLACE_MACRO_OBJECT
        command[1] = 8
        command[4:8] = self.objPlacementListPointer


class SM64_Jet_Stream:
    def __init__(self, command=None, address=None):
        if command is None:
            self.position = None
            self.intensity = 0
        else:
            self.position = readVectorFromShorts(command, 4)
            self.intensity = readFloatFromShort(command, 10)
            self.address = address

    def to_microcode(self, command=None, address=None):
        command = bytearray(12)
        command[0] = L_JET_STREAM
        command[1] = 12
        writeVectorToShorts(command, 4, self.position)
        writeFloatToShort(command, 10, self.intensity)
        self.address = address

        return command


class SM64_Warp:
    def __init__(self, command=None, address=None):
        if command is None:
            self.warpCmd = None
            self.curWarpID = None
            self.destCourseID = None
            self.destCourseArea = None
            self.destWarpID = None
        else:
            self.warpCmd = command[0]
            self.curWarpID = command[2]
            self.destCourseID = command[3]
            self.destCourseArea = command[4]
            self.destWarpID = command[5]
            self.address = address

    def to_microcode(self):
        command = bytearray(8)
        command[0] = self.warpCmd
        command[1] = 8
        command[2] = self.curWarpID
        command[3] = self.destCourseID
        command[4] = self.destCourseArea
        command[5] = self.destWarpID

        return command


class SM64_Area_Warp:
    def __init__(self, command=None, address=None):
        if command is None:
            self.collisionType = None
            self.courseAreaID = None
            self.teleportPosition = [0, 0, 0]
        else:
            self.collisionType = command[2]
            self.courseAreaID = command[3]
            self.teleportPosition = readVectorFromShorts(command, 4)
            self.address = address

    def to_microcode(self):
        command = bytearray(12)
        command[0] = L_WARP_AREA
        command[1] = 12
        command[2] = self.collisionType
        command[3] = self.courseAreaID
        writeVectorToShorts(command, 4, self.teleportPosition)

        return command


class SM64_MarioStart:
    def __init__(self, command=None, address=None):
        if command is None:
            self.areaID = None
            self.position = (0, 0, 0)
            self.yRotation = 0
        else:
            self.areaID = command[2]
            self.yRotation = readEulerFloatFromShort(command, 4)
            self.position = readVectorFromShorts(command, 6)
            self.address = address

    def to_microcode(self):
        command = bytearray(12)
        command[0] = L_SET_DEFAULT_MARIO_POS
        command[1] = 12
        writeEulerFloatToShort(command, 4, self.yRotation)
        writeVectorToShorts(command, 6, self.position)

        return command
