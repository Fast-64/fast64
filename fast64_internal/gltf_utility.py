from pprint import pprint
from typing import Callable
import functools

import addon_utils
import bpy
from bpy.types import Image


def find_glTF2_addon():
    for mod in addon_utils.modules():  # pylint: disable=not-an-iterable
        if mod.__name__ == "io_scene_gltf2":
            return mod
    raise ValueError("glTF2 addon not found")


CUR_GLTF2_ADDON = None


def update_gltf2_addon():
    global CUR_GLTF2_ADDON
    CUR_GLTF2_ADDON = find_glTF2_addon()


def get_version() -> tuple[int, int, int]:
    global CUR_GLTF2_ADDON
    if CUR_GLTF2_ADDON is None:
        CUR_GLTF2_ADDON = find_glTF2_addon()
    return CUR_GLTF2_ADDON.bl_info.get("version", (-1, -1, -1))


def is_blender_image_a_webp(image: Image) -> bool:
    if get_version() >= (4, 3, 13):
        from io_scene_gltf2.blender.exp.material.image import (  # type: ignore # pylint: disable=import-error, import-outside-toplevel
            __is_blender_image_a_webp,
        )
    elif get_version() >= (3, 6, 5):
        from io_scene_gltf2.blender.exp.material.gltf2_blender_gather_image import (  # type: ignore # pylint: disable=import-error, import-outside-toplevel
            __is_blender_image_a_webp,
        )

        return __is_blender_image_a_webp(image)
    return False


def __get_mime_type_of_image(name: str, export_settings: dict):
    image = bpy.data.images[name]
    if image.channels == 4:  # Has alpha channel, doesn´t actually check for transparency
        if is_blender_image_a_webp(image):
            return "image/webp"
        return "image/png"

    if export_settings["gltf_image_format"] == "AUTO":
        if get_version() >= (4, 3, 13):
            from io_scene_gltf2.blender.exp.material.image import (  # pylint: disable=import-error, import-outside-toplevel # type: ignore
                __is_blender_image_a_jpeg,
            )
        elif get_version() >= (3, 6, 0):
            from io_scene_gltf2.blender.exp.material.gltf2_blender_gather_image import (  # pylint: disable=import-error, import-outside-toplevel # type: ignore
                __is_blender_image_a_jpeg,
            )
        else:
            from io_scene_gltf2.blender.exp.gltf2_blender_gather_image import (  # pylint: disable=import-error, import-outside-toplevel # type: ignore
                __is_blender_image_a_jpeg,
            )
        if __is_blender_image_a_jpeg(image):
            return "image/jpeg"
        elif is_blender_image_a_webp(image):
            return "image/webp"
        return "image/png"

    elif export_settings["gltf_image_format"] == "JPEG":
        return "image/jpeg"


def get_gltf_image_from_blender_image(blender_image_name: str, export_settings: dict):
    if get_version() >= (4, 3, 13):
        from io_scene_gltf2.blender.exp.material.encode_image import (  # type: ignore # pylint: disable=import-error, import-outside-toplevel
            ExportImage,
        )
        from io_scene_gltf2.blender.exp.material.image import (  # pylint: disable=import-error, import-outside-toplevel # type: ignore
            __gather_name,
            __make_image,
            __gather_uri,
            __gather_buffer_view,
        )
    elif get_version() >= (3, 6, 0):
        from io_scene_gltf2.blender.exp.material.extensions.gltf2_blender_image import (  # type: ignore # pylint: disable=import-error, import-outside-toplevel
            ExportImage,
        )
        from io_scene_gltf2.blender.exp.material.gltf2_blender_gather_image import (  # pylint: disable=import-error, import-outside-toplevel # type: ignore
            __gather_name,
            __make_image,
            __gather_uri,
            __gather_buffer_view,
        )
    else:
        from io_scene_gltf2.blender.exp.gltf2_blender_image import ExportImage  # type: ignore # pylint: disable=import-error, import-outside-toplevel
        from io_scene_gltf2.blender.exp.gltf2_blender_gather_image import (  # pylint: disable=import-error, import-outside-toplevel # type: ignore
            __gather_name,
            __make_image,
            __gather_uri,
            __gather_buffer_view,
        )
    image_data = ExportImage.from_blender_image(bpy.data.images[blender_image_name])

    if bpy.app.version > (4, 1, 1):
        name = __gather_name(image_data, None, export_settings)
    else:
        name = __gather_name(image_data, export_settings)
    mime_type = __get_mime_type_of_image(blender_image_name, export_settings)

    uri = __gather_uri(image_data, mime_type, name, export_settings)
    buffer_view = __gather_buffer_view(image_data, mime_type, name, export_settings)

    if get_version() >= (3, 3, 0):
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
        if data and any(data):
            self.print_verbose(data)
        return data


def get_gltf_settings(context):
    return context.scene.fast64.settings.glTF


def is_import_context(context):
    return context.space_data.active_operator.bl_idname == "IMPORT_SCENE_OT_gltf"


def prefix_function(original: Callable, prefix: Callable):
    original = getattr(original, "fast64_og_func", original)

    @functools.wraps(original)
    def run(*args, **kwargs):
        prefix(*args, **kwargs)
        return original(*args, **kwargs)

    setattr(run, "fast64_og_func", original)
    return run


def suffix_function(original: Callable, suffix: Callable):
    """Passes in result as the first arg"""
    original = getattr(original, "fast64_og_func", original)

    @functools.wraps(original)
    def run(*args, **kwargs):
        results = original(*args, **kwargs)
        return suffix(results, *args, **kwargs)

    setattr(run, "fast64_og_func", original)
    return run


def swap_function(original: Callable, new: Callable):
    """Passes in the original function as the first arg"""
    original = getattr(original, "fast64_og_func", original)

    @functools.wraps(original)
    def run(*args, **kwargs):
        return new(original, *args, **kwargs)

    setattr(run, "fast64_og_func", original)
    return run
