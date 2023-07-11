import random
import bpy

from mathutils import Vector
from bpy.types import Object, Operator, Context
from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, EnumProperty
from ....utility import PluginError
from .io_classes import OOTCSMotionObjectFactory
from .constants import ootEnumCSActorCueListCommandType
from .utility import (
    createOrInitPreview,
    createNewObject,
    metersToBlend,
    createActorCueList,
    getActorCueObjects,
    createActorCue,
    getCutsceneMotionObject,
    createNewActorCueList,
    createNewCameraShot,
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
        actorCueListObj = getCutsceneMotionObject(False)

        try:
            if actorCueListObj is not None:
                # start by creating the new object with basic values
                objFactory = OOTCSMotionObjectFactory()
                newActorCueObj = objFactory.getNewActorCueObject(
                    "New Actor Cue",
                    0,
                    "0x0000",
                    [0, 0, 0],
                    ["0x0", "0x0", "0x0"],
                    None,
                )

                # if there's other actor cues, take the information from the last non-dummy one
                if len(actorCueListObj.children) > 0:
                    dummyCue = None
                    for i, obj in enumerate(actorCueListObj.children):
                        if obj.ootEmptyType == "CS Dummy Cue":
                            dummyCue = obj

                    if dummyCue is not None:
                        lastCueObj = actorCueListObj.children[i - 1]
                        nameSplit = lastCueObj.name.split(".")
                        index = int(nameSplit[-1]) + 1
                        startFrame = dummyCue.ootCSMotionProperty.actorCueProp.cueStartFrame
                        newActorCueObj.name = f"{nameSplit[0]}.{nameSplit[1]}.{index:02}"
                        newActorCueObj.ootCSMotionProperty.actorCueProp.cueStartFrame = startFrame
                        dummyCue.ootCSMotionProperty.actorCueProp.cueStartFrame += 1
                        newActorCueObj.location = lastCueObj.location
                        newActorCueObj.rotation_euler = lastCueObj.rotation_euler
                else:
                    # else create the name from the actor cue list object
                    nameSplit = actorCueListObj.name.split(".")
                    index = int(nameSplit[1].split(" ")[3])
                    newActorCueObj.name = f"{nameSplit[0]}.{nameSplit[1][:-8]} {index}.01"

                    # add the dummy cue since the list is empty
                    nameSplit = newActorCueObj.name.split(".")
                    newDummyCueObj = objFactory.getNewActorCueObject(
                        f"{nameSplit[0]}.{nameSplit[1]}.999 (D)",
                        1,
                        "0x0000",
                        [0, 0, 0],
                        ["0x0", "0x0", "0x0"],
                        actorCueListObj,
                    )

                # update the end frame of the real cue
                getEndFrame = newActorCueObj.ootCSMotionProperty.actorCueProp.cueEndFrame
                newActorCueObj.parent = actorCueListObj
            else:
                raise PluginError("ERROR: Select the Actor or Player Cue List!")

            return {"FINISHED"}
        except:
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
        csObj = getCutsceneMotionObject(False)

        if csObj is not None:
            createNewCameraShot(csObj)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionCreatePlayerCueList(Operator):
    """Create a cutscene player cue list"""

    bl_idname = "object.create_player_cue_list"
    bl_label = "Create Player Cue List"

    def execute(self, context):
        csObj = getCutsceneMotionObject(False)

        try:
            if csObj is not None:
                createNewActorCueList(csObj, True)
            else:
                raise PluginError("ERROR: You must select the cutscene object!")

            return {"FINISHED"}
        except:
            return {"CANCELLED"}


class OOTCSMotionCreateActorCueList(Operator):
    """Create a cutscene actor cue list"""

    bl_idname = "object.create_actor_cue_list"
    bl_label = "Create Actor Cue list"

    def execute(self, context):
        csObj = getCutsceneMotionObject(False)

        try:
            if csObj is not None:
                createNewActorCueList(csObj, False)
            else:
                raise PluginError("ERROR: You must select the cutscene object!")

            return {"FINISHED"}
        except:
            return {"CANCELLED"}


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
    OOT_SearchActorCueCmdTypeEnumOperator,
)


def csMotion_ops_register():
    for cls in classes:
        register_class(cls)


def csMotion_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
