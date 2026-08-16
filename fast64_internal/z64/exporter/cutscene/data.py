import bpy
import math

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from bpy.types import Object, Bone
from ....utility import PluginError, radians_to_s16
from ....game_data import game_data
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

    useMacros: bool
    motionOnly: bool

    totalEntries: int = field(init=False, default=0)
    frameCount: int = field(init=False, default=0)
    motionFrameCount: int = field(init=False, default=0)
    camEndFrame: int = field(init=False, default=0)
    destination: CutsceneCmdDestination = field(init=False, default=None)
    actorCueList: list[CutsceneCmdActorCueList] = field(init=False, default_factory=list)
    playerCueList: list[CutsceneCmdActorCueList] = field(init=False, default_factory=list)
    camEyeSplineList: list[CutsceneCmdCamEyeSpline] = field(init=False, default_factory=list)
    camATSplineList: list[CutsceneCmdCamATSpline] = field(init=False, default_factory=list)
    camEyeSplineRelPlayerList: list[CutsceneCmdCamEyeSplineRelToPlayer] = field(init=False, default_factory=list)
    camATSplineRelPlayerList: list[CutsceneCmdCamATSplineRelToPlayer] = field(init=False, default_factory=list)
    camEyeList: list[CutsceneCmdCamEye] = field(init=False, default_factory=list)
    camATList: list[CutsceneCmdCamAT] = field(init=False, default_factory=list)
    textList: list[CutsceneCmdTextList] = field(init=False, default_factory=list)
    miscList: list[CutsceneCmdMiscList] = field(init=False, default_factory=list)
    rumbleList: list[CutsceneCmdRumbleControllerList] = field(init=False, default_factory=list)
    transitionList: list[CutsceneCmdTransition] = field(init=False, default_factory=list)
    lightSettingsList: list[CutsceneCmdLightSettingList] = field(init=False, default_factory=list)
    timeList: list[CutsceneCmdTimeList] = field(init=False, default_factory=list)
    seqList: list[CutsceneCmdStartStopSeqList] = field(init=False, default_factory=list)
    fadeSeqList: list[CutsceneCmdFadeSeqList] = field(init=False, default_factory=list)

    @staticmethod
    def new(csObj: Object, useMacros: bool, motionOnly: bool):
        csProp: "OOTCutsceneProperty" = csObj.ootCutsceneProperty
        csObjects = {
            "CS Actor Cue List": [],
            "CS Player Cue List": [],
            "camShot": [],
        }

        for obj in csObj.children_recursive:
            if obj.type == "EMPTY" and obj.ootEmptyType in csObjects.keys():
                csObjects[obj.ootEmptyType].append(obj)
            elif obj.type == "ARMATURE":
                csObjects["camShot"].append(obj)
        csObjects["camShot"].sort(key=lambda obj: obj.name)

        newCutsceneData = CutsceneData(useMacros, motionOnly)
        newCutsceneData.setCutsceneData(csObjects, csProp)
        return newCutsceneData

    def getOoTRotation(self, obj: Object):
        """Returns the converted Blender rotation"""

        def conv(r):
            return radians_to_s16(r, False)

        rotXYZ = [conv(obj.rotation_euler[0]), conv(obj.rotation_euler[2]), conv(obj.rotation_euler[1])]
        return [f"DEG_TO_BINANG({(rot * (180 / 0x8000)):.3f})" for rot in rotXYZ]

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
        item = game_data.z64.enums.enumByKey[enumKey].item_by_key.get(getattr(owner, propName))
        return item.id if item is not None else getattr(owner, f"{propName}Custom")

    def setActorCueListData(self, csObjects: dict[str, list[Object]], isPlayer: bool):
        """Returns the Actor Cue List commands from the corresponding objects"""

        playerOrActor = f"{'Player' if isPlayer else 'Actor'}"
        actorCueListObjects = csObjects[f"CS {playerOrActor} Cue List"]
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
                commandType = game_data.z64.enums.enumByKey["cs_cmd"].item_by_key[commandType].id

            # ignoring dummy cue
            newActorCueList = CutsceneCmdActorCueList(None, None, isPlayer, commandType, entryTotal - 1)

            for i, childObj in enumerate(obj.children, 1):
                startFrame = childObj.ootCSMotionProperty.actorCueProp.cueStartFrame
                if i < len(obj.children) and childObj.ootEmptyType != "CS Dummy Cue":
                    endFrame = obj.children[i].ootCSMotionProperty.actorCueProp.cueStartFrame
                    actionID = None

                    if isPlayer:
                        cueID = childObj.ootCSMotionProperty.actorCueProp.playerCueID
                        if cueID != "Custom":
                            actionID = game_data.z64.enums.enumByKey["cs_player_cue_id"].item_by_key[cueID].id

                    if actionID is None:
                        actionID = childObj.ootCSMotionProperty.actorCueProp.cueActionID

                    newActorCueList.entries.append(
                        CutsceneCmdActorCue(
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

    def getCameraShotPointData(self, bones: list[Bone], useAT: bool):
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
                    ("CS_CAM_CONTINUE" if self.useMacros else "0"),
                    bone.ootCamShotPointProp.shotPointRoll if useAT else 0,
                    bone.ootCamShotPointProp.shotPointFrame,
                    bone.ootCamShotPointProp.shotPointViewAngle,
                    self.getOoTPosition(bone.head if not useAT else bone.tail),
                )
            )

        # NOTE: because of the game's bug explained in the importer we need to add an extra dummy point when exporting
        shotPoints.append(
            CutsceneCmdCamPoint(None, None, "CS_CAM_STOP" if self.useMacros else "-1", 0, 0, 0.0, [0, 0, 0])
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

        entries = self.getCameraShotPointData(shotObj.data.bones, useAT)
        startFrame = shotObj.data.ootCamShotProp.shotStartFrame

        # "fake" end frame
        endFrame = startFrame + max(2, sum(point.frame for point in entries)) + (entries[-2].frame if useAT else 1)

        if not useAT:
            for pointData in entries:
                pointData.frame = 0
            self.camEndFrame = endFrame

        return self.getCamClassOrList(True, shotObj.data.ootCamShotProp.shotCamMode, useAT)(
            startFrame, endFrame, entries
        )

    def setCameraShotData(self, csObjects: dict[str, list[Object]]):
        shotObjects = csObjects["camShot"]

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
                    textEntry.startFrame,
                    textEntry.endFrame,
                    textEntry.textID,
                    self.getEnumValueFromProp("cs_text_type", textEntry, "csTextType"),
                    textEntry.topOptionTextID,
                    textEntry.bottomOptionTextID,
                )
            case "None":
                return CutsceneCmdTextNone(textEntry.startFrame, textEntry.endFrame)
            case "OcarinaAction":
                return CutsceneCmdTextOcarinaAction(
                    textEntry.startFrame,
                    textEntry.endFrame,
                    self.getEnumValueFromProp("ocarina_song_action_id", textEntry, "ocarinaAction"),
                    textEntry.ocarinaMessageId,
                )
        raise PluginError("ERROR: Unknown text type!")

    def setCutsceneData(self, csObjects: dict[str, list[Object]], csProp: "OOTCutsceneProperty"):
        self.setActorCueListData(csObjects, True)
        self.setActorCueListData(csObjects, False)
        self.setCameraShotData(csObjects)

        # don't process the cutscene empty if we don't want its data
        if self.motionOnly:
            return

        if csProp.csUseDestination:
            self.destination = CutsceneCmdDestination(
                csProp.csDestinationStartFrame,
                None,
                self.getEnumValueFromProp("cs_destination", csProp, "csDestination"),
            )
            self.totalEntries += 1

        self.frameCount = csProp.csEndFrame
        self.totalEntries += len(csProp.csLists)

        for entry in csProp.csLists:
            match entry.listType:
                case "StartSeqList" | "StopSeqList" | "FadeOutSeqList":
                    isFadeOutSeq = entry.listType == "FadeOutSeqList"
                    cmdList = cmdToClass[entry.listType](None, None)
                    cmdList.entryTotal = len(entry.seqList)
                    if not isFadeOutSeq:
                        cmdList.type = "start" if entry.listType == "StartSeqList" else "stop"
                    for elem in entry.seqList:
                        data = cmdToClass[entry.listType.removesuffix("List")](elem.startFrame, elem.endFrame)
                        if isFadeOutSeq:
                            data.seqPlayer = self.getEnumValueFromProp("cs_fade_out_seq_player", elem, "csSeqPlayer")
                        else:
                            data.type = cmdList.type
                            data.seqId = self.getEnumValueFromProp("seq_id", elem, "csSeqID")
                        cmdList.entries.append(data)
                    if isFadeOutSeq:
                        self.fadeSeqList.append(cmdList)
                    else:
                        self.seqList.append(cmdList)
                case "Transition":
                    self.transitionList.append(
                        CutsceneCmdTransition(
                            entry.transitionStartFrame,
                            entry.transitionEndFrame,
                            self.getEnumValueFromProp("cs_transition_type", entry, "transitionType"),
                        )
                    )
                case _:
                    curList = getattr(entry, (entry.listType[0].lower() + entry.listType[1:]))
                    cmdList = cmdToClass[entry.listType](None, None)
                    cmdList.entryTotal = len(curList)
                    for elem in curList:
                        match entry.listType:
                            case "TextList":
                                cmdList.entries.append(self.getNewTextCmd(elem))
                            case "LightSettingsList":
                                cmdList.entries.append(
                                    CutsceneCmdLightSetting(
                                        elem.startFrame, elem.endFrame, False, elem.lightSettingsIndex
                                    )
                                )
                            case "TimeList":
                                cmdList.entries.append(
                                    CutsceneCmdTime(elem.startFrame, elem.endFrame, elem.hour, elem.minute)
                                )
                            case "MiscList":
                                cmdList.entries.append(
                                    CutsceneCmdMisc(
                                        elem.startFrame,
                                        elem.endFrame,
                                        self.getEnumValueFromProp("cs_misc_type", elem, "csMiscType"),
                                    )
                                )
                            case "RumbleList":
                                cmdList.entries.append(
                                    CutsceneCmdRumbleController(
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
