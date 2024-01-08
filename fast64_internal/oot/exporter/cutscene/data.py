import bpy
import math

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from bpy.types import Object
from ....utility import PluginError
from ...oot_constants import ootData
from .actor_cue import CutsceneCmdActorCueList, CutsceneCmdActorCue
from .seq import CutsceneCmdStartStopSeqList, CutsceneCmdFadeSeqList, CutsceneCmdStartStopSeq, CutsceneCmdFadeSeq
from .text import CutsceneCmdTextList, CutsceneCmdText, CutsceneCmdTextNone, CutsceneCmdTextOcarinaAction

from .misc import (
    CutsceneCmdLightSetting,
    CutsceneCmdTime,
    CutsceneCmdMisc,
    CutsceneCmdRumbleController,
    CutsceneCmdDestination,
    CutsceneCmdMiscList,
    CutsceneCmdRumbleControllerList,
    CutsceneCmdTransition,
    CutsceneCmdLightSettingList,
    CutsceneCmdTimeList,
)

from .camera import (
    CutsceneCmdCamPoint,
    CutsceneCmdCamEyeSpline,
    CutsceneCmdCamATSpline,
    CutsceneCmdCamEyeSplineRelToPlayer,
    CutsceneCmdCamATSplineRelToPlayer,
    CutsceneCmdCamEye,
    CutsceneCmdCamAT,
)

if TYPE_CHECKING:
    from ...cutscene.properties import OOTCutsceneProperty, OOTCSTextProperty


cmdToClass = {
    "TextList": CutsceneCmdTextList,
    "LightSettingsList": CutsceneCmdLightSettingList,
    "TimeList": CutsceneCmdTimeList,
    "MiscList": CutsceneCmdMiscList,
    "RumbleList": CutsceneCmdRumbleControllerList,
    "StartSeqList": CutsceneCmdStartStopSeqList,
    "StopSeqList": CutsceneCmdStartStopSeqList,
    "FadeOutSeqList": CutsceneCmdFadeSeqList,
    "StartSeq": CutsceneCmdStartStopSeq,
    "StopSeq": CutsceneCmdStartStopSeq,
    "FadeOutSeq": CutsceneCmdFadeSeq,
}

cmdToList = {
    "TextList": "textList",
    "LightSettingsList": "lightSettingsList",
    "TimeList": "timeList",
    "MiscList": "miscList",
    "RumbleList": "rumbleList",
}


@dataclass
class CutsceneData:
    """This class defines the command data inside a cutscene"""

    csObj: Object
    useMacros: bool
    motionOnly: bool
    csObjects: dict[str, list[Object]] = field(default_factory=dict)
    csProp: Optional["OOTCutsceneProperty"] = None
    totalEntries: int = 0
    frameCount: int = 0
    motionFrameCount: int = 0
    camEndFrame: int = 0

    destination: Optional[CutsceneCmdDestination] = None
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

    def __post_init__(self):
        self.csProp: "OOTCutsceneProperty" = self.csObj.ootCutsceneProperty
        self.csObjects = {
            "CS Actor Cue List": [],
            "CS Player Cue List": [],
            "camShot": [],
        }

        for obj in self.csObj.children_recursive:
            if obj.type == "EMPTY" and obj.ootEmptyType in self.csObjects.keys():
                self.csObjects[obj.ootEmptyType].append(obj)
            elif obj.type == "ARMATURE":
                self.csObjects["camShot"].append(obj)

        self.csObjects["camShot"].sort(key=lambda obj: obj.name)
        self.setCutsceneData()

    def getOoTRotation(self, obj: Object):
        """Returns the converted Blender rotation"""

        def conv(r):
            r /= 2.0 * math.pi
            r -= math.floor(r)
            r = round(r * 0x10000)

            if r >= 0x8000:
                r += 0xFFFF0000

            assert r >= 0 and r <= 0xFFFFFFFF and (r <= 0x7FFF or r >= 0xFFFF8000)

            return hex(r & 0xFFFF)

        rotXYZ = [conv(obj.rotation_euler[0]), conv(obj.rotation_euler[2]), conv(obj.rotation_euler[1])]
        return [f"DEG_TO_BINANG({(int(rot, base=16) * (180 / 0x8000)):.3f})" for rot in rotXYZ]

    def getOoTPosition(self, pos):
        """Returns the converted Blender position"""

        scale = bpy.context.scene.ootBlenderScale

        x = round(pos[0] * scale)
        y = round(pos[2] * scale)
        z = round(-pos[1] * scale)

        if any(v < -0x8000 or v >= 0x8000 for v in (x, y, z)):
            raise RuntimeError(f"Position(s) too large, out of range: {x}, {y}, {z}")

        return [x, y, z]

    def getEnumValueFromProp(self, enumKey: str, owner, propName: str):
        item = ootData.enumData.enumByKey[enumKey].itemByKey.get(getattr(owner, propName))
        return item.id if item is not None else getattr(owner, f"{propName}Custom")

    def setActorCueListData(self, isPlayer: bool):
        """Returns the Actor Cue List commands from the corresponding objects"""

        playerOrActor = f"{'Player' if isPlayer else 'Actor'}"
        actorCueListObjects = self.csObjects[f"CS {playerOrActor} Cue List"]
        actorCueListObjects.sort(key=lambda o: o.ootCSMotionProperty.actorCueProp.cueStartFrame)

        self.totalEntries += len(actorCueListObjects)
        for obj in actorCueListObjects:
            entryTotal = len(obj.children)

            if entryTotal == 0:
                raise PluginError("ERROR: The Actor Cue List does not contain any child Actor Cue objects")

            if obj.children[-1].ootEmptyType != "CS Dummy Cue":
                # we need an extra point that won't be exported to get the real last cue's
                # end frame and end position
                raise PluginError("ERROR: The Actor Cue List is missing the extra dummy point!")

            commandType = obj.ootCSMotionProperty.actorCueListProp.commandType

            if commandType == "Custom":
                commandType = obj.ootCSMotionProperty.actorCueListProp.commandTypeCustom
            elif self.useMacros:
                commandType = ootData.enumData.enumByKey["csCmd"].itemByKey[commandType].id

            # ignoring dummy cue
            newActorCueList = CutsceneCmdActorCueList(
                None, isPlayer=isPlayer, entryTotal=entryTotal - 1, commandType=commandType
            )

            for i, childObj in enumerate(obj.children, 1):
                startFrame = childObj.ootCSMotionProperty.actorCueProp.cueStartFrame
                if i < len(obj.children) and childObj.ootEmptyType != "CS Dummy Cue":
                    endFrame = obj.children[i].ootCSMotionProperty.actorCueProp.cueStartFrame
                    actionID = None

                    if isPlayer:
                        cueID = childObj.ootCSMotionProperty.actorCueProp.playerCueID
                        if cueID != "Custom":
                            actionID = ootData.enumData.enumByKey["csPlayerCueId"].itemByKey[cueID].id

                    if actionID is None:
                        actionID = childObj.ootCSMotionProperty.actorCueProp.cueActionID

                    newActorCueList.entries.append(
                        CutsceneCmdActorCue(
                            None,
                            startFrame,
                            endFrame,
                            actionID,
                            self.getOoTRotation(childObj),
                            self.getOoTPosition(childObj.location),
                            self.getOoTPosition(obj.children[i].location),
                            isPlayer,
                        )
                    )

            self.actorCueList.append(newActorCueList)

    def getCameraShotPointData(self, bones, useAT: bool):
        """Returns the Camera Point data from the bone data"""

        shotPoints: list[CutsceneCmdCamPoint] = []

        if len(bones) < 4:
            raise RuntimeError("Camera Armature needs at least 4 bones!")

        for bone in bones:
            if bone.parent is not None:
                raise RuntimeError("Camera Armature bones are not allowed to have parent bones!")

            shotPoints.append(
                CutsceneCmdCamPoint(
                    None,
                    None,
                    None,
                    ("CS_CAM_CONTINUE" if self.useMacros else "0"),
                    bone.ootCamShotPointProp.shotPointRoll if useAT else 0,
                    bone.ootCamShotPointProp.shotPointFrame,
                    bone.ootCamShotPointProp.shotPointViewAngle,
                    self.getOoTPosition(bone.head if not useAT else bone.tail),
                )
            )

        # NOTE: because of the game's bug explained in the importer we need to add an extra dummy point when exporting
        shotPoints.append(
            CutsceneCmdCamPoint(None, None, None, "CS_CAM_STOP" if self.useMacros else "-1", 0, 0, 0.0, [0, 0, 0])
        )
        return shotPoints

    def getCamCmdFunc(self, camMode: str, useAT: bool):
        """Returns the camera get function depending on the camera mode"""

        camCmdFuncMap = {
            "splineEyeOrAT": self.getCamATSplineCmd if useAT else self.getCamEyeSplineCmd,
            "splineEyeOrATRelPlayer": self.getCamATSplineRelToPlayerCmd
            if useAT
            else self.getCamEyeSplineRelToPlayerCmd,
            "eyeOrAT": self.getCamATCmd if useAT else self.getCamEyeCmd,
        }

        return camCmdFuncMap[camMode]

    def getCamClassOrList(self, isClass: bool, camMode: str, useAT: bool):
        """Returns the camera dataclass depending on the camera mode"""

        # TODO: improve this
        if isClass:
            camCmdClassMap = {
                "splineEyeOrAT": CutsceneCmdCamATSpline if useAT else CutsceneCmdCamEyeSpline,
                "splineEyeOrATRelPlayer": CutsceneCmdCamATSplineRelToPlayer
                if useAT
                else CutsceneCmdCamEyeSplineRelToPlayer,
                "eyeOrAT": CutsceneCmdCamAT if useAT else CutsceneCmdCamEye,
            }
        else:
            camCmdClassMap = {
                "splineEyeOrAT": "camATSplineList" if useAT else "camEyeSplineList",
                "splineEyeOrATRelPlayer": "camATSplineRelPlayerList" if useAT else "camEyeSplineRelPlayerList",
                "eyeOrAT": "camATList" if useAT else "camEyeList",
            }

        return camCmdClassMap[camMode]

    def getNewCamData(self, shotObj: Object, useAT: bool):
        """Returns the Camera Shot data from the corresponding Armatures"""

        newCamData = self.getCamClassOrList(True, shotObj.data.ootCamShotProp.shotCamMode, useAT)(None)
        newCamData.entries = self.getCameraShotPointData(shotObj.data.bones, useAT)
        startFrame = shotObj.data.ootCamShotProp.shotStartFrame

        # "fake" end frame
        endFrame = (
            startFrame
            + max(2, sum(point.frame for point in newCamData.entries))
            + (newCamData.entries[-2].frame if useAT else 1)
        )

        if not useAT:
            for pointData in newCamData.entries:
                pointData.frame = 0
            self.camEndFrame = endFrame

        newCamData.startFrame = startFrame
        newCamData.endFrame = endFrame

        return newCamData

    def setCameraShotData(self):
        """Returns every Camera Shot commands"""

        shotObjects = self.csObjects["camShot"]

        if len(shotObjects) > 0:
            motionFrameCount = -1
            for shotObj in shotObjects:
                camMode = shotObj.data.ootCamShotProp.shotCamMode

                eyeCamList = getattr(self, self.getCamClassOrList(False, camMode, False))
                eyeCamList.append(self.getNewCamData(shotObj, False))

                atCamList = getattr(self, self.getCamClassOrList(False, camMode, True))
                atCamList.append(self.getNewCamData(shotObj, True))

                motionFrameCount = max(motionFrameCount, self.camEndFrame + 1)
            self.motionFrameCount += motionFrameCount
            self.totalEntries += len(shotObjects) * 2

    def getNewTextCmd(self, textEntry: "OOTCSTextProperty"):
        match textEntry.textboxType:
            case "Text":
                return CutsceneCmdText(
                    None,
                    textEntry.startFrame,
                    textEntry.endFrame,
                    textEntry.textID,
                    self.getEnumValueFromProp("csTextType", textEntry, "csTextType"),
                    textEntry.topOptionTextID,
                    textEntry.bottomOptionTextID,
                )
            case "None":
                return CutsceneCmdTextNone(None, textEntry.startFrame, textEntry.endFrame)
            case "OcarinaAction":
                return CutsceneCmdTextOcarinaAction(
                    None,
                    textEntry.startFrame,
                    textEntry.endFrame,
                    self.getEnumValueFromProp("ocarinaSongActionId", textEntry, "ocarinaAction"),
                    textEntry.ocarinaMessageId,
                )
        raise PluginError("ERROR: Unknown text type!")

    def setCutsceneData(self):
        self.setActorCueListData(True)
        self.setActorCueListData(False)
        self.setCameraShotData()

        # don't process the cutscene empty if we don't want its data
        if self.motionOnly:
            return

        if self.csProp.csUseDestination:
            self.destination = CutsceneCmdDestination(
                None,
                self.csProp.csDestinationStartFrame,
                None,
                self.getEnumValueFromProp("csDestination", self.csProp, "csDestination"),
            )
            self.totalEntries += 1

        self.frameCount = self.csProp.csEndFrame
        self.totalEntries += len(self.csProp.csLists)

        for entry in self.csProp.csLists:
            match entry.listType:
                case "StartSeqList" | "StopSeqList" | "FadeOutSeqList":
                    isFadeOutSeq = entry.listType == "FadeOutSeqList"
                    cmdList = cmdToClass[entry.listType](None)
                    cmdList.entryTotal = len(entry.seqList)
                    cmdList.type = "start" if entry.listType == "StartSeqList" else "stop"
                    for elem in entry.seqList:
                        data = cmdToClass[entry.listType.removesuffix("List")](None, elem.startFrame, elem.endFrame)
                        if isFadeOutSeq:
                            data.seqPlayer = self.getEnumValueFromProp("csFadeOutSeqPlayer", elem, "csSeqPlayer")
                        else:
                            data.type = cmdList.type
                            data.seqId = self.getEnumValueFromProp("seqId", elem, "csSeqID")
                        cmdList.entries.append(data)
                    if isFadeOutSeq:
                        self.fadeSeqList.append(cmdList)
                    else:
                        self.seqList.append(cmdList)
                case "Transition":
                    self.transitionList.append(
                        CutsceneCmdTransition(
                            None,
                            entry.transitionStartFrame,
                            entry.transitionEndFrame,
                            self.getEnumValueFromProp("csTransitionType", entry, "transitionType"),
                        )
                    )
                case _:
                    curList = getattr(entry, (entry.listType[0].lower() + entry.listType[1:]))
                    cmdList = cmdToClass[entry.listType](None)
                    cmdList.entryTotal = len(curList)
                    for elem in curList:
                        match entry.listType:
                            case "TextList":
                                cmdList.entries.append(self.getNewTextCmd(elem))
                            case "LightSettingsList":
                                cmdList.entries.append(
                                    CutsceneCmdLightSetting(
                                        None, elem.startFrame, elem.endFrame, None, elem.lightSettingsIndex
                                    )
                                )
                            case "TimeList":
                                cmdList.entries.append(
                                    CutsceneCmdTime(None, elem.startFrame, elem.endFrame, elem.hour, elem.minute)
                                )
                            case "MiscList":
                                cmdList.entries.append(
                                    CutsceneCmdMisc(
                                        None,
                                        elem.startFrame,
                                        elem.endFrame,
                                        self.getEnumValueFromProp("csMiscType", elem, "csMiscType"),
                                    )
                                )
                            case "RumbleList":
                                cmdList.entries.append(
                                    CutsceneCmdRumbleController(
                                        None,
                                        elem.startFrame,
                                        elem.endFrame,
                                        elem.rumbleSourceStrength,
                                        elem.rumbleDuration,
                                        elem.rumbleDecreaseRate,
                                    )
                                )
                            case _:
                                raise PluginError("ERROR: Unknown Cutscene List Type!")
                    getattr(self, cmdToList[entry.listType]).append(cmdList)
