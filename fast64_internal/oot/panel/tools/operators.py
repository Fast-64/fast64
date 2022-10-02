from mathutils import Vector
from bpy.ops import mesh, object, curve
from bpy.types import Operator
from bpy.props import FloatProperty, StringProperty
from ....operators import AddWaterBox, addMaterialByName
from ....utility import parentObject, setOrigin


class OOT_AddWaterBox(AddWaterBox):
    bl_idname = "object.oot_add_water_box"

    scale: FloatProperty(default=10)
    preset: StringProperty(default="oot_shaded_texture_transparent")
    matName: StringProperty(default="oot_water_mat")

    def setEmptyType(self, emptyObj):
        emptyObj.ootEmptyType = "Water Box"


class OOT_AddDoor(Operator):
    # set bl_ properties
    bl_idname = "object.oot_add_door"
    bl_label = "Add Door"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    scale: FloatProperty(default=2)
    preset: StringProperty(default="oot_shaded_solid")
    matName: StringProperty(default="unused_mat")

    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        object.select_all(action="DESELECT")

        objScale = (3 * self.scale, 1 * self.scale, 5 * self.scale)

        location = Vector(context.scene.cursor.location) + Vector([0, 0, 0.5 * objScale[2]])

        mesh.primitive_cube_add(align="WORLD", location=location[:], scale=objScale)
        cubeObj = context.view_layer.objects.active
        cubeObj.ignore_render = True
        cubeObj.show_axis = True
        cubeObj.name = "Door Collision"

        addMaterialByName(cubeObj, self.matName, self.preset)

        location += Vector([0, 0, -0.5 * objScale[2]])
        object.empty_add(type="CUBE", radius=1, align="WORLD", location=location[:])
        emptyObj = context.view_layer.objects.active
        emptyObj.ootEmptyType = "Transition Actor"
        emptyObj.name = "Door Actor"
        emptyObj.ootTransitionActorProperty.actor.actorID = "ACTOR_DOOR_SHUTTER"
        emptyObj.ootTransitionActorProperty.actor.actorParam = "0x0000"

        parentObject(cubeObj, emptyObj)

        setOrigin(emptyObj, cubeObj)

        return {"FINISHED"}


class OOT_AddScene(Operator):
    # set bl_ properties
    bl_idname = "object.oot_add_scene"
    bl_label = "Add Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    scale: FloatProperty(default=30)
    preset: StringProperty(default="oot_shaded_solid")
    matName: StringProperty(default="floor_mat")

    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        object.select_all(action="DESELECT")

        location = Vector(context.scene.cursor.location)
        mesh.primitive_plane_add(size=2 * self.scale, enter_editmode=False, align="WORLD", location=location[:])
        planeObj = context.view_layer.objects.active
        planeObj.name = "Floor"
        addMaterialByName(planeObj, self.matName, self.preset)

        object.empty_add(type="CONE", radius=1, align="WORLD", location=location[:])
        entranceObj = context.view_layer.objects.active
        entranceObj.ootEmptyType = "Entrance"
        entranceObj.name = "Entrance"
        entranceObj.ootEntranceProperty.actor.actorParam = "0x0FFF"
        parentObject(planeObj, entranceObj)

        location += Vector([0, 0, 10])
        object.empty_add(type="SPHERE", radius=1, align="WORLD", location=location[:])
        roomObj = context.view_layer.objects.active
        roomObj.ootEmptyType = "Room"
        roomObj.name = "Room"
        parentObject(roomObj, planeObj)

        location += Vector([0, 0, 2])
        object.empty_add(type="SPHERE", radius=1, align="WORLD", location=location[:])
        sceneObj = context.view_layer.objects.active
        sceneObj.ootEmptyType = "Scene"
        sceneObj.name = "Scene"
        parentObject(sceneObj, roomObj)

        context.scene.ootSceneExportObj = sceneObj
        context.scene.fast64.renderSettings.ootSceneObject = sceneObj

        return {"FINISHED"}


class OOT_AddRoom(Operator):
    bl_idname = "object.oot_add_room"
    bl_label = "Add Room"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        object.select_all(action="DESELECT")

        location = Vector(context.scene.cursor.location)
        object.empty_add(type="SPHERE", radius=1, align="WORLD", location=location[:])
        roomObj = context.view_layer.objects.active
        roomObj.ootEmptyType = "Room"
        roomObj.name = "Room"
        sceneObj = context.scene.ootSceneExportObj
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

        object.select_all(action="DESELECT")
        roomObj.select_set(True)
        context.view_layer.objects.active = roomObj
        return {"FINISHED"}


class OOT_AddCutscene(Operator):
    bl_idname = "object.oot_add_cutscene"
    bl_label = "Add Cutscene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        object.select_all(action="DESELECT")

        object.empty_add(type="ARROWS", radius=1, align="WORLD")
        csObj = context.view_layer.objects.active
        csObj.ootEmptyType = "Cutscene"
        csObj.name = "Cutscene.Something"

        object.select_all(action="DESELECT")
        csObj.select_set(True)
        context.view_layer.objects.active = csObj
        return {"FINISHED"}


class OOT_AddPath(Operator):
    bl_idname = "object.oot_add_path"
    bl_label = "Add Path"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        object.select_all(action="DESELECT")

        location = Vector(context.scene.cursor.location)
        curve.primitive_nurbs_path_add(radius=1, align="WORLD", location=location[:])
        pathObj = context.view_layer.objects.active
        pathObj.name = "New Path"
        pathObj.fast64.oot.version = pathObj.fast64.oot.cur_version

        object.select_all(action="DESELECT")
        pathObj.select_set(True)
        context.view_layer.objects.active = pathObj
        return {"FINISHED"}
