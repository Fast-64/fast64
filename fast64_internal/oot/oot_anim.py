import math, mathutils, bpy, re
from ..utility import CData, PluginError, toAlnum, hexOrDecInt
from ..f3d.f3d_parser import getImportData
from .skeleton.exporter import ootConvertArmatureToSkeletonWithoutMesh
from .oot_model_classes import ootGetIncludedAssetData

from ..utility_anim import (
    ValueFrameData,
    saveTranslationFrame,
    saveQuaternionFrame,
    squashFramesIfAllSame,
    getFrameInterval,
    getTranslationRelativeToRest,
    getRotationRelativeToRest,
    stashActionInArmature,
)

from .oot_utility import (
    checkForStartBone,
    getStartBone,
    getNextBone,
    getSortedChildren,
)


def convertToUnsignedShort(value: int) -> int:
    return int.from_bytes(value.to_bytes(2, "big", signed=(value < 0)), "big", signed=False)


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
            data.source += format(convertToUnsignedShort(value), "#06x") + ", "
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
                data.source += (
                    format(
                        convertToUnsignedShort(self.indices[index][field]),
                        "#06x",
                    )
                    + ", "
                )
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


class OOTLinkAnimation:
    def __init__(self, name):
        self.headerName = toAlnum(name)
        self.frameCount = None
        self.data = []

    def dataName(self):
        return self.headerName + "Data"

    def toC(self, isCustomExport: bool):
        data = CData()
        animHeaderData = CData()

        data.source += '#include "ultra64.h"\n#include "global.h"\n\n'
        animHeaderData.source += '#include "ultra64.h"\n#include "global.h"\n\n'

        # TODO: handle custom import?
        if isCustomExport:
            animHeaderData.source += f'#include "{self.dataName()}.h"\n'
        else:
            animHeaderData.source += f'#include "assets/misc/link_animetion/{self.dataName()}.h"\n'

        # data
        data.header += f"extern s16 {self.dataName()}[];\n"
        data.source += f"s16 {self.dataName()}[] = {{\n"
        counter = 0
        for value in self.data:
            if counter == 0:
                data.source += "\t"
            data.source += format(convertToUnsignedShort(value), "#06x") + ", "
            counter += 1
            if counter >= 8:  # round number for finding/counting data
                counter = 0
                data.source += "\n"
        data.source += "\n};\n\n"

        # header
        animHeaderData.header += f"extern LinkAnimationHeader {self.headerName};\n"
        animHeaderData.source += (
            f"LinkAnimationHeader {self.headerName} = {{\n\t{{ {str(self.frameCount)} }}, {self.dataName()} \n}};\n\n"
        )

        return data, animHeaderData


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


def ootConvertNonLinkAnimationData(anim, armatureObj, convertTransformMatrix, *, frame_start, frame_count):
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
    # boneIndex is index in animBones.
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


def ootConvertLinkAnimationData(anim, armatureObj, convertTransformMatrix, *, frame_start, frame_count):
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
    # boneIndex is index in animBones.
    # since we are processing the bones in the same order as ootProcessBone,
    # they should be the same as the limb indices.

    frameData = []

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

        for i in range(3):
            frameData.append(min(int(round(translation[i])), 2**16 - 1))

        for boneIndex in range(len(animBones)):
            boneName = animBones[boneIndex]
            currentBone = armatureObj.data.bones[boneName]
            currentPoseBone = armatureObj.pose.bones[boneName]

            rotation = ootGetAnimBoneRot(currentBone, currentPoseBone, convertTransformMatrix, boneIndex == 0)
            for i in range(3):
                field = rotation.to_euler()[i]
                value = (math.degrees(field) % 360) / 360
                frameData.append(min(int(round(value * (2**16 - 1))), 2**16 - 1))

        textureAnimValue = (armatureObj.ootLinkTextureAnim.eyes & 0xF) | (
            (armatureObj.ootLinkTextureAnim.mouth & 0xF) << 4
        )
        frameData.append(textureAnimValue)

    bpy.context.scene.frame_set(currentFrame)
    return frameData


def ootExportNonLinkAnimation(armatureObj, convertTransformMatrix, skeletonName):
    if armatureObj.animation_data is None or armatureObj.animation_data.action is None:
        raise PluginError("No active animation selected.")
    
    anim = armatureObj.animation_data.action
    stashActionInArmature(armatureObj, anim)

    ootAnim = OOTAnimation(toAlnum(skeletonName + anim.name.capitalize() + "Anim"))

    skeleton = ootConvertArmatureToSkeletonWithoutMesh(armatureObj, convertTransformMatrix, skeletonName)

    frame_start, frame_last = getFrameInterval(anim)
    ootAnim.frameCount = frame_last - frame_start + 1

    armatureFrameData = ootConvertNonLinkAnimationData(
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


def ootExportLinkAnimation(armatureObj, convertTransformMatrix, skeletonName):
    if armatureObj.animation_data is None or armatureObj.animation_data.action is None:
        raise PluginError("No active animation selected.")

    anim = armatureObj.animation_data.action
    stashActionInArmature(armatureObj, anim)

    ootAnim = OOTLinkAnimation(toAlnum(skeletonName + anim.name.capitalize() + "Anim"))

    frame_start, frame_last = getFrameInterval(anim)
    ootAnim.frameCount = frame_last - frame_start + 1

    ootAnim.data = ootConvertLinkAnimationData(
        anim,
        armatureObj,
        convertTransformMatrix,
        frame_start=frame_start,
        frame_count=(frame_last - frame_start + 1),
    )

    return ootAnim


def ootImportNonLinkAnimationC(armatureObj, filepath, animName, actorScale, isCustomImport: bool):
    animData = getImportData([filepath])
    if not isCustomImport:
        basePath = bpy.path.abspath(bpy.context.scene.ootDecompPath)
        animData = ootGetIncludedAssetData(basePath, [filepath], animData) + animData

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
            fcurves = [
                anim.fcurves.new(
                    data_path='pose.bones["' + startBoneName + '"].location',
                    index=propertyIndex,
                    action_group=startBoneName,
                )
                for propertyIndex in range(3)
            ]
            for frame in range(frameCount):
                rawTranslation = mathutils.Vector((0, 0, 0))
                for propertyIndex in range(3):

                    if jointIndex[propertyIndex] < staticIndexMax:
                        value = ootTranslationValue(frameData[jointIndex[propertyIndex]], actorScale)
                    else:
                        value = ootTranslationValue(frameData[jointIndex[propertyIndex] + frame], actorScale)

                    rawTranslation[propertyIndex] = value

                trueTranslation = getTranslationRelativeToRest(armatureObj.data.bones[startBoneName], rawTranslation)

                for propertyIndex in range(3):
                    fcurves[propertyIndex].keyframe_points.insert(frame, trueTranslation[propertyIndex])

            isRootTranslation = False
        else:
            # WARNING: This assumes the order bones are processed are in alphabetical order.
            # If this changes in the future, then this won't work.
            bone, boneStack = getNextBone(boneStack, armatureObj)

            fcurves = [
                anim.fcurves.new(
                    data_path='pose.bones["' + bone.name + '"].rotation_euler',
                    index=propertyIndex,
                    action_group=bone.name,
                )
                for propertyIndex in range(3)
            ]

            for frame in range(frameCount):
                rawRotation = mathutils.Euler((0, 0, 0), "XYZ")
                for propertyIndex in range(3):
                    if jointIndex[propertyIndex] < staticIndexMax:
                        value = binangToRadians(frameData[jointIndex[propertyIndex]])
                    else:
                        value = binangToRadians(frameData[jointIndex[propertyIndex] + frame])

                    rawRotation[propertyIndex] = value

                trueRotation = getRotationRelativeToRest(bone, rawRotation)

                for propertyIndex in range(3):
                    fcurves[propertyIndex].keyframe_points.insert(frame, trueRotation[propertyIndex])

    if armatureObj.animation_data is None:
        armatureObj.animation_data_create()

    stashActionInArmature(armatureObj, anim)
    armatureObj.animation_data.action = anim


# filepath is gameplay_keep.c
# animName is header name.
# numLimbs = 21 for link.
def ootImportLinkAnimationC(
    armatureObj: bpy.types.Object,
    animHeaderFilepath: str,
    animFilepath: str,
    animHeaderName: str,
    actorScale: float,
    numLimbs: int,
    isCustomImport: bool,
):
    animHeaderData = getImportData([animHeaderFilepath])
    animData = getImportData([animFilepath])
    if not isCustomImport:
        basePath = bpy.path.abspath(bpy.context.scene.ootDecompPath)
        animHeaderData = ootGetIncludedAssetData(basePath, [animHeaderFilepath], animHeaderData) + animHeaderData
        animData = ootGetIncludedAssetData(basePath, [animFilepath], animData) + animData

    matchResult = re.search(
        re.escape(animHeaderName) + "\s*=\s*\{\s*\{\s*([^,\s]*)\s*\}\s*,\s*([^,\s]*)\s*\}\s*;",
        animHeaderData,
    )
    if matchResult is None:
        raise PluginError("Cannot find animation named " + animHeaderName + " in " + animHeaderFilepath)
    frameCount = hexOrDecInt(matchResult.group(1).strip())
    frameDataName = matchResult.group(2).strip()

    frameData = getFrameData(animFilepath, animData, frameDataName)
    print(f"{frameDataName}: {frameCount} frames, {len(frameData)} values.")

    bpy.context.scene.frame_end = frameCount
    anim = bpy.data.actions.new(animHeaderName)

    # get ordered list of bone names
    # create animation curves for each bone
    startBoneName = getStartBone(armatureObj)
    boneList = []
    boneCurvesRotation = []
    boneCurveTranslation = None
    boneStack = [startBoneName]

    eyesCurve = anim.fcurves.new(
        data_path="ootLinkTextureAnim.eyes",
        action_group="Texture Animations",
    )
    mouthCurve = anim.fcurves.new(
        data_path="ootLinkTextureAnim.mouth",
        action_group="Texture Animations",
    )

    # create all necessary fcurves
    while len(boneStack) > 0:
        bone, boneStack = getNextBone(boneStack, armatureObj)
        boneList.append(bone)

        if boneCurveTranslation is None:
            boneCurveTranslation = [
                anim.fcurves.new(
                    data_path='pose.bones["' + bone.name + '"].location',
                    index=propertyIndex,
                    action_group=startBoneName,
                )
                for propertyIndex in range(3)
            ]

        boneCurvesRotation.append(
            [
                anim.fcurves.new(
                    data_path='pose.bones["' + bone.name + '"].rotation_euler',
                    index=propertyIndex,
                    action_group=bone.name,
                )
                for propertyIndex in range(3)
            ]
        )

    # vec3 = 3x s16 values
    # padding = u8, tex anim = u8
    # root trans vec3 + rot vec3 for each limb + (s16 with eye/mouth indices)
    frameSize = 3 + 3 * numLimbs + 1
    for frame in range(frameCount):
        currentFrame = frameData[frame * frameSize : (frame + 1) * frameSize]
        if len(currentFrame) < frameSize:
            raise PluginError(
                f"{frameDataName} has malformed data. Framesize = {frameSize}, CurrentFrame = {len(currentFrame)}"
            )

        translation = getTranslationRelativeToRest(
            boneList[0], mathutils.Vector([ootTranslationValue(currentFrame[i], actorScale) for i in range(3)])
        )

        for i in range(3):
            boneCurveTranslation[i].keyframe_points.insert(frame, translation[i])

        for boneIndex in range(numLimbs):
            bone = boneList[boneIndex]
            rawRotation = mathutils.Euler(
                [binangToRadians(currentFrame[i + (boneIndex + 1) * 3]) for i in range(3)], "XYZ"
            )
            trueRotation = getRotationRelativeToRest(bone, rawRotation)
            for i in range(3):
                boneCurvesRotation[boneIndex][i].keyframe_points.insert(frame, trueRotation[i])

        # convert to unsigned short representation
        texAnimValue = int.from_bytes(
            currentFrame[(numLimbs + 1) * 3].to_bytes(2, "big", signed=True), "big", signed=False
        )
        eyesValue = texAnimValue & 0xF
        mouthValue = texAnimValue >> 4 & 0xF

        eyesCurve.keyframe_points.insert(frame, eyesValue).interpolation = "CONSTANT"
        mouthCurve.keyframe_points.insert(frame, mouthValue).interpolation = "CONSTANT"

    if armatureObj.animation_data is None:
        armatureObj.animation_data_create()

    stashActionInArmature(armatureObj, anim)
    armatureObj.animation_data.action = anim


def ootTranslationValue(value, actorScale):
    return value / actorScale


def binangToRadians(value):
    return math.radians(value * 360 / (2**16))


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
