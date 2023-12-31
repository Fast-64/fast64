import bpy

from dataclasses import dataclass, field
from bpy.types import Object
from typing import Optional
from ..oot_constants import ootData
from .motion.utility import getBlenderPosition, getBlenderRotation, getRotation, getInteger


# NOTE: ``paramNumber`` is the expected number of parameters inside the parsed commands,
# this account for the unused parameters. Every classes are based on the commands arguments from ``z64cutscene_commands.h``


@dataclass
class CutsceneCmdBase:
    """This class contains common Cutscene data"""

    params: list[str]

    startFrame: Optional[int] = None
    endFrame: Optional[int] = None

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
class CutsceneCmdCamPoint(CutsceneCmdBase):
    """This class contains a single Camera Point command data"""

    continueFlag: Optional[str] = None
    camRoll: Optional[int] = None
    frame: Optional[int] = None
    viewAngle: Optional[float] = None
    pos: list[int] = field(default_factory=list)
    paramNumber: int = 8

    def __post_init__(self):
        if self.params is not None:
            self.continueFlag = self.params[0]
            self.camRoll = getInteger(self.params[1])
            self.frame = getInteger(self.params[2])
            self.viewAngle = float(self.params[3][:-1])
            self.pos = [getInteger(self.params[4]), getInteger(self.params[5]), getInteger(self.params[6])]


@dataclass
class CutsceneCmdActorCue(CutsceneCmdBase):
    """This class contains a single Actor Cue command data"""

    actionID: Optional[int] = None
    rot: list[str] = field(default_factory=list)
    startPos: list[int] = field(default_factory=list)
    endPos: list[int] = field(default_factory=list)
    paramNumber: int = 15

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.actionID = getInteger(self.params[0])
            self.rot = [getRotation(self.params[3]), getRotation(self.params[4]), getRotation(self.params[5])]
            self.startPos = [getInteger(self.params[6]), getInteger(self.params[7]), getInteger(self.params[8])]
            self.endPos = [getInteger(self.params[9]), getInteger(self.params[10]), getInteger(self.params[11])]


@dataclass
class CutsceneCmdActorCueList(CutsceneCmdBase):
    """This class contains the Actor Cue List command data"""

    isPlayer: bool = False
    commandType: Optional[str] = None
    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdActorCue] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "actorCueList"

    def __post_init__(self):
        if self.params is not None:
            if self.isPlayer:
                self.commandType = "Player"
                self.entryTotal = getInteger(self.params[0])
            else:
                self.commandType = self.params[0]
                if self.commandType.startswith("0x"):
                    # make it a 4 digit hex
                    self.commandType = self.commandType.removeprefix("0x")
                    self.commandType = "0x" + "0" * (4 - len(self.commandType)) + self.commandType
                else:
                    self.commandType = ootData.enumData.enumByKey["csCmd"].itemById[self.commandType].key
                self.entryTotal = getInteger(self.params[1].strip())


@dataclass
class CutsceneCmdCamEyeSpline(CutsceneCmdBase):
    """This class contains the Camera Eye Spline data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeSplineList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])


@dataclass
class CutsceneCmdCamATSpline(CutsceneCmdBase):
    """This class contains the Camera AT (look-at) Spline data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATSplineList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])


@dataclass
class CutsceneCmdCamEyeSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera Eye Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeSplineRelPlayerList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])


@dataclass
class CutsceneCmdCamATSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera AT Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATSplineRelPlayerList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])


@dataclass
class CutsceneCmdCamEye(CutsceneCmdBase):
    """This class contains a single Camera Eye point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])


@dataclass
class CutsceneCmdCamAT(CutsceneCmdBase):
    """This class contains a single Camera AT point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])


@dataclass
class CutsceneCmdMisc(CutsceneCmdBase):
    """This class contains a single misc command entry"""

    type: Optional[str] = None  # see ``CutsceneMiscType`` in decomp
    paramNumber: int = 14

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.type = self.getEnumValue("csMiscType", 0)


@dataclass
class CutsceneCmdMiscList(CutsceneCmdBase):
    """This class contains Misc command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdMisc] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "miscList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])


@dataclass
class CutsceneCmdTransition(CutsceneCmdBase):
    """This class contains Transition command data"""

    type: Optional[str] = None
    paramNumber: int = 3
    listName: str = "transitionList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.type = self.getEnumValue("csTransitionType", 0)


@dataclass
class CutsceneCmdText(CutsceneCmdBase):
    """This class contains Text command data"""

    textId: Optional[int] = None
    type: Optional[str] = None
    altTextId1: Optional[int] = None
    altTextId2: Optional[int] = None
    paramNumber: int = 6
    id: str = "Text"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.textId = getInteger(self.params[0])
            self.type = self.getEnumValue("csTextType", 3)
            self.altTextId1 = (getInteger(self.params[4]),)
            self.altTextId2 = (getInteger(self.params[5]),)


@dataclass
class CutsceneCmdTextNone(CutsceneCmdBase):
    """This class contains Text None command data"""

    paramNumber: int = 2
    id: str = "None"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])


@dataclass
class CutsceneCmdTextOcarinaAction(CutsceneCmdBase):
    """This class contains Text Ocarina Action command data"""

    ocarinaActionId: Optional[str] = None
    messageId: Optional[int] = None
    paramNumber: int = 4
    id: str = "OcarinaAction"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.ocarinaActionId = self.getEnumValue("ocarinaSongActionId", 0)
            self.messageId = getInteger(self.params[3])


@dataclass
class CutsceneCmdTextList(CutsceneCmdBase):
    """This class contains Text List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdText | CutsceneCmdTextNone | CutsceneCmdTextOcarinaAction] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "textList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])


@dataclass
class CutsceneCmdLightSetting(CutsceneCmdBase):
    """This class contains Light Setting command data"""

    isLegacy: Optional[bool] = None
    lightSetting: Optional[int] = None
    paramNumber: int = 11

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.lightSetting = getInteger(self.params[0])
            if self.isLegacy:
                self.lightSetting -= 1


@dataclass
class CutsceneCmdLightSettingList(CutsceneCmdBase):
    """This class contains Light Setting List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdLightSetting] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "lightSettingsList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])


@dataclass
class CutsceneCmdTime(CutsceneCmdBase):
    """This class contains Time Ocarina Action command data"""

    hour: Optional[int] = None
    minute: Optional[int] = None
    paramNumber: int = 5

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.hour = getInteger(self.params[3])
            self.minute = getInteger(self.params[4])


@dataclass
class CutsceneCmdTimeList(CutsceneCmdBase):
    """This class contains Time List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdTime] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "timeList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])


@dataclass
class CutsceneCmdStartStopSeq(CutsceneCmdBase):
    """This class contains Start/Stop Seq command data"""

    isLegacy: Optional[bool] = None
    seqId: Optional[str] = None
    paramNumber: int = 11

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.seqId = self.getEnumValue("seqId", 0, self.isLegacy)


@dataclass
class CutsceneCmdStartStopSeqList(CutsceneCmdBase):
    """This class contains Start/Stop Seq List command data"""

    entryTotal: Optional[int] = None
    type: Optional[str] = None
    entries: list[CutsceneCmdStartStopSeq] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "seqList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])


@dataclass
class CutsceneCmdFadeSeq(CutsceneCmdBase):
    """This class contains Fade Seq command data"""

    seqPlayer: Optional[str] = None
    paramNumber: int = 11
    enumKey: str = "csFadeOutSeqPlayer"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.seqPlayer = self.getEnumValue("csFadeOutSeqPlayer", 0)


@dataclass
class CutsceneCmdFadeSeqList(CutsceneCmdBase):
    """This class contains Fade Seq List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdFadeSeq] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "fadeSeqList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])


@dataclass
class CutsceneCmdRumbleController(CutsceneCmdBase):
    """This class contains Rumble Controller command data"""

    sourceStrength: Optional[int] = None
    duration: Optional[int] = None
    decreaseRate: Optional[int] = None
    paramNumber: int = 8

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.sourceStrength = getInteger(self.params[3])
            self.duration = getInteger(self.params[4])
            self.decreaseRate = getInteger(self.params[5])


@dataclass
class CutsceneCmdRumbleControllerList(CutsceneCmdBase):
    """This class contains Rumble Controller List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdRumbleController] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "rumbleList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])


@dataclass
class CutsceneCmdDestination(CutsceneCmdBase):
    """This class contains Destination command data"""

    id: Optional[str] = None
    paramNumber: int = 3
    listName: str = "destination"

    def __post_init__(self):
        if self.params is not None:
            self.id = self.getEnumValue("csDestination", 0)
            self.startFrame = getInteger(self.params[1])


@dataclass
class Cutscene:
    """This class contains a Cutscene's data, including every commands' data"""

    name: str
    totalEntries: int
    frameCount: int
    paramNumber: int = 2

    destination: CutsceneCmdDestination = None
    actorCueList: list[CutsceneCmdActorCueList] = field(default_factory=list)
    playerCueList: list[CutsceneCmdActorCueList] = field(default_factory=list)
    camEyeSplineList: list[CutsceneCmdCamEyeSpline] = field(default_factory=list)
    camATSplineList: list[CutsceneCmdCamATSpline] = field(default_factory=list)
    camEyeSplineRelPlayerList: list[CutsceneCmdCamEyeSplineRelToPlayer] = field(default_factory=list)
    camATSplineRelPlayerList: list[CutsceneCmdCamATSplineRelToPlayer] = field(default_factory=list)
    camEyeList: list[CutsceneCmdCamEye] = field(default_factory=list)
    camATList: list[CutsceneCmdCamAT] = field(default_factory=list)
    textList: list[CutsceneCmdTextList] = field(default_factory=list)
    miscList: list[CutsceneCmdMiscList] = field(default_factory=list)
    rumbleList: list[CutsceneCmdRumbleControllerList] = field(default_factory=list)
    transitionList: list[CutsceneCmdTransition] = field(default_factory=list)
    lightSettingsList: list[CutsceneCmdLightSettingList] = field(default_factory=list)
    timeList: list[CutsceneCmdTimeList] = field(default_factory=list)
    seqList: list[CutsceneCmdStartStopSeqList] = field(default_factory=list)
    fadeSeqList: list[CutsceneCmdFadeSeqList] = field(default_factory=list)


class CutsceneObjectFactory:
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
