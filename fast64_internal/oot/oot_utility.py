from ..utility import *
import bpy, math, mathutils, os
from bpy.utils import register_class, unregister_class

ootSceneDungeons = [
	"bdan",
	"bdan_boss",
	"bmori1",
	"ddan",
	"ddan_boss",
	"fire_bs",
	"ganon",
	"ganontika",
	"ganontikasonogo",
	"ganon_boss",
	"ganon_demo",
	"ganon_final",
	"ganon_sonogo",
	"ganon_tou",
	"gerudoway",
	"hakadan",
	"hakadanch",
	"hakadan_bs",
	"hidan",
	"ice_doukutu",
	"jyasinboss",
	"jyasinzou",
	"men",
	"mizusin",
	"mizusin_bs",
	"moribossroom",
	"ydan",
	"ydan_boss",
]

ootSceneIndoors = [
	"bowling",
	"daiyousei_izumi",
	"hairal_niwa",
	"hairal_niwa2",
	"hairal_niwa_n",
	"hakasitarelay",
	"hut",
	"hylia_labo",
	"impa",
	"kakariko",
	"kenjyanoma",
	"kokiri_home",
	"kokiri_home3",
	"kokiri_home4",
	"kokiri_home5",
	"labo",
	"link_home",
	"mahouya",
	"malon_stable",
	"miharigoya",
	"nakaniwa",
	"syatekijyou",
	"takaraya",
	"tent",
	"tokinoma",
	"yousei_izumi_tate",
	"yousei_izumi_yoko",
]

ootSceneMisc = [
	"enrui",
	"entra_n",
	"hakaana",
	"hakaana2",
	"hakaana_ouke",
	"hiral_demo",
	"kakariko3",
	"kakusiana",
	"kinsuta",
	"market_alley",
	"market_alley_n",
	"market_day",
	"market_night",
	"market_ruins",
	"shrine",
	"shrine_n",
	"shrine_r",
	"turibori",
]

ootSceneOverworld = [
	"entra",
	"souko",
	"spot00",
	"spot01",
	"spot02",
	"spot03",
	"spot04",
	"spot05",
	"spot06",
	"spot07",
	"spot08",
	"spot09",
	"spot10",
	"spot11",
	"spot12",
	"spot13",
	"spot15",
	"spot16",
	"spot17",
	"spot18",
	"spot20",
]

ootSceneShops = [
	"alley_shop",
	"drag",
	"face_shop",
	"golon",
	"kokiri_shop",
	"night_shop",
	"shop1",
	"zoora",
]

ootSceneTest_levels = [
	"besitu",
	"depth_test",
	"sasatest",
	"sutaru",
	"syotes",
	"syotes2",
	"test01",
	"testroom",
]

ootSceneDirs = {
	'assets/scenes/dungeons/' : ootSceneDungeons,
	'assets/scenes/indoors/' : ootSceneIndoors,
	'assets/scenes/misc/' : ootSceneMisc,
	'assets/scenes/overworld/' : ootSceneOverworld,
	'assets/scenes/shops/' : ootSceneShops,
	'assets/scenes/test_levels/' : ootSceneTest_levels,
}

def getSceneDirFromLevelName(name):
	for sceneDir, dirLevels in ootSceneDirs.items():
		if name in dirLevels:
			return sceneDir + name
	return None

class ExportInfo:
	def __init__(self, isCustomExport, exportPath, customSubPath, name):
		self.isCustomExportPath = isCustomExport
		self.exportPath = exportPath
		self.customSubPath = customSubPath
		self.name = name

def getSceneObj(obj):
	while not (obj is None or (obj is not None and obj.data is None and obj.ootEmptyType == "Scene")):
		obj = obj.parent
	if obj is None:
		return None
	else:
		return obj

def getRoomObj(obj):
	while not (obj is None or (obj is not None and obj.data is None and obj.ootEmptyType == "Room")):
		obj = obj.parent
	if obj is None:
		return None
	else:
		return obj

def checkEmptyName(name):
	if name == "":
		raise PluginError("No name entered for the exporter.")

def ootGetPath(exportPath, isCustomExport, subPath, folderName):
	if isCustomExport:
		path = bpy.path.abspath(os.path.join(exportPath, folderName))
	else:
		if bpy.context.scene.ootDecompPath == "":
			raise PluginError("Decomp base path is empty.")
		path = bpy.path.abspath(os.path.join(bpy.context.scene.ootDecompPath, subPath + folderName))
	if not os.path.exists(path):
		os.makedirs(path)

	return path

def getSortedChildren(armatureObj, bone):
	return sorted([child.name for child in bone.children])

def getStartBone(armatureObj):
	return 'root'

def checkForStartBone(armatureObj):
	if "root" not in armatureObj.data.bones:
		raise PluginError("Skeleton must have a bone named 'root' where the skeleton starts from.")

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
	return [int(round((math.degrees(value) % 360) / 360 * (2**16))) % (2**16) for value in rotation.to_euler()]

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

def drawAddButton(layout, index, collectionType, subIndex, objName):
	if subIndex is None:
		subIndex = 0
	addOp = layout.operator(OOTCollectionAdd.bl_idname)
	addOp.option = index
	addOp.collectionType = collectionType
	addOp.subIndex = subIndex
	addOp.objName = objName

def drawCollectionOps(layout, index, collectionType, subIndex, objName):
	if subIndex is None:
		subIndex = 0

	buttons = layout.row(align = True)

	addOp = buttons.operator(OOTCollectionAdd.bl_idname, text = 'Add', icon = "ADD")
	addOp.option = index + 1
	addOp.collectionType = collectionType
	addOp.subIndex = subIndex
	addOp.objName = objName

	removeOp = buttons.operator(OOTCollectionRemove.bl_idname, text = 'Delete', icon = "REMOVE")
	removeOp.option = index
	removeOp.collectionType = collectionType
	removeOp.subIndex = subIndex
	removeOp.objName = objName
	
	#moveButtons = layout.row(align = True)
	moveButtons = buttons

	moveUp = moveButtons.operator(OOTCollectionMove.bl_idname, text = 'Up', icon = "TRIA_UP")
	moveUp.option = index
	moveUp.offset = -1
	moveUp.collectionType = collectionType
	moveUp.subIndex = subIndex
	moveUp.objName = objName

	moveDown = moveButtons.operator(OOTCollectionMove.bl_idname, text = 'Down', icon = "TRIA_DOWN")
	moveDown.option = index
	moveDown.offset = 1
	moveDown.collectionType = collectionType
	moveDown.subIndex = subIndex
	moveDown.objName = objName

class OOTCollectionAdd(bpy.types.Operator):
	bl_idname = 'object.oot_collection_add'
	bl_label = 'Add Item'
	bl_options = {'REGISTER', 'UNDO'} 

	option : bpy.props.IntProperty()
	collectionType : bpy.props.StringProperty(default = "Actor")
	subIndex : bpy.props.IntProperty(default = 0)
	objName : bpy.props.StringProperty()

	def execute(self, context):
		collection = getCollection(bpy.data.objects[self.objName], self.collectionType, self.subIndex)

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
	objName : bpy.props.StringProperty()

	def execute(self, context):
		collection = getCollection(bpy.data.objects[self.objName], self.collectionType, self.subIndex)
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
	objName : bpy.props.StringProperty()

	collectionType : bpy.props.StringProperty(default = "Actor")
	def execute(self, context):
		collection = getCollection(bpy.data.objects[self.objName], self.collectionType, self.subIndex)
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