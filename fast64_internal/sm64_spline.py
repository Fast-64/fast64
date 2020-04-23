from .utility import *
from .sm64_constants import *
from bpy.utils import register_class, unregister_class
import bpy, bmesh

enumSplineTypes = [
	("Trajectory", "Trajectory", "Exports to Trajectory[]. Used for movement"),
	('Cutscene', 'Cutscene', 'Exports to CutsceneSplinePoint[]. Used for cutscenes'),
	('Vector', 'Vector', 'Exports to Vec4s[]. Used for the jumbo star keyframes'),
]

class SM64Spline:
	def __init__(self, name, splineType, speed):
		self.name = toAlnum(name)
		self.splineType = splineType
		self.points = []
		self.speed = speed
	
	def to_c(self):
		data = ''
		if self.splineType == 'Trajectory':
			data += 'const Trajectory ' + self.name + '[] = {\n'
			for index in range(len(self.points)):
				point = self.points[index]
				data += "\tTRAJECTORY_POS( " + str(index) \
						+ ", " + str(int(round(point[0]))) \
						+ ", " + str(int(round(point[1]))) \
						+ ", " + str(int(round(point[2]))) \
						+ "),\n"
			data += "\tTRAJECTORY_END(),\n};\n"
			return data
		elif self.splineType == 'Cutscene':
			data += 'struct CutsceneSplinePoint ' + self.name + '[] = {\n'
			for index in range(len(self.points)):
				point = self.points[index]
				if index == len(self.points) - 1:
					splineIndex = -1 # last keyframe
				else:
					splineIndex = index
				data += "\t{ " + str(splineIndex) \
						+ ", " + str(self.speed) \
						+ ", { " + str(int(round(point[0]))) \
						+ ", " + str(int(round(point[1]))) \
						+ ", " + str(int(round(point[2]))) \
						+ " }},\n"
			data += "};\n"
			return data
		elif self.splineType == 'Vector':
			data += 'const Vec4s ' + self.name + '[] = {\n'
			for index in range(len(self.points)):
				point = self.points[index]
				if index >= len(self.points) - 3:
					speed = 0 # last 3 points of spline
				else:
					speed = self.speed
				data += "\t{ " + str(speed) \
						+ ", " + str(int(round(point[0]))) \
						+ ", " + str(int(round(point[1]))) \
						+ ", " + str(int(round(point[2]))) \
						+ " },\n"
			data += "};\n"
			return data
		else:
			raise PluginError("Invalid SM64 spline type: " + self.splineType)
	
	def to_c_def(self):
		if self.splineType == 'Trajectory':
			return 'extern const Trajectory ' + self.name + '[];\n'
		elif self.splineType == 'Cutscene':
			return 'extern struct CutsceneSplinePoint ' + self.name + '[];\n'
		elif self.splineType == 'Vector':
			return 'extern const Vec4s ' + self.name + '[];\n'
		else:
			raise PluginError("Invalid SM64 spline type: " + self.splineType)

def convertSplineObject(name, obj, transform):
	sm64_spline = SM64Spline(name, obj.data.sm64_spline_type, obj.data.spline_speed)

	spline = obj.data.splines.active
	for point in spline.points:
		position = transform @ point.co
		sm64_spline.points.append(position)
	
	return sm64_spline

def onSplineTypeSet(self, context):
	if self.sm64_spline_type == 'Trajectory':
		self.splines.active.order_u = 1
	else:
		self.splines.active.order_u = 4

class SM64_ExportSpline(bpy.types.Operator):
	bl_idname = "object.sm64_export_spline"
	bl_label = "Export Spline"
	bl_options = {'REGISTER', 'UNDO'} 

	def execute(self, context):
		context.object.sm64_special_enum = self.sm64_special_enum
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.sm64_special_enum)
		return {'FINISHED'}

class SM64SplinePanel(bpy.types.Panel):
	bl_label = "Spline Inspector"
	bl_idname = "SM64_Spline_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return (context.object is not None and \
			type(context.object.data) == bpy.types.Curve)

	def draw(self, context):
		box = self.layout.box()
		box.box().label(text = 'SM64 Spline Inspector')
		curve = context.object.data
		if curve.splines[0].type != 'NURBS':
			box.label(text = 'Only NURBS curves are compatible.')
		else:
			prop_split(box, curve, 'sm64_spline_type', 'Spline Type')
			if curve.sm64_spline_type == 'Cutscene' or\
				curve.sm64_spline_type == 'Vector':
				prop_split(box, curve, 'spline_speed', "Speed")

def isCurveValid(obj):
	curve = obj.data
	return type(obj.data) == bpy.types.Curve and len(curve.splines) == 1 and curve.splines[0].type == 'NURBS'

sm64_spline_classes = (
	SM64_ExportSpline,
	SM64SplinePanel,
)

def sm64_spline_register():
	for cls in sm64_spline_classes:
		register_class(cls)

	bpy.types.Curve.sm64_spline_type = bpy.props.EnumProperty(
		name = 'Type', items = enumSplineTypes, update = onSplineTypeSet)
	
	bpy.types.Curve.spline_speed = bpy.props.IntProperty(
		name = "Speed", default = 50)

def sm64_spline_unregister():
	del bpy.types.Curve.sm64_spline_type
	del bpy.types.Curve.spline_speed

	for cls in reversed(sm64_spline_classes):
		unregister_class(cls)