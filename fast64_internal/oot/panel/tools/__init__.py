from bpy.utils import register_class, unregister_class
from ...panel import OOT_Panel
from .operators import (
    OOT_AddWaterBox,
    OOT_AddDoor,
    OOT_AddScene,
    OOT_AddRoom,
    OOT_AddCutscene,
    OOT_AddPath,
)


class OoT_ToolsPanel(OOT_Panel):
    bl_idname = "OOT_PT_tools"
    bl_label = "OOT Tools"

    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_AddWaterBox.bl_idname)
        col.operator(OOT_AddDoor.bl_idname)
        col.operator(OOT_AddScene.bl_idname)
        col.operator(OOT_AddRoom.bl_idname)
        col.operator(OOT_AddCutscene.bl_idname)
        col.operator(OOT_AddPath.bl_idname)


oot_operator_panel_classes = [
    OoT_ToolsPanel,
]

toolOpsToRegister = [
    OOT_AddWaterBox,
    OOT_AddDoor,
    OOT_AddScene,
    OOT_AddRoom,
    OOT_AddCutscene,
    OOT_AddPath,
]


def oot_operator_panel_register():
    for cls in oot_operator_panel_classes:
        register_class(cls)


def oot_operator_panel_unregister():
    for cls in oot_operator_panel_classes:
        unregister_class(cls)


def oot_operator_register():
    for cls in toolOpsToRegister:
        register_class(cls)


def oot_operator_unregister():
    for cls in reversed(toolOpsToRegister):
        unregister_class(cls)
