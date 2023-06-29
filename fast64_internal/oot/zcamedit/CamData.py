import bpy
from .utility import CreateObject, MetersToBlend


def EditBoneToBone(armo, eb):
    for b in armo.data.bones:
        if b.name == eb.name:
            return b
    else:
        print("Could not find corresponding bone")
        return eb


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
