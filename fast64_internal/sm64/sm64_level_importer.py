# TODO:
# Add support for special objects
# stretch goals
# deal with direct DLs instead of geos (model metal box for example)
# make layer detection work better?
# make better naming for certain vars
# try to fix edge cases and any weird importing stuff (basically lots of testing, it feels mostly good but this must be done last)

from __future__ import annotations


import bpy
import bmesh

from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
    IntVectorProperty,
    BoolVectorProperty,
)
from bpy.types import (
    Panel,
    Menu,
    Operator,
    PropertyGroup,
)
from bpy.utils import register_class, unregister_class

import cProfile, pstats, io
from pstats import SortKey

import os, sys, math, re, typing
from struct import *
from pathlib import Path
from mathutils import Vector, Euler, Matrix, Quaternion
from copy import deepcopy
from dataclasses import dataclass
from typing import TextIO, BinaryIO
from collections.abc import Sequence

from ..f3d.f3d_import import *
from ..f3d.f3d_material import update_node_values_of_material, getDefaultMaterialPreset, createF3DMat
from ..panels import SM64_Panel
from ..utility_importer import *
from ..utility import (
    transform_mtx_blender_to_n64,
    rotate_quat_n64_to_blender,
    rotate_object,
    parentObject,
    GetEnums,
    prop_split,
    create_collection,
    read16bitRGBA,
    hexOrDecInt,
    gammaInverse,
)
from .sm64_objects import enumEnvFX
from .sm64_utility import import_rom_checks, convert_addr_to_func
from .sm64_constants import (
    ACTOR_PRESET_INFO,
    ModelInfo,
    enumVersionDefs,
    enumLevelNames,
    enumSpecialsNames,
    LEVEL_ID_NUMBERS,
    groups_obj_export,
)

# ------------------------------------------------------------------------
#    Data
# ------------------------------------------------------------------------

# do something better than this later
Layers = {
    "LAYER_FORCE": "0",
    "LAYER_OPAQUE": "1",
    "LAYER_OPAQUE_DECAL": "2",
    "LAYER_OPAQUE_INTER": "3",
    "LAYER_ALPHA": "4",
    "LAYER_TRANSPARENT": "5",
    "LAYER_TRANSPARENT_DECAL": "6",
    "LAYER_TRANSPARENT_INTER": "7",
}

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------


@dataclass
class Object:
    model: str
    pos: Vector
    angle: Euler
    bparam: str
    behavior: str
    act_mask: int


class Area:
    def __init__(
        self,
        root: bpy.types.Object,
        geo: str,
        levelRoot: bpy.types.Object,
        num: int,
        scene: bpy.types.Scene,
        col: bpy.types.Collection,
    ):
        self.root = root
        self.geo = geo
        self.geo_data = None
        self.num = num
        self.scene = scene
        self.props = scene.fast64.sm64.importer
        self.col_file = None
        # Set level root as parent
        parentObject(levelRoot, root)
        # set default vars
        root.sm64_obj_type = "Area Root"
        root.areaIndex = num
        self.objects = []
        self.placed_special_objects = []  # for linking objects later
        self.col = col

    def add_warp(self, args: list[str], type: str):
        # set context to the root
        bpy.context.view_layer.objects.active = self.root
        # call fast64s warp node creation operator
        bpy.ops.bone.add_warp_node()
        warp = self.root.warpNodes[0]
        warp.warpID = args[0]
        warp.destNode = args[3]
        level = get_level_name(args[1]).replace("LEVEL_", "").lower()
        if level == "castle":
            level = "castle_inside"
        warp.warpType = type
        warp.destLevelEnum = level
        warp.destArea = args[2]
        chkpoint = args[-1]
        # Sorry for the hex users here
        if "WARP_NO_CHECKPOINT" in chkpoint or int(chkpoint.isdigit() * chkpoint + "0") == 0:
            warp.warpFlagEnum = "WARP_NO_CHECKPOINT"
        else:
            warp.warpFlagEnum = "WARP_CHECKPOINT"

    def add_instant_warp(self, args: list[str]):
        # set context to the root
        bpy.context.view_layer.objects.active = self.root
        # call fast64s warp node creation operator
        bpy.ops.bone.add_warp_node()
        warp = self.root.warpNodes[0]
        warp.type = "Instant"
        warp.warpID = args[0]
        warp.destArea = args[1]
        warp.instantOffset = [hexOrDecInt(val) for val in args[2:5]]

    def add_object(self, args: list[str]):
        # error prone? do people do math in pos?
        pos = (
            Vector(hexOrDecInt(arg) for arg in args[1:4]) / self.scene.fast64.sm64.blender_to_sm64_scale
        ) @ transform_mtx_blender_to_n64()
        angle = Euler([math.radians(eval_or_int(a)) for a in args[4:7]], "ZXY")
        angle = rotate_quat_n64_to_blender(angle).to_euler("XYZ")
        self.objects.append(Object(args[0], pos, angle, *args[7:]))

    def place_objects(self, col_name: str = None, actor_models: dict[model_name, bpy.Types.Object] = None):
        if not col_name:
            col = self.col
        else:
            col = create_collection(self.root.users_collection[0], col_name)
        for object in self.objects:
            bpy_obj = self.place_object(object, col)
            if not actor_models:
                continue
            model_obj = actor_models.get(object.model, None)
            if model_obj is None:
                continue
            self.link_bpy_obj_to_empty(bpy_obj, model_obj, col)
        if not actor_models:
            return
        for placed_obj in self.placed_special_objects:
            if "level_geo" in placed_obj.sm64_special_enum:
                level_geo_model_name = self.get_level_geo_from_special(placed_obj.sm64_special_enum)
                model_obj = actor_models.get(level_geo_model_name, None)
                if model_obj:
                    self.link_bpy_obj_to_empty(placed_obj, model_obj, col)

    def get_level_geo_from_special(self, special_name: str):
        return special_name.replace("special", "MODEL").replace("geo", "GEOMETRY").upper()

    def write_special_objects(self, special_objs: list[str], col: bpy.types.Collection):
        special_presets = {enum[0] for enum in enumSpecialsNames}
        for special in special_objs:
            bpy_obj = bpy.data.objects.new("Empty", None)
            col.objects.link(bpy_obj)
            parentObject(self.root, bpy_obj)
            bpy_obj.name = f"Special Object {special[0]}"
            bpy_obj.sm64_obj_type = "Special"
            if special[0] in special_presets:
                bpy_obj.sm64_special_enum = special[0]
            else:
                bpy_obj.sm64_special_enum = "Custom"
                bpy_obj.sm64_obj_preset = special[0]
            loc = [eval_or_int(a) / self.scene.fast64.sm64.blender_to_sm64_scale for a in special[1:4]]
            # rotate to fit sm64s axis
            bpy_obj.location = [loc[0], -loc[2], loc[1]]
            bpy_obj.rotation_euler[2] = hexOrDecInt(special[4])
            bpy_obj.sm64_obj_set_yaw = True
            if special[5]:
                bpy_obj.sm64_obj_set_bparam = True
                bpy_obj.fast64.sm64.game_object.use_individual_params = False
                bpy_obj.fast64.sm64.game_object.bparams = special[5]
            self.placed_special_objects.append(bpy_obj)

    def place_object(self, object: Object, col: bpy.types.Collection):
        bpy_obj = bpy.data.objects.new("Empty", None)
        col.objects.link(bpy_obj)
        parentObject(self.root, bpy_obj)
        bpy_obj.name = "Object {} {}".format(object.behavior, object.model)
        bpy_obj.sm64_obj_type = "Object"
        bpy_obj.sm64_behaviour_enum = "Custom"
        bpy_obj.sm64_obj_behaviour = object.behavior.strip() if type(object.behavior) is str else hex(object.behavior)
        #  change this to look at props version number?
        if hasattr(bpy_obj, "sm64_obj_bparam"):
            bpy_obj.sm64_obj_bparam = object.bparam
        else:
            bpy_obj.fast64.sm64.game_object.bparams = object.bparam
        bpy_obj.sm64_obj_model = object.model
        bpy_obj.location = object.pos
        bpy_obj.rotation_euler.rotate(object.angle)
        # set act mask, !fix this for hacker versions
        mask = object.act_mask
        if type(mask) == str and mask.isdigit():
            mask = eval_or_int(mask)
        form = "sm64_obj_use_act{}"
        if mask == 31:
            for i in range(1, 7, 1):
                setattr(bpy_obj, form.format(i), True)
        else:
            for i in range(1, 7, 1):
                if mask & (1 << (i - 1)):
                    setattr(bpy_obj, form.format(i), True)
                else:
                    setattr(bpy_obj, form.format(i), False)
        return bpy_obj

    def link_bpy_obj_to_empty(
        self, bpy_obj: bpy.Types.Object, model_obj: bpy.Types.Collection, col: bpy.Types.Collection
    ):
        # duplicate, idk why temp override doesn't work
        # with bpy.context.temp_override(active_object = model_obj, selected_objects = model_obj.children_recursive):
        # bpy.ops.object.duplicate_move_linked()
        bpy.ops.object.select_all(action="DESELECT")
        for child in model_obj.children_recursive:
            child.select_set(True)
        model_obj.select_set(True)
        bpy.context.view_layer.objects.active = model_obj
        bpy.ops.object.duplicate_move()
        new_obj = bpy.context.active_object
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)
        # unlink from col, add to area col
        for obj in (new_obj, *new_obj.children_recursive):
            obj.users_collection[0].objects.unlink(obj)
            col.objects.link(obj)
        new_obj.location = bpy_obj.location
        new_obj.rotation_euler = bpy_obj.rotation_euler
        # add constraints so obj follows along when you move empty
        copy_loc = new_obj.constraints.new("COPY_LOCATION")
        copy_loc.target = bpy_obj
        copy_rot = new_obj.constraints.new("COPY_ROTATION")
        copy_rot.target = bpy_obj


class Level(DataParser):
    """DataParser for level scripts, run parse_level_script to get data, entry point is anywhere in bin files, level specific script start for C

    Use parse_level_script helper function to setup and run Level script parser properly
    """

    # class data
    _skippable_cmds = {
        "LOAD_MARIO_HEAD",
        "SET_REG",
        "FIXED_LOAD",
        "CMD3A",
        "STOP_MUSIC",
        "GAMMA",
        "BLACKOUT",
        "TRANSITION",
        "NOP",
        "CMD23",
        "PUSH_POOL",
        "POP_POOL",
        "SLEEP",
        "ROOMS",
        "MARIO",
        "INIT_LEVEL",
        "ALLOC_LEVEL_POOL",
        "FREE_LEVEL_POOL",
        "CALL",
        "CLEAR_LEVEL",
        "SLEEP_BEFORE_EXIT",
        "LOAD_AREA",
        "UNLOAD_AREA",
        "UNLOAD_MARIO_AREA",
        # hacker only cmds with no support needed
        "CHANGE_AREA_SKYBOX",
        "SET_ECHO",
        "LOAD_TITLE_SCREEN_BG",
        "LOAD_GODDARD",
        "LOAD_BEHAVIOR_DATA",
        "LOAD_COMMON0",
        "LOAD_GROUPB",
        "LOAD_GROUPA",
        "LOAD_EFFECTS",
        "LOAD_SKYBOX",
        "LOAD_TEXTURE_BIN",
        "LOAD_LEVEL_DATA",
        "LOAD_YAY0",
        "LOAD_YAY0_TEXTURE",
        "LOAD_VANILLA_OBJECTS",
        "LOAD_RAW_WITH_CODE",
    }
    # MSB: (name, PackedFormat)
    _lvl_cmds_bin_format = {
        0x0: ("EXECUTE", PackedFormat(">H3L", make_str=False)),  # seg script_start script_end entry_ptr
        0x1: ("EXIT_AND_EXECUTE", PackedFormat(">H3L", make_str=False)),  # seg script_start script_end entry_ptr
        0x2: ("EXIT", PackedFormat(">H")),  # pad
        0x3: ("SLEEP", PackedFormat(">H")),  # frames
        0x4: ("SLEEP_BEFORE_EXIT", PackedFormat(">H")),  # frames
        0x5: ("JUMP", PackedFormat(">HL", (1,))),  # pad script_ptr
        0x6: ("JUMP_LINK", PackedFormat(">HL", (1,))),  # pad script_ptr
        0x7: ("RETURN", PackedFormat(">H")),  # pad
        0x8: (
            "JUMP_LINK_PUSH_ARG",
            PackedFormat(">H"),
        ),  # arg
        0x9: ("JUMP_N_TIMES", PackedFormat(">H")),  # pad
        0xA: ("LOOP_BEGIN", PackedFormat(">H")),  # pad
        0xB: ("LOOP_UNTIL", PackedFormat(">BBl")),  # op pad arg
        0xC: ("JUMP_IF", PackedFormat(">BBlL", (3,), make_str=False)),  # op pad arg script_ptr
        0xD: ("JUMP_LINK_IF", PackedFormat(">BBlL")),  # op pad arg script_ptr
        0xE: ("SKIP_IF", PackedFormat(">BBl")),  # op pad arg
        0xF: ("SKIP", PackedFormat(">H")),  # pad
        0x10: ("SKIP_NOP", PackedFormat(">H")),  # pad
        0x11: ("CALL", PackedFormat(">HL")),  # arg script_ptr
        0x12: ("CALL_LOOP", PackedFormat(">HL", make_str=False)),  # arg script_ptr
        0x13: ("SET_REG", PackedFormat(">H")),  # value
        0x14: ("PUSH_POOL", PackedFormat(">H")),  # pad
        0x15: ("POP_POOL", PackedFormat(">H")),  # pad
        0x16: ("FIXED_LOAD", PackedFormat(">H3L")),  # load_addr start_ptr end_ptr
        0x17: ("LOAD_RAW", PackedFormat(">2B2L", reorder=(1, 2, 3), make_str=False)),  # pad seg start_ptr end_ptr
        0x18: ("LOAD_MIO0", PackedFormat(">2B2L", reorder=(1, 2, 3), make_str=False)),  # pad seg start_ptr end_ptr
        0x19: ("LOAD_MARIO_HEAD", PackedFormat(">H")),  # set head
        0x1A: (
            "LOAD_MIO0_TEXTURE",
            PackedFormat(">2B2L", reorder=(1, 2, 3), make_str=False),
        ),  # pad seg start_ptr end_ptr
        0x1B: ("INIT_LEVEL", PackedFormat(">H")),  # pad
        0x1C: ("CLEAR_LEVEL", PackedFormat(">H")),  # pad
        0x1D: ("ALLOC_LEVEL_POOL", PackedFormat(">H")),  # pad
        0x1E: ("FREE_LEVEL_POOL", PackedFormat(">H")),  # pad
        0x1F: (
            "AREA",
            PackedFormat(">2BL", make_str=False),
        ),  # index, pad, geo_ptr, delay ptr retrieval because hacks do
        0x20: ("END_AREA", PackedFormat(">H")),  # pad
        0x21: ("LOAD_MODEL_FROM_DL", PackedFormat(">Hl")),  # model|layer dl_ptr
        0x22: ("LOAD_MODEL_FROM_GEO", PackedFormat(">HL", (1,))),  # model geo_ptr
        0x23: ("CMD23", PackedFormat(">HLl")),  # pad ptr unk
        0x24: (
            "OBJECT_WITH_ACTS",
            PackedFormat(">2B6hLL", (9,), reorder=(1, 2, 3, 4, 5, 6, 7, 8, 9, 0)),
        ),  # model posXYZ angleXYZ beh_param beh acts, reorder -> acts model posXYZ angleXYZ beh_param beh
        0x25: ("MARIO", PackedFormat(">BBlL")),  # pad unk beh_param beh_ptr
        0x26: ("WARP_NODE", PackedFormat(">6B")),  # id dest_level dest_area dest_node flags pad
        0x27: ("PAINTING_WARP_NODE", PackedFormat(">6B")),  # id dest_level dest_area dest_node flags pad
        0x28: ("INSTANT_WARP", PackedFormat(">2B4h")),  # index dest_area displaceXYZ pad
        0x29: ("LOAD_AREA", PackedFormat(">H")),  # area
        0x2A: ("UNLOAD_AREA", PackedFormat(">H")),  # area
        0x2B: ("MARIO_POS", PackedFormat(">BB4h")),  # area pad yaw posXYZ
        0x2C: ("UNLOAD_MARIO_AREA", PackedFormat(">H")),  # pad
        0x2D: "UPDATE_OBJECTS",
        0x2E: ("TERRAIN", PackedFormat(">HL", make_str=False)),  # pad col_ptr, delay ptr retrieval because hacks do
        0x2F: ("ROOMS", PackedFormat(">HL")),  # pad rooms_ptr
        0x30: ("SHOW_DIALOG", PackedFormat(">BB")),  # index dialog_id
        0x31: ("TERRAIN_TYPE", PackedFormat(">H")),  # terrain type
        0x32: ("NOP", PackedFormat(">H")),  # pad
        0x33: ("TRANSITION", PackedFormat(">6B")),  # trans_type time rgb_col pad
        0x34: ("BLACKOUT", PackedFormat(">BB")),  # enable pad
        0x35: ("GAMMA", PackedFormat(">BB")),  # enable pad
        0x36: ("SET_BACKGROUND_MUSIC", PackedFormat(">3H")),  # preset seq pad
        0x37: ("SET_MENU_MUSIC", PackedFormat(">H")),  # seq
        0x38: ("STOP_MUSIC", PackedFormat(">H")),  # fade_time
        0x39: ("MACRO_OBJECTS", PackedFormat(">HL", (1,))),  # pad object_list_ptr
        0x3A: ("CMD3A", PackedFormat(">5H")),  # 5 pads
        0x3B: ("WHIRLPOOL", PackedFormat(">2B3hH")),  # index condition posXYZ strength
        0x3C: ("GET_OR_SET", PackedFormat(">BB")),  # op var
        # these are hacker cmds only
        0x3D: "PUPPYVOLUME",
        0x3E: "CHANGE_AREA_SKYBOX",
        0x3F: "SET_ECHO",
    }

    def __init__(
        self,
        scripts: dict[str, list[str]],
        scene: bpy.types.Scene,
        root: bpy.types.Object,
        parse_target: int = DataParser._c_parsing,
    ):
        self.scripts = scripts  # for binary, this will be empty
        self.scene = scene
        self.props = scene.fast64.sm64.importer
        self.areas: dict[area_index:int, Area] = {}
        self.cur_area: int = None
        self.root = root
        self.loaded_geos: dict[model_name:str, geo_name:str] = dict()
        self.loaded_dls: dict[model_name:str, dl_name:str] = dict()
        self.banks = get_bank_loads(reset=True)
        super().__init__(parse_target=parse_target)

    # parsing funcs, see utility_importer for how parsing works
    def parse_level_script(self, entry: str, col: bpy.types.Collection = None):
        if not col:
            col = self.scene.collection
        script_stream = self.get_new_stream(entry)
        self.parse_stream_from_start(script_stream, entry, col)

    def get_new_stream(self, entry: Union[str, int]) -> Union[Sequence, None]:
        if type(entry) is str:
            return self.scripts[entry]
        else:
            return None

    """
    binary parsing funcs:
        * run parse_stream_from_start(dat_stream, entry, *args) w/ dat_stream = None, entry = rom_ptr: int
        * binary_cmd_get(parser) -> cmd_name and cmd_format, update parser.head manually to advanced num bytes read
        * binary_cmd_unpack/f"_decode_cmd_{cmd_name.lower()}_bin"(parser, PackedFormat) -> cmd_args
        * parser head is advanced the length of PackedFormat! Make sure all bytes are read, even padding
        * call Macro function
    """

    def binary_cmd_get(self, parser: Parser) -> tuple[cmd_name:str, PackedFormat]:
        cmd_type = self.unpack_type(parser.cur_stream, parser.head, ">B", make_str=False)
        cmd_name, packed_fmt = self._lvl_cmds_bin_format.get(cmd_type)
        # update head to go past cmd type and cmd length bytes
        parser.advance_head(2)
        return cmd_name, packed_fmt

    def load_segment_two(self, bin_file: BinaryIO):
        """Loads segment two which is based on asm ran during game start"""
        start = self.unpack_type(bin_file, 0x3AC2, ">H", make_str=False) << 16
        start += self.unpack_type(bin_file, 0x3ACE, ">H", make_str=False)
        end = self.unpack_type(bin_file, 0x3AC6, ">H", make_str=False) << 16
        end += self.unpack_type(bin_file, 0x3ACA, ">H", make_str=False)
        # mio0 for seg2 expands by 0x3156, from mio0 header 0xC
        self.banks.tlb[2] = [start + 0x3156, end + 0x3156]

    def check_rom_manager(self, editor: bool = False, rom_manager: bool = True) -> bool:
        """Checks if bin_file is a RM, editor or vanilla ROM based on signatures

        custom hacks override the level script execute jump table (0x8038B914 -> 0x00108694) cmd 0x17 LOAD_RAW with a cmd in custom memory
        in vanilla it is 0x8037ECA4 -> 0x00FBA24
        the function goes to 0x80402000 -> 0x1204000
        in editor the override goes to 0x80401500 -> 0x1201500
        other versions of editor/rom manager may use other overrides but I doubt it's that common
        for debugging purposes, sSegmentTable is 0x8033B400

        check for version based on args, default is rom manager. False for vanilla, True if matching specific tool
        """
        load_raw_func_addr = self.unpack_type(self.bin_file, 0x00108694, ">L", make_str=False)
        if load_raw_func_addr == 0x8037ECA4:
            return False
        if load_raw_func_addr == 0x80402000 and rom_manager:
            return True
        else:
            return editor

    # update area terrain and geo_ptr
    def update_col_ptr(self, area_index: int):
        if self.areas[area_index].terrain:
            self.areas[area_index].col_file = self.seg2phys(self.areas[area_index].terrain)

    def update_geo_ptr(self, area_index: int):
        if self.areas[area_index].geo:
            self.areas[area_index].geo = self.seg2phys(self.areas[area_index].geo)

    def load_segment_E(self, area_index: int):
        """Loads segment 0xE after level script is done, call before parsing col/geo/f3d data

        for RM custom levels, segment 0xE has a hook on the CALL level script to dma new data to seg 0xE
        for blender purposes, this can just be emulated by calling this func before each area is parsed
        """
        is_rm = self.check_rom_manager()
        if not is_rm:
            return
        # if it is a custom level it is using bank 0x19
        if not self.banks.tlb.get(0x19, None):
            return
        area_index = int(area_index)
        load_addr = self.seg2phys(0x19005F00)
        start = self.unpack_type(self.bin_file, load_addr + area_index * 16, ">L", make_str=False)
        end = self.unpack_type(self.bin_file, load_addr + 4 + area_index * 16, ">L", make_str=False)
        self.banks.tlb[0x0E] = [start, end]

    # macro parsing funcs
    def EXECUTE(self, macro: Macro, col: bpy.types.Collection):
        """jump to new script, goes back via EXIT, not RETURN
        shouldn't matter though as long as game follows its own rules, can use normal recursion
        """
        self.banks.tlb[macro.args[0]] = (macro.args[1], macro.args[2])
        if type(macro.args[-1]) is int:
            macro.args[-1] = self.seg2phys(macro.args[-1])
        if macro.args[-1]:
            self.parse_level_script(macro.args[-1], col=col)
        return self._continue_parse

    def EXIT_AND_EXECUTE(self, macro: Macro, col: bpy.types.Collection):
        self.banks.tlb[macro.args[0]] = (macro.args[1], macro.args[2])
        if type(macro.args[-1]) is int:
            macro.args[-1] = self.seg2phys(macro.args[-1])
        if macro.args[-1]:
            self.parse_level_script(macro.args[-1], col=col)
        return self._break_parse

    # hackersm64 alias of EXECUTE
    def EXECUTE_WITH_CODE(self, macro: Macro, col: bpy.types.Collection):
        return self.EXECUTE(macro, col)

    # hackersm64 alias of EXIT_AND_EXECUTE
    def EXIT_AND_EXECUTE_WITH_CODE(self, macro: Macro, col: bpy.types.Collection):
        return self.EXIT_AND_EXECUTE(macro, col)

    def EXIT(self, macro: Macro, col: bpy.types.Collection):
        return self._break_parse

    # ends script
    def JUMP(self, macro: Macro, col: bpy.types.Collection):
        if macro.args[-1]:
            self.parse_level_script(macro.args[-1], col=col)
        return self._break_parse

    # Jumps are only taken if they're in the script.c file for now
    # continues script
    def JUMP_LINK(self, macro: Macro, col: bpy.types.Collection):
        if macro.args[-1]:
            self.parse_level_script(macro.args[-1], col=col)
        return self._continue_parse

    def RETURN(self, macro: Macro, col: bpy.types.Collection):
        return self._break_parse

    # only used once, don't need to process
    def LOOP_BEGIN(self, macro: Macro, col: bpy.types.Collection):
        return self._continue_parse

    # only used once, signals end of script parsing because script will repeat until game over
    def LOOP_UNTIL(self, macro: Macro, col: bpy.types.Collection):
        return self._exit_parse

    # this is where we jump to our level specific script, only necessary in binary processing
    def JUMP_IF(self, macro: Macro, col: bpy.types.Collection):
        target_level = get_level_name(macro.args[-2])
        if macro.args[0] in {"OP_EQ", 2} and target_level == self.props.level_name:
            if macro.args[-1]:
                # reset areas so file select area isn't written out
                self.areas = dict()
                self.cur_area = None
                self.parse_level_script(macro.args[-1], col=col)
        return self._continue_parse

    # used to run the, execute_level_script func, e.g. start the level
    # will represent the end of parsing, check for specific func
    def CALL_LOOP(self, macro: Macro, col: bpy.types.Collection):
        if macro.args[-1] == 0x8024BCD8:
            return self._exit_parse
        else:
            return self._continue_parse

    # use group mapping to set groups eventually
    def LOAD_RAW(self, macro: Macro, col: bpy.types.Collection):
        self.banks.tlb[macro.args[0]] = (macro.args[1], macro.args[2])
        return self._continue_parse

    # mio0 header is sig, len, comp_off decomp_off. Add decomp_off to bank start
    def _decode_cmd_load_mio0_texture_bin(
        self, packed_fmt: PackedFormat, parser: Parser
    ) -> tuple[cmd_name:str, cmd_args : list[int], cmd_len:int]:
        return self._decode_cmd_load_mio0_bin(packed_fmt, parser)

    def _decode_cmd_load_mio0_bin(
        self, packed_fmt: PackedFormat, parser: Parser
    ) -> tuple[cmd_name:str, cmd_args : list[int], cmd_len:int]:
        cmd_args = self.unpack_type(parser.cur_stream, parser.head, packed_fmt, ret_iterable=True)
        mio0_header = cmd_args[1]
        mio0_offset = self.unpack_type(parser.cur_stream, mio0_header + 0xC, ">L", make_str=False)
        return (
            "LOAD_MIO0",
            [cmd_args[0], cmd_args[1] + mio0_offset, cmd_args[2] + mio0_offset],
            packed_fmt.format_size,
        )

    def LOAD_MIO0(self, macro: Macro, col: bpy.types.Collection):
        self.banks.tlb[macro.args[0]] = (macro.args[1], macro.args[2])
        return self._continue_parse

    def LOAD_MIO0_TEXTURE(self, macro: Macro, col: bpy.types.Collection):
        self.banks.tlb[macro.args[0]] = (macro.args[1], macro.args[2])
        return self._continue_parse

    def AREA(self, macro: Macro, col: bpy.types.Collection):
        area_root = bpy.data.objects.new("Empty", None)
        if self.props.use_collection:
            area_col = bpy.data.collections.new(f"{self.props.level_name} area {macro.args[0]}")
            col.children.link(area_col)
        else:
            area_col = col
        area_col.objects.link(area_root)
        area_root.name = f"{self.props.level_name} Area Root {macro.args[0]}"
        self.areas[macro.args[0]] = Area(area_root, macro.args[-1], self.root, int(macro.args[0]), self.scene, area_col)
        self.cur_area = macro.args[0]
        return self._continue_parse

    def END_AREA(self, macro: Macro, col: bpy.types.Collection):
        self.cur_area = None
        return self._continue_parse

    def LOAD_MODEL_FROM_DL(self, macro: Macro, col: bpy.types.Collection):
        self.loaded_dls[macro.args[0]] = macro.args[1]
        return self._continue_parse

    def LOAD_MODEL_FROM_GEO(self, macro: Macro, col: bpy.types.Collection):
        self.loaded_geos[macro.args[0]] = macro.args[1]
        return self._continue_parse

    def OBJECT_WITH_ACTS(self, macro: Macro, col: bpy.types.Collection):
        # convert act mask from ORs of act names to a number
        mask = macro.args[-1]
        if type(mask) is str and not mask.isdigit():
            mask = mask.replace("ACT_", "")
            mask = mask.split("|")
            # Attempt for safety I guess
            try:
                accumulator = 0
                for m in mask:
                    accumulator += 1 << int(m)
                mask = accumulator
            except:
                mask = 31
        self.areas[self.cur_area].add_object([*macro.args[:-1], mask])
        return self._continue_parse

    # alias of object with acts, no bin decode
    def OBJECT(self, macro: Macro, col: bpy.types.Collection):
        # Only difference is act mask, which I set to 31 to mean all acts
        self.areas[self.cur_area].add_object([*macro.args, 31])
        return self._continue_parse

    def WARP_NODE(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].add_warp(macro.args, "Warp")
        return self._continue_parse

    def PAINTING_WARP_NODE(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].add_warp(macro.args, "Painting")
        return self._continue_parse

    def INSTANT_WARP(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].add_instant_warp(macro.args)
        return self._continue_parse

    def MARIO_POS(self, macro: Macro, col: bpy.types.Collection):
        return self._continue_parse

    def TERRAIN(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].terrain = macro.args[-1]
        return self._continue_parse

    def SHOW_DIALOG(self, macro: Macro, col: bpy.types.Collection):
        root = self.areas[self.cur_area].root
        root.showStartDialog = True
        root.startDialog = macro.args[1]
        return self._continue_parse

    def TERRAIN_TYPE(self, macro: Macro, col: bpy.types.Collection):
        if type(macro.args[0]) is str and not macro.args[0].isdigit():
            self.areas[self.cur_area].root.terrainEnum = macro.args[0]
        else:
            terrains = {
                0: "TERRAIN_GRASS",
                1: "TERRAIN_STONE",
                2: "TERRAIN_SNOW",
                3: "TERRAIN_SAND",
                4: "TERRAIN_SPOOKY",
                5: "TERRAIN_WATER",
                6: "TERRAIN_SLIDE",
                7: "TERRAIN_MASK",
            }
            try:
                num = eval_or_int(macro.args[0])
                self.areas[self.cur_area].root.terrainEnum = terrains.get(num)
            except:
                print("could not set terrain")
        return self._continue_parse

    def SET_BACKGROUND_MUSIC(self, macro: Macro, col: bpy.types.Collection):
        return self.generic_music(macro, col)

    # alias of set menu music
    def SET_MENU_MUSIC_WITH_REVERB(self, macro: Macro, col: bpy.types.Collection):
        return self.SET_MENU_MUSIC(macro, col)

    # alias of set bg music
    def SET_BACKGROUND_MUSIC_WITH_REVERB(self, macro: Macro, col: bpy.types.Collection):
        return self.generic_music(macro, col)

    # woops no area root
    def SET_MENU_MUSIC(self, macro: Macro, col: bpy.types.Collection):
        # root = self.areas[self.cur_area].root
        # root.musicSeqEnum = "Custom"
        # root.music_seq = macro.args[0]
        return self._continue_parse

    def generic_music(self, macro: Macro, col: bpy.types.Collection):
        root = self.areas[self.cur_area].root
        root.musicSeqEnum = "Custom"
        root.music_seq = macro.args[1]
        return self._continue_parse

    # Don't support these for now

    def MACRO_OBJECTS(self, macro: Macro, col: bpy.types.Collection):
        return self._continue_parse

    def WHIRLPOOL(self, macro: Macro, col: bpy.types.Collection):
        return self._continue_parse

    def GET_OR_SET(self, macro: Macro, col: bpy.types.Collection):
        return self._continue_parse

    # unused cmds, if someone put one in somehow would mess up flow
    def JUMP_LINK_PUSH_ARG(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def JUMP_N_TIMES(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def JUMP_LINK_IF(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def SKIP_IF(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def SKIP(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def SKIP_NOP(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")


@dataclass
class ColTri:
    type: Any
    verts: list[int]
    special_param: Any = None


class Collision(DataParser):
    """Data parser for collision files, use import_level_collision to setup"""

    def __init__(self, collision: list[str], scale: float, parse_target=DataParser._c_parsing):
        self.collision = collision  # will be none in binary
        self.scale = scale
        self.vertices = []
        # key=type,value=tri data
        self.tris: list[ColTri] = []
        self.type: str = None
        self.special_objects = []
        self.water_boxes = []
        super().__init__(parse_target=parse_target)

    def write_water_boxes(
        self, scene: bpy.types.Scene, parent: bpy.types.Object, name: str, col: bpy.types.Collection = None
    ):
        # water boxes don't work on hacker apparently
        if scene.fast64.sm64.importer.export_friendly and "HackerSM64" in scene.fast64.sm64.refresh_version:
            return
        for i, w in enumerate(self.water_boxes):
            Obj = bpy.data.objects.new("Empty", None)
            scene.collection.objects.link(Obj)
            parentObject(parent, Obj)
            Obj.name = "WaterBox_{}_{}".format(name, i)
            Obj.sm64_obj_type = "Water Box"
            x1 = eval_or_int(w[1]) / (self.scale)
            x2 = eval_or_int(w[3]) / (self.scale)
            z1 = eval_or_int(w[2]) / (self.scale)
            z2 = eval_or_int(w[4]) / (self.scale)
            y = eval_or_int(w[5]) / (self.scale)
            Xwidth = abs(x2 - x1) / (2)
            Zwidth = abs(z2 - z1) / (2)
            loc = [x2 - Xwidth, -(z2 - Zwidth), y - 1]
            Obj.location = loc
            scale = [Xwidth, Zwidth, 1]
            Obj.scale = scale

    def write_collision(
        self, scene: bpy.types.Scene, name: str, parent: bpy.types.Object, col: bpy.types.Collection = None
    ):
        if not col:
            col = scene.collection
        self.write_water_boxes(scene, parent, name, col)
        mesh = bpy.data.meshes.new(f"{name} data")
        mesh.from_pydata(self.vertices, [], [tri.verts for tri in self.tris])
        obj = bpy.data.objects.new(f"{name} mesh", mesh)
        col.objects.link(obj)
        obj.ignore_render = True
        if parent:
            parentObject(parent, obj)
        # look into making this better
        rotate_object(-90, obj, world=1)
        bpy.context.view_layer.objects.active = obj
        max = len(obj.data.polygons)
        col_materials: dict[str, "mat_index"] = dict()
        for i, (bpy_tri, col_tri) in enumerate(zip(obj.data.polygons, self.tris)):
            if col_tri.type not in col_materials:
                bpy.ops.object.create_f3d_mat()  # the newest mat should be in slot[-1]
                mat = obj.data.materials[-1]
                col_materials[col_tri.type] = len(obj.data.materials) - 1
                # fix this
                mat.collision_type_simple = "Custom"
                mat.collision_custom = col_tri.type
                mat.name = "Sm64_Col_Mat_{}".format(col_tri.type)
                # Just to give some variety
                mat.f3d_mat.default_light_color = [a / 255 for a in (hash(id(int(i))) & 0xFFFFFFFF).to_bytes(4, "big")]
                if col_tri.special_param is not None:
                    mat.use_collision_param = True
                    mat.collision_param = col_tri.special_param
                # I don't think I care about this. It makes program slow
                # with bpy.context.temp_override(material=mat):
                # bpy.ops.material.update_f3d_nodes()
            bpy_tri.material_index = col_materials[col_tri.type]
        return obj

    def parse_collision(self):
        self.parse_stream(self.collision, 0)

    def parse_collision_binary(self, bin_file: BinaryIO, entry_id: int):
        # can't use the generic parser since this uses a cmd_len -> dat array format
        self.parsed_streams[entry_id] = (parser := Parser(bin_file))
        parser.head = entry_id
        cmd_name = self.binary_cmd_get(parser)
        if cmd_name == "COL_INIT":
            self.parse_vertices(parser)
        else:
            raise Exception("Collision init not detected at col start")
        self.parse_triangles(parser)
        while True:
            cmd_name = self.binary_cmd_get(parser)
            if cmd_name == "COL_END":
                return
            elif cmd_name == "COL_WATER_BOX_INIT":
                self.parse_water_boxes(parser)
            elif cmd_name == "COL_SPECIAL_INIT":
                self.parse_special_objects(parser)
            else:
                raise Exception("Unhandled collision type")

    def parse_special_objects(self, parser: Parser):
        # parsing this requires knowing all the special object presets, will get to later
        obj_nm = self.unpack_type(parser.cur_stream, parser.head, ">H", make_str=False)
        parser.advance_head(2)
        raise ParseException()
        # for i in range(obj_nm):
        #     args = self.unpack_type(parser.cur_stream, parser.head, ">h5H")
        #     parser.advance_head(12)
        #     self.COL_VERTEX(Macro("COL_WATER_BOX", args))

    def parse_water_boxes(self, parser: Parser):
        box_num = self.unpack_type(parser.cur_stream, parser.head, ">H", make_str=False)
        parser.advance_head(2)
        for i in range(box_num):
            args = self.unpack_type(parser.cur_stream, parser.head, ">h5H", make_str=False)
            parser.advance_head(12)
            self.COL_WATER_BOX(Macro("COL_WATER_BOX", args))

    def parse_vertices(self, parser: Parser):
        vtx_num = self.unpack_type(parser.cur_stream, parser.head, ">H", make_str=False)
        parser.advance_head(2)
        for i in range(vtx_num):
            args = self.unpack_type(parser.cur_stream, parser.head, ">3h", make_str=False)
            parser.advance_head(6)
            self.COL_VERTEX(Macro("COL_VERTEX", args))

    def parse_triangles(self, parser: Parser):
        while True:
            surf_type, tri_num = self.unpack_type(parser.cur_stream, parser.head, ">2H", make_str=False)
            # COL_TRI_STOP
            if surf_type == 0x41:
                parser.advance_head(2)
                return
            self.type = hex(surf_type)
            parser.advance_head(4)
            # special col types in vanilla
            if self.type in {0xE, 0x24, 0x25, 0x27, 0x2C, 0x2D}:
                cmd_len = 4
                cmd_suffix = "_SPECIAL"
            else:
                cmd_len = 3
                cmd_suffix = ""
            for i in range(tri_num):
                args = self.unpack_type(parser.cur_stream, parser.head, f">{cmd_len}H", make_str=False)
                parser.advance_head(cmd_len * 2)
                func = getattr(self, f"COL_TRI{cmd_suffix}")
                func(Macro(f"COL_TRI{cmd_suffix}", args))

    # MSB is cmd type, use cmd type to execute class specific logic for length
    # default is 2nd MSB is length, used in level scripts and geo layouts
    def binary_cmd_get(self, parser: Parser) -> tuple[int, int]:
        cmd_type = self.unpack_type(parser.cur_stream, parser.head, ">H", make_str=False)
        cmd_name = self.get_cmd_name(cmd_type)
        parser.advance_head(2)
        return cmd_name

    def get_cmd_name(self, cmd_type):
        col_cmds = {
            0x0040: "COL_INIT",
            0x0041: "COL_TRI_STOP",
            0x0042: "COL_END",
            0x0043: "COL_SPECIAL_INIT",
            0x0044: "COL_WATER_BOX_INIT",
        }
        return col_cmds.get(cmd_type)

    _skippable_cmds = {
        "COL_WATER_BOX_INIT",
        "COL_INIT",
        "COL_VERTEX_INIT",
        "COL_SPECIAL_INIT",
        "COL_TRI_STOP",
    }

    def COL_VERTEX(self, macro: Macro):
        self.vertices.append([eval_or_int(v) / self.scale for v in macro.args])
        return self._continue_parse

    def COL_TRI_INIT(self, macro: Macro):
        self.type = macro.args[0]
        return self._continue_parse

    def COL_TRI(self, macro: Macro):
        self.tris.append(ColTri(self.type, [eval_or_int(a) for a in macro.args]))
        return self._continue_parse

    def COL_TRI_SPECIAL(self, macro: Macro):
        self.tris.append(
            ColTri(self.type, [eval_or_int(a) for a in macro.args[0:3]], special_param=eval_or_int(macro.args[3]))
        )
        return self._continue_parse

    def COL_END(self, macro: Macro):
        return self._break_parse

    def COL_WATER_BOX(self, macro: Macro):
        self.water_boxes.append(macro.args)
        return self._continue_parse

    # not written out currently
    def SPECIAL_OBJECT(self, macro: Macro):
        self.special_objects.append((*macro.args, 0, 0))
        return self._continue_parse

    def SPECIAL_OBJECT_WITH_YAW(self, macro: Macro):
        self.special_objects.append((*macro.args, 0))
        return self._continue_parse

    def SPECIAL_OBJECT_WITH_YAW_AND_PARAM(self, macro: Macro):
        self.special_objects.append(macro.args)
        return self._continue_parse


class SM64_Material(Mat):
    """Holds parsed material data to be written out to fast64 f3d materials with method apply_material_settings"""

    def load_texture(self, force_new_tex: bool, textures: dict, path: Path, tex: Texture):
        if not tex:
            return None
        # TODO
        # for some reason I can't get the parsing target to be what I want, so read props instead
        # would like for this to be better
        if bpy.context.scene.fast64.sm64.importer.import_target == "Binary":
            return self.load_texture_array(force_new_tex, textures, path, tex, DataParser._binary_parsing)
        else:
            tex_img = textures.get(tex.tex_img)
        if tex_img and "#include" in tex_img[0]:
            return self.load_texture_png(force_new_tex, textures, path, tex)
        elif tex_img:
            return self.load_texture_array(force_new_tex, textures, path, tex)
        else:
            print(f"No tex_img found for tex {tex}")

    def load_texture_png(self, force_new_tex: bool, textures: dict, path: Path, tex: Texture):
        tex_img = textures.get(tex.tex_img)[0].split("/")[-1]
        tex_img = tex_img.replace("#include ", "").replace('"', "").replace("'", "").replace("inc.c", "png")
        image = bpy.data.images.get(tex_img)
        if not image or force_new_tex:
            tex_img = textures.get(tex.tex_img)[0]
            tex_img = tex_img.replace("#include ", "").replace('"', "").replace("'", "").replace("inc.c", "png")
            # deal with duplicate pathing (such as /actors/actors etc.)
            Extra = path.relative_to(Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path)))
            for e in Extra.parts:
                tex_img = tex_img.replace(e + "/", "")
            # deal with actor import path not working for shared textures
            if "textures" in tex_img:
                fp = Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path)) / tex_img
            else:
                fp = path / tex_img
            return bpy.data.images.load(filepath=str(fp))
        else:
            return image

    def apply_PBSDF_Mat(self, mat: bpy.types.Material, textures: dict, tex_path: Path, layer: int, tex: Texture):
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        pbsdf = nodes.get("Principled BSDF")
        if not pbsdf:
            return
        tex_node = nodes.new("ShaderNodeTexImage")
        links.new(pbsdf.inputs[0], tex_node.outputs[0])  # base color
        links.new(pbsdf.inputs[21], tex_node.outputs[1])  # alpha color
        image = self.load_texture(bpy.context.scene.fast64.sm64.importer.force_new_tex, textures, tex_path, tex)
        if image:
            tex_node.image = image
        if int(layer) > 4:
            mat.blend_method == "BLEND"

    def apply_material_settings(self, mat: bpy.types.Material, textures: dict, tex_path: Path, layer: int):
        self.set_texture_tile_mapping()

        if bpy.context.scene.fast64.sm64.importer.as_obj:
            return self.apply_PBSDF_Mat(mat, textures, tex_path, layer, self.tex0)

        f3d = mat.f3d_mat

        f3d.draw_layer.sm64 = layer
        self.set_register_settings(mat, f3d)
        self.set_textures(f3d, textures, tex_path)

        # manually call node update for speed
        mat.f3d_update_flag = True
        update_node_values_of_material(mat, bpy.context)
        mat.f3d_mat.presetName = "Custom"
        mat.f3d_update_flag = False

    def set_textures(self, f3d: F3DMaterialProperty, textures: dict, tex_path: Path):
        self.set_tex_scale(f3d)
        if self.tex0 and self.set_tex:
            self.tex0.standardize_fields()
            self.set_tex_settings(
                f3d.tex0,
                self.load_texture(bpy.context.scene.fast64.sm64.importer.force_new_tex, textures, tex_path, self.tex0),
                self.tiles[0 + self.base_tile],
                self.tex0.tex_img,
            )
        if self.tex1 and self.set_tex:
            self.tex1.standardize_fields()
            self.set_tex_settings(
                f3d.tex1,
                self.load_texture(bpy.context.scene.fast64.sm64.importer.force_new_tex, textures, tex_path, self.tex1),
                self.tiles[1 + self.base_tile],
                self.tex1.tex_img,
            )


class SM64_F3D(DL):
    """DataParser for display lists, must gather sm64 specific data before parsing with get_f3d_data_from_model"""

    def __init__(self, scene, parse_target: int = DataParser._c_parsing):
        self.scene = scene
        self.props = scene.fast64.sm64.importer
        super().__init__(lastmat=SM64_Material(), parse_target=parse_target)

    def get_generic_textures(self, root_path: Path):
        """Add all the textures located in the /textures/ folder in decomp to Textures dict
        without this, Textures only contains the texture data found inside the model.inc.c file and the texture.inc.c file
        """
        # check that there is a textures directory
        if not (tex_path := root_path / "textures").exists():
            raise Exception("you must make project for /textures/ folder to exist")
        for t in [
            "cave.c",
            "effect.c",
            "fire.c",
            "generic.c",
            "grass.c",
            "inside.c",
            "machine.c",
            "mountain.c",
            "outside.c",
            "sky.c",
            "snow.c",
            "spooky.c",
            "water.c",
        ]:
            t = root_path / "bin" / t
            t = open(t, "r", newline="")
            tex = t
            # For textures, try u8, and s16 aswell
            self.Textures.update(
                get_data_types_from_file(
                    tex,
                    {
                        "Texture": [None, None],
                        "u8": [None, None],
                        "s16": [None, None],
                    },
                    macro_check=self.props.version,
                )
            )
            t.close()

    def get_f3d_data_from_model(self, start: str, last_mat: SM64_Material = None, layer: int = None):
        """recursively parse the display list in order to return a bunch of model data"""
        # inherit the mat based on the layer, or explicitly given one
        if last_mat:
            self.last_mat = last_mat
        elif layer:
            last_mat = self.last_mat_dict.get(layer, None)
            if last_mat:
                self.last_mat = last_mat
            else:
                self.last_mat = SM64_Material()
        self.parse_stream_DL(start)
        self.NewMat = 0
        self.StartName = start
        return [self.Verts, self.Tris]


@dataclass
class ModelDat:
    """holds model found by geo layout"""

    transform: Matrix
    layer: int
    model_name: str
    vertex_group_name: str = None
    switch_index: int = 0
    armature_obj: bpy.types.Object = None
    object: bpy.types.Object = None


class GraphNodes(DataParser):
    """base DataParser class for geo layouts and geo armatures, sets up object hierarchy with proper transforms for model in blender based on sm64 geo layouts"""

    # class data
    _skipped_geo_asm_funcs = {
        "geo_movtex_pause_control",
        "geo_movtex_draw_water_regions",
        "geo_movtex_draw_colored",
        "geo_movtex_update_horizontal",
        "geo_cannon_circle_base",
        "geo_envfx_main",
        "2150433248"  # geo_movtex_pause_control
        "2150436940"  # geo_movtex_draw_water_regions
        "2150064592",  # geo_envfx_main
    }
    _skippable_cmds = {
        "GEO_NOP_1A",
        "GEO_NOP_1E",
        "GEO_NOP_1F",
        "GEO_NODE_START",
        "GEO_NODE_SCREEN_AREA",
        "GEO_ZBUFFER",
        "GEO_RENDER_OBJ",
        "GEO_START",
    }

    # geo layouts use first byte to determine if a DL is added
    @staticmethod
    def cmd_rm_dl(format_data, cmd_bytes):
        if (cmd_bytes[1] & 0x80) != 0x80:
            format_data = format_data[:-1]
        return format_data

    # only used for cmd 0xA
    @staticmethod
    def cmd_rm_func(format_data, cmd_bytes):
        if cmd_bytes[1] != 1:
            format_data = format_data[:-1]
        return format_data

    # for binary importing, MSB, name, PackedFormat
    _geo_cmds_bin_format = {
        0x00: ("GEO_BRANCH_AND_LINK", PackedFormat(">BhL", (2,))),
        0x01: ("GEO_END", PackedFormat(">Bh")),
        0x02: ("GEO_BRANCH", PackedFormat(">BhL", (2,))),
        0x03: ("GEO_RETURN", PackedFormat(">Bh")),
        0x04: ("GEO_OPEN_NODE", PackedFormat(">Bh")),
        0x05: ("GEO_CLOSE_NODE", PackedFormat(">Bh")),
        0x06: ("GEO_ASSIGN_AS_VIEW", PackedFormat(">h")),
        0x07: ("GEO_UPDATE_NODE_FLAGS", PackedFormat(">Bh")),
        0x08: ("GEO_NODE_SCREEN_AREA", PackedFormat(">B5h")),
        0x09: ("GEO_NODE_ORTHO", PackedFormat(">Bh")),
        0x0A: ("GEO_CAMERA_FRUSTUM", PackedFormat(f">B3hL", tuple(), lambda x, y: GraphNodes.cmd_rm_func(x, y))),
        0x0B: ("GEO_START", PackedFormat(">Bh")),
        0x0C: ("GEO_ZBUFFER", PackedFormat(">Bh")),
        0x0D: ("GEO_RENDER_RANGE", PackedFormat(">B3h")),
        0x0E: ("GEO_SWITCH_CASE", PackedFormat(">BhL")),
        0x0F: ("GEO_CAMERA", PackedFormat(">B7hL")),
        0x10: (
            "GEO_TRANSLATE_ROTATE",
            PackedFormat(">B"),
        ),  # use a specific function to decode this one, format in dict is dummy
        0x11: (
            "GEO_TRANSLATE_NODE_BIN",
            PackedFormat(f">B3hL", (4,), lambda x, y: GraphNodes.cmd_rm_dl(x, y), make_str=False),
        ),
        0x12: (
            "GEO_ROTATION_NODE_BIN",
            PackedFormat(f">B3hL", (4,), lambda x, y: GraphNodes.cmd_rm_dl(x, y), make_str=False),
        ),
        0x13: ("GEO_ANIMATED_PART", PackedFormat(f">B3hL", (4,))),
        0x14: (
            "GEO_BILLBOARD_BIN",
            PackedFormat(f">B3hL", (4,), lambda x, y: GraphNodes.cmd_rm_dl(x, y), make_str=False),
        ),
        0x15: ("GEO_DISPLAY_LIST", PackedFormat(">BhL", (2,))),
        0x16: ("GEO_SHADOW", PackedFormat(">B3h")),
        0x17: ("GEO_RENDER_OBJ", PackedFormat(">Bh")),
        0x18: ("GEO_ASM", PackedFormat(">BhL")),
        0x19: ("GEO_BACKGROUND_BIN", PackedFormat(">BhL")),
        0x1A: ("GEO_NOP", PackedFormat(">B3h")),
        0x1B: ("GEO_COPY_VIEW", PackedFormat(">Bh")),
        0x1C: ("GEO_HELD_OBJECT", PackedFormat(">B3hL")),
        0x1D: ("GEO_SCALE", PackedFormat(f">BhlL", (3,), lambda x, y: GraphNodes.cmd_rm_dl(x, y), make_str=False)),
        0x1E: ("GEO_NOP", PackedFormat(">B3h")),
        0x1F: ("GEO_NOP", PackedFormat(">B7h")),
        0x20: ("GEO_CULLING_RADIUS", PackedFormat(">Bh")),
    }

    def __init__(
        self,
        geo_layouts: dict[geo_name:str, geo_data : list[str]],
        scene: bpy.types.Scene,
        name: str,
        col: bpy.types.Collection,
        parent_bone: bpy.types.Bone = None,
        geo_parent: GeoArmature = None,
        stream: list[Any] = None,
        parse_target: int = DataParser._c_parsing,
    ):
        self.geo_layouts = geo_layouts
        self.models = []
        self.children = []
        self.scene = scene
        self.props = scene.fast64.sm64.importer
        self.banks = get_bank_loads()
        if not stream:
            stream = list()
        self.stream = stream
        self.parent_transform = transform_mtx_blender_to_n64().inverted()
        self.last_transform = transform_mtx_blender_to_n64().inverted()
        self.name = name
        self.col = col
        super().__init__(parent=geo_parent, parse_target=parse_target)

    # pick the right subclass given contents of geo layout
    @staticmethod
    def new_subclass_dyn_bin(
        bin_file: BinaryIO,
        scene: bpy.types.Scene,
        entry_ptr: int,
        col: bpy.types.Collection = None,
        parse_target: int = DataParser._binary_parsing,
    ) -> Union[GeoLayout, GeoArmature]:
        if not bin_file:
            raise Exception(
                "no binary file included for geo export",
                "pass_linked_export",
            )
        offset = 0
        # hopefully this doesn't go on long
        while offset < 0x40:
            cmd_type = struct.unpack(">B", bin_file[entry_ptr + offset : entry_ptr + 1 + offset])[0]
            cmd_name, packed_cmd = GraphNodes._geo_cmds_bin_format.get(cmd_type)
            offset += packed_cmd.format_size + 1
            # this won't be perfect but it'll avoid having to parse the entire geo layout
            if cmd_name in {"GEO_ANIMATED_PART", "GEO_SHADOW", "GEO_SWITCH_CASE", "GEO_SCALE", "GEO_BILLBOARD_BIN"}:
                arm_obj = bpy.data.objects.new(f"geo_arm_{entry_ptr}", bpy.data.armatures.new(f"geo_arm_{entry_ptr}"))
                col.objects.link(arm_obj)
                geo_layout = GeoArmature(None, arm_obj, scene, entry_ptr, col=col, parse_target=parse_target)
                bpy.context.view_layer.objects.active = geo_layout.get_or_init_geo_armature()
                break
            elif (
                cmd_name
                in {
                    "GEO_END",
                    "GEO_BRANCH_AND_LINK",
                    "GEO_BRANCH",
                    "GEO_TRANSLATE_ROTATE",
                    "GEO_ROTATION_NODE_BIN",
                    "GEO_TRANSLATE_NODE_BIN",
                }
                or offset > 0x40
            ):
                geo_layout = GeoLayout(None, None, scene, entry_ptr, None, col=col, parse_target=parse_target)
                break

        geo_layout.bin_file = bin_file
        geo_layout.parse_geo_from_start(entry_ptr, 0)
        return geo_layout

    # pick the right subclass given contents of geo layout
    @staticmethod
    def new_subclass_dyn_c(
        geo_layout_dict: dict[geo_name:str, geo_data : list[str]],
        scene: bpy.types.Scene,
        layout_name: str,
        col: bpy.types.Collection = None,
        parse_target: int = DataParser._c_parsing,
    ) -> Union[GeoLayout, GeoArmature]:
        geo_layout = geo_layout_dict.get(layout_name)
        if not geo_layout:
            raise Exception(
                "Could not find geo layout {}".format(layout_name),
                "pass_linked_export",
            )
        for line in geo_layout:
            if "GEO_ANIMATED_PART" in line or "GEO_SWITCH_CASE" in line:
                name = f"Actor {layout_name}"
                arm_obj = bpy.data.objects.new(name, bpy.data.armatures.new(name))
                col.objects.link(arm_obj)
                geo_armature = GeoArmature(geo_layout_dict, arm_obj, scene, layout_name, col, parse_target=parse_target)
                geo_armature.parse_armature(layout_name, scene.fast64.sm64.importer)
                return geo_armature
        else:
            geo_layout = GeoLayout(geo_layout_dict, None, scene, layout_name, None, col=col, parse_target=parse_target)
            geo_layout.parse_level_geo(layout_name)
            return geo_layout

    # parsing funcs
    def parse_geo_from_start(self, entry: str, depth: int):
        self.stream.append(entry)
        script_stream = self.get_new_stream(entry)
        self.parse_stream_from_start(script_stream, entry, depth)

    # if binary, entry is a int and self.scripts is None
    def get_new_stream(self, entry: Union[str, int]) -> Union[Sequence, None]:
        if type(entry) is str:
            return self.geo_layouts[entry]
        else:
            return None

    """
    binary parsing funcs:
        * run parse_stream_from_start(dat_stream, entry, *args) w/ dat_stream = None, entry = rom_ptr: int
        * binary_cmd_get(parser) -> cmd_name and cmd_format, update parser.head manually to advanced num bytes read
        * binary_cmd_unpack/f"_decode_cmd_{cmd_name.lower()}_bin"(parser, PackedFormat) -> cmd_args
        * parser head is advanced the length of PackedFormat! Make sure all bytes are read, even padding
        * call Macro function
    """

    def binary_cmd_get(self, parser: Parser) -> tuple[cmd_name:str, PackedFormat]:
        cmd_type = self.unpack_type(parser.cur_stream, parser.head, ">B", make_str=False)
        cmd_name, packed_cmd = self._geo_cmds_bin_format.get(cmd_type)
        first_word = self.unpack_type(parser.cur_stream, parser.head, ">4B", make_str=False)
        packed_cmd.edit_format(first_word)
        parser.advance_head(1)
        return cmd_name, packed_cmd

    def binary_cmd_unpack(self, parser: Parser, cmd_name: str, packed_fmt: PackedFormat) -> tuple[list, int]:
        cmd_args = self.unpack_type(parser.cur_stream, parser.head, packed_fmt, ret_iterable=True)
        return cmd_args, packed_fmt.format_size

    def fix_bin_cmd_dls(self, macro: Macro) -> Macro:
        if (macro.args[0] & 0x80) == 0x80:
            return macro
        else:
            return macro.partial(*macro.args, "NULL")

    # macro parsing helpers
    def parse_layer(self, layer: str) -> int:
        if not layer.isdigit():
            layer = Layers.get(layer)
            if not layer:
                layer = 1
        return layer

    @property
    def ordered_name(self) -> str:
        return f"{self.get_parser(self.stream[-1]).head:04}_{self.name}"

    @property
    def first_obj(self) -> bpy.types.Object:
        if self.root:
            return self.root
        for model in self.models:
            if model.object:
                return model.object
        for child in self.children:
            if root := child.first_obj:
                return root
        return None

    # this gets transformed by root transform
    def get_translation(self, trans_vector: Sequence):
        translation = [float(val) for val in trans_vector]
        return [translation[0], translation[2], -translation[1]]

    def get_rotation(self, rot_vector: Sequence):
        rotation = Euler((math.radians(float(val)) for val in rot_vector), "ZXY")
        return rotate_quat_n64_to_blender(rotation.to_quaternion()).to_euler("XYZ")

    def set_transform(self, geo_obj, translation: Sequence):
        raise Exception("you must call this function from a sublcass")

    def set_geo_type(self, geo_obj: bpy.types.Object, geo_type: str):
        raise Exception("you must call this function from a sublcass")

    def set_draw_layer(self, geo_obj: bpy.types.Object, layer: int):
        raise Exception("you must call this function from a sublcass")

    def make_root(self, name, *args):
        raise Exception("you must call this function from a sublcass")

    def setup_geo_obj(self, *args):
        raise Exception("you must call this function from a sublcass")

    def add_model(self, *args):
        raise Exception("you must call this function from a sublcass")

    # macro parsing
    def GEO_BRANCH_AND_LINK(self, macro: Macro, depth: int):
        if macro.args[-1]:
            self.parse_geo_from_start(macro.args[-1], depth)
        return self._continue_parse

    def GEO_BRANCH(self, macro: Macro, depth: int):
        if macro.args[-1]:
            self.parse_geo_from_start(macro.args[-1], depth)
        # arg 0 determines if you return and continue or end after the branch
        if eval_or_int(macro.args[0]):
            return self._continue_parse
        else:
            return self._break_parse

    def GEO_END(self, macro: Macro, depth: int):
        self.stream = None
        return self._break_parse

    def GEO_RETURN(self, macro: Macro, depth: int):
        self.stream.pop()
        return self._break_parse

    def GEO_CLOSE_NODE(self, macro: Macro, depth: int):
        return self._break_parse

    def GEO_DISPLAY_LIST(self, macro: Macro, depth: int):
        # translation, rotation, layer, model
        model = macro.args[-1]
        if model != "NULL":
            geo_obj = self.add_model(
                ModelDat(self.parent_transform, macro.args[0], model), "display_list", self.display_list, macro.args[1]
            )
        self.set_transform(geo_obj, self.parent_transform)
        return self._continue_parse

    def GEO_BILLBOARD_WITH_PARAMS_AND_DL(self, macro: Macro, depth: int):
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform

        model = macro.args[-1]
        if model != "NULL":
            geo_obj = self.add_model(
                ModelDat(self.last_transform, macro.args[0], model), "billboard", self.billboard, macro.args[0]
            )
        else:
            geo_obj = self.setup_geo_obj("billboard", self.billboard, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self._continue_parse

    def GEO_BILLBOARD_WITH_PARAMS(self, macro: Macro, depth: int):
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform

        geo_obj = self.setup_geo_obj("billboard", self.billboard, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self._continue_parse

    def GEO_BILLBOARD(self, macro: Macro, depth: int):
        self.setup_geo_obj("billboard", self.billboard, macro.args[0])
        return self._continue_parse

    def GEO_BILLBOARD_BIN(self, macro: Macro, depth: int):
        return self.GEO_BILLBOARD_WITH_PARAMS_AND_DL(self.fix_bin_cmd_dls(macro), depth)

    def GEO_ANIMATED_PART(self, macro: Macro, depth: int):
        # layer, translation, DL
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform
        model = macro.args[-1]

        if model != "NULL" and model != 0:
            geo_obj = self.add_model(
                ModelDat(self.last_transform, macro.args[0], model), "bone", self.animated_part, macro.args[0]
            )
        else:
            geo_obj = self.setup_geo_obj("bone", self.animated_part, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self._continue_parse

    def GEO_ROTATION_NODE_BIN(self, macro: Macro, depth: int):
        return self.GEO_ROTATE_WITH_DL(self.fix_bin_cmd_dls(macro), depth)

    def GEO_ROTATION_NODE(self, macro: Macro, depth: int):
        geo_obj = self.GEO_ROTATE(macro, depth)
        if geo_obj:
            self.set_geo_type(geo_obj, self.rotate)
        return self._continue_parse

    def GEO_ROTATE(self, macro: Macro, depth: int):
        transform = Matrix.LocRotScale(Vector(), self.get_rotation(macro.args[1:4]), Vector((1, 1, 1)))
        self.last_transform = self.parent_transform @ transform
        return self.setup_geo_obj("rotate", self.translate_rotate, macro.args[0])

    def GEO_ROTATION_NODE_WITH_DL(self, macro: Macro, depth: int):
        geo_obj = self.GEO_ROTATE_WITH_DL(macro, depth)
        return self._continue_parse

    def GEO_ROTATE_WITH_DL(self, macro: Macro, depth: int):
        transform = Matrix.LocRotScale(Vector(), self.get_rotation(macro.args[1:4]), Vector((1, 1, 1)))
        self.last_transform = self.parent_transform @ transform

        model = macro.args[-1]
        if model != "NULL":
            geo_obj = self.add_model(
                ModelDat(self.last_transform, macro.args[0], model), "rotate", self.translate_rotate, macro.args[0]
            )
        else:
            geo_obj = self.setup_geo_obj("rotate", self.translate_rotate, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return geo_obj

    def _decode_cmd_geo_translate_rotate_bin(self, packed_fmt: PackedFormat, parser: Parser):
        cmd_flags = self.unpack_type(parser.cur_stream, parser.head, ">B")
        # translate rotate
        if (cmd_flags & 0x30) == 0x00:
            packed_fmt = PackedFormat(">B6h")
            cmd_name = "GEO_TRANSLATE_ROTATE"
        # translate
        elif (cmd_flags & 0x10) == 0x10:
            packed_fmt = PackedFormat(">B3h")
            cmd_name = "GEO_TRANSLATE"
        # rotate
        elif (cmd_flags & 0x20) == 0x20:
            packed_fmt = PackedFormat(">B3h")
            cmd_name = "GEO_ROTATE"
        # rotate_y
        elif cmd_flags & 0x30:
            packed_fmt = PackedFormat(">Bh")
            cmd_name = "GEO_ROTATE_Y"
        # has_dl
        if (cmd_flags & 0x80) == 0x80:
            packed_fmt.format_str += "L"
            packed_fmt.ptr_indices = tuple(len(format_str - 1))
            cmd_name += "_WITH_DL"
        cmd_args = self.unpack_type(parser.cur_stream, parser.head, packed_fmt)
        return cmd_name, cmd_args, packed_fmt

    # Build a matrix that rotates around the z axis, then the x axis, then the y axis, and then translates and multiplies.
    def GEO_TRANSLATE_ROTATE_WITH_DL(self, macro: Macro, depth: int):
        transform = Matrix.LocRotScale(
            self.get_translation(macro.args[1:4]), self.get_rotation(macro.args[4:7]), Vector((1, 1, 1))
        )
        self.last_transform = self.parent_transform @ transform

        model = macro.args[-1]
        if model != "NULL":
            geo_obj = self.add_model(
                ModelDat(self.last_transform, macro.args[0], model),
                "trans/rotate",
                self.translate_rotate,
                macro.args[0],
            )
        else:
            geo_obj = self.setup_geo_obj("trans/rotate", self.translate_rotate, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self._continue_parse

    def GEO_TRANSLATE_ROTATE(self, macro: Macro, depth: int):
        transform = Matrix.LocRotScale(
            self.get_translation(macro.args[1:4]), self.get_rotation(macro.args[1:4]), Vector((1, 1, 1))
        )
        self.last_transform = self.parent_transform @ transform

        geo_obj = self.setup_geo_obj("trans/rotate", self.translate_rotate, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self._continue_parse

    def GEO_TRANSLATE_WITH_DL(self, macro: Macro, depth: int):
        geo_obj = self.GEO_TRANSLATE_NODE_WITH_DL(macro, depth)
        if geo_obj:
            self.set_geo_type(geo_obj, self.translate_rotate)
        return self._continue_parse

    def GEO_TRANSLATE_NODE_WITH_DL(self, macro: Macro, depth: int):
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform

        model = macro.args[-1]
        if model != "NULL":
            geo_obj = self.add_model(
                ModelDat(self.last_transform, macro.args[0], model), "translate", self.translate, macro.args[0]
            )
        else:
            geo_obj = self.setup_geo_obj("translate", self.translate, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return geo_obj

    def GEO_TRANSLATE(self, macro: Macro, depth: int):
        obj = self.GEO_TRANSLATE_NODE(macro, depth)
        if obj:
            self.set_geo_type(geo_obj, self.translate_rotate)
        return self._continue_parse

    def GEO_TRANSLATE_NODE_BIN(self, macro: Macro, depth: int):
        return self.GEO_TRANSLATE_NODE_WITH_DL(self.fix_bin_cmd_dls(macro), depth)

    def GEO_TRANSLATE_NODE(self, macro: Macro, depth: int):
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform
        geo_obj = self.setup_geo_obj("translate", self.translate, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return geo_obj

    def GEO_SCALE_WITH_DL(self, macro: Macro, depth: int):
        scale = eval_or_int(macro.args[1]) / 0x10000
        self.last_transform = scale * self.last_transform
        model = macro.args[-1]
        geo_obj = self.add_model(ModelDat(self.last_transform, macro.args[0], macro.args[-1]))
        self.set_transform(geo_obj, self.last_transform)
        return self._continue_parse

    # This should probably do something but I haven't coded it in yet
    def GEO_COPY_VIEW(self, macro: Macro, depth: int):
        return self._continue_parse

    def GEO_ASSIGN_AS_VIEW(self, macro: Macro, depth: int):
        return self._continue_parse

    def GEO_UPDATE_NODE_FLAGS(self, macro: Macro, depth: int):
        return self._continue_parse

    def GEO_NODE_ORTHO(self, macro: Macro, depth: int):
        return self._continue_parse

    # These need special bhv for each type
    def GEO_ASM(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_CULLING_RADIUS(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_HELD_OBJECT(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_SCALE(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_SWITCH_CASE(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_SHADOW(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_CAMERA(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_CAMERA_FRUSTUM(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_CAMERA_FRUSTUM_WITH_FUNC(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_BACKGROUND(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_BACKGROUND_COLOR(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")


class GeoLayout(GraphNodes):
    switch = "Switch"
    translate_rotate = "Geo Translate/Rotate"
    translate = "Geo Translate Node"
    rotate = "Geo Rotation Node"
    billboard = "Geo Billboard"
    display_list = "Geo Displaylist"
    shadow = "Custom"
    asm = "Geo ASM"
    scale = "Geo Scale"
    animated_part = "Geo Translate Node"
    custom = "Custom"

    def __init__(
        self,
        geo_layouts: dict,
        root: bpy.types.Object,
        scene: bpy.types.Scene,
        name: Union[str, int],
        area_root: bpy.types.Object,
        col: bpy.types.Collection = None,
        geo_parent: GeoLayout = None,
        stream: list[Any] = None,
        pass_args: dict = None,
        parse_target: int = DataParser._c_parsing,
    ):
        self.parent = root
        self.area_root = area_root  # for properties that can only be written to area
        self.root = root
        self.obj = None  # last object on this layer of the tree, will become parent of next child
        # undetermined args to pass on in dict
        if pass_args:
            self.pass_args = pass_args
        else:
            self.pass_args = dict()
        if not col:
            col = area_root.users_collection[0]
        else:
            col = col
        super().__init__(geo_layouts, scene, name, col, geo_parent=geo_parent, stream=stream, parse_target=parse_target)

    def set_transform(self, geo_obj: bpy.types.Object, transform: Matrix):
        if not geo_obj:
            return
        geo_obj.matrix_world = (
            geo_obj.matrix_world
            @ transform_matrix_to_bpy(transform)
            * (1 / self.scene.fast64.sm64.blender_to_sm64_scale)
        )

    def set_geo_type(self, geo_obj: bpy.types.Object, geo_cmd: str):
        geo_obj.sm64_obj_type = geo_cmd

    def set_draw_layer(self, geo_obj: bpy.types.Object, layer: int):
        geo_obj.draw_layer_static = str(self.parse_layer(layer))

    # make an empty node to act as the root of this geo layout
    # use this to hold a transform, or an actual cmd, otherwise rt is passed
    def make_root(self, name: str, parent_obj: bpy.types.Object, mesh: bpy.types.Mesh):
        self.obj = bpy.data.objects.new(name, mesh)
        self.col.objects.link(self.obj)
        # keep? I don't like this formulation
        if parent_obj:
            parentObject(parent_obj, self.obj, keep=0)
        return self.obj

    def setup_geo_obj(self, obj_name: str, geo_cmd: str, layer: int = None, mesh: bpy.types.Mesh = None):
        geo_obj = self.make_root(f"{self.ordered_name} {obj_name}", self.root, mesh)
        if geo_cmd:
            self.set_geo_type(geo_obj, geo_cmd)
        if layer:
            self.set_draw_layer(geo_obj, layer)
        return geo_obj

    def add_model(self, model_data: ModelDat, *args):
        self.models.append(model_data)
        # add placeholder mesh
        mesh = bpy.data.meshes.get("sm64_import_placeholder_mesh")
        if not mesh:
            mesh = bpy.data.meshes.new("sm64_import_placeholder_mesh")
        geo_obj = self.setup_geo_obj(model_data.model_name, None, layer=model_data.layer, mesh=mesh)
        geo_obj.ignore_collision = True
        model_data.object = geo_obj
        # check for mesh props
        if render_range := self.pass_args.get("render_range", None):
            geo_obj.use_render_range = True
            geo_obj.render_range = render_range
            del self.pass_args["render_range"]
        if culling_radius := self.pass_args.get("culling_radius", None):
            geo_obj.use_render_area = True
            geo_obj.culling_radius = culling_radius
            del self.pass_args["culling_radius"]
        return geo_obj

    def parse_level_geo(self, start: str):
        geo_layout = self.geo_layouts.get(start)
        if not geo_layout:
            raise Exception(
                "Could not find geo layout {} from levels/{}/{}geo.c".format(
                    start, self.props.level_name, self.props.level_prefix
                ),
                "pass_linked_export",
            )
        self.parse_geo_from_start(start, 0)

    def GEO_ASM(self, macro: Macro, depth: int):
        # envfx goes on the area root
        func = macro.args[-1]
        param = macro.args[-2]
        if "geo_envfx_main" in func:
            if not param or (param == "ENVFX_MODE_NONE" and self.props.export_friendly):
                return self._continue_parse
            elif any(param is enum_fx[0] for enum_fx in enumEnvFX):
                self.area_root.envOption = param
            else:
                self.area_root.envOption = "Custom"
                self.area_root.envType = param
        if func in self._skipped_geo_asm_funcs and self.props.export_friendly:
            return self._continue_parse
        geo_obj = self.setup_geo_obj("asm", self.asm)
        # probably will need to be overridden by each subclass
        asm = geo_obj.fast64.sm64.geo_asm
        asm.param = param
        asm.func = func
        return self._continue_parse

    def GEO_SCALE_BIN(self, macro: Macro, depth: int):
        macro = self.fix_bin_cmd_dls(macro)
        if macro.args[-1] != "NULL":
            return self.GEO_SCALE_WITH_DL(macro, depth)
        else:
            return self.GEO_SCALE(macro, depth)

    def GEO_SCALE(self, macro: Macro, depth: int):
        scale = eval_or_int(macro.args[1]) / 0x10000
        geo_obj = self.setup_geo_obj("scale", self.scale, macro.args[0])
        geo_obj.scale = (scale, scale, scale)
        return self._continue_parse

    # shadows aren't naturally supported but we can emulate them with custom geo cmds
    # change so this can be applied to mesh on root?
    def GEO_SHADOW(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("shadow empty", self.shadow)
        # custom cmds were changed and wrapped into a new update
        # its probably better to just make shadows a real geo cmd or have some generic custom cmd func
        # geo_obj.customGeoCommand = "GEO_SHADOW"
        # geo_obj.customGeoCommandArgs = ", ".join(macro.args)
        return self._continue_parse

    def GEO_SWITCH_CASE(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("switch", self.switch)
        # probably will need to be overridden by each subclass
        geo_obj.switchParam = eval_or_int(macro.args[-2])
        geo_obj.switchFunc = macro.args[-1]
        return self._continue_parse

    # can only apply type to area root
    def GEO_CAMERA(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[-8]
        return self._continue_parse

    def GEO_BACKGROUND_BIN(self, macro: Macro, depth: int):
        if macro.args[-1] != 0:
            self.GEO_BACKGROUND(macro.partial(*macro.args[1:]), depth)
        else:
            self.GEO_BACKGROUND_COLOR(macro.partial(*macro.args[1:]), depth)

    def GEO_BACKGROUND(self, macro: Macro, depth: int):
        level_root = self.area_root.parent
        # check if in enum
        background_id = macro.args[0]
        skybox_name = background_id.replace("BACKGROUND_", "")
        bg_enums = {enum.identifier for enum in level_root.bl_rna.properties["background"].enum_items}
        if skybox_name in bg_enums:
            level_root.background = skybox_name
        else:
            level_root.background = "CUSTOM"
            level_root.fast64.sm64.level.backgroundID = background_id
            # I don't have access to the bg segment, that is in level obj
            # level_root.fast64.sm64.level.backgroundSegment = "unavailable srry :("
            print("background segment not set, left at default srry")

        return self._continue_parse

    def GEO_BACKGROUND_COLOR(self, macro: Macro, depth: int):
        level_root = self.area_root.parent
        level_root.useBackgroundColor = True
        level_root.backgroundColor = read16bitRGBA(hexOrDecInt(macro.args[0]))
        return self._continue_parse

    # can only apply to meshes
    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        self.pass_args["render_range"] = [
            hexOrDecInt(rndr_range) / self.scene.fast64.sm64.blender_to_sm64_scale for rndr_range in macro.args[-2:]
        ]
        return self._continue_parse

    def GEO_CULLING_RADIUS(self, macro: Macro, depth: int):
        self.pass_args["culling_radius"] = hexOrDecInt(macro.args[-1]) / self.scene.fast64.sm64.blender_to_sm64_scale
        return self._continue_parse

    # make better
    def GEO_CAMERA_FRUSTUM(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[0]
        return self._continue_parse

    def GEO_CAMERA_FRUSTUM_WITH_FUNC(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[0]
        return self._continue_parse

    def GEO_OPEN_NODE(self, macro: Macro, depth: int):
        if self.obj:
            GeoChild = GeoLayout(
                self.geo_layouts,
                self.obj,
                self.scene,
                self.name,
                self.area_root,
                col=self.col,
                geo_parent=self,
                stream=self.stream,
                pass_args=self.pass_args,
            )
        else:
            GeoChild = GeoLayout(
                self.geo_layouts,
                self.root,
                self.scene,
                self.name,
                self.area_root,
                col=self.col,
                geo_parent=self,
                stream=self.stream,
                pass_args=self.pass_args,
            )
        GeoChild.parent_transform = self.last_transform
        GeoChild.last_transform = self.last_transform
        GeoChild.parse_stream(self.get_new_stream(self.stream[-1]), self.stream[-1], depth + 1)
        self.children.append(GeoChild)
        return self._continue_parse


class GeoArmature(GraphNodes):
    switch = "Switch"
    start = "Start"
    translate_rotate = "TranslateRotate"
    translate = "Translate"
    rotate = "Rotate"
    billboard = "Billboard"
    display_list = "DisplayList"
    shadow = "Shadow"
    asm = "Function"
    held_object = "HeldObject"
    scale = "Scale"
    render_area = "StartRenderArea"
    animated_part = "DisplayListWithOffset"
    custom = "Custom"

    def __init__(
        self,
        geo_layouts: dict,
        armature_obj: bpy.types.Armature,
        scene: bpy.types.Scene,
        name: Union[str, int],
        col: bpy.types.Collection,
        is_switch_child: bool = False,
        parent_bone: bpy.types.Bone = None,
        geo_parent: GeoArmature = None,
        switch_armatures: dict[int, bpy.types.Object] = None,
        stream: Any = None,
        parse_target: int = DataParser._c_parsing,
    ):
        self.armature = armature_obj
        self.parent_bone = None if not parent_bone else parent_bone.name
        self.bone = None
        self.is_switch_child = is_switch_child
        self.switch_index = 0
        # parent to this instead of parent bone for brief moment it will exist
        self.switch_option_bone: str = None
        if not switch_armatures:
            self.switch_armatures = dict()
        else:
            self.switch_armatures = switch_armatures
        super().__init__(geo_layouts, scene, name, col, geo_parent=geo_parent, stream=stream, parse_target=parse_target)

    @property
    def first_obj(self):
        if self.armature:
            return self.armature
        for model in self.models:
            if model.object:
                return model.object
        for child in self.children:
            if root := child.first_obj:
                return root
        return None

    def enter_edit_mode(self, geo_armature: bpy.types.Object):
        geo_armature.select_set(True)
        bpy.context.view_layer.objects.active = geo_armature
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)

    def get_or_init_geo_armature(self):
        # if not the first child, make a new armature object and switch option root bone
        if self.switch_index > 0 and not self.switch_armatures.get(self.switch_index, None):
            name = f"{self.ordered_name} switch_option"
            switch_armature = bpy.data.objects.new(name, bpy.data.armatures.new(name))
            self.col.objects.link(switch_armature)
            # offset the location
            switch_armature.location += Vector((2.0 * self.switch_index, 0, 0))
            self.switch_armatures[self.switch_index] = switch_armature

            self.enter_edit_mode(switch_armature)
            edit_bone = switch_armature.data.edit_bones.new(name)
            eb_name = edit_bone.name
            # give it a non zero length
            edit_bone.head = (0, 0, 0)
            edit_bone.tail = (0, 0, 0.1)
            bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
            switch_opt_bone = switch_armature.data.bones[eb_name]
            self.switch_option_bone = eb_name
            self.set_geo_type(switch_opt_bone, "SwitchOption")
            # add switch option and set to mesh override
            switch_bone = self.armature.data.bones.get(self.parent_bone, None)
            option = switch_bone.switch_options.add()
            option.switchType = "Mesh"
            option.optionArmature = switch_armature
        elif self.switch_armatures:
            switch_armature = self.switch_armatures.get(self.switch_index, self.armature)
        else:
            switch_armature = self.armature
        return switch_armature

    def set_transform(self, geo_bone: bpy.types.Bone, transform: Matrix):
        # only the position of the head really matters, so the tail
        # will take an ad hoc position of 1 above the head
        name = geo_bone.name
        self.enter_edit_mode(armature_obj := self.get_or_init_geo_armature())
        edit_bone = armature_obj.data.edit_bones.get(name, None)
        location = transform_matrix_to_bpy(transform).to_translation() * (
            1 / self.scene.fast64.sm64.blender_to_sm64_scale
        )
        edit_bone.head = location
        edit_bone.tail = location + Vector((0, 0, 1))
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        # due to blender ptr memes, swapping between edit and obj mode
        # will mutate an attr, because the data struct self.bones is rebuilt
        # or something idk, and now where the previous bone was is replaced by
        # a new one, so I must retrieve it again
        self.bone = armature_obj.data.bones[name]
        # set the rotation mode
        armature_obj.pose.bones[name].rotation_mode = "XYZ"
        if self.is_switch_child:
            self.switch_index += 1

    def set_geo_type(self, geo_bone: bpy.types.Bone, geo_cmd: str):
        geo_bone.geo_cmd = geo_cmd

    def set_draw_layer(self, geo_bone: bpy.types.Bone, layer: int):
        geo_bone.draw_layer = str(self.parse_layer(layer))

    def make_root(self, name: str):
        self.enter_edit_mode(armature_obj := self.get_or_init_geo_armature())
        edit_bone = armature_obj.data.edit_bones.new(name)
        eb_name = edit_bone.name
        # give it a non zero length
        edit_bone.head = (0, 0, 0)
        edit_bone.tail = (0, 0, 0.1)
        # use self.switch_option_bone as parent, this does not logically follow from sm64 graph
        # but is due to fast64 rules, where switch option acts as "virtual" bone in between child and parent
        if self.switch_option_bone or self.parent_bone:
            edit_bone.parent = armature_obj.data.edit_bones.get(self.switch_option_bone or self.parent_bone)
            self.switch_option_bone = None
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        self.bone = armature_obj.data.bones[eb_name]
        return self.bone

    def setup_geo_obj(self, obj_name: str, geo_cmd: str, layer: int = None):
        geo_bone = self.make_root(f"{self.ordered_name} {obj_name}")
        self.set_geo_type(geo_bone, geo_cmd)
        if layer:
            self.set_draw_layer(geo_bone, layer)
        return geo_bone

    def add_model(self, model_data: ModelDat, obj_name: str, geo_cmd: str, layer: int = None):
        self.models.append(model_data)
        model_data.vertex_group_name = f"{self.ordered_name} {obj_name} {model_data.model_name}"
        model_data.switch_index = self.switch_index
        return self.setup_geo_obj(f"{obj_name} {model_data.model_name}", geo_cmd, layer)

    def parse_armature(self, start: str, props: SM64_ImportProperties):
        geo_layout = self.geo_layouts.get(start)
        if not geo_layout:
            raise Exception(
                "Could not find geo layout {} from levels/{}/{}geo.c".format(
                    start, props.level_name, props.level_prefix
                )
            )
        bpy.context.view_layer.objects.active = self.get_or_init_geo_armature()
        self.parse_geo_from_start(start, 0)

    def GEO_ASM(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("asm", self.asm)
        if not macro.args[0].isdigit():
            print("could not convert geo asm arg")
        else:
            geo_obj.func_param = int(macro.args[-2])
        geo_obj.geo_func = macro.args[-1]
        return self._continue_parse

    def GEO_SHADOW(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("shadow", self.shadow)
        geo_bone.shadow_solidity = hexOrDecInt(macro.args[-2]) / 255
        geo_bone.shadow_scale = hexOrDecInt(macro.args[-1])
        return self._continue_parse

    # cmd not supported in fast64 for some reason?
    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        # don't bother tbh
        # geo_bone = self.setup_geo_obj("render_range", self.custom)
        # geo_bone.fast64.sm64.custom.dl_command = "GEO_RENDER_RANGE"
        # geo_bone.fast64.sm64.custom_geo_cmd_args = ",".join(macro.args[-2:])
        return self._continue_parse

    # can switch children have their own culling radius? does it have to
    # be on the root? this currently allows each independent geo to have one
    def GEO_CULLING_RADIUS(self, macro: Macro, depth: int):
        geo_armature = self.get_or_init_geo_armature()
        geo_armature.use_render_area = True  # cringe name, it is cull not render area
        geo_armature.culling_radius = float(macro.args[-1])
        return self._continue_parse

    def GEO_SWITCH_CASE(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("switch", self.switch)
        # probably will need to be overridden by each subclass
        geo_bone.func_param = eval_or_int(macro.args[-2])
        geo_bone.geo_func = macro.args[-1]
        return self._continue_parse

    def GEO_SCALE_BIN(self, macro: Macro, depth: int):
        macro = self.fix_bin_cmd_dls(macro)
        if macro.args[-1] != "NULL":
            return self.GEO_SCALE_WITH_DL(macro.partial(macro[1:]), depth)
        else:
            return self.GEO_SCALE(macro.partial(macro.args[0], macro.args[2]), depth)

    def GEO_SCALE_WITH_DL(self, macro: Macro, depth: int):
        scale = eval_or_int(macro.args[1]) / 0x10000
        self.last_transform = [(0, 0, 0), self.last_transform[1]]

        model = macro.args[-1]
        geo_obj = self.add_model(
            ModelDat((0, 0, 0), (0, 0, 0), macro.args[0], model, scale=scale),
            "scale",
            self.scale,
            macro.args[0],
        )
        self.set_transform(geo_obj, self.last_transform)
        return self._continue_parse

    def GEO_SCALE(self, macro: Macro, depth: int):
        scale = eval_or_int(macro.args[1]) / 0x10000

        geo_bone = self.setup_geo_obj("scale", self.scale, macro.args[0])
        geo_bone.geo_scale = scale
        return self._continue_parse

    # can be used as a container for several nodes under a single switch child
    def GEO_NODE_START(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("start", self.start, "1")
        return self._continue_parse

    # add some stuff here
    def GEO_HELD_OBJECT(self, macro: Macro, depth: int):
        return self._continue_parse

    def GEO_OPEN_NODE(self, macro: Macro, depth: int):
        if self.bone:
            is_switch_child = self.bone.geo_cmd == self.switch
            GeoChild = GeoArmature(
                self.geo_layouts,
                self.get_or_init_geo_armature(),
                self.scene,
                self.name,
                self.col,
                is_switch_child,
                parent_bone=self.bone,
                geo_parent=self,
                stream=self.stream,
                switch_armatures=self.switch_armatures if is_switch_child else None,
            )
        else:
            GeoChild = GeoArmature(
                self.geo_layouts,
                self.get_or_init_geo_armature(),
                self.scene,
                self.name,
                self.col,
                geo_parent=self,
                stream=self.stream,
            )
        GeoChild.parent_transform = self.last_transform
        GeoChild.last_transform = self.last_transform
        GeoChild.parse_stream(self.get_new_stream(self.stream[-1]), self.stream[-1], depth + 1)
        self.children.append(GeoChild)
        return self._continue_parse


# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------

# Helper and pre processing funcs


def get_all_aggregates(aggregate_path: Path, filenames: tuple[callable], root_path: Path) -> list[Path]:
    """parse aggregate files, and search for sm64 specific fast64 export name schemes"""
    if not aggregate_path or not aggregate_path.exists():
        return []
    version = bpy.context.scene.fast64.sm64.importer.version
    with open(aggregate_path, "r", newline="") as file:
        caught_files = parse_aggregate_file(file, filenames, root_path, aggregate_path, macro_check=version)
        # catch fast64 includes
        fast64 = parse_aggregate_file(
            file, (lambda path: "leveldata.inc.c" in path.name,), root_path, aggregate_path, macro_check=version
        )
        if fast64:
            with open(fast64[0], "r", newline="") as fast64_dat:
                caught_files.extend(
                    parse_aggregate_file(fast64_dat, filenames, root_path, aggregate_path, macro_check=version)
                )
    return caught_files


def get_level_name(level_arg: Union[int, str]) -> str:
    if type(level_arg) is not str or level_arg.isdigit():
        level_arg = eval_or_int(level_arg)
        return LEVEL_ID_NUMBERS.get(level_arg)
    else:
        return level_arg


def get_and_check_rom(scene: bpy.types.Scene) -> filepathIO:
    rom_path = Path(bpy.path.abspath(scene.fast64.sm64.import_rom))
    if not rom_path:
        return None
    import_rom_checks(rom_path)
    return rom_path


# Level script functions
def parse_level_script_binary(bin_file: BinaryIO, scene: bpy.types.Scene, col: bpy.types.Collection = None) -> Level:
    """given a rom, parse the level script from the level script start and entering level importer_props.level_name"""
    root = bpy.data.objects.new("Empty", None)
    if not col:
        scene.collection.objects.link(root)
    else:
        col.objects.link(root)
    props = scene.fast64.sm64.importer
    root.name = f"Level Root {props.level_name}"
    root.sm64_obj_type = "Level Root"
    lvl = Level(None, scene, root, DataParser._binary_parsing)
    # seg 2 loaded via asm, so update it now
    lvl.load_segment_two(bin_file)
    lvl.bin_file = bin_file
    entry = 0x108A10  # the expected value for SM64, will not work for roms that mess with this (basically none tbh)
    try:
        lvl.parse_level_script(entry, col=col)
    except Exception as exc:
        if type(exc) is not ParseException:
            raise exc
    return lvl


def parse_level_script_c(script_files: list[Path], scene: bpy.types.Scene, col: bpy.types.Collection = None) -> Level:
    """Given an aggregate scripts path, get a level object by parsing the script.c file from importer_props.entry"""
    props = scene.fast64.sm64.importer
    root = bpy.data.objects.new("Empty", None)
    if not col:
        scene.collection.objects.link(root)
    else:
        col.objects.link(root)
    root.name = f"Level Root {props.level_name}"
    root.sm64_obj_type = "Level Root"
    # Now parse the script and get data about the level
    # Store data in attribute of a level class then assign later and return class
    scripts = dict()
    for script_file in script_files:
        with open(script_file, "r", newline="") as script_file:
            scripts.update(
                get_data_types_from_file(script_file, {"LevelScript": ["(", ")"]}, macro_check=props.version)
            )
    lvl = Level(scripts, scene, root, DataParser._c_parsing)
    entry = props.entry.format(props.level_name)
    try:
        lvl.parse_level_script(entry, col=col)
    except Exception as exc:
        if type(exc) is not ParseException:
            raise exc
    return lvl


def parse_level_script(
    script_files: list[Path],
    decomp_path: Path,
    bin_path: Path,
    scene: bpy.types.Scene,
    col: bpy.types.Collection = None,
) -> Level:
    """generate level object given data containers (rom or aggregate script files)"""
    props = scene.fast64.sm64.importer
    if props.import_target == "C":
        return parse_level_script_c(
            [script_files, decomp_path / "levels" / "scripts.c"], scene, col=col
        )  # returns level class
    elif props.import_target == "Binary":
        with open(bin_path, "rb") as bin_file:
            bin_file = bin_file.read()
            return parse_level_script_binary(bin_file, scene, col=col)


def write_level_objects(lvl: Level, col_name: str = None, actor_models: dict[model_name, bpy.Types.Mesh] = None):
    for area in lvl.areas.values():
        area.place_objects(col_name=col_name, actor_models=actor_models)


# Geo Layout functions
def construct_geo_layouts_from_file(geo_paths: list[Path], root_path: Path) -> dict[geo_name:str, geo_data : list[str]]:
    """given a list of aggregate geo.c file, return cleaned up geo layouts in a dict"""
    geo_layout_files = []
    for path in geo_paths:
        geo_layout_files += get_all_aggregates(path, (lambda path: "geo.inc.c" in path.name,), root_path)
    if not geo_layout_files:
        return
    # because of fast64, these can be recursively defined (though I expect only a depth of one)
    for file in geo_layout_files:
        geo_layout_files.extend(get_all_aggregates(file, (lambda path: "geo.inc.c" in path.name,), root_path))
    geo_layout_data = {}  # stores cleaned up geo layout lines
    for geo_file in geo_layout_files:
        with open(geo_file, "r", newline="") as geo_file:
            geo_layout_data.update(
                get_data_types_from_file(
                    geo_file, {"GeoLayout": ["(", ")"]}, macro_check=bpy.context.scene.fast64.sm64.importer.version
                )
            )
    return geo_layout_data


def find_actor_models_from_model_ids(
    geo_paths: list[Path],
    model_ids: list[str],
    level: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    col: bpy.types.Collection = None,
) -> dict[model_id, GeoLayout]:
    """Parse geo_layouts with matching <model_ids> found in aggregate group_geo.c or level geo.c files"""
    geo_layout_dict = construct_geo_layouts_from_file(geo_paths, root_path)
    geo_layout_per_model: dict[model_id, GeoLayout] = dict()
    for model in model_ids:
        layout_name = level.loaded_geos.get(model, None)
        if not layout_name:
            # create a warning off of this somehow?
            print(f"could not find model {model}")
            continue
        try:
            geo_layout = GraphNodes.new_subclass_dyn_c(geo_layout_dict, scene, layout_name, col)
            geo_layout_per_model[model] = geo_layout
        except Exception as exc:
            if exc.args[1] == "pass_linked_export":
                print(exc)
            else:
                raise Exception(exc)
    return geo_layout_per_model


def find_actor_models_from_geo(
    geo_paths: list[Path],
    layout_name: str,
    scene: bpy.types.Scene,
    root_path: Path,
    col: bpy.types.Collection = None,
) -> GeoLayout:
    """Parse geo_layout <layout_name> found within aggregate group_geo.c file or level geo.c"""
    geo_layout_dict = construct_geo_layouts_from_file(geo_paths, root_path)
    return GraphNodes.new_subclass_dyn_c(geo_layout_dict, scene, layout_name, col)


def find_actor_models_binary(
    bin_file: BinaryIO,
    entry: int,
    scene: bpy.types.Scene,
    root_path: Path,
    col: bpy.types.Collection = None,
) -> GeoLayout:
    """Parse geo_layout <layout_name> found at entry rom offset"""
    return GraphNodes.new_subclass_dyn_bin(bin_file, scene, entry, col)


def find_level_models_from_geo(
    geo_paths: list[Path], lvl: Level, scene: bpy.types.Scene, root_path: Path, col_name: str = None
) -> Level:
    """Parse geo_layout based on area ptr found within aggregate group_geo.c file or level geo.c"""
    props = scene.fast64.sm64.importer
    geo_layout_dict = construct_geo_layouts_from_file(geo_paths, root_path)
    for area_index, area in lvl.areas.items():
        if col_name:
            col = create_collection(area.root.users_collection[0], col_name)
        else:
            col = None
        geo = GeoLayout(
            geo_layout_dict, area.root, scene, f"GeoRoot {props.level_name} {area_index}", area.root, col=col
        )
        geo.parse_level_geo(area.geo)
        area.geo_data = geo
    return lvl


def find_level_models_binary(lvl: Level, scene: bpy.types.Scene, root_path: Path, col_name: str = None) -> Level:
    """Parse geo_layout based on area ptr found within rom_file"""
    props = scene.fast64.sm64.importer
    for area_index, area in lvl.areas.items():
        lvl.load_segment_E(area_index)
        lvl.update_geo_ptr(area_index)
        if col_name:
            col = create_collection(area.root.users_collection[0], col_name)
        else:
            col = None
        geo = GeoLayout(
            None,
            area.root,
            scene,
            f"GeoRoot {props.level_name} {area_index}",
            area.root,
            col=col,
            parse_target=DataParser._binary_parsing,
        )
        geo.bin_file = lvl.bin_file
        try:
            geo.parse_geo_from_start(area.geo, 0)
        except Exception as exc:
            if type(exc) is not ParseException:
                raise exc
        area.geo_data = geo
    return lvl


# F3d data functions
def import_level_graphics(
    geo_paths: list[Path],
    lvl: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    aggregates: list[Path],
    cleanup: bool = False,
    col_name: str = None,
) -> Level:
    """import level graphics given aggregate geo.c and leveldata.c files, and a level object"""
    if lvl.props.import_target == "C":
        lvl = find_level_models_from_geo(geo_paths, lvl, scene, root_path, col_name=col_name)
        models = construct_model_data_from_file(aggregates, scene, root_path)
        # just a try, in case you are importing from something other than base decomp repo (like RM2C output folder)
        try:
            models.get_generic_textures(root_path)
        except:
            print("could not import genric textures, if this errors later from missing textures this may be why")
    elif lvl.props.import_target == "Binary":
        lvl = find_level_models_binary(lvl, scene, root_path, col_name=col_name)
        # dummy f3d_gbi for class initialization
        f3d_option = scene.f3d_type
        scene.f3d_type = "F3D"
        models = SM64_F3D(scene, DataParser._binary_parsing)
        models.bin_file = lvl.bin_file
        models.banks = lvl.banks
        scene.f3d_type = f3d_option
    lvl = write_level_to_bpy(lvl, scene, root_path, models, cleanup=cleanup)
    return lvl


def write_level_to_bpy(lvl: Level, scene: bpy.types.Scene, root_path: Path, f3d_dat: SM64_F3D, cleanup: bool = False):
    """write the gfx for a level given the level data, parsed geolayout and gathered f3d data"""
    for area_index, area in lvl.areas.items():
        write_geo_to_bpy(area.geo_data, scene, f3d_dat, root_path, dict(), cleanup=cleanup)
    return lvl


def write_geo_to_bpy(
    geo: GeoLayout,
    scene: bpy.types.Scene,
    f3d_dat: SM64_F3D,
    root_path: Path,
    meshes: dict[str, bpy.Types.Mesh],
    cleanup: bool = True,
) -> dict[str, bpy.Types.Mesh]:
    """from a parsed geo layout, parse f3d data and create all the meshes"""
    if geo.models:
        # create a mesh for each one.
        for model_data in geo.models:
            name = f"{model_data.model_name} data"
            layer = geo.parse_layer(model_data.layer)
            if meshes and name in meshes.keys():
                mesh = meshes[name]
                name = 0
            else:
                mesh = bpy.data.meshes.new(name)
                meshes[name] = mesh
                [verts, tris] = f3d_dat.get_f3d_data_from_model(model_data.model_name, layer=layer)
                # don't write empty models, delete empties with no children
                # potential mat errors if used for DL setup but current importer should account for that using last_mat system
                if tris:
                    mesh.from_pydata(verts, [], tris)
                elif not geo.children:
                    bpy.data.objects.remove(model_data.object)
                    model_data.object = None
                    meshes.pop(name)
                    continue

            # swap out placeholder mesh data
            model_data.object.data = mesh

            if name:
                apply_mesh_data(f3d_dat, model_data.object, mesh, str(layer), root_path, cleanup)
    if not geo.children:
        return meshes
    for g in geo.children:
        meshes = write_geo_to_bpy(g, scene, f3d_dat, root_path, meshes, cleanup=cleanup)
    return meshes


def write_armature_to_bpy(
    geo_armature: GeoArmature,
    scene: bpy.types.Scene,
    f3d_dat: SM64_F3D,
    root_path: Path,
    parsed_model_data: dict[str, bpy.Types.Mesh],
    cleanup: bool = True,
):
    """from a parsed geo armature, recurse armature and then join meshes to armature roots"""
    parsed_model_data = recurse_armature(geo_armature, scene, f3d_dat, root_path, parsed_model_data, cleanup=cleanup)

    def glob_models_in_arm(object_dict: dict, geo_armature: GeoArmature):
        for model_data in geo_armature.models:
            if not object_dict.get(model_data.armature_obj, None):
                object_dict[model_data.armature_obj] = [model_data.object]
            else:
                object_dict[model_data.armature_obj].append(model_data.object)
        if not geo_armature.children:
            return object_dict
        for arm in geo_armature.children:
            object_dict = glob_models_in_arm(object_dict, arm)
        return object_dict

    objects_by_armature = glob_models_in_arm(dict(), geo_armature)

    for armature_obj, objects in objects_by_armature.items():
        # I don't really know the specific override needed for this to work
        if len(objects) > 1:
            override = {**bpy.context.copy(), "selected_editable_objects": objects, "active_object": objects[0]}
            with bpy.context.temp_override(**override):
                bpy.ops.object.join()

        obj = objects[0]
        obj.location += armature_obj.location
        parentObject(armature_obj, obj, keep=1)
        obj.ignore_collision = True
        # armature deform
        mod = obj.modifiers.new("deform", "ARMATURE")
        mod.object = geo_armature.armature
    return parsed_model_data


def recurse_armature(
    geo_armature: GeoArmature,
    scene: bpy.types.Scene,
    f3d_dat: SM64_F3D,
    root_path: Path,
    parsed_model_data: dict[str, bpy.Types.Mesh],
    cleanup: bool = True,
):
    """from a parsed geo armature, parse f3d data and create meshes for armature"""
    if geo_armature.models:
        # create a mesh for each one
        for model_data in geo_armature.models:
            name = f"{model_data.model_name} data"
            layer = geo_armature.parse_layer(model_data.layer)
            if parsed_model_data and name in parsed_model_data.keys():
                mesh = parsed_model_data[name]
                name = 0
            else:
                mesh = bpy.data.meshes.new(name)
                model_data.mesh = mesh
                parsed_model_data[name] = mesh
                [verts, tris] = f3d_dat.get_f3d_data_from_model(model_data.model_name, layer=layer)
                mesh.from_pydata(verts, [], tris)

            obj = bpy.data.objects.new(f"{model_data.model_name} obj", mesh)

            obj.matrix_world = transform_matrix_to_bpy(model_data.transform) * (
                1 / scene.fast64.sm64.blender_to_sm64_scale
            )

            model_data.object = obj
            geo_armature.col.objects.link(obj)
            # vertex groups are shared with shared mesh data
            if model_data.vertex_group_name and name:
                vertex_group = obj.vertex_groups.new(name=model_data.vertex_group_name)
                vertex_group.add([vert.index for vert in obj.data.vertices], 1, "ADD")
            if model_data.switch_index:
                model_data.armature_obj = geo_armature.switch_armatures[model_data.switch_index]
            else:
                model_data.armature_obj = geo_armature.armature

            if name:
                apply_mesh_data(f3d_dat, obj, mesh, str(layer), root_path, cleanup)

    if not geo_armature.children:
        return parsed_model_data
    for arm in geo_armature.children:
        parsed_model_data = recurse_armature(arm, scene, f3d_dat, root_path, parsed_model_data, cleanup=cleanup)
    return parsed_model_data


def apply_mesh_data(
    f3d_dat: SM64_F3D, obj: bpy.types.Object, mesh: bpy.types.Mesh, layer: int, root_path: Path, cleanup: bool = False
):
    """apply the f3d material data to newly created mesh, textures, f3d mat props, vertex colors and UVs"""
    f3d_dat.apply_mesh_data(obj, mesh, layer, root_path, f3d_dat.props.force_new_tex)
    if cleanup:
        mesh = obj.data
        # clean up after applying dat
        mesh.validate()
        mesh.update(calc_edges=True)
        # final operators to clean stuff up
        # shade smooth
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.mode_set(mode="OBJECT")


def construct_model_data_from_file(aggregates: list[Path], scene: bpy.types.Scene, root_path: Path) -> SM64_F3D:
    """Parse a list of aggregate group.c leveldata.c files for f3d data and organize into F3D class"""
    model_files = []
    texture_files = []
    for dat_file in aggregates:
        model_files += get_all_aggregates(
            dat_file,
            (
                lambda path: "model.inc.c" in path.name,
                lambda path: path.match("*[0-9].inc.c"),  # deal with 1.inc.c files etc.
                lambda path: "painting.inc.c" in path.name,  # add way to deal with 1.inc.c filees etc.
                lambda path: "light.inc.c" in path.name,  # only in vanilla decomp in LLL for some reason
            ),
            root_path,
        )
        texture_files += get_all_aggregates(
            dat_file,
            (
                lambda path: "texture.inc.c" in path.name,
                lambda path: "textureNew.inc.c" in path.name,
            ),
            root_path,
        )
    # Get all modeldata in the level
    sm64_f3d_data = SM64_F3D(scene)
    for model_file in model_files:
        model_file = open(model_file, "r", newline="")
        construct_sm64_f3d_data_from_file(sm64_f3d_data, model_file)
    # Update file to have texture.inc.c textures, deal with included textures in the model.inc.c files aswell
    for texture_file in [*texture_files, *model_files]:
        with open(texture_file, "r", newline="") as texture_file:
            # For textures, try u8, and s16 aswell
            sm64_f3d_data.Textures.update(
                get_data_types_from_file(
                    texture_file,
                    {
                        "Texture": [None, None],
                        "u8": [None, None],
                        "s16": [None, None],
                    },
                    macro_check=sm64_f3d_data.props.version,
                )
            )
    return sm64_f3d_data


def construct_sm64_f3d_data_from_file(gfx: SM64_F3D, model_file: TextIO) -> SM64_F3D:
    """Update F3D class with all the relevant data types cleaned up and organized into appropriate attributes"""
    gfx_dat = get_data_types_from_file(
        model_file,
        {
            "Vtx": ["{", "}"],
            "Gfx": ["(", ")"],
            "Light_t": [None, None],
            "Ambient_t": [None, None],
            "Lights": [None, None],
        },
        macro_check=gfx.props.version,
        collated=True,
    )
    for key, value in gfx_dat.items():
        attr = getattr(gfx, key)
        attr.update(value)
    gfx.Textures.update(
        get_data_types_from_file(
            model_file,
            {
                "Texture": [None, None],
                "u8": [None, None],
                "s16": [None, None],
            },
            macro_check=gfx.props.version,
        )
    )
    return gfx


# Collision functions
def import_level_collision(
    aggregate: Path,
    lvl: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    cleanup: bool,
    col_name: str = None,
) -> Level:
    """import level collision given a level script"""
    if lvl.props.import_target == "C":
        lvl = find_collision_data_from_path(
            aggregate, lvl, scene, root_path
        )  # Now Each area has its collision file nicely formatted
    # in binary, the collision is at the bin_file, area.terrain ptr
    write_level_collision_to_bpy(lvl, scene, cleanup, col_name=col_name)
    return lvl


def import_actor_collision(
    aggregate: Path,
    props: SM64_ImportProperties,
    bin_file: BinaryIO,
    scene: bpy.types.Scene,
    col_ptr: Union[int, str],
    root_path: Path,
    cleanup: bool,
    col: bpy.types.Collection,
) -> Level:
    """import level collision given a level script"""
    if props.import_target == "C":
        collision_files = []
        for agg_path in aggregate:
            collision_files += get_all_aggregates(agg_path, (lambda path: "collision.inc.c" in path.name,), root_path)
        col_data = dict()
        for col_file in collision_files:
            if not os.path.isfile(col_file):
                continue
            with open(col_file, "r", newline="") as col_file:
                col_data.update(
                    get_data_types_from_file(col_file, {"Collision": ["(", ")"]}, macro_check=props.version)
                )
        # search for the area terrain from available collision data
        col_file = col_data.get(col_ptr, None)
        if not col_file:
            raise Exception(f"Collision {col_ptr} not found")
    else:
        col_file = col_ptr
    root_obj = bpy.data.objects.new(f"col obj {col_ptr}", None)
    col.objects.link(root_obj)
    # in binary, the collision is at the bin_file, area.terrain ptr
    write_collision_to_bpy(props, bin_file, scene, col_file, root_obj, f"col obj {col_ptr}", cleanup, col)


def write_level_collision_to_bpy(
    lvl: Level,
    scene: bpy.types.Scene,
    cleanup: bool,
    col_name: str = None,
    actor_models: dict[model_name, bpy.Types.Mesh] = None,
):
    """Write level collision data to blender given parsed collision file"""
    for area_index, area in lvl.areas.items():
        if lvl.props.import_target == "Binary":
            lvl.load_segment_E(area_index)
            lvl.update_col_ptr(area_index)
        if not col_name:
            col = area.root.users_collection[0]
        else:
            col = create_collection(area.root.users_collection[0], col_name)
        col_parser = write_collision_to_bpy(
            lvl.props,
            lvl.bin_file,
            scene,
            area.col_file,
            area.root,
            "SM64 {} Area {} Col".format(lvl.props.level_name, area_index),
            cleanup,
            col,
        )
        area.write_special_objects(col_parser.special_objects, col)


def write_collision_to_bpy(
    props: SM64_ImportProperties,
    bin_file: BinaryIO,
    scene: bpy.types.Scene,
    col_ptr: Union[int, CDataArray],
    root_obj: bpy.types.Object,
    name: str,
    cleanup: bool,
    col: bpy.types.Collection,
):
    """Write level collision data to blender given parsed collision file"""
    col_parser = Collision(col_ptr, scene.fast64.sm64.blender_to_sm64_scale)
    if props.import_target == "C":
        col_parser.parse_collision()
    else:
        try:
            col_parser.parse_collision_binary(bin_file, col_ptr)
        except Exception as exc:
            if type(exc) is not ParseException:
                raise exc
    obj = col_parser.write_collision(scene, name, root_obj, col)
    # final operators to clean stuff up
    if cleanup:
        obj.data.validate()
        obj.data.update(calc_edges=True)
        # shade smooth
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.mode_set(mode="OBJECT")
    return col_parser


def find_collision_data_from_path(aggregate: Path, lvl: Level, scene: bpy.types.Scene, root_path: Path) -> Level:
    """Parse collision data given an aggregate leveldata.c or group.c file"""
    collision_files = get_all_aggregates(aggregate, (lambda path: "collision.inc.c" in path.name,), root_path)
    col_data = dict()
    for col_file in collision_files:
        if not os.path.isfile(col_file):
            continue
        with open(col_file, "r", newline="") as col_file:
            col_data.update(
                get_data_types_from_file(col_file, {"Collision": ["(", ")"]}, macro_check=lvl.props.version)
            )
    # search for the area terrain from available collision data
    for area in lvl.areas.values():
        area.col_file = col_data.get(area.terrain, None)
        if not area.col_file:
            props = scene.fast64.sm64.importer
            raise Exception(
                f"Collision {area.terrain} not found in levels/{props.level_name}/{props.level_prefix}leveldata.c"
            )
    return lvl


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------


class SM64_ActImport(Operator):
    bl_label = "Import Actor"
    bl_idname = "wm.sm64_import_actor"
    bl_options = {"REGISTER", "UNDO"}

    cleanup: BoolProperty(name="Cleanup Mesh", default=1)

    def execute(self, context):
        scene = context.scene
        rt_col = context.collection
        props = scene.fast64.sm64.importer

        rom_path = get_and_check_rom(scene)
        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))

        group_prefix = props.group_prefix
        level_name = props.level_name
        level_prefix = props.level_prefix

        # add in common actor paths for actors that use stars or mario hat
        geo_paths = (
            decomp_path / "actors" / (group_prefix + "_geo.c"),
            decomp_path / "actors" / "common0_geo.c",
            decomp_path / "actors" / "common1_geo.c",
            decomp_path / "actors" / "group0_geo.c",
            decomp_path / "levels" / level_name / (level_prefix + "geo.c"),
        )
        model_data_paths = (
            decomp_path / "actors" / (group_prefix + ".c"),
            decomp_path / "actors" / "common0.c",
            decomp_path / "actors" / "common1.c",
            decomp_path / "actors" / "group0.c",
            decomp_path / "levels" / level_name / (level_prefix + "leveldata.c"),
        )

        if props.import_target == "C":
            # check if actor has collision data
            if props.col_data:
                import_actor_collision(
                    model_data_paths, props, None, scene, props.col_data, decomp_path, self.cleanup, rt_col
                )
            geo_layout = find_actor_models_from_geo(
                geo_paths, props.geo_layout, scene, decomp_path, col=rt_col
            )  # return geo layout class and write the geo layout
            models = construct_model_data_from_file(model_data_paths, scene, decomp_path)
        elif props.import_target == "Binary":
            # levels need to be parsed to get the rom bank loads, choose level object is used in
            lvl = parse_level_script(None, None, rom_path, scene, rt_col)
            # check if actor has collision data
            if props.col_data:
                import_actor_collision(
                    model_data_paths,
                    props,
                    lvl.bin_file,
                    scene,
                    lvl.seg2phys(props.col_data),
                    decomp_path,
                    self.cleanup,
                    rt_col,
                )
            entry = lvl.seg2phys(props.geo_layout_binary)
            geo_layout = find_actor_models_binary(
                lvl.bin_file, entry, scene, decomp_path, col=rt_col
            )  # return geo layout class and write the geo layout
            f3d_option = scene.f3d_type
            scene.f3d_type = "F3D"
            models = SM64_F3D(scene, DataParser._binary_parsing)
            models.bin_file = lvl.bin_file
            models.banks = lvl.banks
            scene.f3d_type = f3d_option

        # just a try, in case you are importing from not the base decomp repo
        try:
            models.get_generic_textures(decomp_path)
        except:
            print("could not import genric textures, if this errors later from missing textures this may be why")
        if type(geo_layout) == GeoLayout:
            write_geo_to_bpy(geo_layout, scene, models, decomp_path, {}, cleanup=self.cleanup)
        else:
            write_armature_to_bpy(geo_layout, scene, models, decomp_path, {}, cleanup=self.cleanup)
        return {"FINISHED"}


def get_operator_paths(props: SM64_ImportProperties, decomp_path: Path) -> Tuple[leveldat_path, script_path, geo_path]:
    level = decomp_path / "levels" / props.level_name
    script = level / (props.level_prefix + "script.c")
    geo = level / (props.level_prefix + "geo.c")
    leveldat = level / (props.level_prefix + "leveldata.c")
    return (leveldat, script, geo)


class SM64_LvlImport(Operator):
    bl_label = "Import Level"
    bl_idname = "wm.sm64_import_level"

    cleanup = False

    def execute(self, context):
        pr = cProfile.Profile()
        pr.enable()
        scene = context.scene
        props = scene.fast64.sm64.importer

        col = context.collection
        if props.use_collection:
            obj_col = f"{props.level_name} obj"
            gfx_col = f"{props.level_name} gfx"
            col_col = f"{props.level_name} col"
        else:
            obj_col = gfx_col = col_col = None

        rom_path = get_and_check_rom(scene)
        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level_data_path, script_path, geo_path = get_operator_paths(props, decomp_path)
        lvl = parse_level_script(script_path, decomp_path, rom_path, scene, col)

        if props.import_linked_actors and props.import_target == "C":
            unique_model_ids = {model for model in lvl.loaded_geos.keys()}
            unique_model_ids.update({model for model in lvl.loaded_dls.keys()})
            unique_model_ids.update({object.model for area in lvl.areas.values() for object in area.objects})

            geo_actor_paths = [
                *(
                    decomp_path / "actors" / (linked_group.group_prefix + "_geo.c")
                    for linked_group in props.linked_groups
                ),
                geo_path,
            ]
            model_actor_paths = [
                *(decomp_path / "actors" / (linked_group.group_prefix + ".c") for linked_group in props.linked_groups),
                level_data_path,
            ]
            actor_col = create_collection(col, "linked actors col")
            actor_geo_layouts: dict[model_id, GeoLayout] = find_actor_models_from_model_ids(
                geo_actor_paths, unique_model_ids, lvl, scene, decomp_path, col=actor_col
            )
            model_data = construct_model_data_from_file(model_actor_paths, scene, decomp_path)
            # just a try, in case you are importing from not the base decomp repo
            try:
                model_data.get_generic_textures(decomp_path)
            except:
                print("could not import genric textures, if this errors later from missing textures this may be why")
            meshes = {}
            for model, geo_layout in actor_geo_layouts.items():
                if type(geo_layout) == GeoLayout:
                    meshes = write_geo_to_bpy(geo_layout, scene, model_data, decomp_path, meshes, cleanup=self.cleanup)
                else:
                    meshes = write_armature_to_bpy(
                        geo_layout, scene, model_data, decomp_path, meshes, cleanup=self.cleanup
                    )
                # update model to be root obj of geo
                actor_geo_layouts[model] = geo_layout.first_obj

            lvl = import_level_collision(level_data_path, lvl, scene, decomp_path, self.cleanup, col_name=col_col)
            write_level_objects(lvl, col_name=obj_col, actor_models=actor_geo_layouts)
            # actor_col.hide_render = True
            # actor_col.hide_viewport = True
        else:
            write_level_objects(lvl, col_name=obj_col)
            lvl = import_level_collision(level_data_path, lvl, scene, decomp_path, self.cleanup, col_name=col_col)
        lvl = import_level_graphics(
            [geo_path], lvl, scene, decomp_path, [level_data_path], cleanup=self.cleanup, col_name=gfx_col
        )
        pr.disable()
        s = io.StringIO()
        sortby = SortKey.CUMULATIVE
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats(20)
        print(s.getvalue())
        return {"FINISHED"}


class SM64_LvlGfxImport(Operator):
    bl_label = "Import Gfx"
    bl_idname = "wm.sm64_import_level_gfx"

    cleanup = False

    def execute(self, context):
        scene = context.scene
        props = scene.fast64.sm64.importer

        col = context.collection
        if props.use_collection:
            gfx_col = f"{props.level_name} gfx"
        else:
            gfx_col = None

        rom_path = get_and_check_rom(scene)
        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        model_data_path, script_path, geo_path = get_operator_paths(props, decomp_path)
        lvl = parse_level_script(script_path, decomp_path, rom_path, scene, gfx_col)
        lvl = import_level_graphics(
            [geo_path], lvl, scene, decomp_path, [model_data_path], cleanup=self.cleanup, col_name=gfx_col
        )
        return {"FINISHED"}


class SM64_LvlColImport(Operator):
    bl_label = "Import Collision"
    bl_idname = "wm.sm64_import_level_col"

    cleanup = True

    def execute(self, context):
        scene = context.scene
        props = scene.fast64.sm64.importer

        col = context.collection
        if props.use_collection:
            col_col = f"{props.level_name} collision"
        else:
            col_col = None

        rom_path = get_and_check_rom(scene)
        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level_data_path, script_path, _ = get_operator_paths(props, decomp_path)
        lvl = parse_level_script(script_path, decomp_path, rom_path, scene, col_col)
        lvl = import_level_collision(level_data_path, lvl, scene, decomp_path, self.cleanup, col_name=col_col)
        return {"FINISHED"}


class SM64_ObjImport(Operator):
    bl_label = "Import Objects"
    bl_idname = "wm.sm64_import_object"

    def execute(self, context):
        scene = context.scene
        props = scene.fast64.sm64.importer

        col = context.collection
        if props.use_collection:
            obj_col = f"{props.level_name} objs"
        else:
            obj_col = None

        rom_path = get_and_check_rom(scene)
        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        _, script_path, _ = get_operator_paths(props, decomp_path)
        lvl = parse_level_script(script_path, decomp_path, rom_path, scene, obj_col)
        write_level_objects(lvl, col_name=obj_col)
        return {"FINISHED"}


# ------------------------------------------------------------------------
#    Props
# ------------------------------------------------------------------------


class SM64_AddGroup(bpy.types.Operator):
    bl_idname = "scene.add_group"
    bl_label = "Add Group"
    option: bpy.props.IntProperty()

    def execute(self, context):
        prop = context.scene.fast64.sm64.importer
        prop.linked_groups.add()
        prop.linked_groups.move(len(prop.linked_groups) - 1, self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class SM64_RemoveGroup(bpy.types.Operator):
    bl_idname = "scene.remove_group"
    bl_label = "Remove Group"
    option: bpy.props.IntProperty()

    def execute(self, context):
        prop = context.scene.fast64.sm64.importer
        prop.linked_groups.remove(self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class SM64_GroupProperties(PropertyGroup):
    """
    properties for selecting a group for importing
    specifically made for when importing levels and you
    need to define loaded groups for linked objects
    """

    expand: bpy.props.BoolProperty(name="Expand", default=True)
    group_preset: EnumProperty(
        name="group preset", description="The group you want to load geo from", items=groups_obj_export
    )
    group_prefix_custom: StringProperty(
        name="Prefix",
        description="Prefix before expected aggregator files like script.c, leveldata.c and geo.c. Enter group name if not using dropdowns.",
        default="",
    )

    @property
    def group_prefix(self):
        if self.group_preset == "custom":
            return self.group_prefix_custom
        else:
            return self.group_preset

    def draw(self, layout, index):
        box = layout.box().column()
        box.prop(
            self,
            "expand",
            text=f"Group Load:   {self.group_preset}",
            icon="TRIA_DOWN" if self.expand else "TRIA_RIGHT",
        )
        if self.expand:
            prop_split(box, self, "group_preset", "Group Preset")
            if self.group_preset == "custom":
                prop_split(box, self, "group_prefix_custom", "Custom Group")

            row = box.row()
            row.operator("scene.add_group", text="Add Group").option = index + 1
            row.operator("scene.remove_group", text="Remove Group").option = index


def get_sm64_geos():
    # model_name, common name, description
    enum_list = []
    for name, actor in ACTOR_PRESET_INFO.items():
        if not actor.models:
            continue
        if type(actor.models) is ModelInfo:
            enum_list.append((name, name, name))
        else:
            for model in actor.models.keys():
                enum_list.append((model, model, name))
    return enum_list


class SM64_ImportProperties(PropertyGroup):
    # actor props
    custom_geo_layout_str: StringProperty(name="Geo Layout Name", description="Name of GeoLayout")
    custom_geo_layout_addr: StringProperty(name="Geo Layout Address", description="Address of GeoLayout")

    actor_preset: EnumProperty(
        name="actor preset", description="Actor to import", items=[*get_sm64_geos(), ("Custom", "Custom", "Custom")]
    )
    custom_actor_prefix: StringProperty(
        name="File Prefix",
        description="Prefix before expected aggregator files like script.c, leveldata.c and geo.c. Enter group name if not using dropdowns.",
        default="",
    )
    version: EnumProperty(
        name="Version",
        description="Version of the game for any ifdef macros",
        items=enumVersionDefs,
    )
    target: StringProperty(
        name="Target", description="The platform target for any #ifdefs in code", default="TARGET_N64"
    )

    # level props
    level_enum: EnumProperty(name="Level", description="Choose a level", items=enumLevelNames, default="bob")
    custom_level_name: StringProperty(
        name="Custom Level Name",
        description="Custom level name",
        default="",
    )
    level_prefix: StringProperty(
        name="Level Prefix",
        description="Prefix before expected aggregator files like script.c, leveldata.c and geo.c. Leave blank unless using custom files",
        default="",
    )
    entry: StringProperty(
        name="Entrypoint",
        description="The name of the level script entry variable. Levelname is put between braces.",
        default="level_{}_entry",
    )
    version: EnumProperty(
        name="Version",
        description="Version of the game for any ifdef macros",
        items=enumVersionDefs,
    )
    target: StringProperty(
        name="Target", description="The platform target for any #ifdefs in code", default="TARGET_N64"
    )
    force_new_tex: BoolProperty(
        name="force_new_tex",
        description="Forcefully load new textures even if duplicate path/name is detected",
        default=False,
    )
    as_obj: BoolProperty(
        name="As OBJ", description="Make new materials as PBSDF so they export to obj format", default=False
    )
    use_collection: BoolProperty(
        name="use_collection", description="Make new collections to organzie content during imports", default=True
    )
    export_friendly: BoolProperty(
        name="Export Friendly",
        description="Format import to be friendly for exporting for hacks rather than importing a 1:1 representation",
        default=True,
    )
    import_linked_actors: BoolProperty(
        name="Import Actors", description="Imports the models of actors. Actor models will be duplicates", default=True
    )
    linked_groups: CollectionProperty(type=SM64_GroupProperties)

    import_target: EnumProperty(
        name="Import Target",
        description="Choose a level",
        items=[("C", "C", "C"), ("Binary", "Binary", "Binary")],
        default="C",
    )

    def get_actor_preset(self):
        enumProp = self.bl_rna.properties.get("actor_preset")
        chosen_enum = None
        for enum in enumProp.enum_items:
            if self.actor_preset == enum.name:
                chosen_enum = enum
                break
        else:
            return None
        return ACTOR_PRESET_INFO[chosen_enum.description]

    @property
    def level_name(self):
        if self.level_enum == "Custom":
            return self.custom_level_name
        else:
            return self.level_enum

    @property
    def group_prefix(self):
        if self.actor_preset == "Custom":
            return self.custom_actor_prefix
        else:
            preset_full = self.get_actor_preset()
            model_info = preset_full.get_model_info(self.actor_preset)
            return preset_full.group

    @property
    def geo_layout(self):
        if self.actor_preset == "Custom":
            return self.custom_geo_layout_str
        else:
            preset_full = self.get_actor_preset()
            model_info = preset_full.get_model_info(self.actor_preset)
            return convert_addr_to_func(f"{model_info.geolayout:08x}", self.actor_preset.replace(" ", "_").lower())

    @property
    def geo_layout_binary(self):
        if self.actor_preset == "Custom":
            return self.custom_geo_layout_str
        else:
            preset_full = self.get_actor_preset()
            model_info = preset_full.get_model_info(self.actor_preset)
            return model_info.geolayout

    @property
    def col_data(self):
        if self.actor_preset == "Custom":
            return None
            # return self.custom_geo_layout_str
        else:
            preset_full = self.get_actor_preset()
            col_info = preset_full.get_collision_info(self.actor_preset)
            if not col_info:
                return None
            if self.import_target == "C":
                return col_info.c_name
            else:
                return col_info.address

    def draw_actor(self, layout: bpy.types.UILayout):
        box = layout.box()
        box.label(text="SM64 Actor Importer")
        box.prop(self, "actor_preset")
        if self.actor_preset == "Custom":
            if self.import_target == "C":
                box.prop(self, "custom_actor_prefix")
                box.prop(self, "custom_geo_layout_str")
                box.prop(self, "level_prefix")
                note = box.box()
                note.label(text=f"Geo must be in /levels/{self.level_name}/{self.level_prefix}geo.c")
                note.label(text=f"or in /actors/{self.group_prefix}_geo.c")
            else:
                box.prop(self, "custom_geo_layout_addr")
        if self.import_target == "C":
            box.prop(self, "version")
            box.prop(self, "target")

    def draw_level(self, layout: bpy.types.UILayout):
        prop_split(layout, self, "import_target", "Import Target")
        layout.separator()
        box = layout.box()
        box.label(text="Level Importer")
        box.prop(self, "level_enum")
        if self.level_enum == "Custom":
            box.prop(self, "custom_level_name")
        if self.import_target == "C":
            box.prop(self, "entry")
            box.prop(self, "level_prefix")
            box.prop(self, "version")
            box.prop(self, "target")
        row = box.row()
        row.prop(self, "force_new_tex")
        row.prop(self, "as_obj")
        row.prop(self, "export_friendly")
        if self.import_target == "C":
            row.prop(self, "import_linked_actors")
        row.prop(self, "use_collection")
        if self.import_linked_actors and self.import_target == "C":
            box = box.box()
            box.operator("scene.add_group", text="Add Group Load")
            for index, group in enumerate(self.linked_groups):
                group.draw(box, index)


# ------------------------------------------------------------------------
#    Panels
# ------------------------------------------------------------------------


class SM64_ImportPanel(SM64_Panel):
    bl_label = "SM64 Importer"
    bl_idname = "sm64_PT_importer"
    bl_context = "objectmode"
    import_panel = True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        importer_props = scene.fast64.sm64.importer
        importer_props.draw_level(layout)
        layout.operator("wm.sm64_import_level")
        layout.operator("wm.sm64_import_level_gfx")
        layout.operator("wm.sm64_import_level_col")
        layout.operator("wm.sm64_import_object")
        importer_props.draw_actor(layout)
        layout.operator("wm.sm64_import_actor")


classes = (
    SM64_AddGroup,
    SM64_RemoveGroup,
    SM64_GroupProperties,
    SM64_ImportProperties,
    SM64_LvlImport,
    SM64_LvlGfxImport,
    SM64_LvlColImport,
    SM64_ObjImport,
    SM64_ActImport,
)


def sm64_import_panel_register():
    register_class(SM64_ImportPanel)


def sm64_import_register():
    for cls in classes:
        register_class(cls)


def sm64_import_panel_unregister():
    unregister_class(SM64_ImportPanel)


def sm64_import_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
