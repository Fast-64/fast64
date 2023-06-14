import bpy, os, copy, shutil, mathutils, math
from bpy.utils import register_class, unregister_class
from ..panels import SM64_Panel, sm64GoalImport
from .sm64_level_parser import parseLevelAtPointer
from .sm64_rom_tweaks import ExtendBank0x04
from .sm64_geolayout_bone import animatableBoneTypes

from ..utility import (
    CData,
    PluginError,
    ValueFrameData,
    raisePluginError,
    encodeSegmentedAddr,
    decodeSegmentedAddr,
    getExportDir,
    toAlnum,
    writeIfNotFound,
    get64bitAlignedAddr,
    writeInsertableFile,
    getFrameInterval,
    findStartBones,
    saveTranslationFrame,
    saveQuaternionFrame,
    removeTrailingFrames,
    applyRotation,
    getPathAndLevel,
    applyBasicTweaks,
    checkExpanded,
    tempName,
    bytesToHex,
    prop_split,
    customExportWarning,
    decompFolderMessage,
    makeWriteInfoBox,
    writeBoxExportType,
    stashActionInArmature,
    enumExportHeaderType,
)

from .sm64_constants import (
    bank0Segment,
    insertableBinaryTypes,
    level_pointers,
    defaultExtendSegment4,
    level_enums,
    enumLevelNames,
    marioAnimations,
)

sm64_anim_types = {"ROTATE", "TRANSLATE"}


class SM64_Animation:
    def __init__(self, name):
        self.name = name
        self.header = None
        self.indices = SM64_ShortArray(name + "_indices", False)
        self.values = SM64_ShortArray(name + "_values", True)

    def get_ptr_offsets(self, isDMA):
        return [12, 16] if not isDMA else []

    def to_binary(self, segmentData, isDMA, startAddress):
        return (
            self.header.to_binary(segmentData, isDMA, startAddress) + self.indices.to_binary() + self.values.to_binary()
        )

    def to_c(self):
        data = CData()
        data.header = "extern const struct Animation *const " + self.name + "[];\n"
        data.source = self.values.to_c() + "\n" + self.indices.to_c() + "\n" + self.header.to_c() + "\n"
        return data


class SM64_ShortArray:
    def __init__(self, name, signed):
        self.name = name
        self.shortData = []
        self.signed = signed

    def to_binary(self):
        data = bytearray(0)
        for short in self.shortData:
            # All euler values have been pre-converted to positive values, so don't care about signed.
            data += short.to_bytes(2, "big", signed=False)
        return data

    def to_c(self):
        data = "static const " + ("s" if self.signed else "u") + "16 " + self.name + "[] = {\n\t"
        wrapCounter = 0
        for short in self.shortData:
            data += "0x" + format(short, "04X") + ", "
            wrapCounter += 1
            if wrapCounter > 8:
                data += "\n\t"
                wrapCounter = 0
        data += "\n};\n"
        return data


class SM64_AnimationHeader:
    def __init__(
        self,
        name,
        repetitions,
        marioYOffset,
        frameInterval,
        nodeCount,
        transformValuesStart,
        transformIndicesStart,
        animSize,
    ):
        self.name = name
        self.repetitions = repetitions
        self.marioYOffset = marioYOffset
        self.frameInterval = frameInterval
        self.nodeCount = nodeCount
        self.transformValuesStart = transformValuesStart
        self.transformIndicesStart = transformIndicesStart
        self.animSize = animSize  # DMA animations only

        self.transformIndices = []

    # presence of segmentData indicates DMA.
    def to_binary(self, segmentData, isDMA, startAddress):
        if isDMA:
            transformValuesStart = self.transformValuesStart
            transformIndicesStart = self.transformIndicesStart
        else:
            transformValuesStart = self.transformValuesStart + startAddress
            transformIndicesStart = self.transformIndicesStart + startAddress

        data = bytearray(0)
        data.extend(self.repetitions.to_bytes(2, byteorder="big"))
        data.extend(self.marioYOffset.to_bytes(2, byteorder="big"))  # y offset, only used for mario
        data.extend([0x00, 0x00])  # unknown, common with secondary anims, variable length animations?
        data.extend(int(round(self.frameInterval[0])).to_bytes(2, byteorder="big"))
        data.extend(int(round(self.frameInterval[1] - 1)).to_bytes(2, byteorder="big"))
        data.extend(self.nodeCount.to_bytes(2, byteorder="big"))
        if not isDMA:
            data.extend(encodeSegmentedAddr(transformValuesStart, segmentData))
            data.extend(encodeSegmentedAddr(transformIndicesStart, segmentData))
            data.extend(bytearray([0x00] * 6))
        else:
            data.extend(transformValuesStart.to_bytes(4, byteorder="big"))
            data.extend(transformIndicesStart.to_bytes(4, byteorder="big"))
            data.extend(self.animSize.to_bytes(4, byteorder="big"))
            data.extend(bytearray([0x00] * 2))
        return data

    def to_c(self):
        data = (
            "static const struct Animation "
            + self.name
            + " = {\n"
            + "\t"
            + str(self.repetitions)
            + ",\n"
            + "\t"
            + str(self.marioYOffset)
            + ",\n"
            + "\t0,\n"
            + "\t"
            + str(int(round(self.frameInterval[0])))
            + ",\n"
            + "\t"
            + str(int(round(self.frameInterval[1] - 1)))
            + ",\n"
            + "\tANIMINDEX_NUMPARTS("
            + self.name
            + "_indices),\n"
            + "\t"
            + self.name
            + "_values,\n"
            + "\t"
            + self.name
            + "_indices,\n"
            + "\t0,\n"
            + "};\n"
        )
        return data


class SM64_AnimIndexNode:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


class SM64_AnimIndex:
    def __init__(self, numFrames, startOffset):
        self.startOffset = startOffset
        self.numFrames = numFrames


def getLastKeyframeTime(keyframes):
    last = keyframes[0].co[0]
    for keyframe in keyframes:
        if keyframe.co[0] > last:
            last = keyframe.co[0]
    return last


# add definition to groupN.h
# add data/table includes to groupN.c (bin_id?)
# add data/table files
def exportAnimationC(armatureObj, loopAnim, dirPath, dirName, groupName, customExport, headerType, levelName):
    dirPath, texDir = getExportDir(customExport, dirPath, headerType, levelName, "", dirName)

    sm64_anim = exportAnimationCommon(armatureObj, loopAnim, dirName + "_anim")
    animName = armatureObj.animation_data.action.name

    geoDirPath = os.path.join(dirPath, toAlnum(dirName))
    if not os.path.exists(geoDirPath):
        os.mkdir(geoDirPath)

    animDirPath = os.path.join(geoDirPath, "anims")
    if not os.path.exists(animDirPath):
        os.mkdir(animDirPath)

    animsName = dirName + "_anims"
    animFileName = "anim_" + toAlnum(animName) + ".inc.c"
    animPath = os.path.join(animDirPath, animFileName)

    data = sm64_anim.to_c()
    outFile = open(animPath, "w", newline="\n")
    outFile.write(data.source)
    outFile.close()

    headerPath = os.path.join(geoDirPath, "anim_header.h")
    headerFile = open(headerPath, "w", newline="\n")
    headerFile.write("extern const struct Animation *const " + animsName + "[];\n")
    headerFile.close()

    # write to data.inc.c
    dataFilePath = os.path.join(animDirPath, "data.inc.c")
    if not os.path.exists(dataFilePath):
        dataFile = open(dataFilePath, "w", newline="\n")
        dataFile.close()
    writeIfNotFound(dataFilePath, '#include "' + animFileName + '"\n', "")

    # write to table.inc.c
    tableFilePath = os.path.join(animDirPath, "table.inc.c")

    # if table doesn´t exist, create one
    if not os.path.exists(tableFilePath):
        tableFile = open(tableFilePath, "w", newline="\n")
        tableFile.write("const struct Animation *const " + animsName + "[] = {\n\tNULL,\n};\n")
        tableFile.close()

    stringData = ""
    with open(tableFilePath, "r") as f:
        stringData = f.read()

    # if animation header isn´t already in the table then add it.
    if sm64_anim.header.name not in stringData:

        # search for the NULL value which represents the end of the table
        # (this value is not present in vanilla animation tables)
        footerIndex = stringData.rfind("\tNULL,\n")

        # if the null value cant be found, look for the end of the array
        if footerIndex == -1:
            footerIndex = stringData.rfind("};")

            # if that can´t be found then throw an error.
            if footerIndex == -1:
                raise PluginError("Animation table´s footer does not seem to exist.")

            stringData = stringData[:footerIndex] + "\tNULL,\n" + stringData[footerIndex:]

        stringData = stringData[:footerIndex] + f"\t&{sm64_anim.header.name},\n" + stringData[footerIndex:]

        with open(tableFilePath, "w") as f:
            f.write(stringData)

    if not customExport:
        if headerType == "Actor":
            groupPathC = os.path.join(dirPath, groupName + ".c")
            groupPathH = os.path.join(dirPath, groupName + ".h")

            writeIfNotFound(groupPathC, '\n#include "' + dirName + '/anims/data.inc.c"', "")
            writeIfNotFound(groupPathC, '\n#include "' + dirName + '/anims/table.inc.c"', "")
            writeIfNotFound(groupPathH, '\n#include "' + dirName + '/anim_header.h"', "#endif")
        elif headerType == "Level":
            groupPathC = os.path.join(dirPath, "leveldata.c")
            groupPathH = os.path.join(dirPath, "header.h")

            writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + "/" + dirName + '/anims/data.inc.c"', "")
            writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + "/" + dirName + '/anims/table.inc.c"', "")
            writeIfNotFound(
                groupPathH, '\n#include "levels/' + levelName + "/" + dirName + '/anim_header.h"', "\n#endif"
            )


def exportAnimationBinary(romfile, exportRange, armatureObj, DMAAddresses, segmentData, isDMA, loopAnim):

    startAddress = get64bitAlignedAddr(exportRange[0])
    sm64_anim = exportAnimationCommon(armatureObj, loopAnim, armatureObj.name)

    animData = sm64_anim.to_binary(segmentData, isDMA, startAddress)

    if startAddress + len(animData) > exportRange[1]:
        raise PluginError(
            "Size too big: Data ends at "
            + hex(startAddress + len(animData))
            + ", which is larger than the specified range."
        )

    romfile.seek(startAddress)
    romfile.write(animData)

    addrRange = (startAddress, startAddress + len(animData))

    if not isDMA:
        animTablePointer = get64bitAlignedAddr(startAddress + len(animData))
        romfile.seek(animTablePointer)
        romfile.write(encodeSegmentedAddr(startAddress, segmentData))
        return addrRange, animTablePointer
    else:
        if DMAAddresses is not None:
            romfile.seek(DMAAddresses["entry"])
            romfile.write((startAddress - DMAAddresses["start"]).to_bytes(4, byteorder="big"))
            romfile.seek(DMAAddresses["entry"] + 4)
            romfile.write(len(animData).to_bytes(4, byteorder="big"))
        return addrRange, None


def exportAnimationInsertableBinary(filepath, armatureObj, isDMA, loopAnim):
    startAddress = get64bitAlignedAddr(0)
    sm64_anim = exportAnimationCommon(armatureObj, loopAnim, armatureObj.name)
    segmentData = copy.copy(bank0Segment)

    animData = sm64_anim.to_binary(segmentData, isDMA, startAddress)

    if startAddress + len(animData) > 0xFFFFFF:
        raise PluginError(
            "Size too big: Data ends at "
            + hex(startAddress + len(animData))
            + ", which is larger than the specified range."
        )

    writeInsertableFile(
        filepath, insertableBinaryTypes["Animation"], sm64_anim.get_ptr_offsets(isDMA), startAddress, animData
    )


def exportAnimationCommon(armatureObj, loopAnim, name):
    if armatureObj.animation_data is None or armatureObj.animation_data.action is None:
        raise PluginError("No active animation selected.")

    anim = armatureObj.animation_data.action
    stashActionInArmature(armatureObj, anim)

    sm64_anim = SM64_Animation(toAlnum(name + "_" + anim.name))

    nodeCount = len(armatureObj.data.bones)

    frame_start, frame_last = getFrameInterval(anim)

    translationData, armatureFrameData = convertAnimationData(
        anim,
        armatureObj,
        frame_start=frame_start,
        frame_count=(frame_last - frame_start + 1),
    )

    repetitions = 0 if loopAnim else 1
    marioYOffset = 0x00  # ??? Seems to be this value for most animations

    transformValuesOffset = 0
    headerSize = 0x1A
    transformIndicesStart = headerSize  # 0x18 if including animSize?

    # all node rotations + root translation
    # *3 for each property (xyz) and *4 for entry size
    # each keyframe stored as 2 bytes
    # transformValuesStart = transformIndicesStart + (nodeCount + 1) * 3 * 4
    transformValuesStart = transformIndicesStart

    for translationFrameProperty in translationData:
        frameCount = len(translationFrameProperty.frames)
        sm64_anim.indices.shortData.append(frameCount)
        sm64_anim.indices.shortData.append(transformValuesOffset)
        if (transformValuesOffset) > 2**16 - 1:
            raise PluginError("Animation is too large.")
        transformValuesOffset += frameCount
        transformValuesStart += 4
        for value in translationFrameProperty.frames:
            sm64_anim.values.shortData.append(
                int.from_bytes(value.to_bytes(2, "big", signed=True), byteorder="big", signed=False)
            )

    for boneFrameData in armatureFrameData:
        for boneFrameDataProperty in boneFrameData:
            frameCount = len(boneFrameDataProperty.frames)
            sm64_anim.indices.shortData.append(frameCount)
            sm64_anim.indices.shortData.append(transformValuesOffset)
            if (transformValuesOffset) > 2**16 - 1:
                raise PluginError("Animation is too large.")
            transformValuesOffset += frameCount
            transformValuesStart += 4
            for value in boneFrameDataProperty.frames:
                sm64_anim.values.shortData.append(value)

    animSize = headerSize + len(sm64_anim.indices.shortData) * 2 + len(sm64_anim.values.shortData) * 2

    sm64_anim.header = SM64_AnimationHeader(
        sm64_anim.name,
        repetitions,
        marioYOffset,
        [frame_start, frame_last + 1],
        nodeCount,
        transformValuesStart,
        transformIndicesStart,
        animSize,
    )

    return sm64_anim


def convertAnimationData(anim, armatureObj, *, frame_start, frame_count):
    bonesToProcess = findStartBones(armatureObj)
    currentBone = armatureObj.data.bones[bonesToProcess[0]]
    animBones = []

    # Get animation bones in order
    while len(bonesToProcess) > 0:
        boneName = bonesToProcess[0]
        currentBone = armatureObj.data.bones[boneName]
        currentPoseBone = armatureObj.pose.bones[boneName]
        bonesToProcess = bonesToProcess[1:]

        # Only handle 0x13 bones for animation
        if currentBone.geo_cmd in animatableBoneTypes:
            animBones.append(boneName)

        # Traverse children in alphabetical order.
        childrenNames = sorted([bone.name for bone in currentBone.children])
        bonesToProcess = childrenNames + bonesToProcess

    # list of boneFrameData, which is [[x frames], [y frames], [z frames]]
    translationData = [ValueFrameData(0, i, []) for i in range(3)]
    armatureFrameData = [
        [ValueFrameData(i, 0, []), ValueFrameData(i, 1, []), ValueFrameData(i, 2, [])] for i in range(len(animBones))
    ]

    currentFrame = bpy.context.scene.frame_current
    for frame in range(frame_start, frame_start + frame_count):
        bpy.context.scene.frame_set(frame)
        rootBone = armatureObj.data.bones[animBones[0]]
        rootPoseBone = armatureObj.pose.bones[animBones[0]]

        # Hacky solution to handle Z-up to Y-up conversion
        translation = (
            rootBone.matrix.to_4x4().inverted()
            @ mathutils.Matrix.Scale(bpy.context.scene.blenderToSM64Scale, 4)
            @ rootPoseBone.matrix
        ).decompose()[0]
        saveTranslationFrame(translationData, translation)

        for boneIndex in range(len(animBones)):
            boneName = animBones[boneIndex]
            currentBone = armatureObj.data.bones[boneName]
            currentPoseBone = armatureObj.pose.bones[boneName]

            rotationValue = (currentBone.matrix.to_4x4().inverted() @ currentPoseBone.matrix).to_quaternion()
            if currentBone.parent is not None:
                rotationValue = (
                    currentBone.matrix.to_4x4().inverted()
                    @ currentPoseBone.parent.matrix.inverted()
                    @ currentPoseBone.matrix
                ).to_quaternion()

                # rest pose local, compared to current pose local

            saveQuaternionFrame(armatureFrameData[boneIndex], rotationValue)

    bpy.context.scene.frame_set(currentFrame)
    removeTrailingFrames(translationData)
    for frameData in armatureFrameData:
        removeTrailingFrames(frameData)

    return translationData, armatureFrameData


def getNextBone(boneStack, armatureObj):
    if len(boneStack) == 0:
        raise PluginError("More bones in animation than on armature.")
    bone = armatureObj.data.bones[boneStack[0]]
    boneStack = boneStack[1:]
    boneStack = sorted([child.name for child in bone.children]) + boneStack

    # Only return 0x13 bone
    while armatureObj.data.bones[bone.name].geo_cmd not in animatableBoneTypes:
        if len(boneStack) == 0:
            raise PluginError("More bones in animation than on armature.")
        bone = armatureObj.data.bones[boneStack[0]]
        boneStack = boneStack[1:]
        boneStack = sorted([child.name for child in bone.children]) + boneStack

    return bone, boneStack


def importAnimationToBlender(romfile, startAddress, armatureObj, segmentData, isDMA, animName):
    boneStack = findStartBones(armatureObj)
    startBoneName = boneStack[0]
    if armatureObj.data.bones[startBoneName].geo_cmd not in animatableBoneTypes:
        startBone, boneStack = getNextBone(boneStack, armatureObj)
        startBoneName = startBone.name
        boneStack = [startBoneName] + boneStack

    animationHeader, armatureFrameData = readAnimation(animName, romfile, startAddress, segmentData, isDMA)

    if len(armatureFrameData) > len(armatureObj.data.bones) + 1:
        raise PluginError("More bones in animation than on armature.")

    # bpy.context.scene.render.fps = 30
    bpy.context.scene.frame_end = animationHeader.frameInterval[1]
    anim = bpy.data.actions.new(animName)

    isRootTranslation = True
    # boneFrameData = [[x keyframes], [y keyframes], [z keyframes]]
    # len(armatureFrameData) should be = number of bones
    # property index = 0,1,2 (aka x,y,z)
    for boneFrameData in armatureFrameData:
        if isRootTranslation:
            for propertyIndex in range(3):
                fcurve = anim.fcurves.new(
                    data_path='pose.bones["' + startBoneName + '"].location',
                    index=propertyIndex,
                    action_group=startBoneName,
                )
                for frame in range(len(boneFrameData[propertyIndex])):
                    fcurve.keyframe_points.insert(frame, boneFrameData[propertyIndex][frame])
            isRootTranslation = False
        else:
            bone, boneStack = getNextBone(boneStack, armatureObj)
            for propertyIndex in range(3):
                fcurve = anim.fcurves.new(
                    data_path='pose.bones["' + bone.name + '"].rotation_euler',
                    index=propertyIndex,
                    action_group=bone.name,
                )
                for frame in range(len(boneFrameData[propertyIndex])):
                    fcurve.keyframe_points.insert(frame, boneFrameData[propertyIndex][frame])

    if armatureObj.animation_data is None:
        armatureObj.animation_data_create()

    stashActionInArmature(armatureObj, anim)
    armatureObj.animation_data.action = anim

def readAnimation(name, romfile, startAddress, segmentData, isDMA):
    animationHeader = readAnimHeader(name, romfile, startAddress, segmentData, isDMA)

    print("Frames: " + str(animationHeader.frameInterval[1]) + " / Nodes: " + str(animationHeader.nodeCount))

    animationHeader.transformIndices = readAnimIndices(
        romfile, animationHeader.transformIndicesStart, animationHeader.nodeCount
    )

    armatureFrameData = []  # list of list of frames

    # sm64 space -> blender space -> pose space
    # BlenderToSM64: YZX (set rotation mode of bones)
    # SM64toBlender: ZXY (set anim keyframes and model armature)
    # new bones should extrude in +Y direction

    # handle root translation
    boneFrameData = [[], [], []]
    rootIndexNode = animationHeader.transformIndices[0]
    boneFrameData[0] = [
        n for n in getKeyFramesTranslation(romfile, animationHeader.transformValuesStart, rootIndexNode.x)
    ]
    boneFrameData[1] = [
        n for n in getKeyFramesTranslation(romfile, animationHeader.transformValuesStart, rootIndexNode.y)
    ]
    boneFrameData[2] = [
        n for n in getKeyFramesTranslation(romfile, animationHeader.transformValuesStart, rootIndexNode.z)
    ]
    armatureFrameData.append(boneFrameData)

    # handle rotations
    for boneIndexNode in animationHeader.transformIndices[1:]:
        boneFrameData = [[], [], []]

        # Transforming SM64 space to Blender space
        boneFrameData[0] = [
            n for n in getKeyFramesRotation(romfile, animationHeader.transformValuesStart, boneIndexNode.x)
        ]
        boneFrameData[1] = [
            n for n in getKeyFramesRotation(romfile, animationHeader.transformValuesStart, boneIndexNode.y)
        ]
        boneFrameData[2] = [
            n for n in getKeyFramesRotation(romfile, animationHeader.transformValuesStart, boneIndexNode.z)
        ]

        armatureFrameData.append(boneFrameData)

    return (animationHeader, armatureFrameData)


def getKeyFramesRotation(romfile, transformValuesStart, boneIndex):
    ptrToValue = transformValuesStart + boneIndex.startOffset
    romfile.seek(ptrToValue)

    keyframes = []
    for frame in range(boneIndex.numFrames):
        romfile.seek(ptrToValue + frame * 2)
        value = int.from_bytes(romfile.read(2), "big") * 360 / (2**16)
        keyframes.append(math.radians(value))

    return keyframes


def getKeyFramesTranslation(romfile, transformValuesStart, boneIndex):
    ptrToValue = transformValuesStart + boneIndex.startOffset
    romfile.seek(ptrToValue)

    keyframes = []
    for frame in range(boneIndex.numFrames):
        romfile.seek(ptrToValue + frame * 2)
        keyframes.append(int.from_bytes(romfile.read(2), "big", signed=True) / bpy.context.scene.blenderToSM64Scale)

    return keyframes


def readAnimHeader(name, romfile, startAddress, segmentData, isDMA):
    frameInterval = [0, 0]

    romfile.seek(startAddress + 0x00)
    numRepeats = int.from_bytes(romfile.read(2), "big")

    romfile.seek(startAddress + 0x02)
    marioYOffset = int.from_bytes(romfile.read(2), "big")

    romfile.seek(startAddress + 0x06)
    frameInterval[0] = int.from_bytes(romfile.read(2), "big")

    romfile.seek(startAddress + 0x08)
    frameInterval[1] = int.from_bytes(romfile.read(2), "big")

    romfile.seek(startAddress + 0x0A)
    numNodes = int.from_bytes(romfile.read(2), "big")

    romfile.seek(startAddress + 0x0C)
    transformValuesOffset = int.from_bytes(romfile.read(4), "big")
    if isDMA:
        transformValuesStart = startAddress + transformValuesOffset
    else:
        transformValuesStart = decodeSegmentedAddr(transformValuesOffset.to_bytes(4, byteorder="big"), segmentData)

    romfile.seek(startAddress + 0x10)
    transformIndicesOffset = int.from_bytes(romfile.read(4), "big")
    if isDMA:
        transformIndicesStart = startAddress + transformIndicesOffset
    else:
        transformIndicesStart = decodeSegmentedAddr(transformIndicesOffset.to_bytes(4, byteorder="big"), segmentData)

    romfile.seek(startAddress + 0x14)
    animSize = int.from_bytes(romfile.read(4), "big")

    return SM64_AnimationHeader(
        name, numRepeats, marioYOffset, frameInterval, numNodes, transformValuesStart, transformIndicesStart, animSize
    )


def readAnimIndices(romfile, ptrAddress, nodeCount):
    indices = []

    # Handle root transform
    rootPosIndex = readTransformIndex(romfile, ptrAddress)
    indices.append(rootPosIndex)

    # Handle rotations
    for i in range(nodeCount):
        rotationIndex = readTransformIndex(romfile, ptrAddress + (i + 1) * 12)
        indices.append(rotationIndex)

    return indices


def readTransformIndex(romfile, startAddress):
    x = readValueIndex(romfile, startAddress + 0)
    y = readValueIndex(romfile, startAddress + 4)
    z = readValueIndex(romfile, startAddress + 8)

    return SM64_AnimIndexNode(x, y, z)


def readValueIndex(romfile, startAddress):
    romfile.seek(startAddress)
    numFrames = int.from_bytes(romfile.read(2), "big")
    romfile.seek(startAddress + 2)

    # multiply 2 because value is the index in array of shorts (???)
    startOffset = int.from_bytes(romfile.read(2), "big") * 2
    #print(str(hex(startAddress)) + ": " + str(numFrames) + " " + str(startOffset))
    return SM64_AnimIndex(numFrames, startOffset)


def writeAnimation(romfile, startAddress, segmentData):
    pass


def writeAnimHeader(romfile, startAddress, segmentData):
    pass


class SM64_ExportAnimMario(bpy.types.Operator):
    bl_idname = "object.sm64_export_anim"
    bl_label = "Export Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileOutput = None
        tempROM = None
        try:
            if len(context.selected_objects) == 0 or not isinstance(
                context.selected_objects[0].data, bpy.types.Armature
            ):
                raise PluginError("Armature not selected.")
            if len(context.selected_objects) > 1:
                raise PluginError("Multiple objects selected, make sure to select only one.")
            armatureObj = context.selected_objects[0]
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            # Rotate all armatures 90 degrees
            applyRotation([armatureObj], math.radians(90), "X")

            if context.scene.fast64.sm64.exportType == "C":
                exportPath, levelName = getPathAndLevel(
                    context.scene.animCustomExport,
                    context.scene.animExportPath,
                    context.scene.animLevelName,
                    context.scene.animLevelOption,
                )
                if not context.scene.animCustomExport:
                    applyBasicTweaks(exportPath)
                exportAnimationC(
                    armatureObj,
                    context.scene.loopAnimation,
                    exportPath,
                    bpy.context.scene.animName,
                    bpy.context.scene.animGroupName,
                    context.scene.animCustomExport,
                    context.scene.animExportHeaderType,
                    levelName,
                )
                self.report({"INFO"}, "Success!")
            elif context.scene.fast64.sm64.exportType == "Insertable Binary":
                exportAnimationInsertableBinary(
                    bpy.path.abspath(context.scene.animInsertableBinaryPath),
                    armatureObj,
                    context.scene.isDMAExport,
                    context.scene.loopAnimation,
                )
                self.report({"INFO"}, "Success! Animation at " + context.scene.animInsertableBinaryPath)
            else:
                checkExpanded(bpy.path.abspath(context.scene.exportRom))
                tempROM = tempName(context.scene.outputRom)
                romfileExport = open(bpy.path.abspath(context.scene.exportRom), "rb")
                shutil.copy(bpy.path.abspath(context.scene.exportRom), bpy.path.abspath(tempROM))
                romfileExport.close()
                romfileOutput = open(bpy.path.abspath(tempROM), "rb+")

                # Note actual level doesn't matter for Mario, since he is in all of 	them
                levelParsed = parseLevelAtPointer(romfileOutput, level_pointers[context.scene.levelAnimExport])
                segmentData = levelParsed.segmentData
                if context.scene.extendBank4:
                    ExtendBank0x04(romfileOutput, segmentData, defaultExtendSegment4)

                DMAAddresses = None
                if context.scene.animOverwriteDMAEntry:
                    DMAAddresses = {}
                    DMAAddresses["start"] = int(context.scene.DMAStartAddress, 16)
                    DMAAddresses["entry"] = int(context.scene.DMAEntryAddress, 16)

                addrRange, nonDMAListPtr = exportAnimationBinary(
                    romfileOutput,
                    [int(context.scene.animExportStart, 16), int(context.scene.animExportEnd, 16)],
                    bpy.context.active_object,
                    DMAAddresses,
                    segmentData,
                    context.scene.isDMAExport,
                    context.scene.loopAnimation,
                )

                if not context.scene.isDMAExport:
                    segmentedPtr = encodeSegmentedAddr(addrRange[0], segmentData)
                    if context.scene.setAnimListIndex:
                        romfileOutput.seek(int(context.scene.addr_0x27, 16) + 4)
                        segAnimPtr = romfileOutput.read(4)
                        virtAnimPtr = decodeSegmentedAddr(segAnimPtr, segmentData)
                        romfileOutput.seek(virtAnimPtr + 4 * context.scene.animListIndexExport)
                        romfileOutput.write(segmentedPtr)
                    if context.scene.overwrite_0x28:
                        romfileOutput.seek(int(context.scene.addr_0x28, 16) + 1)
                        romfileOutput.write(bytearray([context.scene.animListIndexExport]))
                else:
                    segmentedPtr = None

                romfileOutput.close()
                if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
                    os.remove(bpy.path.abspath(context.scene.outputRom))
                os.rename(bpy.path.abspath(tempROM), bpy.path.abspath(context.scene.outputRom))

                if not context.scene.isDMAExport:
                    if context.scene.setAnimListIndex:
                        self.report(
                            {"INFO"},
                            "Sucess! Animation table at "
                            + hex(virtAnimPtr)
                            + ", animation at ("
                            + hex(addrRange[0])
                            + ", "
                            + hex(addrRange[1])
                            + ") "
                            + "(Seg. "
                            + bytesToHex(segmentedPtr)
                            + ").",
                        )
                    else:
                        self.report(
                            {"INFO"},
                            "Sucess! Animation at ("
                            + hex(addrRange[0])
                            + ", "
                            + hex(addrRange[1])
                            + ") "
                            + "(Seg. "
                            + bytesToHex(segmentedPtr)
                            + ").",
                        )
                else:
                    self.report(
                        {"INFO"}, "Success! Animation at (" + hex(addrRange[0]) + ", " + hex(addrRange[1]) + ")."
                    )

            applyRotation([armatureObj], math.radians(-90), "X")
        except Exception as e:
            applyRotation([armatureObj], math.radians(-90), "X")

            if romfileOutput is not None:
                romfileOutput.close()
            if tempROM is not None and os.path.exists(bpy.path.abspath(tempROM)):
                os.remove(bpy.path.abspath(tempROM))
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set


class SM64_ExportAnimPanel(SM64_Panel):
    bl_idname = "SM64_PT_export_anim"
    bl_label = "SM64 Animation Exporter"
    goal = "Export Object/Actor/Anim"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsAnimExport = col.operator(SM64_ExportAnimMario.bl_idname)

        col.prop(context.scene, "loopAnimation")

        if context.scene.fast64.sm64.exportType == "C":
            col.prop(context.scene, "animCustomExport")
            if context.scene.animCustomExport:
                col.prop(context.scene, "animExportPath")
                prop_split(col, context.scene, "animName", "Name")
                customExportWarning(col)
            else:
                prop_split(col, context.scene, "animExportHeaderType", "Export Type")
                prop_split(col, context.scene, "animName", "Name")
                if context.scene.animExportHeaderType == "Actor":
                    prop_split(col, context.scene, "animGroupName", "Group Name")
                elif context.scene.animExportHeaderType == "Level":
                    prop_split(col, context.scene, "animLevelOption", "Level")
                    if context.scene.animLevelOption == "custom":
                        prop_split(col, context.scene, "animLevelName", "Level Name")

                decompFolderMessage(col)
                writeBox = makeWriteInfoBox(col)
                writeBoxExportType(
                    writeBox,
                    context.scene.animExportHeaderType,
                    context.scene.animName,
                    context.scene.animLevelName,
                    context.scene.animLevelOption,
                )

        elif context.scene.fast64.sm64.exportType == "Insertable Binary":
            col.prop(context.scene, "isDMAExport")
            col.prop(context.scene, "animInsertableBinaryPath")
        else:
            col.prop(context.scene, "isDMAExport")
            if context.scene.isDMAExport:
                col.prop(context.scene, "animOverwriteDMAEntry")
                if context.scene.animOverwriteDMAEntry:
                    prop_split(col, context.scene, "DMAStartAddress", "DMA Start Address")
                    prop_split(col, context.scene, "DMAEntryAddress", "DMA Entry Address")
            else:
                col.prop(context.scene, "setAnimListIndex")
                if context.scene.setAnimListIndex:
                    prop_split(col, context.scene, "addr_0x27", "27 Command Address")
                    prop_split(col, context.scene, "animListIndexExport", "Anim List Index")
                    col.prop(context.scene, "overwrite_0x28")
                    if context.scene.overwrite_0x28:
                        prop_split(col, context.scene, "addr_0x28", "28 Command Address")
                col.prop(context.scene, "levelAnimExport")
            col.separator()
            prop_split(col, context.scene, "animExportStart", "Start Address")
            prop_split(col, context.scene, "animExportEnd", "End Address")


class SM64_ImportAnimMario(bpy.types.Operator):
    bl_idname = "object.sm64_import_anim"
    bl_label = "Import Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileSrc = None
        try:
            checkExpanded(bpy.path.abspath(context.scene.importRom))
            romfileSrc = open(bpy.path.abspath(context.scene.importRom), "rb")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}
        try:
            levelParsed = parseLevelAtPointer(romfileSrc, level_pointers[context.scene.levelAnimImport])
            segmentData = levelParsed.segmentData

            animStart = int(context.scene.animStartImport, 16)
            if context.scene.animIsSegPtr:
                animStart = decodeSegmentedAddr(animStart.to_bytes(4, "big"), segmentData)

            if not context.scene.isDMAImport and context.scene.animIsAnimList:
                romfileSrc.seek(animStart + 4 * context.scene.animListIndexImport)
                actualPtr = romfileSrc.read(4)
                animStart = decodeSegmentedAddr(actualPtr, segmentData)

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            armatureObj = context.active_object
            if type(armatureObj.data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            importAnimationToBlender(romfileSrc, animStart, armatureObj, segmentData, context.scene.isDMAImport, "sm64_anim")
            romfileSrc.close()
            self.report({"INFO"}, "Success!")
        except Exception as e:
            if romfileSrc is not None:
                romfileSrc.close()
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set


class SM64_ImportAllMarioAnims(bpy.types.Operator):
    bl_idname = "object.sm64_import_mario_anims"
    bl_label = "Import All Mario Animations"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileSrc = None
        try:
            checkExpanded(bpy.path.abspath(context.scene.importRom))
            romfileSrc = open(bpy.path.abspath(context.scene.importRom), "rb")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}
        try:
            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            armatureObj = context.active_object
            if type(armatureObj.data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            for adress, animName in marioAnimations:
                importAnimationToBlender(romfileSrc, adress, armatureObj, {}, context.scene.isDMAImport, animName)
                
            romfileSrc.close()
            self.report({"INFO"}, "Success!")
        except Exception as e:
            if romfileSrc is not None:
                romfileSrc.close()
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set


class SM64_ImportAnimPanel(SM64_Panel):
    bl_idname = "SM64_PT_import_anim"
    bl_label = "SM64 Animation Importer"
    goal = sm64GoalImport

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsAnimImport = col.operator(SM64_ImportAnimMario.bl_idname)  
        propsMarioAnimsImport = col.operator(SM64_ImportAllMarioAnims.bl_idname)  

        col.prop(context.scene, "isDMAImport")
        if not context.scene.isDMAImport:
            col.prop(context.scene, "animIsAnimList")
            if context.scene.animIsAnimList:
                prop_split(col, context.scene, "animListIndexImport", "Anim List Index")

        prop_split(col, context.scene, "animStartImport", "Start Address")
        col.prop(context.scene, "animIsSegPtr")
        col.prop(context.scene, "levelAnimImport")


sm64_anim_classes = (
    SM64_ExportAnimMario,
    SM64_ImportAnimMario,
    SM64_ImportAllMarioAnims,
)

sm64_anim_panels = (
    SM64_ImportAnimPanel,
    SM64_ExportAnimPanel,
)


def sm64_anim_panel_register():
    for cls in sm64_anim_panels:
        register_class(cls)


def sm64_anim_panel_unregister():
    for cls in sm64_anim_panels:
        unregister_class(cls)


def sm64_anim_register():
    for cls in sm64_anim_classes:
        register_class(cls)

    bpy.types.Scene.animStartImport = bpy.props.StringProperty(name="Import Start", default="4EC690")
    bpy.types.Scene.animExportStart = bpy.props.StringProperty(name="Start", default="11D8930")
    bpy.types.Scene.animExportEnd = bpy.props.StringProperty(name="End", default="11FFF00")
    bpy.types.Scene.isDMAImport = bpy.props.BoolProperty(name="Is DMA Animation", default=True)
    bpy.types.Scene.isDMAExport = bpy.props.BoolProperty(name="Is DMA Animation")
    bpy.types.Scene.DMAEntryAddress = bpy.props.StringProperty(name="DMA Entry Address", default="4EC008")
    bpy.types.Scene.DMAStartAddress = bpy.props.StringProperty(name="DMA Start Address", default="4EC000")
    bpy.types.Scene.levelAnimImport = bpy.props.EnumProperty(items=level_enums, name="Level", default="IC")
    bpy.types.Scene.levelAnimExport = bpy.props.EnumProperty(items=level_enums, name="Level", default="IC")
    bpy.types.Scene.loopAnimation = bpy.props.BoolProperty(name="Loop Animation", default=True)
    bpy.types.Scene.setAnimListIndex = bpy.props.BoolProperty(name="Set Anim List Entry", default=True)
    bpy.types.Scene.overwrite_0x28 = bpy.props.BoolProperty(name="Overwrite 0x28 behaviour command", default=True)
    bpy.types.Scene.addr_0x27 = bpy.props.StringProperty(name="0x27 Command Address", default="21CD00")
    bpy.types.Scene.addr_0x28 = bpy.props.StringProperty(name="0x28 Command Address", default="21CD08")
    bpy.types.Scene.animExportPath = bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    bpy.types.Scene.animOverwriteDMAEntry = bpy.props.BoolProperty(name="Overwrite DMA Entry")
    bpy.types.Scene.animInsertableBinaryPath = bpy.props.StringProperty(name="Filepath", subtype="FILE_PATH")
    bpy.types.Scene.animIsSegPtr = bpy.props.BoolProperty(name="Is Segmented Address", default=False)
    bpy.types.Scene.animIsAnimList = bpy.props.BoolProperty(name="Is Anim List", default=True)
    bpy.types.Scene.animListIndexImport = bpy.props.IntProperty(name="Anim List Index", min=0, max=255)
    bpy.types.Scene.animListIndexExport = bpy.props.IntProperty(name="Anim List Index", min=0, max=255)
    bpy.types.Scene.animName = bpy.props.StringProperty(name="Name", default="mario")
    bpy.types.Scene.animGroupName = bpy.props.StringProperty(name="Group Name", default="group0")
    bpy.types.Scene.animWriteHeaders = bpy.props.BoolProperty(name="Write Headers For Actor", default=True)
    bpy.types.Scene.animCustomExport = bpy.props.BoolProperty(name="Custom Export Path")
    bpy.types.Scene.animExportHeaderType = bpy.props.EnumProperty(
        items=enumExportHeaderType, name="Header Export", default="Actor"
    )
    bpy.types.Scene.animLevelName = bpy.props.StringProperty(name="Level", default="bob")
    bpy.types.Scene.animLevelOption = bpy.props.EnumProperty(items=enumLevelNames, name="Level", default="bob")


def sm64_anim_unregister():
    for cls in reversed(sm64_anim_classes):
        unregister_class(cls)

    del bpy.types.Scene.animStartImport
    del bpy.types.Scene.animExportStart
    del bpy.types.Scene.animExportEnd
    del bpy.types.Scene.levelAnimImport
    del bpy.types.Scene.levelAnimExport
    del bpy.types.Scene.isDMAImport
    del bpy.types.Scene.isDMAExport
    del bpy.types.Scene.DMAStartAddress
    del bpy.types.Scene.DMAEntryAddress
    del bpy.types.Scene.loopAnimation
    del bpy.types.Scene.setAnimListIndex
    del bpy.types.Scene.overwrite_0x28
    del bpy.types.Scene.addr_0x27
    del bpy.types.Scene.addr_0x28
    del bpy.types.Scene.animExportPath
    del bpy.types.Scene.animOverwriteDMAEntry
    del bpy.types.Scene.animInsertableBinaryPath
    del bpy.types.Scene.animIsSegPtr
    del bpy.types.Scene.animIsAnimList
    del bpy.types.Scene.animListIndexImport
    del bpy.types.Scene.animListIndexExport
    del bpy.types.Scene.animName
    del bpy.types.Scene.animGroupName
    del bpy.types.Scene.animWriteHeaders
    del bpy.types.Scene.animCustomExport
    del bpy.types.Scene.animExportHeaderType
    del bpy.types.Scene.animLevelName
    del bpy.types.Scene.animLevelOption
