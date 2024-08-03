# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations


import bpy

from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    EnumProperty,
    PointerProperty,
    IntVectorProperty,
    BoolVectorProperty,
)
from bpy.types import (
    Panel,
    Menu,
    Operator,
    PropertyGroup,
)
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
from ..utility_importer import *
from ..utility import (
    transform_mtx_blender_to_n64,
    rotate_quat_n64_to_blender,
    rotate_object,
    parentObject,
    GetEnums,
    create_collection,
)
from .sm64_constants import (
    enumVersionDefs,
    enumLevelNames,
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

Num2LevelName = {
    4: "bbh",
    5: "ccm",
    7: "hmc",
    8: "ssl",
    9: "bob",
    10: "sl",
    11: "wdw",
    12: "jrb",
    13: "thi",
    14: "ttc",
    15: "rr",
    16: "castle_grounds",
    17: "bitdw",
    18: "vcutm",
    19: "bitfs",
    20: "sa",
    21: "bits",
    22: "lll",
    23: "ddd",
    24: "wf",
    25: "ending",
    26: "castle_courtyard",
    27: "pss",
    28: "cotmc",
    29: "totwc",
    30: "bowser_1",
    31: "wmotr",
    33: "bowser_2",
    34: "bowser_3",
    36: "ttm",
}

# Levelname uses a different castle inside name which is dumb
Num2Name = {6: "castle_inside", **Num2LevelName}


# Dict converting
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
        # Set level root as parent
        parentObject(levelRoot, root)
        # set default vars
        root.sm64_obj_type = "Area Root"
        root.areaIndex = num
        self.objects = []
        self.col = col

    def add_warp(self, args: list[str]):
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
            level = Num2Name.get(eval(level))
            if not level:
                level = "bob"
        warp.destLevelEnum = level
        warp.destArea = args[2]
        chkpoint = args[-1].strip()
        # Sorry for the hex users here
        if "WARP_NO_CHECKPOINT" in chkpoint or int(chkpoint.isdigit() * chkpoint + "0") == 0:
            warp.warpFlagEnum = "WARP_NO_CHECKPOINT"
        else:
            warp.warpFlagEnum = "WARP_CHECKPOINT"

    def add_object(self, args: list[str]):
        self.objects.append(args)

    def place_objects(self, col_name: str = None):
        if not col_name:
            col = self.col
        else:
            col = create_collection(self.root.users_collection[0], col_name)
        for object_args in self.objects:
            self.place_object(object_args, col)

    def place_object(self, args: list[str], col: bpy.types.Collection):
        Obj = bpy.data.objects.new("Empty", None)
        col.objects.link(Obj)
        parentObject(self.root, Obj)
        Obj.name = "Object {} {}".format(args[8], args[0])
        Obj.sm64_obj_type = "Object"
        Obj.sm64_behaviour_enum = "Custom"
        Obj.sm64_obj_behaviour = args[8].strip()
        # bparam was changed in newer version of fast64
        if hasattr(Obj, "sm64_obj_bparam"):
            Obj.sm64_obj_bparam = args[7]
        else:
            Obj.fast64.sm64.game_object.bparams = args[7]
        Obj.sm64_obj_model = args[0]
        loc = [eval(a.strip()) / self.scene.fast64.sm64.blender_to_sm64_scale for a in args[1:4]]
        # rotate to fit sm64s axis
        loc = [loc[0], -loc[2], loc[1]]
        Obj.location = loc
        # fast64 just rotations by 90 on x
        rot = Euler([math.radians(eval(a.strip())) for a in args[4:7]], "ZXY")
        rot = rotate_quat_n64_to_blender(rot).to_euler("XYZ")
        Obj.rotation_euler.rotate(rot)
        # set act mask
        mask = args[-1]
        if type(mask) == str and mask.isdigit():
            mask = eval(mask)
        form = "sm64_obj_use_act{}"
        if mask == 31:
            for i in range(1, 7, 1):
                setattr(Obj, form.format(i), True)
        else:
            for i in range(1, 7, 1):
                if mask & (1 << (i - 1)):
                    setattr(Obj, form.format(i), True)
                else:
                    setattr(Obj, form.format(i), False)


class Level(DataParser):
    def __init__(self, script: TextIO, scene: bpy.types.Scene, root: bpy.types.Object):
        self.scripts: dict[str, list[str]] = get_data_types_from_file(script, {"LevelScript": ["(", ")"]})
        self.scene = scene
        self.areas: dict[Area] = {}
        self.cur_area: int = None
        self.root = root
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
        if self.scene.level_import.use_collection:
            area_col = bpy.data.collections.new(f"{self.scene.level_import.level} area {macro.args[0]}")
            col.children.link(area_col)
        else:
            area_col = col
        area_col.objects.link(area_root)
        area_root.name = f"{self.scene.level_import.level} Area Root {macro.args[0]}"
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
        self.areas[self.cur_area].add_warp(macro.args)
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

    def SET_MENU_MUSIC(self, macro: Macro, col: bpy.types.Collection):
        return self.generic_music(macro, col)

    def generic_music(self, macro: Macro, col: bpy.types.Collection):
        root = self.areas[self.cur_area].root
        root.musicSeqEnum = "Custom"
        root.music_seq = macro.args[-1]
        return self.continue_parse

    # Don't support these for now
    def MACRO_OBJECTS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def MARIO_POS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    # use group mapping to set groups eventually
    def LOAD_MIO0(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_MIO0_TEXTURE(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse
        
    def LOAD_YAY0(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse
        
    def LOAD_YAY0_TEXTURE(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse
        
    def LOAD_VANILLA_OBJECTS(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_RAW(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    # not useful for bpy, dummy these script cmds
    def MARIO(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def INIT_LEVEL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def ALLOC_LEVEL_POOL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def FREE_LEVEL_POOL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_MODEL_FROM_GEO(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def LOAD_MODEL_FROM_DL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CALL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CALL_LOOP(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def CLEAR_LEVEL(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse

    def SLEEP_BEFORE_EXIT(self, macro: Macro, col: bpy.types.Collection):
        return self.continue_parse


class Collision(DataParser):
    def __init__(self, collision: list[str], scale: float):
        self.collision = collision
        self.scale = scale
        self.vertices = []
        # key=type,value=tri data
        self.tris = {}
        self.type = None
        self.special_objects = []
        self.tri_types = []
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
        mesh = bpy.data.meshes.new(name + " data")
        tris = []
        for t in self.tris.values():
            # deal with special tris
            if len(t[0]) > 3:
                t = [a[0:3] for a in t]
            tris.extend(t)
        mesh.from_pydata(self.vertices, [], tris)

        obj = bpy.data.objects.new(name + " Mesh", mesh)
        col.objects.link(obj)
        obj.ignore_render = True
        if parent:
            parentObject(parent, obj)
        rotate_object(-90, obj, world=1)
        polys = obj.data.polygons
        x = 0
        bpy.context.view_layer.objects.active = obj
        max = len(polys)
        for i, p in enumerate(polys):
            a = self.tri_types[x][0]
            if i >= a:
                bpy.ops.object.create_f3d_mat()  # the newest mat should be in slot[-1]
                mat = obj.data.materials[x]
                mat.collision_type_simple = "Custom"
                mat.collision_custom = self.tri_types[x][1]
                mat.name = "Sm64_Col_Mat_{}".format(self.tri_types[x][1])
                color = ((max - a) / (max), (max + a) / (2 * max - a), a / max, 1)  # Just to give some variety
                mat.f3d_mat.default_light_color = color
                # check for param
                if len(self.tri_types[x][2]) > 3:
                    mat.use_collision_param = True
                    mat.collision_param = str(self.tri_types[x][2][3])
                x += 1
                with bpy.context.temp_override(material=mat):
                    bpy.ops.material.update_f3d_nodes()
            p.material_index = x - 1
        return obj

    def parse_collision(self):
        self.parse_stream(self.collision, 0)
        # This will keep track of how to assign mats
        a = 0
        for k, v in self.tris.items():
            self.tri_types.append([a, k, v[0]])
            a += len(v)
        self.tri_types.append([a, 0])

    def COL_VERTEX(self, macro: Macro):
        self.vertices.append([eval(v) / self.scale for v in macro.args])
        return self.continue_parse

    def COL_TRI_INIT(self, macro: Macro):
        self.type = macro.args[0]
        if not self.tris.get(self.type):
            self.tris[self.type] = []
        return self.continue_parse

    def COL_TRI(self, macro: Macro):
        self.tris[self.type].append([eval(a) for a in macro.args])
        return self.continue_parse

    def COL_WATER_BOX(self, macro: Macro):
        # id, x1, z1, x2, z2, y
        self.water_boxes.append(macro.args)
        return self.continue_parse

    # not written out currently
    def SPECIAL_OBJECT(self, macro: Macro):
        self.special_objects.append(macro.args)
        return self.continue_parse

    def SPECIAL_OBJECT_WITH_YAW(self, macro: Macro):
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
        image = self.load_texture(bpy.context.scene.level_import.force_new_tex, textures, tex_path, tex)
        if image:
            tex_node.image = image
        if int(layer) > 4:
            mat.blend_method == "BLEND"

    def apply_material_settings(self, mat: bpy.types.Material, textures: dict, tex_path: Path, layer: int):
        self.set_texture_tile_mapping()
        
        if bpy.context.scene.level_import.as_obj:
            return self.apply_PBSDF_Mat(mat, textures, tex_path, layer, self.tex0)

        f3d = mat.f3d_mat

        f3d.draw_layer.sm64 = layer
        self.set_register_settings(mat, f3d)
        self.set_textures(f3d, textures, tex_path)
        with bpy.context.temp_override(material=mat):
            bpy.ops.material.update_f3d_nodes()

    def set_textures(self, f3d: F3DMaterialProperty, textures: dict, tex_path: Path):
        self.set_tex_scale(f3d)
        if self.tex0 and self.set_tex:
            self.set_tex_settings(
                f3d.tex0,
                self.load_texture(bpy.context.scene.level_import.force_new_tex, textures, tex_path, self.tex0),
                self.tiles[0 + self.base_tile],
                self.tex0.Timg,
            )
        if self.tex1 and self.set_tex:
            self.set_tex_settings(
                f3d.tex1,
                self.load_texture(bpy.context.scene.level_import.force_new_tex, textures, tex_path, self.tex1),
                self.tiles[1 + self.base_tile],
                self.tex1.Timg,
            )


class SM64_F3D(DL):
    def __init__(self, scene):
        self.scene = scene
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
    def get_f3d_data_from_model(self, start: str, last_mat: SM64_Material = None):
        DL = self.Gfx.get(start)
        self.VertBuff = [0] * 32  # If you're doing some fucky shit with a larger vert buffer it sucks to suck I guess
        if not DL:
            raise Exception("Could not find DL {}".format(start))
        self.Verts = []
        self.Tris = []
        self.UVs = []
        self.VCs = []
        self.Mats = []
        if last_mat:
            self.LastMat = last_mat
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
        tris = mesh.polygons
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
        self.Mats.append([len(tris), 0])
        for i, t in enumerate(tris):
            if i > self.Mats[ind + 1][0]:
                new = self.create_new_f3d_mat(self.Mats[ind + 1][1], mesh)
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
                t.material_index = new
                # Get texture size or assume 32, 32 otherwise
                i = mesh.materials[new].f3d_mat.tex0.tex
                if not i:
                    WH = (32, 32)
                else:
                    WH = i.size
                # Set UV data and Vertex Color Data
                for v, l in zip(t.vertices, t.loop_indices):
                    uv = self.UVs[v]
                    vcol = self.VCs[v]
                    # scale verts
                    UVmap.data[l].uv = [a * (1 / (32 * b)) if b > 0 else a * 0.001 * 32 for a, b in zip(uv, WH)]
                    # idk why this is necessary. N64 thing or something?
                    UVmap.data[l].uv[1] = UVmap.data[l].uv[1] * -1 + 1
                    Vcol.data[l].color = [a / 255 for a in vcol]

    # create a new f3d_mat given an SM64_Material class but don't create copies with same props
    def create_new_f3d_mat(self, mat: SM64_Material, mesh: bpy.types.Mesh):
        if not self.scene.level_import.force_new_tex:
            # check if this mat was used already in another mesh (or this mat if DL is garbage or something)
            # even looping n^2 is probably faster than duping 3 mats with blender speed
            for j, F3Dmat in enumerate(bpy.data.materials):
                if F3Dmat.is_f3d:
                    dupe = mat.mat_hash_f3d(F3Dmat.f3d_mat)
                    if dupe:
                        return F3Dmat
        if mesh.materials:
            mat = mesh.materials[-1]
            new = mat.id_data.copy()  # make a copy of the data block
            # add a mat slot and add mat to it
            mesh.materials.append(new)
        else:
            if self.scene.level_import.as_obj:
                NewMat = bpy.data.materials.new(f"sm64 {mesh.name.replace('Data', 'material')}")
                mesh.materials.append(NewMat)  # the newest mat should be in slot[-1] for the mesh materials
                NewMat.use_nodes = True
            else:
                bpy.ops.object.create_f3d_mat()  # the newest mat should be in slot[-1] for the mesh materials
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
    def __init__(
        self,
        geo_layouts: dict,
        scene: bpy.types.Scene,
        name: str,
        col: bpy.types.Collection,
        parent_bone: bpy.types.Bone = None,
        geo_parent: GeoArmature = None,
        stream: Any = None,
    ):
        self.geo_layouts = geo_layouts
        self.models = []
        self.children = []
        self.scene = scene
        self.stream = stream
        self.parent_transform = transform_mtx_blender_to_n64().inverted()
        self.last_transform = transform_mtx_blender_to_n64().inverted()
        self.name = name
        self.col = col
        super().__init__(parent=geo_parent)

    def parse_layer(self, layer: str):
        if not layer.isdigit():
            layer = Layers.get(layer)
            if not layer:
                layer = 1
        return layer

    @property
    def ordered_name(self):
        return f"{self.get_parser(self.stream).head}_{self.name}"

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
            self.parse_stream_from_start(new_geo_layout, macro.args[0], depth)
        return self.continue_parse

    def GEO_BRANCH(self, macro: Macro, depth: int):
        new_geo_layout = self.geo_layouts.get(macro.args[1])
        if new_geo_layout:
            self.parse_stream_from_start(new_geo_layout, macro.args[1], depth)
        # arg 0 determines if you return and continue or end after the branch
        if eval(macro.args[0]):
            return self.continue_parse
        else:
            return self.break_parse

    def GEO_END(self, macro: Macro, depth: int):
        return self.break_parse

    def GEO_RETURN(self, macro: Macro, depth: int):
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

    def GEO_ASM(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("asm", self.asm)
        # probably will need to be overridden by each subclass
        asm = geo_obj.fast64.sm64.geo_asm
        asm.param = macro.args[0]
        asm.func = macro.args[1]
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
        
    def GEO_BACKGROUND(self, macro: Macro, depth: int):
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

    def GEO_BACKGROUND_COLOR(self, macro: Macro, depth: int):
        raise Exception("you must call this function from a sublcass")


class GeoLayout(GraphNodes):
    switch = "Switch"
    translate_rotate = "Geo Translate/Rotat"
    translate = "Geo Translate Node"
    rotate = "Geo Rotation Node"
    billboard = "Geo Billboard"
    display_list = "Geo Displaylist"
    shadow = "Custom Geo Command"
    asm = "Geo ASM"
    scale = "Geo Scale"
    animated_part = "Geo Translate Node"
    custom_animated = "Custom Geo Command"
    custom = "Custom Geo Command"

    def __init__(
        self,
        geo_layouts: dict,
        root: bpy.types.Object,
        scene: bpy.types.Scene,
        name: str,
        area_root: bpy.types.Object,
        col: bpy.types.Collection = None,
        geo_parent: GeoLayout = None,
        stream: Any = None,
        pass_args: dict = None
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
            geo_obj.matrix_world @ transform_matrix_to_bpy(transform) * (1 / self.scene.fast64.sm64.blender_to_sm64_scale)
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
            parentObject(parent_obj, self.obj, keep=1)
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
        geo_obj = self.setup_geo_obj(model_data.model_name, None, layer = model_data.layer, mesh = mesh)
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

    def parse_level_geo(self, start: str, scene: bpy.types.Scene):
        geo_layout = self.geo_layouts.get(start)
        if not geo_layout:
            raise Exception(
                "Could not find geo layout {} from levels/{}/{}geo.c".format(
                    start, scene.level_import.level, scene.level_import.prefix
                )
            )
        self.stream = start
        self.parse_stream_from_start(geo_layout, start, 0)
        
    def GEO_SCALE(self, macro: Macro, depth: int):
        scale = eval(macro.args[1]) / 0x10000
        geo_obj = self.setup_geo_obj("scale", self.scale, macro.args[0])
        geo_obj.scale = (scale, scale, scale)
        return self.continue_parse

    # shadows aren't naturally supported but we can emulate them with custom geo cmds
    # change so this can be applied to mesh on root?
    def GEO_SHADOW(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("shadow empty", self.shadow)
        geo_obj.customGeoCommand = "GEO_SHADOW"
        geo_obj.customGeoCommandArgs = ", ".join(macro.args)
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
    
    # can only apply to meshes
    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        self.pass_args["render_range"] = [hexOrDecInt(range) / self.scene.fast64.sm64.blender_to_sm64_scale for range in macro.args]
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
                pass_args = self.pass_args
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
                pass_args = self.pass_args
            )
        GeoChild.parent_transform = self.last_transform
        GeoChild.parse_stream(self.geo_layouts.get(self.stream), self.stream, depth + 1)
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
        if not switch_armatures:
            self.switch_armatures = dict()
        else:
            self.switch_armatures = switch_armatures
        super().__init__(geo_layouts, scene, name, col, geo_parent=geo_parent, stream=stream)

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
            self.parent_bone = name
            switch_opt_bone = switch_armature.data.bones[name]
            self.set_geo_type(switch_opt_bone, "SwitchOption")
            # add switch option and set to mesh override
            option = switch_opt_bone.switch_options.add()
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
        location = transform_matrix_to_bpy(transform).to_translation() * (1 / self.scene.fast64.sm64.blender_to_sm64_scale)
        print(edit_bone, name, armature_obj)
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
        if self.parent_bone:
            edit_bone.parent = armature_obj.data.edit_bones.get(self.parent_bone)
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        self.bone = armature_obj.data.bones[name]
        return self.bone

    def setup_geo_obj(self, obj_name: str, geo_cmd: str, layer: int = None):
        geo_bone = self.make_root(f"{self.ordered_name} {obj_name}")
        self.set_geo_type(geo_bone, geo_cmd)
        if layer:
            self.set_draw_layer(geo_bone, layer)
        return geo_bone

    def add_model(self, model_data: ModelDat, obj_name: str, geo_cmd: str, layer: int = None):
        ind = self.get_parser(self.stream).head
        self.models.append(model_data)
        model_data.vertex_group_name = f"{self.ordered_name} {obj_name} {model_data.model_name}"
        model_data.switch_index = self.switch_index
        return self.setup_geo_obj(f"{obj_name} {model_data.model_name}", geo_cmd, layer)

    def parse_armature(self, start: str, scene: bpy.types.Scene):
        geo_layout = self.geo_layouts.get(start)
        if not geo_layout:
            raise Exception(
                "Could not find geo layout {} from levels/{}/{}geo.c".format(
                    start, scene.level_import.level, scene.level_import.prefix
                )
            )
        bpy.context.view_layer.objects.active = self.get_or_init_geo_armature()
        self.stream = start
        self.parse_stream_from_start(geo_layout, start, 0)

    def GEO_ASM(self, macro: Macro, depth: int):
        geo_obj = self.setup_geo_obj("asm", self.asm)
        geo_obj.func_param = int(macro.args[0])
        geo_obj.geo_func = macro.args[1]
        return self.continue_parse
        
    def GEO_SHADOW(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("shadow", self.shadow)
        geo_bone.shadow_solidity = hexOrDecInt(macro.args[1]) / 255
        geo_bone.shadow_scale = hexOrDecInt(macro.args[2])
        return self.continue_parse    

    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        geo_bone = self.setup_geo_obj("render_range", self.render_area)
        geo_bone.culling_radius = macro.args
        return self.continue_parse
        
    # can switch children have their own culling radius? does it have to
    # be on the root? this currently allows each independent geo to have one
    def GEO_CULLING_RADIUS(self, macro: Macro, depth: int):
        geo_armature = self.get_or_init_geo_armature()
        geo_armature.use_render_area = True # cringe name, it is cull not render area
        geo_armature.culling_radius = macro.args
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

    # add some stuff here
    def GEO_HELD_OBJECT(self, macro: Macro, depth: int):
        return self.continue_parse
    
    def GEO_OPEN_NODE(self, macro: Macro, depth: int):
        if self.bone:
            GeoChild = GeoArmature(
                self.geo_layouts,
                self.get_or_init_geo_armature(),
                self.scene,
                self.name,
                self.col,
                is_switch_child=(self.bone.geo_cmd == self.switch),
                parent_bone=self.bone,
                geo_parent=self,
                stream=self.stream,
                switch_armatures=self.switch_armatures,
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
                switch_armatures=self.switch_armatures,
            )
        GeoChild.parent_transform = self.last_transform
        GeoChild.parse_stream(self.geo_layouts.get(self.stream), self.stream, depth + 1)
        self.children.append(GeoChild)
        return self.continue_parse


# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------

# parse aggregate files, and search for sm64 specific fast64 export name schemes
def get_all_aggregates(aggregate: Path, filenames: Union[str, tuple[str]], root_path: Path) -> list[Path]:
    with open(aggregate, "r", newline="") as aggregate:
        caught_files = parse_aggregate_file(aggregate, filenames, root_path)
        # catch fast64 includes
        fast64 = parse_aggregate_file(aggregate, "leveldata.inc.c", root_path)
        if fast64:
            with open(fast64[0], "r", newline="") as fast64_dat:
                caught_files.extend(parse_aggregate_file(fast64_dat, filenames, root_path))
    return caught_files


# given a path, get a level object by parsing the script.c file
def parse_level_script(script_file: Path, scene: bpy.types.Scene, col: bpy.types.Collection = None):
    Root = bpy.data.objects.new("Empty", None)
    if not col:
        scene.collection.objects.link(Root)
    else:
        col.objects.link(Root)
    Root.name = f"Level Root {scene.level_import.level}"
    Root.sm64_obj_type = "Level Root"
    # Now parse the script and get data about the level
    # Store data in attribute of a level class then assign later and return class
    with open(script_file, "r", newline="") as script_file:
        lvl = Level(script_file, scene, Root)
    entry = scene.level_import.entry.format(scene.level_import.level)
    lvl.parse_level_script(entry, col=col)
    return lvl


# write the objects from a level object
def write_level_objects(lvl: Level, col_name: str = None):
    for area in lvl.areas.values():
        area.place_objects(col_name=col_name)


# from a geo layout, create all the mesh's
def write_armature_to_bpy(
    geo_armature: GeoArmature,
    scene: bpy.types.Scene,
    f3d_dat: SM64_F3D,
    root_path: Path,
    parsed_model_data: dict,
    cleanup: bool = True,
):
    parsed_model_data = recurse_armature(geo_armature, scene, f3d_dat, root_path, parsed_model_data, cleanup=cleanup)

    objects_by_armature = dict()
    for model_dat in parsed_model_data.values():
        if not objects_by_armature.get(model_dat.armature_obj, None):
            objects_by_armature[model_dat.armature_obj] = [model_dat.object]
        else:
            objects_by_armature[model_dat.armature_obj].append(model_dat.object)

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


def apply_mesh_data(
    f3d_dat: SM64_F3D, obj: bpy.types.Object, mesh: bpy.types.Mesh, layer: int, root_path: Path, cleanup: bool = True
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
    parsed_model_data: dict,
    cleanup: bool = True,
):
    if geo_armature.models:
        # create a mesh for each one
        for model_data in geo_armature.models:
            name = f"{model_data.model_name} data"
            if name in parsed_model_data.keys():
                mesh = parsed_model_data[name].mesh
                name = 0
            else:
                mesh = bpy.data.meshes.new(name)
                model_data.mesh = mesh
                parsed_model_data[name] = model_data
                [verts, tris] = f3d_dat.get_f3d_data_from_model(model_data.model_name)
                mesh.from_pydata(verts, [], tris)

            obj = bpy.data.objects.new(f"{model_data.model_name} obj", mesh)

            obj.matrix_world = transform_matrix_to_bpy(model_data.transform) * (1 / scene.fast64.sm64.blender_to_sm64_scale)

            model_data.object = obj
            geo_armature.col.objects.link(obj)
            if model_data.vertex_group_name:
                vertex_group = obj.vertex_groups.new(name=model_data.vertex_group_name)
                vertex_group.add([vert.index for vert in obj.data.vertices], 1, "ADD")
            if model_data.switch_index:
                model_data.armature_obj = geo_armature.switch_armatures[model_data.switch_index]
            else:
                model_data.armature_obj = geo_armature.armature

            if name:
                layer = geo_armature.parse_layer(model_data.layer)
                apply_mesh_data(f3d_dat, obj, mesh, layer, root_path, cleanup)

    if not geo_armature.children:
        return parsed_model_data
    for arm in geo_armature.children:
        parsed_model_data = recurse_armature(arm, scene, f3d_dat, root_path, parsed_model_data, cleanup=cleanup)
    return parsed_model_data


# from a geo layout, create all the mesh's
def write_geo_to_bpy(
    geo: GeoLayout, scene: bpy.types.Scene, f3d_dat: SM64_F3D, root_path: Path, meshes: dict, cleanup: bool = True
):
    if geo.models:
        # create a mesh for each one.
        for model_data in geo.models:
            name = f"{model_data.model_name} data"
            if name in meshes.keys():
                mesh = meshes[name]
                name = 0
            else:
                mesh = bpy.data.meshes.new(name)
                meshes[name] = mesh
                [verts, tris] = f3d_dat.get_f3d_data_from_model(model_data.model_name)
                mesh.from_pydata(verts, [], tris)

            # swap out placeholder mesh data
            model_data.object.data = mesh

            if name:
                apply_mesh_data(f3d_dat, model_data.object, mesh, str(geo.parse_layer(model_data.layer)), root_path, cleanup)

    if not geo.children:
        return
    for g in geo.children:
        write_geo_to_bpy(g, scene, f3d_dat, root_path, meshes, cleanup=cleanup)


# write the gfx for a level given the level data, and f3d data
def write_level_to_bpy(lvl: Level, scene: bpy.types.Scene, root_path: Path, f3d_dat: SM64_F3D, cleanup: bool = True):
    for area in lvl.areas.values():
        write_geo_to_bpy(area.geo, scene, f3d_dat, root_path, dict(), cleanup=cleanup)
    return lvl


# given a geo.c file and a path, return cleaned up geo layouts in a dict
def construct_geo_layouts_from_file(geo_path: Path, root_path: Path):
    geo_layout_files = get_all_aggregates(geo_path, "geo.inc.c", root_path)
    if not geo_layout_files:
        return
    # because of fast64, these can be recursively defined (though I expect only a depth of one)
    for file in geo_layout_files:
        geo_layout_files.extend(get_all_aggregates(file, "geo.inc.c", root_path))
    geo_layout_data = {}  # stores cleaned up geo layout lines
    for geo_file in geo_layout_files:
        with open(geo_file, "r", newline="") as geo_file:
            geo_layout_data.update(get_data_types_from_file(geo_file, {"GeoLayout": ["(", ")"]}))
    return geo_layout_data


# get all the relevant data types cleaned up and organized for the f3d class
def construct_sm64_f3d_data_from_file(gfx: SM64_F3D, model_file: TextIO):
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
def construct_model_data_from_file(aggregate: Path, scene: bpy.types.Scene, root_path: Path):
    model_files = get_all_aggregates(
        aggregate,
        (
            "model.inc.c",
            "painting.inc.c",
        ),
        root_path,
    )
    texture_files = get_all_aggregates(
        aggregate,
        (
            "texture.inc.c",
            "textureNew.inc.c",
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


# Parse an aggregate group file or level data file for geo layouts
def find_actor_models_from_geo(
    geo_path: Path,
    layout_name: str,
    scene: bpy.types.Scene,
    root_obj: bpy.types.Object,
    root_path: Path,
    col: bpy.types.Collection = None,
):
    geo_layout_dict = construct_geo_layouts_from_file(geo_path, root_path)
    geo_layout = GeoLayout(geo_layout_dict, root_obj, scene, "{}".format(layout_name), root_obj, col=col)
    geo_layout.parse_level_geo(layout_name, scene)
    return geo_layout


def find_armature_models_from_geo(
    geo_path: Path,
    layout_name: str,
    scene: bpy.types.Scene,
    armature_obj: bpy.types.Armature,
    root_path: Path,
    col: bpy.types.Collection,
):
    geo_layout_dict = construct_geo_layouts_from_file(geo_path, root_path)
    geo_armature = GeoArmature(geo_layout_dict, armature_obj, scene, "{}".format(layout_name), col, stream=layout_name)
    geo_armature.parse_armature(layout_name, scene)
    return geo_armature


# Find DL references given a level geo file and a path to a level folder
def find_level_models_from_geo(geo: TextIO, lvl: Level, scene: bpy.types.Scene, root_path: Path, col_name: str = None):
    GeoLayouts = construct_geo_layouts_from_file(geo, root_path)
    for area_index, area in lvl.areas.items():
        if col_name:
            col = create_collection(area.root.users_collection[0], col_name)
        else:
            col = None
        Geo = GeoLayout(
            GeoLayouts, area.root, scene, f"GeoRoot {scene.level_import.level} {area_index}", area.root, col=col
        )
        Geo.parse_level_geo(area.geo, scene)
        area.geo = Geo
    return lvl


# import level graphics given geo.c file, and a level object
def import_level_graphics(
    geo: TextIO,
    lvl: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    aggregate: Path,
    cleanup: bool = True,
    col_name: str = None,
):
    lvl = find_level_models_from_geo(geo, lvl, scene, root_path, col_name=col_name)
    models = construct_model_data_from_file(aggregate, scene, root_path)
    # just a try, in case you are importing from something other than base decomp repo (like RM2C output folder)
    try:
        models.get_generic_textures(root_path)
    except:
        print("could not import genric textures, if this errors later from missing textures this may be why")
    lvl = write_level_to_bpy(lvl, scene, root_path, models, cleanup=cleanup)
    return lvl


# get all the collision data from a certain path
def find_collision_data_from_path(aggregate: Path, lvl: Level, scene: bpy.types.Scene, root_path: Path):
    collision_files = get_all_aggregates(aggregate, "collision.inc.c", root_path)
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
            raise Exception(
                f"Collision {area.terrain} not found in levels/{scene.level_import.level}/{scene.level_import.prefix}leveldata.c"
            )
    return lvl


def write_level_collision_to_bpy(lvl: Level, scene: bpy.types.Scene, cleanup: bool, col_name: str = None):
    for area_index, area in lvl.areas.items():
        if not col_name:
            col = area.root.users_collection[0]
        else:
            col = create_collection(area.root.users_collection[0], col_name)
        col_parser = Collision(area.ColFile, scene.fast64.sm64.blender_to_sm64_scale)
        col_parser.parse_collision()
        name = "SM64 {} Area {} Col".format(scene.level_import.level, area_index)
        obj = col_parser.write_collision(scene, name, area.root, col=col)
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
    aggregate: Path,
    lvl: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    cleanup: bool,
    col_name: str = None,
):
    lvl = find_collision_data_from_path(
        aggregate, lvl, scene, root_path
    )  # Now Each area has its collision file nicely formatted
    write_level_collision_to_bpy(lvl, scene, cleanup, col_name=col_name)
    return lvl


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------


class SM64_OT_Act_Import(Operator):
    bl_label = "Import Actor"
    bl_idname = "wm.sm64_import_actor"
    bl_options = {"REGISTER", "UNDO"}

    cleanup: bpy.props.BoolProperty(name="Cleanup Mesh", default=1)

    def execute(self, context):
        scene = context.scene
        rt_col = context.collection
        scene.gameEditorMode = "SM64"
        path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        folder = path / scene.actor_import.folder_type
        layout_name = scene.actor_import.geo_layout
        prefix = scene.actor_import.prefix
        # different name schemes and I have no clean way to deal with it
        if "actor" in scene.actor_import.folder_type:
            geo_path = folder / (prefix + "_geo.c")
            leveldat = folder / (prefix + ".c")
        else:
            geo_path = folder / (prefix + "geo.c")
            leveldat = folder / (prefix + "leveldata.c")
        root_obj = bpy.data.objects.new("Empty", None)
        root_obj.name = f"Actor {scene.actor_import.geo_layout}"
        rt_col.objects.link(root_obj)

        geo_layout = find_actor_models_from_geo(
            geo_path, layout_name, scene, root_obj, folder, col=rt_col
        )  # return geo layout class and write the geo layout
        models = construct_model_data_from_file(leveldat, scene, folder)
        # just a try, in case you are importing from not the base decomp repo
        try:
            models.get_generic_textures(path)
        except:
            print("could not import genric textures, if this errors later from missing textures this may be why")
        write_geo_to_bpy(geo_layout, scene, models, folder, {}, cleanup=self.cleanup)
        return {"FINISHED"}


class SM64_OT_Armature_Import(Operator):
    bl_label = "Import Armature"
    bl_idname = "wm.sm64_import_armature"
    bl_options = {"REGISTER", "UNDO"}

    cleanup: bpy.props.BoolProperty(name="Cleanup Mesh", default=1)

    def execute(self, context):
        scene = context.scene
        rt_col = context.collection
        scene.gameEditorMode = "SM64"
        path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        folder = path / scene.actor_import.folder_type
        layout_name = scene.actor_import.geo_layout
        prefix = scene.actor_import.prefix
        # different name schemes and I have no clean way to deal with it
        if "actor" in scene.actor_import.folder_type:
            geo_path = folder / (prefix + "_geo.c")
            leveldat = folder / (prefix + ".c")
        else:
            geo_path = folder / (prefix + "geo.c")
            leveldat = folder / (prefix + "leveldata.c")
        name = f"Actor {scene.actor_import.geo_layout}"
        armature_obj = bpy.data.objects.new(name, bpy.data.armatures.new(name))
        rt_col.objects.link(armature_obj)

        geo_armature = find_armature_models_from_geo(
            geo_path, layout_name, scene, armature_obj, folder, col=rt_col
        )  # return geo layout class and write the geo layout
        models = construct_model_data_from_file(leveldat, scene, folder)
        # just a try, in case you are importing from not the base decomp repo
        try:
            models.get_generic_textures(path)
        except:
            print("could not import genric textures, if this errors later from missing textures this may be why")
        write_armature_to_bpy(geo_armature, scene, models, folder, {}, cleanup=self.cleanup)
        return {"FINISHED"}


class SM64_OT_Lvl_Import(Operator):
    bl_label = "Import Level"
    bl_idname = "wm.sm64_import_level"

    cleanup = True

    def execute(self, context):
        scene = context.scene

        col = context.collection
        if scene.level_import.use_collection:
            obj_col = f"{scene.level_import.level} obj"
            gfx_col = f"{scene.level_import.level} gfx"
            col_col = f"{scene.level_import.level} col"
        else:
            obj_col = gfx_col = col_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.level_import.prefix
        path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level = path / "levels" / scene.level_import.level
        script = level / (prefix + "script.c")
        geo = level / (prefix + "geo.c")
        leveldat = level / (prefix + "leveldata.c")
        lvl = parse_level_script(script, scene, col=col)  # returns level class
        write_level_objects(lvl, col_name=obj_col)
        lvl = import_level_collision(leveldat, lvl, scene, path, self.cleanup, col_name=col_col)
        lvl = import_level_graphics(geo, lvl, scene, path, leveldat, cleanup=self.cleanup, col_name=gfx_col)
        return {"FINISHED"}


class SM64_OT_Lvl_Gfx_Import(Operator):
    bl_label = "Import Gfx"
    bl_idname = "wm.sm64_import_level_gfx"

    cleanup = True

    def execute(self, context):
        scene = context.scene

        col = context.collection
        if scene.level_import.use_collection:
            gfx_col = f"{scene.level_import.level} gfx"
        else:
            gfx_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.level_import.prefix
        path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level = path / "levels" / scene.level_import.level
        script = level / (prefix + "script.c")
        geo = level / (prefix + "geo.c")
        model = level / (prefix + "leveldata.c")
        lvl = parse_level_script(script, scene, col=col)  # returns level class
        lvl = import_level_graphics(geo, lvl, scene, path, model, cleanup=self.cleanup, col_name=gfx_col)
        return {"FINISHED"}


class SM64_OT_Lvl_Col_Import(Operator):
    bl_label = "Import Collision"
    bl_idname = "wm.sm64_import_level_col"

    cleanup = True

    def execute(self, context):
        scene = context.scene

        col = context.collection
        if scene.level_import.use_collection:
            col_col = f"{scene.level_import.level} collision"
        else:
            col_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.level_import.prefix
        path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level = path / "levels" / scene.level_import.level
        script = level / (prefix + "script.c")
        model = level / (prefix + "leveldata.c")
        lvl = parse_level_script(script, scene, col=col)  # returns level class
        lvl = import_level_collision(model, lvl, scene, path, self.cleanup, col_name=col_col)
        return {"FINISHED"}


class SM64_OT_Obj_Import(Operator):
    bl_label = "Import Objects"
    bl_idname = "wm.sm64_import_object"

    def execute(self, context):
        scene = context.scene

        col = context.collection
        if scene.level_import.use_collection:
            obj_col = f"{scene.level_import.level} objs"
        else:
            obj_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.level_import.prefix
        path = Path(bpy.path.abspath(scene.fast64.sm64.decomp_path))
        level = path / "levels" / scene.level_import.level
        script = level / (prefix + "script.c")
        lvl = parse_level_script(script, scene, col=col)  # returns level class
        write_level_objects(lvl, col_name=obj_col)
        return {"FINISHED"}


# ------------------------------------------------------------------------
#    Props
# ------------------------------------------------------------------------


class ActorImport(PropertyGroup):
    geo_layout_str: StringProperty(
        name="geo_layout",
        description="Name of GeoLayout"
    )
    folder_type: EnumProperty(
        name="Source",
        description="Whether the actor is from a level or from a group",
        items=[
            ("actors", "actors", ""),
            ("levels", "levels", ""),
        ],
    )
    group_preset: EnumProperty(
        name="group preset",
        description="The group you want to load geo from",
        items=groups_obj_export
    )
    group_0_geo_enum: EnumProperty(
        name="group 0 geos",
        description="preset geos from vanilla in group 0",
        items=[*group_0_geos, ("Custom", "Custom", "Custom")]
    )
    group_1_geo_enum: EnumProperty(
            name="group 1 geos",
            description="preset geos from vanilla in group 1",
            items=[*group_1_geos, ("Custom", "Custom", "Custom")]
        )
    group_2_geo_enum: EnumProperty(
            name="group 2 geos",
            description="preset geos from vanilla in group 2",
            items=[*group_2_geos, ("Custom", "Custom", "Custom")]
        )
    group_3_geo_enum: EnumProperty(
            name="group 3 geos",
            description="preset geos from vanilla in group 3",
            items=[*group_3_geos, ("Custom", "Custom", "Custom")]
        )
    group_4_geo_enum: EnumProperty(
            name="group 4 geos",
            description="preset geos from vanilla in group 4",
            items=[*group_4_geos, ("Custom", "Custom", "Custom")]
        )
    group_5_geo_enum: EnumProperty(
            name="group 5 geos",
            description="preset geos from vanilla in group 5",
            items=[*group_5_geos, ("Custom", "Custom", "Custom")]
        )
    group_6_geo_enum: EnumProperty(
            name="group 6 geos",
            description="preset geos from vanilla in group 6",
            items=[*group_6_geos, ("Custom", "Custom", "Custom")]
        )
    group_7_geo_enum: EnumProperty(
            name="group 7 geos",
            description="preset geos from vanilla in group 7",
            items=[*group_7_geos, ("Custom", "Custom", "Custom")]
        )
    group_8_geo_enum: EnumProperty(
            name="group 8 geos",
            description="preset geos from vanilla in group 8",
            items=[*group_8_geos, ("Custom", "Custom", "Custom")]
        )
    group_9_geo_enum: EnumProperty(
            name="group 9 geos",
            description="preset geos from vanilla in group 9",
            items=[*group_9_geos, ("Custom", "Custom", "Custom")]
        )
    group_10_geo_enum: EnumProperty(
            name="group 10 geos",
            description="preset geos from vanilla in group 10",
            items=[*group_10_geos, ("Custom", "Custom", "Custom")]
        )
    group_11_geo_enum: EnumProperty(
            name="group 11 geos",
            description="preset geos from vanilla in group 11",
            items=[*group_11_geos, ("Custom", "Custom", "Custom")]
        )
    group_12_geo_enum: EnumProperty(
            name="group 12 geos",
            description="preset geos from vanilla in group 12",
            items=[*group_12_geos, ("Custom", "Custom", "Custom")]
        )
    group_13_geo_enum: EnumProperty(
            name="group 13 geos",
            description="preset geos from vanilla in group 13",
            items=[*group_13_geos, ("Custom", "Custom", "Custom")]
        )
    group_14_geo_enum: EnumProperty(
            name="group 14 geos",
            description="preset geos from vanilla in group 14",
            items=[*group_14_geos, ("Custom", "Custom", "Custom")]
        )
    group_15_geo_enum: EnumProperty(
            name="group 15 geos",
            description="preset geos from vanilla in group 15",
            items=[*group_15_geos, ("Custom", "Custom", "Custom")]
        )
    group_16_geo_enum: EnumProperty(
            name="group 16 geos",
            description="preset geos from vanilla in group 16",
            items=[*group_16_geos, ("Custom", "Custom", "Custom")]
        )
    group_17_geo_enum: EnumProperty(
            name="group 17 geos",
            description="preset geos from vanilla in group 17",
            items=[*group_17_geos, ("Custom", "Custom", "Custom")]
        )
    common_0_geo_enum: EnumProperty(
            name="common 0 geos",
            description="preset geos from vanilla in common 0",
            items=[*common_0_geos, ("Custom", "Custom", "Custom")]
        )
    common_1_geo_enum: EnumProperty(
            name="common 1 geos",
            description="preset geos from vanilla in common 1",
            items=[*common_1_geos, ("Custom", "Custom", "Custom")]
        )
    prefix_custom: StringProperty(
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
    def prefix(self):
        if self.folder_type == "levels" or self.group_preset == "custom":
            return self.prefix_custom
        else:
            return self.group_preset
    
    @property
    def geo_layout(self):
        if self.folder_type == "levels" or self.group_preset == "custom":
            return self.geo_layout_str
        else:
            return getattr(self, self.geo_group_name)
    
    def draw(self, layout: bpy.types.UILayout):
        layout.prop(self, "folder_type")
        layout.prop(self, "group_preset")
        if self.folder_type == "levels" or self.group_preset == "custom":
            layout.prop(self, "prefix_custom")
            layout.prop(self, "geo_layout_str")
        else:
            layout.prop(self, self.geo_group_name)
        layout.prop(self, "version")
        layout.prop(self, "target")


class LevelImport(PropertyGroup):
    level: EnumProperty(
        name="Level",
        description="Choose a level",
        items=enumLevelNames,
    )
    prefix: StringProperty(
        name="Prefix",
        description="Prefix before expected aggregator files like script.c, leveldata.c and geo.c. Leave blank unless using custom files",
        default="",
    )
    entry: StringProperty(
        name="Entrypoint", description="The name of the level script entry variable. Levelname is put between braces.", default="level_{}_entry"
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
    
    def draw(self, layout: bpy.types.UILayout):
        layout.prop(self, "level")
        layout.prop(self, "entry")
        layout.prop(self, "prefix")
        layout.prop(self, "version")
        layout.prop(self, "target")
        row = layout.row()
        row.prop(self, "force_new_tex")
        row.prop(self, "as_obj")
        row.prop(self, "use_collection")

# ------------------------------------------------------------------------
#    Panels
# ------------------------------------------------------------------------


class Level_PT_Panel(Panel):
    bl_label = "SM64 Level Importer"
    bl_idname = "sm64_level_importer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SM64 C Importer"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return context.scene is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        level_import = scene.level_import
        level_import.draw(layout)
        layout.operator("wm.sm64_import_level")
        layout.operator("wm.sm64_import_level_gfx")
        layout.operator("wm.sm64_import_level_col")
        layout.operator("wm.sm64_import_object")


class Actor_PT_Panel(Panel):
    bl_label = "SM64 Actor Importer"
    bl_idname = "sm64_actor_importer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SM64 C Importer"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return context.scene is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        actor_import = scene.actor_import
        actor_import.draw(layout)
        layout.operator("wm.sm64_import_actor")
        layout.operator("wm.sm64_import_armature")


classes = (
    LevelImport,
    ActorImport,
    SM64_OT_Lvl_Import,
    SM64_OT_Lvl_Gfx_Import,
    SM64_OT_Lvl_Col_Import,
    SM64_OT_Obj_Import,
    SM64_OT_Act_Import,
    SM64_OT_Armature_Import,
    Level_PT_Panel,
    Actor_PT_Panel,
)


def sm64_import_register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.level_import = PointerProperty(type=LevelImport)
    bpy.types.Scene.actor_import = PointerProperty(type=ActorImport)


def sm64_import_unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.level_import
    del bpy.types.Scene.actor_import
