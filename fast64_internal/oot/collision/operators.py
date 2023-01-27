import bpy, os, mathutils
from bpy.types import Operator, Mesh
from bpy.utils import register_class, unregister_class
from bpy.ops import object
from mathutils import Matrix
from ..oot_collision import exportCollisionCommon, ootCollisionToC
from ..oot_collision_classes import OOTCollision, OOTCameraData
from .properties import OOTCollisionExportSettings

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
    includeChildren = exportSettings.includeChildren
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
        exportCollisionCommon(collision, obj, transformMatrix, includeChildren, name)
        ootCleanupScene(originalObj, allObjs)
    except Exception as e:
        ootCleanupScene(originalObj, allObjs)
        raise Exception(str(e))

    collisionC = ootCollisionToC(collision)

    data = CData()
    data.source += '#include "ultra64.h"\n#include "z64.h"\n#include "macros.h"\n'
    if not isCustomExport:
        data.source += '#include "' + folderName + '.h"\n\n'
    else:
        data.source += "\n"

    data.append(collisionC)

    path = ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, True)
    filename = exportSettings.filename if exportSettings.isCustomFilename else f"{name}_collision"
    writeCData(data, os.path.join(path, f"{filename}.h"), os.path.join(path, f"{filename}.c"))

    if not isCustomExport:
        addIncludeFiles(folderName, path, name)


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
        if type(obj.data) is not Mesh:
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
