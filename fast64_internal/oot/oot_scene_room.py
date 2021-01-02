
import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from .oot_actor import *
from .oot_collision import *

from ..utility import *

class OOT_SearchMusicSeqEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_music_seq_enum_operator"
	bl_label = "Search Music Sequence"
	bl_property = "ootMusicSeq"
	bl_options = {'REGISTER', 'UNDO'} 

	ootMusicSeq : bpy.props.EnumProperty(items = ootEnumMusicSeq, default = "0x02")
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

class OOTExitProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

	exitIndex : bpy.props.EnumProperty(items = ootEnumExitIndex, default = "Default")
	exitIndexCustom : bpy.props.StringProperty(default = '0x0000')

	# These are used when adding an entry to gEntranceTable
	scene : bpy.props.EnumProperty(items = ootEnumSceneID, default = "SCENE_YDAN")
	sceneCustom : bpy.props.StringProperty(default = "SCENE_YDAN")

	# These are used when adding an entry to gEntranceTable
	continueBGM : bpy.props.BoolProperty(default = False)
	displayTitleCard : bpy.props.BoolProperty(default = True)
	fadeInAnim : bpy.props.EnumProperty(items = ootEnumTransitionAnims, default = '0x02')
	fadeInAnimCustom : bpy.props.StringProperty(default = '0x02')
	fadeOutAnim : bpy.props.EnumProperty(items = ootEnumTransitionAnims, default = '0x02')
	fadeOutAnimCustom : bpy.props.StringProperty(default = '0x02')

def drawExitProperty(layout, exitProp, index, headerIndex):
	box = layout.box()
	box.prop(exitProp, 'expandTab', text = 'Exit ' + \
		str(index), icon = 'TRIA_DOWN' if exitProp.expandTab else \
		'TRIA_RIGHT')
	if exitProp.expandTab:
		drawEnumWithCustom(box, exitProp, "exitIndex", "Exit Index", "")
		if exitProp.exitIndex != "Custom":
			box.label(text = "This is unfinished, use \"Custom\".")
			exitGroup = box.column()
			exitGroup.enabled = False
			drawEnumWithCustom(exitGroup, exitProp, "scene", "Scene", "")
			exitGroup.prop(exitProp, "continueBGM", text = "Continue BGM")
			exitGroup.prop(exitProp, "displayTitleCard", text = "Display Title Card")
			drawEnumWithCustom(exitGroup, exitProp, "fadeInAnim", "Fade In Animation", "")
			drawEnumWithCustom(exitGroup, exitProp, "fadeOutAnim", "Fade Out Animation", "")

		drawCollectionOps(box, index, "Exit", headerIndex)


class OOTObjectProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	objectID : bpy.props.EnumProperty(items = ootEnumObjectID, default = 'OBJECT_HUMAN')
	objectIDCustom : bpy.props.StringProperty(default = 'OBJECT_HUMAN')

def drawObjectProperty(layout, objectProp, headerIndex, index):
	objItemBox = layout.box()
	objectName = getEnumName(ootEnumObjectID, objectProp.objectID)
	objItemBox.prop(objectProp, 'expandTab', text = objectName, 
		icon = 'TRIA_DOWN' if objectProp.expandTab else \
		'TRIA_RIGHT')
	if objectProp.expandTab:
		objItemBox.box().label(text = "ID: " + objectName)
		#prop_split(objItemBox, objectProp, "objectID", name = "ID")
		if objectProp.objectID == "Custom":
			prop_split(objItemBox, objectProp, "objectIDCustom", "Object ID Custom")
		objSearch = objItemBox.operator(OOT_SearchObjectEnumOperator.bl_idname, icon = 'VIEWZOOM')
		objSearch.headerIndex = headerIndex if headerIndex is not None else 0
		objSearch.index = index
		drawCollectionOps(objItemBox, index, "Object", headerIndex)

class OOTLightProperty(bpy.types.PropertyGroup):
	ambient : bpy.props.FloatVectorProperty(name = "Ambient Color", size = 4, min = 0, max = 1, default = (70/255, 40/255, 57/255 ,1), subtype = 'COLOR')
	useCustomDiffuse0 : bpy.props.BoolProperty(name = 'Use Custom Light Object')
	useCustomDiffuse1 : bpy.props.BoolProperty(name = 'Use Custom Light Object')
	diffuse0 :  bpy.props.FloatVectorProperty(name = "", size = 4, min = 0, max = 1, default = (180/255, 154/255, 138/255 ,1), subtype = 'COLOR')
	diffuse1 :  bpy.props.FloatVectorProperty(name = "", size = 4, min = 0, max = 1, default = (20/255, 20/255, 60/255 ,1), subtype = 'COLOR')
	diffuse0Custom : bpy.props.PointerProperty(name = "Diffuse 0", type = bpy.types.Light)
	diffuse1Custom : bpy.props.PointerProperty(name = "Diffuse 1", type = bpy.types.Light)
	fogColor : bpy.props.FloatVectorProperty(name = "", size = 4, min = 0, max = 1, default = (140/255, 120/255, 110/255 ,1), subtype = 'COLOR')
	fogNear : bpy.props.IntProperty(name = "", default = 993, min = 0, max = 2**10 - 1)
	transitionSpeed : bpy.props.IntProperty(name = "", default = 1, min = 0, max = 63)
	fogFar : bpy.props.IntProperty(name = "", default = 3200, min = 0, max = 2**16 - 1)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

def drawLightProperty(layout, lightProp, index, sceneHeaderIndex):
	box = layout.box()
	box.prop(lightProp, 'expandTab', text = 'Lighting ' + \
		str(index), icon = 'TRIA_DOWN' if lightProp.expandTab else \
		'TRIA_RIGHT')
	if lightProp.expandTab:
		prop_split(box, lightProp, 'ambient', 'Ambient Color')
		
		if lightProp.useCustomDiffuse0:
			prop_split(box, lightProp, 'diffuse0Custom', 'Diffuse 0 Light')
		else:
			prop_split(box, lightProp, 'diffuse0', 'Diffuse 0 Light')
		box.prop(lightProp, "useCustomDiffuse0")
		
		if lightProp.useCustomDiffuse1:
			prop_split(box, lightProp, 'diffuse1Custom', 'Diffuse 1 Light')
		else:
			prop_split(box, lightProp, 'diffuse1', 'Diffuse 1 Light')
		box.prop(lightProp, "useCustomDiffuse1")
		
		prop_split(box, lightProp, 'fogColor', 'Fog Color')
		prop_split(box, lightProp, 'fogNear', 'Fog Near')
		prop_split(box, lightProp, 'fogFar', 'Fog Far')
		prop_split(box, lightProp, 'transitionSpeed', 'Transition Speed')

		drawCollectionOps(box, index, "Light", sceneHeaderIndex)

class OOTSceneHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	usePreviousHeader : bpy.props.BoolProperty(name = "Use Previous Header", default = True)

	globalObject : bpy.props.EnumProperty(name = "Global Object", default = "0x0002", items = ootEnumGlobalObject)
	globalObjectCustom : bpy.props.StringProperty(name = "Global Object Custom", default = "0x00")
	naviCup : bpy.props.EnumProperty(name = "Navi Hints", default = '0x00', items = ootEnumNaviHints)
	naviCupCustom : bpy.props.StringProperty(name = "Navi Hints Custom", default = '0x00')

	skyboxID : bpy.props.EnumProperty(name = "Skybox", items = ootEnumSkybox, default = "0x00")
	skyboxIDCustom : bpy.props.StringProperty(name = "Skybox ID", default = '0')
	skyboxCloudiness : bpy.props.EnumProperty(name = "Cloudiness", items = ootEnumCloudiness, default = "0x00")
	skyboxCloudinessCustom : bpy.props.StringProperty(name = "Cloudiness ID", default = '0x00')
	skyboxLighting : bpy.props.EnumProperty(name = "Skybox Lighting", items = ootEnumSkyboxLighting, default = "0x00")
	skyboxLightingCustom : bpy.props.StringProperty(name = "Skybox Lighting Custom", default = '0x00')

	mapLocation : bpy.props.EnumProperty(name = "Map Location", items = ootEnumMapLocation, default = "0x00")
	mapLocationCustom : bpy.props.StringProperty(name = "Skybox Lighting Custom", default = '0x00')
	cameraMode : bpy.props.EnumProperty(name = "Camera Mode", items = ootEnumCameraMode, default = "0x00")
	cameraModeCustom : bpy.props.StringProperty(name = "Camera Mode Custom", default = '0x00')

	musicSeq : bpy.props.EnumProperty(name = "Music Sequence", items = ootEnumMusicSeq, default = '0x02')
	musicSeqCustom : bpy.props.StringProperty(name = "Music Sequence ID", default = '0x00')
	nightSeq : bpy.props.EnumProperty(name = "Nighttime SFX", items = ootEnumNightSeq, default = "0x00")
	nightSeqCustom : bpy.props.StringProperty(name = "Nighttime SFX ID", default = '0x00')
	audioSessionPreset : bpy.props.EnumProperty(name = "Audio Session Preset", items = ootEnumAudioSessionPreset, default = "0x00")
	audioSessionPresetCustom : bpy.props.StringProperty(name = "Audio Session Preset", default = "0x00")

	lightList : bpy.props.CollectionProperty(type = OOTLightProperty, name = 'Lighting List')
	exitList : bpy.props.CollectionProperty(type = OOTExitProperty, name = "Exit List")
	camSType : bpy.props.EnumProperty(items = ootEnumCameraSType, default = 'CAM_SET_NONE')
	camSTypeCustom : bpy.props.StringProperty(default = "CAM_SET_NONE")

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
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'audioSessionPreset', "Audio Session Preset", "")

	cameraAndWorldMap = layout.box()
	cameraAndWorldMap.box().label(text = "Camera And World Map")
	drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'mapLocation', "Map Location", "")
	drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'cameraMode', "Camera Mode", "")
	drawEnumWithCustom(cameraAndWorldMap, sceneProp, "camSType", "Camera S Type", "")

	lighting = layout.box()
	lighting.box().label(text = "Lighting List")
	drawAddButton(lighting, len(sceneProp.lightList), "Light", headerIndex)
	for i in range(len(sceneProp.lightList)):
		drawLightProperty(lighting, sceneProp.lightList[i], i, headerIndex)

	if headerIndex is None or headerIndex == 0:
		exitBox = layout.box()
		exitBox.box().label(text = "Exit List")
		drawAddButton(exitBox, len(sceneProp.exitList), "Exit", headerIndex)
		for i in range(len(sceneProp.exitList)):
			drawExitProperty(exitBox, sceneProp.exitList[i], i, headerIndex)

	if headerIndex is not None and headerIndex > 3:
		drawCollectionOps(layout, headerIndex - 4, "Scene", None)

class OOTRoomHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	usePreviousHeader : bpy.props.BoolProperty(name = "Use Previous Header", default = True)

	roomIndex : bpy.props.IntProperty(name = 'Room Index', default = 0, min = 0)
	roomBehaviour : bpy.props.EnumProperty(items = ootEnumRoomBehaviour, default = "0x00")
	roomBehaviourCustom : bpy.props.StringProperty(default = "0x00")
	disableWarpSongs : bpy.props.BoolProperty(name = "Disable Warp Songs")
	showInvisibleActors : bpy.props.BoolProperty(name = "Show Invisible Actors")
	linkIdleMode : bpy.props.EnumProperty(name = "Link Idle Mode",items = ootEnumLinkIdle, default = "0x00")
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
		if roomProp.meshType == '1':
			layout.box().label(text = "Mesh Type 1 not supported at this time.")

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
	drawEnumWithCustom(behaviourBox, roomProp, "roomBehaviour", "Room Behaviour", "")
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