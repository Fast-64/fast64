import shutil, copy, bpy, os
from bpy.utils import register_class, unregister_class

from .oot_utility import *
from .oot_constants import *
from ..f3d.f3d_writer import *
from ..f3d.f3d_material import *
from ..f3d.f3d_parser import *
from ..f3d.flipbook import *
from ..panels import OOT_Panel

from .oot_model_classes import *
from .oot_scene_room import *
from .oot_texture_array import *

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
):

    optimize = bpy.context.scene.ootSkeletonExportOptimize
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
    originalObj,
    finalTransform,
    f3dType,
    isHWv1,
    name,
    folderName,
    DLFormat,
    saveTextures,
    exportPath,
    isCustomExport,
    drawLayer,
    removeVanillaData,
    overlayName: str,
    arrayIndex2D: int,
):
    name = toAlnum(name)

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

    exportData = fModel.to_c(TextureExportSettings(False, saveTextures, "test"), OOTGfxFormatter(ScrollMethod.Vertex))

    data.append(exportData.all())

    if isCustomExport:
        textureArrayData = writeTextureArraysNew(fModel, arrayIndex2D)
        data.append(textureArrayData)

    path = ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, False)
    writeCData(data, os.path.join(path, name + ".h"), os.path.join(path, name + ".c"))

    if not isCustomExport:
        writeTextureArraysExisting(bpy.context.scene.ootDecompPath, overlayName, False, arrayIndex2D, fModel)
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


def writeTextureArraysExisting(exportPath: str, overlayName: str, isLink: bool, arrayIndex2D: int, fModel: OOTModel):
    if isLink:
        actorFilePath = os.path.join(exportPath, f"src/code/z_player_lib.c")
    else:
        actorFilePath = os.path.join(exportPath, f"src/overlays/actors/{overlayName}/z_{overlayName[4:].lower()}.c")
        actorFileDataPath = f"{actorFilePath[:-2]}_data.c"  # some bosses store texture arrays here

        if os.path.exists(actorFileDataPath):
            actorFilePath = actorFileDataPath

    if not os.path.exists(actorFilePath):
        print(f"{actorFilePath} not found, ignoring texture array writing.")
        return

    actorData = readFile(actorFilePath)
    newData = actorData

    for flipbook in fModel.flipbooks:
        if flipbook.exportMode == "Array":
            if arrayIndex2D is None:
                newData = writeTextureArraysExisting1D(newData, flipbook)
            else:
                newData = writeTextureArraysExisting2D(newData, flipbook, arrayIndex2D)

    if newData != actorData:
        writeFile(actorFilePath, newData)


def writeTextureArraysExisting1D(data: str, flipbook: TextureFlipbook) -> str:
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
            newData = newData[: includeMatch.end(0)] + newArrayData + "\n" + newData[includeMatch.end(0) :]
        else:
            newData += newArrayData + "\n"

    return newData


# for flipbook textures, we only replace one element of the 2D array.
def writeTextureArraysExisting2D(data: str, flipbook: TextureFlipbook, arrayIndex2D: int) -> str:
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

        if arrayIndex2D >= len(arrayMatchData):
            while len(arrayMatchData) <= arrayIndex2D:
                arrayMatchData.append(newArrayData)
        else:
            arrayMatchData[arrayIndex2D] = newArrayData

        newArray2DData = ",\n".join([item for item in arrayMatchData])
        newData = replaceMatchContent(newData, newArray2DData, array2DMatch, 2)

        # otherwise, add to end of asset includes
    else:
        arrayMatchData = [newArrayData] * (arrayIndex2D + 1)
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
        box = self.layout.box()
        box.box().label(text="OOT DL Inspector")
        obj = context.object

        # prop_split(box, obj, "ootDrawLayer", "Draw Layer")
        box.prop(obj, "ignore_render")
        box.prop(obj, "ignore_collision")

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
            name = context.scene.ootDLImportName
            folderName = context.scene.ootDLImportFolderName
            importPath = bpy.path.abspath(context.scene.ootDLImportCustomPath)
            isCustomImport = context.scene.ootDLImportUseCustomPath
            scale = context.scene.ootActorBlenderScale
            basePath = bpy.path.abspath(context.scene.ootDecompPath)
            removeDoubles = context.scene.ootDLRemoveDoubles
            importNormals = context.scene.ootDLImportNormals
            drawLayer = bpy.context.scene.ootDLImportDrawLayer
            overlayName = bpy.context.scene.ootDLImportOverlay
            is2DArray = context.scene.ootDLImportIs2DArray
            arrayIndex2D = context.scene.ootDLImportArrayIndex2D if is2DArray else None

            paths = [ootGetObjectPath(isCustomImport, importPath, folderName)]
            data = getImportData(paths)
            f3dContext = OOTF3DContext(F3D("F3DEX2/LX2", False), [name], basePath)
            if not isCustomImport:
                data = ootGetIncludedAssetData(basePath, paths, data) + data

                if overlayName is not None:
                    ootReadTextureArrays(basePath, overlayName, name, f3dContext, False, arrayIndex2D)

            importMeshC(
                data,
                name,
                scale,
                removeDoubles,
                importNormals,
                drawLayer,
                f3dContext,
            )

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

        finalTransform = mathutils.Matrix.Scale(context.scene.ootActorBlenderScale, 4)

        try:
            # exportPath, levelName = getPathAndLevel(context.scene.geoCustomExport,
            # 	context.scene.geoExportPath, context.scene.geoLevelName,
            # 	context.scene.geoLevelOption)

            saveTextures = bpy.context.scene.saveTextures or bpy.context.scene.ignoreTextureRestrictions
            isHWv1 = context.scene.isHWv1
            f3dType = context.scene.f3d_type

            name = context.scene.ootDLExportName
            folderName = context.scene.ootDLExportFolderName
            exportPath = bpy.path.abspath(context.scene.ootDLExportCustomPath)
            isCustomExport = context.scene.ootDLExportUseCustomPath
            drawLayer = context.scene.ootDLExportDrawLayer
            removeVanillaData = context.scene.ootDLRemoveVanillaData
            overlayName = bpy.context.scene.ootDLExportOverlay
            is2DArray = context.scene.ootDLExportIs2DArray
            arrayIndex2D = context.scene.ootDLExportArrayIndex2D if is2DArray else None

            ootConvertMeshToC(
                obj,
                finalTransform,
                f3dType,
                isHWv1,
                name,
                folderName,
                DLFormat.Static,
                saveTextures,
                exportPath,
                isCustomExport,
                drawLayer,
                removeVanillaData,
                overlayName,
                arrayIndex2D,
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

        prop_split(col, context.scene, "ootDLExportName", "DL")
        if context.scene.ootDLExportUseCustomPath:
            prop_split(col, context.scene, "ootDLExportCustomPath", "Folder")
        else:
            prop_split(col, context.scene, "ootDLExportFolderName", "Object")
            prop_split(col, context.scene, "ootDLExportOverlay", "Overlay (Optional)")
            col.prop(context.scene, "ootDLExportIs2DArray")
            if context.scene.ootDLExportIs2DArray:
                box = col.box().column()
                prop_split(box, context.scene, "ootDLExportArrayIndex2D", "Flipbook Index")
        prop_split(col, context.scene, "ootDLExportDrawLayer", "Export Draw Layer")
        col.prop(context.scene, "ootDLExportUseCustomPath")
        col.prop(context.scene, "ootDLRemoveVanillaData")

        col.operator(OOT_ImportDL.bl_idname)

        prop_split(col, context.scene, "ootDLImportName", "DL")
        if context.scene.ootDLImportUseCustomPath:
            prop_split(col, context.scene, "ootDLImportCustomPath", "File")
        else:
            prop_split(col, context.scene, "ootDLImportFolderName", "Object")
            prop_split(col, context.scene, "ootDLImportOverlay", "Overlay (Optional)")
            col.prop(context.scene, "ootDLImportIs2DArray")
            if context.scene.ootDLImportIs2DArray:
                box = col.box().column()
                prop_split(box, context.scene, "ootDLImportArrayIndex2D", "Flipbook Index")
        prop_split(col, context.scene, "ootDLImportDrawLayer", "Import Draw Layer")

        col.prop(context.scene, "ootDLImportUseCustomPath")
        col.prop(context.scene, "ootDLRemoveDoubles")
        col.prop(context.scene, "ootDLImportNormals")


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


# The reason these are separate is for the case when the user changes the material draw layer, but not the
# dynamic material calls. This could cause crashes which would be hard to detect.
class OOTDynamicMaterialProperty(bpy.types.PropertyGroup):
    opaque: bpy.props.PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)
    transparent: bpy.props.PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)


oot_dl_writer_classes = (
    OOTDefaultRenderModesProperty,
    OOTDynamicMaterialDrawLayerProperty,
    OOTDynamicMaterialProperty,
    OOTDynamicTransformProperty,
    OOT_ExportDL,
    OOT_ImportDL,
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

    bpy.types.Scene.ootDLExportName = bpy.props.StringProperty(name="DL Name", default="gBoulderFragmentsDL")
    bpy.types.Scene.ootDLExportFolderName = bpy.props.StringProperty(name="DL Folder", default="gameplay_keep")
    bpy.types.Scene.ootDLExportOverlay = bpy.props.StringProperty(name="Overlay", default="")
    bpy.types.Scene.ootDLExportIs2DArray = bpy.props.BoolProperty(name="Has 2D Flipbook Array", default=False)
    bpy.types.Scene.ootDLExportArrayIndex2D = bpy.props.IntProperty(name="Index if 2D Array", default=0, min=0)
    bpy.types.Scene.ootDLExportCustomPath = bpy.props.StringProperty(name="Custom DL Path", subtype="FILE_PATH")
    bpy.types.Scene.ootDLExportUseCustomPath = bpy.props.BoolProperty(name="Use Custom Path")
    bpy.types.Scene.ootDLRemoveVanillaData = bpy.props.BoolProperty(name="Replace Vanilla DLs")

    bpy.types.Scene.ootDLImportName = bpy.props.StringProperty(name="DL Name", default="gBoulderFragmentsDL")
    bpy.types.Scene.ootDLImportFolderName = bpy.props.StringProperty(name="DL Folder", default="gameplay_keep")
    bpy.types.Scene.ootDLImportOverlay = bpy.props.StringProperty(name="Overlay", default="")
    bpy.types.Scene.ootDLImportIs2DArray = bpy.props.BoolProperty(name="Has 2D Flipbook Array", default=False)
    bpy.types.Scene.ootDLImportArrayIndex2D = bpy.props.IntProperty(name="Index if 2D Array", default=0, min=0)
    bpy.types.Scene.ootDLImportCustomPath = bpy.props.StringProperty(name="Custom DL Path", subtype="FILE_PATH")
    bpy.types.Scene.ootDLImportUseCustomPath = bpy.props.BoolProperty(name="Use Custom Path")

    bpy.types.Scene.ootDLRemoveDoubles = bpy.props.BoolProperty(name="Remove Doubles", default=True)
    bpy.types.Scene.ootDLImportNormals = bpy.props.BoolProperty(name="Import Normals", default=True)
    bpy.types.Scene.ootDLImportDrawLayer = bpy.props.EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)

    bpy.types.Scene.ootDLExportDrawLayer = bpy.props.EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)

    bpy.types.Material.ootMaterial = bpy.props.PointerProperty(type=OOTDynamicMaterialProperty)
    bpy.types.Object.ootObjectMenu = bpy.props.EnumProperty(items=ootEnumObjectMenu)


def oot_dl_writer_unregister():
    for cls in reversed(oot_dl_writer_classes):
        unregister_class(cls)

    del bpy.types.Scene.ootDLExportName
    del bpy.types.Scene.ootDLExportFolderName
    del bpy.types.Scene.ootDLExportOverlay
    del bpy.types.Scene.ootDLExportIs2DArray
    del bpy.types.Scene.ootDLExportArrayIndex2D
    del bpy.types.Scene.ootDLExportCustomPath
    del bpy.types.Scene.ootDLExportUseCustomPath
    del bpy.types.Scene.ootDLRemoveVanillaData

    del bpy.types.Scene.ootDLImportName
    del bpy.types.Scene.ootDLImportFolderName
    del bpy.types.Scene.ootDLImportOverlay
    del bpy.types.Scene.ootDLImportIs2DArray
    del bpy.types.Scene.ootDLImportArrayIndex2D
    del bpy.types.Scene.ootDLImportCustomPath
    del bpy.types.Scene.ootDLImportUseCustomPath

    del bpy.types.Scene.ootDLRemoveDoubles
    del bpy.types.Scene.ootDLImportNormals
    del bpy.types.Scene.ootDLImportDrawLayer

    del bpy.types.Scene.ootDLExportDrawLayer

    del bpy.types.Material.ootMaterial
    del bpy.types.Object.ootObjectMenu
