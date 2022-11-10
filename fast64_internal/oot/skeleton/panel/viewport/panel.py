from bpy.utils import register_class, unregister_class
from .....utility import prop_split
from .....panels import OOT_Panel
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

        col.prop(exportSettings, "removeVanillaData")
        col.prop(exportSettings, "optimize")
        if exportSettings.optimize:
            b = col.box().column()
            b.label(icon="LIBRARY_DATA_BROKEN", text="Do not draw anything in SkelAnime")
            b.label(text="callbacks or cull limbs, will be corrupted.")
        col.prop(exportSettings, "isCustom")
        if exportSettings.isCustom:
            prop_split(col, exportSettings, "name", "Skeleton")
            prop_split(col, exportSettings, "folder", "Object" if not exportSettings.isCustom else "Folder")
            prop_split(col, exportSettings, "customAssetIncludeDir", "Asset Include Path")
            prop_split(col, exportSettings, "customPath", "Path")
        else:
            prop_split(col, exportSettings, "mode", "Mode")
            if exportSettings.mode == "Generic":
                prop_split(col, exportSettings, "name", "Skeleton")
                prop_split(col, exportSettings, "folder", "Object" if not exportSettings.isCustom else "Folder")
                prop_split(col, exportSettings, "actorOverlayName", "Overlay")
                col.prop(exportSettings, "flipbookUses2DArray")
                if exportSettings.flipbookUses2DArray:
                    box = col.box().column()
                    prop_split(box, exportSettings, "flipbookArrayIndex2D", "Flipbook Index")
            elif exportSettings.mode == "Adult Link" or exportSettings.mode == "Child Link":
                col.label(text="Requires enabling NON_MATCHING in Makefile.", icon="ERROR")
                col.label(text="Preserve all bone deform toggles if modifying an imported skeleton.", icon="ERROR")

        col.operator(OOT_ImportSkeleton.bl_idname)
        importSettings: OOTSkeletonImportSettings = context.scene.fast64.oot.skeletonImportSettings

        prop_split(col, importSettings, "drawLayer", "Import Draw Layer")
        col.prop(importSettings, "removeDoubles")
        col.prop(importSettings, "importNormals")
        col.prop(importSettings, "isCustom")
        if importSettings.isCustom:
            prop_split(col, importSettings, "name", "Skeleton")
            prop_split(col, importSettings, "customPath", "File")
        else:
            prop_split(col, importSettings, "mode", "Mode")
            if importSettings.mode == "Generic":
                prop_split(col, importSettings, "name", "Skeleton")
                prop_split(col, importSettings, "folder", "Object")
                prop_split(col, importSettings, "actorOverlayName", "Overlay")
                col.prop(importSettings, "autoDetectActorScale")
                if not importSettings.autoDetectActorScale:
                    prop_split(col, importSettings, "actorScale", "Actor Scale")
                col.prop(importSettings, "flipbookUses2DArray")
                if importSettings.flipbookUses2DArray:
                    box = col.box().column()
                    prop_split(box, importSettings, "flipbookArrayIndex2D", "Flipbook Index")
                if importSettings.actorOverlayName == "ovl_En_Wf":
                    col.box().column().label(
                        text="This actor has branching gSPSegment calls and will not import correctly unless one of the branches is deleted.",
                        icon="ERROR",
                    )
                elif importSettings.actorOverlayName == "ovl_Obj_Switch":
                    col.box().column().label(
                        text="This actor has a 2D texture array and will not import correctly unless the array is flattened.",
                        icon="ERROR",
                    )
            else:
                col.prop(importSettings, "applyRestPose")

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
