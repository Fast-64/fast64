import bpy

from bpy.types import Scene, Object, Bone, Context, EditBone, Operator, Armature
from mathutils import Vector
from ....utility import yUpToZUp
from ...oot_utility import ootParseRotation
from .constants import ootEnumCSActorCueListCommandType


def getBlenderPosition(pos: list[int], scale: int):
    """Returns the converted OoT position"""

    # OoT: +X right, +Y up, -Z forward
    # Blender: +X right, +Z up, +Y forward
    return [float(pos[0]) / scale, -float(pos[2]) / scale, float(pos[1]) / scale]


def getRotation(data: str):
    """Returns the rotation converted to hexadecimal"""

    if "DEG_TO_BINANG" in data or not "0x" in data:
        angle = float(data.split("(")[1].removesuffix(")") if "DEG_TO_BINANG" in data else data)
        binang = int(angle * (0x8000 / 180.0))  # from ``DEG_TO_BINANG()`` in decomp

        # if the angle value is higher than 0xFFFF it means we're at 360 degrees
        return f"0x{0xFFFF if binang > 0xFFFF else binang:04X}"
    else:
        return data


def getBlenderRotation(rotation: list[str]):
    """Returns the converted OoT rotation"""

    rot = [int(getRotation(r), base=16) for r in rotation]
    return yUpToZUp @ Vector(ootParseRotation(rot))


def getCutsceneMotionObject(isParent: bool):
    """Returns the selected motion object or its parent"""

    activeObj = bpy.context.view_layer.objects.active
    nonListTypes = ["CS Player Cue", "CS Actor Cue", "CS Dummy Cue", "Cutscene"]
    listTypes = ["CS Player Cue List", "CS Actor Cue List"]
    parentObj = activeObj.parent

    # get the actor or player cue
    if isParent:
        # get the actor or player cue list
        if parentObj is not None:
            if parentObj.type == "EMPTY" and parentObj.ootEmptyType in listTypes:
                return parentObj
    else:
        if activeObj.type == "EMPTY" and activeObj.ootEmptyType in nonListTypes or activeObj.ootEmptyType in listTypes:
            return activeObj

    # get the camera shot
    if (
        activeObj.type == "ARMATURE"
        and parentObj is not None
        and parentObj.type == "EMPTY"
        and parentObj.ootEmptyType == "Cutscene"
    ):
        return activeObj

    return None


def getNameInformations(csObj: Object, target: str):
    index = csPrefix = None
    csNbr = 0

    # get the last target objects names
    if csObj.children is not None:
        for obj in csObj.children:
            if obj.type == "EMPTY" and "Cue List" in obj.name or "Camera Shot" in obj.name:
                csPrefix = obj.name.split(".")[0]
                if target in obj.name:
                    index = int(obj.name.split(" ")[-1]) + 1

    # saving the cutscene number if the target objects can't be found
    for obj in bpy.data.objects:
        if obj.type == "EMPTY" and obj.ootEmptyType == "Cutscene":
            csNbr += 1

        if obj.name == csObj.name:
            break

    return index, csPrefix, csNbr


def createNewActorCueList(csObj: Object, isPlayer: bool):
    """Creates a new Actor or Player Cue List and adds one basic cue and the dummy one"""
    from .io_classes import OOTCSMotionObjectFactory  # circular import fix

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
    from .io_classes import OOTCSMotionObjectFactory  # circular import fix

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


# ---


def getEditBoneFromBone(shotObj: Object, bone: Bone) -> EditBone | Bone:
    for editBone in shotObj.data.edit_bones:
        if editBone.name == bone.name:
            return editBone
    else:
        print("Could not find corresponding bone")
        return bone


def metersToBlend(context: Context, value: float):
    return value * 56.0 / context.scene.ootBlenderScale


def createNewObject(context: Context, name: str, data, selectObject: bool) -> Object:
    newObj = bpy.data.objects.new(name=name, object_data=data)
    context.view_layer.active_layer_collection.collection.objects.link(newObj)

    if selectObject:
        newObj.select_set(True)
        context.view_layer.objects.active = newObj

    return newObj


def getCSObj(operator: Operator, context: Context):
    """Check if we are editing a cutscene."""
    csObj = context.view_layer.objects.active

    if csObj.ootEmptyType != "Cutscene":
        if operator is not None:
            operator.report({"WARNING"}, "You need to select the Cutscene Empty Object")
        return None

    if not csObj.name.startswith("Cutscene."):
        if operator is not None:
            operator.report({"WARNING"}, 'Cutscene Empty Object must be named "Cutscene.YourCutsceneName"')
        return None

    return csObj


# action data
def getActorName(actor_id: int):
    return "Link" if actor_id < 0 else f"Actor{actor_id}"


def createOrInitPreview(context: Context, csObj: Object, actor_id: int, selectObject=False):
    for obj in bpy.data.objects:
        if (
            obj.ootEmptyType == "CS Actor Cue Preview"
            and obj.parent.ootEmptyType == "Cutscene"
            and obj.parent == csObj
            and obj.ootCSMotionProperty.actorCueListProp.actorCueSlot == actor_id
        ):
            previewObj = obj
            break
    else:
        previewObj = createNewObject(context, f"Preview.{getActorName(actor_id)}.001", None, selectObject)
        previewObj.parent = csObj

    actorHeight = 1.5

    if actor_id < 0:
        actorHeight = 1.7 if context.scene.previewPlayerAge == "link_adult" else 1.3

    previewObj.empty_display_type = "SINGLE_ARROW"
    previewObj.empty_display_size = metersToBlend(context, actorHeight)
    previewObj.ootCSMotionProperty.actorCueListProp.actorCueSlot = actor_id
    previewObj.ootEmptyType = "CS Actor Cue Preview"


class PropsBone:
    def __init__(self, shotObj: Object, bone: Bone):
        editBone = getEditBoneFromBone(shotObj, bone) if shotObj.mode == "EDIT" else None
        self.name = bone.name
        self.head = editBone.head if editBone is not None else bone.head
        self.tail = editBone.tail if editBone is not None else bone.tail

        self.frames = (
            editBone["shotPointFrame"]
            if editBone is not None and "shotPointFrame" in editBone
            else bone.ootCamShotPointProp.shotPointFrame
        )

        self.fov = (
            editBone["shotPointViewAngle"]
            if editBone is not None and "shotPointViewAngle" in editBone
            else bone.ootCamShotPointProp.shotPointViewAngle
        )

        self.camroll = (
            editBone["shotPointRoll"]
            if editBone is not None and "shotPointRoll" in editBone
            else bone.ootCamShotPointProp.shotPointRoll
        )


# camdata
def getShotPropBones(shotObj: Object):
    bones: list[PropsBone] = []

    for bone in shotObj.data.bones:
        if bone.parent is not None:
            print("Camera armature bones are not allowed to have parent bones")
            return None

        bones.append(PropsBone(shotObj, bone))

    bones.sort(key=lambda b: b.name)
    return bones


def getShotPropBonesChecked(shotObj: Object):
    propBones = getShotPropBones(shotObj)

    if propBones is None:
        raise RuntimeError("Error in bone properties")

    if len(propBones) < 4:
        raise RuntimeError(f"Only {len(propBones)} bones in `{shotObj.name}`")

    return propBones


def getShotObjects(scene: Scene, csObj: Object):
    shotObjects: list[Object] = [
        obj for obj in scene.objects if obj.type == "ARMATURE" and obj.parent is not None and obj.parent == csObj
    ]
    shotObjects.sort(key=lambda obj: obj.name)

    return shotObjects


def getFakeCamCmdsLength(shotObj: Object, useAT: bool):
    propBones = getShotPropBonesChecked(shotObj)
    base = max(2, sum(b.frames for b in propBones))
    # Seems to be the algorithm which was used in the canon tool: the at list
    # counts the extra point (same frames as the last real point), and the pos
    # list doesn't count the extra point but adds 1. Of course, neither of these
    # values is actually the number of frames the camera motion lasts for.
    return base + (propBones[-1].frames if useAT else 1)


def getFakeCSEndFrame(context: Context, csObj: Object):
    shotObjects = getShotObjects(context.scene, csObj)
    csEndFrame = -1

    for shotObj in shotObjects:
        endFrame = shotObj.data.ootCamShotProp.shotStartFrame + getFakeCamCmdsLength(shotObj, False) + 1
        csEndFrame = max(csEndFrame, endFrame)

    return csEndFrame


def setupCutscene(csObj: Object):
    from .io_classes import OOTCSMotionObjectFactory  # circular import fix

    objFactory = OOTCSMotionObjectFactory()
    context = bpy.context
    camObj = objFactory.getNewCameraObject(
        f"{csObj.name}.Camera",
        metersToBlend(context, 0.25),
        metersToBlend(context, 1e-3),
        metersToBlend(context, 200.0),
        0.95,
        csObj,
    )
    print("Created New Camera!")

    # Preview setup, used when importing cutscenes
    for obj in csObj.children:
        if obj.ootEmptyType == "CS Actor Cue List":
            createOrInitPreview(context, obj.parent, obj.ootCSMotionProperty.actorCueListProp.actorCueSlot, False)

    # Other setup
    context.scene.frame_start = 0
    context.scene.frame_end = max(getFakeCSEndFrame(context, csObj), context.scene.frame_end)
    context.scene.render.fps = 20
    context.scene.render.resolution_x = 320
    context.scene.render.resolution_y = 240
    context.scene.frame_set(context.scene.frame_start)
    context.scene.camera = camObj


# action data leftovers
def getActorCueObjects(scene: Scene, cueObj: Object):
    cueList: list[Object] = [
        obj
        for obj in scene.objects
        if obj.ootEmptyType == "CS Actor Cue"
        and obj.parent.ootEmptyType == "CS Actor Cue List"
        and obj.parent == cueObj
    ]
    cueList.sort(key=lambda o: o.ootCSMotionProperty.actorCueProp.cueStartFrame)
    return cueList


def getActorCueListObjects(scene: Scene, csObj: Object, actorid: int):
    cueObjects: list[Object] = []

    for obj in scene.objects:
        if (
            obj.ootEmptyType == "CS Actor Cue List"
            and obj.parent.ootEmptyType == "Cutscene"
            and obj.parent == csObj
            and (actorid is None or obj.ootCSMotionProperty.actorCueListProp.actorCueSlot == actorid)
        ):
            cueObjects.append(obj)

    points = getActorCueObjects(scene, obj)

    cueObjects.sort(
        key=lambda o: 1000000 if len(points) < 2 else points[0].ootCSMotionProperty.actorCueProp.cueStartFrame
    )
    return cueObjects


def createActorCue(context: Context, actorCueObj: Object, selectObj: bool, pos, startFrame: int, action_id: str):
    newCue = createNewObject(context, "ActorCue.001", None, selectObj)
    newCue.parent = actorCueObj
    newCue.empty_display_type = "ARROWS"
    newCue.location = pos
    newCue.rotation_mode = "XZY"
    newCue.ootCSMotionProperty.actorCueProp.cueStartFrame = startFrame
    newCue.ootCSMotionProperty.actorCueProp.cueActionID = action_id
    newCue.ootEmptyType = f"CS {'Player' if 'Player' in actorCueObj.ootEmptyType else 'Actor'} Cue"

    return newCue


def createActorCueList(context: Context, actor_id: int, csObj: Object):
    actorCueObj = createNewObject(context, f"ActorCueList.{getActorName(actor_id)}.001", None, True)
    actorCueObj.parent = csObj
    actorCueObj.ootCSMotionProperty.actorCueListProp.actorCueSlot = actor_id
    actorCueObj.ootEmptyType = f"CS {'Player' if actor_id == -1 else 'Actor'} Cue List"

    if actor_id > -1:
        actorCueObj.ootCSMotionProperty.actorCueListProp.commandType = ootEnumCSActorCueListCommandType[actor_id][0]

    return actorCueObj
