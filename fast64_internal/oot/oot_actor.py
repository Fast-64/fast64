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

	itemChest : bpy.props.EnumProperty(items = ootChestContent, default = '0x48')
	objName : bpy.props.StringProperty()

	def execute(self, context):
		bpy.data.objects[self.objName].ootActorDetailedProperties.itemChest = self.itemChest
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

	naviMsgID : bpy.props.EnumProperty(items = ootNaviMsgID, default = "0x00")
	objName : bpy.props.StringProperty()

	def execute(self, context):
		bpy.data.objects[self.objName].ootActorDetailedProperties.naviMsgID = self.naviMsgID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.naviMsgID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTActorDetailedProperties(bpy.types.PropertyGroup):
	pass

class OOTActorParams():
	# Used as a buffer to update the values, this isn't saved in the .blend
	param: str='0x0'
	transParam: str='0x0'
	XRot: str='0x0'
	YRot: str='0x0'
	ZRot: str='0x0'
	rotBool: bool=False
	rotXBool: bool=False
	rotYBool: bool=False
	rotZBool: bool=False

def getValues(self, actorID, actorField, paramField, customField):
	'''Updates the actor parameter field when the user change the options'''
	if self.isActorSynced:
		if paramField == 'transParam': actorProp = bpy.context.object.ootTransitionActorProperty.detailedActor
		else: actorProp = bpy.context.object.ootActorDetailedProperties
		if actorID == 'Custom' and customField is not None:
			setattr(OOTActorParams, paramField, customField)

		value = getattr(OOTActorParams, paramField)
		setattr(actorProp, paramField + 'ToSave', value)

		return value
	else:
		if paramField == 'transParam': actorProp = bpy.context.object.ootTransitionActorProperty.actor
		else: actorProp = bpy.context.object.ootActorProperty
		if actorField is not None:
			return getattr(actorProp, actorField)
		else:
			raise PluginError("Can't return the proper value")

def setValues(self, value, paramTarget, field):
	'''Reverse the process to set the options of the current actor'''
	detailedProp = self
	for actorNode in root:
		if actorNode.get('ID') == getattr(detailedProp, field, '0x0'):
			dPKey = actorNode.get('Key')
			lenProp = getMaxElemIndex(dPKey, 'Property', None)
			lenSwitch = getMaxElemIndex(dPKey, 'Flag', 'Switch')
			lenBool = getMaxElemIndex(dPKey, 'Bool', None)
			lenEnum = getMaxElemIndex(dPKey, 'Enum', None)
			for elem in actorNode:
				tiedParam = elem.get('TiedParam')
				actorType = getattr(detailedProp, dPKey + '.type', None)
				if hasTiedParams(tiedParam, actorType) is True:
					if isinstance(value, bool):
						if value: param = '0x1'
						else: param = '0x0'
					else:
						param = value
					setActorString(elem, eval(param), detailedProp, dPKey, lenProp, lenSwitch, lenBool, lenEnum, paramTarget)

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
				if lenSwitch is not None:
					if int(lenSwitch) > 1: name = f'{elemName} #{i}'
					else: name = elemName
				else: name = elemName

				# Set the name to none to use the element's name instead
				# Set the name to the element's name if it's a flag and its name is set
				curName = elem.get('Name')
				if elemName == None or (elTag == 'Flag' and curName is not None): name = curName

				# Add the index to get the proper attribute
				if elTag == 'Property' or (elTag == 'Flag' and elType == 'Switch') or elTag == 'Bool' or elTag == 'Enum':
					field = elemField + f'{i}'
				else:
					field = elemField

				attr = getattr(detailedProp, field, None)
				tiedParam = elem.get('TiedParam')
				actorType = getattr(detailedProp, key + '.type', None)
				if name != 'None' and elem.tag == elTag and elType == elem.get('Type') and attr is not None:
					if hasTiedParams(tiedParam, actorType) is True:
						prop_split(box, detailedProp, field, name)
					i += 1

def drawOperatorBox(layout, obj, detailedProp, field, labelText, searchOp, enum):
	searchOp.objName = obj
	split = layout.split(factor=0.5)
	split.label(text=labelText)
	split.label(text=getEnumName(enum, getattr(detailedProp, field)))

def editDetailedProperties():
	'''This function is used to edit the OOTActorDetailedProperties class before it's registered'''
	propAnnotations = getattr(OOTActorDetailedProperties, '__annotations__', None)
	if propAnnotations is None:
		propAnnotations = {}
		OOTActorDetailedProperties.__annotations__ = propAnnotations

	# Each prop has its 'custom' variant because of the get and set functions
	# Actors/Entrance Actor
	propAnnotations['actorID'] = bpy.props.EnumProperty(name='Actor ID', items=ootEnumActorID)
	propAnnotations['actorIDCustom'] = bpy.props.StringProperty(name='Actor Key', default='ACTOR_CUSTOM')
	propAnnotations['actorKey'] = bpy.props.StringProperty(name='Actor Key', default='0000')
	propAnnotations['actorParam'] = bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000', \
		get=lambda self: getValues(self, self.actorID, 'actorParam', 'param', self.actorParamCustom),
		set=lambda self, value: setValues(self, value, 'Params', 'actorID'))
	propAnnotations['actorParamCustom'] = bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

	# Rotations
	propAnnotations['rotOverride'] =  bpy.props.BoolProperty(name = 'Rot Override', default = False)
	propAnnotations['rotOverrideX'] =  bpy.props.StringProperty(name = 'Rot X', default = '0x0',
		get=lambda self: getValues(self, self.actorID, None, 'XRot', None),
		set=lambda self, value: setValues(self, value, 'XRot', 'actorID'))
	propAnnotations['rotOverrideY'] =  bpy.props.StringProperty(name = 'Rot Y', default = '0x0',
		get=lambda self: getValues(self, self.actorID, None, 'YRot', None),
		set=lambda self, value: setValues(self, value, 'YRot', 'actorID'))
	propAnnotations['rotOverrideZ'] =  bpy.props.StringProperty(name = 'Rot Z', default = '0x0',
		get=lambda self: getValues(self, self.actorID, None, 'ZRot', None),
		set=lambda self, value: setValues(self, value, 'ZRot', 'actorID'))
	propAnnotations['rotOverrideCustom'] = bpy.props.BoolProperty(name = 'Override Rotation', default = False)
	propAnnotations['rotOverrideXCustom'] = bpy.props.StringProperty(name = 'Rot X', default = '0x0')
	propAnnotations['rotOverrideYCustom'] = bpy.props.StringProperty(name = 'Rot Y', default = '0x0')
	propAnnotations['rotOverrideZCustom'] = bpy.props.StringProperty(name = 'Rot Z', default = '0x0')

	# We have to use a bool to know what's needed to be exported
	propAnnotations['XRotBool'] = bpy.props.BoolProperty(default=False,
		get=lambda self: getValues(self, self.actorID, None, 'rotXBool', None))
	propAnnotations['YRotBool'] = bpy.props.BoolProperty(default=False,
		get=lambda self: getValues(self, self.actorID, None, 'rotYBool', None))
	propAnnotations['ZRotBool'] = bpy.props.BoolProperty(default=False,
		get=lambda self: getValues(self, self.actorID, None, 'rotZBool', None))

	# Transition Actors
	propAnnotations['transActorID'] = bpy.props.EnumProperty(name='Transition Actor ID', items=ootEnumTransitionActorID)
	propAnnotations['transActorIDCustom'] = bpy.props.StringProperty(name='Actor Key', default='ACTOR_CUSTOM')
	propAnnotations['transActorKey'] = bpy.props.StringProperty(name='Transition Actor ID', default='0009')
	propAnnotations['transActorParam'] = bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000', \
		get=lambda self: getValues(self, self.transActorID, 'actorParam', 'transParam', self.transActorParamCustom),
		set=lambda self, value: setValues(self, value, 'Params', 'transActorID'))
	propAnnotations['transActorParamCustom'] = bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

	# Other
	# isActorSynced is used to check if the blend's data is from an older version of Fast64
	propAnnotations['isActorSynced'] = bpy.props.BoolProperty(default=False)
	propAnnotations['itemChest'] = bpy.props.EnumProperty(name='Chest Content', items=ootChestContent)
	propAnnotations['naviMsgID'] = bpy.props.EnumProperty(name='Chest Content', items=ootNaviMsgID)

	# If you use the 'get=' option from Blender props don't actually save the data in the .blend
	# When the get function is called we have to save the data that'll be returned
	propAnnotations['paramToSave'] = bpy.props.StringProperty()
	propAnnotations['transParamToSave'] = bpy.props.StringProperty()
	propAnnotations['XRotToSave'] = bpy.props.StringProperty(default='0x0')
	propAnnotations['YRotToSave'] = bpy.props.StringProperty(default='0x0')
	propAnnotations['ZRotToSave'] = bpy.props.StringProperty(default='0x0')

	# Collectible Drops List
	itemDrops = [(elem.get('Value'), elem.get('Name'), \
					elem.get('Name')) for listNode in root for elem in listNode if listNode.tag == 'List' \
					and listNode.get('Name') == 'Collectibles']

	# Generate the fields
	for actorNode in root:
		i = j = k = l = 1
		actorKey = actorNode.get('Key')
		for elem in actorNode:
			if elem.tag == 'Property':
				genString(propAnnotations, actorKey, f'.props{i}', actorKey)
				i += 1
			elif elem.tag == 'Flag':
				if elem.get('Type') == 'Chest':
					genString(propAnnotations, actorKey, '.chestFlag', 'Chest Flag')
				elif elem.get('Type') == 'Collectible':
					genString(propAnnotations, actorKey, '.collectibleFlag', 'Collectible Flag')
				elif elem.get('Type') == 'Switch':
					genString(propAnnotations, actorKey, f'.switchFlag{j}', 'Switch Flag')
					j += 1
			elif elem.tag == 'Collectible':
				genEnum(propAnnotations, actorKey, '.collectibleDrop', itemDrops, 'Collectible Drop')
			elif elem.tag == 'Parameter':
				actorTypeList = [(elem2.get('Params'), elem2.text, elem2.get('Params')) \
								for actorNode2 in root for elem2 in actorNode2 \
								if actorNode2.get('Key') == actorKey and elem2.tag == 'Parameter']
				genEnum(propAnnotations, actorKey, '.type', actorTypeList, 'Actor Type')
			elif elem.tag == 'Bool':
				objName = actorKey + f'.bool{k}'
				prop = bpy.props.BoolProperty(default=False)
				propAnnotations[objName] = prop
				k += 1
			elif elem.tag == 'Enum':
				actorEnumList = [(item.get('Value'), item.get('Name'), item.get('Value')) \
								for actorNode2 in root if actorNode2.get('Key') == actorKey \
								for elem2 in actorNode2 if elem2.tag == 'Enum' and elem2.get('Index') == f'{l}' for item in elem2]
				genEnum(propAnnotations, actorKey, f'.enum{l}', actorEnumList, elem.get('Name'))
				l += 1

def drawDetailedProperties(user, userProp, userLayout, userObj, userSearchOp, userIDField, userParamField, detailedProp, dpKey):
	'''This function handles the drawing of the detailed actor panel'''
	userActor = 'Actor Property'
	userTransition = 'Transition Property'
	userEntrance = 'Entrance Property'
	entranceBool = None
	if user != userEntrance:
		# Entrance prop has specific fields to display
		userActorID = getattr(userProp, userIDField)
		searchOp = userLayout.operator(userSearchOp.bl_idname, icon = 'VIEWZOOM')
		searchOp.objName = userObj
		if user == userActor:
			actorEnum = ootEnumActorID
		else:
			actorEnum = ootEnumTransitionActorID
		currentActor = "Actor: " + getEnumName(actorEnum, userActorID)
	else:
		userLayout.prop(userProp, "customActor")
		if userProp.customActor:
			prop_split(userLayout, userProp.actor, "actorIDCustom", "Actor ID Custom")

		roomObj = getRoomObj(userObj)
		if roomObj is not None:
			split = userLayout.split(factor = 0.5)
			split.label(text = "Room Index")
			split.label(text = str(roomObj.ootRoomHeader.roomIndex))
		else:
			userLayout.label(text = "This must be part of a Room empty's hierarchy.", icon = 'OUTLINER')

		prop_split(userLayout, userProp, "spawnIndex", "Spawn Index")
		entranceBool = userProp.customActor
		userProp = detailedProp

	if (user != userEntrance and userActorID != 'Custom') or (user == userEntrance and entranceBool is False):
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
			OOTActorParams.rotXBool = OOTActorParams.rotYBool = OOTActorParams.rotZBool = False
			if userActorID == detailedProp.actorID:
				if dpKey == '000A' or dpKey == '009B':
					# If the current actor need a chest content, (en_chest, door_ana), draw the content search box
					searchOp = userLayout.operator(OOT_SearchChestContentEnumOperator.bl_idname, icon='VIEWZOOM')
					drawOperatorBox(userLayout, userObj, detailedProp, 'itemChest', 'Chest Content', searchOp, ootChestContent)
				if dpKey == '011B':
					# If the current actor is Elf_Msg, draw the Navi Message ID search box
					searchOp = userLayout.operator(OOT_SearchNaviMsgIDEnumOperator.bl_idname, icon='VIEWZOOM')
					drawOperatorBox(userLayout, userObj, detailedProp, 'naviMsgID', 'Message ID', searchOp, ootNaviMsgID)

			propAnnot = getattr(detailedProp, dpKey + ('.collectibleDrop'), None)
			if propAnnot is not None:
				prop_split(userLayout, detailedProp, dpKey + '.collectibleDrop', 'Collectible Drop')

		if user == userActor:
			drawParams(userLayout, detailedProp, dpKey, dpKey + '.chestFlag', 'Chest Flag', 'Flag', 'Chest', None)
			drawParams(userLayout, detailedProp, dpKey, dpKey + '.collectibleFlag', 'Collectible Flag', 'Flag', 'Collectible', None)

		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.switchFlag', 'Switch Flag', 'Flag', 'Switch', getMaxElemIndex(dpKey, 'Flag', 'Switch'))
		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.enum', None, 'Enum', None, None)
		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.props', None, 'Property', None, None)
		drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.bool', None, 'Bool', None, None)

		if user != userTransition:
			OOTActorParams.param = getActorFinalParameters(detailedProp, dpKey, 'Params')
		else:
			OOTActorParams.transParam = getActorFinalParameters(detailedProp, dpKey, 'Params')
		paramBox = userLayout.box()
		paramBox.label(text="Actor Parameter")
		paramBox.prop(detailedProp, userParamField, text="")

		if user == userActor:
			for actorNode in root:
				if dpKey == actorNode.get('Key'):
					for elem in actorNode:
						target = elem.get('Target')
						actorType = getattr(detailedProp, dpKey + '.type', None)
						if hasTiedParams(elem.get('TiedParam'), actorType):
							if target == 'XRot':
								OOTActorParams.XRot = getActorFinalParameters(detailedProp, dpKey, 'XRot')
								OOTActorParams.rotXBool = True
							elif target == 'YRot':
								OOTActorParams.YRot = getActorFinalParameters(detailedProp, dpKey, 'YRot')
								OOTActorParams.rotYBool = True
							elif target == 'ZRot':
								OOTActorParams.ZRot = getActorFinalParameters(detailedProp, dpKey, 'ZRot')
								OOTActorParams.rotZBool = True

			if OOTActorParams.rotXBool: 
				prop_split(paramBox, detailedProp, 'rotOverrideX', 'Rot X')
			if OOTActorParams.rotYBool: 
				prop_split(paramBox, detailedProp, 'rotOverrideY', 'Rot Y')
			if OOTActorParams.rotZBool: 
				prop_split(paramBox, detailedProp, 'rotOverrideZ', 'Rot Z')
	else:
		# If the current actor is custom
		if user != userEntrance:
			prop_split(userLayout, detailedProp, userIDField + 'Custom', currentActor)
			prop_split(userLayout, detailedProp, userParamField + 'Custom', 'Actor Parameter')
			userLayout.prop(detailedProp, 'rotOverrideCustom', text = 'Override Rotation (ignore Blender rot)')
			if detailedProp.rotOverrideCustom:
				if user == userActor: prop_split(userLayout, detailedProp, 'rotOverrideXCustom', 'Rot X')
				prop_split(userLayout, detailedProp, 'rotOverrideYCustom', 'Rot Y')
				if user == userActor: prop_split(userLayout, detailedProp, 'rotOverrideZCustom', 'Rot Z')
		else:
			prop_split(userLayout, detailedProp, userParamField + 'Custom', 'Actor Parameter')

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
		childNightRow = headerSetupBox.row()
		childNightRow.prop(headerProp, 'childNightHeader', text = "Child Night")
		adultDayRow = headerSetupBox.row()
		adultDayRow.prop(headerProp, 'adultDayHeader', text = "Adult Day")
		adultNightRow = headerSetupBox.row()
		adultNightRow.prop(headerProp, 'adultNightHeader', text = "Adult Night")

		childNightRow.enabled = not altProp.childNightHeader.usePreviousHeader if altProp is not None else True
		adultDayRow.enabled = not altProp.adultDayHeader.usePreviousHeader if altProp is not None else True
		adultNightRow.enabled = not altProp.adultNightHeader.usePreviousHeader if altProp is not None else True

		for i in range(len(headerProp.cutsceneHeaders)):
			drawActorHeaderItemProperty(headerSetup, propUser, headerProp.cutsceneHeaders[i], i, altProp, objName)
		drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), propUser, None, objName)

# Actor Property
class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_actor_id_enum_operator"
	bl_label = "Select Actor"
	bl_property = "actorID"
	bl_options = {'REGISTER', 'UNDO'}

	actorID : bpy.props.EnumProperty(items = ootEnumActorID, default = "ACTOR_PLAYER")
	objName : bpy.props.StringProperty()

	def execute(self, context):
		obj = bpy.data.objects[self.objName]
		detailedProp = obj.ootActorDetailedProperties

		obj.ootActorProperty.actorID = self.actorID
		detailedProp.actorID = self.actorID
		for actorNode in root:
			if actorNode.get('ID') == self.actorID:
				detailedProp.actorKey = actorNode.get('Key')

		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.actorID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTActorProperty(bpy.types.PropertyGroup):
	# Normal Actors
	# We can't delete this (for now) as it'd ignore data in older blend files
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
	rotOverride : bpy.props.BoolProperty(name = 'Override Rotation', default = False)
	rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0x0')
	rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0x0')
	rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0x0')
	headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

def drawActorProperty(layout, actorProp, altRoomProp, objName, detailedProp):
	actorIDBox = layout.column()

	if detailedProp.isActorSynced:
		drawDetailedProperties('Actor Property', actorProp, actorIDBox, objName, \
			OOT_SearchActorIDEnumOperator, 'actorID', 'actorParam', detailedProp, detailedProp.actorKey)
		drawActorHeaderProperty(actorIDBox, actorProp.headerSettings, "Actor", altRoomProp, objName)
	else:
		sceneObj = getSceneObj(bpy.context.object)
		if sceneObj is None: sceneName = 'Unknown'
		else: sceneName = sceneObj.name
		actorIDBox.box().label(text=f"Scene: '{sceneName}' Actors are not synchronised!")
		actorIDBox.operator(OOT_SyncActors.bl_idname)

# Transition Actor Property
class OOT_SearchTransActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_trans_actor_id_enum_operator"
	bl_label = "Select Transition Actor"
	bl_property = "transActorID"
	bl_options = {'REGISTER', 'UNDO'}

	transActorID: bpy.props.EnumProperty(items = ootEnumTransitionActorID, default = "ACTOR_EN_DOOR")
	objName : bpy.props.StringProperty()

	def execute(self, context):
		obj = bpy.data.objects[self.objName]
		detailedProp = obj.ootTransitionActorProperty.detailedActor

		detailedProp.transActorID = self.transActorID
		for actorNode in root:
			if actorNode.get('ID') == self.transActorID:
				detailedProp.transActorKey = actorNode.get('Key')

		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.transActorID)
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
	actor : bpy.props.PointerProperty(type = OOTActorProperty)
	detailedActor : bpy.props.PointerProperty(type = OOTActorDetailedProperties)

def drawTransitionActorProperty(layout, transActorProp, altSceneProp, roomObj, objName, detailedProp):
	actorIDBox = layout.column()

	detailedProp = transActorProp.detailedActor
	if detailedProp.isActorSynced:
		drawDetailedProperties('Transition Property', detailedProp, actorIDBox, objName, \
			OOT_SearchTransActorIDEnumOperator, 'transActorID', 'transActorParam', detailedProp, detailedProp.transActorKey)
		if roomObj is None:
			actorIDBox.label(text = "This must be part of a Room empty's hierarchy.", icon = "ERROR")
		else:
			label_split(actorIDBox, "Room To Transition From", str(roomObj.ootRoomHeader.roomIndex))
		prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
		actorIDBox.label(text = "Y+ side of door faces toward the \"from\" room.", icon = "ERROR")
		drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
		drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

		drawActorHeaderProperty(actorIDBox, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName)
	else:
		sceneObj = getSceneObj(bpy.context.object)
		if sceneObj is None: sceneName = 'Unknown'
		else: sceneName = sceneObj.name
		actorIDBox.box().label(text=f"Scene: '{sceneName}' Actors are not synchronised!")
		actorIDBox.operator(OOT_SyncActors.bl_idname)

# Entrance Property
class OOTEntranceProperty(bpy.types.PropertyGroup):
	# This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
	spawnIndex : bpy.props.IntProperty(min = 0)
	customActor : bpy.props.BoolProperty(name = "Use Custom Actor")
	actor : bpy.props.PointerProperty(type = OOTActorProperty)

def drawEntranceProperty(layout, obj, altSceneProp, objName, detailedProp):
	box = layout.column()
	entranceProp = obj.ootEntranceProperty

	if detailedProp.isActorSynced:
		drawDetailedProperties('Entrance Property', entranceProp, box, None, \
			None, 'actorID', 'actorParam', detailedProp, '0000')
		drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
	else:
		sceneObj = getSceneObj(bpy.context.object)
		if sceneObj is None: sceneName = 'Unknown'
		else: sceneName = sceneObj.name
		box.box().label(text=f"Scene: '{sceneName}' Actors are not synchronised!")
		box.operator(OOT_SyncActors.bl_idname)
