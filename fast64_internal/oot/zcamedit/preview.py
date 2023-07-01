import bpy
import math

from mathutils import Vector, Quaternion
from bpy.app.handlers import persistent
from bpy.types import Bone, Object, Scene
from .utility import (
    PropsBone,
    getShotPropBones,
    getShotObjects,
    isPreview,
    getActorCueListObjects,
    getActorCuePointObjects,
)


def getUndefinedCamPos():
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


def getZ64SplineInterpolate(bones: list[PropsBone], frame: int):
    # Reverse engineered from func_800BB2B4 in Debug ROM

    p = 0  # keyframe
    t = 0.0  # ratioBetweenPoints

    # Simulate cutscene for all frames up to present
    for f in range(frame):
        if p + 2 >= len(bones) - 1:
            # Camera position is uninitialized
            return getUndefinedCamPosAT()

        framesPoint1 = bones[p + 1].frames
        denomPoint1 = 1.0 / framesPoint1 if framesPoint1 != 0 else 0.0
        framesPoint2 = bones[p + 2].frames
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
    roll = s1 * bones[p].camroll + s2 * bones[p + 1].camroll + s3 * bones[p + 2].camroll + s4 * bones[p + 3].camroll
    fov = s1 * bones[p].fov + s2 * bones[p + 1].fov + s3 * bones[p + 2].fov + s4 * bones[p + 3].fov

    return (eye, at, roll, fov)


def getCmdCamState(shotObj: Object, frame: int):
    frame -= shotObj.data.start_frame + 1

    if frame < 0:
        print(f"Warning, camera command evaluated for frame {frame}")
        return getUndefinedCamPos()

    bones = getShotPropBones(shotObj)

    if bones is None:
        return getUndefinedCamPos()

    eye, at, roll, fov = getZ64SplineInterpolate(bones, frame)
    # TODO handle cam_mode (relativeToLink)
    lookvec = at - eye

    if lookvec.length < 1e-6:
        return getUndefinedCamPos()

    lookvec.normalize()
    ux = Vector((1.0, 0.0, 0.0))
    uy = Vector((0.0, 1.0, 0.0))
    uz = Vector((0.0, 0.0, 1.0))
    qroll = Quaternion(uz, roll * math.pi / 128.0)
    qpitch = Quaternion(-ux, math.pi + math.acos(lookvec.dot(uz)))
    qyaw = Quaternion(-uz, math.atan2(lookvec.dot(ux), lookvec.dot(uy)))

    return (eye, qyaw @ qpitch @ qroll, fov)


def getCutsceneCamState(scene: Scene, csObj: Object, frame: int):
    """Returns (pos, rot_quat, fov)"""

    shotObjects = getShotObjects(scene, csObj)

    if len(shotObjects) > 0:
        shotObj = None
        startFrame = -1

        for obj in shotObjects:
            if obj.data.start_frame < frame and obj.data.start_frame > startFrame:
                shotObj = obj
                startFrame = obj.data.start_frame

    if shotObj is None or len(shotObjects) == 0:
        return getUndefinedCamPos()

    return getCmdCamState(shotObj, frame)


def getActorCueState(scene: Scene, csObj: Object, actorid: int, frame: int):
    cueObjects = getActorCueListObjects(scene, csObj, actorid)
    pos = Vector((0.0, 0.0, 0.0))
    rot = Vector((0.0, 0.0, 0.0))

    for cueObj in cueObjects:
        points = getActorCuePointObjects(scene, cueObj)

        if len(points) >= 2:
            for i in range(len(points) - 1):
                startFrame = points[i].zc_apoint.start_frame
                endFrame = points[i + 1].zc_apoint.start_frame

                if endFrame > startFrame and frame > startFrame:
                    if frame <= endFrame:
                        pos = points[i].location * (endFrame - frame) + points[i + 1].location * (frame - startFrame)
                        pos /= endFrame - startFrame
                        rot = points[i].rotation_euler
                        return pos, rot
                    elif i == len(points) - 2:
                        # If went off the end, use last position
                        pos = points[i + 1].location
                        rot = points[i].rotation_euler
    return pos, rot


@persistent
def previewFrameHandler(scene: Scene):
    for obj in scene.objects:
        if obj.parent is not None and obj.parent.type == "EMPTY" and obj.parent.name.startswith("Cutscene."):
            if obj.type == "CAMERA":
                pos, rot_quat, fov = getCutsceneCamState(scene, obj.parent, scene.frame_current)

                if pos is not None:
                    obj.location = pos
                    obj.rotation_mode = "QUATERNION"
                    obj.rotation_quaternion = rot_quat
                    obj.data.angle = math.pi * fov / 180.0
            elif isPreview(obj):
                pos, rot = getActorCueState(scene, obj.parent, obj.zc_alist.actor_id, scene.frame_current)

                if pos is not None:
                    obj.location = pos
                    obj.rotation_mode = "XYZ"
                    obj.rotation_euler = rot


def csMotion_preview_register():
    bpy.app.handlers.frame_change_pre.append(previewFrameHandler)


def csMotion_preview_unregister():
    if previewFrameHandler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(previewFrameHandler)
