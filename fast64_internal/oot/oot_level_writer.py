import bpy, bmesh, os, math, re, shutil, mathutils
from io import BytesIO
from bpy.utils import register_class, unregister_class

from ..utility import *
from .oot_utility import *
from .oot_constants import *
from ..panels import OOT_Panel

from ..f3d.f3d_gbi import *
from ..f3d.f3d_writer import *
from .oot_f3d_writer import *

from .oot_level_classes import *
from .oot_level import *
from .oot_collision import *
from .oot_spline import *
from .oot_cutscene import *
from .c_writer import *

def sceneNameFromID(sceneID):
	if sceneID in ootSceneIDToName:
		return ootSceneIDToName[sceneID]
	else:
		raise PluginError("Cannot find scene ID " + str(sceneID))

def ootPreprendSceneIncludes(scene, file):
	exportFile = ootSceneIncludes(scene)
	exportFile.append(file)	
	return exportFile

def ootCreateSceneHeader(levelC):
	sceneHeader = CData()

	sceneHeader.append(levelC.sceneMainC)
	if levelC.sceneTexturesIsUsed():
		sceneHeader.append(levelC.sceneTexturesC)
	sceneHeader.append(levelC.sceneCollisionC)
	if levelC.sceneCutscenesIsUsed():
		for i in range(len(levelC.sceneCutscenesC)):
			sceneHeader.append(levelC.sceneCutscenesC[i])
	for roomName, roomMainC in levelC.roomMainC.items():
		sceneHeader.append(roomMainC)
	for roomName, roomMeshInfoC in levelC.roomMeshInfoC.items():
		sceneHeader.append(roomMeshInfoC)
	for roomName, roomMeshC in levelC.roomMeshC.items():
		sceneHeader.append(roomMeshC)

	return sceneHeader

def ootCombineSceneFiles(levelC):
	sceneC = CData()

	sceneC.append(levelC.sceneMainC)
	if levelC.sceneTexturesIsUsed():
		sceneC.append(levelC.sceneTexturesC)
	sceneC.append(levelC.sceneCollisionC)
	if levelC.sceneCutscenesIsUsed():
		for i in range(len(levelC.sceneCutscenesC)):
			sceneC.append(levelC.sceneCutscenesC[i])
	return sceneC

def ootExportSceneToC(originalSceneObj, transformMatrix, 
	f3dType, isHWv1, sceneName, DLFormat, savePNG, exportInfo):

	checkObjectReference(originalSceneObj, "Scene object")
	isCustomExport = exportInfo.isCustomExportPath
	exportPath = exportInfo.exportPath

	scene = ootConvertScene(originalSceneObj, transformMatrix, 
		f3dType, isHWv1, sceneName, DLFormat, not savePNG)
	
	exportSubdir = ''
	if exportInfo.customSubPath is not None:
		exportSubdir = exportInfo.customSubPath
	if not isCustomExport and exportInfo.customSubPath is None:
		for sceneSubdir, sceneNames in ootSceneDirs.items():
			if sceneName in sceneNames:
				exportSubdir = sceneSubdir
				break
		if exportSubdir == "":
			raise PluginError("Scene folder " + sceneName + " cannot be found in the ootSceneDirs list.")

	levelPath = ootGetPath(exportPath, isCustomExport, exportSubdir, sceneName, True, True)	
	levelC = ootLevelToC(scene, TextureExportSettings(False, savePNG, exportSubdir + sceneName, levelPath))

	if bpy.context.scene.ootSceneSingleFile:
		writeCDataSourceOnly(ootPreprendSceneIncludes(scene, ootCombineSceneFiles(levelC)),
			os.path.join(levelPath, scene.sceneName() + '.c'))
		for i in range(len(scene.rooms)):
			roomC = CData()
			roomC.append(levelC.roomMainC[scene.rooms[i].roomName()])
			roomC.append(levelC.roomMeshInfoC[scene.rooms[i].roomName()])
			roomC.append(levelC.roomMeshC[scene.rooms[i].roomName()])
			writeCDataSourceOnly(ootPreprendSceneIncludes(scene, roomC),
				os.path.join(levelPath, scene.rooms[i].roomName() + '.c'))
	else:
		# Export the scene segment .c files
		writeCDataSourceOnly(ootPreprendSceneIncludes(scene, levelC.sceneMainC),
			os.path.join(levelPath, scene.sceneName() + '_main.c'))
		if levelC.sceneTexturesIsUsed():
			writeCDataSourceOnly(ootPreprendSceneIncludes(scene, levelC.sceneTexturesC),
				os.path.join(levelPath, scene.sceneName() + '_tex.c'))
		writeCDataSourceOnly(ootPreprendSceneIncludes(scene, levelC.sceneCollisionC), 
			os.path.join(levelPath, scene.sceneName() + '_col.c'))
		if levelC.sceneCutscenesIsUsed():
			for i in range(len(levelC.sceneCutscenesC)):
				writeCDataSourceOnly(ootPreprendSceneIncludes(scene, levelC.sceneCutscenesC[i]),
					os.path.join(levelPath, scene.sceneName() + '_cs_' + str(i) + '.c'))
		
		# Export the room segment .c files
		for roomName, roomMainC in levelC.roomMainC.items():
			writeCDataSourceOnly(ootPreprendSceneIncludes(scene, roomMainC),
				os.path.join(levelPath, roomName + '_main.c'))
		for roomName, roomMeshInfoC in levelC.roomMeshInfoC.items():
			writeCDataSourceOnly(ootPreprendSceneIncludes(scene, roomMeshInfoC),
				os.path.join(levelPath, roomName + '_model_info.c'))
		for roomName, roomMeshC in levelC.roomMeshC.items():
			writeCDataSourceOnly(ootPreprendSceneIncludes(scene, roomMeshC),
				os.path.join(levelPath, roomName + '_model.c'))
		
	# Export the scene .h file
	writeCDataHeaderOnly(ootCreateSceneHeader(levelC),
		os.path.join(levelPath, scene.sceneName() + '.h'))
	
	if not isCustomExport:
		writeOtherSceneProperties(scene, exportInfo, levelC)

def writeOtherSceneProperties(scene, exportInfo, levelC):
	modifySceneTable(scene, exportInfo)
	modifySegmentSymbols(scene, exportInfo)
	modifySceneIDs(scene, exportInfo)
	modifySegmentDefinition(scene, exportInfo, levelC)
	modifySceneFiles(scene, exportInfo)

def readSceneData(scene, sceneHeader, alternateSceneHeaders):
	scene.sceneTableEntry.drawConfig = sceneHeader.sceneTableEntry.drawConfig
	scene.globalObject = getCustomProperty(sceneHeader, "globalObject")
	scene.naviCup = getCustomProperty(sceneHeader, "naviCup")
	scene.skyboxID = getCustomProperty(sceneHeader, "skyboxID")
	scene.skyboxCloudiness = getCustomProperty(sceneHeader, "skyboxCloudiness")
	scene.skyboxLighting = getCustomProperty(sceneHeader, "skyboxLighting")
	scene.mapLocation = getCustomProperty(sceneHeader, "mapLocation")
	scene.cameraMode = getCustomProperty(sceneHeader, "cameraMode")
	scene.musicSeq = getCustomProperty(sceneHeader, "musicSeq")
	scene.nightSeq = getCustomProperty(sceneHeader, "nightSeq")
	scene.audioSessionPreset = getCustomProperty(sceneHeader, "audioSessionPreset")

	if sceneHeader.skyboxLighting == '0x00': # Time of Day
		scene.lights.append(getLightData(sceneHeader.timeOfDayLights.dawn))
		scene.lights.append(getLightData(sceneHeader.timeOfDayLights.day))
		scene.lights.append(getLightData(sceneHeader.timeOfDayLights.dusk))
		scene.lights.append(getLightData(sceneHeader.timeOfDayLights.night))
	else:
		for lightProp in sceneHeader.lightList:
			scene.lights.append(getLightData(lightProp))

	for exitProp in sceneHeader.exitList:
		scene.exitList.append(getExitData(exitProp))

	scene.writeCutscene = getCustomProperty(sceneHeader, "writeCutscene")
	if scene.writeCutscene:
		scene.csWriteType = getattr(sceneHeader, "csWriteType")
		if scene.csWriteType == "Embedded":
			scene.csEndFrame = getCustomProperty(sceneHeader, "csEndFrame")
			scene.csWriteTerminator = getCustomProperty(sceneHeader, "csWriteTerminator")
			scene.csTermIdx = getCustomProperty(sceneHeader, "csTermIdx")
			scene.csTermStart = getCustomProperty(sceneHeader, "csTermStart")
			scene.csTermEnd = getCustomProperty(sceneHeader, "csTermEnd")
			readCutsceneData(scene, sceneHeader)
		elif scene.csWriteType == "Custom":
			scene.csWriteCustom = getCustomProperty(sceneHeader, "csWriteCustom")
		elif scene.csWriteType == "Object":
			if sceneHeader.csWriteObject is None:
				raise PluginError('No object selected for cutscene reference')
			elif sceneHeader.csWriteObject.ootEmptyType != 'Cutscene':
				raise PluginError('Object selected as cutscene is wrong type, must be empty with Cutscene type')
			elif sceneHeader.csWriteObject.parent is not None:
				raise PluginError('Cutscene empty object should not be parented to anything')
			else:
				scene.csWriteObject = convertCutsceneObject(sceneHeader.csWriteObject)
	for ec in sceneHeader.extraCutscenes:
		scene.extraCutscenes.append(convertCutsceneObject(ec.csObject))

	if alternateSceneHeaders is not None:
		scene.collision.cameraData = OOTCameraData(scene.name)

		if not alternateSceneHeaders.childNightHeader.usePreviousHeader:
			scene.childNightHeader = scene.getAlternateHeaderScene(scene.name)
			readSceneData(scene.childNightHeader, alternateSceneHeaders.childNightHeader, None)

		if not alternateSceneHeaders.adultDayHeader.usePreviousHeader:
			scene.adultDayHeader = scene.getAlternateHeaderScene(scene.name)
			readSceneData(scene.adultDayHeader, alternateSceneHeaders.adultDayHeader, None)

		if not alternateSceneHeaders.adultNightHeader.usePreviousHeader:
			scene.adultNightHeader = scene.getAlternateHeaderScene(scene.name)
			readSceneData(scene.adultNightHeader, alternateSceneHeaders.adultNightHeader, None)

		for i in range(len(alternateSceneHeaders.cutsceneHeaders)):
			cutsceneHeaderProp = alternateSceneHeaders.cutsceneHeaders[i]
			cutsceneHeader = scene.getAlternateHeaderScene(scene.name)
			readSceneData(cutsceneHeader, cutsceneHeaderProp, None)
			scene.cutsceneHeaders.append(cutsceneHeader)

def getConvertedTransform(transformMatrix, sceneObj, obj, handleOrientation):
	
	# Hacky solution to handle Z-up to Y-up conversion
	# We cannot apply rotation to empty, as that modifies scale
	if handleOrientation:
		orientation = mathutils.Quaternion((1, 0, 0), math.radians(90.0))
	else:
		orientation = mathutils.Matrix.Identity(4)
	return getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation)

def getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation):
	relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
	blenderTranslation, blenderRotation, scale = relativeTransform.decompose()
	rotation = blenderRotation @ orientation
	convertedTranslation = ootConvertTranslation(blenderTranslation)
	convertedRotation = ootConvertRotation(rotation)
	
	return convertedTranslation, convertedRotation, scale, rotation
	
def getExitData(exitProp):
	if exitProp.exitIndex != "Custom":
		raise PluginError("Exit index enums not implemented yet.")
	return OOTExit(exitProp.exitIndexCustom)

def getLightData(lightProp):
	light = OOTLight()
	light.ambient = getLightColor(lightProp.ambient)
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

	light.fogColor = getLightColor(lightProp.fogColor)
	light.fogNear = lightProp.fogNear
	light.transitionSpeed = lightProp.transitionSpeed
	light.fogFar = lightProp.fogFar
	return light

def readRoomData(room, roomHeader, alternateRoomHeaders):
	room.roomIndex = roomHeader.roomIndex
	room.roomBehaviour = getCustomProperty(roomHeader, "roomBehaviour")
	room.disableWarpSongs = roomHeader.disableWarpSongs
	room.showInvisibleActors = roomHeader.showInvisibleActors
	room.linkIdleMode = getCustomProperty(roomHeader, "linkIdleMode")
	room.linkIdleModeCustom = roomHeader.linkIdleModeCustom
	room.setWind = roomHeader.setWind
	room.windVector = normToSigned8Vector(mathutils.Vector(roomHeader.windVector).normalized())
	room.windStrength = int(0xFF * max(mathutils.Vector(roomHeader.windVector).length, 1))
	if roomHeader.leaveTimeUnchanged:
		room.timeHours = "0xFF"
		room.timeMinutes = "0xFF"
	else:
		room.timeHours = roomHeader.timeHours
		room.timeMinutes = roomHeader.timeMinutes
	room.timeSpeed = max(-128, min(127, int(round(roomHeader.timeSpeed * 0xA))))
	room.disableSkybox = roomHeader.disableSkybox
	room.disableSunMoon = roomHeader.disableSunMoon
	room.echo = roomHeader.echo
	room.objectList.extend([getCustomProperty(item, "objectID") for item in roomHeader.objectList])
	if len(room.objectList) > 15:
		raise PluginError("Error: A scene can only have a maximum of 15 objects (OOT, not blender objects).")

	if alternateRoomHeaders is not None:
		if not alternateRoomHeaders.childNightHeader.usePreviousHeader:
			room.childNightHeader = room.getAlternateHeaderRoom(room.ownerName)
			readRoomData(room.childNightHeader, alternateRoomHeaders.childNightHeader, None)

		if not alternateRoomHeaders.adultDayHeader.usePreviousHeader:
			room.adultDayHeader = room.getAlternateHeaderRoom(room.ownerName)
			readRoomData(room.adultDayHeader, alternateRoomHeaders.adultDayHeader, None)

		if not alternateRoomHeaders.adultNightHeader.usePreviousHeader:
			room.adultNightHeader = room.getAlternateHeaderRoom(room.ownerName)
			readRoomData(room.adultNightHeader, alternateRoomHeaders.adultNightHeader, None)

		for i in range(len(alternateRoomHeaders.cutsceneHeaders)):
			cutsceneHeaderProp = alternateRoomHeaders.cutsceneHeaders[i]
			cutsceneHeader = room.getAlternateHeaderRoom(room.ownerName)
			readRoomData(cutsceneHeader, cutsceneHeaderProp, None)
			room.cutsceneHeaders.append(cutsceneHeader)

def readCamPos(camPosProp, obj, scene, sceneObj, transformMatrix):
	# Camera faces opposite direction
	orientation = mathutils.Quaternion((0, 1, 0), math.radians(180.0))
	translation, rotation, scale, orientedRotation = \
		getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation)
	camPosProp = obj.ootCameraPositionProperty
	index = camPosProp.index
	# TODO: FOV conversion?
	if index in scene.collision.cameraData.camPosDict:
		raise PluginError("Error: Repeated camera position index: " + str(index))
	scene.collision.cameraData.camPosDict[index] = OOTCameraPosData(
		getCustomProperty(camPosProp, 'camSType'), camPosProp.hasPositionData,
		translation, rotation, int(round(math.degrees(obj.data.angle))), camPosProp.jfifID)

def readPathProp(pathProp, obj, scene, sceneObj, sceneName, transformMatrix):
	relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
	index = obj.ootSplineProperty.index
	if index in scene.pathList:
		raise PluginError("Error: " + obj.name + "has a repeated spline index: " + str(index))
	scene.pathList[index] = ootConvertPath(sceneName, index, obj, relativeTransform)

def ootConvertScene(originalSceneObj, transformMatrix, 
	f3dType, isHWv1, sceneName, DLFormat, convertTextureData):

	if originalSceneObj.data is not None or originalSceneObj.ootEmptyType != "Scene":
		raise PluginError(originalSceneObj.name + " is not an empty with the \"Scene\" empty type.")
	
	if bpy.context.scene.exportHiddenGeometry:
		hiddenObjs = unhideAllAndGetHiddenList(bpy.context.scene)

	# Don't remove ignore_render, as we want to reuse this for collision
	sceneObj, allObjs = \
		ootDuplicateHierarchy(originalSceneObj, None, True, OOTObjectCategorizer())

	if bpy.context.scene.exportHiddenGeometry:
		hideObjsInList(hiddenObjs)
	
	roomObjs = [child for child in sceneObj.children if child.data is None and child.ootEmptyType == 'Room']
	if len(roomObjs) == 0:
		raise PluginError("The scene has no child empties with the 'Room' empty type.")

	try:
		scene = OOTScene(sceneName, OOTModel(f3dType, isHWv1, sceneName + '_dl', DLFormat, None))
		readSceneData(scene, sceneObj.ootSceneHeader, sceneObj.ootAlternateSceneHeaders)
		processedRooms = set()

		for obj in sceneObj.children:
			translation, rotation, scale, orientedRotation = \
				getConvertedTransform(transformMatrix, sceneObj, obj, True)

			if obj.data is None and obj.ootEmptyType == 'Room':
				roomObj = obj
				roomIndex = roomObj.ootRoomHeader.roomIndex
				if roomIndex in processedRooms:
					raise PluginError("Error: room index " + str(roomIndex) + " is used more than once.")
				processedRooms.add(roomIndex)
				room = scene.addRoom(roomIndex, sceneName, roomObj.ootRoomHeader.meshType)
				readRoomData(room, roomObj.ootRoomHeader, roomObj.ootAlternateRoomHeaders)

				DLGroup = room.mesh.addMeshGroup(CullGroup(
					translation, scale, obj.ootRoomHeader.defaultCullDistance)).DLGroup
				ootProcessMesh(room.mesh, DLGroup, sceneObj, roomObj, transformMatrix, convertTextureData, None)
				room.mesh.terminateDLs()
				room.mesh.removeUnusedEntries()
				ootProcessEmpties(scene, room, sceneObj, roomObj, transformMatrix)
			elif obj.data is None and obj.ootEmptyType == "Water Box":
				ootProcessWaterBox(sceneObj, obj, transformMatrix, scene, 0x3F)
			elif isinstance(obj.data, bpy.types.Camera):
				camPosProp = obj.ootCameraPositionProperty
				readCamPos(camPosProp, obj, scene, sceneObj, transformMatrix)
			elif isinstance(obj.data, bpy.types.Curve) and assertCurveValid(obj):
				readPathProp(obj.ootSplineProperty, obj, scene, sceneObj, sceneName, transformMatrix)
		
		scene.validateIndices()
		scene.entranceList = sorted(scene.entranceList, key=lambda x: x.startPositionIndex)
		exportCollisionCommon(scene.collision, sceneObj, transformMatrix, True, sceneName)

		ootCleanupScene(originalSceneObj, allObjs)

	except Exception as e:
		ootCleanupScene(originalSceneObj, allObjs)
		raise Exception(str(e))

	return scene

# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
# When we duplicated obj hierarchy we stripped all ignore_renders from hierarchy.
def ootProcessMesh(roomMesh, DLGroup, sceneObj, obj, transformMatrix, convertTextureData, LODHierarchyObject):

	relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
	translation, rotation, scale = relativeTransform.decompose()

	if obj.data is None and obj.ootEmptyType == "Cull Group":
		if LODHierarchyObject is not None:
			raise PluginError(obj.name + " cannot be used as a cull group because it is " +\
				"in the sub-hierarchy of the LOD group empty " + LODHierarchyObject.name)

		checkUniformScale(scale, obj)
		DLGroup = roomMesh.addMeshGroup(CullGroup(
			ootConvertTranslation(translation), scale, obj.empty_display_size)).DLGroup

	elif isinstance(obj.data, bpy.types.Mesh) and not obj.ignore_render:
		triConverterInfo = TriangleConverterInfo(obj, None, roomMesh.model.f3d, relativeTransform, getInfoDict(obj))
		fMeshes = saveStaticModel(triConverterInfo, roomMesh.model, obj, relativeTransform, roomMesh.model.name,
			convertTextureData, False, 'oot')
		if fMeshes is not None:
			for drawLayer, fMesh in fMeshes.items():
				DLGroup.addDLCall(fMesh.draw, drawLayer)

	alphabeticalChildren = sorted(obj.children, key = lambda childObj: childObj.original_name.lower())
	for childObj in alphabeticalChildren:
		if childObj.data is None and childObj.ootEmptyType == "LOD":
			ootProcessLOD(roomMesh, DLGroup, sceneObj, childObj, transformMatrix, convertTextureData, LODHierarchyObject)
		else:
			ootProcessMesh(roomMesh, DLGroup, sceneObj, childObj, transformMatrix, convertTextureData, LODHierarchyObject)

def ootProcessLOD(roomMesh, DLGroup, sceneObj, obj, transformMatrix, convertTextureData, LODHierarchyObject):

	relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
	translation, rotation, scale = relativeTransform.decompose()
	ootTranslation = ootConvertTranslation(translation)

	LODHierarchyObject = obj
	name = toAlnum(roomMesh.model.name + "_" + obj.name + "_lod")
	opaqueLOD = roomMesh.model.addLODGroup(name + "_opaque", ootTranslation, obj.f3d_lod_always_render_farthest)
	transparentLOD = roomMesh.model.addLODGroup(name + "_transparent", ootTranslation, obj.f3d_lod_always_render_farthest)

	index = 0
	for childObj in obj.children:
		# This group will not be converted to C directly, but its display lists will be converted through the FLODGroup.
		childDLGroup = OOTDLGroup(name + str(index), roomMesh.model.DLFormat)
		index += 1
		
		if childObj.data is None and childObj.ootEmptyType == "LOD":
			ootProcessLOD(roomMesh, childDLGroup, sceneObj, childObj, transformMatrix, convertTextureData, LODHierarchyObject)
		else:
			ootProcessMesh(roomMesh, childDLGroup, sceneObj, childObj, transformMatrix, convertTextureData, LODHierarchyObject)

		# We handle case with no geometry, for the cases where we have "gaps" in the LOD hierarchy.
		# This can happen if a LOD does not use transparency while the levels above and below it does.
		childDLGroup.createDLs()
		childDLGroup.terminateDLs()

		# Add lod AFTER processing hierarchy, so that DLs will be built by then
		opaqueLOD.add_lod(childDLGroup.opaque, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)
		transparentLOD.add_lod(childDLGroup.transparent, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)

	opaqueLOD.create_data()
	transparentLOD.create_data()

	DLGroup.addDLCall(opaqueLOD.draw, "Opaque")
	DLGroup.addDLCall(transparentLOD.draw, "Transparent")

def ootProcessEmpties(scene, room, sceneObj, obj, transformMatrix):
	translation, rotation, scale, orientedRotation = getConvertedTransform(transformMatrix, sceneObj, obj, True)

	if obj.data is None:
		if obj.ootEmptyType == "Actor":
			actorProp = obj.ootActorProperty
			addActor(room, OOTActor(getCustomProperty(actorProp, 'actorID'), 
				translation, rotation, actorProp.actorParam,
				None if not actorProp.rotOverride else (actorProp.rotOverrideX, actorProp.rotOverrideY, actorProp.rotOverrideZ)),
				actorProp, "actorList", obj.name)
		elif obj.ootEmptyType == "Transition Actor":
			transActorProp = obj.ootTransitionActorProperty
			addActor(scene, OOTTransitionActor(
				getCustomProperty(transActorProp.actor, "actorID"),
				room.roomIndex, transActorProp.roomIndex,
				getCustomProperty(transActorProp, "cameraTransitionFront"),
				getCustomProperty(transActorProp, "cameraTransitionBack"),
				translation, rotation[1], # TODO: Correct axis?
				transActorProp.actor.actorParam), transActorProp.actor, "transitionActorList", obj.name)
			#scene.transitionActorList.append(OOTTransitionActor(
			#	getCustomProperty(transActorProp.actor, "actorID"),
			#	room.roomIndex, transActorProp.roomIndex,
			#	getCustomProperty(transActorProp, "cameraTransitionFront"),
			#	getCustomProperty(transActorProp, "cameraTransitionBack"),
			#	translation, rotation[1], # TODO: Correct axis?
			#	transActorProp.actor.actorParam))
		elif obj.ootEmptyType == "Entrance":
			entranceProp = obj.ootEntranceProperty
			spawnIndex = obj.ootEntranceProperty.spawnIndex
			addActor(scene, OOTEntrance(room.roomIndex, spawnIndex), entranceProp.actor, "entranceList", obj.name)
			#scene.entranceList.append(OOTEntrance(room.roomIndex, spawnIndex))
			addStartPosition(scene, spawnIndex, OOTActor(
				"ACTOR_PLAYER" if not entranceProp.customActor else entranceProp.actor.actorIDCustom,
				translation, rotation, entranceProp.actor.actorParam, None), entranceProp.actor,  obj.name)
		elif obj.ootEmptyType == "Water Box":
			ootProcessWaterBox(sceneObj, obj, transformMatrix, scene, room.roomIndex)
	elif isinstance(obj.data, bpy.types.Camera):
		camPosProp = obj.ootCameraPositionProperty
		readCamPos(camPosProp, obj, scene, sceneObj, transformMatrix)
	elif isinstance(obj.data, bpy.types.Curve) and assertCurveValid(obj):
		readPathProp(obj.ootSplineProperty, obj, scene, sceneObj, scene.name, transformMatrix)
	
	for childObj in obj.children:
		ootProcessEmpties(scene, room, sceneObj, childObj, transformMatrix)
	
def ootProcessWaterBox(sceneObj, obj, transformMatrix, scene, roomIndex):
	translation, rotation, scale, orientedRotation = getConvertedTransform(transformMatrix, sceneObj, obj, True)

	checkIdentityRotation(obj, orientedRotation, False)
	waterBoxProp = obj.ootWaterBoxProperty
	scene.collision.waterBoxes.append(OOTWaterBox(
		roomIndex,
		getCustomProperty(waterBoxProp, "lighting"),
		getCustomProperty(waterBoxProp, "camera"),
		translation, scale, obj.empty_display_size))

class OOT_ExportScene(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_export_level'
	bl_label = "Export Scene"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		activeObj = None
		try:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = "OBJECT")
			activeObj = context.view_layer.objects.active
			
			obj = context.scene.ootSceneExportObj
			if obj is None:
				raise PluginError("Scene object input not set.")
			elif obj.data is not None or obj.ootEmptyType != 'Scene':
				raise PluginError("The input object is not an empty with the Scene type.")

			#obj = context.active_object

			scaleValue = bpy.context.scene.ootBlenderScale
			finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((
				scaleValue, scaleValue, scaleValue))).to_4x4()
		
		except Exception as e:
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set
		try:
			levelName = context.scene.ootSceneName
			if context.scene.ootSceneCustomExport:
				exportInfo = ExportInfo(True, bpy.path.abspath(context.scene.ootSceneExportPath), None, levelName)
			else:
				if context.scene.ootSceneOption == 'Custom':	
					subfolder = 'assets/scenes/' + context.scene.ootSceneSubFolder + '/'
				else:
					levelName = sceneNameFromID(context.scene.ootSceneOption)
					subfolder = None
				exportInfo = ExportInfo(False, bpy.path.abspath(context.scene.ootDecompPath), subfolder, levelName)
			#if not context.scene.ootSceneCustomExport:
			#	applyBasicTweaks(exportPath)

			ootExportSceneToC(obj, finalTransform, 
				context.scene.f3d_type, context.scene.isHWv1, levelName, DLFormat.Static, 
					context.scene.saveTextures or bpy.context.scene.ignoreTextureRestrictions, exportInfo)
			
			#ootExportScene(obj, finalTransform,
			#	context.scene.f3d_type, context.scene.isHWv1, levelName, exportPath, 
			#	context.scene.saveTextures or bpy.context.scene.ignoreTextureRestrictions, 
			#	context.scene.ootSceneCustomExport, DLFormat.Dynamic)
			self.report({'INFO'}, 'Success!')

			context.view_layer.objects.active = activeObj
			if activeObj is not None:
				activeObj.select_set(True)

			#applyRotation(obj.children, math.radians(0), 'X')
			return {'FINISHED'} # must return a set

		except Exception as e:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			context.view_layer.objects.active = activeObj
			if activeObj is not None:
				activeObj.select_set(True)
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

def ootRemoveSceneC(exportInfo):
	modifySceneTable(None, exportInfo)
	modifySegmentSymbols(None, exportInfo)
	modifySceneIDs(None, exportInfo)
	modifySegmentDefinition(None, exportInfo)
	deleteSceneFiles(exportInfo)

class OOT_RemoveScene(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_remove_level'
	bl_label = "Remove Scene"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		levelName = context.scene.ootSceneName
		if context.scene.ootSceneCustomExport:
			operator.report({'ERROR'}, "You can only remove scenes from your decomp path.")
			return {"FINISHED"}
			
		if context.scene.ootSceneOption == 'Custom':	
			subfolder = 'assets/scenes/' + context.scene.ootSceneSubFolder + '/'
		else:
			levelName = sceneNameFromID(context.scene.ootSceneOption)
			subfolder = None
		exportInfo = ExportInfo(False, bpy.path.abspath(context.scene.ootDecompPath), subfolder, levelName)
		
		ootRemoveSceneC(exportInfo)

		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} # must return a set

class OOT_ExportScenePanel(OOT_Panel):
	bl_idname = "OOT_PT_export_level"
	bl_label = "OOT Scene Exporter"

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.operator(OOT_ExportScene.bl_idname)
		#if not bpy.context.scene.ignoreTextureRestrictions:
		#	col.prop(context.scene, 'saveTextures')
		prop_split(col, context.scene, 'ootSceneExportObj', "Scene Object")
		col.prop(context.scene, 'ootSceneSingleFile')
		col.prop(context.scene, 'ootSceneCustomExport')
		if context.scene.ootSceneCustomExport:
			prop_split(col, context.scene, 'ootSceneExportPath', 'Directory')
			prop_split(col, context.scene, 'ootSceneName', 'Name')
			customExportWarning(col)
		else:
			col.operator(OOT_SearchSceneEnumOperator.bl_idname, icon = 'VIEWZOOM')
			col.box().column().label(text = getEnumName(ootEnumSceneID, context.scene.ootSceneOption))
			#col.prop(context.scene, 'ootSceneOption')
			if context.scene.ootSceneOption == 'Custom':
				prop_split(col, context.scene, 'ootSceneSubFolder', 'Subfolder')
				prop_split(col, context.scene, 'ootSceneName', 'Name')
			col.operator(OOT_RemoveScene.bl_idname)

def isSceneObj(self, obj):
	return obj.data is None and obj.ootEmptyType == "Scene"

oot_level_classes = (
	OOT_ExportScene,
	OOT_RemoveScene,
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
	
	bpy.types.Scene.ootSceneName = bpy.props.StringProperty(name = 'Name', default = 'spot03')
	bpy.types.Scene.ootSceneSubFolder = bpy.props.StringProperty(name = "Subfolder", default = 'overworld')
	bpy.types.Scene.ootSceneOption = bpy.props.EnumProperty(name = "Scene", items = ootEnumSceneID, default = 'SCENE_YDAN')
	bpy.types.Scene.ootSceneExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.ootSceneCustomExport = bpy.props.BoolProperty(
		name = 'Custom Export Path')
	bpy.types.Scene.ootSceneExportObj = bpy.props.PointerProperty(type = bpy.types.Object, poll = isSceneObj)
	bpy.types.Scene.ootSceneSingleFile = bpy.props.BoolProperty(
		name = "Export as Single File",
		default = False,
		description = "Does not split the scene and rooms into multiple files.")


def oot_level_unregister():
	for cls in reversed(oot_level_classes):
		unregister_class(cls)

	del bpy.types.Scene.ootSceneName
	del bpy.types.Scene.ootSceneExportPath
	del bpy.types.Scene.ootSceneCustomExport
	del bpy.types.Scene.ootSceneOption
	del bpy.types.Scene.ootSceneSubFolder
	del bpy.types.Scene.ootSceneSingleFile
