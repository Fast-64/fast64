from typing import TYPE_CHECKING, Iterable

from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, IntProperty, EnumProperty
from bpy.types import Context, Scene

from ...operators import OperatorBase, CollectionOperatorBase, SearchEnumOperatorBase
from ...utility import PluginError

from .utility import custom_cmd_preset_update, duplicate_name, get_custom_cmd_preset_enum, get_custom_prop

if TYPE_CHECKING:
    from .properties import SM64_CustomCmdProperties, SM64_CustomArgProperties, SM64_CustomEnumProperties


def get_conf_type(context: Context):
    custom = get_custom_prop(context).custom
    return "PRESET_EDIT" if custom is None or custom.preset != "NONE" else "NO_PRESET"


class SM64_CustomCmdOps(OperatorBase):
    bl_idname = "scene.sm64_custom_cmd_ops"
    bl_label = ""
    bl_description = "Remove or add custom command presets"
    bl_options = {"UNDO"}

    index: IntProperty(default=-1)
    op_name: StringProperty()
    example_name: StringProperty(default="")

    def execute_operator(self, context):
        presets = context.scene.fast64.sm64.custom_cmds
        custom, owner = get_custom_prop(context)
        conf_type = get_conf_type(context)
        match self.op_name:
            case "ADD":
                presets.add()
                new_preset: "SM64_CustomCmdProperties" = presets[-1]
                old_preset: "SM64_CustomCmdProperties" | None = None
                if self.index == -1:
                    if custom is not None:
                        old_preset = custom
                else:
                    old_preset = presets[self.index]

                if old_preset is not None:
                    new_preset.from_dict(old_preset.to_dict(conf_type, owner, include_defaults=True), set_defaults=True)
                    old_name = old_preset.name
                else:
                    old_name = None
                existing_names = {preset.name for preset in presets if preset != new_preset}
                new_preset.name = duplicate_name(new_preset.name, existing_names, old_name)
                new_preset.tab = True
                if self.index != -1:
                    presets.move(len(presets) - 1, self.index + 1)
                if custom is not None:
                    custom.preset = new_preset.name
                for area in context.screen.areas:  # HACK: redraw everything
                    area.tag_redraw()
            case "REMOVE":
                presets.remove(self.index)
            case "COPY_EXAMPLE":
                preset = presets[self.index] if custom is None else custom
                context.window_manager.clipboard = preset.get_examples(owner, conf_type)[self.example_name][1]
            case _:
                raise NotImplementedError(f'Unimplemented internal custom command preset op "{self.op_name}"')
        custom_cmd_preset_update(self, context)


class SM64_CustomArgsOps(CollectionOperatorBase):
    bl_idname = "scene.sm64_custom_args_ops"
    bl_label = ""
    bl_description = "Remove or add args to a custom command"
    bl_options = {"UNDO"}

    command_index: IntProperty(default=0)  # for scene command presets

    @classmethod
    def collection(cls, context: Context, op_values: dict) -> Iterable["SM64_CustomArgProperties"]:
        owner = get_custom_prop(context).owner
        if isinstance(owner, Scene):
            return context.scene.fast64.sm64.custom_cmds[op_values.get("command_index", 0)].args
        elif owner is not None:
            return owner.fast64.sm64.custom.args
        else:
            raise PluginError("Invalid context")

    def add(self, context: Context, collection: Iterable["SM64_CustomArgProperties"]):
        old, new = super().add(context, collection)
        old_name = None
        if old is not None:
            old_name = old.name
            new.from_dict(
                old.to_dict(get_conf_type(context), owner=get_custom_prop(context).owner, include_defaults=True),
                set_defaults=True,
            )
        existing_names = {arg.name for arg in collection if arg != new}
        new.name = duplicate_name(new.name, existing_names, old_name)

    def execute_operator(self, context: Context):
        super().execute_operator(context)
        custom_cmd_preset_update(self, context)


class SM64_CustomEnumOps(SM64_CustomArgsOps):
    bl_idname = "scene.sm64_custom_enum_ops"
    bl_description = "Remove or add enum options to a custom arg"

    arg_index: IntProperty(default=0)

    @classmethod
    def collection(cls, context: Context, op_values: dict) -> Iterable["SM64_CustomEnumProperties"]:
        args = super().collection(context, op_values)
        return args[op_values.get("arg_index", 0)].enum_options

    def add(self, context: Context, collection: Iterable["SM64_CustomArgProperties"]):
        old, new = CollectionOperatorBase.add(self, context, collection)
        old_name = None
        if old is not None:
            old_name = old.name
            new.from_dict(old.to_dict())
        existing_names = {enum.name for enum in collection if enum != new}
        new.name = duplicate_name(new.name, existing_names, old_name)


class SM64_SearchCustomCmds(SearchEnumOperatorBase):
    bl_idname = "scene.sm64_search_custom_cmds"
    bl_label = "Search Custom Commands"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "preset"
    preset: EnumProperty(items=get_custom_cmd_preset_enum)

    def update_enum(self, context):
        context.object.fast64.sm64.custom.preset = self.preset


classes = (
    SM64_CustomEnumOps,
    SM64_CustomCmdOps,
    SM64_CustomArgsOps,
    SM64_SearchCustomCmds,
)


def operators_register():
    for cls in classes:
        register_class(cls)


def operators_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
