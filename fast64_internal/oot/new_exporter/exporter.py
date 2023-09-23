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
from .scene import OOTScene, OOTSceneAlternate
from .room import OOTRoom, OOTRoomAlternate

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
    dlFormat: DLFormat = DLFormat.Static
    altHeaderList: list[str] = field(default_factory=lambda: ["childNight", "adultDay", "adultNight"])

    scene: OOTScene = None
    path: str = None
    header: str = ""
    sceneData: OOTSceneData = None
    roomList: dict[int, OOTRoomData] = field(default_factory=dict)
    csList: dict[int, str] = field(default_factory=dict)

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
            roomData = OOTRoom(self.sceneObj, roomObj, self.transform, roomIndex, self.sceneName, name=roomName)
            altHeaderData = OOTRoomAlternate()
            roomData.header = roomData.getNewRoomHeader(roomObj.ootRoomHeader)

            for i, header in enumerate(self.altHeaderList, 1):
                altP: OOTRoomHeaderProperty = getattr(altProp, f"{header}Header")
                if not altP.usePreviousHeader:
                    setattr(altHeaderData, header, roomData.getNewRoomHeader(altP, i))

            altHeaderData.cutscene = [
                roomData.getNewRoomHeader(csHeader, i) for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
            ]

            roomData.alternate = altHeaderData

            if roomIndex in processedRooms:
                raise PluginError(f"ERROR: Room index {roomIndex} used more than once!")

            addMissingObjectsToAllRoomHeadersNew(roomObj, roomData, ootData)
            processedRooms.append(roomIndex)
            roomList.append(roomData)

        return roomList

    def getNewScene(self):
        altProp = self.sceneObj.ootAlternateSceneHeaders
        sceneData = OOTScene(self.sceneObj, None, self.transform, None, f"{toAlnum(self.sceneName)}_scene")
        altHeaderData = OOTSceneAlternate()
        sceneData.header = sceneData.getNewSceneHeader(self.sceneObj.ootSceneHeader)

        for i, header in enumerate(self.altHeaderList, 1):
            altP: OOTSceneHeaderProperty = getattr(altProp, f"{header}Header")
            if not altP.usePreviousHeader:
                setattr(altHeaderData, header, sceneData.getNewSceneHeader(altP, i))

        altHeaderData.cutscene = [
            sceneData.getNewSceneHeader(csHeader, i) for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
        ]

        sceneData.alternate = altHeaderData
        sceneData.roomList = self.getNewRoomList()

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

        sceneData.sceneMain = sceneMainData.source
        self.header += sceneMainData.header
        self.sceneData = sceneData

    def writeScene(self):
        scenePath = os.path.join(self.path, self.scene.sceneName + ".c")
        writeFile(scenePath, self.sceneData.sceneMain)

        for room in self.roomList.values():
            roomPath = os.path.join(self.path, room.name + ".c")
            writeFile(roomPath, room.roomMain)

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

        self.writeScene()
