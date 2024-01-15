import bpy, os, mathutils
from bpy.types import Operator
from bpy.utils import register_class, unregister_class
from bpy.ops import object
from mathutils import Matrix
from ..oot_collision_classes import OOTCollision, OOTCameraData
from .properties import OOTCollisionExportSettings
from ..exporter.collision import CollisionHeader

from ...utility import (
    PluginError,
    CData,
    unhideAllAndGetHiddenState,
    restoreHiddenState,
    writeCData,
    toAlnum,
    raisePluginError,
)

from ..oot_utility import (
    OOTObjectCategorizer,
    addIncludeFiles,
    getOOTScale,
    ootDuplicateHierarchy,
    ootCleanupScene,
    ootGetPath,
    ootGetObjectPath,
)


def exportCollisionToC(
    originalObj: bpy.types.Object, transformMatrix: mathutils.Matrix, exportSettings: OOTCollisionExportSettings
):
    name = toAlnum(originalObj.name)
    isCustomExport = exportSettings.customExport
    folderName = exportSettings.folder
    exportPath = ootGetObjectPath(isCustomExport, bpy.path.abspath(exportSettings.exportPath), folderName)

    collision = OOTCollision(name)
    collision.cameraData = OOTCameraData(name)

    if bpy.context.scene.exportHiddenGeometry:
        hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

    # Don't remove ignore_render, as we want to resuse this for collision
    obj, allObjs = ootDuplicateHierarchy(originalObj, None, True, OOTObjectCategorizer())

    if bpy.context.scene.exportHiddenGeometry:
        restoreHiddenState(hiddenState)

    try:
        if not obj.ignore_collision:
            # get C data
            colData = CData()
            colData.source = '#include "ultra64.h"\n#include "z64.h"\n#include "macros.h"\n'
            if not isCustomExport:
                colData.source += f'#include "{folderName}.h"\n\n'
            else:
                colData.source += "\n"
            colData.append(
                CollisionHeader(
                    None,
                    obj,
                    transformMatrix,
                    bpy.context.scene.useDecompFeatures,
                    exportSettings.includeChildren,
                    f"{name}_collisionHeader",
                    name,
                ).getC()
            )

            # write file
            path = ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, True)
            filename = exportSettings.filename if exportSettings.isCustomFilename else f"{name}_collision"
            writeCData(colData, os.path.join(path, f"{filename}.h"), os.path.join(path, f"{filename}.c"))
            if not isCustomExport:
                addIncludeFiles(folderName, path, name)
        else:
            raise PluginError("ERROR: The selected mesh object ignores collision!")
    except Exception as e:
        raise Exception(str(e))
    finally:
        ootCleanupScene(originalObj, allObjs)


class OOT_ExportCollision(Operator):
    # set bl_ properties
    bl_idname = "object.oot_export_collision"
    bl_label = "Export Collision"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("No object selected.")
        obj = context.active_object
        if obj.type != "MESH":
            raise PluginError("No mesh object selected.")

        finalTransform = Matrix.Scale(getOOTScale(obj.ootActorScale), 4)

        try:
            exportSettings: OOTCollisionExportSettings = context.scene.fast64.oot.collisionExportSettings
            exportCollisionToC(obj, finalTransform, exportSettings)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


oot_col_classes = (OOT_ExportCollision,)


def collision_ops_register():
    for cls in oot_col_classes:
        register_class(cls)


def collision_ops_unregister():
    for cls in reversed(oot_col_classes):
        unregister_class(cls)
