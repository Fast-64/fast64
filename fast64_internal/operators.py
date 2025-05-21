from cProfile import Profile
from pstats import SortKey, Stats
from typing import Optional

import bpy, mathutils
from bpy.types import Operator, Context, UILayout, EnumProperty
from bpy.utils import register_class, unregister_class

from .utility import (
    cleanupTempMeshes,
    get_mode_set_from_context_mode,
    raisePluginError,
    parentObject,
    store_original_meshes,
    store_original_mtx,
)
from .f3d.f3d_material import createF3DMat


def addMaterialByName(obj, matName, preset):
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
        bpy.ops.object.select_all(action="DESELECT")

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
