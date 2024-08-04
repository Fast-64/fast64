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

from ..f3d.f3d_material import F3DMaterialProperty, RDPSettings, TextureProperty
from ..f3d.f3d_gbi import get_F3D_GBI

from ..utility import hexOrDecInt
from ..utility_importer import *

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------

# will format light struct data passed
class Lights1:
    def __init__(self, name: str, data_str: str):
        self.name = name
        data = [eval(dat.strip()) for dat in data_str.split(",")]
        self.ambient = [*data[0:3], 0xFF]
        self.diffuse = [*data[3:6], 0xFF]
        self.direction = data[9:12]


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
        self.tmem = 0
        
    def eval_texture_format(self):
        # make better
        return f"{self.Fmt.replace('G_IM_FMT_','')}{self.Siz.replace('G_IM_SIZ_','').replace('b','')}"


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
        
    def eval_texture_format(self):
        return f"{self.Fmt.replace('G_IM_FMT_','')}{self.Siz.replace('G_IM_SIZ_','').replace('b','')}"


# This is a data storage class and mat to f3dmat converting class
# used when importing for kirby
class Mat:
    def __init__(self):
        self.GeoSet = []
        self.GeoClear = []
        self.tiles = [Tile() for a in range(8)]
        # dict[mem_offset] = tex
        self.tmem = dict()
        self.base_tile = 0
        self.tex0 = None
        self.tex1 = None
        self.other_mode = dict()
        self.num_lights = 1
        self.light_col = {}
        self.ambient_light = tuple()

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
        links.new(pbsdf.inputs[21], tex_node.outputs[1])  # alpha color
        image = self.LoadTexture(0, tex_path, tex)
        if image:
            tex_node.image = image

    def apply_material_settings(self, mat: bpy.types.Material, tex_path: Path):
        f3d = mat.f3d_mat
        
        self.set_texture_tile_mapping()
        self.set_register_settings(mat, f3d)
        self.set_textures(f3d)

        with bpy.context.temp_override(material=mat):
            bpy.ops.material.update_f3d_nodes()

    def set_register_settings(self, mat: bpy.types.Material, f3d: F3DMaterialProperty):
        self.set_fog(f3d)
        self.set_color_registers(f3d)
        self.set_geo_mode(f3d.rdp_settings, mat)
        self.set_combiner(f3d)
        self.set_rendermode(f3d)
        self.set_othermode(f3d)

    # map tiles to locations in tmem
    # this ignores the application of LoDs for magnification
    # since fast64 uses tile0 as tex0 always, so to get expected
    # results we need to start tex0 at the proper base tile
    def set_texture_tile_mapping(self):
        for index, tile in enumerate(self.tiles):
            tex_index = index - self.base_tile
            if tex_index < 0:
                continue
            tex = self.tmem.get(tile.tmem, None)
            setattr(self, f"tex{tex_index}", tex)
    
    def set_textures(self, f3d: F3DMaterialProperty, tex_path: Path):
        self.set_tex_scale(f3d)
        if self.tex0 and self.set_tex:
            self.set_tex_settings(f3d.tex0, self.load_texture(0, tex_path, self.tex0), self.tiles[0 + self.base_tile], self.tex0.Timg)
        if self.tex1 and self.set_tex:
            self.set_tex_settings(f3d.tex1, self.load_texture(0, tex_path, self.tex1), self.tiles[1 + self.base_tile], self.tex1.Timg)

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
        if self.ambient_light:
            f3d.set_ambient_from_light = False
            f3d.ambient_light_color = self.convert_color(self.ambient_light)
        if self.light_col:
            # this is a dict but I'll only use the first color for now
            f3d.set_lights = True
            if self.light_col.get(1):
                f3d.default_light_color = self.convert_color(self.light_col[1])
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

    def set_tex_settings(
        self, tex_prop: TextureProperty, image: bpy.types.Image, tile: Tile, tex_img: Union[Sequence, str]
    ):
        tex_prop.tex_reference = str(tex_img)  # setting prop for hash purposes
        tex_prop.tex_set = True
        tex_prop.tex = image
        tex_prop.tex_format = tile.eval_texture_format()
        s_flags = self.eval_tile_flags(tile.Sflags)
        tex_prop.S.mirror = "mirror" in s_flags
        tex_prop.S.clamp = "clamp" in s_flags
        t_flags = self.eval_tile_flags(tile.Tflags)
        tex_prop.T.mirror = "mirror" in t_flags
        tex_prop.T.clamp = "clamp" in t_flags
        tex_prop.S.low = tile.Slow
        tex_prop.T.low = tile.Tlow
        tex_prop.S.high = tile.Shigh
        tex_prop.T.high = tile.Thigh
        tex_prop.S.mask = tile.SMask
        tex_prop.T.mask = tile.TMask
        
    # rework with new render mode stuffs
    def set_rendermode(self, f3d: F3DMaterialProperty):
        rdp = f3d.rdp_settings
        if hasattr(self, "RenderMode"):
            rdp.set_rendermode = True
            # if the enum isn't there, then just print an error for now
            try:
                rdp.rendermode_preset_cycle_1 = self.RenderMode[0]
                rdp.rendermode_preset_cycle_2 = self.RenderMode[1]
                # print(f"set render modes with render mode {self.RenderMode}")
            except:
                print(f"could not set render modes with render mode {self.RenderMode}")
    
    def set_othermode(self, f3d: F3DMaterialProperty):
        rdp = f3d.rdp_settings
        for prop, val in self.other_mode.items():
            setattr(rdp, prop, val)
            # add in exception handling here

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
        self.NewMat = 1
        self.f3d_gbi = get_F3D_GBI()
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
                    NewDL, self.scene.level_import.Level, self.scene.level_import.Prefix
                )
            )
        self.reset_parser(branched_dl)
        self.parse_stream(NewDL, branched_dl)
        return self.break_parse

    def gsSPDisplayList(self, macro: Macro):
        NewDL = self.Gfx.get(branched_dl := macro.args[0])
        if not NewDL:
            raise Exception(
                "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
                    NewDL, self.scene.level_import.Level, self.scene.level_import.Prefix
                )
            )
        self.reset_parser(branched_dl)
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
        VB = self.Vtx.get(ref.strip())
        if not VB:
            raise Exception(
                "Could not find VB {} in levels/{}/{}leveldata.inc.c".format(
                    ref, self.scene.level_import.Level, self.scene.level_import.Prefix
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

    def gsSPModifyVertex(self, macro: Macro):
        vtx = self.VertBuff[hexOrDecInt(macro.args[0])]
        where = self.eval_modify_vtx(macro.args[1])
        val = hexOrDecInt(macro.args[2])
        # if it is None, something weird, or screenspace I won't edit it
        if where == "ST":
            uv = (val >> 16)& 0xFFFF, val & 0xFFFF
            self.Verts.append(self.Verts[vtx])
            self.UVs.append(uv)
            self.VCs.append(self.VCs[vtx])
            self.VertBuff[hexOrDecInt(macro.args[0])] = len(self.Verts)
        elif where == "RGBA":
            vertex_col = [(val >> 8*i)&0xFF for i in range(4)].reverse()
            self.Verts.append(self.Verts[vtx])
            self.UVs.append(self.UVs[vtx])
            self.VCs.append(vertex_col)
            self.VertBuff[hexOrDecInt(macro.args[0])] = len(self.Verts)
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

    # The highest numbered light is always the ambient light
    def gsSPLight(self, macro: Macro):
        self.NewMat = 1
        light = re.search("&.+\.", macro.args[0]).group()[1:-1]
        light = Lights1(light, self.Lights1.get(light)[0])
        if ".a" in macro.args[0]:
            self.LastMat.ambient_light = light.ambient
        else:
            num = re.search("_\d", macro.args[0]).group()[1]
            num = int(num) if num else 1
            self.LastMat.light_col[num] = light.diffuse
        return self.continue_parse

    # numlights0 still gives one ambient and diffuse light
    def gsSPNumLights(self, macro: Macro):
        self.NewMat = 1
        num = re.search("_\d", macro.args[0]).group()[1]
        num = int(num) if num else 1
        self.LastMat.num_lights = num
        return self.continue_parse

    def gsSPLightColor(self, macro: Macro):
        self.NewMat = 1
        num = re.search("_\d", macro.args[0]).group()[1]
        num = int(num) if num else 1
        self.LastMat.light_col[num] = eval(macro.args[-1]).to_bytes(4, "big")
        return self.continue_parse
    
    # not finished yet
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

    # some independent other mode settings
    def gsDPSetTexturePersp(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_textpersp"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetDepthSource(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_zsrcsel"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetColorDither(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_rgb_dither"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetAlphaDither(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_alpha_dither"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetCombineKey(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_combkey"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetTextureConvert(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_textconv"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetTextureFilter(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_text_filt"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetTextureLOD(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_textlod"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetTextureDetail(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_textdetail"] = macro.args[0]
        return self.continue_parse

    def gsDPSetCycleType(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_cycletype"] = macro.args[0]
        return self.continue_parse
        
    def gsDPPipelineMode(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_pipeline"] = macro.args[0]
        return self.continue_parse
        
    def gsDPSetAlphaCompare(self, macro: Macro):
        self.NewMat = 1
        self.LastMat.other_mode["g_mdsft_alpha_compare"] = macro.args[0]
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
        self.LastMat.base_tile = self.eval_tile_enum(macro.args[-2])
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

    def gsDPLoadBlock(self, macro: Macro):
        if hasattr(self.LastMat, "loadtex"):
            tex = self.LastMat.loadtex
            # these values aren't necessary when the texture is already in png format
            # tex.dxt = hexOrDecInt(args[4])
            # tex.texels = hexOrDecInt(args[3])
            tile_index = self.eval_tile_enum(macro.args[0])
            tex.tile = self.LastMat.tiles[tile_index]
            self.LastMat.tmem[tex.tile.tmem] = tex
        else:
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
        Fmt = macro.args[0]
        Siz = macro.args[1]
        self.LastMat.loadtex = Texture(Timg, Fmt, Siz)
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
        tile = self.LastMat.tiles[self.eval_tile_enum(macro.args[4])]
        tile.tmem = hexOrDecInt(macro.args[3])           
        tile.Fmt = macro.args[0].strip()
        tile.Siz = macro.args[1].strip()
        tile.Tflags = macro.args[6].strip()
        tile.TMask = self.eval_tile_enum(macro.args[7])
        tile.TShift = self.eval_tile_enum(macro.args[8])
        tile.Sflags = macro.args[9].strip()
        tile.SMask = self.eval_tile_enum(macro.args[10])
        tile.SShift = self.eval_tile_enum(macro.args[11])
        return self.continue_parse

    # combined macros
    def gsDPLoadTextureBlock(self, macro: Macro):
        # 0tex, 1fmt, 2siz, 3height, 4width, 5pal, 6flags, 8masks, 10shifts
        args = macro.args
        fmt = self.eval_timg_format(args[1])
        siz = self.eval_timg_format(args[2])
        self.gsDPSetTextureImage(macro.partial(fmt, siz, 1, args[0]))
        self.gsDPSetTile(macro.partial(fmt, siz, 0, 0, 7, 0, args[7], args[9], args[11], args[6], args[8], args[10]))
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, 0, 0)) # I don't need args
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(macro.partial(fmt, siz, 0, 0, 0, args[5], args[7], args[9], args[11], args[6], args[8], args[10]))
        self.gsDPSetTileSize(macro.partial(7, 0, 0, (hexOrDecInt(args[4]) - 1) << 2, (hexOrDecInt(args[3]) - 1) << 2))

        return self.continue_parse
        
    def gsDPLoadTextureBlockS(self, macro: Macro):
        # only changes dxt and that doesn't matter here
        return self.gsDPLoadTextureBlock(macro)

    def _gsDPLoadTextureBlock(self, macro: Macro):
        # 0tex, 1tmem, 2fmt, 3siz, 4height, 5width, 6pal, 7flags, 9masks, 11shifts
        args = macro.args
        fmt = eval_timg_format(args[2])
        siz = eval_timg_format(args[3])
        self.gsDPSetTextureImage(macro.partial(fmt, siz, 1, args[0]))
        self.gsDPSetTile(macro.partial(fmt, siz, 0, 0, 7, 0, args[8], args[10], args[12], args[7], args[9], args[11]))
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, 0, 0))
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(macro.partial(fmt, siz, 0, 0, 0, args[5], args[7], args[9], args[11], args[6], args[8], args[10]))
        self.gsDPSetTileSize(macro.partial(7, 0, 0, (hexOrDecInt(args[4]) - 1) << 2, (hexOrDecInt(args[3]) - 1) << 2))
        return self.continue_parse 
        
    def gsDPLoadTextureBlock_4b(self, macro: Macro):
        # 0tex, 1fmt, 2height, 3width, 4pal, 5flags, 7masks, 9shifts
        args = macro.args
        fmt = eval_timg_format(args[1])
        self.gsDPSetTextureImage(macro.partial(fmt, "G_IM_SIZ_16b", 1, args[0]))
        self.gsDPSetTile(macro.partial(fmt, "G_IM_SIZ_16b", 0, 0, 7, 0, args[6], args[8], args[10], args[5], args[7], args[9]))
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, 0, 0))
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(macro.partial(fmt, "G_IM_SIZ_4b", 0, 0, 0, args[4], args[3], args[8], args[10], args[3], args[7], args[9]))
        self.gsDPSetTileSize(macro.partial(7, 0, 0, (hexOrDecInt(args[4]) - 1) << 2, (hexOrDecInt(args[3]) - 1) << 2))
        return self.continue_parse 
        
    def gsDPLoadTextureBlock_4bs(self, macro: Macro):
        # only changes dxt and that doesn't matter here
        return self.gsDPLoadTextureBlock_4b(macro)
          
        
    # other stuff that probably doesn't matter since idk who uses these
    # if they break make an issue
    # _gsDPLoadTextureBlockTile
    # gsDPLoadMultiBlock
    # gsDPLoadMultiBlockS
    
    # syncs need no processing
    def gsSPCullDisplayList(self, macro: Macro):
        return self.continue_parse
        
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

    def parse_tri(self, Tri: Sequence[int]):
        return [self.VertBuff[a] for a in Tri]

    # if someone uses just the int these catch that
    def eval_timg_format(self, fmt: str):
        GBI_fmt_ints = {
            "0": "G_IM_FMT_RGBA",
            "1": "G_IM_FMT_YUV",
            "2": "G_IM_FMT_CI",
            "3": "G_IM_FMT_IA",
            "4": "G_IM_FMT_I",
        }
        return GBI_fmt_ints.get(fmt, fmt)
        
    def eval_image_frac(self, arg: Union[str, Number]):
        if type(arg) == int:
            return arg
        arg2 = arg.replace("G_TEXTURE_IMAGE_FRAC", "2")
        # evals bad probably
        return eval(arg2)

    def eval_tile_enum(self, arg: Union[str, Number]):
        if type(arg) is str:
            # fix later
            return getattr(self.f3d_gbi, arg, 0)
        else:
            return hexOrDecInt(arg)

    def eval_set_combine_macro(self, arg: str):
        return  getattr(self.f3d_gbi, 
            arg[0], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"]
        ) +  getattr(self.f3d_gbi, arg[1], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"])
