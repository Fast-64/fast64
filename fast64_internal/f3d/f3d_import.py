from __future__ import annotations

import bpy, bmesh

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

from ..f3d.f3d_material import F3DMaterialProperty, RDPSettings, TextureProperty, getDefaultMaterialPreset, createF3DMat
from ..f3d.f3d_gbi import get_F3D_GBI
from ..f3d.f3d_enums import (
    enumAlphaCompare,
    enumAlphaDither,
    enumRGBDither,
    enumCombKey,
    enumTextConv,
    enumTextFilt,
    enumTextLUT,
    enumTextLOD,
    enumTextDetail,
    enumTextPersp,
    enumCycleType,
    enumColorDither,
    enumPipelineMode,
)

from ..utility import hexOrDecInt, gammaInverse, GetEnums
from ..utility_importer import *
from ..bin_png import convert_tex_c, convert_tex_bin

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------


class LightParent:
    """format light struct data passed depending on type of light"""

    def __init__(self, name: str, light_struct: Sequence):
        self.name = name
        getattr(self, light_struct.var_type)(light_struct.var_data)

    # I'm not 100% sure this covers all kinds of light struct from movemem cmd
    @staticmethod
    def ambient_from_binary(bin_file: BinaryIO, macro: Macro):
        # just get first color
        col = [*struct.unpack(">3B", bin_file[macro.args[2] : macro.args[2] + 3]), 0xFF]
        return col

    @staticmethod
    def diffuse_from_binary(bin_file: BinaryIO, macro: Macro):
        # just get first color
        # cls.dir = [*struct.unpack(">3B", bin_file[macro.args[2] + 8:macro.args[2] + 11]), 0xFF]
        col = [*struct.unpack(">3B", bin_file[macro.args[2] : macro.args[2] + 3]), 0xFF]
        return col

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

    # handles all Lights* type data structures, support for Lights1 rn
    def Lights(self, light_data: list[str]):
        data = [eval(dat.strip()) for dat in light_data[0].split(",")]
        self.a = [*data[0:3], 0xFF]
        self.col = self.l = [*data[3:6], 0xFF]
        self.dir = data[7:10]


class TexBase:
    """Holds common methods for tiles & textures"""

    def check_tex_hack(self):
        # check for hacky 4b loading
        if "RGBA" in self.fmt and "4b" in self.siz:
            self.siz = "16b"

    # sometimes int args are used so convert them all to str DEFs
    def standardize_fields(self):
        self.check_tex_hack()
        if self.fmt.isnumeric():
            fmt_types = {0: "RGBA", 2: "CI", 3: "IA", 4: "I"}
            self.fmt = f"G_IM_FMT_{fmt_types.get(int(self.fmt))}"
        if self.siz.isnumeric():
            siz_types = {0: "4b", 1: "8b", 2: "16b", 3: "32b"}
            self.siz = f"G_IM_SIZ_{siz_types.get(int(self.siz))}"

    def eval_texture_format(self):
        self.check_tex_hack()
        return f"{self.fmt.replace('G_IM_FMT_','')}{self.siz.replace('G_IM_SIZ_','').replace('b','')}"

    # if someone uses just the int these catch that
    @staticmethod
    def parse_timg_format(fmt: str):
        GBI_fmt_ints = {
            "0": "G_IM_FMT_RGBA",
            "1": "G_IM_FMT_YUV",
            "2": "G_IM_FMT_CI",
            "3": "G_IM_FMT_IA",
            "4": "G_IM_FMT_I",
        }
        return GBI_fmt_ints.get(fmt, fmt)

    @staticmethod
    def parse_tile_flags(fmt: str):
        GBI_flag_ints = {
            "0": "G_TX_NOMIRROR",
            "1": "G_TX_MIRROR",
            "2": "G_TX_CLAMP",
        }
        return GBI_flag_ints.get(fmt, fmt)

    @staticmethod
    def parse_image_frac(arg: Union[str, Number]):
        if type(arg) == int:
            return arg
        arg2 = arg.replace("G_TEXTURE_IMAGE_FRAC", "2")
        # evals bad probably
        return eval(arg2)

    @staticmethod
    def parse_tile_enum(f3d_gbi: F3D, arg: Union[str, Number]):
        if type(arg) is str and not arg.isdigit():
            # fix later
            return getattr(f3d_gbi, arg, 0)
        else:
            return hexOrDecInt(arg)


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


@dataclass(init=True, eq=True, unsafe_hash=True)
class Texture(TexBase):
    """this will hold texture properties
    dataclass props are created in order for me to make comparisons in a set
    """

    tex_img: str
    fmt: str
    siz: int
    width: int = 0
    height: int = 0
    pal: bool = False
    dxt: int = 0
    texels: int = 0
    num_bytes: int = 0  # to be filled in after self.determine_size

    def determine_size(self):
        """Calculate image size using load block values and texture format
        dxt is a ratio between words and lines of a texture
        we can use it to get the true texture width for textures
        loaded via loadblock

        that said sometimes dxt is used in funny ways for special effects
        in these cases, I will default to another measurement because
        dxt is no longer reliable
        reverse load block texels to be just width * height
        dxs = (((fImage.width) * (fImage.height) + 3) >> 2) - 1 for 4B
        else
        dxs = (
                ((fImage.width) * (fImage.height) + f3d.G_IM_SIZ_VARS[siz + "_INCR"])
                >> f3d.G_IM_SIZ_VARS[siz + "_SHIFT"]
            ) - 1
        """
        bit_size = int(re.search("\d+", self.siz).group())
        if bit_size == 4:
            texels = (self.texels + 1) << 2
        else:
            siz_adjust = 1 if bit_size == 8 else 0
            texels = (self.texels + 1) << siz_adjust
        # you may have the size already figured out due to image data provided by the ROM
        if self.width and self.height:
            self.num_bytes = int(bit_size * self.width * self.height)
            return
        if self.dxt == 0:
            # this just allows export but in no way is this a normal texture
            # nor will it properly show up in blender as an import
            if not self.width:
                self.width = 1
            self.height = texels // self.width
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
            print("width*bitsize < 1", self.tex_img, texels)
            bit_size = 1 / width
            width = int((8 * 0x7FF / bit_size) / (self.dxt - 1))

        height = int((texels + 1) / width)
        self.width = width
        self.height = height
        self.num_bytes = int(bit_size * width * height)

    def size(self):
        return self.width, self.height


class Mat:
    """Holds parsed material data to be written out to fast64 f3d materials with method apply_material_settings"""

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

    def __init__(self, layer: int = None, bin_file: BinaryIO = None):
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
        self.name = None
        if not layer:
            self.layer = self._base_layer
        else:
            self.layer = layer
        self.bin_file = bin_file  # theoretically could be different for each mat

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
                if mode in self.GeoSet:
                    return True
                if mode in self.GeoClear:
                    return False
                else:
                    return True
            chkT = lambda x, y, d: x.__dict__.get(y, d)
            rendermode = getattr(self, "RenderMode", ["G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2"])
            MyProps = (
                MyT,
                *self.Combiner[0:8],
                *rendermode,
                EvalGeo(self, "G_LIGHTING"),
                EvalGeo(self, "G_SHADE"),
                EvalGeo(self, "G_SHADE_SMOOTH"),
                EvalGeo(self, "G_ZBUFFER"),
                chkT(self, "g_mdsft_alpha_compare", "G_AC_NONE"),
                chkT(self, "g_mdsft_zsrcsel", "G_ZS_PIXEL"),
                chkT(self, "g_mdsft_alpha_dither", "G_AD_NOISE"),
                (self.tiles[0].Shigh/4),
                (self.tiles[0].Thigh/4),
                (self.tiles[0].Slow/4),
                (self.tiles[0].Tlow/4),
            )
            dupe = hash(MyProps) == hash(F3Dprops)
            return dupe
        return False

    def mat_hash(self, mat: bpy.types.Material):
        return False

    def convert_color(self, color: Sequence[Number]):
        return (*gammaInverse([int(a) / 255 for a in color[:3]]), int(color[3]) / 255)

    def load_texture(self, force_new_tex: bool, textures: dict, path: Path, tex: Texture):
        if not tex:
            return None
        tex_img = textures.get(tex.tex_img)
        if tex_img and "#include" in tex_img[0]:
            return self.load_texture_png(force_new_tex, textures, path, tex)
        # TODO improve this
        elif tex_img or self.bin_file:
            return self.load_texture_array(
                force_new_tex,
                textures,
                tex,
                DataParser._c_parsing if not self.bin_file else DataParser._binary_parsing,
            )

    def load_texture_array(self, force_new_tex: bool, textures: dict, tex: Texture, parse_target: int):
        """
        Create a new/find image object and then fill pixel buffer with array data
        """
        tex.determine_size()
        # for some reason I can't get the parsing target to be what I want, so read props instead
        # based on naming structure, you shouldn't have repeat texture names since they're ROM addresses
        if parse_target == DataParser._binary_parsing:
            prefix = f"{self.name}_" if self.name else ""
            name = f"{prefix}tex_img_0x{tex.tex_img:X}"
            if i := bpy.data.images.get(name, None):
                return i
            tex_img = tex.tex_img
            tex_img = self.bin_file[tex_img : tex_img + tex.num_bytes]
            # idk if this properly deals with multiple palettes...
            pal_img = self.pal.tex_img if self.pal else None
            if pal_img:
                # determine if CI4 or CI8 and num colors
                if "16b" in tex.siz:
                    pal_img = self.bin_file[pal_img : pal_img + 0x200]
                else:
                    pal_img = self.bin_file[pal_img : pal_img + 32]
            image_texels = convert_tex_bin(
                tex.fmt,
                tex.width,
                tex.height,
                tex.siz,
                tex_img,
                pal_stream=pal_img if pal_img else None,
            )
            name = f"{prefix}tex_img_0x{tex.tex_img:X}"
        else:
            name = tex.tex_img
            if (i := bpy.data.images.get(name, None)) and not force_new_tex:
                return i
            tex_img = textures.get(tex.tex_img)
            # idk if this properly deals with multiple palettes...
            pal_img = textures.get(self.pal.tex_img) if self.pal else None
            image_texels = convert_tex_c(
                tex.fmt,
                tex.width,
                tex.height,
                tex.siz,
                tex_img.var_data[0],
                pal_stream=pal_img.var_data[0] if pal_img else None,
            )
        i = bpy.data.images.new(name, tex.width, tex.height, alpha=True)
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

    def apply_material_settings(self, mat: bpy.types.Material, textures: dict, tex_path: Path, layer: int = 1):
        f3d = mat.f3d_mat

        # self.set_texture_tile_mapping()
        self.set_register_settings(mat, f3d)
        self.set_textures(f3d, textures, tex_path)

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
        use_mag = self.other_mode.get("g_mdsft_textdetail", None) == "G_TD_SHARPEN"
        for index, tile in enumerate(self.tiles):
            # turn off mip mapping since fast64 doesn't emulate it
            # tex_index = index - self.base_tile + use_mag
            tex_index = index
            if tex_index < 0:
                continue
            tex = self.tmem.get(tile.tmem, None)
            if tex:
                setattr(self, f"tex{tex_index}", tex)

    # TODO: add load texture call
    def set_textures(self, f3d: F3DMaterialProperty, textures: dict, tex_path: Path):
        self.set_tex_scale(f3d)
        if self.tex0 and self.set_tex:
            self.tex0.standardize_fields()
            self.set_tex_settings(
                f3d.tex0,
                self.load_texture(0, textures, tex_path, self.tex0),
                self.tiles[0 + self.base_tile],
                self.tex0.tex_img,
            )
        if self.tex1 and self.set_tex:
            self.tex1.standardize_fields()
            self.set_tex_settings(
                f3d.tex1,
                self.load_texture(0, textures, tex_path, self.tex1),
                self.tiles[1 + self.base_tile],
                self.tex1.tex_img,
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
        if self.ambient_light:
            f3d.set_ambient_from_light = False
            f3d.ambient_light_color = self.convert_color(self.ambient_light)
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


class DL(DataParser):
    """handles DL import processing, specifically built to process each cmd into the mat class

    should be inherited into a larger F3d class which wraps DL processing
    does not deal with flow control or gathering the data containers (VB, Geo cls etc.)
    """

    _skippable_cmds = {
        "gsDPNoOp",
        "gsDPFullSync",
        "gsDPTileSync",
        "gsDPPipeSync",
        "gsDPLoadSync",
        "gsSPCullDisplayList",
    }

    # the min needed for this class to work for importing
    def __init__(self, lastmat: dict[any, Mat] = None, parse_target: int = DataParser._c_parsing):
        self.Vtx = {}
        self.Gfx = {}
        self.Light_t = {}
        self.Ambient_t = {}
        self.Lights = {}
        self.Textures = {}
        self.NewMat = 1
        self.f3d_gbi = get_F3D_GBI()  # make sure to set this to the right version for your game!
        self.setup_unpack_dicts()
        # use the dict in subclasses to keep track of mats per layer when parsing in render order
        self.last_mat_dict = dict()
        if not lastmat:
            self.last_mat = Mat()
            self.last_mat_dict[Mat._base_layer] = self.last_mat
            self.last_mat.name = 0
        else:
            self.last_mat = lastmat
        super().__init__(parse_target=parse_target)

    def apply_mesh_data(
        self, obj: bpy.types.Object, mesh: bpy.types.Mesh, layer: int, tex_path: Path, force_new_tex: bool = False
    ):
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
                # set the texture tile mapping so mat.tex0 and mat.tex1 exist for mat hashing
                self.Mats[ind + 1][1].set_texture_tile_mapping()
                new = self.create_new_f3d_mat(self.Mats[ind + 1][1], obj, force_new_tex)
                ind += 1
                if not new:
                    new = len(mesh.materials) - 1
                    mat = mesh.materials[new]
                    mat.name = "F3D Mat {} {}".format(obj.name, new)
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
            if self.parsing_target == DataParser._binary_parsing:
                flip = lambda x: x - 1
            else:
                flip = lambda x: x * -1 + 1
            l[uv_map].uv[1] = flip(l[uv_map].uv[1])
            l[v_color] = [*gammaInverse([a / 255 for a in vcol]), 255]
            l[v_alpha] = [vcol[3] / 255 for i in range(4)]

    # create a new f3d_mat given an SM64_Material class but don't create copies with same props
    def create_new_f3d_mat(self, mat: Mat, obj: bpy.types.Object, force_new_tex: bool):
        if not force_new_tex:
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

    # MSB: (name, PackedFormat), ones empty PackedFormat have no support yet
    # f3d class changes its var values based on f3d type, so f3d_gbi.G_TRI1 matches correct MSB
    def setup_unpack_dicts(self):
        f3d_gbi = self.f3d_gbi
        if f3d_gbi.F3DEX_GBI_2:
            self.f3dex_cmd_gbi_names = dict()
            self.f3d_cmd_gbi_names = dict()

            self.f3dex2_cmd_gbi_names = {
                f3d_gbi.G_VTX: (
                    "gsSPVertexBin",
                    PackedFormat(">7B", (2,), reorder=(1, 2, 3), make_str=False, bit_packing=(4, 8, 4, 8, 32)),
                ),  # pad num_v offset+num seg_ptr, reorder -> num offset ptr
                f3d_gbi.G_DMA_IO: (
                    "gsSPDma_io",
                    PackedFormat(">7B", bit_packing=(1, 10, 1, 12, 32)),
                ),  # i/o dmem_addr siz dram_addr
                f3d_gbi.G_POPMTX: ("gsSPPopMatrix", PackedFormat(">3BL")),  # pad123 num_mtx
                f3d_gbi.G_GEOMETRYMODE: (
                    "gsSPGeometryMode",
                    PackedFormat(">7B", bit_packing=(24, 32), post_unpack=self.parse_geo_flags),
                ),  # clear set
                f3d_gbi.G_MTX: ("gsSPMatrix", PackedFormat(">3BL", (3,))),  # pad pad type seg_ptr
                f3d_gbi.G_MOVEWORD: (
                    "gsMoveWd",
                    PackedFormat(">BHL", (2,), make_str=False),
                ),  # dmem_index offset seg_ptr
                f3d_gbi.G_QUAD: (
                    "gsSP1Quadrangle",
                    PackedFormat(">7B", make_str=False, post_unpack=lambda args: [a // 2 for a in args]),
                ),  # v123 flag v456
            }
        elif f3d_gbi.F3DEX_GBI:
            self.f3dex2_cmd_gbi_names = dict()
            self.f3d_cmd_gbi_names = dict()

            self.f3dex_cmd_gbi_names = {
                f3d_gbi.G_MTX: ("gsSPMatrix", PackedFormat(">BhL", (2,))),  # type pad seg_ptr
                f3d_gbi.G_VTX: (
                    "gsSPVertexBin",
                    PackedFormat(">7B", (2,), reorder=(1, 0, 3), make_str=False, bit_packing=(8, 6, 10, 32)),
                ),  # buf_start num_vert len_dat vtx_ptr, reorder -> num offset ptr
                f3d_gbi.G_SETGEOMETRYMODE: (
                    "gsSPSetGeometryMode",
                    PackedFormat(">7B", bit_packing=(24, 32), reorder=(1,), post_unpack=self.parse_geo_flags),
                ),  # pad word
                f3d_gbi.G_CLEARGEOMETRYMODE: (
                    "gsSPClearGeometryMode",
                    PackedFormat(">7B", bit_packing=(24, 32), reorder=(1,), post_unpack=self.parse_geo_flags),
                ),  # word pad
                f3d_gbi.G_MOVEWORD: (
                    "gsMoveWd",
                    PackedFormat(">HBL", (2,), make_str=False),
                ),  # offset dmem_index seg_ptr
            }
        else:
            self.f3dex_cmd_gbi_names = dict()
            self.f3dex2_cmd_gbi_names = dict()

            self.f3d_cmd_gbi_names = {
                f3d_gbi.G_MTX: ("gsSPMatrix", PackedFormat(">BhL", (2,))),  # type pad seg_ptr
                f3d_gbi.G_MOVEMEM: (
                    "gsSPMoveMem",
                    PackedFormat(">BHL", (2,), make_str=False),
                ),  # dmem_index siz mem_ptr
                f3d_gbi.G_VTX: (
                    "gsSPVertexBin",
                    PackedFormat(
                        ">7B",
                        (2,),
                        reorder=(0, 1, 3),
                        make_str=False,
                        bit_packing=(4, 4, 16, 32),
                        post_unpack=self.f3d_g_vertex_parse,
                    ),
                ),  # num_vert buf_start len_dat vtx_ptr, reorder -> num offset ptr
                f3d_gbi.G_SETGEOMETRYMODE: (
                    "gsSPSetGeometryMode",
                    PackedFormat(">7B", bit_packing=(24, 32), reorder=(1,), post_unpack=self.parse_geo_flags),
                ),  # pad word
                f3d_gbi.G_CLEARGEOMETRYMODE: (
                    "gsSPClearGeometryMode",
                    PackedFormat(">7B", bit_packing=(24, 32), reorder=(1,), post_unpack=self.parse_geo_flags),
                ),  # pad word
                f3d_gbi.G_MOVEWORD: (
                    "gsMoveWd",
                    PackedFormat(">HBL", (2,), make_str=False),
                ),  # offset dmem_index seg_ptr
                f3d_gbi.G_POPMTX: ("gsSPPopMatrix", PackedFormat(">7B")),  # pads
                f3d_gbi.G_TRI1: (
                    "gsSP1Triangle",
                    PackedFormat(
                        ">7B", make_str=False, reorder=(4, 5, 6, 3), post_unpack=lambda args: [a // 10 for a in args]
                    ),
                ),  # pad123 flag v123, reorder v123 flag
            }
        if f3d_gbi.F3DEX_GBI or f3d_gbi.F3DLP_GBI or f3d_gbi.F3DEX_GBI_2:
            self.f3dex_cmd_gbi_names.update(
                {
                    f3d_gbi.G_MOVEMEM: (
                        "gsSPMoveMem",
                        PackedFormat(">3BL", (3,), make_str=False, reorder=(0, 2, 3, 1)),
                    ),  # size offset dmem_index seg_ptr, reorder -> index siz seg_ptr offset
                    f3d_gbi.G_MODIFYVTX: ("gsSPModifyVertex", PackedFormat(">BHl")),  # enum buf_index new_val
                    f3d_gbi.G_CULLDL: ("gsSPCullDisplayList", PackedFormat(">7B")),  # I'll just be ignoring this anyway
                    f3d_gbi.G_BRANCH_Z: (
                        "gsSPBranchLessZrg",
                        PackedFormat(">15B"),
                    ),  # leads w/ rdp half cmd, deal with later
                    f3d_gbi.G_LOAD_UCODE: (
                        "gsSPLoadUcodeEx",
                        PackedFormat(">15B"),
                    ),  # leads w/ rdp half cmd, deal with later
                    f3d_gbi.G_TRI1: (
                        "gsSP1Triangle",
                        PackedFormat(">7B", make_str=False, reorder=(4, 5 ,6 ,3), post_unpack=lambda args: [a // 2 for a in args]),
                    ),  # pad123 flag v123
                    f3d_gbi.G_TRI2: (
                        "gsSP2Triangles",
                        PackedFormat(">7B", make_str=False, post_unpack=lambda args: [a // 2 for a in args]),
                    ),  # v123 flag v456
                    f3d_gbi.G_POPMTX: ("gsSPPopMatrix", PackedFormat(">3BL")),  # pad123 num_mtx
                }
            )
        self.common_cmd_gbi_names = {
            f3d_gbi.G_NOOP: ("gsDPNoOp", PackedFormat(">7B")),  # pads
            f3d_gbi.G_SPNOOP: ("gsDPNoOp", PackedFormat(">7B")),  # pads
            f3d_gbi.G_ENDDL: ("gsSPEndDisplayList", PackedFormat(">7B")),  # pads
            f3d_gbi.G_DL: ("gsSPDisplayListBin", PackedFormat(">BhL", (2,))),  # branch pad dl_ptr
            f3d_gbi.G_TEXTURE: (
                "gsSPTexture",
                PackedFormat(">7B", reorder=(4, 5, 1, 2, 3), bit_packing=(10, 3, 3, 8, 16, 16)),
            ),  # pad lod_lvl tile en s t, reorder s t lod_lvl tile en
            f3d_gbi.G_SETOTHERMODE_H: (
                "gsSPSetOtherMode_H",
                PackedFormat(">3BL", make_str=False),
            ),  # bit_shift num_bits mode_bits
            f3d_gbi.G_SETOTHERMODE_L: (
                "gsSPSetOtherMode_L",
                PackedFormat(">3BL", make_str=False),
            ),  # bit_shift num_bits mode_bits
            # set other modes
        }
        self.rdp_cmd_gbi_names = {
            f3d_gbi.G_SETCIMG: ("gsDPSetColorImage", PackedFormat(">7B")),  # bpy ignores
            f3d_gbi.G_SETZIMG: ("gsDPSetDepthImage", PackedFormat(">7B")),  # bpy ignores
            f3d_gbi.G_SETTIMG: (
                "gsDPSetTextureImage",
                PackedFormat(">7B", (3,), bit_packing=(3, 2, 19, 32)),
            ),  # fmt siz pad im_ptr
            f3d_gbi.G_SETCOMBINE: (
                "gsDPSetCombineLERP",
                PackedFormat(
                    ">7B",
                    bit_packing=(4, 5, 3, 3, 4, 5, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3),
                    reorder=(0, 6, 1, 10, 2, 11, 3, 12, 4, 7, 5, 13, 8, 14, 9, 15),
                    post_unpack=self.parse_color_combiner,
                ),
            ),  # clr_a_1 clr_c_1 alpha_a_1 alpha_c_1 clr_a_2 clr_c_2 clr_b_1 clr_d_1 alpha_b_1 alpha_d_1 clr_b_2 alpha_a_2 alpha_c_2 clr_d_2 alpha_b_2 alpha_d_2
            f3d_gbi.G_SETENVCOLOR: ("gsDPSetEnvColor", PackedFormat(">Bh4B")),  # pad pad rgba
            f3d_gbi.G_SETPRIMCOLOR: ("gsDPSetPrimColor", PackedFormat(">7B")),  # pad minLod loc_frac rgba
            f3d_gbi.G_SETBLENDCOLOR: ("gsDPSetBlendColor", PackedFormat(">Bh4B")),  # pad pad rgba
            f3d_gbi.G_SETFOGCOLOR: ("gsDPSetFogColor", PackedFormat(">Bh4B")),  # pad pad rgba
            f3d_gbi.G_SETFILLCOLOR: ("gsDPSetFillColor", PackedFormat(">Bh4B")),  # pad pad rgba
            f3d_gbi.G_FILLRECT: (
                "gsDPFillRectangle",
                PackedFormat(">7B", bit_packing=(12, 12, 4, 4, 12, 12)),
            ),  # ul_s ul_t pad tile width height
            f3d_gbi.G_SETTILE: (
                "gsDPSetTile",
                PackedFormat(
                    ">7B",
                    reorder=(0, 1, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13),
                    bit_packing=(3, 2, 1, 9, 9, 5, 3, 4, 2, 4, 4, 2, 4, 4),
                ),
            ),  # fmt siz pad num_64_bit_vals tmem pad tile palette t_flag t_mask t_shift s_flag s_mask s_shift, reoder -> remove pads
            f3d_gbi.G_LOADTILE: (
                "gsDPLoadTile",
                PackedFormat(">7B", bit_packing=(12, 12, 4, 4, 12, 12)),
            ),  # ul_s ul_t pad tile width height
            f3d_gbi.G_LOADBLOCK: (
                "gsDPLoadBlock",
                PackedFormat(">7B", reorder=(3, 0, 1, 4, 5), bit_packing=(12, 12, 4, 4, 12, 12)),
            ),  # ul_s ul_t pad tile texels dxt, reorder -> tile ul_s ul_t texels dxt
            f3d_gbi.G_SETTILESIZE: (
                "gsDPSetTileSize",
                PackedFormat(">7B", bit_packing=(12, 12, 8, 12, 12)),
            ),  # ul_s ul_t tile width height
            f3d_gbi.G_LOADTLUT: (
                "gsDPLoadTLUTCmd",
                PackedFormat(">7B", reorder=(1, 2), bit_packing=(28, 4, 12, 12)),
            ),  # pad tile clr_cnt pad, reorder -> tile clr_cnt
            f3d_gbi.G_RDPSETOTHERMODE: (
                "gsDPSetOtherMode",
                PackedFormat(">3BL"),
            ),  # higher_bits (need to combine) lower_bits
            f3d_gbi.G_SETPRIMDEPTH: ("gsDPSetPrimDepth", PackedFormat(">B3h")),  # pad pad z_val delta_z
            f3d_gbi.G_SETSCISSOR: (
                "gsDPSetScissor",
                PackedFormat(">7B", bit_packing=(12, 12, 4, 4, 12, 12)),
            ),  # ul_x ul_y pad interpolation lr_x lr_y
            f3d_gbi.G_SETCONVERT: (
                "gsDPSetConvert",
                PackedFormat(">7B", bit_packing=(2, 9, 9, 9, 9, 9, 9)),
            ),  # k0 k1 k2 k3 k4 k5
            f3d_gbi.G_SETKEYR: (
                "gsDPSetKeyR",
                PackedFormat(">7B", bit_packing=(28, 12, 8, 8)),
            ),  # pad wnd_r int_r soft_r
            f3d_gbi.G_SETKEYGB: (
                "gsDPSetKeyGB",
                PackedFormat(">7B", bit_packing=(12, 12, 8, 8, 8, 8)),
            ),  # wnd_g wnd_b int_g soft_g int_b soft_b (get proper names for args from gbi)
            f3d_gbi.G_RDPFULLSYNC: ("gsDPFullSync", PackedFormat(">7B")),  # bpy ignores
            f3d_gbi.G_RDPTILESYNC: ("gsDPTileSync", PackedFormat(">7B")),  # bpy ignores
            f3d_gbi.G_RDPPIPESYNC: ("gsDPPipeSync", PackedFormat(">7B")),  # bpy ignores
            f3d_gbi.G_RDPLOADSYNC: ("gsDPLoadSync", PackedFormat(">7B")),  # bpy ignores
            # these are ignored in bpy but I unpack them anyway...
            f3d_gbi.G_TEXRECTFLIP: (
                "gsDPTextureRectangleFlip",
                PackedFormat(">23B", bit_packing=(12, 12, 4, 4, 12, 12, 32, 16, 16, 32, 16, 16)),
            ),  # lr_x lr_y pad tile, ul_x ul_y pad ul_s ul_t pad delta_t delta_s
            f3d_gbi.G_TEXRECT: (
                "gsDPTextureRectangle",
                PackedFormat(">23B", bit_packing=(12, 12, 4, 4, 12, 12, 32, 16, 16, 32, 16, 16)),
            ),  # lr_x lr_y pad tile, ul_x ul_y pad ul_s ul_t pad delta_s delta_t
        }
        self.all_f3d_gbi_cmds = {
            **self.common_cmd_gbi_names,
            **self.rdp_cmd_gbi_names,
            **self.f3d_cmd_gbi_names,
            **self.f3dex_cmd_gbi_names,
            **self.f3dex2_cmd_gbi_names,
        }

    # if binary, entry is a int and self.Gfx is empty
    def get_new_stream(self, entry: Union[str, int]):
        if type(entry) is str:
            return self.Gfx[entry]
        else:
            return None

    def binary_cmd_get(self, parser: Parser) -> tuple[cmd_name:str, PackedFormat]:
        cmd_type = self.unpack_type(parser.cur_stream, parser.head, ">B", make_str=False)
        cmd_name, packed_fmt = self.all_f3d_gbi_cmds.get(cmd_type)
        parser.advance_head(1)
        # tex rects and maybe other cmds are longer
        return cmd_name, packed_fmt

    def binary_cmd_unpack(
        self, parser: Parser, cmd_name: str, packed_fmt: PackedFormat
    ) -> tuple[cmd_args, cmd_len:int]:
        # no cmd data
        if not packed_fmt.format_str:
            cmd_args = []
        else:
            cmd_args = self.unpack_type(parser.cur_stream, parser.head, packed_fmt, ret_iterable=True)
        return cmd_args, packed_fmt.format_size

    def init_stream(self):
        self.VertBuff = [0] * 32  # turbo 3d in shambles
        self.Verts = []
        self.Tris = []
        self.UVs = []
        self.VCs = []
        self.Mats = []
        # merge all lights into single lights dictionary
        self.Lights.update(self.Light_t)
        self.Lights.update(self.Ambient_t)
        self.last_mat.bin_file = self.bin_file

    def parse_stream_DL(self, start_name: Union[str, int]):
        """
        Initialize vars and then parse data stream
        """
        self.init_stream()
        self.parse_stream(self.get_new_stream(start_name), start_name)

    def continue_stream_DL(self, start_name: Union[str, int]):
        """
        Parse stream assuming vars already initialized
        """
        self.parse_stream(self.get_new_stream(start_name), start_name)

    def gsSPEndDisplayList(self, macro: Macro):
        return self._break_parse

    def gsSPDisplayListBin(self, macro: Macro):
        if macro.args[0] == 0:
            return self.gsSPBranchList(macro.partial(macro.args[2]))
        else:
            return self.gsSPDisplayList(macro.partial(macro.args[2]))

    def gsSPBranchList(self, macro: Macro):
        NewDL = self.get_new_stream(branched_dl := macro.args[0])
        # if not NewDL:
        #     raise Exception(
        #         "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
        #             NewDL, self.scene.fast64.sm64.importer.level_name, self.scene.fast64.sm64.importer.level_prefix
        #         )
        #     )
        self.parse_stream_from_start(NewDL, branched_dl)
        return self._break_parse

    def gsSPDisplayList(self, macro: Macro):
        NewDL = self.get_new_stream(branched_dl := macro.args[0])
        # if not NewDL:
        #     raise Exception(
        #         "Could not find DL {} in levels/{}/{}leveldata.inc.c".format(
        #             NewDL, self.scene.fast64.sm64.importer.level_name, self.scene.fast64.sm64.importer.level_prefix
        #         )
        #     )
        self.parse_stream_from_start(NewDL, branched_dl)
        return self._continue_parse

    def f3d_g_vertex_parse(self, args: list[int]):
        return [args[0] + 1, *args[1:]]

    def gsSPVertexBin(self, macro: Macro):
        start = macro.args[1]
        length = macro.args[0]
        v_data = [
            self.unpack_type(self.bin_file, macro.args[2] + off * 0x10, ">3hH2h4B", make_str=False)
            for off in range(length)
        ]

        for k, i in enumerate(range(start, length, 1)):
            self.VertBuff[i] = [v_data[k], start]
        # These are all independent data blocks in blender
        self.Verts.extend([v[0:3] for v in v_data])
        self.UVs.extend([v[4:6] for v in v_data])
        self.VCs.extend([v[6:10] for v in v_data])
        self.LastLoad = length
        return self._continue_parse

    def gsSPVertex(self, macro: Macro):
        # check for ptr arithmatic via array offsets
        if "&" in macro.args[0]:
            offset = hexOrDecInt(re.search("\\[[0-9a-fx]*\\]", macro.args[0]).group(0)[1:-1])
            ref = re.split("\\[[0-9a-fx]*\\]", macro.args[0])[0].split("&")[1]
        # if there is a plus sign check that
        elif "+" in macro.args[0]:
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
        return self._continue_parse

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
        return self._continue_parse

    def gsSP2Triangles(self, macro: Macro):
        self.make_new_material()
        args = [hexOrDecInt(a) for a in macro.args]
        Tri1 = self.parse_tri(args[:3])
        Tri2 = self.parse_tri(args[4:7])
        self.Tris.append(Tri1)
        self.Tris.append(Tri2)
        return self._continue_parse

    def gsSP1Triangle(self, macro: Macro):
        self.make_new_material()
        args = [hexOrDecInt(a) for a in macro.args]
        Tri = self.parse_tri(args[:3])
        self.Tris.append(Tri)
        return self._continue_parse

    # materials
    # Mats will be placed sequentially. The first item of the list is the triangle number
    # The second is the material class
    def gsDPSetRenderMode(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.RenderMode = macro.args
        return self._continue_parse

    # TODO: add support at some point, affects fog, and light color
    def gsMoveWd(self, macro: Macro):
        return self._continue_parse

    # aliased in gbi C macros, the binary version affects lights and matrices
    def gsSPMoveMem(self, macro: Macro):
        # dmem_index siz mem_ptr
        # just check for lights
        dmem_indices = {
            12: "G_MV_POINT",
            14: "G_MV_MATRIX",
            0: "G_MV_LOOKATX",
            24: "G_MV_LOOKATY",
            48: "G_MV_L0",
            72: "G_MV_L1",
            96: "G_MV_L2",
            120: "G_MV_L3",
            144: "G_MV_L5",
            168: "G_MV_L5",
            192: "G_MV_L6",
            216: "G_MV_L7",
            128: "G_MV_VIEWPORT",
            130: "G_MV_LOOKATY",
            132: "G_MV_LOOKATX",
            134: "G_MV_L0",
            136: "G_MV_L1",
            138: "G_MV_L2",
            140: "G_MV_L3",
            142: "G_MV_L4",
            146: "G_MV_L6",
            148: "G_MV_L7",
            150: "G_MV_TXTATT",
            158: "G_MV_MATRIX_1",
            152: "G_MV_MATRIX_2",
            154: "G_MV_MATRIX_3",
            156: "G_MV_MATRIX_4",
        }
        index = dmem_indices.get(macro.args[0], None)
        if "G_MV_L" in index:
            light_num = int(re.search("\d", index).group())
            if light_num >= self.last_mat.num_lights:
                self.last_mat.ambient_light = LightParent.ambient_from_binary(self.bin_file, macro)
            else:
                self.last_mat.light_col[light_num] = LightParent.diffuse_from_binary(self.bin_file, macro)
        return self._continue_parse

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
        return self._continue_parse

    # numlights0 still gives one ambient and diffuse light
    def gsSPNumLights(self, macro: Macro):
        self.NewMat = 1
        num = re.search("\d", macro.args[0]).group()
        num = int(num) if num else 1
        self.last_mat.num_lights = num
        return self._continue_parse

    def gsSPLightColor(self, macro: Macro):
        self.NewMat = 1
        num = re.search("\d", macro.args[0]).group()
        num = int(num) if num else 1
        self.last_mat.light_col[num] = eval(macro.args[-1]).to_bytes(4, "big")
        return self._continue_parse

    # not finished yet
    def gsSPSetLights0(self, macro: Macro):
        return self._continue_parse

    def gsSPSetLights1(self, macro: Macro):
        return self._continue_parse

    def gsSPSetLights2(self, macro: Macro):
        return self._continue_parse

    def gsSPSetLights3(self, macro: Macro):
        return self._continue_parse

    def gsSPSetLights4(self, macro: Macro):
        return self._continue_parse

    def gsSPSetLights5(self, macro: Macro):
        return self._continue_parse

    def gsSPSetLights6(self, macro: Macro):
        return self._continue_parse

    def gsSPSetLights7(self, macro: Macro):
        return self._continue_parse

    # helper for othermode, gets first item from enum
    def first_from_enum(self, enum: list[tuple]):
        return [val[0] for val in enum]

    def gsSPSetOtherMode_H(self, macro: Macro):
        mask = ((1 << macro.args[2]) - 1) << macro.args[1]
        data = macro.args[3] & mask

        def set_mode_data(shift: int, num_bits: int, enum: list[tuple], call: callable, vals: list = None):
            mode_bits = ((1 << num_bits) - 1) << shift
            # for modes that don't use all bit combos
            if not vals:
                vals = range(2**num_bits)
            if mask & mode_bits:
                mode_data = data & mode_bits
                mode_options = {a << shift: self.first_from_enum(enum) for a in vals}
                call(Macro("", mode_options.get(mode_data)))

        set_mode_data(self.f3d_gbi.G_MDSFT_ALPHADITHER, 2, enumAlphaDither, self.gsDPSetAlphaCompare)
        set_mode_data(self.f3d_gbi.G_MDSFT_RGBDITHER, 2, enumRGBDither, self.gsDPSetColorDither)
        set_mode_data(self.f3d_gbi.G_MDSFT_COMBKEY, 1, enumCombKey, self.gsDPSetCombineKey)
        set_mode_data(self.f3d_gbi.G_MDSFT_TEXTCONV, 3, enumTextConv, self.gsDPSetTextureConvert, vals=[0, 5, 6])
        set_mode_data(self.f3d_gbi.G_MDSFT_TEXTFILT, 2, enumTextFilt, self.gsDPSetTextureFilter, vals=[0, 2, 3])
        set_mode_data(self.f3d_gbi.G_MDSFT_TEXTLUT, 2, enumTextLUT, self.gsDPSetTextureLUT, vals=[0, 2, 3])
        set_mode_data(self.f3d_gbi.G_MDSFT_TEXTLOD, 1, enumTextLOD, self.gsDPSetTextureLOD)
        set_mode_data(self.f3d_gbi.G_MDSFT_TEXTDETAIL, 2, enumTextDetail, self.gsDPSetTextureDetail, vals=[0, 2, 3])
        set_mode_data(self.f3d_gbi.G_MDSFT_TEXTPERSP, 1, enumTextPersp, self.gsDPSetTexturePersp)
        set_mode_data(self.f3d_gbi.G_MDSFT_CYCLETYPE, 2, enumCycleType, self.gsDPSetCycleType)
        set_mode_data(self.f3d_gbi.G_MDSFT_COLORDITHER, 1, enumColorDither, self.gsDPSetColorDither)
        set_mode_data(self.f3d_gbi.G_MDSFT_PIPELINE, 1, enumPipelineMode, self.gsDPPipelineMode)
        return self._continue_parse

    def gsSPSetOtherMode_L(self, macro: Macro):
        mask = ((1 << macro.args[2]) - 1) << macro.args[1]
        data = macro.args[3] & mask
        # ignore this for now
        if mask & 0xFFFFFFF8:
            render_mode = data & 0xFFFFFFF8
        if mask & 4:
            mode_data = data & 0x4
            self.gsDPSetDepthSource(macro.partial("G_ZS_PRIM" if mode_data else "G_ZS_PIXEL"))
        if mask & 3:
            mode_data = data & 0x3
            mode_options = {
                0: "G_AC_NONE",
                1 << self.f3d_gbi.G_MDSFT_ALPHACOMPARE: "G_AC_THRESHOLD",
                3 << self.f3d_gbi.G_MDSFT_ALPHACOMPARE: "G_AC_DITHER",
            }
            self.gsDPSetAlphaCompare(macro.partial(mode_options.get(mode_data)))
        return self._continue_parse

    # this is kind of wacky?
    def gsSPSetOtherMode(self, macro: Macro):
        self.NewMat = 1
        if macro.args[0] == "G_SETOTHERMODE_H":
            valid_modes = [
                    enumAlphaDither,
                    enumRGBDither,
                    enumCombKey,
                    enumTextConv,
                    enumTextFilt,
                    enumTextLUT,
                    enumTextLOD,
                    enumTextDetail,
                    enumTextPersp,
                    enumCycleType,
                    enumPipelineMode,
                ]
            for i, othermode in enumerate(macro.args[3].split("|")):
                # this may cause an issue if someone uses a wacky custom othermode H or has it out of order
                mode_h_attr = RDPSettings.other_mode_h_attributes[i][1]
                if othermode.strip() not in {a[0] for a in valid_modes[i]}:
                    continue
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
        return self._continue_parse

    # some independent other mode settings
    def gsDPSetTexturePersp(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textpersp"] = macro.args[0]
        return self._continue_parse

    def gsDPSetDepthSource(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_zsrcsel"] = macro.args[0]
        return self._continue_parse

    def gsDPSetColorDither(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_rgb_dither"] = macro.args[0]
        return self._continue_parse

    def gsDPSetAlphaDither(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_alpha_dither"] = macro.args[0]
        return self._continue_parse

    def gsDPSetCombineKey(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_combkey"] = macro.args[0]
        return self._continue_parse

    def gsDPSetTextureConvert(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textconv"] = macro.args[0]
        return self._continue_parse

    def gsDPSetTextureFilter(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_text_filt"] = macro.args[0]
        return self._continue_parse

    def gsDPSetTextureLOD(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textlod"] = macro.args[0]
        return self._continue_parse

    def gsDPSetTextureDetail(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textdetail"] = macro.args[0]
        return self._continue_parse

    def gsDPSetCycleType(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_cycletype"] = macro.args[0]
        return self._continue_parse

    def gsDPSetTextureLUT(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_textlut"] = macro.args[0]
        return self._continue_parse

    def gsDPPipelineMode(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_pipeline"] = macro.args[0]
        return self._continue_parse

    def gsDPSetAlphaCompare(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.other_mode["g_mdsft_alpha_compare"] = macro.args[0]
        return self._continue_parse

    def gsSPFogFactor(self, macro: Macro):
        return self._continue_parse

    def gsDPSetFogColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.fog_color = macro.args
        return self._continue_parse

    def gsSPFogPosition(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.fog_pos = macro.args
        return self._continue_parse

    def gsDPSetBlendColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.blend_color = macro.args
        return self._continue_parse

    def gsDPSetPrimColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.prim_color = macro.args
        return self._continue_parse

    def gsDPSetEnvColor(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.env_color = macro.args
        return self._continue_parse

    # multiple geo modes can happen in a row that contradict each other
    # this is mostly due to culling wanting diff geo modes than drawing
    # but sometimes using the same vertices
    def parse_geo_flags(self, args: list[int]):
        def get_flags(arg: int):
            used_flags = []
            for flag in self.f3d_gbi.allGeomModeFlags:
                flag_val = getattr(self.f3d_gbi, flag, None)
                if flag_val and ((arg & flag_val) == flag_val):
                    used_flags.append(flag)
            return " | ".join(used_flags)

        return [get_flags(arg) for arg in args]

    def gsSPClearGeometryMode(self, macro: Macro):
        self.NewMat = 1
        args = [a.strip() for a in macro.args[0].split("|")]
        for a in args:
            if a in self.last_mat.GeoSet:
                self.last_mat.GeoSet.remove(a)
        self.last_mat.GeoClear.extend(args)
        return self._continue_parse

    def gsSPSetGeometryMode(self, macro: Macro):
        self.NewMat = 1
        args = [a.strip() for a in macro.args[0].split("|")]
        for a in args:
            if a in self.last_mat.GeoClear:
                self.last_mat.GeoClear.remove(a)
        self.last_mat.GeoSet.extend(args)
        return self._continue_parse

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
        return self._continue_parse

    def gsSPLoadGeometryMode(self, macro: Macro):
        self.NewMat = 1
        geo_set = {a.strip().lower() for a in macro.args[0].split("|")}
        all_geos = set(RDPSettings.geo_mode_attributes.values())
        self.last_mat.GeoSet = list(geo_set)
        self.last_mat.GeoClear = list(all_geos.difference(geo_set))
        return self._continue_parse

    # uses bitwise unpacking
    def parse_color_combiner(self, args: list[int]):
        a = {0: "COMBINED", 1: "TEXEL0", 2: "TEXEL1", 3: "PRIMITIVE", 4: "SHADE", 5: "ENVIRONMENT", 6: "1", 7: "NOISE"}
        b = {
            0: "COMBINED",
            1: "TEXEL0",
            2: "TEXEL1",
            3: "PRIMITIVE",
            4: "SHADE",
            5: "ENVIRONMENT",
            6: "CENTER",
            7: "K4",
        }
        c = {
            0: "COMBINED",
            1: "TEXEL0",
            2: "TEXEL1",
            3: "PRIMITIVE",
            4: "SHADE",
            5: "ENVIRONMENT",
            6: "SCALE",
            7: "COMBINED_ALPHA",
            8: "TEXEL0_ALPHA",
            9: "TEXEL1_ALPHA",
            10: "PRIMITIVE_ALPHA",
            11: "SHADE_ALPHA",
            12: "ENV_ALPHA",
            13: "LOD_FRACTION",
            14: "PRIM_LOD_FRAC",
            15: "K5",
        }
        d = {0: "COMBINED", 1: "TEXEL0", 2: "TEXEL1", 3: "PRIMITIVE", 4: "SHADE", 5: "ENVIRONMENT", 6: "1", 7: "0"}
        aa = {0: "COMBINED", 1: "TEXEL0", 2: "TEXEL1", 3: "PRIMITIVE", 4: "SHADE", 5: "ENVIRONMENT", 6: "1", 7: "0"}
        ba = {0: "COMBINED", 1: "TEXEL0", 2: "TEXEL1", 3: "PRIMITIVE", 4: "SHADE", 5: "ENVIRONMENT", 6: "1", 7: "0"}
        ca = da = aa
        return [d.get(val, 0) for val, d in zip(args, [a, b, c, d, aa, ba, ca, da] * 2)]

    def gsDPSetCombineMode(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.Combiner = self.eval_set_combine_macro(macro.args)
        return self._continue_parse

    def gsDPSetCombineLERP(self, macro: Macro):
        self.NewMat = 1
        self.last_mat.Combiner = macro.args
        return self._continue_parse

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
        self.last_mat.base_tile = TexBase.parse_tile_enum(self.f3d_gbi, macro.args[-2])
        return self._continue_parse

    # last tex is a palette
    def gsDPLoadTLUTCmd(self, macro: Macro):
        if hasattr(self.last_mat, "loadtex"):
            tex = self.last_mat.loadtex
            tile_index = TexBase.parse_tile_enum(self.f3d_gbi, macro.args[0])
            tex.tile = self.last_mat.tiles[tile_index]
            tex.pal = True
            self.last_mat.pal = tex
            self.last_mat.loadtex = None
        else:
            print(
                "**--Load block before set t img, DL is partial and missing context"
                "likely static file meant to be used as a piece of a realtime system.\n"
                "No interpretation on file possible**--"
            )
            return None
        return self._continue_parse

    def gsDPLoadBlock(self, macro: Macro):
        if hasattr(self.last_mat, "loadtex"):
            tex = self.last_mat.loadtex
            # these values aren't necessary when the texture is already in png format
            # texels and dxt commonly use math/expressions
            if "CALC_DXT" in macro.args[4]:
                tex.dxt = 0
                tex.width = hexOrDecInt(re.search("\d+", macro.args[4]).group())
            else:
                tex.dxt = hexOrDecInt(macro.args[4])
            if "*" in macro.args[3]:
                tex.texels = eval(macro.args[3])
            else:
                tex.texels = hexOrDecInt(macro.args[3])
            tile_index = TexBase.parse_tile_enum(self.f3d_gbi, macro.args[0])
            tex.tile = self.last_mat.tiles[tile_index]
            self.last_mat.tmem[tex.tile.tmem] = tex
        else:
            print(
                "**--Load block before set t img, DL is partial and missing context"
                "likely static file meant to be used as a piece of a realtime system.\n"
                "No interpretation on file possible**--"
            )
            return None
        return self._continue_parse

    def gsDPSetTextureImage(self, macro: Macro):
        self.NewMat = 1
        tex_img = macro.args[3]
        fmt = macro.args[0]
        siz = macro.args[1]
        self.last_mat.loadtex = Texture(tex_img, fmt, siz)
        return self._continue_parse

    def gsDPSetTileSize(self, macro: Macro):
        self.NewMat = 1
        tile = self.last_mat.tiles[TexBase.parse_tile_enum(self.f3d_gbi, macro.args[0])]
        tile.Slow = tile.parse_image_frac(macro.args[1])
        tile.Tlow = tile.parse_image_frac(macro.args[2])
        tile.Shigh = tile.parse_image_frac(macro.args[3])
        tile.Thigh = tile.parse_image_frac(macro.args[4])
        return self._continue_parse

    def gsDPSetTile(self, macro: Macro):
        self.NewMat = 1
        tile = self.last_mat.tiles[TexBase.parse_tile_enum(self.f3d_gbi, macro.args[4])]
        tile.tmem = hexOrDecInt(macro.args[3])
        tile.fmt = macro.args[0].strip()
        tile.siz = macro.args[1].strip()
        tile.Tflags = tile.parse_tile_flags(macro.args[6].strip())
        tile.TMask = tile.parse_tile_enum(self.f3d_gbi, macro.args[7])
        tile.TShift = tile.parse_tile_enum(self.f3d_gbi, macro.args[8])
        tile.Sflags = tile.parse_tile_flags(macro.args[9].strip())
        tile.SMask = tile.parse_tile_enum(self.f3d_gbi, macro.args[10])
        tile.SShift = tile.parse_tile_enum(self.f3d_gbi, macro.args[11])
        # on a render tile 4 bit textures will change their size here
        tex = self.last_mat.tmem.get(tile.tmem, None)
        if tex:
            tex.siz = tile.siz
        return self._continue_parse

    # combined macros
    def gsDPLoadTLUT(self, macro: Macro):
        # count, tmemaddr, tex
        args = macro.args
        self.gsDPSetTextureImage(macro.partial("G_IM_FMT_RGBA", "G_IM_SIZ_16b", 1, args[2]))
        self.gsDPSetTile(macro.partial(0, 0, 0, args[1], 7, 0, 0, 0, 0, 0, 0, 0))
        self.gsDPLoadTLUTCmd(macro.partial(7, args[0]))
        return self._continue_parse

    def gsDPLoadTextureBlock(self, macro: Macro):
        # 0tex, 1fmt, 2siz, 3height, 4width, 5pal, 6flags, 8masks, 10shifts
        args = macro.args
        fmt = TexBase.parse_timg_format(args[1])
        siz = TexBase.parse_timg_format(args[2])
        self.gsDPSetTextureImage(macro.partial(fmt, siz, 1, args[0]))
        self.gsDPSetTile(macro.partial(fmt, siz, 0, 0, 7, 0, args[7], args[9], args[11], args[6], args[8], args[10]))
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, "0", "0"))  # I don't need args
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(
            macro.partial(fmt, siz, 0, 0, 0, args[5], args[7], args[9], args[11], args[6], args[8], args[10])
        )
        self.gsDPSetTileSize(macro.partial(7, 0, 0, (hexOrDecInt(args[4]) - 1) << 2, (hexOrDecInt(args[3]) - 1) << 2))

        return self._continue_parse

    def gsDPLoadTextureBlockS(self, macro: Macro):
        # only changes dxt and that doesn't matter here
        return self.gsDPLoadTextureBlock(macro)

    def _gsDPLoadTextureBlock(self, macro: Macro):
        # 0tex, 1tmem, 2fmt, 3siz, 4height, 5width, 6pal, 7flags, 9masks, 11shifts
        args = macro.args
        fmt = TexBase.parse_timg_format(args[2])
        siz = TexBase.parse_timg_format(args[3])
        self.gsDPSetTextureImage(macro.partial(fmt, siz, 1, args[0]))
        self.gsDPSetTile(macro.partial(fmt, siz, 0, 0, 7, 0, args[8], args[10], args[12], args[7], args[9], args[11]))
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, "0", "0"))
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(
            macro.partial(fmt, siz, 0, 0, 0, args[5], args[7], args[9], args[11], args[6], args[8], args[10])
        )
        self.gsDPSetTileSize(macro.partial(7, 0, 0, (hexOrDecInt(args[4]) - 1) << 2, (hexOrDecInt(args[3]) - 1) << 2))
        return self._continue_parse

    def gsDPLoadTextureBlock_4b(self, macro: Macro):
        # 0tex, 1fmt, 2height, 3width, 4pal, 5flags, 7masks, 9shifts
        args = macro.args
        fmt = TexBase.parse_timg_format(args[1])
        self.gsDPSetTextureImage(macro.partial(fmt, "G_IM_SIZ_16b", 1, args[0]))
        self.gsDPSetTile(
            macro.partial(fmt, "G_IM_SIZ_16b", 0, 0, 7, 0, args[6], args[8], args[10], args[5], args[7], args[9])
        )
        # self.gsDPLoadSync(macro)
        self.gsDPLoadBlock(macro.partial(7, 0, 0, "0", "0"))
        # self.gsDPPipeSync(macro)
        self.gsDPSetTile(
            macro.partial(fmt, "G_IM_SIZ_4b", 0, 0, 0, args[4], args[3], args[8], args[10], args[3], args[7], args[9])
        )
        self.gsDPSetTileSize(macro.partial(7, 0, 0, (hexOrDecInt(args[4]) - 1) << 2, (hexOrDecInt(args[3]) - 1) << 2))
        return self._continue_parse

    def gsDPLoadTextureBlock_4bs(self, macro: Macro):
        # only changes dxt and that doesn't matter here
        return self.gsDPLoadTextureBlock_4b(macro)

    # other stuff that probably doesn't matter since idk who uses these
    # if they break make an issue
    # _gsDPLoadTextureBlockTile
    # gsDPLoadMultiBlock
    # gsDPLoadMultiBlockS

    # turn member of vtx str arr into vtx args
    def parse_vert(self, Vert: str):
        v = Vert.replace("{", "").replace("}", "").split(",")
        num = lambda x: [eval_or_int(a) for a in x]
        pos = num(v[:3])
        uv = num(v[4:6])
        vc = num(v[6:10])
        return [pos, uv, vc]

    # given tri args in gbi cmd, give appropriate tri indices in vert list
    def parse_tri(self, Tri: list[int]):
        L = len(self.Verts)
        return [a + L - self.LastLoad for a in Tri]

    def make_new_material(self):
        if self.NewMat:
            self.NewMat = 0
            self.Mats.append([len(self.Tris) - 1, self.last_mat])
            self.last_mat = deepcopy(self.last_mat)  # for safety
            self.last_mat_dict[self.last_mat.layer] = self.last_mat

    def eval_set_combine_macro(self, arg: str):
        return getattr(self.f3d_gbi, arg[0], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"]) + getattr(
            self.f3d_gbi, arg[1], ["TEXEL0", "0", "SHADE", "0", "TEXEL0", "0", "SHADE", "0"]
        )
