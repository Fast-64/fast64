from os import PathLike

from bpy.path import abspath
from bpy.types import PropertyGroup, UILayout, Scene
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty
from bpy.utils import register_class, unregister_class

from ...utility import prop_split, upgrade_old_prop
from ..sm64_utility import string_int_prop, import_rom_ui_warnings
from ..sm64_constants import enumLevelNames

from .operators import SM64_AddrConv


class SM64_AddrConvProperties(PropertyGroup):
    version: IntProperty(name="SM64_AddrConvProperties Version", default=0)
    cur_version = 1

    rom: StringProperty(name="Import ROM", subtype="FILE_PATH")
    address: StringProperty(name="Address")
    level: EnumProperty(items=enumLevelNames, name="Level", default="castle_inside")
    clipboard: BoolProperty(name="Copy to Clipboard", default=True)

    def upgrade_changed_props(self, scene: Scene):
        upgrade_old_prop(self, "address", scene, "convertibleAddr", fix_forced_base_16=True)
        upgrade_old_prop(self, "level", scene, "level")
        self.version = SM64_AddrConvProperties.cur_version

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
