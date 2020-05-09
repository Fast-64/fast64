import bpy
import bmesh
import mathutils
from math import pi
from io import BytesIO
import os, re

import copy
from math import pi, ceil
from .utility import *
from .sm64_constants import *
from .f3d_material import all_combiner_uses, getMaterialScrollDimensions
from .f3d_gbi import *
from .f3d_gbi import _DPLoadTextureBlock
from .sm64_texscroll import *

bitSizeDict = {
	'G_IM_SIZ_4b' : 4,
	'G_IM_SIZ_8b' : 8,
	'G_IM_SIZ_16b' : 16,
	'G_IM_SIZ_32b' : 32,
}

texBitSizeOf = {
	'I4' : 'G_IM_SIZ_4b',
	'IA4' : 'G_IM_SIZ_4b',
	'CI4' : 'G_IM_SIZ_4b',
	'I8' : 'G_IM_SIZ_8b',
	'IA8' : 'G_IM_SIZ_8b',
	'CI8' : 'G_IM_SIZ_8b',
	'RGBA16' : 'G_IM_SIZ_16b',
	'IA16' : 'G_IM_SIZ_16b',
	'YUV16' : 'G_IM_SIZ_16b',
	'RGBA32' : 'G_IM_SIZ_32b',
}

texFormatOf = {
	'I4' : 'G_IM_FMT_I',
	'IA4' : 'G_IM_FMT_IA',
	'CI4' : 'G_IM_FMT_CI',
	'I8' : 'G_IM_FMT_I',
	'IA8' : 'G_IM_FMT_IA',
	'CI8' : 'G_IM_FMT_CI',
	'RGBA16' : 'G_IM_FMT_RGBA',
	'IA16' : 'G_IM_FMT_IA',
	'YUV16' : 'G_IM_FMT_YUV',
	'RGBA32' : 'G_IM_FMT_RGBA',
}

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
	if len(obj.data.materials) == 0:
		raise PluginError("Mesh does not have any Fast3D materials.")
	infoDict = {
		'vert' : {}, # all faces connected to a vert
		'edge' : {}, # all faces connected to an edge
		'f3dVert' : {}, # f3d vertex of a given loop
		'edgeValid' : {}, # bool given two faces
		'validNeighbors' : {} # all neighbors of a face with a valid connecting edge
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
		if mesh.materials[face.material_index] is None:
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

def fixLargeUVs(obj, faces, size):
	obj.data.calc_loop_triangles()
	obj.data.calc_normals_split()

	uv_data = obj.data.uv_layers['UVMap'].data

	for face in faces:
		rangeU = [0,0]
		rangeV = [0,0]
		for loopIndex in face.loops:
			#loop = obj.data.loops[loopIndex]
			uv = uv_data[loopIndex].uv
			rangeU[0] = min(uv[0] * size[0], rangeU[0])
			rangeU[1] = max(uv[0] * size[0], rangeU[1])
			rangeV[0] = min(uv[1] * size[1], rangeV[0])
			rangeV[1] = max(uv[1] * size[1], rangeV[1])

		totalAmount = [0,0]
		totalAmount[0] = handleLargeUV(rangeU, size[0]) / size[0]
		totalAmount[1] = handleLargeUV(rangeV, size[1]) / size[1]
		
		if totalAmount[0] != 0 and totalAmount[1] != 0:
			print(str(totalAmount) + " : " + str(uv_data[face.loops[0]].uv) + ", " + \
				str(uv_data[face.loops[1]].uv) + ", " + str(uv_data[face.loops[2]].uv))
			addUV(face, totalAmount, uv_data)

def handleLargeUV(valueRange, size):
	totalAmount = 0

	if valueRange[1] > 1024:
		amount = ceil((valueRange[1] - 1024) / size) * size + size 	
		totalAmount -= amount
		valueRange[0] -= amount
		valueRange[1] -= amount
	
	if valueRange[0] < -1024:
		amount = ceil(-(valueRange[0] + 1024) / size) * size + size 
		totalAmount += amount
		valueRange[0] += amount
		valueRange[1] += amount
	
	return totalAmount

def addUV(face, amount, uv_data):
	for loopIndex in face.loops:
		uv_data[loopIndex].uv =\
			(uv_data[loopIndex].uv[0] + amount[0],
			uv_data[loopIndex].uv[1] + amount[1])


# Make sure to set original_name before calling this
# used when duplicating an object
def saveStaticModel(fModel, obj, transformMatrix, name, DLFormat):
	if len(obj.data.polygons) == 0:
		return None
	
	#checkForF3DMaterial(obj)

	obj.data.calc_loop_triangles()
	obj.data.calc_normals_split()
	infoDict = getInfoDict(obj)

	fMeshGroup = FMeshGroup(toAlnum(name + "_" + obj.original_name), 
		FMesh(toAlnum(name + "_" + obj.original_name) + '_mesh', DLFormat), None, DLFormat)
	fModel.meshGroups[name + "_" + obj.original_name] = fMeshGroup

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
			infoDict, int(obj.draw_layer_static))
	
	revertMatAndEndDraw(fMeshGroup.mesh.draw, [])
	return fMeshGroup

def addCullCommand(obj, fMesh, transformMatrix):
	fMesh.add_cull_vtx()
	for vertexPos in obj.bound_box:
		# Most other fields of convertVertexData are unnecessary for bounding box verts
		fMesh.cullVertexList.vertices.append(
			convertVertexData(obj.data, 
				mathutils.Vector(vertexPos), [0,0], 
				mathutils.Vector([0,0,0]), [32, 32],
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

def exportTexRectToC(dirPath, texProp, f3dType, isHWv1, texDir, 
	savePNG, name, exportToProject, projectExportData):
	fTexRect = exportTexRectCommon(texProp, f3dType, isHWv1, name)

	if name is None or name == '':
		raise PluginError("Name cannot be empty.")

	data, code = fTexRect.to_c(savePNG, texDir)
	declaration = fTexRect.to_c_def_tex()
	code = modifyDLForHUD(code)

	if exportToProject:	
		seg2CPath = os.path.join(dirPath, "bin/segment2.c")
		seg2HPath = os.path.join(dirPath, "src/game/segment2.h")
		seg2TexDir = os.path.join(dirPath, "textures/segment2")
		hudPath = os.path.join(dirPath, projectExportData[0])

		checkIfPathExists(seg2CPath)
		checkIfPathExists(seg2HPath)
		checkIfPathExists(seg2TexDir)
		checkIfPathExists(hudPath)
		
		if savePNG:
			fTexRect.save_textures(seg2TexDir)

		textures = []
		for info, texture in fTexRect.textures.items():
			textures.append(texture)

		# Append/Overwrite texture definition to segment2.c
		overwriteData('const\s*u8\s*', textures[0].name, data, seg2CPath, None, False)
			
		# Append texture declaration to segment2.h
		writeIfNotFound(seg2HPath, declaration, '#endif')

		# Write/Overwrite function to hud.c
		overwriteData('void\s*', fTexRect.name, code, hudPath, projectExportData[1], True)

	else:
		singleFileData = ''
		singleFileData += '// Copy this function to src/game/hud.c or src/game/ingame_menu.c.\n'
		singleFileData += '// Call the function in render_hud() or render_menus_and_dialogs() respectively.\n'
		singleFileData += code
		singleFileData += '// Copy this declaration to src/game/segment2.h.\n'
		singleFileData += declaration
		singleFileData += '// Copy this texture data to bin/segment2.c\n'
		singleFileData += '// If texture data is being included from an inc.c, make sure to copy the png to textures/segment2.\n'
		singleFileData += data
		singleFilePath = os.path.join(dirPath, fTexRect.name + '.c')
		singleFile = open(singleFilePath, 'w', newline='\n')
		singleFile.write(singleFileData)
		singleFile.close()

	if bpy.context.mode != 'OBJECT':
		bpy.ops.object.mode_set(mode = 'OBJECT')

def modifyDLForHUD(data):
	# Use sm64 master dl pointer
	data = re.sub('glistp', 'gDisplayListHead', data)

	# Add positional arguments to drawing, along with negative pos handling
	negativePosHandling = \
		'\ts32 xl = MAX(0, x);\n' +\
    	'\ts32 yl = MAX(0, y);\n' +\
		'\ts32 xh = MAX(0, x + width - 1);\n' +\
    	'\ts32 yh = MAX(0, y + height - 1);\n' +\
    	'\ts = (x < 0) ? s - x : s;\n' +\
    	'\tt = (y < 0) ? t - y : t;\n'
		
	data = re.sub('Gfx\* gDisplayListHead\) \{\n', 
		's32 x, s32 y, s32 width, s32 height, s32 s, s32 t) {\n' + \
		negativePosHandling, data)

	# Remove display list end command and return value
	data = re.sub('\tgSPEndDisplayList\(gDisplayListHead\+\+\)\;\n\treturn gDisplayListHead;\n', '', data)
	data = 'void' + data[4:]

	# Apply positional arguments to SPScisTextureRectangle
	matchResult = re.search('gSPScisTextureRectangle\(gDisplayListHead\+\+\,' + \
		' (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\,', data)
	if matchResult:
		#data = data[:matchResult.start(0)] + \
		#	'gSPScisTextureRectangle(gDisplayListHead++, (x << 2) + ' + \
		#	matchResult.group(1) + ', (y << 2) + ' + \
		#	matchResult.group(3) + ', (x << 2) + ' + \
		#	matchResult.group(5) + ', (y << 2) + ' + \
		#	matchResult.group(7) + ',' + data[matchResult.end(0):]
		data = data[:matchResult.start(0)] + \
			'gSPTextureRectangle(gDisplayListHead++, ' +\
			'xl << 2, yl << 2, xh << 2, yh << 2, ' +\
			matchResult.group(11) + ', s << 5, t << 5, ' + data[matchResult.end(0):]

	# Make sure to convert segmented texture pointer to virtual
	#matchResult = re.search('gDPSetTextureImage\(gDisplayListHead\+\+\,' +\
	#	'(((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\)', data)
	#if matchResult:
	#	data = data[:matchResult.start(7)] + 'segmented_to_virtual(&' + \
	#		matchResult.group(7) + ")" +data[matchResult.end(7):]
	
	return data

def exportTexRectCommon(texProp, f3dType, isHWv1, name):
	tex = texProp.tex
	if tex is None:
		raise PluginError('No texture is selected.')
	
	texProp.S.low = 0
	texProp.S.high = texProp.tex.size[0] - 1
	texProp.S.mask =  math.ceil(math.log(texProp.tex.size[0], 2) - 0.001)
	texProp.S.shift = 0

	texProp.T.low = 0
	texProp.T.high = texProp.tex.size[1] - 1
	texProp.T.mask =  math.ceil(math.log(texProp.tex.size[1], 2) - 0.001)
	texProp.T.shift = 0

	fTexRect = FTexRect(f3dType, isHWv1, toAlnum(name))

	# dl_hud_img_begin
	fTexRect.draw.commands.extend([
		DPPipeSync(),
		DPSetCycleType('G_CYC_COPY'),
		DPSetTexturePersp('G_TP_NONE'),
		DPSetAlphaCompare('G_AC_THRESHOLD'),
		DPSetBlendColor(0xFF, 0xFF, 0xFF, 0xFF),
		DPSetRenderMode(['G_RM_AA_XLU_SURF', 'G_RM_AA_XLU_SURF2'], None)
	])

	drawEndCommands = GfxList("temp", "Dynamic")

	texDimensions, nextTmem = saveTextureIndex(texProp.tex.name, fTexRect, 
		fTexRect.draw, drawEndCommands, texProp, 0, 0, 'texture')

	fTexRect.draw.commands.append(
		SPScisTextureRectangle(0, 0, 
			(texDimensions[0] - 1) << 2, (texDimensions[1] - 1) << 2,
			0, 0, 0)
	)

	fTexRect.draw.commands.extend(drawEndCommands.commands)

	# dl_hud_img_end
	fTexRect.draw.commands.extend([
		DPPipeSync(),
		DPSetCycleType('G_CYC_1CYCLE'),
		SPTexture(0xFFFF, 0xFFFF, 0, 'G_TX_RENDERTILE', 'G_OFF'),
		DPSetTexturePersp('G_TP_PERSP'),
		DPSetAlphaCompare('G_AC_NONE'),
		DPSetRenderMode(['G_RM_AA_ZB_OPA_SURF', 'G_RM_AA_ZB_OPA_SURF2'], None),
		SPEndDisplayList()
	])
	
	return fTexRect

def exportF3DCommon(obj, f3dType, isHWv1, transformMatrix, includeChildren, name, DLFormat):
	fModel = FModel(f3dType, isHWv1, name, DLFormat)

	tempObj, meshList = combineObjects(obj, includeChildren, None, None)
	try:
		fMeshGroup = saveStaticModel(fModel, tempObj, transformMatrix, name, DLFormat)
		cleanupCombineObj(tempObj, meshList)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
	except Exception as e:
		cleanupCombineObj(tempObj, meshList)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		raise Exception(str(e))

	return fModel, fMeshGroup

def exportF3DtoC(basePath, obj, DLFormat, transformMatrix, 
	f3dType, isHWv1, texDir, savePNG, texSeparate, includeChildren, name, levelName, groupName, customExport, headerType):
	dirPath, texDir = getExportDir(customExport, basePath, headerType, 
		levelName, texDir, name)

	fModel, fMeshGroup = \
		exportF3DCommon(obj, f3dType, isHWv1, transformMatrix, 
		includeChildren, name, DLFormat)

	modelDirPath = os.path.join(dirPath, toAlnum(name))

	if not os.path.exists(modelDirPath):
		os.mkdir(modelDirPath)

	if headerType == 'Actor':
		scrollName = 'actor_dl_' + name
	elif headerType == 'Level':
		scrollName = levelName + '_level_dl_' + name

	static_data, dynamic_data, texC, scroll_data = fModel.to_c(texSeparate, savePNG, texDir, scrollName)
	cDefineStatic, cDefineDynamic, cDefineScroll = fModel.to_c_def(scrollName)

	if not bpy.context.scene.disableScroll:
		writeTexScrollFiles(basePath, modelDirPath, cDefineScroll, scroll_data)
	
	if DLFormat == "Static":
		static_data += '\n' + dynamic_data
		cDefineStatic += cDefineDynamic
	else:
		geoString = writeMaterialFiles(basePath, modelDirPath, 
			'#include "actors/' + toAlnum(name) + '/header.h"', 
			'#include "actors/' + toAlnum(name) + '/material.inc.h"',
			cDefineDynamic, dynamic_data, '', customExport)

	if savePNG:
		fModel.save_textures(modelDirPath)

	fModel.freePalettes()

	if texSeparate:
		texCFile = open(os.path.join(modelDirPath, 'texture.inc.c'), 'w', newline='\n')
		texCFile.write(texC)
		texCFile.close()

	modelPath = os.path.join(modelDirPath, 'model.inc.c')
	outFile = open(modelPath, 'w', newline='\n')
	outFile.write(static_data)
	outFile.close()
		
	headerPath = os.path.join(modelDirPath, 'header.h')
	cDefFile = open(headerPath, 'w', newline='\n')
	cDefFile.write(cDefineStatic)
	cDefFile.close()
		
	if not customExport:
		if headerType == 'Actor':
			# Write to group files
			if groupName == '' or groupName is None:
				raise PluginError("Actor header type chosen but group name not provided.")

			groupPathC = os.path.join(dirPath, groupName + ".c")
			groupPathH = os.path.join(dirPath, groupName + ".h")

			writeIfNotFound(groupPathC, '\n#include "' + toAlnum(name) + '/model.inc.c"', '')
			writeIfNotFound(groupPathH, '\n#include "' + toAlnum(name) + '/header.h"', '\n#endif')

			if DLFormat != "Static": # Change this
				writeMaterialHeaders(basePath, 
					'#include "actors/' + toAlnum(name) + '/material.inc.c"',
					'#include "actors/' + toAlnum(name) + '/material.inc.h"')

			texscrollIncludeC = '#include "actors/' + name + '/texscroll.inc.c"'
			texscrollIncludeH = '#include "actors/' + name + '/texscroll.inc.h"'
			texscrollGroup = groupName
			texscrollGroupInclude = '#include "actors/' + groupName + '.h"'
		
		elif headerType == 'Level':
			groupPathC = os.path.join(dirPath, "leveldata.c")
			groupPathH = os.path.join(dirPath, "header.h")

			writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + '/' + \
				toAlnum(name) + '/model.inc.c"', '')
			writeIfNotFound(groupPathH, '\n#include "levels/' + levelName + '/' + \
				toAlnum(name) + '/header.h"', '\n#endif')

			if DLFormat != "Static": # Change this
				writeMaterialHeaders(basePath,
					'#include "levels/' + levelName + '/' + toAlnum(name) + '/material.inc.c"',
					'#include "levels/' + levelName + '/' + toAlnum(name) + '/material.inc.h"')
			
			texscrollIncludeC = '#include "levels/' + levelName + '/' + name + '/texscroll.inc.c"'
			texscrollIncludeH = '#include "levels/' + levelName + '/' + name + '/texscroll.inc.h"'
			texscrollGroup = levelName
			texscrollGroupInclude = '#include "levels/' + levelName + '/header.h"'

		if not bpy.context.scene.disableScroll:
			writeTexScrollHeadersGroup(basePath, texscrollIncludeC, texscrollIncludeH, 
				texscrollGroup, cDefineScroll, texscrollGroupInclude)

	if bpy.context.mode != 'OBJECT':
		bpy.ops.object.mode_set(mode = 'OBJECT')

def exportF3DtoBinary(romfile, exportRange, transformMatrix, 
	obj, f3dType, isHWv1, segmentData, includeChildren):
	fModel, fMeshGroup = exportF3DCommon(obj, f3dType, isHWv1, 
		transformMatrix, includeChildren, obj.name, "Static")
	fModel.freePalettes()

	addrRange = fModel.set_addr(exportRange[0])
	if addrRange[1] > exportRange[1]:
		raise PluginError('Size too big: Data ends at ' + hex(addrRange[1]) +\
			', which is larger than the specified range.')
	fModel.save_binary(romfile, segmentData)
	if bpy.context.mode != 'OBJECT':
		bpy.ops.object.mode_set(mode = 'OBJECT')

	segPointerData = encodeSegmentedAddr(
		fMeshGroup.mesh.draw.startAddress, segmentData)

	return fMeshGroup.mesh.draw.startAddress, addrRange, segPointerData

def exportF3DtoBinaryBank0(romfile, exportRange, transformMatrix, 
	obj, f3dType, isHWv1, RAMAddr, includeChildren):
	fModel, fMeshGroup = \
		exportF3DCommon(obj, f3dType, isHWv1, transformMatrix, includeChildren,
			obj.name, "Static")
	segmentData = copy.copy(bank0Segment)

	data, startRAM = getBinaryBank0F3DData(fModel, RAMAddr, exportRange)

	startAddress = get64bitAlignedAddr(exportRange[0])
	romfile.seek(startAddress)
	romfile.write(data)

	if bpy.context.mode != 'OBJECT':
		bpy.ops.object.mode_set(mode = 'OBJECT')

	segPointerData = encodeSegmentedAddr(
		fMeshGroup.mesh.draw.startAddress, segmentData)

	return (fMeshGroup.mesh.draw.startAddress, \
		(startAddress, startAddress + len(data)), segPointerData)

def exportF3DtoInsertableBinary(filepath, transformMatrix, 
	obj, f3dType, isHWv1, includeChildren):
	fModel, fMeshGroup = \
		exportF3DCommon(obj, f3dType, isHWv1, transformMatrix, includeChildren,
			obj.name, "Static")
	
	data, startRAM = getBinaryBank0F3DData(fModel, 0, [0, 0xFFFFFF])
	# must happen after getBinaryBank0F3DData
	address_ptrs = fModel.get_ptr_addresses(f3dType) 

	writeInsertableFile(filepath, insertableBinaryTypes['Display List'],
		address_ptrs, fMeshGroup.mesh.draw.startAddress, data)

def getBinaryBank0F3DData(fModel, RAMAddr, exportRange):
	fModel.freePalettes()
	segmentData = copy.copy(bank0Segment)

	addrRange = fModel.set_addr(RAMAddr)
	if addrRange[1] - RAMAddr > exportRange[1] - exportRange[0]:
	    raise PluginError('Size too big: Data ends at ' + hex(addrRange[1]) +\
	        ', which is larger than the specified range.')

	bytesIO = BytesIO()
	#actualRAMAddr = get64bitAlignedAddr(RAMAddr)
	bytesIO.seek(RAMAddr)
	fModel.save_binary(bytesIO, segmentData)
	data = bytesIO.getvalue()[RAMAddr:]
	bytesIO.close()
	return data, RAMAddr

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

	if gfxList.DLFormat != "Dynamic":
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
	infoDict, drawLayer):
	if len(faces) == 0:
		print('0 Faces Provided.')
		return
	fMaterial, texDimensions = \
		saveOrGetF3DMaterial(material, fModel, obj, drawLayer)
	#fixLargeUVs(obj, faces, texDimensions)
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

def get8bitRoundedNormal(normal):
	return mathutils.Vector(
		(round(normal[0] * 128) / 128,
		round(normal[1] * 128) / 128,
		round(normal[2] * 128) / 128)
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

def getLoopNormal(loop, face, isFlatShaded):
	# This is a workaround for flat shading not working well.
	# Since we support custom blender normals we can now ignore this.
	#if isFlatShaded:
	#	normal = -face.normal #???
	#else:
	#	normal = -loop.normal #???
	#return get8bitRoundedNormal(normal).freeze()
	return get8bitRoundedNormal(loop.normal).freeze()

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
			0xFF
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
		return getLoopNormal(loop, face, isFlatShaded)

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

def saveOrGetF3DMaterial(material, fModel, obj, drawLayer):
	if material.rdp_settings.set_rendermode:
		if (material, drawLayer) in fModel.materials:
			return fModel.materials[(material, drawLayer)]
	elif (material, None) in fModel.materials:
		return fModel.materials[(material, None)]
	
	if len(obj.data.materials) == 0:
		raise PluginError("Mesh must have at least one material.")
	materialName = fModel.name + "_" + toAlnum(material.name) + (('_layer' + str(drawLayer)) \
		if material.rdp_settings.set_rendermode and drawLayer is not None else '') 
	fMaterial = FMaterial(materialName, "Static" if fModel.DLFormat == "Static" else "Dynamic")
	fMaterial.material.commands.append(DPPipeSync())
	fMaterial.revert.commands.append(DPPipeSync())
	
	if not material.is_f3d:
		raise PluginError("Material named " +  material.name + \
			' is not an F3D material.')

	fMaterial.getScrollData(material, getMaterialScrollDimensions(material))
	
	nodes = material.node_tree.nodes

	if material.set_combiner:
		if material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
			fMaterial.material.commands.append(
				DPSetCombineMode(
					nodes['Case A 1'].inA,
					nodes['Case B 1'].inB,
					nodes['Case C 1'].inC,
					nodes['Case D 1'].inD,
					nodes['Case A Alpha 1'].inA_alpha,
					nodes['Case B Alpha 1'].inB_alpha,
					nodes['Case C Alpha 1'].inC_alpha,
					nodes['Case D Alpha 1'].inD_alpha,
					nodes['Case A 2'].inA,
					nodes['Case B 2'].inB,
					nodes['Case C 2'].inC,
					nodes['Case D 2'].inD,
					nodes['Case A Alpha 2'].inA_alpha,
					nodes['Case B Alpha 2'].inB_alpha,
					nodes['Case C Alpha 2'].inC_alpha,
					nodes['Case D Alpha 2'].inD_alpha
			))
		else:
			fMaterial.material.commands.append(
				DPSetCombineMode(
					nodes['Case A 1'].inA,
					nodes['Case B 1'].inB,
					nodes['Case C 1'].inC,
					nodes['Case D 1'].inD,
					nodes['Case A Alpha 1'].inA_alpha,
					nodes['Case B Alpha 1'].inB_alpha,
					nodes['Case C Alpha 1'].inC_alpha,
					nodes['Case D Alpha 1'].inD_alpha,
					nodes['Case A 1'].inA,
					nodes['Case B 1'].inB,
					nodes['Case C 1'].inC,
					nodes['Case D 1'].inD,
					nodes['Case A Alpha 1'].inA_alpha,
					nodes['Case B Alpha 1'].inB_alpha,
					nodes['Case C Alpha 1'].inC_alpha,
					nodes['Case D Alpha 1'].inD_alpha
			))

	if material.set_fog:
		fMaterial.material.commands.extend([
			DPSetFogColor(
				int(round(material.fog_color[0] * 255)),
				int(round(material.fog_color[1] * 255)),
				int(round(material.fog_color[2] * 255)),
				int(round(material.fog_color[3] * 255))),
			SPFogPosition(material.fog_position[0], material.fog_position[1])
		])

	useDict = all_combiner_uses(material)

	defaults = bpy.context.scene.world.rdp_defaults
	saveGeoModeDefinition(fMaterial, material.rdp_settings, defaults)
	saveOtherModeHDefinition(fMaterial, material.rdp_settings, defaults)
	saveOtherModeLDefinition(fMaterial, material.rdp_settings, defaults,
		drawLayerRenderMode[drawLayer] if drawLayer is not None else None)
	saveOtherDefinition(fMaterial, material, defaults)

	# Set scale
	s = int(material.tex_scale[0] * 0xFFFF)
	t = int(material.tex_scale[1] * 0xFFFF)
	fMaterial.material.commands.append(
		SPTexture(s, t, 0, fModel.f3d.G_TX_RENDERTILE, 1))

	# Save textures
	texDimensions0 = None
	texDimensions1 = None
	nextTmem = 0
	if useDict['Texture 0'] and material.tex0.tex_set:
		if material.tex0.tex is None:
			raise PluginError('In material \"' + material.name + '\", a texture has not been set.')
		texDimensions0, nextTmem = saveTextureIndex(material.name, fModel, 
			fMaterial.material, fMaterial.revert, material.tex0, 0, nextTmem, None)	
	if useDict['Texture 1'] and material.tex1.tex_set:
		if material.tex1.tex is None:
			raise PluginError('In material \"' + material.name + '\", a texture has not been set.')
		texDimensions1, nextTmem = saveTextureIndex(material.name, fModel, 
			fMaterial.material, fMaterial.revert, material.tex1, 1, nextTmem, None)

	# Used so we know how to convert normalized UVs when saving verts.
	if texDimensions0 is not None and texDimensions1 is not None:
		texDimensions = texDimensions0 if material.uv_basis == 'TEXEL0' \
			else texDimensions1
	elif texDimensions0 is not None:
		texDimensions = texDimensions0
	elif texDimensions1 is not None:
		texDimensions = texDimensions1
	else:
		texDimensions = [32, 32]

	if useDict['Primitive'] and material.set_prim:
		color = nodes['Primitive Color'].outputs[0].default_value
		color = gammaCorrect(color[0:3]) + [color[3]]
		fMaterial.material.commands.append(
			DPSetPrimColor(
			int(material.prim_lod_min * 255),
			int(material.prim_lod_frac * 255),
			int(color[0] * 255), 
			int(color[1] * 255), 
			int(color[2] * 255),
			int(color[3] * 255)))

	if useDict['Environment'] and material.set_env:	
		color = nodes['Environment Color'].outputs[0].default_value
		color = gammaCorrect(color[0:3]) + [color[3]]
		fMaterial.material.commands.append(
			DPSetEnvColor(
			int(color[0] * 255), 
			int(color[1] * 255), 
			int(color[2] * 255),
			int(color[3] * 255)))
	
	if useDict['Shade'] and material.set_lights:
		fLights = saveLightsDefinition(fModel, material, 
			materialName + '_lights')
		fMaterial.material.commands.extend([
			SPSetLights(fLights) # TODO: handle synching: NO NEED?
		])
	
	if useDict['Key'] and material.set_key:
		center = nodes['Chroma Key Center'].outputs[0].default_value
		scale = nodes['Chroma Key Scale'].outputs[0].default_value
		width = material.key_width
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
	if useDict['Convert'] and material.set_k0_5:
		fMaterial.material.commands.extend([
			DPSetTextureConvert('G_TC_FILTCONV'), # TODO: allow filter option
			DPSetConvert(
				int(material.k0 * 255),
				int(material.k1 * 255),
				int(material.k2 * 255),
				int(material.k3 * 255),
				int(material.k4 * 255),
				int(material.k5 * 255))
		])
		
	# End Display List
	# For dynamic calls, materials will be called as functions and should not end the DL.
	if fModel.DLFormat != 'SM64 Function Node':
		fMaterial.material.commands.append(SPEndDisplayList())

	#revertMatAndEndDraw(fMaterial.revert)
	if len(fMaterial.revert.commands) > 1: # 1 being the pipe sync
		if fMaterial.DLFormat == 'Static':
			fMaterial.revert.commands.append(SPEndDisplayList())
	else:
		fMaterial.revert = None
	
	materialKey = material, (drawLayer if material.rdp_settings.set_rendermode else None)
	fModel.materials[materialKey] = (fMaterial, texDimensions)

	return fMaterial, texDimensions

def saveTextureIndex(propName, fModel, loadTexGfx, revertTexGfx, texProp, index, tmem, overrideName):
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
		

	nextTmem = tmem + ceil(bitSizeDict[texBitSizeOf[texFormat]] * \
		tex.size[0] * tex.size[1] / 64) 
	if nextTmem > (512 if texFormat[:2] != 'CI' else 256):
		print(nextTmem)
		raise PluginError("Error in \"" + propName + "\": Textures are too big. Max TMEM size is 4k " + \
			"bytes, ex. 2 32x32 RGBA 16 bit textures.")
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
			fModel, tex, texName, texFormat, palFormat)
		savePaletteLoading(loadTexGfx, revertTexGfx, fPalette, 
			palFormat, 0, fPalette.height, fModel.f3d)
	else:
		fImage = saveOrGetTextureDefinition(fModel, tex, texName, 
			texFormat)
	saveTextureLoading(fImage, loadTexGfx, clamp_S,
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
def saveTextureLoading(fImage, loadTexGfx, clamp_S, mirror_S, clamp_T,
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
		dxt = f3d.CALC_DXT_4b(fImage.width)
		line = ((fImage.width >> 1) + 7) >> 3

		loadTexGfx.commands.extend([
			DPTileSync(), # added in
			DPSetTextureImage(fmt, 'G_IM_SIZ_8b', fImage.width >> 1, fImage),
			DPSetTile(fmt, 'G_IM_SIZ_8b', line, tmem, 
				f3d.G_TX_LOADTILE - texIndex, 0, cmt, maskt, shiftt, 
			 	cms, masks, shifts),
			DPLoadSync(),
			DPLoadTile(f3d.G_TX_LOADTILE - texIndex, 0, 0,
				(fImage.width - 1) << (f3d.G_TEXTURE_IMAGE_FRAC - 1),
				(fImage.height - 1) << f3d.G_TEXTURE_IMAGE_FRAC),])

	else:
		dxt = f3d.CALC_DXT(fImage.width, f3d.G_IM_SIZ_VARS[siz + '_BYTES'])
		# Note that _LINE_BYTES and _TILE_BYTES variables are the same.
		line = ((fImage.width * \
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
			DPLoadTile(f3d.G_TX_LOADTILE - texIndex, 0, 0,
				(fImage.width - 1) << f3d.G_TEXTURE_IMAGE_FRAC,
				(fImage.height - 1) << f3d.G_TEXTURE_IMAGE_FRAC),]) # added in
	
	loadTexGfx.commands.extend([
		DPPipeSync(),
		DPSetTile(fmt, siz, line, tmem,	\
			f3d.G_TX_RENDERTILE + texIndex, pal, cmt, maskt, \
			shiftt, cms, masks, shifts),
		DPSetTileSize(f3d.G_TX_RENDERTILE + texIndex, sl, tl, sh, th)
	]) # added in)

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
	
def saveOrGetPaletteDefinition(fModelOrTexRect, image, imageName, texFmt, palFmt):
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
		image.size[0], image.size[1], filename)

	fPalette = FImage(checkDuplicateTextureName(fModelOrTexRect, paletteName), palFormat, 'G_IM_SIZ_16b', 1, 
		len(palette), paletteFilename)
	#paletteTex = bpy.data.images.new(paletteName, 1, len(palette))
	#paletteTex.pixels = palette
	#paletteTex.filepath = getNameFromPath(name, True) + '.' + \
	#	texFmt.lower() + '.pal'

	for color in palette:
		fPalette.data.extend(color.to_bytes(2, 'big')) 
	
	if bitSize == 'G_IM_SIZ_4b':
		fImage.data = compactNibbleArray(texture, image.size[0], image.size[1])
	else:	
		fImage.data = bytearray(texture)
	
	fModelOrTexRect.textures[(image, (texFmt, palFmt))] = fImage
	fModelOrTexRect.textures[(image, (palFmt, 'PAL'))] = fPalette

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

def saveOrGetTextureDefinition(fModel, image, imageName, texFormat):
	fmt = texFormatOf[texFormat]
	bitSize = texBitSizeOf[texFormat]

	# If image already loaded, return that data.
	imageKey = (image, (texFormat, 'NONE'))
	if imageKey in fModel.textures:
		return fModel.textures[imageKey]

	if image.filepath == "":
		name = image.name
	else:
		name = image.filepath
	filename = getNameFromPath(name, True) + '.' + \
		texFormat.lower() + '.inc.c'

	fImage = FImage(checkDuplicateTextureName(fModel, toAlnum(imageName)), fmt, bitSize, 
		image.size[0], image.size[1], filename)

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
	
	fModel.textures[(image, (texFormat, 'NONE'))] = fImage
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
	lightObj = None
	for obj in bpy.context.scene.objects:
		if obj.data == f3d_light:
			lightObj = obj
			break
	if lightObj is None:
		raise PluginError(
			"The material \"" + mat.name + "\" is referencing a light that is no longer in the scene (i.e. has been deleted).")
	
	#spaceRot = blenderToSM64Rotation.to_4x4().to_quaternion()
	spaceRot = mathutils.Euler((-pi / 2, 0, 0)).to_quaternion()
	rotation = spaceRot @ getObjectQuaternion(lightObj)
		
	normal = (rotation @ mathutils.Vector((0,0,1))).normalized()
	color = gammaCorrect(f3d_light.color)
	
	fLights.l.append(Light(
		[
			int(color[0] * 255),
			int(color[1] * 255),
			int(color[2] * 255)
		],
		[
			# Make sure to handle negative values
			int.from_bytes(int(normal[0] * 127).to_bytes(1, 'big', 
				signed = True), 'big'),
			int.from_bytes(int(normal[1] * 127).to_bytes(1, 'big', 
				signed = True), 'big'),
			int.from_bytes(int(normal[2] * 127).to_bytes(1, 'big', 
				signed = True), 'big')
		],
	))

def saveBitGeo(value, defaultValue, flagName, setGeo, clearGeo):
	if value != defaultValue:
		if value:
			setGeo.flagList.append(flagName)
		else:
			clearGeo.flagList.append(flagName)

def saveGeoModeDefinition(fMaterial, settings, defaults):
	setGeo = SPSetGeometryMode([])
	clearGeo = SPClearGeometryMode([])

	saveBitGeo(settings.g_zbuffer, defaults.g_zbuffer, 'G_ZBUFFER',
		setGeo, clearGeo)
	saveBitGeo(settings.g_shade, defaults.g_shade, 'G_SHADE',
		setGeo, clearGeo)
	saveBitGeo(settings.g_cull_front, defaults.g_cull_front, 'G_CULL_FRONT',
		setGeo, clearGeo)
	saveBitGeo(settings.g_cull_back,  defaults.g_cull_back, 'G_CULL_BACK',
		setGeo, clearGeo)
	saveBitGeo(settings.g_fog, defaults.g_fog, 'G_FOG', setGeo, clearGeo)
	saveBitGeo(settings.g_lighting, defaults.g_lighting, 'G_LIGHTING',
		setGeo, clearGeo)

	# make sure normals are saved correctly.
	saveBitGeo(settings.g_tex_gen, defaults.g_tex_gen, 'G_TEXTURE_GEN', 
		setGeo, clearGeo)
	saveBitGeo(settings.g_tex_gen_linear, defaults.g_tex_gen_linear,
		'G_TEXTURE_GEN_LINEAR', setGeo, clearGeo)
	saveBitGeo(settings.g_shade_smooth, defaults.g_shade_smooth,
		'G_SHADING_SMOOTH', setGeo, clearGeo)
	if bpy.context.scene.f3d_type == 'F3DEX_GBI_2' or \
		bpy.context.scene.f3d_type == 'F3DEX_GBI':
		saveBitGeo(settings.g_clipping, defaults.g_clipping, 'G_CLIPPING', 
			setGeo, clearGeo)

	if len(setGeo.flagList) > 0:
		fMaterial.material.commands.append(setGeo)
		fMaterial.revert.commands.append(SPClearGeometryMode(setGeo.flagList))
	if len(clearGeo.flagList) > 0:
		fMaterial.material.commands.append(clearGeo)
		fMaterial.revert.commands.append(SPSetGeometryMode(clearGeo.flagList))

def saveModeSetting(fMaterial, value, defaultValue, cmdClass):
	if value != defaultValue:
		fMaterial.material.commands.append(cmdClass(value))
		fMaterial.revert.commands.append(cmdClass(defaultValue))

def saveOtherModeHDefinition(fMaterial, settings, defaults):
	saveModeSetting(fMaterial, settings.g_mdsft_alpha_dither,
		defaults.g_mdsft_alpha_dither, DPSetAlphaDither)

	if not bpy.context.scene.isHWv1:
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

	if bpy.context.scene.isHWv1:
		saveModeSetting(fMaterial, settings.g_mdsft_color_dither,
			defaults.g_mdsft_color_dither, DPSetColorDither)
	
	saveModeSetting(fMaterial, settings.g_mdsft_pipeline,
		defaults.g_mdsft_pipeline, DPPipelineMode)

def saveOtherModeLDefinition(fMaterial, settings, defaults, defaultRenderMode):
	saveModeSetting(fMaterial, settings.g_mdsft_alpha_compare,
		defaults.g_mdsft_alpha_compare, DPSetAlphaCompare)

	saveModeSetting(fMaterial, settings.g_mdsft_zsrcsel,
		defaults.g_mdsft_zsrcsel, DPSetDepthSource)

	# cycle independent
	if settings.set_rendermode:
		if not settings.rendermode_advanced_enabled:
			fMaterial.renderModeUseDrawLayer = [
				settings.rendermode_preset_cycle_1 == 'Use Draw Layer',
				settings.rendermode_preset_cycle_2 == 'Use Draw Layer']

			if settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
				renderModeSet = DPSetRenderMode([
					settings.rendermode_preset_cycle_1, 
					settings.rendermode_preset_cycle_2], None)
			else: # ???
				renderModeSet = DPSetRenderMode([
					settings.rendermode_preset_cycle_1, 
					settings.rendermode_preset_cycle_2], None)
		else:
			if settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
				renderModeSet = DPSetRenderMode([], 
					[[settings.blend_p1, settings.blend_a1, 
					settings.blend_m1, settings.blend_b1],
					[settings.blend_p2, settings.blend_a2, 
					settings.blend_m2, settings.blend_b2]])
			else:
				renderModeSet = DPSetRenderMode([], 
					[[settings.blend_p1, settings.blend_a1, 
					settings.blend_m1, settings.blend_b1],
					[settings.blend_p1, settings.blend_a1, 
					settings.blend_m1, settings.blend_b1]])

			if settings.aa_en:
				renderModeSet.flagList.append("AA_EN")
			if settings.z_cmp:
				renderModeSet.flagList.append("Z_CMP")
			if settings.z_upd:
				renderModeSet.flagList.append("Z_UPD")
			if settings.im_rd:
				renderModeSet.flagList.append("IM_RD")
			if settings.clr_on_cvg:
				renderModeSet.flagList.append("CLR_ON_CVG")

			renderModeSet.flagList.append(settings.cvg_dst)
			renderModeSet.flagList.append(settings.zmode)

			if settings.cvg_x_alpha:
				renderModeSet.flagList.append("CVG_X_ALPHA")
			if settings.alpha_cvg_sel:
				renderModeSet.flagList.append("ALPHA_CVG_SEL")
			if settings.force_bl:
				renderModeSet.flagList.append("FORCE_BL")
			
		fMaterial.material.commands.append(renderModeSet)
		if defaultRenderMode is not None:
			fMaterial.revert.commands.append(
				DPSetRenderMode(defaultRenderMode, None))
		#fMaterial.revert.commands.append(defaultRenderMode)

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
