import bpy
import mathutils
import math
import copy

from os.path import basename
import os
from io import BytesIO

from .sm64_geolayout_bone import getSwitchOptionBone
from .sm64_geolayout_constants import *
from .sm64_geolayout_utility import *
from .utility import *
from .sm64_constants import *
from .f3d_material import all_combiner_uses
from .f3d_writer import *

def findStartBone(armatureObj):
	noParentBones = [poseBone for poseBone in armatureObj.pose.bones if \
		poseBone.parent is None]
	for poseBone in noParentBones:
		# We want to ignore any switch option bones.
		if poseBone.bone_group is None or \
			(poseBone.bone_group.name != "SwitchOption" and \
			poseBone.bone_group.name != "Ignore"):
			return poseBone.name
	raise ValueError("No non switch option start bone could be found.")

def prepareGeolayoutExport(armatureObj, obj):
	# Make object and armature space the same.
	bpy.ops.object.select_all(action = "DESELECT")
	obj.select_set(True)
	bpy.context.view_layer.objects.active = obj
	bpy.ops.object.transform_apply()
	bpy.context.scene.cursor.location = armatureObj.location
	bpy.ops.object.origin_set(type = 'ORIGIN_CURSOR')

	# Apply armature scale.
	bpy.ops.object.select_all(action = "DESELECT")
	armatureObj.select_set(True)
	bpy.context.view_layer.objects.active = armatureObj
	bpy.ops.object.transform_apply(location = False, rotation = False,
		scale = True, properties = False)

def getAllArmatures(armatureObj, currentArmatures):
	linkedArmatures = []
	for bone in armatureObj.data.bones:
		if bone.geo_cmd == 'Switch':
			for switchOption in bone.switch_options:
				if switchOption.switchType == 'Mesh':
					if switchOption.optionArmature is None:
						raise ValueError('"' + bone.name + '" in armature "' +\
							armatureObj.name + '" has a mesh switch option ' +\
							'with no defined mesh.')
					elif switchOption.optionArmature not in linkedArmatures and \
						switchOption.optionArmature not in currentArmatures:
						linkedArmatures.append(switchOption.optionArmature)
	
	currentArmatures.extend(linkedArmatures)
	for linkedArmature in linkedArmatures:
		getAllArmatures(linkedArmature, currentArmatures)


# Convert to Geolayout
def convertArmatureToGeolayout(armatureObj, obj, convertTransformMatrix, 
	f3dType, isHWv1):
	
	fModel = FModel(f3dType, isHWv1)

	if len(armatureObj.children) == 0:
		raise ValueError("No mesh parented to armature.")

	obj.data.calc_loop_triangles()
	obj.data.calc_normals_split()
	edgeDict = getEdgeToFaceDict(obj.data)
	vertDict = getVertToFaceDict(obj.data)

	# Find start bone, which is not root. Root is the start for animation.
	startBoneName = findStartBone(armatureObj)
	
	convertTransformMatrix = convertTransformMatrix @ \
		mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()

	# Start geolayout
	geolayout = Geolayout()
	geolayout.rootNode = RootTransformNode(StartNode(), toAlnum(armatureObj.name))
	processBone(fModel, startBoneName, obj, armatureObj, 
		convertTransformMatrix, None, None, None, geolayout.rootNode, [], '',
		geolayout, edgeDict, vertDict)
	generateSwitchOptions(geolayout.rootNode)
	return geolayout.rootNode, fModel

def selectMeshChildrenOnly(obj):
	obj.select_set(True)
	obj.original_name = obj.name
	for child in obj.children:
		if isinstance(child.data, bpy.types.Mesh):
			selectMeshChildrenOnly(child)

def convertObjectToGeolayout(obj, convertTransformMatrix, 
	f3dType, isHWv1):
	
	fModel = FModel(f3dType, isHWv1)
	
	#convertTransformMatrix = convertTransformMatrix @ \
	#	mathutils.Matrix.Diagonal(obj.scale).to_4x4()

	# Start geolayout
	geolayout = Geolayout()
	geolayout.rootNode = RootTransformNode(StartNode(), toAlnum(obj.name))

	# Duplicate objects to apply scale / modifiers / linked data
	bpy.ops.object.select_all(action = 'DESELECT')
	selectMeshChildrenOnly(obj)
	obj.select_set(True)
	bpy.context.view_layer.objects.active = obj
	bpy.ops.object.duplicate()
	try:
		tempObj = bpy.context.view_layer.objects.active
		allObjs = bpy.context.selected_objects
		bpy.ops.object.make_single_user(obdata = True)
		bpy.ops.object.transform_apply(location = False, 
			rotation = False, scale = True, properties =  False)
		for selectedObj in allObjs:
			bpy.ops.object.select_all(action = 'DESELECT')
			selectedObj.select_set(True)
			for modifier in selectedObj.modifiers:
				bpy.ops.object.modifier_apply(apply_as='DATA',
					modifier=modifier.name)
		processMesh(fModel, tempObj, convertTransformMatrix,
			geolayout.rootNode, True)
		cleanupDuplicatedObjects(allObjs)
	except Exception as e:
		cleanupDuplicatedObjects(allObjs)
		raise Exception(str(e))

	return geolayout.rootNode, fModel

# C Export
def exportGeolayoutArmatureC(armatureObj, obj, convertTransformMatrix, 
	f3dType, isHWv1, dirPath, texDir, savePNG, texSeparate):
	rootNode, fModel = convertArmatureToGeolayout(armatureObj, obj,
		convertTransformMatrix, f3dType, isHWv1)

	saveGeolayoutC(armatureObj.name, rootNode, fModel, dirPath, texDir,
		savePNG, texSeparate)

def exportGeolayoutObjectC(obj, convertTransformMatrix, 
	f3dType, isHWv1, dirPath, texDir, savePNG, texSeparate):
	rootNode, fModel = convertObjectToGeolayout(obj, 
		convertTransformMatrix, f3dType, isHWv1)

	saveGeolayoutC(obj.name, rootNode, fModel, dirPath, texDir,
		savePNG, texSeparate)

def saveGeolayoutC(dirName, rootNode, fModel, dirPath, texDir, savePNG,
 	texSeparate):
	geoDirPath = os.path.join(dirPath, toAlnum(dirName))

	if not os.path.exists(geoDirPath):
		os.mkdir(geoDirPath)

	if savePNG:
		fModel.save_c_tex_separate(True, texDir, geoDirPath, texSeparate)
		fModel.freePalettes()
	else:
		fModel.freePalettes()
		modelPath = os.path.join(geoDirPath, 'model.inc.c')
		dlData = fModel.to_c(True)
		dlFile = open(modelPath, 'w')
		dlFile.write(dlData)
		dlFile.close()

	geoPath = os.path.join(geoDirPath, 'geo.inc.c')
	geoData = rootNode.to_c()
	geoFile = open(geoPath, 'w')
	geoFile.write(geoData)
	geoFile.close()

	headerPath = os.path.join(geoDirPath, 'header.h')
	cDefine = rootNode.to_c_def() + fModel.to_c_def()
	cDefFile = open(headerPath, 'w')
	cDefFile.write(cDefine)
	cDefFile.close()


# Binary Bank 0 Export
def exportGeolayoutArmatureBinaryBank0(romfile, armatureObj, obj, exportRange,	
 	convertTransformMatrix, levelCommandPos, modelID, textDumpFilePath, 
	f3dType, isHWv1, RAMAddr):
	
	rootNode, fModel = convertArmatureToGeolayout(armatureObj, obj,
		convertTransformMatrix, f3dType, isHWv1)
	
	return saveGeolayoutBinaryBank0(romfile, fModel, rootNode, exportRange,	
 		levelCommandPos, modelID, textDumpFilePath, f3dType, isHWv1, RAMAddr)

def exportGeolayoutObjectBinaryBank0(romfile, obj, exportRange,	
 	convertTransformMatrix, levelCommandPos, modelID, textDumpFilePath, 
	f3dType, isHWv1, RAMAddr):
	
	rootNode, fModel = convertObjectToGeolayout(obj, 
		convertTransformMatrix, f3dType, isHWv1)
	
	return saveGeolayoutBinaryBank0(romfile, fModel, rootNode, exportRange,	
 		levelCommandPos, modelID, textDumpFilePath, f3dType, isHWv1, RAMAddr)

def saveGeolayoutBinaryBank0(romfile, fModel, rootNode, exportRange,	
 	levelCommandPos, modelID, textDumpFilePath, f3dType, isHWv1, RAMAddr):
	fModel.freePalettes()
	segmentData = copy.copy(bank0Segment)
	startRAM = get64bitAlignedAddr(RAMAddr)
	nonGeoStartAddr = startRAM + len(rootNode.to_binary(None))

	addrRange = fModel.set_addr(nonGeoStartAddr)
	addrEndInROM = addrRange[1] - startRAM + exportRange[0]
	if addrEndInROM > exportRange[1]:
		raise ValueError('Size too big: Data ends at ' + hex(addrEndInROM) +\
			', which is larger than the specified range.')
	bytesIO = BytesIO()
	#actualRAMAddr = get64bitAlignedAddr(RAMAddr)
	bytesIO.seek(startRAM)
	bytesIO.write(rootNode.to_binary(segmentData))
	fModel.save_binary(bytesIO, segmentData)

	data = bytesIO.getvalue()[startRAM:]
	bytesIO.close()

	startAddress = get64bitAlignedAddr(exportRange[0])
	romfile.seek(startAddress)
	romfile.write(data)

	segPointerData = encodeSegmentedAddr(startRAM, segmentData)
	geoWriteLevelCommand(romfile, segPointerData, levelCommandPos, modelID)
	geoWriteTextDump(textDumpFilePath, rootNode, segmentData)
	
	return ((startAddress, startAddress + len(data)), startRAM + 0x80000000)
	

# Binary Export
def exportGeolayoutArmatureBinary(romfile, armatureObj, obj, exportRange,	
 	convertTransformMatrix, levelData, levelCommandPos, modelID,
	textDumpFilePath, f3dType, isHWv1):

	rootNode, fModel = convertArmatureToGeolayout(armatureObj, obj,
		convertTransformMatrix, f3dType, isHWv1)

	return saveGeolayoutBinary(romfile, rootNode, fModel, exportRange,	
 		convertTransformMatrix, levelData, levelCommandPos, modelID,
		textDumpFilePath, f3dType, isHWv1)

def exportGeolayoutObjectBinary(romfile, obj, exportRange,	
 	convertTransformMatrix, levelData, levelCommandPos, modelID,
	textDumpFilePath, f3dType, isHWv1):
	
	rootNode, fModel = convertObjectToGeolayout(obj, 
		convertTransformMatrix, f3dType, isHWv1)
	
	return saveGeolayoutBinary(romfile, rootNode, fModel, exportRange,	
 		convertTransformMatrix, levelData, levelCommandPos, modelID,
		textDumpFilePath, f3dType, isHWv1)
	
def saveGeolayoutBinary(romfile, rootNode, fModel, exportRange,	
 	convertTransformMatrix, levelData, levelCommandPos, modelID,
	textDumpFilePath, f3dType, isHWv1):
	fModel.freePalettes()

	# Get length of data, then actually write it after relative addresses 
	# are found.
	startAddress = get64bitAlignedAddr(exportRange[0])
	nonGeoStartAddr = startAddress + len(rootNode.to_binary(None))

	addrRange = fModel.set_addr(nonGeoStartAddr)
	if addrRange[1] > exportRange[1]:
		raise ValueError('Size too big: Data ends at ' + hex(addrRange[1]) +\
			', which is larger than the specified range.')
	romfile.seek(startAddress)
	romfile.write(rootNode.to_binary(levelData))
	fModel.save_binary(romfile, levelData)

	segPointerData = encodeSegmentedAddr(startAddress, levelData)
	geoWriteLevelCommand(romfile, segPointerData, levelCommandPos, modelID)
	geoWriteTextDump(textDumpFilePath, rootNode, levelData)
	
	return (startAddress, addrRange[1]), bytesToHex(segPointerData)


def geoWriteLevelCommand(romfile, segPointerData, levelCommandPos, modelID):
	if levelCommandPos is not None and modelID is not None:
		romfile.seek(levelCommandPos + 3)
		romfile.write(modelID.to_bytes(1, byteorder='big'))
		romfile.seek(levelCommandPos + 4)
		romfile.write(segPointerData)

def geoWriteTextDump(textDumpFilePath, rootNode, levelData):
	if textDumpFilePath is not None:
		openfile = open(textDumpFilePath, 'w')
		openfile.write(rootNode.toTextDump(levelData))
		openfile.close()

# Switch Handling Process
# When convert armature to geolayout node hierarchy, mesh switch options
# are converted to switch node children, but material/draw layer options
# are converted to SwitchOverrideNodes. During this process, any material
# override geometry will be generated as well.

# Afterward, the node hierarchy is traversed again, and any SwitchOverride
# nodes are converted to actual geolayout node hierarchies.
def generateSwitchOptions(transformNode):
	overrideNodes = []
	if isinstance(transformNode.node, SwitchNode):
		i = 0
		while i < len(transformNode.children):
			childNode = transformNode.children[i]
			if isinstance(childNode.node, SwitchOverrideNode):
				drawLayer = childNode.node.drawLayer
				material = childNode.node.material
				specificMat = childNode.node.specificMat
				overrideType = childNode.node.overrideType

				# This should be a 0xB node
				copyNode = duplicateNode(transformNode.children[0],
					transformNode, transformNode.children.index(childNode))
				index = transformNode.children.index(childNode)
				transformNode.children.remove(childNode)
				#i -= 1
				# Assumes each switch child has only one child
				for overrideChild in transformNode.children[0].children:
					generateOverrideHierarchy(copyNode, overrideChild, 
						material, specificMat, overrideType, drawLayer, index)
				if material is not None:
					overrideNodes.append(copyNode)
			i += 1
	for childNode in transformNode.children:
		if childNode not in overrideNodes:
			generateSwitchOptions(childNode)

def generateOverrideHierarchy(parentCopyNode, transformNode, 
	material, specificMat, overrideType, drawLayer, index):
	#print(transformNode.node)
	if isinstance(transformNode.node, SwitchOverrideNode) and \
		material is not None:
		return

	copyNode = TransformNode(copy.copy(transformNode.node))
	copyNode.parent = parentCopyNode
	parentCopyNode.children.insert(index, copyNode)
	if not isinstance(copyNode.node, SwitchOverrideNode) and\
		copyNode.node.hasDL:
		if material is not None:
			copyNode.node.DLmicrocode = \
				copyNode.node.fMesh.drawMatOverrides[(material, specificMat, overrideType)]
		if drawLayer is not None:
			copyNode.node.drawLayer = drawLayer

	for child in transformNode.children:
		generateOverrideHierarchy(copyNode, child, material, specificMat, overrideType,
			drawLayer, transformNode.children.index(child))
		
def addStartNode(transformNode):
	optionNode = TransformNode(StartNode())
	optionNode.parent = transformNode
	transformNode.children.append(optionNode)
	return optionNode

def duplicateNode(transformNode, parentNode, index):
	optionNode = TransformNode(copy.copy(transformNode.node))
	optionNode.parent = parentNode
	parentNode.children.insert(index, optionNode)
	return optionNode

def addPreTranslateRotateNode(parentTransformNode, 
	translate, rotate):
	preNodeTransform = TransformNode(
		TranslateRotateNode(1, 0, False, translate, rotate))

	preNodeTransform.parent = parentTransformNode
	parentTransformNode.children.append(preNodeTransform)
	return preNodeTransform

def addPreRenderAreaNode(parentTransformNode, cullingRadius):
	preNodeTransform = TransformNode(StartRenderAreaNode(cullingRadius))

	preNodeTransform.parent = parentTransformNode
	parentTransformNode.children.append(preNodeTransform)
	return preNodeTransform

class Geolayout:
	def __init__(self):
		self.rootNode = None
		# dict of Object : geolayout
		self.secondaryGeolayouts = {}

class RootTransformNode:
	def __init__(self, node, name):
		self.name = name
		self.node = node
		self.children = []
		self.parent = None

		# dict of Object : node
		self.switchArmatures = {}
	
	def to_binary(self, segmentData):
		data = self.node.to_binary(segmentData)
		if len(self.children) > 0:
			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_OPEN, 0x00, 0x00, 0x00]))
			for child in self.children:
				data.extend(child.to_binary(segmentData))
			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_CLOSE, 0x00, 0x00, 0x00]))
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		data.extend(bytearray([GEO_END, 0x00, 0x00, 0x00]))
		return data
	
	def to_c(self):
		data = 'const GeoLayout ' + self.name + '[] = {\n'
		data += '\t' + self.node.to_c() + '\n'
		if len(self.children) > 0:
			if type(self.node) in nodeGroupClasses:
				data += '\t' + 'GEO_OPEN_NODE(),\n'
			for child in self.children:
				data += child.to_c(2)
			if type(self.node) in nodeGroupClasses:
				data += '\t' + 'GEO_CLOSE_NODE(),\n'
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		data += '\t' + 'GEO_RETURN(),\n'
		data += '};\n'
		return data

	def to_c_def(self):
		return 'extern const GeoLayout ' + self.name + '[];\n'
	
	def toTextDump(self, segmentData):
		data = ''
		command = self.node.to_binary(segmentData)

		for byteVal in command:
			data += (format(byteVal, '02X') + ' ')
		data += '\n'

		if len(self.children) > 0:
			if command[0] in nodeGroupCmds:
				data += '04 00 00 00\n'
			for child in self.children:
				data += child.toTextDump(1, segmentData)
			if command[0] in nodeGroupCmds:
				data += '05 00 00 00\n'
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		data += '01 00 00 00'
		return data

class TransformNode:
	def __init__(self, node):
		self.node = node
		self.children = []
		self.parent = None
	
	# Function commands usually effect the following command, so it is similar
	# to a parent child relationship.
	def to_binary(self, segmentData):
		data = self.node.to_binary(segmentData)
		if len(self.children) > 0:
			if type(self.node) is DisplayListNode:
				raise ValueError("A DisplayListNode cannot have children.")
			elif type(self.node) is FunctionNode:
				raise ValueError("An FunctionNode cannot have children.")

			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_OPEN, 0x00, 0x00, 0x00]))
			for child in self.children:
				data.extend(child.to_binary(segmentData))
			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_CLOSE, 0x00, 0x00, 0x00]))
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		return data

	def to_c(self, depth):
		data = depth * '\t' + self.node.to_c() + '\n'
		if len(self.children) > 0:
			if type(self.node) in nodeGroupClasses:
				data += depth * '\t' + 'GEO_OPEN_NODE(),\n'
			for child in self.children:
				data += child.to_c(depth + 1)
			if type(self.node) in nodeGroupClasses:
				data += depth * '\t' + 'GEO_CLOSE_NODE(),\n'
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		return data
	
	def toTextDump(self, nodeLevel, segmentData):
		data = ''
		command = self.node.to_binary(segmentData)

		data += '\t' * nodeLevel
		for byteVal in command:
			data += (format(byteVal, '02X') + ' ')
		data += '\n'

		if len(self.children) > 0:
			if command[0] in nodeGroupCmds:
				data += '\t' * nodeLevel + '04 00 00 00\n'
			for child in self.children:
				data += child.toTextDump(nodeLevel + 1, segmentData)
			if command[0] in nodeGroupCmds:
				data += '\t' * nodeLevel + '05 00 00 00\n'
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		return data

# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
def processMesh(fModel, obj, transformMatrix, parentTransformNode, isRoot):
	#finalTransform = copy.deepcopy(transformMatrix)

	if not isinstance(obj.data, bpy.types.Mesh):
		return

	translate = obj.matrix_local.decompose()[0]
	rotate = obj.matrix_local.decompose()[1]

	#translation = mathutils.Matrix.Translation(translate)
	#rotation = rotate.to_matrix().to_4x4()

	geoCmd = obj.geo_cmd_static

	if obj.use_render_area:
		parentTransformNode = \
			addPreRenderAreaNode(parentTransformNode, obj.culling_radius)

	rotAxis, rotAngle = rotate.to_axis_angle()
	if rotAngle > 0.00001:
		if geoCmd == 'Billboard':
			node = BillboardNode(int(obj.draw_layer_static), True, 
				mathutils.Vector((0,0,0)))
		else:
			node = DisplayListWithOffsetNode(int(obj.draw_layer_static), True,
				mathutils.Vector((0,0,0)))	

		parentTransformNode = addPreTranslateRotateNode(
			parentTransformNode, translate, rotate)

	else:
		if geoCmd == 'Billboard':
			node = BillboardNode(int(obj.draw_layer_static), True, translate)
		else:
			node = DisplayListWithOffsetNode(int(obj.draw_layer_static), True,
				translate)

	transformNode = TransformNode(node)

	meshGroup = saveStaticModel(fModel, obj, transformMatrix)
	if meshGroup is None:
		node.hasDL = False
	else:
		node.DLmicrocode = meshGroup.mesh.draw
		node.fMesh = meshGroup.mesh

	parentTransformNode.children.append(transformNode)
	transformNode.parent = parentTransformNode
	
	for childObj in obj.children:
		processMesh(fModel, childObj, transformMatrix, transformNode, False)

# need to remember last geometry holding parent bone.
# to do skinning, add the 0x15 command before any non-geometry bone groups.
# 

# transformMatrix is a constant matrix to apply to verts, 
# not related to heirarchy.

# lastTransformParentName: last parent with mesh data.
# lastDeformParentName: last parent in transform node category.
# this may or may not include mesh data.

# If an armature is rotated, its bones' local_matrix will remember original
# rotation. Thus we don't want a bone's matrix relative to armature, but
# relative to the root bone of the armature.

def processBone(fModel, boneName, obj, armatureObj, transformMatrix,
	lastTranslateName, lastRotateName, lastDeformName, parentTransformNode,
	materialOverrides, namePrefix, geolayout, edgeDict, vertDict):
	bone = armatureObj.data.bones[boneName]
	poseBone = armatureObj.pose.bones[boneName]
	boneGroup = poseBone.bone_group
	finalTransform = copy.deepcopy(transformMatrix)
	materialOverrides = copy.copy(materialOverrides)
	
	if boneGroup is not None and boneGroup.name == 'Ignore':
		return

	# Get translate
	if lastTranslateName is not None:
		translateParent = armatureObj.data.bones[lastTranslateName]
		translate = (translateParent.matrix_local.inverted() @ \
			bone.matrix_local).decompose()[0]
	else:
		translateParent = None
		translate = bone.matrix_local.decompose()[0]

	# Get rotate
	if lastRotateName is not None:
		rotateParent = armatureObj.data.bones[lastRotateName]
		rotate = (rotateParent.matrix_local.inverted() @ \
			bone.matrix_local).decompose()[1]
	else:
		rotateParent = None
		rotate = bone.matrix_local.decompose()[1]

	translation = mathutils.Matrix.Translation(translate)
	rotation = rotate.to_matrix().to_4x4()

	if boneGroup is None:
		rotAxis, rotAngle = rotate.to_axis_angle()
		if rotAngle > 0.00001:
			node = DisplayListWithOffsetNode(int(bone.draw_layer),
				bone.use_deform, mathutils.Vector((0,0,0)))	

			parentTransformNode = addPreTranslateRotateNode(
				parentTransformNode, translate, rotate)

			lastTranslateName = boneName
			lastRotateName = boneName
		else:
			node = DisplayListWithOffsetNode(int(bone.draw_layer),
				bone.use_deform, translate)
			lastTranslateName = boneName
		
		finalTransform = transformMatrix @ translation	
	
	elif boneGroup.name == 'Function':
		if bone.geo_func == '':
			raise ValueError('Function bone ' + boneName + ' function value is empty.')
		node = FunctionNode(bone.geo_func, bone.func_param)
	elif boneGroup.name == 'HeldObject':
		if bone.geo_func == '':
			raise ValueError('Held object bone ' + boneName + ' function value is empty.')
		node = HeldObjectNode(bone.geo_func, translate)
	else:
		if boneGroup.name == 'Switch':
			# This is done so we can easily calculate transforms 
			# of switch options.
			
			if bone.geo_func == '':
				raise ValueError('Switch bone ' + boneName + \
					' function value is empty.')
			node = SwitchNode(bone.geo_func, bone.func_param)
			processSwitchBoneMatOverrides(materialOverrides, bone)
			
		elif boneGroup.name == 'Start':
			node = StartNode()
		elif boneGroup.name == 'TranslateRotate':
			drawLayer = int(bone.draw_layer)
			fieldLayout = int(bone.field_layout)
			hasDL = bone.use_deform

			node = TranslateRotateNode(drawLayer, fieldLayout, hasDL, 
				translate, rotate)
			
			if node.fieldLayout == 0:
				finalTransform = transformMatrix @ translation @ rotation
				lastTranslateName = boneName
				lastRotateName = boneName
			elif node.fieldLayout == 1:
				finalTransform = transformMatrix @ translation
				lastTranslateName = boneName
			elif node.fieldLayout == 2:
				finalTransform = transformMatrix @ rotation
				lastRotateName = boneName
			else:
				yRot = rotate.to_euler().y
				rotation = mathutils.Euler((0, yRot, 0)).to_matrix().to_4x4()
				finalTransform = transformMatrix @ rotation
				lastRotateName = boneName
			
		elif boneGroup.name == 'Translate':
			node = TranslateNode(int(bone.draw_layer), bone.use_deform,
				translate)
			finalTransform = transformMatrix @ translation
			lastTranslateName = boneName
		elif boneGroup.name == 'Rotate':
			node = RotateNode(int(bone.draw_layer), bone.use_deform, rotate)
			finalTransform = transformMatrix @ rotation
			lastRotateName = boneName
		elif boneGroup.name == 'Billboard':
			node = BillboardNode(int(bone.draw_layer), bone.use_deform,
				translate)
			finalTransform = transformMatrix @ translation
			lastTranslateName = boneName
		elif boneGroup.name == 'DisplayList':
			node = DisplayListNode(int(bone.draw_layer))
			if not armatureObj.data.bones[boneName].use_deform:
				raise ValueError("Display List (0x15) " + boneName + ' must be a deform bone. Make sure deform is checked in bone properties.')
		elif boneGroup.name == 'Shadow':
			shadowType = int(bone.shadow_type)
			shadowSolidity = bone.shadow_solidity 
			shadowScale = bone.shadow_scale
			node = ShadowNode(shadowType, shadowSolidity, shadowScale)
		elif boneGroup.name == 'Scale':
			node = ScaleNode(int(bone.draw_layer), bone.geo_scale,
				bone.use_deform)
			finalTransform = transformMatrix @ \
				mathutils.Matrix.Scale(node.scaleValue, 4)
		elif boneGroup.name == 'StartRenderArea':
			node = StartRenderAreaNode(bone.culling_radius)
		else:
			raise ValueError("Invalid bone group " + boneGroup.name)
	
	transformNode = TransformNode(node)

	# TODO: HERE!!!
	if node.hasDL:
		meshGroup = saveModelGivenVertexGroup(
			fModel, obj, bone.name, lastDeformName,
			finalTransform, armatureObj, materialOverrides, namePrefix, edgeDict,
			vertDict)

		if meshGroup is None:
			#print("No mesh data.")
			if isinstance(node, DisplayListNode):
				raise ValueError("Display List (0x15) " + boneName + " must have vertices assigned to it. If you have already done this, make sure there aren't any other bones that also own these vertices with greater or equal weighting.")
			node.hasDL = False
			bone.use_deform = False
			parentTransformNode.children.append(transformNode)
			transformNode.parent = parentTransformNode
		else:
			node.DLmicrocode = meshGroup.mesh.draw
			node.fMesh = meshGroup.mesh # Used for material override switches
			if lastDeformName is not None and \
				armatureObj.data.bones[lastDeformName].geo_cmd == 'SwitchOption' \
				and meshGroup.skinnedMesh is not None:
				raise ValueError("Cannot skin geometry to a Switch Option " +\
					"bone. Skinning cannot occur across a switch node.")


			transformNode = addSkinnedMeshNode(armatureObj, boneName,
				meshGroup.skinnedMesh, transformNode, parentTransformNode)

			lastDeformName = boneName
			#print(boneName)
	else:
		parentTransformNode.children.append(transformNode)
		transformNode.parent = parentTransformNode
	
	isSwitch = isinstance(transformNode.node, SwitchNode)
	if isSwitch:
		switchTransformNode = transformNode
		option0Node = addStartNode(transformNode)
		#option0Node = addPreTranslateRotateNode(armatureObj, transformNode,
		#	mathutils.Vector((0,0,0)), mathutils.Quaternion())
		transformNode = option0Node

	#print(boneGroup.name if boneGroup is not None else "Offset")
	if len(bone.children) > 0: 
		#print("\tHas Children")
		if boneGroup is not None and boneGroup.name == 'Function':
			raise ValueError("Function bones cannot have children. They instead affect the next sibling bone in alphabetical order.")

		# Handle child nodes
		# nonDeformTransformData should be modified to be sent to children,
		# otherwise it should not be modified for parent.
		# This is so it can be used for siblings.
		childrenNames = sorted([bone.name for bone in bone.children])
		for name in childrenNames:
			processBone(fModel, name, obj, armatureObj, 
				finalTransform, lastTranslateName, lastRotateName, 
				lastDeformName, transformNode, materialOverrides, namePrefix, 
				geolayout, edgeDict, vertDict)
			#transformNode.children.append(childNode)
			#childNode.parent = transformNode
	
	# see generateSwitchOptions() for explanation.
	if isSwitch:
		bone = armatureObj.data.bones[boneName]
		for switchIndex in range(len( bone.switch_options)):
			switchOption = bone.switch_options[switchIndex]
			if switchOption.switchType == 'Mesh':
				optionArmature = switchOption.optionArmature
				if optionArmature is None:
					raise ValueError('Error: In switch bone ' + boneName +\
						' for option ' + str(switchIndex) + \
						', the switch option armature is None.')
				elif not isinstance(optionArmature.data, bpy.types.Armature):
					raise ValueError('Error: In switch bone ' + boneName +\
						' for option ' + str(switchIndex) + \
						', the object provided is not an armature.')
				elif optionArmature in geolayout.secondaryGeolayouts:
					raise ValueError('Error: In switch bone ' + boneName +\
						' for option ' + str(switchIndex) + \
						', the armature provided cannot be used more than once' + \
						' as a switch option in the entire geolayout.')

				#optionNode = addStartNode(switchTransformNode)
				
				optionBoneName = getSwitchOptionBone(optionArmature)
				optionBone = optionArmature.data.bones[optionBoneName]
				switchOptionRotate = (bone.matrix_local.inverted() @ \
					optionBone.matrix_local).decompose()[1]
				switchOptionRotate = mathutils.Quaternion()

				# Armature doesn't matter here since node is not based off bone
				translateRotateNode = addPreTranslateRotateNode(
					switchTransformNode, translate, rotate @ switchOptionRotate)
				
				geolayout.secondaryGeolayouts[optionArmature] = translateRotateNode
	
				childrenNames = sorted(
					[bone.name for bone in optionBone.children])
				for name in childrenNames:
					# We can use optionBone as the last translate/rotate
					# since we added a TranslateRotate node before
					# the switch node.
					optionObjs = []
					for childObj in optionArmature.children:
						if isinstance(childObj.data, bpy.types.Mesh):
							optionObjs.append(childObj)
					if len(optionObjs) > 1:
						raise ValueError('Error: In switch bone ' + boneName +\
						' for option ' + str(switchIndex) + \
						', the switch option armature has more than one mesh child.')
					elif len(optionObjs) < 1:
						raise ValueError('Error: In switch bone ' + boneName +\
						' for option ' + str(switchIndex) + \
						', the switch option armature has no mesh children.')
					optionObj = optionObjs[0]
					optionObj.data.calc_loop_triangles()
					optionObj.data.calc_normals_split()
					optionEdgeDict = getEdgeToFaceDict(optionObj.data)
					optionVertDict = getVertToFaceDict(optionObj.data)
					processBone(fModel, name, optionObj,
						optionArmature,
						finalTransform, optionBone.name, optionBone.name,
						optionBone.name, translateRotateNode, materialOverrides,
						optionBone.name, geolayout, optionEdgeDict, 
						optionVertDict)
			else:
				if switchOption.switchType == 'Material':
					material = switchOption.materialOverride
					if switchOption.overrideDrawLayer:
						drawLayer = int(switchOption.drawLayer)
					else:
						drawLayer = None
					if switchOption.materialOverrideType == 'Specific':
						specificMat = tuple([matPtr.material for matPtr in \
							switchOption.specificOverrideArray])
					else:
						specificMat = tuple([matPtr.material for matPtr in \
							switchOption.specificIgnoreArray])
				else:
					material = None
					specificMat = None
					drawLayer = int(switchOption.drawLayer)
				
				overrideNode = TransformNode(SwitchOverrideNode(
					material, specificMat, drawLayer,
					switchOption.materialOverrideType))
				overrideNode.parent = switchTransformNode
				switchTransformNode.children.append(overrideNode)

def processSwitchBoneMatOverrides(materialOverrides, switchBone):
	for switchOption in switchBone.switch_options:
		if switchOption.switchType == 'Material':
			if switchOption.materialOverride is None:
				raise ValueError("Error: On switch bone " + \
					switchBone.name + ', a switch option' + \
					' is a Material Override, but no material is provided.')
			if switchOption.materialOverrideType == 'Specific':
				for mat in switchOption.specificOverrideArray:
					if mat is None:
						raise ValueError("Error: On switch bone " + \
							switchBone.name + ', a switch option' + \
							' has a material override field that is None.')
				specificMat = tuple([matPtr.material for matPtr in \
							switchOption.specificOverrideArray])		
			else:
				for mat in switchOption.specificIgnoreArray:
					if mat is None:
						raise ValueError("Error: On switch bone " + \
							switchBone.name + ', a switch option' + \
							' has a material ignore field that is None.')
				specificMat = tuple([matPtr.material for matPtr in \
							switchOption.specificIgnoreArray])

			materialOverrides.append((switchOption.materialOverride, specificMat,
				switchOption.materialOverrideType))

class SwitchOverrideNode:
	def __init__(self, material, specificMat, drawLayer, overrideType):
		self.material = material
		self.specificMat = specificMat
		self.drawLayer = drawLayer
		self.overrideType = overrideType

# We add Function commands to nonDeformTransformData because any skinned
# 0x15 commands should go before them, as they are usually preceding
# an empty transform command (of which they modify?)
class FunctionNode:
	def __init__(self, geo_func, func_param):
		self.geo_func = geo_func
		self.func_param = func_param
		self.hasDL = False
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_CALL_ASM, 0x00])
		command.extend(self.func_param.to_bytes(2, 'big', signed = True))
		command.extend(bytes.fromhex(self.geo_func))
		return command

	def to_c(self):
		return "GEO_ASM(" + str(self.func_param) + ', ' + \
			toAlnum(self.geo_func) + '),'

class HeldObjectNode:
	def __init__(self, geo_func, translate):
		self.geo_func = geo_func
		self.translate = translate
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_HELD_OBJECT, 0x00])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		command.extend(bytes.fromhex(self.geo_func))
		return command
	
	def to_c(self):
		return "GEO_HELD_OBJECT(0, " + \
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) + ', ' +\
			toAlnum(self.geo_func) + '),'

class StartNode:
	def __init__(self):
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_START, 0x00, 0x00, 0x00])
		return command

	def to_c(self):
		return "GEO_NODE_START(),"

class EndNode:
	def __init__(self):
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_END, 0x00, 0x00, 0x00])
		return command

	def to_c(self):
		return 'GEO_END(),'

# Geolayout node hierarchy is first generated without material/draw layer
# override options, but with material override DL's being generated.
# Afterward, for each switch node the node hierarchy is duplicated and
# the correct diplsay lists are added.
class SwitchNode:
	def __init__(self, geo_func, func_param):
		self.switchFunc = geo_func
		self.defaultCase = func_param
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_SWITCH, 0x00])
		command.extend(self.defaultCase.to_bytes(2, 'big', signed = True))
		command.extend(bytes.fromhex(self.switchFunc))
		return command

	def to_c(self):
		return "GEO_SWITCH_CASE(" + \
			str(self.defaultCase) + ', ' +\
			toAlnum(self.switchFunc) + '),'

class TranslateRotateNode:
	def __init__(self, drawLayer, fieldLayout, hasDL, translate, rotate):

		self.drawLayer = drawLayer
		self.fieldLayout = fieldLayout
		self.hasDL = hasDL

		self.translate = translate
		self.rotate = rotate

		self.fMesh = None
		self.DLmicrocode = None
		
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) & \
			(self.fieldLayout << 4) | self.drawLayer

		command = bytearray([GEO_TRANSLATE_ROTATE, params])
		if self.fieldLayout == 0:
			command.extend(bytearray([0x00] * 14))
			writeVectorToShorts(command, 4, self.translate)
			writeEulerVectorToShorts(command, 10, 
				self.rotate.to_euler(geoNodeRotateOrder))
		elif self.fieldLayout == 1:
			command.extend(bytearray([0x00] * 6))
			writeVectorToShorts(command, 2, self.translate)
		elif self.fieldLayout == 2:
			command.extend(bytearray([0x00] * 6))
			writeEulerVectorToShorts(command, 2, 
				self.rotate.to_euler(geoNodeRotateOrder))
		elif self.fieldLayout == 3:
			command.extend(bytearray([0x00] * 2))
			writeFloatToShort(command, 2, 
			self.rotate.to_euler(geoNodeRotateOrder).y)
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		if self.fieldLayout == 0:
			return ("GEO_TRANSLATE_ROTATE_WITH_DL" if self.hasDL else \
				"GEO_TRANSLATE_ROTATE") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertFloatToShort(self.translate[0])) + ', ' +\
				str(convertFloatToShort(self.translate[1])) + ', ' +\
				str(convertFloatToShort(self.translate[2])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[0])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[2])) + \
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
		elif self.fieldLayout == 1:
			return ("GEO_TRANSLATE_WITH_DL" if self.hasDL else \
				"GEO_TRANSLATE") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertFloatToShort(self.translate[0])) + ', ' +\
				str(convertFloatToShort(self.translate[1])) + ', ' +\
				str(convertFloatToShort(self.translate[2])) +\
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
		elif self.fieldLayout == 2:
			return ("GEO_ROTATE_WITH_DL" if self.hasDL else \
				"GEO_ROTATE") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[0])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[2])) + \
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
		elif self.fieldLayout == 3:
			return ("GEO_ROTATE_Y_WITH_DL" if self.hasDL else \
				"GEO_ROTATE_Y") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) +\
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class TranslateNode:
	def __init__(self, drawLayer, useDeform, translate):
		self.drawLayer = drawLayer
		self.hasDL = useDeform
		self.translate = translate
		self.fMesh = None
		self.DLmicrocode = None
		
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_TRANSLATE, params])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command
	
	def to_c(self):
		return ("GEO_TRANSLATE_NODE_WITH_DL" if self.hasDL else \
			"GEO_TRANSLATE_NODE") + "(" + \
			str(self.drawLayer) + ', ' +\
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) +\
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class RotateNode:
	def __init__(self, drawLayer, hasDL, rotate):
		# In the case for automatically inserting rotate nodes between
		# 0x13 bones.

		self.drawLayer = drawLayer
		self.hasDL = hasDL
		self.rotate = rotate
		self.fMesh = None
		self.DLmicrocode = None
		
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_ROTATE, params])
		command.extend(bytearray([0x00] * 6))
		writeEulerVectorToShorts(command, 2, 
			self.rotate.to_euler(geoNodeRotateOrder))
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return ("GEO_ROTATION_NODE_WITH_DL" if self.hasDL else \
			"GEO_ROTATION_NODE") + "(" + \
			str(self.drawLayer) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[0])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[2])) + \
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
	
class BillboardNode:
	def __init__(self, drawLayer, hasDL, translate):
		self.drawLayer = drawLayer
		self.hasDL = hasDL
		self.translate = translate
		self.fMesh = None
		self.DLmicrocode = None

	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_BILLBOARD, params])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return ("GEO_BILLBOARD_WITH_PARAMS_AND_DL" if self.hasDL else \
			"GEO_BILLBOARD_WITH_PARAMS") + "(" + \
			str(self.drawLayer) + ', ' +\
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) +\
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class DisplayListNode:
	def __init__(self, drawLayer):
		self.drawLayer = drawLayer
		self.hasDL = True
		self.fMesh = None
		self.DLmicrocode = None

	def to_binary(self, segmentData):
		if self.DLmicrocode is None:
			raise ValueError("No mesh data associated with this 0x15 command. Make sure you have assigned vertices to this node.")
		command = bytearray([GEO_LOAD_DL, self.drawLayer, 0x00, 0x00])
		if segmentData is not None:
			command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
		else:
			command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return "GEO_DISPLAY_LIST(" + \
			str(self.drawLayer) + ', ' +\
			self.DLmicrocode.name + '),'

class ShadowNode:
	def __init__(self, shadow_type, shadow_solidity, shadow_scale):
		self.shadowType = int(shadow_type)
		self.shadowSolidity = int(round(shadow_solidity * 0xFF))
		self.shadowScale = shadow_scale
		self.hasDL = False

	def to_binary(self, segmentData):
		command = bytearray([GEO_START_W_SHADOW, 0x00])
		command.extend(self.shadowType.to_bytes(2, 'big'))
		command.extend(self.shadowSolidity.to_bytes(2, 'big'))
		command.extend(self.shadowScale.to_bytes(2, 'big'))
		return command
	
	def to_c(self):
		return "GEO_SHADOW(" + \
			str(self.shadowType) + ', ' +\
			str(self.shadowSolidity) + ', ' +\
			str(self.shadowScale) + '),'

class ScaleNode:
	def __init__(self, drawLayer, geo_scale, use_deform):
		self.drawLayer = drawLayer
		self.scaleValue = geo_scale
		self.hasDL = use_deform
		self.fMesh = None
		self.DLmicrocode = None
	
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_SCALE, params, 0x00, 0x00])
		command.extend(int(self.scaleValue * 0x10000).to_bytes(4, 'big'))
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command
	
	def to_c(self):
		return ("GEO_SCALE_WITH_DL" if self.hasDL else "GEO_SCALE") + "(" + \
			str(self.drawLayer) + ', ' +\
			str(int(round(self.scaleValue * 0x10000))) +\
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class StartRenderAreaNode:
	def __init__(self, cullingRadius):
		self.cullingRadius = cullingRadius
		self.hasDL = False

	def to_binary(self, segmentData):
		command = bytearray([GEO_START_W_RENDERAREA, 0x00])
		command.extend(self.cullingRadius.to_bytes(2, 'big'))
		return command
	
	def to_c(self):
		return 'GEO_CULLING_RADIUS(' + str(self.cullingRadius) + '),'

class DisplayListWithOffsetNode:
	def __init__(self, drawLayer, use_deform, translate):
		self.drawLayer = drawLayer
		self.hasDL = use_deform
		self.translate = translate
		self.fMesh = None
		self.DLmicrocode = None

	def to_binary(self, segmentData):
		command = bytearray([GEO_LOAD_DL_W_OFFSET, self.drawLayer])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		if self.hasDL and self.DLmicrocode is not None and segmentData is not None:
			command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
		else:
			command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return "GEO_ANIMATED_PART(" + \
			str(self.drawLayer) + ', ' +\
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) + ', ' +\
			(self.DLmicrocode.name if self.hasDL else 'NULL') + '),'

def getGroupIndexFromname(obj, name):
	for group in obj.vertex_groups:
		if group.name == name:
			return group.index
	return None

def getGroupNameFromIndex(obj, index):
	for group in obj.vertex_groups:
		if group.index == index:
			return group.name
	return None

def getGroupIndex(vert, armatureObj, obj):
	actualGroups = []
	for group in vert.groups:
		groupName = getGroupNameFromIndex(obj, group.group)
		if groupName is not None and groupName in armatureObj.data.bones:
			actualGroups.append(group)

	if len(actualGroups) == 0:
		raise ValueError("All vertices must be part of a vertex group (weight painted), and the vertex group must correspond to a bone in the armature.")
	vertGroup = actualGroups[0]
	for group in actualGroups:
		if group.weight > vertGroup.weight:
			vertGroup = group

	return vertGroup.group

class SkinnedFace():
	def __init__(self, bFace, loopsInGroup, loopsNotInGroup):
		self.bFace= bFace
		self.loopsInGroup = loopsInGroup
		self.loopsNotInGroup = loopsNotInGroup

def checkIfFirstNonASMNode(childNode):
	index = childNode.parent.children.index(childNode)
	if index == 0:
		return True
	while index > 0 and \
		isinstance(childNode.parent.children[index - 1].node, FunctionNode):
		index -= 1
	return index == 0

# parent connects child node to itself
# skinned node handled by child

# A skinned mesh node should be before a mesh node.
# However, other transform nodes may exist in between two mesh nodes,
# So the skinned mesh node must be inserted before any of those transforms.
# Sibling mesh nodes thus cannot share the same transform nodes before it
# If they are both deform.
# Additionally, ASM nodes should count as modifiers for other nodes if 
# they precede them
def addSkinnedMeshNode(armatureObj, boneName, skinnedMesh, transformNode, parentNode):
	# Add node to its immediate parent
	#print(str(type(parentNode.node)) + str(type(transformNode.node)))
	parentNode.children.append(transformNode)
	transformNode.parent = parentNode

	if skinnedMesh is None:
		return transformNode
	#else:
	#	print("Skinned mesh exists.")

	# Get skinned node
	bone = armatureObj.data.bones[boneName]
	skinnedNode = DisplayListNode(int(bone.draw_layer))
	skinnedNode.fMesh = skinnedMesh
	skinnedNode.DLmicrocode = skinnedMesh.draw
	skinnedTransformNode = TransformNode(skinnedNode)

	# Ascend heirarchy until reaching first node before a deform parent.
	# We duplicate the hierarchy along the way to possibly use later.
	highestChildNode = transformNode
	transformNodeCopy = TransformNode(copy.copy(transformNode.node))
	transformNodeCopy.parent = parentNode
	highestChildCopy = transformNodeCopy
	isFirstChild = True
	hasNonDeform0x13Command = False
	acrossSwitchNode = False
	while highestChildNode.parent is not None and\
		not (highestChildNode.parent.node.hasDL): # empty 0x13 command?
		isFirstChild &= checkIfFirstNonASMNode(highestChildNode)
		hasNonDeform0x13Command &= highestChildNode.parent.node is \
			DisplayListWithOffsetNode

		acrossSwitchNode |= isinstance(highestChildNode.parent.node, SwitchNode)
			
		highestChildNode = highestChildNode.parent
		highestChildCopyParent = TransformNode(copy.copy(highestChildNode.node))
		highestChildCopyParent.children = [highestChildCopy]
		highestChildCopy.parent = highestChildCopyParent
		#print(str(highestChildCopy.node) + " " + str(isFirstChild))
		highestChildCopy = highestChildCopyParent
	if highestChildNode.parent is None:
		raise ValueError("There shouldn't be a skinned mesh section if there is no deform parent. This error may have ocurred if a switch option node is trying to skin to a parent but no deform parent exists.")

	# Otherwise, remove the transformNode from the parent and 
	# duplicate the node heirarchy up to the last deform parent.
	# Add the skinned node first to the last deform parent,
	# then add the duplicated node hierarchy afterward.
	if highestChildNode != transformNode:
		if not isFirstChild:
			#print("Hierarchy but not first child.")
			if hasNonDeform0x13Command:
				raise ValueError("Error with " + boneName + ': You cannot have more that one child skinned mesh connected to a parent skinned mesh with a non deform 0x13 bone in between. Try removing any unnecessary non-deform bones.')
		
			if acrossSwitchNode:
				raise ValueError("Error with " + boneName + ': You can not' +\
				' skin across a switch node with more than one child.')

			# Remove transformNode
			parentNode.children.remove(transformNode)
			transformNode.parent = None

			# copy hierarchy, along with any preceding Function commands
			highestChildIndex = \
				highestChildNode.parent.children.index(highestChildNode)
			precedingFunctionCmds = []
			while highestChildIndex > 0 and \
				type(highestChildNode.parent.children[\
				highestChildIndex - 1].node) is FunctionNode:

				precedingFunctionCmds.insert(0, copy.deepcopy(
					highestChildNode.parent.children[highestChildIndex - 1]))
				highestChildIndex -= 1
			#_____________
			# add skinned mesh node
			highestChildCopy.parent = highestChildNode.parent
			highestChildCopy.parent.children.append(skinnedTransformNode)
			skinnedTransformNode.parent = highestChildCopy.parent

			# add Function cmd nodes
			for asmCmdNode in precedingFunctionCmds:
				highestChildCopy.parent.children.append(asmCmdNode)

			# add heirarchy to parent
			highestChildCopy.parent.children.append(highestChildCopy)

			transformNode = transformNodeCopy
		else:
			#print("Hierarchy with first child.")
			nodeIndex = highestChildNode.parent.children.index(highestChildNode)
			while nodeIndex > 0 and \
				type(highestChildNode.parent.children[\
				nodeIndex - 1].node) is FunctionNode:
				nodeIndex -= 1
			highestChildNode.parent.children.insert(
				nodeIndex, skinnedTransformNode)
			skinnedTransformNode.parent = highestChildNode.parent
	else:
		#print("Immediate child.")
		nodeIndex = parentNode.children.index(transformNode)
		parentNode.children.insert(nodeIndex, skinnedTransformNode)
		skinnedTransformNode.parent = parentNode	

	return transformNode	

def getAncestorGroups(parentGroup, armatureObj, obj):
	if parentGroup is None:
		return []
	processingBones = \
		[bone for bone in armatureObj.data.bones if bone.parent is None]
	ancestorBones = []
	while len(processingBones) > 0:
		currentBone = processingBones[0]
		processingBones = processingBones[1:]
		if currentBone.name != parentGroup:
			ancestorBones.append(getGroupIndexFromname(obj, currentBone.name))
			processingBones.extend(currentBone.children)
	return ancestorBones

def checkUniqueBoneNames(fModel, name, vertexGroup):
	if name in fModel.meshGroups:
		raise ValueError(vertexGroup + " has already been processed. Make " +\
			"sure this bone name is unique, even across all switch option " +\
			"armatures.")

def saveModelGivenVertexGroup(fModel, obj, vertexGroup, 
	parentGroup, transformMatrix, armatureObj, materialOverrides, namePrefix,
	edgeDict, vertDict):
	checkForF3DMaterial(obj)

	mesh = obj.data
	currentGroupIndex = getGroupIndexFromname(obj, vertexGroup)
	vertIndices = [vert.index for vert in obj.data.vertices if\
		getGroupIndex(vert, armatureObj, obj) == currentGroupIndex]
	parentGroupIndex = getGroupIndexFromname(obj, parentGroup) \
		if parentGroup is not None else -1

	ancestorGroups = getAncestorGroups(parentGroup, armatureObj, obj)

	if len(vertIndices) == 0:
		return None

	bone = armatureObj.data.bones[vertexGroup]
	
	currentMatrix = mathutils.Matrix.Scale(1 / sm64ToBlenderScale, 4) @ \
		bone.matrix_local.inverted()
	
	if parentGroup is None:
		parentMatrix = mathutils.Matrix.Scale(1 / sm64ToBlenderScale, 4)
	else:
		parentBone = armatureObj.data.bones[parentGroup]
		parentMatrix = mathutils.Matrix.Scale(1 / sm64ToBlenderScale, 4) @ \
		parentBone.matrix_local.inverted()
	
	# dict of material_index keys to face array values
	groupFaces = {}
	
	# dict of material_index keys to SkinnedFace objects
	skinnedFaces = {}

	handledFaces = []
	for vertIndex in vertIndices:
		if vertIndex not in vertDict:
			continue
		for face in vertDict[vertIndex]:
			# generate a vertDict

			# Ignore repeat faces
			if face in handledFaces:
				continue
			else:
				handledFaces.append(face)

			loopsInGroup = []
			loopsNotInGroup = []
			isChildSkinnedFace = False

			# loop is interpreted as face + loop index
			for i in range(3):
				vertGroupIndex = \
					getGroupIndex(mesh.vertices[face.vertices[i]], 
						armatureObj, obj)
				if vertGroupIndex == currentGroupIndex:
					loopsInGroup.append((face, mesh.loops[face.loops[i]]))
				elif vertGroupIndex == parentGroupIndex:
					loopsNotInGroup.append((face, mesh.loops[face.loops[i]]))
				elif vertGroupIndex not in ancestorGroups:
					# Only want to handle skinned faces connected to parent
					isChildSkinnedFace = True
					break
				else:
					raise ValueError("Error with " + vertexGroup + ": Verts attached to one bone can not be attached to any of its ancestor bones besides its first immediate deformable parent bone. For example, a foot vertex can be connected to a leg vertex, but a foot vertex cannot be connected to a thigh vertex.")
			if isChildSkinnedFace:
				continue
			
			if len(loopsNotInGroup) == 0:
				if face.material_index not in groupFaces:
					groupFaces[face.material_index] = []
				groupFaces[face.material_index].append(face)
			else:
				if face.material_index not in skinnedFaces:
					skinnedFaces[face.material_index] = []
				skinnedFaces[face.material_index].append(
					SkinnedFace(face, loopsInGroup, loopsNotInGroup))

	# Save skinned mesh
	if len(skinnedFaces) > 0:
		#print("Skinned")
		fMeshGroup = saveSkinnedMeshByMaterial(skinnedFaces, fModel,
			vertexGroup, obj, currentMatrix, parentMatrix, namePrefix, edgeDict)
	else:
		fMeshGroup = FMeshGroup(toAlnum(namePrefix + vertexGroup), 
			FMesh(toAlnum(namePrefix + vertexGroup) + '_mesh'), None)
	
	# Save mesh group
	checkUniqueBoneNames(fModel, toAlnum(namePrefix + vertexGroup), vertexGroup)
	fModel.meshGroups[toAlnum(namePrefix + vertexGroup)] = fMeshGroup

	# Save unskinned mesh
	for material_index, bFaces in groupFaces.items():
		material = obj.data.materials[material_index]
		saveMeshByFaces(material, bFaces, 
			fModel, fMeshGroup.mesh, obj, currentMatrix, edgeDict)
	
	# End mesh drawing
	# Reset settings to prevent issues with other models
	revertMatAndEndDraw(fMeshGroup.mesh.draw)

	# Must be done after all geometry saved
	for (material, specificMat, overrideType) in materialOverrides:
		if fMeshGroup.mesh is not None:
			saveOverrideDraw(obj, fModel, material, specificMat, overrideType,
			fMeshGroup.mesh)
		if fMeshGroup.skinnedMesh is not None:
			saveOverrideDraw(obj, fModel, material, specificMat, overrideType,
			fMeshGroup.skinnedMesh)
	
	return fMeshGroup

def saveOverrideDraw(obj, fModel, material, specificMat, overrideType, fMesh):
	fOverrideMat, texDimensions = \
		saveOrGetF3DMaterial(material, fModel, obj)
	meshMatOverride = GfxList(
		fMesh.name + '_mat_override_' + toAlnum(material.name))
	#print('fdddddddddddddddd ' + str(fMesh.name) + " " + str(material) + " " + str(specificMat) + " " + str(overrideType))
	fMesh.drawMatOverrides[(material, specificMat, overrideType)] = meshMatOverride
	removeReverts = []
	for command in fMesh.draw.commands:
		meshMatOverride.commands.append(copy.copy(command))
	for command in meshMatOverride.commands:
		if isinstance(command, SPDisplayList):
			for modelMaterial, (fMaterial, texDimensions) in \
				fModel.materials.items():
				shouldModify = \
					(overrideType == 'Specific' and modelMaterial in specificMat) or \
					(overrideType == 'All' and modelMaterial not in specificMat)
				if command.displayList == fMaterial.material and shouldModify:
					#print(fOverrideMat.material.name)
					command.displayList = fOverrideMat.material
				if command.displayList == fMaterial.revert and shouldModify:
					if fOverrideMat.revert is not None:
						command.displayList = fOverrideMat.revert
					else:
						removeReverts.append(command)
	for command in removeReverts:
		meshMatOverride.commands.remove(command)

	#else:
	#	meshMatOverride.commands.append(SPDisplayList(fOverrideMat.material))
	#	for triList in fMesh.triangleLists:
	#		meshMatOverride.commands.append(SPDisplayList(triList))
	#	if fOverrideMat.revert is not None:
	#		meshMatOverride.commands.append(SPDisplayList(fOverrideMat.revert))
	#	meshMatOverride.commands.append(SPEndDisplayList())		

def findVertIndexInBuffer(loop, buffer, loopDict):
	i = 0
	for material_index, vertData in buffer:
		for f3dVert in vertData:
			if f3dVert == loopDict[loop]:
				return i
			i += 1
	#print("Can't find " + str(loop))
	return -1

def convertVertDictToArray(vertDict):
	data = []
	matRegions = {}
	for material_index, vertData in vertDict:
		start = len(data)
		data.extend(vertData)
		end = len(data)
		matRegions[material_index] = (start, end)
	return data, matRegions

# This collapses similar loops together IF they are in the same material.
def splitSkinnedFacesIntoTwoGroups(skinnedFaces, fModel, obj, uv_layer):
	inGroupVertArray = []
	notInGroupVertArray = []
	loopDict = {}
	for material_index, skinnedFaceArray in skinnedFaces.items():
		# These MUST be arrays (not dicts) as order is important
		inGroupVerts = []
		inGroupVertArray.append([material_index, inGroupVerts])
		
		notInGroupVerts = []
		notInGroupVertArray.append([material_index, notInGroupVerts])

		material = obj.data.materials[material_index]
		fMaterial, texDimensions = \
			saveOrGetF3DMaterial(material, fModel, obj)
		
		exportVertexColors = isLightingDisabled(material)
		convertInfo = LoopConvertInfo(uv_layer, obj, exportVertexColors)
		for skinnedFace in skinnedFaceArray:
			for (face, loop) in skinnedFace.loopsInGroup:
				f3dVert = getF3DVert(loop, face, convertInfo, obj.data)
				if f3dVert not in inGroupVerts:
					inGroupVerts.append(f3dVert)
				loopDict[loop] = f3dVert
			for (face, loop) in skinnedFace.loopsNotInGroup:
				f3dVert = getF3DVert(loop, face, convertInfo, obj.data)
				if f3dVert not in notInGroupVerts:
					notInGroupVerts.append(f3dVert)
				loopDict[loop] = f3dVert
	
	return inGroupVertArray, notInGroupVertArray, loopDict

def getGroupVertCount(group):
	count = 0
	for material_index, vertData in group:
		count += len(vertData)
	return count

def saveSkinnedMeshByMaterial(skinnedFaces, fModel, name, obj, 
	currentMatrix, parentMatrix, namePrefix, edgeDict):
	# We choose one or more loops per vert to represent a material from which 
	# texDimensions can be found, since it is required for UVs.
	uv_layer = obj.data.uv_layers.active.data
	inGroupVertArray, notInGroupVertArray, loopDict = \
		splitSkinnedFacesIntoTwoGroups(skinnedFaces, fModel, obj, uv_layer)

	notInGroupCount = getGroupVertCount(notInGroupVertArray)
	if notInGroupCount > fModel.f3d.vert_load_size - 2:
		raise ValueError("Too many connecting vertices in skinned " +\
			"triangles, max is " + str(fModel.f3d.vert_load_size - 2) + \
			" on parent bone, currently at " + str(notInGroupCount) +\
			". Note that a vertex with different UVs/normals/materials in " +\
			"connected faces will count more than once. Try " +\
			"keeping UVs contiguous, minimize edge creasing, and don't " +\
			"disable 'Smooth Shading'. " +\
			"Note that Blender's 'Shade Flat/Smooth' does not actually " +\
			"modify normal data.")
	
	# Load parent group vertices
	fSkinnedMesh = FMesh(toAlnum(namePrefix + name) + '_skinned')

	# Load verts into buffer by material.
	# It seems like material setup must be done BEFORE triangles are drawn.
	# Because of this we cannot share verts between materials (?)
	curIndex = 0
	for material_index, vertData in notInGroupVertArray:
		material = obj.data.materials[material_index]
		fMaterial, texDimensions = fModel.materials[material]
		isPointSampled = isTexturePointSampled(material)
		exportVertexColors = isLightingDisabled(material)

		skinnedTriList = fSkinnedMesh.tri_list_new()
		fSkinnedMesh.draw.commands.append(SPDisplayList(fMaterial.material))
		fSkinnedMesh.draw.commands.append(SPDisplayList(skinnedTriList))
		skinnedTriList.commands.append(
			SPVertex(fSkinnedMesh.vertexList, 
				len(fSkinnedMesh.vertexList.vertices), 
				len(vertData), curIndex))
		curIndex += len(vertData)

		for f3dVert in vertData:
			fSkinnedMesh.vertexList.vertices.append(convertVertexData(obj.data,
				f3dVert[0], f3dVert[1], f3dVert[2], texDimensions,
				parentMatrix, isPointSampled, exportVertexColors))
		
		skinnedTriList.commands.append(SPEndDisplayList())

	# End skinned mesh vertices.
	fSkinnedMesh.draw.commands.append(SPEndDisplayList())

	fMesh = FMesh(toAlnum(namePrefix + name) + '_mesh')

	# Load current group vertices, then draw commands by material
	existingVertData, matRegionDict = \
		convertVertDictToArray(notInGroupVertArray)
	for material_index, skinnedFaceArray in skinnedFaces.items():

		# We've already saved all materials, this just returns the existing ones.
		material = obj.data.materials[material_index]
		fMaterial, texDimensions = \
			saveOrGetF3DMaterial(material, fModel, obj)
		isPointSampled = isTexturePointSampled(material)
		exportVertexColors = isLightingDisabled(material)

		triList = fMesh.tri_list_new()
		fMesh.draw.commands.append(SPDisplayList(fMaterial.material))
		fMesh.draw.commands.append(SPDisplayList(triList))
		if fMaterial.revert is not None:
			fMesh.draw.commands.append(SPDisplayList(fMaterial.revert))

		convertInfo = LoopConvertInfo(uv_layer, obj, exportVertexColors)
		saveTriangleStrip(
			[skinnedFace.bFace for skinnedFace in skinnedFaceArray],
			convertInfo, triList, fMesh.vertexList, fModel.f3d, 
			texDimensions, currentMatrix, isPointSampled, exportVertexColors,
			copy.deepcopy(existingVertData), copy.deepcopy(matRegionDict),
			edgeDict, obj.data)
	
	return FMeshGroup(toAlnum(namePrefix + name), fMesh, fSkinnedMesh)

nodeGroupClasses = [
	StartNode,
	SwitchNode,
	TranslateRotateNode,
	TranslateNode,
	RotateNode,
	DisplayListWithOffsetNode,
	BillboardNode,
	ShadowNode,
	ScaleNode,
	StartRenderAreaNode
]