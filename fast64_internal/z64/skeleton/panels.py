from bpy.types import Armature, Panel
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...panels import Z64_Panel
from .properties import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from .operators import OOT_ImportSkeleton, OOT_ExportSkeleton


class OOT_SkeletonPanel(Panel):
    bl_idname = "Z64_PT_skeleton"
    bl_label = "Skeleton Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene.gameEditorMode in {"OOT", "MM"}
            and hasattr(context, "object")
            and context.object is not None
            and isinstance(context.object.data, Armature)
        )

    # called every frame
    def draw(self, context):
        col = self.layout.box().column()
        col.box().label(text="Skeleton Inspector")
        prop_split(col, context.object, "ootDrawLayer", "Draw Layer")
        context.object.ootSkeleton.draw_props(col)

        prop_split(col, context.object, "ootActorScale", "Actor Scale")


class OOT_BonePanel(Panel):
    bl_idname = "Z64_PT_bone"
    bl_label = "Bone Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode in {"OOT", "MM"} and context.bone is not None

    # called every frame
    def draw(self, context):
        col = self.layout.box().column()
        col.box().label(text="Bone Inspector")
        context.bone.ootBone.draw_props(col)


class OOT_ExportSkeletonPanel(Z64_Panel):
    bl_idname = "Z64_PT_export_skeleton"
    bl_label = "Skeletons"

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
