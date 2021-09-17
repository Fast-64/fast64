from ..panels import OOT_Panel
from .oot_f3d_writer import *
#from .oot_geolayout_writer import *
#from .oot_geolayout_parser import *
from .oot_constants import *
#from .oot_anim import *
#from .oot_geolayout_bone import *
from .oot_collision import *
from .oot_level import *
from .oot_level_writer import *
from .c_writer import *
from .oot_spline import *
from .oot_anim import *
from .oot_skeleton import *
from .oot_operators import *
#from .oot_f3d_parser import *

import bpy
from bpy.utils import register_class, unregister_class

ootEnumRefreshVer = [
	("Refresh 3", "Refresh 3", "Refresh 3"),
]

class OOT_FileSettingsPanel(OOT_Panel):
	bl_idname = "OOT_PT_file_settings"
	bl_label = "OOT File Settings"
	bl_options = set() # default to being open

	# called every frame
	def draw(self, context):
		col = self.layout.column()	
		col.scale_y = 1.1 # extra padding, makes it easier to see these main settings
		prop_split(col, context.scene, 'ootBlenderScale', 'OOT Scene Scale')
		prop_split(col, context.scene, 'ootActorBlenderScale', 'OOT Actor Scale')
		
		#col.prop(context.scene, 'ootDisableScroll')
		#col.prop(context.scene, 'ootSaveTextures')
		prop_split(col, context.scene, 'ootDecompPath', "Decomp Path")
		
		#prop_split(col, context.scene, 'ootRefreshVer', 'Decomp Func Map')

class OOT_Properties(bpy.types.PropertyGroup):
	'''Global OOT Scene Properties found under scene.fast64.oot'''
	version: bpy.props.IntProperty(name="OOT_Properties Version", default=0)

oot_classes = (
	OOT_FileSettingsPanel,
	OOT_Properties,
)

def oot_panel_register():
	oot_operator_panel_register()
	oot_dl_writer_panel_register()
	oot_col_panel_register()
	#oot_bone_panel_register()
	oot_obj_panel_register()
	#oot_geo_parser_panel_register()
	#oot_geo_writer_panel_register()
	oot_level_panel_register()
	oot_spline_panel_register()
	#oot_dl_parser_panel_register()
	oot_anim_panel_register()
	oot_skeleton_panel_register()

def oot_panel_unregister():
	oot_operator_panel_unregister()
	oot_col_panel_unregister()
	#oot_bone_panel_unregister()
	oot_obj_panel_unregister()
	#oot_geo_parser_panel_unregister()
	#oot_geo_writer_panel_unregister()
	oot_level_panel_unregister()
	oot_spline_panel_unregister()
	oot_dl_writer_panel_unregister()
	#oot_dl_parser_panel_unregister()
	oot_anim_panel_unregister()
	oot_skeleton_panel_unregister()

def oot_register(registerPanels):
	for cls in oot_classes:
		register_class(cls)

	oot_operator_register()
	oot_utility_register()
	oot_col_register() # register first, so panel goes above mat panel
	#oot_bone_register()
	oot_obj_register()
	#oot_geo_parser_register()
	#oot_geo_writer_register()
	oot_level_register()
	oot_spline_register()
	oot_dl_writer_register()
	#oot_dl_parser_register()
	oot_anim_register()
	oot_skeleton_register()

	if registerPanels:
		oot_panel_register()

	bpy.types.Scene.ootBlenderScale = bpy.props.FloatProperty(name = 'Blender To OOT Scale', default = 10)
	bpy.types.Scene.ootActorBlenderScale = bpy.props.FloatProperty(name = 'Blender To OOT Actor Scale', default = 1000)
	bpy.types.Scene.ootRefreshVer = bpy.props.EnumProperty(
		items = ootEnumRefreshVer, name = 'Refresh', default = 'Refresh 3')
	bpy.types.Scene.ootDecompPath = bpy.props.StringProperty(
		name ='Decomp Folder', subtype = 'FILE_PATH')
	#bpy.types.Scene.ootDisableScroll = bpy.props.BoolProperty(name = "Disable Scrolling Textures")
	#bpy.types.Scene.ootSaveTextures = bpy.props.BoolProperty(name = "Save Texture Files As Images")

def oot_unregister(unregisterPanels):
	for cls in reversed(oot_classes):
		unregister_class(cls)

	oot_operator_unregister()
	oot_utility_unregister()
	oot_col_unregister() # register first, so panel goes above mat panel
	#oot_bone_unregister()
	oot_obj_unregister()
	#oot_geo_parser_unregister()
	#oot_geo_writer_unregister()
	oot_level_unregister()
	oot_spline_unregister()
	oot_dl_writer_unregister()
	#oot_dl_parser_unregister()
	oot_anim_unregister()
	oot_skeleton_unregister()

	if unregisterPanels:
		oot_panel_unregister()

	del bpy.types.Scene.ootRefreshVer
	del bpy.types.Scene.ootBlenderScale 
	del bpy.types.Scene.ootActorBlenderScale
	del bpy.types.Scene.ootDecompPath
