import mathutils
import bpy
import re
import math

from bpy.types import Object
from pathlib import Path

from ....utility import PluginError, hexOrDecInt, get_include_data, removeComments
from ....f3d.f3d_parser import getImportData
from ...model_classes import ootGetIncludedAssetData

from ....utility_anim import (
    getTranslationRelativeToRest,
    getRotationRelativeToRest,
    stashActionInArmature,
    create_basic_action,
    get_fcurves,
    create_new_fcurve,
)

from ...utility import (
    getStartBone,
    getNextBone,
)


def ootTranslationValue(value, actorScale):
    return value / actorScale


def binangToRadians(value):
    return math.radians(value * 360 / (2**16))


def getFrameData(filepath: Path, animData: str, frameDataName: str):
    matchResult = re.search(re.escape(frameDataName) + r"\s*\[.*?\]\s*=\s*\{([^\}]*)\}", animData, re.DOTALL)
    if matchResult is None:
        raise PluginError(f"Cannot find animation frame data named {frameDataName} in {filepath}")
    data = matchResult.group(1)

    if "#include" in data:
        data = get_include_data(data, strip=True)

    # split array into values as strings
    frameData_str = [value_stripped for value in data.split(",") if (value_stripped := value.strip()) != ""]
    # convert string values to int
    frameData_int = [int(value, 16) for value in frameData_str]
    # apply 2's complement to cast each value to s16
    frameData = [value if value < 0x8000 else value - 0x10000 for value in frameData_int]

    return frameData


def getJointIndices(filepath: Path, animData: str, jointIndicesName: str):
    matchResult = re.search(re.escape(jointIndicesName) + r"\s*\[\s*[0-9]*\s*\]\s*=\s*\{([^;]*);", animData, re.DOTALL)
    if matchResult is None:
        raise PluginError(f"Cannot find animation joint indices data named {jointIndicesName} in {filepath}")
    data = matchResult.group(1)

    if "#include" in data:
        data = get_include_data(data.removesuffix("}"), strip=True)

    jointIndicesData = [
        [hexOrDecInt(match.group(i)) for i in range(1, 4)]
        for match in re.finditer(r"\{([^,\}]*),([^,\}]*),([^,\}]*)\s*,?\s*\}", data, re.DOTALL)
    ]

    return jointIndicesData


def ootImportNonLinkAnimationC(
    armatureObj: Object, filepath: Path, animName: str, actorScale: float, isCustomImport: bool
):
    animData = getImportData([filepath])
    if not isCustomImport:
        basePath = bpy.context.scene.fast64.oot.get_decomp_path()
        animData = ootGetIncludedAssetData(basePath, [filepath], animData) + animData

    matchResult = re.search(re.escape(animName) + r"\s*=\s*\{(.*?)\}\s*;", animData, re.DOTALL | re.MULTILINE)

    if matchResult is None:
        raise PluginError(f"Cannot find definition named {animName} in {filepath}")

    if "#include" in matchResult.group(1):
        anim_data = removeComments(get_include_data(matchResult.group(1))).replace("\n", "").replace(" ", "")
        regex = r"\{(.*?),?\},(.*?),(.*?),(.*?),"
    else:
        anim_data = animData
        regex = (
            re.escape(animName)
            + r"\s*=\s*\{\s*\{\s*([^,\s]*)\s*\}*\s*,\s*([^,\s]*)\s*,\s*([^,\s]*)\s*,\s*([^,\s]*)\s*\}\s*;"
        )

    matchResult = re.search(
        regex,
        anim_data,
    )
    if matchResult is None:
        raise PluginError(f"Cannot find animation named {animName} in {filepath}")
    frameCount = hexOrDecInt(matchResult.group(1).strip())
    frameDataName = matchResult.group(2).strip()
    jointIndicesName = matchResult.group(3).strip()
    staticIndexMax = hexOrDecInt(matchResult.group(4).strip())

    frameData = getFrameData(filepath, animData, frameDataName)
    jointIndices = getJointIndices(filepath, animData, jointIndicesName)

    # print(frameDataName + " " + jointIndicesName)
    # print(str(frameData) + "\n" + str(jointIndices))

    bpy.context.scene.frame_end = frameCount
    anim, slot = create_basic_action(armatureObj, animName)
    anim_fcurves = get_fcurves(anim, slot)

    startBoneName = getStartBone(armatureObj)
    boneStack = [startBoneName]

    isRootTranslation = True
    # boneFrameData = [[x keyframes], [y keyframes], [z keyframes]]
    # len(armatureFrameData) should be = number of bones
    # property index = 0,1,2 (aka x,y,z)
    for jointIndex in jointIndices:
        if isRootTranslation:
            fcurves = [
                create_new_fcurve(
                    anim_fcurves,
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
                create_new_fcurve(
                    anim_fcurves,
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
    armatureObj: Object,
    animHeaderFilepath: Path,
    animFilepath: Path,
    animHeaderName: str,
    actorScale: float,
    numLimbs: int,
    isCustomImport: bool,
):
    header_data = getImportData([animFilepath.with_suffix(".h")])
    animHeaderData = getImportData([animHeaderFilepath])
    animData = getImportData([animFilepath])
    if not isCustomImport:
        basePath = bpy.context.scene.fast64.oot.get_decomp_path()
        animHeaderData = ootGetIncludedAssetData(basePath, [animHeaderFilepath], animHeaderData) + animHeaderData
        animData = ootGetIncludedAssetData(basePath, [animFilepath], animData) + animData

    matchResult = re.search(
        re.escape(animHeaderName) + r"\s*=\s*\{(.*?)\}\s*;", animHeaderData, re.DOTALL | re.MULTILINE
    )

    if matchResult is None:
        raise PluginError(f"Cannot find definition named {animHeaderName} in {animHeaderFilepath}")

    if "#include" in matchResult.group(1):
        anim_data = removeComments(get_include_data(matchResult.group(1))).replace("\n", "").replace(" ", "")
        regex = r"\{\s*([^,\s]*)\s*,?\}\s*,\s*([^,\s]*)"
    else:
        anim_data = animHeaderData
        regex = re.escape(animHeaderName) + r"\s*=\s*\{\s*\{\s*([^,\s]*)\s*\}\s*,\s*([^,\s]*)\s*\}\s*;"

    matchResult = re.search(
        regex,
        anim_data,
    )
    if matchResult is None:
        raise PluginError(f"Cannot find animation named {animHeaderName} in {animHeaderFilepath}")

    frame_count_raw = matchResult.group(1).strip()

    if "FRAMECOUNT_" in frame_count_raw:
        frame_count = re.search(rf"define\s*{frame_count_raw}\s*([0-9\-]*)", header_data, re.DOTALL)
        assert frame_count is not None
        frameCount = hexOrDecInt(frame_count.group(1))
    else:
        frameCount = hexOrDecInt(frame_count_raw)
    frameDataName = matchResult.group(2).strip()

    frameData = getFrameData(animFilepath, animData, frameDataName)
    print(f"{frameDataName}: {frameCount} frames, {len(frameData)} values.")

    bpy.context.scene.frame_end = frameCount
    anim, slot = create_basic_action(armatureObj, animHeaderName)
    anim_fcurves = get_fcurves(anim, slot)

    # get ordered list of bone names
    # create animation curves for each bone
    startBoneName = getStartBone(armatureObj)
    boneList = []
    boneCurvesRotation = []
    boneCurveTranslation = None
    boneStack = [startBoneName]

    eyesCurve = create_new_fcurve(
        anim_fcurves,
        data_path="ootLinkTextureAnim.eyes",
        action_group="Texture Animations",
    )
    mouthCurve = create_new_fcurve(
        anim_fcurves,
        data_path="ootLinkTextureAnim.mouth",
        action_group="Texture Animations",
    )

    # create all necessary fcurves
    while len(boneStack) > 0:
        bone, boneStack = getNextBone(boneStack, armatureObj)
        boneList.append(bone)

        if boneCurveTranslation is None:
            boneCurveTranslation = [
                create_new_fcurve(
                    anim_fcurves,
                    data_path='pose.bones["' + bone.name + '"].location',
                    index=propertyIndex,
                    action_group=startBoneName,
                )
                for propertyIndex in range(3)
            ]

        boneCurvesRotation.append(
            [
                create_new_fcurve(
                    anim_fcurves,
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
