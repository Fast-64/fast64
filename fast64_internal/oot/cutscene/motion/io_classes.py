import bpy

from dataclasses import dataclass, field
from bpy.types import Object
from ...oot_constants import ootData
from .utility import getBlenderPosition, getBlenderRotation


# NOTE: ``paramNumber`` is the expected number of parameters inside the parsed commands,
# this account for the unused parameters. Every classes are based on the commands arguments from ``z64cutscene_commands.h``


@dataclass
class OOTCSMotionBase:
    """This class contains common Cutscene data"""

    startFrame: int
    endFrame: int


@dataclass
class OOTCSMotionCamPoint:
    """This class contains a single Camera Point command data"""

    continueFlag: str
    camRoll: int
    frame: int
    viewAngle: float
    pos: list[int, int, int]
    paramNumber: int = 8


@dataclass
class OOTCSMotionActorCue(OOTCSMotionBase):
    """This class contains a single Actor Cue command data"""

    actionID: int
    rot: list[str, str, str]
    startPos: list[int, int, int]
    endPos: list[int, int, int]
    paramNumber: int = 15


@dataclass
class OOTCSMotionActorCueList:
    """This class contains the Actor Cue List command data"""

    commandType: str
    entryTotal: int
    entries: list[OOTCSMotionActorCue] = field(default_factory=list)
    paramNumber: int = 2


@dataclass
class OOTCSMotionCamEyeSpline(OOTCSMotionBase):
    """This class contains the Camera Eye Spline data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2


@dataclass
class OOTCSMotionCamATSpline(OOTCSMotionBase):
    """This class contains the Camera AT (look-at) Spline data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2


@dataclass
class OOTCSMotionCamEyeSplineRelToPlayer(OOTCSMotionBase):
    """This class contains the Camera Eye Spline Relative to the Player data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2


@dataclass
class OOTCSMotionCamATSplineRelToPlayer(OOTCSMotionBase):
    """This class contains the Camera AT Spline Relative to the Player data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2


@dataclass
class OOTCSMotionCamEye(OOTCSMotionBase):
    """This class contains a single Camera Eye point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2


@dataclass
class OOTCSMotionCamAT(OOTCSMotionBase):
    """This class contains a single Camera AT point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2


@dataclass
class OOTCSMotionMisc(OOTCSMotionBase):
    """This class contains a single misc command entry"""

    type: str  # see ``CutsceneMiscType`` in decomp
    paramNumber: int = 14


@dataclass
class OOTCSMotionMiscList:
    """This class contains Misc command data"""

    entryTotal: int
    entries: list[OOTCSMotionMisc] = field(default_factory=list)
    paramNumber: int = 1


@dataclass
class OOTCSMotionTransition(OOTCSMotionBase):
    """This class contains Transition command data"""

    type: str
    paramNumber: int = 3


@dataclass
class OOTCSMotionCutscene:
    """This class contains a Cutscene's data, including every commands' data"""

    name: str
    totalEntries: int
    frameCount: int
    paramNumber: int = 2

    actorCueList: list[OOTCSMotionActorCueList] = field(default_factory=list)
    playerCueList: list[OOTCSMotionActorCueList] = field(default_factory=list)
    camEyeSplineList: list[OOTCSMotionCamEyeSpline] = field(default_factory=list)
    camATSplineList: list[OOTCSMotionCamATSpline] = field(default_factory=list)
    camEyeSplineRelPlayerList: list[OOTCSMotionCamEyeSplineRelToPlayer] = field(default_factory=list)
    camATSplineRelPlayerList: list[OOTCSMotionCamATSplineRelToPlayer] = field(default_factory=list)
    camEyeList: list[OOTCSMotionCamEye] = field(default_factory=list)
    camATList: list[OOTCSMotionCamAT] = field(default_factory=list)
    miscList: list[OOTCSMotionMiscList] = field(default_factory=list)
    transitionList: list[OOTCSMotionTransition] = field(default_factory=list)


class OOTCSMotionObjectFactory:
    """This class contains functions to create new Blender objects"""

    def getNewObject(self, name: str, data, selectObject: bool, parentObj: Object) -> Object:
        newObj = bpy.data.objects.new(name=name, object_data=data)
        bpy.context.view_layer.active_layer_collection.collection.objects.link(newObj)
        if selectObject:
            newObj.select_set(True)
            bpy.context.view_layer.objects.active = newObj
        newObj.parent = parentObj
        newObj.location = [0.0, 0.0, 0.0]
        newObj.rotation_euler = [0.0, 0.0, 0.0]
        newObj.scale = [1.0, 1.0, 1.0]
        return newObj

    def getNewEmptyObject(self, name: str, selectObject: bool, parentObj: Object):
        return self.getNewObject(name, None, selectObject, parentObj)

    def getNewArmatureObject(self, name: str, selectObject: bool, parentObj: Object):
        newArmatureData = bpy.data.armatures.new(name)
        newArmatureData.display_type = "STICK"
        newArmatureData.show_names = True
        newArmatureObject = self.getNewObject(name, newArmatureData, selectObject, parentObj)
        return newArmatureObject

    def getNewCutsceneObject(self, name: str, frameCount: int, parentObj: Object):
        newCSObj = self.getNewEmptyObject(name, True, parentObj)
        newCSObj.ootEmptyType = "Cutscene"
        newCSObj.ootCutsceneProperty.csEndFrame = frameCount
        return newCSObj

    def getNewActorCueListObject(self, name: str, commandType: str, parentObj: Object):
        newActorCueListObj = self.getNewEmptyObject(name, False, parentObj)
        newActorCueListObj.ootEmptyType = f"CS {'Player' if 'Player' in name else 'Actor'} Cue List"
        cmdEnum = ootData.enumData.enumByKey["csCmd"]

        if commandType == "Player":
            commandType = "player_cue"

        index = cmdEnum.itemByKey[commandType].index if commandType in cmdEnum.itemByKey else int(commandType, base=16)
        item = cmdEnum.itemByIndex.get(index)

        if item is not None:
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = item.key
        else:
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = "Custom"
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandTypeCustom = commandType

        return newActorCueListObj

    def getNewActorCueObject(
        self,
        name: str,
        startFrame: int,
        actionID: int | str,
        location: list[int],
        rot: list[str],
        parentObj: Object,
    ):
        isDummy = "(D)" in name
        isPlayer = not isDummy and not "Actor" in name

        newActorCueObj = self.getNewEmptyObject(name, False, parentObj)
        newActorCueObj.location = getBlenderPosition(location, bpy.context.scene.ootBlenderScale)
        newActorCueObj.empty_display_type = "ARROWS"
        newActorCueObj.rotation_mode = "XZY"
        newActorCueObj.rotation_euler = getBlenderRotation(rot)
        emptyType = "Dummy" if isDummy else "Player" if isPlayer else "Actor"
        newActorCueObj.ootEmptyType = f"CS {emptyType} Cue"
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueStartFrame = startFrame

        item = None
        if isPlayer:
            playerEnum = ootData.enumData.enumByKey["csPlayerCueId"]
            if isinstance(actionID, int):
                item = playerEnum.itemByIndex.get(actionID)
            else:
                item = playerEnum.itemByKey.get(actionID)

        if item is not None:
            newActorCueObj.ootCSMotionProperty.actorCueProp.playerCueID = item.key
        elif not isDummy:
            if isPlayer:
                newActorCueObj.ootCSMotionProperty.actorCueProp.playerCueID = "Custom"

            if isinstance(actionID, int):
                cueActionID = f"0x{actionID:04X}"
            else:
                cueActionID = actionID

            newActorCueObj.ootCSMotionProperty.actorCueProp.cueActionID = cueActionID

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

    def getNewActorCuePreviewObject(self, name: str, selectObject, parentObj: Object):
        newPreviewObj = self.getNewEmptyObject(name, selectObject, parentObj)
        newPreviewObj.ootEmptyType = f"CS {'Actor' if 'Actor' in name else 'Player'} Cue Preview"
        return newPreviewObj
