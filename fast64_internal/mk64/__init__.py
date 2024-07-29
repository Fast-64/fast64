import bpy
from bpy.types import PropertyGroup, Operator
from bpy.utils import register_class, unregister_class
from .f3d.properties import MK64CourseDLImportSettings, f3d_props_register, f3d_props_unregister
from .f3d_course_parser import MK64F3DContext, parseCourseVtx
from ..f3d.f3d_material import createF3DMat
from ..f3d.f3d_gbi import get_F3D_GBI
from ..f3d.f3d_parser import getImportData, importMeshC
from ..panels import MK64_Panel
from ..utility import prop_split
from ..utility import raisePluginError


class MK64_Properties(PropertyGroup):
    """Global MK64 Scene Properties found under scene.fast64.mk64"""

    # Import Course DL
    CourseDLImportSettings: bpy.props.PointerProperty(type=MK64CourseDLImportSettings)

    @staticmethod
    def upgrade_changed_props():
        pass


class MK64_ImportCourseDL(Operator):
    # set bl_ properties
    bl_idname = "scene.fast64_mk64_course_import_dl"
    bl_label = "Import Course DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            importSettings: MK64CourseDLImportSettings = context.scene.fast64.mk64.CourseDLImportSettings
            name = importSettings.name
            importPath = bpy.path.abspath(importSettings.path)
            basePath = bpy.path.abspath(importSettings.basePath)
            scaleValue = importSettings.scale

            removeDoubles = importSettings.removeDoubles
            importNormals = importSettings.importNormals
            drawLayer = ("Opaque", "Opaque", "Opaque")

            paths = [importPath]

            if "course_data" in importPath:
                paths += [importPath.replace("course_data", "course_displaylists.inc")]

            paths += [
                importPath.replace("course_data", "course_textures.linkonly").replace(
                    "course_displaylists.inc", "course_textures.linkonly"
                )
            ]

            data = getImportData(paths)

            material = createF3DMat(None)
            f3d_mat = material.f3d_mat
            f3d_mat.rdp_settings.set_rendermode = importSettings.enableRenderModeDefault
            f3d_mat.combiner1.A = "TEXEL0"
            f3d_mat.combiner1.B = "0"
            f3d_mat.combiner1.C = "SHADE"
            f3d_mat.combiner1.D = "0"
            f3d_mat.combiner1.A_alpha = "TEXEL0"
            f3d_mat.combiner1.B_alpha = "0"
            f3d_mat.combiner1.C_alpha = "SHADE"
            f3d_mat.combiner1.D_alpha = "0"
            f3d_mat.combiner2.name = ""
            f3d_mat.combiner2.A = "TEXEL0"
            f3d_mat.combiner2.B = "0"
            f3d_mat.combiner2.C = "SHADE"
            f3d_mat.combiner2.D = "0"
            f3d_mat.combiner2.A_alpha = "TEXEL0"
            f3d_mat.combiner2.B_alpha = "0"
            f3d_mat.combiner2.C_alpha = "SHADE"
            f3d_mat.combiner2.D_alpha = "0"

            f3d_context = MK64F3DContext(get_F3D_GBI(), basePath, material)
            if "course_displaylists" in importPath or "course_data" in importPath:
                vertexPath = importPath.replace("course_displaylists.inc", "course_vertices.inc").replace(
                    "course_data", "course_vertices.inc"
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
