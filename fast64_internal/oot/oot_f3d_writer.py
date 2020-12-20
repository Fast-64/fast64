import shutil, copy

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import TextureProperty, tmemUsageUI
from bpy.utils import register_class, unregister_class
from .oot_constants import ootEnumSceneID

class OOTGfxFormatter(GameGfxFormatter):
	def __init__(self, scrollMethod):
		GameGfxFormatter.__init__(self, scrollMethod)

	# This code is not functional, only used for an example
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
				if isinstance(command, SPDisplayList) and command.displayList.tag == GfxListTag.Material:
					data += '\t' + 'glistp = ' + command.displayList.name + '(glistp, gAreaUpdateCounter, gAreaUpdateCounter);\n'
				else:
					data += '\t' + command.to_c(False) + ';\n'

			data += '\t}\n\treturn startCmd;\n}'	
			return data
		else:
			return gfxList.to_c(f3d)

	def drawToCDef(self, gfxList):
		if self.functionNodeDraw:
			return 'Gfx* ' + self.name + '(s32 renderContext, struct GraphNode* node, struct AllocOnlyPool *a2);\n'
		else:
			return gfxList.to_c_def()

	# This code is not functional, only used for an example
	def tileScrollMaterialToC(self, f3d, fMaterial):
		materialGfx = fMaterial.material
		scrollDataFields = fMaterial.scrollData.fields

		# Set tile scrolling
		for texIndex in range(2): # for each texture
			for axisIndex in range(2): # for each axis
				scrollField = scrollDataFields[texIndex][axisIndex]
				if scrollField.animType != "None":
					if scrollField.animType == "Linear":
						if axisIndex == 0:
							fMaterial.tileSizeCommands[texIndex].uls = str(fMaterial.tileSizeCommands[0].uls) + \
								" + s * " + str(scrollField.speed)
						else:
							fMaterial.tileSizeCommands[texIndex].ult = str(fMaterial.tileSizeCommands[0].ult) + \
								" + s * " + str(scrollField.speed)

		# Build commands
		data = 'Gfx* ' + materialGfx.name + '(Gfx* glistp, int s, int t) {\n'
		for command in materialGfx.commands:
			data += '\t' + command.to_c(False) + ';\n'
		data += '\treturn glistp;\n}' + '\n\n'

		if fMaterial.revert is not None:
			data += fMaterial.revert.to_c(f3d) + '\n\n'
		return data

	def tileScrollMaterialToCDef(self, fMaterial):
		return 'Gfx* ' + fMaterial.material.name + '(Gfx* glistp, int s, int t);\n' +\
			fMaterial.revert.to_c_def() + '\n\n'

def ootExportF3DtoC(basePath, obj, DLFormat, transformMatrix, 
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

	gfxFormatter = SM64GfxFormatter(ScrollMethod.Vertex)
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

class OOT_ExportDL(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_export_dl'
	bl_label = "Export Display List"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		try:
			if context.mode != 'OBJECT':
				raise PluginError("Operator can only be used in object mode.")	
			allObjs = context.selected_objects
			if len(allObjs) == 0:
				raise PluginError("No objects selected.")
			obj = context.selected_objects[0]
			if not isinstance(obj.data, bpy.types.Mesh):
				raise PluginError("Object is not a mesh.")

			scaleValue = bpy.context.scene.ootBlenderScale
			finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((
				scaleValue, scaleValue, scaleValue))).to_4x4()

		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}
		
		try:
			applyRotation([obj], math.radians(90), 'X')

			exportPath, levelName = getPathAndLevel(context.scene.ootDLCustomExport, 
				context.scene.ootExportPath, context.scene.ootDLLevelName, 
				context.scene.ootDLLevelOption)
			#if not context.scene.ootDLCustomExport:
			#	applyBasicTweaks(exportPath)
			ootExportF3DtoC(exportPath, obj,
				DLFormat.Static if context.scene.ootDLExportisStatic else DLFormat.Dynamic, finalTransform,
				context.scene.f3d_type, context.scene.isHWv1,
				bpy.context.scene.ootDLTexDir,
				bpy.context.scene.ootDLSaveTextures or bpy.context.scene.ignoreTextureRestrictions,
				bpy.context.scene.ootDLSeparateTextureDef,
				bpy.context.scene.ootDLincludeChildren, bpy.context.scene.ootDLName, levelName, context.scene.ootDLGroupName,
				context.scene.ootDLCustomExport,
				context.scene.ootDLExportHeaderType)
			self.report({'INFO'}, 'Success!')

			applyRotation([obj], math.radians(-90), 'X')
			return {'FINISHED'} # must return a set

		except Exception as e:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			applyRotation([obj], math.radians(-90), 'X')
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

class OOT_ExportDLPanel(bpy.types.Panel):
	bl_idname = "OOT_PT_export_dl"
	bl_label = "OOT DL Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'OOT'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsDLE = col.operator(OOT_ExportDL.bl_idname)

		col.prop(context.scene, 'ootDLExportisStatic')
		
		col.prop(context.scene, 'ootDLCustomExport')
		if context.scene.ootDLCustomExport:
			col.prop(context.scene, 'ootDLExportPath')
			prop_split(col, context.scene, 'ootDLName', 'Name')
			if not bpy.context.scene.ignoreTextureRestrictions:
				col.prop(context.scene, 'saveTextures')
				if context.scene.saveTextures:
					prop_split(col, context.scene, 'ootDLTexDir',
						'Texture Include Path')	
					col.prop(context.scene, 'ootDLSeparateTextureDef')
			customExportWarning(col)
		else:
			prop_split(col, context.scene, 'ootDLExportHeaderType', 'Export Type')
			prop_split(col, context.scene, 'ootDLName', 'Name')
			if context.scene.ootDLExportHeaderType == 'Actor':
				prop_split(col, context.scene, 'ootDLGroupName', 'Group Name')
			elif context.scene.ootDLExportHeaderType == 'Level':
				prop_split(col, context.scene, 'ootDLLevelOption', 'Level')
				if context.scene.ootDLLevelOption == 'custom':
					prop_split(col, context.scene, 'ootDLLevelName', 'Level Name')
			if not bpy.context.scene.ignoreTextureRestrictions:
				col.prop(context.scene, 'saveTextures')
				if context.scene.saveTextures:
					col.prop(context.scene, 'ootDLSeparateTextureDef')
			
			#decompFolderMessage(col)
			#writeBox = makeWriteInfoBox(col)
			#writeBoxExportType(writeBox, context.scene.ootDLExportHeaderType, 
			#	context.scene.ootDLName, context.scene.ootDLLevelName, context.scene.ootDLLevelOption)
			
		col.prop(context.scene, 'ootDLincludeChildren')
		
		for i in range(panelSeparatorSize):
			col.separator()

oot_dl_writer_classes = (
	OOT_ExportDL,
)

oot_dl_writer_panel_classes = (
	OOT_ExportDLPanel,
)

def oot_dl_writer_panel_register():
	for cls in oot_dl_writer_panel_classes:
		register_class(cls)

def oot_dl_writer_panel_unregister():
	for cls in oot_dl_writer_panel_classes:
		unregister_class(cls)

def oot_dl_writer_register():
	for cls in oot_dl_writer_classes:
		register_class(cls)

	bpy.types.Scene.ootlevelDLExport = bpy.props.EnumProperty(items = ootEnumSceneID, 
		name = 'Level', default = 'SCENE_YDAN')
	bpy.types.Scene.ootDLExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.ootDLExportisStatic = bpy.props.BoolProperty(
		name = 'Static DL', default = True)
	bpy.types.Scene.ootDLDefinePath = bpy.props.StringProperty(
		name = 'Definitions Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.ootDLTexDir = bpy.props.StringProperty(
		name ='Include Path', default = 'levels/bob')
	bpy.types.Scene.ootDLSeparateTextureDef = bpy.props.BoolProperty(
		name = 'Save texture.inc.c separately')
	bpy.types.Scene.ootDLincludeChildren = bpy.props.BoolProperty(
		name = 'Include Children')
	bpy.types.Scene.ootDLName = bpy.props.StringProperty(
		name = 'Name', default = 'mario')
	bpy.types.Scene.ootDLCustomExport = bpy.props.BoolProperty(
		name = 'Custom Export Path')
	bpy.types.Scene.ootDLExportHeaderType = bpy.props.EnumProperty(
		items = enumExportHeaderType, name = 'Header Export', default = 'Actor')
	bpy.types.Scene.ootDLGroupName = bpy.props.StringProperty(name = 'Group Name', 
		default = 'group0')
	bpy.types.Scene.ootDLLevelName = bpy.props.StringProperty(name = 'Level', 
		default = 'bob')
	bpy.types.Scene.ootDLLevelOption = bpy.props.EnumProperty(
		items = ootEnumSceneID, name = 'Level', default = 'SCENE_YDAN')

def oot_dl_writer_unregister():
	for cls in reversed(oot_dl_writer_classes):
		unregister_class(cls)

	del bpy.types.Scene.ootLevelDLExport
	del bpy.types.Scene.ootDLExportPath
	del bpy.types.Scene.ootDLExportisStatic
	del bpy.types.Scene.ootDLDefinePath
	del bpy.types.Scene.ootDLTexDir
	del bpy.types.Scene.ootDLSeparateTextureDef
	del bpy.types.Scene.ootDLincludeChildren
	del bpy.types.Scene.ootDLName
	del bpy.types.Scene.ootDLCustomExport
	del bpy.types.Scene.ootDLExportHeaderType
	del bpy.types.Scene.ootDLGroupName
	del bpy.types.Scene.ootDLLevelName
	del bpy.types.Scene.ootDLLevelOption