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
from ..panels import SM64_Panel, sm64GoalTypeEnum, sm64GoalImport

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

class SM64_MenuVisibilityPanel(SM64_Panel):
	bl_idname = "SM64_PT_menu_visibility_settings"
	bl_label = "SM64 Menu Visibility Settings"
	bl_options = set() # default to open
	bl_order = 0 # force to front

	def draw(self, context):
		col = self.layout.column()
		col.scale_y = 1.1 # extra padding
		sm64Props: SM64_Properties = context.scene.fast64.sm64

		prop_split(col, sm64Props, 'goal', 'Export goal')
		prop_split(col, sm64Props, 'showImportingMenus', 'Show Importing Options')

class SM64_FileSettingsPanel(SM64_Panel):
	bl_idname = "SM64_PT_file_settings"
	bl_label = "SM64 File Settings"
	bl_options = set()

	def draw(self, context):
		col = self.layout.column()
		col.scale_y = 1.1 # extra padding
		sm64Props: SM64_Properties = context.scene.fast64.sm64

		prop_split(col, sm64Props, 'exportType', 'Export type')
		prop_split(col, context.scene, 'blenderToSM64Scale', 'Blender To SM64 Scale')

		if sm64Props.showImportingMenus:
			col.prop(context.scene, 'importRom')

		if sm64Props.exportType == 'Binary':
			col.prop(context.scene, 'exportRom')
			col.prop(context.scene, 'outputRom')
			col.prop(context.scene, 'extendBank4')
		elif sm64Props.exportType == 'C':
			col.prop(context.scene, 'disableScroll')
			col.prop(context.scene, 'decompPath')
			prop_split(col, context.scene, 'refreshVer', 'Decomp Func Map')
			prop_split(col, context.scene, 'compressionFormat', 'Compression Format')

class SM64_AddressConvertPanel(SM64_Panel):
	bl_idname = "SM64_PT_addr_conv"
	bl_label = "SM64 Address Converter"
	goal = sm64GoalImport

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

def get_legacy_export_type():
	legacy_export_types = ('C', 'Binary', 'Insertable Binary')
	scene = bpy.context.scene

	for exportKey in ['animExportType', 'colExportType', 'DLExportType', 'geoExportType']:
		try:
			eType = scene.pop(exportKey)
			if eType and legacy_export_types[eType] != 'C':
				return legacy_export_types[eType]
		except KeyError:
			pass

	return 'C'

class SM64_Properties(bpy.types.PropertyGroup):
	'''Global SM64 Scene Properties found under scene.fast64.sm64'''
	version: bpy.props.IntProperty(name="SM64_Properties Version", default=0)
	cur_version = 1 # version after property migration

	# UI Selection
	showImportingMenus: bpy.props.BoolProperty(name='Show Importing Menus', default=False)
	exportType: bpy.props.EnumProperty(items = enumExportType, name = 'Export Type', default = 'C')
	goal: bpy.props.EnumProperty(items=sm64GoalTypeEnum, name = 'Export Goal', default = 'All')
	
	# TODO: Utilize these across all exports
	# C exporting
	# useCustomExportLocation = bpy.props.BoolProperty(name = 'Use Custom Export Path')
	# customExportPath: bpy.props.StringProperty(name = 'Custom Export Path', subtype = 'FILE_PATH')
	# exportLocation: bpy.props.EnumProperty(items = enumExportHeaderType, name = 'Export Location', default = 'Actor')
	# useSelectedObjectName = bpy.props.BoolProperty(name = 'Use Name From Selected Object', default=False)
	# exportName: bpy.props.StringProperty(name='Name', default='mario')
	# exportGeolayoutName: bpy.props.StringProperty(name='Name', default='mario_geo')

	# Actor exports
	# exportGroup: bpy.props.StringProperty(name='Group', default='group0')

	# Level exports
	# exportLevelName: bpy.props.StringProperty(name = 'Level', default = 'bob')
	# exportLevelOption: bpy.props.EnumProperty(items = enumLevelNames, name = 'Level', default = 'bob')

	# Insertable Binary
	# exportInsertableBinaryPath: bpy.props.StringProperty(name = 'Filepath', subtype = 'FILE_PATH')

	@staticmethod
	def upgrade_changed_props():
		if bpy.context.scene.fast64.sm64.version != SM64_Properties.cur_version:
			bpy.context.scene.fast64.sm64.exportType = get_legacy_export_type()
			bpy.context.scene.fast64.sm64.version = SM64_Properties.cur_version


sm64_classes = (
	SM64_AddrConv,
	SM64_Properties,
)

sm64_panel_classes = (
	SM64_MenuVisibilityPanel,
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
