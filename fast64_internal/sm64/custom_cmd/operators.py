from typing import TYPE_CHECKING

from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, IntProperty, EnumProperty
from bpy.types import Context, Scene

from ...operators import OperatorBase, SearchEnumOperatorBase
from ...utility import copyPropertyGroup

from .utility import custom_cmd_preset_update, duplicate_name, get_custom_cmd_preset_enum, get_custom_prop

if TYPE_CHECKING:
    from .properties import SM64_CustomCmdProperties, SM64_CustomCmdArgProperties


class SM64_CustomCmdOps(OperatorBase):
    bl_idname = "scene.sm64_custom_cmd_ops"
    bl_label = ""
    bl_description = "Remove or add custom command presets"
    bl_options = {"UNDO"}

    index: IntProperty(default=-1)
    op_name: StringProperty()

    def execute_operator(self, context):
        presets = context.scene.fast64.sm64.custom_cmds
        custom, owner = get_custom_prop(context)
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
                    new_preset.from_dict(
                        old_preset.to_dict(
                            "PRESET_EDIT" if custom is None or custom.preset != "NONE" else "NO_PRESET",
                            owner,
                            include_defaults=True,
                        ),
                        set_defaults=True,
                    )
                    old_name = old_preset.name
                else:
                    old_name = None
                existing_names = {preset.name for preset in presets if preset != new_preset}
                new_preset.name = duplicate_name(new_preset.name, existing_names, old_name)
                new_preset.tab = True
                if self.index != -1:
                    presets.move(len(presets) - 1, self.index + 1)
                if custom is not None:
                    custom.preset = str((len(presets) - 1) if self.index == -1 else self.index)
                for area in context.screen.areas:  # HACK: redraw everything
                    area.tag_redraw()
            case "REMOVE":
                presets.remove(self.index)
            case "COPY_EXAMPLE":
                preset = presets[self.index] if custom is None else custom
                context.window_manager.clipboard = preset.example_macro_define(
                    "PRESET_EDIT" if custom is None else "NO_PRESET"
                )
            case _:
                raise NotImplementedError(f'Unimplemented internal custom command preset op "{self.op_name}"')
        custom_cmd_preset_update(self, context)


class SM64_CustomCmdArgsOps(OperatorBase):
    bl_idname = "scene.sm64_custom_cmd_args_ops"
    bl_label = ""
    bl_description = "Remove or add args to a custom command"
    bl_options = {"UNDO"}

    index: IntProperty(default=-1)
    command_index: IntProperty(default=0)  # for scene command presets
    op_name: StringProperty()

    @staticmethod
    def args(context, command_index) -> "SM64_CustomCmdProperties":
        owner = get_custom_prop(context).owner
        if isinstance(owner, Scene):
            return context.scene.fast64.sm64.custom_cmds[command_index].args
        elif owner is not None:
            return owner.fast64.sm64.custom.args

    @classmethod
    def is_enabled(cls, context: Context, **op_values):
        args = cls.args(context, op_values.get("command_index", 0))
        match op_values.get("op_name"):
            case "MOVE_UP":
                return op_values.get("index") > 0
            case "MOVE_DOWN":
                return op_values.get("index") < len(args) - 1
            case "CLEAR":
                return len(args) > 0
            case _:
                return True

    def execute_operator(self, context):
        args = self.args(context, self.command_index)
        match self.op_name:
            case "ADD":
                args.add()
                new_arg: "SM64_CustomCmdArgProperties" = args[-1]
                if self.index != -1:
                    old_arg: "SM64_CustomCmdArgProperties" = args[self.index]
                    copyPropertyGroup(old_arg, new_arg)
                    old_name = old_arg.name
                else:
                    old_name = None
                if old_name:
                    existing_names = {arg.name for arg in args[:-1]}
                    new_arg.name = duplicate_name(new_arg.name, existing_names, old_name)
                if self.index != -1:
                    args.move(len(args) - 1, self.index + 1)
            case "REMOVE":
                args.remove(self.index)
            case "MOVE_UP":
                args.move(self.index, self.index - 1)
            case "MOVE_DOWN":
                args.move(self.index, self.index + 1)
            case "CLEAR":
                args.clear()
            case _:
                raise NotImplementedError(f'Unimplemented internal custom command args op "{self.op_name}"')
        custom_cmd_preset_update(self, context)


class SM64_SearchCustomCmds(SearchEnumOperatorBase):
    bl_idname = "scene.sm64_search_custom_cmds"
    bl_label = "Search Custom Commands"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "preset"
    preset: EnumProperty(items=get_custom_cmd_preset_enum)

    def update_enum(self, context):
        context.object.fast64.sm64.custom.preset = self.preset


classes = (
    SM64_CustomCmdOps,
    SM64_CustomCmdArgsOps,
    SM64_SearchCustomCmds,
)


def operators_register():
    for cls in classes:
        register_class(cls)


def operators_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
