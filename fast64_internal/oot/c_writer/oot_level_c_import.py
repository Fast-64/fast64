import math, os
from ..oot_f3d_writer import *
from ..oot_level_writer import *
from ..oot_collision import *
from ..oot_cutscene import *
from ..oot_level_writer import OOTImportSceneSettingsProperty


def parseScene(
    f3dType: str, isHWv1: bool, dlFormat: DLFormat, saveTexture: bool, settings: OOTImportSceneSettingsProperty
):
    sceneFolderPath = os.path.join(bpy.context.scene.ootDecompPath, settings.name)
    sceneName = os.path.dirname(sceneFolderPath)
    sceneData = readFile(os.path.join(sceneFolderPath, f"{sceneName}_scene.c"))

    parseSceneCommands(sceneData, f"{sceneName}_sceneCommands")


def parseSceneCommands(sceneData: str, sceneCommandsName: str):
    match = re.search(
        rf"SceneCmd\s*{re.escape(sceneCommandsName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if match:
        commands = match.group(1)
        print(commands)
    else:
        raise PluginError(f"Could not find scene commands {sceneCommandsName}.")
