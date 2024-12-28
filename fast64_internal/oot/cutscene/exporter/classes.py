import math
import bpy

from dataclasses import dataclass
from typing import TYPE_CHECKING
from bpy.types import Object
from ....utility import PluginError, indent
from ...oot_constants import ootData
from ..constants import ootEnumCSListTypeListC

if TYPE_CHECKING:
    from ..properties import OOTCutsceneProperty, OOTCSTextProperty

from ..classes import (
    CutsceneCmdTransition,
    CutsceneCmdRumbleController,
    CutsceneCmdMisc,
    CutsceneCmdTime,
    CutsceneCmdLightSetting,
    CutsceneCmdText,
    CutsceneCmdTextNone,
    CutsceneCmdTextOcarinaAction,
    CutsceneCmdActorCueList,
    CutsceneCmdActorCue,
    CutsceneCmdCamEyeSpline,
    CutsceneCmdCamATSpline,
    CutsceneCmdCamEyeSplineRelToPlayer,
    CutsceneCmdCamATSplineRelToPlayer,
    CutsceneCmdCamEye,
    CutsceneCmdCamAT,
    CutsceneCmdCamPoint,
)


def cs_export_float(v: float):
    return f"{v:f}f"


class CutsceneCmdToC:
    """This class contains functions to create the cutscene commands"""

    def getEnumValue(self, enumKey: str, owner, propName: str):
        item = ootData.enumData.enumByKey[enumKey].itemByKey.get(getattr(owner, propName))
        return item.id if item is not None else getattr(owner, f"{propName}Custom")

    def getGenericListCmd(self, cmdName: str, entryTotal: int):
        return indent * 2 + f"{cmdName}({entryTotal}),\n"

    def getGenericSeqCmd(self, cmdName: str, type: str, startFrame: int, endFrame: int):
        return indent * 3 + f"{cmdName}({type}, {startFrame}, {endFrame}" + ", 0" * 8 + "),\n"

    def getTransitionCmd(self, transition: CutsceneCmdTransition):
        return indent * 2 + f"CS_TRANSITION({transition.type}, {transition.startFrame}, {transition.endFrame}),\n"

    def getRumbleControllerCmd(self, rumble: CutsceneCmdRumbleController):
        return indent * 3 + (
            f"CS_RUMBLE_CONTROLLER("
            + f"0, {rumble.startFrame}, 0, "
            + f"{rumble.sourceStrength}, {rumble.duration}, {rumble.decreaseRate}, 0, 0),\n"
        )

    def getMiscCmd(self, misc: CutsceneCmdMisc):
        return indent * 3 + (f"CS_MISC(" + f"{misc.type}, {misc.startFrame}, {misc.endFrame}" + ", 0" * 11 + "),\n")

    def getTimeCmd(self, time: CutsceneCmdTime):
        return indent * 3 + (f"CS_TIME(" + f"0, {time.startFrame}, 0, {time.hour}, {time.minute}" + "),\n")

    def getLightSettingCmd(self, lightSetting: CutsceneCmdLightSetting):
        return indent * 3 + (
            f"CS_LIGHT_SETTING(" + f"{lightSetting.lightSetting}, {lightSetting.startFrame}" + ", 0" * 9 + "),\n"
        )

    def getTextCmd(self, text: CutsceneCmdText):
        return indent * 3 + (
            f"CS_TEXT("
            + f"{text.textId}, {text.startFrame}, {text.endFrame}, {text.type}, {text.altTextId1}, {text.altTextId2}"
            + "),\n"
        )

    def getTextNoneCmd(self, textNone: CutsceneCmdTextNone):
        return indent * 3 + f"CS_TEXT_NONE({textNone.startFrame}, {textNone.endFrame}),\n"

    def getTextOcarinaActionCmd(self, ocarinaAction: CutsceneCmdTextOcarinaAction):
        return indent * 3 + (
            f"CS_TEXT_OCARINA_ACTION("
            + f"{ocarinaAction.ocarinaActionId}, {ocarinaAction.startFrame}, "
            + f"{ocarinaAction.endFrame}, {ocarinaAction.messageId}"
            + "),\n"
        )

    def getDestinationCmd(self, csProp: "OOTCutsceneProperty"):
        dest = self.getEnumValue("csDestination", csProp, "csDestination")
        return indent * 2 + f"CS_DESTINATION({dest}, {csProp.csDestinationStartFrame}, 0),\n"

    def getActorCueListCmd(self, actorCueList: CutsceneCmdActorCueList, isPlayerActor: bool):
        return indent * 2 + (
            f"CS_{'PLAYER' if isPlayerActor else 'ACTOR'}_CUE_LIST("
            + f"{actorCueList.commandType + ', ' if not isPlayerActor else ''}"
            + f"{actorCueList.entryTotal}),\n"
        )

    def getActorCueCmd(self, actorCue: CutsceneCmdActorCue, isPlayerActor: bool):
        return indent * 3 + (
            f"CS_{'PLAYER' if isPlayerActor else 'ACTOR'}_CUE("
            + f"{actorCue.actionID}, {actorCue.startFrame}, {actorCue.endFrame}, "
            + "".join(f"{rot}, " for rot in actorCue.rot)
            + "".join(f"{pos}, " for pos in actorCue.startPos)
            + "".join(f"{pos}, " for pos in actorCue.endPos)
            + f"{cs_export_float(0)}, {cs_export_float(0)}, {cs_export_float(0)}),\n"
        )

    def getCamListCmd(self, cmdName: str, startFrame: int, endFrame: int):
        return indent * 2 + f"{cmdName}({startFrame}, {endFrame}),\n"

    def getCamEyeSplineCmd(self, camEyeSpline: CutsceneCmdCamEyeSpline):
        return self.getCamListCmd("CS_CAM_EYE_SPLINE", camEyeSpline.startFrame, camEyeSpline.endFrame)

    def getCamATSplineCmd(self, camATSpline: CutsceneCmdCamATSpline):
        return self.getCamListCmd("CS_CAM_AT_SPLINE", camATSpline.startFrame, camATSpline.endFrame)

    def getCamEyeSplineRelToPlayerCmd(self, camEyeSplinePlayer: CutsceneCmdCamEyeSplineRelToPlayer):
        return self.getCamListCmd(
            "CS_CAM_EYE_SPLINE_REL_TO_PLAYER", camEyeSplinePlayer.startFrame, camEyeSplinePlayer.endFrame
        )

    def getCamATSplineRelToPlayerCmd(self, camATSplinePlayer: CutsceneCmdCamATSplineRelToPlayer):
        return self.getCamListCmd(
            "CS_CAM_AT_SPLINE_REL_TO_PLAYER", camATSplinePlayer.startFrame, camATSplinePlayer.endFrame
        )

    def getCamEyeCmd(self, camEye: CutsceneCmdCamEye):
        return self.getCamListCmd("CS_CAM_EYE", camEye.startFrame, camEye.endFrame)

    def getCamATCmd(self, camAT: CutsceneCmdCamAT):
        return self.getCamListCmd("CS_CAM_AT", camAT.startFrame, camAT.endFrame)

    def getCamPointCmd(self, camPoint: CutsceneCmdCamPoint):
        return indent * 3 + (
            f"CS_CAM_POINT("
            + f"{camPoint.continueFlag}, {camPoint.camRoll}, {camPoint.frame}, {cs_export_float(camPoint.viewAngle)}, "
            + "".join(f"{pos}, " for pos in camPoint.pos)
            + "0),\n"
        )


@dataclass
class CutsceneExport(CutsceneCmdToC):
    """This class contains functions to create the new cutscene data"""

    csObjects: dict[str, list[Object]]
    useDecomp: bool
    motionOnly: bool
    entryTotal: int = 0
    frameCount: int = 0
    motionFrameCount: int = 0
    camEndFrame: int = 0

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

    def getActorCueListData(self, isPlayer: bool):
        """Returns the Actor Cue List commands from the corresponding objects"""

        playerOrActor = f"{'Player' if isPlayer else 'Actor'}"
        actorCueListObjects = self.csObjects[f"CS {playerOrActor} Cue List"]
        actorCueListObjects.sort(key=lambda o: o.ootCSMotionProperty.actorCueProp.cueStartFrame)
        actorCueData = ""

        self.entryTotal += len(actorCueListObjects)
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
            elif self.useDecomp:
                commandType = ootData.enumData.enumByKey["csCmd"].itemByKey[commandType].id

            # ignoring dummy cue
            actorCueList = CutsceneCmdActorCueList(None, entryTotal=entryTotal - 1, commandType=commandType)
            actorCueData += self.getActorCueListCmd(actorCueList, isPlayer)

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

                    actorCue = CutsceneCmdActorCue(
                        None,
                        startFrame,
                        endFrame,
                        actionID,
                        self.getOoTRotation(childObj),
                        self.getOoTPosition(childObj.location),
                        self.getOoTPosition(obj.children[i].location),
                    )
                    actorCueData += self.getActorCueCmd(actorCue, isPlayer)

        return actorCueData

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
                    ("CS_CAM_CONTINUE" if self.useDecomp else "0"),
                    bone.ootCamShotPointProp.shotPointRoll if useAT else 0,
                    bone.ootCamShotPointProp.shotPointFrame,
                    bone.ootCamShotPointProp.shotPointViewAngle,
                    self.getOoTPosition(bone.head if not useAT else bone.tail),
                )
            )

        # NOTE: because of the game's bug explained in the importer we need to add an extra dummy point when exporting
        shotPoints.append(
            CutsceneCmdCamPoint(None, None, None, "CS_CAM_STOP" if self.useDecomp else "-1", 0, 0, 0.0, [0, 0, 0])
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

    def getCamClass(self, camMode: str, useAT: bool):
        """Returns the camera dataclass depending on the camera mode"""

        camCmdClassMap = {
            "splineEyeOrAT": CutsceneCmdCamATSpline if useAT else CutsceneCmdCamEyeSpline,
            "splineEyeOrATRelPlayer": CutsceneCmdCamATSplineRelToPlayer
            if useAT
            else CutsceneCmdCamEyeSplineRelToPlayer,
            "eyeOrAT": CutsceneCmdCamAT if useAT else CutsceneCmdCamEye,
        }

        return camCmdClassMap[camMode]

    def getCamListData(self, shotObj: Object, useAT: bool):
        """Returns the Camera Shot data from the corresponding Armatures"""

        camPointList = self.getCameraShotPointData(shotObj.data.bones, useAT)
        startFrame = shotObj.data.ootCamShotProp.shotStartFrame

        # "fake" end frame
        endFrame = (
            startFrame + max(2, sum(point.frame for point in camPointList)) + (camPointList[-2].frame if useAT else 1)
        )

        if not useAT:
            for pointData in camPointList:
                pointData.frame = 0
            self.camEndFrame = endFrame

        camData = self.getCamClass(shotObj.data.ootCamShotProp.shotCamMode, useAT)(None, startFrame, endFrame)
        return self.getCamCmdFunc(shotObj.data.ootCamShotProp.shotCamMode, useAT)(camData) + "".join(
            self.getCamPointCmd(pointData) for pointData in camPointList
        )

    def getCameraShotData(self):
        """Returns every Camera Shot commands"""

        shotObjects = self.csObjects["camShot"]
        cameraShotData = ""

        if len(shotObjects) > 0:
            motionFrameCount = -1
            for shotObj in shotObjects:
                cameraShotData += self.getCamListData(shotObj, False) + self.getCamListData(shotObj, True)
                motionFrameCount = max(motionFrameCount, self.camEndFrame + 1)
            self.motionFrameCount += motionFrameCount
            self.entryTotal += len(shotObjects) * 2

        return cameraShotData

    def getTextListData(self, textEntry: "OOTCSTextProperty"):
        match textEntry.textboxType:
            case "Text":
                return self.getTextCmd(
                    CutsceneCmdText(
                        None,
                        textEntry.startFrame,
                        textEntry.endFrame,
                        textEntry.textID,
                        self.getEnumValue("csTextType", textEntry, "csTextType"),
                        textEntry.topOptionTextID,
                        textEntry.bottomOptionTextID,
                    )
                )
            case "None":
                return self.getTextNoneCmd(CutsceneCmdTextNone(None, textEntry.startFrame, textEntry.endFrame))
            case "OcarinaAction":
                return self.getTextOcarinaActionCmd(
                    CutsceneCmdTextOcarinaAction(
                        None,
                        textEntry.startFrame,
                        textEntry.endFrame,
                        self.getEnumValue("ocarinaSongActionId", textEntry, "ocarinaAction"),
                        textEntry.ocarinaMessageId,
                    )
                )

    def getCutsceneData(self):
        csProp: "OOTCutsceneProperty" = self.csObjects["Cutscene"][0].ootCutsceneProperty
        self.frameCount = csProp.csEndFrame
        data = ""

        if csProp.csUseDestination:
            data += self.getDestinationCmd(csProp)
            self.entryTotal += 1

        for entry in csProp.csLists:
            subData = ""
            listCmd = ""
            entryTotal = 0
            match entry.listType:
                case "StartSeqList" | "StopSeqList" | "FadeOutSeqList":
                    entryTotal = len(entry.seqList)
                    for elem in entry.seqList:
                        enumKey = "csFadeOutSeqPlayer" if entry.listType == "FadeOutSeqList" else "seqId"
                        propName = "csSeqPlayer" if entry.listType == "FadeOutSeqList" else "csSeqID"
                        subData += self.getGenericSeqCmd(
                            ootEnumCSListTypeListC[entry.listType].removesuffix("_LIST"),
                            self.getEnumValue(enumKey, elem, propName),
                            elem.startFrame,
                            elem.endFrame,
                        )
                case "Transition":
                    subData += self.getTransitionCmd(
                        CutsceneCmdTransition(
                            None,
                            entry.transitionStartFrame,
                            entry.transitionEndFrame,
                            self.getEnumValue("csTransitionType", entry, "transitionType"),
                        )
                    )
                case _:
                    curList = getattr(entry, (entry.listType[0].lower() + entry.listType[1:]))
                    entryTotal = len(curList)
                    for elem in curList:
                        match entry.listType:
                            case "TextList":
                                subData += self.getTextListData(elem)
                            case "LightSettingsList":
                                subData += self.getLightSettingCmd(
                                    CutsceneCmdLightSetting(
                                        None, elem.startFrame, elem.endFrame, None, elem.lightSettingsIndex
                                    )
                                )
                            case "TimeList":
                                subData += self.getTimeCmd(
                                    CutsceneCmdTime(None, elem.startFrame, elem.endFrame, elem.hour, elem.minute)
                                )
                            case "MiscList":
                                subData += self.getMiscCmd(
                                    CutsceneCmdMisc(
                                        None,
                                        elem.startFrame,
                                        elem.endFrame,
                                        self.getEnumValue("csMiscType", elem, "csMiscType"),
                                    )
                                )
                            case "RumbleList":
                                subData += self.getRumbleControllerCmd(
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
            if entry.listType != "Transition":
                listCmd = self.getGenericListCmd(ootEnumCSListTypeListC[entry.listType], entryTotal)
            self.entryTotal += 1
            data += listCmd + subData

        return data

    def getExportData(self):
        """Returns the cutscene data"""

        csData = ""
        if not self.motionOnly:
            csData = self.getCutsceneData()
        csData += self.getActorCueListData(False) + self.getActorCueListData(True) + self.getCameraShotData()

        if self.motionFrameCount > self.frameCount:
            self.frameCount += self.motionFrameCount - self.frameCount

        return (
            (indent + f"CS_HEADER({self.entryTotal}, {self.frameCount}),\n")
            + csData
            + (indent + "CS_END_OF_SCRIPT(),\n")
        )
