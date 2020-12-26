import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *

from ..utility import *


class OOTExitProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

	exitIndex : bpy.props.EnumProperty(items = ootEnumExitIndex, default = "Default")
	exitIndexCustom : bpy.props.StringProperty(default = '0x00')

	# These are used when adding an entry to gEntranceTable
	scene : bpy.props.EnumProperty(items = ootEnumSceneID, default = "SCENE_YDAN")
	sceneCustom : bpy.props.StringProperty(default = "SCENE_YDAN")

	# These are used when adding an entry to gEntranceTable
	continueBGM : bpy.props.BoolProperty(default = False)
	displayTitleCard : bpy.props.BoolProperty(default = True)
	fadeInAnim : bpy.props.EnumProperty(items = ootEnumTransitionAnims, default = '0x02')
	fadeInAnimCustom : bpy.props.StringProperty(default = '0x02')
	fadeOutAnim : bpy.props.EnumProperty(items = ootEnumTransitionAnims, default = '0x02')
	fadeOutAnimCustom : bpy.props.StringProperty(default = '0x02')

def drawExitProperty(layout, exitProp, index, headerIndex):
	box = layout.box()
	box.prop(exitProp, 'expandTab', text = 'Exit ' + \
		str(index), icon = 'TRIA_DOWN' if exitProp.expandTab else \
		'TRIA_RIGHT')
	if exitProp.expandTab:
		drawEnumWithCustom(box, exitProp, "exitIndex", "Exit Index", "")
		if exitProp.exitIndex != "Custom":
			box.label(text = "This is unfinished, use \"Custom\".")
			exitGroup = box.column()
			exitGroup.enabled = False
			drawEnumWithCustom(exitGroup, exitProp, "scene", "Scene", "")
			exitGroup.prop(exitProp, "continueBGM", text = "Continue BGM")
			exitGroup.prop(exitProp, "displayTitleCard", text = "Display Title Card")
			drawEnumWithCustom(exitGroup, exitProp, "fadeInAnim", "Fade In Animation", "")
			drawEnumWithCustom(exitGroup, exitProp, "fadeOutAnim", "Fade Out Animation", "")

		drawCollectionOps(box, index, "Exit", headerIndex)

class OOTEntranceProperty(bpy.types.PropertyGroup):
	# This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
	spawnIndex : bpy.props.IntProperty(min = 0)

def drawEntranceProperty(layout, obj):
	box = layout.box()
	if obj.parent is not None and obj.parent.data is None and obj.parent.ootEmptyType == "Room":
		split = box.split(factor = 0.5)
		split.label(text = "Room Index")
		split.box().label(text = str(obj.parent.ootRoomHeader.roomIndex))
	else:
		box.label(text = "Entrance must be parented to a Room.")

	entranceProp = obj.ootEntranceProperty
	prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
