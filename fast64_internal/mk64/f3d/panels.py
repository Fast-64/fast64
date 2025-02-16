from .properties import MK64_ImportProperties
from .operators import MK64_ImportCourseDL, MK64_ExportCourse
from ...panels import MK64_Panel
from ...utility import prop_split


class MK64_ImportCourseDLPanel(MK64_Panel):
    bl_idname = "MK64_PT_import_course_DL"
    bl_label = "MK64 Import Course DL"
    bl_order = 0  # force to front

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding

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
