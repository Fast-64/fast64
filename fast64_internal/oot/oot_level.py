import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from .oot_scene_room import *
from .oot_exit_entrance import *
from .oot_actor import *
#from .oot_function_map import func_map
#from .oot_spline import *

from ..utility import *

def headerSettingsToIndices(headerSettings):
	if headerSettings.inAllSceneSetups:
		return None

	headers = set()
	if headerSettings.childDayHeader:
		headers.add(0)
	if headerSettings.childNightHeader:
		headers.add(1)
	if headerSettings.adultDayHeader:
		headers.add(2)
	if headerSettings.adultNightHeader:
		headers.add(3)
	for cutsceneHeader in headerSettings.cutsceneHeaders:
		headers.add(cutsceneHeader.headerIndex)

	return headers

def exportAreaCommon(areaObj, transformMatrix, geolayout, collision, name):
	bpy.ops.object.select_all(action = 'DESELECT')
	areaObj.select_set(True)

	if not areaObj.noMusic:
		if areaObj.musicSeqEnum != 'Custom':
			musicSeq = areaObj.musicSeqEnum
		else:
			musicSeq = areaObj.music_seq
	else:
		musicSeq = None

	if areaObj.terrainEnum != 'Custom':
		terrainType = areaObj.terrainEnum
	else:
		terrainType = areaObj.terrain_type

	area = SM64_Area(areaObj.areaIndex, musicSeq, areaObj.music_preset, 
		terrainType, geolayout, collision, 
		[areaObj.warpNodes[i].to_c() for i in range(len(areaObj.warpNodes))],
		name, areaObj.startDialog if areaObj.showStartDialog else None)

	start_process_sm64_objects(areaObj, area, transformMatrix, False)

	return area

# These are all done in reference to refresh 8
def handleRefreshDiffModelIDs(modelID):
	if bpy.context.scene.refreshVer == 'Refresh 8' or \
		bpy.context.scene.refreshVer == 'Refresh 7':
		pass
	elif bpy.context.scene.refreshVer == 'Refresh 6':
		if modelID == 'MODEL_TWEESTER':
			modelID = 'MODEL_TORNADO'
	elif bpy.context.scene.refreshVer == 'Refresh 5' or \
		bpy.context.scene.refreshVer == 'Refresh 4' or \
		bpy.context.scene.refreshVer == 'Refresh 3':
		if modelID == 'MODEL_TWEESTER':
			modelID = 'MODEL_TORNADO'
		elif modelID == 'MODEL_WAVE_TRAIL':
			modelID = "MODEL_WATER_WAVES"
		elif modelID == 'MODEL_IDLE_WATER_WAVE':
			modelID = 'MODEL_WATER_WAVES_SURF'
		elif modelID == 'MODEL_SMALL_WATER_SPLASH':
			modelID = 'MODEL_SPOT_ON_GROUND'

	return modelID

def handleRefreshDiffSpecials(preset):
	if bpy.context.scene.refreshVer == 'Refresh 8' or \
		bpy.context.scene.refreshVer == 'Refresh 7' or \
		bpy.context.scene.refreshVer == 'Refresh 6' or \
		bpy.context.scene.refreshVer == 'Refresh 5' or \
		bpy.context.scene.refreshVer == 'Refresh 4' or \
		bpy.context.scene.refreshVer == 'Refresh 3':
		pass
	return preset

def handleRefreshDiffMacros(preset):
	if bpy.context.scene.refreshVer == 'Refresh 8' or \
		bpy.context.scene.refreshVer == 'Refresh 7' or \
		bpy.context.scene.refreshVer == 'Refresh 6' or \
		bpy.context.scene.refreshVer == 'Refresh 5' or \
		bpy.context.scene.refreshVer == 'Refresh 4' or \
		bpy.context.scene.refreshVer == 'Refresh 3':
		pass
	return preset

def start_process_sm64_objects(obj, area, transformMatrix, specialsOnly):
	#spaceRotation = mathutils.Quaternion((1, 0, 0), math.radians(90.0)).to_matrix().to_4x4()

	# We want translations to be relative to area obj, but rotation/scale to be world space
	translation, rotation, scale = obj.matrix_world.decompose()
	process_sm64_objects(obj, area, 
		mathutils.Matrix.Translation(translation), transformMatrix, specialsOnly)

def process_sm64_objects(obj, area, rootMatrix, transformMatrix, specialsOnly):
	translation, originalRotation, scale = \
			(transformMatrix @ rootMatrix.inverted() @ obj.matrix_world).decompose()

	finalTransform = mathutils.Matrix.Translation(translation) @ \
		originalRotation.to_matrix().to_4x4() @ \
		mathutils.Matrix.Diagonal(scale).to_4x4()

	# Hacky solution to handle Z-up to Y-up conversion
	rotation = originalRotation @ mathutils.Quaternion((1, 0, 0), math.radians(90.0))

	if obj.data is None:
		if obj.sm64_obj_type == 'Area Root' and obj.areaIndex != area.index:
			return
		if specialsOnly:
			if obj.sm64_obj_type == 'Special':
				preset = obj.sm64_special_enum if obj.sm64_special_enum != 'Custom' else obj.sm64_obj_preset
				preset = handleRefreshDiffSpecials(preset)
				area.specials.append(SM64_Special_Object(preset, translation, 
					rotation.to_euler() if obj.sm64_obj_set_yaw else None, 
					obj.sm64_obj_bparam if (obj.sm64_obj_set_yaw and obj.sm64_obj_set_bparam) else None))
			elif obj.sm64_obj_type == 'Water Box':
				checkIdentityRotation(obj, rotation, False)
				area.water_boxes.append(CollisionWaterBox(obj.waterBoxType, 
					translation, scale, obj.empty_display_size))
		else:
			if obj.sm64_obj_type == 'Object':
				modelID = obj.sm64_model_enum if obj.sm64_model_enum != 'Custom' else obj.sm64_obj_model
				modelID = handleRefreshDiffModelIDs(modelID)
				behaviour = func_map[bpy.context.scene.refreshVer][obj.sm64_behaviour_enum] if \
					obj.sm64_behaviour_enum != 'Custom' else obj.sm64_obj_behaviour
				area.objects.append(SM64_Object(modelID, translation, rotation.to_euler(), 
					behaviour, obj.sm64_obj_bparam, get_act_string(obj)))
			elif obj.sm64_obj_type == 'Macro':
				macro = obj.sm64_macro_enum if obj.sm64_macro_enum != 'Custom' else obj.sm64_obj_preset
				area.macros.append(SM64_Macro_Object(macro, translation, rotation.to_euler(), 
					obj.sm64_obj_bparam if obj.sm64_obj_set_bparam else None))
			elif obj.sm64_obj_type == 'Mario Start':
				mario_start = SM64_Mario_Start(obj.sm64_obj_mario_start_area, translation, rotation.to_euler())
				area.objects.append(mario_start)
				area.mario_start = mario_start
			elif obj.sm64_obj_type == 'Trajectory':
				pass
			elif obj.sm64_obj_type == 'Whirpool':
				area.objects.append(SM64_Whirpool(obj.whirlpool_index, 
					obj.whirpool_condition, obj.whirpool_strength, translation))
			elif obj.sm64_obj_type == 'Camera Volume':
				checkIdentityRotation(obj, rotation, True)
				if obj.cameraVolumeGlobal:
					triggerIndex = -1
				else:
					triggerIndex = area.index
				area.cameraVolumes.append(CameraVolume(triggerIndex, obj.cameraVolumeFunction,
					translation, rotation.to_euler(), scale, obj.empty_display_size))

	elif not specialsOnly and isCurveValid(obj):
		area.splines.append(convertSplineObject(area.name + '_spline_' + obj.name , obj, finalTransform))
			

	for child in obj.children:
		process_sm64_objects(child, area, rootMatrix, transformMatrix, specialsOnly)

def get_act_string(obj):
	if obj.sm64_obj_use_act1 and obj.sm64_obj_use_act2 and obj.sm64_obj_use_act3 and \
		obj.sm64_obj_use_act4 and obj.sm64_obj_use_act5 and obj.sm64_obj_use_act6:
		return 0x1F
	elif not obj.sm64_obj_use_act1 and not obj.sm64_obj_use_act2 and not obj.sm64_obj_use_act3 and \
		not obj.sm64_obj_use_act4 and not obj.sm64_obj_use_act5 and not obj.sm64_obj_use_act6:
		return 0
	else:
		data = ''
		if obj.sm64_obj_use_act1:
			data += (" | " if len(data) > 0 else '') + 'ACT_1'
		if obj.sm64_obj_use_act2:
			data += (" | " if len(data) > 0 else '') + 'ACT_2'
		if obj.sm64_obj_use_act3:
			data += (" | " if len(data) > 0 else '') + 'ACT_3'
		if obj.sm64_obj_use_act4:
			data += (" | " if len(data) > 0 else '') + 'ACT_4'
		if obj.sm64_obj_use_act5:
			data += (" | " if len(data) > 0 else '') + 'ACT_5'
		if obj.sm64_obj_use_act6:
			data += (" | " if len(data) > 0 else '') + 'ACT_6'
		return data

class OOTObjectPanel(bpy.types.Panel):
	bl_label = "Object Inspector"
	bl_idname = "OBJECT_PT_OOT_Object_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return context.scene.gameEditorMode == "OOT" and (context.object is not None and context.object.data is None)

	def draw(self, context):
		box = self.layout.box()
		box.box().label(text = 'OOT Object Inspector')
		obj = context.object
		prop_split(box, obj, 'ootEmptyType', 'Object Type')
		if obj.ootEmptyType == 'Actor':
			drawActorProperty(box, obj.ootActorProperty)
		
		elif obj.ootEmptyType == 'Transition Actor':
			drawTransitionActorProperty(box, obj.ootTransitionActorProperty)

		elif obj.ootEmptyType == 'Water Box':
			drawWaterBoxProperty(box, obj.ootWaterBoxProperty)

		elif obj.ootEmptyType == 'Scene':
			drawSceneHeaderProperty(box, obj.ootSceneHeader, None, None)
			drawAlternateSceneHeaderProperty(box, obj.ootAlternateSceneHeaders)

		elif obj.ootEmptyType == 'Room':
			drawRoomHeaderProperty(box, obj.ootRoomHeader, None, None)
			drawAlternateRoomHeaderProperty(box, obj.ootAlternateRoomHeaders)
		
		elif obj.ootEmptyType == 'Entrance':
			drawEntranceProperty(box, obj)

		elif obj.ootEmptyType == "Cull Volume":
			drawCullVolumeProperty(box, obj)
		
		elif obj.ootEmptyType == 'None':
			box.box().label(text = 'This can be used as an empty transform node in a geolayout hierarchy.')

def drawCullVolumeProperty(box, obj):
	box.label(text = "No rotation allowed.")

def onUpdateObjectType(self, context):
	if self.sm64_obj_type == 'Water Box':
		self.empty_display_type = "CUBE"

def getCustomProperty(data, prop):
	value = getattr(data, prop)
	return value if value != "Custom" else getattr(data, prop + str("Custom"))

class OOTWaterBoxProperty(bpy.types.PropertyGroup):
	lighting : bpy.props.EnumProperty(
		name = 'Lighting', items = ootEnumWaterBoxLighting, default = 'Default')
	lightingCustom : bpy.props.StringProperty(name = 'Lighting Custom', default = '0x00')
	camera : bpy.props.EnumProperty(
		name = "Camera Mode", items = ootEnumWaterBoxCamera, default = "Default")
	cameraCustom : bpy.props.StringProperty(name = "Camera Mode Custom", default = "0x00")

def drawWaterBoxProperty(layout, waterBoxProp):
	box = layout.box()
	box.box().label(text = "Properties")
	drawEnumWithCustom(box, waterBoxProp, 'lighting', "Lighting", "")
	drawEnumWithCustom(box, waterBoxProp, 'camera', "Camera", "")
	box.label(text = "Water box area defined by top face of box shaped empty.")
	box.label(text = "No rotation allowed.")

oot_obj_classes = (
	OOT_SearchActorIDEnumOperator,
	OOT_SearchMusicSeqEnumOperator,
	OOT_SearchObjectEnumOperator,
	OOTLightProperty,
	OOTEntranceProperty,
	OOTObjectProperty,
	OOTExitProperty,

	OOTActorHeaderItemProperty,
	OOTActorHeaderProperty,
	OOTActorProperty,
	OOTTransitionActorProperty,

	OOTSceneHeaderProperty,
	OOTAlternateSceneHeaderProperty,

	OOTRoomHeaderProperty,
	OOTAlternateRoomHeaderProperty,
	OOTWaterBoxProperty,
)

oot_obj_panel_classes = (
	OOTObjectPanel,
)

def oot_obj_panel_register():
	for cls in oot_obj_panel_classes:
		register_class(cls)

def oot_obj_panel_unregister():
	for cls in oot_obj_panel_classes:
		unregister_class(cls)

def oot_obj_register():
	for cls in oot_obj_classes:
		register_class(cls)

	bpy.types.Object.ootEmptyType = bpy.props.EnumProperty(
		name = 'OOT Object Type', items = ootEnumEmptyType, default = 'None', update = onUpdateObjectType)
	
	bpy.types.Object.ootActorProperty = bpy.props.PointerProperty(type = OOTActorProperty)
	bpy.types.Object.ootTransitionActorProperty = bpy.props.PointerProperty(type = OOTTransitionActorProperty)
	bpy.types.Object.ootWaterBoxProperty = bpy.props.PointerProperty(type = OOTWaterBoxProperty)
	bpy.types.Object.ootRoomHeader = bpy.props.PointerProperty(type = OOTRoomHeaderProperty)
	bpy.types.Object.ootSceneHeader = bpy.props.PointerProperty(type = OOTSceneHeaderProperty)
	bpy.types.Object.ootAlternateSceneHeaders = bpy.props.PointerProperty(type = OOTAlternateSceneHeaderProperty)
	bpy.types.Object.ootAlternateRoomHeaders = bpy.props.PointerProperty(type = OOTAlternateRoomHeaderProperty)
	bpy.types.Object.ootEntranceProperty = bpy.props.PointerProperty(type = OOTEntranceProperty)


def oot_obj_unregister():
	
	del bpy.types.Object.ootEmptyType

	del bpy.types.Object.ootActorProperty 
	del bpy.types.Object.ootTransitionActorProperty 
	del bpy.types.Object.ootRoomHeader
	del bpy.types.Object.ootSceneHeader
	del bpy.types.Object.ootWaterBoxType
	del bpy.types.Object.ootAlternateSceneHeaders
	del bpy.types.Object.ootAlternateRoomHeaders

	for cls in reversed(oot_obj_classes):
		unregister_class(cls)