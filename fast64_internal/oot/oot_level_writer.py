from ..f3d.f3d_gbi import *
from ..f3d.f3d_writer import *

from .oot_constants import *
from .oot_level import *
from .oot_level_classes import *
from .oot_utility import *
from .oot_f3d_writer import *
#from .oot_collision import *

from ..utility import *

from bpy.utils import register_class, unregister_class
from io import BytesIO
import bpy, bmesh, os, math, re, shutil, mathutils


#class OOTBox:
#	def __init__(self):
#		self.minBounds = [-2**8, -2**8]
#		self.maxBounds = [2**8 - 1, 2**8 - 1]


class OOTObjectCategorizer:
	def __init__(self):
		self.sceneObj = None
		self.roomObjs = []
		self.actors = []
		self.transitionActors = []
		self.meshes = []
		self.entrances = []
		self.waterBoxes = []

	def sortObjects(self, allObjs):
		for obj in allObjs:
			if obj.data is None:
				if obj.ootEmptyType == "Actor":
					self.actors.append(obj)
				elif obj.ootEmptyType == "Transition Actor":
					self.transitionActors.append(obj)
				elif obj.ootEmptyType == "Entrance":
					self.entrances.append(obj)
				elif obj.ootEmptyType == "Water Box":
					self.waterBoxes.append(obj)
				elif obj.ootEmptyType == "Room":
					self.roomObjs.append(obj)
				elif obj.ootEmptyType == "Scene":
					self.sceneObj = obj
			elif isinstance(obj.data, bpy.types.Mesh):
				self.meshes.append(obj)

# This also sets all origins relative to the scene object.
def ootDuplicateHierarchy(obj, ignoreAttr, includeEmpties, objectCategorizer):
	# Duplicate objects to apply scale / modifiers / linked data
	bpy.ops.object.select_all(action = 'DESELECT')
	ootSelectMeshChildrenOnly(obj, includeEmpties)
	obj.select_set(True)
	bpy.context.view_layer.objects.active = obj
	bpy.ops.object.duplicate()
	try:
		tempObj = bpy.context.view_layer.objects.active
		allObjs = bpy.context.selected_objects
		bpy.ops.object.make_single_user(obdata = True)
		bpy.ops.object.transform_apply(location = False, 
			rotation = True, scale = True, properties =  False)
		
		objectCategorizer.sortObjects(allObjs)
		meshObjs = objectCategorizer.meshes
		for selectedObj in meshObjs:
			bpy.ops.object.select_all(action = 'DESELECT')
			selectedObj.select_set(True)
			bpy.context.view_layer.objects.active = selectedObj
			for modifier in selectedObj.modifiers:
				bpy.ops.object.modifier_apply(modifier=modifier.name)
		for selectedObj in meshObjs:
			setOrigin(obj, selectedObj)
		if ignoreAttr is not None:
			for selectedObj in meshObjs:
				if getattr(selectedObj, ignoreAttr):
					for child in selectedObj.children:
						bpy.ops.object.select_all(action = 'DESELECT')
						child.select_set(True)
						bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
						selectedObj.parent.select_set(True)
						bpy.ops.object.parent_set(keep_transform = True)
					selectedObj.parent = None
		return tempObj, allObjs
	except Exception as e:
		cleanupDuplicatedObjects(allObjs)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		raise Exception(str(e))

def ootSelectMeshChildrenOnly(obj, includeEmpties):
	isMesh = isinstance(obj.data, bpy.types.Mesh)
	isEmpty = (obj.data is None) and includeEmpties
	if (isMesh or isEmpty):
		obj.select_set(True)
		obj.original_name = obj.name
	for child in obj.children:
		ootSelectMeshChildrenOnly(child, includeEmpties)

def ootCleanupScene(originalSceneObj, allObjs):
	cleanupDuplicatedObjects(allObjs)
	originalSceneObj.select_set(True)
	bpy.context.view_layer.objects.active = originalSceneObj

def ootExportSceneToC(originalSceneObj, transformMatrix, 
	f3dType, isHWv1, sceneName, DLFormat, convertTextureData, exportPath, isCustomExport):
	scene = ootConvertScene(originalSceneObj, transformMatrix, 
		f3dType, isHWv1, sceneName, DLFormat, convertTextureData)
	
	print(list(scene.rooms.items())[0][1].mesh.model.to_c(False, False, "test", OOTGfxFormatter(ScrollMethod.Vertex)))

	#return scene.toC()

def readSceneData(scene, sceneHeader, alternateSceneHeaders):
	scene.globalObject = getCustomProperty(sceneHeader, "globalObject")
	scene.naviCup = getCustomProperty(sceneHeader, "naviCup")
	scene.skyboxID = getCustomProperty(sceneHeader, "skyboxID")
	scene.skyboxCloudiness = getCustomProperty(sceneHeader, "skyboxCloudiness")
	scene.skyboxLighting = getCustomProperty(sceneHeader, "skyboxLighting")
	scene.mapLocation = getCustomProperty(sceneHeader, "mapLocation")
	scene.cameraMode = getCustomProperty(sceneHeader, "cameraMode")
	scene.musicSeq = getCustomProperty(sceneHeader, "musicSeq")
	scene.nightSeq = getCustomProperty(sceneHeader, "nightSeq")

	for lightProp in sceneHeader.lightList:
		scene.lights.append(getLightData(lightProp))

	for exitProp in sceneHeader.exitList:
		scene.exitList.append(getExitData(exitProp))

	if alternateSceneHeaders is not None:
		if not alternateSceneHeaders.childNightHeader.usePreviousHeader:
			scene.childNightHeader = OOTScene(scene.name + "_childNight", scene.model)
			readSceneData(scene.childNightHeader, alternateSceneHeaders.childNightHeader, None)

		if not alternateSceneHeaders.adultDayHeader.usePreviousHeader:
			scene.adultDayHeader = OOTScene(scene.name + "_adultDay", scene.model)
			readSceneData(scene.adultDayHeader, alternateSceneHeaders.adultDayHeader, None)

		if not alternateSceneHeaders.adultNightHeader.usePreviousHeader:
			scene.adultNightHeader = OOTScene(scene.name + "_adultNight", scene.model)
			readSceneData(scene.adultNightHeader, alternateSceneHeaders.adultNightHeader, None)

		for i in range(len(alternateSceneHeaders.cutsceneHeaders)):
			cutsceneHeaderProp = alternateSceneHeaders.cutsceneHeaders[i]
			cutsceneHeader = OOTScene(scene.name + "_cutscene" + str(i), scene.model)
			readSceneData(cutsceneHeader, cutsceneHeaderProp, None)
			scene.cutsceneHeaders.append(cutsceneHeader)

def getExitData(exitProp):
	if exitProp.exitIndex != "Custom":
		raise PluginError("Exit index enums not implemented yet.")
	return OOTExit(exitProp.exitIndexCustom)

def getLightData(lightProp):
	light = OOTLight()
	light.ambient = lightProp.ambient
	if lightProp.useCustomDiffuse0:
		if lightProp.diffuse0Custom is None:
			raise PluginError("Error: Diffuse 0 light object not set in a scene lighting property.")
		light.diffuse0 = getLightColor(lightProp.diffuse0Custom.color)
		light.diffuseDir0 = getLightRotation(lightProp.diffuse0Custom)
	else:
		light.diffuse0 = getLightColor(lightProp.diffuse0)
		light.diffuseDir0 = [0x49, 0x49, 0x49]

	if lightProp.useCustomDiffuse1:
		if lightProp.diffuse1Custom is None:
			raise PluginError("Error: Diffuse 1 light object not set in a scene lighting property.")
		light.diffuse1 = getLightColor(lightProp.diffuse1Custom.color)
		light.diffuseDir1 = getLightRotation(lightProp.diffuse1Custom)
	else:
		light.diffuse1 = getLightColor(lightProp.diffuse1)
		light.diffuseDir1 = [0xB7, 0xB7, 0xB7]

	light.fogColor = lightProp.fogColor
	light.fogDistance = lightProp.fogDistance
	light.transitionSpeed = lightProp.transitionSpeed
	light.drawDistance = lightProp.drawDistance
	return light

def readRoomData(room, roomHeader, alternateRoomHeaders):
	room.roomIndex = roomHeader.roomIndex
	room.disableSunSongEffect = roomHeader.disableSunSongEffect
	room.disableActionJumping = roomHeader.disableActionJumping
	room.disableWarpSongs = roomHeader.disableWarpSongs
	room.showInvisibleActors = roomHeader.showInvisibleActors
	room.linkIdleMode = getCustomProperty(roomHeader, "linkIdleMode")
	room.linkIdleModeCustom = roomHeader.linkIdleModeCustom
	room.setWind = roomHeader.setWind
	room.windVector = normToSigned8Vector(mathutils.Vector(roomHeader.windVector).normalized())
	room.windStrength = int(0xFF * max(mathutils.Vector(roomHeader.windVector).length, 1))
	if roomHeader.leaveTimeUnchanged:
		room.timeValue = "0xFFFF"
	else:
		room.timeValue = "0x" + format(roomHeader.timeHours, 'X') + format(roomHeader.timeMinutes, 'X')
	room.timeSpeed = min(-128, max(127, int(roomHeader.timeSpeed * 0xA)))
	room.disableSkybox = roomHeader.disableSkybox
	room.disableSunMoon = roomHeader.disableSunMoon
	room.echo = roomHeader.echo
	room.objectList.extend([item.objectID for item in roomHeader.objectList])

	if alternateRoomHeaders is not None:
		if not alternateRoomHeaders.childNightHeader.usePreviousHeader:
			room.childNightHeader = OOTRoom(room.name + "_childNight", room.model)
			readRoomData(room.childNightHeader, alternateRoomHeaders.childNightHeader, None)

		if not alternateRoomHeaders.adultDayHeader.usePreviousHeader:
			room.adultDayHeader = OOTRoom(room.name + "_adultDay", room.model)
			readRoomData(room.adultDayHeader, alternateRoomHeaders.adultDayHeader, None)

		if not alternateRoomHeaders.adultNightHeader.usePreviousHeader:
			room.adultNightHeader = OOTRoom(room.name + "_adultNight", room.model)
			readRoomData(room.adultNightHeader, alternateRoomHeaders.adultNightHeader, None)

		for i in range(len(alternateRoomHeaders.cutsceneHeaders)):
			cutsceneHeaderProp = alternateRoomHeaders.cutsceneHeaders[i]
			cutsceneHeader = OOTRoom(room.name + "_cutscene" + str(i), room.mesh.model)
			readRoomData(cutsceneHeader, cutsceneHeaderProp, None)
			room.cutsceneHeaders.append(cutsceneHeader)

def ootConvertScene(originalSceneObj, transformMatrix, 
	f3dType, isHWv1, sceneName, DLFormat, convertTextureData):

	if originalSceneObj.data is not None or originalSceneObj.ootEmptyType != "Scene":
		raise PluginError(originalSceneObj.name + " is not an empty with the \"Scene\" empty type.")

	sceneObj, allObjs = \
		ootDuplicateHierarchy(originalSceneObj, 'ignore_render', True, OOTObjectCategorizer())

	roomObjs = [child for child in sceneObj.children if child.data is None and child.ootEmptyType == 'Room']
	if len(roomObjs) == 0:
		raise PluginError("The scene has no child empties with the 'Room' empty type.")

	try:
		scene = OOTScene(sceneName, FModel(f3dType, isHWv1, sceneName + '_dl', DLFormat))
		readSceneData(scene, sceneObj.ootSceneHeader, sceneObj.ootAlternateSceneHeaders)
		# TODO: handle entrances, exits
		# TODO: handle collision

		processedRooms = set()
		for roomObj in roomObjs:
			roomIndex = roomObj.ootRoomHeader.roomIndex
			if roomIndex in processedRooms:
				raise PluginError("Error: room index " + str(roomIndex) + " is used more than once.")
			processedRooms.add(roomIndex)
			roomName = 'room_' + str(roomIndex)
			room = scene.addRoom(roomIndex, roomName, roomObj.ootRoomHeader.meshType)
			readRoomData(room, roomObj.ootRoomHeader, roomObj.ootAlternateRoomHeaders)

			ootProcessMesh(room.mesh, None, sceneObj, roomObj, transformMatrix, convertTextureData)
			ootProcessEmpties(scene, room, sceneObj, roomObj, transformMatrix)

		scene.validateStartPositions()

		ootCleanupScene(originalSceneObj, allObjs)

	except Exception as e:
		ootCleanupScene(originalSceneObj, allObjs)
		raise Exception(str(e))

	return scene

# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
# When we duplicated obj hierarchy we stripped all ignore_renders from hierarchy.
def ootProcessMesh(roomMesh, roomMeshGroup, sceneObj, obj, transformMatrix, convertTextureData):

	relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
	translation, rotation, scale = relativeTransform.decompose()

	if obj.data is None and obj.ootEmptyType == "Cull Volume":
		roomMeshGroup = roomMesh.addMeshGroup(BoxEmpty(
			ootConvertTranslation(translation), scale, obj.empty_display_size))

	elif isinstance(obj.data, bpy.types.Mesh):
		meshData = saveStaticModel(roomMesh.model, obj, transformMatrix, obj.name, 
			roomMesh.model.DLFormat, convertTextureData, False)
		if roomMeshGroup is None:
			roomMeshGroup = roomMesh.addMeshGroup(None)
		roomMeshGroup.addDLCall(meshData.mesh.draw, obj.ootDrawLayer)

	alphabeticalChildren = sorted(obj.children, key = lambda childObj: childObj.original_name.lower())
	for childObj in alphabeticalChildren:
		ootProcessMesh(roomMesh, roomMeshGroup, sceneObj, childObj, transformMatrix, convertTextureData)

def ootProcessEmpties(scene, room, sceneObj, obj, transformMatrix):
	relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
	translation, rotation, scale = relativeTransform.decompose()

	translation = ootConvertTranslation(translation)
	rotation = ootConvertRotation(rotation)

	if obj.data is None:
		if obj.ootEmptyType == "Actor":
			actorProp = obj.ootActorProperty
			room.actors.append(OOTActor(
				getCustomProperty(actorProp, 'actorID'), 
				translation, rotation, 
				actorProp.actorParam, 
				headerSettingsToIndices(actorProp.headerSettings)))
		elif obj.ootEmptyType == "Transition Actor":
			transActorProp = obj.ootTransitionActorProperty
			room.transitionActors.append(OOTTransitionActor(
				getCustomProperty(transActorProp, "actorID"),
				room.roomIndex, transActorProp.roomIndex,
				getCustomProperty(transActorProp, "cameraTransitionFront"),
				getCustomProperty(transActorProp, "cameraTransitionBack"),
				translation, rotation[1], 
				transActorProp.actorParam))
		elif obj.ootEmptyType == "Entrance":
			scene.entrances.append(OOTEntrance(room.roomIndex, obj.ootEntranceProperty.spawnIndex))
			scene.startPositions[obj.ootEntranceProperty.spawnIndex] = \
				OOTStartPosition(translation, rotation, "0xFFFF")
		elif obj.ootEmptyType == "Water Box":
			waterBoxProp = obj.ootWaterBoxProperty
			scene.collision.waterBoxes.append(OOTWaterBox(
				getCustomProperty(waterBoxProp, "lighting"),
				getCustomProperty(waterBoxProp, "camera"),
				translation, obj.scale, obj.empty_display_size))
	
	for childObj in obj.children:
		ootProcessEmpties(scene, room, sceneObj, childObj, transformMatrix)
	
class OOT_ExportScene(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_export_level'
	bl_label = "Export Scene"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		try:
			if context.mode != 'OBJECT':
				raise PluginError("Operator can only be used in object mode.")
			if len(context.selected_objects) == 0:
				raise PluginError("Object not selected.")
			obj = context.selected_objects[0]
			if obj.data is not None or obj.ootEmptyType != 'Scene':
				raise PluginError("The selected object is not an empty with the Scene type.")

			#obj = context.active_object

			scaleValue = bpy.context.scene.ootBlenderScale
			finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((
				scaleValue, scaleValue, scaleValue))).to_4x4()
		
		except Exception as e:
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set
		try:
			applyRotation([obj], math.radians(90), 'X')
			if context.scene.ootSceneCustomExport:
				exportPath = bpy.path.abspath(context.scene.ootSceneExportPath)
				levelName = context.scene.ootSceneName
			else:
				exportPath = bpy.path.abspath(context.scene.ootDecompPath)
				if context.scene.ootSceneOption == 'custom':
					levelName = context.scene.ootSceneName
				else:
					levelName = context.scene.ootSceneOption
			#if not context.scene.ootSceneCustomExport:
			#	applyBasicTweaks(exportPath)

			ootExportSceneToC(obj, finalTransform, 
				context.scene.f3d_type, context.scene.isHWv1, levelName, DLFormat.Static, 
					context.scene.saveTextures or bpy.context.scene.ignoreTextureRestrictions,
					exportPath, context.scene.ootSceneCustomExport)
			
			#ootExportScene(obj, finalTransform,
			#	context.scene.f3d_type, context.scene.isHWv1, levelName, exportPath, 
			#	context.scene.saveTextures or bpy.context.scene.ignoreTextureRestrictions, 
			#	context.scene.ootSceneCustomExport, DLFormat.Dynamic)
			self.report({'INFO'}, 'Success!')

			applyRotation([obj], math.radians(-90), 'X')
			#applyRotation(obj.children, math.radians(0), 'X')
			return {'FINISHED'} # must return a set

		except Exception as e:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			applyRotation([obj], math.radians(-90), 'X')

			obj.select_set(True)
			context.view_layer.objects.active = obj
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

class OOT_ExportScenePanel(bpy.types.Panel):
	bl_idname = "OOT_PT_export_level"
	bl_label = "OOT Scene Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'OOT'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.operator(OOT_ExportScene.bl_idname)
		if not bpy.context.scene.ignoreTextureRestrictions:
			col.prop(context.scene, 'saveTextures')
		col.prop(context.scene, 'ootSceneCustomExport')
		if context.scene.ootSceneCustomExport:
			prop_split(col, context.scene, 'ootSceneExportPath', 'Directory')
			prop_split(col, context.scene, 'ootSceneName', 'Name')
			customExportWarning(col)
		else:
			col.prop(context.scene, 'ootSceneOption')
			if context.scene.ootSceneOption == 'custom':
				levelName = context.scene.ootSceneName
				box = col.box()
				#box.label(text = 'Adding levels may require modifying the save file format.')
				#box.label(text = 'Check src/game/save_file.c.')
				prop_split(col, context.scene, 'ootSceneName', 'Name')
			else:
				levelName = context.scene.ootSceneOption
		
		for i in range(panelSeparatorSize):
			col.separator()

oot_level_classes = (
	OOT_ExportScene,
)

oot_level_panel_classes = (
	OOT_ExportScenePanel,
)

def oot_level_panel_register():
	for cls in oot_level_panel_classes:
		register_class(cls)

def oot_level_panel_unregister():
	for cls in oot_level_panel_classes:
		unregister_class(cls)

def oot_level_register():
	for cls in oot_level_classes:
		register_class(cls)
	
	bpy.types.Scene.ootSceneName = bpy.props.StringProperty(name = 'Name', default = 'bob')
	bpy.types.Scene.ootSceneOption = bpy.props.EnumProperty(name = "Scene", items = ootEnumSceneID, default = 'SCENE_YDAN')
	bpy.types.Scene.ootSceneExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.ootSceneCustomExport = bpy.props.BoolProperty(
		name = 'Custom Export Path')

def oot_level_unregister():
	for cls in reversed(oot_level_classes):
		unregister_class(cls)

	del bpy.types.Scene.ootSceneName
	del bpy.types.Scene.ootSceneExportPath
	del bpy.types.Scene.ootSceneCustomExport
	del bpy.types.Scene.ootSceneOption