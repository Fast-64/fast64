from .properties import MK64CourseDLImportSettings
from .operators import MK64_ImportCourseDL
from ...panels import MK64_Panel
from ...utility import prop_split


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
        course_DL_import_settings: MK64CourseDLImportSettings = context.scene.fast64.mk64.course_DL_import_settings
        course_DL_import_settings.draw_props(col)
        prop_split(col, context.scene.fast64.mk64, "scale", "Scale")

        box = col.box().column()
        box.label(text="All data must be contained within file.")
        box.label(text="The only exception are pngs converted to inc.c.")
