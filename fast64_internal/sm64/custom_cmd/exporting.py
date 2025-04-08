import dataclasses
from typing import Optional

from ...utility import PluginError

from .utility import AvailableOwners


@dataclasses.dataclass
class CustomCmd:
    owner: Optional[AvailableOwners]
    cmd_property: "SM64_CustomCmdProperties"
    blender_scale: float = 1
    preset_edit: bool = False  # preset edit preview

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
