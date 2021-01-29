import shutil, copy, bpy

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import *
from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *

class OOTModel(FModel):
	def __init__(self, f3dType, isHWv1, name, DLFormat):
		FModel.__init__(self, f3dType, isHWv1, name, DLFormat, GfxMatWriteMethod.WriteAll)

	def getDrawLayer(self, obj):
		return obj.ootDrawLayer

	def getRenderMode(self, drawLayer):
		defaultRenderModes = bpy.context.scene.world.ootDefaultRenderModes
		cycle1 = getattr(defaultRenderModes, drawLayer.lower() + "Cycle1")
		cycle2 = getattr(defaultRenderModes, drawLayer.lower() + "Cycle2")
		return [cycle1, cycle2]

	def getTextureSuffixFromFormat(self, texFmt):
		if texFmt == 'RGBA16':
			return 'rgb5a1'
		else:
			return texFmt.lower()

class OOTGfxFormatter(GameGfxFormatter):
	def __init__(self, scrollMethod):
		GameGfxFormatter.__init__(self, scrollMethod, 64)

	# This code is not functional, only used for an example
	def drawToC(self, f3d, gfxList):
		return gfxList.to_c(f3d)

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
		data = CData()
		data.header = 'Gfx* ' + fMaterial.material.name + '(Gfx* glistp, int s, int t);\n'
		data.source = 'Gfx* ' + materialGfx.name + '(Gfx* glistp, int s, int t) {\n'
		for command in materialGfx.commands:
			data.source += '\t' + command.to_c(False) + ';\n'
		data.source += '\treturn glistp;\n}' + '\n\n'

		if fMaterial.revert is not None:
			data.append(fMaterial.revert.to_c(f3d))
		return data

class OOTTriangleConverter(TriangleConverter):
	def __init__(self, mesh, convertInfo, vertexGroupInfo, currentLimbIndex, triList, vtxList, f3d, 
		texDimensions, transformMatrix, isPointSampled, exportVertexColors,
		existingVertexData, existingVertexMaterialRegions):

		TriangleConverter.__init__(self, mesh, convertInfo, vertexGroupInfo, currentLimbIndex, triList, vtxList, f3d, 
			texDimensions, transformMatrix, isPointSampled, exportVertexColors,
			existingVertexData, existingVertexMaterialRegions)

	def getMatrixAddrFromGroup(self, groupIndex):
		return format((0x0D << 24) + MTX_SIZE * self.vertexGroupInfo.vertexGroupToLimb[groupIndex], "#010x")

def ootProcessVertexGroup(fModel, meshObj, vertexGroup, convertTransformMatrix, armatureObj, namePrefix,
	meshInfo, drawLayerOverride, convertTextureData):

	mesh = meshObj.data
	currentGroupIndex = getGroupIndexFromname(meshObj, vertexGroup)
	vertIndices = [vert.index for vert in meshObj.data.vertices if\
		meshInfo.vertexGroupInfo.vertexGroups[vert.index] == currentGroupIndex]

	if len(vertIndices) == 0:
		print("No vert indices in " + vertexGroup)
		return None, False

	bone = armatureObj.data.bones[vertexGroup]
	currentMatrix = convertTransformMatrix @ bone.matrix_local.inverted()
	
	# dict of material_index keys to face array values
	groupFaces = {}
	
	# dict of material_index keys to SkinnedFace objects
	skinnedFaces = {}

	handledFaces = []
	for vertIndex in vertIndices:
		if vertIndex not in meshInfo.vert:
			continue
		for face in meshInfo.vert[vertIndex]:
			# Ignore repeat faces
			if face in handledFaces:
				continue
			else:
				handledFaces.append(face)

			sortedLoops = {} # (group tuple) : []
			connectedToUnhandledBone = False

			# loop is interpreted as face + loop index
			groupTuple = []
			for i in range(3):
				vertIndex = face.vertices[i]
				vertGroupIndex = meshInfo.vertexGroupInfo.vertexGroups[vertIndex]
				if vertGroupIndex not in groupTuple:
					groupTuple.append(vertGroupIndex)
				if vertGroupIndex not in meshInfo.vertexGroupInfo.vertexGroupToLimb:
					# Only want to handle skinned faces connected to parent
					connectedToUnhandledBone = True
					break
			if connectedToUnhandledBone:
				continue
			groupTuple = tuple(sorted(groupTuple))

			if groupTuple == tuple([vertGroupIndex]):
				if face.material_index not in groupFaces:
					groupFaces[face.material_index] = []
				groupFaces[face.material_index].append(face)
			else:
				if groupTuple not in skinnedFaces:
					skinnedFaces[groupTuple] = {}
				skinnedFacesGroup = skinnedFaces[groupTuple]
				if face.material_index not in skinnedFacesGroup:
					skinnedFacesGroup[face.material_index] = []
				skinnedFacesGroup[face.material_index].append(face)

	if not (len(groupFaces) > 0 or len(skinnedFaces) > 0):
		print("No faces in " + vertexGroup)
		return None, False
	
	fMeshes = {}

	# Usually we would separate DLs into different draw layers.
	# however it seems like OOT skeletons don't have this ability.
	# Therefore we always use the drawLayerOverride as the draw layer key.
	# This means everything will be saved to one mesh. 
	drawLayerKey = drawLayerOverride
	for material_index, faces in groupFaces.items():
		material = meshObj.data.materials[material_index]
		if material.mat_ver > 3:
			drawLayer = material.f3d_mat.draw_layer.oot
		else:
			drawLayer = drawLayerOverride
		
		if drawLayerKey not in fMeshes:
			meshName = getFMeshName(vertexGroup, namePrefix, drawLayer, False)
			checkUniqueBoneNames(fModel, meshName, vertexGroup)
			fMesh = FMesh(meshName, fModel.DLFormat)
			fMeshes[drawLayerKey] = fMesh
			
		checkForF3dMaterialInFaces(meshObj, material)
		fMaterial, texDimensions = \
			saveOrGetF3DMaterial(material, fModel, meshObj, drawLayer, convertTextureData)
		if fMaterial.useLargeTextures:
			currentGroupIndex = saveMeshWithLargeTexturesByFaces(material, faces, fModel, fMeshes[drawLayer], meshObj, currentMatrix,
				meshInfo, drawLayer, convertTextureData, currentGroupIndex, OOTTriangleConverter, None, None)
		else:
			currentGroupIndex = saveMeshByFaces(material, faces, fModel, fMeshes[drawLayer], meshObj, currentMatrix,
				meshInfo, drawLayer, convertTextureData, currentGroupIndex, OOTTriangleConverter, None, None)

	for groupTuple, materialFaces in skinnedFaces.items():
		for material_index, faces in materialFaces.items():
			material = meshObj.data.materials[material_index]
			if material.mat_ver > 3:
				drawLayer = material.f3d_mat.draw_layer.oot
			else:
				drawLayer = drawLayerOverride

			if drawLayerKey not in fMeshes:
				# technically skinned, but for oot we don't have separate skinned/unskinned meshes.
				meshName = getFMeshName(vertexGroup, namePrefix, drawLayer, False)
				checkUniqueBoneNames(fModel, meshName, vertexGroup)
				fMesh = FMesh(meshName, fModel.DLFormat)
				fMeshes[drawLayerKey] = fMesh

			checkForF3dMaterialInFaces(meshObj, material)
			fMaterial, texDimensions = \
				saveOrGetF3DMaterial(material, fModel, meshObj, drawLayer, convertTextureData)
			if fMaterial.useLargeTextures:
				currentGroupIndex = saveMeshWithLargeTexturesByFaces(material, faces, fModel, fMeshes[drawLayer], meshObj, currentMatrix,
					meshInfo, drawLayer, convertTextureData, currentGroupIndex, OOTTriangleConverter, None, None)
			else:
				currentGroupIndex = saveMeshByFaces(material, faces, fModel, fMeshes[drawLayer], meshObj, currentMatrix,
					meshInfo, drawLayer, convertTextureData, currentGroupIndex, OOTTriangleConverter, None, None)

	for drawLayer, fMesh in fMeshes.items():
		fMesh.draw.commands.append(SPEndDisplayList())

	return fMeshes[drawLayerKey], len(skinnedFaces) > 0

class OOT_DisplayListPanel(bpy.types.Panel):
	bl_label = "Display List Inspector"
	bl_idname = "OBJECT_PT_OOT_DL_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return context.scene.gameEditorMode == "OOT" and \
			(context.object is not None and isinstance(context.object.data, bpy.types.Mesh))

	def draw(self, context):
		box = self.layout.box()
		box.box().label(text = 'OOT DL Inspector')
		obj = context.object

		prop_split(box, obj, "ootDrawLayer", "Draw Layer")
		box.prop(obj, "ignore_render")
		box.prop(obj, "ignore_collision")


def ootExportF3DtoC(basePath, obj, DLFormat, transformMatrix, 
	f3dType, isHWv1, texDir, savePNG, texSeparate, includeChildren, name, levelName, groupName, customExport, headerType):
	dirPath, texDir = getExportDir(customExport, basePath, headerType, 
		levelName, texDir, name)

	fModel = OOTModel(f3dType, isHWv1, name, DLFormat)
	fMesh = exportF3DCommon(obj, fModel, transformMatrix, 
		includeChildren, name, DLFormat, not savePNG)

	modelDirPath = os.path.join(dirPath, toAlnum(name))

	if not os.path.exists(modelDirPath):
		os.mkdir(modelDirPath)

	if headerType == 'Actor':
		scrollName = 'actor_dl_' + name
	elif headerType == 'Level':
		scrollName = levelName + '_level_dl_' + name

	gfxFormatter = SM64GfxFormatter(ScrollMethod.Vertex)
	exportData = fModel.to_c(
		TextureExportSettings(texSeparate, savePNG, texDir), gfxFormatter)
	staticData = exportData.staticData
	dynamicData = exportData.dynamicData
	texC = exportData.textureData

	scrollData, hasScrolling = fModel.to_c_vertex_scroll(scrollName, gfxFormatter)
	scroll_data = scrollData.source
	cDefineScroll = scrollData.header 

	modifyTexScrollFiles(basePath, modelDirPath, cDefineScroll, scroll_data, hasScrolling)
	
	if DLFormat == DLFormat.Static:
		staticData.append(dynamicData)
	else:
		geoString = writeMaterialFiles(basePath, modelDirPath, 
			'#include "actors/' + toAlnum(name) + '/header.h"', 
			'#include "actors/' + toAlnum(name) + '/material.inc.h"',
			dynamicData.header, dynamicData.source, '', customExport)

	#fModel.save_textures(modelDirPath, not savePNG)

	#fModel.freePalettes()

	if texSeparate:
		texCFile = open(os.path.join(modelDirPath, 'texture.inc.c'), 'w', newline='\n')
		texCFile.write(texC.source)
		texCFile.close()

	modelPath = os.path.join(modelDirPath, 'model.inc.c')
	outFile = open(modelPath, 'w', newline='\n')
	outFile.write(staticData.source)
	outFile.close()
		
	headerPath = os.path.join(modelDirPath, 'header.h')
	cDefFile = open(headerPath, 'w', newline='\n')
	cDefFile.write(staticData.header)
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

class OOTDefaultRenderModesProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty()
	opaqueCycle1 : bpy.props.StringProperty(default = "G_RM_AA_ZB_OPA_SURF")
	opaqueCycle2 : bpy.props.StringProperty(default = "G_RM_AA_ZB_OPA_SURF2")
	transparentCycle1 : bpy.props.StringProperty(default = "G_RM_AA_ZB_XLU_SURF")
	transparentCycle2 : bpy.props.StringProperty(default = "G_RM_AA_ZB_XLU_SURF2")
	overlayCycle1 : bpy.props.StringProperty(default = "G_RM_AA_ZB_OPA_SURF")
	overlayCycle2 : bpy.props.StringProperty(default = "G_RM_AA_ZB_OPA_SURF2")

class OOT_DrawLayersPanel(bpy.types.Panel):
	bl_label = "OOT Draw Layers"
	bl_idname = "WORLD_PT_OOT_Draw_Layers_Panel"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "world"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return context.scene.gameEditorMode == "OOT"

	def draw(self, context):
		ootDefaultRenderModeProp = context.scene.world.ootDefaultRenderModes
		layout = self.layout

		inputGroup = layout.column()
		inputGroup.prop(ootDefaultRenderModeProp, 'expandTab', 
			text = 'Default Render Modes', 
			icon = 'TRIA_DOWN' if ootDefaultRenderModeProp.expandTab else 'TRIA_RIGHT')
		if ootDefaultRenderModeProp.expandTab:
			prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle1", "Opaque Cycle 1")
			prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle2", "Opaque Cycle 2")
			prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle1", "Transparent Cycle 1")
			prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle2", "Transparent Cycle 2")
			prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle1", "Overlay Cycle 1")
			prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle2", "Overlay Cycle 2")

oot_dl_writer_classes = (
	OOTDefaultRenderModesProperty,
	#OOT_ExportDL,
)

oot_dl_writer_panel_classes = (
	#OOT_ExportDLPanel,
	OOT_DisplayListPanel,
	OOT_DrawLayersPanel,
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

	bpy.types.Object.ootDrawLayer = bpy.props.EnumProperty(items = ootEnumDrawLayers, default = 'Opaque')
	bpy.types.World.ootDefaultRenderModes = bpy.props.PointerProperty(type = OOTDefaultRenderModesProperty)

	bpy.types.Scene.ootLevelDLExport = bpy.props.EnumProperty(items = ootEnumSceneID, 
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