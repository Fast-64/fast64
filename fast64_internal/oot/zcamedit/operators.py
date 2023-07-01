import random
import bpy

from mathutils import Vector
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.types import Object, Operator, Scene, Context, UILayout, TOPBAR_MT_file_import, TOPBAR_MT_file_export
from bpy.utils import register_class, unregister_class
from bpy.props import FloatProperty, EnumProperty, StringProperty, BoolProperty
from .importer import importCutsceneMotion
from .exporter import exportCutsceneMotion
from .utility import (
    initCS,
    CheckGetCSObj,
    IsActionList,
    CreateOrInitPreview,
    CreateObject,
    MetersToBlend,
    IsActionPoint,
    CreateActorAction,
    GetActionListPoints,
    CreateActionPoint,
)


def CheckGetActionList(operator: Operator, context: Context) -> Object | None:
    obj = context.view_layer.objects.active

    if IsActionPoint(obj):
        obj = obj.parent

    if not IsActionList(obj):
        operator.report({"WARNING"}, "Select an action list or action point.")
        return None

    return obj


def CreateShot(context: Context, csObj: Object):
    shotArmature = context.blend_data.armatures.new("Shot")
    shotArmature.display_type = "STICK"
    shotArmature.show_names = True
    shotObj = CreateObject(context, shotArmature.name, shotArmature, True)
    shotObj.parent = csObj

    for i in range(4):
        bpy.ops.object.mode_set(mode="EDIT")
        bone = shotArmature.edit_bones.new(f"K{i + 1:02}")
        boneName = bone.name
        x = MetersToBlend(context, float(i + 1))
        bone.head = [x, 0.0, 0.0]
        bone.tail = [x, MetersToBlend(context, 1.0), 0.0]
        bpy.ops.object.mode_set(mode="OBJECT")
        bone = shotArmature.bones[boneName]
        bone.frames = 20
        bone.fov = 60.0
        bone.camroll = 0


def CreateDefaultActionPoint(context: Context, actorCueObj: Object, selectObj: bool):
    points = GetActionListPoints(context.scene, actorCueObj)

    if len(points) == 0:
        pos = Vector((random.random() * 40.0 - 20.0, -10.0, 0.0))
        startFrame = 0
        action_id = "0x0001"
    else:
        pos = points[-1].location + Vector((0.0, 10.0, 0.0))
        startFrame = points[-1].zc_apoint.start_frame + 20
        action_id = points[-1].zc_apoint.action_id

    CreateActionPoint(context, actorCueObj, selectObj, pos, startFrame, action_id)


def CreateDefaultActorAction(context: Context, actor_id: int, csObj: Object):
    actorCueObj = CreateActorAction(context, actor_id, csObj)

    for _ in range(2):
        CreateDefaultActionPoint(context, actorCueObj, False)


class ZCAMEDIT_OT_add_action_point(Operator):
    """Add a point to a Link or actor action list"""

    bl_idname = "zcamedit.add_action_point"
    bl_label = "Add point to current action"

    def execute(self, context):
        actorCueObj = CheckGetActionList(self, context)

        if actorCueObj is not None:
            CreateDefaultActionPoint(context, actorCueObj, True)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class ZCAMEDIT_OT_create_action_preview(Operator):
    """Create a preview empty object for a Link or actor action list"""

    bl_idname = "zcamedit.create_action_preview"
    bl_label = "Create preview object for action"

    def execute(self, context):
        actorCueObj = CheckGetActionList(self, context)

        if actorCueObj is not None:
            CreateOrInitPreview(context, actorCueObj.parent, actorCueObj.zc_alist.actor_id, True)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class ZCAMEDIT_OT_init_cs(Operator):
    """Click here after adding an empty Cutscene.YourCutsceneName"""

    bl_idname = "zcamedit.init_cs"
    bl_label = "Init Cutscene Empty"

    def execute(self, context):
        csObj = CheckGetCSObj(self, context)

        if csObj is not None:
            initCS(context, csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class ZCAMEDIT_OT_create_shot(Operator):
    """Create and initialize a camera shot armature"""

    bl_idname = "zcamedit.create_shot"
    bl_label = "Create camera shot"

    def execute(self, context):
        csObj = CheckGetCSObj(self, context)

        if csObj is not None:
            CreateShot(context, csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class ZCAMEDIT_OT_create_link_action(Operator):
    """Create a cutscene action list for Link"""

    bl_idname = "zcamedit.create_link_action"
    bl_label = "Create Link action list"

    def execute(self, context):
        csObj = CheckGetCSObj(self, context)

        if csObj is not None:
            CreateDefaultActorAction(context, -1, csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class ZCAMEDIT_OT_create_actor_action(Operator):
    """Create a cutscene action list for an actor (NPC)"""

    bl_idname = "zcamedit.create_actor_action"
    bl_label = "Create actor (NPC) action list"

    def execute(self, context):
        csObj = CheckGetCSObj(self, context)

        if csObj is not None:
            CreateDefaultActorAction(context, random.randint(1, 100), csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class ZCAMEDIT_OT_import_c(Operator, ImportHelper):
    """Import cutscene camera data from a Zelda 64 scene C source file."""

    bl_idname = "zcamedit.import_c"
    bl_label = "Import From C"

    filename_ext = ".c"
    filter_glob: StringProperty(default="*.c", options={"HIDDEN"}, maxlen=4096)

    def execute(self, context):
        ret = importCutsceneMotion(context, self.filepath)

        if ret is not None:
            self.report({"WARNING"}, ret)
            return {"CANCELLED"}

        self.report({"INFO"}, "Import successful")
        return {"FINISHED"}


class ZCAMEDIT_OT_export_c(Operator, ExportHelper):
    """Export cutscene camera into a Zelda 64 scene C source file."""

    bl_idname = "zcamedit.export_c"
    bl_label = "Export Into C"

    filename_ext = ".c"
    filter_glob: StringProperty(default="*.c", options={"HIDDEN"}, maxlen=4096)

    use_floats: BoolProperty(
        name="Use Floats",
        description="Write FOV value as floating point (e.g. 45.0f). If False, write as integer (e.g. 0x42340000)",
        default=False,
    )

    use_tabs: BoolProperty(
        name="Use Tabs",
        description="Indent commands with tabs rather than 4 spaces. For decomp toolchain compatibility",
        default=True,
    )

    use_cscmd: BoolProperty(
        name="Use CS_CMD defines",
        description="Write first parameter as CS_CMD_CONTINUE or CS_CMD_STOP vs. 0 or -1",
        default=False,
    )

    def execute(self, context):
        ret = exportCutsceneMotion(context, self.filepath, self.use_floats, self.use_tabs, self.use_cscmd)

        if ret is not None:
            self.report({"WARNING"}, ret)
            return {"CANCELLED"}

        self.report({"INFO"}, "Export successful")
        return {"FINISHED"}


classes = (
    ZCAMEDIT_OT_add_action_point,
    ZCAMEDIT_OT_create_action_preview,
    ZCAMEDIT_OT_init_cs,
    ZCAMEDIT_OT_create_shot,
    ZCAMEDIT_OT_create_link_action,
    ZCAMEDIT_OT_create_actor_action,
    ZCAMEDIT_OT_import_c,
    ZCAMEDIT_OT_export_c,
)


def menu_func_import(self, context: Context):
    self.layout.operator(ZCAMEDIT_OT_import_c.bl_idname, text="Z64 cutscene C source (.c)")


def menu_func_export(self, context: Context):
    self.layout.operator(ZCAMEDIT_OT_export_c.bl_idname, text="Z64 cutscene C source (.c)")


def zcamedit_ops_register():
    for cls in classes:
        register_class(cls)

    # cs control
    if not hasattr(Scene, "ootBlenderScale"):
        Scene.ootBlenderScale = FloatProperty(
            name="Scale",
            description="All stair steps in game are 10 units high. Assuming Hylian "
            + "carpenters follow US building codes, that's about 17 cm or a scale of about "
            + "56 if your scene is in meters.",
            soft_min=1.0,
            soft_max=1000.0,
            default=56.0,
        )

    Scene.zc_previewlinkage = EnumProperty(
        items=[("link_adult", "Adult", "Adult Link (170 cm)", 0), ("link_child", "Child", "Child Link (130 cm)", 1)],
        name="Link age for preview",
        description="For setting Link's height for preview",
        default="link_adult",
    )

    # import export controls
    TOPBAR_MT_file_import.append(menu_func_import)
    TOPBAR_MT_file_export.append(menu_func_export)


def zcamedit_ops_unregister():
    del Scene.zc_previewlinkage

    # import export controls
    TOPBAR_MT_file_export.remove(menu_func_export)
    TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in reversed(classes):
        unregister_class(cls)
