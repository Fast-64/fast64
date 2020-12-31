from ..utility import *
import bpy, math, mathutils
from bpy.utils import register_class, unregister_class

class BoxEmpty:
	def __init__(self, position, scale, emptyScale):
		# The scale ordering is due to the fact that scaling happens AFTER rotation.
		# Thus the translation uses Y-up, while the scale uses Z-up.
		self.low = (position[0] - scale[0] * emptyScale, position[2] - scale[1] * emptyScale)
		self.high = (position[0] + scale[0] * emptyScale, position[2] + scale[1] * emptyScale)
		self.height = position[1] + scale[2] * emptyScale

		self.low = [int(round(value)) for value in self.low]
		self.high = [int(round(value)) for value in self.high]
		self.height = int(round(self.height))

def getCustomProperty(data, prop):
	value = getattr(data, prop)
	return value if value != "Custom" else getattr(data, prop + str("Custom"))

def convertIntTo2sComplement(value, length):
	return int.from_bytes(int(round(value)).to_bytes(length, 'big', signed = True), 'big')

def drawEnumWithCustom(panel, data, attribute, name, customName):
	prop_split(panel, data, attribute, name)
	if getattr(data, attribute) == "Custom":
		prop_split(panel, data, attribute + "Custom", customName)

def clampShort(value):
	return min(max(round(value), -2**15), 2**15 - 1)

def convertNormalizedFloatToShort(value):
	value *= 2**15
	value = clampShort(value)
	
	return int.from_bytes(int(value).to_bytes(2, 'big', signed = True), 'big')

def convertNormalizedVectorToShort(value):
	return (
		convertNormalizedFloatToShort(value[0]),
		convertNormalizedFloatToShort(value[1]),
		convertNormalizedFloatToShort(value[2]),
	)

def getEnumName(enumItems, value):
	for enumTuple in enumItems:
		if enumTuple[0] == value:
			return enumTuple[1]
	raise PluginError("Could not find enum value " + str(value))

def ootConvertTranslation(translation):
	return [int(round(value)) for value in translation]

def ootConvertRotation(rotation):
	# see BINANG_TO_DEGF
	return [int(round(math.degrees(value) * 65535 / 360)) for value in rotation.to_euler()]

def getCollectionFromIndex(obj, prop, subIndex, isRoom):
	if not isRoom:
		header0 = obj.ootSceneHeader
		header1 = obj.ootAlternateSceneHeaders.childNightHeader
		header2 = obj.ootAlternateSceneHeaders.adultDayHeader
		header3 = obj.ootAlternateSceneHeaders.adultNightHeader
		cutsceneHeaders = obj.ootAlternateSceneHeaders.cutsceneHeaders
	else:
		header0 = obj.ootRoomHeader
		header1 = obj.ootAlternateRoomHeaders.childNightHeader
		header2 = obj.ootAlternateRoomHeaders.adultDayHeader
		header3 = obj.ootAlternateRoomHeaders.adultNightHeader
		cutsceneHeaders = obj.ootAlternateRoomHeaders.cutsceneHeaders

	if subIndex < 0:
		raise PluginError("Alternate scene header index too low: " + str(subIndex))
	elif subIndex == 0:		
		collection = getattr(header0, prop)
	elif subIndex == 1:
		collection = getattr(header1, prop)
	elif subIndex == 2:
		collection = getattr(header2, prop)
	elif subIndex == 3:
		collection = getattr(header3, prop)
	else:
		collection = getattr(cutsceneHeaders[subIndex - 4], prop)
	return collection

# Operators cannot store mutable references (?), so to reuse PropertyCollection modification code we do this.
# Save a string identifier in the operator, then choose the member variable based on that.
# subIndex is for a collection within a collection element
def getCollection(obj, collectionType, subIndex):

	if collectionType == "Actor":	
		collection = obj.ootActorProperty.headerSettings.cutsceneHeaders
	elif collectionType == "Transition Actor":	
		collection = obj.ootTransitionActorProperty.actor.headerSettings.cutsceneHeaders
	elif collectionType == "Entrance":	
		collection = obj.ootEntranceProperty.actor.headerSettings.cutsceneHeaders
	elif collectionType == "Room":
		collection = obj.ootAlternateRoomHeaders.cutsceneHeaders
	elif collectionType == "Scene":
		collection = obj.ootAlternateSceneHeaders.cutsceneHeaders
	elif collectionType == "Light":
		collection = getCollectionFromIndex(obj, 'lightList', subIndex, False)
	elif collectionType == "Exit":
		collection = getCollectionFromIndex(obj, 'exitList', subIndex, False)
	elif collectionType == "Object":
		collection = getCollectionFromIndex(obj, 'objectList', subIndex, True)
	else:
		raise PluginError("Invalid collection type: " + collectionType)

	return collection

def drawAddButton(layout, index, collectionType, subIndex):
	if subIndex is None:
		subIndex = 0
	addOp = layout.operator(OOTCollectionAdd.bl_idname)
	addOp.option = index
	addOp.collectionType = collectionType
	addOp.subIndex = subIndex

def drawCollectionOps(layout, index, collectionType, subIndex):
	if subIndex is None:
		subIndex = 0

	buttons = layout.row(align = True)

	addOp = buttons.operator(OOTCollectionAdd.bl_idname, text = 'Add', icon = "ADD")
	addOp.option = index + 1
	addOp.collectionType = collectionType
	addOp.subIndex = subIndex

	removeOp = buttons.operator(OOTCollectionRemove.bl_idname, text = 'Delete', icon = "REMOVE")
	removeOp.option = index
	removeOp.collectionType = collectionType
	removeOp.subIndex = subIndex
	
	#moveButtons = layout.row(align = True)
	moveButtons = buttons

	moveUp = moveButtons.operator(OOTCollectionMove.bl_idname, text = 'Up', icon = "TRIA_UP")
	moveUp.option = index
	moveUp.offset = -1
	moveUp.collectionType = collectionType
	moveUp.subIndex = subIndex

	moveDown = moveButtons.operator(OOTCollectionMove.bl_idname, text = 'Down', icon = "TRIA_DOWN")
	moveDown.option = index
	moveDown.offset = 1
	moveDown.collectionType = collectionType
	moveDown.subIndex = subIndex

class OOTCollectionAdd(bpy.types.Operator):
	bl_idname = 'object.oot_collection_add'
	bl_label = 'Add Item'
	bl_options = {'REGISTER', 'UNDO'} 

	option : bpy.props.IntProperty()
	collectionType : bpy.props.StringProperty(default = "Actor")
	subIndex : bpy.props.IntProperty(default = 0)

	def execute(self, context):
		obj = context.object
		collection = getCollection(obj, self.collectionType, self.subIndex)

		collection.add()
		collection.move(len(collection)-1, self.option)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

class OOTCollectionRemove(bpy.types.Operator):
	bl_idname = 'object.oot_collection_remove'
	bl_label = 'Remove Item'
	bl_options = {'REGISTER', 'UNDO'} 

	option : bpy.props.IntProperty()
	collectionType : bpy.props.StringProperty(default = "Actor")
	subIndex : bpy.props.IntProperty(default = 0)

	def execute(self, context):
		collection = getCollection(context.object, self.collectionType, self.subIndex)
		collection.remove(self.option)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

class OOTCollectionMove(bpy.types.Operator):
	bl_idname = 'object.oot_collection_move'
	bl_label = 'Move Item'
	bl_options = {'REGISTER', 'UNDO'} 

	option : bpy.props.IntProperty()
	offset : bpy.props.IntProperty()
	subIndex : bpy.props.IntProperty(default = 0)

	collectionType : bpy.props.StringProperty(default = "Actor")
	def execute(self, context):
		obj = context.object
		collection = getCollection(obj, self.collectionType, self.subIndex)
		collection.move(self.option, self.option + self.offset)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

oot_utility_classes = (
	OOTCollectionAdd,
	OOTCollectionRemove,
	OOTCollectionMove,
)

def oot_utility_register():
	for cls in oot_utility_classes:
		register_class(cls)

def oot_utility_unregister():
	for cls in reversed(oot_utility_classes):
		unregister_class(cls)