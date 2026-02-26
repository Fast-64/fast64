import bpy

from mathutils import Matrix
from bpy.types import Object
from pathlib import Path

from ...f3d.f3d_gbi import DLFormat, TextureExportSettings
from ..model_classes import OOTModel
from ..f3d_writer import writeTextureArraysNew, writeTextureArraysExisting1D
from .scene import Scene
from .decomp_edit import Files

from ...utility import (
    PluginError,
    checkObjectReference,
    unhideAllAndGetHiddenState,
    restoreHiddenState,
    toAlnum,
)

from ..utility import (
    ExportInfo,
    OOTObjectCategorizer,
    PathUtils,
    ootDuplicateHierarchy,
    ootCleanupScene,
    getSceneDirFromLevelName,
)


def writeTextureArraysExistingScene(fModel: OOTModel, exportPath: Path, sceneInclude: str):
    drawConfigPath = exportPath / "src/code/z_scene_table.c"
    drawConfigData = drawConfigPath.read_text()
    newData = drawConfigData

    if f'#include "{sceneInclude}"' not in newData:
        additionalIncludes = f'#include "{sceneInclude}"\n'
    else:
        additionalIncludes = ""

    for flipbook in fModel.flipbooks:
        if flipbook.exportMode == "Array":
            newData = writeTextureArraysExisting1D(newData, flipbook, additionalIncludes)
        else:
            raise PluginError("Scenes can only use array flipbooks.")

    if newData != drawConfigData:
        drawConfigPath.write_text(newData)


class SceneExport:
    """This class is the main exporter class, it handles generating the C data and writing the files"""

    @staticmethod
    def create_scene(originalSceneObj: Object, transform: Matrix, exportInfo: ExportInfo) -> Scene:
        """Returns and creates scene data"""
        # init
        if originalSceneObj.type != "EMPTY" or originalSceneObj.ootEmptyType != "Scene":
            raise PluginError(f'{originalSceneObj.name} is not an empty with the "Scene" empty type.')

        if bpy.context.scene.exportHiddenGeometry:
            hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

        # Don't remove ignore_render, as we want to reuse this for collision
        sceneObj, allObjs = ootDuplicateHierarchy(originalSceneObj, None, True, OOTObjectCategorizer())

        if bpy.context.scene.exportHiddenGeometry:
            restoreHiddenState(hiddenState)

        try:
            sceneName = f"{toAlnum(exportInfo.name)}_scene"
            newScene = Scene.new(
                sceneName,
                originalSceneObj,
                sceneObj,
                transform,
                exportInfo,
                OOTModel(f"{sceneName}_dl", DLFormat.Static, False),
            )
            newScene.validateScene()

        except Exception as e:
            raise Exception(str(e))
        finally:
            ootCleanupScene(originalSceneObj, allObjs)

        return newScene

    @staticmethod
    def export(originalSceneObj: Object, transform: Matrix, exportInfo: ExportInfo):
        """Main function"""
        # circular import fixes
        from .decomp_edit.config import Config

        checkObjectReference(originalSceneObj, "Scene object")
        scene = SceneExport.create_scene(originalSceneObj, transform, exportInfo)

        isCustomExport = exportInfo.isCustomExportPath
        exportPath = exportInfo.exportPath
        sceneName = exportInfo.name

        exportSubdir = ""
        if exportInfo.customSubPath is not None:
            exportSubdir = exportInfo.customSubPath
        if not isCustomExport and exportInfo.customSubPath is None:
            scene_dir_name = getSceneDirFromLevelName(sceneName)
            assert scene_dir_name is not None
            exportSubdir = str(Path(scene_dir_name).parent)

        sceneInclude = exportSubdir + "/" + sceneName + "/"

        with PathUtils(False, exportPath, exportSubdir, sceneName, isCustomExport) as path_utils:
            path = path_utils.get_assets_path(check_extracted=False, with_decomp_path=True)

        textureExportSettings = TextureExportSettings(False, exportInfo.saveTexturesAsPNG, sceneInclude, path)

        sceneFile = scene.getNewSceneFile(path, exportInfo.isSingleFile, textureExportSettings)

        if not isCustomExport:
            writeTextureArraysExistingScene(scene.model, exportPath, sceneInclude + sceneName + "_scene.h")
        else:
            textureArrayData = writeTextureArraysNew(scene.model, None)
            sceneFile.sceneTextures += textureArrayData.source
            sceneFile.header += textureArrayData.header

        sceneFile.write()
        for room in scene.rooms.entries:
            room.roomShape.copy_bg_images(path)

        if not isCustomExport:
            Files.add_scene_edits(exportInfo, scene, sceneFile)

        hackerootBootOption = exportInfo.hackerootBootOption
        if hackerootBootOption is not None and hackerootBootOption.bootToScene:
            Config.setBootupScene(
                exportPath / "include/config/config_debug.h" if not isCustomExport else path / "config_bootup.h",
                f"ENTR_{sceneName.upper()}_{hackerootBootOption.spawnIndex}",
                hackerootBootOption,
            )
