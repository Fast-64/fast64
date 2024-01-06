from bpy.utils import register_class, unregister_class
from bpy.path import abspath

from ...panels import SM64_Panel
from ...utility import multilineLabel, prop_split

from ..sm64_utility import import_rom_checks

from .operators import SM64_AddrConv, SM64_CreateSimpleLevel, SM64_AddWaterBox, SM64_AddBoneGroups, SM64_CreateMetarig


class SM64_ToolsPanel(SM64_Panel):
    bl_idname = "SM64_PT_tools"
    bl_label = "SM64 Tools"

    def draw(self, context):
        sm64_props = context.scene.fast64.sm64

        col = self.layout.column()

        misc_box = self.layout.column()
        misc_box.label(text="Misc Tools")
        misc_box = misc_box.box().column()
        misc_box.operator(SM64_CreateSimpleLevel.bl_idname)
        misc_box.operator(SM64_AddWaterBox.bl_idname)

        armature_box = self.layout.column()
        armature_box.label(text="Armature Tools")
        armature_box = armature_box.box().column()
        armature_box.operator(SM64_AddBoneGroups.bl_idname)
        armature_box.operator(SM64_CreateMetarig.bl_idname)

        if not sm64_props.show_importing_menus:
            return

        addr_conv_col = self.layout.column()
        addr_conv_col.label(text="Address Converter")
        addr_conv_box = addr_conv_col.box().column()
        try:
            import_rom_checks(abspath(sm64_props.import_rom))
        except Exception as e:
            multilineLabel(addr_conv_col.box(), str(e), "ERROR")
            addr_conv_box = addr_conv_box.column()
            addr_conv_box.enabled = False

        prop_split(addr_conv_box, sm64_props, "convertible_addr", "Address")
        prop_split(addr_conv_box, sm64_props, "level_convert", "Level")
        seg_to_virt_op = addr_conv_box.operator(SM64_AddrConv.bl_idname, text="Convert Segmented To Virtual")
        seg_to_virt_op.conversion_option = "SEGMENTED_TO_VIRTUAL"
        seg_to_virt_op.address = sm64_props.convertible_addr
        virt_to_seg_op = addr_conv_box.operator(SM64_AddrConv.bl_idname, text="Convert Virtual To Segmented")
        virt_to_seg_op.conversion_option = "VIRTUAL_TO_SEGMENTED"
        virt_to_seg_op.address = sm64_props.convertible_addr


classes = (SM64_ToolsPanel,)


def tools_panels_register():
    for cls in classes:
        register_class(cls)


def tools_panels_unregister():
    for cls in classes:
        unregister_class(cls)
