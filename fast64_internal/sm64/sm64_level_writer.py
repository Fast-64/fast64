import bpy, os, math, re, shutil, mathutils
from collections import defaultdict
from typing import NamedTuple
from dataclasses import dataclass
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
    unhideAllAndGetHiddenState,
    restoreHiddenState,
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
    getPathAndLevel,
)

from ..f3d.f3d_gbi import (
    ScrollMethod,
    GfxMatWriteMethod,
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
        "#include <ultra64.h>\n"
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
        return f"\n{macrosToString(self.masks)}\n"

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
                self.masks.append(Macro("ZOOMOUT_AREA_MASK", ["0"] * 8, ""))
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
        result += macrosToString(self.courses, tabDepth=0, comma=False)
        result += "\nDEFINE_COURSES_END()\n"
        result += macrosToString(self.bonusCourses, tabDepth=0, comma=False)
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
            macroCmd = Macro("DEFINE_COURSE", [courseEnum, "0x44444440"], "")

            self.courses.append(macroCmd)
            return macroCmd

        else:
            macroCmd = Macro("DEFINE_BONUS_COURSE", [courseEnum, "0x44444440"], "")

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
        result += macrosToString(self.defineMacros, tabDepth=0, comma=False)
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
        macroCmd = Macro(
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
        )
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


class Macro(NamedTuple):
    function: str
    args: list[str]
    comment: str


@dataclass
class LevelData:
    script_data: str = ""
    area_data: str = ""
    camera_data: str = ""
    puppycam_data: str = ""
    geo_data: str = ""
    collision_data: str = ""
    header_data: str = ""


class LevelScript:
    def __init__(self, name):
        self.name = name
        self.segmentLoads = []
        self.mario = "MARIO(MODEL_MARIO, 0x00000001, bhvMario),"
        self.macros = []
        self.levelFunctions = []
        self.modelLoads = []
        self.actorIncludes = []
        self.marioStart = None
        self.persistentBlocks = PersistentBlocks.new()
        self.sub_scripts: LevelScript = []

    # this is basically a smaller script jumped to from the main one
    def add_subscript(self, name: str):
        self.sub_scripts.append(new_script := LevelScript(name))
        return new_script

    def sub_script_to_c(self, root_persistent_block):
        result = ""
        if not any(
            [
                f"const LevelScript {self.name}[]" in line
                for line in root_persistent_block.get(PersistentBlocks.scripts, [])
            ]
        ):
            result = f"const LevelScript {self.name}[] = {{\n{macrosToString(self.macros)}\n}};\n"
        for sub_script in self.sub_scripts:
            result += sub_script.sub_script_to_c(result, root_persistent_block)
        return result

    def to_c(self, areaString):
        if self.marioStart is not None:
            mario_start_macro = f"\t{self.marioStart.to_c()},"
        else:
            mario_start_macro = "\tMARIO_POS(1, 0, 0, 0, 0),"
        return "\n".join(
            filter(
                None,
                (
                    # all the includes
                    "#include <ultra64.h>",
                    '#include "sm64.h"',
                    '#include "behavior_data.h"',
                    '#include "model_ids.h"',
                    '#include "seq_ids.h"',
                    '#include "dialog_ids.h"',
                    '#include "segment_symbols.h"',
                    '#include "level_commands.h"\n',
                    '#include "game/level_update.h"\n',
                    '#include "levels/scripts.h"\n',
                    "\n".join(self.actorIncludes),
                    '#include "make_const_nonconst.h"',
                    f'#include "levels/{self.name}/header.h"\n',
                    # persistent block
                    f"{self.get_persistent_block(PersistentBlocks.scripts)}\n",
                    # sub scripts referenced in previous level script in the same file
                    "".join([script.sub_script_to_c(self.persistentBlocks) for script in self.sub_scripts]),
                    # main level script entry
                    f"const LevelScript level_{self.name}_entry[] = {{",
                    "\tINIT_LEVEL(),",
                    macrosToString(self.segmentLoads),
                    f"\tALLOC_LEVEL_POOL(),",
                    f"\t{self.mario}",
                    macrosToString(self.levelFunctions),
                    macrosToString(self.modelLoads),
                    f"{self.get_persistent_block(PersistentBlocks.levelCommands, nTabs=1)}\n",
                    f"{areaString}\tFREE_LEVEL_POOL(),",
                    mario_start_macro,
                    "\tCALL(0, lvl_init_or_update),",
                    "\tCALL_LOOP(1, lvl_init_or_update),",
                    "\tCLEAR_LEVEL(),",
                    "\tSLEEP_BEFORE_EXIT(1),",
                    "\tEXIT(),\n};",
                ),
            )
        )

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
        changedLoad = Macro(command, [hex(changedSegment), "", ""], "")
        levelscript.segmentLoads.append(changedLoad)

    changedLoad[1][1] = segmentName + "SegmentRomStart"
    changedLoad[1][2] = segmentName + "SegmentRomEnd"


def replaceScriptLoads(levelscript, obj):
    newFuncs = []
    for jumpLink in levelscript.levelFunctions:
        target = jumpLink.args[0]  # format is [macro, list[args], comment]
        if "script_func_global_" not in target:
            newFuncs.append(jumpLink)
            continue
        scriptNum = int(re.findall(r"\d+", target)[-1])
        # this is common0
        if scriptNum == 1:
            newFuncs.append(jumpLink)
            continue
        if scriptNum < 13:
            newNum = obj.fast64.sm64.segment_loads.group5
        else:
            newNum = obj.fast64.sm64.segment_loads.group6
        if newNum == "Do Not Write":
            newFuncs.append(jumpLink)
            continue
        newFuncs.append(Macro("JUMP_LINK", [newNum], jumpLink.comment))
    levelscript.levelFunctions = newFuncs


STRING_TO_MACROS_PATTERN = re.compile(
    r"""
    .*? # match as few chars as possible before macro name
    (?P<macro_name>\w+) #group macro name matches 1+ word chars
    \s* # allows any number of spaces after macro name
    \((?P<arguments> # group <arguments> is inside first parenthesis
        [^()]* # anything but ()
        (?: # Non-capturing group for 1 depth parentheses
            \(.*?\) # captures parenthesis+any chars inside
            [^()]*
        )* # allows any number of inner parenthesis ()
    )\)
    (\s*?,)?[^\n]*? # capture a comma, including white space trailing except for new lines following the comma
    (?P<comment> # comment group
        ([^\n]*?|\s*?\\\s*?\n)//.*$ # two // and any number of chars and str or line end
        |
        ([^\n]*?|\s*?\\\s*?\n)/\*[\s\S]*?\*/ # a /*, any number of chars (including new line) and a */
    )? # 0 or 1 repetition of comments
""",
    re.VERBOSE | re.MULTILINE,
)


def stringToMacros(data):
    macroData = []
    for matchResult in re.finditer(STRING_TO_MACROS_PATTERN, data):
        function = matchResult.group("macro_name").strip()
        arguments = matchResult.group("arguments").strip()
        comment = matchResult.group("comment")
        if comment is None:
            comment = ""
        else:
            comment = comment.strip()
        arguments = re.sub("\/\*(\*(?!\/)|[^*])*\*\/", "", arguments)
        arguments = [arg.strip() for arg in arguments.split(",")]

        macroData.append(Macro(function, arguments, comment))
    return macroData


def macroToString(macro_cmd, comma=True):
    return f"{macro_cmd.function}({', '.join(macro_cmd.args)}){',' if comma else ''} {macro_cmd.comment}"


def macrosToString(macro_cmds, tabDepth=1, comma=True):
    tabs = "\t" * tabDepth
    return "\n".join([f"{tabs}{macroToString(macro_cmd, comma = comma)}" for macro_cmd in macro_cmds])


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

    level_script = LevelScript(levelName)

    for matchResult in re.finditer('#include\s*"actors/(\w*)\.h"', scriptData):
        level_script.actorIncludes.append(matchResult.group(0))

    def parse_macros(script_contents, level_script):
        macro_data = stringToMacros(script_contents)
        inArea = False
        for macro_cmd in macro_data:
            level_script.macros.append(macro_cmd)
            if not inArea:
                if macro_cmd.function in {
                    "LOAD_MIO0",
                    "LOAD_MIO0_TEXTURE",
                    "LOAD_YAY0",
                    "LOAD_YAY0_TEXTURE",
                    "LOAD_RAW",
                    "LOAD_VANILLA_OBJECTS",
                }:
                    level_script.segmentLoads.append(macro_cmd)
                elif macro_cmd.function == "JUMP_LINK":
                    level_script.levelFunctions.append(macro_cmd)
                elif macro_cmd.function in {"LOAD_MODEL_FROM_GEO", "LOAD_MODEL_FROM_DL"}:
                    level_script.modelLoads.append(macro_cmd)
                elif macro_cmd.function == "MARIO":
                    level_script.mario = macroToString(macro_cmd)

            if macro_cmd.function == "AREA":
                inArea = True
            elif macro_cmd.function == "END_AREA":
                inArea = False

    # find JUMP_LINK's within the same script.c file and retain them
    def parse_sub_scripts(scriptData, level_script):
        for script_macro in level_script.levelFunctions:
            script_ptr = script_macro.args[0]
            match_result = re.search(
                f"const\s*LevelScript\s*{script_ptr}\[\]\s*=\s*\{{" + "(((?!\}).)*)\}\s*;", scriptData, re.DOTALL
            )
            print(match_result, script_ptr)
            if not match_result:
                continue
            sub_script = level_script.add_subscript(script_ptr)
            parse_macros(match_result.group(1), sub_script)
            parse_sub_scripts(scriptData, sub_script)

    match_result = re.search(
        "const\s*LevelScript\s*level\_\w*\_entry\[\]\s*=\s*\{" + "(((?!\}).)*)\}\s*;", scriptData, re.DOTALL
    )

    if match_result is None:
        raise PluginError('Could not find entry levelscript in "' + scriptPath + '".')

    parse_macros(match_result.group(1), level_script)
    parseLevelPersistentBlocks(scriptData, level_script)
    parse_sub_scripts(scriptData, level_script)

    return level_script


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


def export_area_c(
    obj, level_data, area_root, prev_level_script, transformMatrix, level_name, level_dir, fModel, DLFormat, savePNG
):
    areaName = f"area_{area_root.areaIndex}"
    areaDir = os.path.join(level_dir, areaName)
    if not os.path.exists(areaDir):
        os.mkdir(areaDir)

    envOption = area_root.envOption if area_root.envOption != "Custom" else area_root.envType
    uses_env_fx = envOption != "ENVFX_MODE_NONE"

    def include_proto(file_name):
        return f'#include "levels/{level_name}/{areaName}/{file_name}"\n'

    # Write geolayout
    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj,
        transformMatrix,
        area_root.areaCamera,
        f"{level_name}_{areaName}",
        fModel,
        area_root,
        DLFormat,
        not savePNG,
    )
    geolayoutGraphC = geolayoutGraph.to_c()
    saveDataToFile(os.path.join(areaDir, "geo.inc.c"), geolayoutGraphC.source)
    level_data.geo_data += include_proto("geo.inc.c")
    level_data.header_data += geolayoutGraphC.header

    # Write collision, rooms MUST be done first
    setRooms(area_root)
    collision = exportCollisionCommon(
        area_root, transformMatrix, True, True, f"{level_name}_{areaName}", area_root.areaIndex
    )
    collisionC = collision.to_c()
    saveDataToFile(os.path.join(areaDir, "collision.inc.c"), collisionC.source)
    level_data.script_data += include_proto("collision.inc.c")
    level_data.header_data += collisionC.header

    # Write rooms
    if area_root.enableRoomSwitch:
        roomsC = collision.to_c_rooms()
        saveDataToFile(os.path.join(areaDir, "room.inc.c"), roomsC.source)
        level_data.script_data += include_proto("room.inc.c")
        level_data.header_data += roomsC.header

    # Get area
    area = exportAreaCommon(
        area_root, transformMatrix, geolayoutGraph.startGeolayout, collision, f"{level_name}_{areaName}"
    )
    if area.mario_start is not None:
        prev_level_script.marioStart = area.mario_start
    persistentBlockString = prev_level_script.get_persistent_block(
        PersistentBlocks.areaCommands, nTabs=2, areaIndex=str(area.index)
    )
    level_data.area_data += area.to_c_script(area_root.enableRoomSwitch, persistentBlockString=persistentBlockString)
    level_data.camera_data += area.to_c_camera_volumes()
    level_data.puppycam_data += area.to_c_puppycam_volumes()

    # Write macros
    macrosC = area.to_c_macros()
    saveDataToFile(os.path.join(areaDir, "macro.inc.c"), macrosC.source)
    level_data.script_data += include_proto("macro.inc.c")
    level_data.header_data += macrosC.header

    # Write splines
    splinesC = area.to_c_splines()
    saveDataToFile(os.path.join(areaDir, "spline.inc.c"), splinesC.source)
    level_data.script_data += include_proto("spline.inc.c")
    level_data.header_data += splinesC.header

    return level_data, fModel, uses_env_fx


def export_level_script_c(obj, prev_level_script, level_name, level_data, level_dir, uses_env_fx):
    compressionFmt = bpy.context.scene.fast64.sm64.compression_format
    # replace level loads
    replaceSegmentLoad(prev_level_script, f"_{level_name}_segment_7", f"LOAD_{compressionFmt.upper()}", 0x07)
    if uses_env_fx:
        replaceSegmentLoad(prev_level_script, f"_effect_{compressionFmt}", f"LOAD_{compressionFmt.upper()}", 0x0B)
    if not obj.useBackgroundColor:
        if obj.background == "CUSTOM":
            segment = obj.fast64.sm64.level.backgroundSegment
        else:
            segment = f"{backgroundSegments[obj.background]}_skybox"
        replaceSegmentLoad(prev_level_script, f"_{segment}_{compressionFmt}", f"LOAD_{compressionFmt.upper()}", 0x0A)

    # replace actor loads
    group_seg_loads = obj.fast64.sm64.segment_loads
    if group_seg_loads.seg5_enum != "Do Not Write":
        replaceSegmentLoad(
            prev_level_script,
            f"_{group_seg_loads.seg5}_{compressionFmt}",
            f"LOAD_{compressionFmt.upper()}",
            0x05,
        )
        replaceSegmentLoad(prev_level_script, f"_{group_seg_loads.seg5}_geo", "LOAD_RAW", 0x0C)
    if group_seg_loads.seg6_enum != "Do Not Write":
        replaceSegmentLoad(
            prev_level_script,
            f"_{group_seg_loads.seg6}_{compressionFmt}",
            f"LOAD_{compressionFmt.upper()}",
            0x06,
        )
        replaceSegmentLoad(prev_level_script, f"_{group_seg_loads.seg6}_geo", "LOAD_RAW", 0x0D)

    # write data
    replaceScriptLoads(prev_level_script, obj)
    saveDataToFile(os.path.join(level_dir, "script.c"), prev_level_script.to_c(level_data.area_data))

    return level_data


def exportLevelC(obj, transformMatrix, level_name, exportDir, savePNG, customExport, levelCameraVolumeName, DLFormat):
    fileStatus = SM64OptionalFileStatus()

    if customExport:
        level_dir = os.path.join(exportDir, level_name)
    else:
        level_dir = os.path.join(exportDir, "levels/" + level_name)

    if not os.path.exists(os.path.join(level_dir, "script.c")):
        prev_level_script = LevelScript(level_name)
    else:
        prev_level_script = parseLevelScript(level_dir, level_name)

    if not os.path.exists(level_dir):
        os.mkdir(level_dir)

    level_data = LevelData(camera_data=f"struct CameraTrigger {levelCameraVolumeName}[] = {{\n")

    inline = bpy.context.scene.exportInlineF3D
    fModel = SM64Model(
        level_name + "_dl",
        DLFormat,
        GfxMatWriteMethod.WriteDifferingAndRevert if not inline else GfxMatWriteMethod.WriteAll,
    )
    childAreas = [child for child in obj.children if child.type == "EMPTY" and child.sm64_obj_type == "Area Root"]
    if len(childAreas) == 0:
        raise PluginError("The level root has no child empties with the 'Area Root' object type.")

    uses_env_fx = False
    echoLevels = ["0x00", "0x00", "0x00"]
    zoomFlags = [False, False, False, False]

    if bpy.context.scene.exportHiddenGeometry:
        hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

    area_dict = {}
    for area_root in childAreas:
        # verify validity of level hierarchy
        if len(area_root.children) == 0:
            raise PluginError(f"Area for {area_root.name} has no children.")
        if area_root.areaIndex in area_dict:
            raise PluginError(f"{area_root.name} shares the same area index as {area_dict[area_root.areaIndex].name}")
        area_dict[area_root.areaIndex] = area_root
        # set echo/zoom vals
        if area_root.areaIndex > 0 and area_root.areaIndex < 5:
            zoomFlags[area_root.areaIndex - 1] = area_root.zoomOutOnPause
            if area_root.areaIndex < 4:
                echoLevels[area_root.areaIndex - 1] = area_root.echoLevel

        # write area specific files
        level_data, fModel, uses_env_fx = export_area_c(
            obj,
            level_data,
            area_root,
            prev_level_script,
            transformMatrix,
            level_name,
            level_dir,
            fModel,
            DLFormat,
            savePNG,
        )

    level_data.camera_data += "\tNULL_TRIGGER\n};"

    # Generate levelscript string
    export_level_script_c(obj, prev_level_script, level_name, level_data, level_dir, uses_env_fx)

    if bpy.context.scene.exportHiddenGeometry:
        restoreHiddenState(hiddenState)

    # Remove old areas.
    for folder in os.listdir(level_dir):
        if re.search("area\_\d+", folder):
            existingArea = False
            for index, areaObj in area_dict.items():
                if folder == f"area_{index}":
                    existingArea = True
            if not existingArea:
                shutil.rmtree(os.path.join(level_dir, folder))

    def include_proto(file_name, new_line_first=False):
        include = f'#include "levels/{level_name}/{file_name}"'
        if new_line_first:
            include = "\n" + include
        else:
            include += "\n"
        return include

    gfxFormatter = SM64GfxFormatter(ScrollMethod.Vertex)
    exportData = fModel.to_c(TextureExportSettings(savePNG, savePNG, f"levels/{level_name}", level_dir), gfxFormatter)
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData
    texC = exportData.textureData

    scrollData = fModel.to_c_scroll(level_name, gfxFormatter)

    if fModel.texturesSavedLastExport > 0:
        level_data.script_data = include_proto("texture_include.inc.c") + level_data.script_data
        saveDataToFile(os.path.join(level_dir, "texture_include.inc.c"), texC.source)

    modifyTexScrollFiles(exportDir, level_dir, scrollData)

    # Write materials
    if DLFormat == DLFormat.Static:
        staticData.append(dynamicData)
    else:
        level_data.geo_data = writeMaterialFiles(
            exportDir,
            level_dir,
            include_proto("header.h"),
            include_proto("material.inc.h"),
            dynamicData.header,
            dynamicData.source,
            level_data.geo_data,
            customExport,
        )

    fModel.freePalettes()

    level_data.script_data += include_proto("model.inc.c")
    level_data.header_data += staticData.header

    # Write data
    saveDataToFile(os.path.join(level_dir, "model.inc.c"), staticData.source)
    saveDataToFile(os.path.join(level_dir, "geo.inc.c"), level_data.geo_data)
    saveDataToFile(os.path.join(level_dir, "leveldata.inc.c"), level_data.script_data)
    saveDataToFile(os.path.join(level_dir, "header.inc.h"), level_data.header_data)

    if customExport:
        level_data.camera_data = "\n".join(
            [
                "// Replace the level specific camera volume struct in src/game/camera.c with this.",
                "// Make sure to also add the struct name to the LEVEL_DEFINE in levels/level_defines.h.",
                level_data.camera_data,
            ]
        )
        saveDataToFile(os.path.join(level_dir, "camera_trigger.inc.c"), level_data.camera_data)

        hasPuppyCamData = level_data.puppycam_data != ""
        level_data.puppycam_data = "\n".join(
            [
                "// Put these structs into the newcam_fixedcam[] array in enhancements/puppycam_angles.inc.c.",
                level_data.puppycam_data,
            ]
        )

        if hasPuppyCamData:
            saveDataToFile(os.path.join(level_dir, "puppycam_trigger.inc.c"), level_data.puppycam_data)

    if not customExport:
        if DLFormat != DLFormat.Static:
            # Write material headers
            writeMaterialHeaders(
                exportDir,
                include_proto("material.inc.c"),
                include_proto("material.inc.h"),
            )

        # Export camera triggers
        cameraPath = os.path.join(exportDir, "src/game/camera.c")
        if os.path.exists(cameraPath):
            overwriteData(
                "struct\s*CameraTrigger\s*",
                levelCameraVolumeName,
                level_data.camera_data,
                cameraPath,
                "struct CameraTrigger *sCameraTriggers",
                False,
            )
            fileStatus.cameraC = True

        # Export puppycam triggers
        # If this isn't an ultrapuppycam repo, don't try and export ultrapuppycam triggers
        puppycamAnglesPath = os.path.join(exportDir, "enhancements/puppycam_angles.inc.c")
        if os.path.exists(puppycamAnglesPath) and level_data.puppycam_data != "":
            overwritePuppycamData(puppycamAnglesPath, levelIDNames[level_name], level_data.puppycam_data)

        levelHeadersPath = os.path.join(exportDir, "levels/level_headers.h.in")
        levelDefinesPath = os.path.join(exportDir, "levels/level_defines.h")
        levelDefines = parseLevelDefines(levelDefinesPath)
        levelDefineMacro = levelDefines.getOrMakeMacroByLevelName(level_name)
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

        geoPath = os.path.join(level_dir, "geo.c")
        levelDataPath = os.path.join(level_dir, "leveldata.c")
        headerPath = os.path.join(level_dir, "header.h")

        # Create files if not already existing
        if not os.path.exists(geoPath):
            createGeoFile(level_name, geoPath)
        if not os.path.exists(levelDataPath):
            createLevelDataFile(level_name, levelDataPath)
        if not os.path.exists(headerPath):
            createHeaderFile(level_name, headerPath)

        # Write level data
        writeIfNotFound(geoPath, include_proto("geo.inc.c", new_line_first=True), "")
        writeIfNotFound(levelDataPath, include_proto("leveldata.inc.c", new_line_first=True), "")
        writeIfNotFound(headerPath, include_proto("header.inc.h", new_line_first=True), "#endif")

        if fModel.texturesSavedLastExport == 0:
            textureIncludePath = os.path.join(level_dir, "texture_include.inc.c")
            if os.path.exists(textureIncludePath):
                os.remove(textureIncludePath)
            # This one is for backwards compatibility purposes
            deleteIfFound(os.path.join(level_dir, "texture.inc.c"), include_proto("texture_include.inc.c"))

        # This one is for backwards compatibility purposes
        deleteIfFound(levelDataPath, include_proto("texture_include.inc.c"))

        texscrollIncludeC = include_proto("texscroll.inc.c")
        texscrollIncludeH = include_proto("texscroll.inc.h")
        texscrollGroup = level_name
        texscrollGroupInclude = include_proto("header.h")

        texScrollFileStatus = modifyTexScrollHeadersGroup(
            exportDir,
            texscrollIncludeC,
            texscrollIncludeH,
            texscrollGroup,
            scrollData.topLevelScrollFunc,
            texscrollGroupInclude,
            scrollData.hasScrolling(),
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
                if obj.type != "EMPTY" or obj.sm64_obj_type != "Level Root":
                    raise PluginError("The selected object is not an empty with the Level Root type.")
            except PluginError:
                # try to find parent level root
                if obj is not None:
                    while True:
                        if not obj.parent:
                            break
                        obj = obj.parent
                        if obj.type == "EMPTY" and obj.sm64_obj_type == "Level Root":
                            break
                if obj is None or obj.sm64_obj_type != "Level Root":
                    raise PluginError("Cannot find level empty.")
                selectSingleObject(obj)

            scaleValue = context.scene.fast64.sm64.blender_to_sm64_scale
            final_transform = mathutils.Matrix.Diagonal(mathutils.Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set
        try:
            self.store_object_data()

            applyRotation([obj], math.radians(90), "X")

            props = context.scene.fast64.sm64.combined_export
            export_path, level_name = props.base_level_path, props.export_level_name
            if props.is_custom_level:
                triggerName = "sCam" + level_name.title().replace(" ", "").replace("_", "")
            else:
                triggerName = cameraTriggerNames[level_name]

            if not props.non_decomp_level:
                applyBasicTweaks(export_path)
            fileStatus = exportLevelC(
                obj,
                final_transform,
                level_name,
                export_path,
                context.scene.saveTextures,
                props.non_decomp_level,
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


sm64_level_classes = (SM64_ExportLevel,)


def sm64_level_register():
    for cls in sm64_level_classes:
        register_class(cls)


def sm64_level_unregister():
    for cls in reversed(sm64_level_classes):
        unregister_class(cls)
