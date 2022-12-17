# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations

import bpy

import os, struct, math, enum

from functools import lru_cache
from pathlib import Path
from mathutils import Vector, Euler, Matrix
from collections import namedtuple
from dataclasses import dataclass
from copy import deepcopy
from re import findall
from typing import BinaryIO, TextIO

from . import f3dex2
from .kcs_utils import *
from .kcs_data import (
    Geo_Header,
    Layout,
    TextureScrollStruct,
)

# fast64 imports

from ..utility import (
    propertyGroupGetEnums,
    checkUniqueBoneNames,
    duplicateHierarchy,
    cleanupDuplicatedObjects,
    getFMeshName,
)

from ..f3d.f3d_writer import (
    getInfoDict,
    saveStaticModel,
    TriangleConverterInfo,
)

from ..f3d.f3d_gbi import (
    DLFormat,
    GfxListTag,
    GfxMatWriteMethod,
    GfxFormatter,
    GfxList,
    FModel,
    FMesh,
    FMaterial,
    DPSetTextureImage,
)


# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------

# geo data

# import only classes


class Vertices:
    _Vec3 = namedtuple("Vec3", "x y z")
    _UV = namedtuple("UV", "s t")
    _color = namedtuple("rgba", "r g b a")

    def __init__(self, scale: float):
        self.UVs = []
        self.VCs = []
        self.Pos = []
        self.scale = scale

    def _make(self, v: tuple):
        self.Pos.append(self.scale_verts(self._Vec3._make(v[0:3])))
        self.UVs.append(self._UV._make(v[4:6]))
        self.VCs.append(self._color._make(v[6:10]))  # holds norms and vcs when importing

    def scale_verts(self, pos: tuple):
        v = [a / self.scale for a in pos]
        return v


# this is the class that holds the actual individual scroll struct and textures
class tx_scroll:
    _scroll = namedtuple("texture_scroll", " ".join([x[1] for x in TextureScrollStruct.values()]))

    def __init__(self, *args: tuple):
        self.scroll = self._scroll._make(*args)


# each texture scroll will start from an array of ptrs, and each ptr will reference
# tex scroll data
class Tex_Scroll(BinProcess, BinWrite):
    def extract_dict(self, start, dict):
        a = []
        for k, v in dict.items():
            try:
                if v[3]:
                    a.append(self.upt(start + k, v[0], v[2]))
            except:
                a.append(self.upt(start + k, v[0], v[2])[0])
        return a

    def __init__(self, scrollPtrs, file, ptr):
        self.scroll_ptrs = scrollPtrs
        self.scrolls = {}
        self.file = file
        self.ptr = ptr
        for p in scrollPtrs:
            if p != 0x99999999 and p:
                # get struct
                scr = tx_scroll(self.extract_dict(self.seg2phys(p), TextureScrollStruct))
                self.scrolls[p] = scr
                # search for palletes
                if scr.scroll.palettes:
                    start = self.seg2phys(scr.scroll.palettes)
                    self.pal_start = scr.scroll.textures
                    scr.palettes = self.get_BI_pairs(start, stop=(0x9999, 0x9999))
                # search for textures
                if scr.scroll.textures:
                    start = self.seg2phys(scr.scroll.textures)
                    self.tx_start = scr.scroll.textures
                    scr.textures = self.get_BI_pairs(start, stop=(0x9999, 0x9999))


# this will hold tile properties
class Tile:
    def __init__(self):
        self.Fmt = "RGBA"
        self.Siz = "16"
        self.Slow = 32
        self.Tlow = 32
        self.Shigh = 32
        self.Thigh = 32
        self.SMask = 5
        self.TMask = 5
        self.SShift = 0
        self.TShift = 0
        self.Sflags = None
        self.Tflags = None

    def bounds(self):
        return (self.Slow << 2, self.Tlow << 2, self.Shigh << 2, self.Thigh << 2)

    def load_tile(self, tmem=0, num=0, pal_num=0):
        return (
            self.Fmt,
            self.Siz,
            "n rows",
            tmem,
            "G_TX_LOADTILE",
            0,
            self.Tflags,
            self.TMask,
            self.TShift,
            self.Sflags,
            self.SMask,
            self.SShift,
        )

    def render_tile(self, tmem=0, num=0, pal_num=0):
        return (
            self.Fmt,
            self.Siz,
            "n rows",
            tmem,
            num,
            pal_num,
            self.Tflags,
            self.TMask,
            self.TShift,
            self.Sflags,
            self.SMask,
            self.SShift,
        )


# this will hold texture properties, dataclass props
# are created in order for me to make comparisons in a set
@dataclass(init=True, eq=True, unsafe_hash=True)
class Texture:
    Timg: tuple
    Fmt: str
    Siz: int
    Width: int = 0
    Height: int = 0
    Pal: tuple = None

    def set_img(self):
        return (self.Fmt, self.Siz, 1, self.Timg)

    def load_img(self):
        return ("G_TX_LOADTILE", 0, 0, "math", "dxt")

    def size(self):
        return self.Width, self.Height


# This is a data storage class and mat to f3dmat converting class
# used when importing for kirby
class Mat:
    def __init__(self):
        self.TwoCycle = False
        self.GeoSet = []
        self.GeoClear = []
        self.tiles = [Tile() for a in range(8)]
        self.tex0 = None
        self.tex1 = None
        self.tx_scr = None

    # calc the hash for an f3d mat and see if its equal to this mats hash
    def math_hash_f3d(self, f3d):
        # texture,1 cycle combiner, render mode, geo modes, some other blender settings, tile size (very important in kirby64)
        rdp = f3d.rdp_settings
        if f3d.tex0.tex:
            T = f3d.tex0.tex_reference
        else:
            T = ""
        F3Dprops = (
            T,
            f3d.combiner1.A,
            f3d.combiner1.B,
            f3d.combiner1.C,
            f3d.combiner1.D,
            f3d.combiner1.A_alpha,
            f3d.combiner1.B_alpha,
            f3d.combiner1.C_alpha,
            f3d.combiner1.D_alpha,
            f3d.rdp_settings.render_mode.rendermode_preset_cycle_1,
            f3d.rdp_settings.render_mode.rendermode_preset_cycle_2,
            f3d.rdp_settings.g_lighting,
            f3d.rdp_settings.g_shade,
            f3d.rdp_settings.g_shade_smooth,
            f3d.rdp_settings.g_zbuffer,
            f3d.rdp_settings.g_mdsft_alpha_compare,
            f3d.rdp_settings.g_mdsft_zsrcsel,
            f3d.rdp_settings.g_mdsft_alpha_dither,
            f3d.tex0.S.high,
            f3d.tex0.T.high,
            f3d.tex0.S.low,
            f3d.tex0.T.low,
        )
        if hasattr(self, "Combiner"):
            MyT = ""
            if hasattr(self.tex0, "Timg"):
                MyT = str(self.tex0.Timg)
            else:
                pass

            def EvalGeo(self, mode):
                for a in self.GeoSet:
                    if mode in a.lower():
                        return True
                for a in self.GeoClear:
                    if mode in a.lower():
                        return False
                else:
                    return True

            chkT = lambda x, y, d: x.__dict__.get(y, d)
            rendermode = getattr(self, "RenderMode", ["G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2"])
            MyProps = (
                MyT,
                *self.Combiner[0:8],
                *rendermode,
                EvalGeo(self, "g_lighting"),
                EvalGeo(self, "g_shade"),
                EvalGeo(self, "g_shade_smooth"),
                EvalGeo(self, "g_zbuffer"),
                chkT(self, "g_mdsft_alpha_compare", "G_AC_NONE"),
                chkT(self, "g_mdsft_zsrcsel", "G_ZS_PIXEL"),
                chkT(self, "g_mdsft_alpha_dither", "G_AD_NOISE"),
                self.tiles[0].Shigh,
                self.tiles[0].Thigh,
                self.tiles[0].Slow,
                self.tiles[0].Tlow,
            )
            dupe = hash(MyProps) == hash(F3Dprops)
            return dupe
        return False

    def mat_hash(self, mat):
        return False

    def convert_color(self, color):
        return [int(a) / 255 for a in color]

    def load_texture(self, ForceNewTex, path, tex):
        png = path / f"bank_{tex.Timg[0]}" / f"{tex.Timg[1]}"
        png = (*png.glob("*.png"),)
        if png:
            i = bpy.data.images.get(str(png[0]))
            if not i or ForceNewTex:
                return bpy.data.images.load(filepath=str(png[0]))
            else:
                return i

    def apply_PBSDF_mat(self, mat):
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        pbsdf = nodes.get("Principled BSDF")
        tex = nodes.new("ShaderNodeTexImage")
        links.new(pbsdf.inputs[0], tex.outputs[0])
        links.new(pbsdf.inputs[19], tex.outputs[1])
        i = self.load_texture(0, path)
        if i:
            tex.image = i

    def apply_mat_settings(self, mat, tex_path):
        #        if bpy.context.scene.LevelImp.AsObj:
        #            return self.apply_PBSDF_mat(mat, textures, path, layer)

        f3d = mat.f3d_mat  # This is kure's custom property class for materials

        # set color registers if they exist
        if hasattr(self, "fog_position"):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_position[0] = eval(self.fog_pos[0])
            f3d.fog_position[1] = eval(self.fog_pos[1])
        if hasattr(self, "fog_color"):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_color = self.convert_color(self.fog_color)
        if hasattr(self, "light_col"):
            # this is a dict but I'll only use the first color for now
            f3d.set_lights = True
            if self.light_col.get(1):
                f3d.default_light_color = self.convert_color(eval(self.light_col[1]).to_bytes(4, "big"))
        if hasattr(self, "env_color"):
            f3d.set_env = True
            f3d.env_color = self.convert_color(self.env_color[-4:])
        if hasattr(self, "prim_color"):
            prim = self.prim_color
            f3d.set_prim = True
            f3d.prim_lod_min = int(prim[0])
            f3d.prim_lod_frac = int(prim[1])
            f3d.prim_color = self.convert_color(prim[-4:])
        # I set these but they aren't properly stored because they're reset by fast64 or something
        # its better to have defaults than random 2 cycles
        self.set_geo_mode(f3d.rdp_settings, mat)

        if self.TwoCycle:
            f3d.rdp_settings.g_mdsft_cycletype = "G_CYC_2CYCLE"
        else:
            f3d.rdp_settings.g_mdsft_cycletype = "G_CYC_1CYCLE"

        # make combiner custom
        f3d.presetName = "Custom"
        self.set_combiner(f3d)
        # add tex scroll objects
        if self.tx_scr:
            scr = self.tx_scr
            mat_scr = mat.KCS_tx_scroll
            if hasattr(scr, "textures"):
                [mat_scr.AddTex(t) for t in scr.textures]
            if hasattr(scr, "palettes"):
                [mat_scr.AddPal(t) for t in scr.palettes]
        # deal with custom render modes
        if hasattr(self, "RenderMode"):
            self.set_render_mode(f3d)
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
        # texture 0 then texture 1
        if self.tex0:
            i = self.load_texture(0, tex_path, self.tex0)
            tex0 = f3d.tex0
            tex0.tex_reference = str(self.tex0.Timg)  # setting prop for hash purposes
            tex0.tex_set = True
            tex0.tex = i
            tex0.tex_format = self.eval_tile_fmt(self.tiles[0])
            tex0.autoprop = False
            Sflags = self.eval_tile_flags(self.tiles[0].Sflags)
            for f in Sflags:
                setattr(tex0.S, f, True)
            Tflags = self.eval_tile_flags(self.tiles[0].Tflags)
            for f in Sflags:
                setattr(tex0.T, f, True)
            tex0.S.low = self.tiles[0].Slow
            tex0.T.low = self.tiles[0].Tlow
            tex0.S.high = self.tiles[0].Shigh
            tex0.T.high = self.tiles[0].Thigh

            tex0.S.mask = self.tiles[0].SMask
            tex0.T.mask = self.tiles[0].TMask
        if self.tex1:
            i = self.load_texture(0, tex_path, self.tex1)
            tex1 = f3d.tex1
            tex1.tex_reference = str(self.tex1.Timg)  # setting prop for hash purposes
            tex1.tex_set = True
            tex1.tex = i
            tex1.tex_format = self.eval_tile_fmt(self.tiles[1])
            Sflags = self.eval_tile_flags(self.tiles[1].Sflags)
            for f in Sflags:
                setattr(tex1.S, f, True)
            Tflags = self.eval_tile_flags(self.tiles[1].Tflags)
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

    def eval_tile_flags(self, flags):
        if not flags:
            return []
        GBIflags = {
            "G_TX_NOMIRROR": None,
            "G_TX_WRAP": None,
            "G_TX_MIRROR": ("mirror"),
            "G_TX_CLAMP": ("clamp"),
            "0": None,
            "1": ("mirror"),
            "2": ("clamp"),
            "3": ("clamp", "mirror"),
        }
        x = []
        fsplit = flags.split("|")
        for f in fsplit:
            z = GBIflags.get(f.strip(), 0)
            if z:
                x.append(z)
        return x

    # only work with macros I can recognize for now
    def set_render_mode(self, f3d):
        rdp = f3d.rdp_settings
        rdp.set_rendermode = True
        # if the enum isn't there, then just print an error for now
        try:
            rdp.rendermode_preset_cycle_1 = self.RenderMode[0]
            rdp.rendermode_preset_cycle_2 = self.RenderMode[1]
            # print(f"set render modes with render mode {self.RenderMode}")
        except:
            print(f"could not set render modes with render mode {self.RenderMode}")

    def set_geo_mode(self, rdp, mat):
        # texture gen has a different name than gbi
        for a in self.GeoSet:
            setattr(rdp, a.replace("G_TEXTURE_GEN", "G_TEX_GEN").lower().strip(), True)
        for a in self.GeoClear:
            setattr(rdp, a.replace("G_TEXTURE_GEN", "G_TEX_GEN").lower().strip(), False)

    # Very lazy for now
    def set_combiner(self, f3d):
        if not hasattr(self, "Combiner"):
            f3d.combiner1.A = "TEXEL0"
            f3d.combiner1.A_alpha = "0"
            f3d.combiner1.C = "SHADE"
            f3d.combiner1.C_alpha = "0"
            f3d.combiner1.D = "0"
            f3d.combiner1.D_alpha = "1"
        else:
            f3d.combiner1.A = self.Combiner[0]
            f3d.combiner1.B = self.Combiner[1]
            f3d.combiner1.C = self.Combiner[2]
            f3d.combiner1.D = self.Combiner[3]
            f3d.combiner1.A_alpha = self.Combiner[4]
            f3d.combiner1.B_alpha = self.Combiner[5]
            f3d.combiner1.C_alpha = self.Combiner[6]
            f3d.combiner1.D_alpha = self.Combiner[7]
            f3d.combiner2.A = self.Combiner[8]
            f3d.combiner2.B = self.Combiner[9]
            f3d.combiner2.C = self.Combiner[10]
            f3d.combiner2.D = self.Combiner[11]
            f3d.combiner2.A_alpha = self.Combiner[12]
            f3d.combiner2.B_alpha = self.Combiner[13]
            f3d.combiner2.C_alpha = self.Combiner[14]
            f3d.combiner2.D_alpha = self.Combiner[15]

    def eval_tile_fmt(self, tex):
        GBIfmts = {
            "G_IM_FMT_RGBA": "RGBA",
            "RGBA": "RGBA",
            "G_IM_FMT_CI": "CI",
            "CI": "CI",
            "G_IM_FMT_IA": "IA",
            "IA": "IA",
            "G_IM_FMT_I": "I",
            "I": "I",
            "0": "RGBA",
            "2": "CI",
            "3": "IA",
            "4": "I",
        }
        GBIsiz = {
            "G_IM_SIZ_4b": "4",
            "G_IM_SIZ_8b": "8",
            "G_IM_SIZ_16b": "16",
            "G_IM_SIZ_32b": "32",
            "0": "4",
            "1": "8",
            "2": "16",
            "3": "32",
        }
        return GBIfmts.get(tex.Fmt, "RGBA") + GBIsiz.get(str(tex.Siz), "16")


# handles DL import processing, specifically built to process each cmd into the mat class
# should be inherited into a larger F3d class which wraps DL processing
# does not deal with flow control or gathering the data containers (VB, Geo cls etc.)
class DL:
    # the min needed for this class to work for importing
    def __init__(self, lastmat=None):
        self.VB = {}
        self.Gfx = {}
        self.diff = {}
        self.amb = {}
        self.Lights = {}
        if not lastmat:
            self.LastMat = Mat()
            self.LastMat.name = 0
        else:
            self.LastMat = lastmat

    # DL cmds that control the flow of a DL cannot be handled within a independent	#class method without larger context of the total DL
    # def gsSPEndDisplayList():
    # return
    # def gsSPBranchList():
    # break
    # def gsSPDisplayList():
    # continue
    # Vertices are one big list for kirby64, all buffers are combined in pre process
    def gsSPVertex(self, args, Geo):
        # fill virtual buffer
        args = [int(a) for a in args]
        addr = Geo.seg2phys(args[0]) - 32
        start = int(addr // 16)
        for i in range(args[2], args[2] + args[1], 1):
            self.VertBuff[i] = len(self.Verts) + i - args[2]
        # verts are pre processed
        self.Verts.extend(Geo.vertices.Pos[start : start + args[1]])
        self.UVs.extend(Geo.vertices.UVs[start : start + args[1]])
        self.VCs.extend(Geo.vertices.VCs[start : start + args[1]])

    # Triangles
    def gsSP2Triangles(self, args, Geo):
        self.make_new_mat()
        args = [int(a) for a in args]
        Tri1 = self.parse_tri(args[:3])
        Tri2 = self.parse_tri(args[4:7])
        self.Tris.append(Tri1)
        self.Tris.append(Tri2)

    def gsSP1Triangle(self, args, Geo):
        self.make_new_mat()
        args = [int(a) for a in args]
        Tri = self.parse_tri(args[:3])
        self.Tris.append(Tri)

    # materials
    # Mats will be placed sequentially. The first item of the list is the triangle number
    # The second is the material class
    def gsDPset_render_mode(self, args, Geo):
        self.NewMat = 1
        self.LastMat.RenderMode = [a.strip() for a in args]

    def gsDPSetFogColor(self, args, Geo):
        self.NewMat = 1
        self.LastMat.fog_color = args

    def gsSPFogPosition(self, args, Geo):
        self.NewMat = 1
        self.LastMat.fog_pos = args

    def gsSPLightColor(self, args, Geo):
        self.NewMat = 1
        if not hasattr(self.LastMat, "light_col"):
            self.LastMat.light_col = {}
        num = re.search("_\d", args[0]).group()[1]
        self.LastMat.light_col[num] = args[-1]

    def gsDPSetPrimColor(self, args, Geo):
        self.NewMat = 1
        self.LastMat.prim_color = args

    def gsDPSetEnvColor(self, args, Geo):
        self.NewMat = 1
        self.LastMat.env_color = args

    # multiple geo modes can happen in a row that contradict each other
    # this is mostly due to culling wanting diff geo modes than drawing
    # but sometimes using the same vertices
    def gsSPClearGeometryMode(self, args, Geo):
        self.NewMat = 1
        args = [a.strip() for a in args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoSet:
                self.LastMat.GeoSet.remove(a)
        self.LastMat.GeoClear.extend(args)

    def gsSPSetGeometryMode(self, args, Geo):
        self.NewMat = 1
        args = [a.strip() for a in args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoClear:
                self.LastMat.GeoClear.remove(a)
        self.LastMat.GeoSet.extend(args)

    def gsSPGeometryMode(self, args, Geo):
        self.NewMat = 1
        argsC = [a.strip() for a in args[0].split("|")]
        argsS = [a.strip() for a in args[1].split("|")]
        for a in argsC:
            if a in self.LastMat.GeoSet:
                self.LastMat.GeoSet.remove(a)
        for a in argsS:
            if a in self.LastMat.GeoClear:
                self.LastMat.GeoClear.remove(a)
        self.LastMat.GeoClear.extend(argsC)
        self.LastMat.GeoSet.extend(argsS)

    def gsDPSetCycleType(self, args, Geo):
        if "G_CYC_1CYCLE" in args[0]:
            self.LastMat.TwoCycle = False
        if "G_CYC_2CYCLE" in args[0]:
            self.LastMat.TwoCycle = True

    def gsDPSetCombineMode(self, args, Geo):
        self.NewMat = 1
        self.LastMat.Combiner = args

    def gsDPSetCombineLERP(self, args, Geo):
        self.NewMat = 1
        self.LastMat.Combiner = [a.strip() for a in args]

    # root tile, scale and set tex
    def gsSPTexture(self, args, Geo):
        self.NewMat = 1
        self.LastMat.set_tex = int(args[-1].strip()) == 2
        self.LastMat.tex_scale = [
            ((0x10000 * (int(a) < 0)) + int(a)) / 0xFFFF for a in args[0:2]
        ]  # signed half to unsigned half
        self.LastMat.tile_root = int(args[-2])  # I don't think I'll actually use this

    # last tex is a palette
    def gsDPLoadTLUT(self, args, Geo):
        try:
            tex = self.LastMat.loadtex
            self.LastMat.pal = tex
        except:
            print(
                "**--Load block before set t img, DL is partial and missing context"
                "likely static file meant to be used as a piece of a realtime system.\n"
                "No interpretation on file possible**--"
            )
            return None

    # tells us what tile the last loaded mat goes into
    def gsDPLoadBlock(self, args, Geo):
        try:
            tex = self.LastMat.loadtex
            # these values can be used to calc texture size
            tex.dxt = eval(args[4])
            tex.texels = eval(args[3])
            tile = self.eval_tile_index(args[0])
            tex.tile = tile
            if tile == 7:
                self.LastMat.tex0 = tex
            elif tile == 6:
                self.LastMat.tex1 = tex
        except:
            print(
                "**--Load block before set t img, DL is partial and missing context"
                "likely static file meant to be used as a piece of a realtime system.\n"
                "No interpretation on file possible**--"
            )
            return None

    def gsDPSetTextureImage(self, args, Geo):
        self.NewMat = 1
        Timg = (eval(args[3].strip()) >> 16, eval(args[3].strip()) & 0xFFFF)
        Fmt = args[1].strip()
        Siz = args[2].strip()
        loadtex = Texture(Timg, Fmt, Siz)
        self.LastMat.loadtex = loadtex

    # catch tile size
    def gsDPSetTileSize(self, args, Geo):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.eval_tile_index(args[0])]
        tile.Slow = self.eval_tile_im_frac(args[1].strip())
        tile.Tlow = self.eval_tile_im_frac(args[2].strip())
        tile.Shigh = self.eval_tile_im_frac(args[3].strip())
        tile.Thigh = self.eval_tile_im_frac(args[4].strip())

    def gsDPSetTile(self, args, Geo):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.eval_tile_index(args[4])]
        tile.Fmt = args[0].strip()
        tile.Siz = args[1].strip()
        tile.Tflags = args[6].strip()
        tile.TMask = int(args[7].strip())
        tile.TShift = int(args[8].strip())
        tile.Sflags = args[9].strip()
        tile.SMask = int(args[10].strip())
        tile.SShift = int(args[11].strip())

    def make_new_mat(self):
        if self.NewMat:
            self.NewMat = 0
            self.Mats.append([len(self.Tris) - 1, self.LastMat])
            self.LastMat = deepcopy(self.LastMat)  # for safety
            self.LastMat.name = self.num + 1
            if self.LastMat.tx_scr:
                # I'm clearing here because I did some illegal stuff a bit before, temporary (maybe)
                self.LastMat.tx_scr = None
            self.num += 1

    def parse_tri(self, Tri):
        return [self.VertBuff[a] for a in Tri]

    def eval_tile_im_frac(self, arg):
        if type(arg) == int:
            return arg
        arg2 = arg.replace("G_TEXTURE_IMAGE_FRAC", "2")
        return eval(arg2)

    def eval_tile_index(self, arg):
        # only 0 and 7 have enums, other stuff just uses int (afaik)
        Tiles = {
            "G_TX_LOADTILE": 7,
            "G_TX_RENDERTILE": 0,
        }
        t = Tiles.get(arg)
        if t == None:
            t = int(arg)
        return t


# used to parse imports with specific kirby information, works on entire layouts
class F3d(DL):
    def __init__(self, lastmat=None):
        super().__init__()
        self.num = self.LastMat.name  # for debug

    # use tex scroll struct info to get the equivalent dynamic DL, and set the t_scroll flag to true in mat so when getting mats, I can return an array of mats
    def insert_scroll_dyn_dl(self, Geo, layout, scr_num):
        Tex_Scroll = Geo.tex_scrolls[Geo.tex_header[layout.index]]
        scr = Tex_Scroll.scrolls[Tex_Scroll.scroll_ptrs[scr_num]]
        self.LastMat.tx_scr = scr
        flgs = scr.scroll.flags
        # do textures and palettes by taking only the first texture, the rest will have to go into the scroll object
        if flgs & 3:
            Timg = scr.textures[0]
            Fmt = scr.scroll.fmt1
            Siz = scr.scroll.siz1
            loadtex = Texture(Timg, Fmt, Siz)
            loadtex.scr_tex = scr.textures[:-1]
            self.LastMat.loadtex = loadtex
            # if both textures are present, dyn DL loads tex1 (tile 6)
            # this results in both just being the same as far as my
            # export is concerned, but I will replicate DL bhv
            if flgs & 3 == 3:
                self.LastMat.tex1 = loadtex
                self.LastMat.tex1.scr_tex = scr.textures[:-1]
        # if there is both a tex and a palette, then the load TLUT
        # is inside of the dyn DL, otherwise it isn't
        if flgs & 4:
            Timg = scr.palettes[0]
            Fmt = "G_IM_FMT_RGBA"
            Siz = "G_IM_SIZ_16b"
            pal_tex = Texture(Timg, Fmt, Siz)
            pal_tex.scr_pal = scr.palettes[:-1]
            if scr.scroll.flags & 3:
                self.LastMat.pal = pal_tex
            else:
                self.LastMat.loadtex = pal_tex
        # set some color registers
        if flgs & 0x400:
            self.LastMat.env = scr.scroll.env_col
        if flgs & 0x800:
            self.LastMat.blend = scr.scroll.blend_col
        if flgs & 0x1000:
            self.LastMat.light_col[1] = scr.scroll.light1_col
        if flgs & 0x2000:
            self.LastMat.light_col[2] = scr.scroll.light2_col
        # prim is sort of special and set with various flags
        if flgs & 0x18:
            self.LastMat.prim = (0, scr.scroll.primLODFrac, scr.scroll.prim_col)
        # texture scale
        if flgs & 0x80:
            self.LastMat.tex_scale = (scr.scroll.xScale, scr.scroll.yScale)

    # recursively parse the display list in order to return a bunch of model data
    def get_data_from_dl(self, Geo, layout):
        self.VertBuff = [0] * 32  # If you're doing some fucky shit with a larger vert buffer it sucks to suck I guess
        self.Tris = []
        self.UVs = []
        self.VCs = []
        self.Verts = []
        self.Mats = []
        self.NewMat = 0
        if hasattr(layout, "DLs"):
            for k in layout.entry:
                DL = layout.DLs[k]
                self.parse_dl(DL, Geo, layout)
        return (self.Verts, self.Tris)

    def parse_dl(self, DL, Geo, layout):
        # This will be the equivalent of a giant switch case
        x = -1
        while x < len(DL):
            # manaual iteration so I can skip certain children efficiently if needed
            x += 1
            (cmd, args) = DL[x]  # each member is a tuple of (cmd, arguments)
            LsW = cmd.startswith
            # Deal with control flow first, this requires total DL context
            if LsW("gsSPEndDisplayList"):
                return
            # recursively call parse_dl
            if LsW("gsSPBranchList"):
                if self.eval_dl_segptr(args[0]):
                    self.parse_dl(layout.DLs[self.eval_dl_segptr(args[0])], Geo, layout)
                else:
                    scr_num = (eval(args[0]) & 0xFFFF) // 8
                    self.insert_scroll_dyn_dl(Geo, layout, scr_num)
                break
            if LsW("gsSPDisplayList"):
                if self.eval_dl_segptr(args[0]):
                    self.parse_dl(layout.DLs[self.eval_dl_segptr(args[0])], Geo, layout)
                else:
                    scr_num = (eval(args[0]) & 0xFFFF) // 8
                    self.insert_scroll_dyn_dl(Geo, layout, scr_num)
                continue
            # tri and mat DL cmds will be called via parent class
            func = getattr(self, cmd, None)
            if func:
                func(args, Geo)

    def eval_combiner(self, arg):
        # two args
        GBI_CC_Macros = {
            "G_CC_PRIMITIVE": ["0", "0", "0", "PRIMITIVE", "0", "0", "0", "PRIMITIVE"],
            "G_CC_SHADE": ["0", "0", "0", "SHADE", "0", "0", "0", "SHADE"],
            "G_CC_MODULATEI": ["TEXEL0", "0", "SHADE", "0", "0", "0", "0", "SHADE"],
            "G_CC_MODULATEIDECALA": ["TEXEL0", "0", "SHADE", "0", "0", "0", "0", "TEXEL0"],
            "G_CC_MODULATEIFADE": ["TEXEL0", "0", "SHADE", "0", "0", "0", "0", "ENVIRONMENT"],
            "G_CC_MODULATERGB": ["TEXEL0", "0", "SHADE", "0", "0", "0", "0", "SHADE"],
            "G_CC_MODULATERGBDECALA": ["TEXEL0", "0", "SHADE", "0", "0", "0", "0", "TEXEL0"],
            "G_CC_MODULATERGBFADE": ["TEXEL0", "0", "SHADE", "0", "0", "0", "0", "ENVIRONMENT"],
            "G_CC_MODULATEIA": ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"],
            "G_CC_MODULATEIFADEA": ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "ENVIRONMENT", "0"],
            "G_CC_MODULATEFADE": ["TEXEL0", "0", "SHADE", "0", "ENVIRONMENT", "0", "TEXEL0", "0"],
            "G_CC_MODULATERGBA": ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"],
            "G_CC_MODULATERGBFADEA": ["TEXEL0", "0", "SHADE", "0", "ENVIRONMENT", "0", "TEXEL0", "0"],
            "G_CC_MODULATEI_PRIM": ["TEXEL0", "0", "PRIMITIVE", "0", "0", "0", "0", "PRIMITIVE"],
            "G_CC_MODULATEIA_PRIM": ["TEXEL0", "0", "PRIMITIVE", "0", "TEXEL0", "0", "PRIMITIVE", "0"],
            "G_CC_MODULATEIDECALA_PRIM": ["TEXEL0", "0", "PRIMITIVE", "0", "0", "0", "0", "TEXEL0"],
            "G_CC_MODULATERGB_PRIM": ["TEXEL0", "0", "PRIMITIVE", "0", "TEXEL0", "0", "PRIMITIVE", "0"],
            "G_CC_MODULATERGBA_PRIM": ["TEXEL0", "0", "PRIMITIVE", "0", "TEXEL0", "0", "PRIMITIVE", "0"],
            "G_CC_MODULATERGBDECALA_PRIM": ["TEXEL0", "0", "PRIMITIVE", "0", "0", "0", "0", "TEXEL0"],
            "G_CC_FADE": ["SHADE", "0", "ENVIRONMENT", "0", "SHADE", "0", "ENVIRONMENT", "0"],
            "G_CC_FADEA": ["TEXEL0", "0", "ENVIRONMENT", "0", "TEXEL0", "0", "ENVIRONMENT", "0"],
            "G_CC_DECALRGB": ["0", "0", "0", "TEXEL0", "0", "0", "0", "SHADE"],
            "G_CC_DECALRGBA": ["0", "0", "0", "TEXEL0", "0", "0", "0", "TEXEL0"],
            "G_CC_DECALFADE": ["0", "0", "0", "TEXEL0", "0", "0", "0", "ENVIRONMENT"],
            "G_CC_DECALFADEA": ["0", "0", "0", "TEXEL0", "TEXEL0", "0", "ENVIRONMENT", "0"],
            "G_CC_BLENDI": ["ENVIRONMENT", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"],
            "G_CC_BLENDIA": ["ENVIRONMENT", "SHADE", "TEXEL0", "SHADE", "TEXEL0", "0", "SHADE", "0"],
            "G_CC_BLENDIDECALA": ["ENVIRONMENT", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"],
            "G_CC_BLENDRGBA": ["TEXEL0", "SHADE", "TEXEL0_ALPHA", "SHADE", "0", "0", "0", "SHADE"],
            "G_CC_BLENDRGBDECALA": ["TEXEL0", "SHADE", "TEXEL0_ALPHA", "SHADE", "0", "0", "0", "TEXEL0"],
            "G_CC_BLENDRGBFADEA": ["TEXEL0", "SHADE", "TEXEL0_ALPHA", "SHADE", "0", "0", "0", "ENVIRONMENT"],
            "G_CC_ADDRGB": ["TEXEL0", "0", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"],
            "G_CC_ADDRGBDECALA": ["TEXEL0", "0", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"],
            "G_CC_ADDRGBFADE": ["TEXEL0", "0", "TEXEL0", "SHADE", "0", "0", "0", "ENVIRONMENT"],
            "G_CC_REFLECTRGB": ["ENVIRONMENT", "0", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"],
            "G_CC_REFLECTRGBDECALA": ["ENVIRONMENT", "0", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"],
            "G_CC_HILITERGB": ["PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"],
            "G_CC_HILITERGBA": ["PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "PRIMITIVE", "SHADE", "TEXEL0", "SHADE"],
            "G_CC_HILITERGBDECALA": ["PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "TEXEL0"],
            "G_CC_SHADEDECALA": ["0", "0", "0", "SHADE", "0", "0", "0", "TEXEL0"],
            "G_CC_SHADEFADEA": ["0", "0", "0", "SHADE", "0", "0", "0", "ENVIRONMENT"],
            "G_CC_BLENDPE": ["PRIMITIVE", "ENVIRONMENT", "TEXEL0", "ENVIRONMENT", "TEXEL0", "0", "SHADE", "0"],
            "G_CC_BLENDPEDECALA": ["PRIMITIVE", "ENVIRONMENT", "TEXEL0", "ENVIRONMENT", "0", "0", "0", "TEXEL0"],
            "_G_CC_BLENDPE": ["ENVIRONMENT", "PRIMITIVE", "TEXEL0", "PRIMITIVE", "TEXEL0", "0", "SHADE", "0"],
            "_G_CC_BLENDPEDECALA": ["ENVIRONMENT", "PRIMITIVE", "TEXEL0", "PRIMITIVE", "0", "0", "0", "TEXEL0"],
            "_G_CC_TWOCOLORTEX": ["PRIMITIVE", "SHADE", "TEXEL0", "SHADE", "0", "0", "0", "SHADE"],
            "_G_CC_SPARSEST": [
                "PRIMITIVE",
                "TEXEL0",
                "LOD_FRACTION",
                "TEXEL0",
                "PRIMITIVE",
                "TEXEL0",
                "LOD_FRACTION",
                "TEXEL0",
            ],
            "G_CC_TEMPLERP": [
                "TEXEL1",
                "TEXEL0",
                "PRIM_LOD_FRAC",
                "TEXEL0",
                "TEXEL1",
                "TEXEL0",
                "PRIM_LOD_FRAC",
                "TEXEL0",
            ],
            "G_CC_TRILERP": [
                "TEXEL1",
                "TEXEL0",
                "LOD_FRACTION",
                "TEXEL0",
                "TEXEL1",
                "TEXEL0",
                "LOD_FRACTION",
                "TEXEL0",
            ],
            "G_CC_INTERFERENCE": ["TEXEL0", "0", "TEXEL1", "0", "TEXEL0", "0", "TEXEL1", "0"],
            "G_CC_1CYUV2RGB": ["TEXEL0", "K4", "K5", "TEXEL0", "0", "0", "0", "SHADE"],
            "G_CC_YUV2RGB": ["TEXEL1", "K4", "K5", "TEXEL1", "0", "0", "0", "0"],
            "G_CC_PASS2": ["0", "0", "0", "COMBINED", "0", "0", "0", "COMBINED"],
            "G_CC_MODULATEI2": ["COMBINED", "0", "SHADE", "0", "0", "0", "0", "SHADE"],
            "G_CC_MODULATEIA2": ["COMBINED", "0", "SHADE", "0", "COMBINED", "0", "SHADE", "0"],
            "G_CC_MODULATERGB2": ["COMBINED", "0", "SHADE", "0", "0", "0", "0", "SHADE"],
            "G_CC_MODULATERGBA2": ["COMBINED", "0", "SHADE", "0", "COMBINED", "0", "SHADE", "0"],
            "G_CC_MODULATEI_PRIM2": ["COMBINED", "0", "PRIMITIVE", "0", "0", "0", "0", "PRIMITIVE"],
            "G_CC_MODULATEIA_PRIM2": ["COMBINED", "0", "PRIMITIVE", "0", "COMBINED", "0", "PRIMITIVE", "0"],
            "G_CC_MODULATERGB_PRIM2": ["COMBINED", "0", "PRIMITIVE", "0", "0", "0", "0", "PRIMITIVE"],
            "G_CC_MODULATERGBA_PRIM2": ["COMBINED", "0", "PRIMITIVE", "0", "COMBINED", "0", "PRIMITIVE", "0"],
            "G_CC_DECALRGB2": ["0", "0", "0", "COMBINED", "0", "0", "0", "SHADE"],
            "G_CC_BLENDI2": ["ENVIRONMENT", "SHADE", "COMBINED", "SHADE", "0", "0", "0", "SHADE"],
            "G_CC_BLENDIA2": ["ENVIRONMENT", "SHADE", "COMBINED", "SHADE", "COMBINED", "0", "SHADE", "0"],
            "G_CC_CHROMA_KEY2": ["TEXEL0", "CENTER", "SCALE", "0", "0", "0", "0", "0"],
            "G_CC_HILITERGB2": ["ENVIRONMENT", "COMBINED", "TEXEL0", "COMBINED", "0", "0", "0", "SHADE"],
            "G_CC_HILITERGBA2": [
                "ENVIRONMENT",
                "COMBINED",
                "TEXEL0",
                "COMBINED",
                "ENVIRONMENT",
                "COMBINED",
                "TEXEL0",
                "COMBINED",
            ],
            "G_CC_HILITERGBDECALA2": ["ENVIRONMENT", "COMBINED", "TEXEL0", "COMBINED", "0", "0", "0", "TEXEL0"],
            "G_CC_HILITERGBPASSA2": ["ENVIRONMENT", "COMBINED", "TEXEL0", "COMBINED", "0", "0", "0", "COMBINED"],
        }
        return GBI_CC_Macros.get(
            arg[0].strip(), ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"]
        ) + GBI_CC_Macros.get(arg[1].strip(), ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"])

    def eval_dl_segptr(self, num):
        num = int(num)
        if num >> 24 == 0xE:
            return None
        else:
            return num

    def make_new_mat(self):
        if self.NewMat:
            self.NewMat = 0
            self.Mats.append([len(self.Tris) - 1, self.LastMat])
            self.LastMat = deepcopy(self.LastMat)  # for safety
            self.LastMat.name = self.num + 1
            self.num += 1

    def parse_tri(self, Tri):
        return [self.VertBuff[a] for a in Tri]

    def strip_args(self, cmd):
        a = cmd.find("(")
        return cmd[a + 1 : -2].split(",")

    def apply_f3d_mesh_dat(self, obj, mesh, tex_path):
        tris = mesh.polygons
        bpy.context.view_layer.objects.active = obj
        ind = -1
        new = -1
        UVmap = obj.data.uv_layers.new(name="UVMap")
        # I can get the available enums for color attrs with this func
        vcol_enums = propertyGroupGetEnums(bpy.types.FloatColorAttribute, "data_type")
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
                    mat.name = "KCS F3D Mat {} {}".format(obj.name, new)
                    self.Mats[new][1].apply_mat_settings(mat, tex_path)
                else:
                    # I tried to re use mat slots but it is much slower, and not as accurate
                    # idk if I was just doing it wrong or the search is that much slower, but this is easier
                    mesh.materials.append(new)
                    new = len(mesh.materials) - 1
            # if somehow ther is no material assigned to the triangle or something is lost
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
                    # scale verts. I just copy/pasted this from kirby tbh Idk
                    UVmap.data[l].uv = [a * (1 / (32 * b)) if b > 0 else a * 0.001 * 32 for a, b in zip(uv, WH)]
                    # idk why this is necessary. N64 thing or something?
                    UVmap.data[l].uv[1] = UVmap.data[l].uv[1] * -1 + 1
                    Vcol.data[l].color = [a / 255 for a in vcol]

    def create_new_f3d_mat(self, mat, mesh):
        # check if this mat was used already in another mesh (or this mat if DL is garbage or something)
        # even looping n^2 is probably faster than duping 3 mats with blender speed
        for j, F3Dmat in enumerate(bpy.data.materials):
            if F3Dmat.is_f3d:
                dupe = mat.math_hash_f3d(F3Dmat.f3d_mat)
                if dupe:
                    return F3Dmat
        if mesh.materials:
            mat = mesh.materials[-1]
            new = mat.id_data.copy()  # make a copy of the data block
            # add a mat slot and add mat to it
            mesh.materials.append(new)
        else:
            bpy.ops.object.create_f3d_mat()  # the newest mat should be in slot[-1] for the mesh materials
        return None


@dataclass
class layout(BinProcess, BinWrite):
    flag: int
    depth: int
    ptr: int
    translation: Vector
    rotation: Vector
    scale: Vector
    index: int = 0

    def __post_init__(self):
        self.symbol_init()

    def __hash__(self):
        return id(self)

    @property
    def dat(self):
        return [
            self.flag,
            self.depth,
            self.ptr,
            self.translation,
            self.rotation,
            self.scale,
        ]

    def to_c(self):
        CData = KCS_Cdata()
        self.write_dict_struct(self, Layout, CData, "Layout", f"Geo_LY_{self.index}")
        return CData


# fake storage class that mirrors methods of layout
@dataclass
class faux_LY:
    ptr: int
    index: int = 0

    def __hash__(self):
        return id(self)

    def to_c(self):
        return KCS_Cdata()


# takes binary input and makes geo block data
class geo_bin(BinProcess):
    _Vec3 = namedtuple("Vec3", "x y z")
    _texture = namedtuple("texture", "fmt siz bank_index")

    def __init__(self, file, scale):
        self.file = file
        self.main_header = self.upt(0, ">8L", 32)
        self.scale = scale
        self.get_tex_scrolls()
        self.DLs = (
            dict()
        )  # this is also in layouts, but I want it raw here to print in RAM order, and in layouts to analyze in the processed order
        self.render_mode = self.main_header[2]
        self._render_mode_map[self.render_mode](self)
        # get vtx and img refs null terminated arrays
        self.get_refs()
        self.get_anims()

    def get_tex_scrolls(self):
        if self.main_header[1]:
            start = self.main_header[1]
            # get header of POINTERS
            self.tex_header = self.get_referece_list(start, stop=0x99999999)
            self.tex_scrolls = {}
            for p in self.tex_header:
                if p and p != 0x99999999:
                    self.tex_scrolls[p] = Tex_Scroll(self.get_referece_list(p, stop=0x99999999), self.file, p)
            # sort scrolls
            self.tex_scrolls = self.sort_dict(self.tex_scrolls)

    # anims are bank indices
    def get_anims(self):
        num = self.main_header[5]
        start = self.seg2phys(self.main_header[6])
        self.anims = self.get_BI_pairs(start, num=num)

    # both types of refs are null terminated lists
    def get_refs(self):
        self.img_refs = self.get_referece_list(self.main_header[3])
        self.vtx_refs = self.get_referece_list(self.main_header[4])

    # no layout, just a single DL
    def decode_layout_13(self):
        L = faux_LY(self.seg2phys(self.main_header[0]))
        L.eval_dl_segptrs = [L.ptr]
        self.layouts = [L]
        self.decode_f3d_bin(L)
        Vert_End = L.ptr[0]
        self.decode_vertices(32, Vert_End)

    # no layouts, just an entry point
    def decode_layout_14(self):
        L = faux_LY(self.seg2phys(self.main_header[0]))
        self.decode_entry(L)
        self.layouts = [L]
        self.decode_f3d_bin(L)
        Vert_End = L.ptr[0]
        self.decode_vertices(32, Vert_End)

    # layouts point to DL
    def decode_layout_17(self):
        self.layouts = [
            self.decode_layout(self.main_header[0] + 0x2C * i, index=i) for i in range(self.main_header[-1])
        ]
        starts = []
        for l in self.layouts:
            if l.ptr:
                l.eval_dl_segptrs = [l.ptr]
                starts.extend(self.decode_f3d_bin(l))
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)

    # layouts point to entry point
    def decode_layout_18(self):
        self.layouts = [
            self.decode_layout(self.main_header[0] + 0x2C * i, index=i) for i in range(self.main_header[-1])
        ]
        starts = []
        for l in self.layouts:
            if l.ptr:
                self.decode_entry(l)
                starts.extend(self.decode_f3d_bin(l))
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)

    # layout points to pair of DLs
    def decode_layout_1B(self):
        self.layouts = [
            self.decode_layout(self.main_header[0] + 0x2C * i, index=i) for i in range(self.main_header[-1])
        ]
        starts = []
        for l in self.layouts:
            if l.ptr:
                self.decode_dl_pair(l)
                starts.extend(self.decode_f3d_bin(l))
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)

    # layout points to entry point with pair of DL
    def decode_layout_1C(self):
        self.layouts = [
            self.decode_layout(self.main_header[0] + 0x2C * i, index=i) for i in range(self.main_header[-1])
        ]
        starts = []
        for l in self.layouts:
            if l.ptr:
                self.decode_entry_dbl(l)
                starts.extend(self.decode_f3d_bin(l))
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)

    def decode_layout(self, start, index=None):
        start = self.seg2phys(start)
        LY = self.upt(start, ">2HL9f", 0x2C)
        v = self._Vec3._make
        return layout(*LY[0:3], v(LY[3:6]), v(LY[6:9]), v(LY[9:12]), index=index)

    # has to be after func declarations
    _render_mode_map = {
        0x13: decode_layout_13,
        0x14: decode_layout_14,
        0x17: decode_layout_17,
        0x18: decode_layout_18,
        0x1B: decode_layout_1B,
        0x1C: decode_layout_1C,
    }

    def decode_dl_pair(self, ly: layout):
        ly.eval_dl_segptrs = []  # just a literal list of ptrs
        ptrs = self.upt(self.seg2phys(ly.ptr), ">2L", 8)
        for ptr in ptrs:
            if ptr:
                ly.eval_dl_segptrs.append(ptr)
        ly.DL_Pair = ptrs

    def decode_entry_dbl(self, ly: layout):
        x = 0
        start = self.seg2phys(ly.ptr)
        ly.entry_dbls = []
        ly.eval_dl_segptrs = []  # just a literal list of ptrs
        while True:
            mark, *ptrs = self.upt(start + x, ">3L", 12)
            ly.entry_dbls.append((mark, ptrs))
            if mark == 4:
                return
            else:
                for ptr in ptrs:
                    if ptr:
                        ly.eval_dl_segptrs.append(ptr)
            x += 12
            # shouldn't execute
            if x > 120:
                print("your while loop is broken in geo_bin.decode_entry")
                break

    def decode_entry(self, ly: layout):
        x = 0
        start = self.seg2phys(ly.ptr)
        ly.entry_pts = []  # the actual entry pt raw data
        ly.eval_dl_segptrs = []  # just a literal list of ptrs
        while True:
            mark, ptr = self.upt(start + x, ">2L", 8)
            ly.entry_pts.append((mark, ptr))
            if mark == 4:
                return
            if ptr == 0:
                continue
            else:
                ly.eval_dl_segptrs.append(ptr)
            x += 8
            # shouldn't execute
            if x > 80:
                print("your while loop is broken in geo_bin.decode_entry")
                break

    # gonna use a module for this
    def decode_f3d_bin(self, layout):
        DLs = {}
        self.vertices = []
        starts = []
        layout.entry = layout.eval_dl_segptrs[
            :
        ]  # create shallow copy, use this for analyzing DL, while DL ptrs will be a dict including jumped to DLs
        for dl in layout.eval_dl_segptrs:
            start = self.seg2phys(dl)
            starts.append(start)
            f3d = self.decode_dl_bin(start, layout)
            self.DLs[dl] = f3d
            DLs[dl] = f3d
        layout.DLs = DLs
        return starts

    def eval_dl_segptr(self, num):
        if num >> 24 == 0xE:
            return None
        else:
            return num

    def decode_dl_bin(self, start, layout):
        DL = []
        x = 0
        while True:
            cmd = self.get_f3d_cmd(self.file[start + x : start + x + 8])
            x += 8
            if not cmd:
                continue
            name, args = self.split_args(cmd)
            if name == "gsSPEndDisplayList":
                break
            elif name == "gsSPDisplayList":
                ptr = self.eval_dl_segptr(int(args[0]))
                if ptr:
                    layout.eval_dl_segptrs.append(ptr)
                DL.append((name, args))
                continue
            # this LoD info will probably just stay destroyed for now
            elif name == "gsSPBranchLessZ":
                ptr = self.eval_dl_segptr(int(args[0]))
                if ptr:
                    layout.eval_dl_segptrs.append(ptr)
                DL.append((name, args))
                continue
            elif name == "gsSPBranchList":
                ptr = self.eval_dl_segptr(int(args[0]))
                if ptr:
                    layout.eval_dl_segptrs.append(ptr)
                DL.append((name, args))
                break
            DL.append((name, args))
        DL.append((name, args))
        return DL

    @lru_cache(maxsize=32)  # will save lots of time with repeats of tri calls
    def get_f3d_cmd(self, bin):
        return f3dex2.Ex2String(bin)

    def split_args(self, cmd):
        filt = "\(.*\)"
        a = re.search(filt, cmd)
        return cmd[: a.span()[0]], cmd[a.span()[0] + 1 : a.span()[1] - 1].split(",")

    def decode_vertices(self, start, end):
        self.vertices = Vertices(self.scale)
        for i in range(start, end, 16):
            v = self.upt(i, ">6h4B", 16)
            self.vertices._make(v)


# interim between bpy props and geo blocks, used for importing and exporting
class bpy_geo:
    def __init__(self, rt, scale):
        self.rt = rt
        self.scale = scale

    def write_bpy_gfx_from_geo(self, name, cls, tex_path, collection):
        # for now, do basic import, each layout is an object
        stack = [self.rt]
        self.LastMat = None
        # create dict of models so I can reuse model dat as needed (usually for blocks)
        Models = dict()
        for i, layout in enumerate(cls.layouts):
            if (layout.depth & 0xFF) == 0x12:
                break
            # mesh object
            if layout.ptr:
                prev = Models.get(layout.ptr)
                # model was already imported, reuse data block with new obj
                if prev:
                    mesh, self.LastMat = prev
                else:
                    ModelDat = F3d(lastmat=self.LastMat)
                    (layout.vertices, layout.Triangles) = ModelDat.get_data_from_dl(cls, layout)
                    self.LastMat = ModelDat.LastMat
                    mesh = bpy.data.meshes.new(f"{name} {layout.depth&0xFF} {i}")
                    mesh.from_pydata(layout.vertices, [], layout.Triangles)
                    # add model to dict
                    Models[layout.ptr] = (mesh, self.LastMat)
                obj = bpy.data.objects.new(f"{name} {layout.depth&0xFF} {i}", mesh)
                collection.objects.link(obj)
                # set KCS props of obj
                obj.KCS_mesh.MeshType = "Graphics"
                # apply dat
                ModelDat.apply_f3d_mesh_dat(obj, mesh, tex_path)
                # cleanup
                mesh.validate()
                mesh.update(calc_edges=True)
                if bpy.context.scene.KCS_scene.CleanUp:
                    # shade smooth
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.shade_smooth()
                    bpy.ops.object.mode_set(mode="EDIT")
                    bpy.ops.mesh.remove_doubles()
                    bpy.ops.object.mode_set(mode="OBJECT")
            # empty transform
            else:
                obj = make_empty(f"{name} {layout.depth} {i}", "PLAIN_AXES", collection)
                # set KCS props of obj
                obj.KCS_mesh.MeshType = "Graphics"
            # now that obj is created, parent and add transforms to it
            if (layout.depth & 0xFF) < len(stack) - 1:
                stack = stack[: (layout.depth & 0xFF) + 1]
            Parent(stack[-1], obj, 0)
            if (layout.depth & 0xFF) + 1 > len(stack) - 1:
                stack.append(obj)
            loc = layout.translation
            obj.location += Vector(self.vec3s_translate(loc)) / self.scale
            obj.scale = Vector([1 / a for a in layout.scale])
            apply_rotation_n64_to_bpy(obj)

    @staticmethod
    def vec3s_translate(vec3):
        return (vec3.x, -vec3.z, vec3.y)

    # create the fModel cls and populate it with layouts based on child objects
    def init_fModel_from_bpy(self):
        fModel = KCS_fModel(self.rt)
        depth = 0
        fModel.layouts = []
        # create duplicate objects to work on
        fModel.tempObj, fModel.allObjs = duplicateHierarchy(self.rt, None, True, 0)
        # get all child layouts first
        def loop_children(obj, fModel, depth):
            for child in obj.children:
                if self.is_kcs_gfx(child):
                    # each layout contains fMesh data, which holds triangle, and material info
                    fModel.layouts.append(self.create_layout(child, depth, fModel))
                    if child.children:
                        loop_children(child, fModel, depth + 1)

        loop_children(fModel.tempObj, fModel, 1)
        # add the root as a layout, though if there are no children, set the render mode to 14
        if not fModel.layouts:
            fModel.render_mode = 0x14  # list of DLs (entry point)
            fModel.layouts.append(faux_LY(self.export_f3d_from_obj(fModel.tempObj, fModel, Matrix.Identity)))
        else:
            fModel.render_mode = 0x17  # list of layouts
            fModel.layouts.insert(0, self.create_layout(fModel.tempObj, 0, fModel))
        return fModel

    def cleanup_fModel(self, fModel):
        cleanupDuplicatedObjects(fModel.allObjs)
        self.rt.select_set(True)
        bpy.context.view_layer.objects.active = fModel.rt

    # create a layout for an obj given its depth and the obj props
    def create_layout(self, obj, depth, fModel):
        # transform layout values to match N64 specs
        # only location needs to be transformed here, because rotation in the mesh data
        # will change the scale and rot
        loc = self.vec3s_translate(obj.location)
        rot = tuple(obj.rotation_euler)
        scale = tuple(obj.scale)
        finalTransform = Matrix.Diagonal(
            Vector((self.scale, self.scale, self.scale))
        ).to_4x4()  # just use the blender scale, other obj transforms can be
        ly = layout(
            0,
            depth,
            self.export_f3d_from_obj(obj, fModel, finalTransform),
            loc,
            rot,
            scale,
        )
        ly.name = obj.name  # for debug
        return ly

    # creates a list of KCS_fMesh objects with their bpy data processed and stored
    def export_f3d_from_obj(self, tempObj, fModel, transformMatrix):
        if tempObj.type == "MESH":
            try:
                infoDict = getInfoDict(tempObj)
                triConverterInfo = TriangleConverterInfo(tempObj, None, fModel.f3d, transformMatrix, infoDict)
                fMeshes = saveStaticModel(
                    triConverterInfo, fModel, tempObj, transformMatrix, fModel.name, False, False, None
                )
            except Exception as e:
                self.cleanup_fModel(fModel)
                raise Exception(str(e))
            return list(fMeshes.values())
        else:
            return 0

    # given an obj, eval if it is a kcs gfx export
    def is_kcs_gfx(self, obj):
        if obj.type == "MESH":
            return obj.KCS_mesh.MeshType == "Graphics"
        if obj.type == "EMPTY":
            return obj.KCS_obj.KCS_obj_type == "Graphics"


# export only classes


class EntryEnums(enum.Enum):
    Start = 0
    Continue = 1
    End = 4

    def __str__(self):
        return f"{self.value}"


# holds a list of DL ptrs
class EntryPoint(BinWrite):
    def __init__(self, fMeshes: list[FMesh]):
        self.fMeshes = fMeshes
        self.targets = []
        self.symbol_init()
        self.index = 0
        for fMesh in fMeshes:
            if fMesh.draw:
                # first member is enumerated 0, others are enumerated 1
                self.targets.append(
                    [EntryEnums.Continue if self.targets else EntryEnums.Start, self.add_target(fMesh.draw)]
                )
        if self.targets:
            self.targets.append([EntryEnums.End, 0])

    def to_c(self):
        CData = KCS_Cdata()
        self.write_arr(CData, f"EntryPoint_{self.index}", self.targets, self.format_arr)
        # add pointers
        self.ptr_obj(self, CData, f"&EntryPoint_{self.index}")
        return CData


# subclassed to manage pointers when writing
class KCS_GFXList(GfxList, BinWrite):
    def __init__(self, name, tag, DLFormat):
        super().__init__(name, tag, DLFormat)
        self.symbol_init()

    def to_c_static(self):
        # set symbol if obj is a ptr target
        self.ptr_obj(self, None, f"{self.name}")
        data = f"Gfx {self.name}[] = {{\n"
        for j, command in enumerate(self.commands):
            self.ptr_obj(command, None, f"&{self.name}[{j}]", multi=self)
            data += f"\t{command.to_c(True)},\n"
        data += "};\n\n"
        return data


# a data class that will hold various primitive geo classes and then write them out to files
# population of the classes will be done by bpy_geo or geo_bin
class KCS_fModel(FModel, BinWrite):
    def __init__(self, rt: bpy.types.Object, name="Kirby"):
        super().__init__("F3DEX2/LX2", False, name, DLFormat.Static, GfxMatWriteMethod.WriteAll, inline=True)
        self.rt = rt
        self.gfxFormatter = GfxFormatter(None, 2)
        self.ptrManager = PointerManager()

    # overrides of base class
    def addMesh(self, name, namePrefix, drawLayer, isSkinned, contextObj):
        meshName = getFMeshName(name, namePrefix, drawLayer, isSkinned)
        checkUniqueBoneNames(self, meshName, name)
        self.meshes[meshName] = KCS_fMesh(meshName, self.DLFormat, inline=self.inline)
        self.onAddMesh(self.meshes[meshName], contextObj)
        return self.meshes[meshName]

    def addMaterial(self, materialName: str):
        return KCS_fMaterial(materialName, self.DLFormat)

    # KCS specific methods
    # process the layouts after the KCS_fMesh objects have been added, with their tri and mat info
    def process_layouts(self):
        self.symbol_init()
        self.main_header = StructContainer(
            (
                self.add_target(self.layouts[0]),  # *layout[]
                0,  # *tex_scroll[]
                self.render_mode,
                0,  # *img_refs[]
                0,  # *vtx_refs[]
                0,  # Num_Anims
                0,  # *Anims[]
                len(self.layouts),  # num layouts
            )
        )
        for ly in self.layouts:
            if not ly.ptr:
                continue
            ly.entry = EntryPoint(ly.ptr)
            ly.ptr = ly.add_target(ly.entry)

    # output methods
    def save_binary(self, file: BinaryIO):
        print(file)

    def to_c(self, file: TextIO):
        structData = KCS_Cdata()
        vertexData = KCS_Cdata()
        graphicsData = KCS_Cdata()
        layoutData = KCS_Cdata()
        entryPointData = KCS_Cdata()
        # img ref data is inside each individual fMesh
        imgRefData = KCS_Cdata()
        imgRefs = []
        for ly in self.layouts:
            if ly.ptr:
                entryPoint = ly.entry
                for fMesh in entryPoint.fMeshes:
                    GfxDat, VtxDat = fMesh.to_c(self.f3d, self.gfxFormatter)
                    graphicsData.append(GfxDat)
                    vertexData.append(VtxDat)
                    imgRefs.extend(fMesh.img_refs)

                entryPointData.append(entryPoint.to_c())
            layoutData.append(ly.to_c())
        self.write_dict_struct(self.main_header, Geo_Header, structData, "", "Geo_Header Header")
        self.write_arr(imgRefData, f"void *img_refs", imgRefs, self.format_arr)
        # combine cDatas into one
        cData = (vertexData, graphicsData, imgRefData, entryPointData, layoutData)
        for data in cData:
            structData.append(data)
        # replace plcaeholder pointers in file with real symbols
        self.resolve_ptrs_c(structData)
        # write all out to file
        file.write(structData.source)


# subclassed to manage pointers when writing, and for dynamic DLs with scrolls
class KCS_fMesh(FMesh, BinWrite):
    def __init__(self, name, dlFormat: DLFormat, inline: bool = False):
        self.name = name
        self.inline = inline
        # GfxList
        self.draw = KCS_GFXList(name, GfxListTag.Draw, dlFormat)
        # list of FTriGroup
        self.triangleGroups: list["FTriGroup"] = []
        # VtxList
        self.cullVertexList = None
        # dict of (override Material, specified Material to override,
        # overrideType, draw layer) : GfxList
        self.drawMatOverrides = {}
        self.DLFormat = dlFormat

        # Used to avoid consecutive calls to the same material if unnecessary
        self.currentFMaterial = None

        # Props used for KCS specifically
        self.img_refs = []
        self.symbol_init()

    # after each triGroup is added to fMesh.draw, add the DPSetTextureImage as pointer targets, and add the pointer objects to img refs
    def onTriGroupBleedEnd(self, f3d: F3D, triGroup: FTriGroup, lastMat: FMaterial, bleed: BleedGfx):
        for tile, texGfx in enumerate(bleed.bled_tex):
            set_tex = (c for c in texGfx.commands if type(c) == DPSetTextureImage)
            for set_img in set_tex:
                self.img_refs.append(self.add_target(set_img, multi=self.draw))


# subclassed to manage pointers when writing, and for dynamic DLs with scrolls
class KCS_fMaterial(FMaterial):
    def __init__(self, name: str, dlFormat: DLFormat):
        super().__init__(name, dlFormat, inline=True)
        self.name = name


# ------------------------------------------------------------------------
#    Exorter Functions
# ------------------------------------------------------------------------


@time_func
def export_geo_bin(name: str, obj: bpy.types.Object, context: bpy.types.Context):
    scale = context.scene.KCS_scene.Scale
    blend_geo = bpy_geo(obj, scale)
    # create writer class using blender data, with layouts that have fMesh data
    fModel = blend_geo.init_fModel_from_bpy()
    blend_geo.cleanup_fModel(fModel)  # processing of bpy data is done
    fModel.process_layouts()
    with open(name, "w") as file:
        fModel.save_binary(file)
        fModel.to_c(file)


@time_func
def export_geo_c(name: str, obj: bpy.types.Object, context: bpy.types.Context):
    scale = context.scene.KCS_scene.Scale
    blend_geo = bpy_geo(obj, scale)
    # create writer class using blender data, with layouts that have fMesh data
    fModel = blend_geo.init_fModel_from_bpy()
    blend_geo.cleanup_fModel(fModel)  # processing of bpy data is done
    fModel.process_layouts()
    with open(name, "w") as file:
        fModel.to_c(file)


# ------------------------------------------------------------------------
#    Importer
# ------------------------------------------------------------------------


@time_func
def import_geo_bin(bin_file: BinaryIO, context: bpy.types.Context, name: str, path: Path):
    Geo = bin_file
    Geo = open(Geo, "rb")
    collection = context.scene.collection
    rt = make_empty(name, "PLAIN_AXES", collection)
    rt.KCS_obj.KCS_obj_type = "Graphics"
    Geo_Block = geo_bin(Geo.read(), context.scene.KCS_scene.Scale)
    write = bpy_geo(rt, context.scene.KCS_scene.Scale)
    write.write_bpy_gfx_from_geo("geo", Geo_Block, path, collection)