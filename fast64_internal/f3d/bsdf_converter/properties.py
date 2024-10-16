from bpy.utils import register_class, unregister_class
from bpy.types import PropertyGroup
from bpy.props import EnumProperty, BoolProperty

from .operators import converter_enum

class F3D_BSDFConverterProperties(PropertyGroup):
    """
    Properties in scene.fast64.f3d.bsdf_converter
    """

    backup: BoolProperty(default=True, name="Backup")
    converter_type: EnumProperty(items=converter_enum, name="Type")
    put_alpha_into_color: BoolProperty(default=False, name="Put Alpha Into Color")
    use_recommended: BoolProperty(default=True, name="Use Recommended For Current Gamemode")
    lights_for_colors: BoolProperty(default=False, name="Lights For Colors")
    default_to_fog: BoolProperty(default=False, name="Default To Fog")
    set_rendermode_without_fog: BoolProperty(default=False, name="Set RenderMode Even Without Fog")


classes = (F3D_BSDFConverterProperties,)


def bsdf_converter_props_register():
    for cls in classes:
        register_class(cls)


def bsdf_converter_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
