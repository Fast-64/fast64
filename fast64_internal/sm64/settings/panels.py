from bpy.utils import register_class, unregister_class

from ...utility import prop_split
from ...panels import SM64_Panel

from .properties import SM64_Properties


class SM64_MenuVisibilityPanel(SM64_Panel):
    bl_idname = "SM64_PT_menu_visibility_settings"
    bl_label = "SM64 Menu Visibility Settings"
    bl_options = set()  # default to open
    bl_order = 0  # force to front

    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding
        sm64Props: SM64_Properties = context.scene.fast64.sm64

        prop_split(col, sm64Props, "goal", "Export goal")
        prop_split(col, sm64Props, "showImportingMenus", "Show Importing Options")


class SM64_FileSettingsPanel(SM64_Panel):
    bl_idname = "SM64_PT_file_settings"
    bl_label = "SM64 File Settings"
    bl_options = set()

    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding
        sm64Props: SM64_Properties = context.scene.fast64.sm64

        prop_split(col, sm64Props, "exportType", "Export type")
        prop_split(col, context.scene, "blenderToSM64Scale", "Blender To SM64 Scale")

        if sm64Props.showImportingMenus:
            col.prop(context.scene, "importRom")

        if sm64Props.exportType == "Binary":
            col.prop(context.scene, "exportRom")
            col.prop(context.scene, "outputRom")
            col.prop(context.scene, "extendBank4")
        elif sm64Props.exportType == "C":
            col.prop(context.scene, "disableScroll")
            col.prop(context.scene, "decompPath")
            prop_split(col, context.scene, "refreshVer", "Decomp Func Map")
            prop_split(col, context.scene, "compressionFormat", "Compression Format")


classes = (
    SM64_MenuVisibilityPanel,
    SM64_FileSettingsPanel,
)


def settings_panels_register():
    for cls in classes:
        register_class(cls)


def settings_panels_unregister():
    for cls in classes:
        unregister_class(cls)
