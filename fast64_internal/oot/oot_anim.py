import math, mathutils, bpy, os, re
from .oot_skeleton import ootConvertArmatureToSkeletonWithoutMesh
from ..utility import CData, PluginError, toAlnum, writeCData, readFile, hexOrDecInt

from .oot_utility import (
    checkForStartBone,
    getStartBone,
    getSortedChildren,
    ootGetPath,
    addIncludeFiles,
    checkEmptyName,
)

from ..utility_anim import (
    ValueFrameData,
    saveTranslationFrame,
    saveQuaternionFrame,
    squashFramesIfAllSame,
    getFrameInterval,
)


class OOTAnimation:
    def __init__(self, name):
        self.name = toAlnum(name)
        self.segmentID = None
        self.indices = {}
        self.values = []
        self.frameCount = None
        self.limit = None

    def valuesName(self):
        return self.name + "FrameData"

    def indicesName(self):
        return self.name + "JointIndices"

    def toC(self):
        data = CData()
        data.source += '#include "ultra64.h"\n#include "global.h"\n\n'

        # values
        data.source += "s16 " + self.valuesName() + "[" + str(len(self.values)) + "] = {\n"
        counter = 0
        for value in self.values:
            if counter == 0:
                data.source += "\t"
            data.source += format(value, "#06x") + ", "
            counter += 1
            if counter >= 16:  # round number for finding/counting data
                counter = 0
                data.source += "\n"
        data.source += "};\n\n"

        # indices (index -1 => translation)
        data.source += "JointIndex " + self.indicesName() + "[" + str(len(self.indices)) + "] = {\n"
        for index in range(-1, len(self.indices) - 1):
            data.source += "\t{ "
            for field in range(3):
                data.source += format(self.indices[index][field], "#06x") + ", "
            data.source += "},\n"
        data.source += "};\n\n"

        # header
        data.header += "extern AnimationHeader " + self.name + ";\n"
        data.source += (
            "AnimationHeader "
            + self.name
            + " = { { "
            + str(self.frameCount)
            + " }, "
            + self.valuesName()
            + ", "
            + self.indicesName()
            + ", "
            + str(self.limit)
            + " };\n\n"
        )

        return data


def ootGetAnimBoneRot(bone, poseBone, convertTransformMatrix, isRoot):
    # OoT draws limbs like this:
    # limbMatrix = parentLimbMatrix @ limbFixedTranslationMatrix @ animRotMatrix
    # There is no separate rest position rotation; an animation rotation of 0
    # in all three axes simply means draw the dlist as it is (assuming no
    # parent or translation).
    # We could encode a rest position into the dlists at export time, but the
    # vanilla skeletons don't do this, instead they seem to usually have each
    # dlist along its bone. For example, a forearm limb would normally be
    # modeled along a forearm bone, so when the bone is set to 0 rotation
    # (sticking up), the forearm mesh also sticks up.
    #
    # poseBone.matrix is the final bone matrix in object space after constraints
    # and drivers, which is ultimately the transformation we want to encode.
    # bone.matrix_local is the edit-mode bone matrix in object space,
    # effectively the rest position.
    # Limbs are exported with a transformation of bone.matrix_local.inverted()
    # (in TriangleConverterInfo.getTransformMatrix).
    # To directly put the limb back to its rest position, apply bone.matrix_local.
    # Similarly, to directly put the limb into its pose position, apply
    # poseBone.matrix. If SkelAnime saved 4x4 matrices for each bone each frame,
    # we'd simply write this matrix and that's it:
    # limbMatrix = poseBone.matrix
    # Of course it does not, so we have to "undo" the game transforms like:
    # limbMatrix = parentLimbMatrix
    #             @ limbFixedTranslationMatrix
    #             @ limbFixedTranslationMatrix.inverted()
    #             @ parentLimbMatrix.inverted()
    #             @ poseBone.matrix
    # The product of the final three is what we want to return here.
    # The translation is computed in ootProcessBone as
    # (scaleMtx @ bone.parent.matrix_local.inverted() @ bone.matrix_local).decompose()
    # (convertTransformMatrix is just the global scale and armature scale).
    # However, the translation components of parentLimbMatrix and poseBone.matrix
    # are not in the scaled (100x / 1000x / whatever), but in the normal Blender
    # space. So we don't apply this scale here.
    origTranslationMatrix = (  # convertTransformMatrix @
        bone.parent.matrix_local.inverted() if bone.parent is not None else mathutils.Matrix.Identity(4)
    ) @ bone.matrix_local
    origTranslation = origTranslationMatrix.decompose()[0]
    inverseTranslationMatrix = mathutils.Matrix.Translation(origTranslation).inverted()
    animMatrix = (
        inverseTranslationMatrix
        @ (poseBone.parent.matrix.inverted() if poseBone.parent is not None else mathutils.Matrix.Identity(4))
        @ poseBone.matrix
    )
    finalTranslation, finalRotation, finalScale = animMatrix.decompose()
    if isRoot:
        # 90 degree offset because of coordinate system difference.
        zUpToYUp = mathutils.Quaternion((1, 0, 0), math.radians(-90.0))
        finalRotation.rotate(zUpToYUp)
    # This should be very close to only a rotation, or if root, only a rotation
    # and translation.
    finalScale = [finalScale.x, finalScale.y, finalScale.z]
    if max(finalScale) >= 1.01 or min(finalScale) <= 0.99:
        raise RuntimeError("Animation contains bones with animated scale. OoT SkelAnime does not support this.")
    finalTranslation = [finalTranslation.x, finalTranslation.y, finalTranslation.z]
    if not isRoot and (max(finalTranslation) >= 1.0 or min(finalTranslation) <= -1.0):
        raise RuntimeError(
            "Animation contains non-root bones with animated translation. OoT SkelAnime only supports animated translation on the root bone."
        )
    return finalRotation


def ootConvertAnimationData(anim, armatureObj, convertTransformMatrix, *, frame_start, frame_count):
    checkForStartBone(armatureObj)
    bonesToProcess = [getStartBone(armatureObj)]
    currentBone = armatureObj.data.bones[bonesToProcess[0]]
    animBones = []

    # Get animation bones in order
    # must be SAME order as ootProcessBone
    while len(bonesToProcess) > 0:
        boneName = bonesToProcess[0]
        currentBone = armatureObj.data.bones[boneName]
        bonesToProcess = bonesToProcess[1:]

        animBones.append(boneName)

        childrenNames = getSortedChildren(armatureObj, currentBone)
        bonesToProcess = childrenNames + bonesToProcess

    # list of boneFrameData, which is [[x frames], [y frames], [z frames]]
    # boneIndex is index in animBones in ootConvertAnimationData.
    # since we are processing the bones in the same order as ootProcessBone,
    # they should be the same as the limb indices.

    # index -1 => translation
    translationData = [ValueFrameData(-1, i, []) for i in range(3)]
    rotationData = [
        [ValueFrameData(i, 0, []), ValueFrameData(i, 1, []), ValueFrameData(i, 2, [])] for i in range(len(animBones))
    ]

    currentFrame = bpy.context.scene.frame_current
    for frame in range(frame_start, frame_start + frame_count):
        bpy.context.scene.frame_set(frame)
        rootBone = armatureObj.data.bones[animBones[0]]
        rootPoseBone = armatureObj.pose.bones[animBones[0]]

        # Convert Z-up to Y-up for root translation animation
        translation = (
            mathutils.Quaternion((1, 0, 0), math.radians(-90.0))
            @ (convertTransformMatrix @ rootPoseBone.matrix).decompose()[0]
        )
        saveTranslationFrame(translationData, translation)

        for boneIndex in range(len(animBones)):
            boneName = animBones[boneIndex]
            currentBone = armatureObj.data.bones[boneName]
            currentPoseBone = armatureObj.pose.bones[boneName]

            saveQuaternionFrame(
                rotationData[boneIndex],
                ootGetAnimBoneRot(currentBone, currentPoseBone, convertTransformMatrix, boneIndex == 0),
            )

    bpy.context.scene.frame_set(currentFrame)
    squashFramesIfAllSame(translationData)
    for frameData in rotationData:
        squashFramesIfAllSame(frameData)

    # need to deepcopy?
    armatureFrameData = translationData
    for frameDataGroup in rotationData:
        for i in range(3):
            armatureFrameData.append(frameDataGroup[i])

    return armatureFrameData


def ootExportAnimationCommon(armatureObj, convertTransformMatrix, skeletonName):
    if armatureObj.animation_data is None or armatureObj.animation_data.action is None:
        raise PluginError("No active animation selected.")
    anim = armatureObj.animation_data.action
    ootAnim = OOTAnimation(toAlnum(skeletonName + anim.name.capitalize() + "Anim"))

    skeleton = ootConvertArmatureToSkeletonWithoutMesh(armatureObj, convertTransformMatrix, skeletonName)

    frame_start, frame_last = getFrameInterval(anim)
    ootAnim.frameCount = frame_last - frame_start + 1

    armatureFrameData = ootConvertAnimationData(
        anim,
        armatureObj,
        convertTransformMatrix,
        frame_start=frame_start,
        frame_count=(frame_last - frame_start + 1),
    )

    singleFrameData = []
    multiFrameData = []
    for frameData in armatureFrameData:
        if len(frameData.frames) == 1:
            singleFrameData.append(frameData)
        else:
            multiFrameData.append(frameData)

    for frameData in singleFrameData:
        frame = frameData.frames[0]
        if frameData.boneIndex not in ootAnim.indices:
            ootAnim.indices[frameData.boneIndex] = [None, None, None]
        if frame in ootAnim.values:
            ootAnim.indices[frameData.boneIndex][frameData.field] = ootAnim.values.index(frame)
        else:
            ootAnim.indices[frameData.boneIndex][frameData.field] = len(ootAnim.values)
            ootAnim.values.extend(frameData.frames)

    ootAnim.limit = len(ootAnim.values)
    for frameData in multiFrameData:
        if frameData.boneIndex not in ootAnim.indices:
            ootAnim.indices[frameData.boneIndex] = [None, None, None]
        ootAnim.indices[frameData.boneIndex][frameData.field] = len(ootAnim.values)
        ootAnim.values.extend(frameData.frames)

    return ootAnim


def exportAnimationC(armatureObj, exportPath, isCustomExport, folderName, skeletonName):
    checkEmptyName(folderName)
    checkEmptyName(skeletonName)
    convertTransformMatrix = (
        mathutils.Matrix.Scale(bpy.context.scene.ootActorBlenderScale, 4)
        @ mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()
    )
    ootAnim = ootExportAnimationCommon(armatureObj, convertTransformMatrix, skeletonName)

    ootAnimC = ootAnim.toC()
    path = ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, False)
    writeCData(ootAnimC, os.path.join(path, ootAnim.name + ".h"), os.path.join(path, ootAnim.name + ".c"))

    if not isCustomExport:
        addIncludeFiles(folderName, path, ootAnim.name)


def getNextBone(boneStack, armatureObj):
    if len(boneStack) == 0:
        raise PluginError("More bones in animation than on armature.")
    bone = armatureObj.data.bones[boneStack[0]]
    boneStack = boneStack[1:]
    boneStack = getSortedChildren(armatureObj, bone) + boneStack
    return bone, boneStack


def ootImportAnimationC(armatureObj, filepath, animName, actorScale):
    animData = readFile(filepath)

    matchResult = re.search(
        re.escape(animName)
        + "\s*=\s*\{\s*\{\s*([^,\s]*)\s*\}*\s*,\s*([^,\s]*)\s*,\s*([^,\s]*)\s*,\s*([^,\s]*)\s*\}\s*;",
        animData,
    )
    if matchResult is None:
        raise PluginError("Cannot find animation named " + animName + " in " + filepath)
    frameCount = hexOrDecInt(matchResult.group(1).strip())
    frameDataName = matchResult.group(2).strip()
    jointIndicesName = matchResult.group(3).strip()
    staticIndexMax = hexOrDecInt(matchResult.group(4).strip())

    frameData = getFrameData(filepath, animData, frameDataName)
    jointIndices = getJointIndices(filepath, animData, jointIndicesName)

    # print(frameDataName + " " + jointIndicesName)
    # print(str(frameData) + "\n" + str(jointIndices))

    bpy.context.scene.frame_end = frameCount
    anim = bpy.data.actions.new(animName)

    startBoneName = getStartBone(armatureObj)
    boneStack = [startBoneName]

    isRootTranslation = True
    # boneFrameData = [[x keyframes], [y keyframes], [z keyframes]]
    # len(armatureFrameData) should be = number of bones
    # property index = 0,1,2 (aka x,y,z)
    for jointIndex in jointIndices:
        if isRootTranslation:
            for propertyIndex in range(3):
                fcurve = anim.fcurves.new(
                    data_path='pose.bones["' + startBoneName + '"].location',
                    index=propertyIndex,
                    action_group=startBoneName,
                )
                if jointIndex[propertyIndex] < staticIndexMax:
                    value = frameData[jointIndex[propertyIndex]] / actorScale
                    fcurve.keyframe_points.insert(0, value)
                else:
                    for frame in range(frameCount):
                        value = frameData[jointIndex[propertyIndex] + frame] / actorScale
                        fcurve.keyframe_points.insert(frame, value)
            isRootTranslation = False
        else:
            # WARNING: This assumes the order bones are processed are in alphabetical order.
            # If this changes in the future, then this won't work.
            bone, boneStack = getNextBone(boneStack, armatureObj)
            for propertyIndex in range(3):
                fcurve = anim.fcurves.new(
                    data_path='pose.bones["' + bone.name + '"].rotation_euler',
                    index=propertyIndex,
                    action_group=bone.name,
                )
                if jointIndex[propertyIndex] < staticIndexMax:
                    value = math.radians(frameData[jointIndex[propertyIndex]] * 360 / (2**16))
                    fcurve.keyframe_points.insert(0, value)
                else:
                    for frame in range(frameCount):
                        value = math.radians(frameData[jointIndex[propertyIndex] + frame] * 360 / (2**16))
                        fcurve.keyframe_points.insert(frame, value)

    if armatureObj.animation_data is None:
        armatureObj.animation_data_create()
    armatureObj.animation_data.action = anim


def getFrameData(filepath, animData, frameDataName):
    matchResult = re.search(re.escape(frameDataName) + "\s*\[\s*[0-9]*\s*\]\s*=\s*\{([^\}]*)\}", animData, re.DOTALL)
    if matchResult is None:
        raise PluginError("Cannot find animation frame data named " + frameDataName + " in " + filepath)
    data = matchResult.group(1)
    frameData = [
        int.from_bytes([int(value.strip()[2:4], 16), int(value.strip()[4:6], 16)], "big", signed=True)
        for value in data.split(",")
        if value.strip() != ""
    ]

    return frameData


def getJointIndices(filepath, animData, jointIndicesName):
    matchResult = re.search(re.escape(jointIndicesName) + "\s*\[\s*[0-9]*\s*\]\s*=\s*\{([^;]*);", animData, re.DOTALL)
    if matchResult is None:
        raise PluginError("Cannot find animation joint indices data named " + jointIndicesName + " in " + filepath)
    data = matchResult.group(1)
    jointIndicesData = [
        [hexOrDecInt(match.group(i)) for i in range(1, 4)]
        for match in re.finditer("\{([^,\}]*),([^,\}]*),([^,\}]*)\s*,?\s*\}", data, re.DOTALL)
    ]

    return jointIndicesData
