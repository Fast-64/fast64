import bpy
import os

from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from ...utility import (
    PluginError,
    checkObjectReference,
    unhideAllAndGetHiddenState,
    restoreHiddenState,
    toAlnum,
    writeFile,
)
from ...f3d.f3d_gbi import DLFormat
from ..scene.properties import OOTBootupSceneOptions, OOTSceneHeaderProperty
from ..room.properties import OOTRoomHeaderProperty
from ..oot_constants import ootData
from ..oot_object import addMissingObjectsToAllRoomHeadersNew
from .common import altHeaderList
from .scene import OOTScene, OOTSceneAlternateHeader
from .room import OOTRoom, OOTRoomAlternateHeader
from .collision import OOTSceneCollisionHeader

from ..oot_utility import (
    ExportInfo,
    OOTObjectCategorizer,
    ootDuplicateHierarchy,
    ootCleanupScene,
    getSceneDirFromLevelName,
    ootGetPath,
)


@dataclass
class OOTRoomData:
    name: str
    roomMain: str = None
    roomModel: str = None
    roomModelInfo: str = None


@dataclass
class OOTSceneData:
    sceneMain: str = None
    sceneCollision: str = None
    sceneCutscenes: list[str] = field(default_factory=list)


@dataclass
class OOTSceneExport:
    exportInfo: ExportInfo
    sceneObj: Object
    sceneName: str
    ootBlenderScale: float
    transform: Matrix
    f3dType: str
    saveTexturesAsPNG: bool
    hackerootBootOption: OOTBootupSceneOptions
    singleFileExport: bool
    dlFormat: DLFormat = DLFormat.Static

    scene: OOTScene = None
    path: str = None
    header: str = ""
    sceneData: OOTSceneData = None
    roomList: dict[int, OOTRoomData] = field(default_factory=dict)
    hasCutscenes: bool = False

    def getNewRoomList(self):
        processedRooms = []
        roomList: list[OOTRoom] = []
        roomObjs: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Room"
        ]

        if len(roomObjs) == 0:
            raise PluginError("ERROR: The scene has no child empties with the 'Room' empty type.")

        for roomObj in roomObjs:
            altProp = roomObj.ootAlternateRoomHeaders
            roomIndex = roomObj.ootRoomHeader.roomIndex
            roomName = f"{toAlnum(self.sceneName)}_room_{roomIndex}"
            roomData = OOTRoom(self.sceneObj, self.transform, roomIndex, roomName, roomObj)
            altHeaderData = OOTRoomAlternateHeader(f"{roomData.name}_alternateHeaders")
            roomData.mainHeader = roomData.getNewRoomHeader(roomObj.ootRoomHeader)
            hasAltHeader = False

            for i, header in enumerate(altHeaderList, 1):
                altP: OOTRoomHeaderProperty = getattr(altProp, f"{header}Header")
                if not altP.usePreviousHeader:
                    hasAltHeader = True
                    setattr(altHeaderData, header, roomData.getNewRoomHeader(altP, i))

            altHeaderData.cutscenes = [
                roomData.getNewRoomHeader(csHeader, i) for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
            ]

            if len(altHeaderData.cutscenes) > 0:
                hasAltHeader = True

            roomData.altHeader = altHeaderData if hasAltHeader else None

            if roomIndex in processedRooms:
                raise PluginError(f"ERROR: Room index {roomIndex} used more than once!")

            addMissingObjectsToAllRoomHeadersNew(roomObj, roomData, ootData)
            processedRooms.append(roomIndex)
            roomList.append(roomData)

        return roomList

    def getNewScene(self):
        altProp = self.sceneObj.ootAlternateSceneHeaders
        sceneData = OOTScene(self.sceneObj, self.transform, name=f"{toAlnum(self.sceneName)}_scene")
        altHeaderData = OOTSceneAlternateHeader(f"{sceneData.name}_alternateHeaders")
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
        sceneData.roomList = self.getNewRoomList()
        sceneData.colHeader = sceneData.getNewCollisionHeader()

        sceneData.validateScene()
        return sceneData

    def getNewSceneFromEmptyObject(self):
        """Returns the default scene header and adds the alternate/cutscene ones"""

        # init
        originalSceneObj = self.sceneObj
        if self.sceneObj.type != "EMPTY" or self.sceneObj.ootEmptyType != "Scene":
            raise PluginError(f'{self.sceneObj.name} is not an empty with the "Scene" empty type.')

        if bpy.context.scene.exportHiddenGeometry:
            hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

        # Don't remove ignore_render, as we want to reuse this for collision
        self.sceneObj, allObjs = ootDuplicateHierarchy(self.sceneObj, None, True, OOTObjectCategorizer())

        if bpy.context.scene.exportHiddenGeometry:
            restoreHiddenState(hiddenState)

        # convert scene
        sceneData = None
        try:
            sceneData = self.getNewScene()
            self.hasCutscenes = sceneData.mainHeader.cutscene.writeCutscene

            if not self.hasCutscenes:
                for cs in sceneData.altHeader.cutscenes:
                    if cs.cutscene.writeCutscene:
                        self.hasCutscenes = True
                        break

            ootCleanupScene(originalSceneObj, allObjs)
        except Exception as e:
            ootCleanupScene(originalSceneObj, allObjs)
            raise Exception(str(e))

        if sceneData is None:
            raise PluginError("ERROR: 'sceneData' is None!")

        return sceneData

    def setRoomListData(self):
        for room in self.scene.roomList:
            roomData = OOTRoomData(room.name)
            roomMainData = room.getRoomMainC()

            roomData.roomMain = roomMainData.source
            self.header += roomMainData.header

            self.roomList[room.roomIndex] = roomData

    def setSceneData(self):
        sceneData = OOTSceneData()
        sceneMainData = self.scene.getSceneMainC()
        sceneCollisionData = self.scene.colHeader.getSceneCollisionC()
        sceneCutsceneData = self.scene.getSceneCutscenesC()

        sceneData.sceneMain = sceneMainData.source
        sceneData.sceneCollision = sceneCollisionData.source
        sceneData.sceneCutscenes = [cs.source for cs in sceneCutsceneData]
        self.header += sceneMainData.header + "".join(cs.header for cs in sceneCutsceneData) + sceneCollisionData.header
        self.sceneData = sceneData

    def setIncludeData(self):
        suffix = "\n\n"
        sceneInclude = f'\n#include "{self.scene.name}.h"\n'
        common = (
            "\n".join(
                [
                    '#include "ultra64/ultratypes.h"',
                    '#include "libc/stdint.h"',
                    '#include "z64math.h"',
                ]
            )
            + "\n"
        )

        room = (
            "\n".join(
                [
                    '#include "z64object.h"',
                    '#include "z64actor.h"',
                    '#include "z64scene.h"',
                ]
            )
            + "\n"
        )

        scene = (
            "\n".join(
                [
                    '#include "z64dma.h"',
                    '#include "z64actor.h"',
                    '#include "z64scene.h"',
                    '#include "z64environment.h"',
                ]
            )
            + "\n"
        )

        collision = (
            "\n".join(
                [
                    '#include "macros.h"',
                    '#include "z64camera.h"',
                    '#include "z64bgcheck.h"',
                ]
            )
            + "\n"
        )

        cutscene = (
            "\n".join(
                [
                    '#include "z64cutscene.h"',
                    '#include "z64cutscene_commands.h"',
                ]
            )
            + "\n"
        )

        for roomData in self.roomList.values():
            roomData.roomMain = common + room + sceneInclude + suffix + roomData.roomMain

        if self.singleFileExport:
            common += scene + collision + cutscene + sceneInclude
            self.sceneData.sceneMain = common + suffix + self.sceneData.sceneMain
        else:
            self.sceneData.sceneMain = common + scene + sceneInclude + suffix + self.sceneData.sceneMain
            self.sceneData.sceneCollision = common + collision + sceneInclude + suffix + self.sceneData.sceneCollision

            if self.hasCutscenes:
                for cs in self.sceneData.sceneCutscenes:
                    cs = cutscene + sceneInclude + suffix + cs

    def writeScene(self):
        sceneBasePath = os.path.join(self.path, self.scene.name)

        for room in self.roomList.values():
            writeFile(os.path.join(self.path, room.name + ".c"), room.roomMain)

        if self.singleFileExport:
            self.sceneData.sceneMain += self.sceneData.sceneCollision
            if self.hasCutscenes:
                for i, cs in enumerate(self.sceneData.sceneCutscenes):
                    self.sceneData.sceneMain += cs
        else:
            writeFile(f"{sceneBasePath}_col.c", self.sceneData.sceneCollision)
            if self.hasCutscenes:
                for i, cs in enumerate(self.sceneData.sceneCutscenes):
                    writeFile(f"{sceneBasePath}_cs_{i}.c", cs)

        writeFile(sceneBasePath + ".c", self.sceneData.sceneMain)
        writeFile(sceneBasePath + ".h", self.header)

    def export(self):
        checkObjectReference(self.sceneObj, "Scene object")
        isCustomExport = self.exportInfo.isCustomExportPath
        exportPath = self.exportInfo.exportPath

        exportSubdir = ""
        if self.exportInfo.customSubPath is not None:
            exportSubdir = self.exportInfo.customSubPath
        if not isCustomExport and self.exportInfo.customSubPath is None:
            exportSubdir = os.path.dirname(getSceneDirFromLevelName(self.sceneName))

        sceneInclude = exportSubdir + "/" + self.sceneName + "/"
        levelPath = ootGetPath(exportPath, isCustomExport, exportSubdir, self.sceneName, True, True)

        self.scene = self.getNewSceneFromEmptyObject()
        self.path = levelPath
        self.setSceneData()
        self.setRoomListData()
        self.setIncludeData()

        self.writeScene()
