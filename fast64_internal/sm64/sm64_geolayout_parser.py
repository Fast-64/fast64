import bpy, mathutils, math, bmesh, copy
from bpy.utils import register_class, unregister_class
from ..f3d.f3d_parser import createBlankMaterial, parseF3DBinary
from ..panels import SM64_Panel, sm64GoalImport
from .sm64_level_parser import parseLevelAtPointer
from .sm64_constants import level_pointers, level_enums
from .sm64_geolayout_bone import enumShadowType
from .sm64_geolayout_constants import getGeoLayoutCmdLength, nodeGroupCmds, GEO_BRANCH_STORE

from ..utility import (
    PluginError,
    decodeSegmentedAddr,
    raisePluginError,
    bytesToHexClean,
    bitMask,
    readVectorFromShorts,
    findStartBones,
    readEulerVectorFromShorts,
    readFloatFromShort,
    checkExpanded,
    doRotation,
    prop_split,
    sm64BoneUp,
    geoNodeRotateOrder,
)

from .sm64_geolayout_utility import (
    createBoneGroups,
    createBoneLayerMask,
    getBoneGroupIndex,
    addBoneToGroup,
    boneLayers,
)

from .sm64_geolayout_classes import (
    GEO_NODE_CLOSE,
    GEO_END,
    GEO_BRANCH,
    GEO_RETURN,
    GEO_NODE_OPEN,
    GEO_START,
    GEO_SWITCH,
    GEO_TRANSLATE_ROTATE,
    GEO_TRANSLATE,
    GEO_ROTATE,
    GEO_LOAD_DL_W_OFFSET,
    GEO_BILLBOARD,
    GEO_START_W_SHADOW,
    GEO_CALL_ASM,
    GEO_HELD_OBJECT,
    GEO_SCALE,
    GEO_START_W_RENDERAREA,
    GEO_LOAD_DL,
)


blender_modes = {"OBJECT", "BONE"}

# This geolayout parser is designed to rip armature / model.
# It will only handle transform/mesh related commands.
# For switch cases, only the first option will be chosen.


def parseGeoLayout(
    romfile,
    startAddress,
    scene,
    segmentData,
    convertTransformMatrix,
    useArmature,
    ignoreSwitch,
    shadeSmooth,
    f3dType,
    isHWv1,
):
    currentAddress = startAddress
    romfile.seek(currentAddress)

    # Create new skinned mesh
    # bpy.ops.object.mode_set(mode = 'OBJECT')
    mesh = bpy.data.meshes.new("skinnned-mesh")
    obj = bpy.data.objects.new("skinned", mesh)
    scene.collection.objects.link(obj)
    createBlankMaterial(obj)

    bMesh = bmesh.new()
    bMesh.from_mesh(mesh)

    # Create new armature
    if useArmature:
        armature = bpy.data.armatures.new("Armature")
        armatureObj = bpy.data.objects.new("ArmatureObj", armature)
        armatureObj.show_in_front = True
        armature.show_names = True

        bpy.context.scene.collection.objects.link(armatureObj)
        bpy.context.view_layer.objects.active = armatureObj
        bpy.ops.object.mode_set(mode="EDIT")
        createBoneGroups(armatureObj)
    else:
        armatureObj = None

    # Parse geolayout
    # Pretend that command starts with an 0x04
    currentAddress, armatureMeshGroups = parseNode(
        romfile,
        startAddress,
        currentAddress - 4,
        [0x04, 0x00],
        [currentAddress],
        convertTransformMatrix.to_4x4(),
        bMesh,
        obj,
        armatureObj,
        None,
        ignoreSwitch,
        False,
        0,
        0,
        [None] * 16 * 16,
        f3dType,
        isHWv1,
        segmentData=segmentData,
    )

    armatureMeshGroups.insert(0, (armatureObj, bMesh, obj))

    for i in range(len(armatureMeshGroups)):
        listObj = armatureMeshGroups[i][2]
        listBMesh = armatureMeshGroups[i][1]
        listBMesh.to_mesh(listObj.data)
        listBMesh.free()
        listObj.data.update()

        if shadeSmooth:
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
            listObj.select_set(True)
            bpy.ops.object.shade_smooth()

    # Dont remove doubles here, as importing geolayout all at once results
    # in some overlapping verts from different display lists.
    # bmesh.ops.remove_doubles(bMesh, verts = bMesh.verts, dist = 0.000001)

    if useArmature:
        # Set bone rotation mode.
        for bone in armatureObj.pose.bones:
            bone.rotation_mode = "XYZ"

        for i in range(len(armatureMeshGroups)):
            obj = armatureMeshGroups[i][2]
            switchArmatureObj = armatureMeshGroups[i][0]
            # Apply mesh to armature.
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            switchArmatureObj.select_set(True)
            bpy.context.view_layer.objects.active = switchArmatureObj
            bpy.ops.object.parent_set(type="ARMATURE")
            switchArmatureObj.matrix_world = switchArmatureObj.matrix_world @ mathutils.Matrix.Translation(
                mathutils.Vector((3 * i, 0, 0))
            )

        # Make Mario face forward.
        # bpy.ops.object.select_all(action = 'DESELECT')
        # armatureObj.select_set(True)
        # bpy.ops.transform.rotate(value = math.radians(-90), orient_axis = 'X')
        # bpy.ops.object.transform_apply()

    if useArmature:
        armatureObj.data.layers[1] = True

    """
	if useMetarig:
		metaBones = [bone for bone in armatureObj.data.bones if \
			bone.layers[boneLayers['meta']] or bone.layers[boneLayers['visual']]]
		for bone in metaBones:
			addBoneToGroup(armatureObj, bone.name, 'Ignore')
	"""
    return armatureMeshGroups, armatureObj


# Every node is passed in the address of its OWN command.
# Every node returns the address AFTER the end of its processing extent.
# Make sure to NOT create blender objects if the node is being ignored.
def parseNode(
    romfile,
    geoStartAddress,
    currentAddress,
    currentCmd,
    jumps,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreSwitch,
    ignoreNode,
    switchLevel,
    switchCount,
    vertexBuffer,
    f3dType,
    isHWv1,
    singleChild=False,
    endCmd=GEO_NODE_CLOSE,
    segmentData=None,
):
    print("NODE " + hex(currentAddress))
    currentTransform = copy.deepcopy(currentTransform)
    originalTransform = copy.deepcopy(currentTransform)
    currentAddress += getGeoLayoutCmdLength(*currentCmd)
    romfile.seek(currentAddress)
    currentCmd = romfile.read(2)
    armatureMeshGroups = []

    # True if at least one complete node processed.
    # This is used for switch cases.
    nodeProcessed = False

    # True when a complete node group is processed.
    # Certain commands like 0x13 will be grouped with a proceeding 0x4 commmand.
    # However, they will stand individually if this is not the case.
    # This distinction is important when handling switch cases.
    completeNodeProcessed = False

    # In the case of branches in switches we must treat the branch as one option,
    # not just the first node that is being branched to.
    # We cannot treat a branch as a node because some branches don't return.
    singleChildStack = [singleChild]
    switchActive = False
    localSwitchCount = 0

    # a 0x13 command creates a bone, but we only use it as a parent if
    # a 0x4 command follows. If another 0x13 command follows, we don't use it.
    nextParentBoneName = parentBoneName
    nextParentTransform = copy.deepcopy(currentTransform)
    nodeIndex = [0]
    while currentCmd[0] is not endCmd and currentCmd[0] is not GEO_END:
        isSwitchOption = singleChildStack[-1] and nodeProcessed and completeNodeProcessed

        # Create a separate sub-armature for switch options.
        if isSwitchOption:
            switchCount += 1
            localSwitchCount += 1
            if ignoreSwitch:
                ignoreNode = True
            if not ignoreNode:
                parentBoneName, armatureMeshTuple, currentTransform, nextParentTransform = createSwitchOption(
                    armatureObj,
                    parentBoneName,
                    format(nodeIndex[-1], "03") + "-switch_option",
                    currentTransform,
                    nextParentTransform,
                    switchLevel,
                    switchCount,
                )
                armatureMeshGroups.append(armatureMeshTuple)
                obj = armatureMeshTuple[2]
                bMesh = armatureMeshTuple[1]
                nextParentBoneName = parentBoneName
                armatureObj = armatureMeshTuple[0]
            switchLevel = switchCount

        if currentCmd[0] == GEO_BRANCH_STORE and not ignoreNode:  # 0x00
            currentAddress = parseBranchStore(romfile, currentCmd, currentAddress, jumps, segmentData=segmentData)
            singleChildStack.append(False)
            nodeIndex.append(0)
        elif currentCmd[0] == GEO_BRANCH and not ignoreNode:  # 0x02
            currentAddress = parseBranch(romfile, currentCmd, currentAddress, jumps, segmentData=segmentData)
            singleChildStack.append(False)
            nodeIndex.append(0)

        elif currentCmd[0] == GEO_RETURN and not ignoreNode:  # 0x03
            currentAddress = parseReturn(currentCmd, currentAddress, jumps)
            singleChildStack = singleChildStack[:-1]
            nodeIndex = nodeIndex[:-1]

        elif currentCmd[0] == GEO_NODE_OPEN:  # 0x04
            # print(str(switchCount) + " - " + str(localSwitchCount) + " - " + \
            # 	str(switchLevel))
            currentAddress, newArmatureMeshGroups = parseNode(
                romfile,
                geoStartAddress,
                currentAddress,
                currentCmd,
                jumps,
                nextParentTransform,
                bMesh,
                obj,
                armatureObj,
                nextParentBoneName,
                ignoreSwitch,
                ignoreNode,
                switchLevel,
                switchCount,
                vertexBuffer,
                f3dType,
                isHWv1,
                singleChild=switchActive,
                segmentData=segmentData,
            )
            armatureMeshGroups.extend(newArmatureMeshGroups)
            switchActive = False
            nextParentTransform = copy.deepcopy(currentTransform)

        elif currentCmd[0] == GEO_START:  # 0x0B
            currentAddress, nextParentBoneName, nextParentTransform = parseStart(
                romfile,
                currentAddress,
                currentTransform,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
            )

        elif currentCmd[0] == GEO_SWITCH:  # 0x0E
            currentAddress, nextParentBoneName = parseSwitch(
                romfile,
                currentAddress,
                currentTransform,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
            )
            switchActive = True

        # We skip translate/rotate/scale nodes if before the first 0x13 node.
        # This allows us to import model animations without having to transform keyframes.
        elif currentCmd[0] == GEO_TRANSLATE_ROTATE:  # 0x10
            currentAddress, nextParentBoneName, nextParentTransform = parseTranslateRotate(
                romfile,
                currentAddress,
                currentCmd,
                currentTransform,
                bMesh,
                obj,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
                vertexBuffer,
                f3dType,
                isHWv1,
            )

        elif currentCmd[0] == GEO_TRANSLATE:  # 0x11
            currentAddress, nextParentBoneName, nextParentTransform = parseTranslate(
                romfile,
                currentAddress,
                currentCmd,
                currentTransform,
                bMesh,
                obj,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
                vertexBuffer,
                f3dType,
                isHWv1,
            )

        elif currentCmd[0] == GEO_ROTATE:  # 0x12
            currentAddress, nextParentBoneName, nextParentTransform = parseRotate(
                romfile,
                currentAddress,
                currentCmd,
                currentTransform,
                bMesh,
                obj,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
                vertexBuffer,
                f3dType,
                isHWv1,
            )

        elif currentCmd[0] == GEO_LOAD_DL_W_OFFSET:  # 0x13
            currentAddress, nextParentBoneName, nextParentTransform = parseDLWithOffset(
                romfile,
                currentAddress,
                currentTransform,
                bMesh,
                obj,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                currentCmd,
                segmentData,
                vertexBuffer,
                f3dType,
                isHWv1,
            )

        elif currentCmd[0] == GEO_BILLBOARD:  # 0x14
            currentAddress, nextParentBoneName, nextParentTransform = parseBillboard(
                romfile,
                currentAddress,
                currentCmd,
                currentTransform,
                bMesh,
                obj,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
                vertexBuffer,
                f3dType,
                isHWv1,
            )

        elif currentCmd[0] == GEO_LOAD_DL:  # 0x15
            currentAddress = parseDL(
                romfile,
                currentAddress,
                currentTransform,
                bMesh,
                obj,
                armatureObj,
                parentBoneName,
                ignoreNode,
                currentCmd,
                nodeIndex[-1],
                segmentData,
                vertexBuffer,
                f3dType,
                isHWv1,
            )

        elif currentCmd[0] == GEO_START_W_SHADOW:  # 0x16
            currentAddress, nextParentBoneName, nextParentTransform = parseShadow(
                romfile,
                currentAddress,
                currentTransform,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
            )

        elif currentCmd[0] == GEO_CALL_ASM:  # 0x18
            currentAddress = parseFunction(
                romfile,
                currentAddress,
                currentTransform,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
            )

        elif currentCmd[0] == GEO_HELD_OBJECT:  # 0x1C
            currentAddress, nextParentTransform = parseHeldObject(
                romfile,
                currentAddress,
                currentTransform,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
            )

        elif currentCmd[0] == GEO_SCALE:  # 0x1D
            currentAddress, nextParentBoneName, nextParentTransform = parseScale(
                romfile,
                currentAddress,
                currentCmd,
                currentTransform,
                bMesh,
                obj,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
                vertexBuffer,
                f3dType,
                isHWv1,
            )

        elif currentCmd[0] == GEO_START_W_RENDERAREA:  # 0x20
            currentAddress, nextParentBoneName, nextParentTransform = parseStartWithRenderArea(
                romfile,
                currentAddress,
                currentTransform,
                armatureObj,
                parentBoneName,
                ignoreNode,
                nodeIndex[-1],
                segmentData,
            )

        else:
            currentAddress += getGeoLayoutCmdLength(*currentCmd)
            print("Unhandled command: " + hex(currentCmd[0]))

        nodeIndex[-1] += 1

        romfile.seek(currentAddress)
        previousCmdType = currentCmd[0]
        currentCmd = romfile.read(2)

        if previousCmdType not in nodeGroupCmds or currentCmd[0] != GEO_NODE_OPEN:
            completeNodeProcessed = True
            nodeProcessed = True
        else:
            completeNodeProcessed = False

    if currentCmd[0] == GEO_END:
        currentAddress = jumps.pop()
    else:
        currentAddress += getGeoLayoutCmdLength(*currentCmd)
    return currentAddress, armatureMeshGroups


def generateMetarig(armatureObj):
    startBones = findStartBones(armatureObj)
    createBoneGroups(armatureObj)
    for boneName in startBones:
        traverseArmatureForMetarig(armatureObj, boneName, None)
    armatureObj.data.layers = createBoneLayerMask([boneLayers["visual"]])
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def traverseArmatureForMetarig(armatureObj, boneName, parentName):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    poseBone = armatureObj.pose.bones[boneName]
    if poseBone.bone_group is None:
        processBoneMeta(armatureObj, boneName, parentName)
    elif poseBone.bone_group.name == "Ignore":
        return

    poseBone = armatureObj.pose.bones[boneName]
    nextParentName = boneName if poseBone.bone_group is None else parentName
    childrenNames = [child.name for child in poseBone.children]
    for childName in childrenNames:
        traverseArmatureForMetarig(armatureObj, childName, nextParentName)


def processBoneMeta(armatureObj, boneName, parentName):
    bpy.ops.object.mode_set(mode="EDIT")
    bone = armatureObj.data.edit_bones[boneName]

    # create meta bone, which the actual bone copies the rotation of
    metabone = armatureObj.data.edit_bones.new("meta_" + boneName)
    metabone.use_connect = False
    metabone.head = bone.head
    metabone.tail = bone.tail
    metabone.roll = bone.roll

    # create visual bone, which visually connect parent bone to child
    visualBone = armatureObj.data.edit_bones.new("vis_" + boneName)
    visualBone.use_connect = False
    visualBone.head = bone.head
    visualBone.tail = bone.head + sm64BoneUp * 0.2
    metabone.parent = visualBone

    metaboneName = metabone.name
    visualBoneName = visualBone.name

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    poseBone = armatureObj.pose.bones[boneName]
    metabonePose = armatureObj.pose.bones[metaboneName]
    visualBonePose = armatureObj.pose.bones[visualBoneName]

    metabone = armatureObj.data.bones[metaboneName]
    visualBone = armatureObj.data.bones[visualBoneName]
    metabone.geo_cmd = "Ignore"
    visualBone.geo_cmd = "Ignore"

    # apply rotation constraint
    constraint = poseBone.constraints.new(type="COPY_ROTATION")
    constraint.target = armatureObj
    constraint.subtarget = metaboneName

    translateConstraint = poseBone.constraints.new(type="COPY_LOCATION")
    translateConstraint.target = armatureObj
    translateConstraint.subtarget = metaboneName

    metabone.layers = createBoneLayerMask([boneLayers["meta"]])
    metabone.use_deform = False
    metabonePose.lock_rotation = (True, True, True)

    visualBone.layers = createBoneLayerMask([boneLayers["visual"]])
    visualBone.use_deform = False

    metabonePose.bone_group_index = getBoneGroupIndex(armatureObj, "Ignore")
    visualBonePose.bone_group_index = getBoneGroupIndex(armatureObj, "Ignore")

    bpy.ops.object.mode_set(mode="EDIT")
    metabone = armatureObj.data.edit_bones[metaboneName]
    visualBone = armatureObj.data.edit_bones[visualBoneName]

    if parentName is not None:
        parentVisualBone = armatureObj.data.edit_bones["vis_" + parentName]
        parentVisualBoneName = parentVisualBone.name
        visualChildren = [child for child in parentVisualBone.children if child.name[:5] != "meta_"]
        print(str(parentVisualBoneName) + " " + str([child.name for child in parentVisualBone.children]))
        if len(visualChildren) == 0:
            print("Zero children: " + str(visualBone.name))
            parentVisualBone.tail = visualBone.head
            if parentVisualBone.length < 0.00001:
                parentVisualBone.tail = parentVisualBone.head + sm64BoneUp * 0.1
            else:
                visualBone.use_connect = True
            visualBone.parent = parentVisualBone

        else:
            print("Some children: " + str(visualBone.name) + " " + str([child.name for child in visualChildren]))
            # If multiple children, make parent bone a "straight upward"
            # bone, then add "connection" bones to connect children to parent
            for child in visualChildren:
                # if parentVisualBone.vector.angle(sm64BoneUp, 1) > 0.0001:
                child.use_connect = False
            parentVisualBone.tail = parentVisualBone.head + sm64BoneUp * 0.2
            # createConnectBone(armatureObj, child.name, parentVisualBoneName)
            visualBone = armatureObj.data.edit_bones[visualBoneName]
            parentVisualBone = armatureObj.data.edit_bones[parentVisualBoneName]
            # createConnectBone(armatureObj, visualBone.name,
            # 	parentVisualBone.name)
            visualBone.use_connect = False
            visualBone.parent = parentVisualBone
    else:
        pass  # connect to root anim bone


def createConnectBone(armatureObj, childName, parentName):
    child = armatureObj.data.edit_bones[childName]
    parent = armatureObj.data.edit_bones[parentName]

    connectBone = armatureObj.data.edit_bones.new("connect_" + child.name)
    connectBoneName = connectBone.name
    connectBone.head = parent.head
    connectBone.use_connect = False
    connectBone.parent = parent
    connectBone.tail = child.head
    child.use_connect = False
    connectBone.use_deform = False
    child.parent = connectBone
    if (connectBone.head - connectBone.tail).length < 0.0001:
        connectBone.tail = connectBone.head + sm64BoneUp * 0.2
    else:
        child.use_connect = True

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    connectPoseBone = armatureObj.pose.bones[connectBoneName]
    connectBone = armatureObj.data.bones[connectBoneName]
    connectBone.layers = createBoneLayerMask([boneLayers["visual"]])
    connectPoseBone.bone_group_index = getBoneGroupIndex(armatureObj, "Ignore")
    connectPoseBone.lock_rotation = (True, True, True)
    bpy.ops.object.mode_set(mode="EDIT")


def createBone(armatureObj, parentBoneName, boneName, currentTransform, boneGroup, loadDL):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = armatureObj
    bpy.ops.object.mode_set(mode="EDIT")
    bone = armatureObj.data.edit_bones.new(boneName)
    bone.use_connect = False
    if parentBoneName is not None:
        bone.parent = armatureObj.data.edit_bones[parentBoneName]
    bone.head = currentTransform @ mathutils.Vector((0, 0, 0))
    bone.tail = bone.head + (
        currentTransform.to_quaternion() @ mathutils.Vector((0, 1, 0)) * (0.2 if boneGroup != "DisplayList" else 0.1)
    )

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
            bone.tail += currentTransform.to_quaternion() @ mathutils.Vector((0, 1, 0)) * 0.02

    boneName = bone.name
    addBoneToGroup(armatureObj, bone.name, boneGroup)
    bone = armatureObj.data.bones[boneName]
    bone.geo_cmd = boneGroup if boneGroup is not None else "DisplayListWithOffset"

    return boneName


def createSwitchOption(
    armatureObj, switchBoneName, boneName, currentTransform, nextParentTransform, switchLevel, switchCount
):
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    # bpy.context.view_layer.objects.active = armatureObj
    # bpy.ops.object.mode_set(mode="EDIT")
    # bone = armatureObj.data.edit_bones.new(boneName)
    # bone.use_connect = False

    # calculate transform
    translation = mathutils.Matrix.Translation(mathutils.Vector((0, 3 * (switchCount - switchLevel), 0)))
    translation = mathutils.Matrix.Translation((0, 0, 0))
    finalTransform = translation @ currentTransform
    finalNextParentTransform = translation @ nextParentTransform

    # create armature
    armature = bpy.data.armatures.new("Armature")
    switchArmature = bpy.data.objects.new("armature_" + boneName, armature)
    switchArmature.show_in_front = True
    armature.show_names = True

    bpy.context.scene.collection.objects.link(switchArmature)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    createBoneGroups(switchArmature)
    bpy.context.view_layer.objects.active = switchArmature
    # switchArmature.matrix_world = mathutils.Matrix.Translation(
    # 	finalTransform.to_translation())
    bpy.ops.object.mode_set(mode="EDIT")

    # create switch option bone
    bone = switchArmature.data.edit_bones.new(boneName)
    bone.use_connect = False
    bone.head = finalTransform @ mathutils.Vector((0, 0, 0))
    bone.tail = bone.head + currentTransform.to_quaternion() @ mathutils.Vector((0, 1, 0)) * 0.2

    boneName = bone.name
    bpy.ops.object.mode_set(mode="OBJECT")
    bone = switchArmature.data.bones[boneName]
    # poseBone = switchArmature.pose.bones[boneName]
    switchBone = armatureObj.data.bones[switchBoneName]

    # rotConstraint = poseBone.constraints.new(type = 'COPY_ROTATION')
    # rotConstraint.target = armatureObj
    # rotConstraint.subtarget = switchBone.name

    bone.geo_cmd = "SwitchOption"

    # switchOption = switchBone.switch_options.add()
    # switchOption.switchType = 'Mesh'
    # switchOption.optionArmature = switchArmature

    # Create new mesh as well
    mesh = bpy.data.meshes.new("skinnned-mesh")
    obj = bpy.data.objects.new("skinned", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = switchArmature.matrix_world
    # material = createF3DMat(obj)
    # material.node_tree.nodes['Case A 1'].inA = '1'
    # material.set_env = False

    bMesh = bmesh.new()
    bMesh.from_mesh(mesh)

    addBoneToGroup(switchArmature, boneName, "SwitchOption")

    return boneName, (switchArmature, bMesh, obj), finalTransform, finalNextParentTransform


def parseSwitch(
    romfile, currentAddress, currentTransform, armatureObj, parentBoneName, ignoreNode, nodeIndex, segmentData
):
    print("SWITCH " + hex(currentAddress))

    commandSize = 8

    if not ignoreNode:
        romfile.seek(currentAddress)
        command = romfile.read(commandSize)
        funcParam = int.from_bytes(command[2:4], "big", signed=True)
        switchFunc = bytesToHexClean(command[4:8])

        boneName = format(nodeIndex, "03") + "-switch"
        if armatureObj is not None:
            boneName = createBone(armatureObj, parentBoneName, boneName, currentTransform, "Switch", False)
            bone = armatureObj.data.bones[boneName]
            bone.geo_func = switchFunc
            bone.func_param = funcParam
    else:
        boneName = None

    currentAddress += commandSize
    return currentAddress, boneName


def parseDL(
    romfile,
    currentAddress,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreNode,
    currentCmd,
    nodeIndex,
    segmentData,
    vertexBuffer,
    f3dType,
    isHWv1,
):

    drawLayer = bitMask(currentCmd[1], 0, 4)

    romfile.seek(currentAddress)
    commandSize = 8
    command = romfile.read(commandSize)

    if not ignoreNode:
        boneName = handleNodeCommon(
            romfile,
            armatureObj,
            parentBoneName,
            currentTransform,
            True,
            command,
            segmentData,
            bMesh,
            obj,
            nodeIndex,
            "DisplayList",
            vertexBuffer,
            f3dType,
            isHWv1,
        )
        if armatureObj is not None:
            bone = armatureObj.data.bones[boneName]
            bone.draw_layer = str(drawLayer)

    currentAddress += commandSize
    return currentAddress


def parseDLWithOffset(
    romfile,
    currentAddress,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreNode,
    nodeIndex,
    currentCmd,
    segmentData,
    vertexBuffer,
    f3dType,
    isHWv1,
):
    print("DL_OFFSET " + hex(currentAddress))
    romfile.seek(currentAddress)

    command = romfile.read(getGeoLayoutCmdLength(*currentCmd))

    drawLayer = command[1]

    translationVector = readVectorFromShorts(command, 2)
    translation = mathutils.Matrix.Translation(mathutils.Vector(translationVector))
    finalTransform = currentTransform @ translation

    boneName = format(nodeIndex, "03") + "-offset"

    # Handle parent object and transformation
    # Note: Since we are storing the world transform for each node,
    # we must set the transforms in preorder traversal.
    segmentedAddr = command[8:12]
    hasMeshData = int.from_bytes(segmentedAddr, "big") != 0

    if not ignoreNode:
        if armatureObj is not None:
            # Create bone
            boneName = createBone(armatureObj, parentBoneName, boneName, finalTransform, None, hasMeshData)
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bone = armatureObj.data.bones[boneName]
            bone.draw_layer = str(drawLayer)
            armatureObj.data.bones[boneName].use_deform = hasMeshData
            bpy.ops.object.mode_set(mode="EDIT")

        # load mesh data
        if hasMeshData:
            displayListStartAddress = decodeSegmentedAddr(segmentedAddr, segmentData=segmentData)
            # print(displayListStartAddress)
            parseF3DBinary(
                romfile,
                displayListStartAddress,
                bpy.context.scene,
                bMesh,
                obj,
                finalTransform,
                boneName,
                segmentData,
                vertexBuffer,
            )

    # Handle child objects
    # Validate that next command is 04 (open node)
    currentAddress += getGeoLayoutCmdLength(*currentCmd)
    romfile.seek(currentAddress)  # DONT FORGET THIS, FIXES PARENTING BUG
    currentCmd = romfile.read(2)

    return currentAddress, boneName, finalTransform


def parseBranch(romfile, currentCmd, currentAddress, jumps, segmentData=None):
    print("BRANCH " + hex(currentAddress))
    romfile.seek(currentAddress)
    postJumpAddr = currentAddress + getGeoLayoutCmdLength(*currentCmd)
    currentCmd = romfile.read(getGeoLayoutCmdLength(*currentCmd))

    if currentCmd[1] == 1:
        jumps.append(postJumpAddr)
    currentAddress = decodeSegmentedAddr(currentCmd[4:8], segmentData=segmentData)

    return currentAddress


def parseBranchStore(romfile, currentCmd, currentAddress, jumps, segmentData=None):
    print("BRANCH AND STORE " + hex(currentAddress))
    romfile.seek(currentAddress)
    postJumpAddr = currentAddress + getGeoLayoutCmdLength(*currentCmd)
    currentCmd = romfile.read(getGeoLayoutCmdLength(*currentCmd))

    jumps.append(postJumpAddr)
    currentAddress = decodeSegmentedAddr(currentCmd[4:8], segmentData=segmentData)

    return currentAddress


def parseReturn(currentCmd, currentAddress, jumps):
    print("RETURN " + hex(currentAddress))
    currentAddress = jumps.pop()
    return currentAddress


# Create bone and load geometry
def handleNodeCommon(
    romfile,
    armatureObj,
    parentBoneName,
    finalTransform,
    loadDL,
    command,
    segmentData,
    bMesh,
    obj,
    nodeIndex,
    boneGroupName,
    vertexBuffer,
    f3dType,
    isHWv1,
):

    boneName = format(nodeIndex, "03") + "-" + boneGroupName.lower()

    if armatureObj is not None:
        # Create bone
        boneName = createBone(armatureObj, parentBoneName, boneName, finalTransform, boneGroupName, loadDL)

    if loadDL:
        segmentedAddr = command[-4:]
        hasMeshData = int.from_bytes(segmentedAddr, "big") != 0
        if hasMeshData:
            startAddress = decodeSegmentedAddr(segmentedAddr, segmentData)
            parseF3DBinary(
                romfile,
                startAddress,
                bpy.context.scene,
                bMesh,
                obj,
                finalTransform,
                boneName,
                segmentData,
                vertexBuffer,
            )
    elif armatureObj is not None:
        armatureObj.data.bones[boneName].use_deform = False
    return boneName


def parseScale(
    romfile,
    currentAddress,
    currentCmd,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreNode,
    nodeIndex,
    segmentData,
    vertexBuffer,
    f3dType,
    isHWv1,
):
    print("SCALE " + hex(currentAddress))

    loadDL = bitMask(currentCmd[1], 7, 1)
    drawLayer = bitMask(currentCmd[1], 0, 4)

    romfile.seek(currentAddress)
    commandSize = 8 + (4 if loadDL else 0)
    command = romfile.read(commandSize)

    scale = int.from_bytes(command[4:8], "big") / 0x10000
    # finalTransform = currentTransform @ mathutils.Matrix.Scale(scale, 4)
    finalTransform = currentTransform  # Don't apply to armature

    if not ignoreNode:
        boneName = handleNodeCommon(
            romfile,
            armatureObj,
            parentBoneName,
            finalTransform,
            loadDL,
            command,
            segmentData,
            bMesh,
            obj,
            nodeIndex,
            "Scale",
            vertexBuffer,
            f3dType,
            isHWv1,
        )
        if armatureObj is not None:
            bone = armatureObj.data.bones[boneName]
            bone.draw_layer = str(drawLayer)
            bone.geo_scale = scale
    else:
        boneName = None

    currentAddress += commandSize
    return (currentAddress, boneName, finalTransform)


def parseTranslateRotate(
    romfile,
    currentAddress,
    currentCmd,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreNode,
    nodeIndex,
    segmentData,
    vertexBuffer,
    f3dType,
    isHWv1,
):
    print("TRANSLATE_ROTATE " + hex(currentAddress))

    loadDL = bitMask(currentCmd[1], 7, 1)
    fieldLayout = bitMask(currentCmd[1], 4, 3)
    drawLayer = bitMask(currentCmd[1], 0, 4)

    if fieldLayout == 0:
        commandSize = 16
    elif fieldLayout == 1 or fieldLayout == 2:
        commandSize = 8
    else:
        commandSize = 4
    if loadDL:
        commandSize += 4

    romfile.seek(currentAddress)
    command = romfile.read(commandSize)

    if fieldLayout == 0:
        pos = readVectorFromShorts(command, 4)
        rot = readEulerVectorFromShorts(command, 10)

        rotation = mathutils.Euler(rot, geoNodeRotateOrder).to_matrix().to_4x4()
        translation = mathutils.Matrix.Translation(mathutils.Vector(pos))
        finalTransform = currentTransform @ translation @ rotation

    elif fieldLayout == 1:
        pos = readVectorFromShorts(command, 2)
        translation = mathutils.Matrix.Translation(mathutils.Vector(pos))
        finalTransform = currentTransform @ translation

    elif fieldLayout == 2:
        rot = readEulerVectorFromShorts(command, 2)
        rotation = mathutils.Euler(rot, geoNodeRotateOrder).to_matrix().to_4x4()
        finalTransform = currentTransform @ rotation

    else:
        yRot = readFloatFromShort(command, 2)
        rotation = mathutils.Euler((0, yRot, 0), geoNodeRotateOrder).to_matrix().to_4x4()
        finalTransform = currentTransform @ rotation

    if not ignoreNode:
        boneName = handleNodeCommon(
            romfile,
            armatureObj,
            parentBoneName,
            finalTransform,
            loadDL,
            command,
            segmentData,
            bMesh,
            obj,
            nodeIndex,
            "TranslateRotate",
            vertexBuffer,
            f3dType,
            isHWv1,
        )
        if armatureObj is not None:
            bone = armatureObj.data.bones[boneName]
            bone.draw_layer = str(drawLayer)

            # Rotate Y complicates exporting code, so we treat it as Rotate.
            if fieldLayout == 3:
                fieldLayout = 2
            bone.field_layout = str(fieldLayout)
    else:
        boneName = None

    currentAddress += commandSize

    return (currentAddress, boneName, finalTransform)


def parseTranslate(
    romfile,
    currentAddress,
    currentCmd,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreNode,
    nodeIndex,
    segmentData,
    vertexBuffer,
    f3dType,
    isHWv1,
):
    print("TRANSLATE " + hex(currentAddress))

    loadDL = bitMask(currentCmd[1], 7, 1)
    drawLayer = bitMask(currentCmd[1], 0, 4)

    if loadDL:
        commandSize = 12
    else:
        commandSize = 8

    romfile.seek(currentAddress)
    command = romfile.read(commandSize)

    pos = readVectorFromShorts(command, 2)
    translation = mathutils.Matrix.Translation(mathutils.Vector(pos))
    finalTransform = currentTransform @ translation

    if not ignoreNode:
        boneName = handleNodeCommon(
            romfile,
            armatureObj,
            parentBoneName,
            finalTransform,
            loadDL,
            command,
            segmentData,
            bMesh,
            obj,
            nodeIndex,
            "Translate",
            vertexBuffer,
            f3dType,
            isHWv1,
        )
        if armatureObj is not None:
            bone = armatureObj.data.bones[boneName]
            bone.draw_layer = str(drawLayer)
    else:
        boneName = None

    currentAddress += commandSize

    return (currentAddress, boneName, finalTransform)


def parseRotate(
    romfile,
    currentAddress,
    currentCmd,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreNode,
    nodeIndex,
    segmentData,
    vertexBuffer,
    f3dType,
    isHWv1,
):
    print("ROTATE " + hex(currentAddress))

    loadDL = bitMask(currentCmd[1], 7, 1)
    drawLayer = bitMask(currentCmd[1], 0, 4)

    if loadDL:
        commandSize = 12
    else:
        commandSize = 8

    romfile.seek(currentAddress)
    command = romfile.read(commandSize)

    rot = readEulerVectorFromShorts(command, 2)
    rotation = mathutils.Euler(rot, geoNodeRotateOrder).to_matrix().to_4x4()
    finalTransform = currentTransform @ rotation

    if not ignoreNode:
        boneName = handleNodeCommon(
            romfile,
            armatureObj,
            parentBoneName,
            finalTransform,
            loadDL,
            command,
            segmentData,
            bMesh,
            obj,
            nodeIndex,
            "Rotate",
            vertexBuffer,
            f3dType,
            isHWv1,
        )
        if armatureObj is not None:
            bone = armatureObj.data.bones[boneName]
            bone.draw_layer = str(drawLayer)
    else:
        boneName = None

    currentAddress += commandSize
    return (currentAddress, boneName, finalTransform)


def parseBillboard(
    romfile,
    currentAddress,
    currentCmd,
    currentTransform,
    bMesh,
    obj,
    armatureObj,
    parentBoneName,
    ignoreNode,
    nodeIndex,
    segmentData,
    vertexBuffer,
    f3dType,
    isHWv1,
):
    print("BILLBOARD " + hex(currentAddress))

    loadDL = bitMask(currentCmd[1], 7, 1)
    drawLayer = bitMask(currentCmd[1], 0, 4)

    if loadDL:
        commandSize = 12
    else:
        commandSize = 8

    romfile.seek(currentAddress)
    command = romfile.read(commandSize)

    pos = readVectorFromShorts(command, 2)
    translation = mathutils.Matrix.Translation(mathutils.Vector(pos))
    finalTransform = currentTransform @ translation

    if not ignoreNode:
        boneName = handleNodeCommon(
            romfile,
            armatureObj,
            parentBoneName,
            finalTransform,
            loadDL,
            command,
            segmentData,
            bMesh,
            obj,
            nodeIndex,
            "Billboard",
            vertexBuffer,
            f3dType,
            isHWv1,
        )
        if armatureObj is not None:
            bone = armatureObj.data.bones[boneName]
            bone.draw_layer = str(drawLayer)
    else:
        boneName = None

    currentAddress += commandSize

    return (currentAddress, boneName, finalTransform)


def parseShadow(
    romfile, currentAddress, currentTransform, armatureObj, parentBoneName, ignoreNode, nodeIndex, segmentData
):
    print("SHADOW " + hex(currentAddress))
    commandSize = 8

    romfile.seek(currentAddress)
    command = romfile.read(commandSize)
    shadowType = int.from_bytes(command[2:4], "big")
    if str(shadowType) not in enumShadowType:
        if shadowType > 12 and shadowType < 50:  # Square Shadow
            shadowType = 12
        elif shadowType > 50 and shadowType < 99:  # Rectangle Shadow
            shadowType = 50
        else:  # Invalid shadow
            shadowType = 0
    shadowSolidity = int.from_bytes(command[4:6], "big")
    shadowScale = int.from_bytes(command[6:8], "big")

    if not ignoreNode:
        boneName = format(nodeIndex, "03") + "-shadow"
        if armatureObj is not None:
            boneName = createBone(armatureObj, parentBoneName, boneName, currentTransform, "Shadow", False)
            bone = armatureObj.data.bones[boneName]
            bone.shadow_type = str(shadowType)
            bone.shadow_solidity = shadowSolidity / 0xFF
            bone.shadow_scale = shadowScale
    else:
        boneName = None

    currentAddress += commandSize
    return currentAddress, boneName, copy.deepcopy(currentTransform)


def parseStart(
    romfile, currentAddress, currentTransform, armatureObj, parentBoneName, ignoreNode, nodeIndex, segmentData
):
    print("START " + hex(currentAddress))

    commandSize = 4
    romfile.seek(currentAddress)

    if not ignoreNode:
        boneName = format(nodeIndex, "03") + "-start"
        if armatureObj is not None:
            boneName = createBone(armatureObj, parentBoneName, boneName, currentTransform, "Start", False)
    else:
        boneName = None

    currentAddress += commandSize
    return currentAddress, boneName, copy.deepcopy(currentTransform)


def parseStartWithRenderArea(
    romfile, currentAddress, currentTransform, armatureObj, parentBoneName, ignoreNode, nodeIndex, segmentData
):
    print("START W/ RENDER AREA" + hex(currentAddress))

    commandSize = 4
    romfile.seek(currentAddress)
    command = romfile.read(commandSize)
    cullingRadius = int.from_bytes(command[2:4], "big") / bpy.context.scene.blenderToSM64Scale

    if not ignoreNode:
        boneName = format(nodeIndex, "03") + "-start_render_area"
        if armatureObj is not None:
            boneName = createBone(armatureObj, parentBoneName, boneName, currentTransform, "StartRenderArea", False)
            bone = armatureObj.data.bones[boneName]
            bone.geo_cmd = "StartRenderArea"
            bone.culling_radius = cullingRadius
    else:
        boneName = None

    currentAddress += commandSize
    return currentAddress, boneName, copy.deepcopy(currentTransform)


def parseFunction(
    romfile, currentAddress, currentTransform, armatureObj, parentBoneName, ignoreNode, nodeIndex, segmentData
):
    print("Function " + hex(currentAddress))

    commandSize = 8

    romfile.seek(currentAddress)
    command = romfile.read(commandSize)
    asmParam = int.from_bytes(command[2:4], "big", signed=True)
    asmFunc = bytesToHexClean(command[4:8])

    boneName = format(nodeIndex, "03") + "-asm"
    if armatureObj is not None and not ignoreNode:
        boneName = createBone(armatureObj, parentBoneName, boneName, currentTransform, "Function", False)
        bone = armatureObj.data.bones[boneName]
        bone.geo_func = asmFunc
        bone.func_param = asmParam

    currentAddress += commandSize
    return currentAddress


def parseHeldObject(
    romfile, currentAddress, currentTransform, armatureObj, parentBoneName, ignoreNode, nodeIndex, segmentData
):
    print("HELD OBJECT " + hex(currentAddress))
    commandSize = 12
    romfile.seek(currentAddress)
    command = romfile.read(commandSize)

    pos = readVectorFromShorts(command, 2)
    translation = mathutils.Matrix.Translation(mathutils.Vector(pos))
    finalTransform = currentTransform @ translation
    asmFunc = bytesToHexClean(command[8:12])

    if not ignoreNode:
        boneName = format(nodeIndex, "03") + "-held_object"
        if armatureObj is not None:
            boneName = createBone(armatureObj, parentBoneName, boneName, finalTransform, "HeldObject", False)
            bone = armatureObj.data.bones[boneName]
            bone.geo_func = asmFunc

    currentAddress += commandSize
    return currentAddress, finalTransform


def getMarioBoneName(startRelativeAddr, armatureData, default="sm64_mesh"):
    try:
        boneName = armatureData.findBoneByOffset(startRelativeAddr).name
        return boneName
    except Exception:
        return default


def assignMarioGeoMetadata(obj, commandAddress, geoStartAddress, cmdType, armatureData, lastTransRotAddr=None):

    # for geo_pointer reading offsets:
    # cmd 			= 0
    # draw layer 	= 1
    # translation 	= 2 (for 0x13)
    # display lists = 4 (for 0x15) or 8 (for 0x13)
    sm64_geo_meta = {
        "geo_start": geoStartAddress,
        "geo_pointer_relative": commandAddress - geoStartAddress,
        "geo_cmd_type": cmdType,
        "geo_has_mesh": len(obj.data.loops) > 0,
        "geo_top_overlap_ptr": None,
        "geo_other_overlap_ptrs": [],
    }

    # actual value doesn't matter, just a flag
    if lastTransRotAddr is not None:
        sm64_geo_meta["geo_trans_ptr"] = lastTransRotAddr

    obj["sm64_geo_meta"] = sm64_geo_meta

    if armatureData is not None:
        obj["sm64_part_names"] = [armatureData.findBoneByOffset(commandAddress - geoStartAddress).name]


def handleOverlapGeoMetadata(bone):
    parentBone = bone.parent
    if parentBone is not None and "sm64_geo_meta" in parentBone:
        # boneMeta = copyBlenderPropDict(bone['sm64_geo_meta'])
        boneMeta = bone["sm64_geo_meta"]
        parentBoneMeta = parentBone["sm64_geo_meta"]

        if parentBoneMeta["geo_top_overlap_ptr"] is None:
            parentBoneMeta["geo_top_overlap_ptr"] = parentBoneMeta["geo_pointer_relative"]

        else:
            # Done this way since we cannot deepcopy blender ID property arrays
            parentBoneMeta["geo_other_overlap_ptrs"] = [ptr for ptr in parentBoneMeta["geo_other_overlap_ptrs"]] + [
                parentBoneMeta["geo_pointer_relative"]
            ]

        parentBoneMeta["geo_pointer_relative"] = boneMeta["geo_pointer_relative"]
        parentBoneMeta["geo_cmd_type"] = boneMeta["geo_cmd_type"]
        parentBoneMeta["geo_has_mesh"] = boneMeta["geo_has_mesh"]

        bone["sm64_geo_meta"] = parentBoneMeta
        del parentBone["sm64_geo_meta"]


# See SM64GeoLayoutPtrsByLevels.txt by VLTone
class SM64_ImportGeolayout(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.sm64_import_geolayout"
    bl_label = "Import Geolayout"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileSrc = None
        try:
            geoImportAddr = context.scene.geoImportAddr
            generateArmature = context.scene.generateArmature
            levelGeoImport = context.scene.levelGeoImport
            importRom = context.scene.importRom
            ignoreSwitch = context.scene.ignoreSwitch

            # finalTransform = mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
            finalTransform = mathutils.Matrix.Identity(4)
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}
        try:
            romfileSrc = open(bpy.path.abspath(importRom), "rb")
            checkExpanded(bpy.path.abspath(importRom))

            armatureObj = None

            # Get segment data
            levelParsed = parseLevelAtPointer(romfileSrc, level_pointers[levelGeoImport])
            segmentData = levelParsed.segmentData
            geoStart = int(geoImportAddr, 16)
            if context.scene.geoIsSegPtr:
                geoStart = decodeSegmentedAddr(geoStart.to_bytes(4, "big"), segmentData)

            # Armature mesh groups includes armatureObj.
            armatureMeshGroups, armatureObj = parseGeoLayout(
                romfileSrc,
                geoStart,
                context.scene,
                segmentData,
                finalTransform,
                generateArmature,
                ignoreSwitch,
                True,
                context.scene.f3d_type,
                context.scene.isHWv1,
            )
            romfileSrc.close()

            bpy.ops.object.select_all(action="DESELECT")
            if armatureObj is not None:
                for armatureMeshGroup in armatureMeshGroups:
                    armatureMeshGroup[0].select_set(True)
                doRotation(math.radians(-90), "X")

                for armatureMeshGroup in armatureMeshGroups:
                    bpy.ops.object.select_all(action="DESELECT")
                    armatureMeshGroup[0].select_set(True)
                    bpy.context.view_layer.objects.active = armatureMeshGroup[0]
                    bpy.ops.object.make_single_user(obdata=True)
                    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False, properties=False)
            else:
                doRotation(math.radians(-90), "X")
            bpy.ops.object.select_all(action="DESELECT")
            # objs[-1].select_set(True)

            self.report({"INFO"}, "Generic import succeeded.")
            return {"FINISHED"}  # must return a set

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            if romfileSrc is not None:
                romfileSrc.close()
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class SM64_ImportGeolayoutPanel(SM64_Panel):
    bl_idname = "SM64_PT_import_geolayout"
    bl_label = "SM64 Geolayout Importer"
    goal = sm64GoalImport

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsGeoI = col.operator(SM64_ImportGeolayout.bl_idname)

        # col.prop(context.scene, 'rotationOrder')
        # col.prop(context.scene, 'rotationAxis')
        # col.prop(context.scene, 'rotationAngle')
        prop_split(col, context.scene, "geoImportAddr", "Start Address")
        col.prop(context.scene, "geoIsSegPtr")
        col.prop(context.scene, "levelGeoImport")
        col.prop(context.scene, "generateArmature")
        col.prop(context.scene, "ignoreSwitch")
        if not context.scene.ignoreSwitch:
            boxLayout = col.box()
            boxLayout.label(text="WARNING: May take a long time.")
            boxLayout.label(text="Switch nodes won't be setup.")
        col.box().label(text="Only Fast3D mesh importing allowed.")


sm64_geo_parser_classes = (SM64_ImportGeolayout,)

sm64_geo_parser_panel_classes = (SM64_ImportGeolayoutPanel,)


def sm64_geo_parser_panel_register():
    for cls in sm64_geo_parser_panel_classes:
        register_class(cls)


def sm64_geo_parser_panel_unregister():
    for cls in sm64_geo_parser_panel_classes:
        unregister_class(cls)


def sm64_geo_parser_register():
    for cls in sm64_geo_parser_classes:
        register_class(cls)

    bpy.types.Scene.geoImportAddr = bpy.props.StringProperty(name="Start Address", default="1F1D60")
    bpy.types.Scene.generateArmature = bpy.props.BoolProperty(name="Generate Armature?", default=True)
    bpy.types.Scene.levelGeoImport = bpy.props.EnumProperty(items=level_enums, name="Level", default="HMC")
    bpy.types.Scene.ignoreSwitch = bpy.props.BoolProperty(name="Ignore Switch Nodes", default=True)


def sm64_geo_parser_unregister():
    for cls in reversed(sm64_geo_parser_classes):
        unregister_class(cls)

    del bpy.types.Scene.generateArmature
    del bpy.types.Scene.geoImportAddr
    del bpy.types.Scene.levelGeoImport
    del bpy.types.Scene.ignoreSwitch
