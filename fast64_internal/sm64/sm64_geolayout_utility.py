import bpy
from ..utility import PluginError


def getBoneGroupByName(armatureObj, name):
    for boneGroup in armatureObj.pose.bone_groups:
        if boneGroup.name == name:
            return boneGroup
    return None


def getBoneGroupIndex(armatureObj, name):
    index = 0
    for boneGroup in armatureObj.pose.bone_groups:
        if boneGroup.name == name:
            return index
        else:
            index += 1
    return -1


class BoneNodeProperties:
    def __init__(self, deform, theme):
        self.deform = deform
        self.theme = theme


# Only 0x13 commands are keyframe animated.
# We want to ignore/prevent animations on these other nodes.
boneNodeProperties = {
    "Switch": BoneNodeProperties(False, "THEME01"),  # 0xE
    "Start": BoneNodeProperties(True, "THEME12"),  # 0x0B
    "TranslateRotate": BoneNodeProperties(True, "THEME02"),  # 0x10
    "Translate": BoneNodeProperties(True, "THEME03"),  # 0x11
    "Rotate": BoneNodeProperties(True, "THEME04"),  # 0x12
    "Billboard": BoneNodeProperties(True, "THEME14"),  # 0x14
    "DisplayList": BoneNodeProperties(True, "THEME06"),  # 0x15
    "Shadow": BoneNodeProperties(False, "THEME07"),  # 0x16
    "Function": BoneNodeProperties(False, "THEME05"),  # 0x18
    "HeldObject": BoneNodeProperties(False, "THEME09"),  # 0x1C
    "Scale": BoneNodeProperties(True, "THEME10"),  # 0x1D
    "StartRenderArea": BoneNodeProperties(True, "THEME13"),  # 0x20
    "Ignore": BoneNodeProperties(False, "THEME08"),  # Used for rigging
    "SwitchOption": BoneNodeProperties(False, "THEME11"),
}

boneLayers = {"anim": 0, "other": 1, "meta": 2, "visual": 3}


def createBoneLayerMask(values):
    mask = [False] * 32
    for value in values:
        mask[value] = True
    return mask


def createBoneGroups(armatureObj):
    for (groupName, properties) in boneNodeProperties.items():
        if getBoneGroupByName(armatureObj, groupName) is None:
            boneGroup = armatureObj.pose.bone_groups.new(name=groupName)
            boneGroup.color_set = properties.theme


def addBoneToGroup(armatureObj, boneName, groupName):
    if groupName is None:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        posebone = armatureObj.pose.bones[boneName]
        bone = armatureObj.data.bones[boneName]
        posebone.bone_group = None
        bone.use_deform = True
        bone.layers = createBoneLayerMask([boneLayers["anim"]])
        posebone.lock_location = (False, False, False)
        posebone.lock_rotation = (False, False, False)
        posebone.lock_scale = (False, False, False)
        return

    elif groupName not in boneNodeProperties:
        raise PluginError("Bone group " + groupName + " doesn't exist.")

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    posebone = armatureObj.pose.bones[boneName]
    bone = armatureObj.data.bones[boneName]
    posebone.bone_group_index = getBoneGroupIndex(armatureObj, groupName)
    if groupName != "Ignore":
        bone.use_deform = boneNodeProperties[groupName].deform
        if groupName != "DisplayList":
            bone.layers = createBoneLayerMask([boneLayers["other"]])
        if groupName != "SwitchOption":
            posebone.lock_location = (True, True, True)
        posebone.lock_rotation = (True, True, True)
        posebone.lock_scale = (True, True, True)
