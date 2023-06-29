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

# from SM64classes import *

from ..f3d.f3d_import import *
from ..utility_importer import *
from ..utility import (
    rotate_quat_n64_to_blender,
    rotate_object,
    parentObject,
    GetEnums,
    create_collection,
)
from .sm64_constants import (
    enumVersionDefs,
    enumLevelNames,
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
        loc = [eval(a.strip()) / self.scene.blenderToSM64Scale for a in args[1:4]]
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
        scale = self.scene.blenderToSM64Scale
        if not col:
            col = self.scene.collection
        self.parse_stream(script_stream, entry, col)
        return self.areas

    def AREA(self, macro: Macro, col: bpy.types.Collection):
        area_root = bpy.data.objects.new("Empty", None)
        if self.scene.LevelImp.UseCol:
            area_col = bpy.data.collections.new(f"{self.scene.LevelImp.Level} area {args[0]}")
            col.children.link(area_col)
        else:
            area_col = col
        area_col.objects.link(area_root)
        area_root.name = f"{self.scene.LevelImp.Level} Area Root {macro.args[0]}"
        self.areas[macro.args[0]] = Area(
            area_root, macro.args[1], self.root, int(macro.args[0]), self.scene, area_col
        )
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

    def WriteWaterBoxes(
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

    def WriteCollision(
        self, scene: bpy.types.Scene, name: str, parent: bpy.types.Object, col: bpy.types.Collection = None
    ):
        if not col:
            col = scene.collection
        self.WriteWaterBoxes(scene, parent, name, col)
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
                override = bpy.context.copy()
                override["material"] = mat
                bpy.ops.material.update_f3d_nodes(override)
            p.material_index = x - 1
        return obj

    def GetCollision(self):
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
    def LoadTexture(self, ForceNewTex: bool, textures: dict, path: Path, tex: Texture):
        if not tex:
            return None
        Timg = textures.get(tex.Timg)[0].split("/")[-1]
        Timg = Timg.replace("#include ", "").replace('"', "").replace("'", "").replace("inc.c", "png")
        i = bpy.data.images.get(Timg)
        if not i or ForceNewTex:
            Timg = textures.get(tex.Timg)[0]
            Timg = Timg.replace("#include ", "").replace('"', "").replace("'", "").replace("inc.c", "png")
            # deal with duplicate pathing (such as /actors/actors etc.)
            Extra = path.relative_to(Path(bpy.path.abspath(bpy.context.scene.decompPath)))
            for e in Extra.parts:
                Timg = Timg.replace(e + "/", "")
            # deal with actor import path not working for shared textures
            if "textures" in Timg:
                fp = Path(bpy.path.abspath(bpy.context.scene.decompPath)) / Timg
            else:
                fp = path / Timg
            return bpy.data.images.load(filepath=str(fp))
        else:
            return i

    def ApplyMatSettings(self, mat: bpy.types.Material, textures: dict, path: Path, layer: int):
        if bpy.context.scene.LevelImp.AsObj:
            return self.ApplyPBSDFMat(mat, textures, path, layer, self.tex0)
        f3d = mat.f3d_mat  # This is kure's custom property class for materials
        f3d.draw_layer.sm64 = layer
        # set color registers if they exist
        if hasattr(self, "fog_position"):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_position[0] = eval(self.fog_pos[0])
            f3d.fog_position[1] = eval(self.fog_pos[1])
        if hasattr(self, "fog_color"):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_color = self.ConvertColor(self.fog_color)
        if hasattr(self, "light_col"):
            # this is a dict but I'll only use the first color for now
            f3d.set_lights = True
            if self.light_col.get(1):
                f3d.default_light_color = self.ConvertColor(eval(self.light_col[1]).to_bytes(4, "big"))
        if hasattr(self, "env_color"):
            f3d.set_env = True
            f3d.env_color = self.ConvertColor(self.env_color[-4:])
        if hasattr(self, "prim_color"):
            prim = self.prim_color
            f3d.set_prim = True
            f3d.prim_lod_min = int(prim[0])
            f3d.prim_lod_frac = int(prim[1])
            f3d.prim_color = self.ConvertColor(prim[-4:])
        # I set these but they aren't properly stored because they're reset by fast64 or something
        # its better to have defaults than random 2 cycles
        self.SetGeoMode(f3d.rdp_settings, mat)

        if self.TwoCycle:
            f3d.rdp_settings.g_mdsft_cycletype = "G_CYC_2CYCLE"
        else:
            f3d.rdp_settings.g_mdsft_cycletype = "G_CYC_1CYCLE"
        # make combiner custom
        f3d.presetName = "Custom"
        self.SetCombiner(f3d)

        # deal with custom render modes
        if hasattr(self, "RenderMode"):
            self.SetRenderMode(f3d)
        # g texture handle
        if hasattr(self, "set_tex"):
            # not exactly the same but gets the point across maybe?
            f3d.tex0.tex_set = self.set_tex
            f3d.tex1.tex_set = self.set_tex
            # tex scale gets set to 0 when textures are disabled which is automatically done
            # often to save processing power between mats or something, or just adhoc bhv
            if f3d.rdp_settings.g_tex_gen or any([a < 1 and a > 0 for a in self.tex_scale]):
                f3d.scale_autoprop = False
                f3d.tex_scale = self.tex_scale
            if not self.set_tex:
                # Update node values
                override = bpy.context.copy()
                override["material"] = mat
                bpy.ops.material.update_f3d_nodes(override)
                del override
                return
        # Try to set an image
        # texture 0 then texture 1
        if self.tex0:
            i = self.LoadTexture(bpy.context.scene.LevelImp.ForceNewTex, textures, path, self.tex0)
            tex0 = f3d.tex0
            tex0.tex_reference = str(self.tex0.Timg)  # setting prop for hash purposes
            tex0.tex_set = True
            tex0.tex = i
            tex0.tex_format = self.EvalFmt(self.tiles[0])
            tex0.autoprop = False
            Sflags = self.EvalFlags(self.tiles[0].Sflags)
            for f in Sflags:
                setattr(tex0.S, f, True)
            Tflags = self.EvalFlags(self.tiles[0].Tflags)
            for f in Sflags:
                setattr(tex0.T, f, True)
            tex0.S.low = self.tiles[0].Slow
            tex0.T.low = self.tiles[0].Tlow
            tex0.S.high = self.tiles[0].Shigh
            tex0.T.high = self.tiles[0].Thigh

            tex0.S.mask = self.tiles[0].SMask
            tex0.T.mask = self.tiles[0].TMask
        if self.tex1:
            i = self.LoadTexture(bpy.context.scene.LevelImp.ForceNewTex, textures, path, self.tex1)
            tex1 = f3d.tex1
            tex1.tex_reference = str(self.tex1.Timg)  # setting prop for hash purposes
            tex1.tex_set = True
            tex1.tex = i
            tex1.tex_format = self.EvalFmt(self.tiles[1])
            Sflags = self.EvalFlags(self.tiles[1].Sflags)
            for f in Sflags:
                setattr(tex1.S, f, True)
            Tflags = self.EvalFlags(self.tiles[1].Tflags)
            for f in Sflags:
                setattr(tex1.T, f, True)
            tex1.S.low = self.tiles[1].Slow
            tex1.T.low = self.tiles[1].Tlow
            tex1.S.high = self.tiles[1].Shigh
            tex1.T.high = self.tiles[1].Thigh

            tex1.S.mask = self.tiles[0].SMask
            tex1.T.mask = self.tiles[0].TMask
        # Update node values
        override = bpy.context.copy()
        override["material"] = mat
        bpy.ops.material.update_f3d_nodes(override)
        del override


class SM64_F3D(DL):
    def __init__(self, scene: bpy.types.Scene):
        self.Vtx = {}
        self.Gfx = {}
        self.Light_t = {}
        self.Ambient_t = {}
        self.Lights1 = {}
        self.Textures = {}
        self.scene = scene
        self.num = 0
        super().__init__()

    # Textures only contains the texture data found inside the model.inc.c file and the texture.inc.c file
    def GetGenericTextures(self, root_path: Path):
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
            t = open(t, "r", newline='')
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
    def GetDataFromModel(self, start: str):
        DL = self.Gfx.get(start)
        self.VertBuff = [0] * 32  # If you're doing some fucky shit with a larger vert buffer it sucks to suck I guess
        if not DL:
            raise Exception("Could not find DL {}".format(start))
        self.Verts = []
        self.Tris = []
        self.UVs = []
        self.VCs = []
        self.Mats = []
        self.LastMat = SM64_Material()
        self.parse_stream(DL, start)
        self.NewMat = 0
        self.StartName = start
        print(self.Verts, self.Tris, start)
        return [self.Verts, self.Tris]

    def MakeNewMat(self):
        if self.NewMat:
            self.NewMat = 0
            self.Mats.append([len(self.Tris) - 1, self.LastMat])
            self.LastMat = deepcopy(self.LastMat)  # for safety
            self.LastMat.name = self.num + 1
            self.num += 1

    # turn member of vtx str arr into vtx args
    def ParseVert(self, Vert: str):
        v = Vert.replace("{", "").replace("}", "").split(",")
        num = lambda x: [eval(a) for a in x]
        pos = num(v[:3])
        uv = num(v[4:6])
        vc = num(v[6:10])
        return [pos, uv, vc]

    # given tri args in gbi cmd, give appropriate tri indices in vert list
    def ParseTri(self, Tri: list[int]):
        L = len(self.Verts)
        return [a + L - self.LastLoad for a in Tri]

    def StripArgs(self, cmd: str):
        a = cmd.find("(")
        return cmd[:a].strip(), cmd[a + 1 : -2].split(",")

    def ApplyDat(self, obj: bpy.types.Object, mesh: bpy.types.Mesh, layer: int, tex_path: Path):
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
                new = self.Create_new_f3d_mat(self.Mats[ind + 1][1], mesh)
                ind += 1
                if not new:
                    new = len(mesh.materials) - 1
                    mat = mesh.materials[new]
                    mat.name = "sm64 F3D Mat {} {}".format(obj.name, new)
                    self.Mats[new][1].ApplyMatSettings(mat, self.Textures, tex_path, layer)
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
    def Create_new_f3d_mat(self, mat: SM64_Material, mesh: bpy.types.Mesh):
        if not self.scene.LevelImp.ForceNewTex:
            # check if this mat was used already in another mesh (or this mat if DL is garbage or something)
            # even looping n^2 is probably faster than duping 3 mats with blender speed
            for j, F3Dmat in enumerate(bpy.data.materials):
                if F3Dmat.is_f3d:
                    dupe = mat.MatHashF3d(F3Dmat.f3d_mat)
                    if dupe:
                        return F3Dmat
        if mesh.materials:
            mat = mesh.materials[-1]
            new = mat.id_data.copy()  # make a copy of the data block
            # add a mat slot and add mat to it
            mesh.materials.append(new)
        else:
            if self.scene.LevelImp.AsObj:
                NewMat = bpy.data.materials.new(f"sm64 {mesh.name.replace('Data', 'material')}")
                mesh.materials.append(NewMat)  # the newest mat should be in slot[-1] for the mesh materials
                NewMat.use_nodes = True
            else:
                bpy.ops.object.create_f3d_mat()  # the newest mat should be in slot[-1] for the mesh materials
        return None


# holds model found by geo
@dataclass
class ModelDat:
    translate: tuple
    rotate: tuple
    layer: int
    model: str
    scale: float = 1.0

# base class for geo layouts and armatures
class GraphNodes(DataParser):
    
    def GEO_BRANCH_AND_LINK(self, macro: Macro, depth: int):
        new_geo_layout = self.geo_layouts.get(macro.args[0])
        if new_geo_layout:
            self.parse_stream(new_geo_layout, depth)
        return self.continue_parse

    def GEO_BRANCH(self, macro: Macro, depth: int):
        new_geo_layout = self.geo_layouts.get(macro.args[1])
        if new_geo_layout:
            self.parse_stream(new_geo_layout, depth)
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
        # if there is no more open nodes, then parent this to last node
        if depth:
            return self.break_parse
        else:
            return self.continue_parse

    def GEO_OPEN_NODE(self, macro: Macro, depth: int):
        if self.obj:
            GeoChild = GeoLayout(self.geo_layouts, self.obj, self.scene, self.name, self.area_root, col=self.col, geo_parent=self)
        else:
            GeoChild = GeoLayout(self.geo_layouts, self.root, self.scene, self.name, self.area_root, col=self.col, geo_parent=self)
        GeoChild.parent_transform = self.last_transform
        GeoChild.stream = self.stream
        GeoChild.parse_stream(self.geo_layouts.get(self.stream), self.stream, depth + 1)
        # self.head = self.skip_children(self.cur_dat_stream, self.head)
        self.children.append(GeoChild)
        return self.continue_parse

    # Append to models array. Only check this one for now
    def GEO_DISPLAY_LIST(self, macro: Macro, depth: int):
        # translation, rotation, layer, model
        self.models.append(ModelDat(*self.parent_transform, *macro.args))

    # shadows aren't naturally supported but we can emulate them with custom geo cmds, note: possibly changed with fast64 updates, this is old code
    def GEO_SHADOW(self, macro: Macro, depth: int):
        obj = self.MakeRt(self.name + "shadow empty", self.root)
        obj.sm64_obj_type = "Custom Geo Command"
        obj.customGeoCommand = "GEO_SHADOW"
        obj.customGeoCommandArgs = ", ".join(macro.args)

    def GEO_ANIMATED_PART(self, macro: Macro, depth: int):
        # layer, translation, DL
        layer = macro.args[0]
        Tlate = [float(arg) / bpy.context.scene.blenderToSM64Scale for arg in macro.args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        model = args[-1]
        self.last_transform = [Tlate, self.last_transform[1]]
        if model.strip() != "NULL":
            self.models.append(ModelDat(Tlate, (0, 0, 0), layer, model))
        else:
            obj = self.MakeRt(self.name + "animated empty", self.root)
            obj.location = Tlate

    def GEO_ROTATION_NODE(self, macro: Macro, depth: int):
        obj = self.GEO_ROTATE(macro)
        if obj:
            obj.sm64_obj_type = "Geo Rotation Node"

    def GEO_ROTATE(self, macro: Macro, depth: int):
        layer = macro.args[0]
        Rotate = [math.radians(float(arg)) for arg in macro.args[1:4]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.last_transform = [[0, 0, 0], Rotate]
        self.last_transform = [[0, 0, 0], self.last_transform[1]]
        obj = self.MakeRt(self.name + "rotate", self.root)
        obj.rotation_euler = Rotate
        obj.sm64_obj_type = "Geo Translate/Rotate"
        return obj

    def GEO_ROTATION_NODE_WITH_DL(self, macro: Macro, depth: int):
        obj = self.GEO_ROTATE_WITH_DL(macro)
        if obj:
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_ROTATE_WITH_DL(self, macro: Macro, depth: int):
        layer = macro.args[0]
        Rotate = [math.radians(float(arg)) for arg in macro.args[1:4]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.last_transform = [[0, 0, 0], Rotate]
        model = args[-1]
        self.last_transform = [[0, 0, 0], self.last_transform[1]]
        if model.strip() != "NULL":
            self.models.append(ModelDat([0, 0, 0], Rotate, layer, model))
        else:
            obj = self.MakeRt(self.name + "rotate", self.root)
            obj.rotation_euler = Rotate
            obj.sm64_obj_type = "Geo Translate/Rotate"
            return obj

    def GEO_TRANSLATE_ROTATE_WITH_DL(self, macro: Macro, depth: int):
        layer = macro.args[0]
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in macro.args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        Rotate = [math.radians(float(arg)) for arg in macro.args[4:7]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.last_transform = [Tlate, Rotate]
        model = args[-1]
        self.last_transform = [Tlate, self.last_transform[1]]
        if model.strip() != "NULL":
            self.models.append(ModelDat(Tlate, Rotate, layer, model))
        else:
            obj = self.MakeRt(self.name + "translate rotate", self.root)
            obj.location = Tlate
            obj.rotation_euler = Rotate
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_ROTATE(self, macro: Macro, depth: int):
        Tlate = [float(arg) / bpy.context.scene.blenderToSM64Scale for arg in macro.args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        Rotate = [math.radians(float(arg)) for arg in macro.args[4:7]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.last_transform = [Tlate, Rotate]
        obj = self.MakeRt(self.name + "translate", self.root)
        obj.location = Tlate
        obj.rotation_euler = Rotate
        obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_WITH_DL(self, macro: Macro, depth: int):
        obj = self.GEO_TRANSLATE_NODE_WITH_DL(macro)
        if obj:
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_NODE_WITH_DL(self, macro: Macro, depth: int):
        # translation, layer, model
        layer = macro.args[0]
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in macro.args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        model = macro.args[-1]
        self.last_transform = [Tlate, (0, 0, 0)]
        if model.strip() != "NULL":
            self.models.append(ModelDat(Tlate, (0, 0, 0), layer, model))
        else:
            obj = self.MakeRt(self.name + "translate", self.root)
            obj.location = Tlate
            obj.rotation_euler = Rotate
            obj.sm64_obj_type = "Geo Translate Node"
            return obj

    def GEO_TRANSLATE(self, macro: Macro, depth: int):
        obj = self.GEO_TRANSLATE_NODE(macro)
        if obj:
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_NODE(self, macro: Macro, depth: int):
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in macro.args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        self.last_transform = [Tlate, self.last_transform[1]]
        obj = self.MakeRt(self.name + "translate", self.root)
        obj.location = Tlate
        obj.sm64_obj_type = "Geo Translate Node"
        return obj

    def GEO_SCALE_WITH_DL(self, macro: Macro, depth: int):
        scale = eval(macro.args[1]) / 0x10000
        model = macro.args[-1]
        self.last_transform = [(0, 0, 0), self.last_transform[1]]
        self.models.append(ModelDat((0, 0, 0), (0, 0, 0), layer, model, scale=scale))

    def GEO_SCALE(self, macro: Macro, depth: int):
        obj = self.MakeRt(self.name + "scale", self.root)
        scale = eval(macro.args[1]) / 0x10000
        obj.scale = (scale, scale, scale)
        obj.sm64_obj_type = "Geo Scale"

    def GEO_ASM(self, macro: Macro, depth: int):
        obj = self.MakeRt(self.name + "asm", self.root)
        asm = self.obj.fast64.sm64.geo_asm
        self.obj.sm64_obj_type = "Geo ASM"
        asm.param = macro.args[0]
        asm.func = macro.args[1]

    def GEO_SWITCH_CASE(self, macro: Macro, depth: int):
        obj = self.MakeRt(self.name + "switch", self.root)
        Switch = self.obj
        Switch.sm64_obj_type = "Switch"
        Switch.switchParam = eval(macro.args[0])
        Switch.switchFunc = macro.args[1]

    # This has to be applied to meshes
    def GEO_RENDER_RANGE(self, macro: Macro, depth: int):
        self.render_range = macro.args

    # can only apply type to area root
    def GEO_CAMERA(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[0]
    
    # make better
    def GEO_CAMERA_FRUSTUM_WITH_FUNC(self, macro: Macro, depth: int):
        self.area_root.camOption = "Custom"
        self.area_root.camType = macro.args[0]

    # Geo backgrounds is pointless because the only background possible is the one
    # loaded in the level script. This is the only override
    def GEO_BACKGROUND_COLOR(self, macro: Macro, depth: int):
        self.area_root.areaOverrideBG = True
        color = eval(macro.args[0])
        A = color & 1
        B = (color & 0x3E) > 1
        G = (color & (0x3E << 5)) >> 6
        R = (color & (0x3E << 10)) >> 11
        self.area_root.areaBGColor = (R / 0x1F, G / 0x1F, B / 0x1F, A)
    
    # these have no affect on the bpy
    def GEO_BACKGROUND(self, macro: Macro, depth: int):
        return self.continue_parse
    def GEO_NODE_SCREEN_AREA(self, macro: Macro, depth: int):
        return self.continue_parse
    def GEO_ZBUFFER(self, macro: Macro, depth: int):
        return self.continue_parse
    def GEO_NODE_ORTHO(self, macro: Macro, depth: int):
        return self.continue_parse
    def GEO_RENDER_OBJ(self, macro: Macro, depth: int):
        return self.continue_parse



class GeoLayout(GraphNodes):
    def __init__(
        self,
        geo_layouts: dict,
        root: bpy.types.Object,
        scene: bpy.types.Scene,
        name,
        area_root: bpy.types.Object,
        col: bpy.types.Collection = None,
        geo_parent: GeoLayout = None
    ):
        self.geo_layouts = geo_layouts
        self.parent = root
        self.models = []
        self.children = []
        self.scene = scene
        self.render_range = None
        self.area_root = area_root  # for properties that can only be written to area
        self.root = root
        self.parent_transform = [[0, 0, 0], [0, 0, 0]]
        self.last_transform = [[0, 0, 0], [0, 0, 0]]
        self.name = name
        self.obj = None  # last object on this layer of the tree, will become parent of next child
        if not col:
            self.col = area_root.users_collection[0]
        else:
            self.col = col
        super().__init__(parent=geo_parent)

    def MakeRt(self, name: str, root: bpy.types.Object):
        # make an empty node to act as the root of this geo layout
        # use this to hold a transform, or an actual cmd, otherwise rt is passed
        E = bpy.data.objects.new(name, None)
        self.obj = E
        self.col.objects.link(E)
        parentObject(root, E)
        return E

    def parse_level_geo(self, start: str, scene: bpy.types.Scene):
        geo_layout = self.geo_layouts.get(start)
        if not geo_layout:
            raise Exception(
                "Could not find geo layout {} from levels/{}/{}geo.c".format(
                    start, scene.LevelImp.Level, scene.LevelImp.Prefix
                )
            )
        # This won't parse the geo layout perfectly. For now I'll just get models. This is mostly because fast64
        # isn't a bijection to geo layouts, the props are sort of handled all over the place
        self.stream = start
        self.parse_stream(geo_layout, start, 0)

    def skip_children(self, geo_layout: list[str], head: int):
        open = 0
        opened = 0
        while head < len(geo_layout):
            l = geo_layout[head]
            if l.startswith("GEO_OPEN_NODE"):
                opened = 1
                open += 1
            if l.startswith("GEO_CLOSE_NODE"):
                open -= 1
            if open == 0 and opened:
                break
            head += 1
        return head

    


# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------

# parse aggregate files, and search for sm64 specific fast64 export name schemes
def get_all_aggregates(aggregate: Path, filenames: Union[str, tuple[str]], root_path: Path) -> list[Path]:
    with open(aggregate, "r", newline='') as aggregate:
        caught_files = parse_aggregate_file(aggregate, filenames, root_path)
        # catch fast64 includes
        fast64 = parse_aggregate_file(aggregate, "leveldata.inc.c", root_path)
        if fast64:
            with open(fast64[0], "r", newline='') as fast64_dat:
                caught_files.extend(parse_aggregate_file(fast64_dat, filenames, root_path))
    return caught_files


# given a path, get a level object by parsing the script.c file
def parse_level_script(script_file: Path, scene: bpy.types.Scene, col: bpy.types.Collection = None):
    Root = bpy.data.objects.new("Empty", None)
    if not col:
        scene.collection.objects.link(Root)
    else:
        col.objects.link(Root)
    Root.name = f"Level Root {scene.LevelImp.Level}"
    Root.sm64_obj_type = "Level Root"
    # Now parse the script and get data about the level
    # Store data in attribute of a level class then assign later and return class
    with open(script_file, "r", newline='') as script_file:
        lvl = Level(script_file, scene, Root)
    entry = scene.LevelImp.Entry.format(scene.LevelImp.Level)
    lvl.parse_level_script(entry, col=col)
    return lvl


# write the objects from a level object
def write_level_objects(lvl: Level, col_name: str = None):
    for area in lvl.areas.values():
        area.place_objects(col_name=col_name)


# from a geo layout, create all the mesh's
def write_geo_to_bpy(
    geo: GeoLayout, scene: bpy.types.Scene, f3d_dat: SM64_F3D, root_path: Path, meshes: dict, cleanup: bool = True
):
    if geo.models:
        rt = geo.root
        col = geo.col
        # create a mesh for each one.
        for m in geo.models:
            name = m.model + " Data"
            if name in meshes.keys():
                mesh = meshes[name]
                name = 0
            else:
                mesh = bpy.data.meshes.new(name)
                meshes[name] = mesh
                [verts, tris] = f3d_dat.GetDataFromModel(m.model.strip())
                mesh.from_pydata(verts, [], tris)

            obj = bpy.data.objects.new(m.model + " Obj", mesh)
            layer = m.layer
            if not layer.isdigit():
                layer = Layers.get(layer)
                if not layer:
                    layer = 1
            obj.draw_layer_static = layer
            col.objects.link(obj)
            parentObject(rt, obj)
            rotate_object(-90, obj)
            scale = m.scale / scene.blenderToSM64Scale
            obj.scale = [scale, scale, scale]
            obj.location = m.translate
            obj.ignore_collision = True
            if name:
                f3d_dat.ApplyDat(obj, mesh, layer, root_path)
                if cleanup:
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
    if not geo.children:
        return
    for g in geo.children:
        write_geo_to_bpy(g, scene, f3d_dat, root_path, meshes, cleanup=cleanup)


# write the gfx for a level given the level data, and f3d data
def write_level_to_bpy(lvl: Level, scene: bpy.types.Scene, root_path: Path, f3d_dat: SM64_F3D, cleanup: bool = True):
    for area in lvl.areas.values():
        print(area, area.geo)
        write_geo_to_bpy(area.geo, scene, f3d_dat, root_path, dict(), cleanup=cleanup)
    return lvl


# given a geo.c file and a path, return cleaned up geo layouts in a dict
def construct_geo_layouts_from_file(geo: TextIO, root_path: Path):
    geo_layout_files = get_all_aggregates(geo, "geo.inc.c", root_path)
    if not geo_layout_files:
        return
    # because of fast64, these can be recursively defined (though I expect only a depth of one)
    for file in geo_layout_files:
        geo_layout_files.extend(get_all_aggregates(file, "geo.inc.c", root_path))
    geo_layout_data = {}  # stores cleaned up geo layout lines
    for geo_file in geo_layout_files:
        with open(geo_file, "r", newline='') as geo_file:
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
        collated=True
    )
    for key, value in gfx_dat.items():
        attr = getattr(gfx, key)
        attr.update(value)
    # For textures, try u8, and s16 aswell
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
        model_file = open(model_file, "r", newline='')
        construct_sm64_f3d_data_from_file(sm64_f3d_data, model_file)
    # Update file to have texture.inc.c textures, deal with included textures in the model.inc.c files aswell
    for texture_file in [*texture_files, *model_files]:
        with open(texture_file, "r", newline='') as texture_file:
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
    geo: TextIO,
    Layout: str,
    scene: bpy.types.Scene,
    rt: bpy.types.Object,
    root_path: Path,
    col: bpy.types.Collection = None,
):
    GeoLayouts = construct_geo_layouts_from_file(geo, root_path)
    Geo = GeoLayout(GeoLayouts, rt, scene, "{}".format(Layout), rt, col=col)
    Geo.parse_level_geo(Layout, scene)
    return Geo


# Find DL references given a level geo file and a path to a level folder
def find_level_models_from_geo(
    geo: TextIO, lvl: Level, scene: bpy.types.Scene, root_path: Path, col_name: str = None
):
    GeoLayouts = construct_geo_layouts_from_file(geo, root_path)
    for area_index, area in lvl.areas.items():
        if col_name:
            col = create_collection(area.root.users_collection[0], col_name)
        else:
            col = None
        Geo = GeoLayout(
            GeoLayouts, area.root, scene, f"GeoRoot {scene.LevelImp.Level} {area_index}", area.root, col=col
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
    print(lvl.areas, aggregate)
    # just a try, in case you are importing from something other than base decomp repo (like RM2C output folder)
    try:
        models.GetGenericTextures(root_path)
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
        with open(col_file, "r", newline='') as col_file:
            col_data.update(get_data_types_from_file(col_file, {"Collision": ["(", ")"]}))
    # search for the area terrain from available collision data
    for area in lvl.areas.values():
        area.ColFile = col_data.get(area.terrain, None)
        if not area.ColFile:
            raise Exception(
                f"Collision {area.terrain} not found in levels/{scene.LevelImp.Level}/{scene.LevelImp.Prefix}leveldata.c"
            )
    return lvl


def write_level_collision_to_bpy(lvl: Level, scene: bpy.types.Scene, cleanup: bool, col_name: str = None):
    for area_index, area in lvl.areas.items():
        if not col_name:
            col = area.root.users_collection[0]
        else:
            col = create_collection(area.root.users_collection[0], col_name)
        col_parser = Collision(area.ColFile, scene.blenderToSM64Scale)
        col_parser.GetCollision()
        name = "SM64 {} Area {} Col".format(scene.LevelImp.Level, area_index)
        obj = col_parser.WriteCollision(scene, name, area.root, col=col)
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
        path = Path(bpy.path.abspath(scene.decompPath))
        folder = path / scene.ActImp.FolderType
        Layout = scene.ActImp.GeoLayout
        prefix = scene.ActImp.Prefix
        # different name schemes and I have no clean way to deal with it
        if "actor" in scene.ActImp.FolderType:
            geo = folder / (prefix + "_geo.c")
            leveldat = folder / (prefix + ".c")
        else:
            geo = folder / (prefix + "geo.c")
            leveldat = folder / (prefix + "leveldata.c")
        geo = open(geo, "r", newline='')
        Root = bpy.data.objects.new("Empty", None)
        Root.name = "Actor %s" % scene.ActImp.GeoLayout
        rt_col.objects.link(Root)

        Geo = find_actor_models_from_geo(
            geo, Layout, scene, Root, folder, col=rt_col
        )  # return geo layout class and write the geo layout
        models = construct_model_data_from_file(leveldat, scene, folder)
        # just a try, in case you are importing from not the base decomp repo
        try:
            models.GetGenericTextures(path)
        except:
            print("could not import genric textures, if this errors later from missing textures this may be why")
        meshes = {}  # re use mesh data when the same DL is referenced (bbh is good example)
        write_geo_to_bpy(Geo, scene, models, folder, meshes, cleanup=self.cleanup)
        return {"FINISHED"}


class SM64_OT_Lvl_Import(Operator):
    bl_label = "Import Level"
    bl_idname = "wm.sm64_import_level"

    cleanup = True

    def execute(self, context):
        scene = context.scene

        col = context.collection
        if scene.LevelImp.UseCol:
            obj_col = f"{scene.LevelImp.Level} obj"
            gfx_col = f"{scene.LevelImp.Level} gfx"
            col_col = f"{scene.LevelImp.Level} col"
        else:
            obj_col = gfx_col = col_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.LevelImp.Prefix
        path = Path(bpy.path.abspath(scene.decompPath))
        level = path / "levels" / scene.LevelImp.Level
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
        if scene.LevelImp.UseCol:
            gfx_col = f"{scene.LevelImp.Level} gfx"
        else:
            gfx_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.LevelImp.Prefix
        path = Path(bpy.path.abspath(scene.decompPath))
        level = path / "levels" / scene.LevelImp.Level
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
        if scene.LevelImp.UseCol:
            col_col = f"{scene.LevelImp.Level} collision"
        else:
            col_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.LevelImp.Prefix
        path = Path(bpy.path.abspath(scene.decompPath))
        level = path / "levels" / scene.LevelImp.Level
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
        if scene.LevelImp.UseCol:
            obj_col = f"{scene.LevelImp.Level} objs"
        else:
            obj_col = None

        scene.gameEditorMode = "SM64"
        prefix = scene.LevelImp.Prefix
        path = Path(bpy.path.abspath(scene.decompPath))
        level = path / "levels" / scene.LevelImp.Level
        script = level / (prefix + "script.c")
        lvl = parse_level_script(script, scene, col=col)  # returns level class
        write_level_objects(lvl, col_name=obj_col)
        return {"FINISHED"}


# ------------------------------------------------------------------------
#    Props
# ------------------------------------------------------------------------


class ActorImport(PropertyGroup):
    GeoLayout: StringProperty(name="GeoLayout", description="Name of GeoLayout")
    FolderType: EnumProperty(
        name="Source",
        description="Whether the actor is from a level or from a group",
        items=[
            ("actors", "actors", ""),
            ("levels", "levels", ""),
        ],
    )
    Prefix: StringProperty(
        name="Prefix",
        description="Prefix before expected aggregator files like script.c, leveldata.c and geo.c",
        default="",
    )
    Version: EnumProperty(
        name="Version",
        description="Version of the game for any ifdef macros",
        items=enumVersionDefs,
    )
    Target: StringProperty(
        name="Target", description="The platform target for any #ifdefs in code", default="TARGET_N64"
    )


class LevelImport(PropertyGroup):
    Level: EnumProperty(
        name="Level",
        description="Choose a level",
        items=enumLevelNames,
    )
    Prefix: StringProperty(
        name="Prefix",
        description="Prefix before expected aggregator files like script.c, leveldata.c and geo.c",
        default="",
    )
    Entry: StringProperty(
        name="Entrypoint", description="The name of the level script entry variable", default="level_{}_entry"
    )
    Version: EnumProperty(
        name="Version",
        description="Version of the game for any ifdef macros",
        items=enumVersionDefs,
    )
    Target: StringProperty(
        name="Target", description="The platform target for any #ifdefs in code", default="TARGET_N64"
    )
    ForceNewTex: BoolProperty(
        name="ForceNewTex",
        description="Forcefully load new textures even if duplicate path/name is detected",
        default=False,
    )
    AsObj: BoolProperty(
        name="As OBJ", description="Make new materials as PBSDF so they export to obj format", default=False
    )
    UseCol: BoolProperty(
        name="Use Col", description="Make new collections to organzie content during imports", default=True
    )


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
        LevelImp = scene.LevelImp
        layout.prop(LevelImp, "Level")
        layout.prop(LevelImp, "Entry")
        layout.prop(LevelImp, "Prefix")
        layout.prop(LevelImp, "Version")
        layout.prop(LevelImp, "Target")
        row = layout.row()
        row.prop(LevelImp, "ForceNewTex")
        row.prop(LevelImp, "AsObj")
        row.prop(LevelImp, "UseCol")
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
        ActImp = scene.ActImp
        layout.prop(ActImp, "FolderType")
        layout.prop(ActImp, "GeoLayout")
        layout.prop(ActImp, "Prefix")
        layout.prop(ActImp, "Version")
        layout.prop(ActImp, "Target")
        layout.operator("wm.sm64_import_actor")


classes = (
    LevelImport,
    ActorImport,
    SM64_OT_Lvl_Import,
    SM64_OT_Lvl_Gfx_Import,
    SM64_OT_Lvl_Col_Import,
    SM64_OT_Obj_Import,
    SM64_OT_Act_Import,
    Level_PT_Panel,
    Actor_PT_Panel,
)


def sm64_import_register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.LevelImp = PointerProperty(type=LevelImport)
    bpy.types.Scene.ActImp = PointerProperty(type=ActorImport)


def sm64_import_unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.LevelImp
    del bpy.types.Scene.ActImp
