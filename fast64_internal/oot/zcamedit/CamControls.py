from bpy.types import Panel, Bone, Armature
from bpy.props import FloatProperty, IntProperty, EnumProperty
from bpy.utils import register_class, unregister_class
from .CamData import EditBoneToBone


class ZCAMEDIT_PT_cam_panel(Panel):
    bl_label = "zcamedit Cutscene Camera Controls"
    bl_idname = "ZCAMEDIT_PT_cam_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "ARMATURE":
            return
        box = self.layout.box()
        box.label(text=self.bl_label)
        box.prop(obj.data, "start_frame")
        box.row().prop(obj.data, "cam_mode", expand=True)
        active_bone = edit_bone = None
        if obj.mode == "OBJECT":
            active_bone = obj.data.bones.active
            if active_bone is None:
                return
        elif obj.mode == "EDIT":
            edit_bone = obj.data.edit_bones.active
            if edit_bone is None:
                return
            active_bone = EditBoneToBone(obj, edit_bone)

        def bprop(prop):
            if edit_bone is not None and prop in edit_bone:
                r.prop(edit_bone, '["' + prop + '"]')
            else:
                r.prop(active_bone, prop)

        box.label(text="Bone / Key point:")
        r = box.row()
        bprop("frames")
        bprop("fov")
        bprop("camroll")


def CamControls_register():
    register_class(ZCAMEDIT_PT_cam_panel)
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


def CamControls_unregister():
    del Armature.cam_mode
    del Armature.start_frame
    del Bone.camroll
    del Bone.fov
    del Bone.frames
    unregister_class(ZCAMEDIT_PT_cam_panel)
