import re
import mathutils
import bpy
import math

from pathlib import Path
from typing import List

from ....f3d.f3d_gbi import F3D, get_F3D_GBI
from ....f3d.f3d_parser import getImportData, parseF3D
from ....utility import (
    PluginError,
    hexOrDecInt,
    applyRotation,
    deselectAllObjects,
    selectSingleObject,
    get_include_data,
    removeComments,
)
from ...f3d_writer import ootReadActorScale
from ...model_classes import OOTF3DContext, ootGetIncludedAssetData
from ...utility import OOTEnum, ootGetObjectPath, getOOTScale, ootGetObjectHeaderPath, ootGetEnums, ootStripComments
from ...texture_array import ootReadTextureArrays
from ..constants import ootSkeletonImportDict
from ..properties import OOTSkeletonImportSettings
from ..utility import ootGetLimb, ootGetLimbs, ootGetSkeleton, applySkeletonRestPose, get_anim_names
from ...tools.quick_import import quick_import_exec


class OOTDLEntry:
    def __init__(self, dlName, limbIndex):
        self.dlName = dlName
        self.limbIndex = limbIndex


def ootAddBone(armatureObj, boneName, parentBoneName, currentTransform, loadDL):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    selectSingleObject(armatureObj)
    bpy.ops.object.mode_set(mode="EDIT")
    bone = armatureObj.data.edit_bones.new(boneName)
    bone.use_connect = False
    bone.use_deform = loadDL
    if parentBoneName is not None:
        bone.parent = armatureObj.data.edit_bones[parentBoneName]
    bone.head = currentTransform @ mathutils.Vector((0, 0, 0))
    bone.tail = bone.head + (currentTransform.to_quaternion() @ mathutils.Vector((0, 0.3, 0)))

    # Connect bone to parent if it is possible without changing parent direction.

    if parentBoneName is not None:
        nodeOffsetVector = mathutils.Vector(bone.head - bone.parent.head)
        # set fallback to nonzero to avoid creating zero length bones
        if nodeOffsetVector.angle(bone.parent.tail - bone.parent.head, 1) < 0.0001 and loadDL:
            for child in bone.parent.children:
                if child != bone:
                    child.use_connect = False
            bone.parent.tail = bone.head
            bone.use_connect = True
        elif bone.head == bone.parent.head and bone.tail == bone.parent.tail:
            bone.tail += currentTransform.to_quaternion() @ mathutils.Vector((0, 0.2, 0))

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def ootAddLimbRecursively(
    limbIndex: int,
    skeletonData: str,
    obj: bpy.types.Object,
    armatureObj: bpy.types.Object,
    parentTransform: mathutils.Matrix,
    parentBoneName: str,
    f3dContext: OOTF3DContext,
    useFarLOD: bool,
    enums: List["OOTEnum"],
):
    limbName = f3dContext.getLimbName(limbIndex)
    boneName = f3dContext.getBoneName(limbIndex)
    limb_info = ootGetLimb(skeletonData, limbName, False)
    assert limb_info is not None

    if limb_info.is_lod and useFarLOD:
        dlName = limb_info.far_dl_name
    else:
        dlName = limb_info.dl_name

    # Animations override the root translation, so we just ignore importing them as well.
    if limbIndex == 0:
        translation = [0, 0, 0]
    else:
        translation = [
            hexOrDecInt(limb_info.translationX_str),
            hexOrDecInt(limb_info.translationY_str),
            hexOrDecInt(limb_info.translationZ_str),
        ]

    LIMB_DONE = 0xFF
    nextChildIndex = ootEvaluateLimbExpression(limb_info.nextChildIndex_str, enums)
    nextSiblingIndex = ootEvaluateLimbExpression(limb_info.nextSiblingIndex_str, enums)

    # str(limbIndex) + " " + str(translation) + " " + str(nextChildIndex) + " " + \
    # 	str(nextSiblingIndex) + " " + str(dlName))

    currentTransform = parentTransform @ mathutils.Matrix.Translation(mathutils.Vector(translation))
    f3dContext.matrixData[limbName] = currentTransform
    loadDL = dlName != "NULL"

    ootAddBone(armatureObj, boneName, parentBoneName, currentTransform, loadDL)

    # DLs can access bone transforms not yet processed.
    # Therefore were delay F3D parsing until after skeleton is processed.
    if loadDL:
        f3dContext.dlList.append(OOTDLEntry(dlName, limbIndex))

    isLOD = limb_info.is_lod

    if nextChildIndex != LIMB_DONE:
        isLOD |= ootAddLimbRecursively(
            nextChildIndex, skeletonData, obj, armatureObj, currentTransform, boneName, f3dContext, useFarLOD, enums
        )

    if nextSiblingIndex != LIMB_DONE:
        isLOD |= ootAddLimbRecursively(
            nextSiblingIndex,
            skeletonData,
            obj,
            armatureObj,
            parentTransform,
            parentBoneName,
            f3dContext,
            useFarLOD,
            enums,
        )

    return isLOD


def ootEvaluateLimbExpression(expr: str, enums: List["OOTEnum"]) -> int:
    """
    Evaluate an expression used to define a limb index.
    Limited support for expected expression values:
    - "LIMB_DONE"
    - int value
    - hex value
    - "<ENUM_VALUE> - 1"
    """
    LIMB_DONE = 0xFF

    if expr == "LIMB_DONE":
        return LIMB_DONE

    m = re.search(r"(?P<val>[A-Za-z0-9\_]+)\s*-\s*1", expr)
    if m is not None:
        val = m.group("val")
        index = next((enum.indexOrNone(val) for enum in enums if enum.indexOrNone(val) is not None), None)
        if index is None:
            raise PluginError(f"Couldn't find index for enum value {val}")

        return index - 1

    return hexOrDecInt(expr)


def ootBuildSkeleton(
    skeletonName,
    overlayName,
    skeletonData,
    actorScale,
    removeDoubles,
    importNormals,
    useFarLOD,
    basePath,
    drawLayer,
    isLink,
    flipbookArrayIndex2D: int,
    f3dContext: OOTF3DContext,
):
    lodString = "_lod" if useFarLOD else ""

    # Create new skinned mesh
    mesh = bpy.data.meshes.new(skeletonName + "_mesh" + lodString)
    obj = bpy.data.objects.new(skeletonName + "_mesh" + lodString, mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Create new armature
    armature = bpy.data.armatures.new(skeletonName + lodString)
    armatureObj = bpy.data.objects.new(skeletonName + lodString, armature)
    armatureObj.show_in_front = True
    armatureObj.ootDrawLayer = drawLayer
    # armature.show_names = True

    bpy.context.scene.collection.objects.link(armatureObj)
    bpy.context.view_layer.objects.active = armatureObj
    # bpy.ops.object.mode_set(mode = 'EDIT')

    f3dContext.mat().draw_layer.oot = armatureObj.ootDrawLayer

    # Parse enums, which may be used to link bones by index
    enums = ootGetEnums(skeletonData)

    if overlayName is not None:
        ootReadTextureArrays(basePath, overlayName, skeletonName, f3dContext, isLink, flipbookArrayIndex2D)

    transformMatrix = mathutils.Matrix.Scale(1 / actorScale, 4)
    isLOD = ootAddLimbRecursively(
        0, skeletonData, obj, armatureObj, transformMatrix, None, f3dContext, useFarLOD, enums
    )
    for dlEntry in f3dContext.dlList:
        limbName = f3dContext.getLimbName(dlEntry.limbIndex)
        boneName = f3dContext.getBoneName(dlEntry.limbIndex)
        parseF3D(
            skeletonData,
            dlEntry.dlName,
            f3dContext.matrixData[limbName],
            limbName,
            boneName,
            drawLayer,
            f3dContext,
            True,
        )
        if f3dContext.isBillboard:
            armatureObj.data.bones[boneName].ootBone.dynamicTransform.billboard = True
    f3dContext.createMesh(obj, removeDoubles, importNormals, False)
    armatureObj.location = bpy.context.scene.cursor.location

    # Set bone rotation mode.
    selectSingleObject(armatureObj)
    bpy.ops.object.mode_set(mode="POSE")
    for bone in armatureObj.pose.bones:
        bone.rotation_mode = "XYZ"

    # Apply mesh to armature.
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    deselectAllObjects()
    obj.select_set(True)
    armatureObj.select_set(True)
    bpy.context.view_layer.objects.active = armatureObj
    bpy.ops.object.parent_set(type="ARMATURE")

    applyRotation([armatureObj], math.radians(-90), "X")
    armatureObj.ootActorScale = actorScale / bpy.context.scene.ootBlenderScale

    return isLOD, armatureObj


def ootImportSkeletonC(basePath: str, importSettings: OOTSkeletonImportSettings):
    importPath = bpy.path.abspath(importSettings.customPath)
    isCustomImport = importSettings.isCustom

    if importSettings.mode != "Generic" and not importSettings.isCustom:
        importInfo = ootSkeletonImportDict[importSettings.mode]
        skeletonName = importInfo.skeletonName
        folderName = importInfo.folderName
        overlayName = importInfo.actorOverlayName
        flipbookUses2DArray = importInfo.flipbookArrayIndex2D is not None
        flipbookArrayIndex2D = importInfo.flipbookArrayIndex2D
        isLink = importInfo.isLink
        restPoseData = importInfo.restPoseData
    else:
        skeletonName = importSettings.name
        folderName = importSettings.folder
        overlayName = importSettings.actorOverlayName if not importSettings.isCustom else None
        flipbookUses2DArray = importSettings.flipbookUses2DArray
        flipbookArrayIndex2D = importSettings.flipbookArrayIndex2D if flipbookUses2DArray else None
        isLink = False
        restPoseData = None

    filepaths = [
        ootGetObjectPath(isCustomImport, importPath, folderName, True),
        ootGetObjectHeaderPath(isCustomImport, importPath, folderName, True),
    ]

    if isLink:
        filepaths.append(ootGetObjectPath(isCustomImport, "", "gameplay_keep", True))
        filepaths.append(ootGetObjectHeaderPath(isCustomImport, "", "gameplay_keep", True))

        # starting with zeldaret/oot dbe1a80541173652c344f20226310a8bf90f3086 gameplay_keep is split and committed
        filepaths.append(f"{bpy.context.scene.ootDecompPath}/assets/objects/gameplay_keep/link_textures.c")
        filepaths.append(f"{bpy.context.scene.ootDecompPath}/assets/objects/gameplay_keep/link_textures.h")

        if (Path(bpy.context.scene.ootDecompPath) / "assets/objects" / folderName).exists():
            filepaths.extend(
                [
                    ootGetObjectPath(isCustomImport, importPath, folderName, False),
                    ootGetObjectHeaderPath(isCustomImport, importPath, folderName, False),
                    (
                        f"{bpy.context.scene.ootDecompPath}/include/z64player.h"
                        if bpy.context.scene.fast64.oot.is_z64sceneh_present()
                        else f"{bpy.context.scene.ootDecompPath}/include/player.h"
                    ),
                ]
            )

    for path in filepaths:
        p = Path(path)
        if not p.exists():
            filepaths.remove(path)

    removeDoubles = importSettings.removeDoubles
    importNormals = importSettings.importNormals
    import_animations = importSettings.import_animations
    drawLayer = importSettings.drawLayer

    skeletonData = getImportData(filepaths)
    if overlayName is not None or isLink:
        skeletonData = ootGetIncludedAssetData(basePath, filepaths, skeletonData) + skeletonData

    skel_info = ootGetSkeleton(skeletonData, skeletonName, False)
    assert skel_info is not None
    if skel_info.uses_include:
        ignore_tlut = True
    else:
        ignore_tlut = False

    limbs_info = ootGetLimbs(skeletonData, skel_info.limbs_name, False)

    f3dContext = OOTF3DContext(get_F3D_GBI(), limbs_info.limb_list, basePath)
    f3dContext.mat().draw_layer.oot = drawLayer
    f3dContext.ignore_tlut = ignore_tlut

    actorScale = None

    if overlayName is not None and importSettings.autoDetectActorScale and not importSettings.isCustom:
        actorScale = ootReadActorScale(basePath, overlayName, isLink)

    if actorScale is None:
        actorScale = getOOTScale(importSettings.actorScale)

    isLOD, armatureObj = ootBuildSkeleton(
        skeletonName,
        overlayName,
        skeletonData,
        actorScale,
        removeDoubles,
        importNormals,
        False,
        basePath,
        drawLayer,
        isLink,
        flipbookArrayIndex2D,
        f3dContext,
    )
    if isLOD:
        isLOD, LODArmatureObj = ootBuildSkeleton(
            skeletonName,
            overlayName,
            skeletonData,
            actorScale,
            removeDoubles,
            importNormals,
            True,
            basePath,
            drawLayer,
            isLink,
            flipbookArrayIndex2D,
            f3dContext,
        )
        armatureObj.ootSkeleton.LOD = LODArmatureObj
        LODArmatureObj.location += mathutils.Vector((10, 0, 0))

    f3dContext.deleteMaterialContext()

    if importSettings.applyRestPose and restPoseData is not None:
        applySkeletonRestPose(restPoseData, armatureObj)
        if isLOD:
            applySkeletonRestPose(restPoseData, LODArmatureObj)

    if import_animations:
        if armatureObj is not None:
            selectSingleObject(armatureObj)

        animation_names = get_anim_names(skeletonData, isLink)
        animation_names = list(dict.fromkeys(animation_names))

        # Call quick_import_exec for each animation name
        for animation_name in animation_names:
            quick_import_exec(bpy.context, animation_name)
