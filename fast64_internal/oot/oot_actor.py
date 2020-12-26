
import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *

from ..utility import *

class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_actor_id_enum_operator"
	bl_label = "Search Actor IDs"
	bl_property = "ootEnumActorID"
	bl_options = {'REGISTER', 'UNDO'} 

	ootEnumActorID : bpy.props.EnumProperty(items = ootEnumActorID, default = "ACTOR_PLAYER")

	def execute(self, context):
		context.object.ootActorProperty.actorID = self.ootEnumActorID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootEnumActorID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
	headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

class OOTActorHeaderProperty(bpy.types.PropertyGroup):
	inAllSceneSetups : bpy.props.BoolProperty(name = "Actor Exists In All Scene Setups", default = True)
	childDayHeader : bpy.props.BoolProperty(name = "Child Day Header", default = True)
	childNightHeader : bpy.props.BoolProperty(name = "Child Night Header", default = True)
	adultDayHeader : bpy.props.BoolProperty(name = "Adult Day Header", default = True)
	adultNightHeader : bpy.props.BoolProperty(name = "Adult Night Header", default = True)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTActorHeaderItemProperty)

def drawActorHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetup.prop(headerProp, "inAllSceneSetups", text = "Actor Exists In All Scene Setups")
	if not headerProp.inAllSceneSetups:
		headerSetupBox = headerSetup.box()
		headerSetupBox.prop(headerProp, 'childDayHeader', text = "Child Day")
		headerSetupBox.prop(headerProp, 'childNightHeader', text = "Child Night")
		headerSetupBox.prop(headerProp, 'adultDayHeader', text = "Adult Day")
		headerSetupBox.prop(headerProp, 'adultNightHeader', text = "Adult Night")
		drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Actor", None)
		for i in range(len(headerProp.cutsceneHeaders)):
			drawActorHeaderItemProperty(headerSetup, headerProp.cutsceneHeaders[i], i)

def drawActorHeaderItemProperty(layout, headerItemProp, index):
	box = layout.box()
	box.prop(headerItemProp, 'expandTab', text = 'Header ' + \
		str(headerItemProp.headerIndex), icon = 'TRIA_DOWN' if headerItemProp.expandTab else \
		'TRIA_RIGHT')
	if headerItemProp.expandTab:
		prop_split(box, headerItemProp, 'headerIndex', 'Header Index')
		drawCollectionOps(box, index, "Actor", None)
		
class OOTActorProperty(bpy.types.PropertyGroup):
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
	headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

def drawActorProperty(layout, actorProp):
	#prop_split(layout, actorProp, 'actorID', 'Actor')
	actorIDBox = layout.box()
	actorIDBox.box().label(text = "Actor ID: " + getEnumName(ootEnumActorID, actorProp.actorID))
	if actorProp.actorID == 'Custom':
		#actorIDBox.prop(actorProp, 'actorIDCustom', text = 'Actor ID')
		prop_split(actorIDBox, actorProp, 'actorIDCustom', 'Actor ID')

	actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon = 'VIEWZOOM')
	#layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
	prop_split(layout, actorProp, "actorParam", 'Actor Parameter')

	drawActorHeaderProperty(layout, actorProp.headerSettings)

class OOTTransitionActorProperty(bpy.types.PropertyGroup):
	roomIndex : bpy.props.IntProperty(min = 0)
	cameraTransitionFront : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionFrontCustom : bpy.props.StringProperty(default = '0x00')
	cameraTransitionBack : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
	cameraTransitionBackCustom : bpy.props.StringProperty(default = '0x00')
	
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumTransitionActorID, default = 'ACTOR_EN_DOOR')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_EN_DOOR')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

def drawTransitionActorProperty(layout, transActorProp):
	actorIDBox = layout.box()
	actorIDBox.box().label(text = "Properties")
	prop_split(actorIDBox, transActorProp, 'actorID', 'Actor')
	#actorIDBox.box().label(text = "Actor ID: " + transActorProp.actorID)
	if transActorProp.actorID == 'Custom':
		prop_split(actorIDBox, transActorProp, 'actorIDCustom', 'Actor ID')

	prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
	drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
	drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

	#layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
	prop_split(layout, transActorProp, "actorParam", 'Actor Parameter')
	