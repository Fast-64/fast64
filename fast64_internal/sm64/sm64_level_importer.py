# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
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

# from SM64classes import *

from ..f3d.f3d_import import *
from ..utility import (
    rotate_quat_n64_to_blender,
    parentObject,
    get_enums_from_prop,
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

    def AddWarp(self, args: list[str]):
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

    def AddObject(self, args: list[str]):
        self.objects.append(args)

    def PlaceObjects(self, col_name: str = None):
        if not col_name:
            col = self.col
        else:
            col = CreateCol(self.root.users_collection[0], col_name)
        for a in self.objects:
            self.PlaceObject(a, col)

    def PlaceObject(self, args: list[str], col: bpy.types.Collection):
        Obj = bpy.data.objects.new("Empty", None)
        col.objects.link(Obj)
        parentObject(self.root, Obj)
        Obj.name = "Object {} {}".format(args[8].strip(), args[0].strip())
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
                if mask & (1 << i):
                    setattr(Obj, form.format(i), True)
                else:
                    setattr(Obj, form.format(i), False)


class Level:
    def __init__(self, scr: list[str], scene: bpy.types.Scene, root: bpy.types.Object):
        self.Scripts = FormatDat(scr, "LevelScript", ["(", ")"])
        self.scene = scene
        self.Areas = {}
        self.CurrArea = None
        self.root = root

    def ParseScript(self, entry: str, col: bpy.types.Collection = None):
        Start = self.Scripts[entry]
        scale = self.scene.blenderToSM64Scale
        if not col:
            col = self.scene.collection
        for l in Start:
            args = self.StripArgs(l)
            LsW = l.startswith
            # Find an area
            if LsW("AREA"):
                Root = bpy.data.objects.new("Empty", None)
                if self.scene.LevelImp.UseCol:
                    a_col = bpy.data.collections.new(f"{self.scene.LevelImp.Level} area {args[0]}")
                    col.children.link(a_col)
                else:
                    a_col = col
                a_col.objects.link(Root)
                Root.name = "{} Area Root {}".format(self.scene.LevelImp.Level, args[0])
                self.Areas[args[0]] = Area(Root, args[1], self.root, int(args[0]), self.scene, a_col)
                self.CurrArea = args[0]
                continue
            # End an area
            if LsW("END_AREA"):
                self.CurrArea = None
                continue
            # Jumps are only taken if they're in the script.c file for now
            # continues script
            elif LsW("JUMP_LINK"):
                if self.Scripts.get(args[0]):
                    self.ParseScript(args[0], col=col)
                continue
            # ends script, I get arg -1 because sm74 has a different jump cmd
            elif LsW("JUMP"):
                Nentry = self.Scripts.get(args[-1])
                if Nentry:
                    self.ParseScript(args[-1], col=col)
                # for the sm74 port
                if len(args) != 2:
                    break
            # final exit of recursion
            elif LsW("EXIT") or l.startswith("RETURN"):
                return
            # Now deal with data cmds rather than flow control ones
            if LsW("WARP_NODE"):
                self.Areas[self.CurrArea].AddWarp(args)
                continue
            if LsW("OBJECT_WITH_ACTS"):
                # convert act mask from ORs of act names to a number
                mask = args[-1].strip()
                if not mask.isdigit():
                    mask = mask.replace("ACT_", "")
                    mask = mask.split("|")
                    # Attempt for safety I guess
                    try:
                        a = 0
                        for m in mask:
                            a += 1 << int(m)
                        mask = a
                    except:
                        mask = 31
                self.Areas[self.CurrArea].AddObject([*args[:-1], mask])
                continue
            if LsW("OBJECT"):
                # Only difference is act mask, which I set to 31 to mean all acts
                self.Areas[self.CurrArea].AddObject([*args, 31])
                continue
            # Don't support these for now
            if LsW("MACRO_OBJECTS"):
                continue
            if LsW("TERRAIN_TYPE"):
                if not args[0].isdigit():
                    self.Areas[self.CurrArea].root.terrainEnum = args[0].strip()
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
                        num = eval(args[0])
                        self.Areas[self.CurrArea].root.terrainEnum = terrains.get(num)
                    except:
                        print("could not set terrain")
                continue
            if LsW("SHOW_DIALOG"):
                rt = self.Areas[self.CurrArea].root
                rt.showStartDialog = True
                rt.startDialog = args[1].strip()
                continue
            if LsW("TERRAIN"):
                self.Areas[self.CurrArea].terrain = args[0].strip()
                continue
            if LsW("SET_BACKGROUND_MUSIC") or LsW("SET_MENU_MUSIC"):
                rt = self.Areas[self.CurrArea].root
                rt.musicSeqEnum = "Custom"
                rt.music_seq = args[-1].strip()
        return self.Areas

    def StripArgs(self, cmd: str):
        a = cmd.find("(")
        end = cmd.rfind(")") - len(cmd)
        return cmd[a + 1 : end].split(",")


class Collision:
    def __init__(self, col: list[str], scale: float):
        self.col = col
        self.scale = scale
        self.vertices = []
        # key=type,value=tri data
        self.tris = {}
        self.type = None
        self.SpecialObjs = []
        self.Types = []
        self.WaterBox = []

    def GetCollision(self):
        for l in self.col:
            args = self.StripArgs(l)
            # to avoid catching COL_VERTEX_INIT
            if l.startswith("COL_VERTEX") and len(args) == 3:
                self.vertices.append([eval(v) / self.scale for v in args])
                continue
            if l.startswith("COL_TRI_INIT"):
                self.type = args[0]
                if not self.tris.get(self.type):
                    self.tris[self.type] = []
                continue
            if l.startswith("COL_TRI") and len(args) > 2:
                a = [eval(a) for a in args]
                self.tris[self.type].append(a)
                continue
            if l.startswith("COL_WATER_BOX_INIT"):
                continue
            if l.startswith("COL_WATER_BOX"):
                # id, x1, z1, x2, z2, y
                self.WaterBox.append(args)
            if l.startswith("SPECIAL_OBJECT"):
                self.SpecialObjs.append(args)
        # This will keep track of how to assign mats
        a = 0
        for k, v in self.tris.items():
            self.Types.append([a, k, v[0]])
            a += len(v)
        self.Types.append([a, 0])

    def StripArgs(self, cmd: str):
        a = cmd.find("(")
        return cmd[a + 1 : -2].split(",")

    def WriteWaterBoxes(
        self, scene: bpy.types.Scene, parent: bpy.types.Object, name: str, col: bpy.types.Collection = None
    ):
        for i, w in enumerate(self.WaterBox):
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
        RotateObj(-90, obj, world=1)
        polys = obj.data.polygons
        x = 0
        bpy.context.view_layer.objects.active = obj
        max = len(polys)
        for i, p in enumerate(polys):
            a = self.Types[x][0]
            if i >= a:
                bpy.ops.object.create_f3d_mat()  # the newest mat should be in slot[-1]
                mat = obj.data.materials[x]
                mat.collision_type_simple = "Custom"
                mat.collision_custom = self.Types[x][1]
                mat.name = "Sm64_Col_Mat_{}".format(self.Types[x][1])
                color = ((max - a) / (max), (max + a) / (2 * max - a), a / max, 1)  # Just to give some variety
                mat.f3d_mat.default_light_color = color
                # check for param
                if len(self.Types[x][2]) > 3:
                    mat.use_collision_param = True
                    mat.collision_param = str(self.Types[x][2][3])
                x += 1
                override = bpy.context.copy()
                override["material"] = mat
                bpy.ops.material.update_f3d_nodes(override)
            p.material_index = x - 1
        return obj


class sm64_Mat(Mat):
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
            Extra = path.relative_to(Path(bpy.context.scene.decompPath))
            for e in Extra.parts:
                Timg = Timg.replace(e + "/", "")
            # deal with actor import path not working for shared textures
            if "textures" in Timg:
                fp = Path(bpy.context.scene.decompPath) / Timg
            else:
                fp = path / Timg
            return bpy.data.images.load(filepath=str(fp))
        else:
            return i

    def ApplyPBSDFMat(self, mat: bpy.types.Material, textures: dict, path: Path, layer: int, tex0: Texture):
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        pbsdf = nodes.get("Principled BSDF")
        if not pbsdf:
            return
        tex = nodes.new("ShaderNodeTexImage")
        links.new(pbsdf.inputs[0], tex.outputs[0])  # base color
        i = self.LoadTexture(bpy.context.scene.LevelImp.ForceNewTex, textures, path, tex0)
        if i:
            tex.image = i
        if int(layer) > 4:
            mat.blend_method == "BLEND"

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
                print(self.tex_scale)
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


class sm64_F3d(DL):
    def __init__(self, scene: bpy.types.Scene):
        self.VB = {}
        self.Gfx = {}
        self.diff = {}
        self.amb = {}
        self.Lights = {}
        self.Textures = {}
        self.scene = scene
        self.num = 0

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
            t = open(t, "r")
            tex = t.readlines()
            # For textures, try u8, and s16 aswell
            self.Textures.update(FormatDat(tex, "Texture", [None, None]))
            self.Textures.update(FormatDat(tex, "u8", [None, None]))
            self.Textures.update(FormatDat(tex, "s16", [None, None]))
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
        self.LastMat = sm64_Mat()
        self.ParseDL(DL)
        self.NewMat = 0
        self.StartName = start
        return [self.Verts, self.Tris]

    def ParseDL(self, DL: list[str]):
        # This will be the equivalent of a giant switch case
        x = -1
        while x < len(DL):
            # manaual iteration so I can skip certain children efficiently
            # manaual iteration so I can skip certain children efficiently if needed
            x += 1
            (cmd, args) = self.StripArgs(DL[x])  # each member is a tuple of (cmd, arguments)
            LsW = cmd.startswith
            # Deal with control flow first
            if LsW("gsSPEndDisplayList"):
                return
            if LsW("gsSPBranchList"):
                NewDL = self.Gfx.get(args[0].strip())
                if not DL:
                    raise Exception(
                        "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
                            NewDL, self.scene.LevelImp.Level, self.scene.LevelImp.Prefix
                        )
                    )
                self.ParseDL(NewDL)
                break
            if LsW("gsSPDisplayList"):
                NewDL = self.Gfx.get(args[0].strip())
                if not DL:
                    raise Exception(
                        "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
                            NewDL, self.scene.LevelImp.Level, self.scene.LevelImp.Prefix
                        )
                    )
                self.ParseDL(NewDL)
                continue
            # Vertices
            if LsW("gsSPVertex"):
                # vertex references commonly use pointer arithmatic. I will deal with that case here, but not for other things unless it somehow becomes a problem later
                if "+" in args[0]:
                    ref, add = args[0].split("+")
                else:
                    ref = args[0]
                    add = "0"
                VB = self.VB.get(ref.strip())
                if not VB:
                    raise Exception(
                        "Could not find VB {} in levels/{}/{}leveldata.inc.c".format(
                            ref, self.scene.LevelImp.Level, self.scene.LevelImp.Prefix
                        )
                    )
                Verts = VB[
                    int(add.strip()) : int(add.strip()) + eval(args[1])
                ]  # If you use array indexing here then you deserve to have this not work
                Verts = [self.ParseVert(v) for v in Verts]
                for k, i in enumerate(range(eval(args[2]), eval(args[1]), 1)):
                    self.VertBuff[i] = [Verts[k], eval(args[2])]
                # These are all independent data blocks in blender
                self.Verts.extend([v[0] for v in Verts])
                self.UVs.extend([v[1] for v in Verts])
                self.VCs.extend([v[2] for v in Verts])
                self.LastLoad = eval(args[1])
                continue
            # tri and mat DL cmds will be called via parent class
            func = getattr(self, cmd, None)
            if func:
                func(args)

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
        vcol_enums = get_enums_from_prop(bpy.types.FloatColorAttribute, "data_type")
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

    # create a new f3d_mat given an sm64_Mat class but don't create copies with same props
    def Create_new_f3d_mat(self, mat: sm64_Mat, mesh: bpy.types.Mesh):
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


class GeoLayout:
    def __init__(
        self,
        GeoLayouts: dict,
        root: bpy.types.Object,
        scene: bpy.types.Scene,
        name,
        Aroot: bpy.types.Object,
        col: bpy.types.Collection = None,
    ):
        self.GL = GeoLayouts
        self.parent = root
        self.models = []
        self.Children = []
        self.scene = scene
        self.RenderRange = None
        self.Aroot = Aroot  # for properties that can only be written to area
        self.root = root
        self.ParentTransform = [[0, 0, 0], [0, 0, 0]]
        self.LastTransform = [[0, 0, 0], [0, 0, 0]]
        self.name = name
        self.obj = None  # last object on this layer of the tree, will become parent of next child
        if not col:
            self.col = Aroot.users_collection[0]
        else:
            self.col = col

    def MakeRt(self, name: str, root: bpy.types.Object):
        # make an empty node to act as the root of this geo layout
        # use this to hold a transform, or an actual cmd, otherwise rt is passed
        E = bpy.data.objects.new(name, None)
        self.obj = E
        self.col.objects.link(E)
        parentObject(root, E)
        return E

    def ParseLevelGeosStart(self, start: str, scene: bpy.types.Scene):
        GL = self.GL.get(start)
        if not GL:
            raise Exception(
                "Could not find geo layout {} from levels/{}/{}geo.c".format(
                    start, scene.LevelImp.Level, scene.LevelImp.Prefix
                )
            )
        self.ParseLevelGeos(GL, 0)

    # So I can start where ever for child nodes
    def ParseLevelGeos(self, GL: list[str], depth: int):
        # I won't parse the geo layout perfectly. For now I'll just get models. This is mostly because fast64
        # isn't a bijection to geo layouts, the props are sort of handled all over the place
        x = -1
        while x < len(GL):
            # manaual iteration so I can skip certain children efficiently
            x += 1
            (cmd, args) = self.StripArgs(GL[x])  # each member is a tuple of (cmd, arguments)
            LsW = cmd.startswith
            # Jumps are only taken if they're in the script.c file for now
            # continues script
            if LsW("GEO_BRANCH_AND_LINK"):
                NewGL = self.GL.get(args[0].strip())
                if NewGL:
                    self.ParseLevelGeos(NewGL, depth)
                continue
            # continues
            elif LsW("GEO_BRANCH"):
                NewGL = self.GL.get(args[1].strip())
                if NewGL:
                    self.ParseLevelGeos(NewGL, depth)
                if eval(args[0]):
                    continue
                else:
                    break
            # final exit of recursion
            elif LsW("GEO_END") or LsW("GEO_RETURN"):
                return
            # on an open node, make a child
            elif LsW("GEO_CLOSE_NODE"):
                # if there is no more open nodes, then parent this to last node
                if depth:
                    return
            elif LsW("GEO_OPEN_NODE"):
                if self.obj:
                    GeoChild = GeoLayout(self.GL, self.obj, self.scene, self.name, self.Aroot, col=self.col)
                else:
                    GeoChild = GeoLayout(self.GL, self.root, self.scene, self.name, self.Aroot, col=self.col)
                GeoChild.ParentTransform = self.LastTransform
                GeoChild.ParseLevelGeos(GL[x + 1 :], depth + 1)
                x = self.SkipChildren(GL, x)
                self.Children.append(GeoChild)
                continue
            else:
                # things that only need args can be their own functions
                func = getattr(self, cmd.strip(), None)
                if func:
                    func(args)

    # Append to models array. Only check this one for now
    def GEO_DISPLAY_LIST(self, args: list[str]):
        # translation, rotation, layer, model
        self.models.append(ModelDat(*self.ParentTransform, *args))

    # shadows aren't naturally supported but we can emulate them with custom geo cmds
    def GEO_SHADOW(self, args: list[str]):
        obj = self.MakeRt(self.name + "shadow empty", self.root)
        obj.sm64_obj_type = "Custom Geo Command"
        obj.customGeoCommand = "GEO_SHADOW"
        obj.customGeoCommandArgs = ",".join(args)

    def GEO_ANIMATED_PART(self, args: list[str]):
        # layer, translation, DL
        layer = args[0]
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        model = args[-1]
        self.LastTransform = [Tlate, self.LastTransform[1]]
        if model.strip() != "NULL":
            self.models.append(ModelDat(Tlate, (0, 0, 0), layer, model))
        else:
            obj = self.MakeRt(self.name + "animated empty", self.root)
            obj.location = Tlate

    def GEO_ROTATION_NODE(self, args: list[str]):
        obj = self.GEO_ROTATE(args)
        if obj:
            obj.sm64_obj_type = "Geo Rotation Node"

    def GEO_ROTATE(self, args: list[str]):
        layer = args[0]
        Rotate = [math.radians(float(a)) for a in [args[1], args[2], args[3]]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.LastTransform = [[0, 0, 0], Rotate]
        self.LastTransform = [[0, 0, 0], self.LastTransform[1]]
        obj = self.MakeRt(self.name + "rotate", self.root)
        obj.rotation_euler = Rotate
        obj.sm64_obj_type = "Geo Translate/Rotate"
        return obj

    def GEO_ROTATION_NODE_WITH_DL(self, args: list[str]):
        obj = self.GEO_ROTATE_WITH_DL(args)
        if obj:
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_ROTATE_WITH_DL(self, args: list[str]):
        layer = args[0]
        Rotate = [math.radians(float(a)) for a in [args[1], args[2], args[3]]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.LastTransform = [[0, 0, 0], Rotate]
        model = args[-1]
        self.LastTransform = [[0, 0, 0], self.LastTransform[1]]
        if model.strip() != "NULL":
            self.models.append(ModelDat([0, 0, 0], Rotate, layer, model))
        else:
            obj = self.MakeRt(self.name + "rotate", self.root)
            obj.rotation_euler = Rotate
            obj.sm64_obj_type = "Geo Translate/Rotate"
            return obj

    def GEO_TRANSLATE_ROTATE_WITH_DL(self, args: list[str]):
        layer = args[0]
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        Rotate = [math.radians(float(a)) for a in [args[4], args[5], args[6]]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.LastTransform = [Tlate, Rotate]
        model = args[-1]
        self.LastTransform = [Tlate, self.LastTransform[1]]
        if model.strip() != "NULL":
            self.models.append(ModelDat(Tlate, Rotate, layer, model))
        else:
            obj = self.MakeRt(self.name + "translate rotate", self.root)
            obj.location = Tlate
            obj.rotation_euler = Rotate
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_ROTATE(self, args: list[str]):
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        Rotate = [math.radians(float(a)) for a in [args[4], args[5], args[6]]]
        Rotate = rotate_quat_n64_to_blender(Euler(Rotate, "ZXY").to_quaternion()).to_euler("XYZ")
        self.LastTransform = [Tlate, Rotate]
        obj = self.MakeRt(self.name + "translate", self.root)
        obj.location = Tlate
        obj.rotation_euler = Rotate
        obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_WITH_DL(self, args: list[str]):
        obj = self.GEO_TRANSLATE_NODE_WITH_DL(args)
        if obj:
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_NODE_WITH_DL(self, args: list[str]):
        # translation, layer, model
        layer = args[0]
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        model = args[-1]
        self.LastTransform = [Tlate, (0, 0, 0)]
        if model.strip() != "NULL":
            self.models.append(ModelDat(Tlate, (0, 0, 0), layer, model))
        else:
            obj = self.MakeRt(self.name + "translate", self.root)
            obj.location = Tlate
            obj.rotation_euler = Rotate
            obj.sm64_obj_type = "Geo Translate Node"
            return obj

    def GEO_TRANSLATE(self, args: list[str]):
        obj = self.GEO_TRANSLATE_NODE(args)
        if obj:
            obj.sm64_obj_type = "Geo Translate/Rotate"

    def GEO_TRANSLATE_NODE(self, args: list[str]):
        Tlate = [float(a) / bpy.context.scene.blenderToSM64Scale for a in args[1:4]]
        Tlate = [Tlate[0], -Tlate[2], Tlate[1]]
        self.LastTransform = [Tlate, self.LastTransform[1]]
        obj = self.MakeRt(self.name + "translate", self.root)
        obj.location = Tlate
        obj.sm64_obj_type = "Geo Translate Node"
        return obj

    def GEO_SCALE_WITH_DL(self, args: list[str]):
        scale = eval(args[1].strip()) / 0x10000
        model = args[-1]
        self.LastTransform = [(0, 0, 0), self.LastTransform[1]]
        self.models.append(ModelDat((0, 0, 0), (0, 0, 0), layer, model, scale=scale))

    def GEO_SCALE(self, args: list[str]):
        obj = self.MakeRt(self.name + "scale", self.root)
        scale = eval(args[1].strip()) / 0x10000
        obj.scale = (scale, scale, scale)
        obj.sm64_obj_type = "Geo Scale"

    def GEO_ASM(self, args: list[str]):
        obj = self.MakeRt(self.name + "asm", self.root)
        asm = self.obj.fast64.sm64.geo_asm
        self.obj.sm64_obj_type = "Geo ASM"
        asm.param = args[0].strip()
        asm.func = args[1].strip()

    def GEO_SWITCH_CASE(self, args: list[str]):
        obj = self.MakeRt(self.name + "switch", self.root)
        Switch = self.obj
        Switch.sm64_obj_type = "Switch"
        Switch.switchParam = eval(args[0])
        Switch.switchFunc = args[1].strip()

    # This has to be applied to meshes
    def GEO_RENDER_RANGE(self, args: list[str]):
        self.RenderRange = args

    # can only apply type to area root
    def GEO_CAMERA(self, args: list[str]):
        self.Aroot.camOption = "Custom"
        self.Aroot.camType = args[0]

    # Geo backgrounds is pointless because the only background possible is the one
    # loaded in the level script. This is the only override
    def GEO_BACKGROUND_COLOR(self, args: list[str]):
        self.Aroot.areaOverrideBG = True
        color = eval(args[0])
        A = color & 1
        B = (color & 0x3E) > 1
        G = (color & (0x3E << 5)) >> 6
        R = (color & (0x3E << 10)) >> 11
        self.Aroot.areaBGColor = (R / 0x1F, G / 0x1F, B / 0x1F, A)

    def SkipChildren(self, GL: list[str], x: int):
        open = 0
        opened = 0
        while x < len(GL):
            l = GL[x]
            if l.startswith("GEO_OPEN_NODE"):
                opened = 1
                open += 1
            if l.startswith("GEO_CLOSE_NODE"):
                open -= 1
            if open == 0 and opened:
                break
            x += 1
        return x

    def StripArgs(self, cmd: str):
        a = cmd.find("(")
        return cmd[:a].strip(), cmd[a + 1 : -2].split(",")


# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------


# creates a new collection and links it to parent
def CreateCol(parent: bpy.types.Collection, name: str):
    col = bpy.data.collections.new(name)
    parent.children.link(col)
    return col


def RotateObj(deg: float, obj: bpy.types.Object, world: bool = 0):
    deg = Euler((math.radians(-deg), 0, 0))
    deg = deg.to_quaternion().to_matrix().to_4x4()
    if world:
        obj.matrix_world = obj.matrix_world @ deg
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(rotation=True)
    else:
        obj.matrix_basis = obj.matrix_basis @ deg


def EvalMacro(line: str):
    scene = bpy.context.scene
    if scene.LevelImp.Version in line:
        return False
    if scene.LevelImp.Target in line:
        return False
    return True


# given an aggregate file that imports many files, find files with the name of type <filename>
def ParseAggregat(dat: typing.TextIO, filename: str, root_path: Path):
    dat.seek(0)  # so it may be read multiple times
    InlineReg = "/\*((?!\*/).)*\*/"  # filter out inline comments
    ldat = dat.readlines()
    files = []
    # assume this follows naming convention
    for l in ldat:
        if filename in l:
            comment = l.rfind("//")
            # double slash terminates line basically
            if comment:
                l = l[:comment]
            # remove inline comments from line
            l = re.sub(InlineReg, "", l)
            files.append(l.strip())
    # remove include and quotes inefficiently. Now files is a list of relative paths
    files = [c.replace("#include ", "").replace('"', "").replace("'", "") for c in files]
    # deal with duplicate pathing (such as /actors/actors etc.)
    Extra = root_path.relative_to(Path(bpy.context.scene.decompPath))
    for e in Extra.parts:
        files = [c.replace(e + "/", "") for c in files]
    if files:
        return [root_path / c for c in files]
    else:
        return []


# get all the collision data from a certain path
def FindCollisions(aggregate: Path, lvl: Level, scene: bpy.types.Scene, root_path: Path):
    aggregate = open(aggregate, "r")
    cols = ParseAggregat(aggregate, "collision.inc.c", root_path)
    # catch fast64 includes
    fast64 = ParseAggregat(aggregate, "leveldata.inc.c", root_path)
    if fast64:
        f64dat = open(fast64[0], "r")
        cols += ParseAggregat(f64dat, "collision.inc.c", root_path)
    aggregate.close()
    # search for the area terrain in each file
    for k, v in lvl.Areas.items():
        terrain = v.terrain
        found = 0
        for c in cols:
            if os.path.isfile(c):
                c = open(c, "r")
                c = c.readlines()
                for i, l in enumerate(c):
                    if terrain in l:
                        # Trim Collision to be just the lines that have the file
                        v.ColFile = c[i:]
                        break
                else:
                    c = None
                    continue
                break
            else:
                c = None
        if not c:
            raise Exception(
                "Collision {} not found in levels/{}/{}leveldata.c".format(
                    terrain, scene.LevelImp.Level, scene.LevelImp.Prefix
                )
            )
        Collisions = FormatDat(v.ColFile, "Collision", ["(", ")"])
        v.ColFile = Collisions[terrain]
    return lvl


def WriteLevelCollision(lvl: Level, scene: bpy.types.Scene, cleanup: bool, col_name: str = None):
    for k, v in lvl.Areas.items():
        if not col_name:
            col = v.root.users_collection[0]
        else:
            col = CreateCol(v.root.users_collection[0], col_name)
        # dat is a class that holds all the collision files data
        dat = Collision(v.ColFile, scene.blenderToSM64Scale)
        dat.GetCollision()
        name = "SM64 {} Area {} Col".format(scene.LevelImp.Level, k)
        obj = dat.WriteCollision(scene, name, v.root, col=col)
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


# get all the relevant data types cleaned up and organized for the f3d class
def FormatModel(gfx: sm64_F3d, model: list[str]):
    # For each data type, make an attribute where it cleans the input of the model files
    gfx.VB.update(FormatDat(model, "Vtx", ["{", "}"]))
    gfx.Gfx.update(FormatDat(model, "Gfx", ["(", ")"]))
    gfx.diff.update(FormatDat(model, "Light_t", [None, None]))
    gfx.amb.update(FormatDat(model, "Ambient_t", [None, None]))
    gfx.Lights.update(FormatDat(model, "Lights1", [None, None]))
    # For textures, try u8, and s16 aswell
    gfx.Textures.update(FormatDat(model, "Texture", [None, None]))
    gfx.Textures.update(FormatDat(model, "u8", [None, None]))
    gfx.Textures.update(FormatDat(model, "s16", [None, None]))
    return gfx


# Search through a C file to find data of typeName[] and split it into a list
# of macros with all comments removed
def FormatDat(lines: list[str], typeName: str, Delims: list[str]):
    # Get a dictionary made up with keys=level script names
    # and values as an array of all the cmds inside.
    Models = {}
    InlineReg = "/\*((?!\*/).)*\*/"  # filter out inline comments
    regX = "\[[0-9a-fx]*\]"  # array bounds, basically [] with any number in it
    currScr = 0  # name of current arr of type typeName
    skip = 0  # bool to skip during macros
    for l in lines:
        # remove line comment
        comment = l.rfind("//")
        if comment:
            l = l[:comment]
        # check for macro
        if "#ifdef" in l:
            skip = EvalMacro(l)
        if "#elif" in l:
            skip = EvalMacro(l)
        if "#else" in l:
            skip = 0
            continue
        # Now Check for level script starts
        match = re.search(regX, l, flags=re.IGNORECASE)
        if typeName in l and match and not skip:
            # get var name, get substring from typename to []
            var = l[l.find(typeName) + len(typeName) : match.span()[0]].strip()
            Models[var] = ""
            currScr = var
            continue
        if currScr and not skip:
            # remove inline comments from line
            l = re.sub(InlineReg, "", l)
            # Check for end of Level Script array
            if "};" in l:
                currScr = 0
            # Add line to dict
            else:
                Models[currScr] += l
    # Now remove newlines from each script, and then split macro ends
    # This makes each member of the array a single macro
    for script, v in Models.items():
        v = v.replace("\n", "")
        arr = []  # arr of macros
        buf = ""  # buf to put currently processed macro in
        x = 0  # cur position in str
        stack = 0  # stack cnt of parenthesis
        app = 0  # flag to append macro
        while x < len(v):
            char = v[x]
            if char == Delims[0]:
                stack += 1
                app = 1
            if char == Delims[1]:
                stack -= 1
            if app == 1 and stack == 0:
                app = 0
                buf += v[x : x + 2]  # get the last parenthesis and comma
                arr.append(buf.strip())
                x += 2
                buf = ""
                continue
            buf += char
            x += 1
        # for when the delim characters are nothing
        if buf:
            arr.append(buf)
        Models[script] = arr
    return Models


# given a geo.c file and a path, return cleaned up geo layouts in a dict
def GetGeoLayouts(geo: typing.TextIO, root_path: Path):
    layouts = ParseAggregat(geo, "geo.inc.c", root_path)
    if not layouts:
        return
    # because of fast64, these can be recursively defined (though I expect only a depth of one)
    for l in layouts:
        geoR = open(l, "r")
        layouts += ParseAggregat(geoR, "geo.inc.c", root_path)
    GeoLayouts = {}  # stores cleaned up geo layout lines
    for l in layouts:
        l = open(l, "r")
        lines = l.readlines()
        GeoLayouts.update(FormatDat(lines, "GeoLayout", ["(", ")"]))
    return GeoLayouts


# Find DL references given a level geo file and a path to a level folder
def FindLvlModels(geo: typing.TextIO, lvl: Level, scene: bpy.types.Scene, root_path: Path, col_name: str = None):
    GeoLayouts = GetGeoLayouts(geo, root_path)
    for k, v in lvl.Areas.items():
        GL = v.geo
        rt = v.root
        if col_name:
            col = CreateCol(v.root.users_collection[0], col_name)
        else:
            col = None
        Geo = GeoLayout(GeoLayouts, rt, scene, "GeoRoot {} {}".format(scene.LevelImp.Level, k), rt, col=col)
        Geo.ParseLevelGeosStart(GL, scene)
        v.geo = Geo
    return lvl


# Parse an aggregate group file or level data file for geo layouts
def FindActModels(
    geo: typing.TextIO,
    Layout: str,
    scene: bpy.types.Scene,
    rt: bpy.types.Object,
    root_path: Path,
    col: bpy.types.Collection = None,
):
    GeoLayouts = GetGeoLayouts(geo, root_path)
    Geo = GeoLayout(GeoLayouts, rt, scene, "{}".format(Layout), rt, col=col)
    Geo.ParseLevelGeosStart(Layout, scene)
    return Geo


# Parse an aggregate group file or level data file for f3d data
def FindModelDat(aggregate: Path, scene: bpy.types.Scene, root_path: Path):
    leveldat = open(aggregate, "r")
    models = ParseAggregat(leveldat, "model.inc.c", root_path)
    models += ParseAggregat(leveldat, "painting.inc.c", root_path)
    # fast64 makes a leveldata.inc.c file and puts custom content there, I want to catch that as well
    # this isn't the best way to do this, but I will be lazy here
    fast64 = ParseAggregat(leveldat, "leveldata.inc.c", root_path)
    if fast64:
        f64dat = open(fast64[0], "r")
        models += ParseAggregat(f64dat, "model.inc.c", root_path)
    # leveldat.seek(0)  # so it may be read multiple times
    textures = ParseAggregat(leveldat, "texture.inc.c", root_path)  # Only deal with textures that are actual .pngs
    textures.extend(ParseAggregat(leveldat, "textureNew.inc.c", root_path))  # For RM2C support
    # Get all modeldata in the level
    Models = sm64_F3d(scene)
    for m in models:
        md = open(m, "r")
        lines = md.readlines()
        Models = FormatModel(Models, lines)
    # Update file to have texture.inc.c textures, deal with included textures in the model.inc.c files aswell
    for t in [*textures, *models]:
        t = open(t, "r")
        tex = t.readlines()
        # For textures, try u8, and s16 aswell
        Models.Textures.update(FormatDat(tex, "Texture", [None, None]))
        Models.Textures.update(FormatDat(tex, "u8", [None, None]))
        Models.Textures.update(FormatDat(tex, "s16", [None, None]))
        t.close()
    return Models


# from a geo layout, create all the mesh's
def ReadGeoLayout(
    geo: GeoLayout, scene: bpy.types.Scene, f3d_dat: sm64_F3d, root_path: Path, meshes: dict, cleanup: bool = True
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
            RotateObj(-90, obj)
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
    if not geo.Children:
        return
    for g in geo.Children:
        ReadGeoLayout(g, scene, f3d_dat, root_path, meshes, cleanup=cleanup)


# write the gfx for a level given the level data, and f3d data
def WriteLevelModel(lvl: Level, scene: bpy.types.Scene, root_path: Path, f3d_dat: sm64_F3d, cleanup: bool = True):
    for k, v in lvl.Areas.items():
        # Parse the geolayout class I created earlier to look for models
        meshes = {}  # re use mesh data when the same DL is referenced (bbh is good example)
        ReadGeoLayout(v.geo, scene, f3d_dat, root_path, meshes, cleanup=cleanup)
    return lvl


# given a path, get a level object by parsing the script.c file
def ParseScript(script: Path, scene: bpy.types.Scene, col: bpy.types.Collection = None):
    scr = open(script, "r")
    Root = bpy.data.objects.new("Empty", None)
    if not col:
        scene.collection.objects.link(Root)
    else:
        col.objects.link(Root)
    Root.name = "Level Root {}".format(scene.LevelImp.Level)
    Root.sm64_obj_type = "Level Root"
    # Now parse the script and get data about the level
    # Store data in attribute of a level class then assign later and return class
    scr = scr.readlines()
    lvl = Level(scr, scene, Root)
    entry = scene.LevelImp.Entry.format(scene.LevelImp.Level)
    lvl.ParseScript(entry, col=col)
    return lvl


# write the objects from a level object
def WriteObjects(lvl: Level, col_name: str = None):
    for area in lvl.Areas.values():
        area.PlaceObjects(col_name=col_name)


# import level graphics given geo.c file, and a level object
def ImportLvlVisual(
    geo: typing.TextIO,
    lvl: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    aggregate: Path,
    cleanup: bool = True,
    col_name: str = None,
):
    lvl = FindLvlModels(geo, lvl, scene, root_path, col_name=col_name)
    models = FindModelDat(aggregate, scene, root_path)
    # just a try, in case you are importing from something other than base decomp repo (like RM2C output folder)
    try:
        models.GetGenericTextures(root_path)
    except:
        print("could not import genric textures, if this errors later from missing textures this may be why")
    lvl = WriteLevelModel(lvl, scene, root_path, models, cleanup=cleanup)
    return lvl


# import level collision given a level script
def ImportLvlCollision(
    aggregate: Path,
    lvl: Level,
    scene: bpy.types.Scene,
    root_path: Path,
    cleanup: bool,
    col_name: str = None,
):
    lvl = FindCollisions(aggregate, lvl, scene, root_path)  # Now Each area has its collision file nicely formatted
    WriteLevelCollision(lvl, scene, cleanup, col_name=col_name)
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
        path = Path(scene.decompPath)
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
        geo = open(geo, "r")
        Root = bpy.data.objects.new("Empty", None)
        Root.name = "Actor %s" % scene.ActImp.GeoLayout
        rt_col.objects.link(Root)

        Geo = FindActModels(
            geo, Layout, scene, Root, folder, col=rt_col
        )  # return geo layout class and write the geo layout
        models = FindModelDat(leveldat, scene, folder)
        # just a try, in case you are importing from not the base decomp repo
        try:
            models.GetGenericTextures(path)
        except:
            print("could not import genric textures, if this errors later from missing textures this may be why")
        meshes = {}  # re use mesh data when the same DL is referenced (bbh is good example)
        ReadGeoLayout(Geo, scene, models, folder, meshes, cleanup=self.cleanup)
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
        path = Path(scene.decompPath)
        level = path / "levels" / scene.LevelImp.Level
        script = level / (prefix + "script.c")
        geo = level / (prefix + "geo.c")
        leveldat = level / (prefix + "leveldata.c")
        geo = open(geo, "r")
        lvl = ParseScript(script, scene, col=col)  # returns level class
        WriteObjects(lvl, col_name=obj_col)
        lvl = ImportLvlCollision(leveldat, lvl, scene, path, self.cleanup, col_name=col_col)
        lvl = ImportLvlVisual(geo, lvl, scene, path, leveldat, cleanup=self.cleanup, col_name=gfx_col)
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
        path = Path(scene.decompPath)
        level = path / "levels" / scene.LevelImp.Level
        script = level / (prefix + "script.c")
        geo = level / (prefix + "geo.c")
        model = level / (prefix + "leveldata.c")
        geo = open(geo, "r")
        lvl = ParseScript(script, scene, col=col)  # returns level class
        lvl = ImportLvlVisual(geo, lvl, scene, path, model, cleanup=self.cleanup, col_name=gfx_col)
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
        path = Path(scene.decompPath)
        level = path / "levels" / scene.LevelImp.Level
        script = level / (prefix + "script.c")
        geo = level / (prefix + "geo.c")
        model = level / (prefix + "leveldata.c")
        geo = open(geo, "r")
        lvl = ParseScript(script, scene, col=col)  # returns level class
        lvl = ImportLvlCollision(model, lvl, scene, path, self.cleanup, col_name=col_col)
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
        path = Path(scene.decompPath)
        level = path / "levels" / scene.LevelImp.Level
        script = level / (prefix + "script.c")
        lvl = ParseScript(script, scene, col=col)  # returns level class
        WriteObjects(lvl, col_name=obj_col)
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
        items=[
            ("VERSION_US", "VERSION_US", ""),
            ("VERSION_JP", "VERSION_JP", ""),
            ("VERSION_EU", "VERSION_EU", ""),
            ("VERSION_SH", "VERSION_SH", ""),
        ],
    )
    Target: StringProperty(
        name="Target", description="The platform target for any #ifdefs in code", default="TARGET_N64"
    )


class LevelImport(PropertyGroup):
    Level: EnumProperty(
        name="Level",
        description="Choose a level",
        items=[
            ("bbh", "bbh", ""),
            ("ccm", "ccm", ""),
            ("hmc", "hmc", ""),
            ("ssl", "ssl", ""),
            ("bob", "bob", ""),
            ("sl", "sl", ""),
            ("wdw", "wdw", ""),
            ("jrb", "jrb", ""),
            ("thi", "thi", ""),
            ("ttc", "ttc", ""),
            ("rr", "rr", ""),
            ("castle_grounds", "castle_grounds", ""),
            ("castle_inside", "castle_inside", ""),
            ("bitdw", "bitdw", ""),
            ("vcutm", "vcutm", ""),
            ("bitfs", "bitfs", ""),
            ("sa", "sa", ""),
            ("bits", "bits", ""),
            ("lll", "lll", ""),
            ("ddd", "ddd", ""),
            ("wf", "wf", ""),
            ("ending", "ending", ""),
            ("castle_courtyard", "castle_courtyard", ""),
            ("pss", "pss", ""),
            ("cotmc", "cotmc", ""),
            ("totwc", "totwc", ""),
            ("bowser_1", "bowser_1", ""),
            ("wmotr", "wmotr", ""),
            ("bowser_2", "bowser_2", ""),
            ("bowser_3", "bowser_3", ""),
            ("ttm", "ttm", ""),
        ],
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
        items=[
            ("VERSION_US", "VERSION_US", ""),
            ("VERSION_JP", "VERSION_JP", ""),
            ("VERSION_EU", "VERSION_EU", ""),
            ("VERSION_SH", "VERSION_SH", ""),
        ],
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
