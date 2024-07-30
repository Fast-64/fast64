import bpy
from bpy.types import PropertyGroup
from bpy.utils import register_class, unregister_class
from .f3d.properties import MK64CourseDLImportSettings, f3d_props_register, f3d_props_unregister
from .f3d.operators import MK64_ImportCourseDL
from ..panels import MK64_Panel


class MK64_Properties(PropertyGroup):
    """Global MK64 Scene Properties found under scene.fast64.mk64"""

    # Import Course DL
    CourseDLImportSettings: bpy.props.PointerProperty(type=MK64CourseDLImportSettings)

    @staticmethod
    def upgrade_changed_props():
        pass


class MK64_ImportCourseDLPanel(MK64_Panel):
    bl_idname = "MK64_PT_import_course_DL"
    bl_label = "MK64 Import Course DL"
    bl_options = set()  # default to open
    bl_order = 0  # force to front

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding

        col.operator(MK64_ImportCourseDL.bl_idname)
        CourseDLImportSettings: MK64CourseDLImportSettings = context.scene.fast64.mk64.CourseDLImportSettings
        CourseDLImportSettings.draw_props(col)

        box = col.box().column()
        box.label(text="All data must be contained within file.")
        box.label(text="The only exception are pngs converted to inc.c.")


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
