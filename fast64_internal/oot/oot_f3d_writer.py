import bpy, os, mathutils, re
from bpy.utils import register_class, unregister_class
from ..panels import OOT_Panel
from ..utility import (
    PluginError,
    CData,
    prop_split,
    writeCData,
    raisePluginError,
    getGroupIndexFromname,
    toAlnum,
    readFile,
    writeFile,
)
from ..f3d.f3d_parser import importMeshC, ootEnumDrawLayers, getImportData
from ..f3d.f3d_gbi import DLFormat, TextureExportSettings, ScrollMethod, F3D

from ..f3d.f3d_writer import (
    TriangleConverterInfo,
    removeDL,
    saveStaticModel,
    getInfoDict,
    checkForF3dMaterialInFaces,
    saveOrGetF3DMaterial,
    saveMeshWithLargeTexturesByFaces,
    saveMeshByFaces,
)

from .oot_utility import (
    OOTObjectCategorizer,
    ootGetObjectPath,
    ootDuplicateHierarchy,
    ootCleanupScene,
    ootGetPath,
    addIncludeFiles,
    replaceMatchContent,
    getOOTScale,
)

from .oot_model_classes import (
    OOTF3DContext,
    OOTTriangleConverterInfo,
    OOTModel,
    OOTGfxFormatter,
    OOTDynamicTransformProperty,
    ootGetActorData,
    ootGetLinkData,
    ootGetIncludedAssetData,
)

from .oot_texture_array import TextureFlipbook, ootReadTextureArrays
from ..f3d.flipbook import flipbook_to_c, flipbook_2d_to_c, flipbook_data_to_c
from ..f3d.f3d_material import createF3DMat, F3DMaterial_UpdateLock, update_preset_manual

# Creates a semi-transparent solid color material (cached)
def getColliderMat(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    if "oot_collision_mat_base" not in bpy.data.materials:
        baseMat = createF3DMat(None, preset="oot_shaded_texture_transparent", index=0)
        with F3DMaterial_UpdateLock(baseMat) as lockedMat:
            lockedMat.name = name
            lockedMat.f3d_mat.combiner1.A = "0"
            lockedMat.f3d_mat.combiner1.C = "0"
            lockedMat.f3d_mat.combiner1.D = "SHADE"
            lockedMat.f3d_mat.combiner1.D_alpha = "1"
            lockedMat.f3d_mat.prim_color = color
            update_preset_manual(lockedMat, bpy.context)

    if name not in bpy.data.materials:
        baseMat = bpy.data.materials["oot_collision_mat_base"]
        baseMat.f3d_update_flag = True
        newMat = baseMat.copy()
        baseMat.f3d_update_flag = False
        newMat.f3d_mat.prim_color = color
        return newMat
    else:
        return bpy.data.materials[name]


class OOTDLExportSettings(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="DL Name", default="gBoulderFragmentsDL")
    folder: bpy.props.StringProperty(name="DL Folder", default="gameplay_keep")
    customPath: bpy.props.StringProperty(name="Custom DL Path", subtype="FILE_PATH")
    isCustom: bpy.props.BoolProperty(name="Use Custom Path")
    removeVanillaData: bpy.props.BoolProperty(name="Replace Vanilla DLs")
    drawLayer: bpy.props.EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)
    actorOverlayName: bpy.props.StringProperty(name="Overlay", default="")
    flipbookUses2DArray: bpy.props.BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: bpy.props.IntProperty(name="Index if 2D Array", default=0, min=0)
    customAssetIncludeDir: bpy.props.StringProperty(
        name="Asset Include Directory",
        default="assets/objects/gameplay_keep",
        description="Used in #include for including image files",
    )


class OOTDLImportSettings(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="DL Name", default="gBoulderFragmentsDL")
    folder: bpy.props.StringProperty(name="DL Folder", default="gameplay_keep")
    customPath: bpy.props.StringProperty(name="Custom DL Path", subtype="FILE_PATH")
    isCustom: bpy.props.BoolProperty(name="Use Custom Path")
    removeDoubles: bpy.props.BoolProperty(name="Remove Doubles", default=True)
    importNormals: bpy.props.BoolProperty(name="Import Normals", default=True)
    drawLayer: bpy.props.EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)
    actorOverlayName: bpy.props.StringProperty(name="Overlay", default="")
    flipbookUses2DArray: bpy.props.BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: bpy.props.IntProperty(name="Index if 2D Array", default=0, min=0)
    autoDetectActorScale: bpy.props.BoolProperty(name="Auto Detect Actor Scale", default=True)
    actorScale: bpy.props.FloatProperty(name="Actor Scale", min=0, default=100)


# returns:
# 	mesh,
# 	anySkinnedFaces (to determine if skeleton should be flex)
def ootProcessVertexGroup(
    fModel,
    meshObj,
    vertexGroup,
    convertTransformMatrix,
    armatureObj,
    namePrefix,
    meshInfo,
    drawLayerOverride,
    convertTextureData,
    lastMaterialName,
    optimize: bool,
):
    if not optimize:
        lastMaterialName = None

    mesh = meshObj.data
    currentGroupIndex = getGroupIndexFromname(meshObj, vertexGroup)
    nextDLIndex = len(meshInfo.vertexGroupInfo.vertexGroupToMatrixIndex)
    vertIndices = [
        vert.index
        for vert in meshObj.data.vertices
        if meshInfo.vertexGroupInfo.vertexGroups[vert.index] == currentGroupIndex
    ]

    if len(vertIndices) == 0:
        print("No vert indices in " + vertexGroup)
        return None, False, lastMaterialName

    bone = armatureObj.data.bones[vertexGroup]

    # dict of material_index keys to face array values
    groupFaces = {}

    hasSkinnedFaces = False

    handledFaces = []
    anyConnectedToUnhandledBone = False
    for vertIndex in vertIndices:
        if vertIndex not in meshInfo.vert:
            continue
        for face in meshInfo.vert[vertIndex]:
            # Ignore repeat faces
            if face in handledFaces:
                continue

            connectedToUnhandledBone = False

            # A Blender loop is interpreted as face + loop index
            for i in range(3):
                faceVertIndex = face.vertices[i]
                vertGroupIndex = meshInfo.vertexGroupInfo.vertexGroups[faceVertIndex]
                if vertGroupIndex != currentGroupIndex:
                    hasSkinnedFaces = True
                if vertGroupIndex not in meshInfo.vertexGroupInfo.vertexGroupToLimb:
                    # Connected to a bone not processed yet
                    # These skinned faces will be handled by that limb
                    connectedToUnhandledBone = True
                    anyConnectedToUnhandledBone = True
                    break

            if connectedToUnhandledBone:
                continue

            if face.material_index not in groupFaces:
                groupFaces[face.material_index] = []
            groupFaces[face.material_index].append(face)

            handledFaces.append(face)

    if len(groupFaces) == 0:
        print("No faces in " + vertexGroup)

        # OOT will only allocate matrix if DL exists.
        # This doesn't handle case where vertices belong to a limb, but not triangles.
        # Therefore we create a dummy DL
        if anyConnectedToUnhandledBone:
            fMesh = fModel.addMesh(vertexGroup, namePrefix, drawLayerOverride, False, bone)
            fModel.endDraw(fMesh, bone)
            meshInfo.vertexGroupInfo.vertexGroupToMatrixIndex[currentGroupIndex] = nextDLIndex
            return fMesh, False, lastMaterialName
        else:
            return None, False, lastMaterialName

    meshInfo.vertexGroupInfo.vertexGroupToMatrixIndex[currentGroupIndex] = nextDLIndex
    triConverterInfo = OOTTriangleConverterInfo(meshObj, armatureObj.data, fModel.f3d, convertTransformMatrix, meshInfo)

    if optimize:
        # If one of the materials we need to draw is the currently loaded material,
        # do this one first.
        newGroupFaces = {
            material_index: faces
            for material_index, faces in groupFaces.items()
            if meshObj.material_slots[material_index].material.name == lastMaterialName
        }
        newGroupFaces.update(groupFaces)
        groupFaces = newGroupFaces

    # Usually we would separate DLs into different draw layers.
    # however it seems like OOT skeletons don't have this ability.
    # Therefore we always use the drawLayerOverride as the draw layer key.
    # This means everything will be saved to one mesh.
    fMesh = fModel.addMesh(vertexGroup, namePrefix, drawLayerOverride, False, bone)

    for material_index, faces in groupFaces.items():
        material = meshObj.material_slots[material_index].material
        checkForF3dMaterialInFaces(meshObj, material)
        fMaterial, texDimensions = saveOrGetF3DMaterial(
            material, fModel, meshObj, drawLayerOverride, convertTextureData
        )

        if fMaterial.useLargeTextures:
            currentGroupIndex = saveMeshWithLargeTexturesByFaces(
                material,
                faces,
                fModel,
                fMesh,
                meshObj,
                drawLayerOverride,
                convertTextureData,
                currentGroupIndex,
                triConverterInfo,
                None,
                None,
                lastMaterialName,
            )
        else:
            currentGroupIndex = saveMeshByFaces(
                material,
                faces,
                fModel,
                fMesh,
                meshObj,
                drawLayerOverride,
                convertTextureData,
                currentGroupIndex,
                triConverterInfo,
                None,
                None,
                lastMaterialName,
            )

        lastMaterialName = material.name if optimize else None

    fModel.endDraw(fMesh, bone)

    return fMesh, hasSkinnedFaces, lastMaterialName


ootEnumObjectMenu = [
    ("Scene", "Parent Scene Settings", "Scene"),
    ("Room", "Parent Room Settings", "Room"),
]


def ootConvertMeshToC(
    originalObj: bpy.types.Object,
    finalTransform: mathutils.Matrix,
    f3dType: str,
    isHWv1: bool,
    DLFormat: DLFormat,
    saveTextures: bool,
    settings: OOTDLExportSettings,
):
    folderName = settings.folder
    exportPath = bpy.path.abspath(settings.customPath)
    isCustomExport = settings.isCustom
    drawLayer = settings.drawLayer
    removeVanillaData = settings.removeVanillaData
    name = toAlnum(settings.name)
    overlayName = settings.actorOverlayName
    flipbookUses2DArray = settings.flipbookUses2DArray
    flipbookArrayIndex2D = settings.flipbookArrayIndex2D if flipbookUses2DArray else None

    try:
        obj, allObjs = ootDuplicateHierarchy(originalObj, None, False, OOTObjectCategorizer())

        fModel = OOTModel(f3dType, isHWv1, name, DLFormat, drawLayer)
        triConverterInfo = TriangleConverterInfo(obj, None, fModel.f3d, finalTransform, getInfoDict(obj))
        fMeshes = saveStaticModel(
            triConverterInfo, fModel, obj, finalTransform, fModel.name, not saveTextures, False, "oot"
        )

        # Since we provide a draw layer override, there should only be one fMesh.
        for drawLayer, fMesh in fMeshes.items():
            fMesh.draw.name = name

        ootCleanupScene(originalObj, allObjs)

    except Exception as e:
        ootCleanupScene(originalObj, allObjs)
        raise Exception(str(e))

    data = CData()
    data.source += '#include "ultra64.h"\n#include "global.h"\n'
    if not isCustomExport:
        data.source += '#include "' + folderName + '.h"\n\n'
    else:
        data.source += "\n"

    path = ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, True)
    includeDir = settings.customAssetIncludeDir if settings.isCustom else f"assets/objects/{folderName}"
    exportData = fModel.to_c(
        TextureExportSettings(False, saveTextures, includeDir, path), OOTGfxFormatter(ScrollMethod.Vertex)
    )

    data.append(exportData.all())

    if isCustomExport:
        textureArrayData = writeTextureArraysNew(fModel, flipbookArrayIndex2D)
        data.append(textureArrayData)

    writeCData(data, os.path.join(path, name + ".h"), os.path.join(path, name + ".c"))

    if not isCustomExport:
        writeTextureArraysExisting(bpy.context.scene.ootDecompPath, overlayName, False, flipbookArrayIndex2D, fModel)
        addIncludeFiles(folderName, path, name)
        if removeVanillaData:
            headerPath = os.path.join(path, folderName + ".h")
            sourcePath = os.path.join(path, folderName + ".c")
            removeDL(sourcePath, headerPath, name)


def writeTextureArraysNew(fModel: OOTModel, arrayIndex: int):
    textureArrayData = CData()
    for flipbook in fModel.flipbooks:
        if flipbook.exportMode == "Array":
            if arrayIndex is not None:
                textureArrayData.source += flipbook_2d_to_c(flipbook, True, arrayIndex + 1) + "\n"
            else:
                textureArrayData.source += flipbook_to_c(flipbook, True) + "\n"
    return textureArrayData


def getActorFilepath(basePath: str, overlayName: str | None, isLink: bool, checkDataPath: bool = False):
    if isLink:
        actorFilePath = os.path.join(basePath, f"src/code/z_player_lib.c")
    else:
        actorFilePath = os.path.join(basePath, f"src/overlays/actors/{overlayName}/z_{overlayName[4:].lower()}.c")
        actorFileDataPath = f"{actorFilePath[:-2]}_data.c"  # some bosses store texture arrays here

        if checkDataPath and os.path.exists(actorFileDataPath):
            actorFilePath = actorFileDataPath

    return actorFilePath


def writeTextureArraysExisting(
    exportPath: str, overlayName: str, isLink: bool, flipbookArrayIndex2D: int, fModel: OOTModel
):
    actorFilePath = getActorFilepath(exportPath, overlayName, isLink, True)

    if not os.path.exists(actorFilePath):
        print(f"{actorFilePath} not found, ignoring texture array writing.")
        return

    actorData = readFile(actorFilePath)
    newData = actorData

    for flipbook in fModel.flipbooks:
        if flipbook.exportMode == "Array":
            if flipbookArrayIndex2D is None:
                newData = writeTextureArraysExisting1D(newData, flipbook, "")
            else:
                newData = writeTextureArraysExisting2D(newData, flipbook, flipbookArrayIndex2D)

    if newData != actorData:
        writeFile(actorFilePath, newData)


def writeTextureArraysExisting1D(data: str, flipbook: TextureFlipbook, additionalIncludes: str) -> str:
    newData = data
    arrayMatch = re.search(
        r"(static\s*)?void\s*\*\s*" + re.escape(flipbook.name) + r"\s*\[\s*\]\s*=\s*\{(((?!\}).)*)\}\s*;",
        newData,
        flags=re.DOTALL,
    )

    # replace array if found
    if arrayMatch:
        newArrayData = flipbook_to_c(flipbook, arrayMatch.group(1))
        newData = newData[: arrayMatch.start(0)] + newArrayData + newData[arrayMatch.end(0) :]

        # otherwise, add to end of asset includes
    else:
        newArrayData = flipbook_to_c(flipbook, True)

    # get last asset include
    includeMatch = None
    for includeMatchItem in re.finditer(r"\#include\s*\"assets/.*?\"\s*?\n", newData, flags=re.DOTALL):
        includeMatch = includeMatchItem
    if includeMatch:
        newData = (
            newData[: includeMatch.end(0)]
            + additionalIncludes
            + ((newArrayData + "\n") if not arrayMatch else "")
            + newData[includeMatch.end(0) :]
        )
    else:
        newData = (additionalIncludes + newData + newArrayData + "\n") if not arrayMatch else newData

    return newData


# for flipbook textures, we only replace one element of the 2D array.
def writeTextureArraysExisting2D(data: str, flipbook: TextureFlipbook, flipbookArrayIndex2D: int) -> str:
    newData = data

    # for !AVOID_UB, Link has textures in 2D Arrays
    array2DMatch = re.search(
        r"(static\s*)?void\s*\*\s*"
        + re.escape(flipbook.name)
        + r"\s*\[\s*\]\s*\[\s*[0-9a-fA-Fx]*\s*\]\s*=\s*\{(.*?)\}\s*;",
        newData,
        flags=re.DOTALL,
    )

    newArrayData = "{ " + flipbook_data_to_c(flipbook) + " }"

    # build a list of arrays here
    # replace existing element if list is large enough
    # otherwise, pad list with repeated arrays
    if array2DMatch:
        arrayMatchData = [
            arrayMatch.group(0) for arrayMatch in re.finditer(r"\{(.*?)\}", array2DMatch.group(2), flags=re.DOTALL)
        ]

        if flipbookArrayIndex2D >= len(arrayMatchData):
            while len(arrayMatchData) <= flipbookArrayIndex2D:
                arrayMatchData.append(newArrayData)
        else:
            arrayMatchData[flipbookArrayIndex2D] = newArrayData

        newArray2DData = ",\n".join([item for item in arrayMatchData])
        newData = replaceMatchContent(newData, newArray2DData, array2DMatch, 2)

        # otherwise, add to end of asset includes
    else:
        arrayMatchData = [newArrayData] * (flipbookArrayIndex2D + 1)
        newArray2DData = ",\n".join([item for item in arrayMatchData])

        # get last asset include
        includeMatch = None
        for includeMatchItem in re.finditer(r"\#include\s*\"assets/.*?\"\s*?\n", newData, flags=re.DOTALL):
            includeMatch = includeMatchItem
        if includeMatch:
            newData = newData[: includeMatch.end(0)] + newArray2DData + "\n" + newData[includeMatch.end(0) :]
        else:
            newData += newArray2DData + "\n"

    return newData


# Note this does not work well with actors containing multiple "parts". (z_en_honotrap)
def ootReadActorScale(basePath: str, overlayName: str, isLink: bool) -> float:
    if not isLink:
        actorData = ootGetActorData(basePath, overlayName)
    else:
        actorData = ootGetLinkData(basePath)

    chainInitMatch = re.search(r"CHAIN_VEC3F_DIV1000\s*\(\s*scale\s*,\s*(.*?)\s*,", actorData, re.DOTALL)
    if chainInitMatch is not None:
        scale = chainInitMatch.group(1).strip()
        if scale[-1] == "f":
            scale = scale[:-1]
        return getOOTScale(1 / (float(scale) / 1000))

    actorScaleMatch = re.search(r"Actor\_SetScale\s*\(.*?,\s*(.*?)\s*\)", actorData, re.DOTALL)
    if actorScaleMatch is not None:
        scale = actorScaleMatch.group(1).strip()
        if scale[-1] == "f":
            scale = scale[:-1]
        return getOOTScale(1 / float(scale))

    return getOOTScale(100)


class OOT_DisplayListPanel(bpy.types.Panel):
    bl_label = "Display List Inspector"
    bl_idname = "OBJECT_PT_OOT_DL_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (
            context.object is not None and isinstance(context.object.data, bpy.types.Mesh)
        )

    def draw(self, context):
        box = self.layout.box().column()
        box.box().label(text="OOT DL Inspector")
        obj = context.object

        # prop_split(box, obj, "ootDrawLayer", "Draw Layer")
        box.prop(obj, "ignore_render")
        box.prop(obj, "ignore_collision")

        if not (obj.parent is not None and isinstance(obj.parent.data, bpy.types.Armature)):
            actorScaleBox = box.box().column()
            prop_split(actorScaleBox, obj, "ootActorScale", "Actor Scale")
            actorScaleBox.label(text="This applies to actor exports only.", icon="INFO")

        # Doesn't work since all static meshes are pre-transformed
        # box.prop(obj.ootDynamicTransform, "billboard")

        # drawParentSceneRoom(box, obj)


class OOT_ImportDL(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.oot_import_dl"
    bl_label = "Import DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            settings: OOTDLImportSettings = context.scene.fast64.oot.DLImportSettings
            name = settings.name
            folderName = settings.folder
            importPath = bpy.path.abspath(settings.customPath)
            isCustomImport = settings.isCustom
            basePath = bpy.path.abspath(context.scene.ootDecompPath) if not isCustomImport else importPath
            removeDoubles = settings.removeDoubles
            importNormals = settings.importNormals
            drawLayer = settings.drawLayer
            overlayName = settings.actorOverlayName
            flipbookUses2DArray = settings.flipbookUses2DArray
            flipbookArrayIndex2D = settings.flipbookArrayIndex2D if flipbookUses2DArray else None

            paths = [ootGetObjectPath(isCustomImport, importPath, folderName)]
            data = getImportData(paths)
            f3dContext = OOTF3DContext(F3D("F3DEX2/LX2", False), [name], basePath)

            scale = getOOTScale(settings.actorScale)
            if not isCustomImport:
                data = ootGetIncludedAssetData(basePath, paths, data) + data

                if overlayName is not None:
                    ootReadTextureArrays(basePath, overlayName, name, f3dContext, False, flipbookArrayIndex2D)
                if settings.autoDetectActorScale:
                    scale = ootReadActorScale(basePath, overlayName, False)

            obj = importMeshC(
                data,
                name,
                scale,
                removeDoubles,
                importNormals,
                drawLayer,
                f3dContext,
            )
            obj.ootActorScale = scale / bpy.context.scene.ootBlenderScale

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class OOT_ExportDL(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.oot_export_dl"
    bl_label = "Export DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("Mesh not selected.")
        obj = context.active_object
        if type(obj.data) is not bpy.types.Mesh:
            raise PluginError("Mesh not selected.")

        finalTransform = mathutils.Matrix.Scale(getOOTScale(obj.ootActorScale), 4)

        try:
            # exportPath, levelName = getPathAndLevel(context.scene.geoCustomExport,
            # 	context.scene.geoExportPath, context.scene.geoLevelName,
            # 	context.scene.geoLevelOption)

            saveTextures = bpy.context.scene.saveTextures
            isHWv1 = context.scene.isHWv1
            f3dType = context.scene.f3d_type
            exportSettings = context.scene.fast64.oot.DLExportSettings

            ootConvertMeshToC(
                obj,
                finalTransform,
                f3dType,
                isHWv1,
                DLFormat.Static,
                saveTextures,
                exportSettings,
            )

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class OOT_ExportDLPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_dl"
    bl_label = "OOT DL Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportDL.bl_idname)
        exportSettings: OOTDLExportSettings = context.scene.fast64.oot.DLExportSettings

        prop_split(col, exportSettings, "name", "DL")
        prop_split(col, exportSettings, "folder", "Object" if not exportSettings.isCustom else "Folder")
        if exportSettings.isCustom:
            prop_split(col, exportSettings, "customAssetIncludeDir", "Asset Include Path")
            prop_split(col, exportSettings, "customPath", "Path")
        else:
            prop_split(col, exportSettings, "actorOverlayName", "Overlay (Optional)")
            col.prop(exportSettings, "flipbookUses2DArray")
            if exportSettings.flipbookUses2DArray:
                box = col.box().column()
                prop_split(box, exportSettings, "flipbookArrayIndex2D", "Flipbook Index")

        prop_split(col, exportSettings, "drawLayer", "Export Draw Layer")
        col.prop(exportSettings, "isCustom")
        col.prop(exportSettings, "removeVanillaData")

        col.operator(OOT_ImportDL.bl_idname)
        importSettings: OOTDLImportSettings = context.scene.fast64.oot.DLImportSettings

        prop_split(col, importSettings, "name", "DL")
        if importSettings.isCustom:
            prop_split(col, importSettings, "customPath", "File")
        else:
            prop_split(col, importSettings, "folder", "Object")
            prop_split(col, importSettings, "actorOverlayName", "Overlay (Optional)")
            col.prop(importSettings, "autoDetectActorScale")
            if not importSettings.autoDetectActorScale:
                prop_split(col, importSettings, "actorScale", "Actor Scale")
            col.prop(importSettings, "flipbookUses2DArray")
            if importSettings.flipbookUses2DArray:
                box = col.box().column()
                prop_split(box, importSettings, "flipbookArrayIndex2D", "Flipbook Index")
        prop_split(col, importSettings, "drawLayer", "Import Draw Layer")

        col.prop(importSettings, "isCustom")
        col.prop(importSettings, "removeDoubles")
        col.prop(importSettings, "importNormals")


class OOTDefaultRenderModesProperty(bpy.types.PropertyGroup):
    expandTab: bpy.props.BoolProperty()
    opaqueCycle1: bpy.props.StringProperty(default="G_RM_AA_ZB_OPA_SURF")
    opaqueCycle2: bpy.props.StringProperty(default="G_RM_AA_ZB_OPA_SURF2")
    transparentCycle1: bpy.props.StringProperty(default="G_RM_AA_ZB_XLU_SURF")
    transparentCycle2: bpy.props.StringProperty(default="G_RM_AA_ZB_XLU_SURF2")
    overlayCycle1: bpy.props.StringProperty(default="G_RM_AA_ZB_OPA_SURF")
    overlayCycle2: bpy.props.StringProperty(default="G_RM_AA_ZB_OPA_SURF2")


class OOT_DrawLayersPanel(bpy.types.Panel):
    bl_label = "OOT Draw Layers"
    bl_idname = "WORLD_PT_OOT_Draw_Layers_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT"

    def draw(self, context):
        ootDefaultRenderModeProp = context.scene.world.ootDefaultRenderModes
        layout = self.layout

        inputGroup = layout.column()
        inputGroup.prop(
            ootDefaultRenderModeProp,
            "expandTab",
            text="Default Render Modes",
            icon="TRIA_DOWN" if ootDefaultRenderModeProp.expandTab else "TRIA_RIGHT",
        )
        if ootDefaultRenderModeProp.expandTab:
            prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle1", "Opaque Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle2", "Opaque Cycle 2")
            prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle1", "Transparent Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle2", "Transparent Cycle 2")
            prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle1", "Overlay Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle2", "Overlay Cycle 2")


class OOT_MaterialPanel(bpy.types.Panel):
    bl_label = "OOT Material"
    bl_idname = "MATERIAL_PT_OOT_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.material is not None and context.scene.gameEditorMode == "OOT"

    def draw(self, context):
        layout = self.layout
        mat = context.material
        col = layout.column()

        if (
            hasattr(context, "object")
            and context.object is not None
            and context.object.parent is not None
            and isinstance(context.object.parent.data, bpy.types.Armature)
        ):
            drawLayer = context.object.parent.ootDrawLayer
            if drawLayer != mat.f3d_mat.draw_layer.oot:
                col.label(text="Draw layer is being overriden by skeleton.", icon="OUTLINER_DATA_ARMATURE")
        else:
            drawLayer = mat.f3d_mat.draw_layer.oot

        drawOOTMaterialProperty(col.box().column(), mat, drawLayer)


def drawOOTMaterialDrawLayerProperty(layout, matDrawLayerProp, suffix):
    # layout.box().row().label(text = title)
    row = layout.row()
    for colIndex in range(2):
        col = row.column()
        for rowIndex in range(3):
            i = 8 + colIndex * 3 + rowIndex
            name = "Segment " + format(i, "X") + " " + suffix
            col.prop(matDrawLayerProp, "segment" + format(i, "X"), text=name)
        name = "Custom call (" + str(colIndex + 1) + ") " + suffix
        p = "customCall" + str(colIndex)
        col.prop(matDrawLayerProp, p, text=name)
        if getattr(matDrawLayerProp, p):
            col.prop(matDrawLayerProp, p + "_seg", text="")


drawLayerSuffix = {"Opaque": "OPA", "Transparent": "XLU", "Overlay": "OVL"}


def drawOOTMaterialProperty(layout, mat, drawLayer):
    if drawLayer == "Overlay":
        return
    matProp = mat.ootMaterial
    suffix = "(" + drawLayerSuffix[drawLayer] + ")"
    layout.box().column().label(text="OOT Dynamic Material Properties " + suffix)
    layout.label(text="See gSPSegment calls in z_scene_table.c.")
    layout.label(text="Based off draw config index in gSceneTable.")
    drawOOTMaterialDrawLayerProperty(layout.column(), getattr(matProp, drawLayer.lower()), suffix)
    if not mat.is_f3d:
        return
    f3d_mat = mat.f3d_mat


class OOTDynamicMaterialDrawLayerProperty(bpy.types.PropertyGroup):
    segment8: bpy.props.BoolProperty()
    segment9: bpy.props.BoolProperty()
    segmentA: bpy.props.BoolProperty()
    segmentB: bpy.props.BoolProperty()
    segmentC: bpy.props.BoolProperty()
    segmentD: bpy.props.BoolProperty()
    customCall0: bpy.props.BoolProperty()
    customCall0_seg: bpy.props.StringProperty(description="Segment address of a display list to call, e.g. 0x08000010")
    customCall1: bpy.props.BoolProperty()
    customCall1_seg: bpy.props.StringProperty(description="Segment address of a display list to call, e.g. 0x08000010")

    def key(self):
        return (
            self.segment8,
            self.segment9,
            self.segmentA,
            self.segmentB,
            self.segmentC,
            self.segmentD,
            self.customCall0_seg if self.customCall0 else None,
            self.customCall1_seg if self.customCall1 else None,
        )


# The reason these are separate is for the case when the user changes the material draw layer, but not the
# dynamic material calls. This could cause crashes which would be hard to detect.
class OOTDynamicMaterialProperty(bpy.types.PropertyGroup):
    opaque: bpy.props.PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)
    transparent: bpy.props.PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)

    def key(self):
        return (self.opaque.key(), self.transparent.key())


oot_dl_writer_classes = (
    OOTDefaultRenderModesProperty,
    OOTDynamicMaterialDrawLayerProperty,
    OOTDynamicMaterialProperty,
    OOTDynamicTransformProperty,
    OOT_ExportDL,
    OOT_ImportDL,
    OOTDLExportSettings,
    OOTDLImportSettings,
)

oot_dl_writer_panel_classes = (
    # OOT_ExportDLPanel,
    OOT_DisplayListPanel,
    OOT_DrawLayersPanel,
    OOT_MaterialPanel,
    OOT_ExportDLPanel,
)


def oot_dl_writer_panel_register():
    for cls in oot_dl_writer_panel_classes:
        register_class(cls)


def oot_dl_writer_panel_unregister():
    for cls in oot_dl_writer_panel_classes:
        unregister_class(cls)


def oot_dl_writer_register():
    for cls in oot_dl_writer_classes:
        register_class(cls)

    bpy.types.Object.ootDrawLayer = bpy.props.EnumProperty(items=ootEnumDrawLayers, default="Opaque")

    # Doesn't work since all static meshes are pre-transformed
    # bpy.types.Object.ootDynamicTransform = bpy.props.PointerProperty(type = OOTDynamicTransformProperty)
    bpy.types.World.ootDefaultRenderModes = bpy.props.PointerProperty(type=OOTDefaultRenderModesProperty)
    bpy.types.Material.ootMaterial = bpy.props.PointerProperty(type=OOTDynamicMaterialProperty)
    bpy.types.Object.ootObjectMenu = bpy.props.EnumProperty(items=ootEnumObjectMenu)


def oot_dl_writer_unregister():
    for cls in reversed(oot_dl_writer_classes):
        unregister_class(cls)

    del bpy.types.Material.ootMaterial
    del bpy.types.Object.ootObjectMenu
