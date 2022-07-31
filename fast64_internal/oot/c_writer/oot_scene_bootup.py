import os, re, bpy
import string
from bpy.utils import register_class, unregister_class
from ...utility import PluginError, writeFile
from ..oot_constants import ootEnumHeaderMenuComplete
from typing import Callable, Iterable, Any, List

# note: current regex relies on formatting convention to find function bracket close (i.e. "\n}")


def setBootupScene(exportPath: str, entranceIndex: str, options: Any):
    editTitleSetup(exportPath, "SET_NEXT_GAMESTATE(&this->state, FileSelect_Init, FileSelectState);")
    if options.bootMode == "Play":
        editFileSelect(exportPath, entranceIndex, options, setFileSelectInit, setFileSelectLoadGame)
    else:
        editFileSelect(exportPath, "", None, clearFileSelectInit, clearFileSelectLoadGame)
    editSramInitSave(exportPath, entranceIndex, options, setSramInitSave)


def clearBootupScene(exportPath: str):
    editTitleSetup(exportPath, "SET_NEXT_GAMESTATE(&this->state, ConsoleLogo_Init, ConsoleLogoState);")
    editFileSelect(exportPath, "", None, clearFileSelectInit, clearFileSelectLoadGame)
    editSramInitSave(exportPath, "", None, clearSramInitSave)


# modify save init to ignore file 1 specific code (for debug map select)
def editSramInitSave(
    exportPath: str, entranceIndex: str, options: Any, editSramInitFunction: Callable[[str, Any], str]
):
    try:
        editSramFilepath = os.path.join(exportPath, "src/code/z_sram.c")
        with open(editSramFilepath) as file:
            fileData = file.read()

            # editing Sram_InitSave()
            match = re.search(
                r"void\s*Sram\_InitSave\s*\((((?!\)).)*)\)\s*\{(((?!\n\}).)*)\n\}", fileData, flags=re.DOTALL
            )
            if match:
                functionContents = match.group(3)
                newContents = editSramInitFunction(functionContents, entranceIndex, options)
                newData = fileData[: match.start(3)] + newContents + fileData[match.end(3) :]

                if newData != fileData:
                    writeFile(editSramFilepath, newData)

    except FileNotFoundError:
        raise PluginError("ERROR: Can't find Sram_InitSave() in src/code/z_ram.c.")


def setSramInitSave(functionContents: str, entranceIndex: str, options: Any):
    newContents = functionContents

    # disables file 1 specific code
    newContents = re.sub(
        r"if\s*\(fileSelect-\>buttonIndex\s*==\s*0\s*\)",
        "if (fileSelect->buttonIndex == 0 && false)",
        newContents,
        flags=re.DOTALL,
    )
    newContents = re.sub(
        r"if\s*\(fileSelect-\>buttonIndex\s*\!=\s*0\s*\)",
        "if (fileSelect->buttonIndex != 0 || true)",
        newContents,
        flags=re.DOTALL,
    )

    # sets entrance index
    newContents = addOrModifyAssignment(newContents, "gSaveContext.entranceIndex", entranceIndex)

    # overrides other properties for header
    if options.overrideHeader:
        timeOfDay, linkAge = getParamsFromOptions(options)

        newContents = addOrModifyAssignment(newContents, "gSaveContext.dayTime", timeOfDay)
        newContents = addOrModifyAssignment(newContents, "gSaveContext.linkAge", linkAge)

        if options.headerOption == "Cutscene":
            cutsceneIndex = "0xFFF" + format(options.cutsceneIndex - 4, "X")
            newContents = addOrModifyAssignment(newContents, "gSaveContext.cutsceneIndex", cutsceneIndex)
        else:
            newContents = addOrModifyAssignment(newContents, "gSaveContext.cutsceneIndex", "0")
    else:
        newContents = addOrModifyAssignment(newContents, "gSaveContext.dayTime", "CLOCK_TIME(10, 0)")
        newContents = addOrModifyAssignment(newContents, "gSaveContext.cutsceneIndex", "0")
        newContents = addOrModifyAssignment(newContents, "gSaveContext.linkAge", "LINK_AGE_CHILD")

    return newContents


def clearSramInitSave(functionContents: str, entranceIndex: str, options: Any):
    newContents = functionContents

    # enables file 1 specific code
    newContents = re.sub(
        r"if\s*\(fileSelect-\>buttonIndex\s*\!=\s*0\s*\|\|\s*true\s*\)",
        "if (fileSelect->buttonIndex != 0)",
        newContents,
        flags=re.DOTALL,
    )
    newContents = re.sub(
        r"if\s*\(fileSelect-\>buttonIndex\s*==\s*0\s*\&\&\s*false\s*\)",
        "if (fileSelect->buttonIndex == 0)",
        newContents,
        flags=re.DOTALL,
    )

    # restores default settings
    newContents = addOrModifyAssignment(newContents, "gSaveContext.entranceIndex", "ENTR_LINK_HOME_0")
    newContents = addOrModifyAssignment(newContents, "gSaveContext.dayTime", "CLOCK_TIME(10, 0)")
    newContents = addOrModifyAssignment(newContents, "gSaveContext.cutsceneIndex", "0xFFF1")
    newContents = addOrModifyAssignment(newContents, "gSaveContext.linkAge", "LINK_AGE_CHILD")

    return newContents


# modify setup init to skip console logo and go straight to file select, or revert this process
def editTitleSetup(exportPath: str, gameStateFunction: str):
    try:
        titleSetupFilepath = os.path.join(exportPath, "src/code/title_setup.c")
        with open(titleSetupFilepath) as file:
            fileData = file.read()

            # editing Setup_InitImpl()
            match = re.search(
                r"void\s*Setup\_InitImpl\s*\((((?!\)).)*)\)\s*\{(((?!\n\}).)*)\n\}", fileData, flags=re.DOTALL
            )
            if match:
                functionContents = match.group(3)
                newContents = (
                    re.sub(r"SET_NEXT_GAMESTATE\s*\((((?!\)).)*)\)\s*;", "", functionContents, flags=re.DOTALL)
                    + gameStateFunction
                )
                newData = fileData[: match.start(3)] + newContents + fileData[match.end(3) :]

                if newData != fileData:
                    writeFile(titleSetupFilepath, newData)

    except FileNotFoundError:
        raise PluginError("ERROR: Can't find Setup_InitImpl() in src/code/title_setup.c.")


# modify file select to immediately load the first save and override entrance index, or reverse this process
def editFileSelect(
    exportPath: str,
    entranceIndex: str,
    options: Any,
    editInitFunction: Callable[[str], str],
    editLoadGameFunction: Callable[[str, str, Any], str],
):
    try:
        fileSelectPath = os.path.join(exportPath, "src/overlays/gamestates/ovl_file_choose/z_file_choose.c")
        with open(fileSelectPath) as file:
            fileData = file.read()
            newData = fileData

            # editing FileSelect_Init()
            match = re.search(
                r"void\s*FileSelect\_Init\s*\((((?!\)).)*)\)\s*\{(((?!\n\}).)*)\n\}", newData, flags=re.DOTALL
            )
            if match:
                functionContents = match.group(3)
                newContents = editInitFunction(functionContents)
                newData = newData[: match.start(3)] + newContents + newData[match.end(3) :]
            else:
                raise PluginError(
                    "ERROR: Can't find FileSelect_Init() in src/overlays/gamestates/ovl_file_choose/z_file_choose.c."
                )

            match = None
            newContents = None

            # editing FileSelect_LoadGame()
            match = re.search(
                r"void\s*FileSelect\_LoadGame\s*\((((?!\)).)*)\)\s*\{(((?!\n\}).)*)\n\}", newData, flags=re.DOTALL
            )
            if match:
                functionContents = match.group(3)
                newContents = editLoadGameFunction(functionContents, entranceIndex, options)
                newData = newData[: match.start(3)] + newContents + newData[match.end(3) :]
            else:
                raise PluginError(
                    "ERROR: Can't find FileSelect_LoadGame() in src/overlays/gamestates/ovl_file_choose/z_file_choose.c."
                )

            if newData != fileData:
                writeFile(fileSelectPath, newData)

    except FileNotFoundError:
        raise PluginError("ERROR: Can't open src/overlays/gamestates/ovl_file_choose/z_file_choose.c")


def setFileSelectInit(functionContents: str) -> str:
    # removes file select audio blip on map load (not completely necessary)
    newContents = re.sub(r"func_800F5E18\s*\((((?!\)).)*)\)\s*;", "", functionContents, flags=re.DOTALL)

    # immediately loads first save on init
    if not "FileSelect_LoadGame" in newContents:
        newContents += "FileSelect_LoadGame(thisx);"

    return newContents


def setFileSelectLoadGame(functionContents: str, entranceIndex: str, options: Any) -> str:
    newContents = functionContents

    # disables file 1 specific code
    newContents = re.sub(
        r"if\s*\(this-\>buttonIndex\s*==\s*FS\_BTN\_SELECT\_FILE\_1\s*\)",
        "if (this->buttonIndex == FS_BTN_SELECT_FILE_1 && false)",
        newContents,
        flags=re.DOTALL,
    )

    saveFileNameData = ", ".join(["0x" + format(i, "02X") for i in stringToSaveNameBytes(options.newGameName)])

    # adds empty file check
    if "SLOT_OCCUPIED" not in newContents:
        newContents += (
            f"\n\tif (!SLOT_OCCUPIED((&this->sramCtx), this->buttonIndex)) {{"
            f"\n\t\tu8 name[] = {{ {saveFileNameData} }};"
            f"\n\t\tthis->n64ddFlag = 0;"  # note this is normally called in FileSelect_Main, which would be skipped in this case
            f"\n\t\tMemCpy(&this->fileNames[this->buttonIndex][0], &name, sizeof(name));"
            f"\n\t\tSram_InitSave(this, &this->sramCtx);"
            f"\n\t}}"
        )
    else:
        newContents = re.sub(
            r"u8\s*name\s*\[((?!;).)*;", f"u8 name[] = {{ {saveFileNameData} }};", newContents, flags=re.DOTALL
        )

    # if we only want to change settings for new game, then we wouldn't write this here.
    if not options.newGameOnly:

        # overrides entrance index
        newContents = addOrModifyAssignment(newContents, "gSaveContext.entranceIndex", entranceIndex)

        # overrides other properties for header
        if options.overrideHeader:
            timeOfDay, linkAge = getParamsFromOptions(options)

            newContents = addOrModifyAssignment(newContents, "gSaveContext.nextDayTime", timeOfDay)
            newContents = addOrModifyAssignment(newContents, "gSaveContext.linkAge", linkAge)

            if options.headerOption == "Cutscene":
                cutsceneIndex = "0xFFF" + format(options.cutsceneIndex - 4, "X")
                newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", cutsceneIndex)
            else:
                newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", "0xFFEF")

        else:
            newContents = addOrModifyAssignment(newContents, "gSaveContext.nextDayTime", "NEXT_TIME_NONE")
            newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", "0xFFEF")
            newContents = removeAssignment(newContents, "gSaveContext.linkAge")

    else:
        newContents = removeAssignment(newContents, "gSaveContext.entranceIndex")
        newContents = addOrModifyAssignment(newContents, "gSaveContext.nextDayTime", "NEXT_TIME_NONE")
        newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", "0xFFEF")
        newContents = removeAssignment(newContents, "gSaveContext.linkAge")

    return newContents


def clearFileSelectInit(functionContents: str) -> str:
    # removes file select auto loading
    newContents = re.sub(r"FileSelect\_LoadGame\s*\((((?!\)).)*)\)\s*;", "", functionContents, flags=re.DOTALL)

    # restores file select audio
    if not "func_800F5E18" in newContents:
        newContents += "func_800F5E18(SEQ_PLAYER_BGM_MAIN, NA_BGM_FILE_SELECT, 0, 7, 1);"

    return newContents


# entranceIndex and options will have empty/null values, this is just to match the paired function's signature
def clearFileSelectLoadGame(functionContents: str, entranceIndex: str, options: Any) -> str:

    # restores map select
    newContents = functionContents

    # re enables file 1 specific code
    newContents = re.sub(
        r"if\s*\(this-\>buttonIndex\s*==\s*FS\_BTN\_SELECT\_FILE\_1\s*\&\&\s*false\s*\)",
        "if (this->buttonIndex == FS_BTN_SELECT_FILE_1)",
        newContents,
        flags=re.DOTALL,
    )

    # removes empty file check
    newContents = re.sub(
        r"(\n\s*)?if\s*\(\!SLOT\_OCCUPIED\(\(\s*\&this-\>sramCtx\s*\),\s*this-\>buttonIndex\s*\)\)\s*\{(((?!\n\s+\}).)*)\n\s+\}",
        "",
        newContents,
        flags=re.DOTALL,
    )

    # restores default settings
    newContents = removeAssignment(newContents, "gSaveContext.entranceIndex")
    newContents = addOrModifyAssignment(newContents, "gSaveContext.nextDayTime", "NEXT_TIME_NONE")
    newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", "0xFFEF")
    newContents = removeAssignment(newContents, "gSaveContext.linkAge")

    return newContents


def addOrModifyAssignment(data: str, name: str, value: str) -> str:
    setSceneMatch = re.search(re.escape(name) + r"\s*=\s*(((?!;).)*)\s*;", data, re.DOTALL)
    if setSceneMatch:
        data = data[: setSceneMatch.start(1)] + value + data[setSceneMatch.end(1) :]
    else:
        data += "\n\t" + name + " = " + value + ";"

    return data


def removeAssignment(data: str, name: str) -> str:
    return re.sub("(\n\t)?" + re.escape(name) + r"\s*=\s*([a-zA-Z0-9_]*)\s*;", "", data, flags=re.DOTALL)


def getParamsFromOptions(options: Any) -> tuple[str, str]:
    timeOfDay = (
        "NEXT_TIME_DAY"
        if options.headerOption == "Child Day" or options.headerOption == "Adult Day"
        else "NEXT_TIME_NIGHT"
    )

    linkAge = (
        "LINK_AGE_ADULT"
        if options.headerOption == "Adult Day" or options.headerOption == "Adult Night"
        else "LINK_AGE_CHILD"
    )

    return timeOfDay, linkAge


# converts ascii text to format for save file name.
# see src/code/z_message_PAL.c:Message_Decode()
def stringToSaveNameBytes(name: str) -> bytearray:
    specialChar = {
        " ": 0x3E,
        ".": 0x40,
        "-": 0x3F,
    }

    result = bytearray([0x3E] * 8)

    if len(name) > 8:
        raise PluginError("Save file name for scene bootup must be 8 characters or less.")
    for i in range(len(name)):
        value = ord(name[i])
        if name[i] in specialChar:
            result[i] = specialChar[name[i]]
        elif value >= ord("0") and value <= ord("9"):  # numbers
            result[i] = value - ord("0")
        elif value >= ord("A") and value <= ord("Z"):  # uppercase
            result[i] = value - ord("7")
        elif value >= ord("a") and value <= ord("z"):  # lowercase
            result[i] = value - ord("=")
        else:
            raise PluginError(
                name + " has some invalid characters and cannot be used as a save file name for scene bootup."
            )

    return result


class OOT_ClearBootupScene(bpy.types.Operator):
    bl_idname = "object.oot_clear_bootup_scene"
    bl_label = "Undo Boot To Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        clearBootupScene(bpy.path.abspath(context.scene.ootDecompPath))
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


ootEnumBootMode = [("Play", "Play", "Play"), ("File Select", "File Select", "File Select")]


class OOTBootupSceneOptions(bpy.types.PropertyGroup):
    bootToScene: bpy.props.BoolProperty(default=False, name="Boot To Scene")
    overrideHeader: bpy.props.BoolProperty(default=False, name="Override Header")
    headerOption: bpy.props.EnumProperty(items=ootEnumHeaderMenuComplete, name="Header", default="Child Day")
    spawnIndex: bpy.props.IntProperty(name="Spawn", min=0)
    newGameOnly: bpy.props.BoolProperty(default=False, name="Override Scene On New Game Only")
    newGameName: bpy.props.StringProperty(default="Link", name="New Game Name")
    bootMode: bpy.props.EnumProperty(default="Play", name="Boot Mode", items=ootEnumBootMode)

    # see src/code/z_play.c:Play_Init() - can't access more than 16 cutscenes?
    cutsceneIndex: bpy.props.IntProperty(min=4, max=19, default=4, name="Cutscene Index")


def ootSceneBootupRegister():
    register_class(OOTBootupSceneOptions)
    register_class(OOT_ClearBootupScene)
    bpy.types.Scene.ootBootupSceneOptions = bpy.props.PointerProperty(type=OOTBootupSceneOptions)


def ootSceneBootupUnregister():
    unregister_class(OOTBootupSceneOptions)
    unregister_class(OOT_ClearBootupScene)
    del bpy.types.Scene.ootBootupSceneOptions
