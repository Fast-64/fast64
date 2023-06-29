import bpy, math, mathutils
from bpy.app.handlers import persistent
from .CamData import GetCamBones, GetCamCommands
from .ActionData import IsPreview, GetActorState


def UndefinedCamPos():
    return (mathutils.Vector((0.0, 0.0, 0.0)), mathutils.Quaternion(), 45.0)


def UndefinedCamPosAt():
    return (mathutils.Vector((0.0, 0.0, 0.0)), mathutils.Vector((0.0, 0.0, -1.0)), 0.0, 45.0)


def GetSplineCoeffs(t):
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


def Z64SplineInterpolate(bones, frame):
    # Reverse engineered from func_800BB2B4 in Debug ROM
    p = 0  # keyframe
    t = 0.0  # ratioBetweenPoints
    # Simulate cutscene for all frames up to present
    for f in range(frame):
        if p + 2 >= len(bones) - 1:
            # Camera position is uninitialized
            return UndefinedCamPosAt()
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
        return UndefinedCamPosAt()
    s1, s2, s3, s4 = GetSplineCoeffs(t)
    eye = s1 * bones[p].head + s2 * bones[p + 1].head + s3 * bones[p + 2].head + s4 * bones[p + 3].head
    at = s1 * bones[p].tail + s2 * bones[p + 1].tail + s3 * bones[p + 2].tail + s4 * bones[p + 3].tail
    roll = s1 * bones[p].camroll + s2 * bones[p + 1].camroll + s3 * bones[p + 2].camroll + s4 * bones[p + 3].camroll
    fov = s1 * bones[p].fov + s2 * bones[p + 1].fov + s3 * bones[p + 2].fov + s4 * bones[p + 3].fov
    return (eye, at, roll, fov)


def DummyLinearInterpolate(bones, frame):
    if len(bones) == 0:
        return UndefinedCamPosAt()
    f = 0
    last_bone = None
    next_bone = bones[0]
    for b in bones[1:]:
        last_bone = next_bone
        next_bone = b
        frames = last_bone.frames
        if frame >= f and frame < f + frames:
            fade = float(frame - f) / frames
            break
        f += frames
    else:
        last_bone = bones[-1]
        fade = 0.0
    if last_bone is None or next_bone is None:
        print("Internal error in linear interpolate algorithm")
        return UndefinedCamPosAt()
    last_eye, next_eye = last_bone.head, next_bone.head
    last_at, next_at = last_bone.tail, next_bone.tail  # "At" == "look at"
    last_roll, next_roll = last_bone.camroll, next_bone.camroll
    last_fov, next_fov = last_bone.fov, next_bone.fov
    eye = last_eye * (1.0 - fade) + next_eye * fade
    at = last_at * (1.0 - fade) + next_at * fade
    roll = last_roll * (1.0 - fade) + next_roll * fade
    fov = last_fov * (1.0 - fade) + next_fov * fade
    return (eye, at, roll, fov)


def GetCmdCamState(cmd, frame):
    frame -= cmd.data.start_frame + 1
    if frame < 0:
        print("Warning, camera command evaluated for frame " + str(frame))
        return UndefinedCamPos()
    bones = GetCamBones(cmd)
    if bones is None:
        return UndefinedCamPos()
    eye, at, roll, fov = Z64SplineInterpolate(bones, frame)
    # TODO handle cam_mode (relativeToLink)
    lookvec = at - eye
    if lookvec.length < 1e-6:
        return UndefinedCamPos()
    lookvec.normalize()
    ux = mathutils.Vector((1.0, 0.0, 0.0))
    uy = mathutils.Vector((0.0, 1.0, 0.0))
    uz = mathutils.Vector((0.0, 0.0, 1.0))
    qroll = mathutils.Quaternion(uz, roll * math.pi / 128.0)
    qpitch = mathutils.Quaternion(-ux, math.pi + math.acos(lookvec.dot(uz)))
    qyaw = mathutils.Quaternion(-uz, math.atan2(lookvec.dot(ux), lookvec.dot(uy)))
    return (eye, qyaw @ qpitch @ qroll, fov)


def GetCutsceneCamState(scene, cso, frame):
    """Returns (pos, rot_quat, fov)"""
    cmds = GetCamCommands(scene, cso)
    if len(cmds) == 0:
        return UndefinedCamPos()
    cur_cmd = None
    cur_cmd_start_frame = -1
    for c in cmds:
        if c.data.start_frame >= frame:
            continue
        if c.data.start_frame > cur_cmd_start_frame:
            cur_cmd = c
            cur_cmd_start_frame = c.data.start_frame
    if cur_cmd is None:
        return UndefinedCamPos()
    return GetCmdCamState(cur_cmd, frame)


@persistent
def PreviewFrameHandler(scene):
    for o in scene.objects:
        if o.parent is None:
            continue
        if o.parent.type != "EMPTY":
            continue
        if not o.parent.name.startswith("Cutscene."):
            continue
        if o.type == "CAMERA":
            pos, rot_quat, fov = GetCutsceneCamState(scene, o.parent, scene.frame_current)
            if pos is None:
                continue
            o.location = pos
            o.rotation_mode = "QUATERNION"
            o.rotation_quaternion = rot_quat
            o.data.angle = math.pi * fov / 180.0
        elif IsPreview(o):
            pos, rot = GetActorState(scene, o.parent, o.zc_alist.actor_id, scene.frame_current)
            if pos is None:
                continue
            o.location = pos
            o.rotation_mode = "XYZ"
            o.rotation_euler = rot


def Preview_register():
    bpy.app.handlers.frame_change_pre.append(PreviewFrameHandler)


def Preview_unregister():
    if PreviewFrameHandler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(PreviewFrameHandler)
