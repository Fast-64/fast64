import os, re, bpy
from bpy.utils import register_class, unregister_class
from .....utility import PluginError, writeFile, readFile
from ....oot_constants import ootEnumHeaderMenuComplete
from typing import Any


def setBootupScene(configPath: str, entranceIndex: str, options: "OOTBootupSceneOptions"):

    linkAge = "LINK_AGE_CHILD"
    timeOfDay = "NEXT_TIME_NONE"
    cutsceneIndex = "0xFFEF"
    newEntranceIndex = "0"
    saveName = "LINK"

    if options.bootMode != "Map Select":
        newEntranceIndex = entranceIndex
        saveName = options.newGameName

        if options.overrideHeader:
            timeOfDay, linkAge = getParamsFromOptions(options)
            if options.headerOption == "Cutscene":
                cutsceneIndex = "0xFFF" + format(options.cutsceneIndex - 4, "X")

    saveFileNameData = ", ".join(["0x" + format(i, "02X") for i in stringToSaveNameBytes(saveName)])

    writeBootupSettings(
        configPath,
        options.bootMode,
        options.newGameOnly,
        newEntranceIndex,
        linkAge,
        timeOfDay,
        cutsceneIndex,
        saveFileNameData,
    )


def clearBootupScene(configPath: str):
    writeBootupSettings(
        configPath,
        "",
        False,
        "0",
        "LINK_AGE_CHILD",
        "NEXT_TIME_NONE",
        "0xFFEF",
        "0x15, 0x12, 0x17, 0x14, 0x3E, 0x3E, 0x3E, 0x3E",
    )


def writeBootupSettings(
    configPath: str,
    bootMode: str,
    newGameOnly: bool,
    entranceIndex: str,
    linkAge: str,
    timeOfDay: str,
    cutsceneIndex: str,
    saveFileNameData: str,
):
    if os.path.exists(configPath):
        originalData = readFile(configPath)
        data = originalData
    else:
        originalData = ""
        data = (
            f"// #define BOOT_TO_SCENE\n"
            + f"// #define BOOT_TO_SCENE_NEW_GAME_ONLY\n"
            + f"// #define BOOT_TO_FILE_SELECT\n"
            + f"// #define BOOT_TO_MAP_SELECT\n"
            + f"#define BOOT_ENTRANCE 0\n"
            + f"#define BOOT_AGE LINK_AGE_CHILD\n"
            + f"#define BOOT_TIME NEXT_TIME_NONE\n"
            + f"#define BOOT_CUTSCENE 0xFFEF\n"
            + f"#define BOOT_PLAYER_NAME 0x15, 0x12, 0x17, 0x14, 0x3E, 0x3E, 0x3E, 0x3E\n\n"
        )

    data = re.sub(
        r"(//\s*)?#define\s*BOOT_TO_SCENE",
        ("" if bootMode == "Play" else "// ") + "#define BOOT_TO_SCENE",
        data,
    )
    data = re.sub(
        r"(//\s*)?#define\s*BOOT_TO_SCENE_NEW_GAME_ONLY",
        ("" if newGameOnly else "// ") + "#define BOOT_TO_SCENE_NEW_GAME_ONLY",
        data,
    )
    data = re.sub(
        r"(//\s*)?#define\s*BOOT_TO_FILE_SELECT",
        ("" if bootMode == "File Select" else "// ") + "#define BOOT_TO_FILE_SELECT",
        data,
    )
    data = re.sub(
        r"(//\s*)?#define\s*BOOT_TO_MAP_SELECT",
        ("" if bootMode == "Map Select" else "// ") + "#define BOOT_TO_MAP_SELECT",
        data,
    )
    data = re.sub(r"#define\s*BOOT_ENTRANCE\s*[^\s]*", f"#define BOOT_ENTRANCE {entranceIndex}", data)
    data = re.sub(r"#define\s*BOOT_AGE\s*[^\s]*", f"#define BOOT_AGE {linkAge}", data)
    data = re.sub(r"#define\s*BOOT_TIME\s*[^\s]*", f"#define BOOT_TIME {timeOfDay}", data)
    data = re.sub(r"#define\s*BOOT_CUTSCENE\s*[^\s]*", f"#define BOOT_CUTSCENE {cutsceneIndex}", data)
    data = re.sub(r"#define\s*BOOT_PLAYER_NAME\s*[^\n]*", f"#define BOOT_PLAYER_NAME {saveFileNameData}", data)

    if data != originalData:
        writeFile(configPath, data)


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
        clearBootupScene(os.path.join(bpy.path.abspath(context.scene.ootDecompPath), "include/config/config_debug.h"))
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


ootEnumBootMode = [
    ("Play", "Play", "Play"),
    ("Map Select", "Map Select", "Map Select"),
    ("File Select", "File Select", "File Select"),
]


class OOTBootupSceneOptions(bpy.types.PropertyGroup):
    bootToScene: bpy.props.BoolProperty(default=False, name="Boot To Scene")
    overrideHeader: bpy.props.BoolProperty(default=False, name="Override Header")
    headerOption: bpy.props.EnumProperty(items=ootEnumHeaderMenuComplete, name="Header", default="Child Day")
    spawnIndex: bpy.props.IntProperty(name="Spawn", min=0)
    newGameOnly: bpy.props.BoolProperty(
        default=False,
        name="Override Scene On New Game Only",
        description="Only use this starting scene after loading a new save file",
    )
    newGameName: bpy.props.StringProperty(default="Link", name="New Game Name")
    bootMode: bpy.props.EnumProperty(default="Play", name="Boot Mode", items=ootEnumBootMode)

    # see src/code/z_play.c:Play_Init() - can't access more than 16 cutscenes?
    cutsceneIndex: bpy.props.IntProperty(min=4, max=19, default=4, name="Cutscene Index")


def ootSceneBootupRegister():
    register_class(OOTBootupSceneOptions)
    register_class(OOT_ClearBootupScene)


def ootSceneBootupUnregister():
    unregister_class(OOTBootupSceneOptions)
    unregister_class(OOT_ClearBootupScene)
