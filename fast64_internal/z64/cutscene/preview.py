import bpy

from math import isclose
from typing import TYPE_CHECKING
from bpy.types import Scene, Object, Node
from bpy.app.handlers import persistent
from ...utility import gammaInverse, hexOrDecInt
from ..utility import is_oot_features
from .motion.utility import getCutsceneCamera

if TYPE_CHECKING:
    from .properties import OOTCutscenePreviewSettingsProperty, OOTCutscenePreviewProperty


def getLerp(max: float, min: float, val: float):
    # from ``Environment_LerpWeight()`` in decomp
    diff = max - min
    ret = None

    if diff != 0.0:
        ret = 1.0 - (max - val) / diff

        if not ret >= 1.0:
            return ret

    return 1.0


def getColor(value: float) -> float:
    """Returns the value converted in the linear color space"""
    return gammaInverse([value / 0xFF, 0.0, 0.0])[0]


def getNode(node: Node, type: str, name: str, location: tuple[float, float]):
    """Returns a compositor node"""
    if node is None:
        node = bpy.context.scene.node_tree.nodes.new(type)
    node.select = False
    node.name = node.label = name
    node.location = location
    return node


def setupCompositorNodes():
    """Creates or re-setups compositor nodes"""
    if bpy.app.version < (3, 6, 0):
        # Blender 3.6+ is required in order to use Compositor Nodes
        return

    if not bpy.context.scene.use_nodes:
        bpy.context.scene.use_nodes = True

    # sets the compositor render mode to "Camera"
    space = None
    for area in bpy.context.screen.areas:
        if (area != bpy.context.area) and (area.type == "VIEW_3D"):
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    break
    if space is not None and space.shading.use_compositor != "CAMERA":
        space.shading.use_compositor = "CAMERA"

    # if everything's fine and nodes are already ready to use stop there
    if bpy.context.scene.ootPreviewSettingsProperty.ootCSPreviewNodesReady:
        return

    # get the existing nodes
    nodeTree = bpy.context.scene.node_tree
    nodeRenderLayer = nodeComposite = nodeRGBTrans = nodeAlphaOver = nodeRGBMisc = nodeMixRGBMisc = None
    node_motion_blur = None
    for node in nodeTree.nodes.values():
        if node.type == "R_LAYERS":
            nodeRenderLayer = node
        if node.type == "COMPOSITE":
            nodeComposite = node
        if node.label == "CSTrans_RGB":
            nodeRGBTrans = node
        if node.label == "CSMisc_RGB":
            nodeRGBMisc = node
        if node.label == "CSPreview_AlphaOver":
            nodeAlphaOver = node
        if node.label == "CSMisc_MixRGB":
            nodeMixRGBMisc = node
        if node.label == "CSMotionBlur":
            node_motion_blur = node

    # create or set the data of each nodes
    nodeRenderLayer = getNode(nodeRenderLayer, "CompositorNodeRLayers", "CSPreview_RenderLayer", (-300, 0))
    nodeRGBMisc = getNode(nodeRGBMisc, "CompositorNodeRGB", "CSMisc_RGB", (-200, -200))
    nodeRGBTrans = getNode(nodeRGBTrans, "CompositorNodeRGB", "CSTrans_RGB", (0, -200))
    nodeMixRGBMisc = getNode(nodeMixRGBMisc, "CompositorNodeMixRGB", "CSMisc_MixRGB", (0, 0))
    nodeAlphaOver = getNode(nodeAlphaOver, "CompositorNodeAlphaOver", "CSPreview_AlphaOver", (200, 0))
    node_motion_blur = getNode(node_motion_blur, "CompositorNodeDBlur", "CSMotionBlur", (400, 0))
    nodeComposite = getNode(nodeComposite, "CompositorNodeComposite", "CSPreview_Composite", (600, 0))

    # link the nodes together
    nodeTree.links.new(nodeMixRGBMisc.inputs[1], nodeRenderLayer.outputs[0])
    nodeTree.links.new(nodeMixRGBMisc.inputs[2], nodeRGBMisc.outputs[0])
    nodeTree.links.new(nodeAlphaOver.inputs[1], nodeMixRGBMisc.outputs[0])
    nodeTree.links.new(nodeAlphaOver.inputs[2], nodeRGBTrans.outputs[0])
    nodeTree.links.new(node_motion_blur.inputs[0], nodeAlphaOver.outputs[0])
    nodeTree.links.new(nodeComposite.inputs[0], node_motion_blur.outputs[0])

    # misc settings
    nodeMixRGBMisc.use_alpha = True
    nodeMixRGBMisc.blend_type = "COLOR"
    bpy.context.scene.ootPreviewSettingsProperty.ootCSPreviewNodesReady = True

    # blur settings
    node_motion_blur.iterations = 1


def initFirstFrame(csObj: Object, useNodeFeatures: bool, defaultCam: Object):
    # set default values for frame 0
    if useNodeFeatures:
        color = [0.0, 0.0, 0.0, 0.0]
        bpy.context.scene.node_tree.nodes["CSTrans_RGB"].outputs[0].default_value = color
        bpy.context.scene.node_tree.nodes["CSMisc_RGB"].outputs[0].default_value = color
        bpy.context.scene.node_tree.nodes["CSMotionBlur"].zoom = 0.0
        csObj.ootCutsceneProperty.preview.trigger = False
    csObj.ootCutsceneProperty.preview.isFixedCamSet = False
    if defaultCam is not None:
        bpy.context.scene.camera = defaultCam


def processCurrentFrame(csObj: Object, curFrame: float, useNodeFeatures: bool, cameraObjects: Object):
    """Execute the actions of each command to create the preview for the current frame"""
    # this function was partially adapted from ``z_demo.c``
    previewProp: "OOTCutscenePreviewProperty" = csObj.ootCutsceneProperty.preview
    preview_settings: "OOTCutscenePreviewSettingsProperty" = bpy.context.scene.ootPreviewSettingsProperty

    if curFrame == 0:
        initFirstFrame(csObj, useNodeFeatures, cameraObjects[1])

    if useNodeFeatures:
        previewProp = csObj.ootCutsceneProperty.preview

        for transitionCmd in previewProp.transitionList:
            startFrame = transitionCmd.startFrame
            endFrame = transitionCmd.endFrame
            frameCur = curFrame
            isTriggerInstance = transitionCmd.type == "trigger_instance"
            linear160 = getColor(160.0)

            if transitionCmd.type == "Unknown":
                print("ERROR: Unknown command!")

            if curFrame == 0:
                # makes transitions appear a frame earlier if frame 0
                frameCur += 1

            if isTriggerInstance and not previewProp.trigger:
                color = [linear160, linear160, linear160, 1.0]
                bpy.context.scene.node_tree.nodes["CSTrans_RGB"].outputs[0].default_value = color

            if frameCur >= startFrame and frameCur <= endFrame:
                color = [0.0, 0.0, 0.0, 0.0]
                lerp = getLerp(endFrame, startFrame, frameCur)
                linear255 = getColor(255.0)
                linear155 = getColor(155.0)

                if isTriggerInstance:
                    previewProp.trigger = True

                if transitionCmd.type.endswith("in"):
                    alpha = linear255 * lerp
                else:
                    alpha = (1.0 - lerp) * linear255

                if transitionCmd.type == "gray_to_black":
                    color[0] = color[1] = color[2] = (1.0 - lerp) * linear160
                    alpha = 1.0
                elif transitionCmd.type == "black_to_gray":
                    color[0] = color[1] = color[2] = lerp * linear160
                    alpha = 1.0
                elif "half" in transitionCmd.type:
                    if "_in_" in transitionCmd.type:
                        alpha = linear255 - ((1.0 - lerp) * linear155)
                    else:
                        alpha = linear255 - (linear155 * lerp)
                elif "gray_" in transitionCmd.type or previewProp.trigger:
                    color[0] = color[1] = color[2] = linear160 * alpha
                elif "red_" in transitionCmd.type:
                    color[0] = linear255 * alpha
                elif "green_" in transitionCmd.type:
                    color[1] = linear255 * alpha
                elif "blue_" in transitionCmd.type:
                    color[2] = linear255 * alpha

                color[3] = alpha
                bpy.context.scene.node_tree.nodes["CSTrans_RGB"].outputs[0].default_value = color

        for trans_general_cmd in previewProp.transition_general_list:
            startFrame = trans_general_cmd.startFrame
            endFrame = trans_general_cmd.endFrame
            frameCur = curFrame

            if is_oot_features():
                bpy.context.scene.node_tree.nodes["CSTrans_RGB"].outputs[0].default_value = (0.0, 0.0, 0.0, 0.0)
                break

            if trans_general_cmd.type == "Unknown":
                print("ERROR: Unknown command!")

            if frameCur >= startFrame and endFrame >= frameCur:
                color = [0.0, 0.0, 0.0, 0.0]
                lerp = getLerp(endFrame, startFrame, frameCur)
                linear255 = getColor(255.0)

                if trans_general_cmd.type in {"trans_general_fill_in", "trans_general_fill_out"}:
                    if trans_general_cmd.type == "trans_general_fill_in":
                        alpha = linear255 * lerp
                    else:
                        alpha = (1.0 - lerp) * linear255

                    color[0] = trans_general_cmd.color[0] * alpha
                    color[1] = trans_general_cmd.color[1] * alpha
                    color[2] = trans_general_cmd.color[2] * alpha
                    color[3] = alpha
                    bpy.context.scene.node_tree.nodes["CSTrans_RGB"].outputs[0].default_value = color

        for blur_cmd in previewProp.motion_blur_list:
            startFrame = blur_cmd.startFrame
            endFrame = blur_cmd.endFrame
            frameCur = curFrame

            if is_oot_features():
                bpy.context.scene.node_tree.nodes["CSTrans_RGB"].outputs[0].default_value = (0.0, 0.0, 0.0, 0.0)
                break

            if blur_cmd.type == "Unknown":
                print("ERROR: Unknown command!")

            if frameCur >= startFrame and frameCur <= endFrame:
                if blur_cmd.type == "motion_blur_enable":
                    bpy.context.scene.node_tree.nodes["CSMotionBlur"].zoom = 0.180
                    previewProp.blur_reinit = False
                elif blur_cmd.type == "motion_blur_disable":
                    lerp = getLerp(endFrame, startFrame, frameCur)

                    if lerp >= 0.9:
                        bpy.context.scene.node_tree.nodes["CSMotionBlur"].zoom = 0.0
                    else:
                        bpy.context.scene.node_tree.nodes["CSMotionBlur"].zoom = (1.0 - lerp) * 0.18

    for miscCmd in previewProp.miscList:
        startFrame = miscCmd.startFrame
        endFrame = miscCmd.endFrame

        if miscCmd.type == "Unknown":
            print("ERROR: Unknown command!")

        if curFrame == startFrame:
            if miscCmd.type == "set_locked_viewpoint" and not None in cameraObjects:
                bpy.context.scene.camera = cameraObjects[int(previewProp.isFixedCamSet)]
                previewProp.isFixedCamSet ^= True
            elif not preview_settings.ignore_cs_misc_stop and miscCmd.type == "stop_cutscene":
                # stop the playback and set the frame to 0
                bpy.ops.screen.animation_cancel()
                bpy.context.scene.frame_set(bpy.context.scene.frame_start)

        if curFrame >= startFrame and (curFrame < endFrame or endFrame == startFrame):
            if useNodeFeatures:
                color = [0.0, 0.0, 0.0, 0.0]
                lerp = getLerp(endFrame - 1, startFrame, curFrame)

                if miscCmd.type in ["vismono_sepia", "vismono_black_and_white"]:
                    if miscCmd.type == "vismono_sepia":
                        col = [255.0, 180.0, 100.0]
                    else:
                        col = [255.0, 255.0, 254.0]

                    for i in range(3):
                        color[i] = getColor(col[i])

                    color[3] = getColor(255.0) * lerp
                    bpy.context.scene.node_tree.nodes["CSMisc_RGB"].outputs[0].default_value = color

                elif miscCmd.type == "red_pulsating_lights":
                    color = bpy.context.scene.node_tree.nodes["CSMisc_RGB"].outputs[0].default_value
                    color[0] = getColor(255.0)
                    color[1] = color[2] = 0.0
                    step = 0.05
                    if curFrame & 8:
                        if color[3] < 0.20:
                            color[3] += step
                    else:
                        if color[3] > 0.05:
                            color[3] -= step
                    bpy.context.scene.node_tree.nodes["CSMisc_RGB"].outputs[0].default_value = color


@persistent
def cutscenePreviewFrameHandler(scene: Scene):
    """Preview frame handler, executes each frame when the cutscene is played"""
    previewSettings: "OOTCutscenePreviewSettingsProperty" = scene.ootPreviewSettingsProperty
    csObj: Object = previewSettings.ootCSPreviewCSObj

    if csObj is None or not csObj.type == "EMPTY" and not csObj.ootEmptyType == "Cutscene":
        return

    # populate ``cameraObjects`` with the cutscene camera and the first found prerend fixed camera
    cameraObjects = [None, getCutsceneCamera(csObj)]

    foundObj = None
    for obj in bpy.data.objects:
        if obj.type == "CAMERA" and obj.parent is not None and obj.parent.ootEmptyType in ["Scene", "Room"]:
            camPosProp = obj.ootCameraPositionProperty
            camTypes = ["CAM_SET_PREREND0", "CAM_SET_PREREND_FIXED"]
            if camPosProp.camSType != "Custom" and camPosProp.camSType in camTypes:
                foundObj = obj
                break
            elif camPosProp.camSType == "Custom":
                if camPosProp.camSTypeCustom.startswith("0x"):
                    if hexOrDecInt(camPosProp.camSTypeCustom) == 25:
                        foundObj = obj
                        break
                elif camPosProp.camSTypeCustom in camTypes:
                    foundObj = obj
                    break

    if foundObj is not None:
        cameraObjects[0] = foundObj

    # setup nodes
    previewSettings.ootCSPreviewNodesReady = False
    setupCompositorNodes()
    previewProp = csObj.ootCutsceneProperty.preview

    # set preview properties
    previewProp.miscList.clear()
    previewProp.transitionList.clear()
    previewProp.motion_blur_list.clear()
    previewProp.transition_general_list.clear()
    for item in csObj.ootCutsceneProperty.csLists:
        if item.listType == "Transition":
            for trans_entry in item.transition_list:
                newProp = previewProp.transitionList.add()
                newProp.startFrame = trans_entry.startFrame
                newProp.endFrame = trans_entry.endFrame
                newProp.type = trans_entry.transition_type
        elif item.listType == "MiscList":
            for miscEntry in item.miscList:
                newProp = previewProp.miscList.add()
                newProp.startFrame = miscEntry.startFrame
                newProp.endFrame = miscEntry.endFrame
                newProp.type = miscEntry.csMiscType
        elif item.listType == "MotionBlurList":
            for blur_entry in item.motion_blur_list:
                newProp = previewProp.motion_blur_list.add()
                newProp.startFrame = blur_entry.startFrame
                newProp.endFrame = blur_entry.endFrame
                newProp.type = blur_entry.blur_type
        elif item.listType == "TransitionGeneralList":
            for trans_general_entry in item.trans_general_list:
                newProp = previewProp.transition_general_list.add()
                newProp.startFrame = trans_general_entry.startFrame
                newProp.endFrame = trans_general_entry.endFrame
                newProp.type = trans_general_entry.trans_general_type
                newProp.color = trans_general_entry.trans_color

    # execute the main preview logic
    curFrame = bpy.context.scene.frame_current
    if isclose(curFrame, previewProp.prevFrame, abs_tol=1) and isclose(curFrame, previewProp.nextFrame, abs_tol=1):
        processCurrentFrame(csObj, curFrame, previewSettings.ootCSPreviewNodesReady, cameraObjects)
    else:
        # Simulate cutscene for all frames up to present
        for i in range(bpy.context.scene.frame_current):
            processCurrentFrame(csObj, i, previewSettings.ootCSPreviewNodesReady, cameraObjects)

    # since we reached the end of the function, the current frame becomes the previous one
    previewProp.nextFrame = curFrame + 2 if curFrame > previewProp.prevFrame else curFrame - 2
    previewProp.prevFrame = curFrame


def cutscene_preview_register():
    bpy.app.handlers.frame_change_pre.append(cutscenePreviewFrameHandler)


def cutscene_preview_unregister():
    if cutscenePreviewFrameHandler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(cutscenePreviewFrameHandler)
