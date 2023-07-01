from bpy.types import Panel, Bone, Armature, Object, EditBone
from bpy.utils import register_class, unregister_class
from bpy.props import FloatProperty, IntProperty, EnumProperty
from .utility import getCSObj, isActorCueList, isPreview, isActorCuePoint


def getBoneFromEditBone(shotObject: Object, editBone: EditBone) -> Bone:
    for bone in shotObject.data.bones:
        if bone.name == editBone.name:
            return bone
    else:
        print("Could not find corresponding bone")
        return editBone


class OOT_CSMotionActorCuePanel(Panel):
    bl_label = "Cutscene Motion Actor Cue Controls"
    bl_idname = "OOT_CSMotionActorCuePanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active

        if isActorCuePoint(obj):
            r = layout.row()
            r.label(text="Action point:")
            r.prop(obj.zc_apoint, "start_frame")
            r.prop(obj.zc_apoint, "action_id")
            obj = obj.parent

        if isActorCueList(obj):
            r = layout.row()
            r.label(text="Action list:")
            r.prop(obj.zc_alist, "actor_id")
            layout.operator("zcamedit.add_action_point")
            layout.operator("zcamedit.create_action_preview")

        if isPreview(obj):
            r = layout.row()
            r.label(text="Preview:")
            r.prop(obj.zc_alist, "actor_id")


class OOT_CSMotionCameraShotPanel(Panel):
    bl_label = "Cutscene Motion Camera Shot Controls"
    bl_idname = "OOT_CSMotionCameraShotPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        obj = context.view_layer.objects.active

        if obj is None or obj.type == "ARMATURE":
            box = self.layout.box()
            box.label(text=self.bl_label)
            box.prop(obj.data, "start_frame")
            box.row().prop(obj.data, "cam_mode", expand=True)
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

            def drawBoneProp(prop):
                if editBone is not None and prop in editBone:
                    r.prop(editBone, '["' + prop + '"]')
                else:
                    r.prop(activeBone, prop)

            box.label(text="Bone / Key point:")
            r = box.row()
            drawBoneProp("frames")
            drawBoneProp("fov")
            drawBoneProp("camroll")


class OOT_CutsceneMotionPanel(Panel):
    bl_label = "Cutscene Motion Controls"
    bl_idname = "OOT_CutsceneMotionPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout

        if getCSObj(None, context) is not None:
            layout.prop(context.scene, "ootBlenderScale")
            layout.prop(context.scene, "zc_previewlinkage")
            layout.operator("zcamedit.init_cs")
            layout.operator("zcamedit.create_shot")
            layout.operator("zcamedit.create_link_action")
            layout.operator("zcamedit.create_actor_action")


classes = (OOT_CSMotionActorCuePanel, OOT_CSMotionCameraShotPanel, OOT_CutsceneMotionPanel)


def csMotion_panels_register():
    for cls in classes:
        register_class(cls)

    # cam control
    Bone.frames = IntProperty(name="Frames", description="Key point frames value", default=1234, min=0)
    Bone.fov = FloatProperty(name="FoV", description="Field of view (degrees)", default=179.76, min=0.01, max=179.99)

    Bone.camroll = IntProperty(
        name="Roll",
        description="Camera roll (degrees), positive turns image clockwise",
        default=-0x7E,
        min=-0x80,
        max=0x7F,
    )

    Armature.start_frame = IntProperty(name="Start Frame", description="Shot start frame", default=0, min=0)

    Armature.cam_mode = EnumProperty(
        items=[
            ("normal", "Normal", "Normal (0x1 / 0x2)"),
            ("rel_link", "Rel. Link", "Relative to Link (0x5 / 0x6)"),
            ("0708", "0x7/0x8", "Not Yet Understood Mode (0x7 / 0x8)"),
        ],
        name="Mode",
        description="Camera command mode",
        default="normal",
    )


def csMotion_panels_unregister():
    del Armature.cam_mode
    del Armature.start_frame
    del Bone.camroll
    del Bone.fov
    del Bone.frames

    for cls in reversed(classes):
        unregister_class(cls)
