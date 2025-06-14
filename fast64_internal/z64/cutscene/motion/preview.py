import bpy
import math

from mathutils import Vector, Quaternion
from bpy.app.handlers import persistent
from bpy.types import Object, Scene
from ....utility import PluginError
from .utility import (
    BoneData,
    getCameraShotBoneData,
    getCSMotionValidateObj,
)


# Eye -> Position, AT -> look-at, where the camera is looking


def getUndefinedCamPosEye():
    return (Vector((0.0, 0.0, 0.0)), Quaternion(), 45.0)


def getUndefinedCamPosAT():
    return (Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, -1.0)), 0.0, 45.0)


def getSplineCoeffs(t: float):
    # Reverse engineered from func_800BB0A0 in Debug ROM

    t = min(t, 1.0)  # no check for t < 0
    oneminust = 1.0 - t
    tsq = t * t
    oneminustcube6 = (oneminust * oneminust * oneminust) / 6.0
    tcube = tsq * t
    spline2 = ((tcube * 0.5) - tsq) + 0.6666667
    spline3 = ((tsq + t - tcube) * 0.5) + 0.16666667
    tcube6 = tcube / 6.0

    return oneminustcube6, spline2, spline3, tcube6


def getZ64SplineInterpolate(bones: list[BoneData], frame: int):
    # Reverse engineered from func_800BB2B4 in Debug ROM

    p = 0  # keyframe
    t = 0.0  # ratioBetweenPoints

    # Simulate cutscene for all frames up to present
    for _ in range(frame):
        if p + 2 >= len(bones) - 1:
            # Camera position is uninitialized
            return getUndefinedCamPosAT()

        framesPoint1 = bones[p + 1].frame
        denomPoint1 = 1.0 / framesPoint1 if framesPoint1 != 0 else 0.0
        framesPoint2 = bones[p + 2].frame
        denomPoint2 = 1.0 / framesPoint2 if framesPoint2 != 0 else 0.0
        dt = max(t * (denomPoint2 - denomPoint1) + denomPoint1, 0.0)

        # Different from in game; we remove the extra dummy point at import
        # and add it at export.
        if t + dt >= 1.0:
            if p + 3 == len(bones) - 1:
                break

            t -= 1.0
            p += 1

        t += dt

    # Spline interpolate for current situation
    if p + 3 > len(bones) - 1:
        if frame > 0:
            print("Internal error in spline algorithm")

        return getUndefinedCamPosAT()

    s1, s2, s3, s4 = getSplineCoeffs(t)
    eye = s1 * bones[p].head + s2 * bones[p + 1].head + s3 * bones[p + 2].head + s4 * bones[p + 3].head
    at = s1 * bones[p].tail + s2 * bones[p + 1].tail + s3 * bones[p + 2].tail + s4 * bones[p + 3].tail
    roll = s1 * bones[p].roll + s2 * bones[p + 1].roll + s3 * bones[p + 2].roll + s4 * bones[p + 3].roll
    viewAngle = (
        s1 * bones[p].viewAngle
        + s2 * bones[p + 1].viewAngle
        + s3 * bones[p + 2].viewAngle
        + s4 * bones[p + 3].viewAngle
    )

    return (eye, at, roll, viewAngle)


def getCmdCamState(shotObj: Object, frame: int):
    frame -= shotObj.data.ootCamShotProp.shotStartFrame + 1

    if frame < 0:
        print(f"Warning, camera command evaluated for frame {frame}")
        return getUndefinedCamPosEye()

    bones = getCameraShotBoneData(shotObj, False)

    if bones is None:
        return getUndefinedCamPosEye()

    eye, at, roll, viewAngle = getZ64SplineInterpolate(bones, frame)
    # TODO handle cam_mode (relativeToLink)
    lookvec = at - eye

    if lookvec.length < 1e-6:
        return getUndefinedCamPosEye()

    lookvec.normalize()
    ux = Vector((1.0, 0.0, 0.0))
    uy = Vector((0.0, 1.0, 0.0))
    uz = Vector((0.0, 0.0, 1.0))
    qroll = Quaternion(uz, roll * math.pi / 128.0)
    qpitch = Quaternion(-ux, math.pi + math.acos(lookvec.dot(uz)))
    qyaw = Quaternion(-uz, math.atan2(lookvec.dot(ux), lookvec.dot(uy)))

    return (eye, qyaw @ qpitch @ qroll, viewAngle)


def getCutsceneCamState(csObj: Object, frame: int):
    """Returns (pos, rot_quat, viewAngle)"""

    shotObjects: list[Object] = []
    for childObj in csObj.children:
        obj = getCSMotionValidateObj(csObj, childObj, "Camera Shot")
        if obj is not None:
            shotObjects.append(obj)
    shotObjects.sort(key=lambda obj: obj.name)
    shotObj = None

    if len(shotObjects) > 0:
        startFrame = -1

        for obj in shotObjects:
            if obj.data.ootCamShotProp.shotStartFrame < frame and obj.data.ootCamShotProp.shotStartFrame > startFrame:
                shotObj = obj
                startFrame = obj.data.ootCamShotProp.shotStartFrame

    if shotObj is None or len(shotObjects) == 0:
        return getUndefinedCamPosEye()

    return getCmdCamState(shotObj, frame)


def getActorCueState(cueListObj: Object, frame: int):
    pos = Vector((0.0, 0.0, 0.0))
    rot = Vector((0.0, 0.0, 0.0))

    cueList: list[Object] = []
    for cueObj in cueListObj.children:
        obj = getCSMotionValidateObj(None, cueObj, None)
        if obj is not None:
            cueList.append(obj)
    cueList.sort(key=lambda o: o.ootCSMotionProperty.actorCueProp.cueStartFrame)

    if len(cueList) >= 2:
        for i in range(len(cueList) - 1):
            startFrame = cueList[i].ootCSMotionProperty.actorCueProp.cueStartFrame
            endFrame = cueList[i + 1].ootCSMotionProperty.actorCueProp.cueStartFrame

            if endFrame > startFrame and frame > startFrame:
                if frame <= endFrame:
                    pos = cueList[i].location * (endFrame - frame) + cueList[i + 1].location * (frame - startFrame)
                    pos /= endFrame - startFrame
                    rot = cueList[i].rotation_euler
                    return pos, rot
                elif i == len(cueList) - 2:
                    # If went off the end, use last position
                    pos = cueList[i + 1].location
                    rot = cueList[i].rotation_euler
    return pos, rot


@persistent
def previewFrameHandler(scene: Scene):
    for obj in bpy.data.objects:
        parentObj = obj.parent
        if (
            parentObj is not None
            and parentObj.type == "EMPTY"
            and parentObj.name.startswith("Cutscene.")
            and parentObj.ootEmptyType == "Cutscene"
        ):
            if obj.type == "CAMERA":
                pos, rot_quat, viewAngle = getCutsceneCamState(parentObj, scene.frame_current)

                if scene.ootPreviewSettingsProperty.useWidescreen:
                    viewAngle *= 4 / 3

                if pos is not None:
                    obj.location = pos
                    obj.rotation_mode = "QUATERNION"
                    obj.rotation_quaternion = rot_quat
                    obj.data.angle = math.pi * viewAngle / 180.0
            elif obj.ootEmptyType in ["CS Actor Cue Preview", "CS Player Cue Preview"]:
                cueListToPreview = None
                if "Actor" in obj.ootEmptyType:
                    cueListToPreview = obj.ootCSMotionProperty.actorCueListProp.actorCueListToPreview
                elif "Player" in obj.ootEmptyType:
                    cueListToPreview = obj.ootCSMotionProperty.actorCueListProp.playerCueListToPreview
                else:
                    raise PluginError("Unknown Empty Type!")

                if cueListToPreview is not None:
                    pos, rot = getActorCueState(cueListToPreview, scene.frame_current)

                    if pos is not None:
                        obj.location = pos
                        obj.rotation_mode = "XYZ"
                        obj.rotation_euler = rot


def csMotion_preview_register():
    bpy.app.handlers.frame_change_pre.append(previewFrameHandler)


def csMotion_preview_unregister():
    if previewFrameHandler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(previewFrameHandler)
