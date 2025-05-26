import dataclasses
import math
import operator
import struct
import ast
from io import StringIO
from typing import Iterable, NamedTuple, Optional, TypeVar, Union

from ...utility import PluginError, get_clean_color, quantize_color, to_s16, cast_integer, encodeSegmentedAddr

from ..sm64_constants import SegmentData
from ..sm64_geolayout_utility import BaseDisplayListNode

from .utility import getDrawLayerName

BIT_COUNTS = {"CHAR": 8, "SHORT": 16, "INT": 32, "LONG": 64, "FLOAT": 32, "DOUBLE": 64}

T = TypeVar("T")


def flatten(iterable: Iterable[T]) -> tuple[T]:
    if not isinstance(iterable, Iterable) or isinstance(iterable, str):
        return (iterable,)
    flat = []
    for x in iterable:
        if isinstance(x, Iterable):
            flat.extend(flatten(x))
        else:
            flat.append(x)
    return tuple(flat)


bin_ops = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.BitOr: operator.or_,
    ast.BitAnd: operator.and_,
    ast.BitXor: operator.xor,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: lambda a: a,
    ast.Not: operator.not_,
    ast.NotEq: operator.ne,
    ast.And: operator.and_,
    ast.Or: operator.or_,
    ast.In: operator.contains,
    ast.NotIn: lambda a, b: not operator.contains(a, b),
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.Eq: operator.eq,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Invert: operator.invert,
}

builtins_map = {
    "round": round,
    "abs": abs,
    "tuple": tuple,
    "list": list,
    "set": set,
    "dict": dict,
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "all": all,
    "any": any,
    "enumerate": enumerate,
    "flatten": flatten,
}
collection_constructors = {ast.List: list, ast.Tuple: tuple, ast.Set: set}


def math_eval(s, start_scope: dict[str, object] | None = None):
    if start_scope is None:
        start_scope = {}
    if isinstance(s, int):
        return s

    s = s.strip()
    node = ast.parse(s, mode="eval")

    def _eval(node: ast.expr, scope: dict[str, object]):
        scope = scope.copy()

        def eval_comprehension(elt_node: ast.expr, generators: list[ast.comprehension], scope: dict[str, object]):
            if not generators:
                result = [_eval(elt_node, scope)]
            else:
                result = []
                first_comp, rest_comps = generators[0], generators[1:]
                for value in _eval(first_comp.iter, scope):
                    new_scope = scope.copy()
                    if isinstance(first_comp.target, ast.Name):
                        new_scope[first_comp.target.id] = value
                    elif isinstance(first_comp.target, (ast.Tuple, ast.List, ast.Set)):
                        for i, elt in enumerate(first_comp.target.elts):
                            new_scope[elt.id] = value[i]
                    if all(_eval(if_node, new_scope) for if_node in first_comp.ifs):
                        sub_results = eval_comprehension(elt_node, rest_comps, new_scope)
                        result.extend(sub_results)
            return result

        if isinstance(node, ast.Name):
            if node.id in scope:
                return scope[node.id]
            elif hasattr(math, node.id):
                return getattr(math, node.id)
            else:
                return builtins_map.get(node.id, node.id)
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.UnaryOp):
            return bin_ops[type(node.op)](_eval(node.operand, scope))
        elif isinstance(node, ast.BinOp):
            return bin_ops[type(node.op)](_eval(node.left, scope), _eval(node.right, scope))
        elif isinstance(node, ast.Call):
            args = [_eval(x, scope) for x in node.args]
            funcName = _eval(node.func, scope)
            return funcName(*args)
        elif isinstance(node, ast.ListComp):
            return eval_comprehension(node.elt, node.generators, scope)
        elif isinstance(node, ast.SetComp):
            return set(eval_comprehension(node.elt, node.generators, scope))
        elif isinstance(node, ast.GeneratorExp):
            return eval_comprehension(node.elt, node.generators, scope)
        elif isinstance(node, tuple(collection_constructors.keys())):
            return collection_constructors[type(node)](_eval(x, scope) for x in node.elts)
        elif isinstance(node, ast.Expression):
            return _eval(node.body, scope)
        elif isinstance(node, ast.Subscript):
            return _eval(node.value, scope)[_eval(node.slice, scope)]
        elif isinstance(node, ast.Slice):
            lower, upper, step = 0, None, None
            if node.lower is not None:
                lower = _eval(node.lower, scope)
            if node.upper is not None:
                upper = _eval(node.upper, scope)
            if node.step is not None:
                step = _eval(node.step, scope)
            return slice(lower, upper, step)
        elif isinstance(node, ast.IfExp):
            if _eval(node.test, scope):
                return _eval(node.body, scope)
            else:
                return _eval(node.orelse, scope)
        elif isinstance(node, ast.Compare):
            left = _eval(node.left, scope)
            for op, right in zip(node.ops, node.comparators):
                right = _eval(right, scope)
                if not bin_ops[type(op)](left, right):
                    return False
                left = right
            return True
        else:
            raise Exception(f"Unsupported AST node: {ast.dump(node)}")

    return _eval(node.body, start_scope)


class ArgExport(NamedTuple):
    value: float | int | bool | str
    bit_count: int = 32
    signed: bool = True


@dataclasses.dataclass
class CustomCmd(BaseDisplayListNode):
    data: dict
    draw_layer: int | str | None = 0
    hasDL: bool = False
    dlRef: str = None
    name: str = ""
    bleed_independently: bool = False
    fMesh: "FMesh" = None
    DLmicrocode: Union["GfxList", None] = None
    # exists to get the override DL from an fMesh
    override_hash: tuple | None = None

    def __post_init__(self):
        self.hasDL &= self.data.get("dl_option") != "NONE"
        self.group_children = self.data.get("group_children", True)

    @property
    def drawLayer(self):
        """HACK: drawLayer's default is usually per bone/object, but in the custom cmd system defaults are per argument.
        We instead store a layer that can be none, and set it to a real value if the setter is called.
        """
        if self.draw_layer is None:
            return 0
        return self.draw_layer

    @drawLayer.setter
    def drawLayer(self, value):
        self.draw_layer = value

    @property
    def args(self):
        yield from self.data["args"]
        if self.hasDL and "dl_command" in self.data:
            yield {"name": "Displaylist", "arg_type": "DL"}

    def do_export_checks(self, children_count: int):
        name = "" or self.data.get("name") or self.data.get("str_cmd")
        name = f" ({name})" if name else ""
        children_requirements = self.data.get("children_requirements", "ANY")
        if children_requirements == "MUST" and children_count == 0:
            raise PluginError(f"Command{name} must have at least one child node")
        elif children_requirements == "NONE" and children_count > 0:
            raise PluginError(f"Command{name} must have no children")
        if self.data.get("dl_option") == "REQUIRED":
            if self.DLmicrocode is None:
                raise PluginError(f"Command{name} requires a displaylist")

    def to_arg(self, data: dict, binary=False) -> Iterable[ArgExport]:
        def run_eval(value, bit_count=32, signed=True):
            if (
                (not self.data["skip_eval"] or binary)
                and isinstance(value, (int, float, complex, tuple))
                and (not isinstance(value, bool) or binary)
                and "eval_expression" in data
            ):
                evaluated = math_eval(data["eval_expression"], {"x": value})
                yield from tuple(ArgExport(x, bit_count, signed) for x in flatten(evaluated))
            else:
                yield from tuple(ArgExport(x, bit_count, signed) for x in flatten(value))

        arg_type = data.get("arg_type")
        round_to_sm64 = data.get("round_to_sm64", True)
        match arg_type:
            case "COLOR":
                if round_to_sm64:
                    bit_counts = data.get("color_bits", (8, 8, 8, 8))
                    color = get_clean_color(data["color"], True, False, True)
                    yield from run_eval(quantize_color(color, bit_counts), sum(bit_counts), False)
                else:
                    yield from run_eval(get_clean_color(data["color"], True, True, True), 32, False)
            case "PARAMETER":
                if binary:
                    value = math_eval(data["parameter"], object())
                    if isinstance(value, str):
                        raise PluginError("Strings not supported in binary")
                    yield from run_eval(value)
                else:
                    yield from run_eval(data["parameter"])
            case "ENUM":
                if data["enum"] >= len(data["enum_options"]):
                    option = {"int_value": 0, "str_value": "INVALID"}
                else:
                    option = data["enum_options"][data["enum"]]
                if binary:
                    yield from run_eval(option["int_value"])
                else:
                    yield from run_eval(option["str_value"])
            case "LAYER":
                layer = data["layer"] if self.draw_layer is None or not data.get("inherit", True) else self.draw_layer
                if binary:
                    layer = int(data["layer"])
                    if "dl_command" in self.data:
                        layer = (1 << 7) | layer
                    yield from run_eval(layer, 8, False)
                else:
                    yield from run_eval(getDrawLayerName(layer))
            case "BOOLEAN":
                yield from run_eval(data["boolean"], 8)
            case "NUMBER":
                yield from run_eval(data["value"], 32)
            case "TRANSLATION":
                translation = data["translation"]
                if round_to_sm64:
                    yield from run_eval(tuple(round(x) for x in translation), 16)
                else:
                    yield from run_eval(tuple(x for x in translation), 32)
            case "SCALE" | "MATRIX":
                yield from run_eval(data.get(arg_type.lower()))
            case "ROTATION":
                rot_type = data["rot_type"]
                rot = data.get(rot_type.lower())
                if round_to_sm64 and rot_type == "EULER":
                    yield from run_eval(tuple(to_s16(round(x)) for x in rot), 16)
                else:
                    yield from run_eval(rot, 32)
            case "DL":
                has_dl, dl_ref = self.hasDL, self.dlRef
                self.hasDL, self.dlRef = True, (data.get("dl") or None)
                if binary:
                    yield from run_eval(self.get_dl_address(), 32)
                else:
                    yield from run_eval(self.get_dl_name(), 32)
                self.hasDL, self.dlRef = has_dl, dl_ref
            case _:
                raise PluginError(f"Unknown arg type {arg_type}")

    def to_c(self, depth: int = 0, max_length: int = 150) -> str:
        data = StringIO()
        dl_command = self.data.get("dl_command")
        data.write(dl_command if dl_command is not None and self.hasDL else self.data["str_cmd"])
        data.write("(")
        groups = []
        for i, arg_data in enumerate(self.args):
            group = []
            try:
                for value, _, _ in self.to_arg(arg_data):
                    if value is None:
                        value = "NULL"
                    elif isinstance(value, bool):
                        value = str(value).upper()
                    group.append(str(value))
                group_str = ", ".join(group)
                if "name" in arg_data:
                    group_str = f"/*{arg_data['name']}*/ {group_str}"
                groups.append(group_str)
            except Exception as exc:
                raise PluginError(f'Failed to export arg "{arg_data.get("name", f"Arg {i}")}": {exc}') from exc

        if len("".join(groups)) > max_length:
            separator = ",\n" + ("\t" * (depth + 1))
            data.write(separator.join(groups))
        else:
            data.write(", ".join(groups))

        data.write(")")
        return data.getvalue()

    def to_binary_groups(self, segment_data: Optional[SegmentData] = None):
        groups = []
        groups.append(("Command Index (𝗔𝘂𝘁𝗼𝗺𝗮𝘁𝗶𝗰)", self.data["int_cmd"].to_bytes(1, "big")))
        for i, arg_data in enumerate(self.args):
            name = arg_data.get("name", f"Arg {i}")
            try:
                group = bytearray(0)
                for value, bit_count, signed in self.to_arg(arg_data, True):
                    if value is None:
                        value = 0
                    signed = arg_data.get("signed", signed)
                    if "value_type" in arg_data:
                        bit_count = BIT_COUNTS[arg_data["value_type"]]
                        if arg_data["value_type"] in {"FLOAT", "DOUBLE"}:
                            value = float(value)
                        else:
                            value = int(value)
                    if arg_data.get("seg_addr", False) and segment_data is not None:
                        value = encodeSegmentedAddr(value, segment_data)
                    if isinstance(value, bytes):
                        group += value
                    elif isinstance(value, float):
                        group += struct.pack("f" if bit_count == 32 else "d", value)
                    elif isinstance(value, int):
                        value = cast_integer(value, bit_count, signed)
                        group += value.to_bytes(math.ceil(bit_count / 8), "big", signed=signed)
                    else:
                        raise PluginError(f"{type(value)} not supported in binary")
                groups.append((name, group))
            except Exception as exc:
                raise PluginError(f'Failed to export arg "{name}": \n{exc}') from exc

        size = sum(len(data) for _, data in groups)
        padding = size % 4
        if padding != 0:
            groups.append(("Trailing Padding (𝗔𝘂𝘁𝗼𝗺𝗮𝘁𝗶𝗰)", bytes(4 - padding)))
        return groups

    def to_binary(self, segment_data: Optional[SegmentData] = None):
        return bytearray(b for _, data in self.to_binary_groups(segment_data) for b in data)

    def size(self, segment_data: Optional[SegmentData] = None):
        return sum(len(data) for _, data in self.to_binary_groups(segment_data))

    def get_ptr_offsets(self):
        return []

    def to_text_dump(self, segment_data: Optional[SegmentData] = None):
        data = StringIO()
        data.write(f"Size: {self.size(segment_data)} bytes.")
        if segment_data is None:
            data.write("\nNo segment range provided, won't encode to a respective segment")
        for name, bytes in self.to_binary_groups(segment_data):
            bytes_str = ", ".join(f"0x{byte:02x}" for byte in bytes)
            data.write(f'\n\t"{name}": {bytes_str}')
        return data.getvalue()
