import re
import bpy
import mathutils

from pathlib import Path

from ...game_data import game_data
from ...utility import PluginError, hexOrDecInt
from ...f3d.f3d_parser import parseMatrices
from ...f3d.f3d_gbi import get_F3D_GBI
from ...f3d.flipbook import TextureFlipbook
from ..model_classes import OOTF3DContext
from ..exporter.decomp_edit.scene_table import SceneTableUtility
from ..scene.properties import OOTImportSceneSettingsProperty
from ..cutscene.importer import importCutsceneData
from .scene_header import parseSceneCommands
from .classes import SharedSceneData

from ..utility import (
    PathUtils,
    getSceneDirFromLevelName,
    setCustomProperty,
    sceneNameFromID,
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
    scene_name = settings.name
    subfolder = None

    if settings.isCustomDest:
        import_path = Path(settings.destPath)
    else:
        if option == "Custom":
            subfolder = f"{bpy.context.scene.fast64.oot.get_extracted_path()}/assets/scenes/{settings.subFolder}/"
        else:
            scene_name = sceneNameFromID(option)
        import_path = bpy.context.scene.fast64.oot.get_decomp_path()

    importSubdir = ""
    if subfolder is not None:
        importSubdir = subfolder
    if not settings.isCustomDest and subfolder is None:
        scene_dir_path = getSceneDirFromLevelName(scene_name)
        assert scene_dir_path is not None
        importSubdir = str(Path(scene_dir_path).parent) + "/"
        assert importSubdir is not None

    with PathUtils(True, import_path, importSubdir, scene_name, settings.isCustomDest) as path_utils:
        scene_folder_path = path_utils.get_assets_path(sub_folder="scenes", with_decomp_path=True, custom_mkdir=False)

    if game_data.z64.is_oot():
        file_path = scene_folder_path / f"{scene_name}_scene.c"
    else:
        file_path = scene_folder_path / f"{scene_name}.c"
    is_single_file = True

    if not file_path.exists():
        file_path = scene_folder_path / f"{scene_name}_scene_main.c"
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

    if game_data.z64.is_oot():
        sceneCommandsName = f"{scene_name}_sceneCommands"
    else:
        sceneCommandsName = f"{scene_name}Commands"

    not_zapd_assets = False

    # fast64 naming
    if sceneCommandsName not in sceneData:
        not_zapd_assets = True
        sceneCommandsName = f"{scene_name}_scene_header00"

    # newer assets system naming
    if game_data.z64.is_oot() and sceneCommandsName not in sceneData:
        not_zapd_assets = True
        sceneCommandsName = f"{scene_name}_scene"

    sharedSceneData = SharedSceneData(
        scene_folder_path,
        f"{scene_name}_scene" if game_data.z64.is_oot() else scene_name,
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
        is_single_file,
        f"{scene_name}_scene_header00" in sceneData,
        not_zapd_assets,
    )

    # set scene default registers (see sDefaultDisplayList)
    f3dContext = OOTF3DContext(get_F3D_GBI(), [], str(bpy.context.scene.fast64.oot.get_decomp_path()))
    f3dContext.mat().prim_color = (0.5, 0.5, 0.5, 0.5)
    f3dContext.mat().env_color = (0.5, 0.5, 0.5, 0.5)

    # disable TLUTs only if we're trying to import a scene from the new assets system
    f3dContext.ignore_tlut = sharedSceneData.not_zapd_assets and not sharedSceneData.is_fast64_data

    parseMatrices(sceneData, f3dContext, 1 / bpy.context.scene.ootBlenderScale)
    f3dContext.addMatrix("&gMtxClear", mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4))
    f3dContext.addMatrix("&gIdentityMtx", mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4))

    # TODO: fix the scene table parser for HackerOoT
    try:
        if not settings.isCustomDest:
            drawConfigName = SceneTableUtility.get_draw_config(scene_name)
            filename = "z_scene_table" if game_data.z64.is_oot() else "z_scene_proc"
            z_scene_table_path = import_path / "src" / "code" / f"{filename}.c"
            drawConfigData = z_scene_table_path.read_text()
            parseDrawConfig(drawConfigName, sceneData, drawConfigData, f3dContext)
    except:
        pass

    bpy.context.space_data.overlay.show_relationship_lines = False
    bpy.context.space_data.overlay.show_curve_normals = True
    bpy.context.space_data.overlay.normals_length = 2

    if settings.includeCutscenes:
        bpy.context.scene.ootCSNumber = importCutsceneData(None, sceneData)

    sceneObj = parseSceneCommands(scene_name, None, None, sceneCommandsName, sceneData, f3dContext, 0, sharedSceneData)
    bpy.context.scene.ootSceneExportObj = sceneObj

    # TODO: fix the scene table parser for HackerOoT
    try:
        if not settings.isCustomDest:
            setCustomProperty(
                sceneObj.ootSceneHeader.sceneTableEntry,
                "drawConfig",
                SceneTableUtility.get_draw_config(scene_name),
                game_data.z64.get_enum("drawConfig"),
            )
    except:
        pass

    if bpy.context.scene.fast64.oot.headerTabAffectsVisibility:
        setAllActorsVisibility(sceneObj, bpy.context)
