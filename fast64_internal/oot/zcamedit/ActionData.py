import bpy, mathutils
import random

from .Common import *


def IsActionList(obj):
    if obj is None or obj.type != "EMPTY":
        return False
    if not any(obj.name.startswith(s) for s in ["Path.", "ActionList."]):
        return False
    if obj.parent is None or obj.parent.type != "EMPTY" or not obj.parent.name.startswith("Cutscene."):
        return False
    return True


def IsActionPoint(obj):
    if obj is None or obj.type != "EMPTY":
        return False
    if not any(obj.name.startswith(s) for s in ["Point.", "Action."]):
        return False
    if not IsActionList(obj.parent):
        return False
    return True


def IsPreview(obj):
    if obj is None or obj.type != "EMPTY":
        return False
    if not obj.name.startswith("Preview."):
        return False
    if obj.parent is None or obj.parent.type != "EMPTY" or not obj.parent.name.startswith("Cutscene."):
        return False
    return True


def GetActionListPoints(scene, al_object):
    ret = []
    for o in scene.objects:
        if IsActionPoint(o) and o.parent == al_object:
            ret.append(o)
    ret.sort(key=lambda o: o.zc_apoint.start_frame)
    return ret


def GetActionListStartFrame(scene, al_object):
    points = GetActionListPoints(scene, al_object)
    if len(points) < 2:
        return 1000000
    return points[0].zc_apoint.start_frame


def GetActionLists(scene, cs_object, actorid):
    ret = []
    for o in scene.objects:
        if IsActionList(o) and o.parent == cs_object and (actorid is None or o.zc_alist.actor_id == actorid):
            ret.append(o)
    ret.sort(key=lambda o: GetActionListStartFrame(scene, o))
    return ret


def GetActorState(scene, cs_object, actorid, frame):
    actionlists = GetActionLists(scene, cs_object, actorid)
    pos = mathutils.Vector((0.0, 0.0, 0.0))
    rot = mathutils.Vector((0.0, 0.0, 0.0))
    for al in actionlists:
        points = GetActionListPoints(scene, al)
        if len(points) < 2:
            continue
        for i in range(len(points) - 1):
            s = points[i].zc_apoint.start_frame
            e = points[i + 1].zc_apoint.start_frame
            if e <= s:
                continue
            if frame <= s:
                continue
            if frame <= e:
                pos = points[i].location * (e - frame) + points[i + 1].location * (frame - s)
                pos /= e - s
                rot = points[i].rotation_euler
                return pos, rot
            elif i == len(points) - 2:
                # If went off the end, use last position
                pos = points[i + 1].location
                rot = points[i].rotation_euler
    return pos, rot


def CreateActionPoint(context, al_object, select, pos, start_frame, action_id):
    point = CreateObject(context, "Point.001", None, select)
    point.parent = al_object
    point.empty_display_type = "ARROWS"
    point.location = pos
    point.rotation_mode = "XZY"
    point.zc_apoint.start_frame = start_frame
    point.zc_apoint.action_id = action_id
    return point


def CreateDefaultActionPoint(context, al_object, select):
    points = GetActionListPoints(context.scene, al_object)
    if len(points) == 0:
        pos = mathutils.Vector((random.random() * 40.0 - 20.0, -10.0, 0.0))
        start_frame = 0
        action_id = "0x0001"
    else:
        pos = points[-1].location + mathutils.Vector((0.0, 10.0, 0.0))
        start_frame = points[-1].zc_apoint.start_frame + 20
        action_id = points[-1].zc_apoint.action_id
    CreateActionPoint(context, al_object, select, pos, start_frame, action_id)


def GetActorName(actor_id):
    return "Link" if actor_id < 0 else "Actor" + str(actor_id)


def CreateActorAction(context, actor_id, cs_object):
    al_object = CreateObject(context, "ActionList." + GetActorName(actor_id) + ".001", None, True)
    al_object.parent = cs_object
    al_object.zc_alist.actor_id = actor_id
    return al_object


def CreateDefaultActorAction(context, actor_id, cs_object):
    al_object = CreateActorAction(context, actor_id, cs_object)
    CreateDefaultActionPoint(context, al_object, False)
    CreateDefaultActionPoint(context, al_object, False)


def CreateOrInitPreview(context, cs_object, actor_id, select=False):
    for o in context.blend_data.objects:
        if IsPreview(o) and o.parent == cs_object and o.zc_alist.actor_id == actor_id:
            preview = o
            break
    else:
        preview = CreateObject(context, "Preview." + GetActorName(actor_id) + ".001", None, select)
        preview.parent = cs_object
    preview.empty_display_type = "SINGLE_ARROW"
    preview.empty_display_size = MetersToBlend(context, ActorHeightMeters(context, actor_id))
    preview.zc_alist.actor_id = actor_id
