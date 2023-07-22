import bpy

from bpy.types import Object, Bone, Context, EditBone, Armature
from mathutils import Vector
from ....utility import yUpToZUp
from ...oot_utility import ootParseRotation


class BoneData:
    def __init__(self, shotObj: Object, bone: Bone):
        editBone = self.getEditBoneFromBone(shotObj, bone) if shotObj.mode == "EDIT" else None
        self.name = bone.name
        self.head = editBone.head if editBone is not None else bone.head
        self.tail = editBone.tail if editBone is not None else bone.tail

        self.frame = (
            editBone["shotPointFrame"]
            if editBone is not None and "shotPointFrame" in editBone
            else bone.ootCamShotPointProp.shotPointFrame
        )

        self.viewAngle = (
            editBone["shotPointViewAngle"]
            if editBone is not None and "shotPointViewAngle" in editBone
            else bone.ootCamShotPointProp.shotPointViewAngle
        )

        self.roll = (
            editBone["shotPointRoll"]
            if editBone is not None and "shotPointRoll" in editBone
            else bone.ootCamShotPointProp.shotPointRoll
        )

    def getEditBoneFromBone(self, shotObj: Object, bone: Bone) -> EditBone | Bone:
        for editBone in shotObj.data.edit_bones:
            if editBone.name == bone.name:
                return editBone
        else:
            print("Could not find corresponding bone")
            return bone


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


def createNewCameraShot(csObj: Object):
    from .io_classes import OOTCSMotionObjectFactory  # circular import fix

    index, csPrefix = getNameInformations(csObj, "Camera Shot", None)

    # create a basic armature
    name = f"{csPrefix}.Camera Shot {index:02}"
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


def getCSMotionValidateObj(csObj: Object, obj: Object, target: str):
    """Checks if the given object belong to CS Motion and return it if true"""

    if csObj is not None and obj.parent != csObj:
        return None

    if obj is None:
        obj = bpy.context.view_layer.objects.active

    if target is None or target != "Camera Shot":
        nonListTypes = ["CS Player Cue", "CS Actor Cue", "CS Dummy Cue", "Cutscene"]
        listTypes = ["CS Player Cue List", "CS Actor Cue List"]

        if obj.type == "EMPTY" and obj.ootEmptyType in nonListTypes or obj.ootEmptyType in listTypes:
            return obj
    elif target is not None and target == "Camera Shot":
        # get the camera shot
        parentObj = obj.parent
        if obj.type == "ARMATURE" and parentObj is not None and parentObj.type == "EMPTY":
            return obj

    return None


def getNameInformations(csObj: Object, target: str, index: int):
    idx = csPrefix = None
    csNbr = 0

    # get the last target objects names
    if csObj.children is not None:
        for obj in csObj.children:
            if obj.type == "EMPTY" and "Cue List" in obj.name or "Camera Shot" in obj.name or target in obj.name:
                csPrefix = obj.name.split(".")[0]
                if target in obj.name:
                    idx = int(obj.name.split(" ")[-1]) + 1

    # saving the cutscene number if the target objects can't be found
    if csPrefix is None:
        for obj in bpy.data.objects:
            if obj.type == "EMPTY" and obj.ootEmptyType == "Cutscene":
                csNbr += 1

            if obj.name == csObj.name:
                break

        csPrefix = f"CS_{csNbr:02}"

    if idx is None:
        idx = 1

    if index is not None:
        idx = index

    return idx, csPrefix


def metersToBlend(context: Context, value: float):
    return value * 56.0 / context.scene.ootBlenderScale


def setupActorCuePreview(csObj: Object, actorOrPlayer: str, selectObject: bool, cueList: Object):
    from .io_classes import OOTCSMotionObjectFactory  # circular import fix

    # check if the cue actually moves, if not it's not necessary to create a preview object
    shouldContinue = False
    for i in range(len(cueList.children) - 1):
        actorCue = cueList.children[i]
        nextCue = cueList.children[i + 1]
        curPos = [round(pos) for pos in actorCue.location]
        nextPos = [round(pos) for pos in nextCue.location]
        if curPos != nextPos:
            shouldContinue = True
            break

    if shouldContinue:
        index, csPrefix = getNameInformations(csObj, "Preview", int(cueList.name.split(" ")[-1]))
        name = f"{csPrefix}.{actorOrPlayer} Cue Preview {index:02}"

        for obj in csObj.children:
            if obj.name == name:
                previewObj = obj
                break
        else:
            previewObj = OOTCSMotionObjectFactory().getNewActorCuePreviewObject(name, selectObject, csObj)

        actorHeight = 1.5
        if actorOrPlayer == "Player":
            actorHeight = 1.7 if bpy.context.scene.previewPlayerAge == "link_adult" else 1.3

        previewObj.empty_display_type = "SINGLE_ARROW"
        previewObj.empty_display_size = metersToBlend(bpy.context, actorHeight)
        previewObj.ootCSMotionProperty.actorCueListProp.cueListToPreview = cueList


def getCameraShotBoneData(shotObj: Object, runChecks: bool):
    boneDataList: list[BoneData] = []
    for bone in shotObj.data.bones:
        if bone.parent is not None:
            print("Camera armature bones are not allowed to have parent bones")
            return None
        boneDataList.append(BoneData(shotObj, bone))
    boneDataList.sort(key=lambda b: b.name)

    if runChecks:
        if boneDataList is None:
            raise RuntimeError("Error in bone properties")

        if len(boneDataList) < 4:
            raise RuntimeError(f"Only {len(boneDataList)} bones in `{shotObj.name}`")

    return boneDataList


def getCutsceneEndFrame(csObj: Object):
    shotObjects: list[Object] = []
    for childObj in csObj.children:
        obj = getCSMotionValidateObj(csObj, childObj, "Camera Shot")
        if obj is not None:
            shotObjects.append(obj)
    shotObjects.sort(key=lambda obj: obj.name)

    csEndFrame = -1
    for shotObj in shotObjects:
        # Seems to be the algorithm which was used in the canon tool: the at list
        # counts the extra point (same frames as the last real point), and the pos
        # list doesn't count the extra point but adds 1. Of course, neither of these
        # values is actually the number of frames the camera motion lasts for.
        boneDataList = getCameraShotBoneData(shotObj, True)
        endFrame = shotObj.data.ootCamShotProp.shotStartFrame + max(2, sum(b.frame for b in boneDataList)) + 2
        csEndFrame = max(csEndFrame, endFrame)
    return csEndFrame
    
def setupCutscene(csObj: Object):
    from .io_classes import OOTCSMotionObjectFactory  # circular import fix

    # lock cutscene coordinates and reset location/rotation/scale
    csObj.lock_location = csObj.lock_rotation = csObj.lock_scale = [True, True, True]
    csObj.location = csObj.rotation_euler = [0.0, 0.0, 0.0]
    csObj.scale = [1.0, 1.0, 1.0]

    objFactory = OOTCSMotionObjectFactory()
    context = bpy.context
    bpy.context.scene.ootCSPreviewCSObj = csObj
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
        if obj.ootEmptyType in ["CS Actor Cue List", "CS Player Cue List"]:
            setupActorCuePreview(csObj, "Actor" if "Actor" in obj.ootEmptyType else "Player", False, obj)

    # Other setup
    context.scene.frame_start = 0
    context.scene.frame_end = max(getCutsceneEndFrame(csObj), context.scene.frame_end)
    context.scene.render.fps = 20
    context.scene.render.resolution_x = 320
    context.scene.render.resolution_y = 240
    context.scene.frame_set(context.scene.frame_start)
    context.scene.camera = camObj
