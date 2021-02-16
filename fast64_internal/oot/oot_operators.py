import bpy, mathutils, math
from bpy.utils import register_class, unregister_class
from ..utility import *
from ..f3d.f3d_material import *
from ..operators import *

class OOT_AddWaterBox(AddWaterBox):
	bl_idname = 'object.oot_add_water_box'

	scale : bpy.props.FloatProperty(default = 10)
	preset : bpy.props.StringProperty(default = "oot_shaded_texture_transparent")
	matName : bpy.props.StringProperty(default = "oot_water_mat")
	
	def setEmptyType(self, emptyObj):
		emptyObj.ootEmptyType = "Water Box"

class OOT_AddDoor(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_add_door'
	bl_label = "Add Door"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	scale : bpy.props.FloatProperty(default = 2)
	preset : bpy.props.StringProperty(default = "oot_shaded_solid")
	matName : bpy.props.StringProperty(default = "unused_mat")

	def execute(self, context):
		if context.mode != "OBJECT":
			bpy.ops.object.mode_set(mode = "OBJECT")
		bpy.ops.object.select_all(action = "DESELECT")

		objScale = (3 * self.scale, 1 * self.scale, 5 * self.scale)

		location = mathutils.Vector(bpy.context.scene.cursor.location) +\
			mathutils.Vector([0,0, 0.5 * objScale[2]])

		bpy.ops.mesh.primitive_cube_add(align='WORLD', location=location[:], scale = objScale)
		cubeObj = context.view_layer.objects.active
		cubeObj.ignore_render = True
		cubeObj.show_axis = True
		cubeObj.name = "Door Collision"
		
		addMaterialByName(cubeObj, self.matName, self.preset)
		
		location += mathutils.Vector([0,0, - 0.5 * objScale[2]])
		bpy.ops.object.empty_add(type='CUBE', radius = 1, align='WORLD', location=location[:])
		emptyObj = context.view_layer.objects.active
		emptyObj.ootEmptyType = "Transition Actor"
		emptyObj.name = "Door Actor"
		emptyObj.ootTransitionActorProperty.actor.actorID = "ACTOR_DOOR_SHUTTER"
		emptyObj.ootTransitionActorProperty.actor.actorParam = "0x0000"
		
		parentObject(cubeObj, emptyObj)

		setOrigin(emptyObj, cubeObj)

		return {"FINISHED"}

class OOT_AddScene(bpy.types.Operator):
		# set bl_ properties
	bl_idname = 'object.oot_add_scene'
	bl_label = "Add Scene"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	scale : bpy.props.FloatProperty(default = 30)
	preset : bpy.props.StringProperty(default = "oot_shaded_solid")
	matName : bpy.props.StringProperty(default = "floor_mat")

	def execute(self, context):
		if context.mode != "OBJECT":
			bpy.ops.object.mode_set(mode = "OBJECT")
		bpy.ops.object.select_all(action = "DESELECT")

		location = mathutils.Vector(bpy.context.scene.cursor.location)
		bpy.ops.mesh.primitive_plane_add(size=2 * self.scale, enter_editmode=False, align='WORLD', location=location[:])
		planeObj = context.view_layer.objects.active
		planeObj.name = "Floor"
		addMaterialByName(planeObj, self.matName, self.preset)

		bpy.ops.object.empty_add(type='CONE', radius = 1, align='WORLD', location=location[:])
		entranceObj = context.view_layer.objects.active
		entranceObj.ootEmptyType = "Entrance"
		entranceObj.name = "Entrance"
		entranceObj.ootEntranceProperty.actor.actorParam = "0x0FFF"
		parentObject(planeObj, entranceObj)
		
		location += mathutils.Vector([0,0, 10])
		bpy.ops.object.empty_add(type='SPHERE', radius = 1, align='WORLD', location=location[:])
		roomObj = context.view_layer.objects.active
		roomObj.ootEmptyType = "Room"
		roomObj.name = "Room"
		parentObject(roomObj, planeObj)

		location += mathutils.Vector([0,0, 2])
		bpy.ops.object.empty_add(type='SPHERE', radius = 1, align='WORLD', location=location[:])
		sceneObj = context.view_layer.objects.active
		sceneObj.ootEmptyType = "Scene"
		sceneObj.name = "Scene"
		parentObject(sceneObj, roomObj)

		bpy.context.scene.ootSceneExportObj = sceneObj

		#setOrigin(emptyObj, cubeObj)

		return {"FINISHED"}

class OOT_AddRoom(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_add_room'
	bl_label = "Add Room"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		if context.mode != "OBJECT":
			bpy.ops.object.mode_set(mode = "OBJECT")
		bpy.ops.object.select_all(action = "DESELECT")

		location = mathutils.Vector(bpy.context.scene.cursor.location)
		bpy.ops.object.empty_add(type='SPHERE', radius = 1, align='WORLD', location=location[:])
		roomObj = context.view_layer.objects.active
		roomObj.ootEmptyType = "Room"
		roomObj.name = "Room"
		if bpy.context.scene.ootSceneExportObj is not None:
			sceneObj = bpy.context.scene.ootSceneExportObj
			indices = []
			for sceneChild in sceneObj.children:
				if sceneChild.ootEmptyType == "Room":
					indices.append(sceneChild.ootRoomHeader.roomIndex)
			nextIndex = 0
			while nextIndex in indices:
				nextIndex += 1
			roomObj.ootRoomHeader.roomIndex = nextIndex
			parentObject(bpy.context.scene.ootSceneExportObj, roomObj)
		
		bpy.ops.object.select_all(action = "DESELECT")
		roomObj.select_set(True)
		context.view_layer.objects.active = roomObj
		return {"FINISHED"}

class OOT_OperatorsPanel(bpy.types.Panel):
	bl_idname = "OOT_PT_operators"
	bl_label = "OOT Tools"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'OOT'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.operator(OOT_AddScene.bl_idname)
		col.operator(OOT_AddRoom.bl_idname)
		col.operator(OOT_AddWaterBox.bl_idname)
		col.operator(OOT_AddDoor.bl_idname)

oot_operator_classes = (
	OOT_AddWaterBox,
	OOT_AddDoor,
	OOT_AddScene,
	OOT_AddRoom,
)

oot_operator_panel_classes = (
	OOT_OperatorsPanel,
)

def oot_operator_panel_register():
	for cls in oot_operator_panel_classes:
		register_class(cls)

def oot_operator_panel_unregister():
	for cls in oot_operator_panel_classes:
		unregister_class(cls)

def oot_operator_register():
	for cls in oot_operator_classes:
		register_class(cls)
	

def oot_operator_unregister():
	for cls in reversed(oot_operator_classes):
		unregister_class(cls)