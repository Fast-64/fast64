from ..f3d.f3d_gbi import *
from ..f3d.f3d_writer import *

from .oot_constants import *
from .oot_level import *
from .oot_utility import *
#from .oot_collision import *

from ..utility import *

from bpy.utils import register_class, unregister_class
from io import BytesIO
import bpy, bmesh, os, math, re, shutil


#class OOTBox:
#	def __init__(self):
#		self.minBounds = [-2**8, -2**8]
#		self.maxBounds = [2**8 - 1, 2**8 - 1]

def ootDuplicateHierarchy(obj, ignoreAttr, includeEmpties):
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
		for selectedObj in allObjs:
			bpy.ops.object.select_all(action = 'DESELECT')
			selectedObj.select_set(True)
			bpy.context.view_layer.objects.active = selectedObj
			for modifier in selectedObj.modifiers:
				bpy.ops.object.modifier_apply(modifier=modifier.name)
		for selectedObj in allObjs:
			if ignoreAttr is not None and getattr(selectedObj, ignoreAttr):
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

	#return scene.toC()

def readSceneData(scene, sceneHeader):
	scene.globalObject = getCustomProperty(sceneHeader, "globalObject")
	scene.naviCup = getCustomProperty(sceneHeader, "naviCup")
	scene.skyboxID = getCustomProperty(sceneHeader, "skyboxID")
	scene.skyboxCloudiness = getCustomProperty(sceneHeader, "skyboxCloudiness")
	scene.skyboxLighting = getCustomProperty(sceneHeader, "skyboxLighting")
	scene.mapLocation = getCustomProperty(sceneHeader, "mapLocation")
	scene.cameraMode = getCustomProperty(sceneHeader, "cameraMode")
	scene.musicSeq = getCustomProperty(sceneHeader, "musicSeq")
	scene.nightSeq = getCustomProperty(sceneHeader, "nightSeq")

def getLightData(lightProp):
	light = OOTLight()
	light.ambient = lightProp.ambient
	light.diffuse0 = getLightColor(lightProp.diffuse0.color)
	light.diffuseDir0 = getLightRotation(lightProp.diffuse0)
	light.diffuse1 = getLightColor(lightProp.diffuse1.color)
	light.diffuseDir1 = getLightRotation(lightProp.diffuse1)
	light.fogColor = lightProp.fogColor
	light.fogDistance = lightProp.fogDistance
	light.transitionSpeed = lightProp.transitionSpeed
	light.drawDistance = lightProp.drawDistance
	return light

def readRoomData(room, roomHeader):
	room.roomIndex = roomHeader.roomIndex
	room.disableSunSongEffect = roomHeader.disableSunSongEffect
	room.disableActionJumping = roomHeader.disableActionJumping
	room.disableWarpSongs = roomHeader.disableWarpSongs
	room.showInvisibleActors = roomHeader.showInvisibleActors
	room.linkIdleMode = getCustomProperty(roomHeader, "linkIdleMode")
	room.linkIdleModeCustom = roomHeader.linkIdleModeCustom
	room.setWind = roomHeader.setWind
	room.windVector = normToSigned8Vector(roomHeader.windVector.normalized())
	room.windStrength = int(0xFF * max(roomHeader.windVector.length, 1))
	if roomHeader.leaveTimeUnchanged:
		room.timeValue = "0xFFFF"
	else:
		room.timeValue = "0x" + format(roomHeader.timeHours, 'X') + format(roomHeader.timeMinutes, 'X')
	room.timeSpeed = min(-128, max(127, int(roomHeader.timeSpeed * 0xA)))
	room.disableSkybox = roomHeader.disableSkybox
	room.disableSunMoon = roomHeader.disableSunMoon
	room.echo = roomHeader.echo
	room.objectList.extend([item.objectID for item in roomHeader.objectList])

def ootConvertScene(originalSceneObj, transformMatrix, 
	f3dType, isHWv1, sceneName, DLFormat, convertTextureData):

	if originalSceneObj.data is not None or originalSceneObj.ootEmptyType != "Scene":
		raise PluginError(originalSceneObj.name + " is not an empty with the \"Scene\" empty type.")

	sceneObj, allObjs = \
		ootDuplicateHierarchy(originalSceneObj, 'ignore_render', True)

	roomObjs = [child for child in sceneObj.children if child.data is None and child.ootEmptyType == 'Room']
	if len(roomObjs) == 0:
		raise PluginError("The scene has no child empties with the 'Room' empty type.")

	scene = OOTScene(sceneName, FModel(f3dType, isHWv1, sceneName + '_dl', DLFormat))
	readSceneData(scene, sceneObj.ootSceneHeader)
	# TODO: handle entrances, exits, actors, transition actors

	for lightProp in sceneHeader.lightList:
		scene.lights.append(getLightData(lightProp))

	try:
		for roomObj in roomObjs:
			roomIndex = roomObj.ootRoomHeader.roomIndex
			roomName = 'room_' + str(roomIndex)
			room = scene.addRoom(roomIndex, roomName, roomObj.ootRoomHeader.meshType)
			readRoomData(room, roomObj.ootRoomHeader)

			ootProcessMesh(room.mesh, None, sceneObj, roomObj, transformMatrix, convertTextureData)

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
		roomMeshGroup = roomMesh.addMeshGroup(BoxEmpty(translation, scale, obj.empty_display_size))

	elif isinstance(obj.data, bpy.types.Mesh):
		# TODO: Transform static model data
		meshData = saveStaticModel(roomMesh.model, obj, transformMatrix, obj.name, 
			roomMesh.model.DLFormat, convertTextureData, False)
		if roomMeshGroup is None:
			roomMeshGroup = roomMesh.addMeshGroup(None)
		roomMeshGroup.addDLCall(meshData.mesh.draw, obj.ootDrawLayer)

	alphabeticalChildren = sorted(obj.children, key = lambda childObj: childObj.original_name.lower())
	for childObj in alphabeticalChildren:
		ootProcessMesh(roomMesh, roomMeshGroup, sceneObj, childObj, transformMatrix, convertTextureData)
	
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