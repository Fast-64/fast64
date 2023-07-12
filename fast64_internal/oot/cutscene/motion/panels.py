from bpy.types import Panel, Object, EditBone, Bone
from bpy.utils import register_class, unregister_class
from .properties import OOTCSMotionCameraShotProperty, OOTCSMotionCameraShotPointProperty


def getBoneFromEditBone(shotObject: Object, editBone: EditBone) -> Bone:
    for bone in shotObject.data.bones:
        if bone.name == editBone.name:
            return bone
    else:
        print("Could not find corresponding bone")
        return editBone


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
            if obj.mode == "POSE":
                box.label(text="Warning: You can't be in 'Pose' mode to edit camera bones!")
                return
            elif obj.mode == "OBJECT":
                activeBone = obj.data.bones.active

                if activeBone is None:
                    return
            elif obj.mode == "EDIT":
                editBone = obj.data.edit_bones.active

                if editBone is None:
                    return

                activeBone = getBoneFromEditBone(obj, editBone)

            if activeBone is not None:
                camShotPointProp = activeBone.ootCamShotPointProp
                if editBone is not None:
                    if "shotPointFrame" in editBone or "shotPointViewAngle" in editBone or "shotPointRoll" in editBone:
                        camShotPointProp = editBone.ootCamShotPointProp

                camShotPointProp.draw_props(box)


classes = (OOT_CSMotionCameraShotPanel,)


def csMotion_panels_register():
    for cls in classes:
        register_class(cls)


def csMotion_panels_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
