import bpy
import math

from copy import copy
from typing import Optional, TYPE_CHECKING
from bpy.types import Object, Bone
from ....utility import PluginError, exportColor
from ....game_data import game_data
from ...utility import is_oot_features
from .actor_cue import CutsceneCmdActorCueList, CutsceneCmdActorCue
from .text import CutsceneCmdTextList, CutsceneCmdText, CutsceneCmdTextNone, CutsceneCmdTextOcarinaAction

from .seq import (
    CutsceneCmdStartStopSeqList,
    CutsceneCmdFadeSeqList,
    CutsceneCmdStartStopSeq,
    CutsceneCmdFadeSeq,
    CutsceneCmdModifySeq,
    CutsceneCmdModifySeqList,
    CutsceneCmdStartAmbience,
    CutsceneCmdStartAmbienceList,
    CutsceneCmdFadeOutAmbience,
    CutsceneCmdFadeOutAmbienceList,
)

from .misc import (
    CutsceneCmdLightSetting,
    CutsceneCmdTime,
    CutsceneCmdMisc,
    CutsceneCmdRumbleController,
    CutsceneCmdDestination,
    CutsceneCmdMiscList,
    CutsceneCmdRumbleControllerList,
    CutsceneCmdTransition,
    CutsceneCmdTransitionList,
    CutsceneCmdLightSettingList,
    CutsceneCmdTimeList,
    CutsceneCmdMotionBlur,
    CutsceneCmdMotionBlurList,
    CutsceneCmdChooseCreditsScenes,
    CutsceneCmdChooseCreditsScenesList,
    CutsceneCmdTransitionGeneral,
    CutsceneCmdTransitionGeneralList,
    CutsceneCmdGiveTatl,
)

from .camera import (
    CutsceneCmdCamPoint,
    CutsceneCmdCamEyeSpline,
    CutsceneCmdCamATSpline,
    CutsceneCmdCamEyeSplineRelToPlayer,
    CutsceneCmdCamATSplineRelToPlayer,
    CutsceneCmdCamEye,
    CutsceneCmdCamAT,
    CutsceneCmdNewCamPoint,
    CutsceneCmdCamMisc,
    CutsceneSplinePoint,
    CutsceneCmdCamSpline,
    CutsceneCmdCamSplineList,
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
    "Transition": CutsceneCmdTransitionList,
    "MotionBlurList": CutsceneCmdMotionBlurList,
    "CreditsSceneList": CutsceneCmdChooseCreditsScenesList,
    "TransitionGeneralList": CutsceneCmdTransitionGeneralList,
    "ModifySeqList": CutsceneCmdModifySeqList,
    "StartAmbience": CutsceneCmdStartAmbience,
    "FadeOutAmbience": CutsceneCmdFadeOutAmbience,
    "StartAmbienceList": CutsceneCmdStartAmbienceList,
    "FadeOutAmbienceList": CutsceneCmdFadeOutAmbienceList,
}

# to CutsceneData list
cmdToList = {
    "TextList": "textList",
    "LightSettingsList": "lightSettingsList",
    "TimeList": "timeList",
    "MiscList": "miscList",
    "RumbleList": "rumbleList",
    "Transition": "transitionList",
    "MotionBlurList": "motion_blur_list",
    "CreditsSceneList": "credits_scene_list",
    "TransitionGeneralList": "transition_general_list",
    "ModifySeqList": "modify_seq_list",
    "StartAmbienceList": "start_ambience_list",
    "FadeOutAmbienceList": "fade_out_ambience_list",
}


class CutsceneData:
    """This class defines the command data inside a cutscene"""

    def __init__(self, useMacros: bool, motionOnly: bool):
        self.useMacros = useMacros
        self.motionOnly = motionOnly

        self.totalEntries: int = 0
        self.frameCount: int = 0
        self.motionFrameCount: int = 0
        self.camEndFrame: int = 0
        self.destination: Optional[CutsceneCmdDestination] = None
        self.give_tatl: Optional[CutsceneCmdGiveTatl] = None
        self.actorCueList: list[CutsceneCmdActorCueList] = []
        self.playerCueList: list[CutsceneCmdActorCueList] = []
        self.camEyeSplineList: list[CutsceneCmdCamEyeSpline] = []
        self.camATSplineList: list[CutsceneCmdCamATSpline] = []
        self.camEyeSplineRelPlayerList: list[CutsceneCmdCamEyeSplineRelToPlayer] = []
        self.camATSplineRelPlayerList: list[CutsceneCmdCamATSplineRelToPlayer] = []
        self.camEyeList: list[CutsceneCmdCamEye] = []
        self.camATList: list[CutsceneCmdCamAT] = []
        self.textList: list[CutsceneCmdTextList] = []
        self.miscList: list[CutsceneCmdMiscList] = []
        self.rumbleList: list[CutsceneCmdRumbleControllerList] = []
        self.transitionList: list[CutsceneCmdTransitionList] = []
        self.lightSettingsList: list[CutsceneCmdLightSettingList] = []
        self.timeList: list[CutsceneCmdTimeList] = []
        self.seqList: list[CutsceneCmdStartStopSeqList] = []
        self.fadeSeqList: list[CutsceneCmdFadeSeqList] = []

        # lists from the new cutscene system
        self.camSplineList: list[CutsceneCmdCamSplineList] = []
        self.motion_blur_list: list[CutsceneCmdMotionBlurList] = []
        self.modify_seq_list: list[CutsceneCmdModifySeqList] = []
        self.credits_scene_list: list[CutsceneCmdChooseCreditsScenesList] = []
        self.transition_general_list: list[CutsceneCmdTransitionGeneralList] = []
        self.start_ambience_list: list[CutsceneCmdStartAmbienceList] = []
        self.fade_out_ambience_list: list[CutsceneCmdFadeOutAmbienceList] = []

    @staticmethod
    def new(csObj: Optional[Object], useMacros: bool, motionOnly: bool):
        newCutsceneData = CutsceneData(useMacros, motionOnly)

        if csObj is not None:
            # when csObj is None it means we're in import context
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

            newCutsceneData.setCutsceneData(csObjects, csProp)

        return newCutsceneData

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

    def getEnumValueFromProp(self, enumKey: str, owner, propName: str, custom_suffix: str = "Custom"):
        game_data.z64.update(bpy.context, None)
        item = game_data.z64.enums.enumByKey[enumKey].item_by_key.get(getattr(owner, propName))
        return item.id if item is not None else getattr(owner, f"{propName}{custom_suffix}")

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

                    new_entry = CutsceneCmdActorCue(
                        startFrame,
                        endFrame,
                        actionID,
                        self.getOoTRotation(childObj),
                        self.getOoTPosition(childObj.location),
                        self.getOoTPosition(obj.children[i].location),
                    )
                    new_entry.isPlayer = isPlayer
                    newActorCueList.entries.append(new_entry)

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
            if is_oot_features():
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
            else:
                new_spline_list = CutsceneCmdCamSplineList(0)  # bytes are computed when getting the c data
                i = 0

                for shot_obj in shotObjects:
                    shot_prop = shot_obj.data.ootCamShotProp
                    new_spline = CutsceneCmdCamSpline(0, shot_prop.shot_duration)
                    at_total = 0
                    eye_total = 0

                    for i, bone in enumerate(shot_obj.data.bones):
                        bone_prop = bone.ootCamShotPointProp

                        if i > 0 and i < len(shot_obj.data.bones) - 1:
                            at_total += bone_prop.shot_point_duration
                            eye_total += bone_prop.shot_point_duration

                        # MM TODO: move shot_interp_type and shot_spline_rel_to per bone?
                        # add weight property
                        new_spline.entries.append(
                            CutsceneSplinePoint(
                                # At
                                CutsceneCmdNewCamPoint(
                                    self.getEnumValueFromProp(
                                        "cs_spline_interp_type", shot_prop, "shot_interp_type", "_custom"
                                    ),
                                    0x64,
                                    bone_prop.shot_point_duration,
                                    self.getOoTPosition(bone.tail),
                                    self.getEnumValueFromProp(
                                        "cs_spline_rel", shot_prop, "shot_spline_rel_to", "_custom"
                                    ),
                                ),
                                # Eye
                                CutsceneCmdNewCamPoint(
                                    self.getEnumValueFromProp(
                                        "cs_spline_interp_type", shot_prop, "shot_interp_type", "_custom"
                                    ),
                                    0x64,
                                    bone_prop.shot_point_duration,
                                    self.getOoTPosition(bone.head),
                                    self.getEnumValueFromProp(
                                        "cs_spline_rel", shot_prop, "shot_spline_rel_to", "_custom"
                                    ),
                                ),
                                # Misc
                                CutsceneCmdCamMisc(bone_prop.shotPointRoll, bone_prop.shotPointViewAngle),
                            )
                        )

                    # I don't understand how this camera system works, as far as I can tell it's
                    # the same as OoT? It's clear that the first and last points are ignored and by
                    # looking at the vanilla scenes I came to the conclusion that the last point of
                    # each point type (at and eye) have a duration that is the sum of all the previous
                    # point's durations except the very first one. By looking at the code I'm thinking
                    # this might work exactly like OoT where you need an extra point because of some bug
                    # (see the readme for explanations), idk if this is necessary ¯\_(ツ)_/¯
                    #
                    # this block copies the last entry's informations to the extra one,
                    # except for the duration which is computed in the loop above
                    last_entry = new_spline.entries[-1]
                    # last_entry.at.duration = at_total
                    # last_entry.eye.duration = eye_total
                    new_spline.entries.append(
                        CutsceneSplinePoint(
                            # At
                            CutsceneCmdNewCamPoint(
                                last_entry.at.interp_type,
                                last_entry.at.weight,
                                at_total,
                                last_entry.at.pos,
                                last_entry.at.relative_to,
                            ),
                            # Eye
                            CutsceneCmdNewCamPoint(
                                last_entry.eye.interp_type,
                                last_entry.eye.weight,
                                eye_total,
                                last_entry.eye.pos,
                                last_entry.eye.relative_to,
                            ),
                            # Misc
                            copy(last_entry.misc),
                        )
                    )
                    i += 1  # accounting for the extra point

                    new_spline.num_entries = i
                    new_spline_list.entries.append(new_spline)

                self.camSplineList.append(new_spline_list)
                self.totalEntries += 1

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
                csProp.csDestinationStartFrame + 1,
                self.getEnumValueFromProp("cs_destination", csProp, "csDestination"),
            )
            self.totalEntries += 1

        if not is_oot_features() and csProp.cs_give_tatl:
            self.give_tatl = CutsceneCmdGiveTatl(
                csProp.cs_give_tatl_start_frame,
                csProp.cs_give_tatl_start_frame + 1,
                "true" if csProp.cs_give_tatl else "false",
            )
            self.totalEntries += 1

        self.frameCount = csProp.csEndFrame
        self.totalEntries += len(csProp.csLists)

        prop_map = {
            "Transition": "transition_list",
            "MotionBlurList": "motion_blur_list",
            "CreditsSceneList": "credits_scene_list",
            "TransitionGeneralList": "trans_general_list",
            "ModifySeqList": "mod_seq_list",
        }

        for entry in csProp.csLists:
            match entry.listType:
                case "StartSeqList" | "StopSeqList" | "FadeOutSeqList" | "StartAmbienceList" | "FadeOutAmbienceList":
                    isFadeOutSeq = entry.listType == "FadeOutSeqList"
                    is_start_ambience = entry.listType == "StartAmbienceList"
                    is_fade_out_ambience = entry.listType == "FadeOutAmbienceList"
                    cmdList = cmdToClass[entry.listType](None, None)
                    cmdList.entryTotal = len(entry.seqList)

                    if not isFadeOutSeq and not is_start_ambience and not is_fade_out_ambience:
                        cmdList.type = "start" if entry.listType == "StartSeqList" else "stop"

                    for elem in entry.seqList:
                        data = cmdToClass[entry.listType.removesuffix("List")](elem.startFrame, elem.endFrame)

                        if not is_start_ambience and not is_fade_out_ambience:
                            if isFadeOutSeq:
                                data.seqPlayer = self.getEnumValueFromProp(
                                    "cs_fade_out_seq_player", elem, "csSeqPlayer"
                                )
                            else:
                                data.type = cmdList.type
                                data.seqId = self.getEnumValueFromProp("seq_id", elem, "csSeqID")

                        cmdList.entries.append(data)

                    if is_start_ambience:
                        self.start_ambience_list.append(cmdList)
                    elif is_fade_out_ambience:
                        self.fade_out_ambience_list.append(cmdList)
                    elif isFadeOutSeq:
                        self.fadeSeqList.append(cmdList)
                    else:
                        self.seqList.append(cmdList)
                case _:
                    if entry.listType in prop_map.keys():
                        prop_name = prop_map[entry.listType]
                        cmdList = cmdToClass[entry.listType](None, None)
                    else:
                        prop_name = entry.listType[0].lower() + entry.listType[1:]
                        cmdList = cmdToClass[entry.listType](None, None)
                    curList = getattr(entry, prop_name)
                    cmdList.entryTotal = len(curList)
                    for elem in curList:
                        match entry.listType:
                            case "ModifySeqList":
                                cmdList.entries.append(
                                    CutsceneCmdModifySeq(
                                        elem.startFrame,
                                        elem.startFrame + 1,
                                        self.getEnumValueFromProp("cs_modify_seq_type", elem, "mod_seq_type"),
                                    )
                                )
                            case "CreditsSceneList":
                                cmdList.entries.append(
                                    CutsceneCmdChooseCreditsScenes(
                                        elem.startFrame,
                                        elem.startFrame + 1,
                                        self.getEnumValueFromProp("cs_credits_scene_type", elem, "credits_scene_type"),
                                    )
                                )
                            case "TransitionGeneralList":
                                cmdList.entries.append(
                                    CutsceneCmdTransitionGeneral(
                                        elem.startFrame,
                                        elem.endFrame,
                                        self.getEnumValueFromProp("cs_transition_general", elem, "trans_general_type"),
                                        exportColor(elem.trans_color[0:3]),
                                    )
                                )
                            case "MotionBlurList":
                                cmdList.entries.append(
                                    CutsceneCmdMotionBlur(
                                        elem.startFrame,
                                        elem.endFrame,
                                        self.getEnumValueFromProp("cs_motion_blur_type", elem, "blur_type"),
                                    )
                                )
                            case "Transition":
                                cmdList.entries.append(
                                    CutsceneCmdTransition(
                                        elem.startFrame,
                                        elem.endFrame,
                                        self.getEnumValueFromProp("cs_transition_type", elem, "transition_type"),
                                    )
                                )
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
                                if not is_oot_features():
                                    rumble_type = self.getEnumValueFromProp("cs_rumble_type", elem, "rumble_type")
                                else:
                                    rumble_type = None

                                cmdList.entries.append(
                                    CutsceneCmdRumbleController(
                                        elem.startFrame,
                                        elem.startFrame + 1,
                                        elem.rumbleSourceStrength,
                                        elem.rumbleDuration,
                                        elem.rumbleDecreaseRate,
                                        rumble_type,
                                    )
                                )
                            case _:
                                raise PluginError("ERROR: Unknown Cutscene List Type!")
                    getattr(self, cmdToList[entry.listType]).append(cmdList)
