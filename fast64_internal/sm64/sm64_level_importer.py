# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
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
from array import array
from struct import *
from shutil import copy
from pathlib import Path
from types import ModuleType
from mathutils import Vector, Euler, Matrix, Quaternion
from copy import deepcopy
from dataclasses import dataclass
from typing import TextIO
from numbers import Number
from collections.abc import Sequence

# from SM64classes import *

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
)
from .sm64_objects import enumEnvFX
from .sm64_constants import (
    enumVersionDefs,
    enumLevelNames,
    enumSpecialsNames,
    LEVEL_ID_NUMBERS,
    groups_obj_export,
    group_0_geos,
    group_1_geos,
    group_2_geos,
    group_3_geos,
    group_4_geos,
    group_5_geos,
    group_6_geos,
    group_7_geos,
    group_8_geos,
    group_9_geos,
    group_10_geos,
    group_11_geos,
    group_12_geos,
    group_13_geos,
    group_14_geos,
    group_15_geos,
    group_16_geos,
    group_17_geos,
    common_0_geos,
    common_1_geos,
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
        self.geo = geo.strip()
        self.num = num
        self.scene = scene
        self.props = scene.fast64.sm64.importer
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
        level = args[1].strip().replace("LEVEL_", "").lower()
        if level == "castle":
            level = "castle_inside"
        if level.isdigit():
            level = LEVEL_ID_NUMBERS.get(eval(level))
            if not level:
                level = "bob"
        warp.warpType = type
        warp.destLevelEnum = level
        warp.destArea = args[2]
        chkpoint = args[-1].strip()
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
        angle = Euler([math.radians(eval(a.strip())) for a in args[4:7]], "ZXY")
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
            loc = [eval(a.strip()) / self.scene.fast64.sm64.blender_to_sm64_scale for a in special[1:4]]
            # rotate to fit sm64s axis
            bpy_obj.location = [loc[0], -loc[2], loc[1]]
            bpy_obj.rotation_euler[2] = hexOrDecInt(special[4])
            bpy_obj.sm64_obj_set_yaw = True
            if special[5]:
                bpy_obj.sm64_obj_set_bparam = True
                bpy_obj.fast64.sm64.game_object.use_individual_params = False
                bpy_obj.fast64.sm64.game_object.bparams = str(special[5])
            self.placed_special_objects.append(bpy_obj)

    def place_object(self, object: Object, col: bpy.types.Collection):
        bpy_obj = bpy.data.objects.new("Empty", None)
        col.objects.link(bpy_obj)
        parentObject(self.root, bpy_obj)
        bpy_obj.name = "Object {} {}".format(object.behavior, object.model)
        bpy_obj.sm64_obj_type = "Object"
        bpy_obj.sm64_behaviour_enum = "Custom"
        bpy_obj.sm64_obj_behaviour = object.behavior.strip()
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
            mask = eval(mask)
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
    def __init__(self, scripts: dict[str, list[str]], scene: bpy.types.Scene, root: bpy.types.Object):
        self.scripts = scripts
        self.scene = scene
        self.props = scene.fast64.sm64.importer
        self.areas: dict[area_index:int, Area] = {}
        self.cur_area: int = None
        self.root = root
        self.loaded_geos: dict[model_name:str, geo_name:str] = dict()
        self.loaded_dls: dict[model_name:str, dl_name:str] = dict()
        super().__init__()

    def parse_level_script(self, entry: str, col: bpy.types.Collection = None):
        script_stream = self.scripts[entry]
        scale = self.scene.fast64.sm64.blender_to_sm64_scale
        if not col:
            col = self.scene.collection
        self.parse_stream_from_start(script_stream, entry, col)
        return self.areas

    def AREA(self, macro: Macro, col: bpy.types.Collection):
        area_root = bpy.data.objects.new("Empty", None)
        if self.props.use_collection:
            area_col = bpy.data.collections.new(f"{self.props.level_name} area {macro.args[0]}")
            col.children.link(area_col)
        else:
            area_col = col
        area_col.objects.link(area_root)
        area_root.name = f"{self.props.level_name} Area Root {macro.args[0]}"
        self.areas[macro.args[0]] = Area(area_root, macro.args[1], self.root, int(macro.args[0]), self.scene, area_col)
        self.cur_area = macro.args[0]
        return self.continue_parse

    def END_AREA(self, macro: Macro, col: bpy.types.Collection):
        self.cur_area = None
        return self.continue_parse

    # Jumps are only taken if they're in the script.c file for now
    # continues script
    def JUMP_LINK(self, macro: Macro, col: bpy.types.Collection):
        if self.scripts.get(macro.args[0]):
            self.parse_level_script(macro.args[0], col=col)
        return self.continue_parse

    # ends script
    def JUMP(self, macro: Macro, col: bpy.types.Collection):
        new_entry = self.scripts.get(macro.args[-1])
        if new_entry:
            self.parse_level_script(macro.args[-1], col=col)
        return self.break_parse

    def EXIT(self, macro: Macro, col: bpy.types.Collection):
        return self.break_parse

    def RETURN(self, macro: Macro, col: bpy.types.Collection):
        return self.break_parse

    # Now deal with data cmds rather than flow control ones
    def WARP_NODE(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].add_warp(macro.args, "Warp")
        return self.continue_parse

    def PAINTING_WARP_NODE(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].add_warp(macro.args, "Painting")
        return self.continue_parse

    def INSTANT_WARP(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].add_instant_warp(macro.args)
        return self.continue_parse

    def OBJECT_WITH_ACTS(self, macro: Macro, col: bpy.types.Collection):
        # convert act mask from ORs of act names to a number
        mask = macro.args[-1]
        if not mask.isdigit():
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
        return self.continue_parse

    def OBJECT(self, macro: Macro, col: bpy.types.Collection):
        # Only difference is act mask, which I set to 31 to mean all acts
        self.areas[self.cur_area].add_object([*macro.args, 31])
        return self.continue_parse

    def TERRAIN_TYPE(self, macro: Macro, col: bpy.types.Collection):
        if not macro.args[0].isdigit():
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
                num = eval(macro.args[0])
                self.areas[self.cur_area].root.terrainEnum = terrains.get(num)
            except:
                print("could not set terrain")
        return self.continue_parse

    def SHOW_DIALOG(self, macro: Macro, col: bpy.types.Collection):
        root = self.areas[self.cur_area].root
        root.showStartDialog = True
        root.startDialog = macro.args[1]
        return self.continue_parse

    def TERRAIN(self, macro: Macro, col: bpy.types.Collection):
        self.areas[self.cur_area].terrain = macro.args[0]
        return self.continue_parse

    def SET_BACKGROUND_MUSIC(self, macro: Macro, col: bpy.types.Collection):
        return self.generic_music(macro, col)

    def SET_MENU_MUSIC_WITH_REVERB(self, macro: Macro, col: bpy.types.Collection):
        return self.generic_music(macro, col)

    def SET_BACKGROUND_MUSIC_WITH_REVERB(self, macro: Macro, col: bpy.types.Collection):
        return self.generic_music(macro, col)

    def SET_MENU_MUSIC(self, macro: Macro, col: bpy.types.Collection):
        return self.generic_music(macro, col)

    def generic_music(self, macro: Macro, col: bpy.types.Collection):
        root = self.areas[self.cur_area].root
        root.musicSeqEnum = "Custom"
        root.music_seq = macro.args[1]
        return self.continue_parse

    # Don't support these for now
    def MACRO_OBJECTS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def WHIRLPOOL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def SET_ECHO(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def MARIO_POS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def SET_REG(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def GET_OR_SET(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CHANGE_AREA_SKYBOX(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    # Don't support for now but maybe later
    def JUMP_LINK_PUSH_ARG(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def JUMP_N_TIMES(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def LOOP_BEGIN(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def LOOP_UNTIL(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def JUMP_IF(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def JUMP_LINK_IF(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def SKIP_IF(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def SKIP(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def SKIP_NOP(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def LOAD_AREA(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def UNLOAD_AREA(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def UNLOAD_MARIO_AREA(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    def UNLOAD_AREA(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("no support yet woops")

    # use group mapping to set groups eventually
    def LOAD_MIO0(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_MIO0_TEXTURE(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_TITLE_SCREEN_BG(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_GODDARD(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_BEHAVIOR_DATA(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_COMMON0(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_GROUPB(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_GROUPA(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_EFFECTS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_SKYBOX(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_TEXTURE_BIN(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_LEVEL_DATA(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_YAY0(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_YAY0_TEXTURE(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_VANILLA_OBJECTS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_RAW(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_RAW_WITH_CODE(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_MARIO_HEAD(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_MODEL_FROM_GEO(self, macro: Macro, col: bpy.types.Collection):
        self.loaded_geos[macro.args[0]] = macro.args[1]
        return self.continue_parse

    def LOAD_MODEL_FROM_DL(self, macro: Macro, col: bpy.types.Collection):
        self.loaded_dls[macro.args[0]] = macro.args[1]
        return self.continue_parse

    # throw exception saying I cannot process
    def EXECUTE(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("Processing of EXECUTE macro is not currently supported")

    def EXIT_AND_EXECUTE(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("Processing of EXIT_AND_EXECUTE macro is not currently supported")

    def EXECUTE_WITH_CODE(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("Processing of EXECUTE_WITH_CODE macro is not currently supported")

    def EXIT_AND_EXECUTE_WITH_CODE(self, macro: Macro, col: bpy.types.Collection):
        raise Exception("Processing of EXIT_AND_EXECUTE_WITH_CODE macro is not currently supported")

    # not useful for bpy, dummy these script cmds
    def CMD3A(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def STOP_MUSIC(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def GAMMA(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def BLACKOUT(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def TRANSITION(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def NOP(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CMD23(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def PUSH_POOL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def POP_POOL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def SLEEP(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def ROOMS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def MARIO(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def INIT_LEVEL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def ALLOC_LEVEL_POOL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def FREE_LEVEL_POOL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CALL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CALL_LOOP(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CLEAR_LEVEL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def SLEEP_BEFORE_EXIT(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse


@dataclass
class ColTri:
    type: Any
    verts: list[int]
    special_param: Any = None


class Collision(DataParser):
    def __init__(self, collision: list[str], scale: float):
        self.collision = collision
        self.scale = scale
        self.vertices = []
        # key=type,value=tri data
        self.tris: list[ColTri] = []
        self.type: str = None
        self.special_objects = []
        self.water_boxes = []
        super().__init__()

    def write_water_boxes(
        self, scene: bpy.types.Scene, parent: bpy.types.Object, name: str, col: bpy.types.Collection = None
    ):
        for i, w in enumerate(self.water_boxes):
            Obj = bpy.data.objects.new("Empty", None)
            scene.collection.objects.link(Obj)
            parentObject(parent, Obj)
            Obj.name = "WaterBox_{}_{}".format(name, i)
            Obj.sm64_obj_type = "Water Box"
            x1 = eval(w[1]) / (self.scale)
            x2 = eval(w[3]) / (self.scale)
            z1 = eval(w[2]) / (self.scale)
            z2 = eval(w[4]) / (self.scale)
            y = eval(w[5]) / (self.scale)
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
                    mat.collision_param = str(col_tri.special_param)
                # I don't think I care about this. It makes program slow
                # with bpy.context.temp_override(material=mat):
                # bpy.ops.material.update_f3d_nodes()
            bpy_tri.material_index = col_materials[col_tri.type]
        return obj

    def parse_collision(self):
        self.parse_stream(self.collision, 0)

    def COL_VERTEX(self, macro: Macro):
        self.vertices.append([eval(v) / self.scale for v in macro.args])
        return self.continue_parse

    def COL_TRI_INIT(self, macro: Macro):
        self.type = macro.args[0]
        return self.continue_parse

    def COL_TRI(self, macro: Macro):
        self.tris.append(ColTri(self.type, [eval(a) for a in macro.args]))
        return self.continue_parse

    def COL_TRI_SPECIAL(self, macro: Macro):
        self.tris.append(ColTri(self.type, [eval(a) for a in macro.args[0:3]], special_param=eval(macro.args[3])))
        return self.continue_parse

    def COL_WATER_BOX(self, macro: Macro):
        # id, x1, z1, x2, z2, y
        self.water_boxes.append(macro.args)
        return self.continue_parse

    # not written out currently
    def SPECIAL_OBJECT(self, macro: Macro):
        self.special_objects.append((*macro.args, 0, 0))
        return self.continue_parse

    def SPECIAL_OBJECT_WITH_YAW(self, macro: Macro):
        self.special_objects.append((*macro.args, 0))
        return self.continue_parse

    def SPECIAL_OBJECT_WITH_YAW_AND_PARAM(self, macro: Macro):
        self.special_objects.append(macro.args)
        return self.continue_parse

    # don't do anything to bpy
    def COL_WATER_BOX_INIT(self, macro: Macro):
        return self.continue_parse

    def COL_INIT(self, macro: Macro):
        return self.continue_parse

    def COL_VERTEX_INIT(self, macro: Macro):
        return self.continue_parse

    def COL_SPECIAL_INIT(self, macro: Macro):
        return self.continue_parse

    def COL_TRI_STOP(self, macro: Macro):
        return self.continue_parse

    def COL_END(self, macro: Macro):
        return self.continue_parse


class SM64_Material(Mat):
    def load_texture(self, force_new_tex: bool, textures: dict, path: Path, tex: Texture):
        if not tex:
            return None
        Timg = textures.get(tex.Timg)[0].split("/")[-1]
        Timg = Timg.replace("#include ", "").replace('"', "").replace("'", "").replace("inc.c", "png")
        image = bpy.data.images.get(Timg)
        if not image or force_new_tex:
            Timg = textures.get(tex.Timg)[0]
            Timg = Timg.replace("#include ", "").replace('"', "").replace("'", "").replace("inc.c", "png")
            # deal with duplicate pathing (such as /actors/actors etc.)
            Extra = path.relative_to(Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path)))
            for e in Extra.parts:
                Timg = Timg.replace(e + "/", "")
            # deal with actor import path not working for shared textures
            if "textures" in Timg:
                fp = Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path)) / Timg
            else:
                fp = path / Timg
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
            self.set_tex_settings(
                f3d.tex0,
                self.load_texture(bpy.context.scene.fast64.sm64.importer.force_new_tex, textures, tex_path, self.tex0),
                self.tiles[0 + self.base_tile],
                self.tex0.Timg,
            )
        if self.tex1 and self.set_tex:
            self.set_tex_settings(
                f3d.tex1,
                self.load_texture(bpy.context.scene.fast64.sm64.importer.force_new_tex, textures, tex_path, self.tex1),
                self.tiles[1 + self.base_tile],
                self.tex1.Timg,
            )


class SM64_F3D(DL):
    def __init__(self, scene):
        self.scene = scene
        self.props = scene.fast64.sm64.importer
        super().__init__(lastmat=SM64_Material())

    # Textures only contains the texture data found inside the model.inc.c file and the texture.inc.c file
    # this will add all the textures located in the /textures/ folder in decomp
    def get_generic_textures(self, root_path: Path):
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
                )
            )
            t.close()

    # recursively parse the display list in order to return a bunch of model data
    def get_f3d_data_from_model(self, start: str, last_mat: SM64_Material = None, layer: int = None):
        DL = self.Gfx.get(start)
        self.VertBuff = [0] * 32  # If you're doing some fucky shit with a larger vert buffer it sucks to suck I guess
        if not DL:
            raise Exception("Could not find DL {}".format(start))
        self.Verts = []
        self.Tris = []
        self.UVs = []
        self.VCs = []
        self.Mats = []
        # inherit the mat based on the layer, or explicitly given one
        if last_mat:
            self.last_mat = last_mat
        elif layer:
            last_mat = self.last_mat_dict.get(layer, None)
            if last_mat:
                self.last_mat = last_mat
            else:
                self.last_mat = SM64_Material()
        self.parse_stream(DL, start)
        self.NewMat = 0
        self.StartName = start
        return [self.Verts, self.Tris]

    # turn member of vtx str arr into vtx args
    def parse_vert(self, Vert: str):
        v = Vert.replace("{", "").replace("}", "").split(",")
        num = lambda x: [eval(a) for a in x]
        pos = num(v[:3])
        uv = num(v[4:6])
        vc = num(v[6:10])
        return [pos, uv, vc]

    # given tri args in gbi cmd, give appropriate tri indices in vert list
    def parse_tri(self, Tri: list[int]):
        L = len(self.Verts)
        return [a + L - self.LastLoad for a in Tri]

    def apply_mesh_data(self, obj: bpy.types.Object, mesh: bpy.types.Mesh, layer: int, tex_path: Path):
        bpy.context.view_layer.objects.active = obj
        ind = -1
        new = -1
        UVmap = obj.data.uv_layers.new(name="UVMap")
        # I can get the available enums for color attrs with this func
        vcol_enums = GetEnums(bpy.types.FloatColorAttribute, "data_type")
        # enums were changed in a blender version, this should future proof it a little
        if "FLOAT_COLOR" in vcol_enums:
            e = "FLOAT_COLOR"
        else:
            e = "COLOR"
        Vcol = obj.data.color_attributes.get("Col")
        if not Vcol:
            Vcol = obj.data.color_attributes.new(name="Col", type=e, domain="CORNER")
        Valph = obj.data.color_attributes.get("Alpha")
        if not Valph:
            Valph = obj.data.color_attributes.new(name="Alpha", type=e, domain="CORNER")

        b_mesh = bmesh.new()
        b_mesh.from_mesh(mesh)
        tris = b_mesh.faces
        tris.ensure_lookup_table()
        uv_map = b_mesh.loops.layers.uv.active
        v_color = b_mesh.loops.layers.float_color["Col"]
        v_alpha = b_mesh.loops.layers.float_color["Alpha"]

        self.Mats.append([len(tris), 0])
        for i, t in enumerate(tris):
            if i > self.Mats[ind + 1][0]:
                new = self.create_new_f3d_mat(self.Mats[ind + 1][1], obj)
                ind += 1
                if not new:
                    new = len(mesh.materials) - 1
                    mat = mesh.materials[new]
                    mat.name = "sm64 F3D Mat {} {}".format(obj.name, new)
                    self.Mats[new][1].apply_material_settings(mat, self.Textures, tex_path, layer)
                else:
                    # I tried to re use mat slots but it is much slower, and not as accurate
                    # idk if I was just doing it wrong or the search is that much slower, but this is easier
                    mesh.materials.append(new)
                    new = len(mesh.materials) - 1
            # if somehow there is no material assigned to the triangle or something is lost
            if new != -1:
                self.apply_loop_data(new, mesh, t, uv_map, v_color, v_alpha)
        b_mesh.to_mesh(mesh)

    def apply_loop_data(self, mat: bpy.Types.Material, mesh: bpy.Types.Mesh, tri, uv_map, v_color, v_alpha):
        tri.material_index = mat
        # Get texture size or assume 32, 32 otherwise
        i = mesh.materials[mat].f3d_mat.tex0.tex
        if not i:
            WH = (32, 32)
        else:
            WH = i.size
        # Set UV data and Vertex Color Data
        for v, l in zip(tri.verts, tri.loops):
            uv = self.UVs[v.index]
            vcol = self.VCs[v.index]
            # scale verts
            l[uv_map].uv = [a * (1 / (32 * b)) if b > 0 else a * 0.001 * 32 for a, b in zip(uv, WH)]
            # idk why this is necessary. N64 thing or something?
            l[uv_map].uv[1] = l[uv_map].uv[1] * -1 + 1
            l[v_color] = [a / 255 for a in vcol]
            l[v_alpha] = [vcol[3] / 255 for i in range(4)]

    # create a new f3d_mat given an SM64_Material class but don't create copies with same props
    def create_new_f3d_mat(self, mat: SM64_Material, obj: bpy.types.Object):
        if not self.props.force_new_tex:
            # check if this mat was used already in another mesh (or this mat if DL is suboptimal or something)
            # even looping n^2 is probably faster than duping 3 mats with blender speed
            for j, F3Dmat in enumerate(bpy.data.materials):
                if F3Dmat.is_f3d:
                    dupe = mat.mat_hash_f3d(F3Dmat.f3d_mat)
                    if dupe:
                        return F3Dmat
        # make new mat
        preset = getDefaultMaterialPreset("Shaded Solid")
        createF3DMat(obj, preset)
        return None


# holds model found by geo
@dataclass
class ModelDat:
    transform: Matrix
    layer: int
    model_name: str
    vertex_group_name: str = None
    switch_index: int = 0
    armature_obj: bpy.types.Object = None
    object: bpy.types.Object = None


# base class for geo layouts and armatures
class GraphNodes(DataParser):
    _skipped_geo_asm_funcs = {
        "geo_movtex_pause_control",
        "geo_movtex_draw_water_regions",
        "geo_cannon_circle_base",
        "geo_envfx_main",
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
    ):
        self.geo_layouts = geo_layouts
        self.models = []
        self.children = []
        self.scene = scene
        self.props = scene.fast64.sm64.importer
        if not stream:
            stream = list()
        self.stream = stream
        self.parent_transform = transform_mtx_blender_to_n64().inverted()
        self.last_transform = transform_mtx_blender_to_n64().inverted()
        self.name = name
        self.col = col
        super().__init__(parent=geo_parent)

    # pick the right subclass given contents of geo layout
    @staticmethod
    def new_subclass_dyn(
        geo_layout_dict: dict[geo_name:str, geo_data : list[str]],
        scene: bpy.types.Scene,
        layout_name: str,
        col: bpy.types.Collection = None,
    ) -> Union[GeoLayout, GeoArmature]:
        geo_layout = geo_layout_dict.get(layout_name)
        if not geo_layout:
            raise Exception(
                "Could not find geo layout {}".format(layout_name),
                "pass_linked_export",
            )
        for line in geo_layout:
            if "GEO_ANIMATED_PART" in line:
                name = f"Actor {layout_name}"
                arm_obj = bpy.data.objects.new(name, bpy.data.armatures.new(name))
                col.objects.link(arm_obj)
                geo_armature = GeoArmature(geo_layout_dict, arm_obj, scene, layout_name, col)
                geo_armature.parse_armature(layout_name, scene.fast64.sm64.importer)
                return geo_armature
        else:
            geo_layout = GeoLayout(geo_layout_dict, None, scene, layout_name, None, col=col)
            geo_layout.parse_level_geo(layout_name)
            return geo_layout

    def parse_layer(self, layer: str):
        if not layer.isdigit():
            layer = Layers.get(layer)
            if not layer:
                layer = 1
        return layer

    @property
    def ordered_name(self):
        return f"{self.get_parser(self.stream[-1]).head}_{self.name}"

    @property
    def first_obj(self):
        if self.root:
            return self.root
        for model in self.models:
            if model.object:
                return model.object
        for child in self.children:
            if root := child.first_obj:
                return root
        return None

    def get_translation(self, trans_vector: Sequence):
        translation = [float(val) for val in trans_vector]
        return [translation[0], -translation[2], translation[1]]

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

    def GEO_BRANCH_AND_LINK(self, macro: Macro, depth: int):
        new_geo_layout = self.geo_layouts.get(macro.args[0])
        if new_geo_layout:
            self.stream.append(macro.args[0])
            self.parse_stream_from_start(new_geo_layout, macro.args[0], depth)
        return self.continue_parse

    def GEO_BRANCH(self, macro: Macro, depth: int):
        new_geo_layout = self.geo_layouts.get(macro.args[1])
        if new_geo_layout:
            self.stream.append(macro.args[1])
            self.parse_stream_from_start(new_geo_layout, macro.args[1], depth)
        # arg 0 determines if you return and continue or end after the branch
        if eval(macro.args[0]):
            return self.continue_parse
        else:
            return self.break_parse

    def GEO_END(self, macro: Macro, depth: int):
        self.stream = None
        return self.break_parse

    def GEO_RETURN(self, macro: Macro, depth: int):
        self.stream.pop()
        return self.break_parse

    def GEO_CLOSE_NODE(self, macro: Macro, depth: int):
        return self.break_parse

    def GEO_DISPLAY_LIST(self, macro: Macro, depth: int):
        # translation, rotation, layer, model
        geo_obj = self.add_model(
            ModelDat(self.parent_transform, *macro.args), "display_list", self.display_list, macro.args[0]
        )
        self.set_transform(geo_obj, self.last_transform)
        return self.continue_parse

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
        return self.continue_parse

    def GEO_BILLBOARD_WITH_PARAMS(self, macro: Macro, depth: int):
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform

        geo_obj = self.setup_geo_obj("billboard", self.billboard, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self.continue_parse

    def GEO_BILLBOARD(self, macro: Macro, depth: int):
        self.setup_geo_obj("billboard", self.billboard, macro.args[0])
        return self.continue_parse

    def GEO_ANIMATED_PART(self, macro: Macro, depth: int):
        # layer, translation, DL
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform
        model = macro.args[-1]

        if model != "NULL":
            geo_obj = self.add_model(
                ModelDat(self.last_transform, macro.args[0], model), "bone", self.animated_part, macro.args[0]
            )
        else:
            geo_obj = self.setup_geo_obj("bone", self.animated_part, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self.continue_parse

    def GEO_ROTATION_NODE(self, macro: Macro, depth: int):
        geo_obj = self.GEO_ROTATE(macro, depth)
        if geo_obj:
            self.set_geo_type(geo_obj, self.rotate)
        return self.continue_parse

    def GEO_ROTATE(self, macro: Macro, depth: int):
        transform = Matrix.LocRotScale(Vector(), self.get_rotation(macro.args[1:4]), Vector((1, 1, 1)))
        self.last_transform = self.parent_transform @ transform
        return self.setup_geo_obj("rotate", self.translate_rotate, macro.args[0])

    def GEO_ROTATION_NODE_WITH_DL(self, macro: Macro, depth: int):
        geo_obj = self.GEO_ROTATE_WITH_DL(macro, depth)
        return self.continue_parse

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
        return self.continue_parse

    def GEO_TRANSLATE_ROTATE(self, macro: Macro, depth: int):
        transform = Matrix.LocRotScale(
            self.get_translation(macro.args[1:4]), self.get_rotation(macro.args[1:4]), Vector((1, 1, 1))
        )
        self.last_transform = self.parent_transform @ transform

        geo_obj = self.setup_geo_obj("trans/rotate", self.translate_rotate, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return self.continue_parse

    def GEO_TRANSLATE_WITH_DL(self, macro: Macro, depth: int):
        geo_obj = self.GEO_TRANSLATE_NODE_WITH_DL(macro, depth)
        if geo_obj:
            self.set_geo_type(geo_obj, self.translate_rotate)
        return self.continue_parse

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
        return self.continue_parse

    def GEO_TRANSLATE_NODE(self, macro: Macro, depth: int):
        transform = Matrix()
        transform.translation = self.get_translation(macro.args[1:4])
        self.last_transform = self.parent_transform @ transform

        geo_obj = self.setup_geo_obj("translate", self.translate, macro.args[0])
        self.set_transform(geo_obj, self.last_transform)
        return geo_obj

    def GEO_SCALE_WITH_DL(self, macro: Macro, depth: int):
        scale = eval(macro.args[1]) / 0x10000
        self.last_transform = scale * self.last_transform

        model = macro.args[-1]
        geo_obj = self.add_model(ModelDat(self.last_transform, macro.args[0], macro.args[-1]))
        self.set_transform(geo_obj, self.last_transform)
        return self.continue_parse

    # these have no affect on the bpy
    def GEO_NOP_1A(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_NOP_1E(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_NOP_1F(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_NODE_START(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_NODE_SCREEN_AREA(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_ZBUFFER(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_RENDER_OBJ(self, macro: Macro, depth: int):
        return self.continue_parse

    # This should probably do something but I haven't coded it in yet
    def GEO_COPY_VIEW(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_ASSIGN_AS_VIEW(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_UPDATE_NODE_FLAGS(self, macro: Macro, depth: int):
        return self.continue_parse

    def GEO_NODE_ORTHO(self, macro: Macro, depth: int):
        return self.continue_parse

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

    def GEO_CAMERA_FRUSTRUM(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_CAMERA_FRUSTUM_WITH_FUNC(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_BACKGROUND(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")

    def GEO_BACKGROUND_COLOR(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")


class GeoLayout(GraphNodes):
    switch = "Switch"
    translate_rotate = "Geo Translate/Rotat"
    translate = "Geo Translate Node"
    rotate = "Geo Rotation Node"
    billboard = "Geo Billboard"
    display_list = "Geo Displaylist"
    shadow = "Custom"
    asm = "Geo ASM"
    scale = "Geo Scale"
    animated_part = "Geo Translate Node"
    custom_animated = "Custom"
    custom = "Custom"

    def __init__(
        self,
        geo_layouts: dict,
        root: bpy.types.Object,
        scene: bpy.types.Scene,
        name: str,
        area_root: bpy.types.Object,
        col: bpy.types.Collection = None,
        geo_parent: GeoLayout = None,
        stream: list[Any] = None,
        pass_args: dict = None,
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
        super().__init__(geo_layouts, scene, name, col, geo_parent=geo_parent, stream=stream)

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
        self.stream.append(start)
        self.parse_stream_from_start(geo_layout, start, 0)

    def GEO_ASM(self, macro: Macro, depth: int):
        # envfx goes on the area root
        if "geo_envfx_main" in macro.args[1]:
            env_fx = macro.args[1]
            if any(env_fx is enum_fx[0] for enum_fx in enumEnvFX):
                self.area_root.envOption = env_fx
            else:
                self.area_root.envOption = "Custom"
                self.area_root.envType = env_fx
        if macro.args[1] in self._skipped_geo_asm_funcs and self.props.export_friendly:
            return self.continue_parse
        geo_obj = self.setup_geo_obj("asm", self.asm)
        # probably will need to be overridden by each subclass
        asm = geo_obj.fast64.sm64.geo_asm
        asm.param = macro.args[0]
        asm.func = macro.args[1]
        return self.continue_parse

    def GEO_SCALE(self, macro: Macro, depth: int):
        scale = eval(macro.args[1]) / 0x10000
        geo_obj = self.setup_geo_obj("scale", self.scale, macro.args[0])
        geo_obj.scale = (scale, scale, scale)
        return self.continue_parse

    # shadows aren't naturally supported but we can emulate them with custom geo cmds
    # change so this can be applied to mesh on root?
    def GEO_SHADOW(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("shadow empty", self.shadow)
        # custom cmds were changed and wrapped into a new update
        # its probably better to just make shadows a real geo cmd or have some generic custom cmd func
        # geo_obj.customGeoCommand = "GEO_SHADOW"
        # geo_obj.customGeoCommandArgs = ", ".join(macro.args)
        return self.continue_parse

    def GEO_SWITCH_CASE(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("switch", self.switch)
        # probably will need to be overridden by each subclass
        geo_obj.switchParam = eval(macro.args[0])
        geo_obj.switchFunc = macro.args[1]
        return self.continue_parse

    # can only apply type to area root
    def GEO_CAMERA(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[0]
        return self.continue_parse

    def GEO_BACKGROUND(self, macro: Macro, depth: int):
        level_root = self.area_root.parent
        # check if in enum
        skybox_name = macro.args[0].replace("BACKGROUND_", "")
        bg_enums = {enum.identifier for enum in level_root.bl_rna.properties["background"].enum_items}
        if skybox_name in bg_enums:
            level_root.background = skybox_name
        else:
            level_root.background = "CUSTOM"
            # this is cringe and should be changed
            scene.fast64.sm64.level.backgroundID = macro.args[0]
            # I don't have access to the bg segment, that is in level obj
            scene.fast64.sm64.level.backgroundSegment = "unavailable srry :("

        return self.continue_parse

    def GEO_BACKGROUND_COLOR(self, macro: Macro, depth: int):
        level_root = self.area_root.parent
        level_root.useBackgroundColor = True
        level_root.backgroundColor = read16bitRGBA(hexOrDecInt(macro.args[0]))
        return self.continue_parse

    # can only apply to meshes
    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        self.pass_args["render_range"] = [
            hexOrDecInt(range) / self.scene.fast64.sm64.blender_to_sm64_scale for range in macro.args
        ]
        return self.continue_parse

    def GEO_CULLING_RADIUS(self, macro: Macro, depth: int):
        self.pass_args["culling_radius"] = hexOrDecInt(macro.args[0]) / self.scene.fast64.sm64.blender_to_sm64_scale
        return self.continue_parse

    # make better
    def GEO_CAMERA_FRUSTRUM(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[0]
        return self.continue_parse

    def GEO_CAMERA_FRUSTUM_WITH_FUNC(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[0]
        return self.continue_parse

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
        GeoChild.parse_stream(self.geo_layouts.get(self.stream[-1]), self.stream[-1], depth + 1)
        self.children.append(GeoChild)
        return self.continue_parse


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
    custom_animated = "CustomAnimated"
    custom = "CustomNonAnimated"

    def __init__(
        self,
        geo_layouts: dict,
        armature_obj: bpy.types.Armature,
        scene: bpy.types.Scene,
        name: str,
        col: bpy.types.Collection,
        is_switch_child: bool = False,
        parent_bone: bpy.types.Bone = None,
        geo_parent: GeoArmature = None,
        switch_armatures: dict[int, bpy.types.Object] = None,
        stream: Any = None,
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
        super().__init__(geo_layouts, scene, name, col, geo_parent=geo_parent, stream=stream)

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
        edit_bone.tail = (0, 0, 1)
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
        ind = self.get_parser(self.stream[-1]).head
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
        self.stream.append(start)
        self.parse_stream_from_start(geo_layout, start, 0)

    def GEO_ASM(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("asm", self.asm)
        if not macro.args[0].isdigit():
            print("could not convert geo asm arg")
        else:
            geo_obj.func_param = int(macro.args[0])
        geo_obj.geo_func = macro.args[1]
        return self.continue_parse

    def GEO_SHADOW(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("shadow", self.shadow)
        geo_bone.shadow_solidity = hexOrDecInt(macro.args[1]) / 255
        geo_bone.shadow_scale = hexOrDecInt(macro.args[2])
        return self.continue_parse

    # cmd not supported in fast64 for some reason?
    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("render_range", self.custom)
        geo_bone.fast64.sm64.custom_geo_cmd_macro = "GEO_RENDER_RANGE"
        geo_bone.fast64.sm64.custom_geo_cmd_args = ",".join(macro.args)
        return self.continue_parse

    # can switch children have their own culling radius? does it have to
    # be on the root? this currently allows each independent geo to have one
    def GEO_CULLING_RADIUS(self, macro: Macro, depth: int):
        geo_armature = self.get_or_init_geo_armature()
        geo_armature.use_render_area = True  # cringe name, it is cull not render area
        geo_armature.culling_radius = float(macro.args[0])
        return self.continue_parse

    def GEO_SWITCH_CASE(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("switch", self.switch)
        # probably will need to be overridden by each subclass
        geo_bone.func_param = eval(macro.args[0])
        geo_bone.geo_func = macro.args[1]
        return self.continue_parse

    def GEO_SCALE_WITH_DL(self, macro: Macro, depth: int):
        scale = eval(macro.args[1]) / 0x10000
        self.last_transform = [(0, 0, 0), self.last_transform[1]]

        model = macro.args[-1]
        geo_obj = self.add_model(
            ModelDat((0, 0, 0), (0, 0, 0), macro.args[0], macro.args[-1], scale=scale),
            "scale",
            self.scale,
            macro.args[0],
        )
        self.set_transform(geo_obj, self.last_transform)
        return self.continue_parse

    def GEO_SCALE(self, macro: Macro, depth: int):
        scale = eval(macro.args[1]) / 0x10000

        geo_bone = self.setup_geo_obj("scale", self.scale, macro.args[0])
        geo_bone.geo_scale = scale
        return self.continue_parse

    # can be used as a container for several nodes under a single switch child
    def GEO_NODE_START(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("start", self.start, "1")
        return self.continue_parse

    # add some stuff here
    def GEO_HELD_OBJECT(self, macro: Macro, depth: int):
        return self.continue_parse

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
                # switch_armatures=self.switch_armatures, # I think double open node won't cause an issue here?
            )
        GeoChild.parent_transform = self.last_transform
        GeoChild.parse_stream(self.geo_layouts.get(self.stream[-1]), self.stream[-1], depth + 1)
        self.children.append(GeoChild)
        return self.continue_parse


# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------


# parse aggregate files, and search for sm64 specific fast64 export name schemes
def get_all_aggregates(aggregate_path: Path, filenames: tuple[callable], root_path: Path) -> list[Path]:
    with open(aggregate_path, "r", newline="") as file:
        caught_files = parse_aggregate_file(file, filenames, root_path, aggregate_path)
        # catch fast64 includes
        fast64 = parse_aggregate_file(file, (lambda path: "leveldata.inc.c" in path.name,), root_path, aggregate_path)
        if fast64:
            with open(fast64[0], "r", newline="") as fast64_dat:
                caught_files.extend(parse_aggregate_file(fast64_dat, filenames, root_path, aggregate_path))
    return caught_files


# given a path, get a level object by parsing the script.c file
def parse_level_script(script_files: list[Path], scene: bpy.types.Scene, col: bpy.types.Collection = None):
    root = bpy.data.objects.new("Empty", None)
    if not col:
        scene.collection.objects.link(root)
    else:
        col.objects.link(root)
    props = scene.fast64.sm64.importer
    root.name = f"Level Root {props.level_name}"
    root.sm64_obj_type = "Level Root"
    # Now parse the script and get data about the level
    # Store data in attribute of a level class then assign later and return class
    scripts = dict()
    for script_file in script_files:
        with open(script_file, "r", newline="") as script_file:
            scripts.update(get_data_types_from_file(script_file, {"LevelScript": ["(", ")"]}))
    lvl = Level(scripts, scene, root)
    entry = props.entry.format(props.level_name)
    lvl.parse_level_script(entry, col=col)
    return lvl


# write the objects from a level object
def write_level_objects(lvl: Level, col_name: str = None, actor_models: dict[model_name, bpy.Types.Mesh] = None):
    for area in lvl.areas.values():
        area.place_objects(col_name=col_name, actor_models=actor_models)


# from a geo layout, create all the mesh's
def write_armature_to_bpy(
    geo_armature: GeoArmature,
    scene: bpy.types.Scene,
    f3d_dat: SM64_F3D,
    root_path: Path,
    parsed_model_data: dict[str, bpy.Types.Mesh],
    cleanup: bool = True,
):
    parsed_model_data = recurse_armature(geo_armature, scene, f3d_dat, root_path, parsed_model_data, cleanup=cleanup)

    objects_by_armature = dict()
    for model_data in geo_armature.models:
        if not objects_by_armature.get(model_data.armature_obj, None):
            objects_by_armature[model_data.armature_obj] = [model_data.object]
        else:
            objects_by_armature[model_data.armature_obj].append(model_data.object)

    for armature_obj, objects in objects_by_armature.items():
        # I don't really know the specific override needed for this to work
        override = {**bpy.context.copy(), "selected_editable_objects": objects, "active_object": objects[0]}
        with bpy.context.temp_override(**override):
            bpy.ops.object.join()

        obj = objects[0]
        parentObject(armature_obj, obj)
        obj.scale *= 1 / scene.fast64.sm64.blender_to_sm64_scale
        rotate_object(-90, obj)
        obj.ignore_collision = True
        # armature deform
        mod = obj.modifiers.new("deform", "ARMATURE")
        mod.object = geo_armature.armature
    return parsed_model_data


def apply_mesh_data(
    f3d_dat: SM64_F3D, obj: bpy.types.Object, mesh: bpy.types.Mesh, layer: int, root_path: Path, cleanup: bool = False
):
    f3d_dat.apply_mesh_data(obj, mesh, layer, root_path)
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


def recurse_armature(
    geo_armature: GeoArmature,
    scene: bpy.types.Scene,
    f3d_dat: SM64_F3D,
    root_path: Path,
    parsed_model_data: dict[str, bpy.Types.Mesh],
    cleanup: bool = True,
):
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


# from a geo layout, create all the mesh's
def write_geo_to_bpy(
    geo: GeoLayout,
    scene: bpy.types.Scene,
    f3d_dat: SM64_F3D,
    root_path: Path,
    meshes: dict[str, bpy.Types.Mesh],
    cleanup: bool = True,
) -> dict[str, bpy.Types.Mesh]:
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
                mesh.from_pydata(verts, [], tris)

            # swap out placeholder mesh data
            model_data.object.data = mesh

            if name:
                apply_mesh_data(f3d_dat, model_data.object, mesh, str(layer), root_path, cleanup)
    if not geo.children:
        return meshes
    for g in geo.children:
        meshes = write_geo_to_bpy(g, scene, f3d_dat, root_path, meshes, cleanup=cleanup)
    return meshes


# write the gfx for a level given the level data, and f3d data
def write_level_to_bpy(lvl: Level, scene: bpy.types.Scene, root_path: Path, f3d_dat: SM64_F3D, cleanup: bool = False):
    for area in lvl.areas.values():
        write_geo_to_bpy(area.geo, scene, f3d_dat, root_path, dict(), cleanup=cleanup)
    return lvl


# given a geo.c file and a path, return cleaned up geo layouts in a dict
def construct_geo_layouts_from_file(geo_paths: list[Path], root_path: Path) -> dict[geo_name:str, geo_data : list[str]]:
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
            geo_layout_data.update(get_data_types_from_file(geo_file, {"GeoLayout": ["(", ")"]}))
    return geo_layout_data


# get all the relevant data types cleaned up and organized for the f3d class
def construct_sm64_f3d_data_from_file(gfx: SM64_F3D, model_file: TextIO) -> SM64_F3D:
    gfx_dat = get_data_types_from_file(
        model_file,
        {
            "Vtx": ["{", "}"],
            "Gfx": ["(", ")"],
            "Light_t": [None, None],
            "Ambient_t": [None, None],
            "Lights1": [None, None],
        },
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
        )
    )
    return gfx


# Parse an aggregate group file or level data file for f3d data
def construct_model_data_from_file(aggregates: list[Path], scene: bpy.types.Scene, root_path: Path) -> SM64_F3D:
    model_files = []
    texture_files = []
    for dat_file in aggregates:
        model_files += get_all_aggregates(
            dat_file,
            (
                lambda path: "model.inc.c" in path.name,
                lambda path: path.match("*[0-9].inc.c"),  # deal with 1.inc.c files etc.
                lambda path: "painting.inc.c" in path.name,  # add way to deal with 1.inc.c filees etc.
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
                )
            )
    return sm64_f3d_data


# Parse an aggregate group file or level data file for geo layouts corresponding to list of model IDs
def find_actor_models_from_model_ids(
    geo_paths: list[Path],
    model_ids: list[str],
    level: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    col: bpy.types.Collection = None,
) -> dict[model_id, GeoLayout]:
    geo_layout_dict = construct_geo_layouts_from_file(geo_paths, root_path)
    geo_layout_per_model: dict[model_id, GeoLayout] = dict()
    for model in model_ids:
        layout_name = level.loaded_geos.get(model, None)
        if not layout_name:
            # create a warning off of this somehow?
            print(f"could not find model {model}")
            continue
        try:
            geo_layout = GraphNodes.new_subclass_dyn(geo_layout_dict, scene, layout_name, col)
            geo_layout_per_model[model] = geo_layout
        except Exception as exc:
            if exc.args[1] == "pass_linked_export":
                print(exc)
            else:
                raise Exception(exc)
    return geo_layout_per_model


# Parse an aggregate group file or level data file for geo layouts
def find_actor_models_from_geo(
    geo_paths: list[Path],
    layout_name: str,
    scene: bpy.types.Scene,
    root_path: Path,
    col: bpy.types.Collection = None,
) -> GeoLayout:
    geo_layout_dict = construct_geo_layouts_from_file(geo_paths, root_path)
    return GraphNodes.new_subclass_dyn(geo_layout_dict, scene, layout_name, col)


# Find DL references given a level geo file and a path to a level folder
def find_level_models_from_geo(
    geo_paths: list[Path], lvl: Level, scene: bpy.types.Scene, root_path: Path, col_name: str = None
) -> Level:
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
        area.geo = geo
    return lvl


# import level graphics given geo.c file, and a level object
def import_level_graphics(
    geo_paths: list[Path],
    lvl: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    aggregates: list[Path],
    cleanup: bool = False,
    col_name: str = None,
) -> Level:
    lvl = find_level_models_from_geo(geo_paths, lvl, scene, root_path, col_name=col_name)
    models = construct_model_data_from_file(aggregates, scene, root_path)
    # just a try, in case you are importing from something other than base decomp repo (like RM2C output folder)
    try:
        models.get_generic_textures(root_path)
    except:
        print("could not import genric textures, if this errors later from missing textures this may be why")
    lvl = write_level_to_bpy(lvl, scene, root_path, models, cleanup=cleanup)
    return lvl


# get all the collision data from a certain path
def find_collision_data_from_path(aggregate: Path, lvl: Level, scene: bpy.types.Scene, root_path: Path) -> Level:
    collision_files = get_all_aggregates(aggregate, (lambda path: "collision.inc.c" in path.name,), root_path)
    col_data = dict()
    for col_file in collision_files:
        if not os.path.isfile(col_file):
            continue
        with open(col_file, "r", newline="") as col_file:
            col_data.update(get_data_types_from_file(col_file, {"Collision": ["(", ")"]}))
    # search for the area terrain from available collision data
    for area in lvl.areas.values():
        area.ColFile = col_data.get(area.terrain, None)
        if not area.ColFile:
            props = scene.fast64.sm64.importer
            raise Exception(
                f"Collision {area.terrain} not found in levels/{props.level_name}/{props.level_prefix}leveldata.c"
            )
    return lvl


def write_level_collision_to_bpy(
    lvl: Level,
    scene: bpy.types.Scene,
    cleanup: bool,
    col_name: str = None,
    actor_models: dict[model_name, bpy.Types.Mesh] = None,
):
    for area_index, area in lvl.areas.items():
        if not col_name:
            col = area.root.users_collection[0]
        else:
            col = create_collection(area.root.users_collection[0], col_name)
        col_parser = Collision(area.ColFile, scene.fast64.sm64.blender_to_sm64_scale)
        col_parser.parse_collision()
        name = "SM64 {} Area {} Col".format(scene.fast64.sm64.importer.level_name, area_index)
        obj = col_parser.write_collision(scene, name, area.root, col)
        area.write_special_objects(col_parser.special_objects, col)
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


# import level collision given a level script
def import_level_collision(
    aggregate: Path, lvl: Level, scene: bpy.types.Scene, root_path: Path, cleanup: bool, col_name: str = None
) -> Level:
    lvl = find_collision_data_from_path(
        aggregate, lvl, scene, root_path
    )  # Now Each area has its collision file nicely formatted
    write_level_collision_to_bpy(lvl, scene, cleanup, col_name=col_name)
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

        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))

        group_prefix = props.group_prefix
        level_name = props.level_name
        level_prefix = props.level_prefix
        geo_paths = (
            decomp_path / "actors" / (group_prefix + "_geo.c"),
            decomp_path / "levels" / level_name / (level_prefix + "geo.c"),
        )
        model_data_paths = (
            decomp_path / "actors" / (group_prefix + ".c"),
            decomp_path / "levels" / level_name / (level_prefix + "leveldata.c"),
        )

        geo_layout = find_actor_models_from_geo(
            geo_paths, props.geo_layout, scene, decomp_path, col=rt_col
        )  # return geo layout class and write the geo layout
        models = construct_model_data_from_file(model_data_paths, scene, decomp_path)
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

        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level_data_path, script_path, geo_path = get_operator_paths(props, decomp_path)

        lvl = parse_level_script(
            [script_path, decomp_path / "levels" / "scripts.c"], scene, col=col
        )  # returns level class

        if props.import_linked_actors:
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

        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        model_data_path, script_path, geo_path = get_operator_paths(props, decomp_path)

        lvl = parse_level_script(
            [script_path, decomp_path / "levels" / "scripts.c"], scene, col=col
        )  # returns level class
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

        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level_data_path, script_path, _ = get_operator_paths(props, decomp_path)

        lvl = parse_level_script(
            [script_path, decomp_path / "levels" / "scripts.c"], scene, col=col
        )  # returns level class
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

        decomp_path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        _, script_path, _ = get_operator_paths(props, decomp_path)

        lvl = parse_level_script(
            [script_path, decomp_path / "levels" / "scripts.c"], scene, col=col
        )  # returns level class
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


class SM64_ImportProperties(PropertyGroup):
    # actor props
    geo_layout_str: StringProperty(name="geo_layout", description="Name of GeoLayout")

    group_preset: EnumProperty(
        name="group preset", description="The group you want to load geo from", items=groups_obj_export
    )
    group_0_geo_enum: EnumProperty(
        name="group 0 geos",
        description="preset geos from vanilla in group 0",
        items=[*group_0_geos, ("Custom", "Custom", "Custom")],
    )
    group_1_geo_enum: EnumProperty(
        name="group 1 geos",
        description="preset geos from vanilla in group 1",
        items=[*group_1_geos, ("Custom", "Custom", "Custom")],
    )
    group_2_geo_enum: EnumProperty(
        name="group 2 geos",
        description="preset geos from vanilla in group 2",
        items=[*group_2_geos, ("Custom", "Custom", "Custom")],
    )
    group_3_geo_enum: EnumProperty(
        name="group 3 geos",
        description="preset geos from vanilla in group 3",
        items=[*group_3_geos, ("Custom", "Custom", "Custom")],
    )
    group_4_geo_enum: EnumProperty(
        name="group 4 geos",
        description="preset geos from vanilla in group 4",
        items=[*group_4_geos, ("Custom", "Custom", "Custom")],
    )
    group_5_geo_enum: EnumProperty(
        name="group 5 geos",
        description="preset geos from vanilla in group 5",
        items=[*group_5_geos, ("Custom", "Custom", "Custom")],
    )
    group_6_geo_enum: EnumProperty(
        name="group 6 geos",
        description="preset geos from vanilla in group 6",
        items=[*group_6_geos, ("Custom", "Custom", "Custom")],
    )
    group_7_geo_enum: EnumProperty(
        name="group 7 geos",
        description="preset geos from vanilla in group 7",
        items=[*group_7_geos, ("Custom", "Custom", "Custom")],
    )
    group_8_geo_enum: EnumProperty(
        name="group 8 geos",
        description="preset geos from vanilla in group 8",
        items=[*group_8_geos, ("Custom", "Custom", "Custom")],
    )
    group_9_geo_enum: EnumProperty(
        name="group 9 geos",
        description="preset geos from vanilla in group 9",
        items=[*group_9_geos, ("Custom", "Custom", "Custom")],
    )
    group_10_geo_enum: EnumProperty(
        name="group 10 geos",
        description="preset geos from vanilla in group 10",
        items=[*group_10_geos, ("Custom", "Custom", "Custom")],
    )
    group_11_geo_enum: EnumProperty(
        name="group 11 geos",
        description="preset geos from vanilla in group 11",
        items=[*group_11_geos, ("Custom", "Custom", "Custom")],
    )
    group_12_geo_enum: EnumProperty(
        name="group 12 geos",
        description="preset geos from vanilla in group 12",
        items=[*group_12_geos, ("Custom", "Custom", "Custom")],
    )
    group_13_geo_enum: EnumProperty(
        name="group 13 geos",
        description="preset geos from vanilla in group 13",
        items=[*group_13_geos, ("Custom", "Custom", "Custom")],
    )
    group_14_geo_enum: EnumProperty(
        name="group 14 geos",
        description="preset geos from vanilla in group 14",
        items=[*group_14_geos, ("Custom", "Custom", "Custom")],
    )
    group_15_geo_enum: EnumProperty(
        name="group 15 geos",
        description="preset geos from vanilla in group 15",
        items=[*group_15_geos, ("Custom", "Custom", "Custom")],
    )
    group_16_geo_enum: EnumProperty(
        name="group 16 geos",
        description="preset geos from vanilla in group 16",
        items=[*group_16_geos, ("Custom", "Custom", "Custom")],
    )
    group_17_geo_enum: EnumProperty(
        name="group 17 geos",
        description="preset geos from vanilla in group 17",
        items=[*group_17_geos, ("Custom", "Custom", "Custom")],
    )
    common_0_geo_enum: EnumProperty(
        name="common 0 geos",
        description="preset geos from vanilla in common 0",
        items=[*common_0_geos, ("Custom", "Custom", "Custom")],
    )
    common_1_geo_enum: EnumProperty(
        name="common 1 geos",
        description="preset geos from vanilla in common 1",
        items=[*common_1_geos, ("Custom", "Custom", "Custom")],
    )
    actor_prefix_custom: StringProperty(
        name="Prefix",
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
    level_custom: StringProperty(
        name="Custom Level Name",
        description="Custom level name",
        default="",
    )
    level_prefix: StringProperty(
        name="Prefix",
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
    # add collection property for groups to look through
    # add method to collect all groups and then turn those into paths
    # look through all those path aggregates to get includes for actor importing

    @property
    def level_name(self):
        if self.level_enum == "Custom":
            return self.level_custom
        else:
            return self.level_enum

    @property
    def geo_group_name(self):
        if self.group_preset == "Custom":
            return None
        if self.group_preset == "common0":
            return "common_0_geo_enum"
        if self.group_preset == "common1":
            return "common_1_geo_enum"
        else:
            return f"group_{self.group_preset.removeprefix('group')}_geo_enum"

    @property
    def group_prefix(self):
        if self.group_preset == "custom":
            return self.actor_prefix_custom
        else:
            return self.group_preset

    @property
    def geo_layout(self):
        if self.group_preset == "custom":
            return self.geo_layout_str
        else:
            return getattr(self, self.geo_group_name)

    def draw_actor(self, layout: bpy.types.UILayout):
        box = layout.box()
        box.label(text="SM64 Actor Importer")
        box.prop(self, "group_preset")
        if self.group_preset == "Custom":
            box.prop(self, "actor_prefix_custom")
            box.prop(self, "geo_layout_str")
        else:
            box.prop(self, self.geo_group_name)
        box.prop(self, "version")
        box.prop(self, "target")

    def draw_level(self, layout: bpy.types.UILayout):
        box = layout.box()
        box.label(text="Level Importer")
        box.prop(self, "level_enum")
        if self.level_enum == "Custom":
            box.prop(self, "level_custom")
        box.prop(self, "entry")
        box.prop(self, "level_prefix")
        box.prop(self, "version")
        box.prop(self, "target")
        row = box.row()
        row.prop(self, "force_new_tex")
        row.prop(self, "as_obj")
        row.prop(self, "export_friendly")
        row.prop(self, "import_linked_actors")
        row.prop(self, "use_collection")
        if self.import_linked_actors:
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
