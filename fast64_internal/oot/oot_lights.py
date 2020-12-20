import bpy
from ..utility import *
from .oot_utility import *

class OOTLightProperty(bpy.types.PropertyGroup):
	ambient : bpy.props.FloatVectorProperty(name = "Ambient Color", size = 4, min = 0, max = 1, default = (70/255, 40/255, 57/255 ,1), subtype = 'COLOR')
	diffuse0 : bpy.props.PointerProperty(name = "Diffuse 0", type = bpy.types.Light)
	diffuse1 : bpy.props.PointerProperty(name = "Diffuse 1", type = bpy.types.Light)
	fogColor : bpy.props.FloatVectorProperty(name = "", size = 4, min = 0, max = 1, default = (140/255, 120/255, 110/255 ,1), subtype = 'COLOR')
	fogDistance : bpy.props.FloatProperty(name = "", default = 0x3E1)
	transitionSpeed : bpy.props.FloatProperty(name = "", default = 1)
	drawDistance : bpy.props.FloatProperty(name = "", default = 3200)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

def drawLightProperty(layout, lightProp, index, sceneHeaderIndex):
	box = layout.box()
	box.prop(lightProp, 'expandTab', text = 'Lighting ' + \
		str(index), icon = 'TRIA_DOWN' if lightProp.expandTab else \
		'TRIA_RIGHT')
	if lightProp.expandTab:
		prop_split(box, lightProp, 'ambient', 'Ambient Color')
		prop_split(box, lightProp, 'diffuse0', 'Diffuse 0 Light')
		prop_split(box, lightProp, 'diffuse1', 'Diffuse 1 Light')
		prop_split(box, lightProp, 'fogColor', 'Fog Color')
		prop_split(box, lightProp, 'fogDistance', 'Fog Distance')
		prop_split(box, lightProp, 'transitionSpeed', 'Transition Speed')
		prop_split(box, lightProp, 'drawDistance', 'Draw Distance')

		drawCollectionOps(box, index, "Light", sceneHeaderIndex)