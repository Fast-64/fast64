import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from .oot_lights import *
#from .oot_function_map import func_map
#from .oot_spline import *

from ..utility import *

class OOTActor:
	def __init__(self, actorID, position, rotation, actorParam, sceneSetups):
		self.actorID = actorID
		self.actorParam = actorParam
		self.sceneSetups = sceneSetups
		self.position = position
		self.rotation = rotation
	
	def toC(self):
		return '{' + str(self.actorID) + ', ' + \
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[2])))) + ', ' + \
			str(self.actorParam) + '},'

class OOTTransitionActor:
	def __init__(self, actorID, frontRoom, backRoom, frontCam, backCam, position, rotation, actorParam):
		self.actorID = actorID
		self.actorParam = actorParam
		self.frontRoom = frontRoom
		self.backRoom = backRoom
		self.frontCam = frontCam
		self.backCam = backCam
		self.position = position
		self.rotation = rotation
	
	# TODO: Fix y rotation?
	def toC(self):
		return '{' + str(self.frontRoom) + ', ' + \
			str(self.frontCam) + ', ' + \
			str(self.backRoom) + ', ' + \
			str(self.backCam) + ', ' + \
			str(self.actorID) + ', ' + \
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(self.actorParam) + '},'

class OOTEntrance:
	def __init__(self, position, rotation, room):
		self.room = room
		self.position = position
		self.rotation = rotation
	
	def toCStartPositions(self):
		return 'ENTRANCE(' +\
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[2])))) + ')'

	def toCEntranceList(self):
		pass

class OOTLight:
	def __init__(self):
		self.ambient = (0,0,0)
		self.diffuse0 = (0,0,0)
		self.diffuseDir0 = (0,0,0)
		self.diffuse1 = (0,0,0)
		self.diffuseDir1 = (0,0,0)
		self.fogColor = (0,0,0)
		self.fogDistance = 0
		self.transitionSpeed = 0
		self.drawDistance = 0

class OOTScene:
	def __init__(self, name, model):
		self.name = toAlnum(name)
		self.rooms = {}
		self.transitionActors = []
		self.entrances = []
		self.actors = []
		self.lights = []
		self.model = model
		self.collision = None

		# Skybox
		self.skyboxID = None
		self.skyboxCloudiness = None
		self.skyboxLighting = None

		# Camera
		self.mapLocation = None
		self.cameraMode = None

	def addRoom(self, roomIndex, roomName, meshType):
		roomModel = self.model.addSubModel(roomName + '_dl')
		room = OOTRoom(roomIndex, roomName, roomModel, meshType)
		if roomIndex in self.rooms:
			raise PluginError("Repeat room index " + str(roomIndex) + " for " + str(roomName))
		self.rooms[roomIndex] = room
		return room

class OOTRoomMesh:
	def __init__(self, roomName, meshType, model):
		self.roomName = roomName
		self.meshType = meshType
		self.meshEntries = []
		self.model = model

	def terminateDLs(self):
		for entry in self.meshEntries:
			entry.terminateDLs()

	def headerName(self):
		return str(self.roomName) + "_meshHeader"
	
	def entriesName(self):
		return str(self.roomName) + "_meshDListEntry"

	def headerToC(self):
		return "MeshHeader" + str(self.meshType) + " " + self.headerName() + ' = ' +\
			"{ {" + str(self.meshType) + "}, " + str(len(self.meshEntries)) + ", " +\
			"(u32)&" + self.entriesName() + ", (u32)&(" + self.entriesName() + ") + " +\
			"sizeof(" + self.entriesName() + ") };\n"
	
	def entriesToC(self):
		data = "MeshEntry" + str(self.meshType) + self.entriesName() + "[" + str(len(self.meshEntries)) + "] = \n{\n"
		for entry in self.meshEntries:
			data += '\t' + entry.entryToC(str(self.meshType)) + '\n'
		data += '};\n'
	
	def addMeshGroup(self, cullVolume):
		meshGroup = OOTRoomMeshGroup(cullVolume, self.model.DLFormat, self.roomName, len(self.meshEntries))
		self.meshEntries.append(meshGroup)
		return meshGroup
	
	def currentMeshGroup(self):
		return self.meshEntries[-1]

class OOTRoomMeshGroup:
	def __init__(self, cullVolume, DLFormat, roomName, entryIndex):
		self.opaque = None
		self.transparent = None
		self.cullVolume = cullVolume
		self.DLFormat = DLFormat
		self.roomName = roomName
		self.entryIndex = entryIndex

	def entryName(self):
		return self.roomName + "_entry_" + str(self.entryIndex)
	
	def addDLCall(self, displayList, drawLayer):
		if drawLayer == 'Opaque':
			if self.opaque is None:
				self.opaque = GfxList(self.entryName() + '_opaque', GfxListTag.Draw, self.DLFormat)
			self.opaque.commands.append(SPDisplayList(displayList))
		elif drawLayer == "Transparent":
			if self.transparent is None:
				self.transparent = GfxList(self.entryName() + '_transparent', GfxListTag.Draw, self.DLFormat)
			self.transparent.commands.append(SPDisplayList(displayList))
		else:
			raise PluginError("Unhandled draw layer: " + str(drawLayer))

	def terminateDLs(self):
		if self.opaque is not None:
			self.opaque.commands.append(SPEndDisplayList())
		
		if self.transparent is not None:
			self.transparent.commands.append(SPEndDisplayList())
	
	def entryToC(self, meshType):
		opaqueName = self.opaque.name if self.opaque is not None else "0"
		transparentName = self.transparent.name if self.transparent is not None else "0"
		data = "{ "
		if meshType == "2":
			if self.cullVolume is None:
				data += "0x7FFF, 0x7FFF, 0x8000, 0x8000, "
			else:
				data += "(s16)" + str(self.cullVolume.high[0]) + ", (s16)" + str(self.cullVolume.high[1]) + ", "
				data += "(s16)" + str(self.cullVolume.low[0]) + ", (s16)" + str(self.cullVolume.low[1]) + ", "
		data += "(u32)" + opaqueName + ", (u32)" + transparentName + '},' 
	
	def DLtoC(self):
		data = ''
		if self.opaque is not None:
			data += self.opaque.to_c() + '\n'
		if self.transparent is not None:
			data += self.transparent.to_c() + '\n'
		return data

class OOTRoom:
	def __init__(self, index, name, model, meshType):
		self.name = toAlnum(name)
		self.collision = None
		self.index = index
		self.actors = []
		self.transitionActors = []
		self.water_boxes = []
		self.mesh = OOTRoomMesh(self.name, meshType, model)

		self.entrances = []
		self.exits = []
		self.pathways = []

		# Room behaviour
		self.disableSunSongEffect = False
		self.disableActionJumping = False
		self.disableWarpSongs = False
		self.showInvisibleActors = False
		self.linkIdleMode = None

		self.customBehaviourX = None
		self.customBehaviourY = None

		# Wind 
		self.setWind = False
		self.windVector = [0,0,0]
		self.windStrength = 0

		# Time
		self.timeValue = 0xFFFF
		self.timeSpeed = 0xA

		# Skybox
		self.disableSkybox = False
		self.disableSunMoon = False

		# Echo
		self.echo = 0x00

	def toCWindCommand(self):

		return "SET_WIND(" + '0x' + format(self.windVector[0], 'X') + ', ' +\
			'0x' + format(self.windVector[1], 'X') + ', ' +\
			'0x' + format(self.windVector[2], 'X') + ', ' +\
			'0x' + format(self.windStrength, 'X') + ')'

	def toCScript(self, includeRooms):
		data = ''
		data += '\tAREA(' + str(self.index) + ', ' + self.geolayout.name + '),\n'
		for warpNode in self.warpNodes:
			data += '\t\t' + warpNode + ',\n'
		for obj in self.objects:
			data += '\t\t' + obj.to_c() + ',\n'
		data += '\t\tTERRAIN(' + self.collision.name + '),\n'
		if includeRooms:
			data += '\t\tROOMS(' + self.collision.rooms_name() + '),\n'
		data += '\t\tMACRO_OBJECTS(' + self.macros_name() + '),\n'
		if self.music_seq is None:
			data += '\t\tSTOP_MUSIC(0),\n'
		else:
			data += '\t\tSET_BACKGROUND_MUSIC(' + self.music_preset + ', ' + self.music_seq + '),\n'
		if self.startDialog is not None:
			data += '\t\tSHOW_DIALOG(0x00, ' + self.startDialog + '),\n'
		data += '\t\tTERRAIN_TYPE(' + self.terrain_type + '),\n'
		data += '\tEND_AREA(),\n\n'
		return data
	
	def toCPathways(self):
		data = ''
		for spline in self.pathways:
			data += spline.to_c() + '\n'
		return data
	
	def toCDefSplines(self):
		data = ''
		for spline in self.splines:
			data += spline.to_c_def()
		return data

class OOTWaterBox(BoxEmpty):
	def __init__(self, waterBoxType, position, scale, emptyScale):
		self.waterBoxType = waterBoxType
		BoxEmpty.__init__(self, position, scale, emptyScale)
	
	def to_c(self):
		data = 'WATER_BOX(' + \
			str(self.waterBoxType) + ', ' + \
			str(int(round(self.low[0]))) + ', ' + \
			str(int(round(self.low[1]))) + ', ' + \
			str(int(round(self.high[0]))) + ', ' + \
			str(int(round(self.high[1]))) + ', ' + \
			str(int(round(self.height))) + '),\n'
		return data

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

class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_actor_id_enum_operator"
	bl_label = "Search Actor IDs"
	bl_property = "ootEnumActorID"
	bl_options = {'REGISTER', 'UNDO'} 

	ootEnumActorID : bpy.props.EnumProperty(items = ootEnumActorID, default = "ACTOR_PLAYER")

	def execute(self, context):
		context.object.ootActorProperty.actorID = self.ootEnumActorID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootEnumActorID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOT_SearchMusicSeqEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_music_seq_enum_operator"
	bl_label = "Search Music Sequence"
	bl_property = "ootMusicSeq"
	bl_options = {'REGISTER', 'UNDO'} 

	ootMusicSeq : bpy.props.EnumProperty(items = ootEnumMusicSeq, default = "NA_BGM_FIELD1")
	headerIndex : bpy.props.IntProperty(default = 0, min = 0)

	def execute(self, context):
		if self.headerIndex == 0:
			sceneHeader = context.object.ootSceneHeader
		elif self.headerIndex == 1:
			sceneHeader = context.object.ootAlternateSceneHeaders.childNightHeader
		elif self.headerIndex == 2:
			sceneHeader = context.object.ootAlternateSceneHeaders.adultDayHeader
		elif self.headerIndex == 3:
			sceneHeader = context.object.ootAlternateSceneHeaders.adultNightHeader
		else:
			sceneHeader = context.object.ootAlternateSceneHeaders.cutsceneHeaders[self.headerIndex - 4]

		sceneHeader.musicSeq = self.ootMusicSeq
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootMusicSeq)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOT_SearchObjectEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_object_enum_operator"
	bl_label = "Search Object ID"
	bl_property = "ootObjectID"
	bl_options = {'REGISTER', 'UNDO'} 

	ootObjectID : bpy.props.EnumProperty(items = ootEnumObjectID, default = "OBJECT_HUMAN")
	headerIndex : bpy.props.IntProperty(default = 0, min = 0)
	index : bpy.props.IntProperty(default = 0, min = 0)

	def execute(self, context):
		if self.headerIndex == 0:
			roomHeader = context.object.ootRoomHeader
		elif self.headerIndex == 1:
			roomHeader = context.object.ootAlternateRoomHeaders.childNightHeader
		elif self.headerIndex == 2:
			roomHeader = context.object.ootAlternateRoomHeaders.adultDayHeader
		elif self.headerIndex == 3:
			roomHeader = context.object.ootAlternateRoomHeaders.adultNightHeader
		else:
			roomHeader = context.object.ootAlternateRoomHeaders.cutsceneHeaders[self.headerIndex - 4]

		roomHeader.objectList[self.index].objectID = self.ootObjectID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootObjectID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

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
			drawEntranceProperty(box, obj.OOTEntranceProperty, None, None)
		
		elif obj.ootEmptyType == 'None':
			box.box().label(text = 'This can be used as an empty transform node in a geolayout hierarchy.')

def onUpdateObjectType(self, context):
	if self.sm64_obj_type == 'Water Box':
		self.empty_display_type = "CUBE"

def getCustomProperty(data, prop):
	value = getattr(data, prop)
	return value if value != "Custom" else getattr(data, prop + str("Custom"))

class OOTSceneHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	usePreviousHeader : bpy.props.BoolProperty(name = "Use Previous Header", default = True)

	globalObject : bpy.props.EnumProperty(name = "Global Object", default = "gameplay_field_keep", items = ootEnumGlobalObject)
	globalObjectCustom : bpy.props.StringProperty(name = "Global Object Custom", default = "0x00")
	naviCup : bpy.props.EnumProperty(name = "Navi Hints", default = 'elf_message_field', items = ootEnumNaviHints)
	naviCupCustom : bpy.props.StringProperty(name = "Navi Hints Custom", default = '0x00')

	skyboxID : bpy.props.EnumProperty(name = "Skybox", items = ootEnumSkybox, default = "None")
	skyboxIDCustom : bpy.props.StringProperty(name = "Skybox ID", default = '0')
	skyboxCloudiness : bpy.props.EnumProperty(name = "Cloudiness", items = ootEnumCloudiness, default = "Sunny")
	skyboxCloudinessCustom : bpy.props.StringProperty(name = "Cloudiness ID", default = '0x00')
	skyboxLighting : bpy.props.EnumProperty(name = "Skybox Lighting", items = ootEnumSkyboxLighting, default = "Time Of Day")
	skyboxLightingCustom : bpy.props.StringProperty(name = "Skybox Lighting Custom", default = '0x00')

	mapLocation : bpy.props.EnumProperty(name = "Map Location", items = ootEnumMapLocation, default = "Hyrule Field")
	mapLocationCustom : bpy.props.StringProperty(name = "Skybox Lighting Custom", default = '0x00')
	cameraMode : bpy.props.EnumProperty(name = "Camera Mode", items = ootEnumCameraMode, default = "Default")
	cameraModeCustom : bpy.props.StringProperty(name = "Camera Mode Custom", default = '0x00')

	musicSeq : bpy.props.EnumProperty(name = "Music Sequence", items = ootEnumMusicSeq, default = 'NA_BGM_FIELD1')
	musicSeqCustom : bpy.props.StringProperty(name = "Music Sequence ID", default = '0x00')
	nightSeq : bpy.props.EnumProperty(name = "Nighttime SFX", items = ootEnumNightSeq, default = "Standard night [day and night cycle]")
	nightSeqCustom : bpy.props.StringProperty(name = "Nighttime SFX ID", default = '0x00')

	lightList : bpy.props.CollectionProperty(type = OOTLightProperty, name = 'Lighting List')

def drawSceneHeaderProperty(layout, sceneProp, dropdownLabel, headerIndex):
	if dropdownLabel is not None:
		layout.prop(sceneProp, 'expandTab', text = dropdownLabel, 
			icon = 'TRIA_DOWN' if sceneProp.expandTab else 'TRIA_RIGHT')
		if not sceneProp.expandTab:
			return

	if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
		layout.prop(sceneProp, "usePreviousHeader", text = "Use Previous Header")
		if sceneProp.usePreviousHeader:
			return

	general = layout.box()
	general.box().label(text = "General")
	drawEnumWithCustom(general, sceneProp, 'globalObject', "Global Object", "")
	drawEnumWithCustom(general, sceneProp, 'naviCup', "Navi Hints", "")

	skyboxAndSound = layout.box()
	skyboxAndSound.box().label(text = "Skybox And Sound")
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'skyboxID', "Skybox", "")
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'skyboxCloudiness', "Cloudiness", "")
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'musicSeq', "Music Sequence", "")
	musicSearch = skyboxAndSound.operator(OOT_SearchMusicSeqEnumOperator.bl_idname, icon = 'VIEWZOOM')
	musicSearch.headerIndex = headerIndex if headerIndex is not None else 0
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'nightSeq', "Nighttime SFX", "")

	cameraAndWorldMap = layout.box()
	cameraAndWorldMap.box().label(text = "Camera And World Map")
	drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'mapLocation', "Map Location", "")
	drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'cameraMode', "Camera Mode", "")

	lighting = layout.box()
	lighting.box().label(text = "Lighting List")
	drawAddButton(lighting, len(sceneProp.lightList), "Light", headerIndex)
	for i in range(len(sceneProp.lightList)):
		drawLightProperty(lighting, sceneProp.lightList[i], i, headerIndex)

	if headerIndex is not None and headerIndex > 3:
		drawCollectionOps(layout, headerIndex - 4, "Scene", None)

class OOTObjectProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	objectID : bpy.props.EnumProperty(items = ootEnumObjectID, default = 'OBJECT_HUMAN')

class OOTRoomHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	usePreviousHeader : bpy.props.BoolProperty(name = "Use Previous Header", default = True)

	roomIndex : bpy.props.IntProperty(name = 'Room Index', default = 0, min = 0)
	disableSunSongEffect : bpy.props.BoolProperty(name = "Disable Sun Song Effect")
	disableActionJumping : bpy.props.BoolProperty(name = "Disable Action Jumping")
	disableWarpSongs : bpy.props.BoolProperty(name = "Disable Warp Songs")
	showInvisibleActors : bpy.props.BoolProperty(name = "Show Invisible Actors")
	linkIdleMode : bpy.props.EnumProperty(name = "Link Idle Mode",items = ootEnumLinkIdle, default = "Default")
	linkIdleModeCustom : bpy.props.StringProperty(name = "Link Idle Mode Custom", default = '0x00')

	useCustomBehaviourX : bpy.props.BoolProperty(name = "Use Custom Behaviour X")
	useCustomBehaviourY : bpy.props.BoolProperty(name = "Use Custom Behaviour Y")

	customBehaviourX : bpy.props.StringProperty(name = 'Custom Behaviour X', default = '0x00')

	customBehaviourY : bpy.props.StringProperty(name = 'Custom Behaviour Y', default = '0x00')

	setWind : bpy.props.BoolProperty(name = "Set Wind")
	windVector : bpy.props.FloatVectorProperty(name = "Wind Vector", size = 3)

	leaveTimeUnchanged : bpy.props.BoolProperty(name = "Leave Time Unchanged", default = True)
	timeHours : bpy.props.IntProperty(name = "Hours", default = 0, min = 0, max = 23) #0xFFFE
	timeMinutes : bpy.props.IntProperty(name = "Minutes", default = 0, min = 0, max = 59)
	timeSpeed : bpy.props.FloatProperty(name = "Time Speed", default = 1, min = -13, max = 13) #0xA

	disableSkybox : bpy.props.BoolProperty(name = "Disable Skybox")
	disableSunMoon : bpy.props.BoolProperty(name = "Disable Sun/Moon")

	echo : bpy.props.StringProperty(name = "Echo", default = '0x00')

	objectList : bpy.props.CollectionProperty(type = OOTObjectProperty)

	meshType : bpy.props.EnumProperty(items = ootEnumMeshType, default = '0')

def drawRoomHeaderProperty(layout, roomProp, dropdownLabel, headerIndex):

	if dropdownLabel is not None:
		layout.prop(roomProp, 'expandTab', text = dropdownLabel, 
			icon = 'TRIA_DOWN' if roomProp.expandTab else 'TRIA_RIGHT')
		if not roomProp.expandTab:
			return

	if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
		layout.prop(roomProp, "usePreviousHeader", text = "Use Previous Header")
		if roomProp.usePreviousHeader:
			return

	if headerIndex is None or headerIndex == 0:
		prop_split(layout, roomProp, 'roomIndex', 'Room Index')
		prop_split(layout, roomProp, 'meshType', "Mesh Type")

	skyboxAndTime = layout.box()
	skyboxAndTime.box().label(text = "Skybox And Time")

	# Time
	skyboxAndTime.prop(roomProp, "leaveTimeUnchanged", text = "Leave Time Unchanged")
	if not roomProp.leaveTimeUnchanged:
		skyboxAndTime.label(text = "Time")
		timeRow = skyboxAndTime.row()
		timeRow.prop(roomProp, 'timeHours', text = 'Hours')
		timeRow.prop(roomProp, 'timeMinutes', text = 'Minutes')
		#prop_split(skyboxAndTime, roomProp, "timeValue", "Time Of Day")
	prop_split(skyboxAndTime, roomProp, "timeSpeed", "Time Speed")

	# Echo
	prop_split(skyboxAndTime, roomProp, "echo", "Echo")

	# Skybox
	skyboxAndTime.prop(roomProp, "disableSkybox", text = "Disable Skybox")
	skyboxAndTime.prop(roomProp, "disableSunMoon", text = "Disable Sun/Moon")

	# Wind 
	windBox = layout.box()
	windBox.box().label(text = 'Wind')
	windBox.prop(roomProp, "setWind", text = "Set Wind")
	if roomProp.setWind:
		prop_split(windBox, roomProp, "windVector", "Wind Vector")

	behaviourBox = layout.box()
	behaviourBox.box().label(text = 'Behaviour')
	behaviourBox.prop(roomProp, "disableSunSongEffect", text = "Disable Sun Song Effect")
	behaviourBox.prop(roomProp, "disableActionJumping", text = "Disable Action Jumping")
	behaviourBox.prop(roomProp, "disableWarpSongs", text = "Disable Warp Songs")
	behaviourBox.prop(roomProp, "showInvisibleActors", text = "Show Invisible Actors")
	drawEnumWithCustom(behaviourBox, roomProp, 'linkIdleMode', "Link Idle Mode", "")

	objBox = layout.box()
	objBox.box().label(text = "Objects")
	drawAddButton(objBox, len(roomProp.objectList), "Object", headerIndex)
	for i in range(len(roomProp.objectList)):
		drawObjectProperty(objBox, roomProp.objectList[i], headerIndex, i)

	if headerIndex is not None and headerIndex > 3:
		drawCollectionOps(layout, headerIndex - 4, "Room", None)

def drawObjectProperty(layout, objectProp, headerIndex, index):
	objItemBox = layout.box()
	objItemBox.prop(objectProp, 'expandTab', text = str(objectProp.objectID), 
		icon = 'TRIA_DOWN' if objectProp.expandTab else \
		'TRIA_RIGHT')
	if objectProp.expandTab:
		objItemBox.box().label(text = "ID: " + objectProp.objectID)
		#prop_split(objItemBox, objectProp, "objectID", name = "ID")
		objSearch = objItemBox.operator(OOT_SearchObjectEnumOperator.bl_idname, icon = 'VIEWZOOM')
		objSearch.headerIndex = headerIndex if headerIndex is not None else 0
		objSearch.index = index
		drawCollectionOps(objItemBox, index, "Object", headerIndex)

class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
	headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

class OOTActorHeaderProperty(bpy.types.PropertyGroup):
	inAllSceneSetups : bpy.props.BoolProperty(name = "Actor Exists In All Scene Setups", default = True)
	childDayHeader : bpy.props.BoolProperty(name = "Child Day Header", default = True)
	childNightHeader : bpy.props.BoolProperty(name = "Child Night Header", default = True)
	adultDayHeader : bpy.props.BoolProperty(name = "Adult Day Header", default = True)
	adultNightHeader : bpy.props.BoolProperty(name = "Adult Night Header", default = True)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTActorHeaderItemProperty)

def drawActorHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetup.prop(headerProp, "inAllSceneSetups", text = "Actor Exists In All Scene Setups")
	if not headerProp.inAllSceneSetups:
		headerSetupBox = headerSetup.box()
		headerSetupBox.prop(headerProp, 'childDayHeader', text = "Child Day")
		headerSetupBox.prop(headerProp, 'childNightHeader', text = "Child Night")
		headerSetupBox.prop(headerProp, 'adultDayHeader', text = "Adult Day")
		headerSetupBox.prop(headerProp, 'adultNightHeader', text = "Adult Night")
		drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Actor", None)
		for i in range(len(headerProp.cutsceneHeaders)):
			drawActorHeaderItemProperty(headerSetup, headerProp.cutsceneHeaders[i], i)

def drawActorHeaderItemProperty(layout, headerItemProp, index):
	box = layout.box()
	box.prop(headerItemProp, 'expandTab', text = 'Header ' + \
		str(headerItemProp.headerIndex), icon = 'TRIA_DOWN' if headerItemProp.expandTab else \
		'TRIA_RIGHT')
	if headerItemProp.expandTab:
		prop_split(box, headerItemProp, 'headerIndex', 'Header Index')
		drawCollectionOps(box, index, "Actor", None)
		
class OOTAlternateSceneHeaderProperty(bpy.types.PropertyGroup):
	childNightHeader : bpy.props.PointerProperty(name = "Child Night Header", type = OOTSceneHeaderProperty)
	adultDayHeader : bpy.props.PointerProperty(name = "Adult Day Header", type = OOTSceneHeaderProperty)
	adultNightHeader : bpy.props.PointerProperty(name = "Adult Night Header", type = OOTSceneHeaderProperty)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTSceneHeaderProperty)

def drawAlternateSceneHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetupBox = headerSetup.box()

	drawSceneHeaderProperty(headerSetupBox, headerProp.childNightHeader, "Child Night", 1)
	drawSceneHeaderProperty(headerSetupBox, headerProp.adultDayHeader, "Adult Day", 2)
	drawSceneHeaderProperty(headerSetupBox, headerProp.adultNightHeader, "Adult Night", 3)
	headerSetup.box().label(text = "Cutscene Headers")
	drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Scene", None)
	for i in range(len(headerProp.cutsceneHeaders)):
		box = headerSetup.box()
		drawSceneHeaderProperty(box, headerProp.cutsceneHeaders[i], "Header " + str(i + 4), i + 4)

class OOTAlternateRoomHeaderProperty(bpy.types.PropertyGroup):
	childNightHeader : bpy.props.PointerProperty(name = "Child Night Header", type = OOTRoomHeaderProperty)
	adultDayHeader : bpy.props.PointerProperty(name = "Adult Day Header", type = OOTRoomHeaderProperty)
	adultNightHeader : bpy.props.PointerProperty(name = "Adult Night Header", type = OOTRoomHeaderProperty)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTRoomHeaderProperty)

def drawAlternateRoomHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetupBox = headerSetup.box()

	drawRoomHeaderProperty(headerSetupBox, headerProp.childNightHeader, "Child Night", 1)
	drawRoomHeaderProperty(headerSetupBox, headerProp.adultDayHeader, "Adult Day", 2)
	drawRoomHeaderProperty(headerSetupBox, headerProp.adultNightHeader, "Adult Night", 3)
	headerSetup.box().label(text = "Cutscene Headers")
	drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Room", None)
	for i in range(len(headerProp.cutsceneHeaders)):
		box = headerSetup.box()
		drawRoomHeaderProperty(box, headerProp.cutsceneHeaders[i], "Header " + str(i + 4), i + 4)

class OOTActorProperty(bpy.types.PropertyGroup):
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
	headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

def drawActorProperty(layout, actorProp):
	#prop_split(layout, actorProp, 'actorID', 'Actor')
	actorIDBox = layout.box()
	actorIDBox.box().label(text = "Actor ID: " + actorProp.actorID)
	if actorProp.actorID == 'Custom':
		#actorIDBox.prop(actorProp, 'actorIDCustom', text = 'Actor ID')
		prop_split(actorIDBox, actorProp, 'actorIDCustom', 'Actor ID')

	actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon = 'VIEWZOOM')
	#layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
	prop_split(layout, actorProp, "actorParam", 'Actor Parameter')

	drawActorHeaderProperty(layout, actorProp.headerSettings)

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

class OOTEntranceProperty(bpy.types.PropertyGroup):
	scene : bpy.props.EnumProperty(items = ootEnumSceneID, default = "SCENE_YDAN")
	sceneCustom : bpy.props.StringProperty(default = "SCENE_YDAN")
	spawnIndex : bpy.props.IntProperty(min = 0)
	continueBGM : bpy.props.BoolProperty(default = False)
	displayTitleCard : bpy.props.BoolProperty(default = True)
	fadeInAnim : bpy.props.EnumProperty(items = ootEnumTransitionAnims, default = '0x02')
	fadeInAnimCustom : bpy.props.StringProperty(default = '0x02')
	fadeOutAnim : bpy.props.EnumProperty(items = ootEnumTransitionAnims, default = '0x02')
	fadeOutAnimCustom : bpy.props.StringProperty(default = '0x02')

def drawEntranceProperty(layout, entranceProp, obj):
	if obj.parent is not None and obj.parent.data is None and obj.parent.ootEmptyType == "Room":
		layout.label(text = 'Room Index: ' + str(obj.parent.ootRoomHeader.roomIndex))
	else:
		layout.label(text = "Entrance must be parented to a Room.")

	#box = layout.box()
	#box.box().label(text = "Properties")
	#drawEnumWithCustom(box, entranceProp, scene, "Scene", "")

class OOTTransitionActorProperty(bpy.types.PropertyGroup):
	roomIndex : bpy.props.IntProperty(min = 0)
	cameraTransitionFront : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionFrontCustom : bpy.props.StringProperty(default = '0x00')
	cameraTransitionBack : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionBackCustom : bpy.props.StringProperty(default = '0x00')
	
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumTransitionActorID, default = 'ACTOR_EN_DOOR')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_EN_DOOR')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

def drawTransitionActorProperty(layout, transActorProp):
	actorIDBox = layout.box()
	actorIDBox.box().label(text = "Properties")
	prop_split(actorIDBox, transActorProp, 'actorID', 'Actor')
	#actorIDBox.box().label(text = "Actor ID: " + transActorProp.actorID)
	if transActorProp.actorID == 'Custom':
		prop_split(actorIDBox, transActorProp, 'actorIDCustom', 'Actor ID')

	prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
	drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
	drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

	#layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
	prop_split(layout, transActorProp, "actorParam", 'Actor Parameter')
	
oot_obj_classes = (
	OOT_SearchActorIDEnumOperator,
	OOT_SearchMusicSeqEnumOperator,
	OOT_SearchObjectEnumOperator,
	OOTLightProperty,
	OOTEntranceProperty,
	OOTObjectProperty,

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