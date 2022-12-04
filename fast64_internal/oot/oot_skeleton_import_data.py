import bpy, mathutils
from collections import OrderedDict
from ..utility import PluginError, raisePluginError
from .oot_utility import getStartBone, getNextBone

# Adding new rest pose entry:
# 1. Import a generic skeleton
# 2. Pose into a usable rest pose
# 3. Select skeleton, then run bpy.ops.object.oot_save_rest_pose()
# 4. Copy array data from console into an OOTSkeletonImportInfo object
#       - list of tuples, first is root position, rest are euler XYZ rotations
# 5. Add object to ootSkeletonImportDict


def applySkeletonRestPose(boneData: list[tuple[float, float, float]], armatureObj: bpy.types.Object):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    armatureObj.select_set(True)

    bpy.ops.object.mode_set(mode="POSE")

    startBoneName = getStartBone(armatureObj)
    boneStack = [startBoneName]

    index = 0
    while len(boneStack) > 0:
        bone, boneStack = getNextBone(boneStack, armatureObj)
        poseBone = armatureObj.pose.bones[bone.name]
        if index == 0:
            poseBone.location = mathutils.Vector(boneData[index])

        poseBone.rotation_mode = "XYZ"
        poseBone.rotation_euler = mathutils.Euler(boneData[index + 1])
        index += 1

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.armature_apply_w_mesh()


# Copy data from console into python file
class OOT_SaveRestPose(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.oot_save_rest_pose"
    bl_label = "Save Rest Pose"
    bl_options = {"REGISTER", "UNDO"}

    # path: bpy.props.StringProperty(name="Path", subtype="FILE_PATH")
    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        if len(context.selected_objects) == 0:
            raise PluginError("Armature not selected.")
        armatureObj = context.active_object
        if type(armatureObj.data) is not bpy.types.Armature:
            raise PluginError("Armature not selected.")

        try:
            data = "restPoseData = [\n"
            startBoneName = getStartBone(armatureObj)
            boneStack = [startBoneName]

            firstBone = True
            while len(boneStack) > 0:
                bone, boneStack = getNextBone(boneStack, armatureObj)
                poseBone = armatureObj.pose.bones[bone.name]
                if firstBone:
                    data += str(poseBone.matrix_basis.decompose()[0][:]) + ", "
                    firstBone = False
                data += str((poseBone.matrix_basis.decompose()[1]).to_euler()[:]) + ", "

            data += "\n]"

            print(data)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


# Link overlay will be "", since link texture array data is handled as a special case.
class OOTSkeletonImportInfo:
    def __init__(
        self,
        skeletonName: str,
        folderName: str,
        actorOverlayName: str,
        flipbookArrayIndex2D: int | None,
        restPoseData: list[tuple[float, float, float]] | None,
    ):
        self.skeletonName = skeletonName
        self.folderName = folderName
        self.actorOverlayName = actorOverlayName  # Note that overlayName = None will disable texture array reading.
        self.flipbookArrayIndex2D = flipbookArrayIndex2D
        self.isLink = skeletonName == "gLinkAdultSkel" or skeletonName == "gLinkChildSkel"
        self.restPoseData = restPoseData


ootSkeletonImportDict = OrderedDict(
    {
        "Adult Link": OOTSkeletonImportInfo(
            "gLinkAdultSkel",
            "object_link_boy",
            "",
            0,
            [
                (0.0, 3.6050000190734863, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
        "Child Link": OOTSkeletonImportInfo(
            "gLinkChildSkel",
            "object_link_child",
            "",
            1,
            [
                (0.0, 2.3559017181396484, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
        # "Gerudo": OOTSkeletonImportInfo("gGerudoRedSkel", "object_geldb", "ovl_En_GeldB", None, None),
    }
)

ootEnumSkeletonImportMode = [
    ("Generic", "Generic", "Generic"),
]

for name, info in ootSkeletonImportDict.items():
    ootEnumSkeletonImportMode.append((name, name, name))
