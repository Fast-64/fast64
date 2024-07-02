from os import PathLike

from bpy.path import abspath
from bpy.types import PropertyGroup, UILayout, Scene
from bpy.props import StringProperty, EnumProperty, BoolProperty
from bpy.utils import register_class, unregister_class

from ...utility import prop_split, intToHex
from ..sm64_utility import string_int_prop, import_rom_ui_warnings
from ..sm64_constants import level_enums

from .operators import SM64_AddrConv


class SM64_AddrConvProperties(PropertyGroup):
    rom: StringProperty(name="Import ROM", subtype="FILE_PATH")
    address: StringProperty(name="Address")
    level: EnumProperty(items=level_enums, name="Level", default="IC")
    clipboard: BoolProperty(name="Copy to Clipboard", default=True)

    def upgrade_changed_props(self, scene: Scene):
        old_address = scene.pop("convertibleAddr", None)
        if old_address is not None:
            self.address = intToHex(int(old_address, 16))
        old_level = scene.pop("level", None)
        if old_level is not None:
            self["level"] = old_level

    def draw_props(self, layout: UILayout, import_rom: PathLike = None):
        col = layout.column()
        col.label(text="Uses scene import ROM by default", icon="INFO")
        prop_split(col, self, "rom", "ROM")
        picked_rom = abspath(self.rom if self.rom else import_rom)
        if not import_rom_ui_warnings(col, picked_rom):
            return
        col.prop(self, "level")
        if string_int_prop(col, self, "address", "Address"):
            col.prop(self, "clipboard")
            split = col.split()
            args = {"rom": picked_rom, "level": self.level, "addr": self.address, "clipboard": self.clipboard}
            SM64_AddrConv.draw_props(split, text="Segmented to Virtual", option="TO_VIR", **args)
            SM64_AddrConv.draw_props(split, text="Virtual To Segmented", option="TO_SEG", **args)


classes = (SM64_AddrConvProperties,)


def tools_props_register():
    for cls in classes:
        register_class(cls)


def tools_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
