from ..utility import *
import bpy, math, mathutils, os, re
from bpy.utils import register_class, unregister_class
from .oot_constants import root

ootSceneDungeons = [
	"bdan",
	"bdan_boss",
	"Bmori1",
	"ddan",
	"ddan_boss",
	"FIRE_bs",
	"ganon",
	"ganontika",
	"ganontikasonogo",
	"ganon_boss",
	"ganon_demo",
	"ganon_final",
	"ganon_sonogo",
	"ganon_tou",
	"gerudoway",
	"HAKAdan",
	"HAKAdanCH",
	"HAKAdan_bs",
	"HIDAN",
	"ice_doukutu",
	"jyasinboss",
	"jyasinzou",
	"men",
	"MIZUsin",
	"MIZUsin_bs",
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

def addIncludeFiles(objectName, objectPath, assetName):
	addIncludeFilesExtension(objectName, objectPath, assetName, 'h')
	addIncludeFilesExtension(objectName, objectPath, assetName, 'c')

def addIncludeFilesExtension(objectName, objectPath, assetName, extension):
	include = "#include \"" + assetName + "." + extension + "\"\n"
	if not os.path.exists(objectPath):
		raise PluginError(objectPath + " does not exist.")
	path = os.path.join(objectPath, objectName + '.' + extension)
	data = getDataFromFile(path)

	if include not in data:
		data += '\n' + include
	
	# Save this regardless of modification so it will be recompiled.
	saveDataToFile(path, data)
	

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

class OOTObjectCategorizer:
	def __init__(self):
		self.sceneObj = None
		self.roomObjs = []
		self.actors = []
		self.transitionActors = []
		self.meshes = []
		self.entrances = []
		self.waterBoxes = []

	def sortObjects(self, allObjs):
		for obj in allObjs:
			if obj.data is None:
				if obj.ootEmptyType == "Actor":
					self.actors.append(obj)
				elif obj.ootEmptyType == "Transition Actor":
					self.transitionActors.append(obj)
				elif obj.ootEmptyType == "Entrance":
					self.entrances.append(obj)
				elif obj.ootEmptyType == "Water Box":
					self.waterBoxes.append(obj)
				elif obj.ootEmptyType == "Room":
					self.roomObjs.append(obj)
				elif obj.ootEmptyType == "Scene":
					self.sceneObj = obj
			elif isinstance(obj.data, bpy.types.Mesh):
				self.meshes.append(obj)

# This also sets all origins relative to the scene object.
def ootDuplicateHierarchy(obj, ignoreAttr, includeEmpties, objectCategorizer):
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

		objectCategorizer.sortObjects(allObjs)
		meshObjs = objectCategorizer.meshes
		bpy.ops.object.select_all(action = 'DESELECT')
		for selectedObj in meshObjs:
			selectedObj.select_set(True)
		bpy.ops.object.transform_apply(location = False, 
			rotation = True, scale = True, properties =  False)
		
		for selectedObj in meshObjs:
			bpy.ops.object.select_all(action = 'DESELECT')
			selectedObj.select_set(True)
			bpy.context.view_layer.objects.active = selectedObj
			for modifier in selectedObj.modifiers:
				attemptModifierApply(modifier)
		for selectedObj in meshObjs:
			setOrigin(obj, selectedObj)
		if ignoreAttr is not None:
			for selectedObj in meshObjs:
				if getattr(selectedObj, ignoreAttr):
					for child in selectedObj.children:
						bpy.ops.object.select_all(action = 'DESELECT')
						child.select_set(True)
						bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
						selectedObj.parent.select_set(True)
						bpy.ops.object.parent_set(keep_transform = True)
					selectedObj.parent = None
		
		# Assume objects with these types of constraints are parented, and are
		# intended to be parented in-game, i.e. rendered as an extra DL alongside
		# a skeletal mesh, e.g. for a character to be wearing or holding it.
		# In this case we purely want the transformation of the object relative
		# to whatever it's parented to. Getting rid of the constraint and then
		# doing transform_apply() sets up this transformation.
		hasConstraint = False
		for constraint in tempObj.constraints:
			if constraint.type in {'COPY_LOCATION', 'COPY_ROTATION', 'COPY_SCALE',
				'COPY_TRANSFORMS', 'TRANSFORM', 'CHILD_OF', 'CLAMP_TO', 'DAMPED_TRACK',
				'LOCKED_TRACK', 'TRACK_TO'} and not constraint.mute:
				hasConstraint = True
				tempObj.constraints.remove(constraint)
		if not hasConstraint:
			# For normal objects, the game's coordinate system is 90 degrees
			# away from Blender's.
			applyRotation([tempObj], math.radians(90), 'X')
		else:
			# This is a relative transform we care about so the 90 degrees
			# doesn't matter (since they're both right-handed).
			print('Applying transform')
			bpy.ops.object.select_all(action = "DESELECT")
			tempObj.select_set(True)
			bpy.context.view_layer.objects.active = tempObj
			bpy.ops.object.transform_apply()
		
		return tempObj, allObjs
	except Exception as e:
		cleanupDuplicatedObjects(allObjs)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		raise Exception(str(e))

def ootSelectMeshChildrenOnly(obj, includeEmpties):
	isMesh = isinstance(obj.data, bpy.types.Mesh)
	isEmpty = (obj.data is None or \
		isinstance(obj.data, bpy.types.Camera) or\
		isinstance(obj.data, bpy.types.Curve)) and includeEmpties
	if (isMesh or isEmpty):
		obj.select_set(True)
		obj.original_name = obj.name
	for child in obj.children:
		ootSelectMeshChildrenOnly(child, includeEmpties)

def ootCleanupScene(originalSceneObj, allObjs):
	cleanupDuplicatedObjects(allObjs)
	originalSceneObj.select_set(True)
	bpy.context.view_layer.objects.active = originalSceneObj

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

def ootGetObjectPath(isCustomExport, exportPath, folderName):
	if isCustomExport:
		filepath = exportPath
	else:
		filepath = os.path.join(ootGetPath(exportPath, isCustomExport, 'assets/objects/', 
			folderName, False, False), folderName + '.c')
	return filepath


def ootGetPath(exportPath, isCustomExport, subPath, folderName, makeIfNotExists, useFolderForCustom):
	if isCustomExport:
		path = bpy.path.abspath(os.path.join(exportPath, (folderName if useFolderForCustom else '')))
	else:
		if bpy.context.scene.ootDecompPath == "":
			raise PluginError("Decomp base path is empty.")
		path = bpy.path.abspath(os.path.join(bpy.context.scene.ootDecompPath, subPath + folderName))
		
	if not os.path.exists(path):
		if isCustomExport or makeIfNotExists:
			os.makedirs(path)
		else:
			raise PluginError(path + " does not exist.")

	return path

def getSortedChildren(armatureObj, bone):
	return sorted([child.name for child in bone.children if child.ootBoneType != "Ignore"], key = lambda childName : childName.lower())

def getStartBone(armatureObj):
	startBoneNames = [bone.name for bone in armatureObj.data.bones if \
		bone.parent is None and bone.ootBoneType != "Ignore"]
	if len(startBoneNames) == 0:
		raise PluginError(armatureObj.name + " does not have any root bones that are not of the \"Ignore\" type.")
	startBoneName = startBoneNames[0]
	return startBoneName
	#return 'root'

def checkForStartBone(armatureObj):
	pass
	#if "root" not in armatureObj.data.bones:
	#	raise PluginError("Skeleton must have a bone named 'root' where the skeleton starts from.")

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

def checkUniformScale(scale, obj):
	if abs(scale[0] - scale[1]) > 0.01 or\
		abs(scale[1] - scale[2]) > 0.01 or\
		abs(scale[0] - scale[2]) > 0.01:
		raise PluginError("Cull group " + obj.name + " must have a uniform scale.")

class CullGroup:
	def __init__(self, position, scale, emptyScale):
		self.position = [int(round(field)) for field in position]
		self.cullDepth = abs(int(round(scale[0] * emptyScale)))

def getCustomProperty(data, prop):
	value = getattr(data, prop)
	return value if value != "Custom" else getattr(data, prop + str("Custom"))

def getActorProperty(data, detailedProp, idField, field, toSaveField):
	return getattr(detailedProp, field + str("Custom")) if idField == 'Custom' else getattr(data, toSaveField)

def convertIntTo2sComplement(value, length, signed):
	return int.from_bytes(int(round(value)).to_bytes(length, 'big', signed = signed), 'big')

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

def getCutsceneName(obj):
	name = obj.name
	if name.startswith('Cutscene.'):
		name = name[9:]
	name = name.replace('.', '_')
	return name

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
def getCollection(objName, collectionType, subIndex):
	obj = bpy.data.objects[objName]
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
	elif collectionType.startswith("CSHdr."):
		# CSHdr.HeaderNumber[.ListType]
		# Specifying ListType means uses subIndex
		toks = collectionType.split('.')
		assert len(toks) in [2, 3]
		hdrnum = int(toks[1])
		collection = getCollectionFromIndex(obj, 'csLists', hdrnum, False)
		if len(toks) == 3:
			collection = getattr(collection[subIndex], toks[2])
	elif collectionType.startswith("Cutscene."):
		# Cutscene.ListType
		toks = collectionType.split('.')
		assert len(toks) == 2
		collection = obj.ootCutsceneProperty.csLists
		collection = getattr(collection[subIndex], toks[1])
	elif collectionType == "Cutscene":
		collection = obj.ootCutsceneProperty.csLists
	elif collectionType == "extraCutscenes":
		collection = obj.ootSceneHeader.extraCutscenes
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

def drawCollectionOps(layout, index, collectionType, subIndex, objName, allowAdd=True):
	if subIndex is None:
		subIndex = 0

	buttons = layout.row(align = True)

	if allowAdd:
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
	
	moveUp = buttons.operator(OOTCollectionMove.bl_idname, text = 'Up', icon = "TRIA_UP")
	moveUp.option = index
	moveUp.offset = -1
	moveUp.collectionType = collectionType
	moveUp.subIndex = subIndex
	moveUp.objName = objName

	moveDown = buttons.operator(OOTCollectionMove.bl_idname, text = 'Down', icon = "TRIA_DOWN")
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
		collection = getCollection(self.objName, self.collectionType, self.subIndex)

		collection.add()
		collection.move(len(collection)-1, self.option)
		#self.report({'INFO'}, 'Success!')
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
		collection = getCollection(self.objName, self.collectionType, self.subIndex)
		collection.remove(self.option)
		#self.report({'INFO'}, 'Success!')
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
		collection = getCollection(self.objName, self.collectionType, self.subIndex)
		collection.move(self.option, self.option + self.offset)
		#self.report({'INFO'}, 'Success!')
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

def getActorParameter(object, field, shift):
	attr = getattr(object, field, '0x0')
	if isinstance(attr, str):
		return int(attr, base=16) << shift
	elif isinstance(attr, bool) and attr:
		return 1 << shift
	else:
		return 0

def setActorParameter(object, field, param, mask):
	shift = len(f'{mask:016b}') - len(f'{mask:016b}'.rstrip('0'))
	if field.endswith('.type'):
		setattr(object, field, f'{param & mask:04X}')
	else:
		attr = getattr(object, field, '0x0')
		if isinstance(attr, str):
			setattr(object, field, f'0x{(param & mask) >> shift:02X}')
		elif isinstance(attr, bool):
			setattr(object, field, bool((param & mask) >> shift))
		else:
			setattr(object, field, '0x0')

def getMaxElemIndex(actorKey, elemTag, flagType):
	# Looking for the highest Property/Switch index for the current actor
	length = '0'
	for actorNode in root:
		if actorNode.get('Key') == actorKey:
			for elem in actorNode:
				if elem.tag == elemTag:
					if flagType is None or (flagType == 'Switch' and elem.get('Type') == flagType):
						length = elem.get('Index')
	return length

def stringToInt(str):
	# Checking if the string is an hex number
	if str.startswith('0x') or all(c in string.hexdigits for c in str):
		return int(str, base=16)
	else:
		return int(str, base=10)

def computeParams(elem, detailedProp, field, lenProp, lenSwitch, lenBool):
	params = shift = 0
	strMask = elem.get('Mask')
	if elem.tag != 'Parameter' and strMask is not None:
		mask = int(strMask, base=16)
		shift = len(f'{mask:016b}') - len(f'{mask:016b}'.rstrip('0'))
	if elem.tag == 'Flag':
		elemType = elem.get('Type')
		if elemType == 'Chest':
			params += getActorParameter(detailedProp, field + '.chestFlag', shift)
		if elemType == 'Collectible':
			params += getActorParameter(detailedProp, field + '.collectibleFlag', shift)
		if elemType == 'Switch':
			for i in range(1, (int(lenSwitch, base=10) + 1)):
				if i == int(elem.get('Index'), base=10):
					params += getActorParameter(detailedProp, field + f'.switchFlag{i}', shift)
	if elem.tag == 'Property' and elem.get('Name') != 'None':
		for i in range(1, (int(lenProp, base=10) + 1)):
			if i == int(elem.get('Index'), base=10):
				params += getActorParameter(detailedProp, (field + f'.props{i}'), shift)
	if elem.tag == 'Item':
		params += int(detailedProp.itemChest, base=16) << shift
	if elem.tag == 'Collectible':
		params += getActorParameter(detailedProp, field + '.collectibleDrop', shift)
	if elem.tag == 'Bool':
		for i in range(1, (int(lenBool, base=10) + 1)):
			if i == int(elem.get('Index'), base=10):
				params += getActorParameter(detailedProp, (field + f'.bool{i}'), shift)
	return params

def uncomputeParams(elem, actorProp, detailedProp, field, lenProp, lenSwitch, lenBool):
	params = stringToInt(actorProp.actorParam)
	strMask = elem.get('Mask')

	if strMask is not None:
		target = elem.get('Target')
		mask = int(strMask, base=16)
		if elem.tag != 'Parameter' and (target == 'Params' or target is None):
			if elem.tag == 'Flag':
				elemType = elem.get('Type')
				if elemType == 'Chest':
					setActorParameter(detailedProp, field + '.chestFlag', params, mask)
				if elemType == 'Collectible':
					setActorParameter(detailedProp, field + '.collectibleFlag', params, mask)
				if elemType == 'Switch':
					for i in range(1, (int(lenSwitch, base=10) + 1)):
						if i == int(elem.get('Index'), base=10):
							setActorParameter(detailedProp, field + f'.switchFlag{i}', params, mask)
			if elem.tag == 'Property' and elem.get('Name') != 'None':
				for i in range(1, (int(lenProp, base=10) + 1)):
					if i == int(elem.get('Index'), base=10):
						setActorParameter(detailedProp, field + f'.props{i}', params, mask)
			if elem.tag == 'Item':
				setActorParameter(detailedProp, 'itemChest', params, mask)
			if elem.tag == 'Collectible':
				setActorParameter(detailedProp, field + '.collectibleDrop', params, mask)
			if elem.tag == 'Bool':
				for i in range(1, (int(lenBool, base=10) + 1)):
					if i == int(elem.get('Index'), base=10):
						setActorParameter(detailedProp, field + f'.bool{i}', params, mask)
		elif elem.tag == 'Parameter':
			setActorParameter(detailedProp, field + '.type', params, mask)
