import bpy, bmesh, mathutils, os, re, copy
from math import pi, ceil
from io import BytesIO

from .f3d_constants import *
from .f3d_material import all_combiner_uses, getMaterialScrollDimensions, getTmemWordUsage, bitSizeDict, texBitSizeOf, texFormatOf
from .f3d_gbi import *
from .f3d_gbi import _DPLoadTextureBlock

from ..utility import *

def getEdgeToFaceDict(mesh):
	edgeDict = {}
	for face in mesh.loop_triangles:
		for edgeKey in face.edge_keys:
			if edgeKey not in edgeDict:
				edgeDict[edgeKey] = []
			if face not in edgeDict[edgeKey]:
				edgeDict[edgeKey].append(face)
	return edgeDict

def getVertToFaceDict(mesh):
	vertDict = {}
	for face in mesh.loop_triangles:
		for vertIndex in face.vertices:
			if vertIndex not in vertDict:
				vertDict[vertIndex] = []
			if face not in vertDict[vertIndex]:
				vertDict[vertIndex].append(face)
	return vertDict

def getLoopFromVert(inputIndex, face):
	for i in range(len(face.vertices)):
		if face.vertices[i] == inputIndex:
			return face.loops[i]

def getInfoDict(obj):
	fixLargeUVs(obj)
	obj.data.calc_loop_triangles()
	obj.data.calc_normals_split()
	if len(obj.data.materials) == 0:
		raise PluginError("Mesh does not have any Fast3D materials.")
	infoDict = {
		'vert' : {}, # all faces connected to a vert
		'edge' : {}, # all faces connected to an edge
		'f3dVert' : {}, # f3d vertex of a given loop
		'edgeValid' : {}, # bool given two faces
		'validNeighbors' : {}, # all neighbors of a face with a valid connecting edge
		'texDimensions' : {}, # texture dimensions for each material
	}
	vertDict = infoDict['vert']
	edgeDict = infoDict['edge']
	f3dVertDict = infoDict['f3dVert']
	edgeValidDict = infoDict['edgeValid']
	validNeighborDict = infoDict['validNeighbors']

	mesh = obj.data
	if len(obj.data.uv_layers) == 0:
		uv_data = obj.data.uv_layers.new().data
	else:
		uv_data = None
		for uv_layer in obj.data.uv_layers:
			if uv_layer.name == 'UVMap':
				uv_data = uv_layer.data
		if uv_data is None:
			raise PluginError("Object \'" + obj.name + "\' does not have a UV layer named \'UVMap.\'")
	for face in mesh.loop_triangles:
		validNeighborDict[face] = []
		material = mesh.materials[face.material_index] 
		if material is None:
			raise PluginError("There are some faces on your mesh that are assigned to an empty material slot.")
		for vertIndex in face.vertices:
			if vertIndex not in vertDict:
				vertDict[vertIndex] = []
			if face not in vertDict[vertIndex]:
				vertDict[vertIndex].append(face)
		for edgeKey in face.edge_keys:
			if edgeKey not in edgeDict:
				edgeDict[edgeKey] = []
			if face not in edgeDict[edgeKey]:
				edgeDict[edgeKey].append(face)

		for loopIndex in face.loops:
			convertInfo = LoopConvertInfo(uv_data, obj, 
				isLightingDisabled(mesh.materials[face.material_index]))
			f3dVertDict[loopIndex] = getF3DVert(mesh.loops[loopIndex], face, convertInfo, mesh)
	for face in mesh.loop_triangles:	
		for edgeKey in face.edge_keys:
			for otherFace in edgeDict[edgeKey]:
				if otherFace == face:
					continue
				if (otherFace, face) not in edgeValidDict and \
					(face, otherFace) not in edgeValidDict:
					edgeValid = \
						f3dVertDict[getLoopFromVert(edgeKey[0], face)] == \
						f3dVertDict[getLoopFromVert(edgeKey[0], otherFace)] and \
						f3dVertDict[getLoopFromVert(edgeKey[1], face)] == \
						f3dVertDict[getLoopFromVert(edgeKey[1], otherFace)]
					edgeValidDict[(otherFace, face)] = edgeValid
					if edgeValid:
						validNeighborDict[face].append(otherFace)
						validNeighborDict[otherFace].append(face)
	return infoDict

def fixLargeUVs(obj):
	mesh = obj.data
	if len(obj.data.uv_layers) == 0:
		uv_data = obj.data.uv_layers.new().data
	else:
		uv_data = None
		for uv_layer in obj.data.uv_layers:
			if uv_layer.name == 'UVMap':
				uv_data = uv_layer.data
		if uv_data is None:
			raise PluginError("Object \'" + obj.name + "\' does not have a UV layer named \'UVMap.\'")

	texSizeDict = {}
	for material in obj.data.materials:
		texSizeDict[material] = getTexDimensions(material)

	for polygon in mesh.polygons:
		material = mesh.materials[polygon.material_index] 
		if material is None:
			raise PluginError("There are some faces on your mesh that are assigned to an empty material slot.")

		size = texSizeDict[material]
		cellSize = [1024 / size[0], 1024 / size[1]]
		if not isTexturePointSampled(material):
			cellOffset = [-0.5/size[0], 0.5 / size[1]] # half pixel offset for bilinear filtering
		else:
			cellOffset = [0,0]
		minUV, maxUV = findUVBounds(polygon, uv_data)
		uvOffset = [0,0]

		for i in range(2):

			# Move any UVs close to or straddling edge
			minDiff = -(cellSize[i]-2) - (minUV[i] + cellOffset[i])
			if minDiff >= 0:
				applyOffset(minUV, maxUV, uvOffset, ceil(minDiff), i)
			
			maxDiff = (maxUV[i] + cellOffset[i]) - (cellSize[i] - 2)
			if maxDiff >= 0:
				applyOffset(minUV, maxUV, uvOffset, -ceil(maxDiff), i)

		for loopIndex in polygon.loop_indices:
			newUV = (uv_data[loopIndex].uv[0] + uvOffset[0],
				uv_data[loopIndex].uv[1] + uvOffset[1]) 
			uv_data[loopIndex].uv = newUV
				
			#if newUV[0] > cellSize[0] or \
			#	newUV[1] > cellSize[1] or \
			#	newUV[0] < -cellSize[0] or \
			#	newUV[1] < -cellSize[1]:
			#	print("TOO BIG: " + str(newUV))

def applyOffset(minUV, maxUV, uvOffset, offset, i):
	minUV[i] += offset
	maxUV[i] += offset
	uvOffset[i] += offset

def findUVBounds(polygon, uv_data):
	minUV = [None, None]
	maxUV = [None, None]
	for loopIndex in polygon.loop_indices:
		uv = uv_data[loopIndex].uv
		for i in range(2):
			minUV[i] = uv[i] if minUV[i] is None else min(minUV[i], uv[i])
			maxUV[i] = uv[i] if maxUV[i] is None else max(maxUV[i], uv[i])
	return minUV, maxUV

# Make sure to set original_name before calling this
# used when duplicating an object
def saveStaticModel(fModel, obj, transformMatrix, ownerName, DLFormat, convertTextureData, revertMatAtEnd):
	if len(obj.data.polygons) == 0:
		return None
	
	#checkForF3DMaterial(obj)
	infoDict = getInfoDict(obj)

	fMeshGroup = FMeshGroup(toAlnum(ownerName + "_" + obj.original_name), 
		FMesh(toAlnum(ownerName + "_" + obj.original_name) + '_mesh', DLFormat), None, DLFormat)
	fModel.meshGroups[ownerName + "_" + obj.original_name] = fMeshGroup

	if obj.use_f3d_culling and (fModel.f3d.F3DEX_GBI or fModel.f3d.F3DEX_GBI_2):
		addCullCommand(obj, fMeshGroup.mesh, transformMatrix)

	facesByMat = {}
	for face in obj.data.loop_triangles:
		if face.material_index not in facesByMat:
			facesByMat[face.material_index] = []
		facesByMat[face.material_index].append(face)

	for material_index, faces in facesByMat.items():
		material = obj.data.materials[material_index]
		checkForF3dMaterialInFaces(obj, material)
		saveMeshByFaces(material, faces, 
			fModel, fMeshGroup.mesh, obj, transformMatrix, 
			infoDict, fModel.getDrawLayer(obj), convertTextureData)
	
	if revertMatAtEnd:
		revertMatAndEndDraw(fMeshGroup.mesh.draw, [])
	fMeshGroup.mesh.draw.commands.append(SPEndDisplayList())
	return fMeshGroup

def addCullCommand(obj, fMesh, transformMatrix):
	fMesh.add_cull_vtx()
	for vertexPos in obj.bound_box:
		# Most other fields of convertVertexData are unnecessary for bounding box verts
		fMesh.cullVertexList.vertices.append(
			convertVertexData(obj.data, 
				mathutils.Vector(vertexPos), [0,0], 
				mathutils.Vector([0,0,0,0]), [32, 32],
				transformMatrix, False, False))


	defaults = bpy.context.scene.world.rdp_defaults
	if defaults.g_lighting:
		cullCommands = [
			SPClearGeometryMode(['G_LIGHTING']),
			SPVertex(fMesh.cullVertexList, 0, 8, 0),
			SPSetGeometryMode(['G_LIGHTING']),
			SPCullDisplayList(0, 7)
		]
	else:
		cullCommands = [
			SPVertex(fMesh.cullVertexList, 0, 8, 0),
			SPCullDisplayList(0, 7)
		]
	fMesh.draw.commands = cullCommands + fMesh.draw.commands

def exportF3DCommon(obj, fModel, transformMatrix, includeChildren, name, DLFormat, convertTextureData):
	tempObj, meshList = combineObjects(obj, includeChildren, None, None)
	try:
		fMeshGroup = saveStaticModel(fModel, tempObj, transformMatrix, name, DLFormat, convertTextureData, True)
		cleanupCombineObj(tempObj, meshList)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
	except Exception as e:
		cleanupCombineObj(tempObj, meshList)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		raise Exception(str(e))

	return fMeshGroup


def checkForF3dMaterialInFaces(obj, material):
	if not material.is_f3d:
		raise PluginError("Material '" + material.name + "' on object '" + obj.name +\
			"' is not a Fast3D material. Replace it with a Fast3D material.")

def checkForF3DMaterial(obj):
	if len(obj.material_slots) == 0:
		raise PluginError(obj.name + " has no Fast3D material. Make sure to add a Fast3D material to it.")
	for materialSlot in obj.material_slots:
		if materialSlot.material is None or \
			not materialSlot.material.is_f3d:
			raise PluginError(obj.name + " has either empty material slots " +\
				'or non-Fast3D materials. Remove any regular blender materials / empty slots.')

def revertMatAndEndDraw(gfxList, otherCommands):
	gfxList.commands.extend([
		DPPipeSync(),
		SPSetGeometryMode(['G_LIGHTING']),
		SPClearGeometryMode(['G_TEXTURE_GEN']),
		DPSetCombineMode(*S_SHADED_SOLID),
		SPTexture(0xFFFF, 0xFFFF, 0, 0, 0)] +\
		otherCommands)

	if gfxList.DLFormat != DLFormat.Dynamic:
		gfxList.commands.append(SPEndDisplayList())

def getCommonEdge(face1, face2, mesh):
	for edgeKey1 in face1.edge_keys:
		for edgeKey2 in face2.edge_keys:
			if edgeKey1 == edgeKey2:
				return edgeKey1
	raise PluginError("No common edge between faces " + str(face1.index) + \
		' and ' + str(face2.index))

def edgeValid(edgeValidDict, face, otherFace):
	if (face, otherFace) in edgeValidDict:
		return edgeValidDict[(face, otherFace)]
	else:
		return edgeValidDict[(otherFace, face)]

def getLowestUnvisitedNeighborCountFace(unvisitedFaces, infoDict):
	lowestNeighborFace = unvisitedFaces[0]
	lowestNeighborCount = len(infoDict['validNeighbors'][lowestNeighborFace])
	for face in unvisitedFaces:
		neighborCount = len(infoDict['validNeighbors'][face])
		if neighborCount < lowestNeighborCount:
			lowestNeighborFace = face
			lowestNeighborCount = neighborCount
	return lowestNeighborFace

def getNextNeighborFace(faces, face, lastEdgeKey, visitedFaces, possibleFaces,
	infoDict):
	
	if lastEdgeKey is not None:
		handledEdgeKeys = [lastEdgeKey]
		nextEdgeKey = face.edge_keys[
			(face.edge_keys.index(lastEdgeKey) + 1) % 3]
	else:
		handledEdgeKeys = []
		nextEdgeKey = face.edge_keys[0]

	nextFaceAndEdge = (None, None)
	while nextEdgeKey not in handledEdgeKeys:
		for linkedFace in infoDict['edge'][nextEdgeKey]:
			if linkedFace == face or linkedFace not in faces:
				continue
			elif edgeValid(infoDict['edgeValid'], linkedFace, face) and \
				linkedFace not in visitedFaces:
				if nextFaceAndEdge[0] is None:
					#print(nextLoop.face)
					nextFaceAndEdge = (linkedFace, nextEdgeKey)
				else:
					# Move face to front of queue
					if linkedFace in possibleFaces:
						possibleFaces.remove(linkedFace)
					possibleFaces.insert(0, linkedFace)
		handledEdgeKeys.append(nextEdgeKey)
		nextEdgeKey = face.edge_keys[
			(face.edge_keys.index(nextEdgeKey) + 1) % 3]
	return nextFaceAndEdge

def saveTriangleStrip(faces, convertInfo, triList, vtxList, f3d, 
	texDimensions, transformMatrix, isPointSampled, exportVertexColors,
	existingVertexData, existingVertexMaterialRegions, infoDict, mesh):
	visitedFaces = []
	unvisitedFaces = copy.copy(faces)
	possibleFaces = []
	lastEdgeKey = None
	neighborFace = getLowestUnvisitedNeighborCountFace(unvisitedFaces, infoDict)

	triConverter = TriangleConverter(mesh, convertInfo, triList, vtxList, f3d, 
		texDimensions, transformMatrix, isPointSampled, exportVertexColors,
		existingVertexData, existingVertexMaterialRegions)

	while len(visitedFaces) < len(faces):
		#print(str(len(visitedFaces)) + " " + str(len(bFaces)))
		if neighborFace is None:
			if len(possibleFaces) > 0:
				#print("get neighbor from queue")
				neighborFace = possibleFaces[0]
				lastEdgeKey = None
				possibleFaces = []
			else:
				#print('get new neighbor')
				neighborFace =  getLowestUnvisitedNeighborCountFace(
					unvisitedFaces, infoDict)
				lastEdgeKey = None
		
		triConverter.addFace(neighborFace)
		if neighborFace in visitedFaces:
			raise PluginError("Repeated face")
		visitedFaces.append(neighborFace)
		unvisitedFaces.remove(neighborFace)
		if neighborFace in possibleFaces:
			possibleFaces.remove(neighborFace)
		for otherFace in infoDict['validNeighbors'][neighborFace]:
			infoDict['validNeighbors'][otherFace].remove(neighborFace)

		neighborFace, lastEdgeKey = getNextNeighborFace(faces, 
			neighborFace, lastEdgeKey, visitedFaces, possibleFaces, infoDict)
	
	triConverter.finish()

# Necessary for UV half pixel offset (see 13.7.5.3)
def isTexturePointSampled(material):
	return material.rdp_settings.g_mdsft_text_filt == 'G_TF_POINT'

def isLightingDisabled(material):
	return not material.rdp_settings.g_lighting

# Necessary as G_SHADE_SMOOTH actually does nothing
def checkIfFlatShaded(material):
	return not material.rdp_settings.g_shade_smooth

def saveMeshByFaces(material, faces, fModel, fMesh, obj, transformMatrix,
	infoDict, drawLayer, convertTextureData):
	if len(faces) == 0:
		print('0 Faces Provided.')
		return
	fMaterial, texDimensions = \
		saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)
	isPointSampled = isTexturePointSampled(material)
	exportVertexColors = isLightingDisabled(material)
	uv_data = obj.data.uv_layers['UVMap'].data
	convertInfo = LoopConvertInfo(uv_data, obj, exportVertexColors)

	fMesh.draw.commands.append(SPDisplayList(fMaterial.material))
	triGroup = fMesh.tri_group_new(fMaterial)
	fMesh.draw.commands.append(SPDisplayList(triGroup.triList))

	#saveGeometry(obj, triList, fMesh.vertexList, bFaces, 
	#	bMesh, texDimensions, transformMatrix, isPointSampled, isFlatShaded,
	#	exportVertexColors, fModel.f3d)
	saveTriangleStrip(faces, convertInfo, triGroup.triList, triGroup.vertexList,
		fModel.f3d, texDimensions, transformMatrix, isPointSampled,
		exportVertexColors, None, None, infoDict, obj.data)
	
	if fMaterial.revert is not None:
		fMesh.draw.commands.append(SPDisplayList(fMaterial.revert))

def get8bitRoundedNormal(loop, mesh):
	alpha_layer = mesh.vertex_colors['Alpha'].data if 'Alpha' in \
		mesh.vertex_colors else None
	
	if alpha_layer is not None:
		normalizedAColor = alpha_layer[loop.index].color
		normalizedA = mathutils.Color(normalizedAColor[0:3]).v
	else:
		normalizedA = 1
	
	# Don't round, as this may move UV toward UV bounds.
	return mathutils.Vector(
		(int(loop.normal[0] * 128) / 128,
		int(loop.normal[1] * 128) / 128,
		int(loop.normal[2] * 128) / 128,
		normalizedA)
	)

class LoopConvertInfo:
	def __init__(self, uv_data, obj, exportVertexColors):
		self.uv_data = uv_data
		self.obj = obj
		self.exportVertexColors = exportVertexColors

def getNewIndices(existingIndices, bufferStart):
	n = bufferStart
	newIndices = []
	for index in existingIndices:
		if index is None:
			newIndices.append(n)
			n += 1
		else:
			newIndices.append(index)
	return newIndices

class TriangleConverter:
	def __init__(self, mesh, convertInfo, triList, vtxList, f3d, 
		texDimensions, transformMatrix, isPointSampled, exportVertexColors,
		existingVertexData, existingVertexMaterialRegions):
		self.convertInfo = convertInfo
		self.mesh = mesh

		# Existing data assumed to be already loaded in.
		if existingVertexData is not None:
			# [(position, uv, colorOrNormal)]
			self.vertBuffer = existingVertexData 
		else:
			self.vertBuffer = []
		self.existingVertexMaterialRegions = existingVertexMaterialRegions
		self.bufferStart = len(self.vertBuffer)
		self.vertexBufferTriangles = [] # [(index0, index1, index2)]
		self.f3d = f3d
		self.triList = triList
		self.vtxList = vtxList

		self.texDimensions = texDimensions
		self.transformMatrix = transformMatrix
		self.isPointSampled = isPointSampled
		self.exportVertexColors = exportVertexColors

	def vertInBuffer(self, f3dVert, material_index):
		if self.existingVertexMaterialRegions is None:
			if f3dVert in self.vertBuffer:
				return self.vertBuffer.index(f3dVert)
			else:
				return None
		else:
			if material_index in self.existingVertexMaterialRegions:
				matRegion = self.existingVertexMaterialRegions[material_index]
				for i in range(matRegion[0], matRegion[1]):
					if self.vertBuffer[i] == f3dVert:
						return i
			for i in range(self.bufferStart, len(self.vertBuffer)): 
				if self.vertBuffer[i] == f3dVert:
					return i
			return None

	def addFace(self, face):
		triIndices = []
		existingVertIndices = []
		addedVerts = [] # verts added to existing vertexBuffer
		allVerts = [] # all verts not in 'untouched' buffer region

		for loopIndex in face.loops:
			loop = self.mesh.loops[loopIndex]
			f3dVert = getF3DVert(loop, face, self.convertInfo, self.mesh)
			vertIndex = self.vertInBuffer(f3dVert, face.material_index)
			if vertIndex is not None:
				triIndices.append(vertIndex)			
			else:
				addedVerts.append(f3dVert)
				triIndices.append(len(self.vertBuffer) + len(addedVerts) - 1)

			if f3dVert in self.vertBuffer[:self.bufferStart]:
				existingVertIndices.append(self.vertBuffer.index(f3dVert))
			else:
				allVerts.append(f3dVert)
				existingVertIndices.append(None)
		
		# We care only about load size, since loading is what takes up time.
		# Even if vert_buffer is larger, its still another load to fill it.
		if len(self.vertBuffer) + len(addedVerts) > self.f3d.vert_load_size:
			self.triList.commands.append(
				SPVertex(self.vtxList, len(self.vtxList.vertices), 
				len(self.vertBuffer) - self.bufferStart, self.bufferStart))
			self.triList.commands.extend(createTriangleCommands(
				self.vertexBufferTriangles, self.f3d.F3DEX_GBI))
			for vertData in self.vertBuffer[self.bufferStart:]:
				self.vtxList.vertices.append(convertVertexData(self.convertInfo.obj.data, 
					vertData[0], vertData[1], vertData[2], self.texDimensions,
					self.transformMatrix, self.isPointSampled,
					self.exportVertexColors))
			self.vertBuffer = self.vertBuffer[:self.bufferStart] + allVerts
			self.vertexBufferTriangles = \
				[getNewIndices(existingVertIndices, self.bufferStart)]
		else:
			self.vertBuffer.extend(addedVerts)
			self.vertexBufferTriangles.append(triIndices)
	
	def finish(self):
		if len(self.vertexBufferTriangles) > 0:
			self.triList.commands.append(SPVertex(self.vtxList, 
				len(self.vtxList.vertices), 
				len(self.vertBuffer) - self.bufferStart, self.bufferStart))
			self.triList.commands.extend(createTriangleCommands(
				self.vertexBufferTriangles, self.f3d.F3DEX_GBI))
			for vertData in self.vertBuffer[self.bufferStart:]:
				self.vtxList.vertices.append(convertVertexData(
					self.convertInfo.obj.data, vertData[0], vertData[1], 
					vertData[2], self.texDimensions, self.transformMatrix,
					self.isPointSampled, self.exportVertexColors))
		
		self.triList.commands.append(SPEndDisplayList())
	
def getF3DVert(loop, face, convertInfo, mesh):
	position = mesh.vertices[loop.vertex_index].co.copy().freeze()
	# N64 is -Y, Blender is +Y
	uv = convertInfo.uv_data[loop.index].uv.copy()
	uv[1] = 1 - uv[1]
	uv = uv.freeze()
	colorOrNormal = getLoopColorOrNormal(loop, face, 
		convertInfo.obj.data, convertInfo.obj, convertInfo.exportVertexColors)
	
	return (position, uv, colorOrNormal)

def getLoopNormal(loop, face, mesh, isFlatShaded):
	# This is a workaround for flat shading not working well.
	# Since we support custom blender normals we can now ignore this.
	#if isFlatShaded:
	#	normal = -face.normal #???
	#else:
	#	normal = -loop.normal #???
	#return get8bitRoundedNormal(normal).freeze()
	return get8bitRoundedNormal(loop, mesh).freeze()

'''
def getLoopNormalCreased(bLoop, obj):
	edges = obj.data.edges
	centerVert = bLoop.vert

	availableFaces = []
	visitedFaces = [bLoop.face]
	connectedFaces = getConnectedFaces(bLoop.face, bLoop.vert)
	if len(connectedFaces) == 0:
		return bLoop.calc_normal()

	for face in connectedFaces:
		availableFaces.append(FaceWeight(face, bLoop.face, 1))

	curNormal = bLoop.calc_normal() * bLoop.calc_angle()
	while len(availableFaces) > 0:
		nextFaceWeight = getHighestFaceWeight(availableFaces)
		curNormal += getWeightedNormalAndMoveToNextFace(
			nextFaceWeight, visitedFaces, availableFaces, centerVert, edges)
	
	return curNormal.normalized()

def getConnectedFaces(bFace, bVert):
	connectedFaces = []
	for face in bVert.link_faces:
		if face == bFace:
			continue
		for edge in face.edges:
			if bFace in edge.link_faces:
				connectedFaces.append(face)
	return connectedFaces

# returns false if not enough faces to check for creasing
def getNextFace(faceWeight, bVert, visitedFaces, availableFaces):
	connectedFaces = getConnectedFaces(faceWeight.face, bVert)
	visitedFaces.append(faceWeight.face)

	newFaceFound = False
	nextPrevFace = faceWeight.face
	for face in connectedFaces:
		if face in visitedFaces:
			continue
		elif not newFaceFound:
			newFaceFound = True
			faceWeight.prevFace = faceWeight.face
			faceWeight.face = face
		else:
			availableFaces.append(FaceWeight(face, nextPrevFace,
				faceWeight.weight))
	
	if not newFaceFound:
		availableFaces.remove(faceWeight)
	
	removedFaceWeights = []
	for otherFaceWeight in availableFaces:
		if otherFaceWeight.face in visitedFaces:
			removedFaceWeights.append(otherFaceWeight)
	for removedFaceWeight in removedFaceWeights:
		availableFaces.remove(removedFaceWeight)

def getLoopFromFaceVert(bFace, bVert):
	for loop in bFace.loops:
		if loop.vert == bVert:
			return loop
	return None

def getEdgeBetweenFaces(faceWeight):
	face1 = faceWeight.face
	face2 = faceWeight.prevFace
	for edge1 in face1.edges:
		for edge2 in face2.edges:
			if edge1 == edge2:
				return edge1
	return None

class FaceWeight:
	def __init__(self, face, prevFace, weight):
		self.face = face
		self.prevFace = prevFace
		self.weight = weight

def getWeightedNormalAndMoveToNextFace(selectFaceWeight, visitedFaces, 
	availableFaces, centerVert, edges):
	selectLoop = getLoopFromFaceVert(selectFaceWeight.face, centerVert)
	edgeIndex = getEdgeBetweenFaces(selectFaceWeight).index

	# Ignore triangulated faces
	if edgeIndex < len(edges):
		selectFaceWeight.weight *= 1 - edges[edgeIndex].crease

	getNextFace(selectFaceWeight, centerVert, visitedFaces, availableFaces)
	return selectLoop.calc_normal() * selectLoop.calc_angle() * \
		selectFaceWeight.weight

def getHighestFaceWeight(faceWeights):
	highestFaceWeight = faceWeights[0]
	for faceWeight in faceWeights[1:]:
		if faceWeight.weight > highestFaceWeight.weight:
			highestFaceWeight = faceWeight
	return highestFaceWeight
'''

def convertVertexData(mesh, loopPos, loopUV, loopColorOrNormal, 
	texDimensions, transformMatrix, isPointSampled, exportVertexColors):
	#uv_layer = mesh.uv_layers.active
	#color_layer = mesh.vertex_colors['Col']
	#alpha_layer = mesh.vertex_colors['Alpha']

	# Position (8 bytes)
	position = [int(round(floatValue)) for \
		floatValue in (transformMatrix @ loopPos)]

	# UV (4 bytes)
	# For F3D, Bilinear samples the point from the center of the pixel.
	# However, Point samples from the corner.
	# Thus we add 0.5 to the UV only if bilinear filtering.
	# see section 13.7.5.3 in programming manual.
	pixelOffset = 0 if isPointSampled else 0.5
	uv = [
		convertFloatToFixed16(loopUV[0] * texDimensions[0] - pixelOffset),
		convertFloatToFixed16(loopUV[1] * texDimensions[1] - pixelOffset)
	]

	# Color/Normal (4 bytes)
	if exportVertexColors:
		colorOrNormal = [
			int(round(loopColorOrNormal[0] * 255)).to_bytes(1, 'big')[0],
			int(round(loopColorOrNormal[1] * 255)).to_bytes(1, 'big')[0],
			int(round(loopColorOrNormal[2] * 255)).to_bytes(1, 'big')[0],
			int(round(loopColorOrNormal[3] * 255)).to_bytes(1, 'big')[0]
		]
	else:
		# normal transformed correctly.
		normal = (transformMatrix.inverted().transposed() @ \
			loopColorOrNormal).normalized()
		colorOrNormal = [
			int(round(normal[0] * 127)).to_bytes(1, 'big', signed = True)[0],
			int(round(normal[1] * 127)).to_bytes(1, 'big', signed = True)[0],
			int(round(normal[2] * 127)).to_bytes(1, 'big', signed = True)[0],
			int(round(loopColorOrNormal[3] * 255)).to_bytes(1, 'big')[0],
		]

	return Vtx(position, uv, colorOrNormal)

def getLoopColor(loop, mesh):
	color_layer = mesh.vertex_colors['Col'].data if 'Col' in \
		mesh.vertex_colors else None
	alpha_layer = mesh.vertex_colors['Alpha'].data if 'Alpha' in \
		mesh.vertex_colors else None

	if color_layer is not None:
		normalizedRGB = color_layer[loop.index].color
	else:
		normalizedRGB = [1,1,1]
	if alpha_layer is not None:
		normalizedAColor = alpha_layer[loop.index].color
		normalizedA = mathutils.Color(normalizedAColor[0:3]).v
	else:
		normalizedA = 1
	
	return (normalizedRGB[0], normalizedRGB[1], normalizedRGB[2], normalizedA)

def getLoopColorOrNormal(loop, face, mesh, obj, exportVertexColors):
	material = obj.data.materials[face.material_index]
	isFlatShaded = checkIfFlatShaded(material)
	if exportVertexColors:
		return getLoopColor(loop, mesh)
	else:
		return getLoopNormal(loop, face, mesh, isFlatShaded)

def createTriangleCommands(triangles, useSP2Triangle):
	triangles = copy.deepcopy(triangles)
	commands = []
	if useSP2Triangle:
		while len(triangles) > 0:
			if len(triangles) >= 2:
				commands.append(SP2Triangles(
					triangles[0][0], triangles[0][1], triangles[0][2], 0,
					triangles[1][0], triangles[1][1], triangles[1][2], 0))
				triangles = triangles[2:]
			else:
				commands.append(SP1Triangle(
					triangles[0][0], triangles[0][1], triangles[0][2], 0))
				triangles = []
	else:
		while len(triangles) > 0:
			commands.append(SP1Triangle(
				triangles[0][0], triangles[0][1], triangles[0][2], 0))
			triangles = triangles[1:]
		
	return commands

'''
def saveGeometry(obj, triList, vtxList, bFaces, bMesh, 
	texDimensions, transformMatrix, isPointSampled, isFlatShaded,
	exportVertexColors, f3d):

	uv_layer = bMesh.loops.layers.uv.verify()
	convertInfo = LoopConvertInfo(uv_layer, bMesh, obj, exportVertexColors)
	triangleConverter = TriangleConverter(obj.data, convertInfo, triList, 
		vtxList, f3d, texDimensions, transformMatrix, isPointSampled,
		exportVertexColors, None, None)

	for bFace in bFaces:
		triangleConverter.addFace(bFace)	
	triangleConverter.finish()
'''

# white diffuse, grey ambient, normal = (1,1,1)
defaultLighting = [
	(mathutils.Vector((1,1,1)), mathutils.Vector((1, 1, 1)).normalized()),
	(mathutils.Vector((0.5, 0.5, 0.5)), mathutils.Vector((1, 1, 1)).normalized())]

def getTexDimensions(material):
	if material.mat_ver > 3:
		f3dMat = material.f3d_mat
	else:
		f3dMat = material
	texDimensions0 = None
	texDimensions1 = None
	useDict = all_combiner_uses(f3dMat)
	if useDict['Texture 0'] and f3dMat.tex0.tex_set:
		if f3dMat.tex0.tex is None:
			raise PluginError('In material \"' + material.name + '\", a texture has not been set.')
		texDimensions0 = f3dMat.tex0.tex.size[0], f3dMat.tex0.tex.size[1]
	if useDict['Texture 1'] and f3dMat.tex1.tex_set:
		if f3dMat.tex1.tex is None:
			raise PluginError('In material \"' + material.name + '\", a texture has not been set.')
		texDimensions1 = f3dMat.tex1.tex.size[0], f3dMat.tex1.tex.size[1]

	if texDimensions0 is not None and texDimensions1 is not None:
		texDimensions = texDimensions0 if f3dMat.uv_basis == 'TEXEL0' \
			else texDimensions1
	elif texDimensions0 is not None:
		texDimensions = texDimensions0
	elif texDimensions1 is not None:
		texDimensions = texDimensions1
	else:
		texDimensions = [32, 32]
	return texDimensions

def saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData):
	if material.mat_ver > 3:
		f3dMat = material.f3d_mat
	else:
		f3dMat = material

	areaKey = fModel.global_data.getCurrentAreaKey(f3dMat)
	areaIndex = fModel.global_data.current_area_index

	if f3dMat.rdp_settings.set_rendermode:
		materialKey = (material, drawLayer, areaKey)
	else:
		materialKey = (material, None, areaKey)
	
	materialItem = fModel.getMaterialAndHandleShared(materialKey)
	if materialItem is not None:
		return materialItem
	
	if len(obj.data.materials) == 0:
		raise PluginError("Mesh must have at least one material.")
	materialName = fModel.name + "_" + toAlnum(material.name) + (('_layer' + str(drawLayer)) \
		if f3dMat.rdp_settings.set_rendermode and drawLayer is not None else '') +\
		(('_area' + str(areaIndex)) if \
			f3dMat.set_fog and f3dMat.use_global_fog and areaKey is not None else '')
	fMaterial = FMaterial(materialName, fModel.DLFormat)
	fMaterial.material.commands.append(DPPipeSync())
	fMaterial.revert.commands.append(DPPipeSync())
	
	if not material.is_f3d:
		raise PluginError("Material named " +  material.name + \
			' is not an F3D material.')

	fMaterial.getScrollData(material, getMaterialScrollDimensions(f3dMat))

	if f3dMat.set_combiner:
		if f3dMat.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
			fMaterial.material.commands.append(
				DPSetCombineMode(
					f3dMat.combiner1.A,
					f3dMat.combiner1.B,
					f3dMat.combiner1.C,
					f3dMat.combiner1.D,
					f3dMat.combiner1.A_alpha,
					f3dMat.combiner1.B_alpha,
					f3dMat.combiner1.C_alpha,
					f3dMat.combiner1.D_alpha,
					f3dMat.combiner2.A,
					f3dMat.combiner2.B,
					f3dMat.combiner2.C,
					f3dMat.combiner2.D,
					f3dMat.combiner2.A_alpha,
					f3dMat.combiner2.B_alpha,
					f3dMat.combiner2.C_alpha,
					f3dMat.combiner2.D_alpha
			))
		else:
			fMaterial.material.commands.append(
				DPSetCombineMode(
					f3dMat.combiner1.A,
					f3dMat.combiner1.B,
					f3dMat.combiner1.C,
					f3dMat.combiner1.D,
					f3dMat.combiner1.A_alpha,
					f3dMat.combiner1.B_alpha,
					f3dMat.combiner1.C_alpha,
					f3dMat.combiner1.D_alpha,
					f3dMat.combiner1.A,
					f3dMat.combiner1.B,
					f3dMat.combiner1.C,
					f3dMat.combiner1.D,
					f3dMat.combiner1.A_alpha,
					f3dMat.combiner1.B_alpha,
					f3dMat.combiner1.C_alpha,
					f3dMat.combiner1.D_alpha
			))

	if f3dMat.set_fog:
		if f3dMat.use_global_fog and fModel.global_data.getCurrentAreaData() is not None:
			fogData = fModel.global_data.getCurrentAreaData().fog_data
			fog_position = fogData.position
			fog_color = fogData.color
		else:
			fog_position = f3dMat.fog_position
			fog_color = f3dMat.fog_color
		fMaterial.material.commands.extend([
			DPSetFogColor(
				int(round(fog_color[0] * 255)),
				int(round(fog_color[1] * 255)),
				int(round(fog_color[2] * 255)),
				int(round(fog_color[3] * 255))),
			SPFogPosition(fog_position[0], fog_position[1])
		])

	useDict = all_combiner_uses(f3dMat)

	if drawLayer is not None:
		defaultRM = fModel.getRenderMode(drawLayer)
	else:
		defaultRM = None

	defaults = bpy.context.scene.world.rdp_defaults
	saveGeoModeDefinition(fMaterial, f3dMat.rdp_settings, defaults, fModel.matWriteMethod)
	saveOtherModeHDefinition(fMaterial, f3dMat.rdp_settings, defaults, fModel.f3d._HW_VERSION_1, fModel.matWriteMethod)
	saveOtherModeLDefinition(fMaterial, f3dMat.rdp_settings, defaults, defaultRM, fModel.matWriteMethod)
	saveOtherDefinition(fMaterial, f3dMat, defaults)

	# Set scale
	s = int(f3dMat.tex_scale[0] * 0xFFFF)
	t = int(f3dMat.tex_scale[1] * 0xFFFF)
	fMaterial.material.commands.append(
		SPTexture(s, t, 0, fModel.f3d.G_TX_RENDERTILE, 1))

	# Save textures
	texDimensions0 = None
	texDimensions1 = None
	nextTmem = 0
	if useDict['Texture 0'] and f3dMat.tex0.tex_set:
		if f3dMat.tex0.tex is None:
			raise PluginError('In material \"' + material.name + '\", a texture has not been set.')
		texDimensions0, nextTmem = saveTextureIndex(material.name, fModel, 
			fMaterial, fMaterial.material, fMaterial.revert, f3dMat.tex0, 0, nextTmem, None, convertTextureData)	
	if useDict['Texture 1'] and f3dMat.tex1.tex_set:
		if f3dMat.tex1.tex is None:
			raise PluginError('In material \"' + material.name + '\", a texture has not been set.')
		texDimensions1, nextTmem = saveTextureIndex(material.name, fModel, 
			fMaterial, fMaterial.material, fMaterial.revert, f3dMat.tex1, 1, nextTmem, None, convertTextureData)

	# Used so we know how to convert normalized UVs when saving verts.
	if texDimensions0 is not None and texDimensions1 is not None:
		texDimensions = texDimensions0 if f3dMat.uv_basis == 'TEXEL0' \
			else texDimensions1
	elif texDimensions0 is not None:
		texDimensions = texDimensions0
	elif texDimensions1 is not None:
		texDimensions = texDimensions1
	else:
		texDimensions = [32, 32]

	nodes = material.node_tree.nodes
	if useDict['Primitive'] and f3dMat.set_prim:
		if material.mat_ver > 3:
			color = f3dMat.prim_color
		elif material.mat_ver == 3:
			color = nodes['Primitive Color Output'].inputs[0].default_value
		else:
			color = nodes['Primitive Color'].outputs[0].default_value
		color = gammaCorrect(color[0:3]) + [color[3]]
		fMaterial.material.commands.append(
			DPSetPrimColor(
			int(f3dMat.prim_lod_min * 255),
			int(f3dMat.prim_lod_frac * 255),
			int(color[0] * 255), 
			int(color[1] * 255), 
			int(color[2] * 255),
			int(color[3] * 255)))

	if useDict['Environment'] and f3dMat.set_env:	
		if material.mat_ver == 4:
			color = f3dMat.env_color
		if material.mat_ver == 3:
			color = nodes['Environment Color Output'].inputs[0].default_value
		else:
			color = nodes['Environment Color'].outputs[0].default_value
		color = gammaCorrect(color[0:3]) + [color[3]]
		fMaterial.material.commands.append(
			DPSetEnvColor(
			int(color[0] * 255), 
			int(color[1] * 255), 
			int(color[2] * 255),
			int(color[3] * 255)))
	
	if useDict['Shade'] and f3dMat.set_lights:
		fLights = saveLightsDefinition(fModel, f3dMat, 
			materialName + '_lights')
		fMaterial.material.commands.extend([
			SPSetLights(fLights) # TODO: handle synching: NO NEED?
		])
	
	if useDict['Key'] and f3dMat.set_key:
		if material.mat_ver == 4:
			center = f3dMat.key_center
		else:
			center = nodes['Chroma Key Center'].outputs[0].default_value
		scale = f3dMat.key_scale
		width = f3dMat.key_width
		fMaterial.material.commands.extend([
			DPSetCombineKey('G_CK_KEY'),
			# TODO: Add UI handling width
			DPSetKeyR(int(center[0] * 255), int(scale[0] * 255), 
				int(width[0] * 2**8)),
			DPSetKeyGB(int(center[1] * 255), int(scale[1] * 255), 
				int(width[1] * 2**8), 
				int(center[2] * 255), int(scale[2] * 255), 
				int(width[2] * 2**8))	
		])

	# all k0-5 set at once
	# make sure to handle this in node shader
	# or don't, who cares
	if useDict['Convert'] and f3dMat.set_k0_5:
		fMaterial.material.commands.extend([
			DPSetTextureConvert('G_TC_FILTCONV'), # TODO: allow filter option
			DPSetConvert(
				int(f3dMat.k0 * 255),
				int(f3dMat.k1 * 255),
				int(f3dMat.k2 * 255),
				int(f3dMat.k3 * 255),
				int(f3dMat.k4 * 255),
				int(f3dMat.k5 * 255))
		])
		
	# End Display List
	# For dynamic calls, materials will be called as functions and should not end the DL.
	if fModel.DLFormat == DLFormat.Static:
		fMaterial.material.commands.append(SPEndDisplayList())

	#revertMatAndEndDraw(fMaterial.revert)
	if len(fMaterial.revert.commands) > 1: # 1 being the pipe sync
		if fMaterial.DLFormat == DLFormat.Static:
			fMaterial.revert.commands.append(SPEndDisplayList())
	else:
		fMaterial.revert = None
	
	materialKey = material, (drawLayer if f3dMat.rdp_settings.set_rendermode else None), \
		fModel.global_data.getCurrentAreaKey(f3dMat)
	fModel.materials[materialKey] = (fMaterial, texDimensions)

	return fMaterial, texDimensions

def saveTextureIndex(propName, fModel, fMaterial, loadTexGfx, revertTexGfx, texProp, index, tmem, overrideName, convertTextureData):
	tex = texProp.tex
	if tex is None:
		raise PluginError('In ' + propName + ", no texture is selected.")
	elif len(tex.pixels) == 0:
		raise PluginError("Could not load missing texture: " + tex.name + ". Make sure this texture has not been deleted or moved on disk.")
	
	texFormat = texProp.tex_format
	isCITexture = texFormat[:2] == 'CI'
	palFormat = texProp.ci_format if isCITexture else ''
	if tex.filepath == "":
		name = tex.name
	else:
		name = tex.filepath
	texName = fModel.name + '_' + \
		(getNameFromPath(name, True) + '_' + texFormat.lower() if overrideName is None else overrideName)
		
	nextTmem = tmem + getTmemWordUsage(texFormat, tex.size[0], tex.size[1])
	
	if not bpy.context.scene.ignoreTextureRestrictions:
		if nextTmem > (512 if texFormat[:2] != 'CI' else 256):
			raise PluginError("Error in \"" + propName + "\": Textures are too big. Max TMEM size is 4k " + \
				"bytes, ex. 2 32x32 RGBA 16 bit textures.\nNote that texture width will be internally padded to 64 bit boundaries.")
		if tex.size[0] > 1024 or tex.size[1] > 1024:
			raise PluginError("Error in \"" + propName + "\": Any side of an image cannot be greater " +\
				"than 1024.")

	clamp_S = texProp.S.clamp
	mirror_S = texProp.S.mirror
	tex_SL = texProp.S.low
	tex_SH = texProp.S.high
	mask_S = texProp.S.mask
	shift_S = texProp.S.shift

	clamp_T = texProp.T.clamp
	mirror_T = texProp.T.mirror
	tex_TL = texProp.T.low
	tex_TH = texProp.T.high
	mask_T = texProp.T.mask
	shift_T = texProp.T.shift

	if isCITexture:
		fImage, fPalette = saveOrGetPaletteDefinition(
			fMaterial, fModel, tex, texName, texFormat, palFormat, convertTextureData)
		savePaletteLoading(loadTexGfx, revertTexGfx, fPalette, 
			palFormat, 0, fPalette.height, fModel.f3d)
	else:
		fImage = saveOrGetTextureDefinition(fMaterial, fModel, tex, texName, 
			texFormat, convertTextureData)
	saveTextureLoading(fMaterial, fImage, loadTexGfx, clamp_S,
	 	mirror_S, clamp_T, mirror_T,
		mask_S, mask_T, shift_S, 
		shift_T, tex_SL, tex_TL, tex_SH, 
		tex_TH, texFormat, index, fModel.f3d, tmem)
	texDimensions = fImage.width, fImage.height
	#fImage = saveTextureDefinition(fModel, tex, texName, 
	#	texFormatOf[texFormat], texBitSizeOf[texFormat])
	#fModel.textures[texName] = fImage	

	return texDimensions, nextTmem

# texIndex: 0 for texture0, 1 for texture1
def saveTextureLoading(fMaterial, fImage, loadTexGfx, clamp_S, mirror_S, clamp_T,
	mirror_T, mask_S, mask_T, shift_S, shift_T,
	SL, TL, SH, TH, tex_format, texIndex, f3d, tmem):
	cms = [('G_TX_CLAMP' if clamp_S else 'G_TX_WRAP'),
		('G_TX_MIRROR' if mirror_S else 'G_TX_NOMIRROR')]
	cmt = [('G_TX_CLAMP' if clamp_T else 'G_TX_WRAP'),
		('G_TX_MIRROR' if mirror_T else 'G_TX_NOMIRROR')]
	masks = mask_S
	maskt = mask_T
	shifts = shift_S if shift_S >= 0 else (shift_S + 16)
	shiftt = shift_T if shift_T >= 0 else (shift_T + 16)

	#print('Low ' + str(SL) + ' ' + str(TL))
	sl = int(SL * (2 ** f3d.G_TEXTURE_IMAGE_FRAC))
	tl = int(TL * (2 ** f3d.G_TEXTURE_IMAGE_FRAC))
	sh = int(SH * (2 ** f3d.G_TEXTURE_IMAGE_FRAC))
	th = int(TH * (2 ** f3d.G_TEXTURE_IMAGE_FRAC))
	
	fmt = texFormatOf[tex_format]
	siz = texBitSizeOf[tex_format]
	pal = 0 if fmt[:2] != 'CI' else 0 # handle palettes

	# LoadTile will pad rows to 64 bit word alignment, while
	# LoadBlock assumes this is already done.
	if siz == 'G_IM_SIZ_4b':
		sl2 = int(SL * (2 ** (f3d.G_TEXTURE_IMAGE_FRAC - 1)))
		sh2 = int(SH * (2 ** (f3d.G_TEXTURE_IMAGE_FRAC - 1)))

		dxt = f3d.CALC_DXT_4b(fImage.width)
		line = (((int(SH - SL) + 1) >> 1) + 7) >> 3

		loadTexGfx.commands.extend([
			DPTileSync(), # added in
			DPSetTextureImage(fmt, 'G_IM_SIZ_8b', fImage.width >> 1, fImage),
			DPSetTile(fmt, 'G_IM_SIZ_8b', line, tmem, 
				f3d.G_TX_LOADTILE - texIndex, 0, cmt, maskt, shiftt, 
			 	cms, masks, shifts),
			DPLoadSync(),
			DPLoadTile(f3d.G_TX_LOADTILE - texIndex, sl2, tl, sh2, th),])

	else:
		dxt = f3d.CALC_DXT(fImage.width, f3d.G_IM_SIZ_VARS[siz + '_BYTES'])
		# Note that _LINE_BYTES and _TILE_BYTES variables are the same.
		line = (((int(SH - SL) + 1) * \
			f3d.G_IM_SIZ_VARS[siz + '_LINE_BYTES']) + 7) >> 3

		loadTexGfx.commands.extend([
			DPTileSync(), # added in

			# Load Block version
			#DPSetTextureImage(fmt, siz + '_LOAD_BLOCK', 1, fImage),
			#DPSetTile(fmt, siz + '_LOAD_BLOCK', 0, tmem, 
			#	f3d.G_TX_LOADTILE - texIndex, 0, cmt, maskt, shiftt, 
			# 	cms, masks, shifts),
			#DPLoadSync(),
			#DPLoadBlock(f3d.G_TX_LOADTILE - texIndex, 0, 0, \
			#	(((fImage.width)*(fImage.height) + \
			#	f3d.G_IM_SIZ_VARS[siz + '_INCR']) >> \
			#	f3d.G_IM_SIZ_VARS[siz + '_SHIFT'])-1, \
			#	dxt),

			# Load Tile version
			DPSetTextureImage(fmt, siz, fImage.width, fImage),
			DPSetTile(fmt, siz, line, tmem, 
				f3d.G_TX_LOADTILE - texIndex, 0, cmt, maskt, shiftt, 
			 	cms, masks, shifts),
			DPLoadSync(),
			DPLoadTile(f3d.G_TX_LOADTILE - texIndex, sl, tl, sh, th),]) # added in
	
	tileSizeCommand = DPSetTileSize(f3d.G_TX_RENDERTILE + texIndex, sl, tl, sh, th)
	loadTexGfx.commands.extend([
		DPPipeSync(),
		DPSetTile(fmt, siz, line, tmem,	\
			f3d.G_TX_RENDERTILE + texIndex, pal, cmt, maskt, \
			shiftt, cms, masks, shifts),
		tileSizeCommand,
	]) # added in)

	# hasattr check for FTexRect
	if hasattr(fMaterial, 'tileSizeCommands'):
		fMaterial.tileSizeCommands[f3d.G_TX_RENDERTILE + texIndex] = tileSizeCommand

# palette stored in upper half of TMEM (words 256-511)
# pal is palette number (0-16), for CI8 always set to 0
def savePaletteLoading(loadTexGfx, revertTexGfx, fPalette, palFormat, pal, 
	colorCount, f3d):
	palFmt = texFormatOf[palFormat]
	cms = ['G_TX_WRAP', 'G_TX_NOMIRROR']
	cmt = ['G_TX_WRAP', 'G_TX_NOMIRROR']

	loadTexGfx.commands.append(DPSetTextureLUT(
		'G_TT_RGBA16' if palFmt == 'G_IM_FMT_RGBA' else 'G_TT_IA16'))
	revertTexGfx.commands.append(DPSetTextureLUT('G_TT_NONE'))

	if not f3d._HW_VERSION_1:
		loadTexGfx.commands.extend([
			DPSetTextureImage(palFmt, 'G_IM_SIZ_16b', 1, fPalette),
			DPTileSync(),
			DPSetTile('0', '0', 0, (256+(((pal)&0xf)*16)),\
				f3d.G_TX_LOADTILE, 0, cmt, 0, 0, cms, 0, 0),
			DPLoadSync(),
			DPLoadTLUTCmd(f3d.G_TX_LOADTILE, colorCount - 1),
			DPPipeSync()])
	else:
		loadTexGfx.commands.extend([
			_DPLoadTextureBlock(fPalette, \
				(256+(((pal)&0xf)*16)), \
            	palFmt, 'G_IM_SIZ_16b', 4*colorCount, 1,
            	pal, cms, cmt, 0, 0, 0, 0)])
	
def saveOrGetPaletteDefinition(fMaterial, fModelOrTexRect, image, imageName, texFmt, palFmt, convertTextureData):
	texFormat = texFormatOf[texFmt]
	palFormat = texFormatOf[palFmt]
	bitSize = texBitSizeOf[texFmt]
	# If image already loaded, return that data.
	paletteName = toAlnum(imageName) + '_pal_' + palFmt.lower()
	imageKey = (image, (texFmt, palFmt))
	palKey = (image, (palFmt, 'PAL'))
	if imageKey in fModelOrTexRect.textures:
		return fModelOrTexRect.textures[imageKey], fModelOrTexRect.textures[palKey]

	palette = []
	texture = []
	maxColors = 16 if bitSize == 'G_IM_SIZ_4b' else 256
	if convertTextureData:
		# N64 is -Y, Blender is +Y
		for j in reversed(range(image.size[1])):
			for i in range(image.size[0]):
				color = [1,1,1,1]
				for field in range(image.channels):
					color[field] = image.pixels[
						(j * image.size[0] + i) * image.channels + field]
				if palFormat == 'G_IM_FMT_RGBA':
					pixelColor = getRGBA16Tuple(color)
				elif palFormat == 'G_IM_FMT_IA':
					pixelColor = getIA16Tuple(color)
				else:
					raise PluginError("Invalid combo: " + palFormat + ', ' + bitSize)
				
				if pixelColor not in palette:
					palette.append(pixelColor)
					if len(palette) > maxColors:
						raise PluginError('Texture ' + imageName + ' has more than ' + \
							str(maxColors) + ' colors.')
				texture.append(palette.index(pixelColor))
	
	if image.filepath == "":
		name = image.name
	else:
		name = image.filepath
	filename = getNameFromPath(name, True) + '.' + \
		texFmt.lower() + '.inc.c'
	paletteFilename = getNameFromPath(name, True) + '.' + \
		texFmt.lower() + '.pal'
	fImage = FImage(checkDuplicateTextureName(fModelOrTexRect, toAlnum(imageName)), texFormat, bitSize, 
		image.size[0], image.size[1], filename, convertTextureData)

	fPalette = FImage(checkDuplicateTextureName(fModelOrTexRect, paletteName), palFormat, 'G_IM_SIZ_16b', 1, 
		len(palette), paletteFilename, convertTextureData)
	#paletteTex = bpy.data.images.new(paletteName, 1, len(palette))
	#paletteTex.pixels = palette
	#paletteTex.filepath = getNameFromPath(name, True) + '.' + \
	#	texFmt.lower() + '.pal'

	if convertTextureData:
		for color in palette:
			fPalette.data.extend(color.to_bytes(2, 'big')) 

		if bitSize == 'G_IM_SIZ_4b':
			fImage.data = compactNibbleArray(texture, image.size[0], image.size[1])
		else:	
			fImage.data = bytearray(texture)
	
	fModelOrTexRect.addTexture((image, (texFmt, palFmt)), fImage, fMaterial)
	fModelOrTexRect.addTexture((image, (palFmt, 'PAL')), fPalette, fMaterial)

	return fImage, fPalette #, paletteTex

def compactNibbleArray(texture, width, height):
	nibbleData = bytearray(0)
	dataSize = int(width * height / 2)

	for i in range(dataSize):
		nibbleData.append(
			((texture[i * 2] & 0xF) << 4) |\
			(texture[i * 2 + 1] & 0xF)
		)

	if (width * height) % 2 == 1:
		nibbleData.append((texture[-1] & 0xF) << 4)
	
	return nibbleData

def checkDuplicateTextureName(fModelOrTexRect, name):
	names = []
	for info, texture in fModelOrTexRect.textures.items():
		names.append(texture.name)
	while name in names:
		name = name + '_copy'
	return name

def saveOrGetTextureDefinition(fMaterial, fModel, image, imageName, texFormat, convertTextureData):
	fmt = texFormatOf[texFormat]
	bitSize = texBitSizeOf[texFormat]

	# If image already loaded, return that data.
	imageKey = (image, (texFormat, 'NONE'))
	imageItem = fModel.getTextureAndHandleShared(imageKey)
	if imageItem is not None:
		return imageItem

	if image.filepath == "":
		name = image.name
	else:
		name = image.filepath
	filename = getNameFromPath(name, True) + '.' + \
		texFormat.lower() + '.inc.c'

	fImage = FImage(checkDuplicateTextureName(fModel, toAlnum(imageName)), fmt, bitSize, 
		image.size[0], image.size[1], filename, convertTextureData)

	if convertTextureData:
		# N64 is -Y, Blender is +Y
		for j in reversed(range(image.size[1])):
			for i in range(image.size[0]):
				color = [1,1,1,1]
				for field in range(image.channels):
					color[field] = image.pixels[
						(j * image.size[0] + i) * image.channels + field]
				if fmt == 'G_IM_FMT_RGBA':
					if bitSize == 'G_IM_SIZ_16b':
						words = \
							((int(color[0] * 0x1F) & 0x1F) << 11) | \
							((int(color[1] * 0x1F) & 0x1F) << 6) | \
							((int(color[2] * 0x1F) & 0x1F) << 1) | \
							(1 if color[3] > 0.5 else 0)
						fImage.data.extend(bytearray(words.to_bytes(2, 'big')))
					elif bitSize == 'G_IM_SIZ_32b':
						fImage.data.extend(bytearray([
							int(value * 0xFF) & 0xFF for value in color]))
					else:
						raise PluginError("Invalid combo: " + fmt + ', ' + bitSize)

				elif fmt == 'G_IM_FMT_YUV':
					raise PluginError("YUV not yet implemented.")
					if bitSize == 'G_IM_SIZ_16b':
						pass
					else:
						raise PluginError("Invalid combo: " + fmt + ', ' + bitSize)

				elif fmt == 'G_IM_FMT_CI':
					raise PluginError("CI not yet implemented.")

				elif fmt == 'G_IM_FMT_IA':
					intensity = mathutils.Color(color[0:3]).v
					alpha = color[3]
					if bitSize == 'G_IM_SIZ_4b':
						fImage.data.append(
							((int(intensity * 0x7) & 0x7) << 1) | \
							(1 if alpha > 0.5 else 0))
					elif bitSize == 'G_IM_SIZ_8b':
						fImage.data.append(
							((int(intensity * 0xF) & 0xF) << 4) | \
							(int(alpha * 0xF) & 0xF))
					elif bitSize == 'G_IM_SIZ_16b':
						fImage.data.extend(bytearray(
							[int(intensity * 0xFF), int(alpha * 0xFF)]))
					else:
						raise PluginError("Invalid combo: " + fmt + ', ' + bitSize)
				elif fmt == 'G_IM_FMT_I':
					intensity = mathutils.Color(color[0:3]).v
					if bitSize == 'G_IM_SIZ_4b':
						fImage.data.append(int(intensity * 0xF))
					elif bitSize == 'G_IM_SIZ_8b':
						fImage.data.append(int(intensity * 0xFF))
					else:
						raise PluginError("Invalid combo: " + fmt + ', ' + bitSize)
				else:
					raise PluginError("Invalid image format " + fmt)
			
		# We stored 4bit values in byte arrays, now to convert
		if bitSize == 'G_IM_SIZ_4b':
			fImage.data = \
				compactNibbleArray(fImage.data, image.size[0], image.size[1])
	
	fModel.addTexture((image, (texFormat, 'NONE')), fImage, fMaterial)

	return fImage

def saveLightsDefinition(fModel, material, lightsName):
	lights = Lights(toAlnum(lightsName))

	if material.use_default_lighting:
		color = gammaCorrect(material.default_light_color)
		lights.a = Ambient(
			[int(color[0] * 255 / 2),
			int(color[1] * 255 / 2),
			int(color[2] * 255 / 2)])
		lights.l.append(Light(
			[int(color[0] * 255),
			int(color[1] * 255),
			int(color[2] * 255)], 
			[0x28, 0x28, 0x28]))
	else:
		ambientColor = gammaCorrect(material.ambient_light_color)

		lights.a = Ambient(
			[int(ambientColor[0] * 255),
			int(ambientColor[1] * 255),
			int(ambientColor[2] * 255)])

		if material.f3d_light1 is not None:
			addLightDefinition(material, material.f3d_light1, lights)
		if material.f3d_light2 is not None:
			addLightDefinition(material, material.f3d_light2, lights)
		if material.f3d_light3 is not None:
			addLightDefinition(material, material.f3d_light3, lights)
		if material.f3d_light4 is not None:
			addLightDefinition(material, material.f3d_light4, lights)
		if material.f3d_light5 is not None:
			addLightDefinition(material, material.f3d_light5, lights)
		if material.f3d_light6 is not None:
			addLightDefinition(material, material.f3d_light6, lights)
		if material.f3d_light7 is not None:
			addLightDefinition(material, material.f3d_light7, lights)

	if lightsName in fModel.lights:
		raise PluginError("Duplicate light name.")
	fModel.lights[lightsName] = lights
	return lights

def addLightDefinition(mat, f3d_light, fLights):
	#lightObj = None
	#for obj in bpy.context.scene.objects:
	#	if obj.data == f3d_light:
	#		lightObj = obj
	#		break
	#if lightObj is None:
	#	raise PluginError(
	#		"The material \"" + mat.name + "\" is referencing a light that is no longer in the scene (i.e. has been deleted).")
	
	fLights.l.append(Light(
		getLightColor(f3d_light.color),
		getLightRotation(f3d_light),
	))

def getLightColor(lightColor):
	return [int(round(value * 0xFF)) for value in gammaCorrect(lightColor)]

def getLightRotation(lightData):
	lightObj = None
	for obj in bpy.context.scene.objects:
		if obj.data == lightData:
			lightObj = obj
			break
	if lightObj is None:
		raise PluginError("A material is referencing a light that is no longer in the scene (i.e. has been deleted).")

	return getObjDirection(lightObj)

def getObjDirection(obj):
	spaceRot = mathutils.Euler((-pi / 2, 0, 0)).to_quaternion()
	rotation = spaceRot @ getObjectQuaternion(obj)
	normal = (rotation @ mathutils.Vector((0,0,1))).normalized()
	return normToSigned8Vector(normal)

def normToSigned8Vector(normal):
	return [int.from_bytes(int(value * 127).to_bytes(1, 'big', 
		signed = True), 'big') for value in normal]

def saveBitGeo(value, defaultValue, flagName, setGeo, clearGeo, matWriteMethod):
	if value != defaultValue or matWriteMethod == GfxMatWriteMethod.WriteAll:
		if value:
			setGeo.flagList.append(flagName)
		else:
			clearGeo.flagList.append(flagName)

def saveGeoModeDefinition(fMaterial, settings, defaults, matWriteMethod):
	setGeo = SPSetGeometryMode([])
	clearGeo = SPClearGeometryMode([])

	saveBitGeo(settings.g_zbuffer, defaults.g_zbuffer, 'G_ZBUFFER',
		setGeo, clearGeo, matWriteMethod)
	saveBitGeo(settings.g_shade, defaults.g_shade, 'G_SHADE',
		setGeo, clearGeo, matWriteMethod)
	saveBitGeo(settings.g_cull_front, defaults.g_cull_front, 'G_CULL_FRONT',
		setGeo, clearGeo, matWriteMethod)
	saveBitGeo(settings.g_cull_back,  defaults.g_cull_back, 'G_CULL_BACK',
		setGeo, clearGeo, matWriteMethod)
	saveBitGeo(settings.g_fog, defaults.g_fog, 'G_FOG', setGeo, clearGeo, matWriteMethod)
	saveBitGeo(settings.g_lighting, defaults.g_lighting, 'G_LIGHTING',
		setGeo, clearGeo, matWriteMethod)

	# make sure normals are saved correctly.
	saveBitGeo(settings.g_tex_gen, defaults.g_tex_gen, 'G_TEXTURE_GEN', 
		setGeo, clearGeo, matWriteMethod)
	saveBitGeo(settings.g_tex_gen_linear, defaults.g_tex_gen_linear,
		'G_TEXTURE_GEN_LINEAR', setGeo, clearGeo, matWriteMethod)
	saveBitGeo(settings.g_shade_smooth, defaults.g_shade_smooth,
		'G_SHADING_SMOOTH', setGeo, clearGeo, matWriteMethod)
	if bpy.context.scene.f3d_type == 'F3DEX_GBI_2' or \
		bpy.context.scene.f3d_type == 'F3DEX_GBI':
		saveBitGeo(settings.g_clipping, defaults.g_clipping, 'G_CLIPPING', 
			setGeo, clearGeo, matWriteMethod)

	if len(setGeo.flagList) > 0:
		fMaterial.material.commands.append(setGeo)
		if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
			fMaterial.revert.commands.append(SPClearGeometryMode(setGeo.flagList))
	if len(clearGeo.flagList) > 0:
		fMaterial.material.commands.append(clearGeo)
		if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
			fMaterial.revert.commands.append(SPSetGeometryMode(clearGeo.flagList))

def saveModeSetting(fMaterial, value, defaultValue, cmdClass):
	if value != defaultValue:
		fMaterial.material.commands.append(cmdClass(value))
		fMaterial.revert.commands.append(cmdClass(defaultValue))

def saveOtherModeHDefinition(fMaterial, settings, defaults, isHWv1, matWriteMethod):
	if matWriteMethod == GfxMatWriteMethod.WriteAll:
		saveOtherModeHDefinitionAll(fMaterial, settings, defaults, isHWv1)
	elif matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
		saveOtherModeHDefinitionIndividual(fMaterial, settings, defaults, isHWv1)
	else:
		raise PluginError("Unhandled material write method: " + str(matWriteMethod))

def saveOtherModeHDefinitionAll(fMaterial, settings, defaults, isHWv1):
	cmd = SPSetOtherMode("G_SETOTHERMODE_H", 0, 32, [])
	cmd.flagList.append(settings.g_mdsft_alpha_dither)
	if not isHWv1:
		cmd.flagList.append(settings.g_mdsft_rgb_dither)
		cmd.flagList.append(settings.g_mdsft_combkey)
	cmd.flagList.append(settings.g_mdsft_textconv)
	cmd.flagList.append(settings.g_mdsft_text_filt)
	cmd.flagList.append(settings.g_mdsft_textlod)
	cmd.flagList.append(settings.g_mdsft_textdetail)
	cmd.flagList.append(settings.g_mdsft_textpersp)
	cmd.flagList.append(settings.g_mdsft_cycletype)
	if isHWv1:
		cmd.flagList.append(settings.g_mdsft_color_dither)
	cmd.flagList.append(settings.g_mdsft_pipeline)

	fMaterial.material.commands.append(cmd)
		
def saveOtherModeHDefinitionIndividual(fMaterial, settings, defaults, isHWv1):
	saveModeSetting(fMaterial, settings.g_mdsft_alpha_dither,
		defaults.g_mdsft_alpha_dither, DPSetAlphaDither)

	if not isHWv1:
		saveModeSetting(fMaterial, settings.g_mdsft_rgb_dither,
			defaults.g_mdsft_rgb_dither, DPSetColorDither)

		saveModeSetting(fMaterial, settings.g_mdsft_combkey,
			defaults.g_mdsft_combkey, DPSetCombineKey)
	
	saveModeSetting(fMaterial, settings.g_mdsft_textconv,
		defaults.g_mdsft_textconv, DPSetTextureConvert)

	saveModeSetting(fMaterial, settings.g_mdsft_text_filt,
		defaults.g_mdsft_text_filt, DPSetTextureFilter)

	#saveModeSetting(fMaterial, settings.g_mdsft_textlut,
	#	defaults.g_mdsft_textlut, DPSetTextureLUT)

	saveModeSetting(fMaterial, settings.g_mdsft_textlod,
		defaults.g_mdsft_textlod, DPSetTextureLOD)

	saveModeSetting(fMaterial, settings.g_mdsft_textdetail,
		defaults.g_mdsft_textdetail, DPSetTextureDetail)

	saveModeSetting(fMaterial, settings.g_mdsft_textpersp,
		defaults.g_mdsft_textpersp, DPSetTexturePersp)
	
	saveModeSetting(fMaterial, settings.g_mdsft_cycletype,
		defaults.g_mdsft_cycletype, DPSetCycleType)

	if isHWv1:
		saveModeSetting(fMaterial, settings.g_mdsft_color_dither,
			defaults.g_mdsft_color_dither, DPSetColorDither)
	
	saveModeSetting(fMaterial, settings.g_mdsft_pipeline,
		defaults.g_mdsft_pipeline, DPPipelineMode)

def saveOtherModeLDefinition(fMaterial, settings, defaults, defaultRenderMode, matWriteMethod):
	if matWriteMethod == GfxMatWriteMethod.WriteAll:
		saveOtherModeLDefinitionAll(fMaterial, settings, defaults, defaultRenderMode)
	elif matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
		saveOtherModeLDefinitionIndividual(fMaterial, settings, defaults, defaultRenderMode)
	else:
		raise PluginError("Unhandled material write method: " + str(matWriteMethod))

def saveOtherModeLDefinitionAll(fMaterial, settings, defaults, defaultRenderMode):
	cmd = SPSetOtherMode("G_SETOTHERMODE_L", 0, 32, [])
	cmd.flagList.append(settings.g_mdsft_alpha_compare)
	cmd.flagList.append(settings.g_mdsft_zsrcsel)

	if settings.set_rendermode:
		flagList, blendList = getRenderModeFlagList(settings, fMaterial)
		cmd.flagList.extend(flagList)
		if blendList is not None:
			cmd.flagList.extend(blendList)
	else:
		cmd.flagList.extend(defaultRenderMode)
	fMaterial.material.commands.append(cmd)

def saveOtherModeLDefinitionIndividual(fMaterial, settings, defaults, defaultRenderMode):
	saveModeSetting(fMaterial, settings.g_mdsft_alpha_compare,
		defaults.g_mdsft_alpha_compare, DPSetAlphaCompare)

	saveModeSetting(fMaterial, settings.g_mdsft_zsrcsel,
		defaults.g_mdsft_zsrcsel, DPSetDepthSource)

	if settings.set_rendermode:
		flagList, blendList = getRenderModeFlagList(settings, fMaterial)
		renderModeSet = DPSetRenderMode(flagList, blendList)

		fMaterial.material.commands.append(renderModeSet)
		if defaultRenderMode is not None:
			fMaterial.revert.commands.append(DPSetRenderMode(defaultRenderMode, None))

def getRenderModeFlagList(settings, fMaterial):
	flagList = []
	blendList = None
	# cycle independent
	
	if not settings.rendermode_advanced_enabled:
		fMaterial.renderModeUseDrawLayer = [
			settings.rendermode_preset_cycle_1 == 'Use Draw Layer',
			settings.rendermode_preset_cycle_2 == 'Use Draw Layer']

		if settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
			flagList = [
				settings.rendermode_preset_cycle_1, 
				settings.rendermode_preset_cycle_2]
		else: # ???
			flagList = [
				settings.rendermode_preset_cycle_1, 
				settings.rendermode_preset_cycle_2]
	else:
		if settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
			blendList = \
				[settings.blend_p1, settings.blend_a1, 
				settings.blend_m1, settings.blend_b1,
				settings.blend_p2, settings.blend_a2, 
				settings.blend_m2, settings.blend_b2]
		else:
			blendList = \
				[settings.blend_p1, settings.blend_a1, 
				settings.blend_m1, settings.blend_b1,
				settings.blend_p1, settings.blend_a1, 
				settings.blend_m1, settings.blend_b1]

		if settings.aa_en:
			flagList.append("AA_EN")
		if settings.z_cmp:
			flagList.append("Z_CMP")
		if settings.z_upd:
			flagList.append("Z_UPD")
		if settings.im_rd:
			flagList.append("IM_RD")
		if settings.clr_on_cvg:
			flagList.append("CLR_ON_CVG")

		flagList.append(settings.cvg_dst)
		flagList.append(settings.zmode)

		if settings.cvg_x_alpha:
			flagList.append("CVG_X_ALPHA")
		if settings.alpha_cvg_sel:
			flagList.append("ALPHA_CVG_SEL")
		if settings.force_bl:
			flagList.append("FORCE_BL")

	return flagList, blendList

def saveOtherDefinition(fMaterial, material, defaults):
	settings = material.rdp_settings
	if settings.clip_ratio != defaults.clip_ratio:
		fMaterial.material.commands.append(SPClipRatio(settings.clip_ratio))
		fMaterial.revert.commands.append(SPClipRatio(defaults.clip_ratio))
	
	if material.set_blend:
		fMaterial.material.commands.append(
			DPSetBlendColor(
			int(material.blend_color[0] * 255), 
			int(material.blend_color[1] * 255), 
			int(material.blend_color[2] * 255),
			int(material.blend_color[3] * 255)))
