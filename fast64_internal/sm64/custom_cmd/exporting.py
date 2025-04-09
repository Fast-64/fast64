import dataclasses
from typing import Iterable, NamedTuple, TypeVar

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
                yield ArgExport(data["parameter"], -1)
            case "LAYER":
                yield ArgExport(getDrawLayerName(data.get("layer", 0)), 8, data.get("layer", 0))
            case "BOOLEAN":
                yield ArgExport(data["boolean"], 8)
            case "NUMBER":
                yield ArgExport(data["value"], 32)
            case "TRANSLATION":
                translation = data.get("translation")
                if to_sm64_units:
                    yield from (ArgExport(round(x), 16) for x in translation)
                else:
                    yield from (ArgExport(x, 32) for x in translation)
            case "SCALE" | "MATRIX":
                yield from (ArgExport(x, 32) for x in flatten(data.get(arg_type.lower())))
            case "ROTATION":
                rot_type = data.get("rot_type")
                rot = flatten(data.get(rot_type.lower()))
                if to_sm64_units and rot_type == "EULER":
                    yield from (ArgExport(to_s16((x) % 360.0 / 360.0 * (2**16)), 16) for x in rot)
                else:
                    yield from (ArgExport(x, 32) for x in rot)
            case _:
                raise PluginError(f"Unknown arg type {arg_type}")

    def to_arg_c(self, data: dict):
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
        arg_groups = [self.to_arg_c(arg_data) for arg_data in self.data.get("args")]
        if len(str(arg_groups)) > max_length:
            seperator = ",\n" + ("\t" * (depth + 1))
            args = seperator.join(arg_groups)
        else:
            args = ", ".join(arg_groups)
        return f"{self.data['str_cmd']}({args})"

    def to_binary(self):  # TODO
        raise NotImplementedError("TODO: Implement binary export for custom commands")

    def size(self):
        return 0

    def get_ptr_offsets(self):
        return []
