import bpy
from bpy.props import FloatProperty
from bpy.types import PropertyGroup
from bpy.utils import register_class, unregister_class

from .mk64_properties import mk64_props_register, mk64_props_unregister
from .mk64_operators import mk64_operator_register, mk64_operator_unregister
from .mk64_panels import mk64_panel_register, mk64_panel_unregister


# mk64_classes = (,)


def mk64_register(registerPanels):
    mk64_props_register()
    mk64_operator_register()
    # for cls in mk64_classes:
    # register_class(cls)
    if registerPanels:
        mk64_panel_register()


def mk64_unregister(registerPanel):
    # for cls in reversed(mk64_classes):
    # unregister_class(cls)
    if registerPanel:
        mk64_panel_unregister()
    mk64_operator_unregister()
    mk64_props_unregister()
