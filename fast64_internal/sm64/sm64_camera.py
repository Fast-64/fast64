import bpy, mathutils
from bpy.utils import register_class, unregister_class
from ..utility import colorTo16bitRGBA, gammaCorrect

from .sm64_geolayout_classes import (
    TransformNode,
    ScreenAreaNode,
    ZBufferNode,
    OrthoNode,
    BackgroundNode,
    FrustumNode,
    CameraNode,
    StartNode,
    RenderObjNode,
    FunctionNode,
)

enumBackgroundType = [
    ("OCEAN_SKY", "Ocean Sky", "Ocean Sky"),
    ("FLAMING_SKY", "Flaming Sky", "Flaming Sky"),
    ("UNDERWATER_CITY", "Underwater City", "Underwater City"),
    ("BELOW_CLOUDS", "Below Clouds", "Below Clouds"),
    ("SNOW_MOUNTAINS", "Snow Mountains", "Snow Mountains"),
    ("DESERT", "Desert", "Desert"),
    ("HAUNTED", "Haunted", "Haunted"),
    ("GREEN_SKY", "Green Sky", "Green Sky"),
    ("ABOVE_CLOUDS", "Above Clouds", "Above Clouds"),
    ("PURPLE_SKY", "Purple Sky", "Purple Sky"),
]

backgroundValues = {
    "OCEAN_SKY": 0,
    "FLAMING_SKY": 1,
    "UNDERWATER_CITY": 2,
    "BELOW_CLOUDS": 3,
    "SNOW_MOUNTAINS": 4,
    "DESERT": 5,
    "HAUNTED": 6,
    "GREEN_SKY": 7,
    "ABOVE_CLOUDS": 8,
    "PURPLE_SKY": 9,
}


class CameraSettingsPanel(bpy.types.Panel):
    bl_label = "Camera Settings"
    bl_idname = "Camera_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return hasattr(context, "object") and isinstance(context.object.data, bpy.types.Camera)

    def draw(self, context):
        camera = context.object.data
        layout = self.layout.box()
        layout.box().label(text="SM64 Camera Settings")
        # layout.prop(camera, 'useBackgroundColor')
        # if camera.useBackgroundColor:
        # 	prop_split(layout, camera, 'backgroundColor', 'Background Color')
        # else:
        # 	prop_split(layout, camera, 'backgroundID', 'Background ID')
        # 	layout.box().label(text = 'Background IDs defined in include/geo_commands.h.')
        # layout.prop(camera, 'dynamicFOV')
        # if not camera.dynamicFOV:
        # 	prop_split(layout, camera, 'fov', 'Field Of View')
        # layout.prop(camera, 'useDefaultScreenRect')
        # if not camera.useDefaultScreenRect:
        # 	prop_split(layout, camera, 'screenPos', 'Screen Position')
        # 	prop_split(layout, camera, 'screenSize', 'Screen Size')

        # prop_split(layout, camera, 'clipPlanes', 'Clip Planes')
        # prop_split(layout, camera, 'camType', 'Camera Type')
        # prop_split(layout, camera, 'envType', 'Environment Type')


def saveCameraSettingsToGeolayout(geolayoutGraph, areaObj, rootObj, meshGeolayoutName):
    geolayout = geolayoutGraph.startGeolayout
    screenAreaNode = TransformNode(
        ScreenAreaNode(areaObj.useDefaultScreenRect, 0xA, areaObj.screenPos, areaObj.screenSize)
    )
    geolayout.nodes.insert(0, screenAreaNode)

    if not areaObj.fast64.sm64.area.disable_background:
        zBufferDisable = TransformNode(ZBufferNode(False))
        screenAreaNode.children.append(zBufferDisable)

        orthoNode = TransformNode(OrthoNode(0x64))
        zBufferDisable.children.append(orthoNode)

        # Uses Level Root here
        bgColor = colorTo16bitRGBA(
            gammaCorrect(areaObj.areaBGColor if areaObj.areaOverrideBG else rootObj.backgroundColor) + [1]
        )
        if areaObj.areaOverrideBG:
            bgNode = TransformNode(BackgroundNode(True, bgColor))
        else:
            background = ""
            if rootObj.useBackgroundColor:
                background = bgColor
            else:
                if rootObj.background == "CUSTOM":
                    background = rootObj.fast64.sm64.level.backgroundID
                else:
                    background = "BACKGROUND_" + rootObj.background

            bgNode = TransformNode(BackgroundNode(rootObj.useBackgroundColor, background))
        orthoNode.children.append(bgNode)

    zBufferEnable = TransformNode(ZBufferNode(True))
    screenAreaNode.children.append(zBufferEnable)

    # frustumNode = TransformNode(FrustumNode(
    # 	math.degrees(camera.angle), camera.clip_start, camera.clip_end))
    frustumNode = TransformNode(FrustumNode(areaObj.fov, areaObj.clipPlanes[0], areaObj.clipPlanes[1]))
    zBufferEnable.children.append(frustumNode)

    relativeTransform = rootObj.matrix_world.inverted() @ areaObj.matrix_world
    relativePosition = relativeTransform.decompose()[0]
    relativeRotation = relativeTransform.decompose()[1]
    cameraNode = TransformNode(
        CameraNode(
            areaObj.camOption if areaObj.camOption != "Custom" else areaObj.camType,
            relativePosition,
            relativePosition + relativeRotation @ mathutils.Vector((0, 0, -1)),
        )
    )
    frustumNode.children.append(cameraNode)

    startDLNode = TransformNode(StartNode())
    meshGeolayout = geolayoutGraph.addGeolayout(rootObj, meshGeolayoutName)
    meshGeolayout.nodes.append(startDLNode)
    geolayoutGraph.addJumpNode(cameraNode, geolayout, meshGeolayout)

    # Moving textures here

    cameraNode.children.append(TransformNode(RenderObjNode()))

    # corresponds to geo_enfvx_main
    cameraNode.children.append(
        TransformNode(FunctionNode("802761D0", areaObj.envOption if areaObj.envOption != "Custom" else areaObj.envType))
    )

    return meshGeolayout


sm64_cam_classes = (
    # CameraSettingsPanel,
)

sm64_cam_panel_classes = ()


def sm64_cam_panel_register():
    for cls in sm64_cam_panel_classes:
        register_class(cls)


def sm64_cam_panel_unregister():
    for cls in sm64_cam_panel_classes:
        unregister_class(cls)


#  802763D4 - ASM function for background
#  8029AA3C - ASM function for camera frustum


def sm64_cam_register():
    for cls in sm64_cam_classes:
        register_class(cls)

    # Moved to Level Root
    # bpy.types.Camera.useBackgroundColor = bpy.props.BoolProperty(
    # 	name = 'Use Solid Color For Background', default = False)

    # bpy.types.Camera.backgroundID = bpy.props.StringProperty(
    # 	name = 'Background ID', default = 'BACKGROUND_OCEAN_SKY')
    #
    # bpy.types.Camera.backgroundColor = bpy.props.FloatVectorProperty(
    # 	name = 'Background Color', subtype='COLOR', size = 4,
    # 	min = 0, max = 1, default = (0,0,0,1))

    # bpy.types.Camera.dynamicFOV = bpy.props.BoolProperty(
    # 	name = 'Dynamic FOV', default = True)

    # Moved to Area Root
    # bpy.types.Camera.screenPos = bpy.props.IntVectorProperty(
    # 	name = 'Screen Position', size = 2, default = (160, 120),
    # 	min = -2**15, max = 2**15 - 1)

    # bpy.types.Camera.screenSize = bpy.props.IntVectorProperty(
    # 	name = 'Screen Size', size = 2, default = (160, 120),
    # 	min = -2**15, max = 2**15 - 1)

    # bpy.types.Camera.camType = bpy.props.StringProperty(
    # 	name = 'Camera Type', default = '1')

    # bpy.types.Camera.envType = bpy.props.StringProperty(
    # 	name = 'Environment Type', default = '0')

    # Moved to Area Root
    # bpy.types.Camera.useDefaultScreenRect = bpy.props.BoolProperty(
    # 	name = 'Use Default Screen Rect', default = True)

    # bpy.types.Camera.clipPlanes = bpy.props.IntVectorProperty(
    # 	name = 'Clip Planes', size = 2, min = 0, default = (100, 30000)
    # )

    # bpy.types.Camera.fov = bpy.props.FloatProperty(
    # 	name = 'Field Of View', min = 0, max = 180, default = 45
    # )


def sm64_cam_unregister():
    # del bpy.types.Camera.useBackgroundColor
    # del bpy.types.Camera.backgroundID
    # del bpy.types.Camera.backgroundColor
    # del bpy.types.Camera.dynamicFOV
    # del bpy.types.Camera.orthoScale
    # del bpy.types.Camera.screenPos
    # del bpy.types.Camera.screenSize
    # del bpy.types.Camera.camType
    # del bpy.types.Camera.envType
    # del bpy.types.Camera.useDefaultScreenRect
    # del bpy.types.Camera.clipPlanes
    # del bpy.types.Camera.fov

    for cls in sm64_cam_classes:
        unregister_class(cls)
