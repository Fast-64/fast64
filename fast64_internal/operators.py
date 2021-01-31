import bpy, mathutils, math
from bpy.utils import register_class, unregister_class
from .utility import *
from .f3d.f3d_material import *

def addMaterialByName(obj, matName, preset):
	if matName in bpy.data.materials:
		bpy.ops.object.material_slot_add()
		obj.material_slots[0].material = bpy.data.materials[matName]
	else:
		material = createF3DMat(obj, preset = preset)
		material.name = matName

class AddWaterBox(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.add_water_box'
	bl_label = "Add Water Box"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	scale : bpy.props.FloatProperty(default = 10)
	preset : bpy.props.StringProperty(default = "Shaded Solid")
	matName : bpy.props.StringProperty(default = "water_mat")

	def setEmptyType(self, emptyObj):
		return None

	def execute(self, context):
		if context.mode != "OBJECT":
			bpy.ops.object.mode_set(mode = "OBJECT")
		
		bpy.ops.object.select_all(action = "DESELECT")

		location = mathutils.Vector(bpy.context.scene.cursor.location)
		bpy.ops.mesh.primitive_plane_add(size=2 * self.scale, enter_editmode=False, align='WORLD', location=location[:])
		planeObj = context.view_layer.objects.active
		planeObj.ignore_collision = True
		planeObj.name = "Water Box Mesh"

		addMaterialByName(planeObj, self.matName, self.preset)
		
		location += mathutils.Vector([0,0,-self.scale])
		bpy.ops.object.empty_add(type='CUBE', radius = self.scale, align='WORLD', location=location[:])
		emptyObj = context.view_layer.objects.active
		emptyObj.name = "Water Box"
		self.setEmptyType(emptyObj)

		parentObject(planeObj, emptyObj)

		return {"FINISHED"}