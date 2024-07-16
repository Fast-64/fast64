from dataclasses import dataclass
from math import ceil, floor
import bpy
from bpy.types import NodeTree, PropertyGroup, UILayout, Object, Mesh, Material
from bpy.props import BoolProperty

from ...utility import multilineLabel, PluginError, fix_invalid_props
from ...gltf_utility import GlTF2SubExtension, get_gltf_image_from_blender_image
from ..f3d_gbi import F3D, get_F3D_GBI
from ..f3d_material import (
    all_combiner_uses,
    get_color_info_from_tex,
    getTmemMax,
    getTmemWordUsage,
    rendermode_presets_checks,
    trunc_10_2,
    createScenePropertiesForMaterial,
    link_f3d_material_library,
    update_node_values,
    update_tex_values_and_formats,
    update_rendermode_preset,
    get_tex_basis_size,
    F3DMaterialProperty,
    RDPSettings,
    TextureProperty,
)
from ..f3d_writer import cel_shading_checks, check_face_materials
from ..f3d_texture_writer import UVtoSTLarge

from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.blender.imp.gltf2_blender_image import BlenderImage
from io_scene_gltf2.io.com.gltf2_io_constants import TextureFilter, TextureWrap

MATERIAL_EXTENSION_NAME = "FAST64_materials_f3d"
EX1_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dlx"
EX3_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dex3"
SAMPLER_EXTENSION_NAME = "FAST64_sampler_f3d"
MESH_EXTENSION_NAME = "FAST64_mesh_f3d"
NEW_MESH_EXTENSION_NAME = "FAST64_mesh_f3d_new"

EXCLUDE_FROM_NODE = (
    "rna_type",
    "type",
    "inputs",
    "outputs",
    "dimensions",
    "interface",
    "internal_links",
    "texture_mapping",
    "color_mapping",
    "image_user",
)
EXCLUDE_FROM_INPUT_OUTPUT = (
    "rna_type",
    "label",
    "identifier",
    "is_output",
    "is_linked",
    "is_multi_input",
    "node",
    "bl_idname",
    "default_value",
)


def node_tree_copy(src: NodeTree, dst: NodeTree):
    def copy_attributes(src, dst, excludes=None):
        fails, excludes = [], excludes if excludes else []
        attributes = (attr.identifier for attr in src.bl_rna.properties if attr.identifier not in excludes)
        for attr in attributes:
            try:
                setattr(dst, attr, getattr(src, attr))
            except Exception as exc:  # pylint: disable=broad-except
                fails.append(exc)
        if fails:
            raise AttributeError("Failed to copy all attributes: " + str(fails))

    dst.nodes.clear()
    dst.links.clear()

    node_mapping = {}  # To not have to look up the new node for linking
    for src_node in src.nodes:  # Copy all nodes
        new_node = dst.nodes.new(src_node.bl_idname)
        copy_attributes(src_node, new_node, excludes=EXCLUDE_FROM_NODE)
        node_mapping[src_node] = new_node
    for src_node, dst_node in node_mapping.items():
        for i, src_input in enumerate(src_node.inputs):  # Link all nodes
            for link in src_input.links:
                connected_node = dst.nodes[link.from_node.name]
                dst.links.new(connected_node.outputs[link.from_socket.name], dst_node.inputs[i])

        for src_input, dst_input in zip(src_node.inputs, dst_node.inputs):  # Copy all inputs
            copy_attributes(src_input, dst_input, excludes=EXCLUDE_FROM_INPUT_OUTPUT)
        for src_output, dst_output in zip(src_node.outputs, dst_node.outputs):  # Copy all outputs
            copy_attributes(src_output, dst_output, excludes=EXCLUDE_FROM_INPUT_OUTPUT)


def uvmap_check(obj: Object, mesh: Mesh):
    has_f3d_mat = False
    for material in obj.material_slots:  # Check if any slot is F3D
        if material.material.is_f3d:
            has_f3d_mat = True
            break
    if has_f3d_mat:  # If any slot is F3D check if the mesh uses the material
        has_f3d_mat = False
        for poly in mesh.polygons:
            if obj.material_slots[poly.material_index].material.is_f3d:
                has_f3d_mat = True
                break
    if has_f3d_mat:  # Finally, if there is a F3D material check if the mesh has a uvmap
        for layer in mesh.uv_layers:
            if layer.name == "UVMap":
                break
        else:
            raise PluginError('Object with F3D materials does not have a "UVMap" uvmap layer.')


def large_tex_checks(obj: Object, mesh: Mesh):
    """
    See TileLoad.initWithFace for the usual exporter version of this function
    This strips out any exporting and focous on just error checking
    """

    large_props_dict = {}
    for mat in mesh.materials:  # Cache info on any large tex material that needs to be checked
        if not mat.is_f3d or not mat.f3d_mat.use_large_textures:
            continue
        f3d_mat = mat.f3d_mat
        use_dict = all_combiner_uses(f3d_mat)
        textures = []
        if use_dict["Texture 0"] and f3d_mat.tex0.tex_set:
            textures.append(f3d_mat.tex0)
        if use_dict["Texture 1"] and f3d_mat.tex1.tex_set:
            textures.append(f3d_mat.tex1)

        if len(textures) == 0:
            continue
        texture = textures[0]

        tmem = sum(getTmemWordUsage(tex.tex_format, *tex.get_tex_size()) for tex in textures)
        tmem_size = 256 if texture.is_ci else 512
        if tmem <= tmem_size:
            continue  # Can fit in TMEM without large mode, so skip

        large_props_dict[mat.name] = {
            "clamp": f3d_mat.large_edges == "Clamp",
            "point": f3d_mat.rdp_settings.g_mdsft_text_filt == "G_TF_POINT",
            "dimensions": get_tex_basis_size(f3d_mat),
            "format": texture.tex_format,
            "texels_per_word": 64 // sum(texture.format_size for texture in textures),
            "is_4bit": any(tex.format_size == 4 for tex in textures),
            "large_tex_words": tmem_size,
        }

    def get_low(large_props, value, field):
        value = int(floor(value))
        if large_props["clamp"]:
            value = min(max(value, 0), large_props["dimensions"][field] - 1)
        if large_props["is_4bit"] and field == 0:
            # Must start on an even texel (round down)
            value &= ~1
        return value

    def get_high(large_props, value, field):
        value = int(ceil(value)) - (1 if large_props["point"] else 0)
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

    if "UVMap" not in obj.data.uv_layers:
        raise PluginError('Cannot do large texture checks without a "UVMap" uvmap layer.')
    uv_data = obj.data.uv_layers["UVMap"].data
    for face in mesh.loop_triangles:
        mat_name = obj.material_slots[face.material_index].material.name
        large_props = large_props_dict.get(mat_name)
        if large_props is None:
            continue
        dimensions = large_props["dimensions"]
        face_uvs = [UVtoSTLarge(obj, loop_index, uv_data, dimensions) for loop_index in face.loops]
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
                + f" to cover texels {sl}-{sh} x {tl}-{th}"
                + f" (image dims are {dimensions}), but image space"
                + " only goes up to 1024 so this cannot be represented."
            )
        else:
            raise PluginError(
                f"Large texture material {mat_name} has a face that needs"
                + f" to cover texels {sl}-{sh} x {tl}-{th}"
                + f" ({sh-sl+1} x {th-tl+1} texels) "
                + f"in format {large_props['format']}, which can't fit in TMEM."
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

        return [round_and_clamp(self.r), round_and_clamp(self.g), round_and_clamp(self.b), round_and_clamp(self.a)]

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
            self.print_verbose("Linking F3D material library")
            link_f3d_material_library()
            mat = bpy.data.materials["fast64_f3d_material_library_beefwashere"]
            self.base_node_tree = mat.node_tree.copy()
            bpy.data.materials.remove(mat)
        except Exception as exc:
            raise ImportError("Failed to import f3d material node tree") from exc

    def sampler_from_f3d(self, f3d_mat: F3DMaterialProperty, f3d_tex: TextureProperty):
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

        use_nearest = f3d_mat.rdp_settings.g_mdsft_text_filt == "G_TF_POINT"
        mag_filter = TextureFilter.Nearest if use_nearest else TextureFilter.Linear
        min_filter = TextureFilter.NearestMipmapNearest if use_nearest else TextureFilter.LinearMipmapLinear
        sampler = gltf2_io.Sampler(
            extensions=None,
            extras=None,
            mag_filter=mag_filter,
            min_filter=min_filter,
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
        img = f3d_tex.tex
        if img is not None:
            source = get_gltf_image_from_blender_image(img.name, export_settings)

            if self.settings.raise_texture_limits and f3d_tex.tex_set and not f3d_tex.use_tex_reference:
                tex_size = f3d_tex.get_tex_size()
                tmem_usage = getTmemWordUsage(f3d_tex.tex_format, *tex_size) * 8
                tmem_max = getTmemMax(f3d_tex.tex_format)

                if f3d_mat.use_large_textures:
                    if tex_size[0] > 1024 or tex_size[1] > 1024:
                        raise PluginError(
                            "Texture size (even large textures) limited to 1024 pixels in each dimension."
                        )
                elif tmem_usage > tmem_max:
                    raise PluginError(
                        f"Texture is too large: {tmem_usage} / {tmem_max} bytes. Note that width needs to be padded to 64-bit boundaries."
                    )
                if f3d_tex.is_ci:
                    _, _, _, rgba_colors = get_color_info_from_tex(img)
                    if len(rgba_colors) > 2**f3d_tex.format_size:
                        raise PluginError(f"Too many colors for {f3d_tex.tex_format}: {len(rgba_colors)}")

        else:
            if f3d_tex.tex_set and not f3d_tex.use_tex_reference and not img:
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
        size = f3d_tex.get_tex_size()
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

    def multitex_checks(self, f3d_mat: F3DMaterialProperty):
        tex0, tex1 = f3d_mat.tex0, f3d_mat.tex1
        both_reference = tex0.use_tex_reference and tex1.use_tex_reference
        same_textures = (
            (both_reference and tex0.tex_reference == tex1.tex_reference) or not both_reference and tex0.tex == tex1.tex
        )
        both_ci8 = tex0.tex_format == tex1.tex_format == "CI8"
        tex0_size, tex1_size = tex0.get_tex_size(), tex1.get_tex_size()
        tex0_tmem, tex1_tmem = (
            getTmemWordUsage(tex0.tex_format, *tex0_size),
            getTmemWordUsage(tex1.tex_format, *tex1_size),
        )
        tmem_size = 256 if tex0.is_ci and tex1.is_ci else 512

        if (both_reference and tex0.tex_reference == tex1.tex_reference) and (tex0_size != tex1_size):
            raise PluginError("Textures with the same reference must have the same size.")

        if f3d_mat.use_large_textures:
            if self.settings.raise_large_multitex:
                if tex0_tmem > tmem_size // 2 and tex1_tmem > tmem_size // 2:
                    raise PluginError("Multitexture with two large textures is not currently supported.")
                elif same_textures:
                    raise PluginError("Using the same texture for Tex0 and Tex1 is not compatible with large textures.")
        elif not same_textures and tex0_tmem + tex1_tmem > tmem_size:
            raise PluginError(
                "Textures are too big. Max TMEM size is 4k bytes, ex. 2 32x32 RGBA 16 bit textures. Note that width needs to be padded to 64-bit boundaries."
            )

        if tex0.is_ci != tex1.is_ci:
            raise PluginError("N64 does not support CI + non-CI texture. Must be both CI or neither CI.")
        elif tex0.is_ci and tex1.is_ci:
            if tex0.ci_format != tex1.ci_format:
                raise PluginError("Both CI textures must use the same palette format (usually RGBA16).")
            if (
                both_reference
                and tex0.pal_reference == tex1.pal_reference
                and tex0.pal_reference_size != tex1.pal_reference_size
            ):
                raise PluginError("Textures with the same palette reference must have the same palette size.")
            if not both_reference and both_ci8:
                # TODO: If flipbook is ever implemented, check if the reference is set by the flipbook
                raise PluginError(
                    "Can't have two CI8 textures where only one is a reference; no way to assign the palette."
                )
            if both_reference and both_ci8 and tex0.pal_reference != tex1.pal_reference:
                raise PluginError("Can't have two CI8 textures with different palette references.")

            # TODO: When porting ac f3dzex, skip this check
            rgba_colors = get_color_info_from_tex(tex0.tex)[3]
            rgba_colors.update(get_color_info_from_tex(tex1.tex)[3])
            if len(rgba_colors) > 256:
                raise PluginError(
                    f"The two CI textures together contain a total of {len(rgba_colors)} colors, which can't fit in a CI8 palette (256)."
                )

    def gather_material_hook(self, gltf2_material, blender_material, export_settings: dict):
        if not blender_material.is_f3d:
            if self.settings.raise_non_f3d_mat:
                raise PluginError(
                    'Material is not an F3D material. Turn off "Non F3D Material" to ignore.',
                )
            return
        data = {}

        f3d_mat: F3DMaterialProperty = blender_material.f3d_mat
        fix_invalid_props(f3d_mat)  # This fixes all enums that are not valid, and colors out of range
        rdp: RDPSettings = f3d_mat.rdp_settings

        if self.settings.raise_texture_limits:
            if f3d_mat.is_multi_tex and (f3d_mat.tex0.tex_set and f3d_mat.tex1.tex_set):
                self.multitex_checks(f3d_mat)
        if self.settings.raise_rendermode:
            if rdp.set_rendermode and not rdp.rendermode_advanced_enabled:
                rendermode_presets_checks(f3d_mat)

        use_dict = all_combiner_uses(f3d_mat)

        data["combiner"] = f3d_mat.combiner_to_dict()
        data.update(f3d_mat.f3d_colors_to_dict(use_dict))
        data.update(
            {
                "geometryMode": rdp.f3d_geo_mode_to_dict(),
                "otherModeH": rdp.other_mode_h_to_dict(),
                "otherModeL": rdp.other_mode_l_to_dict(),
                "other": rdp.other_to_dict(),
            }
        )
        data.update(f3d_mat.extra_texture_settings_to_dict())

        textures = {}
        data["textures"] = textures
        if use_dict["Texture 0"]:
            textures[0] = self.f3d_to_glTF2_texture_info(f3d_mat, f3d_mat.tex0, 0, export_settings)
        if use_dict["Texture 1"]:
            textures[1] = self.f3d_to_glTF2_texture_info(f3d_mat, f3d_mat.tex1, 1, export_settings)

        data["extensions"] = {}
        if self.gbi.F3DEX_GBI:  # F3DLX
            data["extensions"][EX1_MATERIAL_EXTENSION_NAME] = self.extension.Extension(
                name=EX1_MATERIAL_EXTENSION_NAME,
                extension={"geometryMode": rdp.f3dlx_geo_mode_to_dict()},
                required=False,
            )
        if self.gbi.F3DEX_GBI_3:  # F3DEX3
            if f3d_mat.use_cel_shading:
                cel_shading_checks(f3d_mat)
            data["extensions"][EX3_MATERIAL_EXTENSION_NAME] = self.extension.Extension(
                name=EX3_MATERIAL_EXTENSION_NAME,
                extension={
                    "geometryMode": rdp.f3dex3_geo_mode_to_dict(),
                    **f3d_mat.f3dex3_colors_to_dict(),
                },
                required=False,
            )

        self.append_extension(gltf2_material, MATERIAL_EXTENSION_NAME, data)

        # glTF Standard
        pbr = gltf2_material.pbr_metallic_roughness
        if f3d_mat.is_multi_tex:
            pbr.base_color_texture = textures[0]
            pbr.metallic_roughness_texture = textures[1]
        elif textures:
            pbr.base_color_texture = list(textures.values())[0]
        pbr.base_color_factor = get_fake_color(data)

        if not f3d_mat.rdp_settings.g_lighting:
            self.append_extension(gltf2_material, "KHR_materials_unlit")

    def gather_mesh_hook(self, gltf2_mesh, blender_mesh, blender_object, _export_settings: dict):
        if self.settings.raise_bad_mat_slot:
            material_slots = blender_object.material_slots
            if len(blender_mesh.materials) == 0 or len(material_slots) == 0:
                raise PluginError("Object does not have any materials.")
            check_face_materials(
                blender_object.name,
                material_slots,
                blender_mesh.polygons,
                self.settings.raise_non_f3d_mat,
            )
        if self.settings.raise_no_uvmap:
            uvmap_check(blender_object, blender_mesh)
        if self.settings.raise_large_tex:
            large_tex_checks(blender_object, blender_mesh)

        data = {}
        if not self.gbi.F3D_OLD_GBI:
            data["use_culling"] = blender_object.use_f3d_culling
            self.append_extension(
                gltf2_mesh,
                MESH_EXTENSION_NAME,
                {
                    "extensions": {
                        NEW_MESH_EXTENSION_NAME: self.extension.Extension(
                            name=NEW_MESH_EXTENSION_NAME, extension=data, required=False
                        )
                    }
                },
            )

    def gather_node_hook(self, gltf2_node, blender_object, _export_settings: dict):
        if gltf2_node.mesh:  # HACK: gather_mesh_hook is broken in 3.2, no blender object included
            self.gather_mesh_hook(gltf2_node.mesh, blender_object.data, blender_object, _export_settings)

    # Importing

    def gather_import_material_after_hook(
        self,
        gltf_material,
        _vertex_color,
        blender_material,
        gltf,
    ):
        data = self.get_extension(gltf_material, MATERIAL_EXTENSION_NAME)
        if data is None:
            return

        try:
            self.print_verbose("Copying f3d node tree")
            node_tree_copy(self.base_node_tree, blender_material.node_tree)
        except Exception as exc:
            raise Exception("Error copying node tree, material may not render correctly") from exc
        try:
            createScenePropertiesForMaterial(blender_material)
        except Exception as exc:
            raise Exception("Error creating scene properties, node tree may be invalid") from exc

        try:
            blender_material.is_f3d = True
            blender_material.mat_ver = 5
            blender_material.f3d_update_flag = True

            f3d_mat: F3DMaterialProperty = blender_material.f3d_mat
            f3d_mat.combiner_from_dict(data.get("combiner", {}))
            f3d_mat.f3d_colors_from_dict(data)
            f3d_mat.rdp_settings.from_dict(data)
            f3d_mat.extra_texture_settings_from_dict(data)

            ex1_data = data.get("extensions", {}).get(EX1_MATERIAL_EXTENSION_NAME, None)
            if ex1_data is not None:  # F3DLX
                f3d_mat.rdp_settings.f3dex1_geo_mode_from_dict(ex1_data.get("geometryMode", {}))

            ex3_data = data.get("extensions", {}).get(EX3_MATERIAL_EXTENSION_NAME, None)
            if ex3_data is not None:  # F3DEX3
                f3d_mat.rdp_settings.f3dex3_geo_mode_from_dict(ex3_data.get("geometryMode", {}))
                f3d_mat.f3dex3_colors_from_dict(ex3_data)

            for num, tex_info in data.get("textures", {}).items():
                index = tex_info["index"]
                self.print_verbose(f"Importing f3d texture {index}")
                gltf2_texture = gltf.data.textures[index]
                if num == "0":
                    self.gltf2_to_f3d_texture(gltf2_texture, gltf, f3d_mat.tex0)
                elif num == "1":
                    self.gltf2_to_f3d_texture(gltf2_texture, gltf, f3d_mat.tex1)
                else:
                    raise Exception("Fast64 does not support more than 2 textures")
        except Exception as exc:
            raise Exception("Failed to import fast64 extension data") from exc
        finally:
            blender_material.f3d_update_flag = False

        # HACK: The simplest way to cause a reload here is to have a valid material context
        gltf_temp_obj = bpy.data.objects["##gltf-import:tmp-object##"]
        bpy.context.scene.collection.objects.link(gltf_temp_obj)
        try:
            bpy.context.view_layer.objects.active = gltf_temp_obj
            gltf_temp_obj.active_material = blender_material
            update_node_values(blender_material, bpy.context, True)
            update_tex_values_and_formats(blender_material, bpy.context)
            update_rendermode_preset(blender_material, bpy.context)
        finally:
            bpy.context.view_layer.objects.active = None
            bpy.context.scene.collection.objects.unlink(gltf_temp_obj)

    def gather_import_node_after_hook(self, _vnode, gltf_node, blender_object, _gltf):
        data = self.get_extension(gltf_node, MESH_EXTENSION_NAME)
        if data is None:
            return

        new_data = data.get("extensions", {}).get(NEW_MESH_EXTENSION_NAME, None)
        if new_data:
            blender_object.use_f3d_culling = new_data.get("use_culling", True)


MATERIAL_EXTENSION_NAME = "FAST64_materials_f3d"
EX1_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dlx"
EX3_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dex3"
SAMPLER_EXTENSION_NAME = "FAST64_sampler_f3d"
MESH_EXTENSION_NAME = "FAST64_mesh_f3d"
NEW_MESH_EXTENSION_NAME = "FAST64_mesh_f3d_new"


class F3DGlTFSettings(PropertyGroup):
    use: BoolProperty(default=True, name="Export/Import F3D extensions")

    raise_texture_limits: BoolProperty(name="Tex Limits", default=True)
    raise_large_multitex: BoolProperty(
        name="Large Multitex",
        description="Raise an error when a multitexture has two large textures. This can theoretically be supported",
        default=True,
    )
    raise_large_tex: BoolProperty(
        name="Large Tex",
        description="Raise an error when a polygon's textures in large texture mode can´t fit in one full TMEM load",
        default=True,
    )
    raise_rendermode: BoolProperty(
        name="Rendermode",
        description="Raise an error when a material uses an invalid combination of rendermode presets. Does not raise in the normal exporter",
        default=True,
    )
    raise_non_f3d_mat: BoolProperty(
        name="Non F3D Mat",
        description="Raise an error when a material is not an f3d material. Useful for tiny3d",
        default=False,
    )
    raise_bad_mat_slot: BoolProperty(
        name="Bad Slot",
        description="Raise an error when the mesh has no materials, a face's material slot is empty or invalid",
        default=False,
    )
    raise_no_uvmap: BoolProperty(
        name="No UVMap",
        description="Raise an error when a mesh with f3d materials has no uv layer named UVMap",
        default=True,
    )

    # TODO: Large texture mode errors and other per mesh stuff

    def to_dict(self):
        return {
            "use": self.use,
            "raiseTextureLimits": self.raise_texture_limits,
            "raiseLargeMultitex": self.raise_large_multitex,
            "raiseLargeTex": self.raise_large_tex,
            "raiseRenderMode": self.raise_rendermode,
            "raiseNonF3DMat": self.raise_non_f3d_mat,
            "raiseBadMatSlot": self.raise_bad_mat_slot,
            "raiseNoUVMap": self.raise_no_uvmap,
        }

    def from_dict(self, data: dict):
        self.use = data.get("use", self.use)
        self.raise_texture_limits = data.get("raiseTextureLimits", self.raise_texture_limits)
        self.raise_large_multitex = data.get("raiseLargeMultitex", self.raise_large_multitex)
        self.raise_large_tex = data.get("raiseLargeTex", self.raise_large_tex)
        self.raise_rendermode = data.get("raiseRenderMode", self.raise_rendermode)
        self.raise_non_f3d_mat = data.get("raiseNonF3DMat", self.raise_non_f3d_mat)
        self.raise_bad_mat_slot = data.get("raiseBadMatSlot", self.raise_bad_mat_slot)
        self.raise_no_uvmap = data.get("raiseNoUVMap", self.raise_no_uvmap)

    def draw_props(self, layout: UILayout, import_context=False):
        col = layout.column()
        col.prop(self, "use", text=f"{'Import' if import_context else 'Export'} F3D extensions")
        if not self.use:
            return

        gbi, scene = get_F3D_GBI(), bpy.context.scene
        col.box().label(
            text=f"Scene Microcode: {scene.bl_rna.properties['f3d_type'].enum_items[scene.f3d_type].name}",
            icon="INFO",
        )
        extensions = [MATERIAL_EXTENSION_NAME, SAMPLER_EXTENSION_NAME, MESH_EXTENSION_NAME]
        if gbi.F3DEX_GBI:
            extensions.append(EX1_MATERIAL_EXTENSION_NAME)
        if gbi.F3DEX_GBI_3:
            extensions.append(EX3_MATERIAL_EXTENSION_NAME)
        if not gbi.F3D_OLD_GBI:
            extensions.append(NEW_MESH_EXTENSION_NAME)
        multilineLabel(col.box(), ",\n".join(extensions))
        col.separator()

        if import_context:
            return

        box = col.box().column()
        box.box().label(text="Raise Errors:", icon="ERROR")

        row = box.row()
        row.prop(self, "raise_texture_limits", toggle=True)
        limits_row = row.row()
        limits_row.enabled = self.raise_texture_limits
        limits_row.prop(self, "raise_large_multitex", toggle=True)
        limits_row.prop(self, "raise_large_tex", toggle=True)

        row = box.row()
        row.prop(self, "raise_rendermode", toggle=True)
        row.prop(self, "raise_non_f3d_mat", toggle=True)
        row.prop(self, "raise_no_uvmap", toggle=True)

        row = box.row()
        row.prop(self, "raise_bad_mat_slot", toggle=True)
