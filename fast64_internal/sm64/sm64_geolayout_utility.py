import bpy

from ..f3d.f3d_parser import math_eval
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
    "Custom": BoneNodeProperties(True, "THEME12"),
}

boneLayers = {"anim": 0, "other": 1, "meta": 2, "visual": 3}


def createBoneLayerMask(values):
    mask = [False] * 32
    for value in values:
        mask[value] = True
    return mask


def createBoneGroups(armatureObj):
    armature = armatureObj.data
    for groupName, properties in boneNodeProperties.items():
        if bpy.app.version >= (4, 0, 0):
            if groupName not in armature.collections:
                boneGroup = armature.collections.new(name=groupName)
        else:
            if getBoneGroupByName(armatureObj, groupName) is None:
                boneGroup = armatureObj.pose.bone_groups.new(name=groupName)
                boneGroup.color_set = properties.theme


def addBoneToGroup(armatureObj, boneName, groupName):
    armature = armatureObj.data
    if groupName is None:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        posebone = armatureObj.pose.bones[boneName]
        bone = armature.bones[boneName]
        bone.use_deform = True
        if bpy.app.version >= (4, 0, 0):
            if not "anim" in armature.collections:
                armature.collections.new(name="anim")
            armature.collections["anim"].assign(bone)
        else:
            posebone.bone_group = None
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
    if bpy.app.version >= (4, 0, 0):
        armature.collections[groupName].assign(bone)
    else:
        posebone.bone_group_index = getBoneGroupIndex(armatureObj, groupName)

    if groupName != "Ignore":
        bone.use_deform = boneNodeProperties[groupName].deform  # TODO: impl custom
        if groupName != "DisplayList":
            if bpy.app.version >= (4, 0, 0):
                if not "other" in armature.collections:
                    armature.collections.new(name="other")
                armature.collections["other"].assign(bone)
            else:
                bone.layers = createBoneLayerMask([boneLayers["other"]])

        if groupName != "SwitchOption":
            posebone.lock_location = (True, True, True)
        posebone.lock_rotation = (True, True, True)
        posebone.lock_scale = (True, True, True)


class BaseDisplayListNode:
    """Base displaylist node with common helper functions dealing with displaylists"""

    dl_ext = "WITH_DL"  # add dl_ext to geo command if command has a displaylist
    bleed_independently = False  # base behavior, can be changed with obj boolProp

    def get_dl_address(self):
        if self.dlRef is not None:
            value = math_eval(self.dlRef, object())
            if not isinstance(value, int):
                raise PluginError(f'Displaylist reference "{self.dlRef}" is not a valid address.')
            return value
        if self.hasDL and self.DLmicrocode is not None:
            return self.DLmicrocode.startAddress
        return None

    def get_dl_name(self):
        if self.hasDL and (self.dlRef or self.DLmicrocode is not None):
            return self.dlRef or self.DLmicrocode.name
        return "NULL"

    def get_c_func_macro(self, base_cmd: str):
        return f"{base_cmd}_{self.dl_ext}" if self.hasDL else base_cmd

    def c_func_macro(self, base_cmd: str, *args: str):
        """
        Supply base command and all arguments for command.
        if self.hasDL:
                this will add self.dl_ext to the command, and
                adds the name of the displaylist to the end of the command
        Example return: 'GEO_YOUR_COMMAND_WITH_DL(arg, arg2),'
        """
        all_args = list(args)
        if self.hasDL:
            all_args.append(self.get_dl_name())
        return f'{self.get_c_func_macro(base_cmd)}({", ".join(all_args)})'
