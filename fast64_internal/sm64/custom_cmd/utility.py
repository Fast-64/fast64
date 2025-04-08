import math
import mathutils
from typing import Literal, NamedTuple, Optional
from re import fullmatch
from bpy.types import Object, Bone, Context, SpaceView3D, Scene

AvailableOwners = Object | Bone | Scene
CustomCmdConf = Literal["PRESET", "PRESET_EDIT", "NO_PRESET"]  # type of configuration


def getDrawLayerName(drawLayer):
    from ..sm64_geolayout_classes import getDrawLayerName

    return getDrawLayerName(drawLayer)


def duplicate_name(name, existing_names: set, old_name: str | None = None):
    if not name in existing_names:
        return name
    num = 0
    if old_name is not None:
        number_match = fullmatch(r"(.*?)\.(\d+)$", old_name)
        if number_match is not None:  # if name already a duplicate/copy, add number
            name, num = number_match.group(1), int(number_match.group(2))
        else:
            name, num = old_name, 0
    new_name = name
    for i in range(1, len(existing_names) + 2):
        if new_name not in existing_names:  # only use name if it's unique
            return new_name
        new_name = f"{name}.{num+i:03}"


def get_custom_prop(context: Context):
    class CustomContext(NamedTuple):
        custom: Optional["SM64_CustomCmdProperties"]
        owner: Optional[AvailableOwners]

    """If owner is a scene, custom is always None"""
    if isinstance(context.space_data, SpaceView3D):
        return CustomContext(None, context.scene)
    else:
        if context.bone is not None:
            return CustomContext(context.bone.fast64.sm64.custom, context.bone)
        if context.object is not None:
            return CustomContext(context.object.fast64.sm64.custom, context.object)
    return CustomContext(None, None)


def get_custom_cmd_preset(custom_cmd: "SM64_CustomCmdProperties", context: Context):
    if custom_cmd.preset == "":
        return None
    presets: list["SM64_CustomCmdProperties"] = context.scene.fast64.sm64.custom_cmds
    return presets[int(custom_cmd.preset)]


def check_preset_hashes(owner: AvailableOwners, context):
    if owner.fast64.sm64.custom.locked:
        return
    custom_cmd: "SM64_CustomCmdProperties" = owner.fast64.sm64.custom
    if custom_cmd.preset == "NONE":
        return
    preset_cmd = get_custom_cmd_preset(custom_cmd, context)
    if preset_cmd is None or (custom_cmd.saved_hash != preset_cmd.preset_hash):
        custom_cmd.preset, custom_cmd.saved_hash = "NONE", custom_cmd.preset_hash


def custom_cmd_preset_update(_self, context: Context):
    owner = get_custom_prop(context).owner
    if isinstance(owner, Scene):  # current context is scene, check all
        for obj in context.scene.objects:
            check_preset_hashes(obj, context)
            if obj.type == "ARMATURE":
                for bone in obj.data.bones:
                    check_preset_hashes(bone, context)
    elif owner is not None:
        check_preset_hashes(owner, context)


def get_custom_cmd_preset_enum(_self, context: Context):
    if isinstance(get_custom_prop(context)[1], Bone):
        allowed_types = {"Geo"}
    else:
        allowed_types = {"Level", "Geo", "Special"}
    return [("NONE", "No Preset", "No preset selected")] + [
        (str(i), preset.name, f"{preset.name} ({preset.cmd_type})")
        for i, preset in enumerate(context.scene.fast64.sm64.custom_cmds)
        if preset.cmd_type in allowed_types
    ]


def better_round(value):  # round, but handle inf
    return round(max(-(2**31), min(2**31 - 1, value)))


def get_transforms(owner: Optional[AvailableOwners] = None):
    if isinstance(owner, Object):
        return (owner.matrix_world, owner.matrix_local)
    elif isinstance(owner, Bone):
        relative = owner.matrix_local
        if owner.parent is not None:
            relative = owner.parent.matrix_local.inverted() @ relative
        return (owner.matrix_local, relative)
    else:
        return (mathutils.Matrix.Identity(4),) * 2
