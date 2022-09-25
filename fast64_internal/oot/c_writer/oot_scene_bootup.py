import os, re, bpy
import string
from bpy.utils import register_class, unregister_class
from ...utility import PluginError, writeFile
from ..oot_constants import ootEnumHeaderMenuComplete
from typing import Callable, Iterable, Any, List


def setBootupScene(exportPath: str, entranceIndex: str, options: "OOTBootupSceneOptions"):

    linkAge = "LINK_AGE_CHILD"
    timeOfDay = "NEXT_TIME_NONE"
    cutsceneIndex = "0xFFEF"
    saveFileNameData = ", ".join(["0x" + format(i, "02X") for i in stringToSaveNameBytes(options.newGameName)])
    if options.overrideHeader:
        timeOfDay, linkAge = getParamsFromOptions(options)
        if options.headerOption == "Cutscene":
            cutsceneIndex = "0xFFF" + format(options.cutsceneIndex - 4, "X")

    data = (
        f"#ifndef CONFIG_BOOTUP_H\n"
        + f"#define CONFIG_BOOTUP_H\n\n"
        + (("" if options.bootMode == "Play" else "// ") + "#define BOOT_TO_SCENE\n")
        + (("" if options.newGameOnly else "// ") + "#define BOOT_TO_SCENE_NEW_GAME_ONLY\n")
        + (("" if options.bootMode == "File Select" else "// ") + "#define BOOT_TO_FILE_SELECT\n")
        + f"#define BOOT_ENTRANCE {entranceIndex}\n"
        + f"#define BOOT_AGE {linkAge}\n"
        + f"#define BOOT_TIME {timeOfDay}\n"
        + f"#define BOOT_CUTSCENE {cutsceneIndex}\n"
        + f"#define BOOT_PLAYER_NAME {saveFileNameData}\n\n"
        + f"#endif\n"
    )

    writeFile(os.path.join(exportPath, "include/config/config_bootup.h"), data)


def clearBootupScene(exportPath: str):

    data = (
        f"#ifndef CONFIG_BOOTUP_H\n"
        + f"#define CONFIG_BOOTUP_H\n\n"
        + f"// #define BOOT_TO_SCENE\n"
        + f"// #define BOOT_TO_SCENE_NEW_GAME_ONLY\n"
        + f"// #define BOOT_TO_FILE_SELECT\n"
        + f"#define BOOT_ENTRANCE 0\n"
        + f"#define BOOT_AGE LINK_AGE_CHILD\n"
        + f"#define BOOT_TIME NEXT_TIME_NONE\n"
        + f"#define BOOT_CUTSCENE 0xFFEF\n"
        + f"#define BOOT_PLAYER_NAME 0x15, 0x12, 0x17, 0x14, 0x3E, 0x3E, 0x3E, 0x3E\n\n"
        + f"#endif\n"
    )

    writeFile(os.path.join(exportPath, "include/config/config_bootup.h"), data)


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
