import bpy
from .oot_constants import ootEnumActorID, ootEnumSceneSetupPreset, ootEnumCamTransition
from ..utility import PluginError, prop_split, label_split
from .oot_utility import getRoomObj, getEnumName, drawAddButton, drawCollectionOps, drawEnumWithCustom


class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_actor_id_enum_operator"
	bl_label = "Select Actor ID"
	bl_property = "actorID"
	bl_options = {'REGISTER', 'UNDO'}

	actorID : bpy.props.EnumProperty(items = ootEnumActorID, default = "ACTOR_PLAYER")
	actorUser : bpy.props.StringProperty(default = "Actor")
	objName : bpy.props.StringProperty()

	def execute(self, context):
		obj = bpy.data.objects[self.objName]
		if self.actorUser == "Transition Actor":
			obj.ootTransitionActorProperty.actor.actorID = self.actorID
		elif self.actorUser == "Actor":
			obj.ootActorProperty.actorID = self.actorID
		elif self.actorUser == "Entrance":
			obj.ootEntranceProperty.actor.actorID = self.actorID
		else:
			raise PluginError("Invalid actor user for search: " + str(self.actorUser))

		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.actorID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
	headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

class OOTActorHeaderProperty(bpy.types.PropertyGroup):
	sceneSetupPreset : bpy.props.EnumProperty(name = "Scene Setup Preset", items = ootEnumSceneSetupPreset, default = "All Scene Setups")
	childDayHeader : bpy.props.BoolProperty(name = "Child Day Header", default = True)
	childNightHeader : bpy.props.BoolProperty(name = "Child Night Header", default = True)
	adultDayHeader : bpy.props.BoolProperty(name = "Adult Day Header", default = True)
	adultNightHeader : bpy.props.BoolProperty(name = "Adult Night Header", default = True)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTActorHeaderItemProperty)

def drawActorHeaderProperty(layout, headerProp, propUser, altProp, objName):
	headerSetup = layout.column()
	#headerSetup.box().label(text = "Alternate Headers")
	prop_split(headerSetup, headerProp, "sceneSetupPreset", "Scene Setup Preset")
	if headerProp.sceneSetupPreset == "Custom":
		headerSetupBox = headerSetup.column()
		headerSetupBox.prop(headerProp, 'childDayHeader', text = "Child Day")
		prevHeaderName = 'childDayHeader'
		childNightRow = headerSetupBox.row()
		if altProp is None or altProp.childNightHeader.usePreviousHeader:
			# Draw previous header checkbox (so get previous state), but labeled
			# as current one and grayed out
			childNightRow.prop(headerProp, prevHeaderName, text = "Child Night")
			childNightRow.enabled = False
		else:
			childNightRow.prop(headerProp, 'childNightHeader', text = "Child Night")
			prevHeaderName = 'childNightHeader'
		adultDayRow = headerSetupBox.row()
		if altProp is None or altProp.adultDayHeader.usePreviousHeader:
			adultDayRow.prop(headerProp, prevHeaderName, text = "Adult Day")
			adultDayRow.enabled = False
		else:
			adultDayRow.prop(headerProp, 'adultDayHeader', text = "Adult Day")
			prevHeaderName = 'adultDayHeader'
		adultNightRow = headerSetupBox.row()
		if altProp is None or altProp.adultNightHeader.usePreviousHeader:
			adultNightRow.prop(headerProp, prevHeaderName, text = "Adult Night")
			adultNightRow.enabled = False
		else:
			adultNightRow.prop(headerProp, 'adultNightHeader', text = "Adult Night")

		headerSetupBox.row().label(text = 'Cutscene headers to include this actor in:')
		for i in range(len(headerProp.cutsceneHeaders)):
			drawActorHeaderItemProperty(headerSetup, propUser, headerProp.cutsceneHeaders[i], i, altProp, objName)
		drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), propUser, None, objName)

def drawActorHeaderItemProperty(layout, propUser, headerItemProp, index, altProp, objName):
	box = layout.box()
	box.prop(headerItemProp, 'expandTab', text = 'Header ' + \
		str(headerItemProp.headerIndex), icon = 'TRIA_DOWN' if headerItemProp.expandTab else \
		'TRIA_RIGHT')

	if headerItemProp.expandTab:
		drawCollectionOps(box, index, propUser, None, objName)
		prop_split(box, headerItemProp, 'headerIndex', 'Header Index')
		if altProp is not None and headerItemProp.headerIndex >= len(altProp.cutsceneHeaders) + 4:
			box.label(text = "Header does not exist.", icon = 'QUESTION')

class OOTActorProperty(bpy.types.PropertyGroup):
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
	rotOverride : bpy.props.BoolProperty(name = 'Override Rotation', default = False)
	rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0')
	rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0')
	rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0')
	headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

def drawActorProperty(layout, actorProp, altRoomProp, objName):
	#prop_split(layout, actorProp, 'actorID', 'Actor')
	actorIDBox = layout.column()
	#actorIDBox.box().label(text = "Settings")
	searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon = 'VIEWZOOM')
	searchOp.actorUser = "Actor"
	searchOp.objName = objName

	split = actorIDBox.split(factor = 0.5)
	split.label(text = "Actor ID")
	split.label(text = getEnumName(ootEnumActorID, actorProp.actorID))

	if actorProp.actorID == 'Custom':
		#actorIDBox.prop(actorProp, 'actorIDCustom', text = 'Actor ID')
		prop_split(actorIDBox, actorProp, 'actorIDCustom', '')

	#layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
	prop_split(actorIDBox, actorProp, "actorParam", 'Actor Parameter')

	actorIDBox.prop(actorProp, 'rotOverride', text = 'Override Rotation (ignore Blender rot)')
	if actorProp.rotOverride:
		prop_split(actorIDBox, actorProp, 'rotOverrideX', 'Rot X')
		prop_split(actorIDBox, actorProp, 'rotOverrideY', 'Rot Y')
		prop_split(actorIDBox, actorProp, 'rotOverrideZ', 'Rot Z')

	drawActorHeaderProperty(actorIDBox, actorProp.headerSettings, "Actor", altRoomProp, objName)

class OOTTransitionActorProperty(bpy.types.PropertyGroup):
	roomIndex : bpy.props.IntProperty(min = 0)
	cameraTransitionFront : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionFrontCustom : bpy.props.StringProperty(default = '0x00')
	cameraTransitionBack : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionBackCustom : bpy.props.StringProperty(default = '0x00')

	actor : bpy.props.PointerProperty(type = OOTActorProperty)

def drawTransitionActorProperty(layout, transActorProp, altSceneProp, roomObj, objName):
	actorIDBox = layout.column()
	#actorIDBox.box().label(text = "Properties")
	#prop_split(actorIDBox, transActorProp, 'actorID', 'Actor')
	#actorIDBox.box().label(text = "Actor ID: " + getEnumName(ootEnumActorID, transActorProp.actor.actorID))
	searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon = 'VIEWZOOM')
	searchOp.actorUser = "Transition Actor"
	searchOp.objName = objName

	split = actorIDBox.split(factor = 0.5)
	split.label(text = "Actor ID")
	split.label(text = getEnumName(ootEnumActorID, transActorProp.actor.actorID))

	if transActorProp.actor.actorID == 'Custom':
		prop_split(actorIDBox, transActorProp.actor, 'actorIDCustom', '')

	#layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
	prop_split(actorIDBox, transActorProp.actor, "actorParam", 'Actor Parameter')

	if roomObj is None:
		actorIDBox.label(text = "This must be part of a Room empty's hierarchy.", icon = 'OUTLINER')
	else:
		label_split(actorIDBox, "Room To Transition From", str(roomObj.ootRoomHeader.roomIndex))
	prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
	actorIDBox.label(text = "Y+ side of door faces toward the \"from\" room.", icon = 'ORIENTATION_NORMAL')
	drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
	drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

	drawActorHeaderProperty(actorIDBox, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName)

class OOTEntranceProperty(bpy.types.PropertyGroup):
	# This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
	spawnIndex : bpy.props.IntProperty(min = 0)
	customActor : bpy.props.BoolProperty(name = "Use Custom Actor")
	actor : bpy.props.PointerProperty(type = OOTActorProperty)

def drawEntranceProperty(layout, obj, altSceneProp, objName):
	box = layout.column()
	#box.box().label(text = "Properties")
	roomObj = getRoomObj(obj)
	if roomObj is not None:
		split = box.split(factor = 0.5)
		split.label(text = "Room Index")
		split.label(text = str(roomObj.ootRoomHeader.roomIndex))
	else:
		box.label(text = "This must be part of a Room empty's hierarchy.", icon = 'OUTLINER')

	entranceProp = obj.ootEntranceProperty
	prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
	prop_split(box, entranceProp.actor, "actorParam", "Actor Param")
	box.prop(entranceProp, "customActor")
	if entranceProp.customActor:
		prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")

	drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
