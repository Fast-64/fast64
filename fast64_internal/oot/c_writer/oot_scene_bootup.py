import os, re, bpy
from bpy.utils import register_class, unregister_class
from ...utility import PluginError, writeFile
from ..oot_constants import ootEnumHeaderMenuComplete
from typing import Callable, Iterable, Any

# note: current regex relies on formatting convention to find function bracket close (i.e. "\n}")

def setBootupScene(exportPath : str, entranceIndex : str, options : Any):
    editTitleSetup(exportPath, "SET_NEXT_GAMESTATE(&this->state, FileSelect_Init, FileSelectState);")
    editFileSelect(exportPath, entranceIndex, options, setFileSelectInit, setFileSelectLoadGame)

def clearBootupScene(exportPath : str):
    editTitleSetup(exportPath, "SET_NEXT_GAMESTATE(&this->state, ConsoleLogo_Init, ConsoleLogoState);")
    editFileSelect(exportPath, "", None, clearFileSelectInit, clearFileSelectLoadGame)

# modify setup init to skip console logo and go straight to file select, or revert this process
def editTitleSetup(exportPath : str, gameStateFunction : str):
    try:
        titleSetupFilepath = os.path.join(exportPath, "src/code/title_setup.c")
        with open(titleSetupFilepath) as file:
            fileData = file.read()

            # editing Setup_InitImpl()
            match = re.search(r"void\s*Setup\_InitImpl\s*\((((?!\)).)*)\)\s*\{(((?!\n\}).)*)\n\}", fileData, re.DOTALL)
            if match:
                functionContents = match.group(3)
                newContents = re.sub(r"SET_NEXT_GAMESTATE\s*\((((?!\)).)*)\)\s*;", "", functionContents, flags=re.DOTALL) +\
                    gameStateFunction
                newData = fileData[:match.start(3)] + newContents + fileData[match.end(3):]

                if newData != fileData:
                    writeFile(titleSetupFilepath, newData)

    except FileNotFoundError:
        raise PluginError("ERROR: Can't find Setup_InitImpl() in src/code/title_setup.c.")

# modify file select to immediately load the first save and override entrance index, or reverse this process
def editFileSelect(exportPath : str, entranceIndex : str, options : Any, 
    editInitFunction : Callable[[str], str], editLoadGameFunction : Callable[[str, str, Any], str]):    
    try:
        fileSelectPath = os.path.join(exportPath, "src/overlays/gamestates/ovl_file_choose/z_file_choose.c")
        with open(fileSelectPath) as file:
            fileData = file.read()
            newData = fileData

            # editing FileSelect_Init()
            match = re.search(r"void\s*FileSelect\_Init\s*\((((?!\)).)*)\)\s*\{(((?!\n\}).)*)\n\}", newData, re.DOTALL)
            if match:
                functionContents = match.group(3)
                newContents = editInitFunction(functionContents)
                newData = newData[:match.start(3)] + newContents + newData[match.end(3):]
            else:
                raise PluginError("ERROR: Can't find FileSelect_Init() in src/overlays/gamestates/ovl_file_choose/z_file_choose.c.")

            match = None
            newContents = None

            # editing FileSelect_LoadGame()
            match = re.search(r"void\s*FileSelect\_LoadGame\s*\((((?!\)).)*)\)\s*\{(((?!\n\}).)*)\n\}", newData, re.DOTALL)
            if match:
                functionContents = match.group(3)
                newContents = editLoadGameFunction(functionContents, entranceIndex, options)
                newData = newData[:match.start(3)] + newContents + newData[match.end(3):]
            else:
                raise PluginError("ERROR: Can't find FileSelect_LoadGame() in src/overlays/gamestates/ovl_file_choose/z_file_choose.c.")

            if newData != fileData:
                writeFile(fileSelectPath, newData)

    except FileNotFoundError:
        raise PluginError("ERROR: Can't open src/overlays/gamestates/ovl_file_choose/z_file_choose.c")

def setFileSelectInit(functionContents : str) -> str:
    # removes file select audio blip on map load (not completely necessary)
    newContents = re.sub(r"func_800F5E18\s*\((((?!\)).)*)\)\s*;", "", functionContents, flags=re.DOTALL)

    # immediately loads first save on init
    if not "FileSelect_LoadGame" in newContents:
        newContents += "FileSelect_LoadGame(thisx);"
    
    return newContents

def setFileSelectLoadGame(functionContents : str, entranceIndex : str, options : Any) -> str:
    # disables map select
    newContents = re.sub(r"SET\_NEXT\_GAMESTATE\s*\(\s*\&this-\>state,\s*MapSelect\_Init,\s*MapSelectState\)\s*;", 
        "SET_NEXT_GAMESTATE(&this->state, Play_Init, PlayState);", functionContents, flags=re.DOTALL)

    # overrides entrance index
    newContents = addOrModifyAssignment(newContents, "gSaveContext.entranceIndex", entranceIndex)

    # overrides other properties for header
    if options.overrideHeader:
        timeOfDay = "NEXT_TIME_DAY" if options.headerOption == "Child Day" or \
            options.headerOption == "Adult Day" else "NEXT_TIME_NIGHT"
        
        linkAge = "LINK_AGE_ADULT" if options.headerOption == "Adult Day" or \
            options.headerOption == "Adult Night" else "LINK_AGE_CHILD"

        newContents = addOrModifyAssignment(newContents, "gSaveContext.nextDayTime", timeOfDay)
        newContents = addOrModifyAssignment(newContents, "gSaveContext.linkAge", linkAge)

        if options.headerOption == "Cutscene":
            cutsceneIndex = "0xFFF" + format(options.cutsceneIndex - 4, 'X')
            newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", cutsceneIndex)
        else:
            newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", "0xFFEF")
    
    else:
        newContents = addOrModifyAssignment(newContents, "gSaveContext.nextDayTime", "NEXT_TIME_NONE")
        newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", "0xFFEF")
        newContents = removeAssignment(newContents, 'gSaveContext.linkAge')
    
    return newContents

def clearFileSelectInit(functionContents : str) -> str:
    # removes file select auto loading
    newContents = re.sub(r"FileSelect\_LoadGame\s*\((((?!\)).)*)\)\s*;", "", functionContents, flags = re.DOTALL)

    # restores file select audio
    if not "func_800F5E18" in newContents:
        newContents += "func_800F5E18(SEQ_PLAYER_BGM_MAIN, NA_BGM_FILE_SELECT, 0, 7, 1);"
    
    return newContents

# entranceIndex and options will have empty/null values, this is just to match the paired function's signature
def clearFileSelectLoadGame(functionContents : str, entranceIndex : str, options : Any) -> str:
    
    # restores map select
    newContents = functionContents

    # warning: this breaks easily (if an close bracket is used within the if statement)
    match = re.search(r"if\s*\(this-\>buttonIndex\s*==\s*FS\_BTN\_SELECT\_FILE\_1\)\s*\{(((?!\}).)*)\}", newContents, flags = re.DOTALL)
    if match:
        mapSelectBranch = match.group(1)
        mapSelectBranch = re.sub(r"SET\_NEXT\_GAMESTATE\s*\(\s*\&this-\>state,\s*Play\_Init,\s*PlayState\s*\)\s*;", 
            "SET_NEXT_GAMESTATE(&this->state, MapSelect_Init, MapSelectState);", mapSelectBranch, flags=re.DOTALL)
        newContents = newContents[:match.start(1)] + mapSelectBranch + newContents[match.end(1):]

    # restores default settings
    newContents = removeAssignment(newContents, "gSaveContext.entranceIndex")
    newContents = addOrModifyAssignment(newContents, "gSaveContext.nextDayTime", "NEXT_TIME_NONE")
    newContents = addOrModifyAssignment(newContents, "gSaveContext.nextCutsceneIndex", "0xFFEF")
    newContents = removeAssignment(newContents, 'gSaveContext.linkAge')

    return newContents

def addOrModifyAssignment(data : str, name : str, value : str) -> str:
    setSceneMatch = re.search(re.escape(name) + r'\s*=\s*([a-zA-Z0-9_]*)\s*;', data, re.DOTALL)
    if setSceneMatch:
        data = data[:setSceneMatch.start(1)] + value + data[setSceneMatch.end(1):]
    else:
        data += "\n\t" + name + " = " + value + ";"
    
    return data

def removeAssignment(data : str, name : str) -> str:
    return re.sub("(\n\t)?" + re.escape(name) + r'\s*=\s*([a-zA-Z0-9_]*)\s*;', "", data, flags=re.DOTALL)

class OOT_ClearBootupScene(bpy.types.Operator):
    bl_idname = "object.oot_clear_bootup_scene"
    bl_label = "Undo Boot To Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        clearBootupScene(bpy.path.abspath(context.scene.ootDecompPath))
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}

class OOTBootupSceneOptions(bpy.types.PropertyGroup):
    bootToScene : bpy.props.BoolProperty(default = False, name = "Boot To Scene")
    overrideHeader : bpy.props.BoolProperty(default = False, name = "Override Header")
    headerOption : bpy.props.EnumProperty(items = ootEnumHeaderMenuComplete, name = "Header", default = "Child Day")
    spawnIndex : bpy.props.IntProperty(name = "Spawn", min = 0)

    # see src/code/z_play.c:Play_Init() - can't access more than 16 cutscenes? 
    cutsceneIndex : bpy.props.IntProperty(min = 4, max = 19, default = 4, name = "Cutscene Index")

def ootSceneBootupRegister():
    register_class(OOTBootupSceneOptions)
    register_class(OOT_ClearBootupScene)
    bpy.types.Scene.ootBootupSceneOptions = bpy.props.PointerProperty(type=OOTBootupSceneOptions)

def ootSceneBootupUnregister():
    unregister_class(OOTBootupSceneOptions)
    unregister_class(OOT_ClearBootupScene)
    del bpy.types.Scene.ootBootupSceneOptions