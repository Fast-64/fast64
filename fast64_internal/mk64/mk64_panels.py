# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations

from bpy.utils import register_class, unregister_class

from ..utility import prop_split
from ..panels import MK64_Panel

from .mk64_properties import MK64_ImportProperties
from .mk64_operators import MK64_ImportCourseDL, MK64_ExportCourse


class MK64_ImportCourseDLPanel(MK64_Panel):
    bl_idname = "MK64_PT_import_course_DL"
    bl_label = "MK64 Import Course DL"
    bl_order = 0  # force to front

    # called every frame
    def draw(self, context):
        col = self.layout.column()

        col.operator(MK64_ImportCourseDL.bl_idname)
        course_DL_import_settings: MK64_ImportProperties = context.scene.fast64.mk64.course_DL_import_settings
        course_DL_import_settings.draw_props(col)
        prop_split(col, context.scene.fast64.mk64, "scale", "Scale")

        box = col.box().column()
        box.label(text="All data must be contained within file.")
        box.label(text="The only exception are pngs converted to inc.c.")


class MK64_ExportCoursePanel(MK64_Panel):
    bl_label = "MK64 Export Course"
    bl_idname = "MK64_PT_export_course"
    bl_context = "objectmode"

    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding
        col.operator(MK64_ExportCourse.bl_idname)
        course_settings: MK64_ExportProperties = context.scene.fast64.mk64.course_export_settings
        course_settings.draw_props(col)
        prop_split(col, context.scene.fast64.mk64, "scale", "Scale")


class MK64_ObjectPanel(MK64_Panel):
    bl_label = "MK64 Object Inspector"
    bl_idname = "MK64_PT_object_inspector"
    bl_context = "object"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        box = self.layout.box()
        box.label(text="MK64 Object Properties")
        obj = context.object
        props = obj.fast64.mk64
        if obj.type == "MESH":
            self.draw_mesh_props(box, props)
        else:
            prop_split(box, props, "obj_type", "object type")

    def draw_mesh_props(self, layout: UILayout, props: MK64_ObjectProperties):
        prop_split(layout, props, "has_col", "Has Collision")
        if props.has_col:
            prop_split(layout, props, "section_id", "Section ID")
            prop_split(layout, props, "col_type", "Collision Type")


class MK64_CurvePanel(MK64_Panel):
    bl_label = "MK64 Curve Inspector"
    bl_idname = "MK64_PT_curve_inspector"
    bl_context = "object"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        if context.object.type != "CURVE"
            return None
        return context.object.data is not None

    def draw(self, context):
        pass


mk64_panel_classes = (MK64_ImportCourseDLPanel, MK64_ExportCoursePanel, MK64_ObjectPanel, MK64_CurvePanel)


def mk64_panel_register():
    for cls in mk64_panel_classes:
        register_class(cls)


def mk64_panel_unregister():
    for cls in mk64_panel_classes:
        unregister_class(cls)
