import bpy, os, mathutils
from bpy.utils import register_class, unregister_class
from ..utility import CData, prop_split, writeCData, getGroupIndexFromname, toAlnum
from ..f3d.f3d_parser import ootEnumDrawLayers
from ..f3d.f3d_gbi import DLFormat, TextureExportSettings, ScrollMethod
from .panel.display_list.classes import OOTDLExportSettings

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
    ootDuplicateHierarchy,
    ootCleanupScene,
    ootGetPath,
    addIncludeFiles,
)

from .oot_model_classes import (
    OOTTriangleConverterInfo,
    OOTModel,
    OOTGfxFormatter,
    OOTDynamicTransformProperty,
)


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

    writeCData(data, os.path.join(path, name + ".h"), os.path.join(path, name + ".c"))

    if not isCustomExport:
        addIncludeFiles(folderName, path, name)
        if removeVanillaData:
            headerPath = os.path.join(path, folderName + ".h")
            sourcePath = os.path.join(path, folderName + ".c")
            removeDL(sourcePath, headerPath, name)


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

        drawOOTMaterialProperty(col.box().column(), mat.ootMaterial, drawLayer)


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


def drawOOTMaterialProperty(layout, matProp, drawLayer):
    if drawLayer == "Overlay":
        return
    suffix = "(" + drawLayerSuffix[drawLayer] + ")"
    layout.box().column().label(text="OOT Dynamic Material Properties " + suffix)
    layout.label(text="See gSPSegment calls in z_scene_table.c.")
    layout.label(text="Based off draw config index in gSceneTable.")
    drawOOTMaterialDrawLayerProperty(layout.column(), getattr(matProp, drawLayer.lower()), suffix)


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
)

oot_dl_writer_panel_classes = (
    OOT_DisplayListPanel,
    OOT_DrawLayersPanel,
    OOT_MaterialPanel,
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
