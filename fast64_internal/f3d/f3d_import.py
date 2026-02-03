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

from ..utility import hexOrDecInt, gammaInverse
from ..utility_importer import *
from ..bin_png import convert_tex

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------


# will format light struct data passed depending on type of light
class LightParent:
    def __init__(self, name: str, light_struct: Sequence):
        self.name = name
        getattr(self, light_struct.var_type)(light_struct.var_data)

    # naming matches var types
    def Ambient_t(self, light_data: list[str]):
        light_data = light_data[0].replace("{", "").replace("}", "").split(",")
        data = [eval(dat.strip()) for dat in light_data]
        self.col = self.a = self.l = [*data[0:3], 0xFF]

    def Light_t(self, light_data: list[str]):
        light_data = light_data[0].replace("{", "").replace("}", "").split(",")
        data = [eval(dat.strip()) for dat in light_data]
        self.col = self.a = self.l = [*data[0:3], 0xFF]
        self.dir = data[8:11]

    def Lights1(self, light_data: list[str]):
        data = [eval(dat.strip()) for dat in light_data[0].split(",")]
        self.a = [*data[0:3], 0xFF]
        self.col = self.l = [*data[3:6], 0xFF]
        self.dir = data[7:10]


# just holds common methods for tiles & textures
class TexBase:
    # sometimes int args are used so convert them all to str DEFs
    def standardize_fields(self):
        if self.fmt.isnumeric():
            fmt_types = {0: "RGBA", 2: "CI", 3: "IA", 4: "I"}
            self.fmt = f"G_IM_FMT_{fmt_types.get(int(self.fmt))}"
        if self.siz.isnumeric():
            siz_types = {0: "4b", 1: "8b", 2: "16b", 3: "32b"}
            self.siz = f"G_IM_SIZ_{siz_types.get(int(self.siz))}"

    def eval_texture_format(self):
        return f"{self.fmt.replace('G_IM_FMT_','')}{self.siz.replace('G_IM_SIZ_','').replace('b','')}"


# this will hold tile properties
class Tile(TexBase):
    def __init__(self):
        self.fmt = "G_IM_FMT_RGBA"
        self.siz = "G_IM_SIZ_16"
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
        self.tmem = -1  # because 0 is the start


# this will hold texture properties, dataclass props
# are created in order for me to make comparisons in a set
@dataclass(init=True, eq=True, unsafe_hash=True)
class Texture(TexBase):
    tex_img: str
    fmt: str
    siz: int
    width: int = 0
    height: int = 0
    pal: bool = False
    dxt: int = 0
    texels: int = 0

    def determine_size(self):
        # dxt is a ratio between words and lines of a texture
        # we can use it to get the true texture width for textures
        # loaded via loadblock

        # that said sometimes dxt is used in funny ways for special effects
        # in these cases, I will default to another measurement because
        # dxt is no longer reliable
        bit_size = int(re.search("\d+", self.siz).group())
        if self.dxt == 0:
            # this just allows export but in no way is this a normal texture
            # nor will it properly show up in blender as an import
            texels = self.texels
            self.width = self.texels
            self.height = 1
            return
        bit_size = math.log2(bit_size // 4)
        if not bit_size:
            bit_size = 0.5
        # 32b is normally 3, but it should be 4 for math to work
        # gbi uses a different define than the normal bitsize for this
        if bit_size == 3:
            bit_size = 4
        # basically 0x800 represents the fixed notation of dxt (u1.11)
        # 8/bit_size is the number of 64 bit chunks per texel
        # dxt is chunks / texel in fixed point, so width = chunks / dxt * 0x800
        width = int((0x7FF * 8 / bit_size) / (self.dxt - 1))
        # width * bitsize can't be below one
        if width * bit_size < 1:
            bit_size = 1 / width
            width = int((8 * 0x7FF / bit_size) / (self.dxt - 1))
        # in 4bit loading, texels are faked as if they're 16 bit
        # so each texel here is actually 4 texels
        if bit_size == 0.5:
            height = int(4 * (self.texels + 1) / width)
        else:
            height = int((self.texels + 1) / width)

        print(width, height, self.tex_img, bit_size)
        self.width = width
        self.height = height

    def size(self):
        return self.width, self.height


# This is a data storage class and mat to f3dmat converting class
# used when importing for kirby
class Mat:
    # constants for lastmat layer lookup
    _base_layer = -1
    _base_combiner = (
        # color
        "0",
        "0",
        "0",
        "SHADE",
        # alpha
        "0",
        "0",
        "0",
        "1",
    )

    def __init__(self, layer: int = None):
        self.GeoSet = []
        self.GeoClear = []
        self.tiles = [Tile() for a in range(8)]
        # dict[mem_offset] = tex
        self.tmem = dict()
        self.base_tile = 0
        self.tex0 = None
        self.tex1 = None
        self.pal = None
        self.set_tex = False
        self.other_mode = dict()
        self.num_lights = 1
        self.light_col = {}
        self.ambient_light = tuple()
        if not layer:
            self.layer = self._base_layer
        else:
            self.layer = layer

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
            if hasattr(self.tex0, "tex_img"):
                MyT = str(self.tex0.tex_img)
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
        return (*gammaInverse([int(a) / 255 for a in color[:3]]), int(color[3]) / 255)

    def load_texture(self, ForceNewTex: bool, path: Path, tex: Texture):
        if not tex:
            return None
        tex_img = textures.get(tex.Timg)[0]
        if "#include" in tex_img:
            return self.load_texture_png(force_new_tex, textures, path, tex)
        else:
            return self.load_texture_array(force_new_tex, textures, path, tex)

    def load_texture_array(self, force_new_tex: bool, textures: dict, path: Path, tex: Texture):
        """
        Create a new/find image object and then fill pixel buffer with array data
        """
        tex_img = textures.get(tex.tex_img)
        # idk if this properly deals with multiple palettes...
        pal_img = textures.get(self.pal.tex_img) if self.pal else None
        if pal_img:
            pal_stream = bytes([int(a.strip(), 0x10) for a in pal_img.var_data[0].split(",") if "0x" in a])
            print(tex_img.var_name, pal_img.var_name, len(pal_stream))
        tex.determine_size()
        image_texels = convert_tex(
            tex.fmt,
            tex.width,
            tex.height,
            tex.siz,
            tex_img.var_data[0],
            pal_stream=pal_img.var_data[0] if pal_img else None,
        )
        i = bpy.data.images.new(tex.tex_img, tex.width, tex.height)
        i.pixels = image_texels
        return i

    # TODO: make real with reasonable basics
    def load_texture_png(self, force_new_tex: bool, textures: dict, path: Path, tex: Texture):
        print("load tex png")
        return None

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
            if tex:
                setattr(self, f"tex{tex_index}", tex)

    # TODO: add load texture call
    def set_textures(self, f3d: F3DMaterialProperty, tex_path: Path):
        self.set_tex_scale(f3d)
        if self.tex0 and self.set_tex:
            self.tex0.standardize_fields()
            self.set_tex_settings(
                f3d.tex0, self.load_texture(0, tex_path, self.tex0), self.tiles[0 + self.base_tile], self.tex0.tex_img
            )
        if self.tex1 and self.set_tex:
            self.tex1.standardize_fields()
            self.set_tex_settings(
                f3d.tex1, self.load_texture(0, tex_path, self.tex1), self.tiles[1 + self.base_tile], self.tex1.tex_img
            )

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
        if hasattr(self, "blend_color"):
            f3d.set_blend = True
            f3d.blend_color = self.convert_color(self.blend_color)
        if hasattr(self, "env_color"):
            f3d.set_env = True
            f3d.env_color = self.convert_color(self.env_color)
        if hasattr(self, "prim_color"):
            prim = self.prim_color
            f3d.set_prim = True
            f3d.prim_lod_min = int(prim[0])
            f3d.prim_lod_frac = int(prim[1])
            f3d.prim_color = self.convert_color(prim[-4:])

    def set_tex_scale(self, f3d: F3DMaterialProperty):
        if self.set_tex:
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
        tile.standardize_fields()
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

    # TODO: rework with new render mode stuffs
    def set_rendermode(self, f3d: F3DMaterialProperty):
        rdp = f3d.rdp_settings
        if hasattr(self, "RenderMode"):
            rdp.set_rendermode = True
            # if the enum isn't there, then just print an error for now
            try:
                rdp.rendermode_preset_cycle_1 = self.RenderMode[0]
                rdp.rendermode_preset_cycle_2 = self.RenderMode[1]
                print(f"set render modes with render mode {self.RenderMode} for {f3d.id_data.name}")
            except:
                rdp.set_rendermode = False
                print(f"could not set render modes with render mode {self.RenderMode}")

    def set_othermode(self, f3d: F3DMaterialProperty):
        rdp = f3d.rdp_settings
        for prop, val in self.other_mode.items():
            setattr(rdp, prop, val)
            # TODO: add in exception handling here

    def set_geo_mode(self, rdp: RDPSettings, mat: bpy.types.Material):
        # texture gen has a different name than gbi
        for a in self.GeoSet:
            setattr(rdp, a.replace("G_TEXTURE_GEN", "G_TEX_GEN").lower().strip(), True)
        for a in self.GeoClear:
            setattr(rdp, a.replace("G_TEXTURE_GEN", "G_TEX_GEN").lower().strip(), False)

    # TODO: Very lazy for now, deal with presets later
    def set_combiner(self, f3d: F3DMaterialProperty):
        f3d.presetName = "Custom"
        if not hasattr(self, "Combiner"):
            # set default combiner per game via subclass, base is shaded solid
            f3d.combiner1.A = self._base_combiner[0]
            f3d.combiner1.B = self._base_combiner[1]
            f3d.combiner1.C = self._base_combiner[2]
            f3d.combiner1.D = self._base_combiner[3]
            f3d.combiner1.A_alpha = self._base_combiner[4]
            f3d.combiner1.B_alpha = self._base_combiner[5]
            f3d.combiner1.C_alpha = self._base_combiner[6]
            f3d.combiner1.D_alpha = self._base_combiner[7]
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
    def __init__(self, lastmat: dict[any, Mat] = None):
        self.Vtx = {}
        self.Gfx = {}
        self.Light_t = {}
        self.Ambient_t = {}
        self.Lights = {}
        self.Textures = {}
        self.NewMat = 1
        self.f3d_gbi = get_F3D_GBI()
        # use the dict in subclasses to keep track of mats per layer when parsing in render order
        self.last_mat_dict = dict()
        if not lastmat:
            self.last_mat = Mat()
            self.last_mat_dict[Mat.base_mat] = self.last_mat
            self.last_mat.name = 0
        else:
            self.last_mat = lastmat
        super().__init__()

    def parse_stream_DL(self, display_list_arr: Sequence, start_name: str):
        """
        Initialize vars and then parse data stream
        """
        self.VertBuff = [0] * 32  # turbo 3d in shambles
        self.Verts = []
        self.Tris = []
        self.UVs = []
        self.VCs = []
        self.Mats = []
        # merge all lights into single lights dictionary
        self.Lights.update(self.Light_t)
        self.Lights.update(self.Ambient_t)
        self.parse_stream(display_list_arr, start_name)

    def gsSPEndDisplayList(self, macro: Macro):
        return self.break_parse

    def gsSPBranchList(self, macro: Macro):
        NewDL = self.Gfx.get(branched_dl := macro.args[0])
        if not NewDL:
            raise Exception(
                "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
                    NewDL, self.scene.fast64.sm64.importer.level_name, self.scene.fast64.sm64.importer.level_prefix
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
                    NewDL, self.scene.fast64.sm64.importer.level_name, self.scene.fast64.sm64.importer.level_prefix
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
                    ref, self.scene.fast64.sm64.importer.level_name, self.scene.fast64.sm64.importer.level_prefix
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
            uv = (val >> 16) & 0xFFFF, val & 0xFFFF
            self.Verts.append(self.Verts[vtx])
            self.UVs.append(uv)
            self.VCs.append(self.VCs[vtx])
            self.VertBuff[hexOrDecInt(macro.args[0])] = len(self.Verts)
        elif where == "RGBA":
            vertex_col = [(val >> 8 * i) & 0xFF for i in range(4)].reverse()
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
        self.last_mat.RenderMode = [a.strip() for a in macro.args]
        return self.continue_parse

    # The highest numbered light is always the ambient light
    def gsSPLight(self, macro: Macro):
        self.NewMat = 1
        light = re.search("&.+\.", macro.args[0]).group()[1:-1]
        # search light data structs in file
        try:
            light_struct = self.Lights.get(light)
        except:
            raise Exception(
                "Could not find Light {} in levels/{}/{}leveldata.inc.c".format(
                    light, self.scene.fast64.sm64.importer.level_name, self.scene.fast64.sm64.importer.level_prefix
                )
            )
        light = LightParent(light, light_struct)
        light_num = int(re.search("\d", macro.args[1]).group())
        # period followed by any number of non whitespace chars
        light_val = getattr(light, re.search("\\.\S+", macro.args[0]).group()[1:])
        if light_num > self.last_mat.num_lights:
            self.last_mat.ambient_light = light_val
        else:
            self.last_mat.light_col[light_num] = light_val
        return self.continue_parse

    # numlights0 still gives one ambient and diffuse light
    def gsSPNumLights(self, macro: Macro):
        self.NewMat = 1
        num = re.search("\d", macro.args[0]).group()
        num = int(num) if num else 1
        self.last_mat.num_lights = num
        return self.continue_parse

    def gsSPLightColor(self, macro: Macro):
        self.NewMat = 1
        num = re.search("\d", macro.args[0]).group()
        num = int(num) if num else 1
        self.last_mat.light_col[num] = eval(macro.args[-1]).to_bytes(4, "big")
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

    def gsSPSetOtherMode(self, macro: Macro):
        self.NewMat = 1
        if macro.args[0] == "G_SETOTHERMODE_H":
            for i, othermode in enumerate(macro.args[3].split("|")):
                # this may cause an issue if someone uses a wacky custom othermode H
                mode_h_attr = RDPSettings.other_mode_h_attributes[i][1]
                self.last_mat.other_mode[mode_h_attr] = othermode.strip()
        else:
            if int(macro.args[2]) > 3:
                self.last_mat.RenderMode = []
            # top two bits are z src and alpha compare, rest is render mode
            for i, othermode in enumerate(macro.args[3].split("|")):
                if int(macro.args[2]) > 3 and i > 1:
                    self.last_mat.RenderMode.append(othermode)
                    continue
                mode_l_attr = RDPSettings.other_mode_l_attributes[i][1]
                self.last_mat.other_mode[mode_l_attr] = othermode.strip()
        return self.continue_parse

    # some independent other mode settings
    def gsDPSetTexturePersp(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textpersp"] = macro.args[0]
        return self.continue_parse

    def gsDPSetDepthSource(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_zsrcsel"] = macro.args[0]
        return self.continue_parse

    def gsDPSetColorDither(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_rgb_dither"] = macro.args[0]
        return self.continue_parse

    def gsDPSetAlphaDither(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_alpha_dither"] = macro.args[0]
        return self.continue_parse

    def gsDPSetCombineKey(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_combkey"] = macro.args[0]
        return self.continue_parse

    def gsDPSetTextureConvert(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textconv"] = macro.args[0]
        return self.continue_parse

    def gsDPSetTextureFilter(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_text_filt"] = macro.args[0]
        return self.continue_parse

    def gsDPSetTextureLOD(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textlod"] = macro.args[0]
        return self.continue_parse

    def gsDPSetTextureDetail(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textdetail"] = macro.args[0]
        return self.continue_parse

    def gsDPSetCycleType(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_cycletype"] = macro.args[0]
        return self.continue_parse

    def gsDPSetTextureLUT(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textlut"] = macro.args[0]
        return self.continue_parse

    def gsDPPipelineMode(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_pipeline"] = macro.args[0]
        return self.continue_parse

    def gsDPSetAlphaCompare(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_alpha_compare"] = macro.args[0]
        return self.continue_parse

    def gsSPFogFactor(self, macro: Macro):
        return self.continue_parse

    def gsDPSetFogColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.fog_color = macro.args
        return self.continue_parse

    def gsSPFogPosition(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.fog_pos = macro.args
        return self.continue_parse

    def gsDPSetBlendColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.blend_color = macro.args
        return self.continue_parse

    def gsDPSetPrimColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.prim_color = macro.args
        return self.continue_parse

    def gsDPSetEnvColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.env_color = macro.args
        return self.continue_parse

    # multiple geo modes can happen in a row that contradict each other
    # this is mostly due to culling wanting diff geo modes than drawing
    # but sometimes using the same vertices
    def gsSPClearGeometryMode(self, macro: Macro):
        self.NewMat = 1
        args = [a.strip() for a in macro.args[0].split("|")]
        for a in args:
            if a in self.last_mat.GeoSet:
                self.last_mat.GeoSet.remove(a)
        self.last_mat.GeoClear.extend(args)
        return self.continue_parse

    def gsSPSetGeometryMode(self, macro: Macro):
        self.NewMat = 1
        args = [a.strip() for a in macro.args[0].split("|")]
        for a in args:
            if a in self.last_mat.GeoClear:
                self.last_mat.GeoClear.remove(a)
        self.last_mat.GeoSet.extend(args)
        return self.continue_parse

    def gsSPGeometryMode(self, macro: Macro):
        self.NewMat = 1
        argsC = [a.strip() for a in macro.args[0].split("|")]
        argsS = [a.strip() for a in macro.args[1].split("|")]
        for a in argsC:
            if a in self.last_mat.GeoSet:
                self.last_mat.GeoSet.remove(a)
        for a in argsS:
            if a in self.last_mat.GeoClear:
                self.last_mat.GeoClear.remove(a)
        self.last_mat.GeoClear.extend(argsC)
        self.last_mat.GeoSet.extend(argsS)
        return self.continue_parse

    def gsSPLoadGeometryMode(self, macro: Macro):
        self.NewMat = 1
        geo_set = {a.strip().lower() for a in macro.args[0].split("|")}
        all_geos = set(RDPSettings.geo_mode_attributes.values())
        self.last_mat.GeoSet = list(geo_set)
        self.last_mat.GeoClear = list(all_geos.difference(geo_set))
        return self.continue_parse

    def gsDPSetCombineMode(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.Combiner = self.eval_set_combine_macro(macro.args)
        return self.continue_parse

    def gsDPSetCombineLERP(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.Combiner = macro.args
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
        # enable is 1 or 2 depending on microcode, 0 is always off
        self.last_mat.set_tex = set_tex != 0
        self.last_mat.tex_scale = [
            ((0x10000 * (hexOrDecInt(a) < 0)) + hexOrDecInt(a)) / 0xFFFF for a in macro.args[0:2]
        ]  # signed half to unsigned half
        self.last_mat.base_tile = self.eval_tile_enum(macro.args[-2])
        return self.continue_parse

    # last tex is a palette
    def gsDPLoadTLUTCmd(self, macro: Macro):
        if hasattr(self.last_mat, "loadtex"):
            tex = self.last_mat.loadtex
            tile_index = self.eval_tile_enum(macro.args[0])
            tex.tile = self.last_mat.tiles[tile_index]
            tex.pal = True
            self.last_mat.pal = tex
            self.last_mat.tmem[tex.tile.tmem] = tex
        else:
            print(
                "**--Load block before set t img, DL is partial and missing context"
                "likely static file meant to be used as a piece of a realtime system.\n"
                "No interpretation on file possible**--"
            )
            return None
        return self.continue_parse

    def gsDPLoadBlock(self, macro: Macro):
        if hasattr(self.last_mat, "loadtex"):
            tex = self.last_mat.loadtex
            # these values aren't necessary when the texture is already in png format
            tex.dxt = hexOrDecInt(macro.args[4])
            tex.texels = hexOrDecInt(macro.args[3])
            tile_index = self.eval_tile_enum(macro.args[0])
            tex.tile = self.last_mat.tiles[tile_index]
            self.last_mat.tmem[tex.tile.tmem] = tex
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
        tex_img = macro.args[3]
        fmt = macro.args[0]
        siz = macro.args[1]
        self.last_mat.loadtex = Texture(tex_img, fmt, siz)
        return self.continue_parse

    def gsDPSetTileSize(self, macro: Macro):
        self.NewMat = 1
        tile = self.last_mat.tiles[self.eval_tile_enum(macro.args[0])]
        tile.Slow = self.eval_image_frac(macro.args[1])
        tile.Tlow = self.eval_image_frac(macro.args[2])
        tile.Shigh = self.eval_image_frac(macro.args[3])
        tile.Thigh = self.eval_image_frac(macro.args[4])
        return self.continue_parse

    def gsDPSetTile(self, macro: Macro):
        self.NewMat = 1
        tile = self.last_mat.tiles[self.eval_tile_enum(macro.args[4])]
        tile.tmem = hexOrDecInt(macro.args[3])
        tile.fmt = macro.args[0].strip()
        tile.siz = macro.args[1].strip()
        tile.Tflags = macro.args[6].strip()
        tile.TMask = self.eval_tile_enum(macro.args[7])
        tile.TShift = self.eval_tile_enum(macro.args[8])
        tile.Sflags = macro.args[9].strip()
        tile.SMask = self.eval_tile_enum(macro.args[10])
        tile.SShift = self.eval_tile_enum(macro.args[11])
        # on a render tile 4 bit textures will change their size here
        tex = self.last_mat.tmem.get(tile.tmem, None)
        if tex:
            tex.siz = tile.siz
        return self.continue_parse

    # combined macros
    def gsDPLoadTLUT(self, macro: Macro):
        # count, tmemaddr, tex
        args = macro.args
        self.gsDPSetTextureImage(macro.partial("G_IM_FMT_RGBA", "G_IM_SIZ_16b", 1, args[2]))
        self.gsDPSetTile(macro.partial(0, 0, 0, args[1], 7, 0, 0, 0, 0, 0, 0, 0))
        self.gsDPLoadTLUTCmd(macro.partial(7, args[0]))
        return self.continue_parse

    def gsDPLoadTextureBlock(self, macro: Macro):
        # 0tex, 1fmt, 2siz, 3height, 4width, 5pal, 6flags, 8masks, 10shifts
        args = macro.args
        fmt = self.eval_timg_format(args[1])
        siz = self.eval_timg_format(args[2])
        self.gsDPSetTextureImage(macro.partial(fmt, siz, 1, args[0]))
        self.gsDPSetTile(macro.partial(fmt, siz, 0, 0, 7, 0, args[7], args[9], args[11], args[6], args[8], args[10]))
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, 0, 0))  # I don't need args
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(
            macro.partial(fmt, siz, 0, 0, 0, args[5], args[7], args[9], args[11], args[6], args[8], args[10])
        )
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
        self.gsDPSetTile(
            macro.partial(fmt, siz, 0, 0, 0, args[5], args[7], args[9], args[11], args[6], args[8], args[10])
        )
        self.gsDPSetTileSize(macro.partial(7, 0, 0, (hexOrDecInt(args[4]) - 1) << 2, (hexOrDecInt(args[3]) - 1) << 2))
        return self.continue_parse

    def gsDPLoadTextureBlock_4b(self, macro: Macro):
        # 0tex, 1fmt, 2height, 3width, 4pal, 5flags, 7masks, 9shifts
        args = macro.args
        fmt = eval_timg_format(args[1])
        self.gsDPSetTextureImage(macro.partial(fmt, "G_IM_SIZ_16b", 1, args[0]))
        self.gsDPSetTile(
            macro.partial(fmt, "G_IM_SIZ_16b", 0, 0, 7, 0, args[6], args[8], args[10], args[5], args[7], args[9])
        )
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, 0, 0))
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(
            macro.partial(fmt, "G_IM_SIZ_4b", 0, 0, 0, args[4], args[3], args[8], args[10], args[3], args[7], args[9])
        )
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
            self.Mats.append([len(self.Tris) - 1, self.last_mat])
            self.last_mat = deepcopy(self.last_mat)  # for safety
            self.last_mat_dict[self.last_mat.layer] = self.last_mat

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
        return getattr(self.f3d_gbi, arg[0], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"]) + getattr(
            self.f3d_gbi, arg[1], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"]
        )
