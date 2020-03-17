import bpy
from math import pi, ceil, degrees, radians
from mathutils import *
from .sm64_constants import *
from .sm64_geolayout_constants import *
import random
import string
import os
import math
import traceback

class PluginError(Exception):
	pass

def raisePluginError(operator, exception):
	if bpy.context.scene.fullTraceback:
		operator.report({'ERROR'}, traceback.format_exc())
	else:
		operator.report({'ERROR'}, str(exception))

def checkIdentityRotation(obj, rotation, allowYaw):
	# Hacky way to handle y-up conversion
	rotationDiff = (mathutils.Quaternion((1, 0, 0), math.radians(90.0)) @ rotation).to_euler()
	if abs(rotationDiff.x) > 0.001 or abs(rotationDiff.y) > 0.001 or abs(rotationDiff.z) > 0.001:
		raise PluginError("Water box \"" + obj.name + "\" cannot have a non-zero world rotation.")

def setOrigin(target, obj):
	bpy.ops.object.select_all(action = "DESELECT")
	obj.select_set(True)
	bpy.context.view_layer.objects.active = obj
	bpy.ops.object.transform_apply()
	bpy.context.scene.cursor.location = target.location
	bpy.ops.object.origin_set(type = 'ORIGIN_CURSOR')
	bpy.ops.object.select_all(action = "DESELECT")

def writeIfNotFound(filePath, stringValue, footer):
	if os.path.exists(filePath):
		fileData = open(filePath, 'r')
		fileData.seek(0)
		stringData = fileData.read()
		fileData.close()
		if stringValue not in stringData:
			if len(footer) > 0:
				stringData = stringData[:-len(footer)] + '\n' + stringValue + footer
			else:
				stringData += stringValue
			fileData = open(filePath, 'w')
			fileData.write(stringData)
		fileData.close()
	else:
		raise PluginError(filePath + " does not exist.")

def deleteIfFound(filePath, stringValue):
	if os.path.exists(filePath):
		fileData = open(filePath, 'r')
		fileData.seek(0)
		stringData = fileData.read()
		fileData.close()
		if stringValue in stringData:
			stringData = stringData.replace(stringValue, '')
			fileData = open(filePath, 'w')
			fileData.write(stringData)
		fileData.close()

def duplicateHierarchy(obj, ignoreAttr, includeEmpties, areaIndex):
	# Duplicate objects to apply scale / modifiers / linked data
	bpy.ops.object.select_all(action = 'DESELECT')
	selectMeshChildrenOnly(obj, None, includeEmpties, areaIndex)
	obj.select_set(True)
	bpy.context.view_layer.objects.active = obj
	bpy.ops.object.duplicate()
	try:
		tempObj = bpy.context.view_layer.objects.active
		allObjs = bpy.context.selected_objects
		bpy.ops.object.make_single_user(obdata = True)
		bpy.ops.object.transform_apply(location = False, 
			rotation = True, scale = True, properties =  False)
		for selectedObj in allObjs:
			bpy.ops.object.select_all(action = 'DESELECT')
			selectedObj.select_set(True)
			for modifier in selectedObj.modifiers:
				bpy.ops.object.modifier_apply(apply_as='DATA',
					modifier=modifier.name)
		for selectedObj in allObjs:
			if ignoreAttr is not None and getattr(selectedObj, ignoreAttr):
				for child in selectedObj.children:
					bpy.ops.object.select_all(action = 'DESELECT')
					child.select_set(True)
					bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
					selectedObj.parent.select_set(True)
					bpy.ops.object.parent_set(keep_transform = True)
				selectedObj.parent = None
		return tempObj, allObjs
	except Exception as e:
		cleanupDuplicatedObjects(allObjs)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		raise Exception(str(e))

def selectMeshChildrenOnly(obj, ignoreAttr, includeEmpties, areaIndex):
	checkArea = areaIndex is not None and obj.data is None
	if checkArea and obj.sm64_obj_type == 'Area Root' and obj.areaIndex != areaIndex:
		return
	ignoreObj = ignoreAttr is not None and getattr(obj, ignoreAttr)
	isMesh = isinstance(obj.data, bpy.types.Mesh)
	isEmpty = (obj.data is None) and includeEmpties and \
		(obj.sm64_obj_type == 'Level Root' or \
		obj.sm64_obj_type == 'Area Root' or \
		obj.sm64_obj_type == 'None')
	if (isMesh or isEmpty) and not ignoreObj:
		obj.select_set(True)
		obj.original_name = obj.name
	for child in obj.children:
		if checkArea and obj.sm64_obj_type == 'Level Root':
			if not (child.data is None and child.sm64_obj_type == 'Area Root'):
				continue
		selectMeshChildrenOnly(child, ignoreAttr, includeEmpties, areaIndex)

def cleanupDuplicatedObjects(selected_objects):
	meshData = []
	for selectedObj in selected_objects:
		if selectedObj.data is not None:
			meshData.append(selectedObj.data)
	for selectedObj in selected_objects:
		bpy.data.objects.remove(selectedObj)
	for mesh in meshData:
		bpy.data.meshes.remove(mesh)

def combineObjects(obj, includeChildren, ignoreAttr, areaIndex):
	obj.original_name = obj.name

	# Duplicate objects to apply scale / modifiers / linked data
	bpy.ops.object.select_all(action = 'DESELECT')
	if includeChildren:
		selectMeshChildrenOnly(obj, ignoreAttr, False, areaIndex)
	else:
		obj.select_set(True)
	if len(bpy.context.selected_objects) == 0:
		return None, []
	bpy.ops.object.duplicate()
	joinedObj = None
	try:
		# duplicate obj and apply modifiers / make single user
		allObjs = bpy.context.selected_objects
		bpy.ops.object.make_single_user(obdata = True)
		bpy.ops.object.transform_apply(location = False, 
			rotation = True, scale = True, properties =  False)
		for selectedObj in allObjs:
			bpy.ops.object.select_all(action = 'DESELECT')
			selectedObj.select_set(True)
			for modifier in selectedObj.modifiers:
				try:
					bpy.ops.object.modifier_apply(apply_as='DATA',
						modifier=modifier.name)
				except RuntimeError as error:
					print(str(error))
					
		bpy.ops.object.select_all(action = 'DESELECT')
		
		# Joining causes orphan data, so we remove it manually.
		meshList = []
		for selectedObj in allObjs:
			selectedObj.select_set(True)
			meshList.append(selectedObj.data)
		
		joinedObj = bpy.context.selected_objects[0]
		bpy.context.view_layer.objects.active = joinedObj
		joinedObj.select_set(True)
		meshList.remove(joinedObj.data)
		bpy.ops.object.join()
		setOrigin(obj, joinedObj)

		bpy.ops.object.select_all(action = 'DESELECT')
		bpy.context.view_layer.objects.active = joinedObj
		joinedObj.select_set(True)

		# Need to clear parent transform in order to correctly apply transform.
		bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
		bpy.ops.object.transform_apply(location = False, 
			rotation = True, scale = True, properties =  False)
		bpy.context.view_layer.objects.active = joinedObj
		joinedObj.select_set(True)
		bpy.ops.object.transform_apply(location = False, 
			rotation = True, scale = True, properties =  False)

	except Exception as e:
		cleanupDuplicatedObjects(allObjs)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		raise Exception(str(e))

	return joinedObj, meshList

def cleanupCombineObj(tempObj, meshList):
	for mesh in meshList:
		bpy.data.meshes.remove(mesh)
	cleanupDuplicatedObjects([tempObj])
	#obj.select_set(True)
	#bpy.context.view_layer.objects.active = obj

def writeInsertableFile(filepath, dataType, address_ptrs, startPtr, data):
	address = 0
	openfile = open(filepath, 'wb')

	# 0-4 - Data Type
	openfile.write(dataType.to_bytes(4, 'big'))
	address += 4

	# 4-8 - Data Size
	openfile.seek(address)
	openfile.write(len(data).to_bytes(4, 'big'))
	address += 4

	# 8-12 Start Address
	openfile.seek(address)
	openfile.write(startPtr.to_bytes(4, 'big'))
	address += 4

	# 12-16 - Number of pointer addresses
	openfile.seek(address)
	openfile.write(len(address_ptrs).to_bytes(4, 'big'))
	address += 4

	# 16-? - Pointer address list
	for i in range(len(address_ptrs)):
		openfile.seek(address)
		openfile.write(address_ptrs[i].to_bytes(4, 'big'))
		address += 4

	openfile.seek(address)
	openfile.write(data)	
	openfile.close()

def colorTo16bitRGBA(color):
	r = int(round(color[0] * 31))
	g = int(round(color[1] * 31))
	b = int(round(color[2] * 31))
	a = 1 if color[3] > 0.5 else 0

	return (r << 11) | (g << 6) | (b << 1) | a

def applyRotation(objList, angle, axis):
	bpy.ops.object.select_all(action = "DESELECT")
	for obj in objList:
		obj.select_set(True)
	bpy.context.view_layer.objects.active = objList[0]
	bpy.ops.transform.rotate(value = angle, orient_axis = axis)
	bpy.ops.object.transform_apply(location = False, 
		rotation = True, scale = True, properties =  False)

def getAddressFromRAMAddress(RAMAddress):
	addr = RAMAddress - 0x80000000
	if addr < 0:
		raise PluginError("Invalid RAM address.")
	return addr

def getObjectQuaternion(obj):
	if obj.rotation_mode == 'QUATERNION':
		rotation = mathutils.Quaternion(obj.rotation_quaternion)
	elif obj.rotation_mode == 'AXIS_ANGLE':
		rotation = mathutils.Quaternion(obj.rotation_axis_angle)
	else:
		rotation = mathutils.Euler(
			obj.rotation_euler, obj.rotation_mode).to_quaternion()
	return rotation

def tempName(name):
   letters = string.digits
   return name + '_temp' + "".join(random.choice(letters) for i in range(10))

def prop_split(layout, data, field, name):
	split = layout.split(factor = 0.5)
	split.label(text = name)
	split.prop(data, field, text = '')

def toAlnum(name):
	if name is None or name == '':
		return None
	for i in range(len(name)):
		if not name[i].isalnum():
			name = name[:i] + '_' + name[i+1:]
	if name[0].isdigit():
		name = '_' + name
	return name

def get64bitAlignedAddr(address):
	endNibble = hex(address)[-1]
	if endNibble != '0' and endNibble != '8':
		address = ceil(address / 8) * 8
	return address

def getNameFromPath(path, removeExtension = False):
	index = len(path) - 1
	extensionIndex = len(path)
	n = path[index]
	extensionFound = not removeExtension
	while n != '/' and n != '\\' and index > 0:
		index -= 1
		if not extensionFound:
			extensionIndex -= 1
		if n == '.':
			extensionFound = True

		n = path[index]
	if index == 0 and n != '/' and n != '\\':
		name = toAlnum(path[:extensionIndex])
	else:
		name = toAlnum(path[index + 1:extensionIndex])

	return name
	
def gammaCorrect(color):
	return [
		gammaCorrectValue(color[0]), 
		gammaCorrectValue(color[1]), 
		gammaCorrectValue(color[2])]

def gammaCorrectValue(u):
	if u < 0.0031308:
		y = u * 12.92
	else:
		y = 1.055 * pow(u, (1/2.4)) - 0.055
	
	return min(max(y, 0), 1)

def gammaInverse(color):
	return [
		gammaInverseValue(color[0]), 
		gammaInverseValue(color[1]), 
		gammaInverseValue(color[2])]

def gammaInverseValue(u):
	if u < 0.04045:
		y = u / 12.92
	else:
		y = ((u + 0.055) / 1.055) ** 2.4
	
	return min(max(y, 0), 1)

def printBlenderMessage(msgSet, message, blenderOp):
	if blenderOp is not None:
		blenderOp.report(msgSet, message)
	else:
		print(message)

def bytesToInt(value):
	return int.from_bytes(value, 'big')

def bytesToHex(value, byteSize = 4):
	return format(bytesToInt(value), '#0' + str(byteSize * 2 + 2) + 'x')

def bytesToHexClean(value, byteSize = 4):
	return format(bytesToInt(value), '0' + str(byteSize * 2) + 'x')

def intToHex(value, byteSize = 4):
	return format(value, '#0' + str(byteSize * 2 + 2) + 'x')

def intToBytes(value, byteSize):
	return bytes.fromhex(intToHex(value, byteSize)[2:])

# byte input
# returns an integer, usually used for file seeking positions
def decodeSegmentedAddr(address, segmentData):
	#print(bytesAsHex(address))
	if address[0] not in segmentData:
		raise PluginError("Segment " + str(address[0]) + ' not found in segment list.')
	segmentStart = segmentData[address[0]][0]
	return segmentStart + bytesToInt(address[1:4])

#int input
# returns bytes, usually used for writing new segmented addresses
def encodeSegmentedAddr(address, segmentData):
	segment = getSegment(address, segmentData)
	segmentStart = segmentData[segment][0]

	segmentedAddr = address - segmentStart
	return intToBytes(segment, 1) + intToBytes(segmentedAddr, 3)

def getSegment(address, segmentData):
	for segment, interval in segmentData.items():
		if address in range(*interval):
			return segment

	raise PluginError("Address " + hex(address) + \
		" is not found in any of the provided segments.")

# Position
def readVectorFromShorts(command, offset):
	return [readFloatFromShort(command, valueOffset) for valueOffset
		in range(offset, offset + 6, 2)]

def readFloatFromShort(command, offset):
	return int.from_bytes(command[offset: offset + 2], 
		'big', signed = True) / bpy.context.scene.blenderToSM64Scale

def writeVectorToShorts(command, offset, values):
	for i in range(3):
		valueOffset = offset + i * 2
		writeFloatToShort(command, valueOffset, values[i])

def writeFloatToShort(command, offset, value):
	command[offset : offset + 2] = \
		int(round(value * bpy.context.scene.blenderToSM64Scale)).to_bytes(
		2, 'big', signed = True)

def convertFloatToShort(value):
	return int(round((value * bpy.context.scene.blenderToSM64Scale)))

def convertEulerFloatToShort(value):
	return int(round(degrees(value)))

# Rotation

# Rotation is stored as a short.
# Zero rotation starts at Z+ on an XZ plane and goes counterclockwise.
# 2**16 - 1 is the last value before looping around again.
def readEulerVectorFromShorts(command, offset):
	return [readEulerFloatFromShort(command, valueOffset) for valueOffset
		in range(offset, offset + 6, 2)]

def readEulerFloatFromShort(command, offset):
	return radians(int.from_bytes(command[offset: offset + 2], 
		'big', signed = True))

def writeEulerVectorToShorts(command, offset, values):
	for i in range(3):
		valueOffset = offset + i * 2
		writeEulerFloatToShort(command, valueOffset, values[i])

def writeEulerFloatToShort(command, offset, value):
	command[offset : offset + 2] = int(round(degrees(value))).to_bytes(
		2, 'big', signed = True)

# convert 32 bit (8888) to 16 bit (5551) color
def convert32to16bitRGBA(oldPixel):
	if oldPixel[3] > 127:
		alpha = 1
	else:
		alpha = 0
	newPixel = 	(oldPixel[0] >> 3) << 11 |\
				(oldPixel[1] >> 3) << 6  |\
				(oldPixel[2] >> 3) << 1  |\
				alpha
	return newPixel.to_bytes(2, 'big')

# convert normalized RGB values to bytes (0-255)
def convertRGB(normalizedRGB):
	return bytearray([
		int(normalizedRGB[0] * 255),
		int(normalizedRGB[1] * 255),
		int(normalizedRGB[2] * 255)
		])
# convert normalized RGB values to bytes (0-255)
def convertRGBA(normalizedRGBA):
	return bytearray([
		int(normalizedRGBA[0] * 255),
		int(normalizedRGBA[1] * 255),
		int(normalizedRGBA[2] * 255),
		int(normalizedRGBA[3] * 255)
		])

def vector3ComponentMultiply(a, b):
	return mathutils.Vector(
		(a.x * b.x, a.y * b.y, a.z * b.z)
	)

# Position values are signed shorts.
def convertPosition(position):
	positionShorts = [int(floatValue) for floatValue in position]
	F3DPosition = bytearray(0)
	for shortData in [shortValue.to_bytes(2, 'big', signed=True) for shortValue in positionShorts]:
		F3DPosition.extend(shortData)
	return F3DPosition

# UVs in F3D are a fixed point short: s10.5 (hence the 2**5)
# fixed point is NOT exponent+mantissa, it is integer+fraction
def convertUV(normalizedUVs, textureWidth, textureHeight):
	#print(str(normalizedUVs[0]) + " - " + str(normalizedUVs[1]))
	F3DUVs = convertFloatToFixed16Bytes(normalizedUVs[0] * textureWidth) +\
			 convertFloatToFixed16Bytes(normalizedUVs[1] * textureHeight)
	return F3DUVs

def convertFloatToFixed16Bytes(value):
	value *= 2**5
	value = min(max(value, -2**15), 2**15 - 1)
	
	return int(round(value)).to_bytes(2, 'big', signed = True)

def convertFloatToFixed16(value):
	value *= 2**5
	value = min(max(value, -2**15), 2**15 - 1)
	return int.from_bytes(
		int(round(value)).to_bytes(2, 'big', signed = True), 'big')


# Normal values are signed bytes (-128 to 127)
# Normalized magnitude = 127
def convertNormal(normal):
	F3DNormal = bytearray(0)
	for axis in normal:
		F3DNormal.extend(int(axis * 127).to_bytes(1, 'big', signed=True))
	return F3DNormal

def byteMask(data, offset, amount):
	return bitMask(data, offset * 8, amount * 8)
def bitMask(data, offset, amount):
	return (~(-1 << amount) << offset & data) >> offset

def read16bitRGBA(data):
	r = bitMask(data, 11, 5) / ((2**5) - 1)
	g = bitMask(data,  6, 5) / ((2**5) - 1)
	b = bitMask(data,  1, 5) / ((2**5) - 1)
	a = bitMask(data,  0, 1) / ((2**1) - 1)

	return [r,g,b,a]