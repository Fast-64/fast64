import mathutils
import bpy

from bpy.types import Scene, Operator, Armature
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from bpy.ops import object
from pathlib import Path

from ...utility import PluginError, ExportUtils, toAlnum, writeCData, raisePluginError
from ..exporter.animation import ootExportLinkAnimation, ootExportNonLinkAnimation
from .properties import OOTAnimExportSettingsProperty, OOTAnimImportSettingsProperty
from .importer import ootImportLinkAnimationC, ootImportNonLinkAnimationC

from ..utility import (
    PathUtils,
    checkEmptyName,
    getOOTScale,
)


def exportAnimationC(armatureObj: bpy.types.Object, settings: OOTAnimExportSettingsProperty):
    if settings.isCustom:
        checkEmptyName(settings.customPath)
    else:
        checkEmptyName(settings.folderName)

    if settings.isCustomFilename:
        checkEmptyName(settings.filename)

    path = (
        Path(bpy.path.abspath(settings.customPath)).resolve()
        if settings.isCustom
        else bpy.context.scene.fast64.oot.get_decomp_path()
    )
    with PathUtils(False, path, "assets/objects/", settings.folderName, settings.isCustom, False) as path_utils:
        exportPath = path_utils.get_assets_path(check_extracted=False, with_decomp_path=True)

    checkEmptyName(armatureObj.name)
    name = toAlnum(armatureObj.name)
    assert name is not None
    filename = settings.filename if settings.isCustomFilename else name
    convertTransformMatrix = (
        mathutils.Matrix.Scale(getOOTScale(armatureObj.ootActorScale), 4)
        @ mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()
    )

    if settings.isLink:
        ootAnim = ootExportLinkAnimation(armatureObj, convertTransformMatrix, name)
        ootAnimC, ootAnimHeaderC = ootAnim.toC(settings.isCustom)
        folder_name = settings.folderName if settings.isCustom else ""

        with PathUtils(
            False, exportPath, "assets/misc/link_animetion", folder_name, settings.isCustom, False
        ) as path_utils:
            path = path_utils.get_assets_path(check_extracted=False, custom_mkdir=False)
            headerPath = path_utils.get_assets_path(check_extracted=False, custom_mkdir=False)
            path_utils.set_base_path(path)

            assert ootAnim.headerName is not None
            writeCData(ootAnimC, path / f"{ootAnim.dataName()}.h", path / f"{ootAnim.dataName()}.c")
            writeCData(ootAnimHeaderC, headerPath / f"{ootAnim.headerName}.h", headerPath / f"{ootAnim.headerName}.c")

            if not settings.isCustom:
                path_utils.set_folder_name("link_animetion")
                path_utils.add_include_files(ootAnim.dataName())

                path_utils.set_folder_name("gameplay_keep")
                path_utils.add_include_files(ootAnim.headerName)
    else:
        ootAnim = ootExportNonLinkAnimation(armatureObj, convertTransformMatrix, name, filename)
        ootAnimC = ootAnim.toC()

        with PathUtils(
            False, exportPath, "assets/objects/", settings.folderName, settings.isCustom, False
        ) as path_utils:
            path = path_utils.get_assets_path(check_extracted=False)
            path_utils.set_base_path(path)

            writeCData(ootAnimC, str(path / f"{filename}.h"), str(path / f"{filename}.c"))
            if not settings.isCustom:
                path_utils.add_include_files(filename)


def ootImportAnimationC(
    armatureObj: bpy.types.Object,
    settings: OOTAnimImportSettingsProperty,
    actorScale: float,
):
    path = (
        Path(bpy.path.abspath(settings.customPath)).resolve()
        if settings.isCustom
        else bpy.context.scene.fast64.oot.get_decomp_path()
    )
    with PathUtils(False, path, "assets/objects/", settings.folderName, settings.isCustom) as path_utils:
        filepath = path_utils.get_object_source_path()

    if settings.isLink:
        numLimbs = 21
        if not settings.isCustom:
            decomp_path: Path = bpy.context.scene.fast64.oot.get_decomp_path()
            with PathUtils(False, decomp_path, None, "link_animetion", settings.isCustom) as path_utils:
                animFilepath = path_utils.get_assets_path(with_decomp_path=True, check_file=True)

                # starting with zeldaret/oot dbe1a80541173652c344f20226310a8bf90f3086 gameplay_keep is split and committed
                animHeaderFilepath = decomp_path / "assets/objects/gameplay_keep/player_anim_headers.c"
                if not animHeaderFilepath.exists():
                    path_utils.set_folder_name("gameplay_keep")
                    animHeaderFilepath = path_utils.get_assets_path(with_decomp_path=True, check_file=True)
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
        with ExportUtils() as export_utils:
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
