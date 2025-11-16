import os
import re
import bpy
import mathutils

from pathlib import Path

from ...utility import PluginError, readFile, hexOrDecInt
from ...f3d.f3d_parser import parseMatrices
from ...f3d.f3d_gbi import get_F3D_GBI
from ...f3d.flipbook import TextureFlipbook
from ..model_classes import OOTF3DContext
from ..exporter.decomp_edit.scene_table import SceneTableUtility
from ..scene.properties import OOTImportSceneSettingsProperty
from ..constants import ootEnumDrawConfig
from ..cutscene.importer import importCutsceneData
from .scene_header import parseSceneCommands
from .classes import SharedSceneData

from ..utility import (
    getSceneDirFromLevelName,
    setCustomProperty,
    sceneNameFromID,
    ootGetPath,
    setAllActorsVisibility,
)


def parseDrawConfig(drawConfigName: str, sceneData: str, drawConfigData: str, f3dContext: OOTF3DContext):
    drawFunctionName = "Scene_DrawConfig" + "".join(
        [value.strip().lower().capitalize() for value in drawConfigName.replace("SDC_", "").split("_")]
    )

    # get draw function
    match = re.search(rf"void\s*{re.escape(drawFunctionName)}(.*?)CLOSE\_DISPS", drawConfigData, flags=re.DOTALL)
    if match is None:
        print(f"Could not find draw function {drawFunctionName}.")
        return
    functionData = match.group(1)

    # get all flipbook textures
    flipbookDict = {}
    for fbMatch in re.finditer(
        r"void\*\s*([a-zA-Z0-9\_]*)\s*\[.*?\]\s*=\s*\{(.*?)\}\s*;", drawConfigData, flags=re.DOTALL
    ):
        name = fbMatch.group(1)
        textureList = [value.strip() for value in fbMatch.group(2).split(",") if value.strip() != ""]
        flipbookDict[name] = textureList

    # static environment color
    for envMatch in re.finditer(
        rf"gDPSetEnvColor\s*\(\s*POLY_[A-Z]{{3}}_DISP\s*\+\+\s*,([^\)]*)\)\s*;", functionData, flags=re.DOTALL
    ):
        params = [value.strip() for value in envMatch.group(1).split(",")]
        try:
            color = tuple([hexOrDecInt(value) / 0xFF for value in params])
            f3dContext.mat().env_color = color
        except:
            pass

    # dynamic textures
    for flipbookMatch in re.finditer(
        rf"gSPSegment\s*\(\s*POLY_([A-Z]{{3}})_DISP\s*\+\+\s*,\s*([^,]*),\s*SEGMENTED_TO_VIRTUAL(.*?)\)\s*;",
        functionData,
        flags=re.DOTALL,
    ):
        drawLayerID = flipbookMatch.group(1)
        segment = flipbookMatch.group(2).strip()
        textureParam = flipbookMatch.group(3)

        drawLayer = "Transparent" if drawLayerID == "XLU" else "Opaque"
        flipbookKey = (hexOrDecInt(segment), drawLayer)

        for name, textureNames in flipbookDict.items():
            if name in textureParam:
                f3dContext.flipbooks[flipbookKey] = TextureFlipbook(name, "Array", flipbookDict[name])


def parseScene(
    settings: OOTImportSceneSettingsProperty,
    option: str,
):
    sceneName = settings.name
    if settings.isCustomDest:
        importPath = bpy.path.abspath(settings.destPath)
        subfolder = None
    else:
        if option == "Custom":
            subfolder = f"{bpy.context.scene.fast64.oot.get_extracted_path()}/assets/scenes/{settings.subFolder}/"
        else:
            sceneName = sceneNameFromID(option)
            subfolder = None
        importPath = bpy.path.abspath(bpy.context.scene.ootDecompPath)

    importSubdir = ""
    if settings.isCustomDest is not None:
        importSubdir = subfolder
    if not settings.isCustomDest and subfolder is None:
        importSubdir = os.path.dirname(getSceneDirFromLevelName(sceneName, True)) + "/"

    sceneFolderPath = ootGetPath(
        importPath if settings.isCustomDest else f"{importPath}/{bpy.context.scene.fast64.oot.get_extracted_path()}/",
        settings.isCustomDest,
        importSubdir,
        sceneName,
        False,
        True,
        True,
    )

    file_path = Path(sceneFolderPath).resolve() / f"{sceneName}_scene.c"
    is_single_file = True

    if not file_path.exists():
        file_path = Path(sceneFolderPath).resolve() / f"{sceneName}_scene_main.c"
        is_single_file = False

    if not file_path.exists():
        raise PluginError("ERROR: scene not found!")

    sceneData = file_path.read_text()

    if not is_single_file:
        # get the other scene files for non-single file fast64 exports
        for file in file_path.parent.rglob("*.c"):
            if "_scene_main.c" not in str(file) and "_room_" not in str(file):
                sceneData += file.read_text()

    if bpy.context.mode != "OBJECT":
        bpy.context.mode = "OBJECT"

    sceneCommandsName = f"{sceneName}_sceneCommands"
    not_zapd_assets = False

    # fast64 naming
    if sceneCommandsName not in sceneData:
        not_zapd_assets = True
        sceneCommandsName = f"{sceneName}_scene_header00"

    # newer assets system naming
    if sceneCommandsName not in sceneData:
        not_zapd_assets = True
        sceneCommandsName = f"{sceneName}_scene"

    sharedSceneData = SharedSceneData(
        sceneFolderPath,
        f"{sceneName}_scene",
        settings.includeMesh,
        settings.includeCollision,
        settings.includeActors,
        settings.includeCullGroups,
        settings.includeLights,
        settings.includeCameras,
        settings.includePaths,
        settings.includeWaterBoxes,
        settings.includeCutscenes,
        is_single_file,
        f"{sceneName}_scene_header00" in sceneData,
        not_zapd_assets,
    )

    # set scene default registers (see sDefaultDisplayList)
    f3dContext = OOTF3DContext(get_F3D_GBI(), [], bpy.path.abspath(bpy.context.scene.ootDecompPath))
    f3dContext.mat().prim_color = (0.5, 0.5, 0.5, 0.5)
    f3dContext.mat().env_color = (0.5, 0.5, 0.5, 0.5)

    # disable TLUTs only if we're trying to import a scene from the new assets system
    f3dContext.ignore_tlut = sharedSceneData.not_zapd_assets and not sharedSceneData.is_fast64_data

    parseMatrices(sceneData, f3dContext, 1 / bpy.context.scene.ootBlenderScale)
    f3dContext.addMatrix("&gMtxClear", mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4))
    f3dContext.addMatrix("&gIdentityMtx", mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4))

    if not settings.isCustomDest:
        drawConfigName = SceneTableUtility.get_draw_config(sceneName)
        drawConfigData = readFile(os.path.join(importPath, "src/code/z_scene_table.c"))
        parseDrawConfig(drawConfigName, sceneData, drawConfigData, f3dContext)

    bpy.context.space_data.overlay.show_relationship_lines = False
    bpy.context.space_data.overlay.show_curve_normals = True
    bpy.context.space_data.overlay.normals_length = 2

    if settings.includeCutscenes:
        bpy.context.scene.ootCSNumber = importCutsceneData(None, sceneData)

    sceneObj = parseSceneCommands(sceneName, None, None, sceneCommandsName, sceneData, f3dContext, 0, sharedSceneData)
    bpy.context.scene.ootSceneExportObj = sceneObj

    if not settings.isCustomDest:
        setCustomProperty(
            sceneObj.ootSceneHeader.sceneTableEntry,
            "drawConfig",
            SceneTableUtility.get_draw_config(sceneName),
            ootEnumDrawConfig,
        )

    if bpy.context.scene.fast64.oot.headerTabAffectsVisibility:
        setAllActorsVisibility(sceneObj, bpy.context)
