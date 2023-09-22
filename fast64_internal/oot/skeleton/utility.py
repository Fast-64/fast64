import mathutils, bpy, os, re
from ...utility_anim import armatureApplyWithMesh
from ..oot_model_classes import OOTVertexGroupInfo
from ..oot_utility import checkForStartBone, getStartBone, getNextBone

from ...utility import (
    PluginError,
    VertexWeightError,
    getDeclaration,
    writeFile,
    readFile,
    setOrigin,
    getGroupNameFromIndex,
    attemptModifierApply,
    cleanupDuplicatedObjects,
    yUpToZUp,
)


def ootGetSkeleton(skeletonData, skeletonName, continueOnError):
    # TODO: Does this handle non flex skeleton?
    matchResult = re.search(
        "(Flex)?SkeletonHeader\s*"
        + re.escape(skeletonName)
        + "\s*=\s*\{\s*\{?\s*([^,\s]*)\s*,\s*([^,\s\}]*)\s*\}?\s*(,\s*([^,\s]*))?\s*\}\s*;\s*",
        skeletonData,
    )
    if matchResult is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot find skeleton named " + skeletonName)
    return matchResult


def ootGetLimbs(skeletonData, limbsName, continueOnError):
    matchResult = re.search(
        "(static\s*)?void\s*\*\s*" + re.escape(limbsName) + "\s*\[\s*[0-9]*\s*\]\s*=\s*\{([^\}]*)\}\s*;\s*",
        skeletonData,
        re.DOTALL,
    )
    if matchResult is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot find skeleton limbs named " + limbsName)
    return matchResult


def ootGetLimb(skeletonData, limbName, continueOnError):
    matchResult = re.search("([A-Za-z0-9\_]*)Limb\s*" + re.escape(limbName), skeletonData)

    if matchResult is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot find skeleton limb named " + limbName)

    limbType = matchResult.group(1)
    if limbType == "Lod":
        dlRegex = "\{\s*([^,\s]*)\s*,\s*([^,\s]*)\s*\}"
    else:
        dlRegex = "([^,\s]*)"

    matchResult = re.search(
        "[A-Za-z0-9\_]*Limb\s*"
        + re.escape(limbName)
        + "\s*=\s*\{\s*\{\s*([^,\s]*)\s*,\s*([^,\s]*)\s*,\s*([^,\s]*)\s*\},\s*([^, ]*)\s*,\s*([^, ]*)\s*,\s*"
        + dlRegex
        + "\s*\}\s*;\s*",
        skeletonData,
        re.DOTALL,
    )

    if matchResult is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot handle skeleton limb named " + limbName + " of type " + limbType)
    return matchResult


def getGroupIndexOfVert(vert, armatureObj, obj, rootGroupIndex):
    actualGroups = []
    nonBoneGroups = []
    for group in vert.groups:
        groupName = getGroupNameFromIndex(obj, group.group)
        if groupName is not None:
            if groupName in armatureObj.data.bones:
                actualGroups.append(group)
            else:
                nonBoneGroups.append(groupName)

    if len(actualGroups) == 0:
        # return rootGroupIndex
        # highlightWeightErrors(obj, [vert], "VERT")
        if len(nonBoneGroups) > 0:
            raise VertexWeightError(
                "All vertices must be part of a vertex group "
                + "that corresponds to a bone in the armature.\n"
                + "Groups of the bad vert that don't correspond to a bone: "
                + str(nonBoneGroups)
                + ". If a vert is supposed to belong to this group then either a bone is missing or you have the wrong group."
            )
        else:
            raise VertexWeightError("There are unweighted vertices in the mesh that must be weighted to a bone.")

    vertGroup = actualGroups[0]
    for group in actualGroups:
        if group.weight > vertGroup.weight:
            vertGroup = group
    # if vertGroup not in actualGroups:
    # raise VertexWeightError("A vertex was found that was primarily weighted to a group that does not correspond to a bone in #the armature. (" + getGroupNameFromIndex(obj, vertGroup.group) + ') Either decrease the weights of this vertex group or remove it. If you think this group should correspond to a bone, make sure to check your spelling.')
    return vertGroup.group


def getGroupIndices(meshInfo, armatureObj, meshObj, rootGroupIndex):
    meshInfo.vertexGroupInfo = OOTVertexGroupInfo()
    for vertex in meshObj.data.vertices:
        meshInfo.vertexGroupInfo.vertexGroups[vertex.index] = getGroupIndexOfVert(
            vertex, armatureObj, meshObj, rootGroupIndex
        )


def ootRemoveSkeleton(filepath, objectName, skeletonName):
    headerPath = os.path.join(filepath, objectName + ".h")
    sourcePath = os.path.join(filepath, objectName + ".c")

    skeletonDataC = readFile(sourcePath)
    originalDataC = skeletonDataC

    skeletonDataH = readFile(headerPath)
    originalDataH = skeletonDataH

    matchResult = ootGetSkeleton(skeletonDataC, skeletonName, True)
    if matchResult is None:
        return
    skeletonDataC = skeletonDataC[: matchResult.start(0)] + skeletonDataC[matchResult.end(0) :]
    limbsName = matchResult.group(2)

    headerMatch = getDeclaration(skeletonDataH, skeletonName)
    if headerMatch is not None:
        skeletonDataH = skeletonDataH[: headerMatch.start(0)] + skeletonDataH[headerMatch.end(0) :]

    matchResult = ootGetLimbs(skeletonDataC, limbsName, True)
    if matchResult is None:
        return
    skeletonDataC = skeletonDataC[: matchResult.start(0)] + skeletonDataC[matchResult.end(0) :]
    limbsData = matchResult.group(2)
    limbList = [entry.strip()[1:] for entry in limbsData.split(",") if entry.strip() != ""]

    headerMatch = getDeclaration(skeletonDataH, limbsName)
    if headerMatch is not None:
        skeletonDataH = skeletonDataH[: headerMatch.start(0)] + skeletonDataH[headerMatch.end(0) :]

    for limb in limbList:
        matchResult = ootGetLimb(skeletonDataC, limb, True)
        if matchResult is not None:
            skeletonDataC = skeletonDataC[: matchResult.start(0)] + skeletonDataC[matchResult.end(0) :]
        headerMatch = getDeclaration(skeletonDataH, limb)
        if headerMatch is not None:
            skeletonDataH = skeletonDataH[: headerMatch.start(0)] + skeletonDataH[headerMatch.end(0) :]

    if skeletonDataC != originalDataC:
        writeFile(sourcePath, skeletonDataC)

    if skeletonDataH != originalDataH:
        writeFile(headerPath, skeletonDataH)


# TODO: check for bone type?
def ootRemoveRotationsFromBone(armatureObj: bpy.types.Object, bone: bpy.types.Bone):
    for childBone in bone.children:
        ootRemoveRotationsFromBone(armatureObj, childBone)

    if bone.parent is not None:
        transform = bone.parent.matrix_local.inverted() @ bone.matrix_local
    else:
        transform = bone.matrix_local

    # extract local transform, excluding rotation/scale
    # apply the inverse of that to the pose bone to get it to zero-rotation rest pose
    translate = mathutils.Matrix.Translation(transform.decompose()[0])
    undoRotationTransform = transform.inverted() @ translate
    if bone.parent is None:
        undoRotationTransform = undoRotationTransform @ yUpToZUp

    poseBone = armatureObj.pose.bones[bone.name]
    poseBone.matrix_basis = undoRotationTransform


def ootRemoveRotationsFromArmature(armatureObj: bpy.types.Object) -> None:
    checkForStartBone(armatureObj)
    startBoneName = getStartBone(armatureObj)

    if bpy.context.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    for editBone in armatureObj.data.edit_bones:
        editBone.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    ootRemoveRotationsFromBone(armatureObj, armatureObj.data.bones[startBoneName])
    armatureApplyWithMesh(armatureObj, bpy.context)


def ootDuplicateArmatureAndRemoveRotations(originalArmatureObj: bpy.types.Object):
    # Duplicate objects to apply scale / modifiers / linked data
    bpy.ops.object.select_all(action="DESELECT")

    for originalMeshObj in [obj for obj in originalArmatureObj.children if obj.type == "MESH"]:
        originalMeshObj.select_set(True)
        originalMeshObj.original_name = originalMeshObj.name

    originalArmatureObj.select_set(True)
    originalArmatureObj.original_name = originalArmatureObj.name
    bpy.context.view_layer.objects.active = originalArmatureObj
    bpy.ops.object.duplicate()

    armatureObj = bpy.context.view_layer.objects.active
    meshObjs = [obj for obj in bpy.context.selected_objects if obj is not armatureObj]

    try:
        for obj in meshObjs:
            setOrigin(armatureObj, obj)

        bpy.ops.object.select_all(action="DESELECT")
        armatureObj.select_set(True)
        bpy.context.view_layer.objects.active = armatureObj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, properties=False)

        ootRemoveRotationsFromArmature(armatureObj)

        # Apply modifiers/data to mesh objs
        bpy.ops.object.select_all(action="DESELECT")
        for obj in meshObjs:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

        bpy.ops.object.make_single_user(obdata=True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)
        for selectedObj in meshObjs:
            bpy.ops.object.select_all(action="DESELECT")
            selectedObj.select_set(True)
            bpy.context.view_layer.objects.active = selectedObj

            for modifier in selectedObj.modifiers:
                attemptModifierApply(modifier)

        # Apply new armature rest pose
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = armatureObj
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.armature_apply()
        bpy.ops.object.mode_set(mode="OBJECT")

        return armatureObj, meshObjs
    except Exception as e:
        cleanupDuplicatedObjects(meshObjs + [armatureObj])
        originalArmatureObj.select_set(True)
        bpy.context.view_layer.objects.active = originalArmatureObj
        raise Exception(str(e))


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
