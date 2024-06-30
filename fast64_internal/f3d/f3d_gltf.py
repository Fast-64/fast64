import bpy
from bpy.types import Image, NodeTree

from ..gltf_utility import GlTF2SubExtension
from .f3d_gbi import F3D, get_F3D_GBI
from .f3d_material import (
    all_combiner_uses,
    createScenePropertiesForMaterial,
    link_f3d_material_library,
    update_node_values,
    update_tex_values_and_formats,
    F3DMaterialProperty,
    TextureProperty,
)

# TODO: Check glTF addon version instead
if bpy.app.version >= (3, 6, 0):
    if bpy.app.version >= (3, 6, 5):
        from io_scene_gltf2.blender.exp.material.gltf2_blender_gather_image import __is_blender_image_a_webp
    from io_scene_gltf2.blender.exp.material.gltf2_blender_gather_image import (
        __gather_name,
        __make_image,
        __gather_uri,
        __gather_buffer_view,
        __is_blender_image_a_jpeg,
    )
    from io_scene_gltf2.blender.exp.material.extensions.gltf2_blender_image import ExportImage
else:
    from io_scene_gltf2.blender.exp.gltf2_blender_gather_image import (
        __gather_name,
        __make_image,
        __gather_uri,
        __gather_buffer_view,
        __is_blender_image_a_jpeg,
    )
    from io_scene_gltf2.blender.exp.gltf2_blender_image import ExportImage

from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.blender.imp.gltf2_blender_image import BlenderImage
from io_scene_gltf2.io.com.gltf2_io_constants import TextureFilter, TextureWrap

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


def is_blender_image_a_webp(image: Image) -> bool:
    if bpy.data.version < (3, 6, 5):
        return False
    return __is_blender_image_a_webp(image)


def __get_mime_type_of_image(name: str, export_settings: dict):
    image = bpy.data.images[name]
    if image.channels == 4:  # Has alpha channel, doesn´t actually check for transparency
        if is_blender_image_a_webp(image):
            return "image/webp"
        return "image/png"

    if export_settings["gltf_image_format"] == "AUTO":
        if __is_blender_image_a_jpeg(image):
            return "image/jpeg"
        elif is_blender_image_a_webp(image):
            return "image/webp"
        return "image/png"

    elif export_settings["gltf_image_format"] == "JPEG":
        return "image/jpeg"


def get_gltf_image_from_blender_image(blender_image_name: str, export_settings: dict):
    image_data = ExportImage.from_blender_image(bpy.data.images[blender_image_name])

    if bpy.app.version > (4, 1, 0):
        name = __gather_name(image_data, None, export_settings)
    else:
        name = __gather_name(image_data, export_settings)
    mime_type = __get_mime_type_of_image(blender_image_name, export_settings)

    uri = __gather_uri(image_data, mime_type, name, export_settings)
    buffer_view = __gather_buffer_view(image_data, mime_type, name, export_settings)

    image = __make_image(buffer_view, None, None, mime_type, name, uri, export_settings)
    return image


class Fast64Extension(GlTF2SubExtension):
    extension_name = "EXT_fast64"

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
            raise Exception("Failed to import f3d material node tree") from exc

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
        self.append_gltf2_extension(sampler, f3d_tex.to_dict())
        return sampler

    def sampler_to_f3d(self, gltf2_sampler, f3d_tex: TextureProperty):
        data = self.get_gltf2_extension(gltf2_sampler)
        if data is None:
            return
        f3d_tex.from_dict(data)

    def f3d_to_gltf2_texture(
        self,
        f3d_mat: F3DMaterialProperty,
        f3d_texture,
        export_settings: dict,
    ):
        source = get_gltf_image_from_blender_image(f3d_texture.tex.name, export_settings)
        sampler = self.sampler_from_f3d(f3d_mat, f3d_texture)
        return gltf2_io.Texture(
            extensions=None,
            extras=None,
            name=None,
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
                f3d_tex.tex.colorspace_settings.is_data = False
                f3d_tex.tex.colorspace_settings.name = "sRGB"
                

    def f3d_to_glTF2_texture_info(
        self,
        f3d_mat: F3DMaterialProperty,
        f3d_texture: TextureProperty,
        export_settings: dict,
    ):
        return gltf2_io.TextureInfo(
            extensions=None,
            extras=None,
            index=self.f3d_to_gltf2_texture(f3d_mat, f3d_texture, export_settings),
            tex_coord=None,  # TODO: Convert high and low to tex_coords
        )

    def gather_material_hook(self, gltf2_material, blender_material, export_settings: dict):
        if not blender_material.is_f3d:
            return
        data = {}

        f3d_mat: F3DMaterialProperty = blender_material.f3d_mat
        use_dict = all_combiner_uses(f3d_mat)

        data["combiner"] = f3d_mat.combiner_to_dict()
        data["colors"] = f3d_mat.colors_to_dict(self.f3d, use_dict)
        data.update(f3d_mat.rdp_settings.to_dict())
        data["textureSettings"] = f3d_mat.extra_texture_settings_to_dict()

        textures = {}
        data["textures"] = textures
        pbr = gltf2_material.pbr_metallic_roughness
        if use_dict["Texture 0"]:
            textures["0"] = self.f3d_to_glTF2_texture_info(f3d_mat, f3d_mat.tex0, export_settings)
        if use_dict["Texture 1"]:
            textures["1"] = self.f3d_to_glTF2_texture_info(f3d_mat, f3d_mat.tex1, export_settings)
        if f3d_mat.is_multi_tex:
            pbr.base_color_texture = textures["0"]
            pbr.metallic_roughness_texture = textures["1"]
        else:
            pbr.base_color_texture = textures.values()[0]
        self.append_gltf2_extension(gltf2_material, data)

    def gather_node_hook(self, gltf2_node, blender_object, _export_settings: dict):
        data = {}
        if self.f3d.F3DEX_GBI or self.f3d.F3DEX_GBI_2:
            data["use_culling"] = blender_object.use_f3d_culling
        self.append_gltf2_extension(gltf2_node, data)

    # Importing

    def gather_import_material_after_hook(
        self,
        gltf_material,
        _vertex_color,
        blender_material,
        gltf,
    ):
        data = self.get_gltf2_extension(gltf_material)
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
            f3d_mat.colors_from_dict(data.get("colors", {}))
            f3d_mat.rdp_settings.from_dict(data)
            f3d_mat.extra_texture_settings_from_dict(data.get("textureSettings", {}))

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
        finally:
            bpy.context.view_layer.objects.active = None
            bpy.context.scene.collection.objects.unlink(gltf_temp_obj)

    def gather_import_node_after_hook(self, _vnode, gltf_node, blender_object, _gltf):
        data = self.get_gltf2_extension(gltf_node)
        if data is None:
            return
        blender_object.use_f3d_culling = data.get("use_culling", True)
