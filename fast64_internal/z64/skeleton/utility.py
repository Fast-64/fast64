import dataclasses
import mathutils, bpy, os, re
from typing import Optional
from ...utility_anim import armatureApplyWithMesh
from ..model_classes import OOTVertexGroupInfo
from ..utility import checkForStartBone, getStartBone, getNextBone, ootStripComments

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
    get_include_data,
    removeComments,
    yUpToZUp,
    deselectAllObjects,
    selectSingleObject,
)


@dataclasses.dataclass
class SkeletonInfo:
    start: int
    end: int
    limbs_name: str
    uses_include: bool


def ootGetSkeleton(skeletonData: str, skeletonName: str, continueOnError: bool):
    matchResult = re.search(
        r"(Flex)?SkeletonHeader\s*"
        + re.escape(skeletonName)
        + r"\s*=\s*\{\s*\{?\s*([^,\s]*)\s*,?\s*([^,\s\}]*)\s*\}?\s*(,\s*([^,\s]*))?\s*\}\s*;\s*",
        skeletonData,
    )
    if matchResult is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot find skeleton named " + skeletonName)

    if "#include" in matchResult.group(0):
        uses_include = True
        split = get_include_data(matchResult.group(3), strip=True).replace("{", "").replace(",}", "").split(",")
        limbs_name = split[0]
    else:
        uses_include = False
        limbs_name = matchResult.group(2)

    return SkeletonInfo(matchResult.start(0), matchResult.end(0), limbs_name, uses_include)


@dataclasses.dataclass
class LimbsInfo:
    start: int
    end: int
    limb_list: list[str]
    uses_include: bool


def ootGetLimbs(skeletonData, limbsName, continueOnError):
    matchResult = re.search(
        r"(static\s*)?void\s*\*\s*" + re.escape(limbsName) + r"\s*\[\s*[0-9]*\s*\]\s*=\s*\{([^\}]*)\}\s*;\s*",
        skeletonData,
        re.DOTALL,
    )
    if matchResult is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot find skeleton limbs named " + limbsName)

    if "#include" in matchResult.group(0):
        uses_include = True
        limbsData = removeComments(get_include_data(matchResult.group(2)))
    else:
        uses_include = False
        limbsData = matchResult.group(2)

    limb_list = [entry.strip()[1:] for entry in ootStripComments(limbsData).split(",") if entry.strip() != ""]

    return LimbsInfo(matchResult.start(0), matchResult.end(0), limb_list, uses_include)


@dataclasses.dataclass
class LimbInfo:
    start: int
    end: int
    translationX_str: str
    translationY_str: str
    translationZ_str: str
    nextChildIndex_str: str
    nextSiblingIndex_str: str
    is_lod: bool
    dl_name: str
    far_dl_name: Optional[str]
    uses_include: bool


def ootGetLimb(skeletonData, limbName, continueOnError):
    matchResultIni = re.search(
        r"([A-Za-z0-9\_]*)Limb\s*" + re.escape(limbName) + r"\s*=\s*\{(.*?)\s*\}\s*;",
        skeletonData,
        re.DOTALL | re.MULTILINE,
    )

    if matchResultIni is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot find skeleton limb named " + limbName)

    result = matchResultIni.group(2)
    if "#include" in result:
        uses_include = True
        limb_data = removeComments(get_include_data(result))
    else:
        uses_include = False
        limb_data = result

    limbType = matchResultIni.group(1)
    if limbType == "Lod":
        is_lod = True
        dlRegex = r"\{\s*([^,\s]*)\s*,\s*([^,\s]*)\s*,?\}"
    else:
        is_lod = False
        dlRegex = r"([^,\s]*)"

    matchResult = re.search(
        r"\{([^,\s]*),([^,\s]*),([^,\s]*),?\},([^,]*),([^,]*),\{?" + dlRegex,
        limb_data.replace("\n", "").replace(" ", ""),
        re.DOTALL,
    )

    if matchResult is None:
        if continueOnError:
            return None
        else:
            raise PluginError("Cannot handle skeleton limb named " + limbName + " of type " + limbType)

    translationX_str = matchResult.group(1)
    translationY_str = matchResult.group(2)
    translationZ_str = matchResult.group(3)
    nextChildIndex_str = matchResult.group(4)
    nextSiblingIndex_str = matchResult.group(5)

    dl_name = matchResult.group(6)

    if is_lod:
        far_dl_name = matchResult.group(7)
    else:
        far_dl_name = None

    return LimbInfo(
        matchResultIni.start(0),
        matchResultIni.end(0),
        translationX_str,
        translationY_str,
        translationZ_str,
        nextChildIndex_str,
        nextSiblingIndex_str,
        is_lod,
        dl_name,
        far_dl_name,
        uses_include,
    )


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

    skel_info = ootGetSkeleton(skeletonDataC, skeletonName, True)

    if skel_info is None:
        return
    skeletonDataC = skeletonDataC[: skel_info.start] + skeletonDataC[skel_info.end :]

    headerMatch = getDeclaration(skeletonDataH, skeletonName)
    if headerMatch is not None:
        skeletonDataH = skeletonDataH[: headerMatch.start(0)] + skeletonDataH[headerMatch.end(0) :]

    limbs_info = ootGetLimbs(skeletonDataC, skel_info.limbs_name, True)
    if limbs_info is None:
        return
    skeletonDataC = skeletonDataC[: limbs_info.start] + skeletonDataC[limbs_info.end :]

    headerMatch = getDeclaration(skeletonDataH, skel_info.limbs_name)
    if headerMatch is not None:
        skeletonDataH = skeletonDataH[: headerMatch.start(0)] + skeletonDataH[headerMatch.end(0) :]

    for limb in limbs_info.limb_list:
        limb_info = ootGetLimb(skeletonDataC, limb, True)
        if limb_info is not None:
            skeletonDataC = skeletonDataC[: limb_info.start] + skeletonDataC[limb_info.end :]
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
    deselectAllObjects()

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
            setOrigin(obj, armatureObj.location)

        selectSingleObject(armatureObj)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, properties=False)

        ootRemoveRotationsFromArmature(armatureObj)

        # Apply modifiers/data to mesh objs
        deselectAllObjects()
        for obj in meshObjs:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

        bpy.ops.object.make_single_user(obdata=True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)
        for selectedObj in meshObjs:
            selectSingleObject(selectedObj)

            for modifier in selectedObj.modifiers:
                attemptModifierApply(modifier)

        # Apply new armature rest pose
        selectSingleObject(armatureObj)
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
    selectSingleObject(armatureObj)

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
