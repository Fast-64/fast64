import shutil

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import TextureProperty, tmemUsageUI
from .sm64_texscroll import *
from bpy.utils import register_class, unregister_class
from .sm64_constants import level_enums, enumLevelNames
from .sm64_level_parser import parseLevelAtPointer
from .sm64_rom_tweaks import ExtendBank0x04
from .sm64_constants import level_pointers, defaultExtendSegment4, bank0Segment

enumHUDExportLocation = [
	('HUD', 'HUD', 'Exports to src/game/hud.c'),
	('Menu', 'Menu', 'Exports to src/game/ingame_menu.c')
]

# filepath, function to insert before
enumHUDPaths = {
	"HUD" : ('src/game/hud.c', 'void render_hud(void)'),
	'Menu' : ('src/game/ingame_menu.c', 's16 render_menus_and_dialogs()'),
}

class SM64GfxFormatter(GameGfxFormatter):
	def __init__(self):
		self.functionNodeDraw = False
		GameGfxFormatter.__init__(self)

	def vertexScrollToC(self, fScrollData, name, count):
		if fScrollData.fields[0].animType == "None" and\
			fScrollData.fields[1].animType == "None":
			return ''

		data = 'void scroll_' + name + "() {\n" +\
			"\tint i = 0;\n" +\
			"\tint count = " + str(count) + ';\n' +\
			"\tint width = " + str(fScrollData.dimensions[0]) + ' * 0x20;\n' +\
			"\tint height = " + str(fScrollData.dimensions[1]) + ' * 0x20;'
		
		variables = ""
		currentVars = ""
		deltaCalculate = ""
		checkOverflow = ""
		scrolling = ""
		increaseCurrentDelta = ""
		for i in range(2):
			field = 'XYZ'[i]
			axis = ['width', 'height'][i]
			if fScrollData.fields[i].animType != "None":
				currentVars += "\tstatic int current" + field + ' = 0;\n\tint delta' + field + ';\n'
				checkOverflow += '\tif (absi(current' + field + ') > ' + axis + ') {\n' +\
					'\t\tdelta' + field + ' -= (int)(absi(current' + field + ') / ' +  axis + ') * ' + axis +\
					' * signum_positive(delta' + field + ');\n\t}\n'
				scrolling += '\t\tvertices[i].n.tc[' + str(i) + '] += delta' + field + ';\n'
				increaseCurrentDelta += '\tcurrent' + field + ' += delta' + field + ';\n'

				if fScrollData.fields[i].animType == "Linear":
					deltaCalculate += '\tdelta' + field + ' = (int)(' + str(fScrollData.fields[i].speed) + ' * 0x20) % ' + axis + ';\n'
				elif fScrollData.fields[i].animType == "Sine":
					currentVars += '\tstatic int time' + field + ';\n' +\
						'\tfloat amplitude' + field + ' = ' + str(fScrollData.fields[i].amplitude) + ';\n' +\
						'\tfloat frequency' + field + ' = ' + str(fScrollData.fields[i].frequency) + ';\n' +\
						'\tfloat offset' + field + ' = ' + str(fScrollData.fields[i].offset) + ';\n'

					deltaCalculate += '\tdelta' + field + ' = (int)(amplitude' + field + ' * frequency' +\
						field + ' * coss((frequency' + field + ' * time' + field + ' + offset' + field + \
						') * (1024 * 16 - 1) / 6.28318530718) * 0x20);\n'
					# Conversion from s10.5 to u16
					#checkOverflow += '\tif (frequency' + field + ' * current' + field + ' / 2 > 6.28318530718) {\n' +\
					#	'\t\tcurrent' + field + ' -= 6.28318530718 * 2 / frequency' + field + ';\n\t}\n'
					increaseCurrentDelta += '\ttime' + field + ' += 1;\n'
				elif fScrollData.fields[i].animType == "Noise":
					deltaCalculate += '\tdelta' + field + ' = (int)(' + str(fScrollData.fields[i].noiseAmplitude) + ' * 0x20 * ' +\
						'random_float() * random_sign()) % ' + axis + ';\n'
				else:
					raise PluginError("Unhandled scroll type: " + str(fScrollData.fields[i].animType))

		return data + '\n' + variables + '\n' + currentVars +\
			'\tVtx *vertices = segmented_to_virtual(' + name + ');\n\n' +\
			deltaCalculate + '\n' + checkOverflow + '\n' +\
			"\tfor (i = 0; i < count; i++) {\n" +\
			scrolling + '\t}\n' + increaseCurrentDelta + '\n}\n'

	def vertexScrollToCDef(self, fScrollData, name):
		if (fScrollData.fields[0].animType == "None") and\
			(fScrollData.fields[1].animType == "None"):
			return ''
		
		return 'extern void scroll_' + name + "();\n"

	def drawToC(self, f3d, gfxList):
		if self.functionNodeDraw:
			data = 'Gfx* ' + self.name + '(s32 renderContext, struct GraphNode* node, struct AllocOnlyPool *a2) {\n' +\
				'\tGfx* startCmd = NULL;\n' +\
				'\tGfx* glistp = NULL;\n' +\
				'\tstruct GraphNodeGenerated *generatedNode;\n' +\
				'\tif(renderContext == GEO_CONTEXT_RENDER) {\n' +\
				'\t\tgeneratedNode = (struct GraphNodeGenerated *) node;\n' +\
				'\t\tgeneratedNode->fnNode.node.flags = (generatedNode->fnNode.node.flags & 0xFF) | (generatedNode->parameter << 8);\n' +\
				'\t\tstartCmd = glistp = alloc_display_list(sizeof(Gfx) * ' + \
				str(int(round(self.size_total(f3d) / GFX_SIZE))) + ');\n' +\
				'\t\tif(startCmd == NULL) return NULL;\n'

			for command in self.commands:
				data += '\t\t' + command.to_c(False) + ';\n'
			data += '\t}\n\treturn startCmd;\n}'	
			return data
		else:
			return gfxList.to_c(f3d)

	def drawToCDef(self, gfxList):
		if self.functionNodeDraw:
			return 'Gfx* ' + self.name + '(s32 renderContext, struct GraphNode* node, struct AllocOnlyPool *a2);\n'
		else:
			return gfxList.to_c_def()

def exportTexRectToC(dirPath, texProp, f3dType, isHWv1, texDir, 
	savePNG, name, exportToProject, projectExportData):
	fTexRect = exportTexRectCommon(texProp, f3dType, isHWv1, name, not savePNG)

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
			'gSPScisTextureRectangle(gDisplayListHead++, ' +\
			'xl << 2, yl << 2, xh << 2, yh << 2, ' +\
			matchResult.group(11) + ', s << 5, t << 5, ' + data[matchResult.end(0):]

	# Make sure to convert segmented texture pointer to virtual
	#matchResult = re.search('gDPSetTextureImage\(gDisplayListHead\+\+\,' +\
	#	'(((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\)', data)
	#if matchResult:
	#	data = data[:matchResult.start(7)] + 'segmented_to_virtual(&' + \
	#		matchResult.group(7) + ")" +data[matchResult.end(7):]
	
	return data

def exportTexRectCommon(texProp, f3dType, isHWv1, name, convertTextureData):
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

	drawEndCommands = GfxList("temp", DLFormat.Dynamic)

	texDimensions, nextTmem = saveTextureIndex(texProp.tex.name, fTexRect, 
		fTexRect, fTexRect.draw, drawEndCommands, texProp, 0, 0, 'texture', convertTextureData)

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

def exportF3DtoC(basePath, obj, DLFormat, transformMatrix, 
	f3dType, isHWv1, texDir, savePNG, texSeparate, includeChildren, name, levelName, groupName, customExport, headerType):
	dirPath, texDir = getExportDir(customExport, basePath, headerType, 
		levelName, texDir, name)

	fModel, fMeshGroup = \
		exportF3DCommon(obj, f3dType, isHWv1, transformMatrix, 
		includeChildren, name, DLFormat, not savePNG)

	modelDirPath = os.path.join(dirPath, toAlnum(name))

	if not os.path.exists(modelDirPath):
		os.mkdir(modelDirPath)

	if headerType == 'Actor':
		scrollName = 'actor_dl_' + name
	elif headerType == 'Level':
		scrollName = levelName + '_level_dl_' + name

	gfxFormatter = SM64GfxFormatter()
	static_data, dynamic_data, texC = fModel.to_c(texSeparate, savePNG, texDir, gfxFormatter)
	scroll_data, hasScrolling = fModel.to_c_vertex_scroll(scrollName, gfxFormatter)
	cDefineStatic, cDefineDynamic = fModel.to_c_def(gfxFormatter)
	cDefineScroll = fModel.to_c_vertex_scroll_def(scrollName, gfxFormatter) 

	modifyTexScrollFiles(basePath, modelDirPath, cDefineScroll, scroll_data, hasScrolling)
	
	if DLFormat == DLFormat.Static:
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

			if DLFormat != DLFormat.Static: # Change this
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

			if DLFormat != DLFormat.Static: # Change this
				writeMaterialHeaders(basePath,
					'#include "levels/' + levelName + '/' + toAlnum(name) + '/material.inc.c"',
					'#include "levels/' + levelName + '/' + toAlnum(name) + '/material.inc.h"')
			
			texscrollIncludeC = '#include "levels/' + levelName + '/' + name + '/texscroll.inc.c"'
			texscrollIncludeH = '#include "levels/' + levelName + '/' + name + '/texscroll.inc.h"'
			texscrollGroup = levelName
			texscrollGroupInclude = '#include "levels/' + levelName + '/header.h"'

		modifyTexScrollHeadersGroup(basePath, texscrollIncludeC, texscrollIncludeH, 
			texscrollGroup, cDefineScroll, texscrollGroupInclude, hasScrolling)

	if bpy.context.mode != 'OBJECT':
		bpy.ops.object.mode_set(mode = 'OBJECT')

def exportF3DtoBinary(romfile, exportRange, transformMatrix, 
	obj, f3dType, isHWv1, segmentData, includeChildren):
	fModel, fMeshGroup = exportF3DCommon(obj, f3dType, isHWv1, 
		transformMatrix, includeChildren, obj.name, DLFormat.Static, True)
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
			obj.name, DLFormat.Static, True)
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
			obj.name, DLFormat.Static, True)
	
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

class SM64_ExportDL(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_dl'
	bl_label = "Export Display List"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		romfileOutput = None
		tempROM = None
		try:
			if context.mode != 'OBJECT':
				raise PluginError("Operator can only be used in object mode.")	
			allObjs = context.selected_objects
			if len(allObjs) == 0:
				raise PluginError("No objects selected.")
			obj = context.selected_objects[0]
			if not isinstance(obj.data, bpy.types.Mesh):
				raise PluginError("Object is not a mesh.")

			#T, R, S = obj.matrix_world.decompose()
			#objTransform = R.to_matrix().to_4x4() @ \
			#	mathutils.Matrix.Diagonal(S).to_4x4()

			#finalTransform = (blenderToSM64Rotation * \
			#	(bpy.context.scene.blenderToSM64Scale)).to_4x4()
			#finalTransform = mathutils.Matrix.Identity(4)
			scaleValue = bpy.context.scene.blenderToSM64Scale
			finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((
				scaleValue, scaleValue, scaleValue))).to_4x4()

			#cProfile.runctx('exportF3DtoC(bpy.path.abspath(context.scene.DLExportPath), obj,' +\
			#	'context.scene.DLExportisStatic, finalTransform,' +\
			#	'context.scene.f3d_type, context.scene.isHWv1,' +\
			#	'bpy.context.scene.DLTexDir,' +\
			#	'bpy.context.scene.DLSaveTextures,' +\
			#	'bpy.context.scene.DLSeparateTextureDef, bpy.context.scene.DLName)',
			#	globals(), locals(), "E:/Non-Steam Games/emulators/Project 64 1.6/SM64 Romhack Tools/_Data/blender.prof")
			#p = pstats.Stats("E:/Non-Steam Games/emulators/Project 64 1.6/SM64 Romhack Tools/_Data/blender.prof")
			#p.sort_stats("cumulative").print_stats(2000)
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}
		
		try:
			applyRotation([obj], math.radians(90), 'X')
			if context.scene.DLExportType == 'C':
				exportPath, levelName = getPathAndLevel(context.scene.DLCustomExport, 
					context.scene.DLExportPath, context.scene.DLLevelName, 
					context.scene.DLLevelOption)
				if not context.scene.DLCustomExport:
					applyBasicTweaks(exportPath)
				exportF3DtoC(exportPath, obj,
					DLFormat.Static if context.scene.DLExportisStatic else DLFormat.Dynamic, finalTransform,
					context.scene.f3d_type, context.scene.isHWv1,
					bpy.context.scene.DLTexDir,
					bpy.context.scene.DLSaveTextures or bpy.context.scene.ignoreTextureRestrictions,
					bpy.context.scene.DLSeparateTextureDef,
					bpy.context.scene.DLincludeChildren, bpy.context.scene.DLName, levelName, context.scene.DLGroupName,
					context.scene.DLCustomExport,
					context.scene.DLExportHeaderType)
				self.report({'INFO'}, 'Success!')
				
			elif context.scene.DLExportType == 'Insertable Binary':
				exportF3DtoInsertableBinary(
					bpy.path.abspath(context.scene.DLInsertableBinaryPath),
					finalTransform, obj, context.scene.f3d_type,
					context.scene.isHWv1, bpy.context.scene.DLincludeChildren)
				self.report({'INFO'}, 'Success! DL at ' + \
					context.scene.DLInsertableBinaryPath + '.')
			else:
				checkExpanded(bpy.path.abspath(context.scene.exportRom))
				tempROM = tempName(context.scene.outputRom)
				romfileExport = \
					open(bpy.path.abspath(context.scene.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(context.scene.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[context.scene.levelDLExport])
				segmentData = levelParsed.segmentData
				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				if context.scene.DLUseBank0:
					startAddress, addrRange, segPointerData = \
						exportF3DtoBinaryBank0(romfileOutput, 
						[int(context.scene.DLExportStart, 16), 
						int(context.scene.DLExportEnd, 16)],
					 	finalTransform, obj, context.scene.f3d_type,
						context.scene.isHWv1, getAddressFromRAMAddress(
						int(context.scene.DLRAMAddr, 16)),
						bpy.context.scene.DLincludeChildren)
				else:
					startAddress, addrRange, segPointerData = \
						exportF3DtoBinary(romfileOutput, 
						[int(context.scene.DLExportStart, 16), 
						int(context.scene.DLExportEnd, 16)],
					 	finalTransform, obj, context.scene.f3d_type,
						context.scene.isHWv1, segmentData,
						bpy.context.scene.DLincludeChildren)
				
				if context.scene.overwriteGeoPtr:
					romfileOutput.seek(int(context.scene.DLExportGeoPtr, 16))
					romfileOutput.write(segPointerData)
	
				romfileOutput.close()
				if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
					os.remove(bpy.path.abspath(context.scene.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(context.scene.outputRom))
					
				if context.scene.DLUseBank0:
					self.report({'INFO'}, 'Success! DL at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						'), ' +\
						'to write to RAM address ' + \
						hex(startAddress + 0x80000000))
				else:
					
					self.report({'INFO'}, 'Success! DL at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						') (Seg. ' + bytesToHex(segPointerData) + ').')

			applyRotation([obj], math.radians(-90), 'X')
			return {'FINISHED'} # must return a set

		except Exception as e:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			applyRotation([obj], math.radians(-90), 'X')
			if context.scene.DLExportType == 'Binary':
				if romfileOutput is not None:
					romfileOutput.close()
				if tempROM is not None and os.path.exists(bpy.path.abspath(tempROM)):
					os.remove(bpy.path.abspath(tempROM))
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

class SM64_ExportDLPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_dl"
	bl_label = "SM64 DL Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsDLE = col.operator(SM64_ExportDL.bl_idname)

		col.prop(context.scene, 'DLExportType')
		if context.scene.DLExportType == 'C':
			col.prop(context.scene, 'DLExportisStatic')
			
			
			col.prop(context.scene, 'DLCustomExport')
			if context.scene.DLCustomExport:
				col.prop(context.scene, 'DLExportPath')
				prop_split(col, context.scene, 'DLName', 'Name')
				if not bpy.context.scene.ignoreTextureRestrictions:
					col.prop(context.scene, 'DLSaveTextures')
					if context.scene.DLSaveTextures:
						prop_split(col, context.scene, 'DLTexDir',
							'Texture Include Path')	
						col.prop(context.scene, 'DLSeparateTextureDef')
				customExportWarning(col)
			else:
				prop_split(col, context.scene, 'DLExportHeaderType', 'Export Type')
				prop_split(col, context.scene, 'DLName', 'Name')
				if context.scene.DLExportHeaderType == 'Actor':
					prop_split(col, context.scene, 'DLGroupName', 'Group Name')
				elif context.scene.DLExportHeaderType == 'Level':
					prop_split(col, context.scene, 'DLLevelOption', 'Level')
					if context.scene.DLLevelOption == 'custom':
						prop_split(col, context.scene, 'DLLevelName', 'Level Name')
				if not bpy.context.scene.ignoreTextureRestrictions:
					col.prop(context.scene, 'DLSaveTextures')
					if context.scene.DLSaveTextures:
						col.prop(context.scene, 'DLSeparateTextureDef')
				
				decompFolderMessage(col)
				writeBox = makeWriteInfoBox(col)
				writeBoxExportType(writeBox, context.scene.DLExportHeaderType, 
					context.scene.DLName, context.scene.DLLevelName, context.scene.DLLevelOption)
			
		elif context.scene.DLExportType == 'Insertable Binary':
			col.prop(context.scene, 'DLInsertableBinaryPath')
		else:
			prop_split(col, context.scene, 'DLExportStart', 'Start Address')
			prop_split(col, context.scene, 'DLExportEnd', 'End Address')
			col.prop(context.scene, 'DLUseBank0')
			if context.scene.DLUseBank0:
				prop_split(col, context.scene, 'DLRAMAddr', 'RAM Address')
			else:
				col.prop(context.scene, 'levelDLExport')
			col.prop(context.scene, 'overwriteGeoPtr')
			if context.scene.overwriteGeoPtr:
				prop_split(col, context.scene, 'DLExportGeoPtr', 
					'Geolayout Pointer')
		col.prop(context.scene, 'DLincludeChildren')
		
		for i in range(panelSeparatorSize):
			col.separator()

class ExportTexRectDraw(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.f3d_texrect_draw'
	bl_label = "Export F3D Texture Rectangle"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		try:
			if context.scene.texrect.tex is None:
				raise PluginError("No texture selected.")
			else:
				if context.scene.decompPath == "":
					raise PluginError("Decomp path has not been set in File Settings.")

				if context.scene.TexRectCustomExport:
					exportPath = context.scene.TexRectExportPath
				else:
					exportPath = context.scene.decompPath
				if not context.scene.TexRectCustomExport:
					applyBasicTweaks(exportPath)
				exportTexRectToC(bpy.path.abspath(exportPath), 
					context.scene.texrect,
					context.scene.f3d_type, context.scene.isHWv1,
					'textures/segment2',
					context.scene.TexRectSaveTextures or bpy.context.scene.ignoreTextureRestrictions,
					context.scene.TexRectName,
					not context.scene.TexRectCustomExport,
					enumHUDPaths[context.scene.TexRectExportType])

				self.report({'INFO'}, 'Success!')
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}
		return {'FINISHED'} # must return a set

class UnlinkTexRect(bpy.types.Operator):
	bl_idname = 'image.texrect_unlink'
	bl_label = "Unlink TexRect Image"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		context.scene.texrect.tex = None
		return {'FINISHED'} # must return a set

class ExportTexRectDrawPanel(bpy.types.Panel):
	bl_idname = "TEXTURE_PT_export_texrect"
	bl_label = "SM64 UI Image Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsTexRectE = col.operator(ExportTexRectDraw.bl_idname)

		textureProp = context.scene.texrect
		tex = textureProp.tex
		col.label(text = 'This is for decomp only.')
		col.template_ID(textureProp, 'tex', new="image.new", open="image.open", unlink="image.texrect_unlink")
		#col.prop(textureProp, 'tex')

		tmemUsageUI(col, textureProp)
		if tex is not None and tex.size[0] > 0 and tex.size[1] > 0:
			col.prop(textureProp, 'tex_format', text = 'Format')
			if textureProp.tex_format[:2] == 'CI':
				col.prop(textureProp, 'ci_format', text = 'CI Format')
			col.prop(textureProp.S, 'clamp', text = 'Clamp S')
			col.prop(textureProp.T, 'clamp', text = 'Clamp T')
			col.prop(textureProp.S, 'mirror', text = 'Mirror S')
			col.prop(textureProp.T, 'mirror', text = 'Mirror T')
			
		prop_split(col, context.scene, 'TexRectName', 'Name')
		if not bpy.context.scene.ignoreTextureRestrictions:
			col.prop(context.scene, 'TexRectSaveTextures')
		col.prop(context.scene, 'TexRectCustomExport')
		if context.scene.TexRectCustomExport:
			col.prop(context.scene, 'TexRectExportPath')
			customExportWarning(col)
		else:
			prop_split(col, context.scene, 'TexRectExportType', 'Export Type')
			if not context.scene.TexRectCustomExport:
				decompFolderMessage(col)
				writeBox = makeWriteInfoBox(col)
				writeBox.label(text = 'bin/segment2.c')
				writeBox.label(text = 'src/game/segment2.h')
				writeBox.label(text = 'textures/segment2')
			infoBox = col.box()
			infoBox.label(text = 'After export, call your hud\'s draw function in ')
			infoBox.label(text = enumHUDPaths[context.scene.TexRectExportType][0] + ': ')
			infoBox.label(text = enumHUDPaths[context.scene.TexRectExportType][1] + '.')

		for i in range(panelSeparatorSize):
			col.separator()

sm64_dl_writer_classes = (
	SM64_ExportDL,
	ExportTexRectDraw,
	UnlinkTexRect,
)

sm64_dl_writer_panel_classes = (
	SM64_ExportDLPanel,
	ExportTexRectDrawPanel,
)

def sm64_dl_writer_panel_register():
	for cls in sm64_dl_writer_panel_classes:
		register_class(cls)

def sm64_dl_writer_panel_unregister():
	for cls in sm64_dl_writer_panel_classes:
		unregister_class(cls)

def sm64_dl_writer_register():
	for cls in sm64_dl_writer_classes:
		register_class(cls)

	bpy.types.Scene.DLExportStart = bpy.props.StringProperty(
		name = 'Start', default = '11D8930')
	bpy.types.Scene.DLExportEnd = bpy.props.StringProperty(
		name = 'End', default = '11FFF00')
	bpy.types.Scene.levelDLExport = bpy.props.EnumProperty(items = level_enums, 
		name = 'Level', default = 'WF')
	bpy.types.Scene.DLExportGeoPtr = bpy.props.StringProperty(
		name ='Geolayout Pointer', default = '132AA8')
	bpy.types.Scene.overwriteGeoPtr = bpy.props.BoolProperty(
		name = "Overwrite geolayout pointer", default = False)
	bpy.types.Scene.DLExportType = bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	bpy.types.Scene.DLExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.DLExportisStatic = bpy.props.BoolProperty(
		name = 'Static DL', default = True)
	bpy.types.Scene.DLDefinePath = bpy.props.StringProperty(
		name = 'Definitions Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.DLUseBank0 = bpy.props.BoolProperty(name = 'Use Bank 0')
	bpy.types.Scene.DLRAMAddr = bpy.props.StringProperty(name = 'RAM Address', 
		default = '80000000')
	bpy.types.Scene.DLTexDir = bpy.props.StringProperty(
		name ='Include Path', default = 'levels/bob')
	bpy.types.Scene.DLSaveTextures = bpy.props.BoolProperty(
		name = 'Save Textures As PNGs (Breaks CI Textures)')
	bpy.types.Scene.DLSeparateTextureDef = bpy.props.BoolProperty(
		name = 'Save texture.inc.c separately')
	bpy.types.Scene.DLincludeChildren = bpy.props.BoolProperty(
		name = 'Include Children')
	bpy.types.Scene.DLInsertableBinaryPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.DLName = bpy.props.StringProperty(
		name = 'Name', default = 'mario')
	bpy.types.Scene.DLCustomExport = bpy.props.BoolProperty(
		name = 'Custom Export Path')
	bpy.types.Scene.DLExportHeaderType = bpy.props.EnumProperty(
		items = enumExportHeaderType, name = 'Header Export', default = 'Actor')
	bpy.types.Scene.DLGroupName = bpy.props.StringProperty(name = 'Group Name', 
		default = 'group0')
	bpy.types.Scene.DLLevelName = bpy.props.StringProperty(name = 'Level', 
		default = 'bob')
	bpy.types.Scene.DLLevelOption = bpy.props.EnumProperty(
		items = enumLevelNames, name = 'Level', default = 'bob')

	bpy.types.Scene.texrect = bpy.props.PointerProperty(type = TextureProperty)
	bpy.types.Scene.texrectImageTexture = bpy.props.PointerProperty(type = bpy.types.ImageTexture)
	bpy.types.Scene.TexRectExportPath = bpy.props.StringProperty(name = 'Export Path', subtype='FILE_PATH')
	bpy.types.Scene.TexRectTexDir = bpy.props.StringProperty(name = 'Include Path', default = 'textures/segment2')
	bpy.types.Scene.TexRectSaveTextures = bpy.props.BoolProperty(name = 'Save Textures as PNGs (Breaks CI Textures)')
	bpy.types.Scene.TexRectName = bpy.props.StringProperty(name = 'Name', default = 'render_hud_image')
	bpy.types.Scene.TexRectCustomExport = bpy.props.BoolProperty(name = 'Custom Export Path')
	bpy.types.Scene.TexRectExportType = bpy.props.EnumProperty(name = 'Export Type', items = enumHUDExportLocation)

def sm64_dl_writer_unregister():
	for cls in reversed(sm64_dl_writer_classes):
		unregister_class(cls)

	del bpy.types.Scene.levelDLExport
	del bpy.types.Scene.DLExportStart
	del bpy.types.Scene.DLExportEnd
	del bpy.types.Scene.DLExportGeoPtr
	del bpy.types.Scene.overwriteGeoPtr
	del bpy.types.Scene.DLExportType
	del bpy.types.Scene.DLExportPath
	del bpy.types.Scene.DLExportisStatic
	del bpy.types.Scene.DLDefinePath
	del bpy.types.Scene.DLUseBank0
	del bpy.types.Scene.DLRAMAddr
	del bpy.types.Scene.DLTexDir
	del bpy.types.Scene.DLSaveTextures
	del bpy.types.Scene.DLSeparateTextureDef
	del bpy.types.Scene.DLincludeChildren
	del bpy.types.Scene.DLInsertableBinaryPath
	del bpy.types.Scene.DLName
	del bpy.types.Scene.DLCustomExport
	del bpy.types.Scene.DLExportHeaderType
	del bpy.types.Scene.DLGroupName
	del bpy.types.Scene.DLLevelName
	del bpy.types.Scene.DLLevelOption
	
	del bpy.types.Scene.texrect
	del bpy.types.Scene.TexRectExportPath
	del bpy.types.Scene.TexRectTexDir
	del bpy.types.Scene.TexRectSaveTextures
	del bpy.types.Scene.TexRectName
	del bpy.types.Scene.texrectImageTexture
	del bpy.types.Scene.TexRectCustomExport
	del bpy.types.Scene.TexRectExportType