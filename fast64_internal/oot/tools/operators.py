import bpy

from mathutils import Vector
from bpy.ops import mesh, object, curve
from bpy.types import Operator, Object, Context
from bpy.props import FloatProperty, StringProperty, EnumProperty, BoolProperty
from ...operators import AddWaterBox, addMaterialByName
from ...utility import parentObject, setOrigin
from ..cutscene.motion.utility import setupCutscene, createNewCameraShot
from ..oot_utility import getNewPath
from .quick_import import QuickImportAborted, quick_import_exec


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
        emptyObj.ootTransitionActorProperty.actor.params = "0x0000"

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
        entranceObj.ootEntranceProperty.actor.params = "0x0FFF"
        parentObject(planeObj, entranceObj)

        location += Vector([0, 0, 10])
        object.empty_add(type="SPHERE", radius=1, align="WORLD", location=location[:])
        roomObj = context.view_layer.objects.active
        roomObj.ootEmptyType = "Room"
        roomObj.name = "Room"
        entranceObj.ootEntranceProperty.tiedRoom = roomObj
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
    bl_options = {"REGISTER", "UNDO"}

    csName: StringProperty(name="", default="Something", description="The Cutscene's Name without `Cutscene.`")

    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        object.select_all(action="DESELECT")

        object.empty_add(type="ARROWS", radius=1, align="WORLD")
        csObj = context.view_layer.objects.active
        csObj.ootEmptyType = "Cutscene"
        csObj.name = f"Cutscene.{self.csName}"
        createNewCameraShot(csObj)
        setupCutscene(csObj)

        object.select_all(action="DESELECT")
        csObj.select_set(True)
        context.view_layer.objects.active = csObj
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Set the Cutscene's Name")
        split = layout.split(factor=0.30)
        split.label(text="Cutscene.")
        split.prop(self, "csName")


class OOT_AddPath(Operator):
    bl_idname = "object.oot_add_path"
    bl_label = "Add Path"
    bl_options = {"REGISTER", "UNDO"}

    isClosedShape: BoolProperty(name="", default=True)
    pathType: EnumProperty(
        name="",
        items=[
            ("Line", "Line", "Line"),
            ("Square", "Square", "Square"),
            ("Triangle", "Triangle", "Triangle"),
            ("Trapezium", "Trapezium", "Trapezium"),
        ],
        default="Line",
    )

    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        object.select_all(action="DESELECT")

        pathObj = getNewPath(self.pathType, self.isClosedShape)
        activeObj = context.view_layer.objects.active
        if activeObj.type == "EMPTY" and activeObj.ootEmptyType == "Scene":
            pathObj.parent = activeObj

        object.select_all(action="DESELECT")
        pathObj.select_set(True)
        context.view_layer.objects.active = pathObj
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Path Settings")
        props = [("Path Type", "pathType"), ("Closed Shape", "isClosedShape")]

        for desc, propName in props:
            split = layout.split(factor=0.30)
            split.label(text=desc)
            split.prop(self, propName)


class OOTClearTransformAndLock(Operator):
    bl_idname = "object.oot_clear_transform"
    bl_label = "Clear Transform (Scenes & Cutscenes)"
    bl_options = {"REGISTER", "UNDO"}

    def clearTransform(self, obj: Object):
        print(obj.name)
        prevSelect = obj.select_get()
        obj.select_set(True)
        object.location_clear()
        object.rotation_clear()
        object.scale_clear()
        object.origin_clear()
        if obj.type != "EMPTY":
            object.transform_apply(location=True, rotation=True, scale=True)
        obj.select_set(prevSelect)

    def execute(self, context: Context):
        try:
            for obj in bpy.data.objects:
                if obj.type == "EMPTY":
                    if obj.ootEmptyType in ["Scene", "Cutscene"]:
                        self.clearTransform(obj)
                        for childObj in obj.children_recursive:
                            self.clearTransform(childObj)
            self.report({"INFO"}, "Success!")
            return {"FINISHED"}
        except:
            return {"CANCELLED"}


class OOTQuickImport(Operator):
    bl_idname = "object.oot_quick_import"
    bl_label = "Quick Import"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = (
        "Import (almost) anything by inputting a symbol name from an object."
        " This operator automatically finds the file to import from (within objects)"
    )

    sym_name: StringProperty(
        name="Symbol name",
        description=(
            "Which symbol to import."
            " This may be a display list (e.g. gBoomerangDL), "
            "a skeleton (e.g. object_daiku_Skel_007958), "
            "an animation (with the appropriate skeleton selected, e.g. object_daiku_Anim_008164)"
        ),
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "sym_name", text="Symbol")

    def execute(self, context: Context):
        try:
            quick_import_exec(
                context,
                self.sym_name,
            )
        except QuickImportAborted as e:
            self.report({"ERROR"}, e.message)
            return {"CANCELLED"}
        return {"FINISHED"}
