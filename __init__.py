import sys
import tempfile
import copy
import shutil
import bpy
import traceback
import os
from pathlib import Path
from .fast64_internal import *

import cProfile
import pstats

# info about add on
bl_info = {
	"name": "Fast64",
	"category": "Object",
	"blender": (2, 80, 0),
	}

axis_enums = [	
	('X', 'X', 'X'), 
	('Y', 'Y', 'Y'), 
	('-X', '-X', '-X'),
	('-Y', '-Y', '-Y'),
]

enumExportType = [
	('C', 'C', 'C'),
	('Binary', 'Binary', 'Binary')
]

panelSeparatorSize = 5

def checkExpanded(filepath):
	size = os.path.getsize(filepath)
	if size < 9000000: # check if 8MB
		raise ValueError("ROM at " + filepath + " is too small. You may be using an unexpanded ROM. You can expand a ROM by opening it in SM64 Editor or ROM Manager.")

class ArmatureApplyWithMesh(bpy.types.Operator):
	# set bl_ properties
	bl_description = 'Applies current pose as default pose. Useful for ' + \
		"rigging an armature that is not in T/A pose. Note that when using " +\
		" with an SM64 armature, you must revert to the default pose after " +\
		"skinning."
	bl_idname = 'object.armature_apply_w_mesh'
	bl_label = "Apply As Rest Pose"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.mode != 'OBJECT' and context.mode != 'POSE':
			raise ValueError("Operator can only be used in object or pose mode.")
		elif context.mode == 'POSE':
			bpy.ops.object.mode_set(mode = "OBJECT")
		
		if len(context.selected_objects) == 0:
			raise ValueError("Armature not selected.")
		elif type(context.selected_objects[0].data) is not\
			bpy.types.Armature:
			raise ValueError("Armature not selected.")
		
		armatureObj = context.selected_objects[0]
		for child in armatureObj.children:
			if type(child.data) is not bpy.types.Mesh:
				continue
			armatureModifier = None
			for modifier in child.modifiers:
				if isinstance(modifier, bpy.types.ArmatureModifier):
					armatureModifier = modifier
			if armatureModifier is None:
				continue
			print(armatureModifier.name)
			bpy.ops.object.select_all(action = "DESELECT")
			context.view_layer.objects.active = child
			bpy.ops.object.modifier_copy(modifier=armatureModifier.name)
			print(len(child.modifiers))
			bpy.ops.object.modifier_apply(modifier=armatureModifier.name)

		bpy.ops.object.select_all(action = "DESELECT")
		context.view_layer.objects.active = armatureObj
		bpy.ops.object.mode_set(mode = "POSE")
		bpy.ops.pose.armature_apply()

		self.report({'INFO'}, 'Applied armature with mesh.')
		return {'FINISHED'} # must return a set

class AddBoneGroups(bpy.types.Operator):
	# set bl_ properties
	bl_description = 'Add bone groups respresenting other node types in ' +\
		'SM64 geolayouts (ex. Shadow, Switch, Function).'
	bl_idname = 'object.add_bone_groups'
	bl_label = "Add Bone Groups"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.mode != 'OBJECT' and context.mode != 'POSE':
			raise ValueError("Operator can only be used in object or pose mode.")
		elif context.mode == 'POSE':
			bpy.ops.object.mode_set(mode = "OBJECT")
		
		if len(context.selected_objects) == 0:
			raise ValueError("Armature not selected.")
		elif type(context.selected_objects[0].data) is not\
			bpy.types.Armature:
			raise ValueError("Armature not selected.")
		
		armatureObj = context.selected_objects[0]
		createBoneGroups(armatureObj)

		self.report({'INFO'}, 'Created bone groups.')
		return {'FINISHED'} # must return a set

class CreateMetarig(bpy.types.Operator):
	# set bl_ properties
	bl_description = 'SM64 imported armatures are usually not good for ' + \
		'rigging. There are often intermediate bones between deform bones ' + \
		'and they don\'t usually point to their children. This operator ' +\
		'creates a metarig on armature layer 4 useful for IK.'
	bl_idname = 'object.create_metarig'
	bl_label = "Create Animatable Metarig"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.mode != 'OBJECT' and context.mode != 'POSE':
			raise ValueError("Operator can only be used in object or pose mode.")
		elif context.mode == 'POSE':
			bpy.ops.object.mode_set(mode = "OBJECT")
		
		if len(context.selected_objects) == 0:
			raise ValueError("Armature not selected.")
		elif type(context.selected_objects[0].data) is not\
			bpy.types.Armature:
			raise ValueError("Armature not selected.")
		
		armatureObj = context.selected_objects[0]
		generateMetarig(armatureObj)

		self.report({'INFO'}, 'Created metarig.')
		return {'FINISHED'} # must return a set

class N64_AddF3dMat(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.add_f3d_mat'
	bl_label = "Add Fast3D Material"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		
		if len(context.selected_objects) == 0:
			raise ValueError("Mesh not selected.")
		elif type(context.selected_objects[0].data) is not\
			bpy.types.Mesh:
			raise ValueError("Mesh not selected.")
		
		obj = context.selected_objects[0]
		createF3DMat(obj)

		self.report({'INFO'}, 'Created F3D material.')
		return {'FINISHED'} # must return a set

# See SM64GeoLayoutPtrsByLevels.txt by VLTone
class SM64_ImportGeolayout(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_import_geolayout'
	bl_label = "Import Geolayout"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	geoImportAddr : bpy.props.StringProperty(name ='Start Address', default = '1F1D60')
	generateArmature : bpy.props.BoolProperty(name ='Generate Armature?')
	levelGeoImport : bpy.props.EnumProperty(items = level_enums, name = 'Level Used By Geolayout Import', default = 'HMC')
	importRom : bpy.props.StringProperty(name ='Import ROM', subtype = 'FILE_PATH')
	ignoreSwitch : bpy.props.BoolProperty(name = 'Ignore Switch Nodes', default = True)

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		#finalTransform = mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
		finalTransform = mathutils.Matrix.Identity(4)
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		try:
			romfileSrc = open(bpy.path.abspath(self.importRom), 'rb')
			checkExpanded(bpy.path.abspath(self.importRom))

			armatureObj = None
			#cProfile.runctx('armatureMeshGroups, armatureObj = parseGeoLayout(romfileSrc, int(self.geoImportAddr, 16),context.scene, self.levelGeoImport, finalTransform, self.generateArmature, self.ignoreSwitch, True, context.scene.f3d_type, context.scene.isHWv1)', globals(), locals(), "E:/Non-Steam Games/emulators/Project 64 1.6/SM64 Romhack Tools/_Data/blender.prof")
			#p = pstats.Stats("E:/Non-Steam Games/emulators/Project 64 1.6/SM64 Romhack Tools/_Data/blender.prof")
			#p.sort_stats("cumulative").print_stats(2000)

			# Armature mesh groups includes armatureObj.
			armatureMeshGroups, armatureObj = parseGeoLayout(romfileSrc, 
				int(self.geoImportAddr, 16),
			 	context.scene, self.levelGeoImport, 
				finalTransform, self.generateArmature, 
				self.ignoreSwitch, True, context.scene.f3d_type, 
				context.scene.isHWv1)
			romfileSrc.close()

			bpy.ops.object.select_all(action = 'DESELECT')
			if armatureObj is not None:
				for armatureMeshGroup in armatureMeshGroups:
					armatureMeshGroup[0].select_set(True)
				bpy.ops.transform.rotate(value = math.radians(-90),
					orient_axis='X')

				for armatureMeshGroup in armatureMeshGroups:
					bpy.ops.object.select_all(action = 'DESELECT')
					armatureMeshGroup[0].select_set(True)
					bpy.context.view_layer.objects.active = armatureMeshGroup[0]
					bpy.ops.object.make_single_user(obdata = True)
					bpy.ops.object.transform_apply(location = False, 
						rotation = True, scale = False, properties =  False)
			else:
				bpy.ops.transform.rotate(value = math.radians(-90),
					orient_axis='X')
			bpy.ops.object.select_all(action = 'DESELECT')
			#objs[-1].select_set(True)

			self.report({'INFO'}, 'Generic import succeeded.')
			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			romfileSrc.close()
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ImportGeolayoutPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_import_geolayout"
	bl_label = "SM64 Geolayout Importer"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsGeoI = col.operator(SM64_ImportGeolayout.bl_idname)

		propsGeoI.generateArmature = context.scene.generateArmature
		propsGeoI.geoImportAddr = context.scene.geoImportAddr
		propsGeoI.levelGeoImport = context.scene.levelGeoImport
		propsGeoI.importRom = context.scene.importRom
		propsGeoI.ignoreSwitch = context.scene.ignoreSwitch
		
		#col.prop(context.scene, 'rotationOrder')
		#col.prop(context.scene, 'rotationAxis')
		#col.prop(context.scene, 'rotationAngle')
		prop_split(col, context.scene, 'geoImportAddr', 'Start Address')
		col.prop(context.scene, 'levelGeoImport')
		col.prop(context.scene, 'generateArmature')
		col.prop(context.scene, 'ignoreSwitch')
		if not context.scene.ignoreSwitch:
			boxLayout = col.box()
			boxLayout.label(text = "WARNING: May take a long time.")
			boxLayout.label(text = "Switch nodes won't be setup.")
		col.box().label(text = "Only Fast3D mesh importing allowed.")
		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ExportGeolayout(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_geolayout'
	bl_label = "Export Geolayout"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	geoExportStart : bpy.props.StringProperty(name = 'Start',
		default = '11D8930')
	geoExportEnd : bpy.props.StringProperty(name = 'End',
		default = '11FFF00')
	overwriteModelLoad: bpy.props.BoolProperty(
		name = 'Overwrite model load in level script?', default = True)
	modelLoadLevelScriptCmd : bpy.props.StringProperty(
		name = 'Level script model load command', default = '2ABD90')
	modelID : bpy.props.IntProperty(name = 'Model ID', default = 0xBB)
	geoUseBank0 : bpy.props.BoolProperty(name = 'Use Bank 0')
	geoRAMAddr : bpy.props.StringProperty(name = 'RAM Address', 
		default = '80000000')

	exportRom : bpy.props.StringProperty(name ='Export ROM', subtype = 'FILE_PATH')
	outputRom : bpy.props.StringProperty(name ='Output ROM', subtype = 'FILE_PATH')
	levelGeoExport : bpy.props.EnumProperty(items = level_enums, 
		name = 'Level Used By Geolayout Export', default = 'CG')
	
	textDumpGeo : bpy.props.BoolProperty(
		name = 'Dump geolayout as text', default = False)
	textDumpGeoPath :  bpy.props.StringProperty(
		name ='Text Dump Path', subtype = 'FILE_PATH')

	geoExportType : bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	geoExportPath : bpy.props.StringProperty(
		name = 'Geo Path', subtype = 'FILE_PATH')
	geoExportPathDL : bpy.props.StringProperty(
		name = 'DL Path', subtype = 'FILE_PATH')
	geoDefinePath : bpy.props.StringProperty(
		name = 'Defines Path', subtype = 'FILE_PATH')

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		tempROM = tempName(self.outputRom)
		armatureObj = None
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		if len(context.selected_objects) == 0:
			raise ValueError("Armature not selected.")
		armatureObj = context.active_object
		if type(armatureObj.data) is not bpy.types.Armature:
			raise ValueError("Armature not selected.")

		obj = armatureObj.children[0]
		finalTransform = mathutils.Matrix.Identity(4)

		# get all switch option armatures as well
		linkedArmatures = [armatureObj]
		getAllArmatures(armatureObj, linkedArmatures)

		linkedArmatureDict = {}

		for linkedArmature in linkedArmatures:
			# IMPORTANT: Do this BEFORE rotation
			optionObjs = []
			for childObj in linkedArmature.children:
				if isinstance(childObj.data, bpy.types.Mesh):
					optionObjs.append(childObj)
			if len(optionObjs) > 1:
				raise ValueError('Error: ' + linkedArmature.name +\
					' has more than one mesh child.')
			elif len(optionObjs) < 1:
				raise ValueError('Error: ' + linkedArmature.name +\
					' has no mesh children.')
			linkedMesh = optionObjs[0]
			prepareGeolayoutExport(linkedArmature, linkedMesh)
			linkedArmatureDict[linkedArmature] = linkedMesh
		
		# Rotate all armatures 90 degrees
		bpy.ops.object.select_all(action = "DESELECT")
		for linkedArmature in linkedArmatures:
			linkedArmature.select_set(True)
		armatureObj.select_set(True)

		bpy.ops.transform.rotate(value = math.radians(90), orient_axis='X')
		bpy.ops.object.transform_apply(location = False, rotation = True,
			scale = False, properties =  False)
		
		# You must ALSO apply object rotation after armature rotation.
		bpy.ops.object.select_all(action = "DESELECT")
		for linkedArmature, linkedMesh in linkedArmatureDict.items():
			linkedMesh.select_set(True)
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		bpy.ops.object.transform_apply(location = False, rotation = True,
			scale = False, properties =  False)

		try:
			if self.geoExportType == 'C':
				exportGeolayoutC(armatureObj, obj, finalTransform,
					context.scene.f3d_type, context.scene.isHWv1,
					bpy.path.abspath(self.geoExportPath), 
					bpy.path.abspath(self.geoExportPathDL),
					bpy.path.abspath(self.geoDefinePath))
				self.report({'INFO'}, 'Success! Geolayout at ' + \
					self.geoExportPath + ', DL at ' + self.geoExportPathDL)
			else:
				checkExpanded(bpy.path.abspath(self.exportRom))
				romfileExport = open(bpy.path.abspath(self.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(self.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[self.levelGeoExport])
				segmentData = levelParsed.segmentData

				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				exportRange = [int(self.geoExportStart, 16), 
					int(self.geoExportEnd, 16)]
				textDumpFilePath = bpy.path.abspath(self.textDumpGeoPath) \
					if self.textDumpGeo else None
				if self.overwriteModelLoad:
					modelLoadInfo = (int(self.modelLoadLevelScriptCmd, 16),
						self.modelID)
				else:
					modelLoadInfo = (None, None)

				if self.geoUseBank0:
					addrRange, startRAM = exportGeolayoutBinaryBank0(
						romfileOutput, armatureObj, obj, exportRange, 
 						finalTransform, *modelLoadInfo, textDumpFilePath,
						context.scene.f3d_type, context.scene.isHWv1, 
						getAddressFromRAMAddress(int(self.geoRAMAddr, 16)))
				else:
					addrRange, segPointer = exportGeolayoutBinary(
						romfileOutput, armatureObj, obj,
						exportRange, finalTransform, segmentData,
						*modelLoadInfo, textDumpFilePath, 
						context.scene.f3d_type, context.scene.isHWv1)

				romfileOutput.close()
				bpy.ops.object.select_all(action = 'DESELECT')
				armatureObj.select_set(True)
				context.view_layer.objects.active = armatureObj

				os.remove(bpy.path.abspath(self.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(self.outputRom))

				if self.geoUseBank0:
					self.report({'INFO'}, 'Success! Geolayout at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						'), to write to RAM Address ' + hex(startRAM))
				else:
					self.report({'INFO'}, 'Success! Geolayout at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						') (Seg. ' + segPointer + ').')

			bpy.ops.object.select_all(action = "DESELECT")
			for linkedArmature in linkedArmatures:
				linkedArmature.select_set(True)
			armatureObj.select_set(True)
			context.view_layer.objects.active = armatureObj
			bpy.ops.transform.rotate(value = math.radians(-90), orient_axis='X')
			bpy.ops.object.transform_apply(location = False, rotation = True,
				scale = False, properties =  False)

			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			bpy.ops.object.select_all(action = "DESELECT")
			for linkedArmature in linkedArmatures:
				linkedArmature.select_set(True)
			armatureObj.select_set(True)
			context.view_layer.objects.active = armatureObj
			bpy.ops.transform.rotate(value = math.radians(-90), orient_axis='X')
			bpy.ops.object.transform_apply(location = False, rotation = True,
				scale = False, properties =  False)

			romfileOutput.close()
			os.remove(bpy.path.abspath(tempROM))
			if armatureObj is not None:
				armatureObj.select_set(True)
				context.view_layer.objects.active = armatureObj
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ExportGeolayoutPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_geolayout"
	bl_label = "SM64 Geolayout Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsGeoE = col.operator(SM64_ExportGeolayout.bl_idname)
		propsGeoE.geoExportStart = context.scene.geoExportStart
		propsGeoE.geoExportEnd = context.scene.geoExportEnd
		propsGeoE.levelGeoExport = context.scene.levelGeoExport
		propsGeoE.exportRom = context.scene.exportRom
		propsGeoE.outputRom = context.scene.outputRom
		propsGeoE.overwriteModelLoad = context.scene.overwriteModelLoad
		propsGeoE.modelLoadLevelScriptCmd = context.scene.modelLoadLevelScriptCmd
		propsGeoE.modelID = context.scene.modelID
		propsGeoE.textDumpGeo = context.scene.textDumpGeo
		propsGeoE.textDumpGeoPath = context.scene.textDumpGeoPath
		propsGeoE.geoExportType = context.scene.geoExportType
		propsGeoE.geoExportPath = context.scene.geoExportPath
		propsGeoE.geoExportPathDL = context.scene.geoExportPathDL
		propsGeoE.geoDefinePath = context.scene.geoDefinePath
		propsGeoE.geoUseBank0 = context.scene.geoUseBank0
		propsGeoE.geoRAMAddr = context.scene.geoRAMAddr

		col.prop(context.scene, 'geoExportType')
		if propsGeoE.geoExportType == 'C':
			col.prop(context.scene, 'geoExportPath')
			col.prop(context.scene, 'geoExportPathDL')
			col.prop(context.scene, 'geoDefinePath')
		else:
			prop_split(col, context.scene, 'geoExportStart', 'Start Address')
			prop_split(col, context.scene, 'geoExportEnd', 'End Address')

			col.prop(context.scene, 'geoUseBank0')
			if propsGeoE.geoUseBank0:
				prop_split(col, context.scene, 'geoRAMAddr', 'RAM Address')
			else:
				col.prop(context.scene, 'levelGeoExport')

			col.prop(context.scene, 'overwriteModelLoad')
			if context.scene.overwriteModelLoad:
				prop_split(col, context.scene, 'modelLoadLevelScriptCmd', 'Model Load Command')
				col.prop(context.scene, 'modelID')
			col.prop(context.scene, 'textDumpGeo')
			if context.scene.textDumpGeo:
				col.prop(context.scene, 'textDumpGeoPath')
		
		for i in range(panelSeparatorSize):
			col.separator()
		
class SM64_ArmatureToolsPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_armature_tools"
	bl_label = "SM64 Armature Tools"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.operator(ArmatureApplyWithMesh.bl_idname)
		col.operator(AddBoneGroups.bl_idname)
		col.operator(CreateMetarig.bl_idname)
		#col.operator(N64_AddF3dMat.bl_idname)

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ImportDL(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_import_dl'
	bl_label = "Import Display List"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	DLImportStart : bpy.props.StringProperty(name ='Import Start', 
		default = 'A3BE1C')
	levelDLImport : bpy.props.EnumProperty(items = level_enums, name = 'Level Used By Display List', default = 'CG')
	importRom : bpy.props.StringProperty(name ='Import ROM', subtype = 'FILE_PATH')
	isSegmentedAddrDLImport : bpy.props.BoolProperty(name = 'Is Segmented Address', default = False)

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		try:
			checkExpanded(bpy.path.abspath(self.importRom))
			romfileSrc = open(bpy.path.abspath(self.importRom), 'rb')
			levelParsed = parseLevelAtPointer(romfileSrc, 
				level_pointers[self.levelDLImport])
			segmentData = levelParsed.segmentData
			start = decodeSegmentedAddr(
				int(self.DLImportStart, 16).to_bytes(4, 'big'), segmentData)\
				if self.isSegmentedAddrDLImport else \
				int(self.DLImportStart, 16)
			readObj = F3DtoBlenderObject(romfileSrc, start, 
				context.scene, 'sm64_mesh', 
				blenderToSM64Rotation.to_4x4().inverted(),
				segmentData, True)
			romfileSrc.close()

			self.report({'INFO'}, 'Generic import succeeded.')
			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			romfileSrc.close()
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ImportDLPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_import_dl"
	bl_label = "SM64 DL Importer"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsDLI = col.operator(SM64_ImportDL.bl_idname)

		propsDLI.DLImportStart = context.scene.DLImportStart
		propsDLI.levelDLImport = context.scene.levelDLImport
		propsDLI.importRom = context.scene.importRom
		propsDLI.isSegmentedAddrDLImport = context.scene.isSegmentedAddrDLImport
		prop_split(col, context.scene, 'DLImportStart', 'Start Address')
		col.prop(context.scene, 'levelDLImport')
		col.prop(context.scene, 'isSegmentedAddrDLImport')
		col.box().label(text = "Only Fast3D mesh importing allowed.")

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ExportDL(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_dl'
	bl_label = "Export Display List"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	exportRom : bpy.props.StringProperty(name ='Export ROM', subtype = 'FILE_PATH')
	outputRom : bpy.props.StringProperty(name ='Output ROM', subtype = 'FILE_PATH')
	levelDLExport : bpy.props.EnumProperty(items = level_enums, 
		name = 'Level Used By Display List', default = 'CG')
	DLExportStart : bpy.props.StringProperty(
		name = 'Start', default = 'A3BE1C')
	DLExportEnd : bpy.props.StringProperty(
		name = 'End', default = 'A4BE1C')
	DLExportGeoPtr : bpy.props.StringProperty(
		name ='Geolayout Pointer', default = 'A3BE1C')
	overwriteGeoPtr : bpy.props.BoolProperty(name = "Overwrite geolayout pointer", default = False)
	DLExportType : bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	DLExportPath : bpy.props.StringProperty(
		name = 'Path', subtype = 'FILE_PATH')
	DLDefinePath : bpy.props.StringProperty(
		name = 'Defines Path', subtype = 'FILE_PATH')
	DLExportisStatic : bpy.props.BoolProperty(name = 'Static DL', 
		default = True)
	DLUseBank0 : bpy.props.BoolProperty(name = 'Use Bank 0')
	DLRAMAddr : bpy.props.StringProperty(name = 'RAM Address', 
		default = '80000000')

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		checkExpanded(bpy.path.abspath(self.exportRom))
		tempROM = tempName(self.outputRom)
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")	
		allObjs = context.selected_objects
		if len(allObjs) == 0:
			raise ValueError("No objects selected.")
		obj = context.selected_objects[0]
		if not isinstance(obj.data, bpy.types.Mesh):
			raise ValueError("Object is not a mesh.")

		T, R, S = obj.matrix_world.decompose()
		objTransform = R.to_matrix().to_4x4() @ \
			mathutils.Matrix.Diagonal(S).to_4x4()
		finalTransform = (blenderToSM64Rotation * \
			(1/sm64ToBlenderScale)).to_4x4() @ objTransform
		
		try:
			if self.DLExportType == 'C':
				exportF3DtoC(bpy.path.abspath(self.DLExportPath), 
					bpy.path.abspath(self.DLDefinePath), obj,
					self.DLExportisStatic, finalTransform,
					context.scene.f3d_type, context.scene.isHWv1)
				self.report({'INFO'}, 'Success! DL at ' + \
					self.DLExportPath + '.')
				return {'FINISHED'} # must return a set
			else:
				romfileExport = open(bpy.path.abspath(self.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(self.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[self.levelDLExport])
				segmentData = levelParsed.segmentData
				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				if self.DLUseBank0:
					startAddress, addrRange, segPointerData = \
						exportF3DtoBinaryBank0(romfileOutput, 
						[int(self.DLExportStart, 16), int(self.DLExportEnd, 16)],
					 	finalTransform, obj, context.scene.f3d_type,
						context.scene.isHWv1, 
						getAddressFromRAMAddress(int(self.DLRAMAddr, 16)))
				else:
					startAddress, addrRange, segPointerData = \
						exportF3DtoBinary(romfileOutput, 
						[int(self.DLExportStart, 16), int(self.DLExportEnd, 16)],
					 	finalTransform, obj, context.scene.f3d_type,
						context.scene.isHWv1, segmentData)
				
				if self.overwriteGeoPtr:
					romfileOutput.seek(int(self.DLExportGeoPtr, 16))
					romfileOutput.write(segPointerData)
	
				romfileOutput.close()
				os.remove(bpy.path.abspath(self.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(self.outputRom))
				
				if self.DLUseBank0:
					self.report({'INFO'}, 'Success! DL at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						'), ' +\
						'to write to RAM address ' + \
						hex(startAddress + 0x80000000))
				else:
					
					self.report({'INFO'}, 'Success! DL at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						') (Seg. ' + bytesToHex(segPointerData) + ').')
				return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			romfileOutput.close()
			os.remove(bpy.path.abspath(tempROM))
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ExportDLPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_dl"
	bl_label = "SM64 DL Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsDLE = col.operator(SM64_ExportDL.bl_idname)
		propsDLE.DLExportStart= context.scene.DLExportStart
		propsDLE.DLExportEnd = context.scene.DLExportEnd
		propsDLE.exportRom = context.scene.exportRom
		propsDLE.outputRom = context.scene.outputRom
		propsDLE.levelDLExport = context.scene.levelDLExport
		propsDLE.DLExportGeoPtr = context.scene.DLExportGeoPtr
		propsDLE.overwriteGeoPtr = context.scene.overwriteGeoPtr
		propsDLE.DLExportType = context.scene.DLExportType
		propsDLE.DLExportPath = context.scene.DLExportPath
		propsDLE.DLExportisStatic = context.scene.DLExportisStatic
		propsDLE.DLDefinePath = context.scene.DLDefinePath
		propsDLE.DLUseBank0 = context.scene.DLUseBank0
		propsDLE.DLRAMAddr = context.scene.DLRAMAddr

		col.prop(context.scene, 'DLExportType')
		if propsDLE.DLExportType == 'C':
			col.prop(context.scene, 'DLExportPath')
			col.prop(context.scene, 'DLExportisStatic')
			col.prop(context.scene, 'DLDefinePath')
		else:
			prop_split(col, context.scene, 'DLExportStart', 'Start Address')
			prop_split(col, context.scene, 'DLExportEnd', 'End Address')
			col.prop(context.scene, 'DLUseBank0')
			if propsDLE.DLUseBank0:
				prop_split(col, context.scene, 'DLRAMAddr', 'RAM Address')
			else:
				col.prop(context.scene, 'levelDLExport')
			col.prop(context.scene, 'overwriteGeoPtr')
			if context.scene.overwriteGeoPtr:
				prop_split(col, context.scene, 'DLExportGeoPtr', 
					'Geolayout Pointer')
		
		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ExportMario(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export'
	bl_label = "Export Character"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	exportRom : bpy.props.StringProperty(name ='Export ROM', subtype = 'FILE_PATH')
	outputRom : bpy.props.StringProperty(name ='Output ROM', subtype = 'FILE_PATH')
	useFaceAnimation : bpy.props.BoolProperty(name ='Use Face Animation?')
	overwriteWingPositions : bpy.props.BoolProperty(name ='Overwrite Wing Positions? (See attatched diagram)')
	segment4 : bpy.props.IntVectorProperty(name="Segment 4", 
		default=defaultExtendSegment4, size = 2)
	exportRange : bpy.props.IntVectorProperty(name="Export range", 
		default=marioFullRomInterval, size = 2)
	useCustomSegment4 : bpy.props.BoolProperty(name = "Use custom segment 4?", default = True)
	sm64_character : bpy.props.EnumProperty(
		items = character_enums, name = 'SM64 Character', default = 'Mario'
	)

	useLogFile : bpy.props.BoolProperty(name ='Write log file?')
	logFilePath : bpy.props.StringProperty(name = 'Log File', subtype = 'FILE_PATH')

	def execute(self, context):
		tempROM = tempName(self.outputRom)
		try:
			romfileExport = open(self.exportRom, 'rb')		
			shutil.copy(self.exportRom, tempROM)
			romfileExport.close()
			romfileOutput = open(tempROM, 'rb+')

			segmentData = {}
			readSegment4(romfileOutput, segmentData)
			print("Export range: " + hex(self.exportRange[0]) + " - " + hex(self.exportRange[1]))

			armatureData = character_data[self.sm64_character]
			isMario = self.sm64_character == 'Mario'
	
			if self.useCustomSegment4:
				ExtendBank0x04(romfileOutput, segmentData, self.segment4)

			if isMario:
				DisableLowPolyMario(romfileOutput, armatureData.geolayoutStart)
	
			# Find armature.
			armatureObj = None
			armature = None
			for obj in bpy.context.selected_objects:
				if isinstance(obj.data, bpy.types.Armature):
					armatureObj = obj
					armature = armatureObj.data
					break
			if armature is None:
				romfileOutput.close()
				self.report({'ERROR'}, 'Mario armature not selected.')
				return {'CANCELLED'} # must return a set
	
			# Update geolayout translation offsets

			if isMario and not self.overwriteWingPositions:
				saveExistingGeolayoutTransforms(romfileOutput, armatureObj, 
					armatureData.geolayoutStart, armatureData, blenderToSM64Rotation, 
					True)
			elif isMario:
				saveExistingGeolayoutTransforms(romfileOutput, armatureObj, 
					armatureData.geolayoutStart, armatureData, blenderToSM64Rotation, False) 

			bodyParts = []
			for obj in bpy.context.scene.objects:
				if isinstance(obj.data, bpy.types.Mesh) and\
					len(obj.data.loops) > 0:
	
					for constraint in obj.constraints:
						if isinstance(constraint, bpy.types.ChildOfConstraint) and\
							constraint.target == armatureObj:
	
							bodyParts.append(obj)
	
			if isMario:
				success = importMario(bodyParts, self, romfileOutput, context, 'Y', segmentData, armatureObj,
					self.exportRange[0], self.exportRange[1])
			else:
				success = importGeolayout(bodyParts, self, romfileOutput, context, 'Y', segmentData, 
					armatureObj, self.exportRange[0], self.exportRange[1],
					armatureData, False)

			armatureObj.select_set(True)
			romfileOutput.close()
			os.remove(self.outputRom)
			os.rename(tempROM, self.outputRom)
	
			if success:
				self.report({'INFO'}, 'Export succeeded.')
				return {'FINISHED'} # must return a set
			else:
				self.report({'INFO'}, 'Export failed.')
				return {'CANCELLED'} # must return a set
		except:
			self.report({'ERROR'}, traceback.format_exc())
			romfileOutput.close()
			os.remove(tempROM)
			return {'CANCELLED'} # must return a set

class SM64_ExportCharacterPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_character"
	bl_label = "SM64 Character Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsE = col.operator(SM64_ExportMario.bl_idname)
		propsE.sm64_character = context.scene.sm64_character
		propsE.exportRom = context.scene.exportRom
		propsE.outputRom = context.scene.outputRom
		propsE.useFaceAnimation = context.scene.useFaceAnimation
		propsE.overwriteWingPositions = context.scene.overwriteWingPositions
		propsE.exportRange = context.scene.exportRange
		propsE.useCustomSegment4 = context.scene.useCustomSegment4
		propsE.segment4 = context.scene.segment4
		propsE.useLogFile = context.scene.useLogFile
		propsE.logFilePath = context.scene.logFilePath

		col.prop(context.scene, 'useFaceAnimation')
		col.prop(context.scene, 'overwriteWingPositions')
		col.prop(context.scene, 'useCustomSegment4')
		if context.scene.useCustomSegment4:
			col.prop(context.scene, 'segment4')
		col.prop(context.scene, 'exportRange')
	
		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ImportMario(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_import'
	bl_label = "Import Character"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	sm64_character : bpy.props.EnumProperty(
		items = character_enums, name = 'SM64 Character', default = 'Mario'
	)

	importRom : bpy.props.StringProperty(name ='Import ROM', subtype = 'FILE_PATH')
	characterIgnoreSwitch : bpy.props.BoolProperty(name = 'Ignore Switch Nodes', default = True)

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		#finalTransform = mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
		finalTransform = mathutils.Matrix.Identity(4)
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		try:
			romfileSrc = open(bpy.path.abspath(self.importRom), 'rb')
			checkExpanded(bpy.path.abspath(self.importRom))

			characterImportData = sm64_character_data[self.sm64_character]

			# Armature mesh groups includes armatureObj.
			armatureMeshGroups, armatureObj = parseGeoLayout(romfileSrc, 
				int(characterImportData.geoAddr, 16),
			 	context.scene, characterImportData.level, 
				finalTransform, True, 
				self.characterIgnoreSwitch, True, context.scene.f3d_type, 
				context.scene.isHWv1, characterImportData.switchDict)
			romfileSrc.close()

			bpy.ops.object.select_all(action = 'DESELECT')
			if armatureObj is not None:
				for armatureMeshGroup in armatureMeshGroups:
					armatureMeshGroup[0].select_set(True)
				bpy.ops.transform.rotate(value = math.radians(-90),
					orient_axis='X')

				for armatureMeshGroup in armatureMeshGroups:
					bpy.ops.object.select_all(action = 'DESELECT')
					armatureMeshGroup[0].select_set(True)
					bpy.context.view_layer.objects.active = armatureMeshGroup[0]
					bpy.ops.object.make_single_user(obdata = True)
					bpy.ops.object.transform_apply(location = False, 
						rotation = True, scale = False, properties =  False)
			else:
				bpy.ops.transform.rotate(value = math.radians(-90),
					orient_axis='X')
			bpy.ops.object.select_all(action = 'DESELECT')
			#objs[-1].select_set(True)

			self.report({'INFO'}, 'Generic import succeeded.')
			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			romfileSrc.close()
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ImportCharacterPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_import_character"
	bl_label = "SM64 Character Importer"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.prop(context.scene, 'sm64_character')
		col.prop(context.scene, 'characterIgnoreSwitch')
		propsI = col.operator(SM64_ImportMario.bl_idname)
		propsI.importRom = context.scene.importRom
		propsI.sm64_character = context.scene.sm64_character
		propsI.characterIgnoreSwitch = context.scene.characterIgnoreSwitch

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ImportLevel(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_import_lvl'
	bl_label = "Import Level"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	importRom : bpy.props.StringProperty(name ='Import ROM', subtype = 'FILE_PATH')
	levelLevel : bpy.props.EnumProperty(items = level_enums, 
		name = 'Level', default = 'CG')

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		try:
			romfileSrc = open(self.importRom, 'rb')
			levelParsed = parseLevelAtPointer(romfileSrc, level_pointers[self.levelLevel])
			segmentData = levelParsed.segmentData

			areaGeos = [parseGeoLayout(romfileSrc, decodeSegmentedAddr(
				area.geoAddress, segmentData), context.scene, self.levelLevel,
				mathutils.Matrix.Rotation(math.radians(90), 4, 'X'), False,
				True, False, context.scene.f3d_type, context.scene.isHWv1) \
				for area in levelParsed.areas]
	
			romfileSrc.close()
	
			return {'FINISHED'} # must return a set
		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			self.report({'ERROR'}, traceback.format_exc())
			romfileSrc.close()
			return {'CANCELLED'} # must return a set

class SM64_ImportLevelPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_import_level"
	bl_label = "SM64 Level Importer"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsLI = col.operator(SM64_ImportLevel.bl_idname)
		#propsLE = col.operator(SM64_ExportLevel.bl_idname)

		propsLI.levelLevel = context.scene.levelLevel
		propsLI.importRom = context.scene.importRom
		col.prop(context.scene, 'levelLevel')

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ExportLevel(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_lvl'
	bl_label = "Export Level"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	exportRom : bpy.props.StringProperty(name ='Export ROM', subtype = 'FILE_PATH')
	outputRom : bpy.props.StringProperty(name ='Output ROM', subtype = 'FILE_PATH')
	levelLevel : bpy.props.EnumProperty(items = level_enums, 
		name = 'Level', default = 'CG')

	def execute(self, context):
		tempROM = tempName(self.outputRom)
		try:
			romfileExport = open(bpy.path.abspath(self.exportRom), 'rb')		
			shutil.copy(bpy.path.abspath(self.exportRom), 
				bpy.path.abspath(tempROM))
			romfileExport.close()
			romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

			segmentData = {}
			ExtendBank0x04(romfileOutput, segmentData, defaultExtendSegment4)
			DisableLowPolyMario(romfileOutput, character_data["Mario"].geolayoutStart)
	
			allObjs = context.selected_objects
			bpy.ops.object.select_all(action = 'DESELECT')
			for obj in allObjs:
				if 'sm64_rom_start' in obj and \
					'sm64_rom_end' in obj and \
					'sm64_geolayout_pointers' in obj:
	
					start = obj['sm64_rom_start']
					end = obj['sm64_rom_end']
					geo = obj['sm64_geolayout_pointers']

					if 'sm64_draw_layer' in obj:
						drawLayer = obj['sm64_draw_layer']
					else:
						drawLayer = 0x01
	
					success = importGeneric(romfileOutput, obj, context, 'Y', start, 
						end, levelEnum, geo, blenderToSM64Rotation,
						drawLayer, verbose = True)
					if not success:
						self.report({'ERROR'}, 'Model is too large.')
						romfileOutput.close()
						return {'CANCELLED'} # must return a set

					obj.select_set(True)
	
				else:
					self.report({'ERROR'}, obj.name + \
						" does not have correct custom properties.")
	
	
			romfileOutput.close()
			os.remove(self.outputRom)
			os.rename(tempROM, self.outputRom)
			self.report({'INFO'}, 'Export succeeded.')
			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			romfileOutput.close()
			os.remove(tempROM)
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ExportLevelPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_level"
	bl_label = "SM64 Level Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsLE.exportRom = context.scene.exportRom
		propsLE.outputRom = context.scene.outputRom
		propsLE.levelLevel = context.scene.levelLevel

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ImportAnimMario(bpy.types.Operator):
	bl_idname = 'object.sm64_import_anim'
	bl_label = "Import Animation"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	animStartImport : bpy.props.StringProperty(name ='Import Start', 
		default = '4EC690')
	importRom : bpy.props.StringProperty(name ='Import ROM', subtype = 'FILE_PATH')
	isDMAImport: bpy.props.BoolProperty(name = 'Is DMA Animation Import')
	levelAnimImport : bpy.props.EnumProperty(items = level_enums, name = 'Level Used By Animation', default = 'CG')

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		checkExpanded(bpy.path.abspath(self.importRom))
		romfileSrc = open(bpy.path.abspath(self.importRom), 'rb')
		try:
			# Note actual level doesn't matter for Mario, since he is in all of them
			#levelParsed = parseLevelAtPointer(romfileSrc, level_pointers['CC'])
			#segmentData = levelParsed.segmentData
			if len(context.selected_objects) == 0:
				raise ValueError("Armature not selected.")
			armatureObj = context.active_object
			if type(armatureObj.data) is not bpy.types.Armature:
				raise ValueError("Armature not selected.")
			levelParsed = parseLevelAtPointer(romfileSrc, level_pointers	[self.levelAnimImport])
			segmentData = levelParsed.segmentData
			importAnimationToBlender(romfileSrc, 
				int(self.animStartImport, 16), armatureObj, 
				segmentData, self.isDMAImport)
			romfileSrc.close()
		except:
			romfileSrc.close()
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

		return {'FINISHED'} # must return a set

class SM64_ImportAnimPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_import_anim"
	bl_label = "SM64 Animation Importer"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsAnimImport = col.operator(SM64_ImportAnimMario.bl_idname)
		propsAnimImport.animStartImport = context.scene.animStartImport
		propsAnimImport.importRom = context.scene.importRom
		propsAnimImport.isDMAImport = context.scene.isDMAImport
		propsAnimImport.levelAnimImport = context.scene.levelAnimImport
		col.prop(context.scene, 'isDMAImport')
		prop_split(col, context.scene, 'animStartImport', 'Start Address')
		col.prop(context.scene, 'levelAnimImport')

		for i in range(panelSeparatorSize):
			col.separator()
		
class SM64_ExportAnimMario(bpy.types.Operator):
	bl_idname = 'object.sm64_export_anim'
	bl_label = "Export Animation"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	animExportStart : bpy.props.StringProperty(name ='Start', 
		default = '11D8930')
	animExportEnd : bpy.props.StringProperty(name ='End', 
		default = '11FFF00')
	exportRom : bpy.props.StringProperty(name ='Export ROM', subtype = 'FILE_PATH')
	outputRom : bpy.props.StringProperty(name ='Output ROM', subtype = 'FILE_PATH')
	isDMAExport : bpy.props.BoolProperty(name = 'Is DMA Animation Export')
	DMAEntryAddress : bpy.props.StringProperty(name = 'DMA Entry Address')
	DMAStartAddress : bpy.props.StringProperty(name = 'DMA Start Address')
	levelAnimExport : bpy.props.EnumProperty(items = level_enums, name = 'Level Used By Animation', default = 'CG')
	loopAnimation : bpy.props.BoolProperty(name = 'Loop Animation', default = True)
	overwrite_0x27 : bpy.props.BoolProperty(
		name = 'Overwrite 0x27 behaviour command')
	overwrite_0x28 : bpy.props.BoolProperty(
		name = 'Overwrite 0x28 behaviour command')
	addr_0x27 : bpy.props.StringProperty(name = '0x27 Command Address', 
		default = '21CD00')
	addr_0x28 : bpy.props.StringProperty(name = '0x28 Command Address', 
		default = '21CD08')
	animExportType : bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	animExportPath : bpy.props.StringProperty(
		name = 'Path', subtype = 'FILE_PATH')
	animOverwriteDMAEntry : bpy.props.BoolProperty(name = 'Overwrite DMA Entry')

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		checkExpanded(bpy.path.abspath(self.exportRom))
		tempROM = tempName(self.outputRom)
		if len(context.selected_objects) == 0 or not \
			isinstance(context.selected_objects[0].data, bpy.types.Armature):
			raise ValueError("Armature not selected.")
		armatureObj = context.selected_objects[0]

		if self.animExportType == 'C':
			try:
				exportAnimationC(armatureObj, self.loopAnimation, 
					bpy.path.abspath(self.animExportPath))
				self.report({'INFO'}, 'Success! Animation at ' +\
					self.animExportPath)
			except:
				self.report({'ERROR'}, traceback.format_exc())
				return {'CANCELLED'} # must return a set
		else:
			try:
				romfileExport = open(bpy.path.abspath(self.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(self.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')
			
				# Note actual level doesn't matter for Mario, since he is in all of 	them
				levelParsed = parseLevelAtPointer(romfileOutput, level_pointers		[self.levelAnimExport])
				segmentData = levelParsed.segmentData
				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				DMAAddresses = None
				if self.animOverwriteDMAEntry:
					DMAAddresses = {}
					DMAAddresses['start'] = int(self.DMAStartAddress, 16)
					DMAAddresses['entry'] = int(self.DMAEntryAddress, 16)

				addrRange, nonDMAListPtr = exportAnimationBinary(
					romfileOutput, [int(self.animExportStart, 16), 
					int(self.animExportEnd, 16)], bpy.context.active_object,
					DMAAddresses, segmentData, self.isDMAExport,
					self.loopAnimation)

				if not self.isDMAExport:
					segmentedPtr = encodeSegmentedAddr(nonDMAListPtr, segmentData)
					if self.overwrite_0x27:
						romfileOutput.seek(int(self.addr_0x27, 16) + 4)
						romfileOutput.write(segmentedPtr)
					if self.overwrite_0x28:
						romfileOutput.seek(int(self.addr_0x28, 16) + 1)
						romfileOutput.write(bytearray([0x00]))
				else:
					segmentedPtr = None
						
				romfileOutput.close()
				os.remove(bpy.path.abspath(self.outputRom))
				os.rename(bpy.path.abspath(tempROM),
					bpy.path.abspath(self.outputRom))
	
				if not self.isDMAExport:
					self.report({'INFO'}, 'Sucess! Animation table at ' + \
						hex(nonDMAListPtr) + ' (Seg. ' + \
						bytesToHex(segmentedPtr) + '), animation at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + ').')
				else:
					self.report({'INFO'}, 'Success! Animation at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + ').')
			except:
				romfileOutput.close()
				os.remove(bpy.path.abspath(tempROM))
				self.report({'ERROR'}, traceback.format_exc())
				return {'CANCELLED'} # must return a set

		return {'FINISHED'} # must return a set

class SM64_ExportAnimPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_anim"
	bl_label = "SM64 Animation Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsAnimExport = col.operator(SM64_ExportAnimMario.bl_idname)
		propsAnimExport.animExportStart = context.scene.animExportStart
		propsAnimExport.animExportEnd = context.scene.animExportEnd
		propsAnimExport.exportRom = context.scene.exportRom
		propsAnimExport.outputRom = context.scene.outputRom
		propsAnimExport.isDMAExport = context.scene.isDMAExport
		propsAnimExport.DMAEntryAddress = context.scene.DMAEntryAddress
		propsAnimExport.DMAStartAddress = context.scene.DMAStartAddress
		propsAnimExport.levelAnimExport = context.scene.levelAnimExport
		propsAnimExport.loopAnimation = context.scene.loopAnimation
		propsAnimExport.overwrite_0x27 = context.scene.overwrite_0x27
		propsAnimExport.addr_0x27 = context.scene.addr_0x27
		propsAnimExport.overwrite_0x28 = context.scene.overwrite_0x28
		propsAnimExport.addr_0x28 = context.scene.addr_0x28
		propsAnimExport.animExportType = context.scene.animExportType 
		propsAnimExport.animExportPath = context.scene.animExportPath
		propsAnimExport.animOverwriteDMAEntry = \
			context.scene.animOverwriteDMAEntry
		
		col.prop(context.scene, 'animExportType')
		col.prop(context.scene, 'loopAnimation')
		if propsAnimExport.animExportType == 'C':
			col.prop(context.scene, 'animExportPath')
		else:
			col.prop(context.scene, 'isDMAExport')
			if context.scene.isDMAExport:
				col.prop(context.scene, 'animOverwriteDMAEntry')
				if context.scene.animOverwriteDMAEntry:
					prop_split(col, context.scene, 'DMAStartAddress', 
						'DMA Start Address')
					prop_split(col, context.scene, 'DMAEntryAddress', 
						'DMA Entry Address')
			else:
				col.prop(context.scene, 'overwrite_0x27')
				if context.scene.overwrite_0x27:
					prop_split(col, context.scene, 'addr_0x27', 
						'27 Command Address')
				col.prop(context.scene, 'overwrite_0x28')
				if context.scene.overwrite_0x28:
					prop_split(col, context.scene, 'addr_0x28', 
						'28 Command Address')
				col.prop(context.scene, 'levelAnimExport')
			col.separator()
			prop_split(col, context.scene, 'animExportStart', 'Start Address')
			prop_split(col, context.scene, 'animExportEnd', 'End Address')
			

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ExportCollision(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_collision'
	bl_label = "Export Collision"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	colStartAddr : bpy.props.StringProperty(name ='Start Address', 
		default = '11D8930')
	colEndAddr : bpy.props.StringProperty(name ='Start Address', 
		default = '11FFF00')
	exportRom : bpy.props.StringProperty(name ='Export ROM', 
		subtype = 'FILE_PATH')
	outputRom : bpy.props.StringProperty(name ='Output ROM', 
		subtype = 'FILE_PATH')
	colExportPath : bpy.props.StringProperty(
		name = 'Path', subtype = 'FILE_PATH')
	colExportType : bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	colExportLevel : bpy.props.EnumProperty(items = level_enums, 
		name = 'Level Used By Collision', default = 'CG')
	addr_0x2A : bpy.props.StringProperty(name = '0x2A Behaviour Command Address',
		default = '0')
	set_addr_0x2A : bpy.props.BoolProperty(
		name = 'Overwrite 0x2A Behaviour Command')

	def execute(self, context):
		tempROM = tempName(self.outputRom)
		obj = None
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		if len(context.selected_objects) == 0:
			raise ValueError("Object not selected.")
		obj = context.active_object
		if type(obj.data) is not bpy.types.Mesh:
			raise ValueError("Mesh not selected.")
		
		T, R, S = obj.matrix_world.decompose()
		objTransform = R.to_matrix().to_4x4() @ \
			mathutils.Matrix.Diagonal(S).to_4x4()
		finalTransform = (blenderToSM64Rotation * \
			(1/sm64ToBlenderScale)).to_4x4() @ objTransform

		try:
			if self.colExportType == 'C':
				exportCollisionC(obj, finalTransform,
					bpy.path.abspath(self.colExportPath), False)
				self.report({'INFO'}, 'Success! Collision at ' + \
					self.colExportPath)
			else:
				checkExpanded(bpy.path.abspath(self.exportRom))
				romfileExport = open(bpy.path.abspath(self.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(self.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[self.colExportLevel])
				segmentData = levelParsed.segmentData

				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				addrRange = \
					exportCollisionBinary(obj, finalTransform, romfileOutput, 
						int(self.colStartAddr, 16), int(self.colEndAddr, 16),
						False)

				segAddress = encodeSegmentedAddr(addrRange[0], segmentData)
				if self.set_addr_0x2A:
					romfileOutput.seek(int(self.addr_0x2A, 16) + 4)
					romfileOutput.write(segAddress)
				segPointer = bytesToHex(segAddress)

				romfileOutput.close()
				bpy.ops.object.select_all(action = 'DESELECT')
				obj.select_set(True)
				context.view_layer.objects.active = obj

				os.remove(bpy.path.abspath(self.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(self.outputRom))

				self.report({'INFO'}, 'Success! Collision at (' + \
					hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
					') (Seg. ' + segPointer + ').')

			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			bpy.ops.object.select_all(action = "DESELECT")
			obj.select_set(True)
			context.view_layer.objects.active = obj

			romfileOutput.close()
			os.remove(bpy.path.abspath(tempROM))
			obj.select_set(True)
			context.view_layer.objects.active = obj
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ExportCollisionPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_collision"
	bl_label = "SM64 Collision Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsColE = col.operator(SM64_ExportCollision.bl_idname)

		propsColE.colExportType = context.scene.colExportType
		propsColE.colStartAddr = context.scene.colStartAddr
		propsColE.colEndAddr = context.scene.colEndAddr
		propsColE.colExportPath = context.scene.colExportPath
		propsColE.colExportLevel = context.scene.colExportLevel
		propsColE.exportRom = context.scene.exportRom
		propsColE.outputRom = context.scene.outputRom
		propsColE.addr_0x2A = context.scene.addr_0x2A
		propsColE.set_addr_0x2A = context.scene.set_addr_0x2A

		col.prop(context.scene, 'colExportType')
		if propsColE.colExportType == 'C':
			col.prop(context.scene, 'colExportPath')
		else:
			prop_split(col, context.scene, 'colStartAddr', 'Start Address')
			prop_split(col, context.scene, 'colEndAddr', 'End Address')
			prop_split(col, context.scene, 'colExportLevel', 
				'Level Used By Collision')
			col.prop(context.scene, 'set_addr_0x2A')
			if propsColE.set_addr_0x2A:
				prop_split(col, context.scene, 'addr_0x2A', 
					'0x2A Behaviour Command Address')
		for i in range(panelSeparatorSize):
			col.separator()

class F3D_GlobalSettingsPanel(bpy.types.Panel):
	bl_idname = "F3D_PT_global_settings"
	bl_label = "F3D Global Settings"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.prop(context.scene, 'f3d_type')
		col.prop(context.scene, 'isHWv1')
		
class SM64_FileSettingsPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_file_settings"
	bl_label = "SM64 File Settings"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tools'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.prop(context.scene, 'importRom')
		col.prop(context.scene, 'exportRom')
		col.prop(context.scene, 'outputRom')
		col.prop(context.scene, 'extendBank4')


# called on add-on enabling
# register operators and panels here
# append menu layout drawing function to an existing window
def register():
	sm64_collision.register() # register first, so panel goes above mat panel
	f3d_material.register()
	sm64_geolayout_bone.register()
	
	bpy.utils.register_class(ArmatureApplyWithMesh)
	bpy.utils.register_class(AddBoneGroups)
	bpy.utils.register_class(CreateMetarig)
	bpy.utils.register_class(N64_AddF3dMat)

	bpy.utils.register_class(F3D_GlobalSettingsPanel)
	bpy.utils.register_class(SM64_FileSettingsPanel)
	#bpy.utils.register_class(SM64_ImportCharacterPanel)
	#bpy.utils.register_class(SM64_ExportCharacterPanel)
	bpy.utils.register_class(SM64_ImportGeolayoutPanel)
	bpy.utils.register_class(SM64_ExportGeolayoutPanel)
	bpy.utils.register_class(SM64_ArmatureToolsPanel)
	bpy.utils.register_class(SM64_ImportAnimPanel)
	bpy.utils.register_class(SM64_ExportAnimPanel)
	bpy.utils.register_class(SM64_ImportDLPanel)
	bpy.utils.register_class(SM64_ExportDLPanel)
	#bpy.utils.register_class(SM64_ImportLevelPanel)
	#bpy.utils.register_class(SM64_ExportLevelPanel)
	bpy.utils.register_class(SM64_ExportCollisionPanel)
	
	#bpy.utils.register_class(SM64_ImportMario)
	#bpy.utils.register_class(SM64_ExportMario)
	bpy.utils.register_class(SM64_ImportGeolayout)
	bpy.utils.register_class(SM64_ExportGeolayout)
	bpy.utils.register_class(SM64_ImportDL)
	bpy.utils.register_class(SM64_ExportDL)
	bpy.utils.register_class(SM64_ImportAnimMario)
	bpy.utils.register_class(SM64_ExportAnimMario)
	#bpy.utils.register_class(SM64_ImportLevel)
	#bpy.utils.register_class(SM64_ExportLevel)
	bpy.utils.register_class(SM64_ExportCollision)

	# Character
	bpy.types.Scene.rotationAxis = bpy.props.FloatVectorProperty(
		size = 3, default = (1,0,0))
	bpy.types.Scene.rotationAngle = bpy.props.FloatProperty(default = 90)
	bpy.types.Scene.rotationOrder = bpy.props.StringProperty(default = 'XYZ')

	bpy.types.Scene.sm64_character = bpy.props.EnumProperty(
		items = character_enums, name = 'SM64 Character', default = 'Mario')
	bpy.types.Scene.useFaceAnimation = bpy.props.BoolProperty(
		name ='Use Face Animation?')
	bpy.types.Scene.overwriteWingPositions = bpy.props.BoolProperty(
		name ='Overwrite Wing Positions? (See attatched diagram)')
	bpy.types.Scene.exportRange = bpy.props.IntVectorProperty(name="Export range",
		default=marioFullRomInterval, size = 2, min = 0)
	bpy.types.Scene.segment4 = bpy.props.IntVectorProperty(name="Segment 4", 
		default=defaultExtendSegment4, size = 2, min = 0)
	bpy.types.Scene.useCustomSegment4 = bpy.props.BoolProperty(
		name = "Use custom segment 4?", default = True)
	bpy.types.Scene.useLogFile = bpy.props.BoolProperty(name ='Write log file?')
	bpy.types.Scene.logFilePath = bpy.props.StringProperty(
		name = 'Log File', subtype = 'FILE_PATH')

	# Display List
	bpy.types.Scene.DLImportStart = bpy.props.StringProperty(
		name ='Start Address', default = 'A3BE1C')
	bpy.types.Scene.DLExportStart = bpy.props.StringProperty(
		name = 'Start', default = '11D8930')
	bpy.types.Scene.DLExportEnd = bpy.props.StringProperty(
		name = 'End', default = '11FFF00')
	bpy.types.Scene.levelDLImport = bpy.props.EnumProperty(items = level_enums, 
		name = 'Level', default = 'CG')
	bpy.types.Scene.levelDLExport = bpy.props.EnumProperty(items = level_enums, 
		name = 'Level', default = 'WF')
	bpy.types.Scene.DLExportGeoPtr = bpy.props.StringProperty(
		name ='Geolayout Pointer', default = '132AA8')
	bpy.types.Scene.overwriteGeoPtr = bpy.props.BoolProperty(
		name = "Overwrite geolayout pointer", default = False)
	bpy.types.Scene.isSegmentedAddrDLImport = bpy.props.BoolProperty(
		name = 'Is Segmented Address', default = False)
	bpy.types.Scene.DLExportType = bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	bpy.types.Scene.DLExportPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.DLExportisStatic = bpy.props.BoolProperty(
		name = 'Static DL', default = True)
	bpy.types.Scene.DLDefinePath = bpy.props.StringProperty(
		name = 'Definitions Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.DLUseBank0 = bpy.props.BoolProperty(name = 'Use Bank 0')
	bpy.types.Scene.DLRAMAddr = bpy.props.StringProperty(name = 'RAM Address', 
		default = '80000000')
	
	# Geolayouts
	bpy.types.Scene.levelGeoImport = bpy.props.EnumProperty(items = level_enums,
		name = 'Level', default = 'HMC')
	bpy.types.Scene.levelGeoExport = bpy.props.EnumProperty(items = level_enums,
		name = 'Level', default = 'HMC')
	bpy.types.Scene.geoExportStart = bpy.props.StringProperty(
		name = 'Start', default = '11D8930')
	bpy.types.Scene.geoExportEnd = bpy.props.StringProperty(
		name = 'End', default = '11FFF00')
	bpy.types.Scene.generateArmature = bpy.props.BoolProperty(
		name ='Generate Armature?', default = True)
	bpy.types.Scene.geoImportAddr = bpy.props.StringProperty(
		name ='Start Address', default = '1F1D60')
	bpy.types.Scene.overwriteModelLoad = bpy.props.BoolProperty(
		name = 'Modify level script', default = True)
	bpy.types.Scene.modelLoadLevelScriptCmd = bpy.props.StringProperty(
		name = 'Level script model load command', default = '2ABCE0')
	bpy.types.Scene.modelID = bpy.props.IntProperty(name = 'Model ID', 
		default = 1, min = 0)
	bpy.types.Scene.ignoreSwitch = bpy.props.BoolProperty(
		name = 'Ignore Switch Nodes', default = True)
	bpy.types.Scene.textDumpGeo = bpy.props.BoolProperty(
		name = 'Dump geolayout as text', default = False)
	bpy.types.Scene.textDumpGeoPath =  bpy.props.StringProperty(
		name ='Text Dump Path', subtype = 'FILE_PATH')
	bpy.types.Scene.geoExportType = bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	bpy.types.Scene.geoExportPath = bpy.props.StringProperty(
		name = 'Geo Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.geoExportPathDL = bpy.props.StringProperty(
		name = 'DL Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.geoDefinePath = bpy.props.StringProperty(
		name = 'Definitions Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.geoUseBank0 = bpy.props.BoolProperty(name = 'Use Bank 0')
	bpy.types.Scene.geoRAMAddr = bpy.props.StringProperty(name = 'RAM Address', 
		default = '80000000')

	# Level
	bpy.types.Scene.levelLevel = bpy.props.EnumProperty(items = level_enums, 
		name = 'Level', default = 'CG')

	# Animation
	bpy.types.Scene.animStartImport = bpy.props.StringProperty(
		name ='Import Start', default = '4EC690')
	bpy.types.Scene.animExportStart = bpy.props.StringProperty(
		name ='Start', default = '11D8930')
	bpy.types.Scene.animExportEnd = bpy.props.StringProperty(
		name ='End', default = '11FFF00')
	bpy.types.Scene.isDMAImport = bpy.props.BoolProperty(name = 'Is DMA Animation', default = True)
	bpy.types.Scene.isDMAExport = bpy.props.BoolProperty(name = 'Is DMA Animation')
	bpy.types.Scene.DMAEntryAddress = bpy.props.StringProperty(name = 'DMA Entry Address', default = '4EC008')
	bpy.types.Scene.DMAStartAddress = bpy.props.StringProperty(name = 'DMA Start Address', default = '4EC000')
	bpy.types.Scene.levelAnimImport = bpy.props.EnumProperty(items = level_enums, name = 'Level', default = 'IC')
	bpy.types.Scene.levelAnimExport = bpy.props.EnumProperty(items = level_enums, name = 'Level', default = 'IC')
	bpy.types.Scene.loopAnimation = bpy.props.BoolProperty(name = 'Loop Animation', default = True)
	bpy.types.Scene.overwrite_0x27 = bpy.props.BoolProperty(name = 'Overwrite 0x27 behaviour command', default = True)
	bpy.types.Scene.overwrite_0x28 = bpy.props.BoolProperty(name = 'Overwrite 0x28 behaviour command', default = True)
	bpy.types.Scene.addr_0x27 = bpy.props.StringProperty(
		name = '0x27 Command Address', default = '21CD00')
	bpy.types.Scene.addr_0x28 = bpy.props.StringProperty(
		name = '0x28 Command Address', default = '21CD08')
	bpy.types.Scene.animExportType = bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	bpy.types.Scene.animExportPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.animOverwriteDMAEntry = bpy.props.BoolProperty(
		name = 'Overwrite DMA Entry')

	# Collision
	bpy.types.Scene.colExportPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.colExportType = bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	bpy.types.Scene.colExportLevel = bpy.props.EnumProperty(items = level_enums, 
		name = 'Level Used By Collision', default = 'WF')
	bpy.types.Scene.addr_0x2A = bpy.props.StringProperty(
		name = '0x2A Behaviour Command Address', default = '21A9CC')
	bpy.types.Scene.set_addr_0x2A = bpy.props.BoolProperty(
		name = 'Overwrite 0x2A Behaviour Command')
	bpy.types.Scene.colStartAddr = bpy.props.StringProperty(name ='Start Address',
		default = '11D8930')
	bpy.types.Scene.colEndAddr = bpy.props.StringProperty(name ='Start Address', 
		default = '11FFF00')

	# ROM
	bpy.types.Scene.importRom = bpy.props.StringProperty(
		name ='Import ROM', subtype = 'FILE_PATH')
	bpy.types.Scene.exportRom = bpy.props.StringProperty(
		name ='Export ROM', subtype = 'FILE_PATH')
	bpy.types.Scene.outputRom = bpy.props.StringProperty(
		name ='Output ROM', subtype = 'FILE_PATH')
	bpy.types.Scene.extendBank4 = bpy.props.BoolProperty(
		name = 'Extend Bank 4 on Export?', default = True, 
		description = 'Sets bank 4 range to (' +\
			hex(defaultExtendSegment4[0]) + ', ' + \
			hex(defaultExtendSegment4[1]) + ') and copies data from old bank')

	bpy.types.Scene.characterIgnoreSwitch = \
		bpy.props.BoolProperty(name = 'Ignore Switch Nodes', default = True)

	
# called on add-on disabling
def unregister():
	del bpy.types.Scene.rotationAxis
	del bpy.types.Scene.rotationAngle
	del bpy.types.Scene.rotationOrder

	# Geolayout
	del bpy.types.Scene.geoExportStart
	del bpy.types.Scene.geoExportEnd
	del bpy.types.Scene.overwriteModelLoad
	del bpy.types.Scene.modelLoadLevelScriptCmd
	del bpy.types.Scene.modelID
	del bpy.types.Scene.textDumpGeo
	del bpy.types.Scene.textDumpGeoPath
	del bpy.types.Scene.geoExportType
	del bpy.types.Scene.geoExportPath
	del bpy.types.Scene.geoExportPathDL
	del bpy.types.Scene.geoDefinePath
	del bpy.types.Scene.geoUseBank0
	del bpy.types.Scene.geoRAMAddr

	# Animation
	del bpy.types.Scene.animStartImport
	del bpy.types.Scene.animExportStart
	del bpy.types.Scene.animExportEnd
	del bpy.types.Scene.levelAnimImport
	del bpy.types.Scene.levelAnimExport
	del bpy.types.Scene.isDMAImport
	del bpy.types.Scene.isDMAExport
	del bpy.types.Scene.DMAStartAddress
	del bpy.types.Scene.DMAEntryAddress
	del bpy.types.Scene.loopAnimation
	del bpy.types.Scene.overwrite_0x27
	del bpy.types.Scene.overwrite_0x28
	del bpy.types.Scene.addr_0x27
	del bpy.types.Scene.addr_0x28
	del bpy.types.Scene.animExportType
	del bpy.types.Scene.animExportPath
	del bpy.types.Scene.animOverwriteDMAEntry

	# Character
	del bpy.types.Scene.characterIgnoreSwitch
	del bpy.types.Scene.sm64_character
	del bpy.types.Scene.useFaceAnimation
	del bpy.types.Scene.overwriteWingPositions
	del bpy.types.Scene.generateArmature
	del bpy.types.Scene.geoImportAddr
	del bpy.types.Scene.levelGeoImport
	del bpy.types.Scene.levelGeoExport
	del bpy.types.Scene.ignoreSwitch

	# Display List
	del bpy.types.Scene.levelDLImport
	del bpy.types.Scene.levelDLExport
	del bpy.types.Scene.DLImportStart
	del bpy.types.Scene.DLExportStart
	del bpy.types.Scene.DLExportEnd
	del bpy.types.Scene.DLExportGeoPtr
	del bpy.types.Scene.overwriteGeoPtr
	del bpy.types.Scene.isSegmentedAddrDLImport
	del bpy.types.Scene.DLExportType
	del bpy.types.Scene.DLExportPath
	del bpy.types.Scene.DLExportisStatic
	del bpy.types.Scene.DLDefinePath
	del bpy.types.Scene.DLUseBank0
	del bpy.types.Scene.DLRAMAddr

	# Level
	del bpy.types.Scene.levelLevel
	del bpy.types.Scene.exportRange
	del bpy.types.Scene.segment4
	del bpy.types.Scene.useCustomSegment4
	del bpy.types.Scene.useLogFile
	del bpy.types.Scene.logFilePath

	# Collision
	del bpy.types.Scene.colExportPath
	del bpy.types.Scene.colExportType
	del bpy.types.Scene.colExportLevel
	del bpy.types.Scene.addr_0x2A
	del bpy.types.Scene.set_addr_0x2A
	del bpy.types.Scene.colStartAddr
	del bpy.types.Scene.colEndAddr

	# ROM
	del bpy.types.Scene.importRom
	del bpy.types.Scene.exportRom
	del bpy.types.Scene.outputRom
	del bpy.types.Scene.extendBank4

	f3d_material.unregister()
	sm64_geolayout_bone.unregister()
	sm64_collision.unregister()
	bpy.utils.unregister_class(ArmatureApplyWithMesh)
	bpy.utils.unregister_class(AddBoneGroups)
	bpy.utils.unregister_class(CreateMetarig)
	bpy.utils.unregister_class(N64_AddF3dMat)
	
	bpy.utils.unregister_class(F3D_GlobalSettingsPanel)
	bpy.utils.unregister_class(SM64_FileSettingsPanel)
	#bpy.utils.unregister_class(SM64_ImportCharacterPanel)
	#bpy.utils.unregister_class(SM64_ExportCharacterPanel)
	bpy.utils.unregister_class(SM64_ImportGeolayoutPanel)
	bpy.utils.unregister_class(SM64_ExportGeolayoutPanel)
	bpy.utils.unregister_class(SM64_ArmatureToolsPanel)
	bpy.utils.unregister_class(SM64_ImportAnimPanel)
	bpy.utils.unregister_class(SM64_ExportAnimPanel)
	bpy.utils.unregister_class(SM64_ImportDLPanel)
	bpy.utils.unregister_class(SM64_ExportDLPanel)
	#bpy.utils.unregister_class(SM64_ImportLevelPanel)
	#bpy.utils.unregister_class(SM64_ExportLevelPanel)
	bpy.utils.unregister_class(SM64_ExportCollisionPanel)
	bpy.utils.unregister_class(SM64_ExportCollision)

	#bpy.utils.unregister_class(SM64_ImportMario)
	#bpy.utils.unregister_class(SM64_ExportMario)
	bpy.utils.unregister_class(SM64_ImportGeolayout)
	bpy.utils.unregister_class(SM64_ExportGeolayout)
	bpy.utils.unregister_class(SM64_ImportDL)
	bpy.utils.unregister_class(SM64_ExportDL)
	bpy.utils.unregister_class(SM64_ImportAnimMario)
	bpy.utils.unregister_class(SM64_ExportAnimMario)
	#bpy.utils.unregister_class(SM64_ImportLevel)
	#bpy.utils.unregister_class(SM64_ExportLevel)