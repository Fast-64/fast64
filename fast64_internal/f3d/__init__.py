from bpy.types import PropertyGroup
from bpy.props import PointerProperty

from .f3d_parser import *
from .f3d_material import *
from .f3d_render_engine import *
from .f3d_gbi import *
from .bsdf_converter import F3D_BSDFConverterProperties, bsdf_converter_register, bsdf_converter_unregister


class F3D_Properties(PropertyGroup):
    """
    Properties in scene.fast64.f3d.
    All new scene f3d properties should be children of this property group.
    """

    bsdf_converter: PointerProperty(name="BSDF Converter", type=F3D_BSDFConverterProperties)


classes = (F3D_Properties,)


def f3d_register(register_panel=True):
    bsdf_converter_register()
    for cls in classes:
        register_class(cls)


def f3d_unregister(register_panel=True):
    for cls in reversed(classes):
        unregister_class(cls)
    bsdf_converter_unregister()
