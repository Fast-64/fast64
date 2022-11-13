from bpy.types import Armature, PropertyGroup, Object, Bone, Panel, Operator
from bpy.ops import object
from bpy.props import EnumProperty, PointerProperty, StringProperty, FloatProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from ....utility import PluginError, raisePluginError, prop_split
from ...oot_utility import getStartBone, getNextBone


ootEnumBoneType = [
    ("Default", "Default", "Default"),
    ("Custom DL", "Custom DL", "Custom DL"),
    ("Ignore", "Ignore", "Ignore"),
]


def pollArmature(self, obj):
    return isinstance(obj.data, Armature)


# Copy data from console into python file
class OOT_SaveRestPose(Operator):
    # set bl_ properties
    bl_idname = "object.oot_save_rest_pose"
    bl_label = "Save Rest Pose"
    bl_options = {"REGISTER", "UNDO"}

    # path: bpy.props.StringProperty(name="Path", subtype="FILE_PATH")
    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        if len(context.selected_objects) == 0:
            raise PluginError("Armature not selected.")
        armatureObj = context.active_object
        if type(armatureObj.data) is not Armature:
            raise PluginError("Armature not selected.")

        try:
            data = "restPoseData = [\n"
            startBoneName = getStartBone(armatureObj)
            boneStack = [startBoneName]

            firstBone = True
            while len(boneStack) > 0:
                bone, boneStack = getNextBone(boneStack, armatureObj)
                poseBone = armatureObj.pose.bones[bone.name]
                if firstBone:
                    data += str(poseBone.matrix_basis.decompose()[0][:]) + ", "
                    firstBone = False
                data += str((poseBone.matrix_basis.decompose()[1]).to_euler()[:]) + ", "

            data += "\n]"

            print(data)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class OOTDynamicTransformProperty(PropertyGroup):
    billboard: BoolProperty(name="Billboard")


class OOTBoneProperty(PropertyGroup):
    boneType: EnumProperty(name="Bone Type", items=ootEnumBoneType)
    dynamicTransform: PointerProperty(type=OOTDynamicTransformProperty)
    customDLName: StringProperty(name="Custom DL", default="gEmptyDL")


class OOTSkeletonProperty(PropertyGroup):
    LOD: PointerProperty(type=Object, poll=pollArmature)


class OOT_SkeletonPanel(Panel):
    bl_idname = "OOT_PT_skeleton"
    bl_label = "OOT Skeleton Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

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
        col = self.layout.box().column()
        col.box().label(text="OOT Skeleton Inspector")
        prop_split(col, context.object, "ootDrawLayer", "Draw Layer")
        prop_split(col, context.object.ootSkeleton, "LOD", "LOD Skeleton")
        if context.object.ootSkeleton.LOD is not None:
            col.label(text="Make sure LOD has same bone structure.", icon="BONE_DATA")
        prop_split(col, context.object, "ootActorScale", "Actor Scale")


class OOT_BonePanel(Panel):
    bl_idname = "OOT_PT_bone"
    bl_label = "OOT Bone Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and context.bone is not None

    # called every frame
    def draw(self, context):
        col = self.layout.box().column()
        col.box().label(text="OOT Bone Inspector")
        prop_split(col, context.bone.ootBone, "boneType", "Bone Type")
        if context.bone.ootBone.boneType == "Custom DL":
            prop_split(col, context.bone.ootBone, "customDLName", "DL Name")
        if context.bone.ootBone.boneType == "Custom DL" or context.bone.ootBone.boneType == "Ignore":
            col.label(text="Make sure no geometry is skinned to this bone.", icon="BONE_DATA")

        if context.bone.ootBone.boneType != "Ignore":
            col.prop(context.bone.ootBone.dynamicTransform, "billboard")


oot_skeleton_classes = (
    OOT_SaveRestPose,
    OOTDynamicTransformProperty,
    OOTBoneProperty,
    OOTSkeletonProperty,
)

oot_skeleton_panels = (
    OOT_SkeletonPanel,
    OOT_BonePanel,
)


def skeleton_props_panel_register():
    for cls in oot_skeleton_panels:
        register_class(cls)


def skeleton_props_panel_unregister():
    for cls in oot_skeleton_panels:
        unregister_class(cls)


def skeleton_props_classes_register():
    for cls in oot_skeleton_classes:
        register_class(cls)

    Object.ootActorScale = FloatProperty(min=0, default=100)
    Object.ootSkeleton = PointerProperty(type=OOTSkeletonProperty)
    Bone.ootBone = PointerProperty(type=OOTBoneProperty)


def skeleton_props_classes_unregister():
    del Object.ootActorScale
    del Bone.ootBone
    del Object.ootSkeleton

    for cls in reversed(oot_skeleton_classes):
        unregister_class(cls)
