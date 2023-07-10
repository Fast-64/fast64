import math
import bpy

from dataclasses import dataclass
from bpy.types import Object
from .....utility import PluginError, indent
from ..constants import ootCSMotionCommandTypeRawToEnum

from ..io_classes import (
    OOTCSMotionActorCueList,
    OOTCSMotionActorCue,
    OOTCSMotionCamEyeSpline,
    OOTCSMotionCamATSpline,
    OOTCSMotionCamEyeSplineRelToPlayer,
    OOTCSMotionCamATSplineRelToPlayer,
    OOTCSMotionCamEye,
    OOTCSMotionCamAT,
    OOTCSMotionCamPoint,
)


class OOTCSMotionExportCommands:
    def getActorCueListCmd(self, actorCueList: OOTCSMotionActorCueList, isPlayerActor: bool):
        return indent + (
            f"CS_{'PLAYER' if isPlayerActor else 'ACTOR'}_CUE_LIST("
            + f"{actorCueList.commandType + ', ' if not isPlayerActor else ''}"
            + f"{actorCueList.entryTotal}),\n"
        )

    def getActorCueCmd(self, actorCue: OOTCSMotionActorCue, isPlayerActor: bool):
        return indent * 2 + (
            f"CS_{'PLAYER' if isPlayerActor else 'ACTOR'}_CUE("
            + f"{actorCue.actionID}, {actorCue.startFrame}, {actorCue.endFrame}, "
            + "".join(f"{rot}, " for rot in actorCue.rot)
            + "".join(f"{pos}, " for pos in actorCue.startPos)
            + "".join(f"{pos}, " for pos in actorCue.endPos)
            + "0.0f, 0.0f, 0.0f),\n"
        )

    def getCamListCmd(self, cmdName: str, startFrame: int, endFrame: int):
        return indent + f"{cmdName}({startFrame}, {endFrame}),\n"

    def getCamEyeSplineCmd(self, camEyeSpline: OOTCSMotionCamEyeSpline):
        return self.getCamListCmd("CS_CAM_EYE_SPLINE", camEyeSpline.startFrame, camEyeSpline.endFrame)

    def getCamATSplineCmd(self, camATSpline: OOTCSMotionCamATSpline):
        return self.getCamListCmd("CS_CAM_AT_SPLINE", camATSpline.startFrame, camATSpline.endFrame)

    def getCamEyeSplineRelToPlayerCmd(self, camEyeSplinePlayer: OOTCSMotionCamEyeSplineRelToPlayer):
        return self.getCamListCmd(
            "CS_CAM_EYE_SPLINE_REL_TO_PLAYER", camEyeSplinePlayer.startFrame, camEyeSplinePlayer.endFrame
        )

    def getCamATSplineRelToPlayerCmd(self, camATSplinePlayer: OOTCSMotionCamATSplineRelToPlayer):
        return self.getCamListCmd(
            "CS_CAM_AT_SPLINE_REL_TO_PLAYER", camATSplinePlayer.startFrame, camATSplinePlayer.endFrame
        )

    def getCamEyeCmd(self, camEye: OOTCSMotionCamEye):
        return self.getCamListCmd("CS_CAM_EYE", camEye.startFrame, camEye.endFrame)

    def getCamATCmd(self, camAT: OOTCSMotionCamAT):
        return self.getCamListCmd("CS_CAM_AT", camAT.startFrame, camAT.endFrame)

    def getCamPointCmd(self, camPoint: OOTCSMotionCamPoint):
        return indent * 2 + (
            f"CS_CAM_POINT("
            + f"{camPoint.continueFlag}, {camPoint.camRoll}, {camPoint.frame}, {camPoint.viewAngle}f, "
            + "".join(f"{pos}, " for pos in camPoint.pos)
            + "0),\n"
        )


@dataclass
class OOTCSMotionExport(OOTCSMotionExportCommands):
    csMotionObjects: dict[str, list[Object]]
    useDecomp: bool
    addBeginEndCmds: bool
    entryTotal: int = 0
    frameCount: int = 0
    camEndFrame: int = 0

    def getOoTRotation(self, obj: Object):
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
        scale = bpy.context.scene.ootBlenderScale

        x = int(round(pos[0] * scale))
        y = int(round(pos[2] * scale))
        z = int(round(-pos[1] * scale))

        if any(v < -0x8000 or v >= 0x8000 for v in (x, y, z)):
            raise RuntimeError(f"Position(s) too large, out of range: {x}, {y}, {z}")

        return [x, y, z]

    def getActorCueListData(self, isPlayer: bool):
        playerOrActor = f"{'Player' if isPlayer else 'Actor'}"
        actorCueListObjects = self.csMotionObjects[f"CS {playerOrActor} Cue List"]
        actorCueData = ""

        self.entryTotal += len(actorCueListObjects)
        for obj in actorCueListObjects:
            if obj.children is None:
                raise PluginError("ERROR: The Actor Cue List does not contain any child Actor Cue objects")

            entryTotal = len(obj.children)
            if entryTotal > 0:
                commandType = obj.ootCSMotionProperty.actorCueListProp.commandType

                if commandType == "Custom":
                    commandType = obj.ootCSMotionProperty.actorCueListProp.commandTypeCustom
                elif self.useDecomp:
                    commandType = ootCSMotionCommandTypeRawToEnum[commandType]

                actorCueList = OOTCSMotionActorCueList(commandType, int(entryTotal / 2))  # 2 points objects per cue
                actorCueData += self.getActorCueListCmd(actorCueList, isPlayer)

                for i, childObj in enumerate(obj.children):
                    if i % 2 == 0:
                        startFrame = childObj.ootCSMotionProperty.actorCueProp.cueStartFrame
                        endFrame = childObj.ootCSMotionProperty.actorCueProp.cueEndFrame
                        actorCue = OOTCSMotionActorCue(
                            startFrame,
                            endFrame,
                            childObj.ootCSMotionProperty.actorCueProp.cueActionID,
                            self.getOoTRotation(childObj),
                            self.getOoTPosition(childObj.location),
                            self.getOoTPosition(obj.children[i + 1].location),
                        )
                        actorCueData += self.getActorCueCmd(actorCue, isPlayer)

        return actorCueData

    def getCameraShotPointData(self, bones, useAT: bool):
        shotPoints: list[OOTCSMotionCamPoint] = []

        if len(bones) < 4:
            raise RuntimeError("Camera Armature needs at least 4 bones!")

        for bone in bones:
            if bone.parent is not None:
                raise RuntimeError("Camera Armature bones are not allowed to have parent bones!")

            posBlend = bone.head if not useAT else bone.tail
            shotPoints.append(
                OOTCSMotionCamPoint(
                    ("CS_CAM_CONTINUE" if self.useDecomp else "0"),
                    bone.ootCamShotPointProp.shotPointRoll,
                    bone.ootCamShotPointProp.shotPointFrame,
                    bone.ootCamShotPointProp.shotPointViewAngle,
                    self.getOoTPosition([int(posBlend[0]), int(posBlend[2]), int(posBlend[1])]),
                )
            )

        # NOTE: because of the game's bug explained in the importer we need to add an extra dummy point when exporting
        shotPoints.append(OOTCSMotionCamPoint("CS_CAM_STOP" if self.useDecomp else "-1", 0, 0, 0.0, [0, 0, 0]))
        return shotPoints

    def getCamCmdFunc(self, camMode: str, useAT: bool):
        camCmdFuncMap = {
            "splineEyeOrAT": self.getCamATSplineCmd if useAT else self.getCamEyeSplineCmd,
            "splineEyeOrATRelPlayer": self.getCamATSplineRelToPlayerCmd
            if useAT
            else self.getCamEyeSplineRelToPlayerCmd,
            "eyeOrAT": self.getCamATCmd if useAT else self.getCamEyeCmd,
        }

        return camCmdFuncMap[camMode]

    def getCamClass(self, camMode: str, useAT: bool):
        camCmdFuncMap = {
            "splineEyeOrAT": OOTCSMotionCamATSpline if useAT else OOTCSMotionCamEyeSpline,
            "splineEyeOrATRelPlayer": OOTCSMotionCamATSplineRelToPlayer
            if useAT
            else OOTCSMotionCamEyeSplineRelToPlayer,
            "eyeOrAT": OOTCSMotionCamAT if useAT else OOTCSMotionCamEye,
        }

        return camCmdFuncMap[camMode]

    def getCamListData(self, obj: Object, useAT: bool):
        splineData = self.getCameraShotPointData(obj.data.bones, useAT)

        startFrame = obj.data.ootCamShotProp.shotStartFrame
        endFrame = (
            startFrame + max(2, sum(point.frame for point in splineData)) + (splineData[-1].frame if useAT else 1)
        )

        self.camEndFrame = endFrame
        camData = self.getCamClass(obj.data.ootCamShotProp.shotCamMode, useAT)(startFrame, endFrame)

        return self.getCamCmdFunc(obj.data.ootCamShotProp.shotCamMode, useAT)(camData) + "".join(
            self.getCamPointCmd(pointData) for pointData in splineData
        )

    def getCameraShotData(self):
        shotObjects = self.csMotionObjects["camShot"]
        cameraShotData = ""

        if len(shotObjects) > 0:
            frameCount = -1
            for obj in shotObjects:
                cameraShotData += self.getCamListData(obj, False) + self.getCamListData(obj, True)
                endFrame = obj.data.ootCamShotProp.shotStartFrame + self.camEndFrame + 1
                frameCount = max(frameCount, endFrame)
            self.frameCount += frameCount
            self.entryTotal += len(shotObjects) * 2

        return cameraShotData

    def getExportData(self):
        data = self.getActorCueListData(False) + self.getActorCueListData(True) + self.getCameraShotData()
        if self.addBeginEndCmds:
            data = (
                indent + f"CS_BEGIN_CUTSCENE({self.entryTotal}, {self.frameCount}),\n" + data + indent + "CS_END(),\n"
            )
        return data
