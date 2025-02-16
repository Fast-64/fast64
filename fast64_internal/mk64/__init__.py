import bpy
from bpy.props import FloatProperty
from bpy.types import PropertyGroup
from bpy.utils import register_class, unregister_class
from .f3d.properties import MK64_ImportProperties, MK64_ExportProperties, f3d_props_register, f3d_props_unregister
from .f3d.operators import MK64_ImportCourseDL, MK64_ExportCourse
from .f3d.panels import MK64_ImportCourseDLPanel, MK64_ExportCoursePanel
from ..render_settings import on_update_render_settings


class MK64_Properties(PropertyGroup):
    """Global MK64 Scene Properties found under scene.fast64.mk64"""

    # Import Course DL
    course_DL_import_settings: bpy.props.PointerProperty(type=MK64_ImportProperties)
    # exporter settings, merge with above later?
    course_export_settings: bpy.props.PointerProperty(type=MK64_ExportProperties)
    scale: FloatProperty(name="F3D Blender Scale", default=100, update=on_update_render_settings)

    @staticmethod
    def upgrade_changed_props():
        pass


mk64_classes = (MK64_Properties,)

mk64_panel_classes = (MK64_ImportCourseDL, MK64_ImportCourseDLPanel, MK64_ExportCoursePanel, MK64_ExportCourse)


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
