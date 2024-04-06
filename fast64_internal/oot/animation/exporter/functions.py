import math
import mathutils
import bpy
from ....utility import PluginError, toAlnum
from ...skeleton.exporter import ootConvertArmatureToSkeletonWithoutMesh
from .classes import OOTAnimation, OOTLinkAnimation

from ....utility_anim import (
    ValueFrameData,
    saveTranslationFrame,
    saveQuaternionFrame,
    squashFramesIfAllSame,
    getFrameInterval,
    stashActionInArmature,
)

from ...oot_utility import (
    checkForStartBone,
    getStartBone,
    getSortedChildren,
)


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
