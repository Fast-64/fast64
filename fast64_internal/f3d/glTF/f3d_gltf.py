from dataclasses import dataclass
import bpy
from bpy.types import NodeTree

from ...gltf_utility import GlTF2SubExtension, get_gltf_image_from_blender_image
from ..f3d_gbi import F3D, get_F3D_GBI
from ..f3d_material import (
    all_combiner_uses,
    trunc_10_2,
    createScenePropertiesForMaterial,
    link_f3d_material_library,
    update_node_values,
    update_tex_values_and_formats,
    update_rendermode_preset,
    F3DMaterialProperty,
    TextureProperty,
)

# We import at the time of export or import, so we can assume the addon already is loaded,
# this also makes it easy to be fully sure we get the correct version

from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.blender.imp.gltf2_blender_image import BlenderImage
from io_scene_gltf2.io.com.gltf2_io_constants import TextureFilter, TextureWrap

MATERIAL_EXTENSION_NAME = "FAST64_materials_f3d"
EX1_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dlx"
EX3_MATERIAL_EXTENSION_NAME = "FAST64_materials_f3dex3"
SAMPLER_EXTENSION_NAME = "FAST64_sampler_f3d"
MESH_EXTENSION_NAME = "FAST64_mesh_f3d_new"

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
    f3d: F3D = None
    base_node_tree: NodeTree = None

    def post_init(self):
        self.f3d: F3D = get_F3D_GBI()
        if not self.extension.importing:
            return
        try:
            self.print_verbose("Linking f3d material library")
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
        if f3d_tex.tex is not None:
            source = get_gltf_image_from_blender_image(f3d_tex.tex.name, export_settings)
        else:
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
        export_settings: dict,
    ):
        tex_info = gltf2_io.TextureInfo(
            extensions=None,
            extras=None,
            index=self.f3d_to_gltf2_texture(f3d_mat, f3d_tex, export_settings),
            tex_coord=None,
        )

        def to_offset(low: float, tex_size: int):
            return trunc_10_2(low) * (1.0 / tex_size)

        transform_data = {}
        size = f3d_tex.get_tex_size()
        offset = [to_offset(f3d_tex.S.low, size[0]), to_offset(f3d_tex.T.low, size[1])]
        if offset != [0.0, 0.0]:
            transform_data = {"offset": offset}

        scale = [2.0 ** (f3d_tex.S.shift * -1.0), 2.0 ** (f3d_tex.T.shift * -1.0)]
        if scale != [1.0, 1.0]:
            transform_data["scale"] = scale

        if transform_data:
            self.append_extension(tex_info, "KHR_texture_transform", transform_data)
        return tex_info

    def gather_material_hook(self, gltf2_material, blender_material, export_settings: dict):
        if not blender_material.is_f3d:
            return
        data = {}

        f3d_mat: F3DMaterialProperty = blender_material.f3d_mat
        rdp = f3d_mat.rdp_settings
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
            textures["0"] = self.f3d_to_glTF2_texture_info(f3d_mat, f3d_mat.tex0, export_settings)
        if use_dict["Texture 1"]:
            textures["1"] = self.f3d_to_glTF2_texture_info(f3d_mat, f3d_mat.tex1, export_settings)

        data["extensions"] = {}
        if self.f3d.F3DEX_GBI:  # F3DLX
            data["extensions"][EX1_MATERIAL_EXTENSION_NAME] = self.extension.Extension(
                name=EX1_MATERIAL_EXTENSION_NAME,
                extension={"geometryMode": rdp.f3dlx_geo_mode_to_dict()},
                required=False,
            )
        if self.f3d.F3DEX_GBI_3:  # F3DEX3
            data["extensions"][EX3_MATERIAL_EXTENSION_NAME] = self.extension.Extension(
                name=EX3_MATERIAL_EXTENSION_NAME,
                extension={"geometryMode": rdp.f3dex3_geo_mode_to_dict(), **f3d_mat.f3dex3_colors_to_dict()},
                required=False,
            )

        self.append_extension(gltf2_material, MATERIAL_EXTENSION_NAME, data)

        # glTF Standard
        pbr = gltf2_material.pbr_metallic_roughness
        if f3d_mat.is_multi_tex:
            pbr.base_color_texture = textures["0"]
            pbr.metallic_roughness_texture = textures["1"]
        elif textures:
            pbr.base_color_texture = list(textures.values())[0]
        pbr.base_color_factor = get_fake_color(data)

        if not f3d_mat.rdp_settings.g_lighting:
            self.append_extension(gltf2_material, "KHR_materials_unlit")

    def gather_node_hook(self, gltf2_node, blender_object, _export_settings: dict):
        data = {}
        if not self.f3d.F3D_OLD_GBI and gltf2_node.mesh:
            data["use_culling"] = blender_object.use_f3d_culling
            self.append_extension(gltf2_node.mesh, MESH_EXTENSION_NAME, data)

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
        blender_object.use_f3d_culling = data.get("use_culling", True)
