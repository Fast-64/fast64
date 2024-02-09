import bpy
import os

from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from typing import Optional
from ...f3d.f3d_gbi import DLFormat, TextureExportSettings
from ..scene.properties import OOTBootupSceneOptions
from ..oot_model_classes import OOTModel
from ..oot_f3d_writer import writeTextureArraysNew
from .scene import Scene
from .other import Files
from .classes import SceneFile

from ...utility import (
    PluginError,
    checkObjectReference,
    unhideAllAndGetHiddenState,
    restoreHiddenState,
    toAlnum,
)

from ..oot_utility import (
    ExportInfo,
    OOTObjectCategorizer,
    ootDuplicateHierarchy,
    ootCleanupScene,
    getSceneDirFromLevelName,
    ootGetPath,
)


@dataclass
class SceneExporter:
    """This class is the main exporter class, it handles generating the C data and writing the files"""

    exportInfo: ExportInfo
    originalSceneObj: Object
    sceneName: str
    ootBlenderScale: float
    transform: Matrix
    saveTexturesAsPNG: bool
    hackerootBootOption: OOTBootupSceneOptions
    isSingleFile: bool
    textureExportSettings: TextureExportSettings
    useMacros: bool

    dlFormat: DLFormat = field(init=False, default=DLFormat.Static)
    sceneObj: Optional[Object] = field(init=False, default=None)
    scene: Optional[Scene] = field(init=False, default=None)
    path: Optional[str] = field(init=False, default=None)
    sceneFile: Optional[SceneFile] = field(init=False, default=None)
    hasCutscenes: bool = field(init=False, default=False)
    hasSceneTextures: bool = field(init=False, default=False)

    def getNewScene(self):
        """Returns and creates scene data"""
        # init
        if self.originalSceneObj.type != "EMPTY" or self.originalSceneObj.ootEmptyType != "Scene":
            raise PluginError(f'{self.originalSceneObj.name} is not an empty with the "Scene" empty type.')

        if bpy.context.scene.exportHiddenGeometry:
            hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

        # Don't remove ignore_render, as we want to reuse this for collision
        self.sceneObj, allObjs = ootDuplicateHierarchy(self.originalSceneObj, None, True, OOTObjectCategorizer())

        if bpy.context.scene.exportHiddenGeometry:
            restoreHiddenState(hiddenState)

        try:
            sceneName = f"{toAlnum(self.sceneName)}_scene"
            newScene = Scene(
                self.sceneObj,
                self.transform,
                self.useMacros,
                sceneName,
                self.saveTexturesAsPNG,
                OOTModel(f"{sceneName}_dl", self.dlFormat, False),
            )
            newScene.validateScene()

            if newScene.mainHeader.cutscene is not None:
                self.hasCutscenes = len(newScene.mainHeader.cutscene.entries) > 0

                if not self.hasCutscenes and newScene.altHeader is not None:
                    for cs in newScene.altHeader.cutscenes:
                        if len(cs.cutscene.entries) > 0:
                            self.hasCutscenes = True
                            break
        except Exception as e:
            raise Exception(str(e))
        finally:
            ootCleanupScene(self.originalSceneObj, allObjs)

        return newScene

    def export(self):
        """Main function"""
        # circular import fixes
        from ..scene.exporter.to_c import setBootupScene
        from ..oot_level_writer import writeTextureArraysExistingScene

        checkObjectReference(self.originalSceneObj, "Scene object")
        isCustomExport = self.exportInfo.isCustomExportPath
        exportPath = self.exportInfo.exportPath

        exportSubdir = ""
        if self.exportInfo.customSubPath is not None:
            exportSubdir = self.exportInfo.customSubPath
        if not isCustomExport and self.exportInfo.customSubPath is None:
            exportSubdir = os.path.dirname(getSceneDirFromLevelName(self.sceneName))

        sceneInclude = exportSubdir + "/" + self.sceneName + "/"
        self.scene = self.getNewScene()
        self.path = ootGetPath(exportPath, isCustomExport, exportSubdir, self.sceneName, True, True)
        self.textureExportSettings.includeDir = sceneInclude
        self.textureExportSettings.exportPath = self.path
        self.sceneFile = self.scene.getNewSceneFile(self.path, self.isSingleFile, self.textureExportSettings)
        self.hasSceneTextures = self.sceneFile.sceneTextures is not None and len(self.sceneFile.sceneTextures) > 0

        if not isCustomExport:
            writeTextureArraysExistingScene(self.scene.model, exportPath, sceneInclude + self.sceneName + "_scene.h")
        else:
            textureArrayData = writeTextureArraysNew(self.scene.model, None)
            self.sceneFile.sceneTextures += textureArrayData.source
            self.sceneFile.header += textureArrayData.header

        self.sceneFile.write()
        for room in self.scene.rooms.entries:
            room.mesh.copyBgImages(self.path)

        if not isCustomExport:
            Files(self).editFiles()

        if self.hackerootBootOption is not None and self.hackerootBootOption.bootToScene:
            setBootupScene(
                os.path.join(exportPath, "include/config/config_debug.h")
                if not isCustomExport
                else os.path.join(self.path, "config_bootup.h"),
                f"ENTR_{self.sceneName.upper()}_{self.hackerootBootOption.spawnIndex}",
                self.hackerootBootOption,
            )
