from typing import TYPE_CHECKING, Optional
from pathlib import Path
import os
import typing
import numpy as np

import bpy
from bpy.types import Object, Action, PoseBone, Context
from bpy.path import abspath
from mathutils import Euler, Quaternion

from ...utility import (
    PluginError,
    bytesToHex,
    encodeSegmentedAddr,
    decodeSegmentedAddr,
    get64bitAlignedAddr,
    getPathAndLevel,
    getExportDir,
    intToHex,
    applyBasicTweaks,
    toAlnum,
    directory_path_checks,
)
from ...utility_anim import get_fcurves, stashActionInArmature, get_slots

from ..sm64_constants import BEHAVIOR_COMMANDS, BEHAVIOR_EXITS, defaultExtendSegment4, level_pointers
from ..sm64_utility import (
    ModifyFoundDescriptor,
    find_descriptor_in_text,
    get_comment_map,
    to_include_descriptor,
    write_includes,
    update_actor_includes,
    int_from_str,
    write_or_delete_if_found,
)
from ..sm64_classes import BinaryExporter, RomReader, InsertableBinaryData
from ..sm64_level_parser import parseLevelAtPointer
from ..sm64_rom_tweaks import ExtendBank0x04

from .classes import (
    SM64_Anim,
    SM64_AnimHeader,
    SM64_AnimData,
    SM64_AnimPair,
    SM64_AnimTable,
    SM64_AnimTableElement,
)
from .importing import import_enums, import_tables, update_table_with_table_enum
from .utility import (
    get_anim_owners,
    get_anim_actor_name,
    anim_name_to_enum_name,
    get_selected_action,
    get_action_props,
    duplicate_name,
)
from .constants import HEADER_SIZE

if TYPE_CHECKING:
    from .properties import (
        SM64_ActionAnimProperty,
        SM64_AnimHeaderProperties,
        SM64_ArmatureAnimProperties,
        SM64_AnimTableElementProperties,
    )
    from ..settings.properties import SM64_Properties
    from ..sm64_objects import SM64_CombinedObjectProperties


def trim_duplicates_vectorized(arr2d: np.ndarray) -> list:
    """
    Similar to the old removeTrailingFrames(), but using numpy vectorization.
    Remove trailing duplicate elements along the last axis of a 2D array.
    One dimensional example of this in SM64_AnimPair.clean_frames
    """
    # Get the last element of each sub-array along the last axis
    last_elements = arr2d[:, -1]
    mask = arr2d != last_elements[:, None]
    #  Reverse the order, find the last element with the same value
    trim_indices = np.argmax(mask[:, ::-1], axis=1)
    # return list(arr2d)  # uncomment to test large sizes
    return [
        sub_array if index == 1 else sub_array[: 1 if index == 0 else (-index + 1)]
        for sub_array, index in zip(arr2d, trim_indices)
    ]


def get_entire_fcurve_data(
    action: Action,
    anim_owner: PoseBone | Object,
    prop: str,
    max_frame: int,
    values: np.ndarray[tuple[typing.Any, typing.Any], np.dtype[np.float32]],
):
    data_path = anim_owner.path_from_id(prop)

    default_values = list(getattr(anim_owner, prop))
    populated = [False] * len(default_values)

    fcurves = get_fcurves(action, get_action_props(action).get_slot(action))
    for fcurve in fcurves:
        if fcurve.data_path == data_path:
            array_index = fcurve.array_index
            for frame in range(max_frame):
                values[array_index, frame] = fcurve.evaluate(frame)
            populated[array_index] = True

    for i, is_populated in enumerate(populated):
        if not is_populated:
            values[i] = np.full(values[i].size, default_values[i])

    return values


def read_quick(actions, max_frames, anim_owners, trans_values, rot_values):
    def to_xyz(row):
        euler = Euler(row, mode)
        return [euler.x, euler.y, euler.z]

    for action, max_frame, action_trans, action_rot in zip(actions, max_frames, trans_values, rot_values):
        quats = np.empty((4, max_frame), dtype=np.float32)

        get_entire_fcurve_data(action, anim_owners[0], "location", max_frame, action_trans)

        for bone_index, anim_owner in enumerate(anim_owners):
            mode = anim_owner.rotation_mode
            prop = {"QUATERNION": "rotation_quaternion", "AXIS_ANGLE": "rotation_axis_angle"}.get(
                mode, "rotation_euler"
            )

            index = bone_index * 3
            if mode == "QUATERNION":
                get_entire_fcurve_data(action, anim_owner, prop, max_frame, quats)
                action_rot[index : index + 3] = np.apply_along_axis(
                    lambda row: Quaternion(row).to_euler(), 1, quats.T
                ).T
            elif mode == "AXIS_ANGLE":
                get_entire_fcurve_data(action, anim_owner, prop, max_frame, quats)
                action_rot[index : index + 3] = np.apply_along_axis(
                    lambda row: list(Quaternion(row[1:], row[0]).to_euler()), 1, quats.T
                ).T
            else:
                get_entire_fcurve_data(action, anim_owner, prop, max_frame, action_rot[index : index + 3])
                if mode != "XYZ":
                    action_rot[index : index + 3] = np.apply_along_axis(to_xyz, -1, action_rot[index : index + 3].T).T


def read_full(actions, max_frames, anim_owners, trans_values, rot_values, obj, is_owner_obj):
    pre_export_frame = bpy.context.scene.frame_current
    pre_export_action = obj.animation_data.action
    pre_export_slot = None
    if bpy.app.version >= (5, 0, 0):
        pre_export_slot = obj.animation_data.action_slot
    was_playing = bpy.context.screen.is_animation_playing

    try:
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()  # if an animation is being played, stop it
        for action, action_trans, action_rot, max_frame in zip(actions, trans_values, rot_values, max_frames):
            print(f'Reading animation data from action "{action.name}".')
            obj.animation_data.action = action
            if bpy.app.version >= (5, 0, 0):
                slot = get_action_props(action).get_slot(action)
                if slot is None:
                    raise PluginError(f'No action slot found for action "{action.name}"')
                obj.animation_data.action_slot = slot
            for frame in range(max_frame):
                bpy.context.scene.frame_set(frame)

                for bone_index, anim_owner in enumerate(anim_owners):
                    if is_owner_obj:
                        local_matrix = anim_owner.matrix_local
                    else:
                        local_matrix = obj.convert_space(
                            pose_bone=anim_owner, matrix=anim_owner.matrix, from_space="POSE", to_space="LOCAL"
                        )
                    if bone_index == 0:
                        action_trans[0:3, frame] = list(local_matrix.to_translation())
                    index = bone_index * 3
                    action_rot[index : index + 3, frame] = list(local_matrix.to_euler())
    finally:
        obj.animation_data.action = pre_export_action
        if bpy.app.version >= (5, 0, 0):
            obj.animation_data.action_slot = pre_export_slot
        bpy.context.scene.frame_set(pre_export_frame)
        if was_playing != bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()


def get_animation_pairs(
    sm64_scale: float, actions: list[Action], obj: Object, quick_read=False
) -> dict[Action, list[SM64_AnimPair]]:
    anim_owners = get_anim_owners(obj)
    is_owner_obj = isinstance(obj.type == "MESH", Object)

    if len(anim_owners) == 0:
        raise PluginError(f'No animation bones in armature "{obj.name}"')

    if len(actions) < 1:
        return {}

    max_frames = [get_action_props(action).get_max_frame(action) for action in actions]
    trans_values = [np.zeros((3, max_frame), dtype=np.float32) for max_frame in max_frames]
    rot_values = [np.zeros((len(anim_owners) * 3, max_frame), dtype=np.float32) for max_frame in max_frames]

    if quick_read:
        read_quick(actions, max_frames, anim_owners, trans_values, rot_values)
    else:
        read_full(actions, max_frames, anim_owners, trans_values, rot_values, obj, is_owner_obj)

    action_pairs = {}
    for action, action_trans, action_rot in zip(actions, trans_values, rot_values):
        action_trans = trim_duplicates_vectorized(np.round(action_trans * sm64_scale).astype(np.int16))
        action_rot = trim_duplicates_vectorized(np.round(np.degrees(action_rot) * (2**16 / 360.0)).astype(np.int16))

        pairs = [SM64_AnimPair(values) for values in action_trans]
        pairs.extend([SM64_AnimPair(values) for values in action_rot])
        action_pairs[action] = pairs

    return action_pairs


def to_header_class(
    header_props: "SM64_AnimHeaderProperties",
    bone_count: int,
    data: SM64_AnimData | None,
    action: Action,
    values_reference: int | str,
    indice_reference: int | str,
    dma: bool,
    export_type: str,
    table_index: Optional[int] = None,
    actor_name="mario",
    gen_enums=False,
    file_name="anim_00.inc.c",
):
    header = SM64_AnimHeader()
    header.reference = header_props.get_name(actor_name, action, dma)
    if gen_enums:
        header.enum_name = header_props.get_enum(actor_name, action)

    header.flags = header_props.get_flags(not (export_type.endswith("Binary") or dma))
    header.trans_divisor = header_props.trans_divisor
    header.start_frame, header.loop_start, header.loop_end = header_props.get_loop_points(action)
    header.values_reference = values_reference
    header.indice_reference = indice_reference
    header.bone_count = bone_count
    header.table_index = header_props.table_index if table_index is None else table_index
    header.file_name = file_name
    header.data = data
    return header


def to_data_class(pairs: list[SM64_AnimPair], data_name="anim_00", file_name: str = "anim_00.inc.c"):
    return SM64_AnimData(pairs, f"{data_name}_indices", f"{data_name}_values", file_name, file_name)


def to_animation_class(
    action_props: "SM64_ActionAnimProperty",
    action: Action,
    obj: Object,
    blender_to_sm64_scale: float,
    quick_read: bool,
    export_type: str,
    dma: bool,
    actor_name="mario",
    gen_enums=False,
) -> SM64_Anim:
    can_reference = not dma
    animation = SM64_Anim()
    animation.file_name = action_props.get_file_name(action, export_type, dma)

    if can_reference and action_props.reference_tables:
        if export_type.endswith("Binary"):
            values_reference, indice_reference = int_from_str(action_props.values_address), int(
                action_props.indices_address, 0
            )
        else:
            values_reference, indice_reference = action_props.values_table, action_props.indices_table
    else:
        pairs = get_animation_pairs(blender_to_sm64_scale, [action], obj, quick_read)[action]
        animation.data = to_data_class(pairs, action_props.get_name(action, dma), animation.file_name)
        values_reference = animation.data.values_reference
        indice_reference = animation.data.indice_reference
    bone_count = len(get_anim_owners(obj))
    for header_props in action_props.headers:
        animation.headers.append(
            to_header_class(
                header_props=header_props,
                bone_count=bone_count,
                data=animation.data,
                action=action,
                values_reference=values_reference,
                indice_reference=indice_reference,
                dma=dma,
                export_type=export_type,
                actor_name=actor_name,
                gen_enums=gen_enums,
                file_name=animation.file_name,
                table_index=None,
            )
        )

    return animation


def to_table_element_class(
    element_props: "SM64_AnimTableElementProperties",
    header_dict: dict["SM64_AnimHeaderProperties", SM64_AnimHeader],
    data_dict: dict[Action, SM64_AnimData],
    action_pairs: dict[Action, list[SM64_AnimPair]],
    bone_count: int,
    table_index: int,
    dma: bool,
    export_type: str,
    actor_name="mario",
    gen_enums=False,
    prev_enums: dict[str, int] | None = None,
):
    prev_enums = prev_enums or {}
    use_addresses, can_reference = export_type.endswith("Binary"), not dma
    element = SM64_AnimTableElement()

    enum = None
    if gen_enums:
        enum = element_props.get_enum(can_reference, actor_name, prev_enums)
        element.enum_name = enum

    if can_reference and element_props.reference:
        reference = int_from_str(element_props.header_address) if use_addresses else element_props.header_name
        element.reference = reference
        if reference == "":
            raise PluginError("Header is not set.")
        if enum == "":
            raise PluginError("Enum name is not set.")
        return element

    # Not reference
    action, header_props = element_props.get_action_header(can_reference)
    if not action:
        raise PluginError("Action is not set.")
    if not header_props:
        raise PluginError("Header is not set.")
    if enum == "":
        raise PluginError("Enum name is not set.")

    action_props = get_action_props(action)
    if can_reference and action_props.reference_tables:
        data = None
        if use_addresses:
            values_reference, indice_reference = (
                int_from_str(action_props.values_address),
                int_from_str(action_props.indices_address),
            )
        else:
            values_reference, indice_reference = action_props.values_table, action_props.indices_table
    else:
        if action in action_pairs and action not in data_dict:
            data_dict[action] = to_data_class(
                action_pairs[action],
                action_props.get_name(action, dma),
                action_props.get_file_name(action, export_type, dma),
            )
        data = data_dict[action]
        values_reference, indice_reference = data.values_reference, data.indice_reference

    if header_props not in header_dict:
        header_dict[header_props] = to_header_class(
            header_props=header_props,
            bone_count=bone_count,
            data=data,
            action=action,
            values_reference=values_reference,
            indice_reference=indice_reference,
            dma=dma,
            export_type=export_type,
            table_index=table_index,
            actor_name=actor_name,
            gen_enums=gen_enums,
            file_name=action_props.get_file_name(action, export_type),
        )

    element.header = header_dict[header_props]
    element.reference = element.header.reference
    return element


def to_table_class(
    anim_props: "SM64_ArmatureAnimProperties",
    obj: Object,
    blender_to_sm64_scale: float,
    quick_read: bool,
    dma: bool,
    export_type: str,
    actor_name="mario",
    gen_enums=False,
) -> SM64_AnimTable:
    can_reference = not dma
    table = SM64_AnimTable(
        anim_props.get_table_name(actor_name),
        anim_props.get_enum_name(actor_name),
        anim_props.get_enum_end(actor_name),
        anim_props.get_table_file_name(actor_name, export_type),
        values_reference=toAlnum(f"anim_{actor_name}_values"),
    )

    header_dict: dict[SM64_AnimHeaderProperties, SM64_AnimHeader] = {}

    bone_count = len(get_anim_owners(obj))
    action_pairs = get_animation_pairs(
        blender_to_sm64_scale,
        [action for action in anim_props.actions if not (can_reference and get_action_props(action).reference_tables)],
        obj,
        quick_read,
    )
    data_dict = {}

    prev_enums = {}
    element_props: SM64_AnimTableElementProperties
    for i, element_props in enumerate(anim_props.elements):
        try:
            table.elements.append(
                to_table_element_class(
                    element_props=element_props,
                    header_dict=header_dict,
                    data_dict=data_dict,
                    action_pairs=action_pairs,
                    bone_count=bone_count,
                    table_index=i,
                    dma=dma,
                    export_type=export_type,
                    actor_name=actor_name,
                    gen_enums=gen_enums,
                    prev_enums=prev_enums,
                )
            )
        except Exception as exc:
            raise PluginError(f"Table element {i}: {exc}") from exc
    if not dma and anim_props.null_delimiter:
        table.elements.append(SM64_AnimTableElement(enum_name=table.enum_list_delimiter))
    return table


def update_includes(
    combined_props: "SM64_CombinedObjectProperties",
    header_dir: Path,
    actor_name,
    update_table: bool,
):
    data_includes = [Path("anims/data.inc.c")]
    header_includes = []
    if update_table:
        data_includes.append(Path("anims/table.inc.c"))
        header_includes.append(Path("anim_header.h"))
    update_actor_includes(
        combined_props.export_header_type,
        combined_props.actor_group_name,
        header_dir,
        actor_name,
        combined_props.export_level_name,
        data_includes,
        header_includes,
    )


def update_anim_header(path: Path, table_name: str, gen_enums: bool, override_files: bool):
    to_add = [
        ModifyFoundDescriptor(
            f"extern const struct Animation *const {table_name}[];",
            rf"extern\h*const\h*struct\h*Animation\h?\*const\h*{table_name}\[.*?\]\h*?;",
        )
    ]
    if gen_enums:
        to_add.append(to_include_descriptor(Path("anims/table_enum.h")))
    if write_or_delete_if_found(path, to_add, create_new=override_files):
        print(f"Updated animation header {path}")


def update_enum_file(path: Path, override_files: bool, table: SM64_AnimTable):
    text, comment_map = "", []
    existing_file = path.exists() and not override_files
    if existing_file:
        text, comment_map = get_comment_map(path.read_text())

    if table.enum_list_start == -1 and table.enum_list_end == -1:  # create new enum list
        if text and text[-1] not in {"\n", "\r"}:
            text += "\n"
        table.enum_list_start = len(text)
        text += f"enum {table.enum_list_reference} {{\n"
        table.enum_list_end = len(text)
        text += "};\n"

    content = text[table.enum_list_start : table.enum_list_end]
    for i, element in enumerate(table.elements):
        if element.enum_start == -1 or element.enum_end == -1:
            content += f"\t{element.enum_c},\n"
            if existing_file:
                print(f"Added enum list entrie {element.enum_c}.")
            continue

        old_text = content[element.enum_start : element.enum_end]
        if old_text != element.enum_c:
            content = content[: element.enum_start] + element.enum_c + content[element.enum_end :]
            if existing_file:
                print(f'Replaced "{old_text}" with "{element.enum_c}".')
        # acccount for changed size
        size_increase = len(element.enum_c) - len(old_text)
        for next_element in table.elements[i + 1 :]:
            if next_element.enum_start != -1 and next_element.enum_end != -1:
                next_element.enum_start += size_increase
                next_element.enum_end += size_increase
    if not existing_file:
        print(f"Creating enum list file at {path}.")
    text = text[: table.enum_list_start] + content + text[table.enum_list_end :]
    path.write_text(text)


def update_table_file(
    table: SM64_AnimTable,
    table_path: Path,
    add_null_delimiter: bool,
    override_files: bool,
    gen_enums: bool,
    designated: bool,
    enum_list_path: Path,
):
    assert isinstance(table.reference, str) and table.reference, "Invalid table reference"

    text, enum_text = "", ""
    existing_file = table_path.exists() and not override_files
    if existing_file:
        text = table_path.read_text()
    comment_less, comment_map = get_comment_map(text)

    # add include if not already there
    descriptor = to_include_descriptor(Path("table_enum.h"))
    if gen_enums and len(find_descriptor_in_text(descriptor, comment_less, comment_map)) == 0:
        text = '#include "table_enum.h"\n' + text
        comment_less, comment_map = get_comment_map(text)

    # First, find existing tables
    tables = import_tables(comment_less, table_path, comment_map, table.reference)
    enum_tables = []
    if gen_enums:
        assert isinstance(table.enum_list_reference, str) and table.enum_list_reference
        enum_text, enum_comment_less, enum_comment_map = "", "", []
        if enum_list_path.exists() and not override_files:
            enum_text = enum_list_path.read_text()
            enum_comment_less, enum_comment_map = get_comment_map(enum_text)
        enum_tables = import_enums(enum_comment_less, enum_list_path, enum_comment_map, table.enum_list_reference)
        if len(enum_tables) > 1:
            raise PluginError(f'Duplicate enum list "{table.enum_list_reference}"')

    if len(tables) > 1:
        raise PluginError(f'Duplicate animation table "{table.reference}"')
    elif len(tables) == 1:
        existing_table = tables[0]
        if gen_enums:
            if enum_tables:  # apply enum table names to existing unset enums
                update_table_with_table_enum(existing_table, enum_tables[0])
                table.enum_list_reference, table.enum_list_start, table.enum_list_end = (
                    existing_table.enum_list_reference,
                    existing_table.enum_list_start,
                    existing_table.enum_list_end,
                )

            # Figure out enums on existing enum-less elements
            prev_enums = {name: 0 for name in existing_table.enum_names}
            for i, element in enumerate(existing_table.elements):
                if element.enum_name:
                    continue
                if not element.reference:
                    if i == len(existing_table.elements) - 1:
                        element.enum_name = duplicate_name(table.enum_list_delimiter, prev_enums)
                    else:
                        element.enum_name = duplicate_name(
                            anim_name_to_enum_name(f"{existing_table.reference}_NULL"), prev_enums
                        )
                    continue
                element.enum_name = duplicate_name(
                    next(
                        (enum for name, enum in zip(*table.names) if enum and name == element.reference),
                        anim_name_to_enum_name(element.reference),
                    ),
                    prev_enums,
                )

        new_elements = existing_table.elements.copy()
        has_null_delimiter = existing_table.has_null_delimiter
        for element in table.elements:
            if element.c_name in existing_table.header_names and (
                not gen_enums or element.enum_name in existing_table.enum_names
            ):
                continue
            if has_null_delimiter:
                new_elements[-1].reference = element.reference
                new_elements[-1].enum_name = element.enum_name
                has_null_delimiter = False
            else:
                new_elements.append(element)
        table.elements = new_elements
        table.start, table.end = (existing_table.start, existing_table.end)
    else:  # create new table
        if text and text[-1] not in {"\n", "\r"}:
            text += "\n"
        table.start = len(text)
        text += f"const struct Animation *const {table.reference}[] = {{\n"
        table.end = len(text)
        text += "};\n"

    if add_null_delimiter and not table.has_null_delimiter:  # add null delimiter if not present or replaced
        table.elements.append(SM64_AnimTableElement(enum_name=table.enum_list_delimiter))

    if gen_enums:
        update_enum_file(enum_list_path, override_files, table)

    content = text[table.start : table.end]
    for i, element in enumerate(table.elements):
        element_text = element.to_c(designated and gen_enums)
        if element.reference_start == -1 or element.reference_end == -1:
            content += f"\t{element_text}\n"
            if existing_file:
                print(f"Added table entrie {element_text}.")
            continue

        # update existing region instead
        old_text = content[element.reference_start : element.reference_end]
        if old_text != element_text:
            content = content[: element.reference_start] + element_text + content[element.reference_end :]
            if existing_file:
                print(f'Replaced "{old_text}" with "{element_text}".')

        size_increase = len(element_text) - len(old_text)
        if size_increase == 0:
            continue
        for next_element in table.elements[i + 1 :]:  # acccount for changed size
            if next_element.reference_start != -1 and next_element.reference_end != -1:
                next_element.reference_start += size_increase
                next_element.reference_end += size_increase

    if not existing_file:
        print(f"Creating table file at {table_path}.")
    text = text[: table.start] + content + text[table.end :]
    table_path.write_text(text)


def update_data_file(path: Path, anim_file_names: list[str], override_files: bool = False):
    includes = [Path(file_name) for file_name in anim_file_names]
    if write_includes(path, includes, create_new=override_files):
        print(f"Updating animation data file includes at {path}")


def update_behaviour_binary(
    binary_exporter: BinaryExporter, address: int, table_address: bytes, beginning_animation: int
):
    load_set = False
    animate_set = False
    exited = False
    while not exited and not (load_set and animate_set):
        command_index = int.from_bytes(binary_exporter.read(1, address), "big")
        name, size = BEHAVIOR_COMMANDS[command_index]
        print(name, intToHex(address))
        if name in BEHAVIOR_EXITS:
            exited = True
        if name == "LOAD_ANIMATIONS":
            ptr_address = address + 4
            print(
                f"Found LOAD_ANIMATIONS at {intToHex(address)}, "
                f"replacing ptr {bytesToHex(binary_exporter.read(4, ptr_address))} "
                f"at {intToHex(ptr_address)} with {bytesToHex(table_address)}"
            )
            binary_exporter.write(table_address, ptr_address)
            load_set = True
        elif name == "ANIMATE":
            value_address = address + 1
            print(
                f"Found ANIMATE at {intToHex(address)}, "
                f"replacing value {int.from_bytes(binary_exporter.read(1, value_address), 'big')} "
                f"at {intToHex(value_address)} with {beginning_animation}"
            )
            binary_exporter.write(beginning_animation.to_bytes(1, "big"), value_address)
            animate_set = True
        address += 4 * size
    if exited:
        if not load_set:
            raise IndexError("Could not find LOAD_ANIMATIONS command")
        if not animate_set:
            print("Could not find ANIMATE command")


def export_animation_table_binary(
    binary_exporter: BinaryExporter,
    anim_props: "SM64_ArmatureAnimProperties",
    table: SM64_AnimTable,
    is_dma: bool,
    level_option: str,
    extend_bank_4: bool,
):
    if is_dma:
        data = table.to_binary_dma()
        binary_exporter.write_to_range(
            get64bitAlignedAddr(int_from_str(anim_props.dma_address)), int_from_str(anim_props.dma_end_address), data
        )
        return

    level_parsed = parseLevelAtPointer(binary_exporter.rom_file_output, level_pointers[level_option])
    segment_data = level_parsed.segmentData
    if extend_bank_4:
        ExtendBank0x04(binary_exporter.rom_file_output, segment_data, defaultExtendSegment4)

    address = get64bitAlignedAddr(int_from_str(anim_props.address))
    end_address = int_from_str(anim_props.end_address)

    if anim_props.write_data_seperately:  # Write the data and the table into seperate address range
        data_address = get64bitAlignedAddr(int_from_str(anim_props.data_address))
        data_end_address = int_from_str(anim_props.data_end_address)
        table_data, data = table.to_combined_binary(address, data_address, segment_data)[:2]
        binary_exporter.write_to_range(address, end_address, table_data)
        binary_exporter.write_to_range(data_address, data_end_address, data)
    else:  # Write table then the data in one address range
        table_data, data = table.to_combined_binary(address, -1, segment_data)[:2]
        binary_exporter.write_to_range(address, end_address, table_data + data)
    if anim_props.update_behavior:
        update_behaviour_binary(
            binary_exporter,
            decodeSegmentedAddr(anim_props.behavior_address.to_bytes(4, "big"), segment_data),
            encodeSegmentedAddr(address, segment_data),
            int_from_str(anim_props.beginning_animation),
        )


def export_animation_table_insertable(table: SM64_AnimTable, is_dma: bool, directory: Path):
    directory_path_checks(directory, "Empty directory path.")
    path = directory / table.file_name
    if is_dma:
        data = table.to_binary_dma()
        InsertableBinaryData("Animation DMA Table", data).write(path)
    else:
        table_data, data, ptrs = table.to_combined_binary()
        InsertableBinaryData("Animation Table", table_data + data, 0, ptrs).write(path)


def create_and_get_paths(
    anim_props: "SM64_ArmatureAnimProperties",
    combined_props: "SM64_CombinedObjectProperties",
    actor_name: str,
    decomp: Path,
):
    anim_directory = geo_directory = header_directory = None
    if anim_props.is_dma:
        if combined_props.export_header_type == "Custom":
            geo_directory = Path(abspath(combined_props.custom_export_path))
            anim_directory = Path(abspath(combined_props.custom_export_path), anim_props.dma_folder)
        else:
            anim_directory = Path(decomp, anim_props.dma_folder)
    else:
        export_path, level_name = getPathAndLevel(
            combined_props.is_actor_custom_export,
            combined_props.actor_custom_path,
            combined_props.export_level_name,
            combined_props.level_name,
        )
        header_directory, _tex_dir = getExportDir(
            combined_props.is_actor_custom_export,
            export_path,
            combined_props.export_header_type,
            level_name,
            texDir="",
            dirName=actor_name,
        )
        header_directory = Path(bpy.path.abspath(header_directory))
        geo_directory = header_directory / actor_name
        anim_directory = geo_directory / "anims"

    for path in (anim_directory, geo_directory, header_directory):
        if path is not None and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
    return (anim_directory, geo_directory, header_directory)


def export_animation_table_c(
    anim_props: "SM64_ArmatureAnimProperties",
    combined_props: "SM64_CombinedObjectProperties",
    table: SM64_AnimTable,
    decomp: Path,
    actor_name: str,
    designated: bool,
):
    if not combined_props.is_actor_custom_export:
        applyBasicTweaks(decomp)
    anim_directory, geo_directory, header_directory = create_and_get_paths(
        anim_props, combined_props, actor_name, decomp
    )

    print("Creating all animation C data")
    if anim_props.export_seperately or anim_props.is_dma:
        files_data = table.data_and_headers_to_c(anim_props.is_dma)
        print("Saving all generated data files")
        for file_name, file_data in files_data.items():
            (anim_directory / file_name).write_text(file_data)
            print(file_name)
        if not anim_props.is_dma:
            update_data_file(
                anim_directory / "data.inc.c",
                list(files_data.keys()),
                anim_props.override_files,
            )
    else:
        result = table.data_and_headers_to_c_combined()
        print("Saving generated data file")
        (anim_directory / "data.inc.c").write_text(result)
    print("All animation data files exported.")
    if anim_props.is_dma:  # Don´t create an actual table and or update includes for dma exports
        return
    assert geo_directory and header_directory and isinstance(table.reference, str)

    header_path = geo_directory / "anim_header.h"
    update_anim_header(header_path, table.reference, anim_props.gen_enums, anim_props.override_files)
    update_table_file(
        table=table,
        table_path=anim_directory / "table.inc.c",
        add_null_delimiter=anim_props.null_delimiter,
        gen_enums=anim_props.gen_enums,
        designated=designated,
        enum_list_path=anim_directory / "table_enum.h",
        override_files=anim_props.override_files,
    )
    update_includes(combined_props, header_directory, actor_name, True)


def export_animation_binary(
    binary_exporter: BinaryExporter,
    animation: SM64_Anim,
    action_props: "SM64_ActionAnimProperty",
    anim_props: "SM64_ArmatureAnimProperties",
    bone_count: int,
    level_option: str,
    extend_bank_4: bool,
):
    if anim_props.is_dma:
        dma_address = int_from_str(anim_props.dma_address)
        print("Reading DMA table from ROM")
        table = SM64_AnimTable().read_dma_binary(
            reader=RomReader(rom_file=binary_exporter.rom_file_output, start_address=dma_address),
            read_headers={},
            table_index=None,
            bone_count=bone_count,
        )
        empty_data = SM64_AnimData()
        for header in animation.headers:
            while header.table_index >= len(table.elements):
                table.elements.append(SM64_AnimTableElement(header=SM64_AnimHeader(data=empty_data)))
            table.elements[header.table_index] = SM64_AnimTableElement(header=header)
        print("Converting to binary data")
        data = table.to_binary_dma()
        binary_exporter.write_to_range(dma_address, int_from_str(anim_props.dma_end_address), data)
        return
    level_parsed = parseLevelAtPointer(binary_exporter.rom_file_output, level_pointers[level_option])
    segment_data = level_parsed.segmentData
    if extend_bank_4:
        ExtendBank0x04(binary_exporter.rom_file_output, segment_data, defaultExtendSegment4)

    animation_address = get64bitAlignedAddr(int_from_str(action_props.start_address))
    animation_end_address = int_from_str(action_props.end_address)

    data = animation.to_binary(animation_address, segment_data)[0]
    binary_exporter.write_to_range(
        animation_address,
        animation_end_address,
        data,
    )
    table_address = get64bitAlignedAddr(int_from_str(anim_props.address))
    table_end_address = int_from_str(anim_props.end_address)
    if anim_props.update_table:
        for i, header in enumerate(animation.headers):
            element_address = table_address + (4 * header.table_index)
            if element_address > table_end_address:
                raise PluginError(
                    f"Animation header {i + 1} sets table index {header.table_index} which is out of bounds, "
                    f"table is {table_end_address - table_address} bytes long, "
                    "update the table start/end addresses in the armature properties"
                )
            binary_exporter.seek(element_address)
            binary_exporter.write(encodeSegmentedAddr(animation_address + (i * HEADER_SIZE), segment_data))
    if anim_props.update_behavior:
        update_behaviour_binary(
            binary_exporter,
            decodeSegmentedAddr(anim_props.behavior_address.to_bytes(4, "big"), segment_data),
            encodeSegmentedAddr(table_address, segment_data),
            int_from_str(anim_props.beginning_animation),
        )


def export_animation_insertable(animation: SM64_Anim, is_dma: bool, directory: Path):
    data, ptrs = animation.to_binary(is_dma)
    InsertableBinaryData("Animation", data, 0, ptrs).write(directory / animation.file_name)


def export_animation_c(
    animation: SM64_Anim,
    anim_props: "SM64_ArmatureAnimProperties",
    combined_props: "SM64_CombinedObjectProperties",
    decomp: Path,
    actor_name: str,
    designated: bool,
):
    if not combined_props.is_actor_custom_export:
        applyBasicTweaks(decomp)
    anim_directory, geo_directory, header_directory = create_and_get_paths(
        anim_props, combined_props, actor_name, decomp
    )

    (anim_directory / animation.file_name).write_text(animation.to_c(anim_props.is_dma))

    if anim_props.is_dma:  # Don´t create an actual table and don´t update includes for dma exports
        return

    table_name = anim_props.get_table_name(actor_name)

    if anim_props.update_table:
        update_anim_header(geo_directory / "anim_header.h", table_name, anim_props.gen_enums, False)
        update_table_file(
            table=SM64_AnimTable(
                table_name,
                enum_list_reference=anim_props.get_enum_name(actor_name),
                enum_list_delimiter=anim_props.get_enum_end(actor_name),
                elements=[
                    SM64_AnimTableElement(header.reference, header, header.enum_name) for header in animation.headers
                ],
            ),
            table_path=anim_directory / "table.inc.c",
            add_null_delimiter=anim_props.null_delimiter,
            gen_enums=anim_props.gen_enums,
            designated=designated,
            enum_list_path=anim_directory / "table_enum.h",
            override_files=False,
        )
    update_data_file(anim_directory / "data.inc.c", [animation.file_name])
    update_includes(combined_props, header_directory, actor_name, anim_props.update_table)


def export_animation(context: Context, obj: Object):
    scene = context.scene
    sm64_props: SM64_Properties = scene.fast64.sm64
    combined_props: SM64_CombinedObjectProperties = sm64_props.combined_export
    anim_props: SM64_ArmatureAnimProperties = obj.fast64.sm64.animation
    actor_name: str = get_anim_actor_name(context)

    action = get_selected_action(obj)
    action_props = get_action_props(action)
    stashActionInArmature(obj, action)
    bone_count = len(get_anim_owners(obj))

    try:
        animation = to_animation_class(
            action_props=action_props,
            action=action,
            obj=obj,
            blender_to_sm64_scale=sm64_props.blender_to_sm64_scale,
            quick_read=combined_props.quick_anim_read,
            export_type=sm64_props.export_type,
            dma=anim_props.is_dma,
            actor_name=actor_name,
            gen_enums=not sm64_props.binary_export and anim_props.gen_enums,
        )
    except Exception as exc:
        raise PluginError(f"Failed to generate animation class. {exc}") from exc
    if sm64_props.export_type == "C":
        export_animation_c(
            animation, anim_props, combined_props, sm64_props.abs_decomp_path, actor_name, sm64_props.designated
        )
    elif sm64_props.export_type == "Insertable Binary":
        export_animation_insertable(animation, anim_props.is_dma, Path(abspath(combined_props.insertable_directory)))
    elif sm64_props.export_type == "Binary":
        with BinaryExporter(
            Path(abspath(sm64_props.export_rom)), Path(abspath(sm64_props.output_rom))
        ) as binary_exporter:
            export_animation_binary(
                binary_exporter,
                animation,
                action_props,
                anim_props,
                bone_count,
                combined_props.level_name,
                sm64_props.extend_bank_4,
            )
    else:
        raise NotImplementedError(f"Export type {sm64_props.export_type} is not implemented")


def export_animation_table(context: Context, obj: Object):
    bpy.ops.object.mode_set(mode="OBJECT")

    scene = context.scene
    sm64_props: SM64_Properties = scene.fast64.sm64
    combined_props: SM64_CombinedObjectProperties = sm64_props.combined_export
    anim_props: SM64_ArmatureAnimProperties = obj.fast64.sm64.animation
    actor_name: str = get_anim_actor_name(context)

    print("Stashing all actions in table")
    for action in anim_props.actions:
        stashActionInArmature(obj, action)

    if len(anim_props.elements) == 0:
        raise PluginError("Empty animation table")

    try:
        print("Reading table data from fast64")
        table = to_table_class(
            anim_props=anim_props,
            obj=obj,
            blender_to_sm64_scale=sm64_props.blender_to_sm64_scale,
            quick_read=combined_props.quick_anim_read,
            dma=anim_props.is_dma,
            export_type=sm64_props.export_type,
            actor_name=actor_name,
            gen_enums=not anim_props.is_dma and not sm64_props.binary_export and anim_props.gen_enums,
        )
    except Exception as exc:
        raise PluginError(f"Failed to generate table class. {exc}") from exc

    print("Exporting table data")
    if sm64_props.export_type == "C":
        export_animation_table_c(
            anim_props, combined_props, table, sm64_props.abs_decomp_path, actor_name, sm64_props.designated
        )
    elif sm64_props.export_type == "Insertable Binary":
        export_animation_table_insertable(table, anim_props.is_dma, Path(abspath(combined_props.insertable_directory)))
    elif sm64_props.export_type == "Binary":
        with BinaryExporter(
            Path(abspath(sm64_props.export_rom)), Path(abspath(sm64_props.output_rom))
        ) as binary_exporter:
            export_animation_table_binary(
                binary_exporter,
                anim_props,
                table,
                anim_props.is_dma,
                combined_props.level_name,
                sm64_props.extend_bank_4,
            )
    else:
        raise NotImplementedError(f"Export type {sm64_props.export_type} is not implemented")
