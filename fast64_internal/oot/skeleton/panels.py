from bpy.types import Armature, Panel
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...panels import OOT_Panel
from .properties import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from .operators import OOT_ImportSkeleton, OOT_ExportSkeleton


class OOT_SkeletonPanel(Panel):
    bl_idname = "OOT_PT_skeleton"
    bl_parent_id = "OBJECT_PT_context_object"
    bl_label = "OOT Skeleton Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return (
            context.scene.gameEditorMode == "OOT"
            and hasattr(context, "object")
            and context.object is not None
            and isinstance(context.object.data, Armature)
        )

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        prop_split(col, context.object, "ootDrawLayer", "Draw Layer")
        context.object.ootSkeleton.draw_props(col)

        prop_split(col, context.object, "ootActorScale", "Actor Scale")


class OOT_BonePanel(Panel):
    bl_idname = "OOT_PT_bone"
    bl_parent_id = "BONE_PT_context_bone"
    bl_label = "OOT Bone Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and context.bone is not None

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        context.bone.ootBone.draw_props(col)


class OOT_ExportSkeletonPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_skeleton"
    bl_label = "OOT Skeleton Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportSkeleton.bl_idname)
        exportSettings: OOTSkeletonExportSettings = context.scene.fast64.oot.skeletonExportSettings
        exportSettings.draw_props(col)

        col.operator(OOT_ImportSkeleton.bl_idname)
        importSettings: OOTSkeletonImportSettings = context.scene.fast64.oot.skeletonImportSettings
        importSettings.draw_props(col)


oot_skeleton_panels = (
    OOT_SkeletonPanel,
    OOT_BonePanel,
    OOT_ExportSkeletonPanel,
)


def skeleton_panels_register():
    for cls in oot_skeleton_panels:
        register_class(cls)


def skeleton_panels_unregister():
    for cls in oot_skeleton_panels:
        unregister_class(cls)
