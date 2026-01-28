from bpy.utils import register_class, unregister_class

from typing import TYPE_CHECKING

from ...panels import SM64_Panel

from .operators import SM64_CreateSimpleLevel, SM64_AddWaterBox, SM64_AddBoneGroups, SM64_CreateMetarig

if TYPE_CHECKING:
    from ..settings.properties import SM64_Properties


class SM64_ToolsPanel(SM64_Panel):
    bl_idname = "SM64_PT_tools"
    bl_label = "SM64 Tools"

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Misc Tools", icon="TOOL_SETTINGS")
        SM64_CreateSimpleLevel.draw_props(col)
        SM64_AddWaterBox.draw_props(col)

        col.label(text="Armature Tools", icon="ARMATURE_DATA")
        SM64_AddBoneGroups.draw_props(col)
        SM64_CreateMetarig.draw_props(col)

        sm64_props: SM64_Properties = context.scene.fast64.sm64
        if not sm64_props.show_importing_menus:
            return
        col.label(text="Address Converter", icon="MEMORY")
        sm64_props.address_converter.draw_props(col.box(), sm64_props.import_rom)


classes = (SM64_ToolsPanel,)


def tools_panels_register():
    for cls in classes:
        register_class(cls)


def tools_panels_unregister():
    for cls in classes:
        unregister_class(cls)
