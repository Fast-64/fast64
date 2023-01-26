import bpy, mathutils
from bpy.utils import register_class, unregister_class
from ..utility import attemptModifierApply, PluginError, raisePluginError, parentObject, selectSingleObject
from ..panels import SM64_Panel
from ..operators import AddWaterBox
from .sm64_utility import check_obj_is_room
from .sm64_geolayout_utility import createBoneGroups
from .sm64_geolayout_parser import generateMetarig


class SM64_ArmatureApplyWithMesh(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "Applies current pose as default pose. Useful for "
        + "rigging an armature that is not in T/A pose. Note that when using "
        + " with an SM64 armature, you must revert to the default pose after "
        + "skinning."
    )
    bl_idname = "object.armature_apply_w_mesh"
    bl_label = "Apply As Rest Pose"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            for child in armatureObj.children:
                if type(child.data) is not bpy.types.Mesh:
                    continue
                armatureModifier = None
                for modifier in child.modifiers:
                    if isinstance(modifier, bpy.types.ArmatureModifier):
                        armatureModifier = modifier
                if armatureModifier is None:
                    continue
                print(armatureModifier.name)
                bpy.ops.object.select_all(action="DESELECT")
                context.view_layer.objects.active = child
                bpy.ops.object.modifier_copy(modifier=armatureModifier.name)
                print(len(child.modifiers))
                attemptModifierApply(armatureModifier)

            bpy.ops.object.select_all(action="DESELECT")
            context.view_layer.objects.active = armatureObj
            bpy.ops.object.mode_set(mode="POSE")
            bpy.ops.pose.armature_apply()
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Applied armature with mesh.")
        return {"FINISHED"}  # must return a set


class AddBoneGroups(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "Add bone groups respresenting other node types in " + "SM64 geolayouts (ex. Shadow, Switch, Function)."
    )
    bl_idname = "object.add_bone_groups"
    bl_label = "Add Bone Groups"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT" and context.mode != "POSE":
                raise PluginError("Operator can only be used in object or pose mode.")
            elif context.mode == "POSE":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            createBoneGroups(armatureObj)
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created bone groups.")
        return {"FINISHED"}  # must return a set


class CreateMetarig(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "SM64 imported armatures are usually not good for "
        + "rigging. There are often intermediate bones between deform bones "
        + "and they don't usually point to their children. This operator "
        + "creates a metarig on armature layer 4 useful for IK."
    )
    bl_idname = "object.create_metarig"
    bl_label = "Create Animatable Metarig"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            generateMetarig(armatureObj)
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created metarig.")
        return {"FINISHED"}  # must return a set


class SM64_ArmatureToolsPanel(SM64_Panel):
    bl_idname = "SM64_PT_armature_tools"
    bl_label = "SM64 Armature Tools"
    goal = "Export Object/Actor/Anim"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(SM64_ArmatureApplyWithMesh.bl_idname)
        col.operator(AddBoneGroups.bl_idname)
        col.operator(CreateMetarig.bl_idname)


class SM64_AddWaterBox(AddWaterBox):
    bl_idname = "object.sm64_add_water_box"

    scale: bpy.props.FloatProperty(default=10)
    preset: bpy.props.StringProperty(default="Shaded Solid")
    matName: bpy.props.StringProperty(default="sm64_water_mat")

    def setEmptyType(self, emptyObj):
        emptyObj.sm64_obj_type = "Water Box"

class SM64_AddRoomToArea(bpy.types.Operator):
    bl_idname = "object.sm64_add_room_empty"
    bl_label = "Add Room To Area"
    bl_options = {'REGISTER', 'UNDO'}

    def add_room_to_area(
        self,
        context: bpy.types.Context,
        area_obj: bpy.types.Object,
        room_index: int,
        original_area_children: list[bpy.types.Object]
    ):
        location: mathutils.Vector = area_obj.matrix_world.translation

        bpy.ops.object.select_all(action = "DESELECT")
        bpy.ops.object.empty_add(align='WORLD', location=location[:])
        room_obj = context.view_layer.objects.active

        prefix = f"Area {area_obj.areaIndex}"
        suffix = "Room 0 (Global Room)" if room_index == 0 else f"Room {room_index}"
        room_obj.name = ' '.join([prefix, suffix])
        room_obj.sm64_obj_type = "None"
        
        # parent room object to area
        parentObject(area_obj, room_obj)

        # make sure that the original children get parented to the new room empty
        for child in original_area_children:
            parentObject(room_obj, child)

    def check_and_init_area_rooms(self, area_obj: bpy.types.Object):
        num_room_children = 0

        for child in area_obj.children:
            if check_obj_is_room(child):
                num_room_children += 1
                continue
            break

        if num_room_children == 0:
            area_obj.enableRoomSwitch = True
        return num_room_children

    def execute(self, context: bpy.types.Context):
        area_obj: bpy.types.Object = None
        try:
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            if len(context.selected_objects) == 0:
                raise PluginError("Area Root Object not selected.")
            area_obj: bpy.types.Object = context.selected_objects[0]
            if area_obj.data is not None or area_obj.sm64_obj_type != "Area Root":
                raise PluginError("The selected object is not an empty with the Area Root type.")

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        try:
            area_obj: bpy.types.Object = area_obj
            
            # if the area doesn't have rooms, the children will be transferred to the new room
            original_area_children: list[bpy.types.Object] = []
            num_room_children = self.check_and_init_area_rooms(area_obj)

            if num_room_children == 0:
                original_area_children = area_obj.children
                self.add_room_to_area(context, area_obj, 0, [])
                num_room_children += 1

            self.add_room_to_area(context, area_obj, num_room_children, original_area_children)

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}

def select_objects(objects: list[bpy.types.Object]):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)

def set_object_origin(obj: bpy.types.Object, location: mathutils.Vector):
    selectSingleObject(obj)
    
    # apply transformations first primarily for scale/rotation
    bpy.ops.object.transform_apply()

    # give 3d cursor new coordinates
    bpy.context.scene.cursor.location = location

    # set the origin on the current object to the 3d cursor location
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    
class SM64_ApplyObjectTransformsToArea(bpy.types.Operator):
    bl_idname = "object.sm64_apply_object_transforms_to_area"
    bl_label = "Apply Objects' Transforms To Area"
    bl_options = {'REGISTER', 'UNDO'}
    
    def set_object_origin(self, context: bpy.types.Context, obj: bpy.types.Object, location: mathutils.Vector):
        # give 3d cursor new coordinates
        bpy.context.scene.cursor.location = location

        selectSingleObject(obj)
        # set the origin on the current object to the 3d cursor location
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    
    def get_area_root_from_object(self, obj: bpy.types.Object):
        obj_parent = obj.parent
        while obj_parent is not None:
            if obj_parent.sm64_obj_type == "Area Root":
                return obj_parent
            obj_parent = obj_parent.parent
        return None

    def execute(self, context: bpy.types.Context):
        area_obj: bpy.types.Object = None
        # location for origin, 
        goal_objects: list[tuple[mathutils.Vector, bpy.types.Object]] = []
        
        # TODO:
        # there are many differences in what should be applied for a type of object
        #   - sm64 objects: no transformations should be applied (if they dont have children)
        #   - rooms and grouping "None" empties: ALL transformations applied, then children?
        #   - water boxes: rotation SHOULD be applied??? i think??? 
        #   
        #  SO MAYBE 
        #  - ONLY apply an empty with children if ALL children are selected 
        #  - fuck, no. agh. this wouldnt let you apply an empty and only the mesh children
        #  
        #  ACTUALLY MAYBE
        #  - operator is for applying meshes 
        #  - this applies starting from the area, down to the mesh (applying rooms in the process) 
        #  wait: is this too "smart"? like - maybe it should just act like applying does, but instead of the world origin its the area root
        #  - seems like this would be fine, though people might think the "room" they applied should move linked origins with it
        #  - mehhhhh, nah
        #  
        # what do I want when i hit this button im spending too much time on?
        #   - i want it to remove geolayout transformations
        # based on that answer, perhaps the solution should be a _kure_ to this problem
        #   - (under an area?) each object OR 'None' empty has a checkbox to apply geolayout transformations
        #   - this defaults to True!
        #   - if True:
        #       - Empty:
        #           - Duplicated empty gets applied to area root
        # 
        # WE INTERRUPT THIS PROGRAM FOR A NEW THOUGHT:
        # - should geo transforms ONLY happen with inline geolayout commands???
        # 
        # answer: YEAH
        #   - objects ALWAYS apply transforms to the highest specified "transformer"
        #       - to an inline geolayout command empty
        #       - to the area
        #       - to the exported object
        #   - you CAN force an object to inline it's transformations
        #   - mesh object Geolayout Command options:
        #   -   - Optimal (apply as stated in first bullet)
        #   -   - Billboard: apply scale and rotation, translate relative to highest transformer
        #   -   - Translate/Rotate: (yeah lmao you already know)
        

        # store the location of current 3d cursor to revert
        objects = context.selected_objects[:]
        saved_location = context.scene.cursor.location.xyz   # returns a vector
        try:
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            if len(context.selected_objects) == 0:
                raise PluginError("Object(s) not selected.")
            # aggregate area positions and objects: make sure all selected objects should succeed!
            for obj in objects:
                # if obj.data is None:
                #     raise PluginError(f"Selected object '{obj.name}' is an empty.")
                # if obj.children:
                #     raise PluginError(f"Selected object '{obj.name}' has children. All mesh objects should not have children")
                area_obj = self.get_area_root_from_object(obj)
                if area_obj is None:
                    raise PluginError(f"Selected object '{obj.name}' does not have an area root above it.")
                location: mathutils.Vector = None
                if isinstance(obj.data, bpy.types.Mesh):
                    # mesh's origin should move to the area
                    location: mathutils.Vector = area_obj.matrix_world.translation
                else:
                    # other origins should be retained, but scale should be applied
                    location: mathutils.Vector = obj.matrix_world.translation
                goal_objects.append((location, obj))

            for location, obj in goal_objects:
                self.set_object_origin(context, obj, location)

        except Exception as e:    
            # set 3d cursor location back to the stored location
            bpy.context.scene.cursor.location.xyz = saved_location
            select_objects(objects)
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        bpy.context.scene.cursor.location.xyz = saved_location
        select_objects(objects)

        return {"FINISHED"}



class SM64_LevelToolsPanel(SM64_Panel):
    bl_idname = "SM64_PT_level_tools"
    bl_label = "SM64 Level Tools"
    goal = "Export Level"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(SM64_AddRoomToArea.bl_idname)
        col.operator(SM64_AddWaterBox.bl_idname)

        col.operator(SM64_ApplyObjectTransformsToArea.bl_idname)

sm64_tool_classes = (
    SM64_ArmatureApplyWithMesh,
    AddBoneGroups,
    CreateMetarig,
    SM64_ArmatureToolsPanel,
    SM64_AddWaterBox,
    SM64_AddRoomToArea,
    SM64_ApplyObjectTransformsToArea,
    SM64_LevelToolsPanel,
)

def sm64_tools_register():
	for cls in sm64_tool_classes:
		register_class(cls)

def sm64_tools_unregister():
	for cls in sm64_tool_classes:
		unregister_class(cls)
