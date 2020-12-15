import bpy
from ..utility import *
from .oot_utility import *

import bpy
from ..utility import *
from .oot_utility import *

class OOTHeaderItemProperty(bpy.types.PropertyGroup):
	headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

class OOTHeaderProperty(bpy.types.PropertyGroup):
	inAllSceneSetups : bpy.props.BoolProperty(name = "Actor Exists In All Scene Setups", default = True)
	childDayHeader : bpy.props.BoolProperty(name = "Child Day Header", default = True)
	childNightHeader : bpy.props.BoolProperty(name = "Child Night Header", default = True)
	adultDayHeader : bpy.props.BoolProperty(name = "Adult Day Header", default = True)
	adultNightHeader : bpy.props.BoolProperty(name = "Adult Night Header", default = True)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTHeaderItemProperty)

def drawHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetup.prop(headerProp, "inAllSceneSetups", text = "Actor Exists In All Scene Setups")
	if not headerProp.inAllSceneSetups:
		headerSetupBox = headerSetup.box()
		headerSetupBox.prop(headerProp, 'childDayHeader', text = "Child Day")
		headerSetupBox.prop(headerProp, 'childNightHeader', text = "Child Night")
		headerSetupBox.prop(headerProp, 'adultDayHeader', text = "Adult Day")
		headerSetupBox.prop(headerProp, 'adultNightHeader', text = "Adult Night")
		headerSetup.operator(OOTAddHeader.bl_idname).option = len(headerProp.cutsceneHeaders)
		for i in range(len(headerProp.cutsceneHeaders)):
			drawHeaderItemProperty(headerSetup, headerProp.cutsceneHeaders[i], i)

def drawHeaderItemProperty(layout, headerItemProp, index):
	box = layout.box()
	box.prop(headerItemProp, 'expandTab', text = 'Header ' + \
		str(headerItemProp.headerIndex), icon = 'TRIA_DOWN' if headerItemProp.expandTab else \
		'TRIA_RIGHT')
	if headerItemProp.expandTab:
		prop_split(box, headerItemProp, 'headerIndex', 'Header Index')

		drawCollectionProperty(box, index, OOTAddHeader.bl_idname,
			OOTRemoveHeader.bl_idname, OOTMoveHeader.bl_idname)
		
class OOTAddHeader(bpy.types.Operator):
	bl_idname = 'object.oot_add_header'
	bl_label = 'Add Header'
	bl_options = {'REGISTER', 'UNDO'} 
	option : bpy.props.IntProperty()
	def execute(self, context):
		obj = context.object
		obj.ootSceneProperty.headerSettings.cutsceneHeaders.add()
		obj.ootSceneProperty.headerSettings.cutsceneHeaders.move(len(obj.ootSceneProperty.headerSettings.cutsceneHeaders)-1, self.option)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

class OOTRemoveHeader(bpy.types.Operator):
	bl_idname = 'object.oot_remove_header'
	bl_label = 'Remove Header'
	bl_options = {'REGISTER', 'UNDO'} 
	option : bpy.props.IntProperty()
	def execute(self, context):
		context.object.ootSceneProperty.headerSettings.cutsceneHeaders.remove(self.option)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

class OOTMoveHeader(bpy.types.Operator):
	bl_idname = 'object.oot_move_header'
	bl_label = 'Move Header'
	bl_options = {'REGISTER', 'UNDO'} 
	option : bpy.props.IntProperty()
	offset : bpy.props.IntProperty()
	def execute(self, context):
		obj = context.object
		obj.ootSceneProperty.headerSettings.cutsceneHeaders.move(self.option, self.option + self.offset)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 
