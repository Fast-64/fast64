import mathutils, bpy, os
from bpy.types import Scene, Operator, Armature
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from bpy.ops import object
from ...utility import PluginError, toAlnum, writeCData, raisePluginError
from .properties import OOTAnimExportSettingsProperty, OOTAnimImportSettingsProperty
from .exporter import ootExportLinkAnimation, ootExportNonLinkAnimation
from .importer import ootImportLinkAnimationC, ootImportNonLinkAnimationC

from ..oot_utility import (
    ootGetPath,
    addIncludeFiles,
    checkEmptyName,
    ootGetObjectPath,
    getOOTScale,
)


def exportAnimationC(armatureObj: bpy.types.Object, settings: OOTAnimExportSettingsProperty):
    path = bpy.path.abspath(settings.customPath)
    exportPath = ootGetObjectPath(settings.isCustom, path, settings.folderName, False)

    checkEmptyName(settings.folderName)
    checkEmptyName(armatureObj.name)
    name = toAlnum(armatureObj.name)
    filename = settings.filename if settings.isCustomFilename else name
    convertTransformMatrix = (
        mathutils.Matrix.Scale(getOOTScale(armatureObj.ootActorScale), 4)
        @ mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()
    )

    if settings.isLink:
        ootAnim = ootExportLinkAnimation(armatureObj, convertTransformMatrix, name)
        ootAnimC, ootAnimHeaderC = ootAnim.toC(settings.isCustom)
        path = ootGetPath(
            exportPath,
            settings.isCustom,
            "assets/misc/link_animetion",
            settings.folderName if settings.isCustom else "",
            False,
            False,
        )
        headerPath = ootGetPath(
            exportPath,
            settings.isCustom,
            "assets/objects/gameplay_keep",
            settings.folderName if settings.isCustom else "",
            False,
            False,
        )
        writeCData(
            ootAnimC, os.path.join(path, ootAnim.dataName() + ".h"), os.path.join(path, ootAnim.dataName() + ".c")
        )
        writeCData(
            ootAnimHeaderC,
            os.path.join(headerPath, ootAnim.headerName + ".h"),
            os.path.join(headerPath, ootAnim.headerName + ".c"),
        )

        if not settings.isCustom:
            addIncludeFiles("link_animetion", path, ootAnim.dataName())
            addIncludeFiles("gameplay_keep", headerPath, ootAnim.headerName)

    else:
        ootAnim = ootExportNonLinkAnimation(armatureObj, convertTransformMatrix, name)

        ootAnimC = ootAnim.toC()
        path = ootGetPath(exportPath, settings.isCustom, "assets/objects/", settings.folderName, True, False)
        writeCData(ootAnimC, os.path.join(path, filename + ".h"), os.path.join(path, filename + ".c"))

        if not settings.isCustom:
            addIncludeFiles(settings.folderName, path, filename)


def ootImportAnimationC(
    armatureObj: bpy.types.Object,
    settings: OOTAnimImportSettingsProperty,
    actorScale: float,
):
    importPath = bpy.path.abspath(settings.customPath)
    filepath = ootGetObjectPath(settings.isCustom, importPath, settings.folderName, True)
    if settings.isLink:
        numLimbs = 21
        if not settings.isCustom:
            basePath = bpy.path.abspath(bpy.context.scene.ootDecompPath)
            animFilepath = os.path.join(
                basePath,
                f"{bpy.context.scene.fast64.oot.get_extracted_path()}/assets/misc/link_animetion/link_animetion.c",
            )
            animHeaderFilepath = os.path.join(
                basePath,
                f"{bpy.context.scene.fast64.oot.get_extracted_path()}/assets/objects/gameplay_keep/gameplay_keep.c",
            )
        else:
            animFilepath = filepath
            animHeaderFilepath = filepath
        ootImportLinkAnimationC(
            armatureObj,
            animHeaderFilepath,
            animFilepath,
            settings.animName,
            actorScale,
            numLimbs,
            settings.isCustom,
        )
    else:
        ootImportNonLinkAnimationC(armatureObj, filepath, settings.animName, actorScale, settings.isCustom)


class OOT_ExportAnim(Operator):
    bl_idname = "object.oot_export_anim"
    bl_label = "Export Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if len(context.selected_objects) == 0 or not isinstance(context.selected_objects[0].data, Armature):
                raise PluginError("Armature not selected.")
            if len(context.selected_objects) > 1:
                raise PluginError("Multiple objects selected, make sure to select only one.")
            armatureObj = context.selected_objects[0]
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            settings = context.scene.fast64.oot.animExportSettings
            exportAnimationC(armatureObj, settings)
            self.report({"INFO"}, "Success!")

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set


class OOT_ImportAnim(Operator):
    bl_idname = "object.oot_import_anim"
    bl_label = "Import Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if len(context.selected_objects) == 0 or not isinstance(context.selected_objects[0].data, Armature):
                raise PluginError("Armature not selected.")
            if len(context.selected_objects) > 1:
                raise PluginError("Multiple objects selected, make sure to select only one.")
            armatureObj = context.selected_objects[0]
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")

            # We need to apply scale otherwise translation imports won't be correct.
            object.select_all(action="DESELECT")
            armatureObj.select_set(True)
            context.view_layer.objects.active = armatureObj
            object.transform_apply(location=False, rotation=False, scale=True, properties=False)

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            actorScale = getOOTScale(armatureObj.ootActorScale)
            settings = context.scene.fast64.oot.animImportSettings
            ootImportAnimationC(armatureObj, settings, actorScale)
            self.report({"INFO"}, "Success!")

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set


oot_anim_classes = (
    OOT_ExportAnim,
    OOT_ImportAnim,
)


def anim_ops_register():
    Scene.ootAnimIsCustomExport = BoolProperty(name="Use Custom Path")
    Scene.ootAnimExportCustomPath = StringProperty(name="Folder", subtype="FILE_PATH")
    Scene.ootAnimExportFolderName = StringProperty(name="Animation Folder", default="object_geldb")

    Scene.ootAnimIsCustomImport = BoolProperty(name="Use Custom Path")
    Scene.ootAnimImportCustomPath = StringProperty(name="Folder", subtype="FILE_PATH")
    Scene.ootAnimImportFolderName = StringProperty(name="Animation Folder", default="object_geldb")

    Scene.ootAnimSkeletonName = StringProperty(name="Skeleton Name", default="gGerudoRedSkel")
    Scene.ootAnimName = StringProperty(name="Anim Name", default="gGerudoRedSpinAttackAnim")
    for cls in oot_anim_classes:
        register_class(cls)


def anim_ops_unregister():
    del Scene.ootAnimIsCustomExport
    del Scene.ootAnimExportCustomPath
    del Scene.ootAnimExportFolderName

    del Scene.ootAnimIsCustomImport
    del Scene.ootAnimImportCustomPath
    del Scene.ootAnimImportFolderName

    del Scene.ootAnimSkeletonName
    del Scene.ootAnimName
    for cls in reversed(oot_anim_classes):
        unregister_class(cls)
