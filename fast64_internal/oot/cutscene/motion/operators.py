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
    initCutscene,
    getCSObj,
    isActorCueList,
    createOrInitPreview,
    createNewObject,
    metersToBlend,
    isActorCuePoint,
    createActorCueList,
    getActorCuePointObjects,
    createActorCuePoint,
)


def getActorCueList(operator: Operator, context: Context) -> Object | None:
    obj = context.view_layer.objects.active

    if isActorCuePoint(obj):
        obj = obj.parent

    if not isActorCueList(obj):
        operator.report({"WARNING"}, "Select an action list or action point.")
        return None

    return obj


def createCameraShot(context: Context, csObj: Object):
    shotArmature = context.blend_data.armatures.new("Shot")
    shotArmature.display_type = "STICK"
    shotArmature.show_names = True
    shotObj = createNewObject(context, shotArmature.name, shotArmature, True)
    shotObj.parent = csObj

    for i in range(4):
        bpy.ops.object.mode_set(mode="EDIT")
        bone = shotArmature.edit_bones.new(f"K{i + 1:02}")
        boneName = bone.name
        x = metersToBlend(context, float(i + 1))
        bone.head = [x, 0.0, 0.0]
        bone.tail = [x, metersToBlend(context, 1.0), 0.0]
        bpy.ops.object.mode_set(mode="OBJECT")
        bone = shotArmature.bones[boneName]
        bone.frames = 20
        bone.fov = 60.0
        bone.camroll = 0


def createBasicActorCuePoint(context: Context, actorCueObj: Object, selectObj: bool):
    points = getActorCuePointObjects(context.scene, actorCueObj)

    if len(points) == 0:
        pos = Vector((random.random() * 40.0 - 20.0, -10.0, 0.0))
        startFrame = 0
        action_id = "0x0001"
    else:
        pos = points[-1].location + Vector((0.0, 10.0, 0.0))
        startFrame = points[-1].zc_apoint.start_frame + 20
        action_id = points[-1].zc_apoint.action_id

    createActorCuePoint(context, actorCueObj, selectObj, pos, startFrame, action_id)


def createBasicActorCueList(context: Context, actor_id: int, csObj: Object):
    actorCueObj = createActorCueList(context, actor_id, csObj)

    for _ in range(2):
        createBasicActorCuePoint(context, actorCueObj, False)


class OOTCSMotionAddActorCuePoint(Operator):
    """Add an entry to a player or actor cue list"""

    bl_idname = "object.add_actor_cue_point"
    bl_label = "Add point to current action"

    def execute(self, context):
        actorCueObj = getActorCueList(self, context)

        if actorCueObj is not None:
            createBasicActorCuePoint(context, actorCueObj, True)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionCreateActorCuePreview(Operator):
    """Create a preview empty object for a player or an actor cue list"""

    bl_idname = "object.create_actor_cue_preview"
    bl_label = "Create preview object for action"

    def execute(self, context):
        actorCueObj = getActorCueList(self, context)

        if actorCueObj is not None:
            createOrInitPreview(context, actorCueObj.parent, actorCueObj.zc_alist.actor_id, True)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionInitCutscene(Operator):
    """Click here after adding an empty Cutscene.YourCutsceneName"""

    bl_idname = "object.init_cutscene"
    bl_label = "Init Cutscene Empty"

    def execute(self, context):
        csObj = getCSObj(self, context)

        if csObj is not None:
            initCutscene(context, csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionCreateCameraShot(Operator):
    """Create and initialize a camera shot armature"""

    bl_idname = "object.create_camera_shot"
    bl_label = "Create Camera Shot"

    def execute(self, context):
        csObj = getCSObj(self, context)

        if csObj is not None:
            createCameraShot(context, csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionCreatePlayerCueList(Operator):
    """Create a cutscene player cue list"""

    bl_idname = "object.create_player_cue_list"
    bl_label = "Create Player Cue List"

    def execute(self, context):
        csObj = getCSObj(self, context)

        if csObj is not None:
            createBasicActorCueList(context, -1, csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionCreateActorCueList(Operator):
    """Create a cutscene actor cue list"""

    bl_idname = "object.create_actor_cue_list"
    bl_label = "Create Actor Cue list"

    def execute(self, context):
        csObj = getCSObj(self, context)

        if csObj is not None:
            createBasicActorCueList(context, random.randint(1, 100), csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionImportFromC(Operator, ImportHelper):
    """Import cutscene camera data from a Zelda 64 scene C source file."""

    bl_idname = "object.import_c"
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


class OOTCSMotionExportToC(Operator, ExportHelper):
    """Export cutscene camera into a Zelda 64 scene C source file."""

    bl_idname = "object.export_c"
    bl_label = "Export Into C"

    filename_ext = ".c"
    filter_glob: StringProperty(default="*.c", options={"HIDDEN"}, maxlen=4096)

    use_floats: BoolProperty(
        name="Use Floats",
        description="Write FOV value as floating point (e.g. 45.0f). If False, write as integer (e.g. 0x42340000)",
        default=False,
    )

    use_cscmd: BoolProperty(
        name="Use CS_CMD defines",
        description="Write first parameter as CS_CMD_CONTINUE or CS_CMD_STOP vs. 0 or -1",
        default=False,
    )

    def execute(self, context):
        ret = exportCutsceneMotion(context, self.filepath, self.use_floats, self.use_cscmd)

        if ret is not None:
            self.report({"WARNING"}, ret)
            return {"CANCELLED"}

        self.report({"INFO"}, "Export successful")
        return {"FINISHED"}


classes = (
    OOTCSMotionAddActorCuePoint,
    OOTCSMotionCreateActorCuePreview,
    OOTCSMotionInitCutscene,
    OOTCSMotionCreateCameraShot,
    OOTCSMotionCreatePlayerCueList,
    OOTCSMotionCreateActorCueList,
    OOTCSMotionImportFromC,
    OOTCSMotionExportToC,
)


def menu_func_import(self, context: Context):
    self.layout.operator(OOTCSMotionImportFromC.bl_idname, text="Z64 cutscene C source (.c)")


def menu_func_export(self, context: Context):
    self.layout.operator(OOTCSMotionExportToC.bl_idname, text="Z64 cutscene C source (.c)")


def csMotion_ops_register():
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


def csMotion_ops_unregister():
    del Scene.zc_previewlinkage

    # import export controls
    TOPBAR_MT_file_export.remove(menu_func_export)
    TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in reversed(classes):
        unregister_class(cls)
