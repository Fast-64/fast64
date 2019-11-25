import bpy
from bpy.utils import register_class, unregister_class
from .utility import *
from .sm64_geolayout_constants import *
from .sm64_geolayout_classes import *
import math

enumBackgroundType = [
	('OCEAN_SKY', 'Ocean Sky', 'Ocean Sky'),
	('FLAMING_SKY', 'Flaming Sky', 'Flaming Sky'),
	('UNDERWATER_CITY', 'Underwater City', 'Underwater City'),
	('BELOW_CLOUDS', 'Below Clouds', 'Below Clouds'),
	('SNOW_MOUNTAINS', 'Snow Mountains', 'Snow Mountains'),
	('DESERT', 'Desert', 'Desert'),
	('HAUNTED', 'Haunted', 'Haunted'),
	('GREEN_SKY', 'Green Sky', 'Green Sky'),
	('ABOVE_CLOUDS', 'Above Clouds', 'Above Clouds'),
	('PURPLE_SKY', 'Purple Sky', 'Purple Sky'),
]

backgroundValues = {
	'OCEAN_SKY' : 0,
	'FLAMING_SKY' : 1,
	'UNDERWATER_CITY' : 2,
	'BELOW_CLOUDS' : 3,
	'SNOW_MOUNTAINS' : 4,
	'DESERT' : 5,
	'HAUNTED' : 6,
	'GREEN_SKY' : 7,
	'ABOVE_CLOUDS' : 8,
	'PURPLE_SKY' : 9,
}

class CameraSettingsPanel(bpy.types.Panel):
	bl_label = "Camera Settings"
	bl_idname = "Camera_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "data"
	bl_options = {'HIDE_HEADER'}

	@classmethod
	def poll(cls, context):
		return hasattr(context, 'object') and \
			isinstance(context.object.data, bpy.types.Camera)

	def draw(self, context):
		camera = context.object.data
		layout = self.layout.box()
		layout.box().label(text = 'SM64 Camera Settings')
		layout.prop(camera, 'useBackgroundColor')
		if camera.useBackgroundColor:
			prop_split(layout, camera, 'backgroundColor', 'Background Color')
		else:
			prop_split(layout, camera, 'backgroundID', 'Background ID')
		layout.prop(camera, 'dynamicFOV')
		layout.prop(camera, 'useDefaultScreenRect')
		if not camera.useDefaultScreenRect:
			prop_split(layout, camera, 'screenPos', 'Screen Position')
			prop_split(layout, camera, 'screenSize', 'Screen Size')
		prop_split(layout, camera, 'camType', 'Camera Type')
		prop_split(layout, camera, 'envType', 'Environment Type')

def saveCameraSettingsToGeolayout(geolayout, cameraObj, rootObj):
	camera = cameraObj.data
	screenAreaNode = TransformNode(ScreenAreaNode(
		camera.useDefaultScreenRect, 0xA, camera.screenPos, camera.screenSize))
	geolayout.nodes.insert(0, screenAreaNode)
	
	zBufferDisable = TransformNode(ZBufferNode(False))
	screenAreaNode.children.append(zBufferDisable)

	orthoNode = TransformNode(OrthoNode(0x64))
	zBufferDisable.children.append(orthoNode)

	bgColor = colorTo16bitRGBA(gammaCorrect(camera.backgroundColor) + [1])
	bgNode = TransformNode(BackgroundNode(
		camera.useBackgroundColor, bgColor))
	orthoNode.children.append(bgNode)

	zBufferEnable = TransformNode(ZBufferNode(True))
	screenAreaNode.children.append(zBufferEnable)

	frustumNode = TransformNode(FrustumNode(
		math.degrees(camera.angle), camera.clip_start, camera.clip_end))
	zBufferEnable.children.append(frustumNode)

	relativeTransform = rootObj.matrix_world.inverted() @ cameraObj.matrix_world
	relativePosition = relativeTransform.decompose()[0]
	relativeRotation = relativeTransform.decompose()[1]
	cameraNode = TransformNode(CameraNode(camera.camType, relativePosition,
		relativePosition + relativeRotation @ mathutils.Vector((0,0,-1))))
	frustumNode.children.append(cameraNode)

	startDLNode = TransformNode(StartNode())
	cameraNode.children.append(startDLNode)

	# Moving textures here

	cameraNode.children.append(TransformNode(RenderObjNode()))
	cameraNode.children.append(TransformNode(EnvFunctionNode(camera.envType)))

	return startDLNode

cam_classes = (
	CameraSettingsPanel,
)

#  802763D4 - ASM function for background
#  8029AA3C - ASM function for camera frustum

def cam_register():
	for cls in cam_classes:
		register_class(cls)

	bpy.types.Camera.useBackgroundColor = bpy.props.BoolProperty(
		name = 'Use Solid Color For Background', default = False)

	bpy.types.Camera.backgroundID = bpy.props.IntProperty(
		name = 'Background ID', min = 0, max = 2**16 - 1)
	
	bpy.types.Camera.backgroundColor = bpy.props.FloatVectorProperty(
		name = 'Background Color', subtype='COLOR', size = 4, 
		min = 0, max = 1, default = (0,0,0,1))
	
	bpy.types.Camera.dynamicFOV = bpy.props.BoolProperty(
		name = 'Dynamic FOV', default = True)
	
	bpy.types.Camera.screenPos = bpy.props.IntVectorProperty(
		name = 'Screen Position', size = 2, default = (160, 120), 
		min = -2**15, max = 2**15 - 1)

	bpy.types.Camera.screenSize = bpy.props.IntVectorProperty(
		name = 'Screen Size', size = 2, default = (160, 120), 
		min = -2**15, max = 2**15 - 1)
	
	bpy.types.Camera.camType = bpy.props.IntProperty(
		name = 'Camera Type', min = 0, max = 2 ** 16 - 1)

	bpy.types.Camera.envType = bpy.props.IntProperty(
		name = 'Environment Type', min = 0, max = 2 ** 16 - 1)

	bpy.types.Camera.useDefaultScreenRect = bpy.props.BoolProperty(
		name = 'Use Default Screen Rect', default = True)

def cam_unregister():
	del bpy.types.Camera.backgroundID
	del bpy.types.Camera.backgroundColor
	del bpy.types.Camera.dynamicFOV
	del bpy.types.Camera.orthoScale
	del bpy.types.Camera.screenPos
	del bpy.types.Camera.screenSize
	del bpy.types.Camera.camType
	del bpy.types.Camera.envType
	del bpy.types.Camera.useDefaultScreenRect

	for cls in cam_classes:
		unregister_class(cls)