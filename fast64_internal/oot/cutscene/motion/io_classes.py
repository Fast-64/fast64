import bpy

from dataclasses import dataclass, field
from bpy.types import Object
from ...oot_constants import ootData
from .utility import getBlenderPosition, getBlenderRotation, getRotation, getInteger


# NOTE: ``paramNumber`` is the expected number of parameters inside the parsed commands,
# this account for the unused parameters. Every classes are based on the commands arguments from ``z64cutscene_commands.h``


@dataclass
class OOTCSMotionBase:
    """This class contains common Cutscene data"""

    params: list[str]

    startFrame: int = None
    endFrame: int = None

    def getEnumValue(self, enumKey: str, index: int, isSeqLegacy: bool = False):
        enum = ootData.enumData.enumByKey[enumKey]
        item = enum.itemById.get(self.params[index])
        if item is None:
            setting = getInteger(self.params[index])
            if isSeqLegacy:
                setting -= 1
            item = enum.itemByIndex.get(setting)
        return item.key if item is not None else self.params[index]


@dataclass
class OOTCSMotionCamPoint(OOTCSMotionBase):
    """This class contains a single Camera Point command data"""

    continueFlag: str = None
    camRoll: int = None
    frame: int = None
    viewAngle: float = None
    pos: list[int, int, int] = field(default_factory=list)
    paramNumber: int = 8

    def __post_init__(self):
        self.continueFlag = self.params[0]
        self.camRoll = getInteger(self.params[1])
        self.frame = getInteger(self.params[2])
        self.viewAngle = float(self.params[3][:-1])
        self.pos = [getInteger(self.params[4]), getInteger(self.params[5]), getInteger(self.params[6])]


@dataclass
class OOTCSMotionActorCue(OOTCSMotionBase):
    """This class contains a single Actor Cue command data"""

    actionID: int = None
    rot: list[str, str, str] = field(default_factory=list)
    startPos: list[int, int, int] = field(default_factory=list)
    endPos: list[int, int, int] = field(default_factory=list)
    paramNumber: int = 15

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.actionID = getInteger(self.params[0])
        self.rot = [getRotation(self.params[3]), getRotation(self.params[4]), getRotation(self.params[5])]
        self.startPos = [getInteger(self.params[6]), getInteger(self.params[7]), getInteger(self.params[8])]
        self.endPos = [getInteger(self.params[9]), getInteger(self.params[10]), getInteger(self.params[11])]


@dataclass
class OOTCSMotionActorCueList(OOTCSMotionBase):
    """This class contains the Actor Cue List command data"""

    isPlayer: bool = False
    commandType: str = None
    entryTotal: int = None
    entries: list[OOTCSMotionActorCue] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "actorCueList"

    def __post_init__(self):
        if self.isPlayer:
            self.commandType = "Player"
            self.entryTotal = getInteger(self.params[0])
        else:
            self.commandType = self.params[0]
            if self.commandType.startswith("0x"):
                # make it a 4 digit hex
                self.commandType = self.commandType.removeprefix("0x")
                self.commandType = "0x" + "0" * (4 - len(self.commandType)) + self.commandType
            self.entryTotal = getInteger(self.params[1].strip())


@dataclass
class OOTCSMotionCamEyeSpline(OOTCSMotionBase):
    """This class contains the Camera Eye Spline data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeSplineList"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[0])
        self.endFrame = getInteger(self.params[1])


@dataclass
class OOTCSMotionCamATSpline(OOTCSMotionBase):
    """This class contains the Camera AT (look-at) Spline data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATSplineList"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[0])
        self.endFrame = getInteger(self.params[1])


@dataclass
class OOTCSMotionCamEyeSplineRelToPlayer(OOTCSMotionBase):
    """This class contains the Camera Eye Spline Relative to the Player data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeSplineRelPlayerList"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[0])
        self.endFrame = getInteger(self.params[1])


@dataclass
class OOTCSMotionCamATSplineRelToPlayer(OOTCSMotionBase):
    """This class contains the Camera AT Spline Relative to the Player data"""

    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATSplineRelPlayerList"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[0])
        self.endFrame = getInteger(self.params[1])


@dataclass
class OOTCSMotionCamEye(OOTCSMotionBase):
    """This class contains a single Camera Eye point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeList"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[0])
        self.endFrame = getInteger(self.params[1])


@dataclass
class OOTCSMotionCamAT(OOTCSMotionBase):
    """This class contains a single Camera AT point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATList"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[0])
        self.endFrame = getInteger(self.params[1])


@dataclass
class OOTCSMotionMisc(OOTCSMotionBase):
    """This class contains a single misc command entry"""

    type: str = None  # see ``CutsceneMiscType`` in decomp
    paramNumber: int = 14

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.type = self.getEnumValue("csMiscType", 0)


@dataclass
class OOTCSMotionMiscList(OOTCSMotionBase):
    """This class contains Misc command data"""

    entryTotal: int = None
    entries: list[OOTCSMotionMisc] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "miscList"

    def __post_init__(self):
        self.entryTotal = getInteger(self.params[0])


@dataclass
class OOTCSMotionTransition(OOTCSMotionBase):
    """This class contains Transition command data"""

    type: str = None
    paramNumber: int = 3
    listName: str = "transitionList"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.type = self.getEnumValue("csTransitionType", 0)


@dataclass
class OOTCSMotionText(OOTCSMotionBase):
    """This class contains Text command data"""

    textId: int = None
    type: str = None
    altTextId1: int = None
    altTextId2: int = None
    paramNumber: int = 6
    id: str = "Text"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.textId = getInteger(self.params[0])
        self.type = self.getEnumValue("csTextType", 3)
        self.altTextId1 = (getInteger(self.params[4]),)
        self.altTextId2 = (getInteger(self.params[5]),)


@dataclass
class OOTCSMotionTextNone(OOTCSMotionBase):
    """This class contains Text None command data"""

    paramNumber: int = 2
    id: str = "None"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[0])
        self.endFrame = getInteger(self.params[1])


@dataclass
class OOTCSMotionTextOcarinaAction(OOTCSMotionBase):
    """This class contains Text Ocarina Action command data"""

    ocarinaActionId: str = None
    messageId: int = None
    paramNumber: int = 4
    id: str = "OcarinaAction"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.ocarinaActionId = self.getEnumValue("ocarinaSongActionId", 0)
        self.messageId = getInteger(self.params[3])


@dataclass
class OOTCSMotionTextList(OOTCSMotionBase):
    """This class contains Text List command data"""

    entryTotal: int = None
    entries: list[OOTCSMotionText | OOTCSMotionTextNone | OOTCSMotionTextOcarinaAction] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "textList"

    def __post_init__(self):
        self.entryTotal = getInteger(self.params[0])


@dataclass
class OOTCSMotionLightSetting(OOTCSMotionBase):
    """This class contains Light Setting command data"""

    isLegacy: bool = None
    lightSetting: int = None
    paramNumber: int = 11

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.lightSetting = getInteger(self.params[0])
        if self.isLegacy:
            self.lightSetting -= 1


@dataclass
class OOTCSMotionLightSettingList(OOTCSMotionBase):
    """This class contains Light Setting List command data"""

    entryTotal: int = None
    entries: list[OOTCSMotionLightSetting] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "lightSettingsList"

    def __post_init__(self):
        self.entryTotal = getInteger(self.params[0])


@dataclass
class OOTCSMotionTime(OOTCSMotionBase):
    """This class contains Time Ocarina Action command data"""

    hour: int = None
    minute: int = None
    paramNumber: int = 5

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.hour = getInteger(self.params[3])
        self.minute = getInteger(self.params[4])


@dataclass
class OOTCSMotionTimeList(OOTCSMotionBase):
    """This class contains Time List command data"""

    entryTotal: int = None
    entries: list[OOTCSMotionTime] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "timeList"

    def __post_init__(self):
        self.entryTotal = getInteger(self.params[0])


@dataclass
class OOTCSMotionStartStopSeq(OOTCSMotionBase):
    """This class contains Start/Stop Seq command data"""

    isLegacy: bool = None
    seqId: str = None
    paramNumber: int = 11

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.seqId = self.getEnumValue("seqId", 0, self.isLegacy)


@dataclass
class OOTCSMotionStartStopSeqList(OOTCSMotionBase):
    """This class contains Start/Stop Seq List command data"""

    entryTotal: int = None
    type: str = None
    entries: list[OOTCSMotionStartStopSeq] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "seqList"

    def __post_init__(self):
        self.entryTotal = getInteger(self.params[0])


@dataclass
class OOTCSMotionFadeSeq(OOTCSMotionBase):
    """This class contains Fade Seq command data"""

    seqPlayer: str = None
    paramNumber: int = 11
    enumKey: str = "csFadeOutSeqPlayer"

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.seqPlayer = self.getEnumValue("csFadeOutSeqPlayer", 0)


@dataclass
class OOTCSMotionFadeSeqList(OOTCSMotionBase):
    """This class contains Fade Seq List command data"""

    entryTotal: int = None
    entries: list[OOTCSMotionFadeSeq] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "fadeSeqList"

    def __post_init__(self):
        self.entryTotal = getInteger(self.params[0])


@dataclass
class OOTCSMotionRumbleController(OOTCSMotionBase):
    """This class contains Rumble Controller command data"""

    sourceStrength: int = None
    duration: int = None
    decreaseRate: int = None
    paramNumber: int = 8

    def __post_init__(self):
        self.startFrame = getInteger(self.params[1])
        self.endFrame = getInteger(self.params[2])
        self.sourceStrength = getInteger(self.params[3])
        self.duration = getInteger(self.params[4])
        self.decreaseRate = getInteger(self.params[5])


@dataclass
class OOTCSMotionRumbleControllerList(OOTCSMotionBase):
    """This class contains Rumble Controller List command data"""

    entryTotal: int = None
    entries: list[OOTCSMotionRumbleController] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "rumbleList"

    def __post_init__(self):
        self.entryTotal = getInteger(self.params[0])


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
    textList: list[OOTCSMotionTextList] = field(default_factory=list)
    lightSettingsList: list[OOTCSMotionLightSettingList] = field(default_factory=list)
    timeList: list[OOTCSMotionTimeList] = field(default_factory=list)
    seqList: list[OOTCSMotionStartStopSeqList] = field(default_factory=list)
    fadeSeqList: list[OOTCSMotionFadeSeqList] = field(default_factory=list)
    rumbleList: list[OOTCSMotionRumbleControllerList] = field(default_factory=list)


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
