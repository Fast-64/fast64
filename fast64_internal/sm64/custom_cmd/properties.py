import math
from typing import TYPE_CHECKING, Optional
from io import StringIO
import mathutils

from bpy.utils import register_class, unregister_class
from bpy.props import (
    StringProperty,
    IntProperty,
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntVectorProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import Object, Bone, UILayout, Context, PropertyGroup

from ...utility import (
    Matrix4x4Property,
    PluginError,
    draw_and_check_tab,
    get_first_set_prop,
    multilineLabel,
    prop_split,
    toAlnum,
    upgrade_old_prop,
)
from ...f3d.f3d_material import sm64EnumDrawLayers

from ..sm64_constants import MIN_S32, MAX_S32

from .exporting import CustomCmd
from .operators import SM64_CustomArgsOps, SM64_CustomCmdOps, SM64_CustomEnumOps, SM64_SearchCustomCmds
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


def update_internal_number_and_check_preset(self: "SM64_CustomArgProperties", context: Context):
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
        default=MIN_S32,
        min=MIN_S32,
        max=MAX_S32,
        update=update_internal_number_and_check_preset,
    )
    integer_max: IntProperty(
        name="Max",
        default=MAX_S32,
        min=MIN_S32,
        max=MAX_S32,
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

    def from_dict(self, data: dict, defaults: dict, set_defaults=True):
        self.is_integer = data.get("is_integer", False)
        if set_defaults:
            value = defaults.get("value", 0)
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


class SM64_CustomEnumProperties(PropertyGroup):
    name: StringProperty(name="Name", default="Enum Name", update=custom_cmd_preset_update)
    description: StringProperty(name="Description", default="Description", update=custom_cmd_preset_update)
    str_value: StringProperty(name="Value", default="ENUM_NAME", update=custom_cmd_preset_update)
    int_value: IntProperty(name="Value", default=0, update=custom_cmd_preset_update)

    def enum_tuple(self, i: int):
        return (str(i), self.name, self.description.replace("\\n", "\n"))

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description.replace("\\n", "\n"),
            "str_value": self.str_value,
            "int_value": self.int_value,
        }

    def from_dict(self, data: dict):
        self.name, self.description = data.get("name", "Name"), data.get("description", "Description")
        self.str_value, self.int_value = data.get("str_value", "ENUM_NAME"), data.get("int_value", 0)

    def draw_props(self, layout: UILayout, op_row: UILayout, is_binary=False):
        op_row.prop(self, "name", text="")
        layout.prop(self, "description")
        prop_split(layout, self, "int_value" if is_binary else "str_value", "Value")


def can_have_mesh(owner: Optional[AvailableOwners]):
    return (isinstance(owner, Object) and owner.type == "MESH") or isinstance(owner, Bone) or owner is None


class SM64_CustomArgProperties(PropertyGroup):
    name: StringProperty(name="Name", default="Argument Name", update=custom_cmd_preset_update)
    arg_type: EnumProperty(
        name="Type",
        items=[
            ("PARAMETER", "Parameter", "Parameter"),
            ("BOOLEAN", "Boolean", "Boolean"),
            ("NUMBER", "Number", "Number"),
            ("COLOR", "Color", "Color"),
            ("ENUM", "Enum", "Enum"),
            ("", "Transforms", ""),
            ("TRANSLATION", "Translation", "Translation"),
            ("ROTATION", "Rotation", "Rotation"),
            ("SCALE", "Scale", "Scale"),
            ("MATRIX", "Matrix", "3x3 Matrix"),
            ("", "", ""),
            ("LAYER", "Layer", "Layer"),
            ("DL", "Displaylist", "Displaylist"),
        ],
        update=custom_cmd_preset_update,
    )
    inherit: BoolProperty(
        name="Inherit", description="Inherit arg from owner", default=True, update=custom_cmd_preset_update
    )
    apply_scale: BoolProperty(name="Blender to SM64 Scale", default=True, update=custom_cmd_preset_update)
    round_to_sm64: BoolProperty(name="Round to Conventional Units", update=custom_cmd_preset_update)
    seg_addr: BoolProperty(name="Encode To Segmented Address", default=True, update=custom_cmd_preset_update)
    value_type: EnumProperty(
        items=[
            ("AUTO", "Auto Type", "Auto"),
            ("", "", ""),
            ("CHAR", "Char", "Char"),
            ("SHORT", "Short", "Short"),
            ("INT", "Int", "Int"),
            ("LONG", "Long", "Long"),
            ("", "", ""),
            ("FLOAT", "Float", "Float"),
            ("DOUBLE", "Double", "Double"),
        ],
        default="AUTO",
    )
    signed: BoolProperty(name="Signed", default=True)

    color: FloatVectorProperty(
        name="Color",
        size=4,
        min=0.0,
        max=1.0,
        subtype="COLOR",
        default=(1.0, 1.0, 1.0, 1.0),
        update=custom_cmd_preset_update,
    )
    color_bits: IntVectorProperty(
        name="Color Bits",
        description="Bits per channel. RGBA",
        size=4,
        default=(5, 5, 5, 1),
        min=0,
        max=8,
        update=custom_cmd_preset_update,
    )
    parameter: StringProperty(name="Parameter", default="0")
    boolean: BoolProperty(name="Boolean", default=True)
    number: PointerProperty(type=SM64_CustomNumberProperties)
    layer: EnumProperty(items=sm64EnumDrawLayers, default="1")
    relative: BoolProperty(name="Use Relative Transformation", default=True, update=custom_cmd_preset_update)
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
    dl: StringProperty(name="Displaylist", default="breakable_box_seg8_dl_cork_box")

    enum_tab: BoolProperty(name="Enum Options", default=False)
    enum_options: CollectionProperty(type=SM64_CustomEnumProperties, name="Options")
    enum_option: EnumProperty(
        name="Enum Option",
        items=lambda self, _context: [e.enum_tuple(i) for i, e in enumerate(self.enum_options)]
        or [("0", "Invalid", "Invalid")],
    )

    eval_expression: StringProperty(
        name="Eval Expression",
        default="",
        description="Apply a limited math expression to the values of this argument group, as seen in scale nodes.\nLeave empty to skip this step",
        update=custom_cmd_preset_update,
    )

    @property
    def is_transform(self):
        return self.arg_type in {"MATRIX", "TRANSLATION", "ROTATION", "SCALE"}

    @property
    def modifable_value_type(self):
        return self.arg_type not in {"LAYER", "DL"}

    @property
    def can_be_signed(self):
        return self.modifable_value_type and self.value_type not in {"FLOAT", "DOUBLE", "AUTO"}

    @property
    def can_round_to_sm64(self):
        return self.arg_type in {"TRANSLATION", "COLOR"} or (self.arg_type == "ROTATION" and self.rot_type == "EULER")

    def show_eval_expression(self, custom_cmd: "SM64_CustomCmdProperties", is_binary: bool):
        if is_binary:
            return True
        if custom_cmd.skips_eval(is_binary):
            return False
        return self.arg_type not in {"PARAMETER", "BOOLEAN", "ENUM", "LAYER", "DL"}

    def can_inherit(self, owner: Optional[AvailableOwners]):
        """Scene still includes all, the inherented property will be defaults, like identity matrix"""
        valid_types = {"MATRIX", "TRANSLATION", "ROTATION"}
        is_mesh = isinstance(owner, Object) and owner.type == "MESH"
        if not isinstance(owner, Bone):
            valid_types.add("SCALE")
        if is_mesh or owner is None:
            valid_types.add("LAYER")
        if can_have_mesh(owner):
            valid_types.add("DL")
        return self.arg_type in valid_types

    def inherits(self, owner: Optional[AvailableOwners]):
        return self.can_inherit(owner) and self.inherit

    def inherits_without_default(self, owner: Optional[AvailableOwners]):
        """Inherits without a default, layers for example inherit but have a default in case of no geometry"""
        return self.inherits(owner) and self.arg_type not in {"LAYER"}

    def modifable_inherit(self, owner: Optional[AvailableOwners]):
        """Can be modified in presets, inherit becomes a default value therefor ignored by the hashing"""
        return self.can_inherit(owner) and self.arg_type in {"DL"}

    def show_inherit_toggle(self, owner: Optional[AvailableOwners], conf_type: CustomCmdConf):
        return (self.can_inherit(owner) and conf_type != "PRESET") or self.modifable_inherit(owner)

    def show_segmented_toggle(self, owner: Optional[AvailableOwners], conf_type: CustomCmdConf):
        return (
            conf_type != "PRESET"
            and ((not self.inherits(owner) or conf_type == "PRESET_EDIT") and self.arg_type in {"DL"})
            or (self.arg_type in {"PARAMETER"} and self.value_type in {"INT", "LONG"} and not self.signed)
        )

    def shows_name(self, owner: Optional[AvailableOwners]):
        return not self.inherits_without_default(owner) or self.show_inherit_toggle(owner, "PRESET")

    def will_draw(self, owner: Optional[AvailableOwners], conf_type: CustomCmdConf):
        return self.shows_name(owner) or conf_type != "PRESET"

    def get_transform(self, owner: Optional[AvailableOwners], blender_scale=1.0):
        inherit = self.inherits(owner)
        if inherit:
            relative, world = get_transforms(owner)
            matrix = relative if self.relative else world
        if not self.apply_scale:
            blender_scale = 1.0
        match self.arg_type:
            case "MATRIX":
                matrix = matrix if inherit else self.matrix.to_matrix()
                if blender_scale != 1.0:
                    trans, rot, scale = matrix.decompose()
                    matrix = (
                        mathutils.Matrix.Translation(trans * blender_scale).to_4x4()
                        @ rot.to_matrix().to_4x4()
                        @ mathutils.Matrix.Diagonal(scale).to_4x4()
                    )
                return tuple(tuple(y for y in x) for x in matrix)
            case "TRANSLATION":
                return tuple(
                    mathutils.Vector(matrix.to_translation() if inherit else self.translation_scale) * blender_scale
                )
            case "ROTATION":
                match self.rot_type:
                    case "EULER":
                        rotation = matrix.to_euler("XYZ") if inherit else mathutils.Euler(self.euler)
                        return tuple(math.degrees(x) for x in rotation)
                    case "QUATERNION":
                        return tuple(matrix.to_quaternion() if inherit else self.quaternion)
                    case "AXIS_ANGLE":
                        axis, angle = self.axis_angle[:3], self.axis_angle[3]
                        if inherit:
                            axis, angle = matrix.to_quaternion().to_axis_angle()
                        return tuple((tuple(axis), math.degrees(angle)))
            case "SCALE":
                return tuple(matrix.to_scale() if inherit else self.translation_scale)

    def to_dict(
        self,
        conf_type: CustomCmdConf,
        owner: Optional[AvailableOwners] = None,
        blender_scale=1.0,
        include_defaults=True,
        is_export=False,
    ):
        data = {}
        defaults = {}
        if conf_type != "PRESET" or is_export:
            if conf_type != "NO_PRESET":
                data["name"] = self.name
            data["arg_type"] = self.arg_type
            if self.modifable_inherit(owner):
                defaults["inherit"] = self.inherit
            elif self.can_inherit(owner):
                data["inherit"] = self.inherit
            if self.eval_expression:
                data["eval_expression"] = self.eval_expression
        if self.modifable_value_type and self.value_type != "AUTO":
            data["value_type"] = self.value_type
            if self.can_be_signed:
                data["signed"] = self.signed
        if self.show_segmented_toggle(owner, conf_type):
            data["seg_addr"] = self.seg_addr
        if self.can_round_to_sm64:
            data["round_to_sm64"] = self.round_to_sm64
        match self.arg_type:
            case "NUMBER":
                number_data, number_defaults = self.number.to_dict(conf_type)
                defaults.update(number_defaults)
                data.update(number_data)
            case "ENUM":
                defaults["enum"] = int(self.enum_option)
                data["enum_options"] = tuple(option.to_dict() for option in self.enum_options)
            case "COLOR":
                defaults["color"] = tuple(self.color)
                if self.round_to_sm64:
                    data["color_bits"] = tuple(self.color_bits)
            case _:
                name = self.arg_type.lower()
                if self.is_transform:
                    data["relative"] = self.relative
                    data["apply_scale"] = self.apply_scale and self.arg_type in {"MATRIX", "TRANSLATION"}
                    if self.arg_type == "ROTATION":
                        data["rot_type"] = self.rot_type
                    if self.arg_type == "ROTATION":
                        name = self.rot_type.lower()
                    defaults[name] = self.get_transform(owner, blender_scale=blender_scale)
                elif (not self.inherits_without_default(owner) or conf_type == "PRESET_EDIT") and hasattr(self, name):
                    defaults[name] = getattr(self, name)
        if defaults and include_defaults:
            if conf_type == "PRESET_EDIT" and not is_export:
                data["defaults"] = defaults
            else:
                data.update(defaults)
        return data

    def from_dict(self, data: dict, index=0, set_defaults=False):
        self.name = data.get("name", f"Arg {index}")
        self.arg_type = data.get("arg_type", "PARAMETER")
        self.inherit = data.get("inherit", True)
        self.eval_expression = data.get("eval_expression", "")
        self.value_type = data.get("value_type", "AUTO")
        self.signed = data.get("signed", True)
        self.seg_addr = data.get("seg_addr", True)
        self.relative = data.get("relative", True)
        self.apply_scale = data.get("apply_scale", True)
        self.round_to_sm64 = data.get("round_to_sm64", False)
        self.rot_type = data.get("rot_type", "EULER")
        self.enum_options.clear()
        for option in data.get("enum_options", []):
            self.enum_options.add()
            self.enum_options[-1].from_dict(option)
        self.color_bits = data.get("color_bits", (8, 8, 8, 8))
        if not set_defaults:
            return
        defaults = data.get("defaults")
        if not defaults:
            defaults = data
        self.number.from_dict(data, defaults, set_defaults)
        self.enum_option = str(defaults.get("enum", 0))
        self.translation_scale = defaults.get("translation", None) or defaults.get("scale", None) or [0, 0, 0]
        self.euler = [math.radians(x) for x in defaults.get("euler", [0, 0, 0])]
        self.quaternion = defaults.get("quaternion", [1, 0, 0, 0])
        axis_angle = defaults.get("axis_angle", [[0, 0, 0], 0])
        self.axis_angle = (*axis_angle[0], math.radians(axis_angle[1]))
        if "matrix" in defaults:
            self.matrix.from_matrix(defaults.get("matrix"))
        else:
            self.matrix.from_matrix(mathutils.Matrix.Identity(4))
        for prop in ["color", "parameter", "layer", "boolean", "dl"]:
            setattr(self, prop, defaults.get(prop, getattr(self, prop)))

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
                if self.round_to_sm64:
                    return add_name([""])
                return add_name(["_r", "_g", "_b", "_a"])
            case "PARAMETER" | "LAYER" | "BOOLEAN" | "NUMBER" | "DL" | "ENUM":
                return add_name([""])
            case _:
                raise PluginError(f"Unknown arg type {self.arg_type}")

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
            if self.arg_type in {"TRANSLATION", "MATRIX"}:
                col.prop(self, "apply_scale")
        force_scale = conf_type == "PRESET_EDIT" and self.arg_type == "SCALE"
        if inherit and force_scale:
            inherit_info.label(text="Not supported in bones.", icon="INFO")
        if not inherit or force_scale:
            if self.arg_type in {"TRANSLATION", "SCALE"}:
                name_split.prop(self, "translation_scale", text="")
            elif self.arg_type == "ROTATION":
                name_split.prop(self, self.rot_type.lower(), text="")
            elif self.arg_type == "MATRIX":
                self.matrix.draw_props(col)

    def draw_enum(
        self,
        name_split: UILayout,
        layout: UILayout,
        command_index: int,
        arg_index: int,
        conf_type: CustomCmdConf = "NO_PRESET",
        is_binary=False,
    ):
        name_split.prop(self, "enum_option", text="")
        if conf_type == "PRESET":
            return
        col = layout.column()
        options_box = col.box().column()
        if not draw_and_check_tab(options_box, self, "enum_tab"):
            return
        SM64_CustomEnumOps.draw_row(options_box.row(), -1, command_index=command_index, arg_index=-arg_index)
        option: SM64_CustomEnumProperties
        for i, option in enumerate(self.enum_options):
            op_row = options_box.row()
            option.draw_props(options_box, op_row, is_binary)
            SM64_CustomEnumOps.draw_row(op_row, i, command_index=command_index, arg_index=arg_index)

    def draw_props(
        self,
        arg_row: UILayout,
        layout: UILayout,
        owner: Optional[AvailableOwners],
        custom_cmd: "SM64_CustomCmdProperties",
        command_index: int,
        arg_index: int,
        conf_type: CustomCmdConf = "NO_PRESET",
        is_binary=False,
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

        if conf_type != "PRESET":
            arg_row.prop(self, "arg_type", text="")
            if self.can_round_to_sm64:
                col.prop(self, "round_to_sm64")

        inherit_info = col
        if self.show_inherit_toggle(owner, conf_type):
            if conf_type == "PRESET":
                inherit_info = name_split
                name_split = col
            inherit_info = inherit_info.row()
            inherit_info.alignment = "LEFT"
            inherit_info.prop(self, "inherit")

        match self.arg_type:
            case "NUMBER":
                self.number.draw_props(name_split, col, conf_type)
            case "ENUM":
                self.draw_enum(name_split, col, command_index, arg_index, conf_type, is_binary)
            case "LAYER" | "DL":
                if inherit and conf_type == "PRESET_EDIT":
                    inherit_info.label(text="Not supported in object empties.", icon="INFO")
                if not inherit or conf_type == "PRESET_EDIT":
                    name_split.prop(self, self.arg_type.lower(), text="")
            case "COLOR":
                name_split.prop(self, "color", text="")
                quantize_split = col.row()
                if self.round_to_sm64:
                    quantize_split.prop(self, "color_bits", text="")
            case _:
                if self.is_transform:
                    self.draw_transforms(name_split, inherit_info, col, owner, conf_type)
                elif hasattr(self, self.arg_type.lower()):
                    name_split.prop(self, self.arg_type.lower(), text="")

        if conf_type != "PRESET":
            if self.show_eval_expression(custom_cmd, is_binary):
                prop_split(col, self, "eval_expression", "Expression")
            if is_binary:
                if self.modifable_value_type:
                    type_split = col.row()
                    type_split.prop(self, "value_type", text="")
                    if self.can_be_signed:
                        type_split.prop(self, "signed")
                if self.show_segmented_toggle(owner, conf_type):
                    col.prop(self, "seg_addr")


def custom_cmd_change_preset(self: "SM64_CustomCmdProperties", context: Context):
    if self.preset == "NONE":
        return
    preset_cmd = get_custom_cmd_preset(self, context)
    if preset_cmd is None:
        self.preset = "NONE"
        return
    self.saved_hash = ""
    self.from_dict(
        preset_cmd.to_dict("PRESET_EDIT", get_custom_prop(context).owner, include_defaults=True), set_defaults=True
    )
    self.saved_hash = self.preset_hash
    custom_cmd_preset_update(self, context)


class SM64_CustomCmdProperties(PropertyGroup):
    version: IntProperty(name="SM64_CustomCmdProperties Version", default=0)

    tab: BoolProperty(default=False)
    preset: EnumProperty(items=get_custom_cmd_preset_enum, update=custom_cmd_change_preset)
    name: StringProperty(name="Name", default="Custom Command Name", update=custom_cmd_preset_update)
    cmd_type: EnumProperty(
        name="Type",
        items=[
            ("Level", "Level", "Level script Command"),
            ("Geo", "Geo", "Geolayout Command"),
            ("Collision", "Collision", "Collision Command"),
        ],
        update=custom_cmd_preset_update,
    )
    str_cmd: StringProperty(name="Command", default="CUSTOM_CMD", update=custom_cmd_preset_update)
    int_cmd: IntProperty(name="Command", default=0, update=custom_cmd_preset_update)
    skip_eval: BoolProperty(
        name="Skip Eval",
        description="Skip evaluating values outside binary",
        default=True,
        update=custom_cmd_preset_update,
    )

    # Geo
    children_requirements: EnumProperty(
        name="Children Requirements",
        items=[
            ("ANY", "None", "No requirements"),
            ("", "", ""),
            ("MUST", "Must Have Children", "Must have at least one child node"),
            ("NONE", "No Children", "Must have no children nodeS"),
        ],
        update=custom_cmd_preset_update,
    )
    group_children: BoolProperty(
        name="Group Children",
        description="Use GEO_OPEN/CLOSE_NODE to group the node's children",
        default=True,
        update=custom_cmd_preset_update,
    )
    dl_option: EnumProperty(
        name="DL Option",
        items=[
            ("NONE", "None", "No geometry will be inherited, deform will be off in bones"),
            (
                "OPTIONAL",
                "Optional",
                "Can inherit geometry, or will use a NULL value, also allows the use of dl ext commands like GEO_TRANSLATE/GEO_TRANSLATE_WITH_DL",
            ),
            ("REQUIRED", "Required", "Must inherit geometry, otherwise an error will occur"),
        ],
        default="OPTIONAL",
        update=custom_cmd_preset_update,
    )
    use_dl_cmd: BoolProperty(
        name="Displaylist Command",
        description="Add a displaylist arg at the end of the command if there is geometry. In c, use this macro, in binary OR the first layer with 0x80",
        update=custom_cmd_preset_update,
    )
    dl_command: StringProperty(
        name="Displaylist Command", default="GEO_CUSTOM_CMD_WITH_DL", update=custom_cmd_preset_update
    )
    is_animated: BoolProperty(name="Is Animated", update=custom_cmd_preset_update)

    args_tab: BoolProperty(default=True)
    args: CollectionProperty(type=SM64_CustomArgProperties)
    examples_tab: BoolProperty(default=False)

    saved_hash: StringProperty()
    locked: BoolProperty()

    @property
    def preset_hash(self):
        return str(hash(str(self.to_dict("PRESET_EDIT", include_defaults=False).items())))

    def upgrade_object(self, obj: Object):
        if self.version != 0:
            return
        found_cmd, arg = upgrade_old_prop(self, "str_cmd", obj, "customGeoCommand"), get_first_set_prop(
            obj, "customGeoCommandArgs"
        )
        if found_cmd:
            self.cmd_type = "Geo"
        if arg is not None:
            self.args.add()
            self.args[-1].arg_type = "PARAMETER"
            self.args[-1].parameter = arg

    def upgrade_bone(self, bone: Bone):
        if self.version != 0:
            return
        upgrade_old_prop(self, "str_cmd", self, "custom_geo_cmd_macro")
        args = get_first_set_prop(self, "custom_geo_cmd_args")
        if args is not None:
            self.args.clear()
            self.args.add()
            self.args[-1].arg_type = "PARAMETER"
            self.args[0].parameter = args
        old_cmd = bone.get("geo_cmd")
        if old_cmd is not None:
            if old_cmd in {15, 16}:  # custom animated / custom non-animated
                bone.geo_cmd = "Custom"
            if old_cmd == 15:
                self.is_animated = True
        self.version = 1

    def get_cmd_type(self, owner: Optional[AvailableOwners] = None):
        if isinstance(owner, Bone):
            return "Geo"
        return self.cmd_type

    def skips_eval(self, is_binary: bool):
        if is_binary:
            return False
        return self.skip_eval

    def can_animate(self, owner: Optional[AvailableOwners] = None):
        return self.get_cmd_type(owner) == "Geo" and isinstance(owner, Bone)

    def can_have_mesh(self, owner: Optional[AvailableOwners] = None):
        return self.get_cmd_type(owner) == "Geo" and can_have_mesh(owner)

    def adds_dl_ext(self, owner: Optional[AvailableOwners] = None):
        return self.can_have_mesh(owner) and self.dl_option == "OPTIONAL" and self.use_dl_cmd

    def to_dict(
        self,
        conf_type: CustomCmdConf,
        owner: Optional[AvailableOwners] = None,
        blender_scale=1.0,
        include_defaults=True,
        is_export=False,
    ):
        preset_export = conf_type == "PRESET" and is_export
        data = {}
        if conf_type == "PRESET_EDIT" or preset_export:
            data["name"] = self.name
        if conf_type != "PRESET" or is_export:
            data.update(
                {
                    "cmd_type": self.get_cmd_type(owner),
                    "str_cmd": self.str_cmd,
                    "int_cmd": self.int_cmd,
                    "skip_eval": self.skip_eval,
                }
            )
            if can_have_mesh(owner):
                if conf_type == "PRESET_EDIT" or preset_export:
                    data["children_requirements"] = self.children_requirements
                if data.get("children_requirements") != "NONE":
                    data["group_children"] = self.group_children
                data["dl_option"] = self.dl_option
            if self.can_animate(owner):
                data["is_animated"] = self.is_animated
            if self.adds_dl_ext(owner):
                data["dl_command"] = self.dl_command
        self.args: list[SM64_CustomArgProperties]
        data["args"] = [arg.to_dict(conf_type, owner, blender_scale, include_defaults, is_export) for arg in self.args]
        return data

    def from_dict(self, data: dict, set_defaults=True):
        try:
            self.locked = True  # dont check preset hashes while setting values
            self.name = data.get("name", "My Custom Command")
            self.cmd_type = data.get("cmd_type", "Level")
            self.str_cmd = data.get("str_cmd", "CUSTOM_COMMAND")
            self.int_cmd = data.get("int_cmd", 0)
            self.skip_eval = data.get("skip_eval", True)
            self.children_requirements = data.get("children_requirements", "ANY")
            self.group_children = data.get("group_children", True)
            self.dl_option = data.get("dl_option", "NONE")
            self.is_animated = data.get("is_animated", False)
            self.use_dl_cmd = "dl_command" in data
            self.dl_command = data.get("dl_command", "GEO_CUSTOM_CMD_WITH_DL")
            self.args.clear()
            for i, arg in enumerate(data.get("args", [])):
                self.args.add()
                self.args[-1].from_dict(arg, i, set_defaults)
        finally:
            self.locked = False

    def get_final_cmd(
        self,
        owner: Optional[AvailableOwners],
        blender_scale: float,
        layer: Optional[str | int] = None,
        has_dl=False,
        dl_ref: Optional[str] = None,
        name="",
        conf_type: Optional[CustomCmdConf] = None,
    ):
        if conf_type is None:
            conf_type = "NO_PRESET" if self.preset == "NONE" else "PRESET"
        return CustomCmd(self.to_dict(conf_type, owner, blender_scale, is_export=True), layer, has_dl, dl_ref, name)

    def example_macro_define(self, conf_type: CustomCmdConf = "NO_PRESET", use_dl_cmd=False, max_len=100):
        macro_define = StringIO()
        macro_define.write(f"// {self.name}\n")
        macro_define.write("#define ")
        macro_define.write(self.dl_command if use_dl_cmd else self.str_cmd)
        macro_define.write("(")
        previous_arg_names = set()
        macro_args = [arg.example_macro_args(self, previous_arg_names, conf_type) for arg in self.args]
        if use_dl_cmd:
            macro_args.append(f'/*Displaylist*/ {duplicate_name("displaylist", previous_arg_names)}')
        joined_args = ", ".join(macro_args)
        if len(joined_args) > max_len:
            joined_args = ", \\\n\t\t".join(macro_args)
            macro_define.write("\\\n\t\t")
        macro_define.write(f"{joined_args}) \\\n")
        macro_define.write("\t(/* Your code goes here */)")
        return macro_define.getvalue()

    def get_examples(self, owner: Optional[AvailableOwners], conf_type: CustomCmdConf, blender_scale=100.0):
        cmd_examples = {
            "Without DL": (
                self.get_final_cmd(owner, blender_scale, has_dl=False, conf_type=conf_type),
                self.example_macro_define(conf_type, False, 25),
            )
        }
        if self.adds_dl_ext(owner):
            cmd_examples["With DL"] = (
                self.get_final_cmd(owner, blender_scale, has_dl=True, conf_type=conf_type),
                self.example_macro_define(conf_type, True, 25),
            )
        return cmd_examples

    def draw_examples(
        self,
        layout: UILayout,
        owner: Optional[AvailableOwners],
        conf_type: CustomCmdConf,
        blender_scale: float,
        is_binary=False,
        command_index=0,
    ):
        col = layout.column()
        cmd_examples = self.get_examples(owner, conf_type, blender_scale)
        try:
            for name, (cmd, macro_example) in cmd_examples.items():
                box = col.box().column()
                if len(cmd_examples) > 1:
                    box.label(text=name)
                if is_binary:
                    multilineLabel(box, cmd.to_text_dump())
                    continue
                multilineLabel(box, cmd.to_c(max_length=25).replace("\t", " " * 5))
                SM64_CustomCmdOps.draw_props(
                    box,
                    "COPYDOWN",
                    "Copy example to clipboard",
                    op_name="COPY_EXAMPLE",
                    index=command_index,
                    example_name=name,
                )
                multilineLabel(box, macro_example.replace("\t", " " * 5))
        except Exception as exc:
            multilineLabel(box, f"Error: {exc}")

    def draw_props(
        self,
        layout: UILayout,
        is_binary: bool,
        owner: Optional[AvailableOwners] = None,
        conf_type: CustomCmdConf = "NO_PRESET",
        blender_scale=100.0,
        command_index=-1,
    ):
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
            prop_split(col, self, "int_cmd" if is_binary else "str_cmd", "Command")
            if not is_binary and conf_type != "NO_PRESET":
                col.prop(self, "skip_eval")
            col.separator()

            if self.can_have_mesh(owner):
                if conf_type == "PRESET_EDIT":
                    prop_split(col, self, "children_requirements", "Children Requirements")
                if conf_type != "PRESET_EDIT" or self.children_requirements != "NONE":
                    col.prop(self, "group_children")
                prop_split(col, self, "dl_option", "Displaylist Option")
                if self.dl_option == "OPTIONAL":
                    row = col.row()
                    row.prop(self, "use_dl_cmd")
                    if self.use_dl_cmd:
                        row.prop(self, "dl_command", text="")
            if self.can_animate(owner):
                col.prop(self, "is_animated")

        if conf_type != "PRESET" and draw_and_check_tab(col, self, "args_tab", text=f"Arguments ({len(self.args)})"):
            SM64_CustomArgsOps.draw_row(col.row(), -1, command_index=command_index)

        if self.args_tab or conf_type == "PRESET":
            arg: SM64_CustomArgProperties
            for i, arg in enumerate(self.args):
                if not arg.will_draw(owner, conf_type):
                    continue
                ops_row = col.row()
                if conf_type != "PRESET":
                    num_row = ops_row.row()
                    num_row.alignment = "LEFT"
                    num_row.label(text=str(i))
                    SM64_CustomArgsOps.draw_row(ops_row, i, command_index=command_index)
                arg.draw_props(ops_row, col, owner, self, command_index, i, conf_type, is_binary)
                if conf_type != "PRESET":
                    col.separator(factor=1.0)

        if conf_type != "PRESET" and draw_and_check_tab(col, self, "examples_tab", text="Examples"):
            self.draw_examples(col, owner, conf_type, blender_scale, is_binary, command_index)


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
    SM64_CustomEnumProperties,
    SM64_CustomArgProperties,
    SM64_CustomCmdProperties,
)


def props_register():
    for cls in classes:
        register_class(cls)


def props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
