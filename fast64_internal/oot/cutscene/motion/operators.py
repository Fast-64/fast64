import bpy

from bpy.types import Object, Operator, Context, Armature
from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, EnumProperty
from ....utility import PluginError
from .io_classes import OOTCSMotionObjectFactory
from .constants import ootEnumCSActorCueListCommandType
from .utility import (
    createOrInitPreview,
    metersToBlend,
    getCutsceneMotionObject,
    getNameInformations,
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
    index, csPrefix, csNbr = getNameInformations(csObj, f"{playerOrActor} Cue List")

    # there are other lists
    if index is not None and csPrefix is not None:
        newActorCueListObj.name = f"{csPrefix}.{playerOrActor} Cue List {index:02}"
    else:
        # it's the first list we're creating
        csPrefix = f"CS_{csNbr:02}"
        index = 1
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


def createNewBone(cameraShotObj: Object, name: str, headPos: list[float], tailPos: list[float]):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    armatureData: Armature = cameraShotObj.data
    newEditBone = armatureData.edit_bones.new(name)
    newEditBone.head = headPos
    newEditBone.tail = tailPos
    bpy.ops.object.mode_set(mode="OBJECT")
    newBone = armatureData.bones[name]
    newBone.ootCamShotPointProp.shotPointFrame = 30
    newBone.ootCamShotPointProp.shotPointViewAngle = 60.0
    newBone.ootCamShotPointProp.shotPointRoll = 0
    bpy.ops.object.select_all(action="DESELECT")


def createNewCameraShot(csObj: Object):
    index, csPrefix, csNbr = getNameInformations(csObj, "Camera Shot")

    if index is not None and csPrefix is not None:
        name = f"{csPrefix}.Camera Shot {index:02}"
    else:
        csPrefix = f"CS_{csNbr:02}"
        name = f"{csPrefix}.Camera Shot 01"

    # create a basic armature
    newCameraShotObj = OOTCSMotionObjectFactory().getNewArmatureObject(name, True, csObj)

    # add 4 bones since it's the minimum required
    for i in range(1, 5):
        posX = metersToBlend(bpy.context, float(i))
        createNewBone(
            newCameraShotObj,
            f"{csPrefix}.Camera Point {i:02}",
            [posX, 0.0, 0.0],
            [posX, metersToBlend(bpy.context, 1.0), 0.0],
        )


class OOTCSMotionAddBone(Operator):
    """Add a bone to an armature"""

    bl_idname = "object.add_bone"
    bl_label = "Add Bone"

    def execute(self, context):
        try:
            cameraShotObj = getCutsceneMotionObject(False)

            if cameraShotObj is not None:
                armatureData: Armature = cameraShotObj.data

                if len(armatureData.bones) > 0 and "CS_" in armatureData.bones[-1].name:
                    splitName = armatureData.bones[-1].name.split(" ")
                    boneName = f"{splitName[0]} Point {int(splitName[2]) + 1:02}"
                else:
                    boneName = f"CS_??.Camera Point ??"

                blendOne = metersToBlend(context, float(1))
                createNewBone(cameraShotObj, boneName, [blendOne, blendOne, 0.0], [blendOne, 0.0, 0.0])
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
