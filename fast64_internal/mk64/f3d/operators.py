import bpy
from bpy.types import Operator
from ..mk64_model_classes import MK64F3DContext, parse_course_vtx
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
            import_settings: MK64CourseDLImportSettings = context.scene.fast64.mk64.course_DL_import_settings
            name = import_settings.name
            import_path = bpy.path.abspath(import_settings.path)
            base_path = bpy.path.abspath(import_settings.base_path)
            scale_value = context.scene.fast64.mk64.scale

            remove_doubles = import_settings.remove_doubles
            import_normals = import_settings.import_normals
            draw_layer = "Opaque"

            paths = [import_path]

            if "course_data" in import_path:
                paths += [import_path.replace("course_data", "course_displaylists.inc")]

            paths += [
                import_path.replace("course_data", "course_textures.linkonly").replace(
                    "course_displaylists.inc", "course_textures.linkonly"
                )
            ]

            data = getImportData(paths)

            material = createF3DMat(None)
            f3d_mat = material.f3d_mat
            f3d_mat.rdp_settings.set_rendermode = import_settings.enable_render_Mode_Default
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

            f3d_context = MK64F3DContext(get_F3D_GBI(), base_path, material)
            if "course_displaylists" in import_path or "course_data" in import_path:
                vertex_path = import_path.replace("course_displaylists.inc", "course_vertices.inc").replace(
                    "course_data", "course_vertices.inc"
                )
                print(vertex_path)
                f3d_context.vertexData["0x4000000"] = parse_course_vtx(vertex_path, f3d_context.f3d)

            importMeshC(
                data,
                name,
                scale_value,
                remove_doubles,
                import_normals,
                draw_layer,
                f3d_context,
            )

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set
