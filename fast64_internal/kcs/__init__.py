from .kcs_ui import kcs_panel_register, kcs_panel_unregister
from .kcs_props import kcs_property_register, kcs_property_unregister
from .kcs_operators import kcs_operator_register, kcs_operator_unregister
from bpy.utils import register_class, unregister_class

# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------


def kcs_register(registerPanels):
    if registerPanels:
        kcs_panel_register()
    kcs_operator_register()
    kcs_property_register()


def kcs_unregister(unregisterPanels):
    if unregisterPanels:
        kcs_panel_unregister()
    kcs_operator_unregister()
    kcs_property_unregister()
