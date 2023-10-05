import bpy
import os

from dataclasses import dataclass
from mathutils import Matrix
from bpy.types import Object
from ...f3d.f3d_gbi import DLFormat, TextureExportSettings
from ..scene.properties import OOTBootupSceneOptions, OOTSceneHeaderProperty
from ..scene.exporter.to_c import setBootupScene
from ..room.properties import OOTRoomHeaderProperty
from ..oot_constants import ootData
from ..oot_object import addMissingObjectsToAllRoomHeadersNew
from ..oot_model_classes import OOTModel
from ..oot_f3d_writer import writeTextureArraysNew
from ..oot_level_writer import BoundingBox, writeTextureArraysExistingScene, ootProcessMesh
from ..oot_utility import CullGroup
from .common import Base, altHeaderList
from .scene import Scene, SceneAlternateHeader
from .room import Room, RoomAlternateHeader
from .other import Files
from .exporter_classes import SceneFile

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
class OOTSceneExport:
    """This class is the main exporter class, it handles generating the C data and writing the files"""

    exportInfo: ExportInfo
    originalSceneObj: Object
    sceneName: str
    ootBlenderScale: float
    transform: Matrix
    f3dType: str
    saveTexturesAsPNG: bool
    hackerootBootOption: OOTBootupSceneOptions
    isSingleFile: bool
    isHWv1: bool
    textureExportSettings: TextureExportSettings
    useMacros: bool
    dlFormat: DLFormat = DLFormat.Static

    sceneObj: Object = None
    scene: Scene = None
    path: str = None
    sceneFile: SceneFile = None
    hasCutscenes: bool = False
    hasSceneTextures: bool = False

    def getNewRoomList(self, scene: Scene):
        """Returns the room list from empty objects with the type 'Room'"""

        roomDict: dict[int, Room] = {}
        roomObjs: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Room"
        ]

        if len(roomObjs) == 0:
            raise PluginError("ERROR: The scene has no child empties with the 'Room' empty type.")

        for roomObj in roomObjs:
            altProp = roomObj.ootAlternateRoomHeaders
            roomHeader = roomObj.ootRoomHeader
            roomIndex = roomHeader.roomIndex

            if roomIndex in roomDict:
                raise PluginError(f"ERROR: Room index {roomIndex} used more than once!")

            roomName = f"{toAlnum(self.sceneName)}_room_{roomIndex}"
            roomDict[roomIndex] = Room(
                self.sceneObj,
                self.transform,
                self.useMacros,
                roomIndex,
                roomName,
                roomObj,
                roomHeader.roomShape,
                scene.model.addSubModel(
                    OOTModel(
                        scene.model.f3d.F3D_VER,
                        scene.model.f3d._HW_VERSION_1,
                        roomName + "_dl",
                        scene.model.DLFormat,
                        None,
                    )
                ),
            )

            # Mesh stuff
            c = Base(self.sceneObj, self.transform, self.useMacros)
            pos, _, scale, _ = c.getConvertedTransform(self.transform, self.sceneObj, roomObj, True)
            cullGroup = CullGroup(pos, scale, roomObj.ootRoomHeader.defaultCullDistance)
            DLGroup = roomDict[roomIndex].mesh.addMeshGroup(cullGroup).DLGroup
            boundingBox = BoundingBox()
            ootProcessMesh(
                roomDict[roomIndex].mesh,
                DLGroup,
                self.sceneObj,
                roomObj,
                self.transform,
                not self.saveTexturesAsPNG,
                None,
                boundingBox,
            )

            centroid, radius = boundingBox.getEnclosingSphere()
            cullGroup.position = centroid
            cullGroup.cullDepth = radius

            roomDict[roomIndex].mesh.terminateDLs()
            roomDict[roomIndex].mesh.removeUnusedEntries()

            # Other
            if roomHeader.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and len(roomHeader.bgImageList) < 1:
                raise PluginError(f'Room {roomObj.name} uses room shape "Image" but doesn\'t have any BG images.')

            if roomHeader.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and len(roomDict) > 1:
                raise PluginError(f'Room shape "Image" can only have one room in the scene.')

            roomDict[roomIndex].roomShape = roomDict[roomIndex].getNewRoomShape(roomHeader, self.sceneName)
            altHeaderData = RoomAlternateHeader(f"{roomDict[roomIndex].name}_alternateHeaders")
            roomDict[roomIndex].mainHeader = roomDict[roomIndex].getNewRoomHeader(roomHeader)
            hasAltHeader = False

            for i, header in enumerate(altHeaderList, 1):
                altP: OOTRoomHeaderProperty = getattr(altProp, f"{header}Header")
                if not altP.usePreviousHeader:
                    hasAltHeader = True
                    setattr(altHeaderData, header, roomDict[roomIndex].getNewRoomHeader(altP, i))

            altHeaderData.cutscenes = [
                roomDict[roomIndex].getNewRoomHeader(csHeader, i)
                for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
            ]

            if len(altHeaderData.cutscenes) > 0:
                hasAltHeader = True

            roomDict[roomIndex].altHeader = altHeaderData if hasAltHeader else None
            addMissingObjectsToAllRoomHeadersNew(roomObj, roomDict[roomIndex], ootData)

        return [roomDict[i] for i in range(min(roomDict.keys()), len(roomDict))]

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
            altProp = self.sceneObj.ootAlternateSceneHeaders
            sceneData = Scene(self.sceneObj, self.transform, self.useMacros, name=f"{toAlnum(self.sceneName)}_scene")
            sceneData.model = OOTModel(self.f3dType, self.isHWv1, f"{sceneData.name}_dl", self.dlFormat, False)
            altHeaderData = SceneAlternateHeader(f"{sceneData.name}_alternateHeaders")
            sceneData.mainHeader = sceneData.getNewSceneHeader(self.sceneObj.ootSceneHeader)
            hasAltHeader = False

            for i, header in enumerate(altHeaderList, 1):
                altP: OOTSceneHeaderProperty = getattr(altProp, f"{header}Header")
                if not altP.usePreviousHeader:
                    setattr(altHeaderData, header, sceneData.getNewSceneHeader(altP, i))
                    hasAltHeader = True

            altHeaderData.cutscenes = [
                sceneData.getNewSceneHeader(csHeader, i) for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
            ]

            if len(altHeaderData.cutscenes) > 0:
                hasAltHeader = True

            sceneData.altHeader = altHeaderData if hasAltHeader else None
            sceneData.roomList = self.getNewRoomList(sceneData)
            sceneData.colHeader = sceneData.getNewCollisionHeader()
            sceneData.validateScene()

            if sceneData.mainHeader.cutscene is not None:
                self.hasCutscenes = sceneData.mainHeader.cutscene.writeCutscene

                if not self.hasCutscenes:
                    for cs in sceneData.altHeader.cutscenes:
                        if cs.cutscene.writeCutscene:
                            self.hasCutscenes = True
                            break

            ootCleanupScene(self.originalSceneObj, allObjs)
        except Exception as e:
            ootCleanupScene(self.originalSceneObj, allObjs)
            raise Exception(str(e))

        return sceneData

    def export(self):
        """Main function"""

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
        self.hasSceneTextures = len(self.sceneFile.sceneTextures) > 0

        if not isCustomExport:
            writeTextureArraysExistingScene(self.scene.model, exportPath, sceneInclude + self.sceneName + "_scene.h")
        else:
            textureArrayData = writeTextureArraysNew(self.scene.model, None)
            self.sceneFile.sceneTextures += textureArrayData.source
            self.sceneFile.header += textureArrayData.header

        self.sceneFile.write()
        for room in self.scene.roomList:
            room.mesh.copyBgImages(self.path)

        if not isCustomExport:
            Files(self).editFiles()

        if self.hackerootBootOption is not None and self.hackerootBootOption.bootToScene:
            setBootupScene(
                os.path.join(exportPath, "include/config/config_debug.h")
                if not isCustomExport
                else os.path.join(self.path, "config_bootup.h"),
                "ENTR_" + self.sceneName.upper() + "_" + str(self.hackerootBootOption.spawnIndex),
                self.hackerootBootOption,
            )
