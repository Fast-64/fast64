from typing import TYPE_CHECKING, Optional
from pathlib import Path
import dataclasses
import functools
import os
import re
import numpy as np

import bpy
from bpy.path import abspath
from bpy.types import Object, Action, Context, PoseBone
from mathutils import Quaternion

from ...f3d.f3d_parser import math_eval
from ...utility import PluginError, decodeSegmentedAddr, filepath_checks, path_checks, intToHex
from ...utility_anim import create_basic_action, get_fcurves, create_new_fcurve

from ..sm64_constants import AnimInfo, level_pointers
from ..sm64_level_parser import parseLevelAtPointer
from ..sm64_utility import CommentMatch, get_comment_map, adjust_start_end, import_rom_checks
from ..sm64_classes import RomReader

from .utility import (
    animation_operator_checks,
    get_action_props,
    get_anim_owners,
    get_scene_anim_props,
    get_anim_actor_name,
    anim_name_to_enum_name,
    table_name_to_enum,
)
from .classes import (
    SM64_Anim,
    CArrayDeclaration,
    SM64_AnimHeader,
    SM64_AnimTable,
    SM64_AnimTableElement,
)
from .constants import ACTOR_PRESET_INFO, TABLE_ENUM_LIST_PATTERN, TABLE_ENUM_PATTERN, TABLE_PATTERN

if TYPE_CHECKING:
    if bpy.app.version >= (5, 0, 0):
        from bpy.types import ActionSlot

    from .properties import (
        SM64_AnimImportProperties,
        SM64_ArmatureAnimProperties,
        SM64_AnimHeaderProperties,
        SM64_ActionAnimProperty,
        SM64_AnimTableElementProperties,
    )
    from ..settings.properties import SM64_Properties


def get_preset_anim_name_list(preset_name: str):
    assert preset_name in ACTOR_PRESET_INFO, "Selected preset not in actor presets"
    preset = ACTOR_PRESET_INFO[preset_name]
    assert preset.animation is not None and isinstance(
        preset.animation, AnimInfo
    ), "Selected preset's actor has not animation information"
    return preset.animation.names


def flip_euler(euler: np.ndarray) -> np.ndarray:
    euler = euler.copy()
    euler[1] = -euler[1]
    euler += np.pi
    return euler


def naive_flip_diff(a1: np.ndarray, a2: np.ndarray) -> np.ndarray:
    diff = a1 - a2
    mask = np.abs(diff) > np.pi
    return a2 + mask * np.sign(diff) * 2 * np.pi


@dataclasses.dataclass
class FramesHolder:
    frames: np.ndarray = dataclasses.field(default_factory=list)

    def populate_action(self, action: Action, action_slot: "ActionSlot", pose_bone: PoseBone, path: str):
        fcurves = get_fcurves(action, action_slot)
        for index in range(3):
            data_path = pose_bone.path_from_id(path)
            f_curve = create_new_fcurve(fcurves, data_path, index=index, action_group=pose_bone.name)
            for time, frame in enumerate(self.frames):
                f_curve.keyframe_points.insert(time, frame[index], options={"FAST"})


def euler_to_quaternion(euler_angles: np.ndarray):
    """
    Fast vectorized euler to quaternion function, euler_angles is an array of shape (-1, 3)
    """
    phi = euler_angles[:, 0]
    theta = euler_angles[:, 1]
    psi = euler_angles[:, 2]

    half_phi = phi / 2.0
    half_theta = theta / 2.0
    half_psi = psi / 2.0

    cos_half_phi = np.cos(half_phi)
    sin_half_phi = np.sin(half_phi)
    cos_half_theta = np.cos(half_theta)
    sin_half_theta = np.sin(half_theta)
    cos_half_psi = np.cos(half_psi)
    sin_half_psi = np.sin(half_psi)

    q_w = cos_half_phi * cos_half_theta * cos_half_psi + sin_half_phi * sin_half_theta * sin_half_psi
    q_x = sin_half_phi * cos_half_theta * cos_half_psi - cos_half_phi * sin_half_theta * sin_half_psi
    q_y = cos_half_phi * sin_half_theta * cos_half_psi + sin_half_phi * cos_half_theta * sin_half_psi
    q_z = cos_half_phi * cos_half_theta * sin_half_psi - sin_half_phi * sin_half_theta * cos_half_psi

    quaternions = np.vstack((q_w, q_x, q_y, q_z)).T  # shape (-1, 4)
    return quaternions


@dataclasses.dataclass
class RotationFramesHolder(FramesHolder):
    @property
    def quaternion(self):
        return euler_to_quaternion(self.frames)  # We make this code path as optiomal as it can be

    def get_euler(self, order: str):
        if order == "XYZ":
            return self.frames
        return [Quaternion(x).to_euler(order) for x in self.quaternion]

    @property
    def axis_angle(self):
        result = []
        for x in self.quaternion:
            x = Quaternion(x).to_axis_angle()
            result.append([x[1]] + list(x[0]))
        return result

    def populate_action(self, action: Action, action_slot: "ActionSlot", pose_bone: PoseBone, path: str = ""):
        rotation_mode = pose_bone.rotation_mode
        rotation_mode_name = {
            "QUATERNION": "rotation_quaternion",
            "AXIS_ANGLE": "rotation_axis_angle",
        }.get(rotation_mode, "rotation_euler")
        data_path = pose_bone.path_from_id(rotation_mode_name)

        size = 4
        if rotation_mode == "QUATERNION":
            rotations = self.quaternion
        elif rotation_mode == "AXIS_ANGLE":
            rotations = self.axis_angle
        else:
            rotations = self.get_euler(rotation_mode)
            size = 3
        fcurves = get_fcurves(action, action_slot)
        for index in range(size):
            f_curve = create_new_fcurve(fcurves, data_path, index=index, action_group=pose_bone.name)
            for frame, rotation in enumerate(rotations):
                f_curve.keyframe_points.insert(frame, rotation[index], options={"FAST"})


@dataclasses.dataclass
class IntermidiateAnimationBone:
    translation: FramesHolder = dataclasses.field(default_factory=FramesHolder)
    rotation: RotationFramesHolder = dataclasses.field(default_factory=RotationFramesHolder)

    def read_pairs(self, pairs: list["SM64_AnimPair"]):
        pair_count = len(pairs)
        max_length = max(len(pair.values) for pair in pairs)
        result = np.empty((max_length, pair_count), dtype=np.int16)

        for i, pair in enumerate(pairs):
            current_length = len(pair.values)
            result[:current_length, i] = pair.values
            result[current_length:, i] = pair.values[-1]
        return result

    def read_translation(self, pairs: list["SM64_AnimPair"], scale: float):
        self.translation.frames = self.read_pairs(pairs) / scale

    def continuity_filter(self, frames: np.ndarray) -> np.ndarray:
        if len(frames) <= 1:
            return frames

        # There is no way to fully vectorize this function
        prev = frames[0]
        for frame, euler in enumerate(frames):
            euler = naive_flip_diff(prev, euler)
            flipped_euler = naive_flip_diff(prev, flip_euler(euler))
            if np.all((prev - flipped_euler) ** 2 < (prev - euler) ** 2):
                euler = flipped_euler
            frames[frame] = prev = euler

        return frames

    def read_rotation(self, pairs: list["SM64_AnimPair"], continuity_filter: bool):
        frames = self.read_pairs(pairs).astype(np.uint16).astype(np.float32)
        frames *= 360.0 / (2**16)
        frames = np.radians(frames)
        if continuity_filter:
            frames = self.continuity_filter(frames)
        self.rotation.frames = frames

    def populate_action(self, action: Action, action_slot: "ActionSlot", pose_bone: PoseBone):
        self.translation.populate_action(action, action_slot, pose_bone, "location")
        self.rotation.populate_action(action, action_slot, pose_bone, "")


def from_header_class(
    header_props: "SM64_AnimHeaderProperties",
    header: SM64_AnimHeader,
    action: Action,
    actor_name: str,
    use_custom_name: bool,
):
    if isinstance(header.reference, str) and header.reference != header_props.get_name(actor_name, action):
        header_props.custom_name = header.reference
        if use_custom_name:
            header_props.use_custom_name = True
    if header.enum_name and header.enum_name != header_props.get_enum(actor_name, action):
        header_props.custom_enum = header.enum_name
        header_props.use_custom_enum = True

    correct_loop_points = header.start_frame, header.loop_start, header.loop_end
    header_props.start_frame, header_props.loop_start, header_props.loop_end = correct_loop_points
    if correct_loop_points != header_props.get_loop_points(action):  # check if auto loop points don´t match
        header_props.use_manual_loop = True

    header_props.trans_divisor = header.trans_divisor
    header_props.set_flags(header.flags)

    header_props.table_index = header.table_index


def from_anim_class(
    action_props: "SM64_ActionAnimProperty",
    action: Action,
    animation: SM64_Anim,
    actor_name: str,
    use_custom_name: bool,
    import_type: str,
):
    main_header = animation.headers[0]
    is_from_binary = import_type.endswith("Binary")

    if animation.action_name:
        action_name = animation.action_name
    elif main_header.file_name:
        action_name = main_header.file_name.removesuffix(".c").removesuffix(".inc")
    elif is_from_binary:
        action_name = intToHex(main_header.reference)

    action.name = action_name.removeprefix("anim_")
    print(f'Populating action "{action.name}" properties.')

    indice_reference, values_reference = main_header.indice_reference, main_header.values_reference
    if is_from_binary:
        action_props.indices_address, action_props.values_address = intToHex(indice_reference), intToHex(
            values_reference
        )
    else:
        action_props.indices_table, action_props.values_table = indice_reference, values_reference

    if animation.data:
        file_name = animation.data.indices_file_name
        action_props.custom_max_frame = max([1] + [len(x.values) for x in animation.data.pairs])
        if action_props.get_max_frame(action) != action_props.custom_max_frame:
            action_props.use_custom_max_frame = True
    else:
        file_name = main_header.file_name
        action_props.reference_tables = True
    if file_name:
        action_props.custom_file_name = file_name
        if use_custom_name and action_props.get_file_name(action, import_type) != action_props.custom_file_name:
            action_props.use_custom_file_name = True
    if is_from_binary:
        start_addresses = [x.reference for x in animation.headers]
        end_addresses = [x.end_address for x in animation.headers]
        if animation.data:
            start_addresses.append(animation.data.start_address)
            end_addresses.append(animation.data.end_address)

        action_props.start_address = intToHex(min(start_addresses))
        action_props.end_address = intToHex(max(end_addresses))

    print("Populating header properties.")
    for i, header in enumerate(animation.headers):
        if i:
            action_props.header_variants.add()
        header_props = action_props.headers[-1]
        header.action = action  # Used in table class to prop
        from_header_class(header_props, header, action, actor_name, use_custom_name)

    action_props.update_variant_numbers()


def from_table_element_class(
    element_props: "SM64_AnimTableElementProperties",
    element: SM64_AnimTableElement,
    use_custom_name: bool,
    actor_name: str,
    prev_enums: dict[str, int],
):
    if element.header:
        assert element.header.action
        element_props.set_variant(element.header.action, element.header.header_variant)
    else:
        element_props.reference = True

    if isinstance(element.reference, int):
        element_props.header_address = intToHex(element.reference)
    else:
        element_props.header_name = element.c_name
        element_props.header_address = intToHex(0)

    if element.enum_name:
        element_props.custom_enum = element.enum_name
        if use_custom_name and element.enum_name != element_props.get_enum(True, actor_name, prev_enums):
            element_props.use_custom_enum = True


def from_anim_table_class(
    anim_props: "SM64_ArmatureAnimProperties",
    table: SM64_AnimTable,
    clear_table: bool,
    use_custom_name: bool,
    actor_name: str,
):
    if clear_table:
        anim_props.elements.clear()
    anim_props.null_delimiter = table.has_null_delimiter

    prev_enums: dict[str, int] = {}
    for i, element in enumerate(table.elements):
        if anim_props.null_delimiter and i == len(table.elements) - 1:
            break
        anim_props.elements.add()
        from_table_element_class(anim_props.elements[-1], element, use_custom_name, actor_name, prev_enums)

    if isinstance(table.reference, int):  # Binary
        anim_props.dma_address = intToHex(table.reference)
        anim_props.dma_end_address = intToHex(table.end_address)
        anim_props.address = intToHex(table.reference)
        anim_props.end_address = intToHex(table.end_address)

        # Data
        start_addresses = []
        end_addresses = []
        for element in table.elements:
            if element.header and element.header.data:
                start_addresses.append(element.header.data.start_address)
                end_addresses.append(element.header.data.end_address)
        if start_addresses and end_addresses:
            anim_props.write_data_seperately = True
            anim_props.data_address = intToHex(min(start_addresses))
            anim_props.data_end_address = intToHex(max(end_addresses))
    elif isinstance(table.reference, str) and table.reference:  # C
        if use_custom_name:
            anim_props.custom_table_name = table.reference
            if anim_props.get_table_name(actor_name) != anim_props.custom_table_name:
                anim_props.use_custom_table_name = True


def animation_import_to_blender(
    obj: Object,
    blender_to_sm64_scale: float,
    anim_import: SM64_Anim,
    actor_name: str,
    use_custom_name: bool,
    import_type: str,
    force_quaternion: bool,
    continuity_filter: bool,
):
    action, action_slot = create_basic_action(obj)
    try:
        if anim_import.data:
            print("Converting pairs to intermidiate data.")
            bones = get_anim_owners(obj)
            bones_data: list[IntermidiateAnimationBone] = []
            pairs = anim_import.data.pairs
            for pair_num in range(3, len(pairs), 3):
                bone = IntermidiateAnimationBone()
                if pair_num == 3:
                    bone.read_translation(pairs[0:3], blender_to_sm64_scale)
                bone.read_rotation(pairs[pair_num : pair_num + 3], continuity_filter)
                bones_data.append(bone)
            print("Populating action keyframes.")
            for pose_bone, bone_data in zip(bones, bones_data):
                if force_quaternion:
                    pose_bone.rotation_mode = "QUATERNION"
                bone_data.populate_action(action, action_slot, pose_bone)

        from_anim_class(get_action_props(action), action, anim_import, actor_name, use_custom_name, import_type)
        return action
    except PluginError as exc:
        bpy.data.actions.remove(action)
        raise exc


def update_table_with_table_enum(table: SM64_AnimTable, enum_table: SM64_AnimTable):
    for element, enum_element in zip(table.elements, enum_table.elements):
        if element.enum_name:
            enum_element = next(
                (
                    other_enum_element
                    for other_enum_element in enum_table.elements
                    if element.enum_name == other_enum_element.enum_name
                ),
                enum_element,
            )
        element.enum_name = enum_element.enum_name
        element.enum_val = enum_element.enum_val
        element.enum_start = enum_element.enum_start
        element.enum_end = enum_element.enum_end
    table.enum_list_reference = enum_table.enum_list_reference
    table.enum_list_start = enum_table.enum_list_start
    table.enum_list_end = enum_table.enum_list_end


def import_enums(c_data: str, path: Path, comment_map: list[CommentMatch], specific_name=""):
    tables = []
    for list_match in re.finditer(TABLE_ENUM_LIST_PATTERN, c_data):
        name, content = list_match.group("name"), list_match.group("content")
        if name is None and content is None:  # comment
            continue
        if specific_name and name != specific_name:
            continue
        list_start, list_end = adjust_start_end(c_data.find(content, list_match.start()), list_match.end(), comment_map)
        content = c_data[list_start:list_end]
        table = SM64_AnimTable(
            file_name=path.name,
            enum_list_reference=name,
            enum_list_start=list_start,
            enum_list_end=list_end,
        )
        for element_match in re.finditer(TABLE_ENUM_PATTERN, content):
            name, num = (element_match.group("name"), element_match.group("num"))
            if name is None and num is None:  # comment
                continue
            enum_start, enum_end = adjust_start_end(
                list_start + element_match.start(), list_start + element_match.end(), comment_map
            )
            table.elements.append(
                SM64_AnimTableElement(
                    enum_name=name, enum_val=num, enum_start=enum_start - list_start, enum_end=enum_end - list_start
                )
            )
        tables.append(table)
    return tables


def import_tables(
    c_data: str,
    path: Path,
    comment_map: list[CommentMatch],
    specific_name="",
    header_decls: Optional[list[CArrayDeclaration]] = None,
    values_decls: Optional[list[CArrayDeclaration]] = None,
    indices_decls: Optional[list[CArrayDeclaration]] = None,
):
    read_headers = {}
    header_decls, values_decls, indices_decls = (
        header_decls or [],
        values_decls or [],
        indices_decls or [],
    )
    tables: list[SM64_AnimTable] = []
    for table_match in re.finditer(TABLE_PATTERN, c_data):
        table_elements = []
        name, content = table_match.group("name"), table_match.group("content")
        if name is None and content is None:  # comment
            continue
        if specific_name and name != specific_name:
            continue

        table = SM64_AnimTable(name, file_name=path.name, elements=table_elements)
        table.read_c(
            c_data,
            c_data.find(content, table_match.start()),
            table_match.end(),
            comment_map,
            read_headers,
            header_decls,
            values_decls,
            indices_decls,
        )
        tables.append(table)
    return tables


DECL_PATTERN = re.compile(
    r"(static\s+const\s+struct\s+Animation|static\s+const\s+u16|static\s+const\s+s16)\s+"
    r"(\w+)\s*?(?:\[.*?\])?\s*?=\s*?\{(.*?)\s*?\};",
    re.DOTALL,
)
VALUE_SPLIT_PATTERN = re.compile(r"\s*(?:(?:\.(?P<var>\w+)|\[\s*(?P<designator>.*?)\s*\])\s*=\s*)?(?P<val>.+?)(?:,|\Z)")


def find_decls(c_data: str, path: Path, decl_list: dict[str, list[CArrayDeclaration]]):
    """At this point a generilized c parser would be better"""
    matches = DECL_PATTERN.findall(c_data)
    for decl_type, name, value_text in matches:
        values = []
        for match in VALUE_SPLIT_PATTERN.finditer(value_text):
            var, designator, val = match.group("var"), match.group("designator"), match.group("val")
            assert val is not None
            if designator is not None:
                designator = math_eval(designator, object())
                if isinstance(designator, int):
                    if isinstance(values, dict):
                        raise PluginError("Invalid mix of designated initializers")
                    first_val = values[0] if values else "0"
                    values.extend([first_val] * (designator + 1 - len(values)))
                else:
                    if not values:
                        values = {}
                    elif isinstance(values, list):
                        raise PluginError("Invalid mix of designated initializers")
                values[designator] = val
            elif var is not None:
                if not values:
                    values = {}
                elif isinstance(values, list):
                    raise PluginError("Mix of designated and positional variable assignment")
                values[var] = val
            else:
                if isinstance(values, dict):
                    raise PluginError("Mix of designated and positional variable assignment")
                values.append(val)
        decl_list[decl_type].append(CArrayDeclaration(name, path, path.name, values))


def import_c_animations(path: Path) -> tuple[SM64_AnimTable | None, dict[str, SM64_AnimHeader]]:
    path_checks(path)
    if path.is_file():
        file_paths = [path]
    elif path.is_dir():
        file_paths = sorted([f for f in path.rglob("*") if f.suffix in {".c", ".h"}])
    else:
        raise PluginError("Path is neither a file or a folder but it exists, somehow.")

    print("Reading from:\n" + "\n".join([f.name for f in file_paths]))
    c_files = {file_path: get_comment_map(file_path.read_text()) for file_path in file_paths}

    decl_lists = {"static const struct Animation": [], "static const u16": [], "static const s16": []}
    header_decls, indices_decls, value_decls = (
        decl_lists["static const struct Animation"],
        decl_lists["static const u16"],
        decl_lists["static const s16"],
    )
    tables: list[SM64_AnimTable] = []
    enum_lists: list[SM64_AnimTable] = []
    for file_path, (comment_less, _comment_map) in c_files.items():
        find_decls(comment_less, file_path, decl_lists)
    for file_path, (comment_less, comment_map) in c_files.items():
        tables.extend(import_tables(comment_less, file_path, comment_map, "", header_decls, value_decls, indices_decls))
        enum_lists.extend(import_enums(comment_less, file_path, comment_map))

    if len(tables) > 1:
        raise ValueError("More than 1 table declaration")
    elif len(tables) == 1:
        table: SM64_AnimTable = tables[0]
        if enum_lists:
            enum_table = next(  # find enum with the same name or use the first
                (
                    enum_table
                    for enum_table in enum_lists
                    if enum_table.reference == table_name_to_enum(table.reference)
                ),
                enum_lists[0],
            )
            update_table_with_table_enum(table, enum_table)
        read_headers = {header.reference: header for header in table.header_set}
        return table, read_headers
    else:
        read_headers: dict[str, SM64_AnimHeader] = {}
        for table_index, header_decl in enumerate(sorted(header_decls, key=lambda h: h.name)):
            SM64_AnimHeader().read_c(header_decl, value_decls, indices_decls, read_headers, table_index)
        return None, read_headers


def import_binary_animations(
    data_reader: RomReader,
    import_type: str,
    read_headers: dict[str, SM64_AnimHeader],
    table: SM64_AnimTable,
    table_index: Optional[int] = None,
    bone_count: Optional[int] = None,
    table_size: Optional[int] = None,
):
    if import_type == "Table":
        table.read_binary(data_reader, read_headers, table_index, bone_count, table_size)
    elif import_type == "DMA":
        table.read_dma_binary(data_reader, read_headers, table_index, bone_count)
    elif import_type == "Animation":
        SM64_AnimHeader.read_binary(
            data_reader,
            read_headers,
            False,
            bone_count,
            table_size,
        )
    else:
        raise PluginError("Unimplemented binary import type.")


def import_insertable_binary_animations(
    reader: RomReader,
    read_headers: dict[str, SM64_AnimHeader],
    table: SM64_AnimTable,
    table_index: Optional[int] = None,
    bone_count: Optional[int] = None,
    table_size: Optional[int] = None,
):
    if reader.insertable.data_type == "Animation":
        SM64_AnimHeader.read_binary(
            reader,
            read_headers,
            False,
            bone_count,
        )
    elif reader.insertable.data_type == "Animation Table":
        table.read_binary(reader, read_headers, table_index, bone_count, table_size)
    elif reader.insertable.data_type == "Animation DMA Table":
        table.read_dma_binary(reader, read_headers, table_index, bone_count)


def import_animations(context: Context):
    animation_operator_checks(context, False)

    scene = context.scene
    obj: Object = context.object
    sm64_props: SM64_Properties = scene.fast64.sm64
    import_props: SM64_AnimImportProperties = sm64_props.animation.importing
    anim_props: SM64_ArmatureAnimProperties = obj.fast64.sm64.animation

    update_table_preset(import_props, context)

    read_headers: dict[str, SM64_AnimHeader] = {}
    table = SM64_AnimTable()

    print("Reading animation data.")

    if import_props.binary:
        rom_path = Path(abspath(import_props.rom if import_props.rom else sm64_props.import_rom))
        binary_args = (
            read_headers,
            table,
            import_props.table_index,
            None if import_props.ignore_bone_count else len(get_anim_owners(obj)),
            import_props.table_size,
        )
    if import_props.import_type == "Binary":
        import_rom_checks(rom_path)
        address = import_props.address
        with rom_path.open("rb") as rom_file:
            if import_props.binary_import_type == "DMA":
                segment_data = None
            else:
                segment_data = parseLevelAtPointer(rom_file, level_pointers[import_props.level]).segmentData
                if import_props.is_segmented_address:
                    address = decodeSegmentedAddr(address.to_bytes(4, "big"), segment_data)
            import_binary_animations(
                RomReader(rom_file, start_address=address, segment_data=segment_data),
                import_props.binary_import_type,
                *binary_args,
            )
    elif import_props.import_type == "Insertable Binary":
        insertable_path = Path(abspath(import_props.path))
        filepath_checks(insertable_path)
        with insertable_path.open("rb") as insertable_file:
            if import_props.read_from_rom:
                import_rom_checks(rom_path)
                with rom_path.open("rb") as rom_file:
                    segment_data = parseLevelAtPointer(rom_file, level_pointers[import_props.level]).segmentData
                    import_insertable_binary_animations(
                        RomReader(rom_file, insertable_file=insertable_file, segment_data=segment_data),
                        *binary_args,
                    )
            else:
                import_insertable_binary_animations(RomReader(insertable_file=insertable_file), *binary_args)
    elif import_props.import_type == "C":
        table, read_headers = import_c_animations(Path(abspath(import_props.path)))
        table = table or SM64_AnimTable()
    else:
        raise NotImplementedError(f"Unimplemented animation import type {import_props.import_type}")

    if not table.elements:
        print("No table was read. Automatically creating table.")
        table.elements = [SM64_AnimTableElement(header=header) for header in read_headers.values()]
    seperate_anims = table.get_seperate_anims()

    actor_name: str = get_anim_actor_name(context)
    if import_props.use_preset and import_props.preset in ACTOR_PRESET_INFO:
        preset_animation_names = get_preset_anim_name_list(import_props.preset)
        for animation in seperate_anims:
            if len(animation.headers) == 0:
                continue
            names, indexes = [], []
            for header in animation.headers:
                if header.table_index >= len(preset_animation_names):
                    continue
                name = preset_animation_names[header.table_index]
                header.enum_name = header.enum_name or anim_name_to_enum_name(f"{actor_name}_anim_{name}")
                names.append(name)
                indexes.append(str(header.table_index))
            animation.action_name = f"{'/'.join(indexes)} - {'/'.join(names)}"
        for i, element in enumerate(table.elements[: len(preset_animation_names)]):
            name = preset_animation_names[i]
            element.enum_name = element.enum_name or anim_name_to_enum_name(f"{actor_name}_anim_{name}")

    print("Importing animations into blender.")
    actions = []
    for animation in seperate_anims:
        actions.append(
            animation_import_to_blender(
                obj,
                sm64_props.blender_to_sm64_scale,
                animation,
                actor_name,
                import_props.use_custom_name,
                import_props.import_type,
                import_props.force_quaternion,
                import_props.continuity_filter if not import_props.force_quaternion else True,
            )
        )

    if import_props.run_decimate:
        print("Decimating imported actions's fcurves")
        old_area = bpy.context.area.type
        old_action = obj.animation_data.action
        try:
            if obj.type == "ARMATURE":
                bpy.ops.object.posemode_toggle()  # Select all bones
                bpy.ops.pose.select_all(action="SELECT")

            bpy.context.area.type = "GRAPH_EDITOR"
            for action in actions:
                print(f"Decimating {action.name}.")
                obj.animation_data.action = action
                bpy.ops.graph.select_all(action="SELECT")
                bpy.ops.graph.decimate(mode="ERROR", factor=1, remove_error_margin=import_props.decimate_margin)
        finally:
            bpy.context.area.type = old_area
            obj.animation_data.action = old_action

    if import_props.binary:
        anim_props.is_dma = import_props.binary_import_type == "DMA"
    if table:
        print("Importing animation table into properties.")
        from_anim_table_class(anim_props, table, import_props.clear_table, import_props.use_custom_name, actor_name)


@functools.cache
def cached_enum_from_import_preset(preset: str):
    animation_names = get_preset_anim_name_list(preset)
    enum_items: list[tuple[str, str, str, int]] = []
    enum_items.append(("Custom", "Custom", "Pick your own animation index", 0))
    if animation_names:
        enum_items.append(("", "Presets", "", 1))
    for i, name in enumerate(animation_names):
        enum_items.append((str(i), f"{i} - {name}", f'"{preset}" Animation {i}', i + 2))
    return enum_items


def get_enum_from_import_preset(_import_props: "SM64_AnimImportProperties", context):
    try:
        return cached_enum_from_import_preset(get_scene_anim_props(context).importing.preset)
    except Exception as exc:  # pylint: disable=broad-except
        print(str(exc))
        return [("Custom", "Custom", "Pick your own animation index", 0)]


def update_table_preset(import_props: "SM64_AnimImportProperties", context):
    if not import_props.use_preset:
        return

    preset = ACTOR_PRESET_INFO[import_props.preset]
    assert preset.animation is not None and isinstance(
        preset.animation, AnimInfo
    ), "Selected preset's actor has not animation information"

    if import_props.preset_animation == "":
        # If the previously selected animation isn't in this preset, select animation 0
        import_props.preset_animation = "0"

    # C
    decomp_path = import_props.decomp_path if import_props.decomp_path else context.scene.fast64.sm64.decomp_path
    directory = preset.animation.directory if preset.animation.directory else f"{preset.decomp_path}/anims"
    import_props.path = os.path.join(decomp_path, directory)

    # Binary
    import_props.ignore_bone_count = preset.animation.ignore_bone_count
    import_props.level = preset.level
    if preset.animation.dma:
        import_props.dma_table_address = intToHex(preset.animation.address)
        import_props.binary_import_type = "DMA"
        import_props.is_segmented_address_prop = False
    else:
        import_props.table_address = intToHex(preset.animation.address)
        import_props.binary_import_type = "Table"
        import_props.is_segmented_address_prop = True

    if preset.animation.size is None:
        import_props.check_null = True
    else:
        import_props.check_null = False
        import_props.table_size_prop = preset.animation.size
