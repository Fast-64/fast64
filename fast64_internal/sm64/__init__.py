from .sm64_f3d_writer import *
from .sm64_geolayout_writer import *
from .sm64_geolayout_parser import *
from .sm64_level_parser import *
from .sm64_constants import *
from .sm64_rom_tweaks import *
from .sm64_anim import *
from .sm64_geolayout_bone import *
from .sm64_collision import *
from .sm64_camera import *
from .sm64_objects import *
from .sm64_level_writer import *
from .sm64_spline import *
from .sm64_f3d_parser import *

import bpy
from bpy.utils import register_class, unregister_class

enumRefreshVer = [
	("Refresh 3", "Refresh 3", "Refresh 3"),
	("Refresh 4", "Refresh 4", "Refresh 4"),
	("Refresh 5", "Refresh 5", "Refresh 5"),
	("Refresh 6", "Refresh 6", "Refresh 6"),
	("Refresh 7", "Refresh 7", "Refresh 7"),
	("Refresh 8", "Refresh 8", "Refresh 8"),
	("Refresh 10", "Refresh 10", "Refresh 10"),
	("Refresh 11", "Refresh 11", "Refresh 11"),
	("Refresh 12", "Refresh 12", "Refresh 12"),
	("Refresh 13", "Refresh 13", "Refresh 13"),
]

class SM64_AddrConv(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.addr_conv'
	bl_label = "Convert Address"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	segToVirt : bpy.props.BoolProperty()

	def execute(self, context):
		romfileSrc = None
		try:
			address = int(context.scene.convertibleAddr, 16)
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
		except Exception as e:
			if romfileSrc is not None:
				romfileSrc.close()
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

class SM64_FileSettingsPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_file_settings"
	bl_label = "SM64 File Settings"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'SM64'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()	
		prop_split(col, context.scene, 'blenderToSM64Scale', 'Blender To SM64 Scale')

		col.prop(context.scene, 'importRom')
		col.prop(context.scene, 'exportRom')
		col.prop(context.scene, 'outputRom')
		col.prop(context.scene, 'extendBank4')
		
		col.prop(context.scene, 'disableScroll')
		
		col.prop(context.scene, 'decompPath')
		
		prop_split(col, context.scene, 'refreshVer', 'Decomp Func Map')
		prop_split(col, context.scene, 'compressionFormat', 'Compression Format')

class SM64_AddressConvertPanel(bpy.types.Panel):
	bl_idname = "SM64_PT_addr_conv"
	bl_label = "SM64 Address Converter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'SM64'

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

sm64_classes = (
	SM64_AddrConv,
)

sm64_panel_classes = (
	SM64_FileSettingsPanel,
	SM64_AddressConvertPanel,
)

def sm64_panel_register():
	for cls in sm64_panel_classes:
		register_class(cls)

	sm64_col_panel_register()
	sm64_bone_panel_register()
	sm64_cam_panel_register()
	sm64_obj_panel_register()
	sm64_geo_parser_panel_register()
	sm64_geo_writer_panel_register()
	sm64_level_panel_register()
	sm64_spline_panel_register()
	sm64_dl_writer_panel_register()
	sm64_dl_parser_panel_register()
	sm64_anim_panel_register()

def sm64_panel_unregister():
	for cls in sm64_panel_classes:
		unregister_class(cls)

	sm64_col_panel_unregister()
	sm64_bone_panel_unregister()
	sm64_cam_panel_unregister()
	sm64_obj_panel_unregister()
	sm64_geo_parser_panel_unregister()
	sm64_geo_writer_panel_unregister()
	sm64_level_panel_unregister()
	sm64_spline_panel_unregister()
	sm64_dl_writer_panel_unregister()
	sm64_dl_parser_panel_unregister()
	sm64_anim_panel_unregister()

def sm64_register(registerPanels):
	for cls in sm64_classes:
		register_class(cls)

	sm64_col_register() # register first, so panel goes above mat panel
	sm64_bone_register()
	sm64_cam_register()
	sm64_obj_register()
	sm64_geo_parser_register()
	sm64_geo_writer_register()
	sm64_level_register()
	sm64_spline_register()
	sm64_dl_writer_register()
	sm64_dl_parser_register()
	sm64_anim_register()

	if registerPanels:
		sm64_panel_register()

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
	bpy.types.Scene.convertibleAddr = bpy.props.StringProperty(
		name = 'Address')
	bpy.types.Scene.levelConvert = bpy.props.EnumProperty(
		items = level_enums, name = 'Level', default = 'IC')
	bpy.types.Scene.refreshVer = bpy.props.EnumProperty(
		items = enumRefreshVer, name = 'Refresh', default = 'Refresh 13')
	bpy.types.Scene.disableScroll = bpy.props.BoolProperty(
		name = 'Disable Scrolling Textures')

	bpy.types.Scene.blenderToSM64Scale = bpy.props.FloatProperty(
		name = 'Blender To SM64 Scale', default = 100) # 212.766
	bpy.types.Scene.decompPath = bpy.props.StringProperty(
		name ='Decomp Folder', subtype = 'FILE_PATH')
	
	bpy.types.Scene.compressionFormat = bpy.props.EnumProperty(
		items = enumCompressionFormat, name = 'Compression', default = 'mio0')

def sm64_unregister(unregisterPanels):
	for cls in reversed(sm64_classes):
		unregister_class(cls)

	sm64_col_unregister() # register first, so panel goes above mat panel
	sm64_bone_unregister()
	sm64_cam_unregister()
	sm64_obj_unregister()
	sm64_geo_parser_unregister()
	sm64_geo_writer_unregister()
	sm64_level_unregister()
	sm64_spline_unregister()
	sm64_dl_writer_unregister()
	sm64_dl_parser_unregister()
	sm64_anim_unregister()

	if unregisterPanels:
		sm64_panel_unregister()

	del bpy.types.Scene.importRom
	del bpy.types.Scene.exportRom
	del bpy.types.Scene.outputRom
	del bpy.types.Scene.extendBank4
	
	del bpy.types.Scene.convertibleAddr
	del bpy.types.Scene.levelConvert
	del bpy.types.Scene.refreshVer

	del bpy.types.Scene.disableScroll
	
	del bpy.types.Scene.blenderToSM64Scale
	del bpy.types.Scene.decompPath
	del bpy.types.Scene.compressionFormat