import bpy

from bpy.types import PropertyGroup, Object, Bone, UILayout
from bpy.props import EnumProperty, PointerProperty, StringProperty, FloatProperty, BoolProperty, IntProperty
from bpy.utils import register_class, unregister_class
from ...f3d.f3d_material import ootEnumDrawLayers
from ...utility import prop_split
from .constants import ootEnumSkeletonImportMode


ootEnumBoneType = [
    ("Default", "Default", "Default"),
    ("Custom DL", "Custom DL", "Custom DL"),
    ("Ignore", "Ignore", "Ignore"),
]


def pollArmature(self, obj):
    return obj.type == "ARMATURE"


class OOTDynamicTransformProperty(PropertyGroup):
    billboard: BoolProperty(name="Billboard")

    def draw_props(self, layout: UILayout):
        layout.prop(self, "billboard")


class OOTBoneProperty(PropertyGroup):
    boneType: EnumProperty(name="Bone Type", items=ootEnumBoneType)
    dynamicTransform: PointerProperty(type=OOTDynamicTransformProperty)
    customDLName: StringProperty(name="Custom DL", default="gEmptyDL")

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "boneType", "Bone Type")
        if self.boneType == "Custom DL":
            prop_split(layout, self, "customDLName", "DL Name")
        if self.boneType == "Custom DL" or self.boneType == "Ignore":
            layout.label(text="Make sure no geometry is skinned to this bone.", icon="BONE_DATA")

        if self.boneType != "Ignore":
            self.dynamicTransform.draw_props(layout)


class OOTSkeletonProperty(PropertyGroup):
    LOD: PointerProperty(type=Object, poll=pollArmature)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "LOD", "LOD Skeleton")
        if self.LOD is not None:
            layout.label(text="Make sure LOD has same bone structure.", icon="BONE_DATA")


class OOTSkeletonExportSettings(PropertyGroup):
    isCustomFilename: BoolProperty(
        name="Use Custom Filename", description="Override filename instead of basing it off of the Blender name"
    )
    filename: StringProperty(name="Filename")
    mode: EnumProperty(name="Mode", items=ootEnumSkeletonImportMode)
    folder: StringProperty(name="Skeleton Folder", default="object_geldb")
    customPath: StringProperty(name="Custom Skeleton Path", subtype="FILE_PATH")
    isCustom: BoolProperty(
        name="Use Custom Path", description="Determines whether or not to export to an explicitly specified folder"
    )
    removeVanillaData: BoolProperty(name="Replace Vanilla Skeletons On Export", default=True)
    actorOverlayName: StringProperty(name="Overlay", default="ovl_En_GeldB")
    flipbookUses2DArray: BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: IntProperty(name="Index if 2D Array", default=0, min=0)
    customAssetIncludeDir: StringProperty(
        name="Asset Include Directory",
        default="assets/objects/object_geldb",
        description="Used in #include for including image files",
    )
    optimize: BoolProperty(
        name="Optimize",
        description="Applies various optimizations between the limbs in a skeleton. "
        + "If enabled, the skeleton limbs must be drawn in their normal order, "
        + "with nothing in between and no culling, otherwise the mesh will be corrupted.",
    )

    def draw_props(self, layout: UILayout):
        layout.prop(self, "removeVanillaData")
        layout.prop(self, "optimize")
        if self.optimize:
            b = layout.box().column()
            b.label(icon="LIBRARY_DATA_BROKEN", text="Do not draw anything in SkelAnime")
            b.label(text="callbacks or cull limbs, will be corrupted.")
        layout.prop(self, "isCustom")
        layout.label(text="Object name used for export.", icon="INFO")
        layout.prop(self, "isCustomFilename")
        if self.isCustomFilename:
            prop_split(layout, self, "filename", "Filename")
        if self.isCustom:
            prop_split(layout, self, "folder", "Object" if not self.isCustom else "Folder")
            prop_split(layout, self, "customAssetIncludeDir", "Asset Include Path")
            prop_split(layout, self, "customPath", "Path")
        else:
            prop_split(layout, self, "mode", "Mode")
            if self.mode == "Generic":
                prop_split(layout, self, "folder", "Object" if not self.isCustom else "Folder")
                prop_split(layout, self, "actorOverlayName", "Overlay")
                layout.prop(self, "flipbookUses2DArray")
                if self.flipbookUses2DArray:
                    box = layout.box().column()
                    prop_split(box, self, "flipbookArrayIndex2D", "Flipbook Index")
            elif self.mode == "Adult Link" or self.mode == "Child Link":
                layout.label(text="Requires enabling NON_MATCHING in Makefile.", icon="ERROR")
                layout.label(text="Preserve all bone deform toggles if modifying an imported skeleton.", icon="ERROR")


class OOTSkeletonImportSettings(PropertyGroup):
    mode: EnumProperty(name="Mode", items=ootEnumSkeletonImportMode)
    applyRestPose: BoolProperty(name="Apply Friendly Rest Pose (If Available)", default=True)
    name: StringProperty(name="Skeleton Name", default="gGerudoRedSkel")
    folder: StringProperty(name="Skeleton Folder", default="object_geldb")
    customPath: StringProperty(name="Custom Skeleton Path", subtype="FILE_PATH")
    isCustom: BoolProperty(name="Use Custom Path")
    removeDoubles: BoolProperty(name="Remove Doubles On Import", default=True)
    importNormals: BoolProperty(name="Import Normals", default=True)
    drawLayer: EnumProperty(name="Import Draw Layer", items=ootEnumDrawLayers)
    actorOverlayName: StringProperty(name="Overlay", default="ovl_En_GeldB")
    flipbookUses2DArray: BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: IntProperty(name="Index if 2D Array", default=0, min=0)
    autoDetectActorScale: BoolProperty(name="Auto Detect Actor Scale", default=True)
    actorScale: FloatProperty(name="Actor Scale", min=0, default=100)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "drawLayer", "Import Draw Layer")
        layout.prop(self, "removeDoubles")
        layout.prop(self, "importNormals")
        layout.prop(self, "isCustom")
        if self.isCustom:
            prop_split(layout, self, "name", "Skeleton")
            prop_split(layout, self, "customPath", "File")
        else:
            prop_split(layout, self, "mode", "Mode")
            if self.mode == "Generic":
                prop_split(layout, self, "name", "Skeleton")
                prop_split(layout, self, "folder", "Object")
                prop_split(layout, self, "actorOverlayName", "Overlay")
                layout.prop(self, "autoDetectActorScale")
                if not self.autoDetectActorScale:
                    prop_split(layout, self, "actorScale", "Actor Scale")
                layout.prop(self, "flipbookUses2DArray")
                if self.flipbookUses2DArray:
                    box = layout.box().column()
                    prop_split(box, self, "flipbookArrayIndex2D", "Flipbook Index")
                if self.actorOverlayName == "ovl_En_Wf":
                    layout.box().column().label(
                        text="This actor has branching gSPSegment calls and will not import correctly unless one of the branches is deleted.",
                        icon="ERROR",
                    )
                elif self.actorOverlayName == "ovl_Obj_Switch":
                    layout.box().column().label(
                        text="This actor has a 2D texture array and will not import correctly unless the array is flattened.",
                        icon="ERROR",
                    )
            else:
                layout.prop(self, "applyRestPose")


oot_skeleton_classes = (
    OOTDynamicTransformProperty,
    OOTBoneProperty,
    OOTSkeletonProperty,
    OOTSkeletonExportSettings,
    OOTSkeletonImportSettings,
)


def skeleton_props_register():
    for cls in oot_skeleton_classes:
        register_class(cls)

    Object.ootActorScale = FloatProperty(min=0, default=100)
    Object.ootSkeleton = PointerProperty(type=OOTSkeletonProperty)
    Bone.ootBone = PointerProperty(type=OOTBoneProperty)


def skeleton_props_unregister():
    del Object.ootActorScale
    del Bone.ootBone
    del Object.ootSkeleton

    for cls in reversed(oot_skeleton_classes):
        unregister_class(cls)
