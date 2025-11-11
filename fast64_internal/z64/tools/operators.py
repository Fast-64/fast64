import bpy

from mathutils import Vector
from bpy.ops import mesh, object
from bpy.types import Operator, Object, Context
from bpy.props import FloatProperty, StringProperty, EnumProperty, BoolProperty

from ...operators import AddWaterBox, addMaterialByName
from ...utility import parentObject, setOrigin, get_new_empty_object
from ..cutscene.motion.utility import setupCutscene, createNewCameraShot
from ..utility import getNewPath
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
        emptyObj.ootTransitionActorProperty.actor.actor_id = "ACTOR_DOOR_SHUTTER"
        emptyObj.ootTransitionActorProperty.actor.params = "0x0000"

        parentObject(cubeObj, emptyObj)

        setOrigin(cubeObj, emptyObj.location)

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

        location = Vector()
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

        object.camera_add(align="WORLD", location=Vector(), rotation=Vector())
        camera_obj = context.view_layer.objects.active
        camera_obj.name = f"{sceneObj.name} Camera"
        camera_props = camera_obj.ootCameraPositionProperty
        camera_props.camSType = "CAM_SET_NORMAL0"
        camera_props.hasPositionData = False
        parentObject(sceneObj, camera_obj)

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


class Z64_AddAnimatedMaterial(Operator):
    bl_idname = "object.z64_add_animated_material"
    bl_label = "Add Animated Materials"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Create a new Animated Material empty object."

    add_test_color: BoolProperty(default=False)
    obj_name: StringProperty(default="Scene Animated Materials")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "obj_name", text="Name")
        self.layout.prop(self, "add_test_color", text="Add Color Non-linear Interpolation Example")

    def execute(self, context: Context):
        scene_obj: Object = context.scene.ootSceneExportObj
        new_obj = get_new_empty_object(self.obj_name, parent=scene_obj)
        new_obj.ootEmptyType = "Animated Materials"

        if self.add_test_color:
            am_props = new_obj.fast64.oot.animated_materials
            new_am = am_props.items.add()
            new_am_item = new_am.entries.add()
            new_am_item.type = "color_nonlinear_interp"
            new_am_item.color_params.keyframe_length = 60

            keyframe_1 = new_am_item.color_params.keyframes.add()
            keyframe_1.frame_num = 0
            keyframe_1.prim_lod_frac = 128

            keyframe_2 = new_am_item.color_params.keyframes.add()
            keyframe_2.frame_num = 5
            keyframe_2.prim_lod_frac = 128

            keyframe_3 = new_am_item.color_params.keyframes.add()
            keyframe_3.frame_num = 30
            keyframe_3.prim_lod_frac = 128
            keyframe_3.prim_color = (1.0, 0.18, 0.0, 1.0)  # FF7600

            keyframe_4 = new_am_item.color_params.keyframes.add()
            keyframe_4.frame_num = 55
            keyframe_4.prim_lod_frac = 128

            keyframe_5 = new_am_item.color_params.keyframes.add()
            keyframe_5.frame_num = 59
            keyframe_5.prim_lod_frac = 128

        return {"FINISHED"}
