import bmesh
import bpy
import mathutils
import pprint
from .f3d_gbi import *
from .utility import *
from .sm64_constants import *
from .f3d_material import createF3DMat, update_preset_manual

def getAxisVector(enumValue):
	sign = -1 if enumValue[0] == '-' else 1
	axis = enumValue[0] if sign == 1 else enumValue[1]
	return (
		sign if axis == 'X' else 0,
		sign if axis == 'Y' else 0,
		sign if axis == 'Z' else 0
	)

def getExportRotation(forwardAxisEnum, convertTransformMatrix):
	if 'Z' in forwardAxisEnum:
		print("Z axis reserved for verticals.")
		return None
	elif forwardAxisEnum == 'X':
		rightAxisEnum = '-Y'
	elif forwardAxisEnum == '-Y':
		rightAxisEnum = '-X'
	elif forwardAxisEnum == '-X':
		rightAxisEnum = 'Y'
	else:
		rightAxisEnum = 'X'

	forwardAxis = getAxisVector(forwardAxisEnum)
	rightAxis = getAxisVector(rightAxisEnum)

	upAxis = (0, 0, 1)

	# Z assumed to be up
	columns = [rightAxis, forwardAxis, upAxis]
	localToBlenderRotation = mathutils.Matrix([
		[col[0] for col in columns],
		[col[1] for col in columns],
		[col[2] for col in columns]
	]).to_quaternion()

	return convertTransformMatrix.to_quaternion() @ localToBlenderRotation

def F3DtoBlenderObject(romfile, startAddress, scene,
	newname, transformMatrix, 
	segmentData, shadeSmooth):
	
	mesh = bpy.data.meshes.new(newname + '-mesh')
	obj = bpy.data.objects.new(newname, mesh)
	scene.collection.objects.link(obj)
	createBlankMaterial(obj)

	bMesh = bmesh.new()
	bMesh.from_mesh(mesh)
	
	parseF3D(romfile, startAddress, scene, bMesh, obj, \
		transformMatrix, newname, segmentData, \
		[None] * 16 * 16)

	#bmesh.ops.rotate(bMesh, cent = [0,0,0], 
	#	matrix = blenderToSM64Rotation,
	#	verts = bMesh.verts)
	bMesh.to_mesh(mesh)
	bMesh.free()
	mesh.update()

	if shadeSmooth:
		bpy.ops.object.select_all(action = 'DESELECT')
		obj.select_set(True)
		bpy.ops.object.shade_smooth()

	return obj

def getOrMakeVertexGroup(obj, groupName):
	for group in obj.vertex_groups:
		if group.name == groupName:
			return group
	return obj.vertex_groups.new(name = groupName)

def cmdToPositiveInt(cmd):
	return cmd if cmd >= 0 else 256 + cmd

def parseF3D(romfile, startAddress, scene,
	bMesh, obj, transformMatrix, groupName,  segmentData, vertexBuffer):
	f3d = F3D('F3D', False)
	currentAddress = startAddress
	romfile.seek(currentAddress)
	command = romfile.read(8)
	
	faceSeq = bMesh.faces
	vertSeq = bMesh.verts
	uv_layer = bMesh.loops.layers.uv.verify()
	deform_layer = bMesh.verts.layers.deform.verify()
	vertexGroup = getOrMakeVertexGroup(obj, groupName)
	groupIndex = vertexGroup.index

	textureSize = [32, 32]

	currentTextureAddr = -1
	jumps = [startAddress]

	# Used for remove_double op at end
	vertList = []

	while len(jumps) > 0:
		# FD, FC, B7 (tex, shader, geomode)
		#print(format(command[0], '#04x') + ' at ' + hex(currentAddress))
		if command[0] == cmdToPositiveInt(f3d.G_TRI1):
			try:
				newVerts = interpretDrawTriangle(command, vertexBuffer,
					faceSeq, vertSeq, uv_layer, deform_layer, groupIndex)
				vertList.extend(newVerts)
			except TypeError:
				print("Ignoring triangle from unloaded vertices.")

		elif command[0] == cmdToPositiveInt(f3d.G_VTX):
			interpretLoadVertices(romfile, vertexBuffer, transformMatrix, 
				command, segmentData)

		elif command[0] == cmdToPositiveInt(f3d.G_SETTILESIZE):
			textureSize = interpretSetTileSize(
				int.from_bytes(command[4:8], 'big'))

		elif command[0] == cmdToPositiveInt(f3d.G_DL):
			if command[1] == 0:
				jumps.append(currentAddress)
			currentAddress = decodeSegmentedAddr(command[4:8], 
				segmentData = segmentData)
			romfile.seek(currentAddress)
			command = romfile.read(8)
			continue

		elif command[0] == cmdToPositiveInt(f3d.G_ENDDL):
			currentAddress = jumps.pop()

		elif command[0] == cmdToPositiveInt(f3d.G_SETGEOMETRYMODE):
			pass
		elif command[0] == cmdToPositiveInt(f3d.G_SETCOMBINE):
			pass

		elif command[0] == cmdToPositiveInt(f3d.G_SETTIMG):
			currentTextureAddr =\
				interpretSetTImage(command, segmentData)

		elif command[0] == cmdToPositiveInt(f3d.G_LOADBLOCK):
			# for now only 16bit RGBA is supported.
			interpretLoadBlock(command, romfile, currentTextureAddr, textureSize,
				'RGBA', 16)

		elif command[0] == cmdToPositiveInt(f3d.G_SETTILE):
			interpretSetTile(int.from_bytes(command[4:8], 'big'), None)

		else:
			pass
			#print(format(command[0], '#04x') + ' at ' + hex(currentAddress))

		currentAddress += 8
		romfile.seek(currentAddress)
		command = romfile.read(8)
	
	bmesh.ops.remove_doubles(bMesh, verts = vertList, dist = 0.0001)
	return vertexBuffer

def getPosition(vertexBuffer, index):
	xStart = index * 16 + 0
	yStart = index * 16 + 2
	zStart = index * 16 + 4

	xBytes = vertexBuffer[xStart : xStart + 2]
	yBytes = vertexBuffer[yStart : yStart + 2]
	zBytes = vertexBuffer[zStart : zStart + 2]

	x = int.from_bytes(xBytes, 'big', signed=True) / bpy.context.scene.blenderToSM64Scale
	y = int.from_bytes(yBytes, 'big', signed=True) / bpy.context.scene.blenderToSM64Scale
	z = int.from_bytes(zBytes, 'big', signed=True) / bpy.context.scene.blenderToSM64Scale

	return (x, y, z)

def getNormalorColor(vertexBuffer, index, isNormal = True):
	xByte = bytes([vertexBuffer[index * 16 + 12]])
	yByte = bytes([vertexBuffer[index * 16 + 13]])
	zByte = bytes([vertexBuffer[index * 16 + 14]])
	wByte = bytes([vertexBuffer[index * 16 + 15]])

	if isNormal:
		x = int.from_bytes(xByte, 'big', signed=True)
		y = int.from_bytes(yByte, 'big', signed=True)
		z = int.from_bytes(zByte, 'big', signed=True)
		return (x,y,z)

	else: # vertex color
		r = int.from_bytes(xByte, 'big') / 255
		g = int.from_bytes(yByte, 'big') / 255
		b = int.from_bytes(zByte, 'big') / 255
		a = int.from_bytes(wByte, 'big') / 255
		return (r,g,b,a)

def getUV(vertexBuffer, index, textureDimensions = [32,32]):
	uStart = index * 16 + 8
	vStart = index * 16 + 10

	uBytes = vertexBuffer[uStart : uStart + 2]
	vBytes = vertexBuffer[vStart : vStart + 2]

	u = int.from_bytes(uBytes, 'big', signed = True) / 32
	v = int.from_bytes(vBytes, 'big', signed = True) / 32

	# We don't know texture size, so assume 32x32.
	u /= textureDimensions[0]
	v /= textureDimensions[1]
	v = 1 - v

	return (u,v)

def interpretSetTile(data, texture):
	clampMirrorFlags = bitMask(data, 18, 2)

def interpretSetTileSize(data):
	hVal = bitMask(data, 0, 12)
	wVal = bitMask(data, 12, 12)

	height = hVal >> 2 + 1
	width = wVal >> 2 + 1

	return (width, height)

def interpretLoadVertices(romfile, vertexBuffer, transformMatrix, command,
	segmentData = None):
	command = int.from_bytes(command, 'big', signed=True)

	numVerts = bitMask(command, 52, 4) + 1
	startIndex = bitMask(command, 48, 4)
	dataLength = bitMask(command, 32, 16)
	segmentedAddr = bitMask(command, 0, 32)

	dataStartAddr = decodeSegmentedAddr(segmentedAddr.to_bytes(4, 'big'), 
		segmentData = segmentData)

	romfile.seek(dataStartAddr)
	data = romfile.read(dataLength)

	for i in range(numVerts):
		vert = mathutils.Vector(readVectorFromShorts(data, i * 16))
		vert = transformMatrix @ vert
		transformedVert = bytearray(6)
		writeVectorToShorts(transformedVert, 0, vert)
		
		start = (startIndex + i) * 16
		vertexBuffer[start: start + 6] = transformedVert
		vertexBuffer[start + 6: start + 16] = data[i * 16 + 6: i * 16 + 16]


# Note the divided by 0x0A, which is due to the way BF command stores indices.
# Without this the triangles are drawn incorrectly.
def interpretDrawTriangle(command, vertexBuffer,
	faceSeq, vertSeq, uv_layer, deform_layer, groupIndex):

	verts = [None, None, None]

	index0 = int(command[5] / 0x0A)
	index1 = int(command[6] / 0x0A)
	index2 = int(command[7] / 0x0A)

	vert0 = mathutils.Vector(getPosition(vertexBuffer, index0))
	vert1 = mathutils.Vector(getPosition(vertexBuffer, index1))
	vert2 = mathutils.Vector(getPosition(vertexBuffer, index2))

	verts[0] = vertSeq.new(vert0)
	verts[1] = vertSeq.new(vert1)
	verts[2] = vertSeq.new(vert2)

	tri = faceSeq.new(verts)

	# Assign vertex group
	for vert in tri.verts:
		vert[deform_layer][groupIndex] = 1

	loopIndex = 0
	for loop in tri.loops:
		loop[uv_layer].uv = mathutils.Vector(
			getUV(vertexBuffer, int(command[5 + loopIndex] / 0x0A)))
		loopIndex += 1
	
	return verts

def interpretSetTImage(command, levelData):
	segmentedAddr = command[4:8]
	return decodeSegmentedAddr(segmentedAddr, levelData)

def interpretLoadBlock(command, romfile, textureStart, textureSize, colorFormat, colorDepth):
	numTexels = ((int.from_bytes(command[6:8], 'big')) >> 12) + 1

	# This is currently broken.
	#createNewTextureMaterial(romfile, textureStart, textureSize, numTexels, colorFormat, colorDepth, obj)

def printvbuf(vertexBuffer):
	for i in range(0, int(len(vertexBuffer) / 16)):
		print(getPosition(vertexBuffer, i))
		print(getNormalorColor(vertexBuffer, i))
		print(getUV(vertexBuffer, i))


def createBlankMaterial(obj):
	material = createF3DMat(obj)
	material.f3d_preset = 'Shaded Solid'
	update_preset_manual(material, bpy.context)

	#newMat = bpy.data.materials.new('sm64_material')
	#obj.data.materials.append(newMat)

def createNewTextureMaterial(romfile, textureStart, textureSize, texelCount, colorFormat, colorDepth, obj):
	newMat = bpy.data.materials.new('sm64_material')
	newTex = bpy.data.textures.new('sm64_texture', 'IMAGE')
	newImg = bpy.data.images.new('sm64_image', *textureSize, True, True)
	
	newTex.image = newImg
	newSlot = newMat.texture_slots.add()
	newSlot.texture = newTex
	
	obj.data.materials.append(newMat)
	
	romfile.seek(textureStart)
	texelSize = int(colorDepth / 8)
	dataLength = texelCount * texelSize
	textureData = romfile.read(dataLength)

	if colorDepth != 16:
		print("Warning: Only 16bit RGBA supported, input was " + \
			str(colorDepth) + 'bit ' + colorFormat)
	else:
		print(str(texelSize) + " " + str(colorDepth))
		for n in range(0, dataLength, texelSize):
			oldPixel = textureData[n : n + texelSize]
			newImg.pixels[n : n+4] = read16bitRGBA(
				int.from_bytes(oldPixel, 'big'))