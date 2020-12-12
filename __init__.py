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
	"author": "kurethedead",
	"location": "3DView",
	"description": "Plugin for exporting F3D display lists and other game data related to Super Mario 64.",
	"category": "Import-Export",
	"blender": (2, 82, 0),
	}

sm64_panels_registered = False

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
		try:
			if context.mode != 'OBJECT' and context.mode != 'POSE':
				raise PluginError("Operator can only be used in object or pose mode.")
			elif context.mode == 'POSE':
				bpy.ops.object.mode_set(mode = "OBJECT")

			if len(context.selected_objects) == 0:
				raise PluginError("Armature not selected.")
			elif type(context.selected_objects[0].data) is not\
				bpy.types.Armature:
				raise PluginError("Armature not selected.")
			
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
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}

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
		try:
			if context.mode != 'OBJECT' and context.mode != 'POSE':
				raise PluginError("Operator can only be used in object or pose mode.")
			elif context.mode == 'POSE':
				bpy.ops.object.mode_set(mode = "OBJECT")

			if len(context.selected_objects) == 0:
				raise PluginError("Armature not selected.")
			elif type(context.selected_objects[0].data) is not\
				bpy.types.Armature:
				raise PluginError("Armature not selected.")
			
			armatureObj = context.selected_objects[0]
			createBoneGroups(armatureObj)
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}

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
		try:
			if context.mode != 'OBJECT' and context.mode != 'POSE':
				raise PluginError("Operator can only be used in object or pose mode.")
			elif context.mode == 'POSE':
				bpy.ops.object.mode_set(mode = "OBJECT")

			if len(context.selected_objects) == 0:
				raise PluginError("Armature not selected.")
			elif type(context.selected_objects[0].data) is not\
				bpy.types.Armature:
				raise PluginError("Armature not selected.")
			
			armatureObj = context.selected_objects[0]
			generateMetarig(armatureObj)
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}

		self.report({'INFO'}, 'Created metarig.')
		return {'FINISHED'} # must return a set

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
		
classes = (
	ArmatureApplyWithMesh,
	AddBoneGroups,
	CreateMetarig,

	F3D_GlobalSettingsPanel,
	SM64_ArmatureToolsPanel,
)

# called on add-on enabling
# register operators and panels here
# append menu layout drawing function to an existing window
def register():
	mat_register()
	render_engine_register()
	bsdf_conv_register()
	sm64_register(False)

	sm64_panel_register()
	sm64_panels_registered = True

	for cls in classes:
		register_class(cls)

	# ROM
	
	bpy.types.Scene.decomp_compatible = bpy.props.BoolProperty(
		name = 'Decomp Compatibility', default = True)
	bpy.types.Scene.blenderToSM64Scale = bpy.props.FloatProperty(
		name = 'Blender To SM64 Scale', default = 212.766)
	bpy.types.Scene.decompPath = bpy.props.StringProperty(
		name ='Decomp Folder', subtype = 'FILE_PATH')
	bpy.types.Scene.ignoreTextureRestrictions = bpy.props.BoolProperty(
		name = 'Ignore Texture Restrictions (Breaks CI Textures)')
	bpy.types.Scene.compressionFormat = bpy.props.EnumProperty(
		items = enumCompressionFormat, name = 'Compression', default = 'mio0')
	bpy.types.Scene.fullTraceback = \
		bpy.props.BoolProperty(name = 'Show Full Error Traceback', default = False)

# called on add-on disabling
def unregister():
	sm64_unregister(True)
	sm64_panels_registered = False
	mat_unregister()
	bsdf_conv_unregister()
	render_engine_unregister()

	# ROM
	del bpy.types.Scene.blenderToSM64Scale
	del bpy.types.Scene.fullTraceback
	del bpy.types.Scene.decompPath
	del bpy.types.Scene.decomp_compatible
	del bpy.types.Scene.ignoreTextureRestrictions

	for cls in classes:
		unregister_class(cls)
