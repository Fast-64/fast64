# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations

import bpy

import os, struct, math
from pathlib import Path
from mathutils import Vector, Euler, Matrix
from collections import namedtuple
from dataclasses import dataclass, field
from typing import BinaryIO, TextIO, NamedTuple

from .mk64_constants import MODEL_HEADER

from ..f3d.f3d_writer import exportF3DCommon
from ..f3d.f3d_bleed import BleedGraphics
from ..f3d.f3d_gbi import (
    DLFormat,
    GfxListTag,
    GfxMatWriteMethod,
    GfxFormatter,
    ScrollMethod,
    GfxList,
    FModel,
    FMesh,
    FMaterial,
    DPSetTextureImage,
    TextureExportSettings,
)

from ..utility import (
    transform_mtx_blender_to_n64,
    cleanupCombineObj,
    combineObjects,
    parentObject,
    PluginError,
    CData,
    writeCData,
)

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------


class MK64_BpyCourse:
    """
    Interim class that transforms course data back
    and forth between blender and internal data
    """

    def __init__(self, course_root: bpy.types.Object):
        self.root = course_root

    def make_mk64_course_from_bpy(self, scale: float, mat_write_method):
        """
        Creates a MK64_fModel class with all model data ready to exported to c
        also generates lists for items, pathing and collision (in future)
        """
        fModel = MK64_fModel(self.root, mat_write_method)
        # create duplicate objects to export from
        transform = Matrix.Diagonal(Vector((scale, scale, scale))).to_4x4()
        fMeshes = exportF3DCommon(self.root, fModel, transform, True, "mk64", DLFormat.Static, 1)
        # retrieve data for items and pathing
        return fModel, fMeshes

    # creates a list of fMesh objects with their bpy data processed and stored
    # def export_f3d_from_obj(self, obj: bpy.types.Object, fModel: MK64_fModel, transformMatrix: Matrix):
    # if obj and obj.type == "MESH":
    # try:
    # infoDict = getInfoDict(obj)
    # triConverterInfo = TriangleConverterInfo(obj, None, fModel.f3d, transformMatrix, infoDict)
    # fMeshes = saveStaticModel(
    # triConverterInfo,
    # fModel,
    # obj,
    # transformMatrix,
    # fModel.name,
    # 1,
    # False,
    # None,
    # )
    # except Exception as e:
    # self.cleanup_course(fModel)
    # raise PluginError(str(e))
    # return list(fMeshes.values())
    # else:
    # return 0

    # def cleanup_course(self, mk64_course: MK64_Course):
    # cleanupCombineObj(mk64_course.all_objs)
    # self.root.select_set(True)
    # bpy.context.view_layer.objects.active = self.root


class MK64_fModel(FModel):
    def __init__(self, rt: bpy.types.Object, mat_write_method, name="mk64"):
        super().__init__(name, DLFormat.Static, mat_write_method)


class MK64_fMesh(FMesh):
    pass


# ------------------------------------------------------------------------
#    Exorter Functions
# ------------------------------------------------------------------------


def export_course_c(obj: bpy.types.Object, context: bpy.types.Context, export_dir: Path):
    """
    this is similar to exportF3DtoC except that we
    pay attention to other objects within the course
    namely paths, items and collision
    """
    inline = context.scene.exportInlineF3D
    mk64_props: MK64_Properties = context.scene.fast64.mk64
    scale = mk64_props.scale
    # does this matter? idk
    mat_write_method = context.scene.matWriteMethod if not inline else GfxMatWriteMethod.WriteAll

    bpy_course = MK64_BpyCourse(obj)
    mk64_fModel, mk64_fMeshes = bpy_course.make_mk64_course_from_bpy(scale, mat_write_method)

    if inline:
        bleed_gfx = BleedGraphics()
        bleed_gfx.bleed_fModel(mk64_fModel, mk64_fMeshes)

    # idk how scrolls would actually affect this export
    gfxFormatter = GfxFormatter(ScrollMethod.Vertex, 64, None)
    exportData = mk64_fModel.to_c(TextureExportSettings(False, False, export_dir, export_dir), gfxFormatter)
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData

    model_data = CData()
    model_data.source += MODEL_HEADER
    model_data.append(staticData)
    model_data.append(dynamicData)

    writeCData(model_data, os.path.join(export_dir, "header.h"), os.path.join(export_dir, "model.inc.c"))
