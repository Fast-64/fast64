import bpy
from bpy.types import Operator
from ..f3d_course_parser import MK64F3DContext, parseCourseVtx
from ...f3d.f3d_material import createF3DMat
from ...f3d.f3d_gbi import get_F3D_GBI
from ...f3d.f3d_parser import getImportData, importMeshC
from ...utility import raisePluginError
from .properties import MK64CourseDLImportSettings


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
            drawLayer = "Opaque"

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
