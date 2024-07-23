import bpy
import os
import traceback

from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from typing import Optional
from ...f3d.f3d_gbi import DLFormat, TextureExportSettings
from ..scene.properties import OOTBootupSceneOptions
from ..oot_model_classes import OOTModel
from ..oot_f3d_writer import writeTextureArraysNew
from .scene import Scene
from .decomp_edit import Files
from .file import SceneFile

from ...utility import (
    PluginError,
    checkObjectReference,
    unhideAllAndGetHiddenState,
    restoreHiddenState,
    toAlnum,
)

from ..oot_utility import (
    ExportInfo,
    RemoveInfo,
    OOTObjectCategorizer,
    ootDuplicateHierarchy,
    ootCleanupScene,
    getSceneDirFromLevelName,
    ootGetPath,
)


@dataclass
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
                sceneObj,
                transform,
                exportInfo.useMacros,
                exportInfo.saveTexturesAsPNG,
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
        from ..scene.exporter.to_c import setBootupScene
        from ..oot_level_writer import writeTextureArraysExistingScene

        checkObjectReference(originalSceneObj, "Scene object")
        scene = SceneExport.create_scene(originalSceneObj, transform, exportInfo)

        isCustomExport = exportInfo.isCustomExportPath
        exportPath = exportInfo.exportPath
        sceneName = exportInfo.name

        exportSubdir = ""
        if exportInfo.customSubPath is not None:
            exportSubdir = exportInfo.customSubPath
        if not isCustomExport and exportInfo.customSubPath is None:
            exportSubdir = os.path.dirname(getSceneDirFromLevelName(sceneName))

        sceneInclude = exportSubdir + "/" + sceneName + "/"
        path = ootGetPath(exportPath, isCustomExport, exportSubdir, sceneName, True, True)
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
            room.mesh.copyBgImages(path)

        if not isCustomExport:
            Files.add_scene_edits(exportInfo, scene, sceneFile)

        hackerootBootOption = exportInfo.hackerootBootOption
        if hackerootBootOption is not None and hackerootBootOption.bootToScene:
            setBootupScene(
                os.path.join(exportPath, "include/config/config_debug.h")
                if not isCustomExport
                else os.path.join(path, "config_bootup.h"),
                f"ENTR_{sceneName.upper()}_{hackerootBootOption.spawnIndex}",
                hackerootBootOption,
            )
