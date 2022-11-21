import bpy, os, math, re, shutil, mathutils
from collections import defaultdict
from bpy.utils import register_class, unregister_class
from ..panels import SM64_Panel
from ..operators import ObjectDataExporter
from .sm64_constants import cameraTriggerNames, levelIDNames, enumLevelNames
from .sm64_objects import exportAreaCommon, backgroundSegments
from .sm64_collision import exportCollisionCommon
from .sm64_f3d_writer import SM64Model, SM64GfxFormatter
from .sm64_geolayout_writer import setRooms, convertObjectToGeolayout
from .sm64_f3d_writer import modifyTexScrollFiles, modifyTexScrollHeadersGroup
from .sm64_utility import cameraWarning, starSelectWarning

from ..utility import (
    PluginError,
    writeIfNotFound,
    getDataFromFile,
    saveDataToFile,
    unhideAllAndGetHiddenList,
    hideObjsInList,
    overwriteData,
    selectSingleObject,
    deleteIfFound,
    applyBasicTweaks,
    applyRotation,
    prop_split,
    toAlnum,
    writeMaterialHeaders,
    raisePluginError,
    customExportWarning,
    decompFolderMessage,
    makeWriteInfoBox,
    writeMaterialFiles,
)

from ..f3d.f3d_gbi import (
    ScrollMethod,
    TextureExportSettings,
    DLFormat,
)


levelDefineArgs = {
    "internal name": 0,
    "level enum": 1,
    "course name": 2,
    "folder name": 3,
    "texture bin": 4,
    "acoustic reach": 5,
    "echo level 1": 6,
    "echo level 2": 7,
    "echo level 3": 8,
    "dynamic music": 9,
    "camera table": 10,
}


def createGeoFile(levelName, filepath):
    result = (
        "#include <ultra64.h>\n"
        + '#include "sm64.h"\n'
        + '#include "geo_commands.h"\n\n'
        + '#include "game/level_geo.h"\n'
        + '#include "game/geo_misc.h"\n'
        + '#include "game/camera.h"\n'
        + '#include "game/moving_texture.h"\n'
        + '#include "game/screen_transition.h"\n'
        + '#include "game/paintings.h"\n\n'
        + '#include "make_const_nonconst.h"\n\n'
        + '#include "levels/'
        + levelName
        + '/header.h"\n\n'
    )

    geoFile = open(filepath, "w", newline="\n")
    geoFile.write(result)
    geoFile.close()


def createLevelDataFile(levelName, filepath):
    result = (
        '#include <ultra64.h>"\n'
        + '#include "sm64.h"\n'
        + '#include "surface_terrains.h"\n'
        + '#include "moving_texture_macros.h"\n'
        + '#include "level_misc_macros.h"\n'
        + '#include "macro_preset_names.h"\n'
        + '#include "special_preset_names.h"\n'
        + '#include "textures.h"\n'
        + '#include "dialog_ids.h"\n\n'
        + '#include "make_const_nonconst.h"\n\n'
    )

    levelDataFile = open(filepath, "w", newline="\n")
    levelDataFile.write(result)
    levelDataFile.close()


def createHeaderFile(levelName, filepath):
    result = (
        "#ifndef "
        + levelName.upper()
        + "_HEADER_H\n"
        + "#define "
        + levelName.upper()
        + "_HEADER_H\n\n"
        + '#include "types.h"\n'
        + '#include "game/moving_texture.h"\n\n'
        + "extern const LevelScript level_"
        + levelName
        + "_entry[];\n\n"
        + "#endif\n"
    )

    headerFile = open(filepath, "w", newline="\n")
    headerFile.write(result)
    headerFile.close()


class ZoomOutMasks:
    def __init__(self, masks, originalData):
        self.masks = masks
        self.originalData = originalData

    def to_c(self):
        result = ""
        # result += 'u8 sZoomOutAreaMasks[] = {\n'
        result += "\n"
        result += macrosToString(self.masks, True)
        # result += '};\n'
        return result

    def write(self, filepath):
        matchResult = re.search(
            "u8\s*sZoomOutAreaMasks\s*\[\]\s*=\s*\{" + "(((?!\}).)*)\}\s*;", self.originalData, re.DOTALL
        )

        if matchResult is None:
            raise PluginError('Could not find sZoomOutAreaMasks in "' + filepath + '".')
        data = self.originalData[: matchResult.start(1)] + self.to_c() + self.originalData[matchResult.end(1) :]

        if data == self.originalData:
            return

        maskFile = open(filepath, "w", newline="\n")
        maskFile.write(data)
        maskFile.close()

    def updateMaskCount(self, levelCount):
        if len(self.masks) - 1 < int(levelCount / 2):
            while len(self.masks) - 1 < int(levelCount / 2):
                self.masks.append(
                    [
                        "ZOOMOUT_AREA_MASK",
                        [
                            "0",
                            "0",
                            "0",
                            "0",
                            "0",
                            "0",
                            "0",
                            "0",
                        ],
                        "",
                    ]
                )
        else:
            self.masks = self.masks[: int(levelCount / 2) + 1]

    def setMask(self, levelIndex, zoomFlags):
        # sZoomOutAreaMasks has extra bits for one unused level at beginning
        # Thus, we add one to index
        index = int(levelIndex / 2)
        if levelIndex % 2 == 1:
            index += 1
            isLow = True
        else:
            isLow = False
        mask = self.masks[index]

        base = 0 if isLow else 4
        mask[1][0 + base] = "1" if zoomFlags[0] else "0"
        mask[1][1 + base] = "1" if zoomFlags[1] else "0"
        mask[1][2 + base] = "1" if zoomFlags[2] else "0"
        mask[1][3 + base] = "1" if zoomFlags[3] else "0"


class CourseDefines:
    def __init__(self, headerInfo, courses, bonusCourses, originalData):
        self.headerInfo = headerInfo
        self.courses = courses
        self.bonusCourses = bonusCourses
        self.originalData = originalData

    def to_c(self):
        result = self.headerInfo
        result += macrosToString(self.courses, False, tabDepth=0)
        result += "DEFINE_COURSES_END()\n"
        result += macrosToString(self.bonusCourses, False, tabDepth=0)
        return result

    def write(self, filepath):
        data = self.to_c()
        if data == self.originalData:
            return
        defineFile = open(filepath, "w", newline="\n")
        defineFile.write(data)
        defineFile.close()

    def getOrMakeMacroByCourseName(self, courseEnum, isBonus):
        for course in self.courses:
            if course[1][0] == courseEnum:
                return course
        for bonusCourse in self.bonusCourses:
            if bonusCourse[1][0] == courseEnum:
                return bonusCourse
        if not isBonus:
            macroCmd = ["DEFINE_COURSE", [courseEnum, "0x44444440"], ""]

            self.courses.append(macroCmd)
            return macroCmd

        else:
            macroCmd = ["DEFINE_BONUS_COURSE", [courseEnum, "0x44444440"], ""]

            self.bonusCourses.append(macroCmd)
            return macroCmd


class LevelDefines:
    def __init__(self, headerInfo, defineMacros, originalData):
        self.headerInfo = headerInfo
        self.defineMacros = defineMacros
        self.originalData = originalData
        self.newLevelAdded = False

    def to_c(self):
        result = self.headerInfo
        result += macrosToString(self.defineMacros, False, tabDepth=0)
        return result

    def write(self, filepath, headerPath):
        data = self.to_c()
        if data == self.originalData:
            return
        defineFile = open(filepath, "w", newline="\n")
        defineFile.write(data)
        defineFile.close()

        # Headers won't be updated unless this file is touched
        if self.newLevelAdded:
            os.utime(headerPath)

    def getOrMakeMacroByLevelName(self, levelName):
        for macro in self.defineMacros:
            if macro[0] == "DEFINE_LEVEL" and macro[1][3] == levelName:
                return macro
        macroCmd = [
            "DEFINE_LEVEL",
            [
                '"' + levelName.upper() + '"',
                "LEVEL_" + levelName.upper(),
                "COURSE_" + levelName.upper(),
                levelName,
                "generic",
                "20000",
                "0x00",
                "0x00",
                "0x00",
                "_",
                "_",
            ],
            "",
        ]
        self.newLevelAdded = True
        self.defineMacros.append(macroCmd)
        return macroCmd


class PersistentBlocks:
    beginMagic = "Fast64 begin persistent block"
    endMagic = "Fast64 end persistent block"

    beginRegex = re.compile(rf".*{beginMagic} (\[[\w ]+\]).*")
    endRegex = re.compile(rf".*{endMagic} (\[[\w ]+\]).*")

    includes = "[includes]"
    scripts = "[scripts]"
    levelCommands = "[level commands]"
    areaCommands = "[area commands]"

    @classmethod
    def new(cls):
        return {cls.includes: [], cls.scripts: [], cls.levelCommands: [], cls.areaCommands: defaultdict(list)}


class LevelScript:
    def __init__(self, name):
        self.name = name
        self.segmentLoads = []
        self.mario = "MARIO(MODEL_MARIO, 0x00000001, bhvMario),"
        self.levelFunctions = []
        self.modelLoads = []
        self.actorIncludes = []
        self.marioStart = None
        self.persistentBlocks = PersistentBlocks.new()

    def to_c(self, areaString):
        result = (
            "#include <ultra64.h>\n"
            + '#include "sm64.h"\n'
            + '#include "behavior_data.h"\n'
            + '#include "model_ids.h"\n'
            + '#include "seq_ids.h"\n'
            + '#include "dialog_ids.h"\n'
            + '#include "segment_symbols.h"\n'
            + '#include "level_commands.h"\n\n'
            + '#include "game/level_update.h"\n\n'
            + '#include "levels/scripts.h"\n\n'
        )

        for actorInclude in self.actorIncludes:
            result += actorInclude + "\n"

        result += f"\n{self.get_persistent_block(PersistentBlocks.includes)}\n\n"

        result += '#include "make_const_nonconst.h"\n'
        result += '#include "levels/' + self.name + '/header.h"\n\n'

        result += f"{self.get_persistent_block(PersistentBlocks.scripts)}\n\n"

        result += "const LevelScript level_" + self.name + "_entry[] = {\n"
        result += "\tINIT_LEVEL(),\n"
        for segmentLoad in self.segmentLoads:
            result += "\t" + macroToString(segmentLoad, True) + "\n"
        result += "\tALLOC_LEVEL_POOL(),\n"
        result += "\t" + self.mario + "\n"
        for levelFunction in self.levelFunctions:
            result += "\t" + macroToString(levelFunction, True) + "\n"
        for modelLoad in self.modelLoads:
            result += "\t" + macroToString(modelLoad, True) + "\n"
        result += "\n"

        result += f"{self.get_persistent_block(PersistentBlocks.levelCommands, nTabs=1)}\n\n"

        result += areaString

        result += "\tFREE_LEVEL_POOL(),\n"
        if self.marioStart is not None:
            result += "\t" + self.marioStart.to_c() + ",\n"
        else:
            result += "\tMARIO_POS(1, 0, 0, 0, 0),\n"
        result += (
            "\tCALL(0, lvl_init_or_update),\n"
            + "\tCALL_LOOP(1, lvl_init_or_update),\n"
            + "\tCLEAR_LEVEL(),\n"
            + "\tSLEEP_BEFORE_EXIT(1),\n"
            + "\tEXIT(),\n};\n"
        )

        return result

    def get_persistent_block(self, retainType: str, nTabs=0, areaIndex: str = None):
        tabs = "\t" * nTabs
        lines = [f"{tabs}/* {PersistentBlocks.beginMagic} {retainType} */"]
        if areaIndex:
            lines.extend(self.persistentBlocks[PersistentBlocks.areaCommands].get(areaIndex, []))
        else:
            lines.extend(self.persistentBlocks.get(retainType, []))
        lines.append(f"{tabs}/* {PersistentBlocks.endMagic} {retainType} */")
        return "\n".join(lines)


def parseCourseDefines(filepath):
    if not os.path.exists(filepath):
        raise PluginError('Path "' + filepath + '" does not exist, could not read course defines file.')
    scriptFile = open(filepath, "r", newline="\n")
    scriptData = scriptFile.read()
    scriptFile.close()

    matchResult = re.search("(\w*)\((((?!\)).)+)\)", scriptData, re.DOTALL)
    if matchResult is None:
        raise PluginError('Path "' + filepath + '" does not have any course define macros in it.')
    headerInfo = scriptData[: matchResult.start(0)]
    defineMacros = stringToMacros(scriptData)
    courses = []
    bonusCourses = []

    for macro in defineMacros:
        if macro[0] == "DEFINE_COURSE":
            courses.append(macro)
        elif macro[0] == "DEFINE_BONUS_COURSE":
            bonusCourses.append(macro)

    return CourseDefines(headerInfo, courses, bonusCourses, scriptData)


def parseLevelDefines(filepath):
    if not os.path.exists(filepath):
        raise PluginError('Path "' + filepath + '" does not exist, could not read level defines file.')
    scriptFile = open(filepath, "r", newline="\n")
    scriptData = scriptFile.read()
    scriptFile.close()

    matchResult = re.search("(\w*)\((((?!\)).)*)\)", scriptData, re.DOTALL)
    if matchResult is None:
        raise PluginError('Path "' + filepath + '" does not have any level define macros in it.')
    headerInfo = scriptData[: matchResult.start(0)]
    defineMacros = stringToMacros(scriptData)

    return LevelDefines(headerInfo, defineMacros, scriptData)


def parseZoomMasks(filepath):
    if not os.path.exists(filepath):
        raise PluginError('Path "' + filepath + '" does not exist, could not read camera.c file.')
    cameraFile = open(filepath, "r", newline="\n")
    cameraData = cameraFile.read()
    cameraFile.close()

    matchResult = re.search("u8\s*sZoomOutAreaMasks\s*\[\]\s*=\s*\{" + "(((?!\}).)*)\}\s*;", cameraData, re.DOTALL)

    if matchResult is None:
        raise PluginError('Could not find sZoomOutAreaMasks in "' + filepath + '".')

    zoomMaskString = matchResult.group(1)
    zoomMacros = stringToMacros(zoomMaskString)

    return ZoomOutMasks(zoomMacros, cameraData)


def replaceSegmentLoad(levelscript, segmentName, command, changedSegment):
    changedLoad = None
    for segmentLoad in levelscript.segmentLoads:
        segmentString = segmentLoad[1][0].lower()
        segment = int(segmentString, 16 if "x" in segmentString else 10)
        if segmentLoad[0] == command and segment == changedSegment:
            changedLoad = segmentLoad
    if changedLoad is None:
        changedLoad = [command, [hex(changedSegment), "", ""], ""]
        levelscript.segmentLoads.append(changedLoad)

    changedLoad[1][1] = segmentName + "SegmentRomStart"
    changedLoad[1][2] = segmentName + "SegmentRomEnd"


def stringToMacros(data):
    macroData = []
    for matchResult in re.finditer("(\w*)\((((?!\)).)*)\),?(((?!\n)\s)*\/\/((?!\n).)*)?", data):
        macro = matchResult.group(1)
        arguments = matchResult.group(2)
        if matchResult.group(4) is not None:
            comment = matchResult.group(4).strip()
        else:
            comment = ""
        arguments = re.sub("\/\*(\*(?!\/)|[^*])*\*\/", "", arguments)
        arguments = arguments.split(",")
        for i in range(len(arguments)):
            arguments[i] = arguments[i].strip()

        macroData.append([macro, arguments, comment])

    return macroData


def macroToString(macroCmd, useComma):
    result = macroCmd[0] + "("
    for arg in macroCmd[1]:
        result += arg + ", "
    result = result[:-2] + ")" + ("," if useComma else "")
    result += " " + macroCmd[2]
    return result


def macrosToString(macroCmds, useComma, tabDepth=1):
    result = ""
    for macroCmd in macroCmds:
        result += "\t" * tabDepth + macroToString(macroCmd, useComma) + "\n"
    return result


def setStartLevel(basePath, levelEnum):
    filepath = os.path.join(basePath, "levels/menu/script.c")
    data = getDataFromFile(filepath)

    newData = re.sub("SET\_REG\((((?!\)).)*)\)", "SET_REG(" + levelEnum + ")", data, count=1)
    if newData != data:
        saveDataToFile(filepath, newData)


def addActSelectorIgnore(basePath, levelEnum):
    filepath = os.path.join(basePath, "src/game/level_update.c")
    data = getDataFromFile(filepath)

    checkResult = re.search("if\s*\(gCurrLevelNum\s*==\s*" + levelEnum + "\)\s*return\s*0;", data, re.DOTALL)
    if checkResult is not None:
        return

    # This won't actually match whole function, but only up to first closing bracket.
    # This should be okay though... ?
    matchResultFunction = re.search(
        "s32\s*lvl\_set\_current\_level\s*\((((?!\)).)*)\)\s*\{" + "(((?!\}).)*)\}", data, re.DOTALL
    )

    if matchResultFunction is None:
        raise PluginError('Could not find lvl_set_current_level in "' + filepath + '".')

    functionContents = matchResultFunction.group(3)

    matchResult = re.search("gCurrCourseNum\s*\=\s*gLevelToCourseNumTable(((?!\;).)*)\;", functionContents, re.DOTALL)
    if matchResult is None:
        raise PluginError('Could not find gCurrCourseNum setting in lvl_set_current_level in "' + filepath + '".')

    functionContents = (
        functionContents[: matchResult.end(0)]
        + "\n\tif (gCurrLevelNum == "
        + levelEnum
        + ") return 0;"
        + functionContents[matchResult.end(0) :]
    )

    newData = data[: matchResultFunction.start(3)] + functionContents + data[matchResultFunction.end(3) :]

    saveDataToFile(filepath, newData)


def removeActSelectorIgnore(basePath, levelEnum):
    filepath = os.path.join(basePath, "src/game/level_update.c")
    data = getDataFromFile(filepath)

    newData = re.sub("if\s*\(gCurrLevelNum\s*\=\=\s*" + levelEnum + "\)\s*return\s*0\;\n", "", data, re.DOTALL)
    if data != newData:
        saveDataToFile(filepath, newData)


areaNumReg = re.compile(r".*AREA\(([0-9]+),.+\),")


def parseLevelPersistentBlocks(scriptData: str, levelScript: LevelScript):
    curBlock: str = None
    areaIndex: str = None

    for line in scriptData.splitlines():
        if curBlock and PersistentBlocks.endMagic in line:
            endMatch = PersistentBlocks.endRegex.match(line)
            if endMatch and endMatch.group(1) != curBlock:
                raise PluginError(f"script.c: Non-matching end block ({endMatch.group(1)}) found for {curBlock}")
            curBlock = None
            areaIndex = None
            continue

        areaIndexMatch = areaNumReg.match(line)
        if areaIndexMatch:
            areaIndex = areaIndexMatch.group(1)

        elif curBlock and curBlock == PersistentBlocks.areaCommands:
            if areaIndex:
                levelScript.persistentBlocks[curBlock][areaIndex].append(line)
            else:
                raise PluginError(
                    f'script.c: "{PersistentBlocks.beginMagic} {PersistentBlocks.areaCommands}" found outside of area block'
                )

        elif curBlock:
            levelScript.persistentBlocks[curBlock].append(line)

        elif PersistentBlocks.beginMagic in line:
            blockNameMatch = PersistentBlocks.beginRegex.match(line)
            if curBlock and blockNameMatch:
                raise PluginError(
                    f"script.c: Found new persistent block ({blockNameMatch.group(1)}) while looking for an end block for {curBlock}"
                )
            elif blockNameMatch:
                curBlock = blockNameMatch.group(1)

    if curBlock:
        raise PluginError(
            f'script.c: "{PersistentBlocks.beginMagic} {curBlock}" never found a "{PersistentBlocks.endMagic}"'
        )


def parseLevelScript(filepath, levelName):
    scriptPath = os.path.join(filepath, "script.c")
    scriptData = getDataFromFile(scriptPath)

    levelscript = LevelScript(levelName)

    for matchResult in re.finditer('#include\s*"actors/(\w*)\.h"', scriptData):
        levelscript.actorIncludes.append(matchResult.group(0))

    matchResult = re.search(
        "const\s*LevelScript\s*level\_\w*\_entry\[\]\s*=\s*\{" + "(((?!\}).)*)\}\s*;", scriptData, re.DOTALL
    )

    if matchResult is None:
        raise PluginError('Could not find entry levelscript in "' + scriptPath + '".')

    scriptContents = matchResult.group(1)

    macroData = stringToMacros(scriptContents)
    inArea = False
    for macroCmd in macroData:
        if not inArea:
            if (
                macroCmd[0] == "LOAD_MIO0"
                or macroCmd[0] == "LOAD_MIO0_TEXTURE"
                or macroCmd[0] == "LOAD_YAY0"
                or macroCmd[0] == "LOAD_YAY0_TEXTURE"
                or macroCmd[0] == "LOAD_RAW"
            ):
                levelscript.segmentLoads.append(macroCmd)
            elif macroCmd[0] == "JUMP_LINK":
                levelscript.levelFunctions.append(macroCmd)
            elif macroCmd[0] in ["LOAD_MODEL_FROM_GEO", "LOAD_MODEL_FROM_DL"]:
                levelscript.modelLoads.append(macroCmd)
            elif macroCmd[0] == "MARIO":
                levelscript.mario = macroToString(macroCmd, True)

        if macroCmd[0] == "AREA":
            inArea = True
        elif macroCmd[0] == "END_AREA":
            inArea = False

    parseLevelPersistentBlocks(scriptData, levelscript)
    return levelscript


def overwritePuppycamData(filePath, levelToReplace, newPuppycamTriggers):
    # Splits the file into what's before, inside, and after the array
    arrayEntiresRegex = "(.+struct\s+newcam_hardpos\s+newcam_fixedcam\[\]\s+=\s+{)(.+)(\};)"
    # Splits the individual entries in the array apart
    structEntry = "(.+?\{.+?\}.+?\n)"

    if os.path.exists(filePath):
        dataFile = open(filePath, "r")
        data = dataFile.read()
        dataFile.close()

        matchResult = re.search(arrayEntiresRegex, data, re.DOTALL)

        if matchResult:
            data = ""
            entriesString = matchResult.group(2)

            # Iterate through each existing entry, getting rid of any that are in the level we're importing to.
            entriesList = re.findall(structEntry, entriesString, re.DOTALL)
            for entry in entriesList:
                if (
                    re.search(
                        "(\{\s?" + levelToReplace + "\s?,)", re.sub("(/\*.+?\*/)|(//.+?\n)", "", entry), re.DOTALL
                    )
                    is None
                ):
                    data += entry

            # Add the new entries from this export, then put the file back together again.
            data += "\n\n" + newPuppycamTriggers
            data = matchResult.group(1) + data + "\n" + matchResult.group(3)
        else:
            raise PluginError("Could not find 'struct newcam_hardpos newcam_fixedcam[]'.")

        dataFile = open(filePath, "w", newline="\n")
        dataFile.write(data)
        dataFile.close()
    else:
        raise PluginError(filePath + " does not exist.")


class SM64OptionalFileStatus:
    def __init__(self):
        self.cameraC = False
        self.starSelectC = False


def exportLevelC(
    obj, transformMatrix, f3dType, isHWv1, levelName, exportDir, savePNG, customExport, levelCameraVolumeName, DLFormat
):

    fileStatus = SM64OptionalFileStatus()

    if customExport:
        levelDir = os.path.join(exportDir, levelName)
    else:
        levelDir = os.path.join(exportDir, "levels/" + levelName)

    if customExport or not os.path.exists(os.path.join(levelDir, "script.c")):
        prevLevelScript = LevelScript(levelName)
    else:
        prevLevelScript = parseLevelScript(levelDir, levelName)

    if not os.path.exists(levelDir):
        os.mkdir(levelDir)
    areaDict = {}

    geoString = ""
    levelDataString = ""
    headerString = ""
    areaString = ""
    cameraVolumeString = "struct CameraTrigger " + levelCameraVolumeName + "[] = {\n"
    puppycamVolumeString = ""

    fModel = SM64Model(f3dType, isHWv1, levelName + "_dl", DLFormat)
    childAreas = [child for child in obj.children if child.data is None and child.sm64_obj_type == "Area Root"]
    if len(childAreas) == 0:
        raise PluginError("The level root has no child empties with the 'Area Root' object type.")

    usesEnvFX = False
    echoLevels = ["0x00", "0x00", "0x00"]
    zoomFlags = [False, False, False, False]

    if bpy.context.scene.exportHiddenGeometry:
        hiddenObjs = unhideAllAndGetHiddenList(bpy.context.scene)

    for child in childAreas:
        if len(child.children) == 0:
            raise PluginError("Area for " + child.name + " has no children.")
        if child.areaIndex in areaDict:
            raise PluginError(child.name + " shares the same area index as " + areaDict[child.areaIndex].name)
        # if child.areaCamera is None:
        #    raise PluginError(child.name + ' does not have an area camera set.')
        # setOrigin(obj, child)
        areaDict[child.areaIndex] = child

        areaIndex = child.areaIndex
        areaName = "area_" + str(areaIndex)
        areaDir = os.path.join(levelDir, areaName)
        if not os.path.exists(areaDir):
            os.mkdir(areaDir)

        envOption = child.envOption if child.envOption != "Custom" else child.envType
        usesEnvFX |= envOption != "ENVFX_MODE_NONE"

        if child.areaIndex == 1 or child.areaIndex == 2 or child.areaIndex == 3:
            echoLevels[child.areaIndex - 1] = child.echoLevel
        if child.areaIndex == 1 or child.areaIndex == 2 or child.areaIndex == 3 or child.areaIndex == 4:
            zoomFlags[child.areaIndex - 1] = child.zoomOutOnPause

        # Needs to be done BEFORE collision parsing
        setRooms(child)

        geolayoutGraph, fModel = convertObjectToGeolayout(
            obj,
            transformMatrix,
            f3dType,
            isHWv1,
            child.areaCamera,
            levelName + "_" + areaName,
            fModel,
            child,
            DLFormat,
            not savePNG,
        )
        geolayoutGraphC = geolayoutGraph.to_c()

        # Write geolayout
        geoFile = open(os.path.join(areaDir, "geo.inc.c"), "w", newline="\n")
        geoFile.write(geolayoutGraphC.source)
        geoFile.close()
        geoString += '#include "levels/' + levelName + "/" + areaName + '/geo.inc.c"\n'
        headerString += geolayoutGraphC.header

        # Write collision
        collision = exportCollisionCommon(
            child, transformMatrix, True, True, levelName + "_" + areaName, child.areaIndex
        )
        collisionC = collision.to_c()
        colFile = open(os.path.join(areaDir, "collision.inc.c"), "w", newline="\n")
        colFile.write(collisionC.source)
        colFile.close()
        levelDataString += '#include "levels/' + levelName + "/" + areaName + '/collision.inc.c"\n'
        headerString += collisionC.header

        # Write rooms
        if child.enableRoomSwitch:
            roomsC = collision.to_c_rooms()
            roomFile = open(os.path.join(areaDir, "room.inc.c"), "w", newline="\n")
            roomFile.write(roomsC.source)
            roomFile.close()
            levelDataString += '#include "levels/' + levelName + "/" + areaName + '/room.inc.c"\n'
            headerString += roomsC.header

        # Get area
        area = exportAreaCommon(
            child, transformMatrix, geolayoutGraph.startGeolayout, collision, levelName + "_" + areaName
        )
        if area.mario_start is not None:
            prevLevelScript.marioStart = area.mario_start
        persistentBlockString = prevLevelScript.get_persistent_block(
            PersistentBlocks.areaCommands, nTabs=2, areaIndex=str(area.index)
        )
        areaString += area.to_c_script(child.enableRoomSwitch, persistentBlockString=persistentBlockString)
        cameraVolumeString += area.to_c_camera_volumes()
        puppycamVolumeString += area.to_c_puppycam_volumes()

        # Write macros
        macroFile = open(os.path.join(areaDir, "macro.inc.c"), "w", newline="\n")
        macrosC = area.to_c_macros()
        macroFile.write(macrosC.source)
        macroFile.close()
        levelDataString += '#include "levels/' + levelName + "/" + areaName + '/macro.inc.c"\n'
        headerString += macrosC.header

        # Write splines
        splineFile = open(os.path.join(areaDir, "spline.inc.c"), "w", newline="\n")
        splinesC = area.to_c_splines()
        splineFile.write(splinesC.source)
        splineFile.close()
        levelDataString += '#include "levels/' + levelName + "/" + areaName + '/spline.inc.c"\n'
        headerString += splinesC.header

    cameraVolumeString += "\tNULL_TRIGGER\n};"

    # Generate levelscript string
    compressionFmt = bpy.context.scene.compressionFormat
    replaceSegmentLoad(prevLevelScript, "_" + levelName + "_segment_7", "LOAD_" + compressionFmt.upper(), 0x07)
    if usesEnvFX:
        replaceSegmentLoad(prevLevelScript, "_effect_" + compressionFmt, "LOAD_" + compressionFmt.upper(), 0x0B)
    if not obj.useBackgroundColor:
        segment = ""
        if obj.background == "CUSTOM":
            segment = obj.fast64.sm64.level.backgroundSegment
        else:
            segment = backgroundSegments[obj.background] + "_skybox"

        replaceSegmentLoad(
            prevLevelScript, "_" + segment + "_" + compressionFmt, "LOAD_" + compressionFmt.upper(), 0x0A
        )
    levelscriptString = prevLevelScript.to_c(areaString)

    if bpy.context.scene.exportHiddenGeometry:
        hideObjsInList(hiddenObjs)

    # Remove old areas.
    for f in os.listdir(levelDir):
        if re.search("area\_\d+", f):
            existingArea = False
            for index, areaObj in areaDict.items():
                if f == "area_" + str(index):
                    existingArea = True
            if not existingArea:
                shutil.rmtree(os.path.join(levelDir, f))

    gfxFormatter = SM64GfxFormatter(ScrollMethod.Vertex)
    exportData = fModel.to_c(TextureExportSettings(savePNG, savePNG, "levels/" + levelName, levelDir), gfxFormatter)
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData
    texC = exportData.textureData

    scrollData, hasScrolling = fModel.to_c_vertex_scroll(levelName, gfxFormatter)
    scroll_data = scrollData.source
    headerScroll = scrollData.header

    if fModel.texturesSavedLastExport > 0:
        levelDataString = '#include "levels/' + levelName + '/texture_include.inc.c"\n' + levelDataString
        texPath = os.path.join(levelDir, "texture_include.inc.c")
        texFile = open(texPath, "w", newline="\n")
        texFile.write(texC.source)
        texFile.close()

    modifyTexScrollFiles(exportDir, levelDir, headerScroll, scroll_data, hasScrolling)

    # Write materials
    if DLFormat == DLFormat.Static:
        staticData.append(dynamicData)
    else:
        geoString = writeMaterialFiles(
            exportDir,
            levelDir,
            '#include "levels/' + levelName + '/header.h"',
            '#include "levels/' + levelName + '/material.inc.h"',
            dynamicData.header,
            dynamicData.source,
            geoString,
            customExport,
        )

    modelPath = os.path.join(levelDir, "model.inc.c")
    modelFile = open(modelPath, "w", newline="\n")
    modelFile.write(staticData.source)
    modelFile.close()

    fModel.freePalettes()

    levelDataString += '#include "levels/' + levelName + '/model.inc.c"\n'
    headerString += staticData.header
    # headerString += '\nextern const LevelScript level_' + levelName + '_entry[];\n'
    # headerString += '\n#endif\n'

    # Write geolayout
    geoFile = open(os.path.join(levelDir, "geo.inc.c"), "w", newline="\n")
    geoFile.write(geoString)
    geoFile.close()

    levelDataFile = open(os.path.join(levelDir, "leveldata.inc.c"), "w", newline="\n")
    levelDataFile.write(levelDataString)
    levelDataFile.close()

    headerFile = open(os.path.join(levelDir, "header.inc.h"), "w", newline="\n")
    headerFile.write(headerString)
    headerFile.close()

    scriptFile = open(os.path.join(levelDir, "script.c"), "w", newline="\n")
    scriptFile.write(levelscriptString)
    scriptFile.close()

    if customExport:
        cameraVolumeString = (
            "// Replace the level specific camera volume struct in src/game/camera.c with this.\n"
            + "// Make sure to also add the struct name to the LEVEL_DEFINE in levels/level_defines.h.\n"
            + cameraVolumeString
        )
        cameraFile = open(os.path.join(levelDir, "camera_trigger.inc.c"), "w", newline="\n")
        cameraFile.write(cameraVolumeString)
        cameraFile.close()

        hasPuppyCamData = puppycamVolumeString != ""
        puppycamVolumeString = (
            "// Put these structs into the newcam_fixedcam[] array in enhancements/puppycam_angles.inc.c. \n"
            + puppycamVolumeString
        )

        if hasPuppyCamData:
            cameraFile = open(os.path.join(levelDir, "puppycam_trigger.inc.c"), "w", newline="\n")
            cameraFile.write(puppycamVolumeString)
            cameraFile.close()

    if not customExport:
        if DLFormat != DLFormat.Static:
            # Write material headers
            writeMaterialHeaders(
                exportDir,
                '#include "levels/' + levelName + '/material.inc.c"',
                '#include "levels/' + levelName + '/material.inc.h"',
            )

        # Export camera triggers
        cameraPath = os.path.join(exportDir, "src/game/camera.c")
        if os.path.exists(cameraPath):
            overwriteData(
                "struct\s*CameraTrigger\s*",
                levelCameraVolumeName,
                cameraVolumeString,
                cameraPath,
                "struct CameraTrigger *sCameraTriggers",
                False,
            )
            fileStatus.cameraC = True

        # Export puppycam triggers
        # If this isn't an ultrapuppycam repo, don't try and export ultrapuppycam triggers
        puppycamAnglesPath = os.path.join(exportDir, "enhancements/puppycam_angles.inc.c")
        if os.path.exists(puppycamAnglesPath) and puppycamVolumeString != "":
            overwritePuppycamData(puppycamAnglesPath, levelIDNames[levelName], puppycamVolumeString)

        levelHeadersPath = os.path.join(exportDir, "levels/level_headers.h.in")
        levelDefinesPath = os.path.join(exportDir, "levels/level_defines.h")
        levelDefines = parseLevelDefines(levelDefinesPath)
        levelDefineMacro = levelDefines.getOrMakeMacroByLevelName(levelName)
        levelIndex = levelDefines.defineMacros.index(levelDefineMacro)
        levelEnum = levelDefineMacro[1][levelDefineArgs["level enum"]]

        levelDefineMacro[1][levelDefineArgs["camera table"]] = levelCameraVolumeName
        levelDefineMacro[1][levelDefineArgs["acoustic reach"]] = obj.acousticReach
        levelDefineMacro[1][levelDefineArgs["echo level 1"]] = echoLevels[0]
        levelDefineMacro[1][levelDefineArgs["echo level 2"]] = echoLevels[1]
        levelDefineMacro[1][levelDefineArgs["echo level 3"]] = echoLevels[2]

        levelDefines.write(levelDefinesPath, levelHeadersPath)

        courseDefinesPath = os.path.join(exportDir, "levels/course_defines.h")
        courseDefines = parseCourseDefines(courseDefinesPath)
        courseEnum = levelDefineMacro[1][levelDefineArgs["course name"]]
        courseMacro = courseDefines.getOrMakeMacroByCourseName(courseEnum, False)
        courseMacro[1][1] = obj.starGetCutscenes.value()
        courseDefines.write(courseDefinesPath)

        if os.path.exists(cameraPath):
            zoomMasks = parseZoomMasks(cameraPath)
            zoomMasks.updateMaskCount(len(levelDefines.defineMacros))
            zoomMasks.setMask(levelIndex, zoomFlags)
            zoomMasks.write(cameraPath)

        if obj.actSelectorIgnore:
            addActSelectorIgnore(exportDir, levelEnum)
        else:
            removeActSelectorIgnore(exportDir, levelEnum)

        if obj.setAsStartLevel:
            setStartLevel(exportDir, levelEnum)

        geoPath = os.path.join(levelDir, "geo.c")
        levelDataPath = os.path.join(levelDir, "leveldata.c")
        headerPath = os.path.join(levelDir, "header.h")

        # Create files if not already existing
        if not os.path.exists(geoPath):
            createGeoFile(levelName, geoPath)
        if not os.path.exists(levelDataPath):
            createLevelDataFile(levelName, levelDataPath)
        if not os.path.exists(headerPath):
            createHeaderFile(levelName, headerPath)

        # Write level data
        writeIfNotFound(geoPath, '\n#include "levels/' + levelName + '/geo.inc.c"\n', "")
        writeIfNotFound(levelDataPath, '\n#include "levels/' + levelName + '/leveldata.inc.c"\n', "")
        writeIfNotFound(headerPath, '\n#include "levels/' + levelName + '/header.inc.h"\n', "#endif")

        if fModel.texturesSavedLastExport == 0:
            textureIncludePath = os.path.join(levelDir, "texture_include.inc.c")
            if os.path.exists(textureIncludePath):
                os.remove(textureIncludePath)
            # This one is for backwards compatibility purposes
            deleteIfFound(
                os.path.join(levelDir, "texture.inc.c"), '#include "levels/' + levelName + '/texture_include.inc.c"'
            )

        # This one is for backwards compatibility purposes
        deleteIfFound(levelDataPath, '#include "levels/' + levelName + '/texture_include.inc.c"')

        texscrollIncludeC = '#include "levels/' + levelName + '/texscroll.inc.c"'
        texscrollIncludeH = '#include "levels/' + levelName + '/texscroll.inc.h"'
        texscrollGroup = levelName
        texscrollGroupInclude = '#include "levels/' + levelName + '/header.h"'

        texScrollFileStatus = modifyTexScrollHeadersGroup(
            exportDir,
            texscrollIncludeC,
            texscrollIncludeH,
            texscrollGroup,
            headerScroll,
            texscrollGroupInclude,
            hasScrolling,
        )

        if texScrollFileStatus is not None:
            fileStatus.starSelectC = texScrollFileStatus.starSelectC

    return fileStatus


def addGeoC(levelName):
    header = (
        "#include <ultra64.h>\n"
        '#include "sm64.h"\n'
        '#include "geo_commands.h"\n'
        "\n"
        '#include "game/level_geo.h"\n'
        '#include "game/geo_misc.h"\n'
        '#include "game/camera.h"\n'
        '#include "game/moving_texture.h"\n'
        '#include "game/screen_transition.h"\n'
        '#include "game/paintings.h"\n\n'
    )

    header += '#include "levels/' + levelName + '/header.h"\n'
    return header


def addLevelDataC(levelName):
    header = (
        "#include <ultra64.h>\n"
        '#include "sm64.h"\n'
        '#include "surface_terrains.h"\n'
        '#include "moving_texture_macros.h"\n'
        '#include "level_misc_macros.h"\n'
        '#include "macro_preset_names.h"\n'
        '#include "special_preset_names.h"\n'
        '#include "textures.h"\n'
        '#include "dialog_ids.h"\n'
        "\n"
        '#include "make_const_nonconst.h"\n'
    )

    return header


def addHeaderC(levelName):
    header = (
        "#ifndef " + levelName.upper() + "_HEADER_H\n" + "#define " + levelName.upper() + "_HEADER_H\n" + "\n"
        '#include "types.h"\n'
        '#include "game/moving_texture.h"\n\n'
    )

    return header


class SM64_ExportLevel(ObjectDataExporter):
    # set bl_ properties
    bl_idname = "object.sm64_export_level"
    bl_label = "Export Level"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        if context.mode != "OBJECT":
            raise PluginError("Operator can only be used in object mode.")
        obj: bpy.types.Object = None
        try:
            try:
                if len(context.selected_objects) == 0:
                    raise PluginError("Object not selected.")
                obj = context.selected_objects[0]
                if obj.data is not None or obj.sm64_obj_type != "Level Root":
                    raise PluginError("The selected object is not an empty with the Level Root type.")
            except PluginError:
                # try to find parent level root
                if obj is not None:
                    while True:
                        if not obj.parent:
                            break
                        obj = obj.parent
                        if obj.data is None and obj.sm64_obj_type == "Level Root":
                            break
                if obj is None or obj.sm64_obj_type != "Level Root":
                    raise PluginError("Cannot find level empty.")
                selectSingleObject(obj)

            scaleValue = bpy.context.scene.blenderToSM64Scale
            finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set
        try:
            self.store_object_data()

            applyRotation([obj], math.radians(90), "X")
            if context.scene.levelCustomExport:
                exportPath = bpy.path.abspath(context.scene.levelExportPath)
                levelName = context.scene.levelName
                triggerName = "sCam" + context.scene.levelName.title().replace(" ", "").replace("_", "")
            else:
                exportPath = bpy.path.abspath(context.scene.decompPath)
                if context.scene.levelOption == "custom":
                    levelName = context.scene.levelName
                    triggerName = "sCam" + context.scene.levelName.title().replace(" ", "").replace("_", "")
                else:
                    levelName = context.scene.levelOption
                    triggerName = cameraTriggerNames[context.scene.levelOption]
            if not context.scene.levelCustomExport:
                applyBasicTweaks(exportPath)
            fileStatus = exportLevelC(
                obj,
                finalTransform,
                context.scene.f3d_type,
                context.scene.isHWv1,
                levelName,
                exportPath,
                context.scene.saveTextures,
                context.scene.levelCustomExport,
                triggerName,
                DLFormat.Static,
            )

            cameraWarning(self, fileStatus)
            starSelectWarning(self, fileStatus)

            applyRotation([obj], math.radians(-90), "X")
            self.cleanup_temp_object_data()

            self.report({"INFO"}, "Success!")
            self.show_warnings()
            return {"FINISHED"}  # must return a set

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            applyRotation([obj], math.radians(-90), "X")
            self.cleanup_temp_object_data()

            obj.select_set(True)
            context.view_layer.objects.active = obj
            self.reset_warnings()
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class SM64_ExportLevelPanel(SM64_Panel):
    bl_idname = "SM64_PT_export_level"
    bl_label = "SM64 Level Exporter"
    goal = "Export Level"
    decomp_only = True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.label(text="This is for decomp only.")
        col.operator(SM64_ExportLevel.bl_idname)
        col.prop(context.scene, "levelCustomExport")
        if context.scene.levelCustomExport:
            prop_split(col, context.scene, "levelExportPath", "Directory")
            prop_split(col, context.scene, "levelName", "Name")
            customExportWarning(col)
        else:
            col.prop(context.scene, "levelOption")
            if context.scene.levelOption == "custom":
                levelName = context.scene.levelName
                box = col.box()
                box.label(text="Adding levels may require modifying the save file format.")
                box.label(text="Check src/game/save_file.c.")
                prop_split(col, context.scene, "levelName", "Name")
            else:
                levelName = context.scene.levelOption
            decompFolderMessage(col)
            writeBox = makeWriteInfoBox(col)
            writeBox.label(text="levels/" + toAlnum(levelName) + " (data).")
            writeBox.label(text="src/game/camera.c (camera volume).")
            writeBox.label(text="levels/level_defines.h (camera volume).")


sm64_level_classes = (SM64_ExportLevel,)

sm64_level_panel_classes = (SM64_ExportLevelPanel,)


def sm64_level_panel_register():
    for cls in sm64_level_panel_classes:
        register_class(cls)


def sm64_level_panel_unregister():
    for cls in sm64_level_panel_classes:
        unregister_class(cls)


def sm64_level_register():
    for cls in sm64_level_classes:
        register_class(cls)

    bpy.types.Scene.levelName = bpy.props.StringProperty(name="Name", default="bob")
    bpy.types.Scene.levelOption = bpy.props.EnumProperty(name="Level", items=enumLevelNames, default="bob")
    bpy.types.Scene.levelExportPath = bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    bpy.types.Scene.levelCustomExport = bpy.props.BoolProperty(name="Custom Export Path")


def sm64_level_unregister():
    for cls in reversed(sm64_level_classes):
        unregister_class(cls)

    del bpy.types.Scene.levelName
    del bpy.types.Scene.levelExportPath
    del bpy.types.Scene.levelCustomExport
    del bpy.types.Scene.levelOption
