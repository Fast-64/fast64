import dataclasses
import struct
from io import StringIO
from typing import Iterable, NamedTuple, Optional, TypeVar, Union

from ...f3d.f3d_parser import math_eval
from ...utility import PluginError, get_clean_color, to_s16, cast_integer, encodeSegmentedAddr

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


class ArgExport(NamedTuple):
    value: float | int | bool | str
    bit_count: int = 32
    signed: bool = True


class ValueHolder:
    def __init__(self, value):
        self.x = value


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
            for value in flatten(value):
                if (
                    (not self.data["skip_eval"] or binary)
                    and isinstance(value, (int, float, complex))
                    and (not isinstance(value, bool) or binary)
                    and "eval_expression" in data
                ):
                    yield ArgExport(math_eval(data["eval_expression"], ValueHolder(value)), bit_count, signed)
                else:
                    yield ArgExport(value, bit_count, signed)

        arg_type = data.get("arg_type")
        to_sm64_units = data.get("convert_to_sm64", True)
        match arg_type:
            case "COLOR":
                yield from run_eval(get_clean_color(data["color"], True, False), 32, False)
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
                if to_sm64_units:
                    yield from run_eval((round(x) for x in translation), 16)
                else:
                    yield from run_eval((x for x in translation), 32)
            case "SCALE" | "MATRIX":
                yield from run_eval(data.get(arg_type.lower()))
            case "ROTATION":
                rot_type = data["rot_type"]
                rot = flatten(data.get(rot_type.lower()))
                if to_sm64_units and rot_type == "EULER":
                    yield from run_eval((to_s16((x) % 360.0 / 360.0 * (2**16)) for x in rot), 16)
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
                        group += value.to_bytes(bit_count // 8, "big", signed=signed)
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
