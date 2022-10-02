from bpy.types import Operator, Mesh
from bpy.ops import object
from bpy.path import abspath
from mathutils import Matrix
from os import path
from ....utility import PluginError, raisePluginError
from ....f3d.f3d_parser import importMeshC
from ....f3d.f3d_gbi import DLFormat, F3D
from ...oot_utility import ootGetObjectPath
from ...oot_model_classes import OOTF3DContext
from .classes import OOTDLImportSettings


class OOT_ImportDL(Operator):
    # set bl_ properties
    bl_idname = "object.oot_import_dl"
    bl_label = "Import DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        try:
            settings: OOTDLImportSettings = context.scene.fast64.oot.DLImportSettings
            name = settings.name
            folderName = settings.folder
            importPath = abspath(settings.customPath)
            isCustomImport = settings.isCustom
            scale = context.scene.ootActorBlenderScale
            basePath = abspath(context.scene.ootDecompPath)
            removeDoubles = settings.removeDoubles
            importNormals = settings.importNormals
            drawLayer = settings.drawLayer

            filepaths = [ootGetObjectPath(isCustomImport, importPath, folderName)]
            if not isCustomImport:
                filepaths.append(path.join(context.scene.ootDecompPath, "assets/objects/gameplay_keep/gameplay_keep.c"))

            importMeshC(
                filepaths,
                name,
                scale,
                removeDoubles,
                importNormals,
                drawLayer,
                OOTF3DContext(F3D("F3DEX2/LX2", False), [name], basePath),
            )

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class OOT_ExportDL(Operator):
    # set bl_ properties
    bl_idname = "object.oot_export_dl"
    bl_label = "Export DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        from ...oot_f3d_writer import ootConvertMeshToC  # calling it here avoids a circular import

        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("Mesh not selected.")
        obj = context.active_object
        if type(obj.data) is not Mesh:
            raise PluginError("Mesh not selected.")

        finalTransform = Matrix.Scale(context.scene.ootActorBlenderScale, 4)

        try:
            saveTextures = context.scene.saveTextures
            isHWv1 = context.scene.isHWv1
            f3dType = context.scene.f3d_type
            exportSettings = context.scene.fast64.oot.DLExportSettings

            ootConvertMeshToC(
                obj,
                finalTransform,
                f3dType,
                isHWv1,
                DLFormat.Static,
                saveTextures,
                exportSettings,
            )

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set
