import mathutils, bpy, math, os, re
from ..f3d.f3d_gbi import DLFormat, FMesh, TextureExportSettings, ScrollMethod, F3D
from ..f3d.f3d_writer import getInfoDict, GfxList
from ..f3d.f3d_parser import getImportData, parseF3D
from .oot_f3d_writer import ootProcessVertexGroup, writeTextureArraysNew, writeTextureArraysExisting, ootReadActorScale

from ..utility import (
    PluginError,
    CData,
    VertexWeightError,
    getDeclaration,
    hexOrDecInt,
    applyRotation,
    getGroupIndexFromname,
    writeFile,
    readFile,
    writeCData,
    toAlnum,
    setOrigin,
    getGroupNameFromIndex,
    attemptModifierApply,
    cleanupDuplicatedObjects,
    yUpToZUp,
)

from .oot_model_classes import (
    OOTVertexGroupInfo,
    OOTModel,
    OOTGfxFormatter,
    OOTF3DContext,
    ootGetIncludedAssetData,
)

from .oot_utility import (
    ootGetObjectPath,
    checkEmptyName,
    checkForStartBone,
    getStartBone,
    getSortedChildren,
    ootGetPath,
    addIncludeFiles,
    getOOTScale,
)

from ..utility_anim import armatureApplyWithMesh
from .oot_texture_array import ootReadTextureArrays
from .oot_skeleton_import_data import applySkeletonRestPose, ootSkeletonImportDict
from .skeleton.properties import OOTSkeletonExportSettings, OOTSkeletonImportSettings


class OOTSkeleton:
    def __init__(self, name):
        self.name = name
        self.segmentID = None
        self.limbRoot = None
        self.hasLOD = False

    def createLimbList(self):
        if self.limbRoot is None:
            return []

        limbList = []
        self.limbRoot.getList(limbList)
        self.limbRoot.setLinks()
        return limbList

    def getNumDLs(self):
        if self.limbRoot is not None:
            return self.limbRoot.getNumDLs()
        else:
            return 0

    def getNumLimbs(self):
        if self.limbRoot is not None:
            return self.limbRoot.getNumLimbs()
        else:
            return 0

    def isFlexSkeleton(self):
        if self.limbRoot is not None:
            return self.limbRoot.isFlexSkeleton()
        else:
            return False

    def limbsName(self):
        return self.name + "Limbs"

    def toC(self):
        limbData = CData()
        data = CData()

        if self.limbRoot is None:
            return data

        limbList = self.createLimbList()
        isFlex = self.isFlexSkeleton()

        data.source += "void* " + self.limbsName() + "[" + str(self.getNumLimbs()) + "] = {\n"
        for limb in limbList:
            limbData.source += limb.toC(self.hasLOD)
            data.source += "\t&" + limb.name() + ",\n"
        limbData.source += "\n"
        data.source += "};\n\n"

        if isFlex:
            data.source += (
                "FlexSkeletonHeader "
                + self.name
                + " = { "
                + self.limbsName()
                + ", "
                + str(self.getNumLimbs())
                + ", "
                + str(self.getNumDLs())
                + " };\n\n"
            )
            data.header = "extern FlexSkeletonHeader " + self.name + ";\n"
        else:
            data.source += (
                "SkeletonHeader " + self.name + " = { " + self.limbsName() + ", " + str(self.getNumLimbs()) + " };\n\n"
            )
            data.header = "extern SkeletonHeader " + self.name + ";\n"

        for limb in limbList:
            name = (self.name + "_" + toAlnum(limb.boneName)).upper()
            if limb.index == 0:
                data.header += "#define " + name + "_POS_LIMB 0\n"
                data.header += "#define " + name + "_ROT_LIMB 1\n"
            else:
                data.header += "#define " + name + "_LIMB " + str(limb.index + 1) + "\n"
        data.header += "#define " + self.name.upper() + "_NUM_LIMBS " + str(len(limbList) + 1) + "\n"

        limbData.append(data)

        return limbData


class OOTDLReference:
    def __init__(self, name: str):
        self.name = name


class OOTLimb:
    def __init__(
        self,
        skeletonName: str,
        boneName: str,
        index: int,
        translation: mathutils.Vector,
        DL: GfxList | OOTDLReference,
        lodDL: GfxList | OOTDLReference,
    ):
        self.skeletonName = skeletonName
        self.boneName = boneName
        self.translation = translation
        self.firstChildIndex = 0xFF
        self.nextSiblingIndex = 0xFF
        self.DL = DL
        self.lodDL = lodDL

        self.isFlex = False
        self.index = index
        self.children = []
        self.inverseRotation = None

    def toC(self, isLOD):
        if not isLOD:
            data = "StandardLimb "
        else:
            data = "LodLimb "

        data += (
            self.name()
            + " = { "
            + "{ "
            + str(int(round(self.translation[0])))
            + ", "
            + str(int(round(self.translation[1])))
            + ", "
            + str(int(round(self.translation[2])))
            + " }, "
            + str(self.firstChildIndex)
            + ", "
            + str(self.nextSiblingIndex)
            + ", "
        )

        if not isLOD:
            data += self.DL.name if self.DL is not None else "NULL"
        else:
            data += (
                "{ "
                + (self.DL.name if self.DL is not None else "NULL")
                + ", "
                + (self.lodDL.name if self.lodDL is not None else "NULL")
                + " }"
            )

        data += " };\n"

        return data

    def name(self):
        return self.skeletonName + "Limb_" + format(self.index, "03")

    def getNumLimbs(self):
        numLimbs = 1
        for child in self.children:
            numLimbs += child.getNumLimbs()
        return numLimbs

    def getNumDLs(self):
        numDLs = 0
        if self.DL is not None or self.lodDL is not None:
            numDLs += 1

        for child in self.children:
            numDLs += child.getNumDLs()

        return numDLs

    def isFlexSkeleton(self):
        if self.isFlex:
            return True
        else:
            for child in self.children:
                if child.isFlexSkeleton():
                    return True
            return False

    def getList(self, limbList):
        # Like ootProcessBone, this must be in depth-first order to match the
        # OoT SkelAnime draw code, so the bones are listed in the file in the
        # same order as they are drawn. This is needed to enable the programmer
        # to get the limb indices and to enable optimization between limbs.
        limbList.append(self)
        for child in self.children:
            child.getList(limbList)

    def setLinks(self):
        if len(self.children) > 0:
            self.firstChildIndex = self.children[0].index
        for i in range(len(self.children)):
            if i < len(self.children) - 1:
                self.children[i].nextSiblingIndex = self.children[i + 1].index
            self.children[i].setLinks()
        # self -> child -> sibling


def getGroupIndices(meshInfo, armatureObj, meshObj, rootGroupIndex):
    meshInfo.vertexGroupInfo = OOTVertexGroupInfo()
    for vertex in meshObj.data.vertices:
        meshInfo.vertexGroupInfo.vertexGroups[vertex.index] = getGroupIndexOfVert(
            vertex, armatureObj, meshObj, rootGroupIndex
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


def ootDuplicateArmatureAndRemoveRotations(originalArmatureObj: bpy.types.Object):
    # Duplicate objects to apply scale / modifiers / linked data
    bpy.ops.object.select_all(action="DESELECT")

    for originalMeshObj in [obj for obj in originalArmatureObj.children if isinstance(obj.data, bpy.types.Mesh)]:
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


def ootConvertArmatureToSkeletonWithoutMesh(originalArmatureObj, convertTransformMatrix, name):
    skeleton, fModel = ootConvertArmatureToSkeleton(
        originalArmatureObj, convertTransformMatrix, None, name, False, True, "Opaque", False
    )
    return skeleton


def ootConvertArmatureToSkeletonWithMesh(
    originalArmatureObj, convertTransformMatrix, fModel, name, convertTextureData, drawLayer, optimize
):
    return ootConvertArmatureToSkeleton(
        originalArmatureObj, convertTransformMatrix, fModel, name, convertTextureData, False, drawLayer, optimize
    )


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


def ootConvertArmatureToSkeleton(
    originalArmatureObj,
    convertTransformMatrix,
    fModel,
    name,
    convertTextureData,
    skeletonOnly,
    drawLayer,
    optimize: bool,
):
    checkEmptyName(name)

    armatureObj, meshObjs = ootDuplicateArmatureAndRemoveRotations(originalArmatureObj)

    try:
        skeleton = OOTSkeleton(name)

        if len(armatureObj.children) == 0:
            raise PluginError("No mesh parented to armature.")

        # startBoneNames = sorted([bone.name for bone in armatureObj.data.bones if bone.parent is None])
        # startBoneName = startBoneNames[0]
        checkForStartBone(armatureObj)
        startBoneName = getStartBone(armatureObj)
        meshObj = meshObjs[0]

        meshInfo = getInfoDict(meshObj)
        getGroupIndices(meshInfo, armatureObj, meshObj, getGroupIndexFromname(meshObj, startBoneName))

        convertTransformMatrix = convertTransformMatrix @ mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()

        # for i in range(len(startBoneNames)):
        # 	startBoneName = startBoneNames[i]
        ootProcessBone(
            fModel,
            startBoneName,
            skeleton,
            0,
            meshObj,
            armatureObj,
            convertTransformMatrix,
            meshInfo,
            convertTextureData,
            name,
            skeletonOnly,
            drawLayer,
            None,
            optimize,
        )

        cleanupDuplicatedObjects(meshObjs + [armatureObj])
        originalArmatureObj.select_set(True)
        bpy.context.view_layer.objects.active = originalArmatureObj

        return skeleton, fModel
    except Exception as e:
        cleanupDuplicatedObjects(meshObjs + [armatureObj])
        originalArmatureObj.select_set(True)
        bpy.context.view_layer.objects.active = originalArmatureObj
        raise Exception(str(e))


def ootProcessBone(
    fModel,
    boneName,
    parentLimb,
    nextIndex,
    meshObj,
    armatureObj,
    convertTransformMatrix,
    meshInfo,
    convertTextureData,
    namePrefix,
    skeletonOnly,
    drawLayer,
    lastMaterialName,
    optimize: bool,
):
    bone = armatureObj.data.bones[boneName]
    if bone.parent is not None:
        transform = convertTransformMatrix @ bone.parent.matrix_local.inverted() @ bone.matrix_local
    else:
        transform = convertTransformMatrix @ bone.matrix_local

    translate, rotate, scale = transform.decompose()

    groupIndex = getGroupIndexFromname(meshObj, boneName)

    meshInfo.vertexGroupInfo.vertexGroupToLimb[groupIndex] = nextIndex

    if skeletonOnly:
        mesh = None
        hasSkinnedFaces = None
    else:
        mesh, hasSkinnedFaces, lastMaterialName = ootProcessVertexGroup(
            fModel,
            meshObj,
            boneName,
            convertTransformMatrix,
            armatureObj,
            namePrefix,
            meshInfo,
            drawLayer,
            convertTextureData,
            lastMaterialName,
            optimize,
        )

    if bone.ootBone.boneType == "Custom DL":
        if mesh is not None:
            raise PluginError(
                bone.name
                + " is set to use a custom DL but still has geometry assigned to it. Remove this geometry from this bone."
            )
        else:
            # Dummy data, only used so that name is set correctly
            mesh = FMesh(bone.ootBone.customDLName, DLFormat.Static)

    DL = None
    if mesh is not None:
        if not bone.use_deform:
            raise PluginError(
                bone.name
                + " has vertices in its vertex group but is not set to deformable. Make sure to enable deform on this bone."
            )
        DL = mesh.draw

    if isinstance(parentLimb, OOTSkeleton):
        skeleton = parentLimb
        limb = OOTLimb(skeleton.name, boneName, nextIndex, translate, DL, None)
        skeleton.limbRoot = limb
    else:
        limb = OOTLimb(parentLimb.skeletonName, boneName, nextIndex, translate, DL, None)
        parentLimb.children.append(limb)

    limb.isFlex = hasSkinnedFaces
    nextIndex += 1

    # This must be in depth-first order to match the OoT SkelAnime draw code, so
    # the bones are listed in the file in the same order as they are drawn. This
    # is needed to enable the programmer to get the limb indices and to enable
    # optimization between limbs.
    childrenNames = getSortedChildren(armatureObj, bone)
    for childName in childrenNames:
        nextIndex, lastMaterialName = ootProcessBone(
            fModel,
            childName,
            limb,
            nextIndex,
            meshObj,
            armatureObj,
            convertTransformMatrix,
            meshInfo,
            convertTextureData,
            namePrefix,
            skeletonOnly,
            drawLayer,
            lastMaterialName,
            optimize,
        )

    return nextIndex, lastMaterialName


def ootConvertArmatureToC(
    originalArmatureObj: bpy.types.Object,
    convertTransformMatrix: mathutils.Matrix,
    f3dType: str,
    isHWv1: bool,
    DLFormat: DLFormat,
    savePNG: bool,
    drawLayer: str,
    settings: OOTSkeletonExportSettings,
):
    if settings.mode != "Generic" and not settings.isCustom:
        importInfo = ootSkeletonImportDict[settings.mode]
        skeletonName = importInfo.skeletonName
        filename = skeletonName
        folderName = importInfo.folderName
        overlayName = importInfo.actorOverlayName
        flipbookUses2DArray = importInfo.flipbookArrayIndex2D is not None
        flipbookArrayIndex2D = importInfo.flipbookArrayIndex2D
        isLink = importInfo.isLink
    else:
        skeletonName = toAlnum(originalArmatureObj.name)
        filename = settings.filename if settings.isCustomFilename else skeletonName
        folderName = settings.folder
        overlayName = settings.actorOverlayName if not settings.isCustom else None
        flipbookUses2DArray = settings.flipbookUses2DArray
        flipbookArrayIndex2D = settings.flipbookArrayIndex2D if flipbookUses2DArray else None
        isLink = False

    exportPath = bpy.path.abspath(settings.customPath)
    isCustomExport = settings.isCustom
    removeVanillaData = settings.removeVanillaData
    optimize = settings.optimize

    fModel = OOTModel(f3dType, isHWv1, skeletonName, DLFormat, drawLayer)
    skeleton, fModel = ootConvertArmatureToSkeletonWithMesh(
        originalArmatureObj, convertTransformMatrix, fModel, skeletonName, not savePNG, drawLayer, optimize
    )

    if originalArmatureObj.ootSkeleton.LOD is not None:
        lodSkeleton, fModel = ootConvertArmatureToSkeletonWithMesh(
            originalArmatureObj.ootSkeleton.LOD,
            convertTransformMatrix,
            fModel,
            skeletonName + "_lod",
            not savePNG,
            drawLayer,
            optimize,
        )
    else:
        lodSkeleton = None

    if lodSkeleton is not None:
        skeleton.hasLOD = True
        limbList = skeleton.createLimbList()
        lodLimbList = lodSkeleton.createLimbList()

        if len(limbList) != len(lodLimbList):
            raise PluginError(
                originalArmatureObj.name
                + " cannot use "
                + originalArmatureObj.ootSkeleton.LOD.name
                + "as LOD because they do not have the same bone structure."
            )

        for i in range(len(limbList)):
            limbList[i].lodDL = lodLimbList[i].DL
            limbList[i].isFlex |= lodLimbList[i].isFlex

    data = CData()
    data.source += '#include "ultra64.h"\n#include "global.h"\n'
    if not isCustomExport:
        data.source += '#include "' + folderName + '.h"\n\n'
    else:
        data.source += "\n"

    path = ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, True)
    includeDir = settings.customAssetIncludeDir if settings.isCustom else f"assets/objects/{folderName}"
    exportData = fModel.to_c(
        TextureExportSettings(False, savePNG, includeDir, path), OOTGfxFormatter(ScrollMethod.Vertex)
    )
    skeletonC = skeleton.toC()

    data.append(exportData.all())
    data.append(skeletonC)

    if isCustomExport:
        textureArrayData = writeTextureArraysNew(fModel, flipbookArrayIndex2D)
        data.append(textureArrayData)

    writeCData(data, os.path.join(path, filename + ".h"), os.path.join(path, filename + ".c"))

    if not isCustomExport:
        writeTextureArraysExisting(bpy.context.scene.ootDecompPath, overlayName, isLink, flipbookArrayIndex2D, fModel)
        addIncludeFiles(folderName, path, filename)
        if removeVanillaData:
            ootRemoveSkeleton(path, folderName, skeletonName)


class OOTDLEntry:
    def __init__(self, dlName, limbIndex):
        self.dlName = dlName
        self.limbIndex = limbIndex


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

    filepaths = [ootGetObjectPath(isCustomImport, importPath, folderName)]

    removeDoubles = importSettings.removeDoubles
    importNormals = importSettings.importNormals
    drawLayer = importSettings.drawLayer

    skeletonData = getImportData(filepaths)
    if overlayName is not None or isLink:
        skeletonData = ootGetIncludedAssetData(basePath, filepaths, skeletonData) + skeletonData

    matchResult = ootGetSkeleton(skeletonData, skeletonName, False)
    limbsName = matchResult.group(2)

    matchResult = ootGetLimbs(skeletonData, limbsName, False)
    limbsData = matchResult.group(2)
    limbList = [entry.strip()[1:] for entry in limbsData.split(",") if entry.strip() != ""]

    f3dContext = OOTF3DContext(F3D("F3DEX2/LX2", False), limbList, basePath)
    f3dContext.mat().draw_layer.oot = drawLayer

    if overlayName is not None and importSettings.autoDetectActorScale:
        actorScale = ootReadActorScale(basePath, overlayName, isLink)
    else:
        actorScale = getOOTScale(importSettings.actorScale)

    # print(limbList)
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

    if overlayName is not None:
        ootReadTextureArrays(basePath, overlayName, skeletonName, f3dContext, isLink, flipbookArrayIndex2D)

    transformMatrix = mathutils.Matrix.Scale(1 / actorScale, 4)
    isLOD = ootAddLimbRecursively(0, skeletonData, obj, armatureObj, transformMatrix, None, f3dContext, useFarLOD)
    for dlEntry in f3dContext.dlList:
        limbName = f3dContext.getLimbName(dlEntry.limbIndex)
        boneName = f3dContext.getBoneName(dlEntry.limbIndex)
        parseF3D(
            skeletonData,
            dlEntry.dlName,
            f3dContext.matrixData[limbName],
            limbName,
            boneName,
            "oot",
            drawLayer,
            f3dContext,
            True,
        )
        if f3dContext.isBillboard:
            armatureObj.data.bones[boneName].ootBone.dynamicTransform.billboard = True
    f3dContext.createMesh(obj, removeDoubles, importNormals, False)
    armatureObj.location = bpy.context.scene.cursor.location

    # Set bone rotation mode.
    bpy.ops.object.select_all(action="DESELECT")
    armatureObj.select_set(True)
    bpy.context.view_layer.objects.active = armatureObj
    bpy.ops.object.mode_set(mode="POSE")
    for bone in armatureObj.pose.bones:
        bone.rotation_mode = "XYZ"

    # Apply mesh to armature.
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    armatureObj.select_set(True)
    bpy.context.view_layer.objects.active = armatureObj
    bpy.ops.object.parent_set(type="ARMATURE")

    applyRotation([armatureObj], math.radians(-90), "X")
    armatureObj.ootActorScale = actorScale / bpy.context.scene.ootBlenderScale

    return isLOD, armatureObj


def ootAddBone(armatureObj, boneName, parentBoneName, currentTransform, loadDL):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = armatureObj
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
):
    limbName = f3dContext.getLimbName(limbIndex)
    boneName = f3dContext.getBoneName(limbIndex)
    matchResult = ootGetLimb(skeletonData, limbName, False)

    isLOD = matchResult.lastindex > 6

    if isLOD and useFarLOD:
        dlName = matchResult.group(7)
    else:
        dlName = matchResult.group(6)

    # Animations override the root translation, so we just ignore importing them as well.
    if limbIndex == 0:
        translation = [0, 0, 0]
    else:
        translation = [
            hexOrDecInt(matchResult.group(1)),
            hexOrDecInt(matchResult.group(2)),
            hexOrDecInt(matchResult.group(3)),
        ]

    LIMB_DONE = 0xFF
    nextChildIndexStr = matchResult.group(4)
    nextChildIndex = LIMB_DONE if nextChildIndexStr == "LIMB_DONE" else hexOrDecInt(nextChildIndexStr)
    nextSiblingIndexStr = matchResult.group(5)
    nextSiblingIndex = LIMB_DONE if nextSiblingIndexStr == "LIMB_DONE" else hexOrDecInt(nextSiblingIndexStr)

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

    if nextChildIndex != LIMB_DONE:
        isLOD |= ootAddLimbRecursively(
            nextChildIndex, skeletonData, obj, armatureObj, currentTransform, boneName, f3dContext, useFarLOD
        )

    if nextSiblingIndex != LIMB_DONE:
        isLOD |= ootAddLimbRecursively(
            nextSiblingIndex, skeletonData, obj, armatureObj, parentTransform, parentBoneName, f3dContext, useFarLOD
        )

    return isLOD


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
