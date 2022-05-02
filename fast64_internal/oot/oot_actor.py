import bpy

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from ..utility import *
from .oot_operators import *

# General classes

class OOT_SearchChestContentEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_chest_content_enum_operator"
	bl_label = "Select Chest Content"
	bl_property = "itemChest"
	bl_options = {'REGISTER', 'UNDO'}

	itemChest : bpy.props.EnumProperty(items = ootChestContent, default = 'item_heart')
	objName : bpy.props.StringProperty()

	def execute(self, context):
		bpy.data.objects[self.objName].fast64.oot.actor.itemChest = self.itemChest
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.itemChest)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOT_SearchNaviMsgIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_navi_msg_id_enum_operator"
	bl_label = "Select Message ID"
	bl_property = "naviMsgID"
	bl_options = {'REGISTER', 'UNDO'}

	naviMsgID : bpy.props.EnumProperty(items = ootNaviMsgID, default = "msg_00")
	objName : bpy.props.StringProperty()

	def execute(self, context):
		bpy.data.objects[self.objName].fast64.oot.actor.naviMsgID = self.naviMsgID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.naviMsgID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTActorProperties(bpy.types.PropertyGroup):
	# Each prop has its 'custom' variant because of the get and set functions
	# Actors/Entrance Actor
	actorKey : bpy.props.EnumProperty(name='Actor Key', items=ootEnumActorID)
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000',
		get=lambda self: getActorValues(self, self.actorKey, 'Params'),
		set=lambda self, value: setActorValues(self, value, self.actorKey, 'Params'))
	actorIDCustom : bpy.props.StringProperty(name='Actor ID', default='ACTOR_PLAYER')
	actorParamCustom : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

	# Rotations
	rotOverride : bpy.props.BoolProperty(name = 'Rot Override', default = False)
	rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0x0',
		get=lambda self: getActorValues(self, self.actorKey, 'XRot'),
		set=lambda self, value: setActorValues(self, value, self.actorKey, 'XRot'))
	rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0x0',
		get=lambda self: getActorValues(self, self.actorKey, 'YRot'),
		set=lambda self, value: setActorValues(self, value, self.actorKey, 'YRot'))
	rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0x0',
		get=lambda self: getActorValues(self, self.actorKey, 'ZRot'),
		set=lambda self, value: setActorValues(self, value, self.actorKey, 'ZRot'))
	rotOverrideXCustom : bpy.props.StringProperty(name = 'Rot X', default = '0x0')
	rotOverrideYCustom : bpy.props.StringProperty(name = 'Rot Y', default = '0x0')
	rotOverrideZCustom : bpy.props.StringProperty(name = 'Rot Z', default = '0x0')

	# Transition Actors
	transActorKey : bpy.props.EnumProperty(name='Transition Actor ID', items=ootEnumTransitionActorID)
	transActorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000',
		get=lambda self: getTransActorValues(self, self.transActorKey, 'Params'),
		set=lambda self, value: setTransActorValues(self, value, self.transActorKey, 'Params'))
	transActorIDCustom : bpy.props.StringProperty(name='Transition Actor ID', default='ACTOR_EN_DOOR')
	transActorParamCustom : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

	# Other
	itemChest : bpy.props.StringProperty(name='Chest Content', default = 'item_heart')
	naviMsgID : bpy.props.StringProperty(name='Navi Message ID', default = 'msg_00')

	@staticmethod
	def upgrade_object(obj):
		if obj.data is None:
			if (obj.ootEmptyType == 'Scene') or (obj.ootEmptyType == 'Room'):
				print(f"Processing '{obj.name}'...")
				for child in obj.children:
					OOTActorProperties.upgrade_object(child)
			elif ((obj.fast64.oot.version < obj.fast64.oot.cur_version) and
				(obj.ootEmptyType == 'Actor' or	obj.ootEmptyType == 'Transition Actor' or obj.ootEmptyType == 'Entrance')):
				upgradeActorInit(obj)

# Get functions

def getCustomActorValues(self, target):
	'''Returns custom actor values'''
	if target == 'Params':
		return self.actorParamCustom
	if self.rotOverride:
		if target == 'XRot':
			return self.rotOverrideXCustom
		if target == 'YRot':
			return self.rotOverrideYCustom
		if target == 'ZRot':
			return self.rotOverrideZCustom

def getCustomTransActorValues(self, target):
	'''Returns custom actor values'''
	if target == 'Params':
		return self.transActorParamCustom
	if self.rotOverride and target == 'YRot':
		return self.rotOverrideYCustom

def getParameterValue(self, actorProp, actorKey, target):
	'''Returns the actor's parameters'''
	value = ""
	for actorNode in root:
		if actorNode.get('Key') == actorKey:
			for elem in actorNode:
				paramTarget = elem.get('Target', 'Params')
				if paramTarget == target:
					if hasActorTiedParams(elem.get('TiedParam'), getattr(self, actorKey + '.type', None)):
						value = getActorParameter(actorProp, actorKey, paramTarget, None)
	return value

def getAccurateParameter(self, actorKey, target, user):
	'''Returns the custom parameters if it's a custom actor, otherwise the detailed panel parameters are returned'''
	actorProp = bpy.context.object.fast64.oot.actor
	if isActorCustom(actorKey):
		if not (user == "default"):
			return getCustomTransActorValues(self, target)
		else:
			return getCustomActorValues(self, target)
	else:
		return getParameterValue(self, actorProp, actorKey, target)

def getActorValues(self, actorKey, target):
	'''Returns the right value depending on the version'''
	if isLatestVersion():
		return getAccurateParameter(self, actorKey, target, "default")
	else:
		return getattr(bpy.context.object.ootActorProperty, getLegacyPropName(target))

def getTransActorValues(self, actorKey, target):
	'''Same as ``getActorValues`` but for transition actors'''
	if isLatestVersion():
		return getAccurateParameter(self, actorKey, target, "transition")
	else:
		return getattr(bpy.context.object.ootTransitionActorProperty.actor, getLegacyPropName(target))

def getComputedActorValues(value):
	if isinstance(value, bool):
		if value:
			param = '0x1'
		else:
			param = '0x0'
	else:
		param = value
	return eval(param)

# Set functions

def setCustomActorValues(self, value, target):
	'''Sets the custom actor's values'''
	if target == 'Params':
		self.actorParamCustom = value
	if self.rotOverride:
		if target == 'XRot':
			self.rotOverrideXCustom = value
		if target == 'YRot':
			self.rotOverrideYCustom = value
		if target == 'ZRot':
			self.rotOverrideZCustom = value

def setCustomTransActorValues(self, value, target):
	'''Sets the custom actor's values'''
	if target == 'Params':
		self.transActorParamCustom = value
	if self.rotOverride and target == 'YRot':
		self.rotOverrideYCustom = value

def setActorParameterValues(self, value, field, target):
	'''Sets the actor's parameters'''
	for actorNode in root:
		dPKey = actorNode.get('Key')
		if dPKey == getattr(self, field, '0x0'):
			for elem in actorNode:
				if hasActorTiedParams(elem.get('TiedParam'), getattr(self, dPKey + '.type', None)) is True:
					setActorParameter(elem, getComputedActorValues(value), self, dPKey,
						getActorLastElemIndex(dPKey, 'Property', None),	getActorLastElemIndex(dPKey, 'Flag', 'Switch'), 
						getActorLastElemIndex(dPKey, 'Bool', None),	getActorLastElemIndex(dPKey, 'Enum', None), target, 1)

def setActorValues(self, value, actorKey, target):
	if isActorCustom(actorKey):
		setCustomActorValues(self, value, target)
	else:
		setActorParameterValues(self, value, 'actorKey', target)

def setTransActorValues(self, value, actorKey, target):
	if isActorCustom(actorKey):
		setCustomTransActorValues(self, value, target)
	else:
		setActorParameterValues(self, value, 'transActorKey', target)

# General functions

def genEnum(annotations, key, suffix, enumList, enumName):
	'''This function is used to generate the proper enum blender property'''
	objName = key + suffix
	prop = bpy.props.EnumProperty(name=enumName, items=enumList)
	annotations[objName] = prop

def genString(annotations, key, suffix, stringName):
	'''This function is used to generate the proper string blender property'''
	objName = key + suffix
	prop = bpy.props.StringProperty(name=stringName, default='0x0')
	annotations[objName] = prop

def drawParams(box, detailedProp, key, elemField, elemName, elTag, elType, lenSwitch):
	'''Actual draw on the UI'''
	for actorNode in root:
		i = 1
		name = 'None'
		if key == actorNode.get('Key'):
			for elem in actorNode:
				# Checks if there's at least 2 Switch Flags, in this case the
				# Name will be 'Switch Flag #[number]
				# If it's not a Switch Flag, change nothing to the name
				name = elemName
				if lenSwitch is not None and int(lenSwitch) > 1:
					name = f'{elemName} #{i}'

				# Set the name to none to use the element's name instead
				# Set the name to the element's name if it's a flag and its name is set
				curName = elem.get('Name')
				if elemName is None or (elTag == 'Flag' and curName is not None):
					name = curName

				# Add the index to get the proper attribute
				field = elemField + f'{i}'
				if elTag == 'Parameter':
					field = elemField

				attr = getattr(detailedProp, field, None)
				tiedParam = elem.get('TiedParam')
				actorType = getattr(detailedProp, key + '.type', None)

				if name != 'None' and elem.tag == elTag and elType == elem.get('Type') and attr is not None:
					if hasActorTiedParams(tiedParam, actorType) is True:
						prop_split(box, detailedProp, field, name)
					i += 1

def editOOTActorProperties():
	'''This function is used to edit the OOTActorProperties class before it's registered'''
	propAnnotations = getattr(OOTActorProperties, '__annotations__', None)
	if propAnnotations is None:
		propAnnotations = {}
		OOTActorProperties.__annotations__ = propAnnotations

	# Collectible Drops List
	itemDrops = [(elem.get('Key'), elem.get('Name'),
					elem.get('Name')) for listNode in root for elem in listNode if listNode.tag == 'List'
					and listNode.get('Name') == 'Collectibles']

	# Generate the fields
	for actorNode in root:
		i_drop = i_property = i_chest = i_collectible = i_switch = i_bool = i_enum = 1
		actorKey = actorNode.get('Key')
		for elem in actorNode:
			if elem.tag == 'Property':
				genString(propAnnotations, actorKey, f'.props{i_property}', actorKey)
				i_property += 1
			elif elem.tag == 'Flag':
				if elem.get('Type') == 'Chest':
					genString(propAnnotations, actorKey, f'.chestFlag{i_chest}', 'Chest Flag')
					i_chest += 1
				elif elem.get('Type') == 'Collectible':
					genString(propAnnotations, actorKey, f'.collectibleFlag{i_collectible}', 'Collectible Flag')
					i_collectible += 1
				elif elem.get('Type') == 'Switch':
					genString(propAnnotations, actorKey, f'.switchFlag{i_switch}', 'Switch Flag')
					i_switch += 1
			elif elem.tag == 'Collectible':
				genEnum(propAnnotations, actorKey, f'.collectibleDrop{i_drop}', itemDrops, 'Collectible Drop')
			elif elem.tag == 'Parameter':
				actorTypeList = [(elem2.get('Params'), elem2.text, elem2.get('Params'))
								for actorNode2 in root for elem2 in actorNode2
								if actorNode2.get('Key') == actorKey and elem2.tag == 'Parameter']
				genEnum(propAnnotations, actorKey, '.type', actorTypeList, 'Actor Type')
			elif elem.tag == 'Bool':
				objName = actorKey + f'.bool{i_bool}'
				prop = bpy.props.BoolProperty(default=False)
				propAnnotations[objName] = prop
				i_bool += 1
			elif elem.tag == 'Enum':
				actorEnumList = [(item.get('Value'), item.get('Name'), item.get('Value'))
								for actorNode2 in root if actorNode2.get('Key') == actorKey
								for elem2 in actorNode2 if elem2.tag == 'Enum' and elem2.get('Index') == f'{i_enum}' for item in elem2]
				genEnum(propAnnotations, actorKey, f'.enum{i_enum}', actorEnumList, elem.get('Name'))
				i_enum += 1

def drawDetailedProperties(user, userProp, userLayout, userObj, userSearchOp, userIDField, userParamField, detailedProp, dpKey):
	'''This function handles the drawing of the detailed actor panel'''
	userActor = 'Actor Property'
	userEntrance = 'Entrance Property'
	entranceBool = None
	if user != userEntrance:
		# Entrance prop has specific fields to display
		userActorID = getIDFromKey(dpKey)
		searchOp = userLayout.operator(userSearchOp.bl_idname, icon = 'VIEWZOOM')
		searchOp.objName = userObj
		if user == userActor:
			actorEnum = ootEnumActorID
		else:
			actorEnum = ootEnumTransitionActorID
		currentActor = "Actor: " + getEnumName(actorEnum, dpKey)
	else:
		userLayout.prop(userProp, "customActor")
		if userProp.customActor:
			prop_split(userLayout, detailedProp, "actorIDCustom", "Actor ID Custom")

		roomObj = getRoomObj(userObj)
		if roomObj is not None:
			split = userLayout.split(factor = 0.5)
			split.label(text = "Room Index")
			split.label(text = str(roomObj.ootRoomHeader.roomIndex))
		else:
			userLayout.label(text = "This must be part of a Room empty's hierarchy.", icon = 'OUTLINER')

		prop_split(userLayout, userProp, "spawnIndex", "Spawn Index")
		entranceBool = userProp.customActor

	if (user != userEntrance and userActorID is not None and userActorID != 'Custom') or (user == userEntrance and entranceBool is False):
		# If the current actor isn't custom
		if user != userEntrance:
			userLayout.label(text = currentActor)
			typeText = 'Type'
		else:
			typeText = 'Spawn Type'

		propAnnot = getattr(detailedProp, dpKey + '.type', None)
		if propAnnot is not None:
			prop_split(userLayout, detailedProp, dpKey + '.type', typeText)

		if user == userActor:
			rotXBool = rotYBool = rotZBool = False
			if dpKey == 'en_box':
				# Draw chest content searchbox
				searchOp = userLayout.operator(OOT_SearchChestContentEnumOperator.bl_idname, icon='VIEWZOOM')
				searchOp.objName = userObj
				split = userLayout.split(factor=0.5)
				split.label(text='Chest Content')
				split.label(text=getItemAttrFromKey('Chest Content', detailedProp.itemChest, 'Name'))
			elif dpKey == 'elf_msg':
				# Draw Navi message ID searchbox
				searchOp = userLayout.operator(OOT_SearchNaviMsgIDEnumOperator.bl_idname, icon='VIEWZOOM')
				searchOp.objName = userObj
				split = userLayout.split(factor=0.5)
				split.label(text='Message ID')
				split.label(text=getItemAttrFromKey('Elf_Msg Message ID', detailedProp.naviMsgID, 'Value'))

			drawParams(userLayout, detailedProp, dpKey, dpKey + '.collectibleDrop', 'Collectible Drop', 'Collectible', 'Drop', None)
			drawParams(userLayout, detailedProp, dpKey, dpKey + '.chestFlag', 'Chest Flag', 'Flag', 'Chest', None)
			drawParams(userLayout, detailedProp, dpKey, dpKey + '.collectibleFlag', 'Collectible Flag', 'Flag', 'Collectible', None)

		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.switchFlag', 'Switch Flag', 'Flag', 'Switch', getActorLastElemIndex(dpKey, 'Flag', 'Switch'))
		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.enum', None, 'Enum', None, None)
		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.props', None, 'Property', None, None)
		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.bool', None, 'Bool', None, None)

		paramBox = userLayout.box()
		paramBox.label(text="Actor Parameter")
		params = getattr(detailedProp, userParamField, "")
		if params != "":
			paramBox.prop(detailedProp, userParamField, text="")
		else:
			paramBox.label(text="This Actor doesn't have parameters.")

		if user == userActor:
			for actorNode in root:
				if dpKey == actorNode.get('Key'):
					for elem in actorNode:
						target = elem.get('Target')
						actorType = getattr(detailedProp, dpKey + '.type', None)
						if hasActorTiedParams(elem.get('TiedParam'), actorType):
							if target == 'XRot':
								rotXBool = True
							elif target == 'YRot':
								rotYBool = True
							elif target == 'ZRot':
								rotZBool = True

			if rotXBool:
				prop_split(paramBox, detailedProp, 'rotOverrideX', 'Rot X')
			if rotYBool:
				prop_split(paramBox, detailedProp, 'rotOverrideY', 'Rot Y')
			if rotZBool:
				prop_split(paramBox, detailedProp, 'rotOverrideZ', 'Rot Z')
	else:
		# If the current actor is custom
		if user != userEntrance:
			prop_split(userLayout, detailedProp, userIDField, currentActor)
			prop_split(userLayout, detailedProp, userParamField, 'Actor Parameter')
			userLayout.prop(detailedProp, 'rotOverride', text = 'Override Rotation (ignore Blender rot)')
			if detailedProp.rotOverride:
				if user == userActor:
					prop_split(userLayout, detailedProp, 'rotOverrideX', 'Rot X')
				prop_split(userLayout, detailedProp, 'rotOverrideY', 'Rot Y')
				if user == userActor:
					prop_split(userLayout, detailedProp, 'rotOverrideZ', 'Rot Z')
		else:
			prop_split(userLayout, detailedProp, userParamField, 'Actor Parameter')

# Actor Header Item Property
class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
	headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

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

# Actor Header Property
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

# Actor Property
class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_actor_id_enum_operator"
	bl_label = "Select Actor"
	bl_property = "actorKey"
	bl_options = {'REGISTER', 'UNDO'}

	actorKey : bpy.props.EnumProperty(items = ootEnumActorID, default = "player")
	objName : bpy.props.StringProperty()

	def execute(self, context):
		obj = bpy.data.objects[self.objName]
		detailedProp = obj.fast64.oot.actor
		detailedProp.actorKey = self.actorKey

		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.actorKey)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTActorPropertiesLegacy(bpy.types.PropertyGroup):
	# Normal Actors
	# We can't delete this (for now) as it'd ignore data in older blend files
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorIDLegacy, default = 'ACTOR_PLAYER')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
	rotOverride : bpy.props.BoolProperty(name = 'Override Rotation', default = False)
	rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0x0')
	rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0x0')
	rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0x0')
	headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

def drawActorProperty(layout, actorProp, altRoomProp, objName, detailedProp):
	actorIDBox = layout.column()

	if (detailedProp.version == detailedProp.cur_version):
		drawDetailedProperties('Actor Property', actorProp, actorIDBox, objName,
			OOT_SearchActorIDEnumOperator, 'actorIDCustom', 'actorParam', detailedProp.actor, detailedProp.actor.actorKey)
		drawActorHeaderProperty(actorIDBox, actorProp.headerSettings, "Actor", altRoomProp, objName)

# Transition Actor Property
class OOT_SearchTransActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_trans_actor_id_enum_operator"
	bl_label = "Select Transition Actor"
	bl_property = "transActorKey"
	bl_options = {'REGISTER', 'UNDO'}

	transActorKey: bpy.props.EnumProperty(items = ootEnumTransitionActorID, default = "en_door")
	objName : bpy.props.StringProperty()

	def execute(self, context):
		obj = bpy.data.objects[self.objName]
		detailedProp = obj.fast64.oot.actor
		detailedProp.transActorKey = self.transActorKey

		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.transActorKey)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTTransitionActorProperty(bpy.types.PropertyGroup):
	roomIndex : bpy.props.IntProperty(min = 0)
	cameraTransitionFront : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionFrontCustom : bpy.props.StringProperty(default = '0x00')
	cameraTransitionBack : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionBackCustom : bpy.props.StringProperty(default = '0x00')
	actor : bpy.props.PointerProperty(type = OOTActorPropertiesLegacy)

def drawTransitionActorProperty(layout, transActorProp, altSceneProp, roomObj, objName, detailedProp):
	actorIDBox = layout.column()

	if (detailedProp.version == detailedProp.cur_version):
		drawDetailedProperties('Transition Property', detailedProp.actor, actorIDBox, objName,
			OOT_SearchTransActorIDEnumOperator, 'transActorIDCustom', 'transActorParam', detailedProp.actor, detailedProp.actor.transActorKey)
		if roomObj is None:
			actorIDBox.label(text = "This must be part of a Room empty's hierarchy.", icon = "ERROR")
		else:
			label_split(actorIDBox, "Room To Transition From", str(roomObj.ootRoomHeader.roomIndex))
		prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
		actorIDBox.label(text = 'Y+ side of door faces toward the "from" room.', icon = "ERROR")
		drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
		drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

		drawActorHeaderProperty(actorIDBox, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName)

# Entrance Property
class OOTEntranceProperty(bpy.types.PropertyGroup):
	# This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
	spawnIndex : bpy.props.IntProperty(min = 0)
	customActor : bpy.props.BoolProperty(name = "Use Custom Actor")
	actor : bpy.props.PointerProperty(type = OOTActorPropertiesLegacy)

def drawEntranceProperty(layout, obj, altSceneProp, objName, detailedProp):
	box = layout.column()
	entranceProp = obj.ootEntranceProperty

	if (detailedProp.version == detailedProp.cur_version):
		drawDetailedProperties('Entrance Property', entranceProp, box, None,
			None, 'actorIDCustom', 'actorParam', detailedProp.actor, 'player')
		drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
