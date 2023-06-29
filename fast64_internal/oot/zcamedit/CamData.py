import bpy

from .Common import *


def GetCamCommands(scene, cso):
    ret = []
    for o in scene.objects:
        if o.type != "ARMATURE":
            continue
        if o.parent is None:
            continue
        if o.parent != cso:
            continue
        ret.append(o)
    ret.sort(key=lambda o: o.name)
    return ret


def BoneToEditBone(armo, b):
    for eb in armo.data.edit_bones:
        if eb.name == b.name:
            return eb
    else:
        print("Could not find corresponding bone")
        return b


def EditBoneToBone(armo, eb):
    for b in armo.data.bones:
        if b.name == eb.name:
            return b
    else:
        print("Could not find corresponding bone")
        return eb


class PropsBone:
    def __init__(self, armo, b):
        eb = BoneToEditBone(armo, b) if armo.mode == "EDIT" else None
        self.name = b.name
        self.head = eb.head if eb is not None else b.head
        self.tail = eb.tail if eb is not None else b.tail
        self.frames = eb["frames"] if eb is not None and "frames" in eb else b.frames
        self.fov = eb["fov"] if eb is not None and "fov" in eb else b.fov
        self.camroll = eb["camroll"] if eb is not None and "camroll" in eb else b.camroll


def GetCamBones(armo):
    bones = []
    for b in armo.data.bones:
        if b.parent is not None:
            print("Camera armature bones are not allowed to have parent bones")
            return None
        bones.append(PropsBone(armo, b))
    bones.sort(key=lambda b: b.name)
    return bones


def GetCamBonesChecked(cmd):
    bones = GetCamBones(cmd)
    if bones is None:
        raise RuntimeError("Error in bone properties")
    if len(bones) < 4:
        raise RuntimeError("Only {} bones in {}".format(len(bones), cmd.name))
    return bones


def GetFakeCamCmdLength(armo, at):
    bones = GetCamBonesChecked(armo)
    base = max(2, sum(b.frames for b in bones))
    # Seems to be the algorithm which was used in the canon tool: the at list
    # counts the extra point (same frames as the last real point), and the pos
    # list doesn't count the extra point but adds 1. Of course, neither of these
    # values is actually the number of frames the camera motion lasts for.
    return base + (bones[-1].frames if at else 1)


def GetCSFakeEnd(context, cs_object):
    cmdlists = GetCamCommands(context.scene, cs_object)
    cs_endf = -1
    for c in cmdlists:
        end_frame = c.data.start_frame + GetFakeCamCmdLength(c, False) + 1
        cs_endf = max(cs_endf, end_frame)
    return cs_endf


def CreateShot(context, cs_object):
    arm = context.blend_data.armatures.new("Shot")
    arm.display_type = "STICK"
    arm.show_names = True
    armo = CreateObject(context, arm.name, arm, True)
    armo.parent = cs_object
    for i in range(4):
        bpy.ops.object.mode_set(mode="EDIT")
        bone = arm.edit_bones.new("K{:02}".format(i + 1))
        bname = bone.name
        x = MetersToBlend(context, float(i + 1))
        bone.head = [x, 0.0, 0.0]
        bone.tail = [x, MetersToBlend(context, 1.0), 0.0]
        bpy.ops.object.mode_set(mode="OBJECT")
        bone = arm.bones[bname]
        bone.frames = 20
        bone.fov = 60.0
        bone.camroll = 0
