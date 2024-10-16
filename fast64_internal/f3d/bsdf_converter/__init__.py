from .operators import bsdf_converter_ops_register, bsdf_converter_ops_unregister
from .ui import bsdf_converter_panel_draw
from .properties import F3D_BSDFConverterProperties, bsdf_converter_props_register, bsdf_converter_props_unregister


def bsdf_converter_register():
    bsdf_converter_ops_register()
    bsdf_converter_props_register()


def bsdf_converter_unregister():
    bsdf_converter_ops_unregister()
    bsdf_converter_props_unregister()
