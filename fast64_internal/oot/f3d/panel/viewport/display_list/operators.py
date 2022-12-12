from bpy.types import Operator, Mesh
from bpy.ops import object
from bpy.path import abspath
from mathutils import Matrix
from ......utility import PluginError, raisePluginError
from ......f3d.f3d_parser import importMeshC, getImportData
from ......f3d.f3d_gbi import DLFormat, F3D
from .....oot_utility import ootGetObjectPath, getOOTScale
from .....oot_model_classes import OOTF3DContext, ootGetIncludedAssetData
from .....oot_texture_array import ootReadTextureArrays
from .classes import OOTDLImportSettings


class OOT_ImportDL(Operator):
    # set bl_ properties
    bl_idname = "object.oot_import_dl"
    bl_label = "Import DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        from .....oot_f3d_writer import ootReadActorScale  # temp circular import fix

        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        try:
            settings: OOTDLImportSettings = context.scene.fast64.oot.DLImportSettings
            name = settings.name
            folderName = settings.folder
            importPath = abspath(settings.customPath)
            isCustomImport = settings.isCustom
            basePath = abspath(context.scene.ootDecompPath) if not isCustomImport else importPath
            removeDoubles = settings.removeDoubles
            importNormals = settings.importNormals
            drawLayer = settings.drawLayer
            overlayName = settings.actorOverlayName
            flipbookUses2DArray = settings.flipbookUses2DArray
            flipbookArrayIndex2D = settings.flipbookArrayIndex2D if flipbookUses2DArray else None

            paths = [ootGetObjectPath(isCustomImport, importPath, folderName)]
            data = getImportData(paths)
            f3dContext = OOTF3DContext(F3D("F3DEX2/LX2", False), [name], basePath)

            scale = getOOTScale(settings.actorScale)
            if not isCustomImport:
                data = ootGetIncludedAssetData(basePath, paths, data) + data

                if overlayName is not None:
                    ootReadTextureArrays(basePath, overlayName, name, f3dContext, False, flipbookArrayIndex2D)
                if settings.autoDetectActorScale:
                    scale = ootReadActorScale(basePath, overlayName, False)

            obj = importMeshC(
                data,
                name,
                scale,
                removeDoubles,
                importNormals,
                drawLayer,
                f3dContext,
            )
            obj.ootActorScale = scale / context.scene.ootBlenderScale

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
        from .....oot_f3d_writer import ootConvertMeshToC  # temp circular import fix


        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("Mesh not selected.")
        obj = context.active_object
        if type(obj.data) is not Mesh:
            raise PluginError("Mesh not selected.")

        finalTransform = Matrix.Scale(getOOTScale(obj.ootActorScale), 4)

        try:
            # exportPath, levelName = getPathAndLevel(context.scene.geoCustomExport,
            # 	context.scene.geoExportPath, context.scene.geoLevelName,
            # 	context.scene.geoLevelOption)

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
