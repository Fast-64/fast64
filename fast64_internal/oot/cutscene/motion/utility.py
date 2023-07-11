import bpy

from bpy.types import Scene, Object, Bone, Context, EditBone
from mathutils import Vector
from ....utility import yUpToZUp
from ...oot_utility import ootParseRotation


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
