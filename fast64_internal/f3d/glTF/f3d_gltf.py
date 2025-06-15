from dataclasses import dataclass
from math import ceil, floor
import copy
import bpy
import numpy as np

from bpy.types import NodeTree, Mesh, Material, Context, Panel, PropertyGroup, UILayout
from bpy.props import BoolProperty

from ...utility import (
    json_to_prop_group,
    multilineLabel,
    prop_group_to_json,
    prop_split,
    PluginError,
    fix_invalid_props,
)
from ...gltf_utility import (
    GlTF2SubExtension,
    get_gltf_image_from_blender_image,
    get_gltf_settings,
    is_import_context,
    swap_function,
    suffix_function,
    get_version,
)
from ..f3d_gbi import F3D, get_F3D_GBI
from ..f3d_material import (
    all_combiner_uses,
    get_color_info_from_tex,
    link_if_none_exist,
    remove_first_link_if_exists,
    rendermode_presets_checks,
    trunc_10_2,
    createScenePropertiesForMaterial,
    get_f3d_node_tree,
    update_all_node_values,
    update_blend_method,
    get_textlut_mode,
    F3DMaterialProperty,
    RDPSettings,
    TextureProperty,
    F3D_MAT_CUR_VERSION,
)
from ..f3d_material_helpers import node_tree_copy
from ..f3d_writer import cel_shading_checks, check_face_materials, getColorLayer
from ..f3d_texture_writer import UVtoSTLarge

MATERIAL_EXTENSION_NAME = "FAST64_materials_n64"
F3D_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3d"
EX1_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dlx"
EX3_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dex3"
SAMPLER_EXTENSION_NAME = "FAST64_sampler_n64"
MESH_EXTENSION_NAME = "FAST64_mesh_f3d"
NEW_MESH_EXTENSION_NAME = "FAST64_mesh_f3d_new"


def is_mat_f3d(mat: Material | None) -> bool:
    return mat is not None and mat.is_f3d and mat.mat_ver == F3D_MAT_CUR_VERSION


def mesh_has_f3d_mat(mesh: Mesh):
    return any(is_mat_f3d(mat) for mat in mesh.materials)


def get_settings(context: Context | None = None):
    context = context or bpy.context
    return context.scene.fast64.settings.glTF.f3d


def uvmap_check(mesh: Mesh):
    # If there is a F3D material check if the mesh has a uvmap
    if mesh_has_f3d_mat(mesh) and not any(layer.name == "UVMap" for layer in mesh.uv_layers):
        raise PluginError('Object with F3D materials does not have a "UVMap" uvmap layer.')


def large_tex_checks(materials: list[Material], mesh: Mesh):
    """
    See TileLoad.initWithFace for the usual exporter version of this function
    This strips out any exporting and focous on just error checking
    """

    large_props_dict = {}
    for mat in mesh.materials:  # Cache info on any large tex material that needs to be checked
        if not (is_mat_f3d(mat) and mat.f3d_mat.use_large_textures):
            continue
        f3d_mat: F3DMaterialProperty = mat.f3d_mat
        use_dict = all_combiner_uses(f3d_mat)
        textures: list[TextureProperty] = []
        if use_dict["Texture 0"] and f3d_mat.tex0.tex_set:
            textures.append(f3d_mat.tex0)
        if use_dict["Texture 1"] and f3d_mat.tex1.tex_set:
            textures.append(f3d_mat.tex1)

        if len(textures) == 0:
            continue
        texture = textures[0]

        tex_sizes = [tex.tex_size for tex in textures]
        tmem = sum(tex.word_usage for tex in textures)
        tmem_size = 256 if texture.is_ci else 512
        if tmem <= tmem_size:
            continue  # Can fit in TMEM without large mode, so skip
        widths, heights = zip(*tex_sizes)
        large_props_dict[mat.name] = {
            "clamp": f3d_mat.large_edges == "Clamp",
            "point": f3d_mat.rdp_settings.g_mdsft_text_filt == "G_TF_POINT",
            "dimensions": (min(widths), min(heights)),
            "format": texture.tex_format,
            "texels_per_word": 64 // sum(texture.format_size for texture in textures),
            "is_4bit": any(tex.format_size == 4 for tex in textures),
            "large_tex_words": tmem_size,
        }

    def get_low(large_props, value, field):
        value = floor(value)
        if large_props["clamp"]:
            value = min(max(value, 0), large_props["dimensions"][field] - 1)
        if large_props["is_4bit"] and field == 0:
            # Must start on an even texel (round down)
            value &= ~1
        return value

    def get_high(large_props, value, field):
        value = ceil(value) - (1 if large_props["point"] else 0)
        if large_props["clamp"]:
            value = min(max(value, 0), large_props["dimensions"][field] - 1)
        if large_props["is_4bit"] and field == 0:
            value |= 1
        return value

    def fix_region(large_props, sl, sh, tl, th):
        dimensions = large_props["dimensions"]
        assert sl <= sh and tl <= th
        soffset = int(floor(sl / dimensions[0])) * dimensions[0]
        toffset = int(floor(tl / dimensions[1])) * dimensions[1]
        sl -= soffset
        sh -= soffset
        tl -= toffset
        th -= toffset
        assert 0 <= sl < dimensions[0] and 0 <= tl < dimensions[1]

        if sh >= 1024 or th >= 1024:
            return False
        texels_per_word = large_props["texels_per_word"]
        if sh >= dimensions[0]:
            if texels_per_word > dimensions[0]:
                raise PluginError(f"Large texture must be at least {texels_per_word} wide.")
            sl -= dimensions[0]
            sl = int(floor(sl / texels_per_word)) * texels_per_word
            sl += dimensions[0]
        if th >= dimensions[1]:
            tl -= dimensions[1]
            tl = int(floor(tl / 2.0)) * 2
            tl += dimensions[1]

        def get_tmem_usage(width, height, texels_per_word=texels_per_word):
            return (width + texels_per_word - 1) // texels_per_word * height

        tmem_usage = get_tmem_usage(sh - sl + 1, th - tl + 1)
        return tmem_usage <= large_props["large_tex_words"]

    if not large_props_dict:
        return

    if "UVMap" not in mesh.uv_layers:
        raise PluginError('Cannot do large texture checks without a "UVMap" uvmap layer.')
    uv_data = mesh.uv_layers["UVMap"].data
    for face in mesh.loop_triangles:
        material = materials[face.material_index]
        if material is None:
            continue
        mat_name: str = material.name
        large_props = large_props_dict.get(mat_name)
        if large_props is None:
            continue

        dimensions = large_props["dimensions"]
        face_uvs = [UVtoSTLarge(None, loop_index, uv_data, dimensions) for loop_index in face.loops]
        sl, sh, tl, th = 1000000, -1, 1000000, -1
        for point in face_uvs:
            sl = min(sl, get_low(large_props, point[0], 0))
            sh = max(sh, get_high(large_props, point[0], 0))
            tl = min(tl, get_low(large_props, point[1], 1))
            th = max(th, get_high(large_props, point[1], 1))

        if fix_region(large_props, sl, sh, tl, th):
            continue  # Region fits in TMEM
        if sh >= 1024 or th >= 1024:
            raise PluginError(
                f"Large texture material {mat_name} has a face that needs"
                f" to cover texels {sl}-{sh} x {tl}-{th}"
                f" (image dims are {dimensions}), but image space"
                " only goes up to 1024 so this cannot be represented."
            )
        else:
            raise PluginError(
                f"Large texture material {mat_name} has a face that needs"
                f" to cover texels {sl}-{sh} x {tl}-{th}"
                f" ({sh-sl+1} x {th-tl+1} texels) "
                f"in format {large_props['format']}, which can't fit in TMEM."
            )


def multitex_checks(raise_large_multitex: bool, f3d_mat: F3DMaterialProperty):
    tex0: TextureProperty = f3d_mat.tex0
    tex1: TextureProperty = f3d_mat.tex1
    both_reference = tex0.use_tex_reference and tex1.use_tex_reference
    same_reference = both_reference and tex0.tex_reference == tex1.tex_reference
    same_textures = same_reference or (not both_reference and tex0.tex == tex1.tex)
    both_ci8 = tex0.tex_format == tex1.tex_format == "CI8"

    tex0_size, tex1_size = tex0.tex_size, tex1.tex_size
    tex0_tmem, tex1_tmem = tex0.word_usage, tex1.word_usage
    tmem = tex0_tmem if same_textures else tex0_tmem + tex1_tmem
    tmem_size = 256 if tex0.is_ci and tex1.is_ci else 512

    if same_reference and tex0_size != tex1_size:
        raise PluginError("Textures with the same reference must have the same size.")

    if raise_large_multitex and f3d_mat.use_large_textures:
        if tex0_tmem > tmem_size // 2 and tex1_tmem > tmem_size // 2:
            raise PluginError("Cannot multitexture with two large textures.")
        if same_textures:
            raise PluginError(
                "Cannot use the same texture for Tex 0 and 1 when using large textures.",
            )
    if not f3d_mat.use_large_textures and tmem > tmem_size:
        raise PluginError(
            "Textures are too big. Max TMEM size is 4kb, ex. 2 32x32 RGBA 16 bit textures.\n"
            "Note that width needs to be padded to 64-bit boundaries.",
        )

    if tex0.is_ci != tex1.is_ci:
        raise PluginError("Can't have a CI + non-CI texture. Must be both or neither CI.")
    if not (tex0.is_ci and tex1.is_ci):
        return

    # CI multitextures
    same_pal_reference = both_reference and tex0.pal_reference == tex1.pal_reference
    if tex0.ci_format != tex1.ci_format:
        raise PluginError(
            "Both CI textures must use the same palette format (usually RGBA16).",
        )
    if same_pal_reference and tex0.pal_reference_size != tex1.pal_reference_size:
        raise PluginError(
            "Textures with the same palette reference must have the same palette size.",
        )
    if tex0.use_tex_reference != tex1.use_tex_reference and both_ci8:
        # TODO: If flipbook is ever implemented, check if the reference is set by the flipbook
        # Theoretically possible if there was an option to have half the palette for each
        raise PluginError("Can't have two CI8 textures where only one is a reference; no way to assign the palette.")
    if both_reference and both_ci8 and not same_pal_reference:
        raise PluginError("Can't have two CI8 textures with different palette references.")

    # TODO: When porting ac f3dzex, skip this check
    rgba_colors = get_color_info_from_tex(tex0.tex)[3]
    rgba_colors.update(get_color_info_from_tex(tex1.tex)[3])
    if len(rgba_colors) > 256:
        raise PluginError(
            f"The two CI textures together contain a total of {len(rgba_colors)} colors,\n"
            "which can't fit in a CI8 palette (256)."
        )


# Ideally we'd use mathutils.Color here but it does not support alpha (and mul for some reason)
@dataclass
class Color:
    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 0.0

    def wrap(self, min_value: float, max_value: float):
        def wrap_value(value, min_value=min_value, max_value=max_value):
            range_width = max_value - min_value
            return ((value - min_value) % range_width) + min_value

        return Color(wrap_value(self.r), wrap_value(self.g), wrap_value(self.b), wrap_value(self.a))

    def to_clean_list(self):
        def round_and_clamp(value):
            return round(max(min(value, 1.0), 0.0), 4)

        return [
            round_and_clamp(self.r),
            round_and_clamp(self.g),
            round_and_clamp(self.b),
            round_and_clamp(self.a),
        ]

    def __sub__(self, other):
        return Color(self.r - other.r, self.g - other.g, self.b - other.b, self.a - other.a)

    def __add__(self, other):
        return Color(self.r + other.r, self.g + other.g, self.b + other.b, self.a + other.a)

    def __mul__(self, other):
        return Color(self.r * other.r, self.g * other.g, self.b * other.b, self.a * other.a)


def get_color_component(inp: str, data: dict, previous_alpha: float) -> float:
    if inp == "0":
        return 0.0
    elif inp == "1":
        return 1.0
    elif inp.startswith("COMBINED"):
        return previous_alpha
    elif inp == "LOD_FRACTION":
        return 0.0  # Fast64 always uses black, let's do that for now
    elif inp.startswith("PRIM"):
        prim = data["primitive"]
        if inp == "PRIM_LOD_FRAC":
            return prim["loDFraction"]
        if inp == "PRIMITIVE_ALPHA":
            return prim["color"][3]
    elif inp == "ENV_ALPHA":
        return data["environment"]["color"][3]
    elif inp.startswith("K"):
        values = data["yuvConvert"]["values"]
        if inp == "K4":
            return values[4]
        if inp == "K5":
            return values[5]


def get_color_from_input(inp: str, previous_color: Color, data: dict, is_alpha: bool, default_color: Color) -> Color:
    if inp == "COMBINED" and not is_alpha:
        return previous_color
    elif inp == "CENTER":
        return Color(*data["chromaKey"]["center"], 1.0)
    elif inp == "SCALE":
        return Color(*data["chromaKey"]["scale"], 1.0)
    elif inp == "PRIMITIVE":
        return Color(*data["primitive"]["color"])
    elif inp == "ENVIRONMENT":
        return Color(*data["environment"]["color"])
    else:
        value = get_color_component(inp, data, previous_color.a)
        if value:
            return Color(value, value, value, value)
        return default_color


def fake_color_from_cycle(cycle: list[str], previous_color: Color, data: dict, is_alpha=False):
    default_colors = [Color(1.0, 1.0, 1.0, 1.0), Color(), Color(1.0, 1.0, 1.0, 1.0), Color()]
    a, b, c, d = [
        get_color_from_input(inp, previous_color, data, is_alpha, default_color)
        for inp, default_color in zip(cycle, default_colors)
    ]
    sign_extended_c = c.wrap(-1.0, 1.0001)
    unwrapped_result = (a - b) * sign_extended_c + d
    result = unwrapped_result.wrap(-0.5, 1.5)
    if is_alpha:
        result = Color(previous_color.r, previous_color.g, previous_color.b, result.a)
    return result


def get_fake_color(data: dict):
    fake_color = Color()
    for cycle in data["combiner"]["cycles"]:  # Try to emulate solid colors
        fake_color = fake_color_from_cycle(cycle["color"], fake_color, data)
        fake_color = fake_color_from_cycle(cycle["alpha"], fake_color, data, True)
    return fake_color.to_clean_list()


class F3DExtensions(GlTF2SubExtension):
    settings: "F3DGlTFSettings" = None
    gbi: F3D = None
    base_node_tree: NodeTree = None

    def post_init(self):
        self.settings = self.extension.settings.f3d
        self.gbi: F3D = get_F3D_GBI()

        if not self.extension.importing:
            return
        try:
            self.print_verbose("Linking F3D material library and caching F3D node tree")
            self.base_node_tree = get_f3d_node_tree()
        except Exception as exc:
            raise PluginError(f"Failed to import F3D node tree: {str(exc)}") from exc

    def sampler_from_f3d(self, f3d_mat: F3DMaterialProperty, f3d_tex: TextureProperty):
        from io_scene_gltf2.io.com import gltf2_io  # pylint: disable=import-error

        if get_version() >= (4, 3, 13):
            from io_scene_gltf2.io.com.constants import TextureFilter, TextureWrap  # pylint: disable=import-error
        else:
            from io_scene_gltf2.io.com.gltf2_io_constants import (
                TextureFilter,
                TextureWrap,
            )  # pylint: disable=import-error

        wrap = []
        for field in ["S", "T"]:
            field_prop = getattr(f3d_tex, field)
            wrap.append(
                TextureWrap.ClampToEdge
                if field_prop.clamp
                else TextureWrap.MirroredRepeat
                if field_prop.mirror
                else TextureWrap.Repeat
            )

        nearest = f3d_mat.rdp_settings.g_mdsft_text_filt == "G_TF_POINT"
        mag_f = TextureFilter.Nearest if nearest else TextureFilter.Linear
        min_f = TextureFilter.NearestMipmapNearest if nearest else TextureFilter.LinearMipmapLinear
        sampler = gltf2_io.Sampler(
            extensions=None,
            extras=None,
            mag_filter=mag_f,
            min_filter=min_f,
            name=None,
            wrap_s=wrap[0],
            wrap_t=wrap[1],
        )
        self.append_extension(sampler, SAMPLER_EXTENSION_NAME, f3d_tex.to_dict())
        return sampler

    def sampler_to_f3d(self, gltf2_sampler, f3d_tex: TextureProperty):
        data = self.get_extension(gltf2_sampler, SAMPLER_EXTENSION_NAME)
        if data is None:
            return
        f3d_tex.from_dict(data)

    def f3d_to_gltf2_texture(
        self,
        f3d_mat: F3DMaterialProperty,
        f3d_tex: TextureProperty,
        export_settings: dict,
    ):
        from io_scene_gltf2.io.com import gltf2_io  # pylint: disable=import-error

        img = f3d_tex.tex
        if img is not None:
            source = get_gltf_image_from_blender_image(img.name, export_settings)

            if self.settings.raise_texture_limits and f3d_tex.tex_set:
                tex_size = f3d_tex.tex_size
                tmem_usage = f3d_tex.word_usage
                tmem_max = 256 if f3d_tex.is_ci else 512

                if f3d_mat.use_large_textures and tex_size[0] > 1024 or tex_size[1] > 1024:
                    raise PluginError(
                        "Texture size (even large textures) limited to 1024 pixels in each dimension.",
                    )
                if not f3d_mat.use_large_textures and tmem_usage > tmem_max:
                    raise PluginError(
                        f"Texture is too large: {tmem_usage} / {tmem_max} bytes.\n"
                        "Note that width needs to be padded to 64-bit boundaries."
                    )
                if f3d_tex.is_ci and not f3d_tex.use_tex_reference:
                    _, _, _, rgba_colors = get_color_info_from_tex(img)
                    if len(rgba_colors) > 2**f3d_tex.format_size:
                        raise PluginError(
                            f"Too many colors for {f3d_tex.tex_format}: {len(rgba_colors)}",
                        )
        else:  # Image isn´t set
            if f3d_tex.tex_set and not f3d_tex.use_tex_reference:
                raise PluginError("Non texture reference must have an image.")
            source = None
        sampler = self.sampler_from_f3d(f3d_mat, f3d_tex)
        return gltf2_io.Texture(
            extensions=None,
            extras=None,
            name=source.name if source else None,
            sampler=sampler,
            source=source,
        )

    def gltf2_to_f3d_texture(self, gltf2_texture, gltf, f3d_tex: TextureProperty):
        if get_version() >= (4, 3, 13):
            from io_scene_gltf2.blender.imp.image import (
                BlenderImage,
            )  # pylint: disable=import-error, import-outside-toplevel
        else:
            from io_scene_gltf2.blender.imp.gltf2_blender_image import (
                BlenderImage,
            )  # pylint: disable=import-error, import-outside-toplevel

        if gltf2_texture.sampler is not None:
            sampler = gltf.data.samplers[gltf2_texture.sampler]
            self.sampler_to_f3d(sampler, f3d_tex)
        if gltf2_texture.source is not None:
            BlenderImage.create(gltf, gltf2_texture.source)
            img = gltf.data.images[gltf2_texture.source]
            blender_image_name = img.blender_image_name
            if blender_image_name:
                f3d_tex.tex = bpy.data.images[blender_image_name]
                f3d_tex.tex.colorspace_settings.name = "sRGB"

    def f3d_to_glTF2_texture_info(
        self,
        f3d_mat: F3DMaterialProperty,
        f3d_tex: TextureProperty,
        num: int,
        export_settings: dict,
    ):
        from io_scene_gltf2.io.com import gltf2_io  # pylint: disable=import-error

        try:
            texture = self.f3d_to_gltf2_texture(f3d_mat, f3d_tex, export_settings)
        except Exception as exc:
            raise PluginError(f"Failed to create texture {num}: {str(exc)}") from exc
        tex_info = gltf2_io.TextureInfo(
            index=texture,
            extensions=None,
            extras=None,
            tex_coord=None,
        )

        def to_offset(low: float, tex_size: int):
            return trunc_10_2(low) * (1.0 / tex_size)

        transform_data = {}
        size = f3d_tex.tex_size
        if size != [0, 0]:
            offset = [to_offset(f3d_tex.S.low, size[0]), to_offset(f3d_tex.T.low, size[1])]
            if offset != [0.0, 0.0]:
                transform_data = {"offset": offset}

        scale = [2.0 ** (f3d_tex.S.shift * -1.0), 2.0 ** (f3d_tex.T.shift * -1.0)]
        if scale != [1.0, 1.0]:
            transform_data["scale"] = scale

        if transform_data:
            self.append_extension(tex_info, "KHR_texture_transform", transform_data)
        return tex_info

    def gather_material_hook(self, gltf2_material, blender_material: Material, export_settings: dict):
        if not blender_material.is_f3d:
            if self.settings.raise_non_f3d_mat:
                raise PluginError(
                    'Material is not an F3D material. Turn off "Non F3D Material" to ignore.',
                )
            return
        if blender_material.mat_ver < F3D_MAT_CUR_VERSION:
            raise PluginError(
                f"Material is an F3D material but its version is too old ({blender_material.mat_ver}).",
            )

        f3d_mat: F3DMaterialProperty = blender_material.f3d_mat
        fix_invalid_props(f3d_mat)
        rdp: RDPSettings = f3d_mat.rdp_settings

        if self.settings.raise_texture_limits:
            if f3d_mat.is_multi_tex and (f3d_mat.tex0.tex_set and f3d_mat.tex1.tex_set):
                multitex_checks(self.settings.raise_large_multitex, f3d_mat)
        if self.settings.raise_rendermode:
            if rdp.set_rendermode and not rdp.rendermode_advanced_enabled:
                rendermode_presets_checks(f3d_mat)

        use_dict = all_combiner_uses(f3d_mat)
        n64_data = {
            "combiner": f3d_mat.combiner_to_dict(),
            **f3d_mat.n64_colors_to_dict(use_dict),
            "otherModes": (
                {
                    **rdp.other_mode_h_to_dict(True, lut_format=get_textlut_mode(f3d_mat)),
                    **rdp.other_mode_l_to_dict(True),
                }
            ),
        }
        if rdp.g_mdsft_zsrcsel == "G_ZS_PRIM":
            n64_data["primDepth"] = rdp.prim_depth.to_dict()
        if rdp.g_mdsft_textlod == "G_TL_LOD":
            n64_data.update({"mipmapCount": rdp.num_textures_mipmapped})
        n64_data.update(f3d_mat.extra_texture_settings_to_dict())

        textures = {}
        n64_data["textures"] = textures
        if use_dict["Texture 0"]:
            textures["0"] = self.f3d_to_glTF2_texture_info(
                f3d_mat,
                f3d_mat.tex0,
                0,
                export_settings,
            )
        if use_dict["Texture 1"]:
            textures["1"] = self.f3d_to_glTF2_texture_info(
                f3d_mat,
                f3d_mat.tex1,
                1,
                export_settings,
            )
        n64_data["extensions"] = {}

        f3d_data = {"geometryMode": rdp.f3d_geo_mode_to_dict()}
        if rdp.clip_ratio != 2:
            f3d_data["clipRatio"] = rdp.clip_ratio
        f3d_data.update({**f3d_mat.f3d_colors_to_dict(use_dict), "extensions": {}})
        if self.gbi.F3DEX_GBI:  # F3DLX
            f3d_data["extensions"][EX1_MATERIAL_EXTENSION_NAME] = self.extension.Extension(
                name=EX1_MATERIAL_EXTENSION_NAME,
                extension={"geometryMode": rdp.f3dlx_geo_mode_to_dict()},
                required=False,
            )
        if self.gbi.F3DEX_GBI_3:  # F3DEX3
            if f3d_mat.use_cel_shading:
                cel_shading_checks(f3d_mat)
            f3d_data["extensions"][EX3_MATERIAL_EXTENSION_NAME] = self.extension.Extension(
                name=EX3_MATERIAL_EXTENSION_NAME,
                extension={
                    "geometryMode": rdp.f3dex3_geo_mode_to_dict(),
                    **f3d_mat.f3dex3_colors_to_dict(),
                },
                required=False,
            )

        n64_data["extensions"][F3D_MATERIAL_EXTENSION_NAME] = self.extension.Extension(
            name=F3D_MATERIAL_EXTENSION_NAME,
            extension=f3d_data,
            required=False,
        )

        self.append_extension(gltf2_material, MATERIAL_EXTENSION_NAME, n64_data)

        # glTF Standard
        pbr = gltf2_material.pbr_metallic_roughness
        if f3d_mat.is_multi_tex:
            pbr.base_color_texture = textures["0"]
            pbr.metallic_roughness_texture = textures["1"]
        elif textures:
            pbr.base_color_texture = list(textures.values())[0]
        pbr.base_color_factor = get_fake_color(n64_data)

        if not f3d_mat.rdp_settings.g_lighting:
            self.append_extension(gltf2_material, "KHR_materials_unlit")

    def gather_mesh_hook(
        self, gltf2_mesh, blender_mesh, _blender_object, _vertex_groups, _modifiers, materials, _export_settings
    ):
        if self.settings.raise_bad_mat_slot:
            if len(blender_mesh.materials) == 0 or len(materials) == 0:
                raise PluginError("Object does not have any materials.")
            check_face_materials(
                gltf2_mesh.name,
                materials,
                blender_mesh.polygons,
                self.settings.raise_non_f3d_mat,
            )
        if self.settings.raise_no_uvmap:
            uvmap_check(blender_mesh)
        if self.settings.raise_large_tex:
            large_tex_checks(materials, blender_mesh)

    def gather_node_hook(self, gltf2_node, blender_object, _export_settings: dict):
        if gltf2_node.mesh and not self.gbi.F3D_OLD_GBI and not blender_object.use_f3d_culling:
            self.append_extension(
                gltf2_node.mesh,
                MESH_EXTENSION_NAME,
                {
                    "extensions": {
                        NEW_MESH_EXTENSION_NAME: self.extension.Extension(
                            name=NEW_MESH_EXTENSION_NAME,
                            extension={"use_culling": False},
                            required=False,
                        )
                    }
                },
            )

    # Importing

    def gather_import_material_after_hook(
        self,
        gltf_material,
        _vertex_color,
        blender_material: Material,
        gltf,
    ):
        n64_data = self.get_extension(gltf_material, MATERIAL_EXTENSION_NAME)
        if n64_data is None:
            return

        try:
            blender_material.f3d_update_flag = True

            f3d_mat: F3DMaterialProperty = blender_material.f3d_mat
            rdp: RDPSettings = f3d_mat.rdp_settings
            f3d_mat.combiner_from_dict(n64_data.get("combiner", {}))
            f3d_mat.n64_colors_from_dict(n64_data)
            other_modes = n64_data.get("otherModes", {})
            rdp.other_mode_h_from_dict(other_modes)
            rdp.other_mode_l_from_dict(other_modes)
            rdp.prim_depth.from_dict(n64_data.get("primDepth", {}))
            f3d_mat.extra_texture_settings_from_dict(n64_data)
            rdp.num_textures_mipmapped = n64_data.get("mipmapCount", 2)

            for num, tex_info in n64_data.get("textures", {}).items():
                index = tex_info["index"]
                self.print_verbose(f"Importing F3D texture {index}")
                gltf2_texture = gltf.data.textures[index]
                if num == "0":
                    self.gltf2_to_f3d_texture(gltf2_texture, gltf, f3d_mat.tex0)
                elif num == "1":
                    self.gltf2_to_f3d_texture(gltf2_texture, gltf, f3d_mat.tex1)
                else:
                    raise PluginError("Fast64 currently only supports the first two textures")

            f3d_data = n64_data.get("extensions", {}).get(F3D_MATERIAL_EXTENSION_NAME, None)
            if f3d_data:
                rdp.clip_ratio = f3d_data.get("clipRatio", 2)
                f3d_mat.f3d_colors_from_dict(f3d_data)
                rdp.f3d_geo_mode_from_dict(f3d_data.get("geometryMode", []))

                ex1_data = f3d_data.get("extensions", {}).get(EX1_MATERIAL_EXTENSION_NAME, None)
                if ex1_data is not None:  # F3DLX
                    f3d_mat.rdp_settings.f3dex1_geo_mode_from_dict(ex1_data.get("geometryMode", {}))

                ex3_data = f3d_data.get("extensions", {}).get(EX3_MATERIAL_EXTENSION_NAME, None)
                if ex3_data is not None:  # F3DEX3
                    f3d_mat.rdp_settings.f3dex3_geo_mode_from_dict(ex3_data.get("geometryMode", {}))
                    f3d_mat.f3dex3_colors_from_dict(ex3_data)
        except Exception as exc:
            raise Exception(  # pylint: disable=broad-exception-raised
                f"Failed to import fast64 extension data:\n{str(exc)}",
            ) from exc
        finally:
            blender_material.f3d_update_flag = False
        blender_material.is_f3d = True
        blender_material.mat_ver = F3D_MAT_CUR_VERSION

        self.print_verbose(
            "Copying F3D node tree, creating scene properties and updating all nodes",
        )
        try:
            node_tree_copy(self.base_node_tree, blender_material.node_tree)
            createScenePropertiesForMaterial(blender_material)
            with bpy.context.temp_override(material=blender_material):
                update_all_node_values(blender_material, bpy.context)
        except Exception as exc:
            raise Exception(  # pylint: disable=broad-exception-raised
                f"Error creating F3D node tree:\n{str(exc)}",
            ) from exc

    def gather_import_node_after_hook(self, _vnode, gltf_node, blender_object, _gltf):
        data = self.get_extension(gltf_node, MESH_EXTENSION_NAME)
        if data is None:
            return
        new_data = data.get("extensions", {}).get(NEW_MESH_EXTENSION_NAME, None)
        if new_data:
            blender_object.use_f3d_culling = new_data.get("use_culling", True)

    def gather_import_mesh_after_hook(self, gltf_mesh, blender_mesh, gltf):
        if len(blender_mesh.vertex_colors) < 1 or not mesh_has_f3d_mat(blender_mesh):
            return
        color_layer = blender_mesh.vertex_colors[0]
        color_layer.name = "Col"
        color = np.empty(len(blender_mesh.loops) * 4, dtype=np.float32)
        color_layer.data.foreach_get("color", color)
        color = color.reshape(-1, 4)

        alpha = color[:, 3]
        alpha_rgba = np.repeat(alpha[:, np.newaxis], 4, axis=1).flatten()
        alpha_layer = blender_mesh.vertex_colors.new(name="Alpha").data
        alpha_layer.foreach_set("color", alpha_rgba)


class F3DGlTFSettings(PropertyGroup):
    use: BoolProperty(default=True, name="Export/Import F3D extensions")
    use_3_2_hacks_prop: BoolProperty(
        name="Use 3.2 vertex color hacks",
        description="Blender version 3.2 ships with the last version of the glTF 2.0 addon to not support "
        "float colors (3.2.40).\n"
        "This hack will override the primitive gathering function in the glTF addon with a custom one",
        default=True,
    )
    apply_alpha_to_col: BoolProperty(
        name='Apply alpha to "Col" layer',
        description='"Col" color attribute will have alpha applied for a single color accessor',
        default=True,
    )
    raise_texture_limits: BoolProperty(
        name="Tex Limits",
        description="Raises errors when texture limits are exceeded,\n"
        "such as texture resolution, pallete size, format conflicts, etc",
        default=True,
    )
    raise_large_multitex: BoolProperty(
        name="Large Multi",
        description="Raise an error when a multitexture has two large textures.\n"
        "This can theoretically be supported",
        default=True,
    )
    raise_large_tex: BoolProperty(
        name="Large Tex",
        description="Raise an error when a polygon's textures in large texture mode can´t fit in\n"
        "one full TMEM load",
        default=True,
    )
    raise_rendermode: BoolProperty(
        name="Rendermode",
        description="Raise an error when a material uses an invalid combination of rendermode presets.\n"
        "Does not raise in the normal exporter",
        default=True,
    )
    raise_non_f3d_mat: BoolProperty(
        name="Non F3D",
        description="Raise an error when a material is not an F3D material. Useful for tiny3d",
        default=False,
    )
    raise_bad_mat_slot: BoolProperty(
        name="Bad Slot",
        description="Raise an error when the mesh has no materials, " "a face's material slot is empty or invalid",
        default=False,
    )
    raise_no_uvmap: BoolProperty(
        name="No UVMap",
        description="Raise an error when a mesh with F3D materials has no uv layer named UVMap",
        default=True,
    )

    @property
    def use_3_2_hacks(self):
        return self.use and self.use_3_2_hacks_prop

    def to_dict(self):
        return prop_group_to_json(self, ["use_3_2_hacks_prop"])

    def from_dict(self, data: dict):
        json_to_prop_group(self, data)

    def draw_props(self, layout: UILayout, import_context=False):
        col = layout.column()
        action = "Import" if import_context else "Export"
        if not self.use:
            col.box().label(text="Not enabled", icon="ERROR")
            return

        if not import_context:
            scene = bpy.context.scene
            prop_split(col, scene, "f3d_type", "Scene Microcode")
            if not scene.f3d_type:
                col.box().label(text="No microcode selected", icon="ERROR")
            gbi = get_F3D_GBI()
        extensions = [MATERIAL_EXTENSION_NAME, SAMPLER_EXTENSION_NAME, MESH_EXTENSION_NAME, F3D_MATERIAL_EXTENSION_NAME]
        if import_context or gbi.F3DEX_GBI:
            extensions.append(EX1_MATERIAL_EXTENSION_NAME)
        if import_context or gbi.F3DEX_GBI_3:
            extensions.append(EX3_MATERIAL_EXTENSION_NAME)
        if import_context or not gbi.F3D_OLD_GBI:
            extensions.append(NEW_MESH_EXTENSION_NAME)
        multilineLabel(col.box(), f"Will {action}:\n" + ",\n".join(extensions), icon=action.upper())

        if import_context:
            return
        col.separator()

        col.box().label(text="See tooltips for more info", icon="INFO")

        if GLTF2_ADDON_VERSION == (3, 2, 40):
            col.prop(self, "use_3_2_hacks_prop")
        col.prop(self, "apply_alpha_to_col")

        box = col.box().column()
        box.box().label(text="Raise Errors:", icon="ERROR")

        row = box.row(align=True)
        row.prop(self, "raise_texture_limits", toggle=True)
        limits_row = row.row(align=True)
        limits_row.enabled = self.raise_texture_limits
        limits_row.prop(self, "raise_large_multitex", toggle=True)
        limits_row.prop(self, "raise_large_tex", toggle=True)

        row = box.row(align=True)
        row.prop(self, "raise_rendermode", toggle=True)
        row.prop(self, "raise_non_f3d_mat", toggle=True)
        row.prop(self, "raise_no_uvmap", toggle=True)

        row = box.split(factor=1.0 / 3.0, align=True)
        row.prop(self, "raise_bad_mat_slot", toggle=True)


class F3DGlTFPanel(Panel):
    bl_idname = "GLTF_PT_F3D"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_label = ""
    bl_parent_id = "GLTF_PT_Fast64"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context: Context):
        row = self.layout.row()
        row.separator(factor=0.25)
        row.prop(
            get_settings(context),
            "use",
            text=("Import" if is_import_context(context) else "Export") + " F3D extensions",
        )

    def draw(self, context: Context):
        self.layout.use_property_decorate = False  # No animation.
        get_gltf_settings(context).f3d.draw_props(self.layout, is_import_context(context))


def modify_f3d_nodes_for_export(use: bool):
    """
    HACK: For 4.1 and 4.2, we create new, way simpler nodes that glTF can use to gather the correct vertex color layer.
    We can´t have glTF interacting with the f3d nodes either, otherwise an infinite recursion occurs in texture gathering
    this is also called in gather_gltf_extensions_hook (glTF2_post_export_callback can fail)
    """
    if not get_settings().use:
        return
    for mat in bpy.data.materials:
        if not is_mat_f3d(mat):
            continue
        node_tree = mat.node_tree
        nodes = node_tree.nodes
        f3d_output = nodes.get("OUTPUT")
        if not f3d_output:
            mat.use_nodes = use
            continue

        material_output = next((node for node in nodes if node.bl_idname == "ShaderNodeOutputMaterial"), None)
        if material_output is None:
            material_output = nodes.new("ShaderNodeOutputMaterial")

        bsdf = next((node for node in nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        if bsdf is None:
            bsdf = nodes.new("ShaderNodeBsdfPrincipled")
            bsdf["f3d_gltf_owned"] = True
        bsdf.location = (1260, 900)

        if get_version() < (4, 1, 0):
            mix_name = "ShaderNodeMixRGB"
        else:
            mix_name = "ShaderNodeMix"
        # we need to use a mix node because 4.1
        mix = next((node for node in nodes if node.bl_idname == mix_name and node.get("f3d_gltf_owned")), None)
        if mix is None:
            mix = nodes.new(mix_name)
            mix["f3d_gltf_owned"] = True
        mix.location = (1075, 850)
        mix.blend_type = "MULTIPLY"
        if get_version() >= (4, 1, 0):
            mix.data_type = "RGBA"
            mix.inputs[2].default_value = 1.0
        else:
            mix.inputs[2].default_value = [1.0, 1.0, 1.0, 1.0]
        mix.inputs[0].default_value = 1.0

        vertex_color = next(
            (node for node in nodes if node.bl_idname == "ShaderNodeVertexColor" and node.get("f3d_gltf_owned")), None
        )
        if vertex_color is None:
            vertex_color = nodes.new("ShaderNodeVertexColor")
        vertex_color["f3d_gltf_owned"] = True
        vertex_color.location = (900, 850)
        vertex_color.layer_name = "Col"

        remove_first_link_if_exists(mat, material_output.inputs["Surface"].links)
        if use:
            link_if_none_exist(mat, f3d_output.outputs["Shader"], material_output.inputs["Surface"])
            update_blend_method(mat, bpy.context)
        else:
            mat.blend_method = "BLEND"  # HACK: same thing, 4.1 is weird with alpha
            link_if_none_exist(
                mat, vertex_color.outputs["Color"], bsdf.inputs.get("Color") or bsdf.inputs.get("Base Color")
            )
            link_if_none_exist(mat, vertex_color.outputs["Alpha"], mix.inputs[1])
            link_if_none_exist(mat, mix.outputs[0], bsdf.inputs["Alpha"])
            link_if_none_exist(mat, bsdf.outputs["BSDF"], material_output.inputs["Surface"])


def get_gamma_corrected(layer):
    colors = np.empty(len(layer) * 4, dtype=np.float32)
    if bpy.app.version > (3, 2, 0):
        layer.foreach_get("color_srgb", colors)
    else:  # vectorized linear -> sRGB conversion
        layer.foreach_get("color", colors)
        mask = colors > 0.0031308
        colors[mask] = 1.055 * (np.power(colors[mask], (1.0 / 2.4))) - 0.055
        colors[~mask] *= 12.0
    return colors.reshape((-1, 4))


RGB_TO_LUM_COEF = np.array([0.2126729, 0.7151522, 0.0721750], np.float32)  # blender rgb -> lum coefficient


def pre_gather_mesh_hook(blender_mesh: Mesh, *_args):
    """HACK: Runs right before the actual gather_mesh func in the addon, we need to join col and alpha"""
    if not get_settings().apply_alpha_to_col:
        return
    if not mesh_has_f3d_mat(blender_mesh):
        return
    print("F3D glTF: Applying alpha")
    color_layer = getColorLayer(blender_mesh, layer="Col")
    alpha_layer = getColorLayer(blender_mesh, layer="Alpha")
    if not color_layer or not alpha_layer:
        return
    color = np.empty(len(blender_mesh.loops) * 4, dtype=np.float32)
    color_layer.foreach_get("color", color)
    color = color.reshape(-1, 4)
    rgb_alpha = get_gamma_corrected(alpha_layer)

    alpha_median = np.dot(rgb_alpha[:, :3], RGB_TO_LUM_COEF)
    color[:, 3] = alpha_median

    color = color.flatten()
    color = color.clip(0.0, 1.0)  # clamp
    color_layer.foreach_set("color", color)


def get_fast64_custom_colors(blender_mesh):
    color_layer = getColorLayer(blender_mesh, layer="Col")  # assume Col already has alpha from other hack
    colors = np.zeros(len(blender_mesh.loops) * 4, dtype=np.float32)
    if color_layer is not None:
        color_layer.foreach_get("color", colors)
    colors = colors.reshape(-1, 4)
    return colors


def extract_primitives_fast64(
    original_function, blender_mesh, uuid_for_skined_data, blender_vertex_groups, modifiers, export_settings
):
    """
    https://github.com/KhronosGroup/glTF-Blender-IO/blob/bb0e780711f2021defb06c5650d5490f3771f252/addons/io_scene_gltf2/blender/exp/gltf2_blender_extract.py#L23-L383
    SPDX-License-Identifier: Apache-2.0
    Copyright 2018-2021 The glTF-Blender-IO authors.

    All changes are marked by "# FAST64 CHANGE/END:"
    We must gather fast64 colors manually since they are corner float colors (unsupported in 3.2 glTF 2.0 addon)

    Extract primitives from a mesh.
    """
    # FAST64 CHANGE: Local imports
    from io_scene_gltf2.blender.exp.gltf2_blender_extract import (  # pylint: disable=import-error
        __get_positions,
        __get_bone_data,
        __get_normals,
        __get_tangents,
        __get_bitangent_signs,
        __get_uvs,
        __get_colors,
        __calc_morph_tangents,
    )
    from io_scene_gltf2.blender.exp import gltf2_blender_export_keys  # pylint: disable=import-error
    from io_scene_gltf2.io.com.gltf2_io_debug import print_console  # pylint: disable=import-error
    from io_scene_gltf2.blender.exp import gltf2_blender_gather_skins  # pylint: disable=import-error

    # FAST64 END
    # FAST64 CHANGE: Use custom fast64 function or use original
    if not (get_settings().use_3_2_hacks and mesh_has_f3d_mat(blender_mesh)):
        return original_function(blender_mesh, uuid_for_skined_data, blender_vertex_groups, modifiers, export_settings)
    # FAST64 END

    # FAST64 CHANGE: Changed print so the user knows the custom function is being used
    print_console("INFO", "(Fast64) Extracting primitive: " + blender_mesh.name)

    blender_object = None
    if uuid_for_skined_data:
        blender_object = export_settings["vtree"].nodes[uuid_for_skined_data].blender_object

    use_normals = export_settings[gltf2_blender_export_keys.NORMALS]
    if use_normals:
        blender_mesh.calc_normals_split()

    use_tangents = False
    if use_normals and export_settings[gltf2_blender_export_keys.TANGENTS]:
        if blender_mesh.uv_layers.active and len(blender_mesh.uv_layers) > 0:
            try:
                blender_mesh.calc_tangents()
                use_tangents = True
            except Exception:
                print_console("WARNING", "Could not calculate tangents. Please try to triangulate the mesh first.")

    tex_coord_max = 0
    if export_settings[gltf2_blender_export_keys.TEX_COORDS]:
        if blender_mesh.uv_layers.active:
            tex_coord_max = len(blender_mesh.uv_layers)

    color_max = 0
    if export_settings[gltf2_blender_export_keys.COLORS]:
        color_max = len(blender_mesh.vertex_colors)

    armature = None
    skin = None
    if blender_vertex_groups and export_settings[gltf2_blender_export_keys.SKINS]:
        if modifiers is not None:
            modifiers_dict = {m.type: m for m in modifiers}
            if "ARMATURE" in modifiers_dict:
                modifier = modifiers_dict["ARMATURE"]
                armature = modifier.object

        # Skin must be ignored if the object is parented to a bone of the armature
        # (This creates an infinite recursive error)
        # So ignoring skin in that case
        is_child_of_arma = (
            armature
            and blender_object
            and blender_object.parent_type == "BONE"
            and blender_object.parent.name == armature.name
        )
        if is_child_of_arma:
            armature = None

        if armature:
            skin = gltf2_blender_gather_skins.gather_skin(
                export_settings["vtree"].nodes[uuid_for_skined_data].armature, export_settings
            )
            if not skin:
                armature = None

    use_morph_normals = use_normals and export_settings[gltf2_blender_export_keys.MORPH_NORMAL]
    use_morph_tangents = use_morph_normals and use_tangents and export_settings[gltf2_blender_export_keys.MORPH_TANGENT]

    key_blocks = []
    if blender_mesh.shape_keys and export_settings[gltf2_blender_export_keys.MORPH]:
        key_blocks = [
            key_block
            for key_block in blender_mesh.shape_keys.key_blocks
            if not (key_block == key_block.relative_key or key_block.mute)
        ]

    use_materials = export_settings[gltf2_blender_export_keys.MATERIALS]

    # Fetch vert positions and bone data (joint,weights)

    locs, morph_locs = __get_positions(blender_mesh, key_blocks, armature, blender_object, export_settings)
    if skin:
        vert_bones, num_joint_sets, need_neutral_bone = __get_bone_data(blender_mesh, skin, blender_vertex_groups)
        if need_neutral_bone is True:
            # Need to create a fake joint at root of armature
            # In order to assign not assigned vertices to it
            # But for now, this is not yet possible, we need to wait the armature node is created
            # Just store this, to be used later
            armature_uuid = export_settings["vtree"].nodes[uuid_for_skined_data].armature
            export_settings["vtree"].nodes[armature_uuid].need_neutral_bone = True

    # In Blender there is both per-vert data, like position, and also per-loop
    # (loop=corner-of-poly) data, like normals or UVs. glTF only has per-vert
    # data, so we need to split Blender verts up into potentially-multiple glTF
    # verts.
    #
    # First, we'll collect a "dot" for every loop: a struct that stores all the
    # attributes at that loop, namely the vertex index (which determines all
    # per-vert data), and all the per-loop data like UVs, etc.
    #
    # Each unique dot will become one unique glTF vert.

    # List all fields the dot struct needs.
    dot_fields = [("vertex_index", np.uint32)]
    if use_normals:
        dot_fields += [("nx", np.float32), ("ny", np.float32), ("nz", np.float32)]
    if use_tangents:
        dot_fields += [("tx", np.float32), ("ty", np.float32), ("tz", np.float32), ("tw", np.float32)]
    for uv_i in range(tex_coord_max):
        dot_fields += [("uv%dx" % uv_i, np.float32), ("uv%dy" % uv_i, np.float32)]
    for col_i in range(color_max):
        dot_fields += [
            ("color%dr" % col_i, np.float32),
            ("color%dg" % col_i, np.float32),
            ("color%db" % col_i, np.float32),
            ("color%da" % col_i, np.float32),
        ]
    # FAST64 CHANGE: Add fields for custom fast64 color
    dot_fields += [
        ("fast64_color_r", np.float32),
        ("fast64_color_g", np.float32),
        ("fast64_color_b", np.float32),
        ("fast64_color_a", np.float32),
    ]
    # FAST64 CHANGE: END
    if use_morph_normals:
        for morph_i, _ in enumerate(key_blocks):
            dot_fields += [
                ("morph%dnx" % morph_i, np.float32),
                ("morph%dny" % morph_i, np.float32),
                ("morph%dnz" % morph_i, np.float32),
            ]

    dots = np.empty(len(blender_mesh.loops), dtype=np.dtype(dot_fields))

    vidxs = np.empty(len(blender_mesh.loops))
    blender_mesh.loops.foreach_get("vertex_index", vidxs)
    dots["vertex_index"] = vidxs
    del vidxs

    if use_normals:
        kbs = key_blocks if use_morph_normals else []
        normals, morph_normals = __get_normals(blender_mesh, kbs, armature, blender_object, export_settings)
        dots["nx"] = normals[:, 0]
        dots["ny"] = normals[:, 1]
        dots["nz"] = normals[:, 2]
        del normals
        for morph_i, ns in enumerate(morph_normals):
            dots["morph%dnx" % morph_i] = ns[:, 0]
            dots["morph%dny" % morph_i] = ns[:, 1]
            dots["morph%dnz" % morph_i] = ns[:, 2]
        del morph_normals

    if use_tangents:
        tangents = __get_tangents(blender_mesh, armature, blender_object, export_settings)
        dots["tx"] = tangents[:, 0]
        dots["ty"] = tangents[:, 1]
        dots["tz"] = tangents[:, 2]
        del tangents
        signs = __get_bitangent_signs(blender_mesh, armature, blender_object, export_settings)
        dots["tw"] = signs
        del signs

    for uv_i in range(tex_coord_max):
        uvs = __get_uvs(blender_mesh, uv_i)
        dots["uv%dx" % uv_i] = uvs[:, 0]
        dots["uv%dy" % uv_i] = uvs[:, 1]
        del uvs

    for col_i in range(color_max):
        colors = __get_colors(blender_mesh, col_i)
        dots["color%dr" % col_i] = colors[:, 0]
        dots["color%dg" % col_i] = colors[:, 1]
        dots["color%db" % col_i] = colors[:, 2]
        dots["color%da" % col_i] = colors[:, 3]
        del colors

    # FAST64 CHANGE: Add custom fast64 color
    colors = get_fast64_custom_colors(blender_mesh)
    dots["fast64_color_r"] = colors[:, 0]
    dots["fast64_color_g"] = colors[:, 1]
    dots["fast64_color_b"] = colors[:, 2]
    dots["fast64_color_a"] = colors[:, 3]
    del colors
    # FAST64 CHANGE: End

    # Calculate triangles and sort them into primitives.

    blender_mesh.calc_loop_triangles()
    loop_indices = np.empty(len(blender_mesh.loop_triangles) * 3, dtype=np.uint32)
    blender_mesh.loop_triangles.foreach_get("loops", loop_indices)

    prim_indices = {}  # maps material index to TRIANGLES-style indices into dots

    if use_materials == "NONE":  # Only for None. For placeholder and export, keep primitives
        # Put all vertices into one primitive
        prim_indices[-1] = loop_indices

    else:
        # Bucket by material index.

        tri_material_idxs = np.empty(len(blender_mesh.loop_triangles), dtype=np.uint32)
        blender_mesh.loop_triangles.foreach_get("material_index", tri_material_idxs)
        loop_material_idxs = np.repeat(tri_material_idxs, 3)  # material index for every loop
        unique_material_idxs = np.unique(tri_material_idxs)
        del tri_material_idxs

        for material_idx in unique_material_idxs:
            prim_indices[material_idx] = loop_indices[loop_material_idxs == material_idx]

    # Create all the primitives.

    primitives = []

    for material_idx, dot_indices in prim_indices.items():
        # Extract just dots used by this primitive, deduplicate them, and
        # calculate indices into this deduplicated list.
        prim_dots = dots[dot_indices]
        prim_dots, indices = np.unique(prim_dots, return_inverse=True)

        if len(prim_dots) == 0:
            continue

        # Now just move all the data for prim_dots into attribute arrays

        attributes = {}

        blender_idxs = prim_dots["vertex_index"]

        attributes["POSITION"] = locs[blender_idxs]

        for morph_i, vs in enumerate(morph_locs):
            attributes["MORPH_POSITION_%d" % morph_i] = vs[blender_idxs]

        if use_normals:
            normals = np.empty((len(prim_dots), 3), dtype=np.float32)
            normals[:, 0] = prim_dots["nx"]
            normals[:, 1] = prim_dots["ny"]
            normals[:, 2] = prim_dots["nz"]
            attributes["NORMAL"] = normals

        if use_tangents:
            tangents = np.empty((len(prim_dots), 4), dtype=np.float32)
            tangents[:, 0] = prim_dots["tx"]
            tangents[:, 1] = prim_dots["ty"]
            tangents[:, 2] = prim_dots["tz"]
            tangents[:, 3] = prim_dots["tw"]
            attributes["TANGENT"] = tangents

        if use_morph_normals:
            for morph_i, _ in enumerate(key_blocks):
                ns = np.empty((len(prim_dots), 3), dtype=np.float32)
                ns[:, 0] = prim_dots["morph%dnx" % morph_i]
                ns[:, 1] = prim_dots["morph%dny" % morph_i]
                ns[:, 2] = prim_dots["morph%dnz" % morph_i]
                attributes["MORPH_NORMAL_%d" % morph_i] = ns

                if use_morph_tangents:
                    attributes["MORPH_TANGENT_%d" % morph_i] = __calc_morph_tangents(normals, ns, tangents)

        for tex_coord_i in range(tex_coord_max):
            uvs = np.empty((len(prim_dots), 2), dtype=np.float32)
            uvs[:, 0] = prim_dots["uv%dx" % tex_coord_i]
            uvs[:, 1] = prim_dots["uv%dy" % tex_coord_i]
            attributes["TEXCOORD_%d" % tex_coord_i] = uvs

        for color_i in range(color_max):
            colors = np.empty((len(prim_dots), 4), dtype=np.float32)
            colors[:, 0] = prim_dots["color%dr" % color_i]
            colors[:, 1] = prim_dots["color%dg" % color_i]
            colors[:, 2] = prim_dots["color%db" % color_i]
            colors[:, 3] = prim_dots["color%da" % color_i]
            attributes["COLOR_%d" % color_i] = colors

        # FAST64 CHANGE: Start
        mat = blender_mesh.materials[material_idx]
        if is_mat_f3d(mat):
            colors = np.empty((len(prim_dots), 4), dtype=np.float32)
            colors[:, 0] = prim_dots["fast64_color_r"]
            colors[:, 1] = prim_dots["fast64_color_g"]
            colors[:, 2] = prim_dots["fast64_color_b"]
            colors[:, 3] = prim_dots["fast64_color_a"]
            attributes["FAST64_COLOR"] = colors
            del colors
        # FAST64 CHANGE: End

        if skin:
            joints = [[] for _ in range(num_joint_sets)]
            weights = [[] for _ in range(num_joint_sets)]

            for vi in blender_idxs:
                bones = vert_bones[vi]
                for j in range(0, 4 * num_joint_sets):
                    if j < len(bones):
                        joint, weight = bones[j]
                    else:
                        joint, weight = 0, 0.0
                    joints[j // 4].append(joint)
                    weights[j // 4].append(weight)

            for i, (js, ws) in enumerate(zip(joints, weights)):
                attributes["JOINTS_%d" % i] = js
                attributes["WEIGHTS_%d" % i] = ws

        primitives.append(
            {
                "attributes": attributes,
                "indices": indices,
                "material": material_idx,
            }
        )

    if export_settings["gltf_loose_edges"]:
        # Find loose edges
        loose_edges = [e for e in blender_mesh.edges if e.is_loose]
        blender_idxs = [vi for e in loose_edges for vi in e.vertices]

        if blender_idxs:
            # Export one glTF vert per unique Blender vert in a loose edge
            blender_idxs = np.array(blender_idxs, dtype=np.uint32)
            blender_idxs, indices = np.unique(blender_idxs, return_inverse=True)

            attributes = {}

            attributes["POSITION"] = locs[blender_idxs]

            for morph_i, vs in enumerate(morph_locs):
                attributes["MORPH_POSITION_%d" % morph_i] = vs[blender_idxs]

            if skin:
                joints = [[] for _ in range(num_joint_sets)]
                weights = [[] for _ in range(num_joint_sets)]

                for vi in blender_idxs:
                    bones = vert_bones[vi]
                    for j in range(0, 4 * num_joint_sets):
                        if j < len(bones):
                            joint, weight = bones[j]
                        else:
                            joint, weight = 0, 0.0
                        joints[j // 4].append(joint)
                        weights[j // 4].append(weight)

                for i, (js, ws) in enumerate(zip(joints, weights)):
                    attributes["JOINTS_%d" % i] = js
                    attributes["WEIGHTS_%d" % i] = ws

            primitives.append(
                {
                    "attributes": attributes,
                    "indices": indices,
                    "mode": 1,  # LINES
                    "material": 0,
                }
            )

    if export_settings["gltf_loose_points"]:
        # Find loose points
        verts_in_edge = set(vi for e in blender_mesh.edges for vi in e.vertices)
        blender_idxs = [vi for vi, _ in enumerate(blender_mesh.vertices) if vi not in verts_in_edge]

        if blender_idxs:
            blender_idxs = np.array(blender_idxs, dtype=np.uint32)

            attributes = {}

            attributes["POSITION"] = locs[blender_idxs]

            for morph_i, vs in enumerate(morph_locs):
                attributes["MORPH_POSITION_%d" % morph_i] = vs[blender_idxs]

            if skin:
                joints = [[] for _ in range(num_joint_sets)]
                weights = [[] for _ in range(num_joint_sets)]

                for vi in blender_idxs:
                    bones = vert_bones[vi]
                    for j in range(0, 4 * num_joint_sets):
                        if j < len(bones):
                            joint, weight = bones[j]
                        else:
                            joint, weight = 0, 0.0
                        joints[j // 4].append(joint)
                        weights[j // 4].append(weight)

                for i, (js, ws) in enumerate(zip(joints, weights)):
                    attributes["JOINTS_%d" % i] = js
                    attributes["WEIGHTS_%d" % i] = ws

            primitives.append(
                {
                    "attributes": attributes,
                    "mode": 0,  # POINTS
                    "material": 0,
                }
            )

    print_console("INFO", "Primitives created: %d" % len(primitives))

    return primitives


def post__gather_colors(results, blender_primitive, _export_settings):
    from io_scene_gltf2.io.com import gltf2_io, gltf2_io_constants  # pylint: disable=import-error
    from io_scene_gltf2.io.exp import gltf2_io_binary_data  # pylint: disable=import-error

    attributes = blender_primitive["attributes"]
    colors = attributes.get("FAST64_COLOR", None)
    if colors is not None:
        # Rename other attributes
        for attr_name, values in copy.copy(attributes).items():
            if attr_name.startswith("COLOR_"):
                num = int(attr_name.lstrip("COLOR_"))
                attributes.pop(attr_name)
                attributes["COLOR_%d" % num] = values
        results["COLOR_0"] = gltf2_io.Accessor(
            buffer_view=gltf2_io_binary_data.BinaryData(colors.tobytes()),
            byte_offset=None,
            component_type=gltf2_io_constants.ComponentType.Float,
            count=len(colors),
            extensions=None,
            extras=None,
            max=None,
            min=None,
            name=None,
            normalized=True,
            sparse=None,
            type=gltf2_io_constants.DataType.Vec4,
        )
    return results


def add_3_2_hooks():
    """3.2 hack for float colors"""
    if get_version() == (3, 2, 40):
        import io_scene_gltf2.blender.exp.gltf2_blender_gather_primitive_attributes as __gather_colors_owner  # pylint: disable=import-error, import-outside-toplevel
        import io_scene_gltf2.blender.exp.gltf2_blender_extract as extract_primitives_owner  # pylint: disable=import-error, import-outside-toplevel

        extract_primitives_owner.extract_primitives = swap_function(
            extract_primitives_owner.extract_primitives, extract_primitives_fast64
        )
        __gather_colors_owner.__gather_colors = suffix_function(
            __gather_colors_owner.__gather_colors, post__gather_colors
        )
