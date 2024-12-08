import copy

import bpy
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, BoolProperty
from bpy.types import Context, Object, Material, UILayout

from ...operators import OperatorBase
from ...utility import PluginError

from .converter import obj_to_f3d, obj_to_bsdf

converter_enum = [("Object", "Selected Objects", "Object"), ("Scene", "Scene", "Scene"), ("All", "All", "All")]
RECOGNISED_GAMEMODES = ["SM64", "OOT", "MK64"]


def draw_generic_converter_props(owner, layout: UILayout, direction: str, context: Context):
    if direction == "":
        layout.prop(owner, "converter_type")
        layout.prop(owner, "backup")
    if direction == "BSDF":
        layout.prop(owner, "put_alpha_into_color")
    elif direction == "F3D":
        recognised_gamemode = context.scene.gameEditorMode in RECOGNISED_GAMEMODES
        if recognised_gamemode:
            layout.prop(owner, "use_recommended")
        if not owner.use_recommended or not recognised_gamemode:
            layout.prop(owner, "lights_for_colors")
            layout.prop(owner, "default_to_fog")
            layout.prop(owner, "set_rendermode_without_fog")


class F3D_ConvertBSDF(OperatorBase):
    bl_idname = "scene.f3d_convert_to_bsdf"
    bl_label = "BSDF Converter (F3D To BSDF or BSDF To F3D)"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    icon = "MATERIAL"

    # we store these in the operator itself for user presets!
    direction: EnumProperty(items=[("F3D", "BSDF To F3D", "F3D"), ("BSDF", "F3D To BSDF", "BSDF")], name="Direction")
    converter_type: EnumProperty(items=converter_enum, name="Type")
    backup: BoolProperty(default=True, name="Backup")
    put_alpha_into_color: BoolProperty(default=False, name="Put Alpha Into Color")
    use_recommended: BoolProperty(default=True, name="Use Recommended For Current Gamemode")
    lights_for_colors: BoolProperty(default=False, name="Lights For Colors")
    default_to_fog: BoolProperty(default=False, name="Default To Fog")
    set_rendermode_without_fog: BoolProperty(default=False, name="Set RenderMode Even Without Fog")

    def draw(self, context: Context):
        layout = self.layout.column()
        layout.prop(self, "direction")
        draw_generic_converter_props(self, layout, self.direction, context)

    def execute_operator(self, context: Context):
        collection = context.scene.collection
        view_layer = context.view_layer
        scene = context.scene

        def exclude_non_mesh(objs: list[Object]) -> list[Object]:
            return [obj for obj in objs if obj.type == "MESH"]

        if self.converter_type == "Object":
            objs = exclude_non_mesh(context.selected_objects)
            if not objs:
                raise PluginError("No objects selected to convert.")
        elif self.converter_type == "Scene":
            objs = exclude_non_mesh(scene.objects)
            if not objs:
                raise PluginError("No objects in current scene to convert.")
        elif self.converter_type == "All":
            objs = exclude_non_mesh(bpy.data.objects)
            if not objs:
                raise PluginError("No objects in current file to convert.")

        if self.use_recommended and scene.gameEditorMode in RECOGNISED_GAMEMODES:
            game_mode: str = scene.gameEditorMode
            lights_for_colors = game_mode == "SM64"
            default_to_fog = game_mode != "SM64"
            set_rendermode_without_fog = default_to_fog
        else:
            lights_for_colors, default_to_fog, set_rendermode_without_fog = (
                self.lights_for_colors,
                self.default_to_fog,
                self.set_rendermode_without_fog,
            )
        original_names = [obj.name for obj in objs]
        new_objs: list[Object] = []
        backup_collection = None

        try:
            materials: dict[Material, Material] = {}
            converted_something = False
            for old_obj in objs:  # make copies and convert them
                obj = old_obj.copy()
                obj.data = old_obj.data.copy()
                scene.collection.objects.link(obj)
                view_layer.objects.active = obj
                new_objs.append(obj)
                if self.direction == "F3D":
                    converted_something |= obj_to_f3d(
                        obj, materials, lights_for_colors, default_to_fog, set_rendermode_without_fog
                    )
                elif self.direction == "BSDF":
                    converted_something |= obj_to_bsdf(obj, materials, self.put_alpha_into_color)
            if not converted_something:  # nothing converted
                raise PluginError("No materials to convert.")

            bpy.ops.object.select_all(action="DESELECT")
            if self.backup:
                name = "BSDF -> F3D Backup" if self.direction == "F3D" else "F3D -> BSDF Backup"
                if name in bpy.data.collections:
                    backup_collection = bpy.data.collections[name]
                else:
                    backup_collection = bpy.data.collections.new(name)
                    scene.collection.children.link(backup_collection)

            for old_obj, obj, name in zip(objs, new_objs, original_names):
                for collection in copy.copy(old_obj.users_collection):
                    collection.objects.unlink(old_obj)  # remove old object from current collection
                view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.make_single_user(type="SELECTED_OBJECTS")
                obj.select_set(False)

                obj.name = name
                if self.backup:
                    old_obj.name = f"{name}_backup"
                    backup_collection.objects.link(old_obj)
                    view_layer.objects.active = old_obj
                else:
                    bpy.data.objects.remove(old_obj)
            if self.backup:
                for layer_collection in view_layer.layer_collection.children:
                    if layer_collection.collection == backup_collection:
                        layer_collection.exclude = True
        except Exception as exc:
            for obj in new_objs:
                bpy.data.objects.remove(obj)
            if backup_collection is not None:
                bpy.data.collections.remove(backup_collection)
            raise exc
        self.report({"INFO"}, "Done.")


classes = (F3D_ConvertBSDF,)


def bsdf_converter_ops_register():
    for cls in classes:
        register_class(cls)


def bsdf_converter_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
