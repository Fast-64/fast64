from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from ...panel import OOT_Panel
from .classes import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from .operators import OOT_ImportSkeleton, OOT_ExportSkeleton


class OOT_ExportSkeletonPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_skeleton"
    bl_label = "OOT Skeleton Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportSkeleton.bl_idname)
        exportSettings: OOTSkeletonExportSettings = context.scene.fast64.oot.skeletonExportSettings

        prop_split(col, exportSettings, "name", "Skeleton")
        prop_split(col, exportSettings, "folder", "Object" if not exportSettings.isCustom else "Folder")
        if exportSettings.isCustom:
            prop_split(col, exportSettings, "customAssetIncludeDir", "Asset Include Path")
            prop_split(col, exportSettings, "customPath", "Path")

        col.prop(exportSettings, "isCustom")
        col.prop(exportSettings, "removeVanillaData")
        col.prop(exportSettings, "optimize")
        if exportSettings.optimize:
            b = col.box().column()
            b.label(icon="LIBRARY_DATA_BROKEN", text="Do not draw anything in SkelAnime")
            b.label(text="callbacks or cull limbs, will be corrupted.")

        col.operator(OOT_ImportSkeleton.bl_idname)
        importSettings: OOTSkeletonImportSettings = context.scene.fast64.oot.skeletonImportSettings

        prop_split(col, importSettings, "name", "Skeleton")
        if importSettings.isCustom:
            prop_split(col, importSettings, "customPath", "File")
        else:
            prop_split(col, importSettings, "folder", "Object")
        prop_split(col, importSettings, "drawLayer", "Import Draw Layer")

        col.prop(importSettings, "isCustom")
        col.prop(importSettings, "removeDoubles")
        col.prop(importSettings, "importNormals")


oot_skeleton_panels = [
    OOT_ExportSkeletonPanel,
]

oot_skeleton_classes = [
    OOT_ExportSkeleton,
    OOT_ImportSkeleton,
    OOTSkeletonExportSettings,
    OOTSkeletonImportSettings,
]


def skeletonPanelRegister():
    for cls in oot_skeleton_panels:
        register_class(cls)


def skeletonPanelUnregister():
    for cls in oot_skeleton_panels:
        unregister_class(cls)


def skeletonRegister():
    for cls in oot_skeleton_classes:
        register_class(cls)


def skeletonUnregister():
    for cls in reversed(oot_skeleton_classes):
        unregister_class(cls)
