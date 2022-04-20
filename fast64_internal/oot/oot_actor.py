import bpy

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from ..utility import *
from .oot_operators import *

# General classes and functions

class OOT_SearchChestContentEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_chest_content_enum_operator"
	bl_label = "Select Chest Content"
	bl_property = "itemChest"
	bl_options = {'REGISTER', 'UNDO'}

	itemChest : bpy.props.EnumProperty(items = ootChestContent, default = 'item_heart')
	objName : bpy.props.StringProperty()

	def execute(self, context):
		for listNode in root:
			if listNode.tag == 'List' and listNode.get('Name') == 'Chest Content':
				for elem in listNode:
					if elem.get('Key') == self.itemChest:
						bpy.data.objects[self.objName].fast64.oot.actor.itemChest = elem.get('Value')
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
		for listNode in root:
			if listNode.tag == 'List' and listNode.get('Name') == 'Elf_Msg Message ID':
				for elem in listNode:
					if elem.get('Key') == self.naviMsgID:
						bpy.data.objects[self.objName].fast64.oot.actor.naviMsgID = elem.get('Value')
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.naviMsgID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTActorProperties(bpy.types.PropertyGroup):
	# Each prop has its 'custom' variant because of the get and set functions
	# Actors/Entrance Actor
	actorID : bpy.props.StringProperty(name='Actor ID', default='ACTOR_PLAYER')
	actorKey : bpy.props.EnumProperty(name='Actor Key', items=ootEnumActorID)
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000',
		get=lambda self: getValues(self, self.actorKey, 'actorParam', 'Params', None),
		set=lambda self, value: setValues(self, value, 'Params', 'actorID'))
	actorParamCustom : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

	# Rotations
	rotOverride : bpy.props.BoolProperty(name = 'Rot Override', default = False)
	rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0x0',
		get=lambda self: getValues(self, self.actorKey, 'rotOverrideX', 'XRot', None),
		set=lambda self, value: setValues(self, value, 'XRot', 'actorID'))
	rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0x0',
		get=lambda self: getValues(self, self.actorKey, 'rotOverrideY', 'YRot', None),
		set=lambda self, value: setValues(self, value, 'YRot', 'actorID'))
	rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0x0',
		get=lambda self: getValues(self, self.actorKey, 'rotOverrideZ', 'ZRot', None),
		set=lambda self, value: setValues(self, value, 'ZRot', 'actorID'))
	rotOverrideXCustom : bpy.props.StringProperty(name = 'Rot X', default = '0x0')
	rotOverrideYCustom : bpy.props.StringProperty(name = 'Rot Y', default = '0x0')
	rotOverrideZCustom : bpy.props.StringProperty(name = 'Rot Z', default = '0x0')

	# Transition Actors
	transActorID : bpy.props.StringProperty(name='Transition Actor ID', default='ACTOR_EN_DOOR')
	transActorKey : bpy.props.EnumProperty(name='Transition Actor ID', items=ootEnumTransitionActorID)
	transActorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000',
		get=lambda self: getValues(self, self.transActorKey, 'actorParam', 'Params', 'transActorParam'),
		set=lambda self, value: setValues(self, value, 'Params', 'transActorID'))
	transActorParamCustom : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

	# Other
	itemChest : bpy.props.StringProperty(name='Chest Content', default = '0x48')
	naviMsgID : bpy.props.StringProperty(name='Navi Message ID', default = '0x00')

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

def getValues(self, actorKey, actorField, target, paramField):
	'''Updates the actor parameter field when the user changes the options'''
	if bpy.context.object.fast64.oot.version == bpy.context.object.fast64.oot.cur_version:
		actorProp = bpy.context.object.fast64.oot.actor
		value = ""
		if actorKey == 'Custom' or (bpy.context.view_layer.objects.active.ootEmptyType == 'Entrance'
			and bpy.context.object.ootEntranceProperty.customActor):
			if target == 'Params':
				return self.actorParamCustom
			if self.rotOverride:
				if target == 'XRot':
					return self.rotOverrideXCustom
				if target == 'YRot':
					return self.rotOverrideYCustom
				if target == 'ZRot':
					return self.rotOverrideZCustom
		else:
			for actorNode in root:
				if actorNode.get('Key') == actorKey:
					for elem in actorNode:
						paramTarget = elem.get('Target')
						if paramTarget is None:
							paramTarget = 'Params'
						if paramTarget == target:
							tiedParam = elem.get('TiedParam')
							actorType = getattr(self, actorKey + '.type', None)
							if hasActorTiedParams(tiedParam, actorType):
								value = getActorParameter(actorProp, actorKey, paramTarget, None)
		return value
	else:
		if paramField == 'transActorParam':
			actorProp = bpy.context.object.ootTransitionActorProperty.actor
		else:
			actorProp = bpy.context.object.ootActorProperty
		if actorField is not None:
			return getattr(actorProp, actorField)
		else:
			raise PluginError("Can't return the proper value")

def setValues(self, value, paramTarget, field):
	'''Reverse the process to set the options of the current actor'''
	if self.actorKey == "Custom" or (bpy.context.view_layer.objects.active.ootEmptyType == 'Entrance'
			and bpy.context.object.ootEntranceProperty.customActor):
		if paramTarget == 'Params':
			self.actorParamCustom = value
		if self.rotOverride:
			if paramTarget == 'XRot':
				self.rotOverrideXCustom = value
			if paramTarget == 'YRot':
				self.rotOverrideYCustom = value
			if paramTarget == 'ZRot':
				self.rotOverrideZCustom = value
	else:
		for actorNode in root:
			if actorNode.get('ID') == getattr(self, field, '0x0'):
				dPKey = actorNode.get('Key')
				lenProp = getActorLastElemIndex(dPKey, 'Property', None)
				lenSwitch = getActorLastElemIndex(dPKey, 'Flag', 'Switch')
				lenBool = getActorLastElemIndex(dPKey, 'Bool', None)
				lenEnum = getActorLastElemIndex(dPKey, 'Enum', None)
				for elem in actorNode:
					tiedParam = elem.get('TiedParam')
					actorType = getattr(self, dPKey + '.type', None)
					if hasActorTiedParams(tiedParam, actorType) is True:
						if isinstance(value, bool):
							if value:
								param = '0x1'
							else:
								param = '0x0'
						else:
							param = value
						setActorParameter(elem, eval(param), self, dPKey, lenProp, lenSwitch, lenBool, lenEnum, paramTarget)

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

def drawOperatorBox(layout, obj, name, labelText, searchOp):
	searchOp.objName = obj
	split = layout.split(factor=0.5)
	split.label(text=labelText)
	split.label(text=name)

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
			prop_split(userLayout, detailedProp, "actorID", "Actor ID Custom")

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
			if userActorID is not None and userActorID == detailedProp.actorID:
				if dpKey == 'en_box':
					enumValue = detailedProp.itemChest
				elif dpKey == 'elf_msg':
					enumValue = detailedProp.naviMsgID
				else:
					enumValue = None

				if enumValue is not None:
					for listNode in root:
						listName = listNode.get('Name')
						if listNode.tag == 'List' and (listName == 'Elf_Msg Message ID' or listName == 'Chest Content'):
							for elem in listNode:
								if elem.get('Value') == enumValue:
									enumName = elem.get('Name')

				for actorNode in root:
					if actorNode.get('ID') == userActorID:
						for elem in actorNode:
							if elem.tag == 'ChestContent':
								# Draw chest content searchbox
								searchOp = userLayout.operator(OOT_SearchChestContentEnumOperator.bl_idname, icon='VIEWZOOM')
								drawOperatorBox(userLayout, userObj, enumName, 'Chest Content', searchOp)
							if elem.tag == 'Message':
								# Draw Navi message ID searchbox
								searchOp = userLayout.operator(OOT_SearchNaviMsgIDEnumOperator.bl_idname, icon='VIEWZOOM')
								drawOperatorBox(userLayout, userObj, detailedProp.naviMsgID, 'Message ID', searchOp)

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
		actorID = getIDFromKey(self.actorKey)
		if actorID is not None:
			detailedProp.actorID = obj.ootActorProperty.actorID = actorID
			detailedProp.actorKey = self.actorKey
			if self.transActorKey == 'Custom':
				detailedProp.transActorKey = self.actorKey

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
			OOT_SearchActorIDEnumOperator, 'actorID', 'actorParam', detailedProp.actor, detailedProp.actor.actorKey)
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
		actorID = getIDFromKey(self.transActorKey)
		if actorID is not None:
			detailedProp.transActorID = actorID
			detailedProp.transActorKey = self.transActorKey
			if self.transActorKey == 'Custom':
				detailedProp.actorKey = self.transActorKey

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
			OOT_SearchTransActorIDEnumOperator, 'transActorID', 'transActorParam', detailedProp.actor, detailedProp.actor.transActorKey)
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
			None, 'actorID', 'actorParam', detailedProp.actor, 'player')
		drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
