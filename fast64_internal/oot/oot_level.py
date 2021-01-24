import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from .oot_scene_room import *
from .oot_actor import *
from .oot_collision import *
from .oot_spline import *
#from .oot_function_map import func_map
#from .oot_spline import *

from ..utility import *

def headerSettingsToIndices(headerSettings):

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

def getAltSceneObjProp(obj):
	while not (obj is None or (obj is not None and obj.data is None and obj.ootEmptyType == "Scene")):
		obj = obj.parent
	if obj is None:
		return None
	else:
		return obj.ootAlternateSceneHeaders

def getAltRoomObjProp(obj):
	while not (obj is None or (obj is not None and obj.data is None and obj.ootEmptyType == "Room")):
		obj = obj.parent
	if obj is None:
		return None
	else:
		return obj.ootAlternateRoomHeaders

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

		altSceneProp = getAltSceneObjProp(obj)
		altRoomProp = getAltRoomObjProp(obj)

		if obj.ootEmptyType == 'Actor':
			drawActorProperty(box, obj.ootActorProperty, altRoomProp)
		
		elif obj.ootEmptyType == 'Transition Actor':
			drawTransitionActorProperty(box, obj.ootTransitionActorProperty, altSceneProp)

		elif obj.ootEmptyType == 'Water Box':
			drawWaterBoxProperty(box, obj.ootWaterBoxProperty)

		elif obj.ootEmptyType == 'Scene':
			drawSceneHeaderProperty(box, obj.ootSceneHeader, None, None)
			if obj.ootSceneHeader.menuTab == 'Alternate':
				drawAlternateSceneHeaderProperty(box, obj.ootAlternateSceneHeaders)

		elif obj.ootEmptyType == 'Room':
			drawRoomHeaderProperty(box, obj.ootRoomHeader, None, None)
			if obj.ootRoomHeader.menuTab == 'Alternate':
				drawAlternateRoomHeaderProperty(box, obj.ootAlternateRoomHeaders)
		
		elif obj.ootEmptyType == 'Entrance':
			drawEntranceProperty(box, obj, altSceneProp)

		elif obj.ootEmptyType == "Cull Volume":
			drawCullVolumeProperty(box, obj)
		
		elif obj.ootEmptyType == 'None':
			box.label(text = 'Geometry can be parented to this.')

def drawCullVolumeProperty(box, obj):
	box.label(text = "No rotation allowed.")

def onUpdateObjectType(self, context):
	if self.sm64_obj_type == 'Water Box':
		self.empty_display_type = "CUBE"

oot_obj_classes = (
	OOT_SearchActorIDEnumOperator,
	OOT_SearchMusicSeqEnumOperator,
	OOT_SearchObjectEnumOperator,
	OOT_SearchSceneEnumOperator,
	OOTLightProperty,
	OOTLightGroupProperty,
	OOTObjectProperty,
	OOTExitProperty,

	OOTActorHeaderItemProperty,
	OOTActorHeaderProperty,
	OOTActorProperty,
	OOTTransitionActorProperty,
	OOTEntranceProperty,

	OOTSceneHeaderProperty,
	OOTAlternateSceneHeaderProperty,

	OOTRoomHeaderProperty,
	OOTAlternateRoomHeaderProperty,
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