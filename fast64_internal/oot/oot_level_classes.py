import bpy, os, shutil
from typing import Optional
from ..utility import PluginError, toAlnum, indent
from .oot_collision_classes import OOTCollision
from .oot_model_classes import OOTModel
from ..f3d.f3d_gbi import (
    SPDisplayList,
    SPEndDisplayList,
    GfxListTag,
    GfxList,
)


class OOTCommonCommands:
    def getAltHeaderListCmd(self, altName):
        return indent + f"SCENE_CMD_ALTERNATE_HEADER_LIST({altName}),\n"

    def getEndCmd(self):
        return indent + "SCENE_CMD_END(),\n"


class OOTActor:
    def __init__(self, actorName, actorID, position, rotation, actorParam):
        self.actorName = actorName
        self.actorID = actorID
        self.actorParam = actorParam
        self.position = position
        self.rotation = rotation


class OOTTransitionActor:
    def __init__(self, actorName, actorID, frontRoom, backRoom, frontCam, backCam, position, rotationY, actorParam):
        self.actorName = actorName
        self.actorID = actorID
        self.actorParam = actorParam
        self.frontRoom = frontRoom
        self.backRoom = backRoom
        self.frontCam = frontCam
        self.backCam = backCam
        self.position = position
        self.rotationY = rotationY


class OOTExit:
    def __init__(self, index):
        self.index = index


class OOTEntrance:
    def __init__(self, roomIndex, startPositionIndex):
        self.roomIndex = roomIndex
        self.startPositionIndex = startPositionIndex


class OOTLight:
    def __init__(self):
        self.ambient = (0, 0, 0)
        self.diffuse0 = (0, 0, 0)
        self.diffuseDir0 = (0, 0, 0)
        self.diffuse1 = (0, 0, 0)
        self.diffuseDir1 = (0, 0, 0)
        self.fogColor = (0, 0, 0)
        self.fogNear = 0
        self.fogFar = 0
        self.transitionSpeed = 0

    def getBlendFogNear(self):
        return f"(({self.transitionSpeed} << 10) | {self.fogNear})"


class OOTCSTextbox:
    def __init__(self):
        self.textboxType = None
        self.messageId = "0x0000"
        self.ocarinaSongAction = "0x0000"
        self.startFrame = 0
        self.endFrame = 1
        self.type = "0x0000"
        self.topOptionBranch = "0x0000"
        self.bottomOptionBranch = "0x0000"
        self.ocarinaMessageId = "0x0000"


class OOTCSLighting:
    def __init__(self):
        self.index = 1
        self.startFrame = 0


class OOTCSTime:
    def __init__(self):
        self.startFrame = 0
        self.hour = 23
        self.minute = 59


class OOTCSBGM:
    def __init__(self):
        self.value = "0x0000"
        self.startFrame = 0
        self.endFrame = 1


class OOTCSMisc:
    def __init__(self):
        self.operation = 1
        self.startFrame = 0
        self.endFrame = 1


class OOTCS0x09:
    def __init__(self):
        self.startFrame = 0
        self.unk2 = "0x00"
        self.unk3 = "0x00"
        self.unk4 = "0x00"


class OOTCSUnk:
    def __unk__(self):
        self.unk1 = "0x00000000"
        self.unk2 = "0x00000000"
        self.unk3 = "0x00000000"
        self.unk4 = "0x00000000"
        self.unk5 = "0x00000000"
        self.unk6 = "0x00000000"
        self.unk7 = "0x00000000"
        self.unk8 = "0x00000000"
        self.unk9 = "0x00000000"
        self.unk10 = "0x00000000"
        self.unk11 = "0x00000000"
        self.unk12 = "0x00000000"


class OOTCSList:
    def __init__(self):
        self.listType = None
        self.entries = []
        self.unkType = "0x0001"
        self.fxType = "1"
        self.fxStartFrame = 0
        self.fxEndFrame = 0


class OOTCutscene:
    def __init__(self):
        self.name = ""
        self.csEndFrame = 100
        self.csWriteTerminator = False
        self.csTermIdx = 0
        self.csTermStart = 99
        self.csTermEnd = 100
        self.csLists = []


class OOTSceneTableEntry:
    def __init__(self):
        self.drawConfig = 0


class OOTScene(OOTCommonCommands):
    def __init__(self, name, model):
        self.name = toAlnum(name)
        self.write_dummy_room_list = False
        self.rooms = {}
        self.transitionActorList = set()
        self.entranceList = set()
        self.startPositions = {}
        self.lights = []
        self.model = model
        self.collision = OOTCollision(self.name)

        self.globalObject = None
        self.naviCup = None

        # Skybox
        self.skyboxID = None
        self.skyboxCloudiness = None
        self.skyboxLighting = None
        self.isSkyboxLightingCustom = False

        # Camera
        self.mapLocation = None
        self.cameraMode = None

        self.musicSeq = None
        self.nightSeq = None

        self.childNightHeader: Optional[OOTScene] = None
        self.adultDayHeader: Optional[OOTScene] = None
        self.adultNightHeader: Optional[OOTScene] = None
        self.cutsceneHeaders: list["OOTScene"] = []

        self.exitList = []
        self.pathList = set()
        self.cameraList = []

        self.writeCutscene = False
        self.csWriteType = "Embedded"
        self.csWriteCustom = ""
        self.csWriteObject = None
        self.csEndFrame = 100
        self.csWriteTerminator = False
        self.csTermIdx = 0
        self.csTermStart = 99
        self.csTermEnd = 100
        self.csLists = []
        self.extraCutscenes = []

        self.sceneTableEntry = OOTSceneTableEntry()

    def getAlternateHeaderScene(self, name):
        scene = OOTScene(name, self.model)
        scene.write_dummy_room_list = self.write_dummy_room_list
        scene.rooms = self.rooms
        scene.collision = self.collision
        scene.exitList = []
        scene.pathList = set()
        scene.cameraList = self.cameraList
        return scene

    def sceneName(self):
        return self.name + "_scene"

    def roomListName(self):
        return self.sceneName() + "_roomList"

    def entranceListName(self, headerIndex):
        return self.sceneName() + "_header" + format(headerIndex, "02") + "_entranceList"

    def startPositionsName(self, headerIndex):
        return f"{self.sceneName()}_header{headerIndex:02}_playerEntryList"

    def exitListName(self, headerIndex):
        return self.sceneName() + "_header" + format(headerIndex, "02") + "_exitList"

    def lightListName(self, headerIndex):
        return self.sceneName() + "_header" + format(headerIndex, "02") + "_lightSettings"

    def transitionActorListName(self, headerIndex):
        return self.sceneName() + "_header" + format(headerIndex, "02") + "_transitionActors"

    def pathListName(self, headerIndex: int):
        return self.sceneName() + "_pathway" + str(headerIndex)

    def cameraListName(self):
        return self.sceneName() + "_cameraList"

    def cutsceneDataName(self, headerIndex):
        return self.sceneName() + "_header" + format(headerIndex, "02") + "_cutscene"

    def alternateHeadersName(self):
        return self.sceneName() + "_alternateHeaders"

    def hasAlternateHeaders(self):
        return not (
            self.childNightHeader == None
            and self.adultDayHeader == None
            and self.adultNightHeader == None
            and len(self.cutsceneHeaders) == 0
        )

    def validateIndices(self):
        self.collision.cameraData.validateCamPositions()
        self.validateStartPositions()
        self.validateRoomIndices()

    def validateStartPositions(self):
        count = 0
        while count < len(self.startPositions):
            if count not in self.startPositions:
                raise PluginError(
                    "Error: Entrances (start positions) do not have a consecutive list of indices. "
                    + "Missing index: "
                    + str(count)
                )
            count = count + 1

    def validateRoomIndices(self):
        count = 0
        while count < len(self.rooms):
            if count not in self.rooms:
                raise PluginError(
                    "Error: Room indices do not have a consecutive list of indices. " + "Missing index: " + str(count)
                )
            count = count + 1

    def validatePathIndices(self):
        count = 0
        while count < len(self.pathList):
            if count not in self.pathList:
                raise PluginError(
                    "Error: Path list does not have a consecutive list of indices.\n" + "Missing index: " + str(count)
                )
            count = count + 1

    def addRoom(self, roomIndex, roomName, roomShape):
        roomModel = self.model.addSubModel(
            OOTModel(self.model.f3d.F3D_VER, self.model.f3d._HW_VERSION_1, roomName + "_dl", self.model.DLFormat, None)
        )
        room = OOTRoom(roomIndex, roomName, roomModel, roomShape)
        if roomIndex in self.rooms:
            raise PluginError("Repeat room index " + str(roomIndex) + " for " + str(roomName))
        self.rooms[roomIndex] = room
        return room

    def sortEntrances(self):
        self.entranceList = sorted(self.entranceList, key=lambda x: x.startPositionIndex)
        if self.appendNullEntrance:
            self.entranceList.append(OOTEntrance(0, 0))

        if self.childNightHeader is not None:
            self.childNightHeader.sortEntrances()
        if self.adultDayHeader is not None:
            self.adultDayHeader.sortEntrances()
        if self.adultNightHeader is not None:
            self.adultNightHeader.sortEntrances()
        for header in self.cutsceneHeaders:
            header.sortEntrances()

    def copyBgImages(self, exportPath: str):
        for i in range(len(self.rooms)):
            self.rooms[i].mesh.copyBgImages(exportPath)


class OOTBGImage:
    def __init__(self, name: str, image: bpy.types.Image, otherModeFlags: str):
        self.name = name
        self.image = image
        self.otherModeFlags = otherModeFlags

    def getFilename(self) -> str:
        return f"{self.name}.jpg"

    def singlePropertiesC(self, tabDepth: int) -> str:
        return (indent * tabDepth) + (indent * tabDepth).join(
            (
                f"{self.name},\n",
                f"0x00000000,\n",  # (``unk_0C`` in decomp)
                "NULL,\n",
                f"{self.image.size[0]}, {self.image.size[1]},\n",
                f"G_IM_FMT_RGBA, G_IM_SIZ_16b,\n",  # RGBA16
                f"{self.otherModeFlags}, 0x0000",
            )
        )

    def multiPropertiesC(self, tabDepth: int, cameraIndex: int) -> str:
        return (indent * tabDepth) + f"0x0082, {cameraIndex},\n" + self.singlePropertiesC(tabDepth) + "\n"


class OOTRoomMesh:
    def __init__(self, roomName, roomShape, model):
        self.roomName = roomName
        self.roomShape = roomShape
        self.meshEntries = []
        self.model = model
        self.bgImages = []

    def terminateDLs(self):
        for entry in self.meshEntries:
            entry.DLGroup.terminateDLs()

    def headerName(self):
        return str(self.roomName) + "_shapeHeader"

    def entriesName(self):
        return str(self.roomName) + (
            "_shapeDListEntry" if self.roomShape != "ROOM_SHAPE_TYPE_CULLABLE" else "_shapeCullableEntry"
        )

    def addMeshGroup(self, cullGroup):
        meshGroup = OOTRoomMeshGroup(cullGroup, self.model.DLFormat, self.roomName, len(self.meshEntries))
        self.meshEntries.append(meshGroup)
        return meshGroup

    def currentMeshGroup(self):
        return self.meshEntries[-1]

    def removeUnusedEntries(self):
        newList = []
        for meshEntry in self.meshEntries:
            if not meshEntry.DLGroup.isEmpty():
                newList.append(meshEntry)
        self.meshEntries = newList

    def copyBgImages(self, exportPath: str):
        jpegCompatibility = False  # maybe delete some code later if jpeg compatibility improves
        for bgImage in self.bgImages:
            image = bgImage.image
            imageFileName = bgImage.getFilename()
            if jpegCompatibility:
                isPacked = image.packed_file is not None
                if not isPacked:
                    image.pack()
                oldpath = image.filepath
                oldFormat = image.file_format
                try:
                    image.filepath = bpy.path.abspath(os.path.join(exportPath, imageFileName))
                    image.file_format = "JPEG"
                    image.save()
                    if not isPacked:
                        image.unpack()
                    image.filepath = oldpath
                    image.file_format = oldFormat
                except Exception as e:
                    image.filepath = oldpath
                    image.file_format = oldFormat
                    raise Exception(str(e))
            else:
                filepath = bpy.path.abspath(os.path.join(exportPath, imageFileName))
                shutil.copy(bpy.path.abspath(image.filepath), filepath)

    def getMultiBgStructName(self):
        return self.roomName + "BgImage"


class OOTDLGroup:
    def __init__(self, name, DLFormat):
        self.opaque = None
        self.transparent = None
        self.DLFormat = DLFormat
        self.name = toAlnum(name)

    def addDLCall(self, displayList, drawLayer):
        if drawLayer == "Opaque":
            if self.opaque is None:
                self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, self.DLFormat)
            self.opaque.commands.append(SPDisplayList(displayList))
        elif drawLayer == "Transparent":
            if self.transparent is None:
                self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, self.DLFormat)
            self.transparent.commands.append(SPDisplayList(displayList))
        else:
            raise PluginError("Unhandled draw layer: " + str(drawLayer))

    def terminateDLs(self):
        if self.opaque is not None:
            self.opaque.commands.append(SPEndDisplayList())

        if self.transparent is not None:
            self.transparent.commands.append(SPEndDisplayList())

    def createDLs(self):
        if self.opaque is None:
            self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, self.DLFormat)
        if self.transparent is None:
            self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, self.DLFormat)

    def isEmpty(self):
        return self.opaque is None and self.transparent is None


class OOTRoomMeshGroup:
    def __init__(self, cullGroup, DLFormat, roomName, entryIndex):
        self.cullGroup = cullGroup
        self.roomName = roomName
        self.entryIndex = entryIndex

        self.DLGroup = OOTDLGroup(self.entryName(), DLFormat)

    def entryName(self):
        return self.roomName + "_entry_" + str(self.entryIndex)


class OOTRoom(OOTCommonCommands):
    def __init__(self, index, name, model, roomShape):
        self.ownerName = toAlnum(name)
        self.index = index
        self.actorList = set()
        self.mesh = OOTRoomMesh(self.roomName(), roomShape, model)

        # Room behaviour
        self.roomBehaviour = None
        self.disableWarpSongs = False
        self.showInvisibleActors = False
        self.linkIdleMode = None

        self.customBehaviourX = None
        self.customBehaviourY = None

        # Wind
        self.setWind = False
        self.windVector = [0, 0, 0]
        self.windStrength = 0

        # Time
        self.timeHours = 0x00
        self.timeMinutes = 0x00
        self.timeSpeed = 0xA

        # Skybox
        self.disableSkybox = False
        self.disableSunMoon = False

        # Echo
        self.echo = 0x00

        self.objectIDList = []

        self.childNightHeader = None
        self.adultDayHeader = None
        self.adultNightHeader = None
        self.cutsceneHeaders = []

        self.appendNullEntrance = False

    def getAlternateHeaderRoom(self, name):
        room = OOTRoom(self.index, name, self.mesh.model, self.mesh.roomShape)
        room.mesh = self.mesh
        return room

    def roomName(self):
        return self.ownerName + "_room_" + str(self.index)

    def objectListName(self, headerIndex):
        return self.roomName() + "_header" + format(headerIndex, "02") + "_objectList"

    def actorListName(self, headerIndex):
        return self.roomName() + "_header" + format(headerIndex, "02") + "_actorList"

    def alternateHeadersName(self):
        return self.roomName() + "_alternateHeaders"

    def hasAlternateHeaders(self):
        return not (
            self.childNightHeader == None
            and self.adultDayHeader == None
            and self.adultNightHeader == None
            and len(self.cutsceneHeaders) == 0
        )

    def getObjectLengthDefineName(self, headerIndex: int):
        return f"LENGTH_{self.objectListName(headerIndex).upper()}"

    def getActorLengthDefineName(self, headerIndex: int):
        return f"LENGTH_{self.actorListName(headerIndex).upper()}"


def addActor(owner, actor, actorProp, propName, actorObjName):
    sceneSetup = actorProp.headerSettings
    if (
        sceneSetup.sceneSetupPreset == "All Scene Setups"
        or sceneSetup.sceneSetupPreset == "All Non-Cutscene Scene Setups"
    ):
        getattr(owner, propName).add(actor)
        if owner.childNightHeader is not None:
            getattr(owner.childNightHeader, propName).add(actor)
        if owner.adultDayHeader is not None:
            getattr(owner.adultDayHeader, propName).add(actor)
        if owner.adultNightHeader is not None:
            getattr(owner.adultNightHeader, propName).add(actor)
        if sceneSetup.sceneSetupPreset == "All Scene Setups":
            for cutsceneHeader in owner.cutsceneHeaders:
                getattr(cutsceneHeader, propName).add(actor)
    elif sceneSetup.sceneSetupPreset == "Custom":
        if sceneSetup.childDayHeader and owner is not None:
            getattr(owner, propName).add(actor)
        if sceneSetup.childNightHeader and owner.childNightHeader is not None:
            getattr(owner.childNightHeader, propName).add(actor)
        if sceneSetup.adultDayHeader and owner.adultDayHeader is not None:
            getattr(owner.adultDayHeader, propName).add(actor)
        if sceneSetup.adultNightHeader and owner.adultNightHeader is not None:
            getattr(owner.adultNightHeader, propName).add(actor)
        for cutsceneHeader in sceneSetup.cutsceneHeaders:
            if cutsceneHeader.headerIndex >= len(owner.cutsceneHeaders) + 4:
                raise PluginError(
                    actorObjName
                    + " uses a cutscene header index that is outside the range of the current number of cutscene headers."
                )
            getattr(owner.cutsceneHeaders[cutsceneHeader.headerIndex - 4], propName).add(actor)
    else:
        raise PluginError("Unhandled scene setup preset: " + str(sceneSetup.sceneSetupPreset))


def addStartPosition(scene, index, actor, actorProp, actorObjName):
    sceneSetup = actorProp.headerSettings
    if (
        sceneSetup.sceneSetupPreset == "All Scene Setups"
        or sceneSetup.sceneSetupPreset == "All Non-Cutscene Scene Setups"
    ):
        addStartPosAtIndex(scene.startPositions, index, actor)
        if scene.childNightHeader is not None:
            addStartPosAtIndex(scene.childNightHeader.startPositions, index, actor)
        if scene.adultDayHeader is not None:
            addStartPosAtIndex(scene.adultDayHeader.startPositions, index, actor)
        if scene.adultNightHeader is not None:
            addStartPosAtIndex(scene.adultNightHeader.startPositions, index, actor)
        if sceneSetup.sceneSetupPreset == "All Scene Setups":
            for cutsceneHeader in scene.cutsceneHeaders:
                addStartPosAtIndex(cutsceneHeader.startPositions, index, actor)
    elif sceneSetup.sceneSetupPreset == "Custom":
        if sceneSetup.childDayHeader and scene is not None:
            addStartPosAtIndex(scene.startPositions, index, actor)
        if sceneSetup.childNightHeader and scene.childNightHeader is not None:
            addStartPosAtIndex(scene.childNightHeader.startPositions, index, actor)
        if sceneSetup.adultDayHeader and scene.adultDayHeader is not None:
            addStartPosAtIndex(scene.adultDayHeader.startPositions, index, actor)
        if sceneSetup.adultNightHeader and scene.adultNightHeader is not None:
            addStartPosAtIndex(scene.adultNightHeader.startPositions, index, actor)
        for cutsceneHeader in sceneSetup.cutsceneHeaders:
            if cutsceneHeader.headerIndex >= len(scene.cutsceneHeaders) + 4:
                raise PluginError(
                    actorObjName
                    + " uses a cutscene header index that is outside the range of the current number of cutscene headers."
                )
            addStartPosAtIndex(scene.cutsceneHeaders[cutsceneHeader.headerIndex - 4].startPositions, index, actor)
    else:
        raise PluginError("Unhandled scene setup preset: " + str(sceneSetup.sceneSetupPreset))


def addStartPosAtIndex(startPosDict, index, value):
    if index in startPosDict:
        raise PluginError("Error: Repeated start position spawn index: " + str(index))
    startPosDict[index] = value
