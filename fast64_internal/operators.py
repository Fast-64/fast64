from cProfile import Profile
from pstats import SortKey, Stats
from typing import TypeVar, Iterable, Optional

import bpy, mathutils
from bpy.types import Operator, Context, UILayout, EnumProperty
from bpy.utils import register_class, unregister_class
from bpy.props import IntProperty, StringProperty

from .utility import (
    cleanupTempMeshes,
    get_mode_set_from_context_mode,
    raisePluginError,
    parentObject,
    store_original_meshes,
    store_original_mtx,
    deselectAllObjects,
)
from .f3d.f3d_material import createF3DMat


def addMaterialByName(obj, matName, preset):
    from .f3d.f3d_material import createF3DMat

    if matName in bpy.data.materials:
        bpy.ops.object.material_slot_add()
        obj.material_slots[0].material = bpy.data.materials[matName]
    else:
        material = createF3DMat(obj, preset=preset)
        material.name = matName


PROFILE_ENABLED = False


class OperatorBase(Operator):
    """Base class for operators, keeps track of context mode and sets it back after running
    execute_operator() and catches exceptions for raisePluginError()"""

    context_mode: str = ""
    icon = "NONE"

    @classmethod
    def is_enabled(cls, context: Context, **op_values):
        return True

    @classmethod
    def draw_props(cls, layout: UILayout, icon="", text: Optional[str] = None, **op_values):
        """Op args are passed to the operator via setattr()"""
        icon = icon if icon else cls.icon
        layout = layout.column()
        op = layout.operator(cls.bl_idname, icon=icon, text=text)
        for key, value in op_values.items():
            setattr(op, key, value)
        layout.enabled = cls.is_enabled(bpy.context, **op_values)
        return op

    def execute_operator(self, context: Context):
        raise NotImplementedError()

    def execute(self, context: Context):
        starting_mode = context.mode
        starting_mode_set = get_mode_set_from_context_mode(starting_mode)
        starting_object = context.object
        try:
            if self.context_mode and self.context_mode != starting_mode_set:
                bpy.ops.object.mode_set(mode=self.context_mode)
            if PROFILE_ENABLED:
                with Profile() as profile:
                    self.execute_operator(context)
                    print(Stats(profile).strip_dirs().sort_stats(SortKey.CUMULATIVE).print_stats())
            else:
                self.execute_operator(context)
            return {"FINISHED"}
        except Exception as exc:
            raisePluginError(self, exc)
            return {"CANCELLED"}
        finally:
            if starting_mode != context.mode:
                if starting_mode != "OBJECT" and starting_object:
                    context.view_layer.objects.active = starting_object
                    starting_object.select_set(True)
                bpy.ops.object.mode_set(mode=starting_mode_set)


CollectionMember = TypeVar("CollectionMember")


class CollectionOperatorBase(OperatorBase):
    """
    A basic collection operator, implements basic add/remove/move/clear operations,
    but can support more by the subclass implementing the .lower equivelent of the op_name.
    See some examples in sm64/custom_cmd/operators.py
    """

    # index -1 means no index, so on an add that would mean adding at the end with no copy of the previous element
    index: IntProperty(default=-1)
    op_name: StringProperty()
    copy_on_add: bool = False
    object_name: str = "item"  # simple name to be used in descriptions

    @classmethod
    def description(cls, context: Context, properties: dict) -> str:
        op_name: str = properties.get("op_name", "")
        description = op_name.capitalize()
        index = properties.get("index", -1)
        if index != -1:
            description += f" (copy of {index})"

        object_name = cls.object_name
        if op_name == "CLEAR":
            object_name += "s"
        description += f" {object_name}"
        return description

    @classmethod
    def collection(cls, context: Context, op_values: dict) -> Iterable[CollectionMember]:
        """Abstract method for getting the collection from the context"""
        raise NotImplementedError()

    @classmethod
    def is_enabled(cls, context: Context, **op_values) -> bool:
        """Checks if the operation being drawn should be enabled in the UI, for example clear requires the collection to not be empty"""
        collection = cls.collection(context, op_values)
        op_name: str = op_values.get("op_name", "")
        match op_name:
            case "MOVE_UP":
                return op_values.get("index") > 0
            case "MOVE_DOWN":
                return op_values.get("index") < len(collection) - 1
            case "CLEAR":
                return len(collection) > 0
            case _:
                lower = op_name.lower() + "_enabled"
                if hasattr(cls, lower):
                    return getattr(cls, lower)(context, collection)
                return True

    @classmethod
    def draw_row(cls, row: UILayout, index: int, **op_values):
        """Draw add/remove/move/clear operations, clear only draws in a element-less index (-1)"""

        def draw_op(icon: str, op_name: str):
            cls.draw_props(row, icon, "", op_name=op_name, index=index, **op_values)

        draw_op("ADD", "ADD")
        if index == -1:
            draw_op("TRASH", "CLEAR")
        else:
            draw_op("REMOVE", "REMOVE")
            draw_op("TRIA_DOWN", "MOVE_DOWN")
            draw_op("TRIA_UP", "MOVE_UP")

    def add(
        self, _context: Context, collection: Iterable[CollectionMember]
    ) -> tuple[CollectionMember | None, CollectionMember]:
        """Returns the previous element and the newly created element"""
        collection.add()
        old_arg: CollectionMember | None = None
        new_arg: CollectionMember = collection[-1]
        if self.index != -1:
            collection.move(len(collection) - 1, self.index + 1)
            old_arg = collection[self.index]
            new_arg = collection[self.index + 1]
        if self.copy_on_add:
            copyPropertyGroup(old_arg, new_arg)
        return old_arg, new_arg

    def execute_operator(self, context: Context):
        collection = self.__class__.collection(context, self.properties)
        match self.op_name:
            case "ADD":
                self.add(context, collection)
            case "REMOVE":
                collection.remove(self.index)
            case "MOVE_UP":
                collection.move(self.index, self.index - 1)
            case "MOVE_DOWN":
                collection.move(self.index, self.index + 1)
            case "CLEAR":
                collection.clear()
            case _:
                lower = self.op_name.lower()
                if hasattr(self, lower):
                    getattr(self, lower)(context, collection)
                else:
                    raise NotImplementedError(f'Unimplemented internal op "{self.op_name}"')


class SearchEnumOperatorBase(OperatorBase):
    bl_description = "Search Enum"
    bl_label = "Search"
    bl_property = None
    bl_options = {"UNDO"}

    @classmethod
    def draw_props(cls, layout: UILayout, data, prop: str, name: str):
        row = layout.row()
        if name:
            row.label(text=name)
        row.prop(data, prop, text="")
        row.operator(cls.bl_idname, icon="VIEWZOOM", text="")

    def update_enum(self, context: Context):
        raise NotImplementedError()

    def execute_operator(self, context: Context):
        assert self.bl_property
        self.report({"INFO"}, f"Selected: {getattr(self, self.bl_property)}")
        self.update_enum(context)
        context.region.tag_redraw()

    def invoke(self, context: Context, _):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class AddWaterBox(OperatorBase):
    bl_idname = "object.add_water_box"
    bl_label = "Add Water Box"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "CUBE"

    scale: bpy.props.FloatProperty(default=10)
    preset: bpy.props.StringProperty(default="Shaded Solid")
    matName: bpy.props.StringProperty(default="water_mat")

    def setEmptyType(self, emptyObj):
        return None

    def execute_operator(self, context):
        deselectAllObjects()

        location = mathutils.Vector(bpy.context.scene.cursor.location)
        bpy.ops.mesh.primitive_plane_add(size=2 * self.scale, enter_editmode=False, align="WORLD", location=location[:])
        planeObj = context.view_layer.objects.active
        planeObj.ignore_collision = True
        planeObj.name = "Water Box Mesh"

        addMaterialByName(planeObj, self.matName, self.preset)

        location += mathutils.Vector([0, 0, -self.scale])
        bpy.ops.object.empty_add(type="CUBE", radius=self.scale, align="WORLD", location=location[:])
        emptyObj = context.view_layer.objects.active
        emptyObj.name = "Water Box"
        self.setEmptyType(emptyObj)

        parentObject(planeObj, emptyObj)

        self.report({"INFO"}, "Water box added.")


class WarningOperator(bpy.types.Operator):
    """Extension of Operator that allows collecting and displaying warnings"""

    warnings = set()

    def reset_warnings(self):
        self.warnings.clear()

    def add_warning(self, warning: str):
        self.warnings.add(warning)

    def show_warnings(self):
        if len(self.warnings):
            self.report({"WARNING"}, "Operator completed with warnings:")
            for warning in self.warnings:
                self.report({"WARNING"}, warning)
            self.reset_warnings()


class ObjectDataExporter(WarningOperator):
    """Operator that uses warnings and can store original matrixes and meshes for use in exporting"""

    def store_object_data(self):
        store_original_mtx()
        store_original_meshes(self.add_warning)

    def cleanup_temp_object_data(self):
        cleanupTempMeshes()
