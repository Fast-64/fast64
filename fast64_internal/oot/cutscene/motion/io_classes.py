import bpy

from dataclasses import dataclass, field
from bpy.types import Object
from ...oot_utility import getEnumIndex
from .constants import ootEnumCSActorCueListCommandType


@dataclass
class OOTCSMotionBase:
    startFrame: int
    endFrame: int


@dataclass
class OOTCSMotionCamPoint:
    continueFlag: str
    camRoll: int
    frame: int
    viewAngle: float
    pos: list[int, int, int]


@dataclass
class OOTCSMotionActorCue(OOTCSMotionBase):
    actionID: str
    rot: list[str, str, str]
    startPos: list[int, int, int]
    endPos: list[int, int, int]


@dataclass
class OOTCSMotionActorCueList:
    commandType: str
    entryTotal: int
    entries: list[OOTCSMotionActorCue] = field(default_factory=list)


@dataclass
class OOTCSMotionCamEyeSpline(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamATSpline(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamEyeSplineRelToPlayer(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamATSplineRelToPlayer(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamEye(OOTCSMotionBase):
    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)


@dataclass
class OOTCSMotionCamAT(OOTCSMotionBase):
    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)


@dataclass
class OOTCSMotionCutscene:
    name: str
    totalEntries: int
    frameCount: int

    actorCueList: list[OOTCSMotionActorCueList] = field(default_factory=list)
    playerCueList: list[OOTCSMotionActorCueList] = field(default_factory=list)
    camEyeSplineList: list[OOTCSMotionCamEyeSpline] = field(default_factory=list)
    camATSplineList: list[OOTCSMotionCamATSpline] = field(default_factory=list)
    camEyeSplineRelPlayerList: list[OOTCSMotionCamEyeSplineRelToPlayer] = field(default_factory=list)
    camATSplineRelPlayerList: list[OOTCSMotionCamATSplineRelToPlayer] = field(default_factory=list)
    camEyeList: list[OOTCSMotionCamEye] = field(default_factory=list)
    camATList: list[OOTCSMotionCamAT] = field(default_factory=list)


class OOTCSMotionObjectFactory:
    def getNewObject(self, name: str, data, selectObject: bool, parentObj: Object) -> Object:
        newObj = bpy.data.objects.new(name=name, object_data=data)
        bpy.context.view_layer.active_layer_collection.collection.objects.link(newObj)
        if selectObject:
            newObj.select_set(True)
            bpy.context.view_layer.objects.active = newObj
        newObj.parent = parentObj
        return newObj

    def getNewEmptyObject(self, name: str, selectObject: bool, parentObj: Object):
        return self.getNewObject(name, None, selectObject, parentObj)

    def getNewArmatureObject(self, name: str, selectObject: bool, parentObj: Object):
        newArmatureData = bpy.data.armatures.new(name)
        newArmatureData.display_type = "STICK"
        newArmatureData.show_names = True
        return self.getNewObject(name, newArmatureData, selectObject, parentObj)

    def getNewCutsceneObject(self, name: str, frameCount: int, parentObj: Object):
        newCSObj = self.getNewEmptyObject(name, True, parentObj)
        newCSObj.ootEmptyType = "Cutscene"
        newCSObj.ootCutsceneProperty.csEndFrame = frameCount
        return newCSObj

    def getNewActorCueListObject(self, name: str, commandType: str, parentObj: Object):
        newActorCueListObj = self.getNewEmptyObject(name, False, parentObj)
        newActorCueListObj.ootEmptyType = f"CS {'Player' if 'Player' in name else 'Actor'} Cue List"
        index = getEnumIndex(ootEnumCSActorCueListCommandType, commandType)

        if index is not None:
            cmdType = ootEnumCSActorCueListCommandType[index][0]
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = cmdType
        else:
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = "Custom"
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandTypeCustom = commandType

        return newActorCueListObj

    def getNewActorCueObject(
        self,
        name: str,
        startFrame: int,
        endFrame: int,
        actionID: str,
        location: list[int],
        rot: list[str],
        parentObj: Object,
    ):
        newActorCueObj = self.getNewEmptyObject(name, False, parentObj)
        newActorCueObj.location = self.getBlenderPosition(location, bpy.context.scene.ootBlenderScale)
        newActorCueObj.empty_display_type = "ARROWS"
        newActorCueObj.rotation_mode = "XZY"
        newActorCueObj.rotation_euler = self.getBlenderRotation(rot)
        newActorCueObj.ootEmptyType = f"CS {'Actor' if 'Actor' in name else 'Player'} Cue"
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueStartFrame = startFrame
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueEndFrame = endFrame
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueActionID = actionID
        return newActorCueObj

    def getNewCameraObject(
        self, name: str, displaySize: float, clipStart: float, clipEnd: float, alpha: float, parentObj: Object
    ):
        newCamera = bpy.data.cameras.new(name)
        newCameraObj = self.getNewObject(name, newCamera, False, parentObj)
        newCameraObj.data.display_size = displaySize
        newCameraObj.data.clip_start = clipStart
        newCameraObj.data.clip_end = clipEnd
        newCameraObj.data.passepartout_alpha = alpha
        return newCameraObj
