import bpy
from bpy.props import FloatProperty
from bpy.types import PropertyGroup
from bpy.utils import register_class, unregister_class
from .f3d.properties import MK64CourseDLImportSettings, f3d_props_register, f3d_props_unregister
from .f3d.operators import MK64_ImportCourseDL
from .f3d.panels import MK64_ImportCourseDLPanel
from ..render_settings import on_update_render_settings


class MK64_Properties(PropertyGroup):
    """Global MK64 Scene Properties found under scene.fast64.mk64"""

    # Import Course DL
    course_DL_import_settings: bpy.props.PointerProperty(type=MK64CourseDLImportSettings)
    scale: FloatProperty(name="F3D Blender Scale", default=100, update=on_update_render_settings)
    

    @staticmethod
    def upgrade_changed_props():
        pass


mk64_classes = (MK64_Properties,)

mk64_panel_classes = (
    MK64_ImportCourseDL,
    MK64_ImportCourseDLPanel,
)


def mk64_panel_register():
    for cls in mk64_panel_classes:
        register_class(cls)


def mk64_panel_unregister():
    for cls in mk64_panel_classes:
        unregister_class(cls)


def mk64_register(registerPanels):
    f3d_props_register()
    for cls in mk64_classes:
        register_class(cls)
    if registerPanels:
        mk64_panel_register()


def mk64_unregister(registerPanel):
    for cls in reversed(mk64_classes):
        unregister_class(cls)
    if registerPanel:
        mk64_panel_unregister()
    f3d_props_unregister()
