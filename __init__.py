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
	('Binary', 'Binary', 'Binary'),
	('Insertable Binary', 'Insertable Binary', 'Insertable Binary')
]

enumRefreshVer = [
	("Refresh 3", "Refresh 3", "Refresh 3"),
	("Refresh 4", "Refresh 4", "Refresh 4"),
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

class SM64_AddrConv(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.addr_conv'
	bl_label = "Convert Address"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	segToVirt : bpy.props.BoolProperty()

	def execute(self, context):
		address = int(context.scene.convertibleAddr, 16)
		try:
			importRom = context.scene.importRom
			romfileSrc = open(bpy.path.abspath(importRom), 'rb')
			checkExpanded(bpy.path.abspath(importRom))
			levelParsed = parseLevelAtPointer(romfileSrc, 
				level_pointers[context.scene.levelConvert])
			segmentData = levelParsed.segmentData
			if self.segToVirt:
				ptr = decodeSegmentedAddr(
					address.to_bytes(4, 'big'), segmentData)
				self.report({'INFO'}, 
					'Virtual pointer is 0x' + format(ptr, '08X'))
			else:
				ptr = int.from_bytes(
					encodeSegmentedAddr(address, segmentData), 'big')
				self.report({'INFO'}, 
					'Segmented pointer is 0x' + format(ptr, '08X'))
			romfileSrc.close()
			return {'FINISHED'}
		except:
			romfileSrc.close()
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

# See SM64GeoLayoutPtrsByLevels.txt by VLTone
class SM64_ImportGeolayout(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_import_geolayout'
	bl_label = "Import Geolayout"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		geoImportAddr = context.scene.geoImportAddr
		generateArmature = context.scene.generateArmature
		levelGeoImport = context.scene.levelGeoImport
		importRom = context.scene.importRom
		ignoreSwitch = context.scene.ignoreSwitch

		#finalTransform = mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
		finalTransform = mathutils.Matrix.Identity(4)
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		try:
			romfileSrc = open(bpy.path.abspath(importRom), 'rb')
			checkExpanded(bpy.path.abspath(importRom))

			armatureObj = None

			# Get segment data
			levelParsed = parseLevelAtPointer(romfileSrc, 
				level_pointers[levelGeoImport])
			segmentData = levelParsed.segmentData
			geoStart = int(geoImportAddr, 16)
			if context.scene.geoIsSegPtr:
				geoStart = decodeSegmentedAddr(
					geoStart.to_bytes(4, 'big'), segmentData)

			# Armature mesh groups includes armatureObj.
			armatureMeshGroups, armatureObj = parseGeoLayout(romfileSrc, 
				geoStart,
			 	context.scene, segmentData, 
				finalTransform, generateArmature, 
				ignoreSwitch, True, context.scene.f3d_type, 
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
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsGeoI = col.operator(SM64_ImportGeolayout.bl_idname)

		#col.prop(context.scene, 'rotationOrder')
		#col.prop(context.scene, 'rotationAxis')
		#col.prop(context.scene, 'rotationAngle')
		prop_split(col, context.scene, 'geoImportAddr', 'Start Address')
		col.prop(context.scene, 'geoIsSegPtr')
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

class SM64_ExportGeolayoutObject(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_geolayout_object'
	bl_label = "Export Geolayout Object"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		obj = None
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		if len(context.selected_objects) == 0:
			raise ValueError("Object not selected.")
		obj = context.active_object
		if type(obj.data) is not bpy.types.Mesh:
			raise ValueError("Mesh not selected.")
		if context.scene.saveCameraSettings and \
			context.scene.levelCamera is None:
			raise ValueError("Cannot save camera settings with no camera provided.")
		levelCamera = context.scene.levelCamera if \
			context.scene.saveCameraSettings else None

		finalTransform = mathutils.Matrix.Identity(4)
		scaleValue = bpy.context.scene.blenderToSM64Scale
		finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((
			scaleValue, scaleValue, scaleValue))).to_4x4()

		try:
			# Rotate all armatures 90 degrees
			applyRotation([obj], math.radians(90), 'X')

			if context.scene.geoExportType == 'C':
				exportGeolayoutObjectC(obj, finalTransform,
					context.scene.f3d_type, context.scene.isHWv1,
					bpy.path.abspath(context.scene.geoExportPath),
					bpy.context.scene.geoTexDir,
					bpy.context.scene.geoSaveTextures,
					bpy.context.scene.geoSeparateTextureDef,
					levelCamera)
				self.report({'INFO'}, 'Success! Geolayout at ' + \
					context.scene.geoExportPath)
			elif context.scene.geoExportType == 'Insertable Binary':
				exportGeolayoutObjectInsertableBinary(obj,
					finalTransform, context.scene.f3d_type,
					context.scene.isHWv1, 
					bpy.path.abspath(bpy.context.scene.geoInsertableBinaryPath),
					levelCamera)
				self.report({'INFO'}, 'Success! Data at ' + \
					context.scene.geoInsertableBinaryPath)
			else:
				tempROM = tempName(context.scene.outputRom)
				checkExpanded(bpy.path.abspath(context.scene.exportRom))
				romfileExport = open(
					bpy.path.abspath(context.scene.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(context.scene.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[context.scene.levelGeoExport])
				segmentData = levelParsed.segmentData

				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				exportRange = [int(context.scene.geoExportStart, 16), 
					int(context.scene.geoExportEnd, 16)]
				textDumpFilePath = \
					bpy.path.abspath(context.scene.textDumpGeoPath) \
					if context.scene.textDumpGeo else None
				if context.scene.overwriteModelLoad:
					modelLoadInfo = \
						(int(context.scene.modelLoadLevelScriptCmd, 16),
						int(context.scene.modelID,16))
				else:
					modelLoadInfo = (None, None)

				if context.scene.geoUseBank0:
					addrRange, startRAM, geoStart = \
						exportGeolayoutObjectBinaryBank0(
						romfileOutput, obj, exportRange, 
 						finalTransform, *modelLoadInfo, textDumpFilePath,
						context.scene.f3d_type, context.scene.isHWv1, 
						getAddressFromRAMAddress(int(
						context.scene.geoRAMAddr, 16)),
						levelCamera)
				else:
					addrRange, segPointer = exportGeolayoutObjectBinary(
						romfileOutput, obj,
						exportRange, finalTransform, segmentData,
						*modelLoadInfo, textDumpFilePath, 
						context.scene.f3d_type, context.scene.isHWv1,
						levelCamera)

				romfileOutput.close()
				bpy.ops.object.select_all(action = 'DESELECT')
				obj.select_set(True)
				context.view_layer.objects.active = obj

				if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
					os.remove(bpy.path.abspath(context.scene.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(context.scene.outputRom))

				if context.scene.geoUseBank0:
					self.report({'INFO'}, 'Success! Geolayout at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						'), to write to RAM Address ' + hex(startRAM) + \
						', with geolayout starting at ' + hex(geoStart))
				else:
					self.report({'INFO'}, 'Success! Geolayout at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						') (Seg. ' + segPointer + ').')
			
			applyRotation([obj], math.radians(-90), 'X')
			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			applyRotation([obj], math.radians(-90), 'X')

			if context.scene.geoExportType == 'Binary':
				romfileOutput.close()
				if os.path.exists(bpy.path.abspath(tempROM)):
					os.remove(bpy.path.abspath(tempROM))
			self.report({'ERROR'}, traceback.format_exc())
			return {'CANCELLED'} # must return a set

class SM64_ExportGeolayoutArmature(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_geolayout_armature'
	bl_label = "Export Geolayout Armature"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		armatureObj = None
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		if len(context.selected_objects) == 0:
			raise ValueError("Armature not selected.")
		armatureObj = context.active_object
		if type(armatureObj.data) is not bpy.types.Armature:
			raise ValueError("Armature not selected.")

		if len(armatureObj.children) == 0 or \
			not isinstance(armatureObj.children[0].data, bpy.types.Mesh):
			raise ValueError("Armature does not have any mesh children, or " +\
				'has a non-mesh child.')
		if context.scene.saveCameraSettings and \
			context.scene.levelCamera is None:
			raise ValueError("Cannot save camera settings with no camera provided.")
		levelCamera = context.scene.levelCamera if \
			context.scene.saveCameraSettings else None

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

		try:
			# Rotate all armatures 90 degrees
			applyRotation([armatureObj] + linkedArmatures, 
				math.radians(90), 'X')

			# You must ALSO apply object rotation after armature rotation.
			bpy.ops.object.select_all(action = "DESELECT")
			for linkedArmature, linkedMesh in linkedArmatureDict.items():
				linkedMesh.select_set(True)
			obj.select_set(True)
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.transform_apply(location = False, rotation = True,
				scale = True, properties =  False)
			if context.scene.geoExportType == 'C':
				exportGeolayoutArmatureC(armatureObj, obj, finalTransform,
					context.scene.f3d_type, context.scene.isHWv1,
					bpy.path.abspath(context.scene.geoExportPath),
					bpy.context.scene.geoTexDir,
					bpy.context.scene.geoSaveTextures,
					bpy.context.scene.geoSeparateTextureDef,
					levelCamera)
				self.report({'INFO'}, 'Success! Geolayout at ' + \
					context.scene.geoExportPath)
			elif context.scene.geoExportType == 'Insertable Binary':
				exportGeolayoutArmatureInsertableBinary(armatureObj, obj,
					finalTransform, context.scene.f3d_type,
					context.scene.isHWv1, 
					bpy.path.abspath(bpy.context.scene.geoInsertableBinaryPath),
					levelCamera)
				self.report({'INFO'}, 'Success! Data at ' + \
					context.scene.geoInsertableBinaryPath)
			else:
				tempROM = tempName(context.scene.outputRom)
				checkExpanded(bpy.path.abspath(context.scene.exportRom))
				romfileExport = open(
					bpy.path.abspath(context.scene.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(context.scene.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[context.scene.levelGeoExport])
				segmentData = levelParsed.segmentData

				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				exportRange = [int(context.scene.geoExportStart, 16), 
					int(context.scene.geoExportEnd, 16)]
				textDumpFilePath = \
					bpy.path.abspath(context.scene.textDumpGeoPath) \
					if context.scene.textDumpGeo else None
				if context.scene.overwriteModelLoad:
					modelLoadInfo = \
						(int(context.scene.modelLoadLevelScriptCmd, 16),
						int(context.scene.modelID, 16))
				else:
					modelLoadInfo = (None, None)

				if context.scene.geoUseBank0:
					addrRange, startRAM, geoStart = \
						exportGeolayoutArmatureBinaryBank0(
						romfileOutput, armatureObj, obj, exportRange, 
 						finalTransform, *modelLoadInfo, textDumpFilePath,
						context.scene.f3d_type, context.scene.isHWv1, 
						getAddressFromRAMAddress(int(
						context.scene.geoRAMAddr, 16)), levelCamera)
				else:
					addrRange, segPointer = exportGeolayoutArmatureBinary(
						romfileOutput, armatureObj, obj,
						exportRange, finalTransform, segmentData,
						*modelLoadInfo, textDumpFilePath, 
						context.scene.f3d_type, context.scene.isHWv1,
						levelCamera)

				romfileOutput.close()
				bpy.ops.object.select_all(action = 'DESELECT')
				armatureObj.select_set(True)
				context.view_layer.objects.active = armatureObj

				if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
					os.remove(bpy.path.abspath(context.scene.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(context.scene.outputRom))

				if context.scene.geoUseBank0:
					self.report({'INFO'}, 'Success! Geolayout at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						'), to write to RAM Address ' + hex(startRAM) + \
						', with geolayout starting at ' + hex(geoStart))
				else:
					self.report({'INFO'}, 'Success! Geolayout at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
						') (Seg. ' + segPointer + ').')

			applyRotation([armatureObj] + linkedArmatures, 
				math.radians(-90), 'X')

			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			applyRotation([armatureObj] + linkedArmatures, 
				math.radians(-90), 'X')

			if context.scene.geoExportType == 'Binary':
				romfileOutput.close()
				if os.path.exists(bpy.path.abspath(tempROM)):
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
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsGeoE = col.operator(SM64_ExportGeolayoutArmature.bl_idname)
		propsGeoE = col.operator(SM64_ExportGeolayoutObject.bl_idname)

		col.prop(context.scene, 'geoExportType')
		if context.scene.geoExportType == 'C':
			col.prop(context.scene, 'geoExportPath')
			col.prop(context.scene, 'geoSaveTextures')
			if context.scene.geoSaveTextures:
				col.prop(context.scene, 'geoTexDir')	
				col.prop(context.scene, 'geoSeparateTextureDef')
		elif context.scene.geoExportType == 'Insertable Binary':
			col.prop(context.scene, 'geoInsertableBinaryPath')
		else:
			prop_split(col, context.scene, 'geoExportStart', 'Start Address')
			prop_split(col, context.scene, 'geoExportEnd', 'End Address')

			col.prop(context.scene, 'geoUseBank0')
			if context.scene.geoUseBank0:
				prop_split(col, context.scene, 'geoRAMAddr', 'RAM Address')
			else:
				col.prop(context.scene, 'levelGeoExport')

			col.prop(context.scene, 'overwriteModelLoad')
			if context.scene.overwriteModelLoad:
				prop_split(col, context.scene, 'modelLoadLevelScriptCmd', 'Model Load Command')
				prop_split(col, context.scene, 'modelID', 'Model ID')
			col.prop(context.scene, 'textDumpGeo')
			if context.scene.textDumpGeo:
				col.prop(context.scene, 'textDumpGeoPath')
		
		col.prop(context.scene, 'saveCameraSettings')
		if context.scene.saveCameraSettings:
			prop_split(col, context.scene, 'levelCamera', 'Level Camera')
		
		for i in range(panelSeparatorSize):
			col.separator()
		
class SM64_ArmatureToolsPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_armature_tools"
	bl_label = "SM64 Armature Tools"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

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

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.mode != 'OBJECT':
			raise ValueError("Operator can only be used in object mode.")
		try:
			checkExpanded(bpy.path.abspath(context.scene.importRom))
			romfileSrc = open(bpy.path.abspath(context.scene.importRom), 'rb')
			levelParsed = parseLevelAtPointer(romfileSrc, 
				level_pointers[context.scene.levelDLImport])
			segmentData = levelParsed.segmentData
			start = decodeSegmentedAddr(
				int(context.scene.DLImportStart, 16).to_bytes(4, 'big'),
				segmentData) if context.scene.isSegmentedAddrDLImport else \
				int(context.scene.DLImportStart, 16)
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
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsDLI = col.operator(SM64_ImportDL.bl_idname)

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

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		
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
			(bpy.context.scene.blenderToSM64Scale)).to_4x4() @ objTransform

		#cProfile.runctx('exportF3DtoC(bpy.path.abspath(context.scene.DLExportPath), obj,' +\
		#	'context.scene.DLExportisStatic, finalTransform,' +\
		#	'context.scene.f3d_type, context.scene.isHWv1,' +\
		#	'bpy.context.scene.DLTexDir,' +\
		#	'bpy.context.scene.DLSaveTextures,' +\
		#	'bpy.context.scene.DLSeparateTextureDef)',
		#	globals(), locals(), "E:/Non-Steam Games/emulators/Project 64 1.6/SM64 Romhack Tools/_Data/blender.prof")
		#p = pstats.Stats("E:/Non-Steam Games/emulators/Project 64 1.6/SM64 Romhack Tools/_Data/blender.prof")
		#p.sort_stats("cumulative").print_stats(2000)
		
		try:
			if context.scene.DLExportType == 'C':
				exportF3DtoC(bpy.path.abspath(context.scene.DLExportPath), obj,
					context.scene.DLExportisStatic, finalTransform,
					context.scene.f3d_type, context.scene.isHWv1,
					bpy.context.scene.DLTexDir,
					bpy.context.scene.DLSaveTextures,
					bpy.context.scene.DLSeparateTextureDef,
					bpy.context.scene.DLincludeChildren)
				self.report({'INFO'}, 'Success! DL at ' + \
					context.scene.DLExportPath + '.')
				return {'FINISHED'} # must return a set
			elif context.scene.DLExportType == 'Insertable Binary':
				exportF3DtoInsertableBinary(
					bpy.path.abspath(context.scene.DLInsertableBinaryPath),
					finalTransform, obj, context.scene.f3d_type,
					context.scene.isHWv1, bpy.context.scene.DLincludeChildren)
				self.report({'INFO'}, 'Success! DL at ' + \
					context.scene.DLInsertableBinaryPath + '.')
				return {'FINISHED'} # must return a set
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
				return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			if context.scene.DLExportType == 'Binary':
				romfileOutput.close()
				if os.path.exists(bpy.path.abspath(tempROM)):
					os.remove(bpy.path.abspath(tempROM))
			self.report({'ERROR'}, traceback.format_exc())
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
			col.prop(context.scene, 'DLExportPath')
			col.prop(context.scene, 'DLExportisStatic')
			col.prop(context.scene, 'DLSaveTextures')
			if context.scene.DLSaveTextures:
				col.prop(context.scene, 'DLTexDir')	
				col.prop(context.scene, 'DLSeparateTextureDef')
			#col.prop(context.scene, 'DLDefinePath')
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

class SM64_ExportMario(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export'
	bl_label = "Export Character"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		self.report({'ERROR'}, 'Not Implemented.')
		return {'CANCELLED'} # must return a set

class SM64_ExportCharacterPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_character"
	bl_label = "SM64 Character Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsE = col.operator(SM64_ExportMario.bl_idname)
	
		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ImportMario(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_import'
	bl_label = "Import Character"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		characterImportData = sm64_character_data[context.scene.sm64_character]
			
		self.report({'ERROR'}, 'Not Implemented.')
		return {'CANCELLED'} # must return a set

class SM64_ImportCharacterPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_import_character"
	bl_label = "SM64 Character Importer"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.prop(context.scene, 'sm64_character')
		col.prop(context.scene, 'characterIgnoreSwitch')
		propsI = col.operator(SM64_ImportMario.bl_idname)

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ImportLevel(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_import_lvl'
	bl_label = "Import Level"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		self.report({'ERROR'}, "Not Implemented.")
		return {'CANCELLED'} # must return a set

class SM64_ImportLevelPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_import_level"
	bl_label = "SM64 Level Importer"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsLI = col.operator(SM64_ImportLevel.bl_idname)
		col.prop(context.scene, 'levelLevel')

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ExportLevel(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.sm64_export_lvl'
	bl_label = "Export Level"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		self.report({'ERROR'}, 'Not Implemented.')
		return {'CANCELLED'} # must return a set

class SM64_ExportLevelPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_level"
	bl_label = "SM64 Level Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()

		for i in range(panelSeparatorSize):
			col.separator()

class SM64_ImportAnimMario(bpy.types.Operator):
	bl_idname = 'object.sm64_import_anim'
	bl_label = "Import Animation"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		checkExpanded(bpy.path.abspath(context.scene.importRom))
		romfileSrc = open(bpy.path.abspath(context.scene.importRom), 'rb')
		try:
			levelParsed = parseLevelAtPointer(romfileSrc, 
				level_pointers[context.scene.levelAnimImport])
			segmentData = levelParsed.segmentData

			animStart = int(context.scene.animStartImport, 16)
			if context.scene.animIsSegPtr:
				animStart = decodeSegmentedAddr(
					animStart.to_bytes(4, 'big'), segmentData)

			if not context.scene.isDMAImport and context.scene.animIsAnimList:
				romfileSrc.seek(animStart + 4 * context.scene.animListIndexImport)
				actualPtr = romfileSrc.read(4)
				animStart = decodeSegmentedAddr(actualPtr, segmentData)

			if len(context.selected_objects) == 0:
				raise ValueError("Armature not selected.")
			armatureObj = context.active_object
			if type(armatureObj.data) is not bpy.types.Armature:
				raise ValueError("Armature not selected.")
			
			importAnimationToBlender(romfileSrc, 
				animStart, armatureObj, 
				segmentData, context.scene.isDMAImport)
			romfileSrc.close()
			self.report({'INFO'}, 'Success!')
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
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsAnimImport = col.operator(SM64_ImportAnimMario.bl_idname)
		col.prop(context.scene, 'isDMAImport')
		if not context.scene.isDMAImport:
			col.prop(context.scene, 'animIsAnimList')
			if context.scene.animIsAnimList:
				prop_split(col, context.scene, 'animListIndexImport', 
					'Anim List Index')

		prop_split(col, context.scene, 'animStartImport', 'Start Address')
		col.prop(context.scene, 'animIsSegPtr')
		col.prop(context.scene, 'levelAnimImport')

		for i in range(panelSeparatorSize):
			col.separator()
		
class SM64_ExportAnimMario(bpy.types.Operator):
	bl_idname = 'object.sm64_export_anim'
	bl_label = "Export Animation"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		
		if len(context.selected_objects) == 0 or not \
			isinstance(context.selected_objects[0].data, bpy.types.Armature):
			raise ValueError("Armature not selected.")
		armatureObj = context.selected_objects[0]

		if context.scene.animExportType == 'C':
			try:
				exportAnimationC(armatureObj, context.scene.loopAnimation, 
					bpy.path.abspath(context.scene.animExportPath))
				self.report({'INFO'}, 'Success! Animation at ' +\
					context.scene.animExportPath)
			except:
				self.report({'ERROR'}, traceback.format_exc())
				return {'CANCELLED'} # must return a set
		elif context.scene.animExportType == 'Insertable Binary':
			exportAnimationInsertableBinary(
				bpy.path.abspath(context.scene.animInsertableBinaryPath),
				armatureObj, context.scene.isDMAExport, 
				context.scene.loopAnimation)
			self.report({'INFO'}, 'Success! Animation at ' +\
				context.scene.animInsertableBinaryPath)
		else:
			try:
				checkExpanded(bpy.path.abspath(context.scene.exportRom))
				tempROM = tempName(context.scene.outputRom)
				romfileExport = \
					open(bpy.path.abspath(context.scene.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(context.scene.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')
			
				# Note actual level doesn't matter for Mario, since he is in all of 	them
				levelParsed = parseLevelAtPointer(romfileOutput, level_pointers		[context.scene.levelAnimExport])
				segmentData = levelParsed.segmentData
				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				DMAAddresses = None
				if context.scene.animOverwriteDMAEntry:
					DMAAddresses = {}
					DMAAddresses['start'] = \
						int(context.scene.DMAStartAddress, 16)
					DMAAddresses['entry'] = \
						int(context.scene.DMAEntryAddress, 16)

				addrRange, nonDMAListPtr = exportAnimationBinary(
					romfileOutput, [int(context.scene.animExportStart, 16), 
					int(context.scene.animExportEnd, 16)],
					bpy.context.active_object,
					DMAAddresses, segmentData, context.scene.isDMAExport,
					context.scene.loopAnimation)

				if not context.scene.isDMAExport:
					segmentedPtr = encodeSegmentedAddr(addrRange[0], segmentData)
					if context.scene.setAnimListIndex:
						romfileOutput.seek(int(context.scene.addr_0x27, 16) + 4)
						segAnimPtr = romfileOutput.read(4)
						virtAnimPtr = decodeSegmentedAddr(segAnimPtr, segmentData)
						romfileOutput.seek(virtAnimPtr + 4 * context.scene.animListIndexExport)
						romfileOutput.write(segmentedPtr)
					if context.scene.overwrite_0x28:
						romfileOutput.seek(int(context.scene.addr_0x28, 16) + 1)
						romfileOutput.write(bytearray([context.scene.animListIndexExport]))
				else:
					segmentedPtr = None
						
				romfileOutput.close()
				if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
					os.remove(bpy.path.abspath(context.scene.outputRom))
				os.rename(bpy.path.abspath(tempROM),
					bpy.path.abspath(context.scene.outputRom))
	
				if not context.scene.isDMAExport:
					self.report({'INFO'}, 'Sucess! Animation table at ' + \
						hex(virtAnimPtr) + ', animation at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + ') ' +\
						'(Seg. ' + bytesToHex(segmentedPtr) + ').')
				else:
					self.report({'INFO'}, 'Success! Animation at (' + \
						hex(addrRange[0]) + ', ' + hex(addrRange[1]) + ').')
			except:
				romfileOutput.close()
				if os.path.exists(bpy.path.abspath(tempROM)):
					os.remove(bpy.path.abspath(tempROM))
				self.report({'ERROR'}, traceback.format_exc())
				return {'CANCELLED'} # must return a set

		return {'FINISHED'} # must return a set

class SM64_ExportAnimPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_export_anim"
	bl_label = "SM64 Animation Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsAnimExport = col.operator(SM64_ExportAnimMario.bl_idname)
		
		col.prop(context.scene, 'animExportType')
		col.prop(context.scene, 'loopAnimation')
		if context.scene.animExportType == 'C':
			col.prop(context.scene, 'animExportPath')
		elif context.scene.animExportType == 'Insertable Binary':
			col.prop(context.scene, 'isDMAExport')
			col.prop(context.scene, 'animInsertableBinaryPath')
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
				col.prop(context.scene, 'setAnimListIndex')
				if context.scene.setAnimListIndex:
					prop_split(col, context.scene, 'addr_0x27', 
						'27 Command Address')
					prop_split(col, context.scene, 'animListIndexExport',
						'Anim List Index')
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

	def execute(self, context):
		
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
			(bpy.context.scene.blenderToSM64Scale)).to_4x4() @ objTransform
		
		try:
			#applyRotation([obj], math.radians(90), 'X')
			if context.scene.colExportType == 'C':
				exportCollisionC(obj, finalTransform,
					bpy.path.abspath(context.scene.colExportPath), False,
					context.scene.colIncludeChildren)
				self.report({'INFO'}, 'Success! Collision at ' + \
					context.scene.colExportPath)
			elif context.scene.colExportType == 'Insertable Binary':
				exportCollisionInsertableBinary(obj, finalTransform, 
					bpy.path.abspath(context.scene.colInsertableBinaryPath), 
					False, context.scene.colIncludeChildren)
				self.report({'INFO'}, 'Success! Collision at ' + \
					context.scene.colInsertableBinaryPath)
			else:
				tempROM = tempName(context.scene.outputRom)
				checkExpanded(bpy.path.abspath(context.scene.exportRom))
				romfileExport = \
					open(bpy.path.abspath(context.scene.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(context.scene.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[context.scene.colExportLevel])
				segmentData = levelParsed.segmentData

				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				addrRange = \
					exportCollisionBinary(obj, finalTransform, romfileOutput, 
						int(context.scene.colStartAddr, 16), 
						int(context.scene.colEndAddr, 16),
						False, context.scene.colIncludeChildren)

				segAddress = encodeSegmentedAddr(addrRange[0], segmentData)
				if context.scene.set_addr_0x2A:
					romfileOutput.seek(int(context.scene.addr_0x2A, 16) + 4)
					romfileOutput.write(segAddress)
				segPointer = bytesToHex(segAddress)

				romfileOutput.close()

				if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
					os.remove(bpy.path.abspath(context.scene.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(context.scene.outputRom))

				self.report({'INFO'}, 'Success! Collision at (' + \
					hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
					') (Seg. ' + segPointer + ').')

			#applyRotation([obj], math.radians(-90), 'X')
			return {'FINISHED'} # must return a set

		except:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			#applyRotation([obj], math.radians(-90), 'X')

			if context.scene.colExportType == 'Binary':
				romfileOutput.close()
				if os.path.exists(bpy.path.abspath(tempROM)):
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
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsColE = col.operator(SM64_ExportCollision.bl_idname)

		col.prop(context.scene, 'colExportType')
		col.prop(context.scene, 'colIncludeChildren')
		if context.scene.colExportType == 'C':
			col.prop(context.scene, 'colExportPath')
		elif context.scene.colExportType == 'Insertable Binary':
			col.prop(context.scene, 'colInsertableBinaryPath')
		else:
			prop_split(col, context.scene, 'colStartAddr', 'Start Address')
			prop_split(col, context.scene, 'colEndAddr', 'End Address')
			prop_split(col, context.scene, 'colExportLevel', 
				'Level Used By Collision')
			col.prop(context.scene, 'set_addr_0x2A')
			if context.scene.set_addr_0x2A:
				prop_split(col, context.scene, 'addr_0x2A', 
					'0x2A Behaviour Command Address')
		for i in range(panelSeparatorSize):
			col.separator()

class F3D_GlobalSettingsPanel(bpy.types.Panel):
	bl_idname = "F3D_PT_global_settings"
	bl_label = "F3D Global Settings"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

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
	bl_category = 'Fast64'

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
		col.prop(context.scene, 'decomp_compatible')
		prop_split(col, context.scene, 'refreshVer', 'Decomp Func Map')
		prop_split(col, context.scene, 'blenderToSM64Scale', 'Blender To SM64 Scale')

class SM64_AddressConvertPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_addr_conv"
	bl_label = "SM64 Address Converter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Fast64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		segToVirtOp = col.operator(SM64_AddrConv.bl_idname, 
			text = "Convert Segmented To Virtual")
		segToVirtOp.segToVirt = True
		virtToSegOp = col.operator(SM64_AddrConv.bl_idname, 
			text = "Convert Virtual To Segmented")
		virtToSegOp.segToVirt = False
		prop_split(col, context.scene, 'convertibleAddr', 'Address')
		col.prop(context.scene, 'levelConvert')

classes = (
	ArmatureApplyWithMesh,
	AddBoneGroups,
	CreateMetarig,
	N64_AddF3dMat,
	SM64_AddrConv,

	F3D_GlobalSettingsPanel,
	SM64_FileSettingsPanel,
	SM64_AddressConvertPanel,
	#SM64_ImportCharacterPanel,
	#SM64_ExportCharacterPanel,
	SM64_ImportGeolayoutPanel,
	SM64_ExportGeolayoutPanel,
	SM64_ArmatureToolsPanel,
	SM64_ImportAnimPanel,
	SM64_ExportAnimPanel,
	SM64_ImportDLPanel,
	SM64_ExportDLPanel,
	#SM64_ImportLevelPanel,
	#SM64_ExportLevelPanel,
	SM64_ExportCollisionPanel,

	#SM64_ImportMario,
	#SM64_ExportMario,
	SM64_ImportGeolayout,
	SM64_ExportGeolayoutArmature,
	SM64_ExportGeolayoutObject,
	SM64_ImportDL,
	SM64_ExportDL,
	SM64_ImportAnimMario,
	SM64_ExportAnimMario,
	#SM64_ImportLevel
	#SM64_ExportLevel
	SM64_ExportCollision,
)

# called on add-on enabling
# register operators and panels here
# append menu layout drawing function to an existing window
def register():
	col_register() # register first, so panel goes above mat panel
	mat_register()
	bone_register()
	cam_register()

	for cls in classes:
		register_class(cls)

	# Camera
	bpy.types.Scene.saveCameraSettings = bpy.props.BoolProperty(
		name = 'Save Level Camera Settings', default = False)
	bpy.types.Scene.levelCamera = bpy.props.PointerProperty(
		type = bpy.types.Camera, name = 'Level Camera')

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
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.DLExportisStatic = bpy.props.BoolProperty(
		name = 'Static DL', default = True)
	bpy.types.Scene.DLDefinePath = bpy.props.StringProperty(
		name = 'Definitions Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.DLUseBank0 = bpy.props.BoolProperty(name = 'Use Bank 0')
	bpy.types.Scene.DLRAMAddr = bpy.props.StringProperty(name = 'RAM Address', 
		default = '80000000')
	bpy.types.Scene.DLTexDir = bpy.props.StringProperty(
		name ='Include Path', default = '/level/ddd/')
	bpy.types.Scene.DLSaveTextures = bpy.props.BoolProperty(
		name = 'Save Textures As PNGs')
	bpy.types.Scene.DLSeparateTextureDef = bpy.props.BoolProperty(
		name = 'Save texture.inc.c separately')
	
	bpy.types.Scene.DLincludeChildren = bpy.props.BoolProperty(
		name = 'Include Children')
	bpy.types.Scene.DLInsertableBinaryPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')
	
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
	bpy.types.Scene.modelID = bpy.props.StringProperty(name = 'Model ID', 
		default = '1')
	bpy.types.Scene.ignoreSwitch = bpy.props.BoolProperty(
		name = 'Ignore Switch Nodes', default = True)
	bpy.types.Scene.textDumpGeo = bpy.props.BoolProperty(
		name = 'Dump geolayout as text', default = False)
	bpy.types.Scene.textDumpGeoPath =  bpy.props.StringProperty(
		name ='Text Dump Path', subtype = 'FILE_PATH')
	bpy.types.Scene.geoExportType = bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	bpy.types.Scene.geoExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.geoUseBank0 = bpy.props.BoolProperty(name = 'Use Bank 0')
	bpy.types.Scene.geoRAMAddr = bpy.props.StringProperty(name = 'RAM Address', 
		default = '80000000')
	bpy.types.Scene.geoTexDir = bpy.props.StringProperty(
		name ='Include Path', default = 'actors/mario/')
	bpy.types.Scene.geoSaveTextures = bpy.props.BoolProperty(
		name = 'Save Textures As PNGs')
	bpy.types.Scene.geoSeparateTextureDef = bpy.props.BoolProperty(
		name = 'Save texture.inc.c separately')
	bpy.types.Scene.geoInsertableBinaryPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.geoIsSegPtr = bpy.props.BoolProperty(
		name = 'Is Segmented Address')

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
	bpy.types.Scene.setAnimListIndex = bpy.props.BoolProperty(name = 'Set Anim List Entry', default = True)
	bpy.types.Scene.overwrite_0x28 = bpy.props.BoolProperty(name = 'Overwrite 0x28 behaviour command', default = True)
	bpy.types.Scene.addr_0x27 = bpy.props.StringProperty(
		name = '0x27 Command Address', default = '21CD00')
	bpy.types.Scene.addr_0x28 = bpy.props.StringProperty(
		name = '0x28 Command Address', default = '21CD08')
	bpy.types.Scene.animExportType = bpy.props.EnumProperty(
		items = enumExportType, name = 'Export', default = 'Binary')
	bpy.types.Scene.animExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.animOverwriteDMAEntry = bpy.props.BoolProperty(
		name = 'Overwrite DMA Entry')
	bpy.types.Scene.animInsertableBinaryPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')
	bpy.types.Scene.animIsSegPtr = bpy.props.BoolProperty(
		name = 'Is Segmented Address', default = False)
	bpy.types.Scene.animIsAnimList = bpy.props.BoolProperty(
		name = 'Is Anim List', default = True)
	bpy.types.Scene.animListIndexImport = bpy.props.IntProperty(
		name = 'Anim List Index', min = 0, max = 255)
	bpy.types.Scene.animListIndexExport = bpy.props.IntProperty(
		name = "Anim List Index", min = 0, max = 255)
	

	# Collision
	bpy.types.Scene.colExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
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
	bpy.types.Scene.colIncludeChildren = bpy.props.BoolProperty(
		name = 'Include child objects', default = True)
	bpy.types.Scene.colInsertableBinaryPath = bpy.props.StringProperty(
		name = 'Filepath', subtype = 'FILE_PATH')

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
	bpy.types.Scene.decomp_compatible = bpy.props.BoolProperty(
		name = 'Decomp Compatibility', default = True)
	bpy.types.Scene.convertibleAddr = bpy.props.StringProperty(
		name = 'Address')
	bpy.types.Scene.levelConvert = bpy.props.EnumProperty(
		items = level_enums, name = 'Level', default = 'IC')
	bpy.types.Scene.refreshVer = bpy.props.EnumProperty(
		items = enumRefreshVer, name = 'Refresh', default = 'Refresh 4')
	bpy.types.Scene.blenderToSM64Scale = bpy.props.FloatProperty(
		name = 'Blender To SM64 Scale', default = 212.766)

	bpy.types.Scene.characterIgnoreSwitch = \
		bpy.props.BoolProperty(name = 'Ignore Switch Nodes', default = True)

# called on add-on disabling
def unregister():

	# Camera
	del bpy.types.Scene.saveCameraSettings
	del bpy.types.Scene.levelCamera

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
	del bpy.types.Scene.geoUseBank0
	del bpy.types.Scene.geoRAMAddr
	del bpy.types.Scene.geoTexDir
	del bpy.types.Scene.geoSaveTextures
	del bpy.types.Scene.geoSeparateTextureDef
	del bpy.types.Scene.geoInsertableBinaryPath
	del bpy.types.Scene.geoIsSegPtr

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
	del bpy.types.Scene.setAnimListIndex
	del bpy.types.Scene.overwrite_0x28
	del bpy.types.Scene.addr_0x27
	del bpy.types.Scene.addr_0x28
	del bpy.types.Scene.animExportType
	del bpy.types.Scene.animExportPath
	del bpy.types.Scene.animOverwriteDMAEntry
	del bpy.types.Scene.animInsertableBinaryPath
	del bpy.types.Scene.animIsSegPtr
	del bpy.types.Scene.animIsAnimList
	del bpy.types.Scene.animListIndexImport
	del bpy.types.Scene.animListIndexExport

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
	del bpy.types.Scene.DLTexDir
	del bpy.types.Scene.DLSaveTextures
	del bpy.types.Scene.DLSeparateTextureDef
	del bpy.types.Scene.DLincludeChildren
	del bpy.types.Scene.DLInsertableBinaryPath

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
	del bpy.types.Scene.colInsertableBinaryPath

	# ROM
	del bpy.types.Scene.importRom
	del bpy.types.Scene.exportRom
	del bpy.types.Scene.outputRom
	del bpy.types.Scene.extendBank4
	del bpy.types.Scene.convertibleAddr
	del bpy.types.Scene.levelConvert
	del bpy.types.Scene.refreshVer
	del bpy.types.Scene.blenderToSM64Scale

	mat_unregister()
	bone_unregister()
	col_unregister()
	cam_unregister()
	for cls in classes:
		unregister_class(cls)
