from bpy.utils import register_class, unregister_class
from ....panels import OOT_Panel
from .properties import CutsceneCmdCameraShotProperty, CutsceneCmdCameraShotPointProperty


class OOT_CSMotionCameraShotPanel(OOT_Panel):
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
            camShotProp: CutsceneCmdCameraShotProperty = obj.data.ootCamShotProp
            camShotPointProp: CutsceneCmdCameraShotPointProperty = None
            activeBone = editBone = None

            box = layout.box()
            camShotProp.draw_props(box, self.bl_label)

            if obj.mode == "POSE":
                box.label(text="Warning: You can't be in 'Pose' mode to edit camera bones!")
            elif obj.mode == "OBJECT":
                activeBone = obj.data.bones.active
                if activeBone is not None:
                    camShotPointProp = activeBone.ootCamShotPointProp
                    camShotPointProp.draw_props(box)
            elif obj.mode == "EDIT":
                editBone = obj.data.edit_bones.active
                if editBone is not None:
                    camShotPointProp = editBone.ootCamShotPointProp
                    camShotPointProp.draw_props(box)


classes = (OOT_CSMotionCameraShotPanel,)


def csMotion_panels_register():
    for cls in classes:
        register_class(cls)


def csMotion_panels_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
