from bpy.types import Panel, Object, EditBone, Bone
from bpy.utils import register_class, unregister_class
from .utility import getCSObj, isActorCueList, isPreview, isActorCuePoint

from .properties import (
    OOTCutsceneMotionProperty,
    OOTCSMotionActorCueListProperty,
    OOTCSMotionActorCuePointProperty,
    OOTCSMotionCameraShotProperty,
    OOTCSMotionCameraShotPointProperty,
)

from .operators import (
    OOTCSMotionCreateActorCuePreview,
    OOTCSMotionAddActorCuePoint,
    OOTCSMotionInitCutscene,
    OOTCSMotionCreateCameraShot,
    OOTCSMotionCreatePlayerCueList,
    OOTCSMotionCreateActorCueList,
)


def getBoneFromEditBone(shotObject: Object, editBone: EditBone) -> Bone:
    for bone in shotObject.data.bones:
        if bone.name == editBone.name:
            return bone
    else:
        print("Could not find corresponding bone")
        return editBone


class OOT_CSMotionActorCuePanel(Panel):
    bl_label = "Cutscene Motion Actor Cue Controls"
    bl_idname = "OOT_PT_actor_cue_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        csMotionProp: OOTCutsceneMotionProperty = obj.ootCSMotionProperty
        actorCueProp: OOTCSMotionActorCuePointProperty = csMotionProp.actorCueProp
        actorCueListProp: OOTCSMotionActorCueListProperty = csMotionProp.actorCueListProp

        if isActorCuePoint(obj):
            actorCueProp.draw_props(layout)
            obj = obj.parent

        if isActorCueList(obj):
            actorCueListProp.draw_props(layout, False)
            layout.operator(OOTCSMotionAddActorCuePoint.bl_idname)
            layout.operator(OOTCSMotionCreateActorCuePreview.bl_idname)

        if isPreview(obj):
            actorCueListProp.draw_props(layout, True)


class OOT_CSMotionCameraShotPanel(Panel):
    bl_label = "Cutscene Motion Camera Shot Controls"
    bl_idname = "OOT_PT_camera_shot_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        obj = context.view_layer.objects.active
        layout = self.layout

        if obj.type == "ARMATURE":
            camShotProp: OOTCSMotionCameraShotProperty = obj.data.ootCamShotProp
            camShotPointProp: OOTCSMotionCameraShotPointProperty = None

            box = layout.box()
            camShotProp.draw_props(box, self.bl_label)

            activeBone = editBone = None
            if obj.mode == "OBJECT":
                activeBone = obj.data.bones.active

                if activeBone is None:
                    return
            elif obj.mode == "EDIT":
                editBone = obj.data.edit_bones.active

                if editBone is None:
                    return

                activeBone = getBoneFromEditBone(obj, editBone)

            camShotPointProp = activeBone.ootCamShotPointProp
            if editBone is not None:
                if "frames" in editBone or "fov" in editBone or "camroll" in editBone:
                    camShotPointProp = editBone.ootCamShotPointProp

            camShotPointProp.draw_props(box)


class OOT_CutsceneMotionPanel(Panel):
    bl_label = "Cutscene Motion Controls"
    bl_idname = "OOT_PT_cutscene_motion_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout

        if getCSObj(None, context) is not None:
            layout.prop(context.scene, "zc_previewlinkage")
            layout.operator(OOTCSMotionInitCutscene.bl_idname)
            layout.operator(OOTCSMotionCreateCameraShot.bl_idname)
            layout.operator(OOTCSMotionCreatePlayerCueList.bl_idname)
            layout.operator(OOTCSMotionCreateActorCueList.bl_idname)


classes = (OOT_CSMotionActorCuePanel, OOT_CSMotionCameraShotPanel, OOT_CutsceneMotionPanel)


def csMotion_panels_register():
    for cls in classes:
        register_class(cls)


def csMotion_panels_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
