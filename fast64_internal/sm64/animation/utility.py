from typing import TYPE_CHECKING, Union
import functools
import re

from bpy.types import Context, Object, Action, PoseBone

from ...utility import findStartBones, PluginError, toAlnum
from ..sm64_geolayout_utility import is_bone_animatable

if TYPE_CHECKING:
    from .properties import (
        SM64_AnimHeaderProperties,
        SM64_ActionAnimProperty,
        SM64_AnimProperties,
        SM64_AnimTableElementProperties,
        SM64_ArmatureAnimProperties,
    )


def is_obj_animatable(obj: Object) -> bool:
    if obj.type == "ARMATURE" or (obj.type == "MESH" and obj.geo_cmd_static == "DisplayListWithOffset"):
        return True
    return False


def get_anim_obj(context: Context) -> Object | None:
    obj = context.object
    if obj is None and len(context.selected_objects) > 0:
        obj = context.selected_objects[0]
    if obj is not None and is_obj_animatable(obj):
        return obj


def animation_operator_checks(context: Context, requires_animation=True, specific_obj: Object | None = None):
    if specific_obj is None:
        if len(context.selected_objects) > 1:
            raise PluginError("Multiple objects selected at once.")
        obj = get_anim_obj(context)
    else:
        obj = specific_obj
        if is_obj_animatable(obj):
            raise PluginError(f'Selected object "{obj.name}" is not an armature.')
    if requires_animation and obj.animation_data is None:
        raise PluginError(f'Armature "{obj.name}" has no animation data.')


def get_selected_action(obj: Object, raise_exc=True) -> Action:
    assert obj is not None
    if not is_obj_animatable(obj):
        if raise_exc:
            raise ValueError(f'Object "{obj.name}" is not animatable in SM64.')
    elif obj.animation_data is not None and obj.animation_data.action is not None:
        return obj.animation_data.action
    if raise_exc:
        raise ValueError(f'No action selected in object "{obj.name}".')


def get_anim_owners(obj: Object):
    """Get SM64 animation bones from an armature or return the obj if it's an animated cmd mesh"""

    def check_children(children: list[Object] | None):
        if children is None:
            return
        for child in children:
            if child.geo_cmd_static == "DisplayListWithOffset":
                raise PluginError("Cannot have child mesh with animation, use an armature")
            check_children(child.children)

    if obj.type == "MESH":  # Object will be treated as a bone
        if obj.geo_cmd_static == "DisplayListWithOffset":
            check_children(obj.children)
            return [obj]
        else:
            raise PluginError("Mesh is not animatable")

    assert obj.type == "ARMATURE", "Obj is neither mesh or armature"

    bones_to_process: list[str] = findStartBones(obj)
    current_bone = obj.data.bones[bones_to_process[0]]
    anim_bones: list[PoseBone] = []

    # Get animation bones in order
    while len(bones_to_process) > 0:
        bone_name = bones_to_process[0]
        current_bone = obj.data.bones[bone_name]
        current_pose_bone = obj.pose.bones[bone_name]
        bones_to_process = bones_to_process[1:]

        # Only handle 0x13 bones for animation
        if is_bone_animatable(current_bone):
            anim_bones.append(current_pose_bone)

        # Traverse children in alphabetical order.
        children_names = sorted([bone.name for bone in current_bone.children])
        bones_to_process = children_names + bones_to_process

    return anim_bones


def num_to_padded_hex(num: int):
    hex_str = hex(num)[2:].upper()  # remove the '0x' prefix
    return hex_str.zfill(2)


@functools.cache
def get_dma_header_name(index: int):
    return f"anim_{num_to_padded_hex(index)}"


def get_dma_anim_name(header_indices: list[int]):
    return f'anim_{"_".join([f"{num_to_padded_hex(num)}" for num in header_indices])}'


@functools.cache
def action_name_to_anim_name(action_name: str) -> str:
    return re.sub(r"^_(\d+_)+(?=\w)", "", toAlnum(action_name), flags=re.MULTILINE)


@functools.cache
def anim_name_to_enum_name(anim_name: str) -> str:
    enum_name = anim_name.upper()
    enum_name: str = re.sub(r"(?<=_)_|_$", "", toAlnum(enum_name), flags=re.MULTILINE)
    if anim_name == enum_name:
        enum_name = f"{enum_name}_ENUM"
    return enum_name


def duplicate_name(name: str, existing_names: dict[str, int]) -> str:
    """Updates existing_names"""
    current_num = existing_names.get(name)
    if current_num is None:
        existing_names[name] = 0
    elif name != "":
        current_num += 1
        existing_names[name] = current_num
        return f"{name}_{current_num}"
    return name


def table_name_to_enum(name: str):
    return name.title().replace("_", "")


def get_action_props(action: Action) -> "SM64_ActionAnimProperty":
    return action.fast64.sm64.animation


def get_scene_anim_props(context: Context) -> "SM64_AnimProperties":
    return context.scene.fast64.sm64.animation


def get_anim_props(context: Context) -> "SM64_ArmatureAnimProperties":
    obj = get_anim_obj(context)
    assert obj is not None
    return obj.fast64.sm64.animation


def get_anim_actor_name(context: Context) -> str | None:
    sm64_props = context.scene.fast64.sm64
    if sm64_props.export_type == "C" and sm64_props.combined_export.export_anim:
        return toAlnum(sm64_props.combined_export.obj_name_anim)
    elif context.object:
        return sm64_props.combined_export.filter_name(toAlnum(context.object.name), True)
    else:
        return None


def dma_structure_context(context: Context) -> bool:
    if get_anim_obj(context) is None:
        return False
    return get_anim_props(context).is_dma


def check_for_headers_in_table(
    headers: list[Union["SM64_AnimHeaderProperties", tuple[Action, int]]],
    table: list["SM64_AnimTableElementProperties"],
    dma: bool,
) -> bool:
    can_reference = not dma

    remaining_headers = set(headers)
    for element in table:
        for header in list(remaining_headers):
            if isinstance(header, tuple):
                action, specific_variant = header
                if (
                    element.get_action(can_reference) == action
                    and element.get_header(can_reference) is not None
                    and element.variant == specific_variant
                ):
                    remaining_headers.remove(header)
            else:
                if element.get_action(can_reference) is not None and element.get_header(can_reference) == header:
                    remaining_headers.remove(header)
            if len(remaining_headers) == 0:
                return True
    return len(remaining_headers) == 0


def check_for_action_in_table(
    action: "SM64_ActionAnimProperty", table_elements: list["SM64_AnimTableElementProperties"], dma: bool
) -> bool:
    return any(element.get_action(not dma) == action for element in table_elements)


def get_active_diff_slot(context: Context, action: Action = None):
    obj = get_anim_obj(context)
    if obj is None or action is None:
        return None
    if obj.animation_data is None or obj.animation_data.action_slot is None:
        return None
    if obj.animation_data.action != action:
        return None
    return obj.animation_data.action_slot
