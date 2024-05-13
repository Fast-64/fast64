from bpy.utils import register_class, unregister_class

from ...panels import SM64_Panel
from ...utility import prop_split

from ..sm64_utility import import_rom_ui_warnings. string_int_warning

from .operators import SM64_AddrConv, SM64_CreateSimpleLevel, SM64_AddWaterBox, SM64_AddBoneGroups, SM64_CreateMetarig


class SM64_ToolsPanel(SM64_Panel):
    bl_idname = "SM64_PT_tools"
    bl_label = "SM64 Tools"

    def draw(self, context):
        sm64_props = context.scene.fast64.sm64

        col = self.layout.column()

        col.label(text="Misc Tools", icon="TOOL_SETTINGS")
        SM64_CreateSimpleLevel.draw_props(col)
        SM64_AddWaterBox.draw_props(col)

        col.label(text="Armature Tools", icon="ARMATURE_DATA")
        SM64_AddBoneGroups.draw_props(col)
        SM64_CreateMetarig.draw_props(col)

        if not sm64_props.show_importing_menus:
            return
        col.label(text="Address Converter", icon="MEMORY")

        if not import_rom_ui_warnings(col, sm64_props.import_rom):
            col = col.column()
            col.enabled = False
        prop_split(col, sm64_props, "level_convert", "Level")
        prop_split(col, sm64_props, "convertible_addr", "Address")
        if string_int_warning(col, sm64_props.convertible_addr):
            address = sm64_props.convertible_addr
            split = col.split()
            to_virt_op = SM64_AddrConv.draw_props(split, text="Segmented To Virtual")
            to_virt_op.option, to_virt_op.address = "SEGMENTED_TO_VIRTUAL", address
            to_virt_op = SM64_AddrConv.draw_props(split, text="Virtual To Segmented")
            to_virt_op.option, to_virt_op.address = "VIRTUAL_TO_SEGMENTED", address


classes = (SM64_ToolsPanel,)


def tools_panels_register():
    for cls in classes:
        register_class(cls)


def tools_panels_unregister():
    for cls in classes:
        unregister_class(cls)
