import bpy, mathutils, dataclasses
from typing import Literal
from re import fullmatch

from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, FloatVectorProperty, CollectionProperty
from bpy.types import Object, UILayout, Context, SpaceView3D

from ..operators import OperatorBase, SearchEnumOperatorBase

from ..utility import (
    PluginError,
    copyPropertyGroup,
    draw_and_check_tab,
    get_first_set_prop,
    multilineLabel,
    prop_split,
    upgrade_old_prop,
    exportColor,
)


@dataclasses.dataclass
class CustomCmd:
    cmd_property: "SM64_CustomCmdProperties" = dataclasses.field()
    world: mathutils.Matrix
    local: mathutils.Matrix

    name: str = ""  # for sorting

    def __post_init__(self):
        self.hasDL = False
        # to prevent issues with copy:
        self.str_cmd = self.cmd_property.str_cmd
        self.int_cmd = self.cmd_property.int_cmd
        self.arg_groups = []
        arg: "SM64_CustomCmdArgProperties"
        for arg in self.cmd_property.args:
            self.arg_groups.append(arg.to_c(self))

    def size(self):
        return 8

    def get_ptr_offsets(self):
        return []

    def to_binary(self, segmentData):
        raise PluginError("Custom commands are not supported for binary exports.")

    def to_c(self, depth=0, max_length=100):
        if len(str(self.arg_groups)) > max_length:
            seperator = ",\n" + ("\t" * (depth + 1))
            args = seperator.join(self.arg_groups)
        else:
            args = ", ".join(self.arg_groups)
        return f"{self.str_cmd}({args})"


def duplicate_name(name, existing_names, old_name: str | None = ""):
    if not name in existing_names:
        return name
    num = 0
    if old_name is not None:
        number_match = fullmatch("(.*?) \((\d+)\)$", old_name)
        if number_match is not None:  # if name already a duplicate/copy, add number
            name, num = number_match.group(1), int(number_match.group(2))
        else:
            name, num = old_name, 0
    new_name = name
    for i in range(1, len(existing_names) + 2):
        if new_name not in existing_names:  # only use name if it's unique
            return new_name
        new_name = f"{name} ({num+i:03d})"


class SM64_CustomCmdOps(OperatorBase):
    bl_idname = "scene.sm64_custom_cmd_ops"
    bl_label = ""
    bl_description = "Remove or add custom command presets"
    bl_options = {"UNDO"}

    index: IntProperty(default=-1)
    op_name: StringProperty()

    def execute_operator(self, context):
        presets = context.scene.fast64.sm64.custom_cmds
        match self.op_name:
            case "ADD":
                presets.add()
                new_preset: "SM64_CustomCmdProperties" = presets[-1]
                old_preset: "SM64_CustomCmdProperties" | None = None
                if self.index == -1:
                    if not isinstance(context.space_data, SpaceView3D):  # object area
                        old_preset = context.object.fast64.sm64.custom
                else:
                    old_preset = presets[self.index]

                if old_preset is not None:
                    copyPropertyGroup(old_preset, new_preset)
                    old_name = old_preset.name
                else:
                    old_name = None
                existing_names = {preset.name for preset in presets if preset != new_preset}
                new_preset.name = duplicate_name(new_preset.name, existing_names, old_name)
                new_preset.tab = True
                if self.index != -1:
                    presets.move(len(presets) - 1, self.index + 1)
                for area in context.screen.areas:  # HACK: redraw everything
                    area.tag_redraw()
            case "REMOVE":
                presets.remove(self.index)
            case _:
                raise NotImplementedError(f'Unimplemented internal custom command preset op "{self.op_name}"')


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
        if isinstance(context.space_data, SpaceView3D):
            return context.scene.fast64.sm64.custom_cmds[command_index].args
        return context.object.fast64.sm64.custom.args

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
        custom_cmd_preset_update(self, context)
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
                    existing_names = {arg.name for arg in args if arg != new_arg and arg.has_params}
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


def get_custom_cmd_preset(custom_cmd: "SM64_CustomCmdProperties", context: Context) -> "SM64_CustomCmdProperties":
    return context.scene.fast64.sm64.custom_cmds[int(custom_cmd.preset)]


def check_preset_hashes(obj, context):
    custom_cmd: "SM64_CustomCmdProperties" = obj.fast64.sm64.custom
    if custom_cmd.preset == "NONE":
        return
    preset_cmd = get_custom_cmd_preset(custom_cmd, context)
    if custom_cmd.saved_hash and custom_cmd.saved_hash != preset_cmd.preset_hash:
        custom_cmd.preset, custom_cmd.saved_hash = "NONE", ""


def custom_cmd_preset_update(_self, context: Context):
    if isinstance(context.space_data, SpaceView3D):
        for obj in context.scene.objects:
            check_preset_hashes(obj, context)
    elif context.object:
        check_preset_hashes(context.object, context)


def custom_cmd_change_preset(self: "SM64_CustomCmdProperties", context: Context):
    if self.preset == "NONE":
        return
    preset_cmd = get_custom_cmd_preset(self, context)
    self.saved_hash = ""
    self.from_dict(preset_cmd.to_dict("PRESET_EDIT", include_defaults=False), set_defaults=False)
    self.saved_hash = self.preset_hash


def get_custom_cmd_preset_enum(_self, context: Context):
    return [("NONE", "No Preset", "No preset selected")] + [
        (str(i), preset.name, f"{preset.name} ({preset.cmd_type})")
        for i, preset in enumerate(context.scene.fast64.sm64.custom_cmds)
    ]


class SM64_SearchCustomCmds(SearchEnumOperatorBase):
    bl_idname = "scene.sm64_search_custom_cmds"
    bl_label = "Search Custom Commands"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "preset"
    preset: EnumProperty(items=get_custom_cmd_preset_enum)

    def update_enum(self, context):
        context.object.fast64.sm64.custom.preset = self.preset


CustomCmdConf = Literal["PRESET", "PRESET_EDIT", "NO_PRESET"]  # type of configuration


class SM64_CustomCmdArgProperties(bpy.types.PropertyGroup):
    name: StringProperty(name="Argument Name", default="Example Named Arg", update=custom_cmd_preset_update)
    arg_type: EnumProperty(
        name="Argument Type",
        items=[
            ("PARAMETER", "Parameter", "Parameter"),
            ("COLOR", "Color", "Color"),
            ("", "Transforms", ""),
            ("TRANSLATION", "Translation", "Translation"),
            ("ROTATION", "Rotation", "Rotation"),
            ("SCALE", "Scale", "Scale"),
            ("MATRIX", "Matrix", "3x3 Matrix"),
        ],
        update=custom_cmd_preset_update,
    )
    relative: BoolProperty(name="Use Relative Transformation", default=True)
    color: FloatVectorProperty(
        name="Color",
        size=4,
        min=0.0,
        max=1.0,
        subtype="COLOR",
        default=(1.0, 1.0, 1.0, 1.0),
        update=custom_cmd_preset_update,
    )
    parameter: StringProperty(name="Parameter", default="0")
    rot_type: EnumProperty(
        name="Rotation",
        items=[
            ("EULER", "Euler (XYZ deg)", "Euler XYZ order, degrees"),
            ("QUATERNION", "Quaternion", "Quaternion"),
            ("AXIS_ANGLE", "Axis Angle", "Axis angle"),
        ],
        update=custom_cmd_preset_update,
    )

    @property
    def is_transform(self):
        return self.arg_type in {"MATRIX", "TRANSLATION", "ROTATION", "SCALE"}

    @property
    def has_params(self):
        return self.arg_type in {"PARAMETER", "COLOR"}

    def to_dict(self, conf_type: CustomCmdConf, owner: Object | None = None, include_defaults=True):
        data = {}
        if conf_type != "PRESET":
            if conf_type == "PRESET_EDIT":
                data["name"] = self.name
            data["arg_type"] = self.arg_type
            if self.is_transform:
                data["relative"] = self.relative
                if self.arg_type == "ROTATION":
                    data["rot_type"] = self.rot_type
        if conf_type != "PRESET_EDIT" and self.is_transform and owner is not None:
            data["matrix"] = [y for x in (owner.matrix_local if self.relative else owner.matrix_world) for y in x]
        defaults = {}
        match self.arg_type:
            case "COLOR":
                defaults["color"] = tuple(self.color)
            case "PARAMETER":
                defaults["parameter"] = self.parameter
        if defaults and include_defaults:
            data["defaults"] = defaults
        return data

    def from_dict(self, data: dict, set_defaults=False):
        self.name = data.get("name", "Example Named Arg")
        self.arg_type = data.get("arg_type", "PARAMETER")
        self.relative = data.get("relative", True)
        self.rot_type = data.get("rot_type", "EULER")
        defaults = data.get("defaults", {})
        if set_defaults:
            self.color = defaults.get("color", (1.0, 1.0, 1.0, 1.0))
            self.parameter = defaults.get("parameter", "0")

    def to_c(self, cmd: CustomCmd):
        def add_name(c: str):
            if cmd.cmd_property.preset == "NONE":
                return f"/*{self.arg_type.lower()}*/{c}"
            if self.name == "":
                return c
            return f"/*{self.name}*/{c}"

        transform = cmd.local if self.relative else cmd.world
        match self.arg_type:
            case "MATRIX":
                return add_name(",".join([str(round(y, 4)) for x in transform for y in x]))
            case "TRANSLATION":
                return add_name(",".join([str(round(x, 4)) for x in transform.to_translation()]))
            case "ROTATION":
                match self.rot_type:
                    case "EULER":
                        return add_name(",".join([str(round(x, 4)) for x in transform.to_euler("XYZ")]))
                    case "QUATERNION":
                        return add_name(",".join([str(round(x, 4)) for x in transform.to_quaternion()]))
                    case "AXIS_ANGLE":
                        axis, angle = transform.to_quaternion().to_axis_angle()
                        return add_name(
                            ",".join(
                                [
                                    str(round(x, 4))
                                    for x in (
                                        *axis,
                                        angle,
                                    )
                                ]
                            )
                        )
            case "SCALE":
                return add_name(",".join([str(round(x, 4)) for x in transform.to_scale()]))
            case "COLOR":
                return add_name(",".join([str(x) for x in exportColor(self.color)]))
            case "PARAMETER":
                return add_name(self.parameter)

    def draw_props(self, arg_row: UILayout, layout: UILayout, conf_type: CustomCmdConf = "NO_PRESET"):
        col = layout.column()
        if conf_type != "NO_PRESET":
            name_split = col.split(factor=0.5)
            if conf_type == "PRESET" and self.has_params and self.name != "":
                name_split.label(text=self.name)
            elif conf_type == "PRESET_EDIT":
                name_split.prop(self, "name", text="")
        else:
            name_split = col
        if conf_type != "PRESET":
            arg_row.prop(self, "arg_type", text="")
            if self.is_transform:
                col.prop(self, "relative")
            if self.arg_type == "ROTATION":
                prop_split(col, self, "rot_type", "Rotation Type")

        match self.arg_type:
            case "COLOR":
                name_split.prop(self, "color", text="")
            case "PARAMETER":
                name_split.prop(self, "parameter", text="")


class SM64_CustomCmdProperties(bpy.types.PropertyGroup):
    tab: BoolProperty(default=False)
    preset: EnumProperty(items=get_custom_cmd_preset_enum, update=custom_cmd_change_preset)
    name: StringProperty(name="Name", default="Custom Command", update=custom_cmd_preset_update)
    cmd_type: EnumProperty(
        name="Type",
        items=[
            ("Level", "Level", "Level script Command"),
            ("Geo", "Geo", "Geolayout Command"),
            ("Special", "Special", "Collision Command"),
        ],
        update=custom_cmd_preset_update,
    )
    str_cmd: StringProperty(name="Command", default="CUSTOM_COMMAND", update=custom_cmd_preset_update)
    int_cmd: IntProperty(name="Command", default=0, update=custom_cmd_preset_update)
    args: CollectionProperty(type=SM64_CustomCmdArgProperties)
    saved_hash: StringProperty()

    def to_dict(self, conf_type: CustomCmdConf, obj: Object | None = None, include_defaults=True):
        data = {}
        if conf_type == "PRESET_EDIT":
            data["name"] = self.name
        if conf_type != "PRESET":
            data.update({"cmd_type": self.cmd_type, "str_cmd": self.str_cmd, "int_cmd": self.int_cmd})
        data["args"] = [arg.to_dict(conf_type, obj, include_defaults) for arg in self.args]
        return data

    def from_dict(self, data: dict, set_defaults=True):
        self.name = data.get("name", "My Custom Command")
        self.cmd_type = data.get("cmd_type", "Level")
        self.str_cmd = data.get("str_cmd", "CUSTOM_COMMAND")
        self.int_cmd = data.get("int_cmd", 0)
        self.args.clear()
        for arg in data.get("args", []):
            self.args.add()
            self.args[-1].from_dict(arg, set_defaults)

    @property
    def preset_hash(self):
        return str(hash(str(self.to_dict("PRESET_EDIT", include_defaults=False).items())))

    @staticmethod
    def upgrade_object(obj: Object):
        check_preset_hashes(obj, bpy.context)
        self: SM64_CustomCmdProperties = obj.fast64.sm64.custom
        found_cmd, arg = upgrade_old_prop(self, "str_cmd", obj, "customGeoCommand"), get_first_set_prop(
            obj, "customGeoCommandArgs"
        )
        if found_cmd:
            self.cmd_type = "Geo"
        if arg is not None:
            self.args.add()
            self.args[-1].arg_type = "PARAMETER"
            self.args[-1].parameter = arg

    def get_final_cmd(self, owner: Object | None, blender_scale: float):
        base_matrices = (
            (mathutils.Matrix.Identity(4),) * 2 if owner is None else (owner.matrix_world, owner.matrix_local)
        )
        world_local: list[mathutils.Matrix] = []
        for base_matrix in base_matrices:
            loc, rot, scale = base_matrix.decompose()
            scaled_translation = loc * blender_scale
            world_local.append(
                (
                    mathutils.Matrix.Translation(scaled_translation).to_4x4()
                    @ rot.to_matrix().to_4x4()
                    @ mathutils.Matrix.Diagonal(scale).to_4x4()
                )
            )
        return CustomCmd(self, *world_local)

    def draw_props(
        self,
        layout: UILayout,
        is_binary: bool,
        owner: Object | None = None,
        conf_type: CustomCmdConf = "NO_PRESET",
        blender_scale=100.0,
        command_index=-1,
    ):
        def arg_ops(layout: UILayout, icon: str, op_name: str, index=-1):
            SM64_CustomCmdArgsOps.draw_props(
                layout, icon, "", op_name=op_name, index=index, command_index=command_index
            )

        col = layout.column()
        if self.preset != "NONE":
            conf_type = "PRESET"
        if conf_type != "PRESET_EDIT":
            preset_row = col.row()
            label_row = preset_row.row()
            label_row.alignment = "LEFT"
            label_row.label(text="Preset")
            SM64_SearchCustomCmds.draw_props(preset_row, self, "preset", "")
            SM64_CustomCmdOps.draw_props(preset_row, "PRESET_NEW", "", op_name="ADD")
        if conf_type != "PRESET":
            if conf_type == "PRESET_EDIT":
                prop_split(col, self, "name", "Preset Name")
            prop_split(col, self, "cmd_type", "Type")
            if conf_type == "PRESET_EDIT" or not is_binary:
                prop_split(col, self, "str_cmd", "Command" if conf_type == "NO_PRESET" else "C Command")
            if conf_type == "PRESET_EDIT" or is_binary:
                prop_split(col, self, "int_cmd", "Command" if conf_type == "NO_PRESET" else "Binary Command")
            col.separator()
            args_col = col.box().column()
        else:
            args_col = col.column()  # don't box the arguments in preset mode

        if conf_type != "PRESET":
            basic_ops_row = args_col.row()
            basic_ops_row.label(text=f"Arguments ({len(self.args)})")
            arg_ops(basic_ops_row, "ADD", "ADD")
            arg_ops(basic_ops_row, "TRASH", "CLEAR")
        for i, arg in enumerate(self.args):
            if conf_type == "PRESET":
                ops_row = args_col.row()
            else:
                if i != 0:
                    args_col.separator()
                ops_row = args_col.row()
                num_row = ops_row.row()
                num_row.alignment = "LEFT"
                num_row.label(text=str(i))
                arg_ops(ops_row, "ADD", "ADD", i)
                arg_ops(ops_row, "REMOVE", "REMOVE", i)
                arg_ops(ops_row, "TRIA_DOWN", "MOVE_DOWN", i)
                arg_ops(ops_row, "TRIA_UP", "MOVE_UP", i)
            arg.draw_props(ops_row, args_col, conf_type)

        multilineLabel(col.box(), self.get_final_cmd(owner, blender_scale).to_c(max_length=25).replace("\t", " " * 20))


def draw_custom_cmd_presets(sm64_props: "SM64_Properties", layout: UILayout):
    col = layout.column()
    if not draw_and_check_tab(col, sm64_props, "custom_cmds_tab", icon="SETTINGS"):
        return
    basic_op_row = col.row()
    SM64_CustomCmdOps.draw_props(basic_op_row, "ADD", "", op_name="ADD")
    preset: SM64_CustomCmdProperties
    for i, preset in enumerate(sm64_props.custom_cmds):
        op_row = col.row()
        if draw_and_check_tab(op_row, preset, "tab", preset.name):
            preset.draw_props(col, sm64_props.binary_export, conf_type="PRESET_EDIT", command_index=i)
        SM64_CustomCmdOps.draw_props(op_row, "ADD", "", op_name="ADD", index=i)
        SM64_CustomCmdOps.draw_props(op_row, "REMOVE", "", op_name="REMOVE", index=i)


sm64_custom_cmd_classes = (
    SM64_CustomCmdOps,
    SM64_CustomCmdArgsOps,
    SM64_SearchCustomCmds,
    SM64_CustomCmdArgProperties,
    SM64_CustomCmdProperties,
)


def sm64_custom_cmd_register():
    for cls in sm64_custom_cmd_classes:
        register_class(cls)


def sm64_custom_cmd_unregister():
    for cls in reversed(sm64_custom_cmd_classes):
        unregister_class(cls)
