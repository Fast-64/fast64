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

        col.label(text="Misc Tools", icon="TOOL_SETTINGS")
        col.operator(SM64_CreateSimpleLevel.bl_idname)
        col.operator(SM64_AddWaterBox.bl_idname)

        col.label(text="Armature Tools", icon="ARMATURE_DATA")
        col.operator(SM64_AddBoneGroups.bl_idname)
        col.operator(SM64_CreateMetarig.bl_idname)

        if not sm64_props.show_importing_menus:
            return
        col.label(text="Address Converter", icon="VIEWZOOM")
        try:
            import_rom_checks(abspath(sm64_props.import_rom))
        except Exception as e:
            multilineLabel(col.box(), str(e), "ERROR")
            col = col.column()
            col.enabled = False

        prop_split(col, sm64_props, "convertible_addr", "Address")
        prop_split(col, sm64_props, "level_convert", "Level")
        seg_to_virt_op = col.operator(SM64_AddrConv.bl_idname, text="Convert Segmented To Virtual")
        seg_to_virt_op.conversion_option = "SEGMENTED_TO_VIRTUAL"
        seg_to_virt_op.address = sm64_props.convertible_addr
        virt_to_seg_op = col.operator(SM64_AddrConv.bl_idname, text="Convert Virtual To Segmented")
        virt_to_seg_op.conversion_option = "VIRTUAL_TO_SEGMENTED"
        virt_to_seg_op.address = sm64_props.convertible_addr


classes = (SM64_ToolsPanel,)


def tools_panels_register():
    for cls in classes:
        register_class(cls)


def tools_panels_unregister():
    for cls in classes:
        unregister_class(cls)
