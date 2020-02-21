from .utility import *
from .sm64_constants import *
from bpy.utils import register_class, unregister_class
import bpy, bmesh
import os
from io import BytesIO
import math

class SM64_Object:
	def __init__(self, model, position, rotation, behaviour, bparam, acts):
		self.model = model
		self.behaviour = behaviour
		self.bparam = bparam
		self.acts = acts
		self.position = position
		self.rotation = rotation
	
	def to_c(self):
		if self.acts == 0x1F:
			return 'OBJECT(' + str(self.model) + ', ' + \
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ', ' + \
				str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
				str(int(round(math.degrees(self.rotation[2])))) + ', ' + \
				str(self.bparam) + ', ' + str(self.behaviour) + ')'
		else:
			return 'OBJECT_WITH_ACTS(' + str(self.model) + ', ' + \
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ', ' + \
				str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
				str(int(round(math.degrees(self.rotation[2])))) + ', ' + \
				str(self.bparam) + ', ' + str(self.behaviour) + ', ' + str(self.acts) + ')'

class SM64_Whirpool:
	def __init__(self, index, condition, strength, position):
		self.index = index
		self.condition = condition
		self.strength = strength
		self.position = position
	
	def to_c(self):
		return 'WHIRPOOL(' + str(self.index) + ', ' +  str(self.condition) + ', ' +\
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(self.strength) + ')'

class SM64_Macro_Object:
	def __init__(self, preset, position, rotation, bparam):
		self.preset = preset
		self.bparam = bparam
		self.position = position
		self.rotation = rotation
	
	def to_c(self):
		if self.bparam is None:
			return 'MACRO_OBJECT(' + str(self.preset) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ')'
		else:
			return 'MACRO_OBJECT_WITH_BEH_PARAM(' + str(self.preset) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ', ' + \
				str(self.bparam) + ')'

class SM64_Special_Object:
	def __init__(self, preset, position, rotation, bparam):
		self.preset = preset
		self.bparam = bparam
		self.position = position
		self.rotation = rotation

	def to_binary(self):
		data = int(self.preset).to_bytes(2, 'big')
		if len(self.position) > 3:
			raise PluginError("Object position should not be " + \
				str(len(self.position) + ' fields long.'))
		for index in self.position:
			data.extend(int(round(index)).to_bytes(2, 'big', signed = False))
		if self.rotation is not None:
			data.extend(int(round(math.degrees(self.rotation[1]))).to_bytes(2, 'big'))
			if self.bparam is not None:
				data.extend(int(self.bparam).to_bytes(2, 'big'))
		return data
	
	def to_c(self):
		if self.rotation is None:
			return 'SPECIAL_OBJECT(' + str(self.preset) + ', ' +\
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + '),\n'
		elif self.bparam is None:
			return 'SPECIAL_OBJECT_WITH_YAW(' + str(self.preset) + ', ' +\
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + '),\n'
		else:
			return 'SPECIAL_OBJECT_WITH_YAW_AND_PARAM(' + str(self.preset) + ', ' +\
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
				str(self.bparam) + '),\n'

class SM64_Mario_Start:
	def __init__(self, area, position, rotation):
		self.area = area
		self.position = position
		self.rotation = rotation
	
	def to_c(self):
		return 'MARIO_POS(' + str(self.area) + ', ' + str(int(round(self.rotation[1]))) + ', ' +\
			str(int(round(self.position[0]))) + ', ' + str(int(round(self.position[1]))) + ', ' + str(int(round(self.position[2]))) + ')'

class SM64_Area:
	def __init__(self, index, music_seq, music_preset, 
		terrain_type, geolayout, collision, warpNodes, name):
		self.name = toAlnum(name)
		self.geolayout = geolayout
		self.collision = collision
		self.index = index
		self.objects = []
		self.macros = []
		self.specials = []
		self.water_boxes = []
		self.music_preset = music_preset
		self.music_seq = music_seq
		self.terrain_type = terrain_type
		self.warpNodes = warpNodes

	def macros_name(self):
		return self.name + '_macro_objs'

	def to_c_script(self):
		data = ''
		data += '\tAREA(' + str(self.index) + ', ' + self.geolayout.name + '),\n'
		for warpNode in self.warpNodes:
			data += '\t\t' + warpNode + ',\n'
		for obj in self.objects:
			data += '\t\t' + obj.to_c() + ',\n'
		data += '\t\tTERRAIN(' + self.collision.name + '),\n'
		data += '\t\tMACRO_OBJECTS(' + self.macros_name() + '),\n'
		if self.music_seq is None:
			data += '\t\tSTOP_MUSIC(0),\n'
		else:
			data += '\t\tSET_BACKGROUND_MUSIC(' + self.music_preset + ', ' + self.music_seq + '),\n'
		data += '\t\tTERRAIN_TYPE(' + self.terrain_type + '),\n'
		data += '\tEND_AREA(),\n\n'
		return data

	def to_c_macros(self):
		data = ''
		data += 'const MacroObject ' + self.macros_name() + '[] = {\n'
		for macro in self.macros:
			data += '\t' + macro.to_c() + ',\n'
		data += '\tMACRO_OBJECT_END(),\n};\n\n'

		return data
	
	def to_c_def_macros(self):
		return 'extern const MacroObject ' + self.macros_name() + '[];\n'

class CollisionWaterBox:
	def __init__(self, waterBoxType, position, blenderSize):
		size = (blenderSize[0] * bpy.context.scene.blenderToSM64Scale, 
			blenderSize[1] * bpy.context.scene.blenderToSM64Scale)
		self.waterBoxType = waterBoxType
		self.low = (position[0] - size[0] / 2, position[2] - size[1] / 2)
		self.high = (position[0] + size[0] / 2, position[2] + size[1] / 2)
		self.height = position[1]

	def to_binary(self):
		data = bytearray([0x00, 0x00 if self.waterBoxType == 'Water' else 0x32])
		data.extend(int(round(self.low[0])).to_bytes(2, 'big', signed=True))
		data.extend(int(round(self.low[1])).to_bytes(2, 'big', signed=True))
		data.extend(int(round(self.high[0])).to_bytes(2, 'big', signed=True))
		data.extend(int(round(self.high[1])).to_bytes(2, 'big', signed=True))
		data.extend(int(round(self.height)).to_bytes(2, 'big', signed=True))
		return data
	
	def to_c(self):
		data = 'COL_WATER_BOX(' + \
			('0x00' if self.waterBoxType == 'Water' else '0x32') + ', ' + \
			str(int(round(self.low[0]))) + ', ' + \
			str(int(round(self.low[1]))) + ', ' + \
			str(int(round(self.high[0]))) + ', ' + \
			str(int(round(self.high[1]))) + ', ' + \
			str(int(round(self.height))) + '),\n'
		return data

def exportAreaCommon(levelObj, areaObj, transformMatrix, geolayout, collision, name):
	bpy.ops.object.select_all(action = 'DESELECT')
	areaObj.select_set(True)

	area = SM64_Area(areaObj.areaIndex, areaObj.music_seq if not areaObj.noMusic else None, areaObj.music_preset, 
		areaObj.terrain_type, geolayout, collision, 
		[areaObj.warpNodes[i].to_c() for i in range(len(areaObj.warpNodes))],
		name + '_' + areaObj.name)
	process_sm64_objects(levelObj, area, levelObj.matrix_world, transformMatrix, False)

	return area

def process_sm64_objects(obj, area, rootMatrix, transformMatrix, specialsOnly):
	if obj.data is None:
		if obj.sm64_obj_type == 'Area Root' and obj.areaIndex != area.index:
			return
		translation, rotation, scale = \
			(transformMatrix @ rootMatrix.inverted() @ obj.matrix_world).decompose()

		if specialsOnly:
			if obj.sm64_obj_type == 'Special':
				area.specials.append(SM64_Special_Object(obj.sm64_obj_preset, translation, 
					rotation.to_euler() if obj.sm64_obj_set_yaw else None, 
					obj.sm64_obj_bparam if (obj.sm64_obj_set_yaw and obj.sm64_obj_set_bparam) else None))
			elif obj.sm64_obj_type == 'Water Box':
				area.water_boxes.append(CollisionWaterBox(obj.waterBoxType, 
					translation, obj.waterBoxSize))
		else:
			if obj.sm64_obj_type == 'Object':
				area.objects.append(SM64_Object(obj.sm64_obj_model, translation, rotation.to_euler(), 
					obj.sm64_obj_behaviour, obj.sm64_obj_bparam, get_act_string(obj)))
			elif obj.sm64_obj_type == 'Macro':
				area.macros.append(SM64_Macro_Object(obj.sm64_obj_preset, translation, rotation.to_euler(), 
					obj.sm64_obj_bparam if obj.sm64_obj_set_bparam else None))
			elif obj.sm64_obj_type == 'Mario Start':
				area.objects.append(SM64_Mario_Start(obj.sm64_obj_mario_start_area, translation, rotation.to_euler()))
			elif obj.sm64_obj_type == 'Trajectory':
				pass
			elif obj.sm64_obj_type == 'Whirpool':
				area.objects.append(SM64_Whirpool(obj.whirlpool_index, 
					obj.whirpool_condition, obj.whirpool_strength, translation))
			

	for child in obj.children:
		process_sm64_objects(child, area, rootMatrix, transformMatrix, specialsOnly)

def get_act_string(obj):
	if obj.sm64_obj_use_act1 and obj.sm64_obj_use_act2 and obj.sm64_obj_use_act3 and \
		obj.sm64_obj_use_act4 and obj.sm64_obj_use_act5 and obj.sm64_obj_use_act6:
		return 0x1F
	else:
		data = ''
		if obj.sm64_obj_use_act1:
			data += (" | " if len(data) > 0 else '') + 'ACT_1'
		if obj.sm64_obj_use_act2:
			data += (" | " if len(data) > 0 else '') + 'ACT_2'
		if obj.sm64_obj_use_act3:
			data += (" | " if len(data) > 0 else '') + 'ACT_3'
		if obj.sm64_obj_use_act4:
			data += (" | " if len(data) > 0 else '') + 'ACT_4'
		if obj.sm64_obj_use_act5:
			data += (" | " if len(data) > 0 else '') + 'ACT_5'
		if obj.sm64_obj_use_act6:
			data += (" | " if len(data) > 0 else '') + 'ACT_6'
		return data

class SM64ObjectPanel(bpy.types.Panel):
	bl_label = "Object Inspector"
	bl_idname = "SM64_Object_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return (context.object is not None and context.object.data is None)

	def draw(self, context):
		box = self.layout.box()
		box.box().label(text = 'SM64 Object Inspector')
		obj = context.object
		prop_split(box, obj, 'sm64_obj_type', 'Object Type')
		if obj.sm64_obj_type == 'Object':
			
			prop_split(box, obj, 'sm64_obj_model', 'Model')
			box.box().label(text = 'Model IDs defined in include/model_ids.h.')
			prop_split(box, obj, 'sm64_obj_behaviour', 'Behaviour')
			behaviourLabel = box.box()
			behaviourLabel.label(text = 'Behaviours defined in include/behaviour_data.h.')
			behaviourLabel.label(text = 'Actual contents in data/behaviour_data.c.')
			prop_split(box, obj, 'sm64_obj_bparam', 'Behaviour Parameter')
			self.draw_acts(obj, box)
		elif obj.sm64_obj_type == 'Macro':
			prop_split(box, obj, 'sm64_obj_preset', 'Preset')
			box.box().label(text = 'Macro presets defined in include/macro_presets.h.')
			box.prop(obj, 'sm64_obj_set_bparam', text = 'Set Behaviour Parameter')
			if obj.sm64_obj_set_bparam:
				prop_split(box, obj, 'sm64_obj_bparam', 'Behaviour Parameter')
		elif obj.sm64_obj_type == 'Special':
			prop_split(box, obj, 'sm64_obj_preset', 'Preset')
			box.box().label(text = 'Special presets defined in include/special_presets.h.')
			box.prop(obj, 'sm64_obj_set_yaw', text = 'Set Yaw')
			if obj.sm64_obj_set_yaw:
				box.prop(obj, 'sm64_obj_set_bparam', text = 'Set Behaviour Parameter')
				if obj.sm64_obj_set_bparam:
					prop_split(box, obj, 'sm64_obj_bparam', 'Behaviour Parameter')
		elif obj.sm64_obj_type == 'Mario Start':
			prop_split(box, obj, 'sm64_obj_mario_start_area', 'Area')
		elif obj.sm64_obj_type == 'Trajectory':
			pass
		elif obj.sm64_obj_type == 'Whirlpool':
			prop_split(box, obj, 'whirpool_index', 'Index')
			prop_split(box, obj, 'whirpool_condition', 'Condition')
			prop_split(box, obj, 'whirpool_strength', 'Strength')
			pass
		elif obj.sm64_obj_type == 'Water Box':
			prop_split(box, obj, 'waterBoxType', 'Water Box Type')
			prop_split(box, obj, 'waterBoxSize', 'Water Box Size (Blender Units)')
		elif obj.sm64_obj_type == 'Level Root':
			
			if obj.useBackgroundColor:
				prop_split(box, obj, 'backgroundColor', 'Background Color')
				box.prop(obj, 'useBackgroundColor')
			else:
				#prop_split(box, obj, 'backgroundID', 'Background ID')
				prop_split(box, obj, 'background', 'Background')
				box.prop(obj, 'useBackgroundColor')
				#box.box().label(text = 'Background IDs defined in include/geo_commands.h.')
		elif obj.sm64_obj_type == 'Area Root':
			box.prop(obj, 'useDefaultScreenRect')
			if not obj.useDefaultScreenRect:
				prop_split(box, obj, 'screenPos', 'Screen Position')
				prop_split(box, obj, 'screenSize', 'Screen Size')
		
			prop_split(box, obj, 'clipPlanes', 'Clip Planes')

	def draw_acts(self, obj, layout):
		layout.label(text = 'Acts')
		acts = layout.row()
		self.draw_act(obj, acts, 1)
		self.draw_act(obj, acts, 2)
		self.draw_act(obj, acts, 3)
		self.draw_act(obj, acts, 4)
		self.draw_act(obj, acts, 5)
		self.draw_act(obj, acts, 6)

	def draw_act(self, obj, layout, value):
		layout = layout.column()
		layout.label(text = str(value))
		layout.prop(obj, 'sm64_obj_use_act' + str(value), text = '')

sm64_obj_classes = (
	SM64ObjectPanel,
)

def sm64_obj_register():
	for cls in sm64_obj_classes:
		register_class(cls)
	
	bpy.types.Object.sm64_obj_type = bpy.props.EnumProperty(
		name = 'SM64 Object Type', items = enumObjectType, default = 'None')
	
	bpy.types.Object.sm64_obj_model = bpy.props.StringProperty(
		name = 'Model')

	bpy.types.Object.sm64_obj_preset = bpy.props.StringProperty(
		name = 'Preset')

	bpy.types.Object.sm64_obj_bparam = bpy.props.StringProperty(
		name = 'Behaviour Parameter')

	bpy.types.Object.sm64_obj_behaviour = bpy.props.StringProperty(
		name = 'Behaviour')

	bpy.types.Object.sm64_obj_mario_start_area = bpy.props.StringProperty(
		name = 'Area', default = '0x01')

	bpy.types.Object.whirpool_index = bpy.props.StringProperty(
		name = 'Index', default = '0')
	bpy.types.Object.whirpool_condition = bpy.props.StringProperty(
		name = 'Condition', default = '3')
	bpy.types.Object.whirpool_strength = bpy.props.StringProperty(
		name = 'Strength', default = '-30')
	bpy.types.Object.waterBoxType = bpy.props.EnumProperty(
		name = 'Water Box Type', items = enumWaterBoxType, default = 'Water')
	bpy.types.Object.waterBoxSize = bpy.props.FloatVectorProperty(
		name = 'Water Box Size (Blender Units)', size = 2, default = (1,1), min = 0)

	bpy.types.Object.sm64_obj_use_act1 = bpy.props.BoolProperty(
		name = 'Act 1', default = True)
	bpy.types.Object.sm64_obj_use_act2 = bpy.props.BoolProperty(
		name = 'Act 2', default = True)
	bpy.types.Object.sm64_obj_use_act3 = bpy.props.BoolProperty(
		name = 'Act 3', default = True)
	bpy.types.Object.sm64_obj_use_act4 = bpy.props.BoolProperty(
		name = 'Act 4', default = True)
	bpy.types.Object.sm64_obj_use_act5 = bpy.props.BoolProperty(
		name = 'Act 5', default = True)
	bpy.types.Object.sm64_obj_use_act6 = bpy.props.BoolProperty(
		name = 'Act 6', default = True)

	bpy.types.Object.sm64_obj_set_bparam = bpy.props.BoolProperty(
		name = 'Set Behaviour Parameter', default = True)
	
	bpy.types.Object.sm64_obj_set_yaw = bpy.props.BoolProperty(
		name = 'Set Yaw', default = False)
	
	bpy.types.Object.useBackgroundColor = bpy.props.BoolProperty(
		name = 'Use Solid Color For Background', default = False)

	#bpy.types.Object.backgroundID = bpy.props.StringProperty(
	#	name = 'Background ID', default = 'BACKGROUND_OCEAN_SKY')

	bpy.types.Object.background = bpy.props.EnumProperty(
		name = 'Background', items = enumBackground, default = 'OCEAN_SKY')
	
	bpy.types.Object.backgroundColor = bpy.props.FloatVectorProperty(
		name = 'Background Color', subtype='COLOR', size = 4, 
		min = 0, max = 1, default = (0,0,0,1))

	bpy.types.Object.screenPos = bpy.props.IntVectorProperty(
		name = 'Screen Position', size = 2, default = (160, 120), 
		min = -2**15, max = 2**15 - 1)

	bpy.types.Object.screenSize = bpy.props.IntVectorProperty(
		name = 'Screen Size', size = 2, default = (160, 120), 
		min = -2**15, max = 2**15 - 1)

	bpy.types.Object.useDefaultScreenRect = bpy.props.BoolProperty(
		name = 'Use Default Screen Rect', default = True)

	bpy.types.Object.clipPlanes = bpy.props.IntVectorProperty(
		name = 'Clip Planes', size = 2, min = 0, default = (100, 30000)
	)

	bpy.types.Object.camType = bpy.props.StringProperty(
		name = 'Camera Type', default = '1')

	bpy.types.Object.envType = bpy.props.StringProperty(
		name = 'Environment Type', default = '0')

	bpy.types.Object.fov = bpy.props.FloatProperty(
		name = 'Field Of View', min = 0, max = 180, default = 45
	)

	bpy.types.Object.dynamicFOV = bpy.props.BoolProperty(
		name = 'Dynamic FOV', default = True)

def sm64_obj_unregister():
	
	del bpy.types.Object.sm64_obj_type
	del bpy.types.Object.sm64_obj_model
	del bpy.types.Object.sm64_obj_preset
	del bpy.types.Object.sm64_obj_bparam
	del bpy.types.Object.sm64_obj_behaviour

	del bpy.types.Object.whirpool_index
	del bpy.types.Object.whirpool_condition
	del bpy.types.Object.whirpool_strength

	del bpy.types.Object.waterBoxType
	del bpy.types.Object.waterBoxSize

	del bpy.types.Object.sm64_obj_use_act1
	del bpy.types.Object.sm64_obj_use_act2
	del bpy.types.Object.sm64_obj_use_act3
	del bpy.types.Object.sm64_obj_use_act4
	del bpy.types.Object.sm64_obj_use_act5
	del bpy.types.Object.sm64_obj_use_act6

	del bpy.types.Object.sm64_obj_set_bparam
	del bpy.types.Object.sm64_obj_set_yaw

	del bpy.types.Object.useBackgroundColor
	#del bpy.types.Object.backgroundID
	del bpy.types.Object.background
	del bpy.types.Object.backgroundColor
	
	del bpy.types.Object.screenPos
	del bpy.types.Object.screenSize
	del bpy.types.Object.useDefaultScreenRect
	del bpy.types.Object.clipPlanes
	del bpy.types.Object.camType
	del bpy.types.Object.envType
	del bpy.types.Object.fov
	del bpy.types.Object.dynamicFOV

	for cls in reversed(sm64_obj_classes):
		unregister_class(cls)

enumBackground = [
	('OCEAN_SKY', 'Ocean Sky', 'Ocean Sky'),
	('FLAMING_SKY', 'Flaming Sky', 'Flaming Sky'),
	('UNDERWATER_CITY', 'Underwater City', 'Underwater City'),
	('BELOW_CLOUDS', 'Below Clouds', 'Below Clouds'),
	('SNOW_MOUNTAINS', 'Snow Mountains', 'Snow Mountains'),
	('DESERT', 'Desert', 'Desert'),
	('HAUNTED', 'Haunted', 'Haunted'),
	('GREEN_SKY', 'Green Sky', 'Green Sky'),
	('ABOVE_CLOUDS', 'Above Clouds', 'Above Clouds'),
	('PURPLE_SKY', 'Purple Sky', 'Purple Sky'),
]

backgroundSegments = {
	'OCEAN_SKY' : 'water',
	'FLAMING_SKY' : 'bitfs',
	'UNDERWATER_CITY' : 'wdw',
	'BELOW_CLOUDS' : 'clouds',
	'SNOW_MOUNTAINS' : 'ccm',
	'DESERT' : 'ssl',
	'HAUNTED' : 'bbh',
	'GREEN_SKY' : 'bidw',
	'ABOVE_CLOUDS' : 'cloud_floor',
	'PURPLE_SKY' : 'bits',
}

enumWaterBoxType = [
	("Water", 'Water', "Water"),
	('Toxic Haze', 'Toxic Haze', 'Toxic Haze')
]

enumObjectType = [
	('None', 'None', 'None'),
	('Level Root', 'Level Root', 'Level Root'),
	('Area Root', 'Area Root', 'Area Root'),
	('Object', 'Object', 'Object'),
	('Macro', 'Macro', 'Macro'),
	('Special', 'Special', 'Special'),
	('Mario Start', 'Mario Start', 'Mario Start'),
	('Whirlpool', 'Whirlpool', 'Whirlpool'),
	('Water Box', 'Water Box', 'Water Box'),
	#('Trajectory', 'Trajectory', 'Trajectory'),
]

'''
object: model, bparam, behaviour, acts
macro: preset, [bparam]
special: preset, [yaw, [bparam]]
trajectory: id
'''