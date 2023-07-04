import random
import bpy

from mathutils import Vector
from bpy_extras.io_utils import ImportHelper
from bpy.types import Object, Operator, Context, TOPBAR_MT_file_import
from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, BoolProperty, EnumProperty
from .constants import ootEnumCSActorCueListCommandType
from .importer import importCutsceneMotion
from .utility import (
    getCSObj,
    createOrInitPreview,
    createNewObject,
    metersToBlend,
    createActorCueList,
    getActorCueObjects,
    createActorCue,
)


def getActorCueList(operator: Operator, context: Context) -> Object | None:
    cueListObj = activeObj = context.view_layer.objects.active

    if activeObj.ootEmptyType == "CS Actor Cue" and activeObj.parent.ootEmptyType == "CS Actor Cue List":
        cueListObj = activeObj.parent

    if not cueListObj.ootEmptyType == "CS Actor Cue List" and cueListObj.parent.ootEmptyType == "Cutscene":
        operator.report({"WARNING"}, "Select an action list or action point.")
        return None

    return cueListObj


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
        bone.ootCamShotPointProp.shotPointFrame = 20
        bone.ootCamShotPointProp.shotPointViewAngle = 60.0
        bone.ootCamShotPointProp.shotPointRoll = 0


def createBasicActorCue(context: Context, actorCueObj: Object, selectObj: bool):
    points = getActorCueObjects(context.scene, actorCueObj)

    if len(points) == 0:
        pos = Vector((random.random() * 40.0 - 20.0, -10.0, 0.0))
        startFrame = 0
        action_id = "0x0001"
    else:
        pos = points[-1].location + Vector((0.0, 10.0, 0.0))
        startFrame = points[-1].ootCSMotionProperty.actorCueProp.cueStartFrame + 20
        action_id = points[-1].ootCSMotionProperty.actorCueProp.cueActionID

    createActorCue(context, actorCueObj, selectObj, pos, startFrame, action_id)


def createBasicActorCueList(context: Context, actor_id: int, csObj: Object):
    actorCueObj = createActorCueList(context, actor_id, csObj)

    for _ in range(2):
        createBasicActorCue(context, actorCueObj, False)


class OOTCSMotionAddActorCue(Operator):
    """Add an entry to a player or actor cue list"""

    bl_idname = "object.add_actor_cue_point"
    bl_label = "Add Actor Cue"

    def execute(self, context):
        actorCueObj = getActorCueList(self, context)

        if actorCueObj is not None:
            createBasicActorCue(context, actorCueObj, True)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionCreateActorCuePreview(Operator):
    """Create a preview empty object for a player or an actor cue list"""

    bl_idname = "object.create_actor_cue_preview"
    bl_label = "Create Preview Object"

    def execute(self, context):
        actorCueObj = getActorCueList(self, context)

        if actorCueObj is not None:
            createOrInitPreview(
                context, actorCueObj.parent, actorCueObj.ootCSMotionProperty.actorCueListProp.actorCueSlot, True
            )
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


class OOT_SearchActorCueCmdTypeEnumOperator(Operator):
    bl_idname = "object.oot_search_actorcue_cmdtype_enum_operator"
    bl_label = "Select Command Type"
    bl_property = "commandType"
    bl_options = {"REGISTER", "UNDO"}

    commandType: EnumProperty(items=ootEnumCSActorCueListCommandType, default="0x000F")
    objName: StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.objName]
        obj.ootCSMotionProperty.actorCueListProp.commandType = self.commandType

        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.commandType)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


classes = (
    OOTCSMotionAddActorCue,
    OOTCSMotionCreateActorCuePreview,
    OOTCSMotionCreateCameraShot,
    OOTCSMotionCreatePlayerCueList,
    OOTCSMotionCreateActorCueList,
    OOTCSMotionImportFromC,
    OOT_SearchActorCueCmdTypeEnumOperator,
)


def menu_func_import(self, context: Context):
    self.layout.operator(OOTCSMotionImportFromC.bl_idname, text="Z64 cutscene C source (.c)")


def csMotion_ops_register():
    for cls in classes:
        register_class(cls)

    # import export controls
    TOPBAR_MT_file_import.append(menu_func_import)


def csMotion_ops_unregister():
    # import export controls
    TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in reversed(classes):
        unregister_class(cls)
