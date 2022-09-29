import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..utility import *
from .oot_utility import *
from .oot_constants import *
from ..f3d.f3d_gbi import *
from .oot_collision_classes import *
from .oot_model_classes import *
from .oot_spline import OOTPath


class OOTActor:
    def __init__(self, actorID, position, rotation, actorParam, rotOverride):
        self.actorID = actorID
        self.actorParam = actorParam
        self.rotOverride = rotOverride
        self.position = position
        self.rotation = rotation


class OOTTransitionActor:
    def __init__(self, actorID, frontRoom, backRoom, frontCam, backCam, position, rotationY, actorParam):
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

    def getBlendFogShort(self):
        return "0x{:04X}".format((self.transitionSpeed << 10) | self.fogNear)


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


class OOTScene:
    def __init__(self, name: str, model: OOTModel):
        """Initialises the class"""
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

        # Camera
        self.mapLocation = None
        self.cameraMode = None

        self.musicSeq = None
        self.nightSeq = None

        self.childNightHeader = None
        self.adultDayHeader = None
        self.adultNightHeader = None
        self.cutsceneHeaders = []

        self.exitList = []
        self.pathList: dict[int, OOTPath] = {}
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

    def getAlternateHeaderScene(self, name: str):
        """Returns a new ``OOTScene()`` for the wanted header"""
        scene = OOTScene(name, self.model)
        scene.write_dummy_room_list = self.write_dummy_room_list
        scene.rooms = self.rooms
        scene.collision = self.collision
        scene.exitList = self.exitList
        scene.pathList = self.pathList
        scene.cameraList = self.cameraList
        return scene

    def sceneName(self):
        """Returns the scene's name"""
        return f"{self.name}_scene"

    def sceneHeaderName(self, headerIndex: int):
        """Returns the scene's name with the current header index in it"""
        return f"{self.sceneName()}_header{headerIndex:02}"

    def roomListName(self):
        return self.sceneName() + "_roomList"

    def entranceListName(self, headerIndex: int):
        return f"{self.sceneHeaderName(headerIndex)}_entranceList"

    def startPositionsName(self, headerIndex: int):
        return f"{self.sceneHeaderName(headerIndex)}_startPositionList"

    def exitListName(self, headerIndex: int):
        return f"{self.sceneHeaderName(headerIndex)}_exitList"

    def lightListName(self, headerIndex: int):
        return f"{self.sceneHeaderName(headerIndex)}_lightSettings"

    def transitionActorListName(self, headerIndex: int):
        return f"{self.sceneHeaderName(headerIndex)}_transitionActors"

    def pathListName(self):
        return self.sceneName() + "_pathway"

    def cameraListName(self):
        return self.sceneName() + "_cameraList"

    def cutsceneDataName(self, headerIndex: int):
        return f"{self.sceneHeaderName(headerIndex)}_cutscene"

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
        """Checks if the scene's indices are all correct"""
        self.collision.cameraData.validateCamPositions() # ``collision.cameraData`` type: ``OOTCameraData``
        self.validateStartPositions()
        self.validateRoomIndices()
        self.validatePathIndices()

    def validateStartPositions(self):
        for index in range(len(self.startPositions)):
            if not (index in self.startPositions):
                raise PluginError(
                    "Error: Entrances (start positions) do not have a consecutive list of indices. "
                    + f"Missing index: {index}"
                )

    def validateRoomIndices(self):
        for index in range(len(self.rooms)):
            if not (index in self.rooms):
                raise PluginError(
                    f"Error: Room indices do not have a consecutive list of indices. Missing index: {index}"
                )

    def validatePathIndices(self):
        for index in range(len(self.pathList)):
            if not (index in self.pathList):
                raise PluginError(
                    f"Error: Path list does not have a consecutive list of indices. Missing index: {index}"
                )

    def addRoom(self, roomIndex: int, roomName: str, roomShape: str):
        """Adds a new room"""
        roomModel = self.model.addSubModel(
            OOTModel(self.model.f3d.F3D_VER, self.model.f3d._HW_VERSION_1, f"{roomName}_dl", self.model.DLFormat, None)
        )
        room = OOTRoom(roomIndex, roomName, roomModel, roomShape)

        if roomIndex in self.rooms:
            raise PluginError(f"Error: Repeated room index for room '{roomName}': {roomIndex}")

        self.rooms[roomIndex] = room
        return room


class OOTRoomMesh:
    def __init__(self, roomName: str, roomShape: str, model: OOTModel):
        self.roomName = roomName
        self.roomShape = roomShape
        self.meshEntries = []
        self.model = model

    def terminateDLs(self):
        for entry in self.meshEntries:
            entry.DLGroup.terminateDLs()

    def headerName(self):
        return f"{self.roomName}_shapeHeader"

    def entriesName(self):
        entryName = "shapeDListEntry" if self.roomShape == "ROOM_SHAPE_TYPE_NORMAL" else "shapeCullableEntry"
        return f"{self.roomName}_{entryName}"

    def addMeshGroup(self, cullGroup: CullGroup):
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


class OOTDLGroup:
    def __init__(self, name: str, dlFormat: DLFormat):
        self.opaque = None
        self.transparent = None
        self.dlFormat = dlFormat
        self.name = toAlnum(name)

    def addDLCall(self, displayList: GfxList, drawLayer: str):
        if drawLayer == "Opaque":
            if self.opaque is None:
                self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, self.dlFormat)
            self.opaque.commands.append(SPDisplayList(displayList))
        elif drawLayer == "Transparent":
            if self.transparent is None:
                self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, self.dlFormat)
            self.transparent.commands.append(SPDisplayList(displayList))
        else:
            raise PluginError(f"Unhandled draw layer: {drawLayer}")

    def terminateDLs(self):
        if self.opaque is not None:
            self.opaque.commands.append(SPEndDisplayList())

        if self.transparent is not None:
            self.transparent.commands.append(SPEndDisplayList())

    def createDLs(self):
        if self.opaque is None:
            self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, self.dlFormat)
        if self.transparent is None:
            self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, self.dlFormat)

    def isEmpty(self):
        return self.opaque is None and self.transparent is None


class OOTRoomMeshGroup:
    def __init__(self, cullGroup: CullGroup, dlFormat: DLFormat, roomName: str, entryIndex: int):
        self.cullGroup = cullGroup
        self.roomName = roomName
        self.entryIndex = entryIndex

        self.DLGroup = OOTDLGroup(self.entryName(), dlFormat)

    def entryName(self):
        return f"{self.roomName}_entry_{self.entryIndex}"


class OOTRoom:
    def __init__(self, index: int, name: str, model: OOTModel, roomShape: str):
        self.ownerName = toAlnum(name)
        self.index = index
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

        # Other
        self.objectIDList = []

        # @TODO: check if ``actorList`` really need to be a set
        self.actorList = set()  # filled in ``add_actor()`` (called by ``ootProcessEmpties``)

        # Other layers
        self.childNightHeader = None
        self.adultDayHeader = None
        self.adultNightHeader = None
        self.cutsceneHeaders = []

    def getAlternateHeaderRoom(self, name: str):
        room = OOTRoom(self.index, name, self.mesh.model, self.mesh.roomShape)
        room.mesh = self.mesh
        return room

    def roomName(self):
        return f"{self.ownerName}_room_{self.index}"

    def roomHeaderName(self, headerIndex: int):
        """Returns the room's name with the current header index in it"""
        return f"{self.roomName()}_header{headerIndex:02}"

    def objectListName(self, headerIndex: int):
        return f"{self.roomHeaderName(headerIndex)}_objectList"

    def actorListName(self, headerIndex: int):
        return f"{self.roomHeaderName(headerIndex)}_actorList"

    def alternateHeadersName(self):
        return f"{self.roomName()}_alternateHeaders"

    def hasAlternateHeaders(self):
        return not (
            self.childNightHeader == None
            and self.adultDayHeader == None
            and self.adultNightHeader == None
            and len(self.cutsceneHeaders) == 0
        )


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
            addAtStartPosIndex(scene.cutsceneHeaders[cutsceneHeader.headerIndex - 4].startPositions, index, actor)
    else:
        raise PluginError("Unhandled scene setup preset: " + str(sceneSetup.sceneSetupPreset))


def addStartPosAtIndex(startPosDict, index, value):
    if index in startPosDict:
        raise PluginError("Error: Repeated start position spawn index: " + str(index))
    startPosDict[index] = value
