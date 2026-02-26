import bpy
import mathutils

from bpy.types import Operator
from bpy.ops import object
from bpy.utils import register_class, unregister_class
from mathutils import Matrix
from typing import Optional
from pathlib import Path

from ...utility import CData, PluginError, ExportUtils, raisePluginError, writeCData, toAlnum
from ...f3d.f3d_parser import importMeshC, getImportData
from ...f3d.f3d_gbi import DLFormat, TextureExportSettings, ScrollMethod, get_F3D_GBI
from ...f3d.f3d_writer import TriangleConverterInfo, removeDL, saveStaticModel, getInfoDict
from ..utility import PathUtils, getOOTScale
from ..model_classes import OOTF3DContext, ootGetIncludedAssetData
from ..texture_array import ootReadTextureArrays
from ..model_classes import OOTModel, OOTGfxFormatter
from ..f3d_writer import ootReadActorScale, writeTextureArraysNew, writeTextureArraysExisting
from .properties import OOTDLImportSettings, OOTDLExportSettings

from ..utility import (
    OOTObjectCategorizer,
    PathUtils,
    ootDuplicateHierarchy,
    ootCleanupScene,
    getOOTScale,
)


class OOTF3DGfxFormatter(OOTGfxFormatter):
    def __init__(self, scrollMethod):
        OOTGfxFormatter.__init__(self, scrollMethod)

    # override the function to give a custom name to the DL array
    def drawToC(self, f3d, gfxList, layer: Optional[str] = None):
        return gfxList.to_c(f3d, name_override=f"{gfxList.name}_{layer.lower()}_dl")


def ootConvertMeshToC(
    originalObj: bpy.types.Object,
    finalTransform: mathutils.Matrix,
    DLFormat: DLFormat,
    saveTextures: bool,
    settings: OOTDLExportSettings,
):
    folderName = settings.folder
    isCustomExport = settings.isCustom
    export_path = Path(settings.customPath) if isCustomExport else bpy.context.scene.fast64.oot.get_decomp_path()
    removeVanillaData = settings.removeVanillaData
    name = toAlnum(originalObj.name)
    assert name is not None
    overlayName = settings.actorOverlayName
    flipbookUses2DArray = settings.flipbookUses2DArray
    flipbookArrayIndex2D = settings.flipbookArrayIndex2D if flipbookUses2DArray else None

    try:
        obj, allObjs = ootDuplicateHierarchy(originalObj, None, False, OOTObjectCategorizer())

        fModel = OOTModel(name, DLFormat, None)
        triConverterInfo = TriangleConverterInfo(obj, None, fModel.f3d, finalTransform, getInfoDict(obj))
        fMeshes = saveStaticModel(
            triConverterInfo, fModel, obj, finalTransform, fModel.name, not saveTextures, False, "oot"
        )

        # Since we provide a draw layer override, there should only be one fMesh.
        for fMesh in fMeshes.values():
            fMesh.draw.name = name

        ootCleanupScene(originalObj, allObjs)

    except Exception as e:
        ootCleanupScene(originalObj, allObjs)
        raise Exception(str(e))

    filename = settings.filename if settings.isCustomFilename else name
    data = CData()
    data.header = f"#ifndef {filename.upper()}_H\n" + f"#define {filename.upper()}_H\n\n" + '#include "ultra64.h"\n'

    if bpy.context.scene.fast64.oot.is_globalh_present():
        data.header += '#include "global.h"\n'

    data.source = f'#include "{filename}.h"\n\n'
    if not isCustomExport:
        data.header += f'#include "{folderName}.h"\n\n'
    else:
        data.header += "\n"

    with PathUtils(False, export_path, "assets/objects/", folderName, isCustomExport) as path_utils:
        path = path_utils.get_assets_path(check_extracted=False, with_decomp_path=True)
        path_utils.set_base_path(path)

        includeDir = settings.customAssetIncludeDir if settings.isCustom else f"assets/objects/{folderName}"
        exportData = fModel.to_c(
            TextureExportSettings(False, saveTextures, includeDir, path), OOTF3DGfxFormatter(ScrollMethod.Vertex)
        )

        data.append(exportData.all())

        if isCustomExport:
            textureArrayData = writeTextureArraysNew(fModel, flipbookArrayIndex2D)
            data.append(textureArrayData)

        data.header += "\n#endif\n"
        writeCData(data, path / f"{filename}.h", path / f"{filename}.c")

        if not isCustomExport:
            writeTextureArraysExisting(
                bpy.context.scene.fast64.oot.get_decomp_path(), overlayName, False, flipbookArrayIndex2D, fModel
            )
            path_utils.add_include_files(name)
            if removeVanillaData:
                headerPath = path / f"{folderName}.h"
                sourcePath = path / f"{folderName}.c"
                removeDL(str(sourcePath), str(headerPath), name)


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
            isCustomImport = settings.isCustom
            importPath = (
                Path(bpy.path.abspath(settings.customPath)).resolve()
                if isCustomImport
                else context.scene.fast64.oot.get_decomp_path()
            )
            basePath = context.scene.fast64.oot.get_decomp_path() if not isCustomImport else importPath.parent
            removeDoubles = settings.removeDoubles
            importNormals = settings.importNormals
            drawLayer = settings.drawLayer
            overlayName = settings.actorOverlayName
            flipbookUses2DArray = settings.flipbookUses2DArray
            flipbookArrayIndex2D = settings.flipbookArrayIndex2D if flipbookUses2DArray else None

            with PathUtils(True, importPath, "assets/objects", folderName, isCustomImport) as path_utils:
                paths = [
                    path_utils.get_object_header_path(),
                    path_utils.get_object_source_path(),
                ]

            filedata = getImportData(paths)
            f3dContext = OOTF3DContext(get_F3D_GBI(), [name], str(basePath))
            f3dContext.ignore_tlut = '.inc.c"' in filedata

            scale = None
            if not isCustomImport:
                filedata = ootGetIncludedAssetData(basePath, paths, filedata, True) + filedata

                if overlayName is not None:
                    ootReadTextureArrays(basePath, overlayName, name, f3dContext, False, flipbookArrayIndex2D)
                if settings.autoDetectActorScale:
                    scale = ootReadActorScale(basePath, overlayName, False)

            if scale is None:
                scale = getOOTScale(settings.actorScale)

            obj = importMeshC(
                filedata,
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
        with ExportUtils() as export_utils:
            obj = None
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            if len(context.selected_objects) == 0:
                raise PluginError("Mesh not selected.")
            obj = context.active_object
            if obj.type != "MESH":
                raise PluginError("Mesh not selected.")

            finalTransform = Matrix.Scale(getOOTScale(obj.ootActorScale), 4)

            try:
                # exportPath, levelName = getPathAndLevel(context.scene.geoCustomExport,
                # 	context.scene.geoExportPath, context.scene.geoLevelName,
                # 	context.scene.geoLevelOption)

                saveTextures = context.scene.saveTextures
                exportSettings = context.scene.fast64.oot.DLExportSettings

                ootConvertMeshToC(
                    obj,
                    finalTransform,
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


oot_dl_writer_classes = (
    OOT_ImportDL,
    OOT_ExportDL,
)


def f3d_ops_register():
    for cls in oot_dl_writer_classes:
        register_class(cls)


def f3d_ops_unregister():
    for cls in reversed(oot_dl_writer_classes):
        unregister_class(cls)
