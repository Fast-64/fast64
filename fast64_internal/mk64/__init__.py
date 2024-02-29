import bpy
from bpy.types import PropertyGroup
from ..f3d.f3d_gbi import get_F3D_GBI
from ..f3d.f3d_material import createF3DMat
from ..f3d.f3d_parser import getImportData, importMeshC
from ..panels import MK64_Panel
from ..utility import prop_split
from bpy.utils import register_class, unregister_class
from ..utility import raisePluginError
from .f3d_course_parser import MK64F3DContext, parseCourseVtx


class MK64_Properties(PropertyGroup):
    """Global MK64 Scene Properties found under scene.fast64.mk64"""

    version: bpy.props.IntProperty(name="MK64_Properties Version", default=0)
    cur_version = 0

    @staticmethod
    def upgrade_changed_props():
        if bpy.context.scene.fast64.mk64.version != MK64_Properties.cur_version:
            bpy.context.scene.fast64.mk64.version = MK64_Properties.cur_version


class MK64_ImportCourseDL(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.fast64_mk64_course_import_dl"
    bl_label = "Import Course DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            name = context.scene.DLImportName
            importPath = bpy.path.abspath(context.scene.DLImportPath)
            basePath = bpy.path.abspath(context.scene.DLImportBasePath)
            scaleValue = context.scene.blenderF3DScale

            removeDoubles = context.scene.DLRemoveDoubles
            importNormals = context.scene.DLImportNormals
            drawLayer = context.scene.DLImportDrawLayer

            paths = [importPath]

            if "course_data" in importPath:
                paths += [importPath.replace("course_data", "course_displaylists")]

            paths += [
                importPath.replace("course_data.inc", "course_textures.linkonly").replace(
                    "course_displaylists.inc", "course_textures.linkonly"
                )
            ]

            data = getImportData(paths)

            f3d_context = MK64F3DContext(get_F3D_GBI(), basePath, createF3DMat(None))
            if "course_displaylists" in importPath or "course_data" in importPath:
                vertexPath = importPath.replace("course_displaylists", "course_vertices").replace(
                    "course_data", "course_vertices"
                )
                print(vertexPath)
                f3d_context.vertexData["0x4000000"] = parseCourseVtx(vertexPath, f3d_context.f3d)

            importMeshC(
                data,
                name,
                scaleValue,
                removeDoubles,
                importNormals,
                drawLayer,
                f3d_context,
            )

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class MK64_ImportCourseDLPanel(MK64_Panel):
    bl_idname = "MK64_import_course_DL_panel_settings"
    bl_label = "MK64 Import Course DL Panel Settings"
    bl_options = set()  # default to open
    bl_order = 0  # force to front

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "SM64"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding

        col.operator(MK64_ImportCourseDL.bl_idname)
        prop_split(col, context.scene, "DLImportName", "Name")
        prop_split(col, context.scene, "DLImportPath", "File")
        prop_split(col, context.scene, "DLImportBasePath", "Base Path")
        prop_split(col, context.scene, "blenderF3DScale", "Scale")
        prop_split(col, context.scene, "DLImportDrawLayer", "Draw Layer")
        col.prop(context.scene, "DLRemoveDoubles")
        col.prop(context.scene, "DLImportNormals")

        box = col.box().column()
        box.label(text="All data must be contained within file.")
        box.label(text="The only exception are pngs converted to inc.c.")

        # col.template_list('F3D_UL_ImportDLPathList', '', context.scene,
        # 	'DLImportOtherFiles', context.scene, 'DLImportOtherFilesIndex')


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
    for cls in mk64_classes:
        register_class(cls)
    if registerPanels:
        mk64_panel_register()


def mk64_unregister(registerPanel):
    for cls in reversed(mk64_classes):
        unregister_class(cls)
    if registerPanel:
        mk64_panel_unregister()
