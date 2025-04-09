import dataclasses
import struct
from typing import Iterable, NamedTuple, TypeVar

from ...f3d.f3d_parser import math_eval
from ...utility import PluginError, exportColor, to_s16

from .utility import getDrawLayerName

T = TypeVar("T")


def flatten(iterable: Iterable[T]) -> tuple[T]:
    flat = []
    for x in iterable:
        if isinstance(x, Iterable):
            flat.extend(flatten(x))
        else:
            flat.append(x)
    return tuple(flat)


class ArgExport(NamedTuple):
    value: float | int | bool | str
    bit_count: int
    binary_value: float | int | bool | str = None


@dataclasses.dataclass
class CustomCmd:
    data: dict
    name: str = ""  # for sorting

    def __post_init__(self):
        self.hasDL = False

    def to_arg(self, data: dict) -> Iterable[ArgExport]:
        arg_type = data.get("arg_type")
        to_sm64_units = data.get("convert_to_sm64", True)
        match arg_type:
            case "COLOR":
                yield from (ArgExport(x, 8) for x in exportColor(data["color"], True))
            case "PARAMETER":
                yield ArgExport(data["parameter"], 32, math_eval(data["parameter"], object()))
            case "LAYER":
                yield ArgExport(getDrawLayerName(data["layer"]), 8, int(data["layer"]))
            case "BOOLEAN":
                yield ArgExport(data["boolean"], 8)
            case "NUMBER":
                yield ArgExport(data["value"], 32)
            case "TRANSLATION":
                translation = data["translation"]
                if to_sm64_units:
                    yield from (ArgExport(round(x), 16) for x in translation)
                else:
                    yield from (ArgExport(x, 32) for x in translation)
            case "SCALE" | "MATRIX":
                yield from (ArgExport(x, 32) for x in flatten(data.get(arg_type.lower())))
            case "ROTATION":
                rot_type = data["rot_type"]
                rot = flatten(data.get(rot_type.lower()))
                if to_sm64_units and rot_type == "EULER":
                    yield from (ArgExport(to_s16((x) % 360.0 / 360.0 * (2**16)), 16) for x in rot)
                else:
                    yield from (ArgExport(x, 32) for x in rot)
            case _:
                raise PluginError(f"Unknown arg type {arg_type}")

    def to_c_arg_group(self, data: dict):
        arg_group = []
        for value, _, _ in self.to_arg(data):
            if isinstance(value, bool):
                value = str(value).upper()
            arg_group.append(str(value))
        arg_group = ", ".join(arg_group)
        if "name" not in data:
            return arg_group
        return f"/*{data.get('name')}*/ {arg_group}"

    def to_c(self, depth=0, max_length=100):
        groups = [self.to_c_arg_group(arg_data) for arg_data in self.data["args"]]
        if len(str(groups)) > max_length:
            seperator = ",\n" + ("\t" * (depth + 1))
            args = seperator.join(groups)
        else:
            args = ", ".join(groups)
        return f"{self.data['str_cmd']}({args})"

    def to_binary_arg_group(self, i, arg_data):
        data = bytearray(0)
        name = f"Arg {i}"
        if "name" in arg_data:
            name = f"{arg_data['name']}"
        try:
            for value, bit_count, binary_value in self.to_arg(arg_data):
                if binary_value is not None:
                    value = binary_value
                if isinstance(value, str):
                    raise PluginError("Strings not supported in binary")
                if isinstance(value, float):
                    data += struct.pack("f" if bit_count == 32 else "d", value)
                else:
                    data += value.to_bytes(bit_count // 8, "big")
        except Exception as exc:
            raise PluginError(f'Failed to export arg "{name}": {exc}') from exc
        return name, data

    def to_binary_groups(self):
        groups = []
        groups.append(("Command Index", self.data["int_cmd"].to_bytes(1, "big")))
        for i, arg_data in enumerate(self.data["args"]):
            groups.append(self.to_binary_arg_group(i, arg_data))
        size = sum(len(data) for _, data in groups)
        padding = size % 4
        if padding != 0:
            groups.append(("Trailing Padding", bytes(4 - padding)))
        return groups

    def to_binary(self, _segment_data: dict):
        return bytearray(b for _, data in self.to_binary_groups() for b in data)

    def size(self):
        return sum(len(data) for _, data in self.to_binary_groups())

    def get_ptr_offsets(self):
        return []

    def to_text_dump(self):
        groups = []
        for name, data in self.to_binary_groups():
            data = ", ".join(f"0x{byte:02x}" for byte in data)
            groups.append(f'"{name}": {data}')
        groups = "\n".join(groups)
        return f"Size: {self.size()} bytes.\n{groups}"
