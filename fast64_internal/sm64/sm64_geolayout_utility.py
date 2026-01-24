import bpy
from bpy.types import Object, Armature, Bone, PoseBone

from ..f3d.f3d_gbi import GfxList
from ..utility import PluginError


def is_bone_animatable(bone: Bone):
    bone_props: "SM64_BoneProperties" = bone.fast64.sm64
    geo_cmd: str = bone.geo_cmd
    if geo_cmd == "DisplayListWithOffset":
        return True
    elif geo_cmd == "Custom" and bone_props.custom.is_animated:
        return True
    return False


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
    "DisplayListWithOffset": BoneNodeProperties(True, "THEME00"),
    "Custom": BoneNodeProperties(True, "THEME15"),
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


def addBoneToGroup(armature_obj: Object, name: str):
    armature: Armature = armature_obj.data
    pose_bone: PoseBone = armature_obj.pose.bones[name]
    bone: Bone = armature.bones[name]
    geo_cmd: str = bone.geo_cmd
    if geo_cmd not in boneNodeProperties:
        raise PluginError(f"Bone group {geo_cmd} doesn't exist.")

    lock_location, lock_rotation, lock_scale = False, False, False

    if is_bone_animatable(bone):
        if bpy.app.version >= (4, 0, 0):
            if not "anim" in armature.collections:
                armature.collections.new(name="anim")
            armature.collections["anim"].assign(bone)
        else:
            pose_bone.bone_group = None
            bone.layers = createBoneLayerMask([boneLayers["anim"]])

    if bpy.app.version >= (4, 0, 0):
        armature.collections[geo_cmd].assign(bone)
    else:
        pose_bone.bone_group_index = getBoneGroupIndex(armature_obj, geo_cmd)

    if geo_cmd == "Custom":
        custom = bone.fast64.sm64.custom
        bone.use_deform = custom.dl_option != "NONE"
        if not custom.is_animated:
            lock_location = lock_rotation = lock_scale = True
    elif geo_cmd != "Ignore":
        bone.use_deform = boneNodeProperties[geo_cmd].deform
        if geo_cmd != "SwitchOption":
            lock_location = True
        lock_rotation = lock_scale = True
    if geo_cmd not in {"Ignore", "DisplayList"}:
        if bpy.app.version >= (4, 0, 0):
            if not "other" in armature.collections:
                armature.collections.new(name="other")
            armature.collections["other"].assign(bone)
        else:
            bone.layers = createBoneLayerMask([boneLayers["other"]])

    pose_bone.lock_location = (lock_location, lock_location, lock_location)
    pose_bone.lock_rotation = (lock_rotation, lock_rotation, lock_rotation)
    pose_bone.lock_scale = (lock_scale, lock_scale, lock_scale)


def updateBone(bone, context):
    armatureObj = context.object

    createBoneGroups(armatureObj)
    addBoneToGroup(armatureObj, bone.name)


OverrideHash = tuple[any, ...]


class BaseDisplayListNode:
    """Base displaylist node with common helper functions dealing with displaylists"""

    dl_ext = "WITH_DL"  # add dl_ext to geo command if command has a displaylist
    override_layer = False
    dlRef: str | GfxList | None
    override_hash: OverrideHash | None = None
    DLmicrocode = None

    def get_dl_address(self):
        assert not isinstance(self.dlRef, str), "dlRef string not supported in binary"
        if isinstance(self.dlRef, GfxList):
            return self.dlRef.startAddress
        if self.hasDL and self.DLmicrocode is not None:
            return self.DLmicrocode.startAddress
        return None

    def get_dl_name(self):
        if isinstance(self.dlRef, GfxList):
            return self.dlRef.name
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
