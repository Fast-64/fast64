import bpy, mathutils, math, string

from .oot_utility import *
from .oot_constants import root
from bpy.utils import register_class, unregister_class
from ..utility import *
from ..f3d.f3d_material import *
from ..operators import *
from ..panels import OOT_Panel

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
		emptyObj.ootTransitionActorProperty.actor.transActorID = "ACTOR_EN_DOOR"
		
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
		setattr(entranceObj.ootActorDetailedProperties, '0000.type', '0F00')
		setattr(entranceObj.ootActorDetailedProperties, '0000.props1', '0xFF')
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
		sceneObj = bpy.context.scene.ootSceneExportObj
		if sceneObj is not None:
			indices = []
			for sceneChild in sceneObj.children:
				if sceneChild.ootEmptyType == "Room":
					indices.append(sceneChild.ootRoomHeader.roomIndex)
			nextIndex = 0
			while nextIndex in indices:
				nextIndex += 1
			roomObj.ootRoomHeader.roomIndex = nextIndex
			parentObject(sceneObj, roomObj)
		
		bpy.ops.object.select_all(action = "DESELECT")
		roomObj.select_set(True)
		context.view_layer.objects.active = roomObj
		return {"FINISHED"}

class OOT_AddCutscene(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_add_cutscene'
	bl_label = "Add Cutscene"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}
	
	def execute(self, context):
		if context.mode != "OBJECT":
			bpy.ops.object.mode_set(mode = "OBJECT")
		bpy.ops.object.select_all(action = "DESELECT")

		bpy.ops.object.empty_add(type='ARROWS', radius = 1, align='WORLD')
		csObj = context.view_layer.objects.active
		csObj.ootEmptyType = "Cutscene"
		csObj.name = "Cutscene.Something"
		
		bpy.ops.object.select_all(action = "DESELECT")
		csObj.select_set(True)
		context.view_layer.objects.active = csObj
		return {"FINISHED"}


class OOT_SyncActors(bpy.types.Operator):
	# To synchronize the panel we need to update each actor obj.ootActorDetailedProperties
	bl_idname = 'object.oot_sync_actor_ids'
	bl_label = "Sync Actors"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		sceneObj = getSceneObj(context.object)
		for roomObj in sceneObj.children:
			if roomObj.data is None and roomObj.ootEmptyType == 'Room':
				for obj in roomObj.children:
					processObj(obj)

		self.report({'INFO'}, f"Scene '{sceneObj.name}' synchronized!")
		return {"FINISHED"}

def processObj(obj):
	objType = obj.ootEmptyType
	if obj.data is None and objType == "Actor":
		print(f"Processing Actor '{obj.name}'...")
		actorID = obj.ootActorProperty.actorID
		actorProp = obj.ootActorProperty
		detailedProp = obj.ootActorDetailedProperties
		if actorID != 'Custom':
			for actorNode in root:
				if actorNode.get('ID') == actorID:
					dPKey = actorNode.get('Key')
					detailedProp.actorID = actorID
					detailedProp.actorKey = dPKey
					lenProp = getMaxElemIndex(dPKey, 'Property', None)
					lenSwitch = getMaxElemIndex(dPKey, 'Flag', 'Switch')
					lenBool = getMaxElemIndex(dPKey, 'Bool', None)
					for elem in actorNode:
						uncomputeParams(elem, actorProp, detailedProp, dPKey, lenProp, lenSwitch, lenBool)
						actorProp.paramToSave = actorProp.actorParam
		else:
			detailedProp.actorIDCustom = actorProp.actorIDCustom
			detailedProp.actorParamCustom = actorProp.actorParam
		detailedProp.isActorSynced = actorProp.isActorSynced = True

	for childObj in obj.children:
		processObj(childObj)

class OOT_OperatorsPanel(OOT_Panel):
	bl_idname = "OOT_PT_operators"
	bl_label = "OOT Tools"

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.operator(OOT_AddScene.bl_idname)
		col.operator(OOT_AddRoom.bl_idname)
		col.operator(OOT_AddWaterBox.bl_idname)
		col.operator(OOT_AddDoor.bl_idname)
		col.operator(OOT_AddCutscene.bl_idname)

oot_operator_classes = (
	OOT_AddWaterBox,
	OOT_AddDoor,
	OOT_AddScene,
	OOT_AddRoom,
	OOT_AddCutscene,
	OOT_SyncActors,
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
