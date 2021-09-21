
import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from .oot_actor import *
#from .oot_collision import *

from ..utility import *

class OOT_SearchMusicSeqEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_music_seq_enum_operator"
	bl_label = "Search Music Sequence"
	bl_property = "ootMusicSeq"
	bl_options = {'REGISTER', 'UNDO'} 

	ootMusicSeq : bpy.props.EnumProperty(items = ootEnumMusicSeq, default = "0x02")
	headerIndex : bpy.props.IntProperty(default = 0, min = 0)
	objName : bpy.props.StringProperty()

	def execute(self, context):
		obj = bpy.data.objects[self.objName]
		if self.headerIndex == 0:
			sceneHeader = obj.ootSceneHeader
		elif self.headerIndex == 1:
			sceneHeader = obj.ootAlternateSceneHeaders.childNightHeader
		elif self.headerIndex == 2:
			sceneHeader = obj.ootAlternateSceneHeaders.adultDayHeader
		elif self.headerIndex == 3:
			sceneHeader = obj.ootAlternateSceneHeaders.adultNightHeader
		else:
			sceneHeader = obj.ootAlternateSceneHeaders.cutsceneHeaders[self.headerIndex - 4]

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
	objName : bpy.props.StringProperty()

	def execute(self, context):
		obj = bpy.data.objects[self.objName]
		if self.headerIndex == 0:
			roomHeader = obj.ootRoomHeader
		elif self.headerIndex == 1:
			roomHeader = obj.ootAlternateRoomHeaders.childNightHeader
		elif self.headerIndex == 2:
			roomHeader = obj.ootAlternateRoomHeaders.adultDayHeader
		elif self.headerIndex == 3:
			roomHeader = obj.ootAlternateRoomHeaders.adultNightHeader
		else:
			roomHeader = obj.ootAlternateRoomHeaders.cutsceneHeaders[self.headerIndex - 4]

		roomHeader.objectList[self.index].objectID = self.ootObjectID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootObjectID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOT_SearchSceneEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_scene_enum_operator"
	bl_label = "Choose Scene"
	bl_property = "ootSceneID"
	bl_options = {'REGISTER', 'UNDO'} 

	ootSceneID : bpy.props.EnumProperty(items = ootEnumSceneID, default = "SCENE_YDAN")
	headerIndex : bpy.props.IntProperty(default = -1, min = -1)
	index : bpy.props.IntProperty(default = 0, min = 0)
	objName : bpy.props.StringProperty()

	def execute(self, context):
		if self.objName != "":
			obj = bpy.data.objects[self.objName]
		else:
			obj = None

		if self.headerIndex == -1:
			pass
		elif self.headerIndex == 0:
			sceneHeader = obj.ootSceneHeader
		elif self.headerIndex == 1:
			sceneHeader = obj.ootAlternateSceneHeaders.childNightHeader
		elif self.headerIndex == 2:
			sceneHeader = obj.ootAlternateSceneHeaders.adultDayHeader
		elif self.headerIndex == 3:
			sceneHeader = obj.ootAlternateSceneHeaders.adultNightHeader
		else:
			sceneHeader = obj.ootAlternateSceneHeaders.cutsceneHeaders[self.headerIndex - 4]

		if self.headerIndex == -1:
			context.scene.ootSceneOption = self.ootSceneID
		else:
			sceneHeader.exitList[self.index].sceneID = self.sceneID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootSceneID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

def drawAlternateRoomHeaderProperty(layout, headerProp, objName):
	headerSetup = layout.column()
	#headerSetup.box().label(text = "Alternate Headers")
	headerSetupBox = headerSetup.column()

	headerSetupBox.row().prop(headerProp, "headerMenuTab", expand = True)
	if headerProp.headerMenuTab == "Child Night":
		drawRoomHeaderProperty(headerSetupBox, headerProp.childNightHeader, None, 1, objName)
	elif headerProp.headerMenuTab == "Adult Day":
		drawRoomHeaderProperty(headerSetupBox, headerProp.adultDayHeader, None, 2, objName)
	elif headerProp.headerMenuTab == "Adult Night":
		drawRoomHeaderProperty(headerSetupBox, headerProp.adultNightHeader, None, 3, objName)
	elif headerProp.headerMenuTab == "Cutscene":
		prop_split(headerSetup, headerProp, 'currentCutsceneIndex', "Cutscene Index")
		drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Room", None, objName)
		index = headerProp.currentCutsceneIndex
		if index - 4 < len(headerProp.cutsceneHeaders):
			drawRoomHeaderProperty(headerSetup, headerProp.cutsceneHeaders[index - 4], None, index, objName)
		else:
			headerSetup.label(text = "No cutscene header for this index.", icon = "ERROR")

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

def drawExitProperty(layout, exitProp, index, headerIndex, objName):
	box = layout.box()
	box.prop(exitProp, 'expandTab', text = 'Exit ' + \
		str(index + 1), icon = 'TRIA_DOWN' if exitProp.expandTab else \
		'TRIA_RIGHT')
	if exitProp.expandTab:
		drawCollectionOps(box, index, "Exit", headerIndex, objName)
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


class OOTObjectProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	objectID : bpy.props.EnumProperty(items = ootEnumObjectID, default = 'OBJECT_HUMAN')
	objectIDCustom : bpy.props.StringProperty(default = 'OBJECT_HUMAN')

def drawObjectProperty(layout, objectProp, headerIndex, index, objName):
	objItemBox = layout.box()
	objectName = getEnumName(ootEnumObjectID, objectProp.objectID)
	objItemBox.prop(objectProp, 'expandTab', text = objectName, 
		icon = 'TRIA_DOWN' if objectProp.expandTab else \
		'TRIA_RIGHT')
	if objectProp.expandTab:
		drawCollectionOps(objItemBox, index, "Object", headerIndex, objName)
		
		objSearch = objItemBox.operator(OOT_SearchObjectEnumOperator.bl_idname, icon = 'VIEWZOOM')
		objSearch.objName = objName
		objItemBox.column().label(text = "ID: " + objectName)
		#prop_split(objItemBox, objectProp, "objectID", name = "ID")
		if objectProp.objectID == "Custom":
			prop_split(objItemBox, objectProp, "objectIDCustom", "Object ID Custom")
		objSearch.headerIndex = headerIndex if headerIndex is not None else 0
		objSearch.index = index

class OOTLightProperty(bpy.types.PropertyGroup):
	ambient : bpy.props.FloatVectorProperty(name = "Ambient Color", size = 4, min = 0, max = 1, default = (70/255, 40/255, 57/255 ,1), subtype = 'COLOR')
	useCustomDiffuse0 : bpy.props.BoolProperty(name = 'Use Custom Diffuse 0 Light Object')
	useCustomDiffuse1 : bpy.props.BoolProperty(name = 'Use Custom Diffuse 1 Light Object')
	diffuse0 :  bpy.props.FloatVectorProperty(name = "", size = 4, min = 0, max = 1, default = (180/255, 154/255, 138/255 ,1), subtype = 'COLOR')
	diffuse1 :  bpy.props.FloatVectorProperty(name = "", size = 4, min = 0, max = 1, default = (20/255, 20/255, 60/255 ,1), subtype = 'COLOR')
	diffuse0Custom : bpy.props.PointerProperty(name = "Diffuse 0", type = bpy.types.Light)
	diffuse1Custom : bpy.props.PointerProperty(name = "Diffuse 1", type = bpy.types.Light)
	fogColor : bpy.props.FloatVectorProperty(name = "", size = 4, min = 0, max = 1, default = (140/255, 120/255, 110/255 ,1), subtype = 'COLOR')
	fogNear : bpy.props.IntProperty(name = "", default = 993, min = 0, max = 2**10 - 1)
	transitionSpeed : bpy.props.IntProperty(name = "", default = 1, min = 0, max = 63)
	fogFar : bpy.props.IntProperty(name = "", default = 0x3200, min = 0, max = 2**16 - 1)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

class OOTLightGroupProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty()
	menuTab : bpy.props.EnumProperty(items = ootEnumLightGroupMenu)
	dawn : bpy.props.PointerProperty(type = OOTLightProperty)
	day : bpy.props.PointerProperty(type = OOTLightProperty)
	dusk : bpy.props.PointerProperty(type = OOTLightProperty)
	night : bpy.props.PointerProperty(type = OOTLightProperty)
	defaultsSet : bpy.props.BoolProperty()

def drawLightGroupProperty(layout, lightGroupProp):

	box = layout.column()
	box.row().prop(lightGroupProp, 'menuTab', expand = True)
	if lightGroupProp.menuTab == "Dawn":
		drawLightProperty(box, lightGroupProp.dawn, "Dawn", False, None, None, None)
	if lightGroupProp.menuTab == "Day":
		drawLightProperty(box, lightGroupProp.day, "Day", False, None, None, None)
	if lightGroupProp.menuTab == "Dusk":
		drawLightProperty(box, lightGroupProp.dusk, "Dusk", False, None, None, None)
	if lightGroupProp.menuTab == "Night":
		drawLightProperty(box, lightGroupProp.night, "Night", False, None, None, None)
			

def drawLightProperty(layout, lightProp, name, showExpandTab, index, sceneHeaderIndex, objName):
	if showExpandTab:
		box = layout.box().column()
		box.prop(lightProp, 'expandTab', text = name,
			icon = 'TRIA_DOWN' if lightProp.expandTab else \
			'TRIA_RIGHT')
		expandTab = lightProp.expandTab
	else:
		box = layout
		expandTab = True

	if expandTab:
		if index is not None:
			drawCollectionOps(box, index, "Light", sceneHeaderIndex, objName)
		prop_split(box, lightProp, 'ambient', 'Ambient Color')
		
		if lightProp.useCustomDiffuse0:
			prop_split(box, lightProp, 'diffuse0Custom', 'Diffuse 0')
			box.label(text = "Make sure light is not part of scene hierarchy.", icon = "ERROR")
		else:
			prop_split(box, lightProp, 'diffuse0', 'Diffuse 0')
		box.prop(lightProp, "useCustomDiffuse0")
		
		if lightProp.useCustomDiffuse1:
			prop_split(box, lightProp, 'diffuse1Custom', 'Diffuse 1')
			box.label(text = "Make sure light is not part of scene hierarchy.", icon = "ERROR")
		else:
			prop_split(box, lightProp, 'diffuse1', 'Diffuse 1')
		box.prop(lightProp, "useCustomDiffuse1")
		
		prop_split(box, lightProp, 'fogColor', 'Fog Color')
		prop_split(box, lightProp, 'fogNear', 'Fog Near')
		prop_split(box, lightProp, 'fogFar', 'Fog Far')
		prop_split(box, lightProp, 'transitionSpeed', 'Transition Speed')


class OOTCSProperty():
	propName = None
	attrName = None
	subprops = ["startFrame", "endFrame"]
	expandTab : bpy.props.BoolProperty(default = True)
	startFrame : bpy.props.IntProperty(name = '', default = 0, min = 0)
	endFrame : bpy.props.IntProperty(name = '', default = 1, min = 0)
		
	def getName(self):
		return self.propName
		
	def filterProp(self, name, listProp):
		return True
	
	def filterName(self, name, listProp):
		return name
	
	def draw(self, layout, listProp, listIndex, cmdIndex, objName, headerIndex):
		layout.prop(self, 'expandTab', text = self.getName() + " " + str(cmdIndex),
			icon = 'TRIA_DOWN' if self.expandTab else 'TRIA_RIGHT')
		if not self.expandTab: return
		box = layout.box().column()
		drawCollectionOps(box, cmdIndex, 
			"CSHdr." + str(headerIndex) + "." + self.attrName, listIndex, objName)
		for p in self.subprops:
			if self.filterProp(p, listProp):
				prop_split(box, self, p, self.filterName(p, listProp))

class OOTCSTextboxProperty(OOTCSProperty, bpy.types.PropertyGroup):
	propName = "Textbox"
	attrName = "textbox"
	subprops = ["messageId", "ocarinaSongAction", "startFrame", "endFrame",
		"type", "topOptionBranch", "bottomOptionBranch", "ocarinaMessageId"]
	textboxType : bpy.props.EnumProperty(items = ootEnumCSTextboxType)
	messageId : bpy.props.StringProperty(name = '', default = '0x0000')
	ocarinaSongAction : bpy.props.StringProperty(name = '', default = '0x0000')
	type : bpy.props.StringProperty(name = '', default = '0x0000')
	topOptionBranch : bpy.props.StringProperty(name = '', default = '0x0000')
	bottomOptionBranch : bpy.props.StringProperty(name = '', default = '0x0000')
	ocarinaMessageId : bpy.props.StringProperty(name = '', default = '0x0000')
	
	def getName(self):
		return self.textboxType
	
	def filterProp(self, name, listProp):
		if self.textboxType == "Text":
			return name not in ["ocarinaSongAction", "ocarinaMessageId"]
		elif self.textboxType == "None":
			return name in ["startFrame", "endFrame"]
		elif self.textboxType == "LearnSong":
			return name in ["ocarinaSongAction", "startFrame", "endFrame", "ocarinaMessageId"]
		else:
			raise PluginError("Invalid property name for OOTCSTextboxProperty")

class OOTCSTextboxAdd(bpy.types.Operator):
	bl_idname = 'object.oot_cstextbox_add'
	bl_label = 'Add CS Textbox'
	bl_options = {'REGISTER', 'UNDO'} 

	collectionType : bpy.props.StringProperty()
	textboxType : bpy.props.EnumProperty(items = ootEnumCSTextboxType)
	listIndex : bpy.props.IntProperty()
	objName : bpy.props.StringProperty()

	def execute(self, context):
		collection = getCollection(self.objName, self.collectionType, self.listIndex)
		collection.add()
		collection[len(collection)-1].textboxType = self.textboxType
		#self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

class OOTCSLightingProperty(OOTCSProperty, bpy.types.PropertyGroup):
	propName = "Lighting"
	attrName = "lighting"
	subprops = ["index", "startFrame", 
		# "endFrame", "unused0", "unused1", "unused2",
		#"unused3", "unused4", "unused5", "unused6", "unused7"
		]
	index : bpy.props.IntProperty(name = '', default = 1, min = 1)
	# unused0 : bpy.props.StringProperty(name = '', default = '0x0000')
	# unused1 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused2 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused3 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused4 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused5 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused6 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused7 : bpy.props.StringProperty(name = '', default = '0x00000000')
	
class OOTCSTimeProperty(OOTCSProperty, bpy.types.PropertyGroup):
	propName = "Time"
	attrName = "time"
	subprops = [# "unk", 
		"startFrame", # "endFrame", 
		"hour", "minute", # "unused"
		]
	#unk : bpy.props.StringProperty(name = '', default = '0x0000')
	hour : bpy.props.IntProperty(name = '', default = 23, min = 0, max = 23)
	minute : bpy.props.IntProperty(name = '', default = 59, min = 0, max = 59)
	#unused : bpy.props.StringProperty(name = '', default = '0x00000000')
	
class OOTCSBGMProperty(OOTCSProperty, bpy.types.PropertyGroup):
	propName = "BGM"
	attrName = "bgm"
	subprops = ["value", "startFrame", "endFrame", 
		# "unused0", "unused1", "unused2",
		# "unused3", "unused4", "unused5", "unused6", "unused7"
		]
	value : bpy.props.StringProperty(name = '', default = '0x0000')
	# unused0 : bpy.props.StringProperty(name = '', default = '0x0000')
	# unused1 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused2 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused3 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused4 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused5 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused6 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused7 : bpy.props.StringProperty(name = '', default = '0x00000000')
	
	def filterProp(self, name, listProp):
		return name != "endFrame" or listProp.listType == "FadeBGM"
	
	def filterName(self, name, listProp):
		if name == 'value':
			return "Fade Type" if listProp.listType == "FadeBGM" else "Sequence"
		return name

class OOTCSMiscProperty(OOTCSProperty, bpy.types.PropertyGroup):
	propName = "Misc"
	attrName = "misc"
	subprops = ["operation", "startFrame", "endFrame", # "unused0", "unused1", "unused2", 
		# "unused3", "unused4", "unused5", "unused6", "unused7",
		# "unused8", "unused9", "unused10"
		]
	operation : bpy.props.IntProperty(name = '', default = 1, min = 1, max = 35)
	# unused0 : bpy.props.StringProperty(name = '', default = '0x0000')
	# unused1 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused2 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused3 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused4 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused5 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused6 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused7 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused8 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused9 : bpy.props.StringProperty(name = '', default = '0x00000000')
	# unused10 : bpy.props.StringProperty(name = '', default = '0x00000000')

class OOTCS0x09Property(OOTCSProperty, bpy.types.PropertyGroup):
	propName = "0x09"
	attrName = "nine"
	subprops = [# "unk", 
		"startFrame", # "endFrame", 
		"unk2", "unk3", "unk4",
		#"unused0", "unused1"
		]
	# unk : bpy.props.StringProperty(name = '', default = '0x0000')
	unk2 : bpy.props.StringProperty(name = '', default = '0x00')
	unk3 : bpy.props.StringProperty(name = '', default = '0x00')
	unk4 : bpy.props.StringProperty(name = '', default = '0x00')
	# unused0 : bpy.props.StringProperty(name = '', default = '0x00')
	# unused1 : bpy.props.StringProperty(name = '', default = '0x0000')

class OOTCSUnkProperty(OOTCSProperty, bpy.types.PropertyGroup):
	propName = "Unk"
	attrName = "unk"
	subprops = ["unk1", "unk2", "unk3", "unk4", "unk5", "unk6", "unk7",
		"unk8", "unk9", "unk10", "unk11", "unk12"]
	unk1 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk2 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk3 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk4 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk5 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk6 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk7 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk8 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk9 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk10 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk11 : bpy.props.StringProperty(name = '', default = '0x00000000')
	unk12 : bpy.props.StringProperty(name = '', default = '0x00000000')

	
class OOTCSListProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(default = True)
	
	listType : bpy.props.EnumProperty(items = ootEnumCSListType)
	textbox : bpy.props.CollectionProperty(type = OOTCSTextboxProperty)
	lighting: bpy.props.CollectionProperty(type = OOTCSLightingProperty)
	time : bpy.props.CollectionProperty(type = OOTCSTimeProperty)
	bgm : bpy.props.CollectionProperty(type = OOTCSBGMProperty)
	misc : bpy.props.CollectionProperty(type = OOTCSMiscProperty)
	nine : bpy.props.CollectionProperty(type = OOTCS0x09Property)
	unk : bpy.props.CollectionProperty(type = OOTCSUnkProperty)
	
	unkType : bpy.props.StringProperty(name = '', default = '0x0001')
	fxType : bpy.props.EnumProperty(items = ootEnumCSTransitionType)
	fxStartFrame : bpy.props.IntProperty(name = '', default = 0, min = 0)
	fxEndFrame : bpy.props.IntProperty(name = '', default = 1, min = 0)

def drawCSListProperty(layout, listProp, listIndex, objName, headerIndex):
	layout.prop(listProp, 'expandTab', 
		text = listProp.listType + ' List' if listProp.listType != 'FX' else 'Scene Trans FX',
		icon = 'TRIA_DOWN' if listProp.expandTab else 'TRIA_RIGHT')
	if not listProp.expandTab: return
	box = layout.box().column()
	drawCollectionOps(box, listIndex, "CSHdr." + str(headerIndex), None, objName, False)
	
	if listProp.listType == "Textbox":
		attrName = "textbox"
	elif listProp.listType == "FX":
		prop_split(box, listProp, 'fxType', 'Transition')
		prop_split(box, listProp, 'fxStartFrame', 'Start Frame')
		prop_split(box, listProp, 'fxEndFrame', 'End Frame')
		return
	elif listProp.listType == "Lighting":
		attrName = "lighting"
	elif listProp.listType == "Time":
		attrName = "time"
	elif listProp.listType in ["PlayBGM", "StopBGM", "FadeBGM"]:
		attrName = "bgm"
	elif listProp.listType == "Misc":
		attrName = "misc"
	elif listProp.listType == "0x09":
		attrName = "nine"
	elif listProp.listType == "Unk":
		prop_split(box, listProp, 'unkType', 'Unk List Type')
		attrName = "unk"
	else:
		raise PluginError("Invalid listType")
		
	dat = getattr(listProp, attrName)
	for i, p in enumerate(dat):
		p.draw(box, listProp, listIndex, i, objName, headerIndex)
	if len(dat) == 0:
		box.label(text = "No items in " + listProp.listType + " List.")
	if listProp.listType == "Textbox":
		row = box.row(align=True)
		for l in range(3):
			addOp = row.operator(OOTCSTextboxAdd.bl_idname, text = 'Add ' + ootEnumCSTextboxType[l][1], icon = ootEnumCSTextboxTypeIcons[l])
			addOp.collectionType = "CSHdr." + str(headerIndex) + '.textbox'
			addOp.textboxType = ootEnumCSTextboxType[l][0]
			addOp.listIndex = listIndex
			addOp.objName = objName
	else:
		addOp = box.operator(OOTCollectionAdd.bl_idname, text = 'Add item to ' + listProp.listType + ' List')
		addOp.option = len(dat)
		addOp.collectionType = "CSHdr." + str(headerIndex) + '.' + attrName
		addOp.subIndex = listIndex
		addOp.objName = objName


class OOTCSListAdd(bpy.types.Operator):
	bl_idname = 'object.oot_cslist_add'
	bl_label = 'Add CS List'
	bl_options = {'REGISTER', 'UNDO'} 

	collectionType : bpy.props.StringProperty()
	listType : bpy.props.EnumProperty(items = ootEnumCSListType)
	objName : bpy.props.StringProperty()

	def execute(self, context):
		collection = getCollection(self.objName, self.collectionType, None)
		collection.add()
		collection[len(collection)-1].listType = self.listType
		#self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

def drawCSAddButtons(layout, objName, headerIndex):
	def addButton(row):
		nonlocal l
		op = row.operator(OOTCSListAdd.bl_idname, text = ootEnumCSListType[l][1], icon = ootEnumCSListTypeIcons[l])
		op.collectionType = "CSHdr." + str(headerIndex)
		op.listType = ootEnumCSListType[l][0]
		op.objName = objName
		l += 1
	box = layout.column(align=True)
	l = 0
	row = box.row(align=True)
	row.label(text = 'Add:')
	addButton(row)
	for _ in range(3):
		row = box.row(align=True)
		for _ in range(3):
			addButton(row)
	box.label(text = 'Install zcamedit for camera/actor motion.')


class OOTSceneTableEntryProperty(bpy.types.PropertyGroup):
	drawConfig : bpy.props.IntProperty(name = "Scene Draw Config", min = 0)
	hasTitle : bpy.props.BoolProperty(default = True)

class OOTSceneHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	usePreviousHeader : bpy.props.BoolProperty(name = "Use Previous Header", default = True)

	globalObject : bpy.props.EnumProperty(name = "Global Object", default = "0x0002", items = ootEnumGlobalObject)
	globalObjectCustom : bpy.props.StringProperty(name = "Global Object Custom", default = "0x00")
	naviCup : bpy.props.EnumProperty(name = "Navi Hints", default = '0x00', items = ootEnumNaviHints)
	naviCupCustom : bpy.props.StringProperty(name = "Navi Hints Custom", default = '0x00')

	skyboxID : bpy.props.EnumProperty(name = "Skybox", items = ootEnumSkybox, default = "0x01")
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

	timeOfDayLights : bpy.props.PointerProperty(type = OOTLightGroupProperty, name = "Time Of Day Lighting")
	lightList : bpy.props.CollectionProperty(type = OOTLightProperty, name = 'Lighting List')
	exitList : bpy.props.CollectionProperty(type = OOTExitProperty, name = "Exit List")

	writeCutscene : bpy.props.BoolProperty(name = "Write Cutscene")
	csEndFrame : bpy.props.IntProperty(name = "End Frame", min = 0, default = 100)
	csWriteTerminator : bpy.props.BoolProperty(name = "Write Terminator (Code Execution)")
	csTermIdx : bpy.props.IntProperty(name = "Index", min = 0)
	csTermStart : bpy.props.IntProperty(name = "Start Frm", min = 0, default = 99)
	csTermEnd : bpy.props.IntProperty(name = "End Frm", min = 0, default = 100)
	csLists : bpy.props.CollectionProperty(type = OOTCSListProperty, name = 'Cutscene Lists')

	sceneTableEntry : bpy.props.PointerProperty(type = OOTSceneTableEntryProperty)

	menuTab : bpy.props.EnumProperty(name = "Menu", items = ootEnumSceneMenu)
	altMenuTab : bpy.props.EnumProperty(name = "Menu", items = ootEnumSceneMenuAlternate)

def drawSceneTableEntryProperty(layout, sceneTableEntryProp):
	prop_split(layout, sceneTableEntryProp, "drawConfig", "Draw Config")
	
def drawSceneHeaderProperty(layout, sceneProp, dropdownLabel, headerIndex, objName):
	if dropdownLabel is not None:
		layout.prop(sceneProp, 'expandTab', text = dropdownLabel, 
			icon = 'TRIA_DOWN' if sceneProp.expandTab else 'TRIA_RIGHT')
		if not sceneProp.expandTab:
			return
	if headerIndex is not None and headerIndex > 3:
		drawCollectionOps(layout, headerIndex - 4, "Scene", None, objName)

	if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
		layout.prop(sceneProp, "usePreviousHeader", text = "Use Previous Header")
		if sceneProp.usePreviousHeader:
			return

	if headerIndex is None or headerIndex == 0:
		layout.row().prop(sceneProp, "menuTab", expand = True)
		menuTab = sceneProp.menuTab
	else:
		layout.row().prop(sceneProp, "altMenuTab", expand = True)
		menuTab = sceneProp.altMenuTab

	if menuTab == 'General':
		general = layout.column()
		general.box().label(text = "General")
		if headerIndex is None or headerIndex == 0:
			drawSceneTableEntryProperty(layout, sceneProp.sceneTableEntry)
		drawEnumWithCustom(general, sceneProp, 'globalObject', "Global Object", "")
		drawEnumWithCustom(general, sceneProp, 'naviCup', "Navi Hints", "")

		skyboxAndSound = layout.column()
		skyboxAndSound.box().label(text = "Skybox And Sound")
		drawEnumWithCustom(skyboxAndSound, sceneProp, 'skyboxID', "Skybox", "")
		drawEnumWithCustom(skyboxAndSound, sceneProp, 'skyboxCloudiness', "Cloudiness", "")
		drawEnumWithCustom(skyboxAndSound, sceneProp, 'musicSeq', "Music Sequence", "")
		musicSearch = skyboxAndSound.operator(OOT_SearchMusicSeqEnumOperator.bl_idname, icon = 'VIEWZOOM')
		musicSearch.objName = objName
		musicSearch.headerIndex = headerIndex if headerIndex is not None else 0
		drawEnumWithCustom(skyboxAndSound, sceneProp, 'nightSeq', "Nighttime SFX", "")
		drawEnumWithCustom(skyboxAndSound, sceneProp, 'audioSessionPreset', "Audio Session Preset", "")

		cameraAndWorldMap = layout.column()
		cameraAndWorldMap.box().label(text = "Camera And World Map")
		drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'mapLocation', "Map Location", "")
		drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'cameraMode', "Camera Mode", "")

	elif menuTab == 'Lighting':
		lighting = layout.column()
		lighting.box().label(text = "Lighting List")
		drawEnumWithCustom(lighting, sceneProp, 'skyboxLighting', "Lighting Mode", "")
		if sceneProp.skyboxLighting == '0x00': # Time of Day
			drawLightGroupProperty(lighting, sceneProp.timeOfDayLights)
		else:
			for i in range(len(sceneProp.lightList)):
				drawLightProperty(lighting, sceneProp.lightList[i], "Lighting " + str(i), True, i, headerIndex, objName)
			drawAddButton(lighting, len(sceneProp.lightList), "Light", headerIndex, objName)

	elif menuTab == 'Cutscene':
		cutscene = layout.column()
		r = cutscene.row()
		r.prop(sceneProp, "writeCutscene", text = "Write Cutscene")
		if not sceneProp.writeCutscene:
			return
		r.prop(sceneProp, "csEndFrame", text = "End Frame")
		cutscene.prop(sceneProp, "csWriteTerminator", text = "Write Terminator (Code Execution)")
		if sceneProp.csWriteTerminator:
			r = cutscene.row()
			r.prop(sceneProp, "csTermIdx", text = "Index")
			r.prop(sceneProp, "csTermStart", text = "Start Frm")
			r.prop(sceneProp, "csTermEnd", text = "End Frm")
		tempHeaderIndex = 0 if headerIndex is None else headerIndex
		for i, p in enumerate(sceneProp.csLists):
			drawCSListProperty(cutscene, p, i, objName, tempHeaderIndex)
		drawCSAddButtons(cutscene, objName, tempHeaderIndex)

	elif menuTab == 'Exits':
		if headerIndex is None or headerIndex == 0:
			exitBox = layout.column()
			exitBox.box().label(text = "Exit List")
			for i in range(len(sceneProp.exitList)):
				drawExitProperty(exitBox, sceneProp.exitList[i], i, headerIndex, objName)
			
			drawAddButton(exitBox, len(sceneProp.exitList), "Exit", headerIndex, objName)
		else:
			layout.label(text = "Exits are edited in main header.")

class OOTRoomHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	menuTab : bpy.props.EnumProperty(items = ootEnumRoomMenu)
	altMenuTab : bpy.props.EnumProperty(items = ootEnumRoomMenuAlternate)
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
	defaultCullDistance : bpy.props.IntProperty(name = "Default Cull Distance", min = 1, default = 100)

def drawRoomHeaderProperty(layout, roomProp, dropdownLabel, headerIndex, objName):

	if dropdownLabel is not None:
		layout.prop(roomProp, 'expandTab', text = dropdownLabel, 
			icon = 'TRIA_DOWN' if roomProp.expandTab else 'TRIA_RIGHT')
		if not roomProp.expandTab:
			return
	if headerIndex is not None and headerIndex > 3:
		drawCollectionOps(layout, headerIndex - 4, "Room", None, objName)

	if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
		layout.prop(roomProp, "usePreviousHeader", text = "Use Previous Header")
		if roomProp.usePreviousHeader:
			return

	if headerIndex is None or headerIndex == 0:
		layout.row().prop(roomProp, "menuTab", expand = True)
		menuTab = roomProp.menuTab
	else:
		layout.row().prop(roomProp, "altMenuTab", expand = True)
		menuTab = roomProp.altMenuTab

	if menuTab == "General":
		if headerIndex is None or headerIndex == 0:
			general = layout.column()
			general.box().label(text = "General")
			prop_split(general, roomProp, 'roomIndex', 'Room Index')
			prop_split(general, roomProp, 'meshType', "Mesh Type")
			if roomProp.meshType == '1':
				general.box().label(text = "Mesh Type 1 not supported at this time.")
			if roomProp.meshType == '2':
				prop_split(general, roomProp, 'defaultCullDistance', 'Default Cull (Blender Units)')

		# Behaviour
		behaviourBox = layout.column()
		behaviourBox.box().label(text = 'Behaviour')
		drawEnumWithCustom(behaviourBox, roomProp, "roomBehaviour", "Room Behaviour", "")
		drawEnumWithCustom(behaviourBox, roomProp, 'linkIdleMode', "Link Idle Mode", "")
		behaviourBox.prop(roomProp, "disableWarpSongs", text = "Disable Warp Songs")
		behaviourBox.prop(roomProp, "showInvisibleActors", text = "Show Invisible Actors")

		# Time
		skyboxAndTime = layout.column()
		skyboxAndTime.box().label(text = "Skybox And Time")

		# Skybox
		skyboxAndTime.prop(roomProp, "disableSkybox", text = "Disable Skybox")
		skyboxAndTime.prop(roomProp, "disableSunMoon", text = "Disable Sun/Moon")
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

		# Wind 
		windBox = layout.column()
		windBox.box().label(text = 'Wind')
		windBox.prop(roomProp, "setWind", text = "Set Wind")
		if roomProp.setWind:
			windBox.row().prop(roomProp, "windVector", text = '')
			#prop_split(windBox, roomProp, "windVector", "Wind Vector")
	
	elif menuTab == "Objects":
		objBox = layout.column()
		objBox.box().label(text = "Objects")
		for i in range(len(roomProp.objectList)):
			drawObjectProperty(objBox, roomProp.objectList[i], headerIndex, i, objName)
		drawAddButton(objBox, len(roomProp.objectList), "Object", headerIndex, objName)

class OOTAlternateSceneHeaderProperty(bpy.types.PropertyGroup):
	childNightHeader : bpy.props.PointerProperty(name = "Child Night Header", type = OOTSceneHeaderProperty)
	adultDayHeader : bpy.props.PointerProperty(name = "Adult Day Header", type = OOTSceneHeaderProperty)
	adultNightHeader : bpy.props.PointerProperty(name = "Adult Night Header", type = OOTSceneHeaderProperty)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTSceneHeaderProperty)

	headerMenuTab : bpy.props.EnumProperty(name = "Header Menu", items = ootEnumHeaderMenu)
	currentCutsceneIndex : bpy.props.IntProperty(min = 4, default = 4)

def drawAlternateSceneHeaderProperty(layout, headerProp, objName):
	headerSetup = layout.column()
	#headerSetup.box().label(text = "Alternate Headers")
	headerSetupBox = headerSetup.column()

	headerSetupBox.row().prop(headerProp, "headerMenuTab", expand = True)
	if headerProp.headerMenuTab == "Child Night":
		drawSceneHeaderProperty(headerSetupBox, headerProp.childNightHeader, None, 1, objName)
	elif headerProp.headerMenuTab == "Adult Day":
		drawSceneHeaderProperty(headerSetupBox, headerProp.adultDayHeader, None, 2, objName)
	elif headerProp.headerMenuTab == "Adult Night":
		drawSceneHeaderProperty(headerSetupBox, headerProp.adultNightHeader, None, 3, objName)
	elif headerProp.headerMenuTab == "Cutscene":
		prop_split(headerSetup, headerProp, 'currentCutsceneIndex', "Cutscene Index")
		drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Scene", None, objName)
		index = headerProp.currentCutsceneIndex
		if index - 4 < len(headerProp.cutsceneHeaders):
			drawSceneHeaderProperty(headerSetup, headerProp.cutsceneHeaders[index - 4], None, index, objName)
		else:
			headerSetup.label(text = "No cutscene header for this index.", icon = "ERROR")

class OOTAlternateRoomHeaderProperty(bpy.types.PropertyGroup):
	childNightHeader : bpy.props.PointerProperty(name = "Child Night Header", type = OOTRoomHeaderProperty)
	adultDayHeader : bpy.props.PointerProperty(name = "Adult Day Header", type = OOTRoomHeaderProperty)
	adultNightHeader : bpy.props.PointerProperty(name = "Adult Night Header", type = OOTRoomHeaderProperty)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTRoomHeaderProperty)

	headerMenuTab : bpy.props.EnumProperty(name = "Header Menu", items = ootEnumHeaderMenu)
	currentCutsceneIndex : bpy.props.IntProperty(min = 4, default = 4)

def drawParentSceneRoom(box, obj):
	sceneObj = getSceneObj(obj)
	roomObj = getRoomObj(obj)

	#box = layout.box().column()
	box.box().column().label(text = "Parent Scene/Room Settings")
	box.row().prop(obj, 'ootObjectMenu', expand = True)
	
	if obj.ootObjectMenu == "Scene":
		if sceneObj is not None:
			drawSceneHeaderProperty(box, sceneObj.ootSceneHeader, None, None, sceneObj.name)
			if sceneObj.ootSceneHeader.menuTab == 'Alternate':
				drawAlternateSceneHeaderProperty(box, sceneObj.ootAlternateSceneHeaders, sceneObj.name)
		else:
			box.label(text = "This object is not part of any Scene hierarchy.", icon = "ERROR")
	
	elif obj.ootObjectMenu == "Room":
		if roomObj is not None:
			drawRoomHeaderProperty(box, roomObj.ootRoomHeader, None, None, roomObj.name)
			if roomObj.ootRoomHeader.menuTab == 'Alternate':
				drawAlternateRoomHeaderProperty(box, roomObj.ootAlternateRoomHeaders, roomObj.name)
		else:
			box.label(text = "This object is not part of any Room hierarchy.", icon = "ERROR")
