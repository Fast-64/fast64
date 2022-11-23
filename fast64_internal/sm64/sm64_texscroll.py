import os, re, bpy
from ..utility import PluginError, writeIfNotFound, getDataFromFile, saveDataToFile
from .c_templates.tile_scroll import tile_scroll_c, tile_scroll_h
from .sm64_utility import getMemoryCFilePath

# This is for writing framework for scroll code.
# Actual scroll code found in f3d_gbi.py (FVertexScrollData)


class SM64TexScrollFileStatus:
    def __init__(self):
        self.starSelectC = False


def readSegmentInfo(baseDir):
    ldPath = os.path.join(baseDir, "sm64.ld")
    ldFile = open(ldPath, "r", newline="\n")
    ldData = ldFile.read()
    ldFile.close()

    compressionFmt = bpy.context.scene.compressionFormat
    segDict = {}
    for matchResult in re.finditer(
        "(?<!#define )STANDARD\_OBJECTS\(" + "(((?!\,).)*)\,\s*(((?!\,).)*)\,\s*(((?!\)).)*)\)", ldData
    ):
        segDict[matchResult.group(1).strip()] = (
            "_" + matchResult.group(1) + "_" + compressionFmt + "SegmentRomStart",
            int(matchResult.group(3).strip()[2:4], 16),
            int(matchResult.group(5).strip()[2:4], 16),
        )

    levelPath = os.path.join(baseDir, "levels/level_defines.h")
    levelFile = open(levelPath, "r", newline="\n")
    levelData = levelFile.read()
    levelFile.close()
    for matchResult in re.finditer(
        "DEFINE\_LEVEL\(\s*"
        + "(((?!\,).)*)\,\s*"
        + "(((?!\,).)*)\,\s*"  # internal name
        + "(((?!\,).)*)\,\s*"  # level enum
        + "(((?!\,).)*)\,\s*"  # course enum
        + "(((?!\,).)*)\,\s*"  # folder name
        + "(((?!\,).)*)\,\s*"  # texture bin
        + "(((?!\,).)*)\,\s*"  # acoustic reach
        + "(((?!\,).)*)\,\s*"  # echo level 1
        + "(((?!\,).)*)\,\s*"  # echo level 2
        + "(((?!\,).)*)\,\s*"  # echo level 3
        + "(((?!\)).)*)\)",  # dynamic music table  # camera table
        levelData,
    ):
        segDict[matchResult.group(7).strip()] = ("_" + matchResult.group(7) + "_segment_7SegmentRomStart", 7, None)
    return segDict


def writeSegmentROMTable(baseDir):
    memPath = getMemoryCFilePath(baseDir)
    memFile = open(memPath, "r", newline="\n")
    memData = memFile.read()
    memFile.close()

    if "uintptr_t sSegmentROMTable[32];" not in memData:
        memData = re.sub(
            "(?<!extern )uintptr\_t sSegmentTable\[32\]\;",
            "\nuintptr_t sSegmentTable[32];\nuintptr_t sSegmentROMTable[32];",
            memData,
            re.DOTALL,
        )

        memData = re.sub(
            "set\_segment\_base\_addr\s*\((((?!\)).)*)\)\s*;",
            r"set_segment_base_addr(\1); sSegmentROMTable[segment] = (uintptr_t) srcStart;",
            memData,
            re.DOTALL,
        )

        memFile = open(memPath, "w", newline="\n")
        memFile.write(memData)
        memFile.close()

    # Add extern definition of segment table
    writeIfNotFound(os.path.join(baseDir, "src/game/memory.h"), "\nextern uintptr_t sSegmentROMTable[32];", "#endif")


def writeScrollTextureCall(path, include, callString):
    data = getDataFromFile(path)
    if include not in data:
        data = include + "\n" + data

        callScrollIndex = data.index(callString)
        if callScrollIndex != -1:
            callScrollIndex += len(callString)
            data = data[:callScrollIndex] + " scroll_textures();" + data[callScrollIndex:]
        else:
            raise PluginError("Cannot find " + callString + " in " + path)

        saveDataToFile(path, data)


TILE_SCROLL_REL_PATH = "src/game/tile_scroll"


def writeTileScrollFiles(baseDir):
    tile_scroll_path = os.path.join(baseDir, TILE_SCROLL_REL_PATH)
    tile_scroll_c_path = f"{tile_scroll_path}.c"
    tile_scroll_h_path = f"{tile_scroll_path}.h"

    if not os.path.exists(tile_scroll_c_path):
        with open(tile_scroll_c_path, "w", newline="\n") as tile_c_fp:
            tile_c_fp.write(tile_scroll_c)

    if not os.path.exists(tile_scroll_h_path):
        with open(tile_scroll_h_path, "w", newline="\n") as tile_h_fp:
            tile_h_fp.write(tile_scroll_h)


def writeTexScrollBase(baseDir):
    fileStatus = SM64TexScrollFileStatus()
    writeSegmentROMTable(baseDir)

    # Create texscroll.inc.h
    texscrollHPath = os.path.join(baseDir, "src/game/texscroll.h")
    if not os.path.exists(texscrollHPath):
        texscrollHFile = open(texscrollHPath, "w", newline="\n")

        texscrollHFile.write(
            "#ifndef TEXSCROLL_H\n" + "#define TEXSCROLL_H\n\n" + "extern void scroll_textures();\n\n" + "#endif\n"
        )

        texscrollHFile.close()

    # Create texscroll.inc.c
    texscrollCPath = os.path.join(baseDir, "src/game/texscroll.c")
    if not os.path.exists(texscrollCPath):
        texscrollCFile = open(texscrollCPath, "w", newline="\n")
        scrollData = (
            '#include "types.h"\n'
            + '#include "include/segment_symbols.h"\n'
            + '#include "memory.h"\n'
            + '#include "engine/math_util.h"\n'
            + '#include "src/engine/behavior_script.h"\n'
            + '#include "tile_scroll.h"\n'
            + '#include "texscroll.h"\n\n'
        )

        # Write global texture load function here
        # Write material.inc.c
        # Write update_materials

        scrollData += "void scroll_textures() {\n}\n"

        texscrollCFile.write(scrollData)
        texscrollCFile.close()

    texscrollCFile = open(texscrollCPath, "r", newline="\n")
    scrollData = texscrollCFile.read()
    texscrollCFile.close()

    texScrollIncludeDef = '#include "texscroll.h"'
    macroIndex = scrollData.index(texScrollIncludeDef)

    update_tex_scroll = False

    if '#include "tile_scroll.h"' not in scrollData:
        scrollData = scrollData[:macroIndex] + '#include "tile_scroll.h"\n' + scrollData[macroIndex:]
        macroIndex = scrollData.index(texScrollIncludeDef)
        update_tex_scroll = True

    scrollConditionDefine = (
        "#ifdef TARGET_N64\n"
        + "#define SCROLL_CONDITION(condition) condition\n"
        + "#else\n"
        + "#define SCROLL_CONDITION(condition) 1\n"
        + "#endif\n"
    )
    if "#define SCROLL_CONDITION" not in scrollData:
        if macroIndex != -1:
            macroIndex += len(texScrollIncludeDef)
            scrollData = scrollData[:macroIndex] + "\n\n" + scrollConditionDefine + scrollData[macroIndex:]
            update_tex_scroll = True
        else:
            raise PluginError('Cannot find \'#include "texscroll.h" in src/game/texscroll.c')

    if update_tex_scroll:
        with open(texscrollCPath, "w", newline="\n") as texscrollCFile:
            texscrollCFile.write(scrollData)

    # Create texscroll folder for groups
    texscrollDirPath = os.path.join(baseDir, "src/game/texscroll")
    if not os.path.exists(texscrollDirPath):
        os.mkdir(texscrollDirPath)

    # parse level_defines.h
    # create texscroll.inc.c/h in each level folder
    # Don't have to make level scroll function, but should call scroll of groups/common

    writeScrollTextureCall(
        os.path.join(baseDir, "src/game/level_update.c"), '#include "texscroll.h"', "changeLevel = play_mode_normal();"
    )

    starSelectPath = os.path.join(baseDir, "src/menu/star_select.c")
    if os.path.exists(starSelectPath):
        writeScrollTextureCall(starSelectPath, '#include "src/game/texscroll.h"', "area_update_objects();")
        fileStatus.starSelectC = True

    # Weird encoding error in this file?
    # writeScrollTextureCall(os.path.join(baseDir, 'src/menu/file_select.c'),
    # 	'#include "src/game/texscroll.h"', 'area_update_objects();')

    # writeScrollTextureCall(os.path.join(baseDir, 'src/menu/level_select_menu.c'),
    # 	'#include "src/game/texscroll.h"', 's32 retVar;')

    # write tile scroll files
    writeTileScrollFiles(baseDir)

    return fileStatus


def createTexScrollHeadersGroup(exportDir, groupName, dataInclude):
    includeH = "src/game/texscroll/" + groupName + "_texscroll.inc.h"
    includeC = "src/game/texscroll/" + groupName + "_texscroll.inc.c"

    # Create base scroll files
    fileStatus = writeTexScrollBase(exportDir)

    # Create group inc.h
    groupPathH = os.path.join(exportDir, includeH)
    if not os.path.exists(groupPathH):
        groupFileH = open(groupPathH, "w", newline="\n")
        groupDataH = "extern void scroll_textures_" + groupName + "();\n"
        groupFileH.write(groupDataH)
        groupFileH.close()

    # Create group inc.c
    groupPathC = os.path.join(exportDir, includeC)
    if not os.path.exists(groupPathC):
        groupFileC = open(groupPathC, "w", newline="\n")
        groupDataC = dataInclude + "\n"
        groupDataC += "void scroll_textures_" + groupName + "() {\n}\n"
        groupFileC.write(groupDataC)
        groupFileC.close()

    # Include group inc.h in texscroll.h
    texscrollPathH = os.path.join(exportDir, "src/game/texscroll.h")
    texscrollFileH = open(texscrollPathH, "r", newline="\n")
    texscrollDataH = texscrollFileH.read()
    texscrollFileH.close()

    includeHText = '#include "' + includeH + '"'
    if includeHText not in texscrollDataH:
        scrollIndex = texscrollDataH.index("extern void scroll_textures();")
        if scrollIndex != -1:
            texscrollDataH = texscrollDataH[:scrollIndex] + includeHText + "\n" + texscrollDataH[scrollIndex:]
        else:
            raise PluginError("Texture scroll function not found.")

        texscrollFileH = open(texscrollPathH, "w", newline="\n")
        texscrollFileH.write(texscrollDataH)
        texscrollFileH.close()

    # Include group inc.c in texscroll.c
    includeCText = '#include "' + includeC + '"'
    texscrollPathC = os.path.join(exportDir, "src/game/texscroll.c")
    texscrollFileC = open(texscrollPathC, "r", newline="\n")
    texscrollDataC = texscrollFileC.read()
    texscrollFileC.close()
    originalTexScrollC = texscrollDataC

    if includeCText not in texscrollDataC:
        scrollIndex = texscrollDataC.index("void scroll_textures()")
        if scrollIndex != -1:
            texscrollDataC = texscrollDataC[:scrollIndex] + includeCText + "\n" + texscrollDataC[scrollIndex:]
        else:
            raise PluginError("Texture scroll function not found.")

    # Call group scroll function in scroll_textures()
    groupDict = readSegmentInfo(exportDir)
    segment = groupDict[groupName][1]
    segmentRomStart = groupDict[groupName][0]

    groupFunctionCall = (
        "if(SCROLL_CONDITION(sSegmentROMTable["
        + hex(segment)
        + "] == (uintptr_t)"
        + segmentRomStart
        + ")) {\n"
        + "\t\tscroll_textures_"
        + groupName
        + "();\n\t}\n"
    )

    callWithoutMacro = (
        "if(sSegmentROMTable["
        + hex(segment)
        + "] == (uintptr_t)"
        + segmentRomStart
        + ") {\n"
        + "\t\tscroll_textures_"
        + groupName
        + "();\n\t}\n"
    )

    matchResult = re.search("void\s*scroll\_textures" + "\s*\(\)\s*\{\s*(.*)\n\}", texscrollDataC, re.DOTALL)
    if matchResult:
        functionCalls = matchResult.group(1)

        if groupFunctionCall not in functionCalls:
            functionCalls += "\n\t" + groupFunctionCall

        # Handle case with old function calls
        if callWithoutMacro in functionCalls:
            functionCalls = functionCalls.replace(callWithoutMacro, "")

        texscrollDataC = texscrollDataC[: matchResult.start(1)] + functionCalls + texscrollDataC[matchResult.end(1) :]
    else:
        raise PluginError("Texture scroll function not found.")

    if originalTexScrollC != texscrollDataC:
        texscrollFileC = open(texscrollPathC, "w", newline="\n")
        texscrollFileC.write(texscrollDataC)
        texscrollFileC.close()

    return fileStatus


def writeTexScrollHeadersLevel(exportDir, includeC, includeH, groupName, scrollDefines):
    pass


def modifyTexScrollHeadersGroup(exportDir, includeC, includeH, groupName, scrollDefines, dataInclude, hasScrolling):
    if not bpy.context.scene.disableScroll and hasScrolling:
        fileStatus = writeTexScrollHeadersGroup(exportDir, includeC, includeH, groupName, scrollDefines, dataInclude)
        return fileStatus
    else:
        removeTexScrollHeadersGroup(exportDir, includeC, includeH, groupName, scrollDefines, dataInclude)
        return None


def writeTexScrollHeadersGroup(exportDir, includeC, includeH, groupName, scrollDefines, dataInclude):

    # Create group scroll files
    fileStatus = createTexScrollHeadersGroup(exportDir, groupName, dataInclude)

    # Write to group inc.h
    groupPathH = os.path.join(exportDir, "src/game/texscroll/" + groupName + "_texscroll.inc.h")
    groupFileH = open(groupPathH, "r", newline="\n")
    groupDataH = groupFileH.read()
    groupFileH.close()

    if includeH not in groupDataH:
        groupDataH = includeH + "\n" + groupDataH
        groupFileH = open(groupPathH, "w", newline="\n")
        groupFileH.write(groupDataH)
        groupFileH.close()

    # Write to group inc.c
    groupPathC = os.path.join(exportDir, "src/game/texscroll/" + groupName + "_texscroll.inc.c")
    groupFileC = open(groupPathC, "r", newline="\n")
    groupDataC = groupFileC.read()
    groupFileC.close()
    originalGroupDataC = groupDataC

    includeIndex = groupDataC.index("void scroll_textures_" + groupName + "()")
    if includeIndex != -1:
        if includeC not in groupDataC:
            groupDataC = groupDataC[:includeIndex] + includeC + "\n" + groupDataC[includeIndex:]
    else:
        raise PluginError("Could not find include string index.")

    # Call actor scroll functions in group scroll function
    # The last function will be the one that calls all the others
    scrollFunction = scrollDefines.split("extern void ")[-1]
    matchResult = re.search(
        "void\s*scroll\_textures\_" + re.escape(groupName) + "\s*\(\)\s*{\s*" + "(((?!\}).)*)\}", groupDataC, re.DOTALL
    )
    if matchResult:
        functionCalls = matchResult.group(1)
        if scrollFunction not in functionCalls:
            functionCalls += "\t" + scrollFunction
        groupDataC = groupDataC[: matchResult.start(1)] + functionCalls + groupDataC[matchResult.end(1) :]
    else:
        raise PluginError("Texture scroll function not found.")

    if originalGroupDataC != groupDataC:
        groupFileC = open(groupPathC, "w", newline="\n")
        groupFileC.write(groupDataC)
        groupFileC.close()

    return fileStatus


def removeTexScrollHeadersGroup(exportDir, includeC, includeH, groupName, scrollDefines, dataInclude):

    includeH += "\n"
    includeC += "\n"

    # Remove include from group inc.h
    groupPathH = os.path.join(exportDir, "src/game/texscroll/" + groupName + "_texscroll.inc.h")
    if os.path.exists(groupPathH):
        groupFileH = open(groupPathH, "r", newline="\n")
        groupDataH = groupFileH.read()
        groupFileH.close()

        if includeH in groupDataH:
            groupDataH = groupDataH.replace(includeH, "")
            groupFileH = open(groupPathH, "w", newline="\n")
            groupFileH.write(groupDataH)
            groupFileH.close()

    # Remove include and function call from group inc.c
    groupPathC = os.path.join(exportDir, "src/game/texscroll/" + groupName + "_texscroll.inc.c")
    if os.path.exists(groupPathC):
        groupFileC = open(groupPathC, "r", newline="\n")
        groupDataC = groupFileC.read()
        groupFileC.close()
        originalGroupDataC = groupDataC

        if includeC in groupDataC:
            groupDataC = groupDataC.replace(includeC, "")

        scrollFunction = scrollDefines.split("extern void ")[-1]
        matchResult = re.search(
            "void\s*scroll\_textures\_" + re.escape(groupName) + "\s*\(\)\s*{\s*" + "(((?!\}).)*)\}",
            groupDataC,
            re.DOTALL,
        )
        if matchResult:
            functionCalls = matchResult.group(1)
            functionCalls = functionCalls.replace(scrollFunction, "")
            groupDataC = groupDataC[: matchResult.start(1)] + functionCalls + groupDataC[matchResult.end(1) :]

        if originalGroupDataC != groupDataC:
            groupFileC = open(groupPathC, "w", newline="\n")
            groupFileC.write(groupDataC)
            groupFileC.close()


def modifyTexScrollFiles(exportDir, assetDir, header, data, hasScrolling):
    if not bpy.context.scene.disableScroll and hasScrolling:
        writeTexScrollFiles(exportDir, assetDir, header, data)
    else:
        removeTexScrollFiles(exportDir, assetDir)


def removeTexScrollFiles(exportDir, assetDir):
    texscrollCPath = os.path.join(assetDir, "texscroll.inc.c")
    texscrollHPath = os.path.join(assetDir, "texscroll.inc.h")
    if os.path.exists(texscrollCPath):
        os.remove(texscrollCPath)
    if os.path.exists(texscrollHPath):
        os.remove(texscrollHPath)


def writeTexScrollFiles(exportDir, assetDir, header, data):
    texscrollCPath = os.path.join(assetDir, "texscroll.inc.c")
    texscrollHPath = os.path.join(assetDir, "texscroll.inc.h")

    texscrollCFile = open(texscrollCPath, "w", newline="\n")
    texscrollCFile.write(data)
    texscrollCFile.close()

    texscrollHFile = open(texscrollHPath, "w", newline="\n")
    texscrollHFile.write(header)
    texscrollHFile.close()
