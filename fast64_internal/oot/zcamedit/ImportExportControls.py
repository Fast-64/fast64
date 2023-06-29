from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.types import Operator, TOPBAR_MT_file_import, TOPBAR_MT_file_export
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from .CFile import ImportCFile, ExportCFile


class ZCAMEDIT_OT_import_c(Operator, ImportHelper):
    """Import cutscene camera data from a Zelda 64 scene C source file."""

    bl_idname = "zcamedit.import_c"
    bl_label = "Import From C"

    filename_ext = ".c"
    filter_glob: StringProperty(default="*.c", options={"HIDDEN"}, maxlen=4096)

    def execute(self, context):
        ret = ImportCFile(context, self.filepath)
        if ret is not None:
            self.report({"WARNING"}, ret)
            return {"CANCELLED"}
        self.report({"INFO"}, "Import successful")
        return {"FINISHED"}


class ZCAMEDIT_OT_export_c(Operator, ExportHelper):
    """Export cutscene camera into a Zelda 64 scene C source file."""

    bl_idname = "zcamedit.export_c"
    bl_label = "Export Into C"

    filename_ext = ".c"
    filter_glob: StringProperty(default="*.c", options={"HIDDEN"}, maxlen=4096)

    use_floats: BoolProperty(
        name="Use Floats",
        description="Write FOV value as floating point (e.g. 45.0f). If False, write as integer (e.g. 0x42340000)",
        default=False,
    )
    use_tabs: BoolProperty(
        name="Use Tabs",
        description="Indent commands with tabs rather than 4 spaces. For decomp toolchain compatibility",
        default=True,
    )
    use_cscmd: BoolProperty(
        name="Use CS_CMD defines",
        description="Write first parameter as CS_CMD_CONTINUE or CS_CMD_STOP vs. 0 or -1",
        default=False,
    )

    def execute(self, context):
        ret = ExportCFile(context, self.filepath, self.use_floats, self.use_tabs, self.use_cscmd)
        if ret is not None:
            self.report({"WARNING"}, ret)
            return {"CANCELLED"}
        self.report({"INFO"}, "Export successful")
        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(ZCAMEDIT_OT_import_c.bl_idname, text="Z64 cutscene C source (.c)")


def menu_func_export(self, context):
    self.layout.operator(ZCAMEDIT_OT_export_c.bl_idname, text="Z64 cutscene C source (.c)")


def ImportExportControls_register():
    register_class(ZCAMEDIT_OT_import_c)
    register_class(ZCAMEDIT_OT_export_c)
    TOPBAR_MT_file_import.append(menu_func_import)
    TOPBAR_MT_file_export.append(menu_func_export)


def ImportExportControls_unregister():
    TOPBAR_MT_file_export.remove(menu_func_export)
    TOPBAR_MT_file_import.remove(menu_func_import)
    unregister_class(ZCAMEDIT_OT_export_c)
    unregister_class(ZCAMEDIT_OT_import_c)
