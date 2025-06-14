import os
import re

from ....utility import PluginError, readFile, writeFile
from ...scene.properties import OOTBootupSceneOptions


class Config:
    @staticmethod
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

    @staticmethod
    def setBootupScene(configPath: str, entranceIndex: str, options: "OOTBootupSceneOptions"):
        # ``options`` argument type: OOTBootupSceneOptions
        linkAge = "LINK_AGE_CHILD"
        timeOfDay = "NEXT_TIME_NONE"
        cutsceneIndex = "0xFFEF"
        newEntranceIndex = "0"
        saveName = "LINK"

        if options.bootMode != "Map Select":
            newEntranceIndex = entranceIndex
            saveName = options.newGameName

            if options.overrideHeader:
                timeOfDay, linkAge = Config.getParamsFromOptions(options)
                if options.headerOption == "Cutscene":
                    cutsceneIndex = "0xFFF" + format(options.cutsceneIndex - 4, "X")

        saveFileNameData = ", ".join(["0x" + format(i, "02X") for i in Config.stringToSaveNameBytes(saveName)])

        Config.writeBootupSettings(
            configPath,
            options.bootMode,
            options.newGameOnly,
            newEntranceIndex,
            linkAge,
            timeOfDay,
            cutsceneIndex,
            saveFileNameData,
        )

    @staticmethod
    def clearBootupScene(configPath: str):
        Config.writeBootupSettings(
            configPath,
            "",
            False,
            "0",
            "LINK_AGE_CHILD",
            "NEXT_TIME_NONE",
            "0xFFEF",
            "0x15, 0x12, 0x17, 0x14, 0x3E, 0x3E, 0x3E, 0x3E",
        )

    @staticmethod
    def getParamsFromOptions(options: "OOTBootupSceneOptions") -> tuple[str, str]:
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
    @staticmethod
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
