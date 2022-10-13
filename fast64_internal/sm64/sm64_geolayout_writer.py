import bpy, mathutils, math, copy, os, shutil
from bpy.utils import register_class, unregister_class

from os.path import basename
from io import BytesIO

from .sm64_objects import InlineGeolayoutObjConfig, inlineGeoLayoutObjects
from .sm64_geolayout_bone import getSwitchOptionBone, animatableBoneTypes
from .sm64_geolayout_constants import *
from .sm64_geolayout_utility import *
from .sm64_constants import *
from .sm64_camera import saveCameraSettingsToGeolayout
from .sm64_geolayout_classes import *
from .sm64_f3d_writer import *
from .sm64_texscroll import *
from .sm64_utility import *
from .sm64_utility import check_obj_is_room

from ..utility import *
from ..operators import ObjectDataExporter
from ..panels import SM64_Panel


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
    setOrigin(armatureObj, obj)

    # Apply armature scale.
    bpy.ops.object.select_all(action="DESELECT")
    armatureObj.select_set(True)
    bpy.context.view_layer.objects.active = armatureObj
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


def appendRevertToGeolayout(geolayoutGraph, fModel):
    fModel.materialRevert = GfxList(
        fModel.name + "_" + "material_revert_render_settings", GfxListTag.MaterialRevert, fModel.DLFormat
    )
    revertMatAndEndDraw(fModel.materialRevert, [DPSetEnvColor(0xFF, 0xFF, 0xFF, 0xFF), DPSetAlphaCompare("G_AC_NONE")])

    # Get all draw layers, turn layers into strings (some are ints), deduplicate using a set
    drawLayers = set(str(layer) for layer in geolayoutGraph.getDrawLayers())

    # Revert settings in each draw layer
    for layer in sorted(drawLayers):  # Must be sorted, otherwise ordering is random due to `set` behavior
        dlNode = DisplayListNode(layer)
        dlNode.DLmicrocode = fModel.materialRevert

        # Assume first node is start render area
        # This is important, since a render area groups things separately.
        # If we added these nodes outside the render area, they would not happen
        # right after the nodes inside.
        geolayoutGraph.startGeolayout.nodes[0].children.append(TransformNode(dlNode))


# Convert to Geolayout
def convertArmatureToGeolayout(
    armatureObj, obj, convertTransformMatrix, f3dType, isHWv1, camera, name, DLFormat, convertTextureData
):

    fModel = SM64Model(f3dType, isHWv1, name, DLFormat)

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
            meshGeolayout.nodes[i],
            [],
            name,
            meshGeolayout,
            geolayoutGraph,
            infoDict,
            convertTextureData,
        )
    generateSwitchOptions(meshGeolayout.nodes[0], meshGeolayout, geolayoutGraph, name)
    appendRevertToGeolayout(geolayoutGraph, fModel)
    geolayoutGraph.generateSortedList()
    # if DLFormat == DLFormat.GameSpecific:
    # 	geolayoutGraph.convertToDynamic()
    return geolayoutGraph, fModel


# Camera is unused here
def convertObjectToGeolayout(
    obj, convertTransformMatrix, f3dType, isHWv1, camera, name, fModel: FModel, areaObj, DLFormat, convertTextureData
):

    if fModel is None:
        fModel = SM64Model(f3dType, isHWv1, name, DLFormat)

    # convertTransformMatrix = convertTransformMatrix @ \
    # 	mathutils.Matrix.Diagonal(obj.scale).to_4x4()

    # Start geolayout
    if areaObj is not None:
        geolayoutGraph = GeolayoutGraph(name)
        # cameraObj = getCameraObj(camera)
        meshGeolayout = saveCameraSettingsToGeolayout(geolayoutGraph, areaObj, obj, name + "_geo")
        rootObj = areaObj
        fModel.global_data.addAreaData(
            areaObj.areaIndex, FAreaData(FFogData(areaObj.area_fog_position, areaObj.area_fog_color))
        )

    else:
        geolayoutGraph = GeolayoutGraph(name + "_geo")
        if isinstance(obj.data, bpy.types.Mesh) and obj.use_render_area:
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
        cleanupDuplicatedObjects(allObjs)
        rootObj.select_set(True)
        bpy.context.view_layer.objects.active = rootObj
    except Exception as e:
        cleanupDuplicatedObjects(allObjs)
        rootObj.select_set(True)
        bpy.context.view_layer.objects.active = rootObj
        raise Exception(str(e))

    appendRevertToGeolayout(geolayoutGraph, fModel)
    geolayoutGraph.generateSortedList()
    # if DLFormat == DLFormat.GameSpecific:
    # 	geolayoutGraph.convertToDynamic()
    return geolayoutGraph, fModel


# C Export
def exportGeolayoutArmatureC(
    armatureObj,
    obj,
    convertTransformMatrix,
    f3dType,
    isHWv1,
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
        armatureObj, obj, convertTransformMatrix, f3dType, isHWv1, camera, dirName, DLFormat, not savePNG
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
    f3dType,
    isHWv1,
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
    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, f3dType, isHWv1, camera, dirName, None, None, DLFormat, not savePNG
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

    gfxFormatter = SM64GfxFormatter(ScrollMethod.Vertex)
    if not customExport and headerType == "Level":
        texExportPath = dirPath
    else:
        texExportPath = geoDirPath
    exportData = fModel.to_c(TextureExportSettings(texSeparate, savePNG, texDir, texExportPath), gfxFormatter)
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData
    texC = exportData.textureData

    scrollData, hasScrolling = fModel.to_c_vertex_scroll(scrollName, gfxFormatter)
    scroll_data = scrollData.source
    cDefineScroll = scrollData.header
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
        matCInclude = '#include "actors/' + dirName + '/material.inc.c"'
        matHInclude = '#include "actors/' + dirName + '/material.inc.h"'
        headerInclude = '#include "actors/' + dirName + '/geo_header.h"'

        if not customExport:
            # Group name checking, before anything is exported to prevent invalid state on error.
            if groupName == "" or groupName is None:
                raise PluginError("Actor header type chosen but group name not provided.")

            groupPathC = os.path.join(dirPath, groupName + ".c")
            groupPathGeoC = os.path.join(dirPath, groupName + "_geo.c")
            groupPathH = os.path.join(dirPath, groupName + ".h")

            if not os.path.exists(groupPathC):
                raise PluginError(
                    groupPathC + ' not found.\n Most likely issue is that "' + groupName + '" is an invalid group name.'
                )
            elif not os.path.exists(groupPathGeoC):
                raise PluginError(
                    groupPathGeoC
                    + ' not found.\n Most likely issue is that "'
                    + groupName
                    + '" is an invalid group name.'
                )
            elif not os.path.exists(groupPathH):
                raise PluginError(
                    groupPathH + ' not found.\n Most likely issue is that "' + groupName + '" is an invalid group name.'
                )

    else:
        matCInclude = '#include "levels/' + levelName + "/" + dirName + '/material.inc.c"'
        matHInclude = '#include "levels/' + levelName + "/" + dirName + '/material.inc.h"'
        headerInclude = '#include "levels/' + levelName + "/" + dirName + '/geo_header.h"'

    modifyTexScrollFiles(exportDir, geoDirPath, cDefineScroll, scroll_data, hasScrolling)

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

            # Write to group files
            groupPathC = os.path.join(dirPath, groupName + ".c")
            groupPathGeoC = os.path.join(dirPath, groupName + "_geo.c")
            groupPathH = os.path.join(dirPath, groupName + ".h")

            writeIfNotFound(groupPathC, '\n#include "' + dirName + '/model.inc.c"', "")
            writeIfNotFound(groupPathGeoC, '\n#include "' + dirName + '/geo.inc.c"', "")
            writeIfNotFound(groupPathH, '\n#include "' + dirName + '/geo_header.h"', "\n#endif")

            texscrollIncludeC = '#include "actors/' + dirName + '/texscroll.inc.c"'
            texscrollIncludeH = '#include "actors/' + dirName + '/texscroll.inc.h"'
            texscrollGroup = groupName
            texscrollGroupInclude = '#include "actors/' + groupName + '.h"'

        elif headerType == "Level":
            groupPathC = os.path.join(dirPath, "leveldata.c")
            groupPathGeoC = os.path.join(dirPath, "geo.c")
            groupPathH = os.path.join(dirPath, "header.h")

            writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + "/" + dirName + '/model.inc.c"', "")
            writeIfNotFound(groupPathGeoC, '\n#include "levels/' + levelName + "/" + dirName + '/geo.inc.c"', "")
            writeIfNotFound(
                groupPathH, '\n#include "levels/' + levelName + "/" + dirName + '/geo_header.h"', "\n#endif"
            )

            texscrollIncludeC = '#include "levels/' + levelName + "/" + dirName + '/texscroll.inc.c"'
            texscrollIncludeH = '#include "levels/' + levelName + "/" + dirName + '/texscroll.inc.h"'
            texscrollGroup = levelName
            texscrollGroupInclude = '#include "levels/' + levelName + '/header.h"'

        fileStatus = modifyTexScrollHeadersGroup(
            exportDir,
            texscrollIncludeC,
            texscrollIncludeH,
            texscrollGroup,
            cDefineScroll,
            texscrollGroupInclude,
            hasScrolling,
        )

        if DLFormat != DLFormat.Static:  # Change this
            writeMaterialHeaders(exportDir, matCInclude, matHInclude)

    return staticData.header, fileStatus


# Insertable Binary
def exportGeolayoutArmatureInsertableBinary(
    armatureObj, obj, convertTransformMatrix, f3dType, isHWv1, filepath, camera
):
    geolayoutGraph, fModel = convertArmatureToGeolayout(
        armatureObj, obj, convertTransformMatrix, f3dType, isHWv1, camera, armatureObj.name, DLFormat.Static, True
    )

    saveGeolayoutInsertableBinary(geolayoutGraph, fModel, filepath, f3dType)


def exportGeolayoutObjectInsertableBinary(obj, convertTransformMatrix, f3dType, isHWv1, filepath, camera):
    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, f3dType, isHWv1, camera, obj.name, None, None, DLFormat.Static, True
    )

    saveGeolayoutInsertableBinary(geolayoutGraph, fModel, filepath, f3dType)


def saveGeolayoutInsertableBinary(geolayoutGraph, fModel, filepath, f3d):
    data, startRAM = getBinaryBank0GeolayoutData(fModel, geolayoutGraph, 0, [0, 0xFFFFFF])

    address_ptrs = geolayoutGraph.get_ptr_addresses()
    address_ptrs.extend(fModel.get_ptr_addresses(f3d))

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
    f3dType,
    isHWv1,
    RAMAddr,
    camera,
):

    geolayoutGraph, fModel = convertArmatureToGeolayout(
        armatureObj, obj, convertTransformMatrix, f3dType, isHWv1, camera, armatureObj.name, DLFormat.Static, True
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
    f3dType,
    isHWv1,
    RAMAddr,
    camera,
):

    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, f3dType, isHWv1, camera, obj.name, None, None, DLFormat.Static, True
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
    f3dType,
    isHWv1,
    camera,
):

    geolayoutGraph, fModel = convertArmatureToGeolayout(
        armatureObj, obj, convertTransformMatrix, f3dType, isHWv1, camera, armatureObj.name, DLFormat.Static, True
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
    f3dType,
    isHWv1,
    camera,
):

    geolayoutGraph, fModel = convertObjectToGeolayout(
        obj, convertTransformMatrix, f3dType, isHWv1, camera, obj.name, None, None, DLFormat.Static, True
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


# Switch Handling Process
# When convert armature to geolayout node hierarchy, mesh switch options
# are converted to switch node children, but material/draw layer options
# are converted to SwitchOverrideNodes. During this process, any material
# override geometry will be generated as well.

# Afterward, the node hierarchy is traversed again, and any SwitchOverride
# nodes are converted to actual geolayout node hierarchies.
def generateSwitchOptions(transformNode, geolayout, geolayoutGraph, prefix):
    if isinstance(transformNode.node, JumpNode):
        for node in transformNode.node.geolayout.nodes:
            generateSwitchOptions(node, transformNode.node.geolayout, geolayoutGraph, prefix)
    overrideNodes = []
    if isinstance(transformNode.node, SwitchNode):
        switchName = transformNode.node.name
        prefix += "_" + switchName
        # prefix = switchName

        materialOverrideTexDimensions = None

        i = 0
        while i < len(transformNode.children):
            prefixName = prefix + "_opt" + str(i)
            childNode = transformNode.children[i]
            if isinstance(childNode.node, SwitchOverrideNode):
                drawLayer = childNode.node.drawLayer
                material = childNode.node.material
                specificMat = childNode.node.specificMat
                overrideType = childNode.node.overrideType
                texDimensions = childNode.node.texDimensions
                if (
                    texDimensions is not None
                    and materialOverrideTexDimensions is not None
                    and materialOverrideTexDimensions != tuple(texDimensions)
                ):
                    raise PluginError(
                        'In switch bone "'
                        + switchName
                        + '", some material '
                        + "overrides \nhave textures with dimensions differing from the original material.\n"
                        + "UV coordinates are in pixel units, so there will be UV errors in those overrides.\n "
                        + "Make sure that all overrides have the same texture dimensions as the original material.\n"
                        + "Note that materials with no textures default to dimensions of 32x32."
                    )

                if texDimensions is not None:
                    materialOverrideTexDimensions = tuple(texDimensions)

                # This should be a 0xB node
                # copyNode = duplicateNode(transformNode.children[0],
                # 	transformNode, transformNode.children.index(childNode))
                index = transformNode.children.index(childNode)
                transformNode.children.remove(childNode)

                # Switch option bones should have unique names across all
                # armatures.
                optionGeolayout = geolayoutGraph.addGeolayout(childNode, prefixName)
                geolayoutGraph.addJumpNode(transformNode, geolayout, optionGeolayout, index)
                optionGeolayout.nodes.append(TransformNode(StartNode()))
                copyNode = optionGeolayout.nodes[0]

                # i -= 1
                # Assumes first child is a start node, where option 0 is
                # assumes overrideChild starts with a Start node
                option0Nodes = [transformNode.children[0]]
                if len(option0Nodes) == 1 and isinstance(option0Nodes[0].node, StartNode):
                    for startChild in option0Nodes[0].children:
                        generateOverrideHierarchy(
                            copyNode,
                            startChild,
                            material,
                            specificMat,
                            overrideType,
                            drawLayer,
                            option0Nodes[0].children.index(startChild),
                            optionGeolayout,
                            geolayoutGraph,
                            optionGeolayout.name,
                        )
                else:
                    for overrideChild in option0Nodes:
                        generateOverrideHierarchy(
                            copyNode,
                            overrideChild,
                            material,
                            specificMat,
                            overrideType,
                            drawLayer,
                            option0Nodes.index(overrideChild),
                            optionGeolayout,
                            geolayoutGraph,
                            optionGeolayout.name,
                        )
                if material is not None:
                    overrideNodes.append(copyNode)
            i += 1
    for i in range(len(transformNode.children)):
        childNode = transformNode.children[i]
        if isinstance(transformNode.node, SwitchNode):
            prefixName = prefix + "_opt" + str(i)
        else:
            prefixName = prefix

        if childNode not in overrideNodes:
            generateSwitchOptions(childNode, geolayout, geolayoutGraph, prefixName)


def generateOverrideHierarchy(
    parentCopyNode,
    transformNode,
    material,
    specificMat,
    overrideType,
    drawLayer,
    index,
    geolayout,
    geolayoutGraph,
    switchOptionName,
):
    # print(transformNode.node)
    if isinstance(transformNode.node, SwitchOverrideNode) and material is not None:
        return

    copyNode = TransformNode(copy.copy(transformNode.node))
    copyNode.parent = parentCopyNode
    parentCopyNode.children.insert(index, copyNode)
    if isinstance(transformNode.node, JumpNode):
        jumpName = switchOptionName + "_jump_" + transformNode.node.geolayout.name
        jumpGeolayout = geolayoutGraph.addGeolayout(transformNode, jumpName)
        oldGeolayout = copyNode.node.geolayout
        copyNode.node.geolayout = jumpGeolayout
        geolayoutGraph.addGeolayoutCall(geolayout, jumpGeolayout)
        startNode = TransformNode(StartNode())
        jumpGeolayout.nodes.append(startNode)
        if len(oldGeolayout.nodes) == 1 and isinstance(oldGeolayout.nodes[0].node, StartNode):
            for node in oldGeolayout.nodes[0].children:
                generateOverrideHierarchy(
                    startNode,
                    node,
                    material,
                    specificMat,
                    overrideType,
                    drawLayer,
                    oldGeolayout.nodes[0].children.index(node),
                    jumpGeolayout,
                    geolayoutGraph,
                    jumpName,
                )
        else:
            for node in oldGeolayout.nodes:
                generateOverrideHierarchy(
                    startNode,
                    node,
                    material,
                    specificMat,
                    overrideType,
                    drawLayer,
                    oldGeolayout.nodes.index(node),
                    jumpGeolayout,
                    geolayoutGraph,
                    jumpName,
                )

    elif not isinstance(copyNode.node, SwitchOverrideNode) and copyNode.node.hasDL:
        if material is not None:
            copyNode.node.DLmicrocode = copyNode.node.fMesh.drawMatOverrides[(material, specificMat, overrideType)]
        if drawLayer is not None:
            copyNode.node.drawLayer = drawLayer

    for child in transformNode.children:
        generateOverrideHierarchy(
            copyNode,
            child,
            material,
            specificMat,
            overrideType,
            drawLayer,
            transformNode.children.index(child),
            geolayout,
            geolayoutGraph,
            switchOptionName,
        )


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
    useGeoEmpty = obj.data is None and checkSM64EmptyUsesGeoLayout(obj.sm64_obj_type)

    return isinstance(obj.data, bpy.types.Mesh) or useGeoEmpty


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
    elif inlineGeoConfig.name == "Custom Geo Command":
        node = CustomNode(obj.customGeoCommand, obj.customGeoCommandArgs)
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
        node = ScaleNode(obj.draw_layer_static, scale, obj.useDLReference, obj.dlReference)
    else:
        raise PluginError(f"Ooops! Didnt implement inline geo exporting for {inlineGeoConfig.name}")

    return node, parentTransformNode


def extract_room_objects(objects: list[bpy.types.Object]):
    objs: list[bpy.types.Object] = []
    for obj in objects:
        if not obj:
            continue
        if check_obj_is_room(obj):
            objs.extend(sorted(obj.children, key=lambda childObj: childObj.original_name.lower()))
        else:
            objs.append(obj)
    return objs


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
    # finalTransform = copy.deepcopy(transformMatrix)

    useGeoEmpty = obj.data is None and checkSM64EmptyUsesGeoLayout(obj.sm64_obj_type)

    useSwitchNode = obj.data is None and obj.sm64_obj_type == "Switch"

    useInlineGeo = obj.data is None and checkIsSM64InlineGeoLayout(obj.sm64_obj_type)

    addRooms = isRoot and obj.data is None and obj.sm64_obj_type == "Area Root" and obj.enableRoomSwitch

    # if useAreaEmpty and areaIndex is not None and obj.areaIndex != areaIndex:
    # 	return

    inlineGeoConfig: InlineGeolayoutObjConfig = inlineGeoLayoutObjects.get(obj.sm64_obj_type)
    processed_inline_geo = False

    isPreInlineGeoLayout = checkIsSM64PreInlineGeoLayout(obj.sm64_obj_type)
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
        orig_mtx = mathutils.Matrix(obj["original_mtx"])
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
            childObj: bpy.types.Object = alphabeticalChildren[i]
            if i == 0:  # Outside room system
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
                inlineGeoConfig, obj, parentTransformNode, translate, rotate, scale[0]
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

        if obj.data is not None and (obj.use_render_range or obj.add_shadow or obj.add_func):

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

        if obj.data is None:
            fMeshes = {}
        elif obj.get("instanced_mesh_name"):
            temp_obj = get_obj_temp_mesh(obj)
            if temp_obj is None:
                raise ValueError(
                    "The source of an instanced mesh could not be found. Please contact a Fast64 maintainer for support."
                )

            src_meshes = temp_obj.get("src_meshes", [])

            if len(src_meshes):
                fMeshes = {}
                node.dlRef = src_meshes[0]["name"]
                node.drawLayer = src_meshes[0]["layer"]
                processed_inline_geo = True

                for src_mesh in src_meshes[1:]:
                    additionalNode = (
                        DisplayListNode(src_mesh["layer"], src_mesh["name"])
                        if not isinstance(node, BillboardNode)
                        else BillboardNode(src_mesh["layer"], True, [0, 0, 0], src_mesh["name"])
                    )
                    additionalTransformNode = TransformNode(additionalNode)
                    transformNode.children.append(additionalTransformNode)
                    additionalTransformNode.parent = transformNode

            else:
                triConverterInfo = TriangleConverterInfo(
                    temp_obj, None, fModel.f3d, transformMatrix, getInfoDict(temp_obj)
                )
                fMeshes = saveStaticModel(
                    triConverterInfo, fModel, temp_obj, transformMatrix, fModel.name, convertTextureData, False, "sm64"
                )
                if fMeshes:
                    temp_obj["src_meshes"] = [
                        ({"name": fMesh.draw.name, "layer": drawLayer}) for drawLayer, fMesh in fMeshes.items()
                    ]
                    node.dlRef = temp_obj["src_meshes"][0]["name"]
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
            for drawLayer, fMesh in fMeshes.items():
                if not firstNodeProcessed:
                    node.DLmicrocode = fMesh.draw
                    node.fMesh = fMesh
                    node.drawLayer = drawLayer  # previous drawLayer assignments useless?
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
                    transformNode.children.append(additionalTransformNode)
                    additionalTransformNode.parent = transformNode

        parentTransformNode.children.append(transformNode)
        transformNode.parent = parentTransformNode

        alphabeticalChildren = sorted(obj.children, key=lambda childObj: childObj.original_name.lower())
        if obj.parent and obj.parent.sm64_obj_type == "Area Root" and obj.parent.enableRoomSwitch:
            room_data = obj.fast64.sm64.room
            alphabeticalChildren = (
                extract_room_objects([o.obj for o in room_data.objects_render_before if o.obj])
                + alphabeticalChildren
                + extract_room_objects([o.obj for o in room_data.objects_render_after if o.obj])
            )

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
    poseBone = armatureObj.pose.bones[boneName]
    boneGroup = poseBone.bone_group
    finalTransform = copy.deepcopy(transformMatrix)
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

    translation = mathutils.Matrix.Translation(translate)
    rotation = rotate.to_matrix().to_4x4()
    zeroTranslation = isZeroTranslation(translate)
    zeroRotation = isZeroRotation(rotate)

    # hasDL = bone.use_deform
    hasDL = True
    if bone.geo_cmd in animatableBoneTypes:
        if bone.geo_cmd == "CustomAnimated":
            if not bone.fast64.sm64.custom_geo_cmd_macro:
                raise PluginError(f'Bone "{boneName}" on armature "{armatureObj.name}" needs a geo command macro.')
            node = CustomAnimatedNode(bone.fast64.sm64.custom_geo_cmd_macro, int(bone.draw_layer), translate, rotate)
            lastTranslateName = boneName
            lastRotateName = boneName
        else:  # DisplayListWithOffset
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

        finalTransform = transformMatrix @ translation

    elif bone.geo_cmd == "CustomNonAnimated":
        if bone.fast64.sm64.custom_geo_cmd_macro == "":
            raise PluginError(f'Bone "{boneName}" on armature "{armatureObj.name}" needs a geo command macro.')
        node = CustomNode(bone.fast64.sm64.custom_geo_cmd_macro, bone.fast64.sm64.custom_geo_cmd_args)
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
                finalTransform = transformMatrix @ translation @ rotation
                lastTranslateName = boneName
                lastRotateName = boneName
            elif node.fieldLayout == 1:
                finalTransform = transformMatrix @ translation
                lastTranslateName = boneName
            elif node.fieldLayout == 2:
                finalTransform = transformMatrix @ rotation
                lastRotateName = boneName
            else:
                yRot = rotate.to_euler().y
                rotation = mathutils.Euler((0, yRot, 0)).to_matrix().to_4x4()
                finalTransform = transformMatrix @ rotation
                lastRotateName = boneName

        elif bone.geo_cmd == "Translate":
            node = TranslateNode(int(bone.draw_layer), hasDL, translate)
            finalTransform = transformMatrix @ translation
            lastTranslateName = boneName
        elif bone.geo_cmd == "Rotate":
            node = RotateNode(int(bone.draw_layer), hasDL, rotate)
            finalTransform = transformMatrix @ rotation
            lastRotateName = boneName
        elif bone.geo_cmd == "Billboard":
            node = BillboardNode(int(bone.draw_layer), hasDL, translate)
            finalTransform = transformMatrix @ translation
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
            finalTransform = transformMatrix @ mathutils.Matrix.Scale(node.scaleValue, 4)
        elif bone.geo_cmd == "StartRenderArea":
            node = StartRenderAreaNode(bone.culling_radius)
        else:
            raise PluginError("Invalid geometry command: " + bone.geo_cmd)

    transformNode = TransformNode(node)
    additionalNodes = []

    if node.hasDL:
        triConverterInfo = TriangleConverterInfo(
            obj,
            armatureObj.data,
            fModel.f3d,
            mathutils.Matrix.Scale(bpy.context.scene.blenderToSM64Scale, 4) @ bone.matrix_local.inverted(),
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

    if not isinstance(transformNode.node, SwitchNode):
        # print(boneGroup.name if boneGroup is not None else "Offset")
        if len(bone.children) > 0:
            # print("\tHas Children")
            if bone.geo_cmd == "Function":
                raise PluginError(
                    "Function bones cannot have children. They instead affect the next sibling bone in alphabetical order."
                )

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
                    finalTransform,
                    lastTranslateName,
                    lastRotateName,
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

    # see generateSwitchOptions() for explanation.
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
                    finalTransform,
                    lastTranslateName,
                    lastRotateName,
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
                elif not isinstance(optionArmature.data, bpy.types.Armature):
                    raise PluginError(
                        "Error: In switch bone "
                        + boneName
                        + " for option "
                        + str(switchIndex)
                        + ", the object provided is not an armature."
                    )
                elif optionArmature in geolayoutGraph.secondaryGeolayouts:
                    optionGeolayout = geolayoutGraph.secondaryGeolayouts[optionArmature]
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
                        if isinstance(childObj.data, bpy.types.Mesh):
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
                        finalTransform,
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
                    specificMat = None
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

            materialOverrides.append((switchOption.materialOverride, specificMat, switchOption.materialOverrideType))


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
    skinnedNode = DisplayListNode(drawLayer)
    skinnedNode.fMesh = skinnedMesh
    skinnedNode.DLmicrocode = skinnedMesh.draw
    skinnedTransformNode = TransformNode(skinnedNode)

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

    transformMatrix = mathutils.Matrix.Scale(bpy.context.scene.blenderToSM64Scale, 4)
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

        for material_index, bFaces in materialFaces.items():
            material = obj.material_slots[material_index].material
            checkForF3dMaterialInFaces(obj, material)
            fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)
            if fMaterial.useLargeTextures:
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

    # Must be done after all geometry saved
    for (material, specificMat, overrideType) in materialOverrides:
        for drawLayer, fMesh in fMeshes.items():
            saveOverrideDraw(obj, fModel, material, specificMat, overrideType, fMesh, drawLayer, convertTextureData)
        for drawLayer, fMesh in fSkinnedMeshes.items():
            saveOverrideDraw(obj, fModel, material, specificMat, overrideType, fMesh, drawLayer, convertTextureData)

    return fMeshes, fSkinnedMeshes, usedDrawLayers


def saveOverrideDraw(obj, fModel, material, specificMat, overrideType, fMesh, drawLayer, convertTextureData):
    fOverrideMat, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)
    overrideIndex = str(len(fMesh.drawMatOverrides))
    if (material, specificMat, overrideType) in fMesh.drawMatOverrides:
        overrideIndex = fMesh.drawMatOverrides[(material, specificMat, overrideType)].name[-1]
    meshMatOverride = GfxList(
        fMesh.name + "_mat_override_" + toAlnum(material.name) + "_" + overrideIndex, GfxListTag.Draw, fModel.DLFormat
    )
    fMesh.drawMatOverrides[(material, specificMat, overrideType)] = meshMatOverride
    # Copy the DL from the original mesh into the material override mesh
    for command in fMesh.draw.commands:
        meshMatOverride.commands.append(copy.copy(command))
    # Keep track of a set of commands to remove
    removeCommands = set()
    # Keep track of the reverts that were added during scanning
    addedReverts = set()
    # Keep track of the previous material for removing unnecessary material loads and reverts
    prevMaterial = None
    # Keep track of the previous command, so we can remove if it becomes an unnecessary revert
    prevCommand = None
    # Scan the displaylist to look for material loads and reverts
    # Use a while instead of a for to be able to insert into the list during iteration
    commandIdx = 0
    while commandIdx < len(meshMatOverride.commands):
        # Get the command at the current index
        command = meshMatOverride.commands[commandIdx]
        if isinstance(command, SPDisplayList):
            # Check every material in the model
            for (modelMaterial, modelDrawLayer, modelAreaIndex), (
                fMaterial,
                texDimensions,
            ) in fModel.getAllMaterials().items():
                # Determine if the currently checked material should be overriden
                shouldModify = (overrideType == "Specific" and modelMaterial in specificMat) or (
                    overrideType == "All" and modelMaterial not in specificMat
                )
                # Check if this is a DL to load the checked material
                if command.displayList == fMaterial.material:
                    curMaterial = fMaterial
                    # If it is, check if this material should be replaced and replace it if so
                    if shouldModify:
                        # Replace the current material with the override
                        curMaterial = fOverrideMat
                        command.displayList = fOverrideMat.material
                    # Check if this material is the same as the prevous loaded material in the DL
                    if prevMaterial == curMaterial:
                        # If so, tag this material load for removal
                        removeCommands.add(command)
                        # Scan backwards for any reverts
                        prevIndex = commandIdx - 1
                        while prevIndex >= 0:
                            prevCommand = meshMatOverride.commands[prevIndex]
                            # If the previous command is a revert for this material, remove that revert as well
                            if isinstance(prevCommand, SPDisplayList) and prevCommand.displayList == curMaterial.revert:
                                removeCommands.add(prevCommand)
                                prevIndex -= 1
                            else:
                                break
                    # Record the current material as the next command's previous material
                    prevMaterial = curMaterial
                    # We found what this current command is, so we can skip checking other materials
                    break
                # Check if this is a DL to revert for checked material
                if command.displayList == fMaterial.revert:
                    # If it is, check if this material should be replaced and replace the revert if so
                    if shouldModify:
                        # Check if the override material has a revert
                        if fOverrideMat.revert is not None:
                            # If it does, then replace the displaylist for this revert
                            command.displayList = fOverrideMat.revert
                        else:
                            # Otherwise, tag this revert for removal
                            removeCommands.add(command)
                    # We found what this current command is, so we can skip checking other materials
                    break
                # At this point, the current command is confirmed to be neither a material load nor a material revert.
                # If the override material has a revert and the original material didn't, insert a revert after this command.
                # This is needed to ensure that override materials that need a revert get them.
                # Improperly added reverts will get removed later.
                # Don't add reverts after added reverts, or we get stuck in an infinite loop.
                if command not in addedReverts:
                    if fMaterial.revert is None and fOverrideMat.revert is not None:
                        newCommand = SPDisplayList(fOverrideMat.revert)
                        # Add this revert to the set of reverts that were inserted for checking later on
                        addedReverts.add(newCommand)
                        # Insert the new command
                        meshMatOverride.commands.insert(commandIdx + 1, newCommand)
                # Check if the previous command was a revert we added, as a revert must be followed by a load for it to
                # be valid. This command is confirmed to not be a material load, so remove the previous command if it is
                # an added revert.
                prevIndex = commandIdx - 1
                if prevIndex > 0:
                    prevCommand = meshMatOverride.commands[prevIndex]
                    if prevCommand in addedReverts:
                        # Remove this added revert
                        removeCommands.add(prevCommand)

        commandIdx += 1
    # Remove all commands tagged for removal
    for command in removeCommands:
        meshMatOverride.commands.remove(command)


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
    for material_index, skinnedFaceArray in skinnedFaces.items():
        # These MUST be arrays (not dicts) as order is important
        inGroupVerts = []
        inGroupVertArray.append([material_index, inGroupVerts])

        notInGroupVerts = []
        notInGroupVertArray.append([material_index, notInGroupVerts])

        material = obj.material_slots[material_index].material
        fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)

        exportVertexColors = isLightingDisabled(material)
        convertInfo = LoopConvertInfo(uv_data, obj, exportVertexColors)
        for skinnedFace in skinnedFaceArray:
            for (face, loop) in skinnedFace.loopsInGroup:
                f3dVert = getF3DVert(loop, face, convertInfo, obj.data)
                bufferVert = BufferVertex(f3dVert, None, material_index)
                if bufferVert not in inGroupVerts:
                    inGroupVerts.append(bufferVert)
                loopDict[loop] = f3dVert
            for (face, loop) in skinnedFace.loopsNotInGroup:
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
    for material_index, vertData in notInGroupVertArray:
        material = obj.material_slots[material_index].material
        checkForF3dMaterialInFaces(obj, material)
        f3dMat = material.f3d_mat if material.mat_ver > 3 else material
        if f3dMat.rdp_settings.set_rendermode:
            drawLayerKey = drawLayer
        else:
            drawLayerKey = None

        materialKey = (material, drawLayerKey, fModel.global_data.getCurrentAreaKey(material))
        fMaterial, texDimensions = fModel.getMaterialAndHandleShared(materialKey)
        isPointSampled = isTexturePointSampled(material)
        exportVertexColors = isLightingDisabled(material)

        skinnedTriGroup = fSkinnedMesh.tri_group_new(fMaterial)
        fSkinnedMesh.draw.commands.append(SPDisplayList(fMaterial.material))
        fSkinnedMesh.draw.commands.append(SPDisplayList(skinnedTriGroup.triList))
        skinnedTriGroup.triList.commands.append(
            SPVertex(skinnedTriGroup.vertexList, len(skinnedTriGroup.vertexList.vertices), len(vertData), curIndex)
        )
        curIndex += len(vertData)

        for bufferVert in vertData:
            skinnedTriGroup.vertexList.vertices.append(
                convertVertexData(
                    obj.data,
                    bufferVert.f3dVert[0],
                    bufferVert.f3dVert[1],
                    bufferVert.f3dVert[2],
                    texDimensions,
                    parentMatrix,
                    isPointSampled,
                    exportVertexColors,
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

    for material_index, skinnedFaceArray in skinnedFaces.items():
        material = obj.material_slots[material_index].material
        faces = [skinnedFace.bFace for skinnedFace in skinnedFaceArray]
        fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)
        if fMaterial.useLargeTextures:
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
    # for material_index, skinnedFaceArray in skinnedFaces.items():
    #
    # 	# We've already saved all materials, this just returns the existing ones.
    # 	material = obj.material_slots[material_index].material
    # 	fMaterial, texDimensions = \
    # 		saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)
    # 	isPointSampled = isTexturePointSampled(material)
    # 	exportVertexColors = isLightingDisabled(material)
    #
    # 	triGroup = fMesh.tri_group_new(fMaterial)
    # 	fMesh.draw.commands.append(SPDisplayList(fMaterial.material))
    # 	fMesh.draw.commands.append(SPDisplayList(triGroup.triList))
    # 	if fMaterial.revert is not None:
    # 		fMesh.draw.commands.append(SPDisplayList(fMaterial.revert))
    #
    # 	convertInfo = LoopConvertInfo(uv_data, obj, exportVertexColors)
    # 	triConverter = TriangleConverter(triConverterInfo, texDimensions, material,
    # 		None, triGroup.triList, triGroup.vertexList, copy.deepcopy(existingVertData), copy.deepcopy(matRegionDict))
    # 	saveTriangleStrip(triConverter, [skinnedFace.bFace for skinnedFace in skinnedFaceArray], obj.data, True)
    # 	saveTriangleStrip(triConverterClass,
    # 		[skinnedFace.bFace for skinnedFace in skinnedFaceArray],
    # 		convertInfo, triGroup.triList, triGroup.vertexList, fModel.f3d,
    # 		texDimensions, currentMatrix, isPointSampled, exportVertexColors,
    # 		copy.deepcopy(existingVertData), copy.deepcopy(matRegionDict),
    # 		infoDict, obj.data, None, True)

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

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileOutput = None
        tempROM = None
        try:
            obj = None
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            if len(context.selected_objects) == 0:
                raise PluginError("Object not selected.")
            obj = context.active_object
            if type(obj.data) is not bpy.types.Mesh and not (
                obj.data is None and (obj.sm64_obj_type == "None" or obj.sm64_obj_type == "Switch")
            ):
                raise PluginError('Selected object must be a mesh or an empty with the "None" or "Switch" type.')
            # if context.scene.saveCameraSettings and \
            # 	context.scene.levelCamera is None:
            # 	raise PluginError("Cannot save camera settings with no camera provided.")
            # levelCamera = context.scene.levelCamera if \
            # 	context.scene.saveCameraSettings else None

            finalTransform = mathutils.Matrix.Identity(4)
            scaleValue = bpy.context.scene.blenderToSM64Scale
            finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((scaleValue, scaleValue, scaleValue))).to_4x4()
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            self.store_object_data()

            # Rotate all armatures 90 degrees
            applyRotation([obj], math.radians(90), "X")

            saveTextures = bpy.context.scene.saveTextures or bpy.context.scene.ignoreTextureRestrictions

            if context.scene.fast64.sm64.exportType == "C":
                exportPath, levelName = getPathAndLevel(
                    context.scene.geoCustomExport,
                    context.scene.geoExportPath,
                    context.scene.geoLevelName,
                    context.scene.geoLevelOption,
                )
                if not context.scene.geoCustomExport:
                    applyBasicTweaks(exportPath)
                exportGeolayoutObjectC(
                    obj,
                    finalTransform,
                    context.scene.f3d_type,
                    context.scene.isHWv1,
                    exportPath,
                    bpy.context.scene.geoTexDir,
                    saveTextures,
                    saveTextures and bpy.context.scene.geoSeparateTextureDef,
                    None,
                    bpy.context.scene.geoGroupName,
                    context.scene.geoExportHeaderType,
                    context.scene.geoName,
                    context.scene.geoStructName,
                    levelName,
                    context.scene.geoCustomExport,
                    DLFormat.Static,
                )
                self.report({"INFO"}, "Success!")
            elif context.scene.fast64.sm64.exportType == "Insertable Binary":
                exportGeolayoutObjectInsertableBinary(
                    obj,
                    finalTransform,
                    context.scene.f3d_type,
                    context.scene.isHWv1,
                    bpy.path.abspath(bpy.context.scene.geoInsertableBinaryPath),
                    None,
                )
                self.report({"INFO"}, "Success! Data at " + context.scene.geoInsertableBinaryPath)
            else:
                tempROM = tempName(context.scene.outputRom)
                checkExpanded(bpy.path.abspath(context.scene.exportRom))
                romfileExport = open(bpy.path.abspath(context.scene.exportRom), "rb")
                shutil.copy(bpy.path.abspath(context.scene.exportRom), bpy.path.abspath(tempROM))
                romfileExport.close()
                romfileOutput = open(bpy.path.abspath(tempROM), "rb+")

                levelParsed = parseLevelAtPointer(romfileOutput, level_pointers[context.scene.levelGeoExport])
                segmentData = levelParsed.segmentData

                if context.scene.extendBank4:
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
                        finalTransform,
                        *modelLoadInfo,
                        textDumpFilePath,
                        context.scene.f3d_type,
                        context.scene.isHWv1,
                        getAddressFromRAMAddress(int(context.scene.geoRAMAddr, 16)),
                        None,
                    )
                else:
                    addrRange, segPointer = exportGeolayoutObjectBinary(
                        romfileOutput,
                        obj,
                        exportRange,
                        finalTransform,
                        segmentData,
                        *modelLoadInfo,
                        textDumpFilePath,
                        context.scene.f3d_type,
                        context.scene.isHWv1,
                        None,
                    )

                romfileOutput.close()
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                context.view_layer.objects.active = obj

                if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
                    os.remove(bpy.path.abspath(context.scene.outputRom))
                os.rename(bpy.path.abspath(tempROM), bpy.path.abspath(context.scene.outputRom))

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

            if context.scene.fast64.sm64.exportType == "Binary":
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

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileOutput = None
        tempROM = None
        try:
            armatureObj = None
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            armatureObj = context.active_object
            if type(armatureObj.data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            if len(armatureObj.children) == 0 or not isinstance(armatureObj.children[0].data, bpy.types.Mesh):
                raise PluginError("Armature does not have any mesh children, or " + "has a non-mesh child.")
            # if context.scene.saveCameraSettings and \
            # 	context.scene.levelCamera is None:
            # 	raise PluginError("Cannot save camera settings with no camera provided.")
            # levelCamera = context.scene.levelCamera if \
            # 	context.scene.saveCameraSettings else None

            obj = armatureObj.children[0]
            finalTransform = mathutils.Matrix.Identity(4)

            # get all switch option armatures as well
            linkedArmatures = [armatureObj]
            getAllArmatures(armatureObj, linkedArmatures)

            linkedArmatureDict = {}

            for linkedArmature in linkedArmatures:
                # IMPORTANT: Do this BEFORE rotation
                optionObjs = []
                for childObj in linkedArmature.children:
                    if isinstance(childObj.data, bpy.types.Mesh):
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
            bpy.ops.object.select_all(action="DESELECT")
            for linkedArmature, linkedMesh in linkedArmatureDict.items():
                linkedMesh.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)
            if context.scene.fast64.sm64.exportType == "C":
                exportPath, levelName = getPathAndLevel(
                    context.scene.geoCustomExport,
                    context.scene.geoExportPath,
                    context.scene.geoLevelName,
                    context.scene.geoLevelOption,
                )

                saveTextures = bpy.context.scene.saveTextures or bpy.context.scene.ignoreTextureRestrictions
                if not context.scene.geoCustomExport:
                    applyBasicTweaks(exportPath)
                header, fileStatus = exportGeolayoutArmatureC(
                    armatureObj,
                    obj,
                    finalTransform,
                    context.scene.f3d_type,
                    context.scene.isHWv1,
                    exportPath,
                    bpy.context.scene.geoTexDir,
                    saveTextures,
                    saveTextures and bpy.context.scene.geoSeparateTextureDef,
                    None,
                    bpy.context.scene.geoGroupName,
                    context.scene.geoExportHeaderType,
                    context.scene.geoName,
                    context.scene.geoStructName,
                    levelName,
                    context.scene.geoCustomExport,
                    DLFormat.Static,
                )
                starSelectWarning(self, fileStatus)
                self.report({"INFO"}, "Success!")
            elif context.scene.fast64.sm64.exportType == "Insertable Binary":
                exportGeolayoutArmatureInsertableBinary(
                    armatureObj,
                    obj,
                    finalTransform,
                    context.scene.f3d_type,
                    context.scene.isHWv1,
                    bpy.path.abspath(bpy.context.scene.geoInsertableBinaryPath),
                    None,
                )
                self.report({"INFO"}, "Success! Data at " + context.scene.geoInsertableBinaryPath)
            else:
                tempROM = tempName(context.scene.outputRom)
                checkExpanded(bpy.path.abspath(context.scene.exportRom))
                romfileExport = open(bpy.path.abspath(context.scene.exportRom), "rb")
                shutil.copy(bpy.path.abspath(context.scene.exportRom), bpy.path.abspath(tempROM))
                romfileExport.close()
                romfileOutput = open(bpy.path.abspath(tempROM), "rb+")

                levelParsed = parseLevelAtPointer(romfileOutput, level_pointers[context.scene.levelGeoExport])
                segmentData = levelParsed.segmentData

                if context.scene.extendBank4:
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
                        finalTransform,
                        *modelLoadInfo,
                        textDumpFilePath,
                        context.scene.f3d_type,
                        context.scene.isHWv1,
                        getAddressFromRAMAddress(int(context.scene.geoRAMAddr, 16)),
                        None,
                    )
                else:
                    addrRange, segPointer = exportGeolayoutArmatureBinary(
                        romfileOutput,
                        armatureObj,
                        obj,
                        exportRange,
                        finalTransform,
                        segmentData,
                        *modelLoadInfo,
                        textDumpFilePath,
                        context.scene.f3d_type,
                        context.scene.isHWv1,
                        None,
                    )

                romfileOutput.close()
                bpy.ops.object.select_all(action="DESELECT")
                armatureObj.select_set(True)
                context.view_layer.objects.active = armatureObj

                if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
                    os.remove(bpy.path.abspath(context.scene.outputRom))
                os.rename(bpy.path.abspath(tempROM), bpy.path.abspath(context.scene.outputRom))

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

            if context.scene.fast64.sm64.exportType == "Binary":
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
    goal = "Export Object/Actor/Anim"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsGeoE = col.operator(SM64_ExportGeolayoutArmature.bl_idname)
        propsGeoE = col.operator(SM64_ExportGeolayoutObject.bl_idname)

        if context.scene.fast64.sm64.exportType == "C":
            if not bpy.context.scene.ignoreTextureRestrictions and context.scene.saveTextures:
                if context.scene.geoCustomExport:
                    prop_split(col, context.scene, "geoTexDir", "Texture Include Path")
                col.prop(context.scene, "geoSeparateTextureDef")

            col.prop(context.scene, "geoCustomExport")
            if context.scene.geoCustomExport:
                col.prop(context.scene, "geoExportPath")
                prop_split(col, context.scene, "geoName", "Folder Name")
                prop_split(col, context.scene, "geoStructName", "Geolayout Name")
                customExportWarning(col)
            else:
                prop_split(col, context.scene, "geoExportHeaderType", "Export Type")
                if context.scene.geoExportHeaderType == "Actor":
                    prop_split(col, context.scene, "geoGroupName", "Group Name")

                    """
					if context.scene.geoName == 'marios_cap' or\
						context.scene.geoName == 'marios_metal_cap' or\
						context.scene.geoName == 'marios_wing_cap' or\
						context.scene.geoName == 'marios_winged_metal_cap':
						col.prop(context.scene, 'modifyOldGeo')
					elif context.scene.geoName == 'mario_cap':
						warningBox = col.box()
						warningBox.label(text = 'WARNING: DO NOT REPLACE THIS ACTOR.', icon = "QUESTION")
						warningBox.label(text = 'This contains geolayouts for all cap types.')
						warningBox.label(text = 'Use one of these geolayout names instead:')
						warningBox.label(text = ' - marios_cap')
						warningBox.label(text = ' - marios_metal_cap')
						warningBox.label(text = ' - marios_wing_cap')
						warningBox.label(text = ' - marios_winged_metal_cap')

					if context.scene.geoName == 'koopa_with_shell' or\
						context.scene.geoName == 'koopa_without_shell':
						col.prop(context.scene, 'modifyOldGeo')
					elif context.scene.geoName == 'koopa':
						warningBox = col.box()
						warningBox.label(text = 'WARNING: DO NOT REPLACE THIS ACTOR.', icon = "QUESTION")
						warningBox.label(text = 'This contains geolayouts for both koopa with and without shell.')
						warningBox.label(text = 'Use one of these geolayout names instead:')
						warningBox.label(text = ' - koopa_with_shell')
						warningBox.label(text = ' - koopa_without_shell')

					if context.scene.geoName == 'black_bobomb' or\
						context.scene.geoName == 'bobomb_buddy':
						col.prop(context.scene, 'modifyOldGeo')
					elif context.scene.geoName == 'bobomb':
						warningBox = col.box()
						warningBox.label(text = 'WARNING: DO NOT REPLACE THIS ACTOR.', icon = "QUESTION")
						warningBox.label(text = 'This contains geolayouts for both red and black bobombs.')
						warningBox.label(text = 'Also note that this contains a display list used in bowling_ball.')
						warningBox.label(text = 'Use one of these geolayout names instead:')
						warningBox.label(text = ' - black_bobomb')
						warningBox.label(text = ' - bobomb_buddy')

					if context.scene.geoName == 'purple_marble':
						col.prop(context.scene, 'modifyOldGeo')
					elif context.scene.geoName == 'bubble':
						warningBox = col.box()
						warningBox.label(text = 'WARNING: SECONDARY GEOLAYOUTS.', icon = "QUESTION")
						warningBox.label(text = 'If you replace this you must also replace purple_marble.')
						warningBox.label(text = 'Otherwise you will get a compilation error.')
					"""

                elif context.scene.geoExportHeaderType == "Level":
                    prop_split(col, context.scene, "geoLevelOption", "Level")
                    if context.scene.geoLevelOption == "custom":
                        prop_split(col, context.scene, "geoLevelName", "Level Name")
                prop_split(col, context.scene, "geoName", "Folder Name")
                prop_split(col, context.scene, "geoStructName", "Geolayout Name")
                if context.scene.geoExportHeaderType == "Actor":
                    if context.scene.geoName == "star":
                        col.prop(context.scene, "replaceStarRefs")
                    if context.scene.geoName == "transparent_star":
                        col.prop(context.scene, "replaceTransparentStarRefs")
                    if context.scene.geoName == "marios_cap":
                        col.prop(context.scene, "replaceCapRefs")
                infoBox = col.box()
                infoBox.label(text="If a geolayout file contains multiple actors,")
                infoBox.label(text="all other actors must also be replaced (with unique folder names)")
                infoBox.label(text="to prevent compilation errors.")
                decompFolderMessage(col)
                writeBox = makeWriteInfoBox(col)
                writeBoxExportType(
                    writeBox,
                    context.scene.geoExportHeaderType,
                    context.scene.geoName,
                    context.scene.geoLevelName,
                    context.scene.geoLevelOption,
                )

            # extendedRAMLabel(col)
        elif context.scene.fast64.sm64.exportType == "Insertable Binary":
            col.prop(context.scene, "geoInsertableBinaryPath")
        else:
            prop_split(col, context.scene, "geoExportStart", "Start Address")
            prop_split(col, context.scene, "geoExportEnd", "End Address")

            col.prop(context.scene, "geoUseBank0")
            if context.scene.geoUseBank0:
                prop_split(col, context.scene, "geoRAMAddr", "RAM Address")
            else:
                col.prop(context.scene, "levelGeoExport")

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

    bpy.types.Scene.levelGeoExport = bpy.props.EnumProperty(items=level_enums, name="Level", default="HMC")
    bpy.types.Scene.geoExportStart = bpy.props.StringProperty(name="Start", default="11D8930")
    bpy.types.Scene.geoExportEnd = bpy.props.StringProperty(name="End", default="11FFF00")

    bpy.types.Scene.overwriteModelLoad = bpy.props.BoolProperty(name="Modify level script", default=True)
    bpy.types.Scene.modelLoadLevelScriptCmd = bpy.props.StringProperty(
        name="Level script model load command", default="2ABCE0"
    )
    bpy.types.Scene.modelID = bpy.props.StringProperty(name="Model ID", default="1")

    bpy.types.Scene.textDumpGeo = bpy.props.BoolProperty(name="Dump geolayout as text", default=False)
    bpy.types.Scene.textDumpGeoPath = bpy.props.StringProperty(name="Text Dump Path", subtype="FILE_PATH")
    bpy.types.Scene.geoExportPath = bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    bpy.types.Scene.geoUseBank0 = bpy.props.BoolProperty(name="Use Bank 0")
    bpy.types.Scene.geoRAMAddr = bpy.props.StringProperty(name="RAM Address", default="80000000")
    bpy.types.Scene.geoTexDir = bpy.props.StringProperty(name="Include Path", default="actors/mario/")
    bpy.types.Scene.geoSeparateTextureDef = bpy.props.BoolProperty(name="Save texture.inc.c separately")
    bpy.types.Scene.geoInsertableBinaryPath = bpy.props.StringProperty(name="Filepath", subtype="FILE_PATH")
    bpy.types.Scene.geoIsSegPtr = bpy.props.BoolProperty(name="Is Segmented Address")
    bpy.types.Scene.geoName = bpy.props.StringProperty(name="Directory Name", default="mario")
    bpy.types.Scene.geoGroupName = bpy.props.StringProperty(name="Name", default="group0")
    bpy.types.Scene.geoExportHeaderType = bpy.props.EnumProperty(
        name="Header Export", items=enumExportHeaderType, default="Actor"
    )
    bpy.types.Scene.geoCustomExport = bpy.props.BoolProperty(name="Custom Export Path")
    bpy.types.Scene.geoLevelName = bpy.props.StringProperty(name="Level", default="bob")
    bpy.types.Scene.geoLevelOption = bpy.props.EnumProperty(items=enumLevelNames, name="Level", default="bob")
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
    bpy.types.Scene.geoStructName = bpy.props.StringProperty(name="Geolayout Name", default="mario_geo")


def sm64_geo_writer_unregister():
    for cls in reversed(sm64_geo_writer_classes):
        unregister_class(cls)

    del bpy.types.Scene.levelGeoExport
    del bpy.types.Scene.geoExportStart
    del bpy.types.Scene.geoExportEnd
    del bpy.types.Scene.overwriteModelLoad
    del bpy.types.Scene.modelLoadLevelScriptCmd
    del bpy.types.Scene.modelID
    del bpy.types.Scene.textDumpGeo
    del bpy.types.Scene.textDumpGeoPath
    del bpy.types.Scene.geoExportPath
    del bpy.types.Scene.geoUseBank0
    del bpy.types.Scene.geoRAMAddr
    del bpy.types.Scene.geoTexDir
    del bpy.types.Scene.geoSeparateTextureDef
    del bpy.types.Scene.geoInsertableBinaryPath
    del bpy.types.Scene.geoIsSegPtr
    del bpy.types.Scene.geoName
    del bpy.types.Scene.geoGroupName
    del bpy.types.Scene.geoExportHeaderType
    del bpy.types.Scene.geoCustomExport
    del bpy.types.Scene.geoLevelName
    del bpy.types.Scene.geoLevelOption
    del bpy.types.Scene.replaceStarRefs
    del bpy.types.Scene.replaceTransparentStarRefs
    del bpy.types.Scene.replaceCapRefs
    del bpy.types.Scene.modifyOldGeo
    del bpy.types.Scene.geoStructName
