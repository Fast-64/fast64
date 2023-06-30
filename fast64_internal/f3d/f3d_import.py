# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------

import bpy

import os, struct, math

from functools import lru_cache
from pathlib import Path
from mathutils import Vector, Euler, Matrix
from collections import namedtuple
from dataclasses import dataclass
from copy import deepcopy
from re import findall
from numbers import Number
from collections.abc import Sequence

from ..f3d.f3d_material import (
    F3DMaterialProperty,
    RDPSettings,
    TextureProperty
)

from ..utility import hexOrDecInt
from ..utility_importer import *

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

    # calc the hash for an f3d mat and see if its equal to this mats hash
    def mat_hash_f3d(self, f3d: F3DMaterialProperty):
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
            f3d.rdp_settings.rendermode_preset_cycle_1,
            f3d.rdp_settings.rendermode_preset_cycle_2,
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

    def mat_hash(self, mat: bpy.types.Material):
        return False

    def convert_color(self, color: Sequence[Number]):
        return [int(a) / 255 for a in color]

    def load_texture(self, ForceNewTex: bool, path: Path, tex: Texture):
        png = path / f"bank_{tex.Timg[0]}" / f"{tex.Timg[1]}"
        png = (*png.glob("*.png"),)
        if png:
            i = bpy.data.images.get(str(png[0]))
            if not i or ForceNewTex:
                return bpy.data.images.load(filepath=str(png[0]))
            else:
                return i

    def apply_PBSDF_Mat(self, mat: bpy.types.Material, tex_path: Path, tex: Texture):
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        pbsdf = nodes.get("Principled BSDF")
        if not pbsdf:
            return
        tex_node = nodes.new("ShaderNodeTexImage")
        links.new(pbsdf.inputs[0], tex_node.outputs[0])  # base color
        image = self.LoadTexture(0, tex_path, tex)
        if image:
            tex_node.image = image

    def apply_material_settings(self, mat: bpy.types.Material, tex_path: Path):
        f3d = mat.f3d_mat

        self.set_register_settings(mat, f3d)
        self.set_textures(f3d)
        
        with bpy.context.temp_override(material=mat):
            bpy.ops.material.update_f3d_nodes()

    def set_register_settings(self, mat: bpy.types.Material, f3d: F3DMaterialProperty):
        self.set_fog(f3d)
        self.set_color_registers(f3d)
        self.set_geo_mode(f3d.rdp_settings, mat)
        self.set_combiner(f3d)
        self.set_render_mode(f3d)
    
    def set_textures(self, f3d: F3DMaterialProperty, tex_path: Path):
        self.set_tex_scale(f3d)
        if self.tex0 and self.set_tex:
            self.set_tex_settings(f3d.tex0, self.load_texture(0, tex_path, self.tex0), self.tiles[0], self.tex0.Timg)
        if self.tex1 and self.set_tex:
            self.set_tex_settings(f3d.tex1, self.load_texture(0, tex_path, self.tex1), self.tiles[1], self.tex1.Timg)
            
    def set_fog(self, f3d: F3DMaterialProperty):
        if hasattr(self, "fog_position"):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_position[0] = eval(self.fog_pos[0])
            f3d.fog_position[1] = eval(self.fog_pos[1])
        if hasattr(self, "fog_color"):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_color = self.convert_color(self.fog_color)

    def set_color_registers(self, f3d: F3DMaterialProperty):
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

    def set_tex_scale(self, f3d: F3DMaterialProperty):
        if hasattr(self, "set_tex"):
            # not exactly the same but gets the point across maybe?
            f3d.tex0.tex_set = self.set_tex
            f3d.tex1.tex_set = self.set_tex
            # tex scale gets set to 0 when textures are disabled which is automatically done
            # often to save processing power between mats or something, or just adhoc bhv
            # though in fast64, we don't want to ever set it to zero
            if f3d.rdp_settings.g_tex_gen or any([a < 1 and a > 0 for a in self.tex_scale]):
                f3d.scale_autoprop = False
                f3d.tex_scale = self.tex_scale

    def set_tex_settings(self, tex_prop: TextureProperty, image: bpy.types.Image, tile: Tile, tex_img: Union[Sequence, str]):
        tex_prop.tex_reference = str(tex_img)  # setting prop for hash purposes
        tex_prop.tex_set = True
        tex_prop.tex = image
        tex_prop.tex_format = self.eval_texture_format(tile)
        Sflags = self.eval_tile_flags(tile.Sflags)
        for f in Sflags:
            setattr(tex_prop.S, f, True)
        Tflags = self.eval_tile_flags(tile.Tflags)
        for f in Sflags:
            setattr(tex_prop.T, f, True)
        tex_prop.S.low = tile.Slow
        tex_prop.T.low = tile.Tlow
        tex_prop.S.high = tile.Shigh
        tex_prop.T.high = tile.Thigh
        tex_prop.S.mask = tile.SMask
        tex_prop.T.mask = tile.TMask

    # rework with combinatoric render mode draft PR
    def set_render_mode(self, f3d: F3DMaterialProperty):
        rdp = f3d.rdp_settings
        if self.TwoCycle:
            rdp.g_mdsft_cycletype = "G_CYC_2CYCLE"
        else:
            rdp.g_mdsft_cycletype = "G_CYC_1CYCLE"
        if hasattr(self, "RenderMode"):
            rdp.set_rendermode = True
            # if the enum isn't there, then just print an error for now
            try:
                rdp.rendermode_preset_cycle_1 = self.RenderMode[0]
                rdp.rendermode_preset_cycle_2 = self.RenderMode[1]
                # print(f"set render modes with render mode {self.RenderMode}")
            except:
                print(f"could not set render modes with render mode {self.RenderMode}")

    def set_geo_mode(self, rdp: RDPSettings, mat: bpy.types.Material):
        # texture gen has a different name than gbi
        for a in self.GeoSet:
            setattr(rdp, a.replace("G_TEXTURE_GEN", "G_TEX_GEN").lower().strip(), True)
        for a in self.GeoClear:
            setattr(rdp, a.replace("G_TEXTURE_GEN", "G_TEX_GEN").lower().strip(), False)

    # Very lazy for now
    def set_combiner(self, f3d: F3DMaterialProperty):
        f3d.presetName = "Custom"
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

    def eval_tile_flags(self, flags: str):
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

    def eval_texture_format(self, tex: Texture):
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
class DL(DataParser):
    # the min needed for this class to work for importing
    def __init__(self, lastmat=None):
        self.Vtx = {}
        self.Gfx = {}
        self.Light_t = {}
        self.Ambient_t = {}
        self.Lights1 = {}
        self.Textures = {}
        if not lastmat:
            self.LastMat = Mat()
            self.LastMat.name = 0
        else:
            self.LastMat = lastmat
        super().__init__()

    def gsSPEndDisplayList(self, macro: Macro):
        return self.break_parse

    def gsSPBranchList(self, macro: Macro):
        NewDL = self.Gfx.get(branched_dl := macro.args[0])
        if not NewDL:
            raise Exception(
                "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
                    NewDL, self.scene.LevelImp.Level, self.scene.LevelImp.Prefix
                )
            )
        self.parse_stream(NewDL, branched_dl)
        return self.break_parse

    def gsSPDisplayList(self, macro: Macro):
        NewDL = self.Gfx.get(branched_dl := macro.args[0])
        if not NewDL:
            raise Exception(
                "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
                    NewDL, self.scene.LevelImp.Level, self.scene.LevelImp.Prefix
                )
            )
        self.parse_stream(NewDL, branched_dl)
        return self.continue_parse

    def gsSPEndDisplayList(self, macro: Macro):
        return self.break_parse

    def gsSPVertex(self, macro: Macro):
        # vertex references commonly use pointer arithmatic. I will deal with that case here, but not for other things unless it somehow becomes a problem later
        if "+" in macro.args[0]:
            ref, offset = macro.args[0].split("+")
            offset = hexOrDecInt(offset)
        else:
            ref = macro.args[0]
            offset = 0
        VB = self.Vtx.get(ref)
        if not VB:
            raise Exception(
                "Could not find VB {} in levels/{}/{}leveldata.inc.c".format(
                    ref, self.scene.LevelImp.Level, self.scene.LevelImp.Prefix
                )
            )
        vertex_load_start = hexOrDecInt(macro.args[2])
        vertex_load_length = hexOrDecInt(macro.args[1])
        Verts = VB[
            offset : offset + vertex_load_length
        ]  # If you use array indexing here then you deserve to have this not work
        Verts = [self.parse_vert(v) for v in Verts]
        for k, i in enumerate(range(vertex_load_start, vertex_load_length, 1)):
            self.VertBuff[i] = [Verts[k], vertex_load_start]
        # These are all independent data blocks in blender
        self.Verts.extend([v[0] for v in Verts])
        self.UVs.extend([v[1] for v in Verts])
        self.VCs.extend([v[2] for v in Verts])
        self.LastLoad = vertex_load_length
        return self.continue_parse

    def gsSP2Triangles(self, macro: Macro):
        self.make_new_material()
        args = [hexOrDecInt(a) for a in macro.args]
        Tri1 = self.parse_tri(args[:3])
        Tri2 = self.parse_tri(args[4:7])
        self.Tris.append(Tri1)
        self.Tris.append(Tri2)
        return self.continue_parse

    def gsSP1Triangle(self, macro: Macro):
        self.make_new_material()
        args = [hexOrDecInt(a) for a in macro.args]
        Tri = self.parse_tri(args[:3])
        self.Tris.append(Tri)
        return self.continue_parse

    # materials
    # Mats will be placed sequentially. The first item of the list is the triangle number
    # The second is the material class
    def gsDPSetRenderMode(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.RenderMode = [a.strip() for a in macro.args]
        return self.continue_parse

    # not finished yet
    def gsSPLight(self, macro: Macro):
        return self.continue_parse

    def gsSPLightColor(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights0(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights1(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights2(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights3(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights4(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights5(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights6(self, macro: Macro):
        return self.continue_parse

    def gsSPSetLights7(self, macro: Macro):
        return self.continue_parse

    def gsDPSetDepthSource(self, macro: Macro):
        return self.continue_parse

    def gsSPFogFactor(self, macro: Macro):
        return self.continue_parse

    def gsDPSetFogColor(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.fog_color = macro.args
        return self.continue_parse

    def gsSPFogPosition(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.fog_pos = macro.args
        return self.continue_parse

    def gsSPLightColor(self, macro: Macro):
        self.NewMat = 1
        if not hasattr(self.LastMat, "light_col"):
            self.LastMat.light_col = {}
        num = re.search("_\d", macro.args[0]).group()[1]
        self.LastMat.light_col[num] = macro.args[-1]
        return self.continue_parse

    def gsDPSetPrimColor(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.prim_color = macro.args
        return self.continue_parse

    def gsDPSetEnvColor(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.env_color = macro.args
        return self.continue_parse

    # multiple geo modes can happen in a row that contradict each other
    # this is mostly due to culling wanting diff geo modes than drawing
    # but sometimes using the same vertices
    def gsSPClearGeometryMode(self, macro: Macro):
        self.NewMat = 1
        args = [a.strip() for a in macro.args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoSet:
                self.LastMat.GeoSet.remove(a)
        self.LastMat.GeoClear.extend(args)
        return self.continue_parse

    def gsSPSetGeometryMode(self, macro: Macro):
        self.NewMat = 1
        args = [a.strip() for a in macro.args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoClear:
                self.LastMat.GeoClear.remove(a)
        self.LastMat.GeoSet.extend(args)
        return self.continue_parse

    def gsSPGeometryMode(self, macro: Macro):
        self.NewMat = 1
        argsC = [a.strip() for a in macro.args[0].split("|")]
        argsS = [a.strip() for a in macro.args[1].split("|")]
        for a in argsC:
            if a in self.LastMat.GeoSet:
                self.LastMat.GeoSet.remove(a)
        for a in argsS:
            if a in self.LastMat.GeoClear:
                self.LastMat.GeoClear.remove(a)
        self.LastMat.GeoClear.extend(argsC)
        self.LastMat.GeoSet.extend(argsS)
        return self.continue_parse

    def gsDPSetCycleType(self, macro: Macro):
        if "G_CYC_1CYCLE" in macro.args[0]:
            self.LastMat.TwoCycle = False
        if "G_CYC_2CYCLE" in macro.args[0]:
            self.LastMat.TwoCycle = True
        return self.continue_parse

    def gsDPSetCombineMode(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.Combiner = self.eval_set_combine_macro(macro.args)
        return self.continue_parse

    def gsDPSetCombineLERP(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.Combiner = macro.args
        return self.continue_parse

    # root tile, scale and set tex
    def gsSPTexture(self, macro: Macro):
        self.NewMat = 1
        macros = {
            "G_ON": 2,
            "G_OFF": 0,
        }
        set_tex = macros.get(macro.args[-1])
        if set_tex == None:
            set_tex = hexOrDecInt(macro.args[-1])
        self.LastMat.set_tex = set_tex == 2
        self.LastMat.tex_scale = [
            ((0x10000 * (hexOrDecInt(a) < 0)) + hexOrDecInt(a)) / 0xFFFF for a in macro.args[0:2]
        ]  # signed half to unsigned half
        self.LastMat.tile_root = self.eval_tile_enum(macro.args[-2])  # I don't think I'll actually use this
        return self.continue_parse

    # last tex is a palette
    def gsDPLoadTLUT(self, macro: Macro):
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
        return self.continue_parse

    # tells us what tile the last loaded mat goes into
    def gsDPLoadBlock(self, macro: Macro):
        try:
            tex = self.LastMat.loadtex
            # these values aren't necessary when the texture is already in png format
            # tex.dxt = hexOrDecInt(args[4])
            # tex.texels = hexOrDecInt(args[3])
            tile = self.eval_tile_enum(macro.args[0])
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
        return self.continue_parse

    def gsDPSetTextureImage(self, macro: Macro):
        self.NewMat = 1
        Timg = macro.args[3]
        Fmt = macro.args[1]
        Siz = macro.args[2]
        loadtex = Texture(Timg, Fmt, Siz)
        self.LastMat.loadtex = loadtex
        return self.continue_parse

    def gsDPSetTileSize(self, macro: Macro):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.eval_tile_enum(macro.args[0])]
        tile.Slow = self.eval_image_frac(macro.args[1])
        tile.Tlow = self.eval_image_frac(macro.args[2])
        tile.Shigh = self.eval_image_frac(macro.args[3])
        tile.Thigh = self.eval_image_frac(macro.args[4])
        return self.continue_parse

    def gsDPSetTile(self, macro: Macro):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.eval_tile_enum(macro.args[4].strip())]
        tile.Fmt = macro.args[0].strip()
        tile.Siz = macro.args[1].strip()
        tile.Tflags = macro.args[6].strip()
        tile.TMask = self.eval_tile_enum(macro.args[7])
        tile.TShift = self.eval_tile_enum(macro.args[8])
        tile.Sflags = macro.args[9].strip()
        tile.SMask = self.eval_tile_enum(macro.args[10])
        tile.SShift = self.eval_tile_enum(macro.args[11])
        return self.continue_parse

    # syncs need no processing
    def gsDPPipeSync(self, macro: Macro):
        return self.continue_parse

    def gsDPLoadSync(self, macro: Macro):
        return self.continue_parse

    def gsDPTileSync(self, macro: Macro):
        return self.continue_parse

    def gsDPFullSync(self, macro: Macro):
        return self.continue_parse

    def gsDPNoOp(self, macro: Macro):
        return self.continue_parse

    def make_new_material(self):
        if self.NewMat:
            self.NewMat = 0
            self.Mats.append([len(self.Tris) - 1, self.LastMat])
            self.LastMat = deepcopy(self.LastMat)  # for safety
            self.LastMat.name = self.num + 1
            self.num += 1

    def parse_tri(self, Tri: Sequence[int]):
        return [self.VertBuff[a] for a in Tri]

    def eval_image_frac(self, arg: Union[str, Number]):
        if type(arg) == int:
            return arg
        arg2 = arg.replace("G_TEXTURE_IMAGE_FRAC", "2")
        return eval(arg2)

    def eval_tile_enum(self, arg: Union[str, Number]):
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

    def eval_set_combine_macro(self, arg: str):
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
            arg[0], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"]
        ) + GBI_CC_Macros.get(arg[1], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"])
