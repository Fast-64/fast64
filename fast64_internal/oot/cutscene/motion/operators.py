import bpy

from bpy.types import Object, Operator, Context, Armature
from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, EnumProperty
from ....utility import PluginError
from .io_classes import OOTCSMotionObjectFactory
from .constants import ootEnumCSActorCueListCommandType
from ..preview import initFirstFrame, setupCompositorNodes
from .utility import (
    setupActorCuePreview,
    metersToBlend,
    getCSMotionValidateObj,
    getNameInformations,
    createNewBone,
    createNewCameraShot,
    getCutsceneEndFrame,
)


def getActorCueList(operator: Operator, context: Context) -> Object | None:
    cueListObj = activeObj = context.view_layer.objects.active

    if activeObj.ootEmptyType == "CS Actor Cue" and activeObj.parent.ootEmptyType == "CS Actor Cue List":
        cueListObj = activeObj.parent

    if not cueListObj.ootEmptyType == "CS Actor Cue List" and cueListObj.parent.ootEmptyType == "Cutscene":
        operator.report({"WARNING"}, "Select an action list or action point.")
        return None

    return cueListObj


def createNewActorCueList(csObj: Object, isPlayer: bool):
    """Creates a new Actor or Player Cue List and adds one basic cue and the dummy one"""
    objFactory = OOTCSMotionObjectFactory()
    playerOrActor = "Player" if isPlayer else "Actor"
    newActorCueListObj = objFactory.getNewActorCueListObject(f"New {playerOrActor} Cue List", "0x000F", None)
    index, csPrefix = getNameInformations(csObj, f"{playerOrActor} Cue List", None)
    newActorCueListObj.name = f"{csPrefix}.{playerOrActor} Cue List {index:02}"

    # add a basic actor cue and the dummy one
    for i in range(2):
        nameSuffix = f"{i + 1:02}" if i == 0 else "999 (D)"
        newActorCueObj = objFactory.getNewActorCueObject(
            f"{csPrefix}.{playerOrActor} Cue {index:02}.{nameSuffix}",
            i,
            "0x0000",
            [0, 0, 0],
            ["0x0", "0x0", "0x0"],
            newActorCueListObj,
        )

    # finally, parenting the object to the cutscene
    newActorCueListObj.parent = csObj


class OOTCSMotionPlayPreview(Operator):
    """Camera Preview Playback"""

    bl_idname = "object.play_preview"
    bl_label = "Preview Playback"

    def execute(self, context):
        try:
            csObj = getCSMotionValidateObj(None, None, None)

            if csObj is not None:
                # get and set the camera
                cameraObj = None
                for childObj in csObj.children:
                    if childObj.type == "CAMERA":
                        cameraObj = childObj
                        break

                # from https://blender.stackexchange.com/a/259103
                space = None
                for area in context.screen.areas:
                    if (area != context.area) and (area.type == "VIEW_3D"):
                        for space in area.spaces:
                            if space.type == "VIEW_3D":
                                break
                if space is not None:
                    space.region_3d.view_perspective = "CAMERA"

                # setup frame data and play the animation
                endFrame = getCutsceneEndFrame(csObj)
                context.scene.frame_end = endFrame if endFrame > -1 else context.scene.frame_end
                context.scene.frame_set(context.scene.frame_start)
                bpy.context.scene.ootCSPreviewCSObj = csObj
                bpy.context.scene.ootCSPreviewNodesReady = False
                setupCompositorNodes()
                initFirstFrame(csObj, bpy.context.scene.ootCSPreviewNodesReady, cameraObj)
                bpy.ops.screen.animation_cancel()
                bpy.ops.screen.animation_play()
                return {"FINISHED"}
        except:
            return {"CANCELLED"}
        

class OOTCSMotionAddBone(Operator):
    """Add a bone to an armature"""

    bl_idname = "object.add_bone"
    bl_label = "Add Bone"

    def execute(self, context):
        try:
            cameraShotObj = getCSMotionValidateObj(None, None, "Camera Shot")

            if cameraShotObj is not None:
                armatureData: Armature = cameraShotObj.data
                cameraShotObj.select_set(True)
                lastMode = "EDIT" if "EDIT" in context.mode else context.mode

                # create the new bone with standard informations
                blendOne = metersToBlend(context, float(1))
                boneName = f"CS_??.Camera Point ??"
                createNewBone(cameraShotObj, boneName, [blendOne, blendOne, 0.0], [blendOne, 0.0, 0.0])

                # update the name of the new bone and move it to the position of the previous last one
                bpy.ops.object.mode_set(mode="EDIT")
                if len(armatureData.edit_bones) > 0 and "CS_" in armatureData.edit_bones[-2].name:
                    secondToLastBone = armatureData.edit_bones[-2]
                    newBone = armatureData.edit_bones[-1]
                    splitName = secondToLastBone.name.split(" ")
                    newBone.name = f"{splitName[0]} Point {int(splitName[2]) + 1:02}"
                    newBone.head = secondToLastBone.head
                    newBone.tail = secondToLastBone.tail
                bpy.ops.object.mode_set(mode="OBJECT") # going back to object mode to update the bones properly

                if armatureData.bones[-1].name == boneName:
                    raise PluginError("ERROR: Something went wrong...")

                bpy.ops.object.mode_set(mode=lastMode)
                return {"FINISHED"}
            else:
                raise PluginError("You must select an armature object parented to a cutscene empty object!")
        except:
            return {"CANCELLED"}


class OOTCSMotionAddActorCue(Operator):
    """Add an entry to a player or actor cue list"""

    bl_idname = "object.add_actor_cue_point"
    bl_label = "Add Actor Cue"

    def execute(self, context):
        actorCueListObj = getCSMotionValidateObj(None, None, None)

        try:
            if actorCueListObj is not None:
                if actorCueListObj.parent is not None and actorCueListObj.parent.ootEmptyType != "Cutscene":
                    actorCueListObj = actorCueListObj.parent

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
        cueList = getCSMotionValidateObj(None, None, None)

        if cueList is not None and cueList.ootEmptyType in ["CS Actor Cue List", "CS Player Cue List"]:
            setupActorCuePreview(
                cueList.parent, "Actor" if "Actor" in cueList.ootEmptyType else "Player", True, cueList
            )
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


class OOTCSMotionCreateCameraShot(Operator):
    """Create and initialize a camera shot armature"""

    bl_idname = "object.create_camera_shot"
    bl_label = "Create Camera Shot"

    def execute(self, context):
        csObj = getCSMotionValidateObj(None, None, None)

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
        csObj = getCSMotionValidateObj(None, None, None)

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
        csObj = getCSMotionValidateObj(None, None, None)

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
    OOTCSMotionPlayPreview,
    OOTCSMotionAddBone,
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
