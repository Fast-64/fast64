from pprint import pprint
import functools
from typing import Callable

import addon_utils
import bpy
from bpy.types import Image


def find_glTF2_addon():
    for mod in addon_utils.modules():
        if mod.__name__ == "io_scene_gltf2":
            return mod
    else:
        raise ValueError("glTF2 addon not found")


GLTF2_ADDDON = find_glTF2_addon()
GLTF2_ADDON_VERSION = GLTF2_ADDDON.bl_info.get("version", (-1, -1, -1))

if GLTF2_ADDON_VERSION >= (3, 6, 0):
    if GLTF2_ADDON_VERSION:
        from io_scene_gltf2.blender.exp.material.gltf2_blender_gather_image import (
            __is_blender_image_a_webp,
        )  # pylint: disable=import-error
    from io_scene_gltf2.blender.exp.material.gltf2_blender_gather_image import (  # pylint: disable=import-error
        __gather_name,
        __make_image,
        __gather_uri,
        __gather_buffer_view,
        __is_blender_image_a_jpeg,
    )
    from io_scene_gltf2.blender.exp.material.extensions.gltf2_blender_image import (
        ExportImage,
    )  # pylint: disable=import-error
else:
    from io_scene_gltf2.blender.exp.gltf2_blender_gather_image import (  # pylint: disable=import-error
        __gather_name,
        __make_image,
        __gather_uri,
        __gather_buffer_view,
        __is_blender_image_a_jpeg,
    )
    from io_scene_gltf2.blender.exp.gltf2_blender_image import ExportImage  # pylint: disable=import-error


def is_blender_image_a_webp(image: Image) -> bool:
    if GLTF2_ADDON_VERSION < (3, 6, 5):
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

    if GLTF2_ADDON_VERSION >= (3, 3, 0):
        buffer_view, _factor_buffer_view = buffer_view
        uri, _factor_uri = uri

    image = __make_image(buffer_view, None, None, mime_type, name, uri, export_settings)
    return image


class GlTF2SubExtension:
    required: bool = False

    def post_init(self):
        pass

    def __init__(self, extension):
        self.extension = extension
        self.post_init()

    def print_verbose(self, content):
        if self.extension.verbose:
            pprint(content)

    def append_extension(self, gltf_prop, name: str, data: dict | None = None, required=False, skip_if_empty=True):
        if skip_if_empty and not data and data is not None:  # If none, assume it shouldn´t skip
            return
        self.print_verbose(f"Appending {name} extension")
        if data:
            self.print_verbose(data)
        if gltf_prop.extensions is None:
            gltf_prop.extensions = {}
        gltf_prop.extensions[name] = self.extension.Extension(
            name=name,
            extension=data if data else {},
            required=required if required else self.required,
        )
        return gltf_prop.extensions[name]

    def get_extension(self, gltf_prop, name: str):
        if gltf_prop.extensions is None:
            return None
        data = gltf_prop.extensions.get(name, None)
        if any(data):
            self.print_verbose(data)
        return data


def get_gltf_settings(context):
    return context.scene.fast64.settings.glTF


def is_import_context(context):
    return context.space_data.active_operator.bl_idname == "IMPORT_SCENE_OT_gltf"


def prefix_function(function: Callable, prefunction: Callable):
    function = getattr(function, "fast64_og_func", function)

    @functools.wraps(function)
    def run(*args, **kwargs):
        prefunction(*args, **kwargs)
        return function(*args, **kwargs)

    setattr(run, "fast64_og_func", function)
    return run


def suffix_function(function: Callable, suffix_function: Callable):
    """Passes in result as the first arg"""
    function = getattr(function, "fast64_og_func", function)

    @functools.wraps(function)
    def run(*args, **kwargs):
        results = function(*args, **kwargs)
        return suffix_function(results, *args, **kwargs)

    setattr(run, "fast64_og_func", function)
    return run


def swap_function(function: Callable, new_function: Callable):
    """Passes in the original function as the first arg"""
    function = getattr(function, "fast64_og_func", function)

    @functools.wraps(function)
    def run(*args, **kwargs):
        return new_function(function, *args, **kwargs)

    setattr(run, "fast64_og_func", function)
    return run
