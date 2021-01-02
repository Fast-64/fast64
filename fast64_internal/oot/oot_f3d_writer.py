import shutil, copy

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import TextureProperty, tmemUsageUI
from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *

class OOTGfxFormatter(GameGfxFormatter):
	def __init__(self, scrollMethod):
		GameGfxFormatter.__init__(self, scrollMethod)

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
		box.prop(obj, "ootIgnoreRender")
		box.prop(obj, "ootIgnoreCollision")

def ootConvertObjectToLevel(obj, convertTransformMatrix, 
	f3dType, isHWv1, name, fModel, DLFormat, convertTextureData):
	
	#if fModel is None:
	#	fModel = FModel(f3dType, isHWv1, name, DLFormat)

	# Start geolayout
	if areaObj is not None:
		geolayoutGraph = GeolayoutGraph(name)
		#cameraObj = getCameraObj(camera)
		meshGeolayout = saveCameraSettingsToGeolayout(
			geolayoutGraph, areaObj, obj, name + '_geo')
		rootObj = areaObj
		fModel.global_data.addAreaData(areaObj.areaIndex, 
			FAreaData(FFogData(areaObj.area_fog_position, areaObj.area_fog_color)))

	else:
		geolayoutGraph = GeolayoutGraph(name + '_geo')
		if isinstance(obj.data, bpy.types.Mesh) and obj.use_render_area:
			rootNode = TransformNode(StartRenderAreaNode(obj.culling_radius))
		else:
			rootNode = TransformNode(StartNode())
		geolayoutGraph.startGeolayout.nodes.append(rootNode)
		meshGeolayout = geolayoutGraph.startGeolayout
		rootObj = obj

	# Duplicate objects to apply scale / modifiers / linked data
	tempObj, allObjs = \
		duplicateHierarchy(rootObj, 'ootIgnoreRender', True, None if areaObj is None else areaObj.areaIndex)
	try:
		processMesh(fModel, tempObj, convertTransformMatrix,
			meshGeolayout.nodes[0], geolayoutGraph.startGeolayout,
			geolayoutGraph, True, convertTextureData)
		cleanupDuplicatedObjects(allObjs)
		rootObj.select_set(True)
		bpy.context.view_layer.objects.active = rootObj
	except Exception as e:
		cleanupDuplicatedObjects(allObjs)
		rootObj.select_set(True)
		bpy.context.view_layer.objects.active = rootObj
		raise Exception(str(e))

	appendRevertToGeolayout(geolayoutGraph, fModel)
	geolayoutGraph.generateSortedList()
	#if DLFormat == DLFormat.GameSpecific:
	#	geolayoutGraph.convertToDynamic()
	return geolayoutGraph, fModel
	
# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
def processMesh(fModel, obj, transformMatrix, parentTransformNode,
	geolayout, geolayoutGraph, isRoot, convertTextureData):
	#finalTransform = copy.deepcopy(transformMatrix)

	useGeoEmpty = obj.data is None and \
		(obj.sm64_obj_type == 'None' or \
		obj.sm64_obj_type == 'Level Root' or \
		obj.sm64_obj_type == 'Area Root' or \
		obj.sm64_obj_type == 'Switch')

	useSwitchNode = obj.data is None and \
		obj.sm64_obj_type == 'Switch'

	addRooms = isRoot and obj.data is None and \
		obj.sm64_obj_type == 'Area Root' and \
		obj.enableRoomSwitch
		
	#if useAreaEmpty and areaIndex is not None and obj.areaIndex != areaIndex:
	#	return
		
	# Its okay to return if ignore_render, because when we duplicated obj hierarchy we stripped all
	# ignore_renders from geolayout.
	if not partOfGeolayout(obj) or obj.ignore_render:
		return

	if isRoot:
		translate = mathutils.Vector((0,0,0))
		rotate = mathutils.Quaternion()
	else:
		translate = obj.matrix_local.decompose()[0]
		rotate = obj.matrix_local.decompose()[1]
	rotAxis, rotAngle = rotate.to_axis_angle()
	zeroRotation = isZeroRotation(rotate)
	zeroTranslation = isZeroTranslation(translate)

	#translation = mathutils.Matrix.Translation(translate)
	#rotation = rotate.to_matrix().to_4x4()

	if useSwitchNode or addRooms: # Specific empty types
		if useSwitchNode:
			switchFunc = obj.switchFunc
			switchParam = obj.switchParam
		elif addRooms:
			switchFunc = 'geo_switch_area'
			switchParam = len(obj.children)

		# Rooms are not set here (since this is just a copy of the original hierarchy)
		# They should be set previously, using setRooms()
		parentTransformNode = addParentNode(parentTransformNode, SwitchNode(switchFunc, switchParam, obj.original_name))
		alphabeticalChildren = getSwitchChildren(obj)
		for i in range(len(alphabeticalChildren)):
			childObj = alphabeticalChildren[i]
			optionGeolayout = geolayoutGraph.addGeolayout(
				childObj, fModel.name + '_' + childObj.original_name + '_geo')
			geolayoutGraph.addJumpNode(parentTransformNode, geolayout,
				optionGeolayout)
			if not zeroRotation or not zeroTranslation:
				startNode = TransformNode(getOptimalNode(translate, rotate, 1, False,
					zeroTranslation, zeroRotation))
			else:
				startNode = TransformNode(StartNode())
			optionGeolayout.nodes.append(startNode)
			processMesh(fModel, childObj, transformMatrix, startNode, 
				optionGeolayout, geolayoutGraph, False, convertTextureData)

	else:			
		if obj.geo_cmd_static == 'Optimal' or useGeoEmpty:
			node = getOptimalNode(translate, rotate, int(obj.draw_layer_static), True,
				zeroTranslation, zeroRotation)
	
		elif obj.geo_cmd_static == "DisplayListWithOffset":
			if not zeroRotation:
				node = DisplayListWithOffsetNode(int(obj.draw_layer_static), True,
					mathutils.Vector((0,0,0)))	
	
				parentTransformNode = addParentNode(parentTransformNode,
					TranslateRotateNode(1, 0, False, translate, rotate))
			else:
				node = DisplayListWithOffsetNode(int(obj.draw_layer_static), True,
					translate)
	
		else: #Billboard
			if not zeroRotation:
				node = BillboardNode(int(obj.draw_layer_static), True, 
					mathutils.Vector((0,0,0)))
	
				parentTransformNode = addParentNode(parentTransformNode,
					TranslateRotateNode(1, 0, False, translate, rotate))
			else:
				node = BillboardNode(int(obj.draw_layer_static), True, translate)


		transformNode = TransformNode(node)

		additionalNodes = False
		if obj.data is not None and \
			(obj.use_render_range or obj.add_shadow or obj.add_func):

			parentTransformNode.children.append(transformNode)
			transformNode.parent = parentTransformNode
			transformNode.node.hasDL = False
			parentTransformNode = transformNode

			node = DisplayListNode(int(obj.draw_layer_static))
			transformNode = TransformNode(node)

			if obj.use_render_range:
				parentTransformNode = \
					addParentNode(parentTransformNode, RenderRangeNode(obj.render_range[0], obj.render_range[1]))

			if obj.add_shadow:
				parentTransformNode = \
					addParentNode(parentTransformNode, ShadowNode(obj.shadow_type, obj.shadow_solidity, obj.shadow_scale))

			if obj.add_func:
				addParentNode(parentTransformNode, FunctionNode(obj.geo_func, obj.func_param))

			# Make sure to add additional cases to if statement above

		if obj.data is None:
			meshGroup = None
		else:
			meshGroup = saveStaticModel(fModel, obj, transformMatrix, fModel.name, fModel.DLFormat, convertTextureData, False)

		if meshGroup is None:
			node.hasDL = False
		else:
			node.DLmicrocode = meshGroup.mesh.draw
			node.fMesh = meshGroup.mesh

		parentTransformNode.children.append(transformNode)
		transformNode.parent = parentTransformNode

		alphabeticalChildren = sorted(obj.children, key = lambda childObj: childObj.original_name.lower())
		for childObj in alphabeticalChildren:
			processMesh(fModel, childObj, transformMatrix, transformNode, 
				geolayout, geolayoutGraph, False, convertTextureData)


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
	staticData, dynamicData, texC = fModel.to_c(texSeparate, savePNG, texDir, gfxFormatter)
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

	if savePNG:
		fModel.save_textures(modelDirPath)

	fModel.freePalettes()

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

oot_dl_writer_classes = (
	OOT_ExportDL,
)

oot_dl_writer_panel_classes = (
	OOT_ExportDLPanel,
	OOT_DisplayListPanel,
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
	bpy.types.Object.ootIgnoreRender = bpy.props.BoolProperty(name = "Ignore Render")
	bpy.types.Object.ootIgnoreCollision = bpy.props.BoolProperty(name = "Ignore Collision")

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