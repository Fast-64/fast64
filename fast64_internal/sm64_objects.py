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
	
	def to_c(self):
		if self.rotation is None:
			return 'SPECIAL_OBJECT(' + str(self.preset) + ', ' +\
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ')'
		elif self.bparam is None:
			return 'SPECIAL_OBJECT_WITH_YAW(' + str(self.preset) + ', ' +\
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + ')'
		else:
			return 'SPECIAL_OBJECT_WITH_YAW_AND_PARAM(' + str(self.preset) + ', ' +\
				str(int(round(self.position[0]))) + ', ' + \
				str(int(round(self.position[1]))) + ', ' + \
				str(int(round(self.position[2]))) + ', ' + \
				str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
				str(int(round(self.bparam))) + ')'

class SM64_Mario_Start:
	def __init__(self, area, position, rotation):
		self.area = area
		self.position = position
		self.rotation = rotation
	
	def to_c(self):
		return 'MARIO_POS(' + str(self.area) + ', ' + str(int(round(self.rotation[1]))) + ', ' +\
			str(int(round(self.position[0]))) + ', ' + str(int(round(self.position[1]))) + ', ' + str(int(round(self.position[2]))) + ')'

class SM64_Object_List:
	def __init__(self, name):
		self.name = toAlnum(name)
		self.objects = []
		self.macros = []
		self.specials = []
		self.mario_start = None
	
	def to_c(self):
		data = ''
		if len(self.objects) > 0 or self.mario_start is not None:
			data += '// Copy paste these contents to a script.c of a level.\n'
			data += 'static const LevelScript script_' + self.name + '[] = {\n'
			for obj in self.objects:
				data += '\t' + obj.to_c() + ',\n'
			if self.mario_start is not None:
				data += '\t' + self.mario_start.to_c() + ',\n'
			data += '\tRETURN(),\n};\n\n'
		if len(self.macros) > 0:
			data += '// Copy paste these contents to a macro.inc.c of an area.\n'
			data += 'static const MacroObject ' + self.name + '_macro_objs[] = {\n'
			for macro in self.macros:
				data += '\t' + macro.to_c() + ',\n'
			data += '\tMACRO_OBJECT_END(),\n};\n\n'
		if len(self.specials) > 0:
			data += '// Copy paste these contents to a collision.inc.c of an area.\n'
			data += 'const Collision ' + self.name + '_specials[] = {\n'
			data += '\tCOL_SPECIAL_INIT(' + str(len(self.specials)) + '),\n'
			for special in self.specials:
				data += '\t' + special.to_c() + ',\n'
			data += '\tCOL_END()\n};\n\n'
		
		return data


def exportObjectsCommon(obj, transformMatrix, rotationModifier):
	bpy.ops.object.select_all(action = 'DESELECT')
	obj.select_set(True)

	objList = SM64_Object_List(obj.name)
	process_sm64_objects(obj, objList, obj.matrix_world, transformMatrix, rotationModifier)

	return objList

def process_sm64_objects(obj, objList, rootMatrix, transformMatrix, rotationModifier):
	if obj.data is None:
		translation, rotation, scale = (transformMatrix @ rootMatrix.inverted() @ obj.matrix_world).decompose()
		rotation = rotationModifier @ rotation
		if obj.sm64_obj_type == 'Object':
			objList.objects.append(SM64_Object(obj.sm64_obj_model, translation, rotation.to_euler(), 
				obj.sm64_obj_behaviour, obj.sm64_obj_bparam, get_act_string(obj)))
		elif obj.sm64_obj_type == 'Macro':
			objList.macros.append(SM64_Macro_Object(obj.sm64_obj_preset, translation, rotation.to_euler(), 
				obj.sm64_obj_bparam if obj.sm64_obj_set_bparam else None))
		elif obj.sm64_obj_type == 'Special':
			objList.specials.append(SM64_Special_Object(obj.sm64_obj_preset, translation, 
				rotation.to_euler() if obj.sm64_obj_set_yaw else None, 
				obj.sm64_obj_bparam if (obj.sm64_obj_set_yaw and obj.sm64_obj_set_bparam) else None))
		elif obj.sm64_obj_type == 'Mario Start':
			objList.mario_start = SM64_Mario_Start(obj.sm64_obj_mario_start_area, translation, rotation.to_euler())
		elif obj.sm64_obj_type == 'Trajectory':
			pass

	for child in obj.children:
		process_sm64_objects(child, objList, rootMatrix, transformMatrix, rotationModifier)

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

def exportObjectsC(obj, transformMatrix, rotationModifier, dirPath):
	dirPath = os.path.join(dirPath, toAlnum(obj.name))

	if not os.path.exists(dirPath):
		os.mkdir(dirPath)

	path = os.path.join(dirPath, 'objects.h')

	fileObj = open(path, 'w')
	objectList = exportObjectsCommon(obj, transformMatrix, rotationModifier)
	fileObj.write(objectList.to_c())
	fileObj.close()

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
			prop_split(box, obj, 'sm64_obj_behaviour', 'Behaviour')
			prop_split(box, obj, 'sm64_obj_bparam', 'Behaviour Parameter')
			self.draw_acts(obj, box)
		elif obj.sm64_obj_type == 'Macro':
			prop_split(box, obj, 'sm64_obj_preset', 'Preset')
			box.prop(obj, 'sm64_obj_set_bparam', text = 'Set Behaviour Parameter')
			if obj.sm64_obj_set_bparam:
				prop_split(box, obj, 'sm64_obj_bparam', 'Behaviour Parameter')
		elif obj.sm64_obj_type == 'Special':
			prop_split(box, obj, 'sm64_obj_preset', 'Preset')
			box.prop(obj, 'sm64_obj_set_yaw', text = 'Set Yaw')
			if obj.sm64_obj_set_yaw:
				box.prop(obj, 'sm64_obj_set_bparam', text = 'Set Behaviour Parameter')
				if obj.sm64_obj_set_bparam:
					prop_split(box, obj, 'sm64_obj_bparam', 'Behaviour Parameter')
		elif obj.sm64_obj_type == 'Mario Start':
			prop_split(box, obj, 'sm64_obj_mario_start_area', 'Area')
		elif obj.sm64_obj_type == 'Trajectory':
			pass

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
		name = 'Area')

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
		name = 'Set Behaviour Parameter')
	
	bpy.types.Object.sm64_obj_set_yaw = bpy.props.BoolProperty(
		name = 'Set Yaw', default = True)

def sm64_obj_unregister():
	
	del bpy.types.Object.sm64_obj_type
	del bpy.types.Object.sm64_obj_model
	del bpy.types.Object.sm64_obj_preset
	del bpy.types.Object.sm64_obj_bparam
	del bpy.types.Object.sm64_obj_behaviour

	del bpy.types.Object.sm64_obj_use_act1
	del bpy.types.Object.sm64_obj_use_act2
	del bpy.types.Object.sm64_obj_use_act3
	del bpy.types.Object.sm64_obj_use_act4
	del bpy.types.Object.sm64_obj_use_act5
	del bpy.types.Object.sm64_obj_use_act6

	del bpy.types.Object.sm64_obj_set_bparam
	del bpy.types.Object.sm64_obj_set_yaw

	for cls in reversed(sm64_obj_classes):
		unregister_class(cls)

enumWaterBoxType = [
	("Water", 'Water', "Water"),
	('Toxic Haze', 'Toxic Haze', 'Toxic Haze')
]

enumObjectType = [
	('None', 'None', 'None'),
	('Object', 'Object', 'Object'),
	('Macro', 'Macro', 'Macro'),
	('Special', 'Special', 'Special'),
	('Mario Start', 'Mario Start', 'Mario Start'),
	#('Trajectory', 'Trajectory', 'Trajectory'),
]

'''
object: model, bparam, behaviour, acts
macro: preset, [bparam]
special: preset, [yaw, [bparam]]
trajectory: id
'''