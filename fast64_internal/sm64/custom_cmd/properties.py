import math
import bpy
import mathutils
from typing import TYPE_CHECKING, Optional

from bpy.utils import register_class, unregister_class
from bpy.props import (
    StringProperty,
    IntProperty,
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import Object, Bone, UILayout, Context, PropertyGroup

from ...utility import (
    PluginError,
    Matrix4x4Property,
    convertRadiansToS16,
    draw_and_check_tab,
    get_first_set_prop,
    multilineLabel,
    prop_split,
    toAlnum,
    upgrade_old_prop,
    exportColor,
)
from ...f3d.f3d_material import sm64EnumDrawLayers

from .exporting import CustomCmd
from .operators import SM64_CustomCmdArgsOps, SM64_CustomCmdOps, SM64_SearchCustomCmds
from .utility import (
    AvailableOwners,
    CustomCmdConf,
    better_round,
    custom_cmd_preset_update,
    duplicate_name,
    get_custom_cmd_preset,
    get_custom_cmd_preset_enum,
    get_custom_prop,
    get_transforms,
    getDrawLayerName,
)

if TYPE_CHECKING:
    from ..settings.properties import SM64_Properties


def update_internal_number(self: "SM64_CustomNumberProperties", context: Context):
    use_limits = True
    custom, owner = get_custom_prop(context)
    if owner is None:
        return
    if custom is not None:
        use_limits = custom.preset != "NONE"
    if not math.isclose(self.floating, self.get_new_number(use_limits), rel_tol=1e-7):
        self.floating = self.get_new_number(use_limits)
    if self.integer != better_round(self.get_new_number(use_limits)):
        self.integer = better_round(self.get_new_number(use_limits))
    self.set_step_min_max(*self.step_min_max)


def update_internal_number_and_check_preset(self: "SM64_CustomCmdArgProperties", context: Context):
    update_internal_number(self, context)
    custom_cmd_preset_update(self, context)


class SM64_CustomNumberProperties(PropertyGroup):
    is_integer: BoolProperty(name="Is Integer", default=False, update=update_internal_number_and_check_preset)
    floating: FloatProperty(name="Float", default=0.0, precision=5, update=update_internal_number)
    integer: IntProperty(name="Integer", default=0, update=update_internal_number)
    floating_step: FloatProperty(name="Step", default=0.0, update=update_internal_number_and_check_preset)
    floating_min: FloatProperty(
        name="Min", default=-math.inf, min=-math.inf, max=math.inf, update=update_internal_number_and_check_preset
    )
    floating_max: FloatProperty(
        name="Max", default=math.inf, min=-math.inf, max=math.inf, update=update_internal_number_and_check_preset
    )
    integer_step: IntProperty(name="Step", default=1, update=update_internal_number_and_check_preset)
    integer_min: IntProperty(
        name="Min",
        default=-(2**31),
        min=-(2**31),
        max=(2**31) - 1,
        update=update_internal_number_and_check_preset,
    )
    integer_max: IntProperty(
        name="Max",
        default=(2**31) - 1,
        min=-(2**31),
        max=(2**31) - 1,
        update=update_internal_number_and_check_preset,
    )

    @property
    def step_min_max(self):
        if self.is_integer:
            return self.integer_step, self.integer_min, self.integer_max
        else:
            return self.floating_step, self.floating_min, self.floating_max

    def set_step_min_max(self, step: float, min_value: float, max_value: float):
        for name, value in zip(("step", "min", "max"), (step, min_value, max_value)):
            if getattr(self, f"integer_{name}") != better_round(value):
                setattr(self, f"integer_{name}", better_round(value))
            if not math.isclose(getattr(self, f"floating_{name}"), value, rel_tol=1e-7):
                setattr(self, f"floating_{name}", value)

    def get_new_number(self, skip_limits=False):
        new_value = self.integer if self.is_integer else self.floating
        if skip_limits:
            step, min_value, max_value = self.step_min_max
            if step == 0:
                new_value = max(min_value, min(new_value, max_value))
            else:
                if min_value > -math.inf:
                    new_value -= min_value  # start value from min
                step_count = new_value // step  # number of steps for the closest value
                new_value = step_count * step
                if min_value > -math.inf:
                    new_value += min_value
                new_value = max(min_value, min(new_value, max_value))
        if self.is_integer:
            return int(new_value)
        return new_value

    def to_dict(self, conf_type: CustomCmdConf = "PRESET_EDIT"):
        data = {"is_integer": self.is_integer}
        if conf_type == "PRESET_EDIT":
            if self.is_integer:
                data.update({"step": self.integer_step, "min": self.integer_min, "max": self.integer_max})
            else:
                data.update({"step": self.floating_step, "min": self.floating_min, "max": self.floating_max})
        return data, {"value": self.get_new_number()}

    def from_dict(self, data: dict, set_defaults=True):
        self.is_integer = data.get("is_integer", False)
        if set_defaults:
            value = data.get("defaults", {}).get("value", 0)
            self.floating = value
            self.integer = better_round(value)
        self.set_step_min_max(
            data.get("step", 1.0 if self.is_integer else 0), data.get("min", -math.inf), data.get("max", math.inf)
        )

    def draw_props(self, name_split: UILayout, layout: UILayout, conf_type: CustomCmdConf):
        col = layout.column()
        if conf_type != "PRESET":
            col.prop(self, "is_integer")
        name_split.prop(self, "integer" if self.is_integer else "floating", text="")
        usual_steps = {0, 1} if self.is_integer else {0}
        if conf_type != "PRESET_EDIT" and self.step_min_max[0] not in usual_steps:
            col.label(text=f"Increments of {self.step_min_max[0]}")
            col.separator(factor=0.5)
        if conf_type == "PRESET_EDIT":
            typ = "integer" if self.is_integer else "floating"
            prop_split(col, self, f"{typ}_min", "Min")
            prop_split(col, self, f"{typ}_max", "Max")
            prop_split(col, self, f"{typ}_step", "Step")


class SM64_CustomCmdArgProperties(PropertyGroup):
    name: StringProperty(name="Argument Name", default="Name", update=custom_cmd_preset_update)
    arg_type: EnumProperty(
        name="Argument Type",
        items=[
            ("PARAMETER", "Parameter", "Parameter"),
            ("BOOLEAN", "Boolean", "Boolean"),
            ("NUMBER", "Number", "Number"),
            ("COLOR", "Color", "Color"),
            ("LAYER", "Layer", "Layer"),
            ("", "Transforms", ""),
            ("TRANSLATION", "Translation", "Translation"),
            ("ROTATION", "Rotation", "Rotation"),
            ("SCALE", "Scale", "Scale"),
            ("MATRIX", "Matrix", "3x3 Matrix"),
        ],
        update=custom_cmd_preset_update,
    )
    inherit: BoolProperty(name="Inherit", description="Inherit arg from owner", default=True)
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
    boolean: BoolProperty(name="Boolean", default=True)
    number: PointerProperty(type=SM64_CustomNumberProperties)
    layer: EnumProperty(items=sm64EnumDrawLayers, default="1")
    relative: BoolProperty(name="Use Relative Transformation", default=True, update=custom_cmd_preset_update)
    convert_to_sm64: BoolProperty(name="Convert to SM64 units", default=True, update=custom_cmd_preset_update)
    rot_type: EnumProperty(
        name="Rotation",
        items=[
            ("EULER", "Euler (XYZ deg)", "Euler XYZ order, degrees"),
            ("QUATERNION", "Quaternion", "Quaternion"),
            ("AXIS_ANGLE", "Axis Angle", "Axis angle"),
        ],
        update=custom_cmd_preset_update,
    )
    translation_scale: FloatVectorProperty(name="Translation", size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")
    euler: FloatVectorProperty(name="Rotation", size=3, default=(0.0, 0.0, 0.0), subtype="EULER")
    quaternion: FloatVectorProperty(name="Quaternion", size=4, default=(1.0, 0.0, 0.0, 0.0), subtype="QUATERNION")
    axis_angle: FloatVectorProperty(name="Axis Angle", size=4, default=((1.0), 0.0, 0.0, 0.0), subtype="AXISANGLE")
    matrix: PointerProperty(type=Matrix4x4Property)

    @property
    def is_transform(self):
        return self.arg_type in {"MATRIX", "TRANSLATION", "ROTATION", "SCALE"}

    def can_inherit(self, owner: Optional[AvailableOwners]):
        """Scene still includes all, the inherented property will be defaults, like identity matrix"""
        valid_types = {"MATRIX", "TRANSLATION", "ROTATION"}
        if not isinstance(owner, Bone):
            valid_types.add("SCALE")
        if not isinstance(owner, Object) or owner.type == "MESH":
            valid_types.add("LAYER")
        return self.arg_type in valid_types

    def inherits(self, owner: Optional[AvailableOwners]):
        return self.can_inherit(owner) and self.inherit

    def shows_name(self, owner: Optional[AvailableOwners]):
        return not self.inherits(owner)

    def get_transform(self, owner: Optional[AvailableOwners], blender_scale=1.0, skip_convert=False, flatten=True):
        inherit = self.inherits(owner)
        relative, world = get_transforms(owner)
        matrix = relative if self.relative else world
        match self.arg_type:
            case "MATRIX":
                matrix = matrix if inherit else self.matrix.to_matrix()
                if self.convert_to_sm64 and not skip_convert:
                    trans, rot, scale = matrix.decompose()
                    matrix = (
                        mathutils.Matrix.Translation(trans * blender_scale).to_4x4()
                        @ rot.to_matrix().to_4x4()
                        @ mathutils.Matrix.Diagonal(scale).to_4x4()
                    )
                return (
                    [round(y, 4) for x in matrix for y in x] if flatten else [[round(y, 4) for y in x] for x in matrix]
                )
            case "TRANSLATION":
                translation = mathutils.Vector(matrix.to_translation() if inherit else self.translation_scale)
                if self.convert_to_sm64 and not skip_convert:
                    return [round(x) for x in translation * blender_scale]
                return [round(x, 4) for x in translation]
            case "ROTATION":
                match self.rot_type:
                    case "EULER":
                        rotation = matrix.to_euler("XYZ") if inherit else mathutils.Euler(self.euler)
                        if self.convert_to_sm64 and not skip_convert:
                            return [convertRadiansToS16(x) for x in rotation]
                        return [round(math.degrees(x), 4) for x in rotation]
                    case "QUATERNION":
                        rotation = matrix.to_quaternion() if inherit else mathutils.Quaternion(self.quaternion)
                        return [round(x, 4) for x in rotation]
                    case "AXIS_ANGLE":
                        axis, angle = self.axis_angle[:3], self.axis_angle[3]
                        if inherit:
                            axis, angle = matrix.to_quaternion().to_axis_angle()
                        axis, angle = [round(x, 4) for x in axis], round(math.degrees(angle), 4)
                        return (*axis, angle) if flatten else [axis, angle]
            case "SCALE":
                scale = matrix.to_scale() if inherit else self.translation_scale
                return [round(x, 4) for x in scale]

    def to_dict(self, conf_type: CustomCmdConf, owner: Optional[AvailableOwners] = None, include_defaults=True):
        data = {}
        if conf_type != "PRESET":
            if conf_type == "PRESET_EDIT":
                data["name"] = self.name
            data["arg_type"] = self.arg_type
            if self.can_inherit(owner):
                data["inherit"] = self.inherit
        defaults = {}
        match self.arg_type:
            case "NUMBER":
                number_data, number_defaults = self.number.to_dict(conf_type)
                defaults.update(number_defaults)
                data.update(number_data)
            case "COLOR":
                defaults["color"] = tuple(self.color)
            case _:
                if self.is_transform:
                    data["relative"] = self.relative
                    data["convert_to_sm64"] = (
                        self.convert_to_sm64
                        if self.arg_type in {"MATRIX", "TRANSLATION"}
                        or (self.arg_type == "ROTATION" and self.rot_type == "EULER")
                        else False
                    )
                    if self.arg_type == "ROTATION":
                        data["rot_type"] = self.rot_type
                    name = self.arg_type.lower()
                    if self.arg_type == "ROTATION":
                        name = self.rot_type.lower()
                    defaults[name] = self.get_transform(owner, skip_convert=True, flatten=False)
                elif not self.inherits(owner) or conf_type == "PRESET_EDIT":
                    defaults[self.arg_type.lower()] = getattr(self, self.arg_type.lower())
        if defaults and include_defaults:
            data["defaults"] = defaults
        return data

    def from_dict(self, data: dict, index=0, set_defaults=False):
        self.name = data.get("name", f"Arg {index}")
        self.arg_type = data.get("arg_type", "PARAMETER")
        self.inherit = data.get("inherit", True)
        self.relative = data.get("relative", True)
        self.convert_to_sm64 = data.get("convert_to_sm64", True)
        self.rot_type = data.get("rot_type", "EULER")
        if not set_defaults:
            return
        self.number.from_dict(data, set_defaults)
        defaults = data.get("defaults", {})
        self.translation_scale = defaults.get("translation", None) or defaults.get("scale", None) or [0, 0, 0]
        self.euler = [math.radians(x) for x in defaults.get("euler", [0, 0, 0])]
        self.quaternion = defaults.get("quaternion", [1, 0, 0, 0])
        axis_angle = defaults.get("axis_angle", [[0, 0, 0], 0])
        self.axis_angle = axis_angle[0] + [math.radians(axis_angle[1])]
        if "matrix" in defaults:
            self.matrix.from_matrix(defaults.get("matrix"))
        else:
            self.matrix.from_matrix(mathutils.Matrix.Identity(4))
        for prop in ["color", "parameter", "layer", "boolean"]:
            setattr(self, prop, data.get("defaults", {}).get(prop, getattr(self, prop)))

    def to_c(self, cmd: CustomCmd):
        def add_name(c: str):
            if cmd.cmd_property.preset == "NONE" and not cmd.preset_edit:
                return f"/*{self.arg_type.lower()}*/ {c}"
            if self.name == "":
                return c
            return f"/*{self.name}*/ {c}"

        match self.arg_type:
            case "COLOR":
                return add_name(", ".join([str(x) for x in exportColor(self.color)]))
            case "PARAMETER":
                return add_name(self.parameter)
            case "LAYER":
                return add_name(getDrawLayerName(self.layer))
            case "BOOLEAN":
                return add_name(str(self.boolean).upper())
            case "NUMBER":
                return add_name(str(self.number.get_new_number(cmd.cmd_property.preset != "NONE")))
            case _:
                if self.is_transform:
                    return add_name(", ".join(str(x) for x in self.get_transform(cmd.owner, cmd.blender_scale)))
                raise PluginError(f"Unknown arg type {self.arg_type}")

    def example_macro_args(
        self, cmd_prop: "SM64_CustomCmdProperties", previous_arg_names: set[str], conf_type: CustomCmdConf = "NO_PRESET"
    ):
        def add_name(args: list[str]):
            name = self.name
            if not name or (cmd_prop.preset == "NONE" and conf_type == "NO_PRESET"):
                name = self.arg_type.lower()
            name = duplicate_name(name, previous_arg_names)
            previous_arg_names.add(name)
            return ", ".join(toAlnum(name + arg).lower() for arg in args)

        if self.arg_type == "ROTATION":
            return add_name(
                {
                    "EULER": ("_x", "_y", "_z"),
                    "QUATERNION": ("_w", "_x", "_y", "_z"),
                    "AXIS_ANGLE": ("_x", "_y", "_z", "_a"),
                }[self.rot_type]
            )

        match self.arg_type:
            case "MATRIX":
                return add_name([f"_{x}_{y}" for x in range(4) for y in range(4)])
            case "TRANSLATION" | "SCALE":
                return add_name(["_x", "_y", "_z"])
            case "COLOR":
                return add_name(["_r", "_g", "_b", "_a"])
            case "PARAMETER" | "LAYER" | "BOOLEAN" | "NUMBER":
                return add_name([""])

    def draw_transforms(
        self,
        name_split: UILayout,
        inherit_info: UILayout,
        layout: UILayout,
        owner: Optional[AvailableOwners],
        conf_type: CustomCmdConf = "NO_PRESET",
    ):
        col = layout.column()
        inherit = self.inherits(owner)
        if conf_type != "PRESET":
            if inherit:
                col.prop(self, "relative")
            if self.arg_type == "ROTATION":
                prop_split(col, self, "rot_type", "Rotation Type")
            if self.arg_type in {"TRANSLATION", "MATRIX"} or (self.arg_type == "ROTATION" and self.rot_type == "EULER"):
                col.prop(self, "convert_to_sm64")
        force_scale = conf_type == "PRESET_EDIT" and self.arg_type == "SCALE"
        if inherit and force_scale:
            inherit_info.label(text="Scale inherenting not supported in bones.", icon="INFO")
        if not inherit or force_scale:
            if self.arg_type in {"TRANSLATION", "SCALE"}:
                name_split.prop(self, "translation_scale", text="")
            elif self.arg_type == "ROTATION":
                name_split.prop(self, self.rot_type.lower(), text="")
            elif self.arg_type == "MATRIX":
                self.matrix.draw_props(col)

    def draw_props(
        self,
        arg_row: UILayout,
        layout: UILayout,
        owner: Optional[AvailableOwners],
        _cmd_type: str,
        conf_type: CustomCmdConf = "NO_PRESET",
    ):
        inherit = self.inherits(owner)
        col = layout.column()
        if conf_type != "NO_PRESET":
            name_split = col.split(factor=0.5)
            if conf_type == "PRESET" and self.shows_name(owner) and self.name != "":
                name_split.label(text=self.name)
            elif conf_type == "PRESET_EDIT":
                name_split.prop(self, "name", text="")
        else:
            name_split = col
        inherit_info = col
        if conf_type != "PRESET":
            if self.can_inherit(owner):
                inherit_info = col.row()
                inherit_info.alignment = "LEFT"
                inherit_info.prop(self, "inherit")
            arg_row.prop(self, "arg_type", text="")

        match self.arg_type:
            case "NUMBER":
                self.number.draw_props(name_split, col, conf_type)
            case "LAYER":
                if inherit and conf_type == "PRESET_EDIT":
                    inherit_info.label(text="Layer inherenting not supported in object empties.", icon="INFO")
                if not inherit or conf_type == "PRESET_EDIT":
                    name_split.prop(self, "layer", text="")
            case _:
                if self.is_transform:
                    self.draw_transforms(name_split, inherit_info, col, owner, conf_type)
                else:
                    name_split.prop(self, self.arg_type.lower(), text="")


def custom_cmd_change_preset(self: "SM64_CustomCmdProperties", context: Context):
    if self.preset == "NONE":
        return
    preset_cmd = get_custom_cmd_preset(self, context)
    if preset_cmd is None:
        self.preset = "NONE"
        return
    self.saved_hash = ""
    self.from_dict(preset_cmd.to_dict("PRESET_EDIT", context.object, include_defaults=True), set_defaults=True)
    self.saved_hash = self.preset_hash


class SM64_CustomCmdProperties(PropertyGroup):
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
    str_cmd: StringProperty(name="Command", default="CUSTOM_CMD", update=custom_cmd_preset_update)
    int_cmd: IntProperty(name="Command", default=0, update=custom_cmd_preset_update)
    args: CollectionProperty(type=SM64_CustomCmdArgProperties)
    saved_hash: StringProperty()
    locked: BoolProperty(default=False)

    @property
    def preset_hash(self):
        return str(hash(str(self.to_dict("PRESET_EDIT", include_defaults=False).items())))

    def get_cmd_type(self, owner: Optional[AvailableOwners] = None):
        if isinstance(owner, Bone):
            return "Geo"
        return self.cmd_type

    def to_dict(self, conf_type: CustomCmdConf, owner: Optional[AvailableOwners] = None, include_defaults=True):
        data = {}
        if conf_type == "PRESET_EDIT":
            data["name"] = self.name
        if conf_type != "PRESET":
            data.update({"cmd_type": self.get_cmd_type(owner), "str_cmd": self.str_cmd, "int_cmd": self.int_cmd})
        data["args"] = [arg.to_dict(conf_type, owner, include_defaults) for arg in self.args]
        return data

    def from_dict(self, data: dict, set_defaults=True):  # TODO: move this out
        try:
            self.locked = True  # dont check preset hashes while setting values
            self.name = data.get("name", "My Custom Command")
            self.cmd_type = data.get("cmd_type", "Level")
            self.str_cmd = data.get("str_cmd", "CUSTOM_COMMAND")
            self.int_cmd = data.get("int_cmd", 0)
            self.args.clear()
            for i, arg in enumerate(data.get("args", [])):
                self.args.add()
                self.args[-1].from_dict(arg, i, set_defaults)
        finally:
            self.locked = False

    @staticmethod
    def upgrade_object(obj: Object):
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

    def get_final_cmd(
        self, owner: Optional[AvailableOwners], blender_scale: float, conf_type: CustomCmdConf = "NO_PRESET"
    ):
        return CustomCmd(owner, self, blender_scale, conf_type == "PRESET_EDIT")

    def example_macro_define(self, conf_type: CustomCmdConf = "NO_PRESET", max_len=100):
        macro_define = ""
        macro_define += f"// {self.name}\n"
        macro_define += f"#define {self.str_cmd} ("
        previous_arg_names = set()
        macro_args = [arg.example_macro_args(self, previous_arg_names, conf_type) for arg in self.args]
        joined_args = ", ".join(macro_args)
        if len(joined_args) > max_len:
            joined_args = ", \\\n\t\t".join(macro_args)
            macro_define += "\\\n\t\t"
        macro_define += f"{joined_args}) \\\n"
        macro_define += "\t(/* Your code goes here */)"
        return macro_define

    def draw_props(
        self,
        layout: UILayout,
        is_binary: bool,
        owner: Optional[AvailableOwners] = None,
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
            SM64_CustomCmdOps.draw_props(preset_row, "PRESET_NEW", "", op_name="ADD", index=-1)
        if conf_type != "PRESET":
            if conf_type == "PRESET_EDIT":
                prop_split(col, self, "name", "Preset Name")
            if not isinstance(owner, Bone):  # bone is always Geo
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

        arg: SM64_CustomCmdArgProperties
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
            arg.draw_props(ops_row, args_col, owner, self.cmd_type, conf_type)

        if conf_type != "PRESET":
            multilineLabel(
                col.box(),
                self.get_final_cmd(owner, blender_scale, conf_type).to_c(max_length=25).replace("\t", " " * 5),
            )
            example_macro_box = col.box().column()
            SM64_CustomCmdOps.draw_props(
                example_macro_box, "COPYDOWN", "Copy example to clipboard", op_name="COPY_EXAMPLE", index=command_index
            )
            multilineLabel(example_macro_box, self.example_macro_define(conf_type, 25).replace("\t", " " * 5))


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


classes = (
    SM64_CustomNumberProperties,
    SM64_CustomCmdArgProperties,
    SM64_CustomCmdProperties,
)


def props_register():
    for cls in classes:
        register_class(cls)


def props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
