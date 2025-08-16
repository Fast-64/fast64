from bpy.utils import register_class, unregister_class
from ....panels import OOT_Panel
from .properties import CutsceneCmdCameraShotProperty, CutsceneCmdCameraShotPointProperty


class OOT_CSMotionCameraShotPanel(OOT_Panel):
    bl_label = "Cutscene Motion Camera Shot Controls"
    bl_idname = "Z64_PT_camera_shot_panel"
    bl_parent_id = "ARMATURE_PT_OOT_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        obj = context.view_layer.objects.active
        col = self.layout.column()

        camShotProp: CutsceneCmdCameraShotProperty = obj.data.ootCamShotProp
        camShotPointProp: CutsceneCmdCameraShotPointProperty = None
        activeBone = editBone = None

        camShotProp.draw_props(col)

        if obj.mode == "POSE":
            col.label(text="Warning: You can't be in 'Pose' mode to edit camera bones!")
        elif obj.mode == "OBJECT":
            activeBone = obj.data.bones.active
            if activeBone is not None:
                camShotPointProp = activeBone.ootCamShotPointProp
                camShotPointProp.draw_props(col)
        elif obj.mode == "EDIT":
            editBone = obj.data.edit_bones.active
            if editBone is not None:
                camShotPointProp = editBone.ootCamShotPointProp
                camShotPointProp.draw_props(col)


classes = (OOT_CSMotionCameraShotPanel,)


def csMotion_panels_register():
    for cls in classes:
        register_class(cls)


def csMotion_panels_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
