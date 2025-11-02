import os
import re
import bpy
import mathutils

from ...game_data import game_data
from ...utility import readFile, hexOrDecInt
from ...f3d.f3d_parser import parseMatrices
from ...f3d.f3d_gbi import get_F3D_GBI
from ...f3d.flipbook import TextureFlipbook
from ..model_classes import OOTF3DContext
from ..exporter.decomp_edit.scene_table import SceneTableUtility
from ..scene.properties import Z64_ImportSceneSettingsProperty
from .scene_header import parseSceneCommands
from .classes import SharedSceneData
from ..cutscene.importer import importCutsceneData

from ..utility import (
    getSceneDirFromLevelName,
    setCustomProperty,
    sceneNameFromID,
    ootGetPath,
    setAllActorsVisibility,
)


def parseDrawConfig(drawConfigName: str, sceneData: str, drawConfigData: str, f3dContext: OOTF3DContext):
    if game_data.z64.is_oot():
        drawFunctionName = "Scene_DrawConfig" + "".join(
            [value.strip().lower().capitalize() for value in drawConfigName.replace("SDC_", "").split("_")]
        )
    else:
        mm_draw_config_to_func_name = {
            "SCENE_DRAW_CFG_DEFAULT": "Scene_DrawConfigDefault",
            "SCENE_DRAW_CFG_MAT_ANIM": "Scene_DrawConfigMatAnim",
            "SCENE_DRAW_CFG_NOTHING": "Scene_DrawConfigDoNothing",
            "SCENE_DRAW_CFG_UNUSED_3": "Scene_DrawConfig3",
            "SCENE_DRAW_CFG_UNUSED_4": "Scene_DrawConfig4",
            "SCENE_DRAW_CFG_UNUSED_5": "Scene_DrawConfig5",
            "SCENE_DRAW_CFG_GREAT_BAY_TEMPLE": "Scene_DrawConfigGreatBayTemple",
            "SCENE_DRAW_CFG_MAT_ANIM_MANUAL_STEP": "Scene_DrawConfigMatAnimManualStep",
        }
        drawFunctionName = mm_draw_config_to_func_name[drawConfigName]

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
    settings: Z64_ImportSceneSettingsProperty,
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
    )
    if game_data.z64.is_oot():
        filePath = os.path.join(sceneFolderPath, f"{sceneName}_scene.c")
    else:
        filePath = os.path.join(sceneFolderPath, f"{sceneName}.c")
    sceneData = readFile(filePath)

    if bpy.context.mode != "OBJECT":
        bpy.context.mode = "OBJECT"

    # set scene default registers (see sDefaultDisplayList)
    f3dContext = OOTF3DContext(get_F3D_GBI(), [], bpy.path.abspath(bpy.context.scene.ootDecompPath))
    f3dContext.mat().prim_color = (0.5, 0.5, 0.5, 0.5)
    f3dContext.mat().env_color = (0.5, 0.5, 0.5, 0.5)

    parseMatrices(sceneData, f3dContext, 1 / bpy.context.scene.ootBlenderScale)
    f3dContext.addMatrix("&gMtxClear", mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4))

    if not settings.isCustomDest:
        drawConfigName = SceneTableUtility.get_draw_config(sceneName)
        filename = "z_scene_table" if game_data.z64.is_oot() else "z_scene_proc"
        drawConfigData = readFile(os.path.join(importPath, f"src/code/{filename}.c"))
        parseDrawConfig(drawConfigName, sceneData, drawConfigData, f3dContext)

    bpy.context.space_data.overlay.show_relationship_lines = False
    bpy.context.space_data.overlay.show_curve_normals = True
    bpy.context.space_data.overlay.normals_length = 2

    if game_data.z64.is_oot():
        sceneCommandsName = f"{sceneName}_sceneCommands"
    else:
        sceneCommandsName = f"{sceneName}Commands"

    if sceneCommandsName not in sceneData:
        sceneCommandsName = f"{sceneName}_scene_header00"  # fast64 naming

    sharedSceneData = SharedSceneData(
        sceneFolderPath,
        settings.includeMesh,
        settings.includeCollision,
        settings.includeActors,
        settings.includeCullGroups,
        settings.includeLights,
        settings.includeCameras,
        settings.includePaths,
        settings.includeWaterBoxes,
        settings.includeCutscenes,
        settings.includeAnimatedMats,
        settings.includeActorCs,
    )

    if settings.includeCutscenes:
        bpy.context.scene.ootCSNumber = importCutsceneData(None, sceneData)

    sceneObj = parseSceneCommands(sceneName, None, None, sceneCommandsName, sceneData, f3dContext, 0, sharedSceneData)
    bpy.context.scene.ootSceneExportObj = sceneObj

    if not settings.isCustomDest:
        setCustomProperty(
            sceneObj.ootSceneHeader.sceneTableEntry,
            "drawConfig",
            SceneTableUtility.get_draw_config(sceneName),
            game_data.z64.get_enum("drawConfig"),
            "drawConfigCustom",
        )

    if bpy.context.scene.fast64.oot.headerTabAffectsVisibility:
        setAllActorsVisibility(sceneObj, bpy.context)
