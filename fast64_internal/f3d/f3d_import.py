# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------

import bpy

import os, struct, math, re

from functools import lru_cache
from pathlib import Path
from mathutils import Vector, Euler, Matrix
from collections import namedtuple
from dataclasses import dataclass
from copy import deepcopy

from ..utility import hexOrDecInt

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------


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
        if not pbsdf:
            return
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
        # add tex scroll objects, make this a callback
        if self.tx_scr:
            scr = self.tx_scr
            mat_scr = mat.KCS_tx_scroll
            if hasattr(scr, "textures"):
                [mat_scr.add_texture(t) for t in scr.textures]
            if hasattr(scr, "palettes"):
                [mat_scr.add_palette(t) for t in scr.palettes]
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
            rdp.render_mode.rendermode_preset_cycle_1 = self.RenderMode[0]
            rdp.render_mode.rendermode_preset_cycle_2 = self.RenderMode[1]
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

    # Vertices are not currently handled in the base class

    # Triangles
    def gsSP2Triangles(self, args):
        self.make_new_mat()
        args = [hexOrDecInt(a) for a in args]
        Tri1 = self.parse_tri(args[:3])
        Tri2 = self.parse_tri(args[4:7])
        self.Tris.append(Tri1)
        self.Tris.append(Tri2)

    def gsSP1Triangle(self, args):
        self.make_new_mat()
        args = [hexOrDecInt(a) for a in args]
        Tri = self.parse_tri(args[:3])
        self.Tris.append(Tri)

    # materials
    # Mats will be placed sequentially. The first item of the list is the triangle number
    # The second is the material class
    def gsDPSetRenderMode(self, args):
        self.NewMat = 1
        self.LastMat.RenderMode = [a.strip() for a in args]

    def gsDPSetFogColor(self, args):
        self.NewMat = 1
        self.LastMat.fog_color = args

    def gsSPFogPosition(self, args):
        self.NewMat = 1
        self.LastMat.fog_pos = args

    def gsSPLightColor(self, args):
        self.NewMat = 1
        if not hasattr(self.LastMat, "light_col"):
            self.LastMat.light_col = {}
        num = re.search("_\d", args[0]).group()[1]
        self.LastMat.light_col[num] = args[-1]

    def gsDPSetPrimColor(self, args):
        self.NewMat = 1
        self.LastMat.prim_color = args

    def gsDPSetEnvColor(self, args):
        self.NewMat = 1
        self.LastMat.env_color = args

    # multiple geo modes can happen in a row that contradict each other
    # this is mostly due to culling wanting diff geo modes than drawing
    # but sometimes using the same vertices
    def gsSPClearGeometryMode(self, args):
        self.NewMat = 1
        args = [a.strip() for a in args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoSet:
                self.LastMat.GeoSet.remove(a)
        self.LastMat.GeoClear.extend(args)

    def gsSPSetGeometryMode(self, args):
        self.NewMat = 1
        args = [a.strip() for a in args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoClear:
                self.LastMat.GeoClear.remove(a)
        self.LastMat.GeoSet.extend(args)

    def gsSPGeometryMode(self, args):
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

    def gsDPSetCycleType(self, args):
        if "G_CYC_1CYCLE" in args[0]:
            self.LastMat.TwoCycle = False
        if "G_CYC_2CYCLE" in args[0]:
            self.LastMat.TwoCycle = True

    def gsDPSetCombineMode(self, args):
        self.NewMat = 1
        self.LastMat.Combiner = self.EvalCombiner(args)

    def gsDPSetCombineLERP(self, args):
        self.NewMat = 1
        self.LastMat.Combiner = [a.strip() for a in args]

    # root tile, scale and set tex
    def gsSPTexture(self, args):
        self.NewMat = 1
        macros = {
            "G_ON": 2,
            "G_OFF": 0,
        }
        set_tex = macros.get(args[-1].strip())
        if set_tex == None:
            set_tex = hexOrDecInt(args[-1].strip())
        self.LastMat.set_tex = set_tex == 2
        self.LastMat.tex_scale = [
            ((0x10000 * (hexOrDecInt(a) < 0)) + hexOrDecInt(a)) / 0xFFFF for a in args[0:2]
        ]  # signed half to unsigned half
        self.LastMat.tile_root = self.eval_tile_macros(args[-2].strip())  # I don't think I'll actually use this

    # last tex is a palette
    def gsDPLoadTLUT(self, args):
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
    def gsDPLoadBlock(self, args):
        try:
            tex = self.LastMat.loadtex
            # these values aren't necessary when the texture is already in png format
            # tex.dxt = hexOrDecInt(args[4])
            # tex.texels = hexOrDecInt(args[3])
            tile = self.eval_tile_macros(args[0])
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

    def gsDPSetTextureImage(self, args):
        self.NewMat = 1
        Timg = args[3].strip()
        Fmt = args[1].strip()
        Siz = args[2].strip()
        loadtex = Texture(Timg, Fmt, Siz)
        self.LastMat.loadtex = loadtex

    def gsDPSetTileSize(self, args):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.eval_tile_macros(args[0])]
        tile.Slow = self.eval_tile_im_frac(args[1].strip())
        tile.Tlow = self.eval_tile_im_frac(args[2].strip())
        tile.Shigh = self.eval_tile_im_frac(args[3].strip())
        tile.Thigh = self.eval_tile_im_frac(args[4].strip())

    def gsDPSetTile(self, args):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.eval_tile_macros(args[4])]
        tile.Fmt = args[0].strip()
        tile.Siz = args[1].strip()
        tile.Tflags = args[6].strip()
        tile.TMask = self.eval_tile_macros(args[7].strip())
        tile.TShift = self.eval_tile_macros(args[8].strip())
        tile.Sflags = args[9].strip()
        tile.SMask = self.eval_tile_macros(args[10].strip())
        tile.SShift = self.eval_tile_macros(args[11].strip())

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

    def eval_tile_macros(self, arg):
        # only 0 and 7 have enums, other stuff just uses int (afaik)
        Tiles = {
            "G_TX_LOADTILE": 7,
            "G_TX_RENDERTILE": 0,
            "G_TX_NOMASK": 0,
            "G_TX_NOLOD": 0,
        }
        t = Tiles.get(arg)
        if t == None:
            t = hexOrDecInt(arg)
        return t

    def EvalCombiner(self, arg):
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
