from __future__ import annotations
from pathlib import Path
import typing

import bpy, mathutils, math, copy, os, shutil, re
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..operators import ObjectDataExporter
from ..panels import SM64_Panel
from .sm64_objects import InlineGeolayoutObjConfig, inlineGeoLayoutObjects
from .sm64_geolayout_bone import getSwitchOptionBone
from .sm64_camera import saveCameraSettingsToGeolayout
from .sm64_f3d_writer import SM64Model, SM64GfxFormatter, GfxOverride, OverrideHash
from .sm64_texscroll import modifyTexScrollFiles, modifyTexScrollHeadersGroup
from .sm64_level_parser import parse_level_binary
from .sm64_rom_tweaks import ExtendBank0x04
from .sm64_utility import export_rom_checks, starSelectWarning, update_actor_includes, write_material_headers

from ..utility import (
    PluginError,
    VertexWeightError,
    z_up_to_y_up_matrix,
    setOrigin,
    raisePluginError,
    findStartBones,
    duplicateHierarchy,
    cleanupDuplicatedObjects,
    getExportDir,
    toAlnum,
    writeMaterialFiles,
    get64bitAlignedAddr,
    encodeSegmentedAddr,
    writeInsertableFile,
    bytesToHex,
    checkSM64EmptyUsesGeoLayout,
    convertEulerFloatToShort,
    convertFloatToShort,
    checkIsSM64InlineGeoLayout,
    checkIsSM64PreInlineGeoLayout,
    translate_blender_to_n64,
    rotate_quat_blender_to_n64,
    get_obj_temp_mesh,
    getGroupNameFromIndex,
    highlightWeightErrors,
    getGroupIndexFromname,
    getFMeshName,
    checkUniqueBoneNames,
    applyRotation,
    getPathAndLevel,
    applyBasicTweaks,
    tempName,
    getAddressFromRAMAddress,
    prop_split,
    geoNodeRotateOrder,
    deselectAllObjects,
    selectSingleObject,
)

from ..f3d.f3d_bleed import (
    find_material_from_jump_cmd,
)

from ..f3d.f3d_material import (
    isTexturePointSampled,
)

from ..f3d.f3d_writer import (
    TriangleConverterInfo,
    LoopConvertInfo,
    BufferVertex,
    revertMatAndEndDraw,
    getInfoDict,
    saveStaticModel,
    getTexDimensions,
    checkForF3dMaterialInFaces,
    saveOrGetF3DMaterial,
    saveMeshWithLargeTexturesByFaces,
    saveMeshByFaces,
    getF3DVert,
)

from ..f3d.f3d_gbi import (
    get_F3D_GBI,
    GfxList,
    GfxListTag,
    GfxMatWriteMethod,
    DPSetAlphaCompare,
    FModel,
    FMesh,
    SPVertex,
    DPSetEnvColor,
    FAreaData,
    FFogData,
    ScrollMethod,
    TextureExportSettings,
    DLFormat,
    SPEndDisplayList,
    SPDisplayList,
)

from .sm64_geolayout_classes import (
    BaseDisplayListNode,
    DisplayListNode,
    TransformNode,
    StartNode,
    StartRenderAreaNode,
    GeolayoutGraph,
    GeoLayoutBleed,
    JumpNode,
    SwitchOverrideNode,
    SwitchNode,
    TranslateNode,
    RotateNode,
    TranslateRotateNode,
    FunctionNode,
    BillboardNode,
    ScaleNode,
    RenderRangeNode,
    ShadowNode,
    DisplayListWithOffsetNode,
    HeldObjectNode,
    Geolayout,
)

from .sm64_constants import insertableBinaryTypes, bank0Segment, defaultExtendSegment4

if typing.TYPE_CHECKING:
    from .sm64_geolayout_bone import SM64_BoneProperties


def get_custom_cmd_with_transform(node: "CustomNode", parentTransformNode: TransformNode, translate, rotate, scale):
    types = {a["arg_type"] for a in node.data["args"]}
    has_translation, has_rotation, has_scale = "TRANSLATION" in types, "ROTATION" in types, "SCALE" in types
    if (not has_translation and not isZeroTranslation(translate)) or (not has_rotation and not isZeroRotation(rotate)):
        field = 0 if not (has_translation or has_rotation) else (1 if has_rotation else 2)
        parentTransformNode = addParentNode(
            parentTransformNode, TranslateRotateNode(node.drawLayer, field, False, translate, rotate)
        )
    if not has_scale and not isZeroScaleChange(scale):
        parentTransformNode = addParentNode(parentTransformNode, ScaleNode(node.drawLayer, scale[0], False))
    return node, parentTransformNode, has_translation, has_rotation, has_scale


def appendSecondaryGeolayout(geoDirPath, geoName1, geoName2, additionalNode=""):
    geoPath = os.path.join(geoDirPath, "geo.inc.c")
    geoFile = open(geoPath, "a", newline="\n")
    geoFile.write(
        "\n\nconst GeoLayout "
        + geoName2
        + "_geo[] = {\n"
        + (("\t" + additionalNode + ",\n") if additionalNode is not None else "")
        + "\tGEO_BRANCH(1, "
        + geoName1
        + "_geo),\n"
        + "\tGEO_END(),\n};\n"
    )
    geoFile.close()


def replaceStarReferences(basePath):
    kleptoPattern = (
        "GEO\_SCALE\(0x00\, 16384\)\,\s*"
        + "GEO\_OPEN\_NODE\(\)\,\s*"
        + "GEO\_ASM\([^\)]*?\)\,\s*"
        + "GEO\_TRANSLATE\_ROTATE\_WITH\_DL\([^\)]*? star\_seg3.*?GEO\_CLOSE\_NODE\(\)\,"
    )

    unagiPattern = (
        "GEO\_SCALE\(0x00\, 16384\)\,\s*"
        + "GEO\_OPEN\_NODE\(\)\,\s*"
        + "GEO\_TRANSLATE\_ROTATE\_WITH\_DL\([^\)]*? star\_seg3.*?GEO\_CLOSE\_NODE\(\)\,"
    )

    unagiReplacement = (
        "GEO_TRANSLATE_ROTATE(LAYER_OPAQUE, 500, 0, 0, 0, 0, 0),\n"
        + "\t" * 10
        + "GEO_OPEN_NODE(),\n"
        + "\t" * 10
        + "\tGEO_BRANCH_AND_LINK(star_geo),\n"
        + "\t" * 10
        + "GEO_CLOSE_NODE(),"
    )

    kleptoReplacement = (
        "GEO_TRANSLATE_ROTATE(LAYER_OPAQUE, 75, 75, 0, 180, 270, 0),\n"
        + "\t" * 10
        + "GEO_OPEN_NODE(),\n"
        + "\t" * 10
        + "\tGEO_BRANCH_AND_LINK(star_geo),\n"
        + "\t" * 10
        + "GEO_CLOSE_NODE(),"
    )

    unagiPath = os.path.join(basePath, "actors/unagi/geo.inc.c")
    replaceDLReferenceInGeo(unagiPath, unagiPattern, unagiReplacement)

    kleptoPath = os.path.join(basePath, "actors/klepto/geo.inc.c")
    replaceDLReferenceInGeo(kleptoPath, kleptoPattern, kleptoReplacement)


def replaceTransparentStarReferences(basePath):
    pattern = (
        "GEO\_SCALE\(0x00\, 16384\)\,\s*"
        + "GEO\_OPEN\_NODE\(\)\,\s*"
        + "GEO\_ASM\([^\)]*?\)\,\s*"
        + "GEO\_TRANSLATE\_ROTATE\_WITH\_DL\([^\)]*? transparent_star\_seg3.*?GEO\_CLOSE\_NODE\(\)\,"
    )

    kleptoReplacement = (
        "GEO_TRANSLATE_ROTATE(LAYER_OPAQUE, 75, 75, 0, 180, 270, 0),\n"
        + "\t" * 10
        + "GEO_OPEN_NODE(),\n"
        + "\t" * 10
        + "\tGEO_BRANCH_AND_LINK(transparent_star_geo),\n"
        + "\t" * 10
        + "GEO_CLOSE_NODE(),"
    )

    kleptoPath = os.path.join(basePath, "actors/klepto/geo.inc.c")
    replaceDLReferenceInGeo(kleptoPath, pattern, kleptoReplacement)


def replaceCapReferences(basePath):
    pattern = "GEO\_TRANSLATE\_ROTATE\_WITH\_DL\([^\)]*?mario\_cap\_seg3.*?\)\,"
    kleptoPattern = (
        "GEO\_SCALE\(0x00\, 16384\)\,\s*"
        + "GEO\_OPEN\_NODE\(\)\,\s*"
        + "GEO\_ASM\([^\)]*?\)\,\s*"
        + "GEO\_TRANSLATE\_ROTATE\_WITH\_DL\([^\)]*? mario\_cap\_seg3.*?GEO\_CLOSE\_NODE\(\)\,"
    )

    kleptoReplacement = (
        "GEO_TRANSLATE_ROTATE(LAYER_OPAQUE, 75, 75, 0, 180, 270, 0),\n"
        + "\t" * 10
        + "GEO_OPEN_NODE(),\n"
        + "\t" * 10
        + "\tGEO_BRANCH_AND_LINK(marios_cap_geo),\n"
        + "\t" * 10
        + "GEO_CLOSE_NODE(),"
    )

    ukikiReplacement = (
        "GEO_TRANSLATE_ROTATE(LAYER_OPAQUE, 100, 0, 0, -90, -90, 0),\n"
        + "\t" * 8
        + "GEO_OPEN_NODE(),\n"
        + "\t" * 8
        + "GEO_SCALE(0x00, 0x40000),\n"
        + "\t" * 8
        + "\tGEO_OPEN_NODE(),\n"
        + "\t" * 8
        + "\t\tGEO_BRANCH_AND_LINK(marios_cap_geo),\n"
        + "\t" * 8
        + "\tGEO_CLOSE_NODE(),"
        + "\t" * 8
        + "GEO_CLOSE_NODE(),"
    )

    snowmanReplacement = (
        "GEO_TRANSLATE_ROTATE(LAYER_OPAQUE, 490, 14, 43, 305, 0, 248),\n"
        + "\t" * 7
        + "GEO_OPEN_NODE(),\n"
        + "\t" * 7
        + "GEO_SCALE(0x00, 0x40000),\n"
        + "\t" * 7
        + "\tGEO_OPEN_NODE(),\n"
        + "\t" * 7
        + "\t\tGEO_BRANCH_AND_LINK(marios_cap_geo),\n"
        + "\t" * 7
        + "\tGEO_CLOSE_NODE(),"
        + "\t" * 7
        + "GEO_CLOSE_NODE(),"
    )

    ukikiPath = os.path.join(basePath, "actors/ukiki/geo.inc.c")
    replaceDLReferenceInGeo(ukikiPath, pattern, ukikiReplacement)

    snowmanPath = os.path.join(basePath, "actors/snowman/geo.inc.c")
    replaceDLReferenceInGeo(snowmanPath, pattern, snowmanReplacement)

    kleptoPath = os.path.join(basePath, "actors/klepto/geo.inc.c")
    replaceDLReferenceInGeo(kleptoPath, kleptoPattern, kleptoReplacement)


def replaceDLReferenceInGeo(geoPath, pattern, replacement):
    if not os.path.exists(geoPath):
        return
    geoFile = open(geoPath, "r", newline="\n")
    geoData = geoFile.read()
    geoFile.close()

    newData = re.sub(pattern, replacement, geoData, flags=re.DOTALL)
    if newData != geoData:
        geoFile = open(geoPath, "w", newline="\n")
        geoFile.write(newData)
        geoFile.close()


def prepareGeolayoutExport(armatureObj, obj):
    # Make object and armature space the same.
    setOrigin(obj, armatureObj.location)

    # Apply armature scale.
    selectSingleObject(armatureObj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, properties=False)


def getAllArmatures(armatureObj, currentArmatures):
    linkedArmatures = []
    for bone in armatureObj.data.bones:
        if bone.geo_cmd == "Switch":
            for switchOption in bone.switch_options:
                if switchOption.switchType == "Mesh":
                    if switchOption.optionArmature is None:
                        raise PluginError(
                            '"'
                            + bone.name
                            + '" in armature "'
                            + armatureObj.name
                            + '" has a mesh switch option '
                            + "with no defined mesh."
                        )
                    elif (
                        switchOption.optionArmature not in linkedArmatures
                        and switchOption.optionArmature not in currentArmatures
                    ):
                        linkedArmatures.append(switchOption.optionArmature)

    currentArmatures.extend(linkedArmatures)
    for linkedArmature in linkedArmatures:
        getAllArmatures(linkedArmature, currentArmatures)


def getCameraObj(camera):
    for obj in bpy.data.objects:
        if obj.data == camera:
            return obj
    raise PluginError("The level camera " + camera.name + " is no longer in the scene.")


DrawLayerDict = dict[int, list[TransformNode]]


def append_revert_to_geolayout(graph: GeolayoutGraph, f_model: SM64Model):
    material_revert = GfxList(
        f_model.name + "_" + "material_revert_render_settings", GfxListTag.MaterialRevert, f_model.DLFormat
    )
    revertMatAndEndDraw(material_revert, [DPSetEnvColor(0xFF, 0xFF, 0xFF, 0xFF), DPSetAlphaCompare("G_AC_NONE")])

    # walk the geo layout graph to find the last used DL for each layer
    # each switch child will be considered a last used DL, unless subsequent
    # DL is drawn outside switch root
    def walk(node, draw_layer_dict: DrawLayerDict) -> DrawLayerDict:
        base_node = node.node
        if type(base_node) == JumpNode:
            if base_node.geolayout:
                for node in base_node.geolayout.nodes:
                    draw_layer_dict = walk(node, draw_layer_dict.copy())
        fMesh = getattr(base_node, "fMesh", None)
        if fMesh:
            draw_layer_dict[base_node.drawLayer] = [node]

        start_draw_layer_dict = draw_layer_dict.copy()
        for child in node.children:
            if type(base_node) == SwitchNode:
                option_resets = walk(child, {})
                for (
                    draw_layer,
                    nodes,
                ) in option_resets.items():  # add draw layers that are not already in draw_layer_dict
                    if draw_layer not in start_draw_layer_dict:
                        if draw_layer not in draw_layer_dict:
                            draw_layer_dict[draw_layer] = []
                        draw_layer_dict[draw_layer].extend(nodes)
                for draw_layer, nodes in start_draw_layer_dict.items():
                    if draw_layer in option_resets:  # option overrides a previous draw layer
                        nodes.clear()
                        nodes.extend(option_resets[draw_layer])
            else:
                draw_layer_dict = walk(child, draw_layer_dict.copy())
        return draw_layer_dict

    draw_layer_dict: DrawLayerDict = {}
    for node in graph.startGeolayout.nodes:
        draw_layer_dict = walk(node, draw_layer_dict.copy())

    def create_revert_node(draw_layer, node: DisplayListNode | None = None):
        f_mesh = f_model.addMesh("final_revert", f_model.name, draw_layer, False, None, dedup=True)
        f_mesh.draw = gfx_list = GfxList(f_mesh.name, GfxListTag.Draw, f_model.DLFormat)
        gfx_list.commands.extend(material_revert.commands)
        revert_node = DisplayListNode(draw_layer)
        revert_node.DLmicrocode = gfx_list
        revert_node.fMesh = f_mesh
        if node is None:
            graph.startGeolayout.nodes.append(TransformNode(revert_node))
        else:
            addParentNode(node, revert_node)

    # Revert settings in each unique draw layer
    for draw_layer, nodes in draw_layer_dict.items():
        if len(nodes) == 0:
            create_revert_node(draw_layer)
        for transform_node in nodes:
            node = transform_node.node
            f_mesh: FMesh = node.fMesh
            cmd_list: GfxList = node.DLmicrocode
            if f_mesh.cullVertexList:
                create_revert_node(draw_layer, transform_node)
            else:
                if node.override_hash:
                    node.override_hash = (5, *node.override_hash)
                elif hasattr(f_mesh, "override_layer") and f_mesh.override_layer:
                    node.override_hash = (5, node.drawLayer)
                else:
                    node.override_hash = (6,)
                override = f_model.draw_overrides.get(f_mesh, {}).get(node.override_hash)
                if override is not None:
                    node.DLmicrocode = override.gfx
                    override.nodes.append(node)
                    continue
                else:
                    node.DLmicrocode = cmd_list = copy.copy(cmd_list)
                    if hasattr(f_mesh, "override_layer") and f_mesh.override_layer:
                        cmd_list.name += f"_with_layer_{node.drawLayer}_revert"
                    else:
                        cmd_list.name += "_with_revert"
                    cmd_list.commands = cmd_list.commands.copy()
                    f_model.draw_overrides.setdefault(f_mesh, {})[node.override_hash] = GfxOverride(cmd_list, [node])
                # remove SPEndDisplayList from gfx_list, material_revert has its own SPEndDisplayList cmd
                while SPEndDisplayList() in cmd_list.commands:
                    cmd_list.commands.remove(SPEndDisplayList())
                cmd_list.commands.extend(material_revert.commands)


def add_overrides_to_fmodel(f_model: SM64Model):
    for f_mesh, draw_overrides in f_model.draw_overrides.items():
        # each override dict might have a none which ends up unused, actually check the node
        nodes = [node for override in draw_overrides.values() for node in override.nodes]
        if (
            len(nodes) > 0
            and all(node.override_hash is not None for node in nodes)
            and not any(node.dlRef is f_mesh.draw for node in nodes)
        ):
            override_hash, cmd_list, nodes = next(
                (override_hash, cmd_list, nodes)
                for override_hash, (cmd_list, nodes) in draw_overrides.items()
                if any(node.override_hash == override_hash for node in nodes)
            )
            for node in nodes:
                if node.override_hash == override_hash:
                    node.DLmicrocode = cmd_list
                    node.override_hash = None
            f_mesh.draw = cmd_list
            f_mesh.name = cmd_list.name
            draw_overrides.pop(override_hash)

        for override_hash, (cmd_list, nodes) in draw_overrides.items():
            # remove no longer used overrides
            if all(node.override_hash is None or node.override_hash != override_hash for node in nodes):
                continue
            if cmd_list not in f_mesh.draw_overrides:
                f_mesh.draw_overrides.append(cmd_list)


# Convert to Geolayout
def convertArmatureToGeolayout(armatureObj, obj, convertTransformMatrix, camera, name, DLFormat, convertTextureData):
    inline = bpy.context.scene.exportInlineF3D
    fModel = SM64Model(
        name,
        DLFormat,
        bpy.context.scene.fast64.sm64.gfx_write_method,
    )

    if len(armatureObj.children) == 0:
        raise PluginError("No mesh parented to armature.")

    infoDict = getInfoDict(obj)

    # Find start bone, which is not root. Root is the start for animation.
    startBoneNames = findStartBones(armatureObj)

    convertTransformMatrix = convertTransformMatrix @ mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()

    # Start geolayout
    if camera is not None:
        geolayoutGraph = GeolayoutGraph(name)
        cameraObj = getCameraObj(camera)
        meshGeolayout = saveCameraSettingsToGeolayout(geolayoutGraph, cameraObj, armatureObj, name + "_geo")
    else:
        geolayoutGraph = GeolayoutGraph(name + "_geo")
        if armatureObj.use_render_area:
            rootNode = TransformNode(StartRenderAreaNode(armatureObj.culling_radius))
        else:
            rootNode = TransformNode(StartNode())
        geolayoutGraph.startGeolayout.nodes.append(rootNode)
        meshGeolayout = geolayoutGraph.startGeolayout

    for i in range(len(startBoneNames)):
        startBoneName = startBoneNames[i]
        if i > 0:
            meshGeolayout.nodes.append(TransformNode(StartNode()))
        processBone(
            fModel,
            startBoneName,
            obj,
            armatureObj,
            convertTransformMatrix,
            None,
            None,
            None,
            None,
            meshGeolayout.nodes[i],
            [],
            name,
            meshGeolayout,
            geolayoutGraph,
            infoDict,
            convertTextureData,
        )

    children = meshGeolayout.nodes
    meshGeolayout.nodes = []
    for child in children:
        child_copy = copy.copy(child)
        child_copy.node = copy.copy(child_copy.node)
        meshGeolayout.nodes.append(generate_overrides(fModel, child_copy, [], meshGeolayout, geolayoutGraph))

    append_revert_to_geolayout(geolayoutGraph, fModel)
    add_overrides_to_fmodel(fModel)
    geolayoutGraph.generateSortedList()
    if inline:
        bleed_gfx = GeoLayoutBleed()
        bleed_gfx.bleed_geo_layout_graph(fModel, geolayoutGraph)
    # if DLFormat == DLFormat.GameSpecific:
    # 	geolayoutGraph.convertToDynamic()
    return geolayoutGraph, fModel


def convertObjectToGeolayout(
    obj, convertTransformMatrix, is_actor: bool, name, fModel: FModel, areaObj, DLFormat, convertTextureData
):
    inline = bpy.context.scene.exportInlineF3D
    if fModel is None:
        fModel = SM64Model(
            name,
            DLFormat,
            bpy.context.scene.fast64.sm64.gfx_write_method,
        )

    # convertTransformMatrix = convertTransformMatrix @ \
    # 	mathutils.Matrix.Diagonal(obj.scale).to_4x4()

    # Start geolayout
    if areaObj is not None:
        geolayoutGraph = GeolayoutGraph(name)
        # cameraObj = getCameraObj(camera)
        meshGeolayout = saveCameraSettingsToGeolayout(geolayoutGraph, areaObj, obj, name + "_geo")
        rootObj = areaObj
        if areaObj.fast64.sm64.area.set_fog:
            fog_data = FFogData(areaObj.area_fog_position, areaObj.area_fog_color)
        else:
            fog_data = None
        fModel.global_data.addAreaData(areaObj.areaIndex, FAreaData(fog_data))

    else:
        geolayoutGraph = GeolayoutGraph(name + "_geo")
        if obj.type == "MESH" and obj.use_render_area:
            rootNode = TransformNode(StartRenderAreaNode(obj.culling_radius))
        else:
            rootNode = TransformNode(StartNode())
        geolayoutGraph.startGeolayout.nodes.append(rootNode)
        meshGeolayout = geolayoutGraph.startGeolayout
        rootObj = obj

    # Duplicate objects to apply scale / modifiers / linked data
    tempObj, allObjs = duplicateHierarchy(
        rootObj, "ignore_render", True, None if areaObj is None else areaObj.areaIndex
    )
    try:
        processMesh(
            fModel,
            tempObj,
            convertTransformMatrix,
            meshGeolayout.nodes[0],
            geolayoutGraph.startGeolayout,
            geolayoutGraph,
            True,
            convertTextureData,
        )
        if is_actor and not meshGeolayout.has_data():
            raise PluginError("No gfx data to export, gfx export cancelled", PluginError.exc_warn)
    except Exception as e:
        raise Exception(str(e))
    finally:
        cleanupDuplicatedObjects(allObjs)
        rootObj.select_set(True)
        bpy.context.view_layer.objects.active = rootObj

    append_revert_to_geolayout(geolayoutGraph, fModel)
    add_overrides_to_fmodel(fModel)
    geolayoutGraph.generateSortedList()
    if inline:
        bleed_gfx = GeoLayoutBleed()
        bleed_gfx.bleed_geo_layout_graph(
            fModel, geolayoutGraph, use_rooms=None if areaObj is None else areaObj.enableRoomSwitch
        )
    # if DLFormat == DLFormat.GameSpecific:
    # 	geolayoutGraph.convertToDynamic()
    return geolayoutGraph, fModel


# C Export
def exportGeolayoutArmatureC(
    armatureObj,
    obj,
    convertTransformMatrix,
    dirPath,
    texDir,
    savePNG,
    texSeparate,
    camera,
    groupName,
    headerType,
    dirName,
    geoName,
    levelName,
    customExport,
    DLFormat,
):
    geolayoutGraph, fModel = convertArmatureToGeolayout(
        armatureObj, obj, convertTransformMatrix, camera, dirName, DLFormat, not savePNG
    )

    return saveGeolayoutC(
        geoName,
        dirName,
        geolayoutGraph,
        fModel,
        dirPath,
        texDir,
        savePNG,
        texSeparate,
        groupName,
        headerType,
        levelName,
        customExport,
        DLFormat,
    )


def exportGeolayoutObjectC(
    obj,
    convertTransformMatrix,
    dirPath,
    texDir,
    savePNG,
    texSeparate,
    groupName,
    headerType,
    dirName,
    geoName,
    levelName,
    customExport,
    DLFormat,
):
    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, True, dirName, None, None, DLFormat, not savePNG
    )

    return saveGeolayoutC(
        geoName,
        dirName,
        geolayoutGraph,
        fModel,
        dirPath,
        texDir,
        savePNG,
        texSeparate,
        groupName,
        headerType,
        levelName,
        customExport,
        DLFormat,
    )


def saveGeolayoutC(
    geoName,
    dirName,
    geolayoutGraph: GeolayoutGraph,
    fModel: FModel,
    exportDir,
    texDir,
    savePNG,
    texSeparate,
    groupName,
    headerType,
    levelName,
    customExport,
    DLFormat,
):
    dirPath, texDir = getExportDir(customExport, exportDir, headerType, levelName, texDir, dirName)

    dirName = toAlnum(dirName)
    groupName = toAlnum(groupName)
    geoDirPath = os.path.join(dirPath, toAlnum(dirName))

    if not os.path.exists(geoDirPath):
        os.mkdir(geoDirPath)

    if headerType == "Actor":
        scrollName = "actor_geo_" + dirName
    elif headerType == "Level":
        scrollName = levelName + "_level_geo_" + dirName
    elif headerType == "Custom":
        scrollName = "geo_" + dirName

    gfxFormatter = SM64GfxFormatter(ScrollMethod.Vertex)
    if not customExport and headerType == "Level":
        texExportPath = dirPath
    else:
        texExportPath = geoDirPath
    exportData = fModel.to_c(TextureExportSettings(texSeparate, savePNG, texDir, texExportPath), gfxFormatter)
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData
    texC = exportData.textureData

    scrollData = fModel.to_c_scroll(scrollName, gfxFormatter)
    geolayoutGraph.startGeolayout.name = geoName

    # Handle cases where geolayout name != folder name + _geo
    # if dirName == 'blue_fish':
    # 	geolayoutGraph.startGeolayout.name = 'fish_geo'
    # if dirName == 'bomb':
    # 	geolayoutGraph.startGeolayout.name = 'bowser_bomb_geo'
    # if dirName == 'book':
    # 	geolayoutGraph.startGeolayout.name = 'bookend_geo'
    # if dirName == 'bookend':
    # 	geolayoutGraph.startGeolayout.name = 'bookend_part_geo'
    # if dirName == 'bowser_flame':
    # 	geolayoutGraph.startGeolayout.name = 'bowser_flames_geo'
    # if dirName == 'capswitch':
    # 	geolayoutGraph.startGeolayout.name = 'cap_switch_geo'
    geoData = geolayoutGraph.to_c()

    if headerType == "Actor":
        matCInclude = Path("actors", dirName, "material.inc.c")
        matHInclude = Path("actors", dirName, "material.inc.h")
        headerInclude = '#include "actors/' + dirName + '/geo_header.h"'
    else:
        matCInclude = Path("levels", levelName, dirName, "material.inc.c")
        matHInclude = Path("levels", levelName, dirName, "material.inc.h")
        headerInclude = '#include "levels/' + levelName + "/" + dirName + '/geo_header.h"'

    modifyTexScrollFiles(exportDir, geoDirPath, scrollData)

    if DLFormat == DLFormat.Static:
        staticData.source += "\n" + dynamicData.source
        staticData.header = geoData.header + staticData.header + dynamicData.header
    else:
        geoData.source = writeMaterialFiles(
            exportDir,
            geoDirPath,
            headerInclude,
            matHInclude,
            dynamicData.header,
            dynamicData.source,
            geoData.source,
            customExport,
        )

    modelPath = os.path.join(geoDirPath, "model.inc.c")
    modelFile = open(modelPath, "w", newline="\n")
    modelFile.write(staticData.source)
    modelFile.close()

    if texSeparate:
        texPath = os.path.join(geoDirPath, "texture.inc.c")
        texFile = open(texPath, "w", newline="\n")
        texFile.write(texC.source)
        texFile.close()

    fModel.freePalettes()

    # save geolayout
    geoPath = os.path.join(geoDirPath, "geo.inc.c")
    geoFile = open(geoPath, "w", newline="\n")
    geoFile.write(geoData.source)
    geoFile.close()

    # save header
    headerPath = os.path.join(geoDirPath, "geo_header.h")
    cDefFile = open(headerPath, "w", newline="\n")
    cDefFile.write(staticData.header)
    cDefFile.close()

    fileStatus = None
    update_actor_includes(
        headerType,
        groupName,
        Path(dirPath),
        dirName,
        levelName,
        [Path("model.inc.c")],
        [Path("geo_header.h")],
        [Path("geo.inc.c")],
    )
    if not customExport:
        if headerType == "Actor":
            if dirName == "star" and bpy.context.scene.replaceStarRefs:
                replaceStarReferences(exportDir)
            if dirName == "transparent_star" and bpy.context.scene.replaceTransparentStarRefs:
                replaceTransparentStarReferences(exportDir)
            if dirName == "marios_cap" and bpy.context.scene.replaceCapRefs:
                replaceCapReferences(exportDir)

            """
			capPath = os.path.join(exportDir, 'actors/mario_cap/geo.inc.c')
			if dirName == 'marios_cap' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(capPath, 'marios\_cap\_geo\[\]', 'marios_cap_geo_old[]')
			if dirName == 'marios_metal_cap' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(capPath, 'marios\_metal\_cap\_geo\[\]', 'marios_metal_cap_geo_old[]')
			if dirName == 'marios_wing_cap' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(capPath, 'marios\_wing\_cap\_geo\[\]', 'marios_wing_cap_geo_old[]')
			if dirName == 'marios_winged_metal_cap' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(capPath, 'marios\_winged\_metal\_cap\_geo\[\]', 'marios_winged_metal_cap_geo_old[]')

			koopaPath = os.path.join(exportDir, 'actors/koopa/geo.inc.c')
			if dirName == 'koopa_with_shell' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(koopaPath, 'koopa\_with\_shell\_geo\[\]', 'koopa_with_shell_old[]')
			if dirName == 'koopa_without_shell' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(koopaPath, 'koopa\_without\_shell\_geo\[\]', 'koopa_without_shell_old[]')

			bobombPath = os.path.join(exportDir, 'actors/bobomb/geo.inc.c')
			if dirName == 'black_bobomb' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(bobombPath, 'black\_bobomb\_geo\[\]', 'black\_bobomb\_geo\_old\[\]')
			if dirName == 'bobomb_buddy' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(bobombPath, 'bobomb\_buddy\_geo\[\]', 'bobomb\_buddy\_geo\_old\[\]')

			bubblePath = os.path.join(exportDir, 'actors/bubble/geo.inc.c')
			if dirName == 'purple_marble' and bpy.context.scene.modifyOldGeo:
				replaceDLReferenceInGeo(bubblePath, 'purple\_marble\_geo\[\]', 'purple\_marble\_geo\_old\[\]')

			# Instances where a geo file has multiple similar geolayouts
			if dirName == 'bowser':
				appendSecondaryGeolayout(geoDirPath, 'bowser', 'bowser2')
			if dirName == 'bowling_ball':
				appendSecondaryGeolayout(geoDirPath, 'bowling_ball', 'bowling_ball_track')
			if dirName == 'blue_fish':
				appendSecondaryGeolayout(geoDirPath, 'fish', 'fish_shadow', 'GEO_SHADOW(SHADOW_CIRCLE_4_VERTS, 0x9B, 50)')
			if dirName == 'bowser_key':
				appendSecondaryGeolayout(geoDirPath, 'bowser_key', 'bowser_key_cutscene')
			if dirName == 'breakable_box':
				appendSecondaryGeolayout(geoDirPath, 'breakable_box', 'breakable_box_small')
			if dirName == 'bully':
				appendSecondaryGeolayout(geoDirPath, 'bully', 'bully_boss', 'GEO_SCALE(0x00, 0x2000), GEO_NODE_OPEN(),')
			"""

            texscrollIncludeC = '#include "actors/' + dirName + '/texscroll.inc.c"'
            texscrollIncludeH = '#include "actors/' + dirName + '/texscroll.inc.h"'
            texscrollGroup = groupName
            texscrollGroupInclude = '#include "actors/' + groupName + '.h"'

        elif headerType == "Level":
            texscrollIncludeC = '#include "levels/' + levelName + "/" + dirName + '/texscroll.inc.c"'
            texscrollIncludeH = '#include "levels/' + levelName + "/" + dirName + '/texscroll.inc.h"'
            texscrollGroup = levelName
            texscrollGroupInclude = '#include "levels/' + levelName + '/header.h"'

        fileStatus = modifyTexScrollHeadersGroup(
            exportDir,
            texscrollIncludeC,
            texscrollIncludeH,
            texscrollGroup,
            scrollData.topLevelScrollFunc,
            texscrollGroupInclude,
            scrollData.hasScrolling(),
        )

        if DLFormat != DLFormat.Static:  # Change this
            write_material_headers(Path(exportDir), matCInclude, matHInclude)

    return staticData.header, fileStatus


# Insertable Binary
def exportGeolayoutArmatureInsertableBinary(armatureObj, obj, convertTransformMatrix, filepath, camera):
    geolayoutGraph, fModel = convertArmatureToGeolayout(
        armatureObj, obj, convertTransformMatrix, camera, armatureObj.name, DLFormat.Static, True
    )

    saveGeolayoutInsertableBinary(geolayoutGraph, fModel, filepath)


def exportGeolayoutObjectInsertableBinary(obj, convertTransformMatrix, filepath):
    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, True, obj.name, None, None, DLFormat.Static, True
    )

    saveGeolayoutInsertableBinary(geolayoutGraph, fModel, filepath)


def saveGeolayoutInsertableBinary(geolayoutGraph, fModel, filepath):
    data, startRAM = getBinaryBank0GeolayoutData(fModel, geolayoutGraph, 0, [0, 0xFFFFFF])

    address_ptrs = geolayoutGraph.get_ptr_addresses()
    address_ptrs.extend(fModel.get_ptr_addresses(get_F3D_GBI()))

    writeInsertableFile(
        filepath, insertableBinaryTypes["Geolayout"], address_ptrs, geolayoutGraph.startGeolayout.startAddress, data
    )


# Binary Bank 0 Export
def exportGeolayoutArmatureBinaryBank0(
    romfile,
    armatureObj,
    obj,
    exportRange,
    convertTransformMatrix,
    levelCommandPos,
    modelID,
    textDumpFilePath,
    RAMAddr,
    camera,
):
    geolayoutGraph, fModel = convertArmatureToGeolayout(
        armatureObj, obj, convertTransformMatrix, camera, armatureObj.name, DLFormat.Static, True
    )

    return saveGeolayoutBinaryBank0(
        romfile, fModel, geolayoutGraph, exportRange, levelCommandPos, modelID, textDumpFilePath, RAMAddr
    )


def exportGeolayoutObjectBinaryBank0(
    romfile,
    obj,
    exportRange,
    convertTransformMatrix,
    levelCommandPos,
    modelID,
    textDumpFilePath,
    RAMAddr,
):
    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, True, obj.name, None, None, DLFormat.Static, True
    )

    return saveGeolayoutBinaryBank0(
        romfile, fModel, geolayoutGraph, exportRange, levelCommandPos, modelID, textDumpFilePath, RAMAddr
    )


def saveGeolayoutBinaryBank0(
    romfile, fModel, geolayoutGraph, exportRange, levelCommandPos, modelID, textDumpFilePath, RAMAddr
):
    data, startRAM = getBinaryBank0GeolayoutData(fModel, geolayoutGraph, RAMAddr, exportRange)
    segmentData = copy.copy(bank0Segment)

    startAddress = get64bitAlignedAddr(exportRange[0])
    romfile.seek(startAddress)
    romfile.write(data)

    geoStart = geolayoutGraph.startGeolayout.startAddress
    segPointerData = encodeSegmentedAddr(geoStart, segmentData)
    geoWriteLevelCommand(romfile, segPointerData, levelCommandPos, modelID)
    geoWriteTextDump(textDumpFilePath, geolayoutGraph, segmentData)

    return ((startAddress, startAddress + len(data)), startRAM + 0x80000000, geoStart + 0x80000000)


def getBinaryBank0GeolayoutData(fModel, geolayoutGraph, RAMAddr, exportRange):
    fModel.freePalettes()
    segmentData = copy.copy(bank0Segment)
    startRAM = get64bitAlignedAddr(RAMAddr)
    nonGeoStartAddr = startRAM + geolayoutGraph.size()

    geolayoutGraph.set_addr(startRAM)
    addrRange = fModel.set_addr(nonGeoStartAddr)
    addrEndInROM = addrRange[1] - startRAM + exportRange[0]
    if addrEndInROM > exportRange[1]:
        raise PluginError(
            "Size too big: Data ends at " + hex(addrEndInROM) + ", which is larger than the specified range."
        )
    bytesIO = BytesIO()
    # actualRAMAddr = get64bitAlignedAddr(RAMAddr)
    geolayoutGraph.save_binary(bytesIO, segmentData)
    fModel.save_binary(bytesIO, segmentData)

    data = bytesIO.getvalue()[startRAM:]
    bytesIO.close()
    return data, startRAM


# Binary Export
def exportGeolayoutArmatureBinary(
    romfile,
    armatureObj,
    obj,
    exportRange,
    convertTransformMatrix,
    levelData,
    levelCommandPos,
    modelID,
    textDumpFilePath,
    camera,
):
    geolayoutGraph, fModel = convertArmatureToGeolayout(
        armatureObj, obj, convertTransformMatrix, camera, armatureObj.name, DLFormat.Static, True
    )

    return saveGeolayoutBinary(
        romfile, geolayoutGraph, fModel, exportRange, levelData, levelCommandPos, modelID, textDumpFilePath
    )


def exportGeolayoutObjectBinary(
    romfile,
    obj,
    exportRange,
    convertTransformMatrix,
    levelData,
    levelCommandPos,
    modelID,
    textDumpFilePath,
):
    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, True, obj.name, None, None, DLFormat.Static, True
    )

    return saveGeolayoutBinary(
        romfile, geolayoutGraph, fModel, exportRange, levelData, levelCommandPos, modelID, textDumpFilePath
    )


def saveGeolayoutBinary(
    romfile, geolayoutGraph, fModel, exportRange, levelData, levelCommandPos, modelID, textDumpFilePath
):
    fModel.freePalettes()

    # Get length of data, then actually write it after relative addresses
    # are found.
    startAddress = get64bitAlignedAddr(exportRange[0])
    nonGeoStartAddr = startAddress + geolayoutGraph.size()

    geolayoutGraph.set_addr(startAddress)
    addrRange = fModel.set_addr(nonGeoStartAddr)
    if addrRange[1] > exportRange[1]:
        raise PluginError(
            "Size too big: Data ends at " + hex(addrRange[1]) + ", which is larger than the specified range."
        )
    geolayoutGraph.save_binary(romfile, levelData)
    fModel.save_binary(romfile, levelData)

    geoStart = geolayoutGraph.startGeolayout.startAddress
    segPointerData = encodeSegmentedAddr(geoStart, levelData)
    geoWriteLevelCommand(romfile, segPointerData, levelCommandPos, modelID)
    geoWriteTextDump(textDumpFilePath, geolayoutGraph, levelData)

    return (startAddress, addrRange[1]), bytesToHex(segPointerData)


def geoWriteLevelCommand(romfile, segPointerData, levelCommandPos, modelID):
    if levelCommandPos is not None and modelID is not None:
        romfile.seek(levelCommandPos + 3)
        romfile.write(modelID.to_bytes(1, byteorder="big"))
        romfile.seek(levelCommandPos + 4)
        romfile.write(segPointerData)


def geoWriteTextDump(textDumpFilePath, geolayoutGraph, levelData):
    if textDumpFilePath is not None:
        openfile = open(textDumpFilePath, "w", newline="\n")
        openfile.write(geolayoutGraph.toTextDump(levelData))
        openfile.close()


def generate_overrides(
    fModel: SM64Model,
    transform_node: TransformNode,
    switch_stack: list[SwitchOverrideNode],
    geolayout: Geolayout,
    graph: GeolayoutGraph,
    name: str = "",
):
    node = transform_node.node
    children = transform_node.children
    transform_node.children = []
    if isinstance(node, JumpNode):
        start_nodes, new_name = node.geolayout.nodes, name
        if switch_stack:
            new_name = f"{node.geolayout.name}{name}"
            new_geolayout = graph.addGeolayout(transform_node, new_name)
            node.geolayout = new_geolayout
            graph.addGeolayoutCall(geolayout, new_geolayout)
        else:
            node.geolayout.nodes = []
        for child in start_nodes:
            child_copy = copy.copy(child)
            child_copy.node = copy.copy(child_copy.node)
            node.geolayout.nodes.append(
                generate_overrides(fModel, child_copy, switch_stack.copy(), geolayout, graph, name)
            )
    elif node.hasDL or hasattr(node, "drawLayer"):
        draw_overrides = fModel.draw_overrides.setdefault(node.fMesh, {})
        for i, override_node in enumerate(switch_stack):
            if node.hasDL:
                save_override_draw(
                    fModel,
                    node.DLmicrocode,
                    name,
                    draw_overrides,
                    node.override_hash,
                    override_node.material,
                    override_node.specificMat,
                    override_node.drawLayer,
                    override_node.overrideType,
                    node.fMesh,
                    node,
                    node.drawLayer,
                    True,
                )
            if override_node.drawLayer is not None and node.drawLayer != override_node.drawLayer:
                node.drawLayer = override_node.drawLayer
                if node.fMesh is not None:
                    node.fMesh.override_layer = True
        if node.hasDL:
            nodes = draw_overrides.setdefault(node.override_hash, GfxOverride(node.DLmicrocode, [])).nodes
            nodes.append(node)
    for i, child in enumerate(children):
        child_copy = copy.copy(child)
        child_node_copy = child_copy.node = copy.copy(child_copy.node)
        if isinstance(child_node_copy, SwitchOverrideNode):
            child_copy.parent = None
            assert i != 0, "Switch override must not be the first child of its parent"
            override_switch_stack = [*switch_stack, child_node_copy]
            option0 = copy.copy(children[0])
            option0_copy = copy.copy(option0)
            new_name = toAlnum(f"{name}_opt_{i}")
            new_geolayout = graph.addGeolayout(transform_node, geolayout.name + new_name)
            graph.addGeolayoutCall(geolayout, new_geolayout)
            new_geolayout.nodes.append(
                generate_overrides(fModel, option0_copy, override_switch_stack.copy(), new_geolayout, graph, new_name)
            )
            option_child = TransformNode(JumpNode(True, new_geolayout))
            transform_node.children.append(option_child)
            option_child.parent = transform_node
        else:
            generate_overrides(fModel, child_copy, switch_stack.copy(), geolayout, graph, name)
            transform_node.children.append(child_copy)
            child_copy.parent = transform_node
    return transform_node


def addParentNode(parentTransformNode: TransformNode, geoNode):
    transformNode = TransformNode(geoNode)
    transformNode.parent = parentTransformNode
    parentTransformNode.children.append(transformNode)
    return transformNode


def duplicateNode(transformNode, parentNode, index):
    optionNode = TransformNode(copy.copy(transformNode.node))
    optionNode.parent = parentNode
    parentNode.children.insert(index, optionNode)
    return optionNode


def partOfGeolayout(obj):
    useGeoEmpty = obj.type == "EMPTY" and checkSM64EmptyUsesGeoLayout(obj)

    return obj.type == "MESH" or useGeoEmpty


def getSwitchChildren(areaRoot):
    geoChildren = [child for child in areaRoot.children if partOfGeolayout(child)]
    alphabeticalChildren = sorted(geoChildren, key=lambda childObj: childObj.original_name.lower())
    return alphabeticalChildren


def setRooms(obj, roomIndex=None):
    # Child objects
    if roomIndex is not None:
        obj.room_num = roomIndex
        for childObj in obj.children:
            setRooms(childObj, roomIndex)

    # Area root object
    else:
        alphabeticalChildren = getSwitchChildren(obj)
        for i in range(len(alphabeticalChildren)):
            setRooms(alphabeticalChildren[i], i)  # index starts at 1, but 0 is reserved for no room.


def isZeroRotation(rotate: mathutils.Quaternion):
    eulerRot = rotate.to_euler(geoNodeRotateOrder)
    return (
        convertEulerFloatToShort(eulerRot[0]) == 0
        and convertEulerFloatToShort(eulerRot[1]) == 0
        and convertEulerFloatToShort(eulerRot[2]) == 0
    )


def isZeroTranslation(translate: mathutils.Vector):
    return (
        convertFloatToShort(translate[0]) == 0
        and convertFloatToShort(translate[1]) == 0
        and convertFloatToShort(translate[2]) == 0
    )


def isZeroScaleChange(scale: mathutils.Vector):
    return (
        int(round(scale[0] * 0x10000)) == 0x10000
        and int(round(scale[1] * 0x10000)) == 0x10000
        and int(round(scale[2] * 0x10000)) == 0x10000
    )


def getOptimalNode(translate, rotate, drawLayer, hasDL, zeroTranslation, zeroRotation):
    if zeroRotation and zeroTranslation:
        node = DisplayListNode(drawLayer)
    elif zeroRotation:
        node = TranslateNode(drawLayer, hasDL, translate)
    elif zeroTranslation:
        node = RotateNode(drawLayer, hasDL, rotate)
    else:
        node = TranslateRotateNode(drawLayer, 0, hasDL, translate, rotate)
    return node


def processPreInlineGeo(
    inlineGeoConfig: InlineGeolayoutObjConfig, obj: bpy.types.Object, parentTransformNode: TransformNode
):
    if inlineGeoConfig.name == "Geo ASM":
        node = FunctionNode(obj.fast64.sm64.geo_asm.func, obj.fast64.sm64.geo_asm.param)
    elif inlineGeoConfig.name == "Geo Branch":
        node = JumpNode(True, None, obj.geoReference)
    elif inlineGeoConfig.name == "Geo Displaylist":
        node = DisplayListNode(int(obj.draw_layer_static), obj.dlReference)
    addParentNode(parentTransformNode, node)  # Allow this node to be translated/rotated


def processInlineGeoNode(
    inlineGeoConfig: InlineGeolayoutObjConfig,
    obj: bpy.types.Object,
    parentTransformNode: TransformNode,
    translate: mathutils.Vector,
    rotate: mathutils.Quaternion,
    scale: mathutils.Vector,
):
    node = None
    if inlineGeoConfig.name == "Geo Translate/Rotate":
        node = TranslateRotateNode(obj.draw_layer_static, 0, obj.useDLReference, translate, rotate, obj.dlReference)
    elif inlineGeoConfig.name == "Geo Billboard":
        node = BillboardNode(obj.draw_layer_static, obj.useDLReference, translate, obj.dlReference)
    elif inlineGeoConfig.name == "Geo Translate Node":
        node = TranslateNode(obj.draw_layer_static, obj.useDLReference, translate, obj.dlReference)
    elif inlineGeoConfig.name == "Geo Rotation Node":
        node = RotateNode(obj.draw_layer_static, obj.useDLReference, rotate, obj.dlReference)
    elif inlineGeoConfig.name == "Geo Scale":
        node = ScaleNode(obj.draw_layer_static, scale[0], obj.useDLReference, obj.dlReference)
    elif inlineGeoConfig.name == "Custom":
        local_matrix = (
            mathutils.Matrix.Translation(translate)
            @ rotate.to_matrix().to_4x4()
            @ mathutils.Matrix.Diagonal(scale).to_4x4()
        )
        node = obj.fast64.sm64.custom.get_final_cmd(
            obj,
            bpy.context.scene.fast64.sm64.blender_to_sm64_scale,
            z_up_to_y_up_matrix @ mathutils.Matrix(obj.get("original_mtx_world")) @ z_up_to_y_up_matrix.inverted(),
            local_matrix,
            obj.draw_layer_static,
            obj.useDLReference,
            obj.dlReference,
        )
        node, parentTransformNode, _, _, _ = get_custom_cmd_with_transform(
            node, parentTransformNode, translate, rotate, scale
        )
    else:
        raise PluginError(f"Ooops! Didnt implement inline geo exporting for {inlineGeoConfig.name}")

    return node, parentTransformNode


# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
def processMesh(
    fModel: FModel,
    obj: bpy.types.Object,
    transformMatrix: mathutils.Matrix,
    parentTransformNode: TransformNode,
    geolayout: Geolayout,
    geolayoutGraph: GeolayoutGraph,
    isRoot: bool,
    convertTextureData: bool,
):
    # final_transform = copy.deepcopy(transformMatrix)

    useGeoEmpty = obj.type == "EMPTY" and checkSM64EmptyUsesGeoLayout(obj)

    useSwitchNode = obj.type == "EMPTY" and obj.sm64_obj_type == "Switch"

    useInlineGeo = obj.type == "EMPTY" and checkIsSM64InlineGeoLayout(obj)

    addRooms = isRoot and obj.type == "EMPTY" and obj.sm64_obj_type == "Area Root" and obj.enableRoomSwitch

    # if useAreaEmpty and areaIndex is not None and obj.areaIndex != areaIndex:
    # 	return

    inlineGeoConfig: InlineGeolayoutObjConfig = inlineGeoLayoutObjects.get(obj.sm64_obj_type)
    processed_inline_geo = False

    isPreInlineGeoLayout = checkIsSM64PreInlineGeoLayout(obj)
    if useInlineGeo and isPreInlineGeoLayout:
        processed_inline_geo = True
        processPreInlineGeo(inlineGeoConfig, obj, parentTransformNode)

    # Its okay to return if ignore_render, because when we duplicated obj hierarchy we stripped all
    # ignore_renders from geolayout.
    if not partOfGeolayout(obj) or obj.ignore_render:
        return

    if isRoot:
        translate = mathutils.Vector((0, 0, 0))
        rotate = mathutils.Quaternion()
        scale = mathutils.Vector((1, 1, 1))
    elif obj.get("original_mtx"):  # object is instanced or a transformation
        orig_mtx = mathutils.Matrix(obj.get("original_mtx"))
        translate, rotate, scale = orig_mtx.decompose()
        translate = translate_blender_to_n64(translate)
        rotate = rotate_quat_blender_to_n64(rotate)
    else:  # object is NOT instanced
        translate, rotate, scale = obj.matrix_local.decompose()

    zeroRotation = isZeroRotation(rotate)
    zeroTranslation = isZeroTranslation(translate)
    zeroScaleChange = isZeroScaleChange(scale)

    if useSwitchNode or addRooms:  # Specific empty types
        if useSwitchNode:
            switchFunc = obj.switchFunc
            switchParam = obj.switchParam
        elif addRooms:
            switchFunc = "geo_switch_area"
            switchParam = len(obj.children)

        # Rooms are not set here (since this is just a copy of the original hierarchy)
        # They should be set previously, using setRooms()
        preRoomSwitchParentNode = parentTransformNode
        parentTransformNode = addParentNode(parentTransformNode, SwitchNode(switchFunc, switchParam, obj.original_name))
        alphabeticalChildren = getSwitchChildren(obj)
        for i in range(len(alphabeticalChildren)):
            childObj = alphabeticalChildren[i]
            if i == 0 and addRooms:  # Outside room system
                # TODO: Allow users to specify whether this should be rendered before or after rooms (currently, it is after)
                processMesh(
                    fModel,
                    childObj,
                    transformMatrix,
                    preRoomSwitchParentNode,
                    geolayout,
                    geolayoutGraph,
                    False,
                    convertTextureData,
                )
            else:
                optionGeolayout = geolayoutGraph.addGeolayout(
                    childObj, fModel.name + "_" + childObj.original_name + "_geo"
                )
                geolayoutGraph.addJumpNode(parentTransformNode, geolayout, optionGeolayout)
                if not zeroRotation or not zeroTranslation:
                    startNode = TransformNode(
                        getOptimalNode(translate, rotate, 1, False, zeroTranslation, zeroRotation)
                    )
                else:
                    startNode = TransformNode(StartNode())
                optionGeolayout.nodes.append(startNode)
                processMesh(
                    fModel,
                    childObj,
                    transformMatrix,
                    startNode,
                    optionGeolayout,
                    geolayoutGraph,
                    False,
                    convertTextureData,
                )

    else:
        if useInlineGeo and not processed_inline_geo:
            node, parentTransformNode = processInlineGeoNode(
                inlineGeoConfig, obj, parentTransformNode, translate, rotate, scale
            )
            processed_inline_geo = True

        elif obj.geo_cmd_static == "Optimal" or useGeoEmpty:
            if not zeroScaleChange:
                # - first translate/rotate without a DL
                # - then child -> scale with DL
                if not zeroTranslation or not zeroRotation:
                    pNode = getOptimalNode(
                        translate, rotate, int(obj.draw_layer_static), False, zeroTranslation, zeroRotation
                    )
                    parentTransformNode = addParentNode(parentTransformNode, pNode)
                node = ScaleNode(int(obj.draw_layer_static), scale[0], True)
            else:
                node = getOptimalNode(
                    translate, rotate, int(obj.draw_layer_static), True, zeroTranslation, zeroRotation
                )

        elif obj.geo_cmd_static == "DisplayListWithOffset":
            if not zeroRotation or not zeroScaleChange:
                # translate/rotate -> scale -> DisplayListWithOffset
                node = DisplayListWithOffsetNode(int(obj.draw_layer_static), True, mathutils.Vector((0, 0, 0)))

                parentTransformNode = addParentNode(
                    parentTransformNode, TranslateRotateNode(1, 0, False, translate, rotate)
                )

                if not zeroScaleChange:
                    parentTransformNode = addParentNode(
                        parentTransformNode, ScaleNode(int(obj.draw_layer_static), scale[0], False)
                    )
            else:
                node = DisplayListWithOffsetNode(int(obj.draw_layer_static), True, translate)

        else:  # Billboard
            if not zeroRotation or not zeroScaleChange:  # If rotated or scaled
                # Order here MUST be billboard with translation -> rotation -> scale -> displaylist
                node = DisplayListNode(int(obj.draw_layer_static))

                # Add billboard to top layer with translation
                parentTransformNode = addParentNode(
                    parentTransformNode, BillboardNode(int(obj.draw_layer_static), False, translate)
                )

                if not zeroRotation:
                    # Add rotation to top layer
                    parentTransformNode = addParentNode(
                        parentTransformNode, RotateNode(int(obj.draw_layer_static), False, rotate)
                    )

                if not zeroScaleChange:
                    # Add scale node after billboard
                    parentTransformNode = addParentNode(
                        parentTransformNode, ScaleNode(int(obj.draw_layer_static), scale[0], False)
                    )
            else:  # Use basic billboard node
                node = BillboardNode(int(obj.draw_layer_static), True, translate)

        transformNode = TransformNode(node)

        if obj.type != "EMPTY" and (obj.use_render_range or obj.add_shadow or obj.add_func):
            parentTransformNode.children.append(transformNode)
            transformNode.parent = parentTransformNode
            transformNode.node.hasDL = False
            parentTransformNode = transformNode

            node = DisplayListNode(int(obj.draw_layer_static))
            transformNode = TransformNode(node)

            if obj.use_render_range:
                parentTransformNode = addParentNode(
                    parentTransformNode, RenderRangeNode(obj.render_range[0], obj.render_range[1])
                )

            if obj.add_shadow:
                parentTransformNode = addParentNode(
                    parentTransformNode, ShadowNode(obj.shadow_type, obj.shadow_solidity, obj.shadow_scale)
                )

            if obj.add_func:
                geo_asm = obj.fast64.sm64.geo_asm
                addParentNode(parentTransformNode, FunctionNode(geo_asm.func, geo_asm.param))

            # Make sure to add additional cases to if statement above

        if obj.type == "EMPTY":
            fMeshes = {}
        elif obj.get("instanced_mesh_name"):
            temp_obj = get_obj_temp_mesh(obj)
            if temp_obj is None:
                raise ValueError(
                    "The source of an instanced mesh could not be found. Please contact a Fast64 maintainer for support."
                )

            src_meshes = temp_obj.get("src_meshes", [])

            def find_draw_by_name(name):
                for fmesh in fModel.meshes.values():
                    for fmesh_draw in [fmesh.draw] + fmesh.draw_overrides:
                        if fmesh_draw.name == name:
                            return fmesh_draw
                return None

            if len(src_meshes):
                fMeshes = {}
                name = src_meshes[0]["dl_name"]
                node.dlRef = find_draw_by_name(name)
                node.drawLayer = src_meshes[0]["layer"]
                processed_inline_geo = True

                for src_mesh in src_meshes[1:]:
                    additionalNode = (
                        DisplayListNode(src_mesh["layer"], src_mesh["dl_name"])
                        if not isinstance(node, BillboardNode)
                        else BillboardNode(src_mesh["layer"], True, [0, 0, 0], src_mesh["dl_name"])
                    )
                    additionalTransformNode = TransformNode(additionalNode)
                    transformNode.children.append(additionalTransformNode)
                    additionalTransformNode.parent = transformNode
                    additionalTransformNode.revert_previous_mat = (
                        additionalTransformNode.revert_after_mat
                    ) = obj.bleed_independently

            else:
                triConverterInfo = TriangleConverterInfo(
                    temp_obj, None, fModel.f3d, transformMatrix, getInfoDict(temp_obj)
                )
                fMeshes = saveStaticModel(
                    triConverterInfo, fModel, temp_obj, transformMatrix, fModel.name, convertTextureData, False, "sm64"
                )
                if fMeshes:
                    temp_obj["src_meshes"] = [
                        ({"dl_name": fMesh.draw.name, "layer": drawLayer}) for drawLayer, fMesh in fMeshes.items()
                    ]
                else:
                    # TODO: Display warning to the user that there is an object that doesn't have polygons
                    print("Object", obj.original_name, "does not have any polygons.")

        else:
            triConverterInfo = TriangleConverterInfo(obj, None, fModel.f3d, transformMatrix, getInfoDict(obj))
            fMeshes = saveStaticModel(
                triConverterInfo, fModel, obj, transformMatrix, fModel.name, convertTextureData, False, "sm64"
            )

        if fMeshes is None or len(fMeshes) == 0:
            if not processed_inline_geo or isPreInlineGeoLayout:
                node.hasDL = False
        else:
            firstNodeProcessed = False
            node: BaseDisplayListNode
            for drawLayer, fMesh in fMeshes.items():
                if not firstNodeProcessed:
                    node.DLmicrocode = fMesh.draw
                    node.fMesh = fMesh
                    node.drawLayer = drawLayer  # previous drawLayer assigments useless?
                    firstNodeProcessed = True
                else:
                    additionalNode = (
                        DisplayListNode(drawLayer)
                        if not isinstance(node, BillboardNode)
                        else BillboardNode(drawLayer, True, [0, 0, 0])
                    )
                    additionalNode.DLmicrocode = fMesh.draw
                    additionalNode.fMesh = fMesh
                    additionalTransformNode = TransformNode(additionalNode)
                    additionalTransformNode.revert_previous_mat = (
                        additionalTransformNode.revert_after_mat
                    ) = obj.bleed_independently
                    transformNode.children.append(additionalTransformNode)
                    additionalTransformNode.parent = transformNode

        parentTransformNode.children.append(transformNode)
        transformNode.parent = parentTransformNode
        transformNode.revert_previous_mat = transformNode.revert_after_mat = obj.bleed_independently

        alphabeticalChildren = sorted(obj.children, key=lambda childObj: childObj.original_name.lower())
        for childObj in alphabeticalChildren:
            processMesh(
                fModel, childObj, transformMatrix, transformNode, geolayout, geolayoutGraph, False, convertTextureData
            )


# need to remember last geometry holding parent bone.
# to do skinning, add the 0x15 command before any non-geometry bone groups.
#

# transformMatrix is a constant matrix to apply to verts,
# not related to heirarchy.

# lastTransformParentName: last parent with mesh data.
# lastDeformParentName: last parent in transform node category.
# this may or may not include mesh data.

# If an armature is rotated, its bones' local_matrix will remember original
# rotation. Thus we don't want a bone's matrix relative to armature, but
# relative to the root bone of the armature.


def processBone(
    fModel,
    boneName,
    obj,
    armatureObj,
    transformMatrix,
    lastTranslateName,
    lastRotateName,
    last_scale_name,
    lastDeformName,
    parentTransformNode,
    materialOverrides,
    namePrefix,
    geolayout,
    geolayoutGraph,
    infoDict,
    convertTextureData,
):
    bone = armatureObj.data.bones[boneName]
    bone_props: "SM64_BoneProperties" = bone.fast64.sm64

    poseBone = armatureObj.pose.bones[boneName]
    final_transform = copy.deepcopy(transformMatrix)
    materialOverrides = copy.copy(materialOverrides)

    if bone.geo_cmd == "Ignore":
        return

    # Get translate
    if lastTranslateName is not None:
        translateParent = armatureObj.data.bones[lastTranslateName]
        translate = (translateParent.matrix_local.inverted() @ bone.matrix_local).decompose()[0]
    else:
        translateParent = None
        translate = bone.matrix_local.decompose()[0]

    # Get rotate
    if lastRotateName is not None:
        rotateParent = armatureObj.data.bones[lastRotateName]
        rotate = (rotateParent.matrix_local.inverted() @ bone.matrix_local).decompose()[1]
    else:
        rotateParent = None
        rotate = bone.matrix_local.decompose()[1]

    # Get scale
    if last_scale_name is not None:
        scaleParent = armatureObj.data.bones[last_scale_name]
        scale = (scaleParent.matrix_local.inverted() @ bone.matrix_local).decompose()[2]
    else:
        scaleParent = None
        scale = bone.matrix_local.decompose()[2]

    translation = mathutils.Matrix.Translation(translate)
    rotation = rotate.to_matrix().to_4x4()
    zeroTranslation = isZeroTranslation(translate)
    zeroRotation = isZeroRotation(rotate)
    zero_scale = isZeroScaleChange(scale)

    # hasDL = bone.use_deform
    hasDL = True
    if bone.geo_cmd == "DisplayListWithOffset":
        if not zeroRotation:
            node = DisplayListWithOffsetNode(int(bone.draw_layer), hasDL, mathutils.Vector((0, 0, 0)))

            parentTransformNode = addParentNode(
                parentTransformNode, TranslateRotateNode(1, 0, False, translate, rotate)
            )

            lastTranslateName = boneName
            lastRotateName = boneName
        else:
            node = DisplayListWithOffsetNode(int(bone.draw_layer), hasDL, translate)
            lastTranslateName = boneName

        final_transform = transformMatrix @ translation

    elif bone.geo_cmd == "Function":
        if bone.geo_func == "":
            raise PluginError("Function bone " + boneName + " function value is empty.")
        node = FunctionNode(bone.geo_func, bone.func_param)
    elif bone.geo_cmd == "HeldObject":
        if bone.geo_func == "":
            raise PluginError("Held object bone " + boneName + " function value is empty.")
        node = HeldObjectNode(bone.geo_func, translate)
    else:
        if bone.geo_cmd == "Switch":
            # This is done so we can easily calculate transforms
            # of switch options.

            if bone.geo_func == "":
                raise PluginError("Switch bone " + boneName + " function value is empty.")
            node = SwitchNode(bone.geo_func, bone.func_param, boneName)
            processSwitchBoneMatOverrides(materialOverrides, bone)

        elif bone.geo_cmd == "Start":
            node = StartNode()
        elif bone.geo_cmd == "TranslateRotate":
            drawLayer = int(bone.draw_layer)
            fieldLayout = int(bone.field_layout)

            node = TranslateRotateNode(drawLayer, fieldLayout, hasDL, translate, rotate)

            if node.fieldLayout == 0:
                final_transform = transformMatrix @ translation @ rotation
                lastTranslateName = boneName
                lastRotateName = boneName
            elif node.fieldLayout == 1:
                final_transform = transformMatrix @ translation
                lastTranslateName = boneName
            elif node.fieldLayout == 2:
                final_transform = transformMatrix @ rotation
                lastRotateName = boneName
            else:
                yRot = rotate.to_euler().y
                rotation = mathutils.Euler((0, yRot, 0)).to_matrix().to_4x4()
                final_transform = transformMatrix @ rotation
                lastRotateName = boneName

        elif bone.geo_cmd == "Translate":
            node = TranslateNode(int(bone.draw_layer), hasDL, translate)
            final_transform = transformMatrix @ translation
            lastTranslateName = boneName
        elif bone.geo_cmd == "Rotate":
            node = RotateNode(int(bone.draw_layer), hasDL, rotate)
            final_transform = transformMatrix @ rotation
            lastRotateName = boneName
        elif bone.geo_cmd == "Billboard":
            node = BillboardNode(int(bone.draw_layer), hasDL, translate)
            final_transform = transformMatrix @ translation
            lastTranslateName = boneName
        elif bone.geo_cmd == "DisplayList":
            node = DisplayListNode(int(bone.draw_layer))
            if not armatureObj.data.bones[boneName].use_deform:
                raise PluginError(
                    "Display List (0x15) "
                    + boneName
                    + " must be a deform bone. Make sure deform is checked in bone properties."
                )
        elif bone.geo_cmd == "Shadow":
            shadowType = int(bone.shadow_type)
            shadowSolidity = bone.shadow_solidity
            shadowScale = bone.shadow_scale
            node = ShadowNode(shadowType, shadowSolidity, shadowScale)
        elif bone.geo_cmd == "Scale":
            node = ScaleNode(int(bone.draw_layer), bone.geo_scale, hasDL)
            final_transform = transformMatrix @ mathutils.Matrix.Scale(node.scaleValue, 4)
        elif bone.geo_cmd == "StartRenderArea":
            node = StartRenderAreaNode(bone.culling_radius)
        elif bone.geo_cmd == "Custom":
            local_matrix = mathutils.Matrix.LocRotScale(translate, rotate, scale)
            world_matrix = z_up_to_y_up_matrix @ bone.matrix_local @ z_up_to_y_up_matrix.inverted()
            node = bone_props.custom.get_final_cmd(
                bone, bpy.context.scene.fast64.sm64.blender_to_sm64_scale, world_matrix, local_matrix, None, hasDL
            )
            node, parentTransformNode, has_translation, has_rotation, has_scale = get_custom_cmd_with_transform(
                node, parentTransformNode, translate, rotate, scale
            )
            if has_translation:
                lastTranslateName = boneName
            elif has_rotation:
                lastRotateName = boneName
            elif has_scale:
                last_scale_name = boneName
        else:
            raise PluginError("Invalid geometry command: " + bone.geo_cmd)

    transformNode = TransformNode(node)
    additionalNodes = []

    if node.hasDL:
        triConverterInfo = TriangleConverterInfo(
            obj,
            armatureObj.data,
            fModel.f3d,
            mathutils.Matrix.Scale(bpy.context.scene.fast64.sm64.blender_to_sm64_scale, 4)
            @ bone.matrix_local.inverted(),
            infoDict,
        )
        fMeshes, fSkinnedMeshes, usedDrawLayers = saveModelGivenVertexGroup(
            fModel,
            obj,
            bone.name,
            lastDeformName,
            armatureObj,
            materialOverrides,
            namePrefix,
            infoDict,
            convertTextureData,
            triConverterInfo,
            "sm64",
            int(bone.draw_layer),
        )

        if (fMeshes is None or len(fMeshes) == 0) and (fSkinnedMeshes is None or len(fSkinnedMeshes) == 0):
            # print("No mesh data.")
            node.hasDL = False
            transformNode.skinnedWithoutDL = usedDrawLayers is not None
            # bone.use_deform = False
            if usedDrawLayers is not None:
                lastDeformName = boneName
            parentTransformNode.children.append(transformNode)
            transformNode.parent = parentTransformNode
        else:
            lastDeformName = boneName
            if not bone.use_deform:
                raise PluginError(
                    bone.name
                    + " has vertices in its vertex group but is not set to deformable. Make sure to enable deform on this bone."
                )
            for drawLayer, fMesh in fMeshes.items():
                drawLayer = int(drawLayer)  # IMPORTANT, otherwise 1 and '1' will be considered separate keys
                if node.DLmicrocode is not None:
                    print("Adding additional node from layer " + str(drawLayer))
                    additionalNode = (
                        DisplayListNode(drawLayer)
                        if not isinstance(node, BillboardNode)
                        else BillboardNode(drawLayer, True, [0, 0, 0])
                    )
                    additionalNode.DLmicrocode = fMesh.draw
                    additionalNode.fMesh = fMesh
                    additionalTransformNode = TransformNode(additionalNode)
                    additionalNodes.append(additionalTransformNode)
                else:
                    print("Adding node from layer " + str(drawLayer))
                    # Setting drawLayer on construction is useless?
                    node.drawLayer = drawLayer
                    node.DLmicrocode = fMesh.draw
                    node.fMesh = fMesh  # Used for material override switches

                    parentTransformNode.children.append(transformNode)
                    transformNode.parent = parentTransformNode

            if (
                lastDeformName is not None
                and armatureObj.data.bones[lastDeformName].geo_cmd == "SwitchOption"
                and len(fSkinnedMeshes) > 0
            ):
                raise PluginError(
                    "Cannot skin geometry to a Switch Option " + "bone. Skinning cannot occur across a switch node."
                )

            for drawLayer, fSkinnedMesh in fSkinnedMeshes.items():
                print("Adding skinned mesh node.")
                transformNode = addSkinnedMeshNode(
                    armatureObj, boneName, fSkinnedMesh, transformNode, parentTransformNode, int(drawLayer)
                )

            for additionalTransformNode in additionalNodes:
                transformNode.children.append(additionalTransformNode)
                additionalTransformNode.parent = transformNode
            # print(boneName)
    else:
        parentTransformNode.children.append(transformNode)
        transformNode.parent = parentTransformNode

    new_node: TransformNode
    for new_node in additionalNodes + [transformNode]:
        new_node.revert_previous_mat = (
            bone_props.revert_before_func
            if bone.geo_cmd in {"Function", "HeldObject"}
            else bone_props.revert_previous_mat
        )
        if isinstance(new_node.node, BaseDisplayListNode):
            new_node.revert_after_mat = bone_props.revert_after_mat

    if not isinstance(transformNode.node, SwitchNode):
        # print(boneGroup.name if boneGroup is not None else "Offset")
        if len(bone.children) > 0:
            # Handle child nodes
            # nonDeformTransformData should be modified to be sent to children,
            # otherwise it should not be modified for parent.
            # This is so it can be used for siblings.
            childrenNames = sorted([bone.name for bone in bone.children])
            for name in childrenNames:
                processBone(
                    fModel,
                    name,
                    obj,
                    armatureObj,
                    final_transform,
                    lastTranslateName,
                    lastRotateName,
                    last_scale_name,
                    lastDeformName,
                    transformNode,
                    materialOverrides,
                    namePrefix,
                    geolayout,
                    geolayoutGraph,
                    infoDict,
                    convertTextureData,
                )
                # transformNode.children.append(childNode)
                # childNode.parent = transformNode

    else:
        # print(boneGroup.name if boneGroup is not None else "Offset")
        if len(bone.children) > 0:
            # optionGeolayout = \
            # 	geolayoutGraph.addGeolayout(
            # 		transformNode, boneName + '_opt0')
            # geolayoutGraph.addJumpNode(transformNode, geolayout,
            # 	optionGeolayout)
            # optionGeolayout.nodes.append(TransformNode(StartNode()))
            nextStartNode = TransformNode(StartNode())
            transformNode.children.append(nextStartNode)
            nextStartNode.parent = transformNode

            childrenNames = sorted([bone.name for bone in bone.children])
            for name in childrenNames:
                processBone(
                    fModel,
                    name,
                    obj,
                    armatureObj,
                    final_transform,
                    lastTranslateName,
                    lastRotateName,
                    last_scale_name,
                    lastDeformName,
                    nextStartNode,
                    materialOverrides,
                    namePrefix,
                    geolayout,
                    geolayoutGraph,
                    infoDict,
                    convertTextureData,
                )
                # transformNode.children.append(childNode)
                # childNode.parent = transformNode
        else:
            raise PluginError('Switch bone "' + bone.name + '" must have child bones with geometry attached.')

        bone = armatureObj.data.bones[boneName]
        for switchIndex in range(len(bone.switch_options)):
            switchOption = bone.switch_options[switchIndex]
            if switchOption.switchType == "Mesh":
                optionArmature = switchOption.optionArmature
                if optionArmature is None:
                    raise PluginError(
                        "Error: In switch bone "
                        + boneName
                        + " for option "
                        + str(switchIndex)
                        + ", the switch option armature is None."
                    )
                elif optionArmature.type != "ARMATURE":
                    raise PluginError(
                        "Error: In switch bone "
                        + boneName
                        + " for option "
                        + str(switchIndex)
                        + ", the object provided is not an armature."
                    )
                elif optionArmature in geolayoutGraph.secondary_geolayouts_dict:
                    optionGeolayout = geolayoutGraph.secondary_geolayouts_dict[optionArmature]
                    geolayoutGraph.addJumpNode(transformNode, geolayout, optionGeolayout)
                    continue

                # optionNode = addParentNode(switchTransformNode, StartNode())

                optionBoneName = getSwitchOptionBone(optionArmature)
                optionBone = optionArmature.data.bones[optionBoneName]

                # Armature doesn't matter here since node is not based off bone
                optionGeolayout = geolayoutGraph.addGeolayout(optionArmature, namePrefix + "_" + optionArmature.name)
                geolayoutGraph.addJumpNode(transformNode, geolayout, optionGeolayout)

                if not zeroRotation or not zeroTranslation:
                    startNode = TransformNode(TranslateRotateNode(1, 0, False, translate, rotate))
                else:
                    startNode = TransformNode(StartNode())
                optionGeolayout.nodes.append(startNode)

                childrenNames = sorted([bone.name for bone in optionBone.children])
                for name in childrenNames:
                    # We can use optionBone as the last translate/rotate
                    # since we added a TranslateRotate node before
                    # the switch node.
                    optionObjs = []
                    for childObj in optionArmature.children:
                        if childObj.type == "MESH":
                            optionObjs.append(childObj)
                    if len(optionObjs) > 1:
                        raise PluginError(
                            "Error: In switch bone "
                            + boneName
                            + " for option "
                            + str(switchIndex)
                            + ", the switch option armature has more than one mesh child."
                        )
                    elif len(optionObjs) < 1:
                        raise PluginError(
                            "Error: In switch bone "
                            + boneName
                            + " for option "
                            + str(switchIndex)
                            + ", the switch option armature has no mesh children."
                        )
                    optionObj = optionObjs[0]
                    optionInfoDict = getInfoDict(optionObj)
                    processBone(
                        fModel,
                        name,
                        optionObj,
                        optionArmature,
                        final_transform,
                        optionBone.name,
                        optionBone.name,
                        optionBone.name,
                        optionBone.name,
                        startNode,
                        materialOverrides,
                        namePrefix + "_" + optionBone.name,
                        optionGeolayout,
                        geolayoutGraph,
                        optionInfoDict,
                        convertTextureData,
                    )
            else:
                if switchOption.switchType == "Material":
                    material = switchOption.materialOverride
                    if switchOption.overrideDrawLayer:
                        drawLayer = int(switchOption.drawLayer)
                    else:
                        drawLayer = None
                    if switchOption.materialOverrideType == "Specific":
                        specificMat = tuple([matPtr.material for matPtr in switchOption.specificOverrideArray])
                    else:
                        specificMat = tuple([matPtr.material for matPtr in switchOption.specificIgnoreArray])
                else:
                    material = None
                    specificMat = tuple()
                    drawLayer = int(switchOption.drawLayer)

                texDimensions = getTexDimensions(material) if material is not None else None
                overrideNode = TransformNode(
                    SwitchOverrideNode(
                        material, specificMat, drawLayer, switchOption.materialOverrideType, texDimensions
                    )
                )
                overrideNode.parent = transformNode
                transformNode.children.append(overrideNode)


def processSwitchBoneMatOverrides(materialOverrides, switchBone):
    for switchOption in switchBone.switch_options:
        if switchOption.switchType == "Material":
            if switchOption.materialOverride is None:
                raise PluginError(
                    "Error: On switch bone "
                    + switchBone.name
                    + ", a switch option"
                    + " is a Material Override, but no material is provided."
                )
            if switchOption.materialOverrideType == "Specific":
                for mat in switchOption.specificOverrideArray:
                    if mat is None:
                        raise PluginError(
                            "Error: On switch bone "
                            + switchBone.name
                            + ", a switch option"
                            + " has a material override field that is None."
                        )
                specificMat = tuple([matPtr.material for matPtr in switchOption.specificOverrideArray])
            else:
                for mat in switchOption.specificIgnoreArray:
                    if mat is None:
                        raise PluginError(
                            "Error: On switch bone "
                            + switchBone.name
                            + ", a switch option"
                            + " has a material ignore field that is None."
                        )
                specificMat = tuple([matPtr.material for matPtr in switchOption.specificIgnoreArray])
            materialOverrides.append(
                (switchOption.materialOverride, specificMat, None, switchOption.materialOverrideType)
            )
        elif switchOption.switchType == "Draw Layer":
            materialOverrides.append((None, (), int(switchOption.drawLayer), "All"))


def getGroupIndex(vert, armatureObj, obj):
    actualGroups = []
    belowLimitGroups = []
    nonBoneGroups = []
    for group in vert.groups:
        groupName = getGroupNameFromIndex(obj, group.group)
        if groupName is not None:
            if groupName in armatureObj.data.bones:
                if group.weight > 0.4:
                    actualGroups.append(group)
                else:
                    belowLimitGroups.append(groupName)
            else:
                nonBoneGroups.append(groupName)

    if len(actualGroups) == 0:
        highlightWeightErrors(obj, [vert], "VERT")
        raise VertexWeightError(
            "All vertices must be part of a vertex group, be non-trivially weighted (> 0.4), and the vertex group must correspond to a bone in the armature.\n"
            + "Groups of the bad vert that don't correspond to a bone: "
            + str(nonBoneGroups)
            + ". If a vert is supposed to belong to this group then either a bone is missing or you have the wrong group.\n"
            + "Groups of the bad vert below weight limit: "
            + str(belowLimitGroups)
            + ". If a vert is supposed to belong to one of these groups then make sure to increase its weight."
        )
    vertGroup = actualGroups[0]
    significantWeightGroup = None
    for group in actualGroups:
        if group.weight > 0.5:
            if significantWeightGroup is None:
                significantWeightGroup = group
            else:
                highlightWeightErrors(obj, [vert], "VERT")
                raise VertexWeightError(
                    "A vertex was found that was significantly weighted to multiple groups. Make sure each vertex only belongs to one group whose weight is greater than 0.5. ("
                    + getGroupNameFromIndex(obj, group.group)
                    + ", "
                    + getGroupNameFromIndex(obj, significantWeightGroup.group)
                    + ")"
                )
        if group.weight > vertGroup.weight:
            vertGroup = group
    # if vertGroup not in actualGroups:
    # raise VertexWeightError("A vertex was found that was primarily weighted to a group that does not correspond to a bone in #the armature. (" + getGroupNameFromIndex(obj, vertGroup.group) + ') Either decrease the weights of this vertex group or remove it. If you think this group should correspond to a bone, make sure to check your spelling.')
    return vertGroup.group


class SimpleSkinnedFace:
    def __init__(self, bFace, loopsInGroup, loopsNotInGroup):
        self.bFace = bFace
        self.loopsInGroup = loopsInGroup
        self.loopsNotInGroup = loopsNotInGroup


def checkIfFirstNonASMNode(childNode):
    index = childNode.parent.children.index(childNode)
    if index == 0:
        return True
    while index > 0 and (
        isinstance(childNode.parent.children[index - 1].node, FunctionNode)
        or not childNode.parent.children[index - 1].skinned
    ):
        index -= 1
    return index == 0


# parent connects child node to itself
# skinned node handled by child


# A skinned mesh node should be before a mesh node.
# However, other transform nodes may exist in between two mesh nodes,
# So the skinned mesh node must be inserted before any of those transforms.
# Sibling mesh nodes thus cannot share the same transform nodes before it
# If they are both deform.
# Additionally, ASM nodes should count as modifiers for other nodes if
# they precede them
def addSkinnedMeshNode(armatureObj, boneName, skinnedMesh, transformNode, parentNode, drawLayer):
    # Add node to its immediate parent
    # print(str(type(parentNode.node)) + str(type(transformNode.node)))

    transformNode.skinned = True
    # print("Skinned mesh exists.")

    # Get skinned node
    bone = armatureObj.data.bones[boneName]
    bone_props: "SM64_BoneProperties" = bone.fast64.sm64
    skinnedNode = DisplayListNode(drawLayer)
    skinnedNode.fMesh = skinnedMesh
    skinnedNode.DLmicrocode = skinnedMesh.draw
    skinnedTransformNode = TransformNode(skinnedNode)
    skinnedTransformNode.revert_previous_mat, skinnedTransformNode.revert_after_mat = (
        bone_props.revert_previous_mat,
        bone_props.revert_after_mat,
    )

    # Ascend heirarchy until reaching first node before a deform parent.
    # We duplicate the hierarchy along the way to possibly use later.
    highestChildNode = transformNode
    transformNodeCopy = TransformNode(copy.copy(transformNode.node))
    transformNodeCopy.parent = parentNode
    highestChildCopy = transformNodeCopy
    isFirstChild = True
    hasNonDeform0x13Command = False
    acrossSwitchNode = False
    while highestChildNode.parent is not None and not (
        highestChildNode.parent.node.hasDL or highestChildNode.parent.skinnedWithoutDL
    ):  # empty 0x13 command?
        isFirstChild &= checkIfFirstNonASMNode(highestChildNode)
        hasNonDeform0x13Command |= isinstance(highestChildNode.parent.node, DisplayListWithOffsetNode)

        acrossSwitchNode |= isinstance(highestChildNode.parent.node, SwitchNode)

        highestChildNode = highestChildNode.parent
        highestChildCopyParent = TransformNode(copy.copy(highestChildNode.node))
        highestChildCopyParent.children = [highestChildCopy]
        highestChildCopy.parent = highestChildCopyParent
        # print(str(highestChildCopy.node) + " " + str(isFirstChild))
        highestChildCopy = highestChildCopyParent
    # isFirstChild &= checkIfFirstNonASMNode(highestChildNode)
    if highestChildNode.parent is None:
        raise PluginError('Issue with "' + boneName + '": Deform parent bone not found for skinning.')
        # raise PluginError("There shouldn't be a skinned mesh section if there is no deform parent. This error may have ocurred if a switch option node is trying to skin to a parent but no deform parent exists.")

    # Otherwise, remove the transformNode from the parent and
    # duplicate the node heirarchy up to the last deform parent.
    # Add the skinned node first to the last deform parent,
    # then add the duplicated node hierarchy afterward.
    if highestChildNode != transformNode:
        if not isFirstChild:
            # print("Hierarchy but not first child.")
            if hasNonDeform0x13Command:
                raise PluginError(
                    "Error with "
                    + boneName
                    + ": You cannot have more that one child skinned mesh connected to a parent skinned mesh with a non deform 0x13 bone in between. Try removing any unnecessary non-deform bones."
                )

            if acrossSwitchNode:
                raise PluginError(
                    "Error with " + boneName + ": You can not" + " skin across a switch node with more than one child."
                )

            # Remove transformNode
            parentNode.children.remove(transformNode)
            transformNode.parent = None

            # copy hierarchy, along with any preceding Function commands
            highestChildIndex = highestChildNode.parent.children.index(highestChildNode)
            precedingFunctionCmds = []
            while (
                highestChildIndex > 0
                and type(highestChildNode.parent.children[highestChildIndex - 1].node) is FunctionNode
            ):
                precedingFunctionCmds.insert(0, copy.deepcopy(highestChildNode.parent.children[highestChildIndex - 1]))
                highestChildIndex -= 1
            # _____________
            # add skinned mesh node
            highestChildCopy.parent = highestChildNode.parent
            highestChildCopy.parent.children.append(skinnedTransformNode)
            skinnedTransformNode.parent = highestChildCopy.parent

            # add Function cmd nodes
            for asmCmdNode in precedingFunctionCmds:
                highestChildCopy.parent.children.append(asmCmdNode)

            # add heirarchy to parent
            highestChildCopy.parent.children.append(highestChildCopy)

            transformNode = transformNodeCopy
        else:
            # print("Hierarchy with first child.")
            nodeIndex = highestChildNode.parent.children.index(highestChildNode)
            while nodeIndex > 0 and type(highestChildNode.parent.children[nodeIndex - 1].node) is FunctionNode:
                nodeIndex -= 1
            highestChildNode.parent.children.insert(nodeIndex, skinnedTransformNode)
            skinnedTransformNode.parent = highestChildNode.parent
    else:
        # print("Immediate child.")
        nodeIndex = parentNode.children.index(transformNode)
        parentNode.children.insert(nodeIndex, skinnedTransformNode)
        skinnedTransformNode.parent = parentNode

    return transformNode


def getAncestorGroups(parentGroup, vertexGroup, armatureObj, obj):
    if parentGroup is None:
        return []
    ancestorBones = []
    processingBones = [armatureObj.data.bones[vertexGroup]]
    while len(processingBones) > 0:
        currentBone = processingBones[0]
        processingBones = processingBones[1:]

        ancestorBones.append(currentBone)
        processingBones.extend(currentBone.children)

    currentBone = armatureObj.data.bones[vertexGroup].parent
    while currentBone is not None and currentBone.name != parentGroup:
        ancestorBones.append(currentBone)
        currentBone = currentBone.parent
    ancestorBones.append(armatureObj.data.bones[parentGroup])

    # print(vertexGroup + ", " + parentGroup)
    # print([bone.name for bone in ancestorBones])
    return [getGroupIndexFromname(obj, bone.name) for bone in armatureObj.data.bones if bone not in ancestorBones]


# returns fMeshes, fSkinnedMeshes, makeLastDeformBone
def saveModelGivenVertexGroup(
    fModel,
    obj,
    vertexGroup,
    parentGroup,
    armatureObj,
    materialOverrides,
    namePrefix,
    infoDict,
    convertTextureData,
    triConverterInfo,
    drawLayerField,
    drawLayerV3,
):
    # checkForF3DMaterial(obj)

    # print("GROUP " + vertexGroup)

    # TODO: Implement lastMaterialName optimization
    lastMaterialName = None

    mesh = obj.data
    currentGroupIndex = getGroupIndexFromname(obj, vertexGroup)
    vertIndices = [
        vert.index for vert in obj.data.vertices if getGroupIndex(vert, armatureObj, obj) == currentGroupIndex
    ]
    parentGroupIndex = getGroupIndexFromname(obj, parentGroup) if parentGroup is not None else -1

    if len(vertIndices) == 0:
        print("No vert indices in " + vertexGroup)
        return None, None, None

    transformMatrix = mathutils.Matrix.Scale(bpy.context.scene.fast64.sm64.blender_to_sm64_scale, 4)
    if parentGroup is None:
        parentMatrix = transformMatrix
    else:
        parentBone = armatureObj.data.bones[parentGroup]
        parentMatrix = transformMatrix @ parentBone.matrix_local.inverted()

    groupFaces = {}  # draw layer : {material_index : [faces]}
    skinnedFaces = {}  # draw layer : {material_index : [skinned faces]}
    handledFaces = []
    usedDrawLayers = set()
    ancestorGroups = {}  # vertexGroup : ancestor list

    for vertIndex in vertIndices:
        if vertIndex not in infoDict.vert:
            continue
        for face in infoDict.vert[vertIndex]:
            material = obj.material_slots[face.material_index].material
            if material.mat_ver > 3:
                drawLayer = int(getattr(material.f3d_mat.draw_layer, drawLayerField))
            else:
                drawLayer = drawLayerV3

            # Ignore repeat faces
            if face in handledFaces:
                continue
            else:
                handledFaces.append(face)

            loopsInGroup = []
            loopsNotInGroup = []
            isChildSkinnedFace = False

            # loop is interpreted as face + loop index
            for i in range(3):
                vertGroupIndex = getGroupIndex(mesh.vertices[face.vertices[i]], armatureObj, obj)
                if vertGroupIndex not in ancestorGroups:
                    ancestorGroups[vertGroupIndex] = getAncestorGroups(parentGroup, vertexGroup, armatureObj, obj)

                if vertGroupIndex == currentGroupIndex:
                    loopsInGroup.append((face, mesh.loops[face.loops[i]]))
                elif vertGroupIndex == parentGroupIndex:
                    loopsNotInGroup.append((face, mesh.loops[face.loops[i]]))
                elif vertGroupIndex not in ancestorGroups[vertGroupIndex]:
                    # Only want to handle skinned faces connected to parent
                    isChildSkinnedFace = True
                    break
                else:
                    highlightWeightErrors(obj, [face], "FACE")
                    raise VertexWeightError(
                        "Error with "
                        + vertexGroup
                        + ": Verts attached to one bone can not be attached to any of its ancestor or sibling bones besides its first immediate deformable parent bone. For example, a foot vertex can be connected to a leg vertex, but a foot vertex cannot be connected to a thigh vertex."
                    )
            if isChildSkinnedFace:
                usedDrawLayers.add(drawLayer)
                continue

            if len(loopsNotInGroup) == 0:
                if drawLayer not in groupFaces:
                    groupFaces[drawLayer] = {}
                drawLayerFaces = groupFaces[drawLayer]
                if face.material_index not in drawLayerFaces:
                    drawLayerFaces[face.material_index] = []
                drawLayerFaces[face.material_index].append(face)
            else:
                if drawLayer not in skinnedFaces:
                    skinnedFaces[drawLayer] = {}
                drawLayerSkinnedFaces = skinnedFaces[drawLayer]
                if face.material_index not in drawLayerSkinnedFaces:
                    drawLayerSkinnedFaces[face.material_index] = []
                drawLayerSkinnedFaces[face.material_index].append(
                    SimpleSkinnedFace(face, loopsInGroup, loopsNotInGroup)
                )

    if len(groupFaces) == 0 and len(skinnedFaces) == 0:
        print("No faces in " + vertexGroup)
        return None, None, usedDrawLayers

    # Save skinned mesh
    fMeshes = {}
    fSkinnedMeshes = {}
    for drawLayer, materialFaces in skinnedFaces.items():
        meshName = getFMeshName(vertexGroup, namePrefix, drawLayer, False)
        checkUniqueBoneNames(fModel, meshName, vertexGroup)
        skinnedMeshName = getFMeshName(vertexGroup, namePrefix, drawLayer, True)
        checkUniqueBoneNames(fModel, skinnedMeshName, vertexGroup)

        fMesh, fSkinnedMesh = saveSkinnedMeshByMaterial(
            materialFaces,
            fModel,
            meshName,
            skinnedMeshName,
            obj,
            parentMatrix,
            namePrefix,
            vertexGroup,
            drawLayer,
            convertTextureData,
            triConverterInfo,
        )

        fSkinnedMeshes[drawLayer] = fSkinnedMesh
        fMeshes[drawLayer] = fMesh

        fModel.meshes[skinnedMeshName] = fSkinnedMeshes[drawLayer]
        fModel.meshes[meshName] = fMeshes[drawLayer]

        if drawLayer not in groupFaces:
            fMeshes[drawLayer].draw.commands.extend(
                [
                    SPEndDisplayList(),
                ]
            )

    # Save unskinned mesh
    for drawLayer, materialFaces in groupFaces.items():
        if drawLayer not in fMeshes:
            fMesh = fModel.addMesh(vertexGroup, namePrefix, drawLayer, False, None)
            fMeshes[drawLayer] = fMesh

        for material_index, bFaces in sorted(materialFaces.items()):
            material = obj.material_slots[material_index].material
            checkForF3dMaterialInFaces(obj, material)
            fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)
            if fMaterial.isTexLarge[0] or fMaterial.isTexLarge[1]:
                currentGroupIndex = saveMeshWithLargeTexturesByFaces(
                    material,
                    bFaces,
                    fModel,
                    fMeshes[drawLayer],
                    obj,
                    drawLayer,
                    convertTextureData,
                    None,
                    triConverterInfo,
                    None,
                    None,
                    lastMaterialName,
                )
            else:
                saveMeshByFaces(
                    material,
                    bFaces,
                    fModel,
                    fMeshes[drawLayer],
                    obj,
                    drawLayer,
                    convertTextureData,
                    None,
                    triConverterInfo,
                    None,
                    None,
                    lastMaterialName,
                )

        fMeshes[drawLayer].draw.commands.extend(
            [
                SPEndDisplayList(),
            ]
        )

    return fMeshes, fSkinnedMeshes, usedDrawLayers


def save_override_draw(
    f_model: SM64Model,
    draw: GfxList,
    prefix: str,
    draw_overrides: dict[OverrideHash, GfxOverride],
    existing_hash: OverrideHash,
    override_mat: bpy.types.Material | None,
    specific_mats: tuple[bpy.types.Material] | None,
    override_layer: int | None,
    override_type: str,
    fMesh: FMesh,
    node: DisplayListNode,
    draw_layer: int,
    convert_texture_data: bool,
):
    specific_mats = specific_mats or tuple()
    f_override_mat = override_tex_dimensions = None
    new_layer = draw_layer if override_layer is None else override_layer
    material_hash = override_mat, new_layer, convert_texture_data
    g_tex_gen = False

    if override_mat is not None:
        f_override_mat, override_tex_dimensions = saveOrGetF3DMaterial(
            override_mat, f_model, None, new_layer, convert_texture_data
        )
        g_tex_gen = override_mat.f3d_mat.rdp_settings.g_tex_gen

    name = f"{fMesh.name}{prefix}"
    new_name = name
    override_index = -1
    while new_name in [x.gfx.name for x in draw_overrides.values()]:
        override_index += 1
        new_name = f"{name}_{override_index}"
    name = new_name

    new_dl_override = GfxList(name, GfxListTag.Draw, f_model.DLFormat)
    new_dl_override.commands = [copy.copy(cmd) for cmd in draw.commands]
    save_mesh_override = False
    prev_material = None
    last_replaced = None
    command_index = 0

    new_hash = [] if existing_hash is None else [*existing_hash]
    while command_index < len(new_dl_override.commands):
        command = new_dl_override.commands[command_index]
        if not isinstance(command, SPDisplayList):
            command_index += 1
            continue
        # get the material referenced, and then check if it should be overriden
        # a material override will either have a list of mats it overrides, or a mask of mats it doesn't based on type
        bpy_material, fmaterial = find_material_from_jump_cmd(f_model.getAllMaterials().items(), command)
        should_modify = override_mat is not None and (
            (override_type == "Specific" and bpy_material in specific_mats)
            or (override_type == "All" and bpy_material not in specific_mats)
        )

        if should_modify and bpy_material is not None and override_tex_dimensions is not None and not g_tex_gen:
            _, tex_dimensions = saveOrGetF3DMaterial(bpy_material, f_model, None, new_layer, convert_texture_data)
            if tex_dimensions != override_tex_dimensions:
                raise PluginError(
                    f'Material "{bpy_material.name}" has a texture with dimensions of {tex_dimensions}\n'
                    f'but is being overriden by material "{override_mat.name}" with dimensions of {override_tex_dimensions}.\n'
                    + "UV coordinates are in pixel units, so there will be UV errors in those overrides.\n "
                    + "Make sure that all overrides have the same texture dimensions as the original material.\n"
                    + "Note that materials with no textures default to dimensions of 32x32."
                )

        new_mat: FMaterial = f_override_mat if should_modify else None
        cur_bpy_material = override_mat if should_modify else bpy_material
        if cur_bpy_material is not None and override_layer is not None:
            material_hash = (cur_bpy_material, new_layer, convert_texture_data)
            # generate a new material for the specific layer if rendermode is set
            if material_hash not in f_model.layer_adapted_fmats:
                f_model.layer_adapted_fmats[material_hash] = None
                rdp = cur_bpy_material.f3d_mat.rdp_settings
                preset = (rdp.rendermode_preset_cycle_1, rdp.rendermode_preset_cycle_2)
                cur_preset = f_model.getRenderMode(new_layer)
                if rdp.set_rendermode and (rdp.rendermode_advanced_enabled or preset != cur_preset):
                    new_mat: FMaterial = saveOrGetF3DMaterial(
                        cur_bpy_material, f_model, None, new_layer, convert_texture_data
                    )[0]
                    if override_mat is None:
                        new_mat.material = copy.copy(new_mat.material)  # so we can change the tag
                        new_mat.material.tag |= GfxListTag.NoExport
                    f_model.layer_adapted_fmats[material_hash] = new_mat
            new_mat = new_mat or f_model.layer_adapted_fmats.get(material_hash)

        # replace the material load if necessary
        # if we replaced the previous load with the same override, then remove the cmd to optimize DL
        if command.displayList.tag & GfxListTag.Material:
            curMaterial = fmaterial
            # if layer ever changes the main material use new_mat here
            if should_modify:
                save_mesh_override = True
                new_hash.append((0, f_override_mat))
                last_replaced = fmaterial
                curMaterial = f_override_mat
                command.displayList = f_override_mat.material
            # remove cmd if it is a repeat load
            if prev_material is not None and prev_material == curMaterial:
                save_mesh_override = True
                new_hash.append((1, curMaterial))
                new_dl_override.commands.pop(command_index)
                command_index -= 1
                # if we added a revert for our material redundant load, remove that as well
                prevIndex = command_index - 1
                prev_command = new_dl_override.commands[prevIndex]
                if (
                    prevIndex > 0
                    and isinstance(prev_command, SPDisplayList)
                    and prev_command.displayList == curMaterial.revert
                ):
                    new_dl_override.commands.pop(prevIndex)
                    command_index -= 1
            # update the last loaded material
            prev_material = curMaterial

        # replace the revert if the override has a revert, otherwise remove the command
        if command.displayList.tag & GfxListTag.MaterialRevert and new_mat is not None:
            new_hash.append((2, new_mat))
            save_mesh_override = True
            if new_mat.revert is not None:
                command.displayList = new_mat.revert
            else:
                new_dl_override.commands.pop(command_index)
                command_index -= 1

        if not command.displayList.tag & GfxListTag.Geometry:
            command_index += 1
            continue
        # If the previous command was a revert we added, remove it. All reverts must be followed by a load
        prev_index = command_index - 1
        prev_command = new_dl_override.commands[prev_index]
        if (
            prev_index > 0
            and isinstance(prev_command, SPDisplayList)
            and (new_mat is not None and prev_command.displayList == new_mat.revert)
        ):
            new_hash.append((3, new_mat))
            save_mesh_override = True
            new_dl_override.commands.pop(prev_index)
            command_index -= 1
        # If the override material has a revert and the original material didn't, insert a revert after this command.
        # This is needed to ensure that override materials that need a revert get them.
        # Reverts are only needed if the next command is a different material load
        if (
            last_replaced
            and last_replaced.revert is None
            and new_mat is not None
            and new_mat.revert is not None
            and prev_material == new_mat
        ):
            next_command = new_dl_override.commands[command_index + 1]
            if (
                isinstance(next_command, SPDisplayList)
                and next_command.displayList.tag & GfxListTag.Material
                and next_command.displayList != prev_material.material
            ) or (isinstance(next_command, SPEndDisplayList)):
                new_hash.append((4, new_mat))
                save_mesh_override = True
                new_dl_override.commands.insert(command_index + 1, SPDisplayList(new_mat.revert))
                command_index += 1
        # iterate to the next cmd
        command_index += 1

    new_hash = tuple(new_hash)
    if save_mesh_override:
        override = draw_overrides.setdefault(new_hash, GfxOverride(new_dl_override, []))
        node.DLmicrocode = override.gfx
        node.override_hash = new_hash
        override.nodes.append(node)


def findVertIndexInBuffer(loop, buffer, loopDict):
    i = 0
    for material_index, vertData in buffer:
        for f3dVert in vertData:
            if f3dVert == loopDict[loop]:
                return i
            i += 1
    # print("Can't find " + str(loop))
    return -1


def convertVertDictToArray(vertDict):
    data = []
    matRegions = {}
    for material_index, vertData in vertDict:
        start = len(data)
        data.extend(vertData)
        end = len(data)
        matRegions[material_index] = (start, end)
    return data, matRegions


# This collapses similar loops together IF they are in the same material.
def splitSkinnedFacesIntoTwoGroups(skinnedFaces, fModel, obj, uv_data, drawLayer, convertTextureData):
    inGroupVertArray = []
    notInGroupVertArray = []

    # For selecting on error
    notInGroupBlenderVerts = []
    loopDict = {}
    for material_index, skinnedFaceArray in sorted(skinnedFaces.items()):
        # These MUST be arrays (not dicts) as order is important
        inGroupVerts = []
        inGroupVertArray.append([material_index, inGroupVerts])

        notInGroupVerts = []
        notInGroupVertArray.append([material_index, notInGroupVerts])

        material = obj.material_slots[material_index].material
        fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)

        convertInfo = LoopConvertInfo(uv_data, obj, material)
        for skinnedFace in skinnedFaceArray:
            for face, loop in skinnedFace.loopsInGroup:
                f3dVert = getF3DVert(loop, face, convertInfo, obj.data)
                bufferVert = BufferVertex(f3dVert, None, material_index)
                if bufferVert not in inGroupVerts:
                    inGroupVerts.append(bufferVert)
                loopDict[loop] = f3dVert
            for face, loop in skinnedFace.loopsNotInGroup:
                vert = obj.data.vertices[loop.vertex_index]
                if vert not in notInGroupBlenderVerts:
                    notInGroupBlenderVerts.append(vert)
                f3dVert = getF3DVert(loop, face, convertInfo, obj.data)
                bufferVert = BufferVertex(f3dVert, None, material_index)
                if bufferVert not in notInGroupVerts:
                    notInGroupVerts.append(bufferVert)
                loopDict[loop] = f3dVert

    return inGroupVertArray, notInGroupVertArray, loopDict, notInGroupBlenderVerts


def getGroupVertCount(group):
    count = 0
    for material_index, vertData in group:
        count += len(vertData)
    return count


def saveSkinnedMeshByMaterial(
    skinnedFaces,
    fModel,
    meshName,
    skinnedMeshName,
    obj,
    parentMatrix,
    namePrefix,
    vertexGroup,
    drawLayer,
    convertTextureData,
    triConverterInfo,
):
    # We choose one or more loops per vert to represent a material from which
    # texDimensions can be found, since it is required for UVs.
    uv_data = obj.data.uv_layers["UVMap"].data
    inGroupVertArray, notInGroupVertArray, loopDict, notInGroupBlenderVerts = splitSkinnedFacesIntoTwoGroups(
        skinnedFaces, fModel, obj, uv_data, drawLayer, convertTextureData
    )

    notInGroupCount = getGroupVertCount(notInGroupVertArray)
    if notInGroupCount > fModel.f3d.vert_load_size - 2:
        highlightWeightErrors(obj, notInGroupBlenderVerts, "VERT")
        raise VertexWeightError(
            "Too many connecting vertices in skinned "
            + "triangles for bone '"
            + vertexGroup
            + "'. Max is "
            + str(fModel.f3d.vert_load_size - 2)
            + " on parent bone, currently at "
            + str(notInGroupCount)
            + ". Note that a vertex with different UVs/normals/materials in "
            + "connected faces will count more than once. Try "
            + "keeping UVs contiguous, and avoid using "
            + "split normals."
        )

    # TODO: Implement lastMaterialName optimization
    lastMaterialName = None

    # Load parent group vertices
    fSkinnedMesh = FMesh(skinnedMeshName, fModel.DLFormat)

    # Load verts into buffer by material.
    # It seems like material setup must be done BEFORE triangles are drawn.
    # Because of this we cannot share verts between materials (?)
    curIndex = 0
    for material_index, vertData in sorted(notInGroupVertArray, key=lambda x: x[0]):
        material = obj.material_slots[material_index].material
        checkForF3dMaterialInFaces(obj, material)
        f3dMat = material.f3d_mat if material.mat_ver > 3 else material
        if f3dMat.rdp_settings.set_rendermode:
            drawLayerKey = drawLayer
        else:
            drawLayerKey = None

        materialKey = (material, drawLayerKey, fModel.global_data.getCurrentAreaKey(f3dMat))
        fMaterial, texDimensions = fModel.getMaterialAndHandleShared(materialKey)
        isPointSampled = isTexturePointSampled(material)

        skinnedTriGroup = fSkinnedMesh.tri_group_new(fMaterial)
        fSkinnedMesh.draw.commands.append(SPDisplayList(fMaterial.material))
        fSkinnedMesh.draw.commands.append(SPDisplayList(skinnedTriGroup.triList))
        skinnedTriGroup.triList.commands.append(
            SPVertex(skinnedTriGroup.vertexList, len(skinnedTriGroup.vertexList.vertices), len(vertData), curIndex)
        )
        curIndex += len(vertData)

        for bufferVert in vertData:
            skinnedTriGroup.vertexList.vertices.append(
                bufferVert.f3dVert.toVtx(
                    obj.data,
                    texDimensions,
                    parentMatrix,
                    isPointSampled,
                )
            )

        skinnedTriGroup.triList.commands.append(SPEndDisplayList())
        if fMaterial.revert is not None:
            fSkinnedMesh.draw.commands.append(SPDisplayList(fMaterial.revert))

    # End skinned mesh vertices.
    fSkinnedMesh.draw.commands.append(SPEndDisplayList())

    fMesh = FMesh(meshName, fModel.DLFormat)

    # Load current group vertices, then draw commands by material
    existingVertData, matRegionDict = convertVertDictToArray(notInGroupVertArray)

    for material_index, skinnedFaceArray in sorted(skinnedFaces.items()):
        material = obj.material_slots[material_index].material
        faces = [skinnedFace.bFace for skinnedFace in skinnedFaceArray]
        fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)
        if fMaterial.isTexLarge[0] or fMaterial.isTexLarge[1]:
            saveMeshWithLargeTexturesByFaces(
                material,
                faces,
                fModel,
                fMesh,
                obj,
                drawLayer,
                convertTextureData,
                None,
                triConverterInfo,
                copy.deepcopy(existingVertData),
                copy.deepcopy(matRegionDict),
                lastMaterialName,
            )
        else:
            saveMeshByFaces(
                material,
                faces,
                fModel,
                fMesh,
                obj,
                drawLayer,
                convertTextureData,
                None,
                triConverterInfo,
                copy.deepcopy(existingVertData),
                copy.deepcopy(matRegionDict),
                lastMaterialName,
            )

    return fMesh, fSkinnedMesh


def writeDynamicMeshFunction(name, displayList):
    data = """Gfx *{}(s32 callContext, struct GraphNode *node, UNUSED Mat4 *c) {
	struct GraphNodeGenerated *asmNode = (struct GraphNodeGenerated *) node;
    Gfx *displayListStart = NULL;
    if (callContext == GEO_CONTEXT_RENDER) {
        displayListStart = alloc_display_list({} * sizeof(*displayListStart));
        Gfx* glistp = displayListStart;
		{}
    }
    return displayListStart;
}""".format(
        name, str(len(displayList.commands)), displayList.to_c(False)
    )

    return data


class SM64_ExportGeolayoutObject(ObjectDataExporter):
    # set bl_ properties
    bl_idname = "object.sm64_export_geolayout_object"
    bl_label = "Export Object Geolayout"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    export_obj: bpy.props.StringProperty()

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileOutput = None
        tempROM = None
        props = context.scene.fast64.sm64.combined_export
        try:
            obj = None
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            obj = bpy.data.objects.get(self.export_obj, None) or context.active_object
            self.export_obj = ""
            if obj.type != "MESH" and not (
                obj.type == "EMPTY" and (obj.sm64_obj_type == "None" or obj.sm64_obj_type == "Switch")
            ):
                raise PluginError('Selected object must be a mesh or an empty with the "None" or "Switch" type.')

            final_transform = mathutils.Matrix.Identity(4)
            scaleValue = context.scene.fast64.sm64.blender_to_sm64_scale
            final_transform = mathutils.Matrix.Diagonal(mathutils.Vector((scaleValue, scaleValue, scaleValue))).to_4x4()
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            self.store_object_data()

            # Rotate all armatures 90 degrees
            applyRotation([obj], math.radians(90), "X")
            save_textures = bpy.context.scene.saveTextures

            if context.scene.fast64.sm64.export_type == "C":
                export_path, level_name = getPathAndLevel(
                    props.is_actor_custom_export,
                    props.actor_custom_path,
                    props.export_level_name,
                    props.level_name,
                )
                if not props.is_actor_custom_export:
                    applyBasicTweaks(export_path)
                exportGeolayoutObjectC(
                    obj,
                    final_transform,
                    export_path,
                    props.custom_include_directory,
                    save_textures,
                    save_textures and bpy.context.scene.geoSeparateTextureDef,
                    props.actor_group_name,
                    props.export_header_type,
                    props.obj_name_gfx,
                    props.geo_name,
                    level_name,
                    props.is_actor_custom_export,
                    DLFormat.Static,
                )
                self.report({"INFO"}, "Success!")
            elif context.scene.fast64.sm64.export_type == "Insertable Binary":
                exportGeolayoutObjectInsertableBinary(
                    obj,
                    final_transform,
                    bpy.path.abspath(bpy.context.scene.geoInsertableBinaryPath),
                )
                self.report({"INFO"}, "Success! Data at " + context.scene.geoInsertableBinaryPath)
            else:
                tempROM = tempName(context.scene.fast64.sm64.output_rom)
                export_rom_checks(bpy.path.abspath(context.scene.fast64.sm64.export_rom))
                romfileExport = open(bpy.path.abspath(context.scene.fast64.sm64.export_rom), "rb")
                shutil.copy(bpy.path.abspath(context.scene.fast64.sm64.export_rom), bpy.path.abspath(tempROM))
                romfileExport.close()
                romfileOutput = open(bpy.path.abspath(tempROM), "rb+")

                levelParsed = parse_level_binary(romfileOutput, props.level_name)
                segmentData = levelParsed.segmentData

                if context.scene.fast64.sm64.extend_bank_4:
                    ExtendBank0x04(romfileOutput, segmentData, defaultExtendSegment4)

                exportRange = [int(context.scene.geoExportStart, 16), int(context.scene.geoExportEnd, 16)]
                textDumpFilePath = (
                    bpy.path.abspath(context.scene.textDumpGeoPath) if context.scene.textDumpGeo else None
                )
                if context.scene.overwriteModelLoad:
                    modelLoadInfo = (int(context.scene.modelLoadLevelScriptCmd, 16), int(context.scene.modelID, 16))
                else:
                    modelLoadInfo = (None, None)

                if context.scene.geoUseBank0:
                    addrRange, startRAM, geoStart = exportGeolayoutObjectBinaryBank0(
                        romfileOutput,
                        obj,
                        exportRange,
                        final_transform,
                        *modelLoadInfo,
                        textDumpFilePath,
                        getAddressFromRAMAddress(int(context.scene.geoRAMAddr, 16)),
                    )
                else:
                    addrRange, segPointer = exportGeolayoutObjectBinary(
                        romfileOutput,
                        obj,
                        exportRange,
                        final_transform,
                        segmentData,
                        *modelLoadInfo,
                        textDumpFilePath,
                    )

                romfileOutput.close()
                selectSingleObject(obj)

                if os.path.exists(bpy.path.abspath(context.scene.fast64.sm64.output_rom)):
                    os.remove(bpy.path.abspath(context.scene.fast64.sm64.output_rom))
                os.rename(bpy.path.abspath(tempROM), bpy.path.abspath(context.scene.fast64.sm64.output_rom))

                if context.scene.geoUseBank0:
                    self.report(
                        {"INFO"},
                        "Success! Geolayout at ("
                        + hex(addrRange[0])
                        + ", "
                        + hex(addrRange[1])
                        + "), to write to RAM Address "
                        + hex(startRAM)
                        + ", with geolayout starting at "
                        + hex(geoStart),
                    )
                else:
                    self.report(
                        {"INFO"},
                        "Success! Geolayout at ("
                        + hex(addrRange[0])
                        + ", "
                        + hex(addrRange[1])
                        + ") (Seg. "
                        + segPointer
                        + ").",
                    )

            self.cleanup_temp_object_data()
            applyRotation([obj], math.radians(-90), "X")
            self.show_warnings()
            return {"FINISHED"}  # must return a set

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            self.cleanup_temp_object_data()
            applyRotation([obj], math.radians(-90), "X")

            if context.scene.fast64.sm64.export_type == "Binary":
                if romfileOutput is not None:
                    romfileOutput.close()
                if tempROM is not None and os.path.exists(bpy.path.abspath(tempROM)):
                    os.remove(bpy.path.abspath(tempROM))
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class SM64_ExportGeolayoutArmature(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.sm64_export_geolayout_armature"
    bl_label = "Export Armature Geolayout"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    export_obj: bpy.props.StringProperty()

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileOutput = None
        tempROM = None
        props = context.scene.fast64.sm64.combined_export
        try:
            armatureObj = None
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            armatureObj = bpy.data.objects.get(self.export_obj, None) or context.active_object
            self.export_obj = ""
            if armatureObj.type != "ARMATURE":
                raise PluginError("Armature not selected.")

            if len(armatureObj.children) == 0 or not isinstance(armatureObj.children[0].data, bpy.types.Mesh):
                raise PluginError("Armature does not have any mesh children, or has a non-mesh child.")

            obj = armatureObj.children[0]
            final_transform = mathutils.Matrix.Identity(4)

            # get all switch option armatures as well
            linkedArmatures = [armatureObj]
            getAllArmatures(armatureObj, linkedArmatures)

            linkedArmatureDict = {}

            for linkedArmature in linkedArmatures:
                # IMPORTANT: Do this BEFORE rotation
                optionObjs = []
                for childObj in linkedArmature.children:
                    if childObj.type == "MESH":
                        optionObjs.append(childObj)
                if len(optionObjs) > 1:
                    raise PluginError("Error: " + linkedArmature.name + " has more than one mesh child.")
                elif len(optionObjs) < 1:
                    raise PluginError("Error: " + linkedArmature.name + " has no mesh children.")
                linkedMesh = optionObjs[0]
                prepareGeolayoutExport(linkedArmature, linkedMesh)
                linkedArmatureDict[linkedArmature] = linkedMesh
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            # Rotate all armatures 90 degrees
            applyRotation([armatureObj] + linkedArmatures, math.radians(90), "X")

            # You must ALSO apply object rotation after armature rotation.
            deselectAllObjects()
            for linkedArmature, linkedMesh in linkedArmatureDict.items():
                linkedMesh.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)
            if context.scene.fast64.sm64.export_type == "C":
                export_path, level_name = getPathAndLevel(
                    props.is_actor_custom_export,
                    props.actor_custom_path,
                    props.export_level_name,
                    props.level_name,
                )

                save_textures = bpy.context.scene.saveTextures
                if not props.is_actor_custom_export:
                    applyBasicTweaks(export_path)
                header, fileStatus = exportGeolayoutArmatureC(
                    armatureObj,
                    obj,
                    final_transform,
                    export_path,
                    props.custom_include_directory,
                    save_textures,
                    save_textures and bpy.context.scene.geoSeparateTextureDef,
                    None,
                    props.actor_group_name,
                    props.export_header_type,
                    props.obj_name_gfx,
                    props.geo_name,
                    level_name,
                    props.is_actor_custom_export,
                    DLFormat.Static,
                )
                starSelectWarning(self, fileStatus)
                self.report({"INFO"}, "Success!")
            elif context.scene.fast64.sm64.export_type == "Insertable Binary":
                exportGeolayoutArmatureInsertableBinary(
                    armatureObj,
                    obj,
                    final_transform,
                    bpy.path.abspath(bpy.context.scene.geoInsertableBinaryPath),
                    None,
                )
                self.report({"INFO"}, "Success! Data at " + context.scene.geoInsertableBinaryPath)
            else:
                tempROM = tempName(context.scene.fast64.sm64.output_rom)
                export_rom_checks(bpy.path.abspath(context.scene.fast64.sm64.export_rom))
                romfileExport = open(bpy.path.abspath(context.scene.fast64.sm64.export_rom), "rb")
                shutil.copy(bpy.path.abspath(context.scene.fast64.sm64.export_rom), bpy.path.abspath(tempROM))
                romfileExport.close()
                romfileOutput = open(bpy.path.abspath(tempROM), "rb+")

                levelParsed = parse_level_binary(romfileOutput, props.level_name)
                segmentData = levelParsed.segmentData

                if context.scene.fast64.sm64.extend_bank_4:
                    ExtendBank0x04(romfileOutput, segmentData, defaultExtendSegment4)

                exportRange = [int(context.scene.geoExportStart, 16), int(context.scene.geoExportEnd, 16)]
                textDumpFilePath = (
                    bpy.path.abspath(context.scene.textDumpGeoPath) if context.scene.textDumpGeo else None
                )
                if context.scene.overwriteModelLoad:
                    modelLoadInfo = (int(context.scene.modelLoadLevelScriptCmd, 16), int(context.scene.modelID, 16))
                else:
                    modelLoadInfo = (None, None)

                if context.scene.geoUseBank0:
                    addrRange, startRAM, geoStart = exportGeolayoutArmatureBinaryBank0(
                        romfileOutput,
                        armatureObj,
                        obj,
                        exportRange,
                        final_transform,
                        *modelLoadInfo,
                        textDumpFilePath,
                        getAddressFromRAMAddress(int(context.scene.geoRAMAddr, 16)),
                        None,
                    )
                else:
                    addrRange, segPointer = exportGeolayoutArmatureBinary(
                        romfileOutput,
                        armatureObj,
                        obj,
                        exportRange,
                        final_transform,
                        segmentData,
                        *modelLoadInfo,
                        textDumpFilePath,
                        None,
                    )

                romfileOutput.close()
                selectSingleObject(armatureObj)

                if os.path.exists(bpy.path.abspath(context.scene.fast64.sm64.output_rom)):
                    os.remove(bpy.path.abspath(context.scene.fast64.sm64.output_rom))
                os.rename(bpy.path.abspath(tempROM), bpy.path.abspath(context.scene.fast64.sm64.output_rom))

                if context.scene.geoUseBank0:
                    self.report(
                        {"INFO"},
                        "Success! Geolayout at ("
                        + hex(addrRange[0])
                        + ", "
                        + hex(addrRange[1])
                        + "), to write to RAM Address "
                        + hex(startRAM)
                        + ", with geolayout starting at "
                        + hex(geoStart),
                    )
                else:
                    self.report(
                        {"INFO"},
                        "Success! Geolayout at ("
                        + hex(addrRange[0])
                        + ", "
                        + hex(addrRange[1])
                        + ") (Seg. "
                        + segPointer
                        + ").",
                    )

            applyRotation([armatureObj] + linkedArmatures, math.radians(-90), "X")

            return {"FINISHED"}  # must return a set

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            applyRotation([armatureObj] + linkedArmatures, math.radians(-90), "X")

            if context.scene.fast64.sm64.export_type == "Binary":
                if romfileOutput is not None:
                    romfileOutput.close()
                if tempROM is not None and os.path.exists(bpy.path.abspath(tempROM)):
                    os.remove(bpy.path.abspath(tempROM))
            if armatureObj is not None:
                armatureObj.select_set(True)
                context.view_layer.objects.active = armatureObj
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class SM64_ExportGeolayoutPanel(SM64_Panel):
    bl_idname = "SM64_PT_export_geolayout"
    bl_label = "SM64 Geolayout Exporter"
    goal = "Object/Actor/Anim"
    binary_only = True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsGeoE = col.operator(SM64_ExportGeolayoutArmature.bl_idname)
        propsGeoE = col.operator(SM64_ExportGeolayoutObject.bl_idname)
        props = context.scene.fast64.sm64.combined_export
        if context.scene.fast64.sm64.export_type == "Insertable Binary":
            col.prop(context.scene, "geoInsertableBinaryPath")
        else:
            prop_split(col, context.scene, "geoExportStart", "Start Address")
            prop_split(col, context.scene, "geoExportEnd", "End Address")

            col.prop(context.scene, "geoUseBank0")
            if context.scene.geoUseBank0:
                prop_split(col, context.scene, "geoRAMAddr", "RAM Address")
            else:
                prop_split(col, props, "level_name", "Level")

            col.prop(context.scene, "overwriteModelLoad")
            if context.scene.overwriteModelLoad:
                prop_split(col, context.scene, "modelLoadLevelScriptCmd", "Model Load Command")
                prop_split(col, context.scene, "modelID", "Model ID")
            col.prop(context.scene, "textDumpGeo")
            if context.scene.textDumpGeo:
                col.prop(context.scene, "textDumpGeoPath")


sm64_geo_writer_classes = (
    SM64_ExportGeolayoutObject,
    SM64_ExportGeolayoutArmature,
)

sm64_geo_writer_panel_classes = (SM64_ExportGeolayoutPanel,)


def sm64_geo_writer_panel_register():
    for cls in sm64_geo_writer_panel_classes:
        register_class(cls)


def sm64_geo_writer_panel_unregister():
    for cls in sm64_geo_writer_panel_classes:
        unregister_class(cls)


def sm64_geo_writer_register():
    for cls in sm64_geo_writer_classes:
        register_class(cls)

    bpy.types.Scene.geoExportStart = bpy.props.StringProperty(name="Start", default="11D8930")
    bpy.types.Scene.geoExportEnd = bpy.props.StringProperty(name="End", default="11FFF00")

    bpy.types.Scene.overwriteModelLoad = bpy.props.BoolProperty(name="Modify level script", default=True)
    bpy.types.Scene.modelLoadLevelScriptCmd = bpy.props.StringProperty(
        name="Level script model load command", default="2ABCE0"
    )
    bpy.types.Scene.modelID = bpy.props.StringProperty(name="Model ID", default="1")

    bpy.types.Scene.textDumpGeo = bpy.props.BoolProperty(name="Dump geolayout as text", default=False)
    bpy.types.Scene.textDumpGeoPath = bpy.props.StringProperty(name="Text Dump Path", subtype="FILE_PATH")
    bpy.types.Scene.geoUseBank0 = bpy.props.BoolProperty(name="Use Bank 0")
    bpy.types.Scene.geoRAMAddr = bpy.props.StringProperty(name="RAM Address", default="80000000")
    bpy.types.Scene.geoSeparateTextureDef = bpy.props.BoolProperty(name="Save texture.inc.c separately")
    bpy.types.Scene.geoInsertableBinaryPath = bpy.props.StringProperty(name="Filepath", subtype="FILE_PATH")
    bpy.types.Scene.geoIsSegPtr = bpy.props.BoolProperty(name="Is Segmented Address")
    bpy.types.Scene.replaceStarRefs = bpy.props.BoolProperty(
        name="Replace old DL references in other actors", default=True
    )
    bpy.types.Scene.replaceTransparentStarRefs = bpy.props.BoolProperty(
        name="Replace old DL references in other actors", default=True
    )
    bpy.types.Scene.replaceCapRefs = bpy.props.BoolProperty(
        name="Replace old DL references in other actors", default=True
    )
    bpy.types.Scene.modifyOldGeo = bpy.props.BoolProperty(name="Rename old geolayout to avoid conflicts", default=True)


def sm64_geo_writer_unregister():
    for cls in reversed(sm64_geo_writer_classes):
        unregister_class(cls)

    del bpy.types.Scene.geoExportStart
    del bpy.types.Scene.geoExportEnd
    del bpy.types.Scene.overwriteModelLoad
    del bpy.types.Scene.modelLoadLevelScriptCmd
    del bpy.types.Scene.modelID
    del bpy.types.Scene.textDumpGeo
    del bpy.types.Scene.textDumpGeoPath
    del bpy.types.Scene.geoUseBank0
    del bpy.types.Scene.geoRAMAddr
    del bpy.types.Scene.geoSeparateTextureDef
    del bpy.types.Scene.geoInsertableBinaryPath
    del bpy.types.Scene.geoIsSegPtr
    del bpy.types.Scene.replaceStarRefs
    del bpy.types.Scene.replaceTransparentStarRefs
    del bpy.types.Scene.replaceCapRefs
    del bpy.types.Scene.modifyOldGeo
