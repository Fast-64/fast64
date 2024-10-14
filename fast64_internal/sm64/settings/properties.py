import os
import bpy
from bpy.types import PropertyGroup, UILayout, Context
from bpy.props import BoolProperty, StringProperty, EnumProperty, IntProperty, FloatProperty, PointerProperty
from bpy.path import abspath
from bpy.utils import register_class, unregister_class

from ...render_settings import on_update_render_settings
from ...utility import directory_path_checks, directory_ui_warnings, prop_split, set_prop_if_in_data, upgrade_old_prop
from ..sm64_constants import defaultExtendSegment4
from ..sm64_objects import SM64_CombinedObjectProperties
from ..sm64_utility import export_rom_ui_warnings, import_rom_ui_warnings
from ..tools import SM64_AddrConvProperties

from .constants import (
    enum_refresh_versions,
    enum_compression_formats,
    enum_export_type,
    enum_sm64_goal_type,
)


def decomp_path_update(self, context: Context):
    fast64_settings = context.scene.fast64.settings
    if fast64_settings.repo_settings_path:
        return
    directory_path_checks(abspath(self.decomp_path))
    fast64_settings.repo_settings_path = os.path.join(abspath(self.decomp_path), "fast64.json")


class SM64_Properties(PropertyGroup):
    """Global SM64 Scene Properties found under scene.fast64.sm64"""

    version: IntProperty(name="SM64_Properties Version", default=0)
    cur_version = 4  # version after property migration

    # UI Selection
    show_importing_menus: BoolProperty(name="Show Importing Menus", default=False)
    export_type: EnumProperty(items=enum_export_type, name="Export Type", default="C")
    goal: EnumProperty(items=enum_sm64_goal_type, name="Goal", default="All")
    combined_export: bpy.props.PointerProperty(type=SM64_CombinedObjectProperties)

    blender_to_sm64_scale: FloatProperty(
        name="Blender To SM64 Scale",
        default=100,
        update=on_update_render_settings,
    )
    import_rom: StringProperty(name="Import ROM", subtype="FILE_PATH")

    export_rom: StringProperty(name="Export ROM", subtype="FILE_PATH")
    output_rom: StringProperty(name="Output ROM", subtype="FILE_PATH")
    extend_bank_4: BoolProperty(
        name="Extend Bank 4 on Export?",
        default=True,
        description=f"Sets bank 4 range to ({hex(defaultExtendSegment4[0])}, "
        f"{hex(defaultExtendSegment4[1])}) and copies data from old bank",
    )

    address_converter: PointerProperty(type=SM64_AddrConvProperties)
    # C
    decomp_path: StringProperty(
        name="Decomp Folder",
        subtype="FILE_PATH",
        update=decomp_path_update,
    )
    sm64_repo_settings_tab: BoolProperty(default=True, name="SM64 Repo Settings")
    disable_scroll: BoolProperty(name="Disable Scrolling Textures")
    refresh_version: EnumProperty(items=enum_refresh_versions, name="Refresh", default="Refresh 16")
    compression_format: EnumProperty(
        items=enum_compression_formats,
        name="Compression",
        default="mio0",
    )
    force_extended_ram: BoolProperty(
        name="Force Extended Ram",
        default=True,
        description="USE_EXT_RAM will be defined in include/segments.h on export, increasing the available RAM by 4MB but requiring the expansion pack, this prevents crashes from running out of RAM",
    )
    matstack_fix: BoolProperty(
        name="Matstack Fix",
        description="Exports account for matstack fix requirements",
    )

    @property
    def binary_export(self):
        return self.export_type in ["Binary", "Insertable Binary"]

    @staticmethod
    def upgrade_changed_props():
        old_scene_props_to_new = {
            "importRom": "import_rom",
            "exportRom": "export_rom",
            "outputRom": "output_rom",
            "disableScroll": "disable_scroll",
            "blenderToSM64Scale": "blender_to_sm64_scale",
            "decompPath": "decomp_path",
            "extendBank4": "extend_bank_4",
            "refreshVer": "refresh_version",
            "exportType": "export_type",
        }
        old_export_props_to_new = {
            "custom_group_name": {"geoLevelName", "colLevelName", "animLevelName"},
            "custom_export_path": {"geoExportPath", "colExportPath", "animExportPath"},
            "object_name": {"geoName", "colName", "animName"},
            "group_name": {"geoGroupName", "colGroupName", "animGroupName"},
            "level_name": {"levelOption", "geoLevelOption", "colLevelOption", "animLevelOption"},
            "custom_level_name": {"levelName", "geoLevelName", "colLevelName", "animLevelName"},
            "non_decomp_level": {"levelCustomExport"},
            "export_header_type": {"geoExportHeaderType", "colExportHeaderType", "animExportHeaderType"},
            "custom_include_directory": {"geoTexDir"},
        }
        for scene in bpy.data.scenes:
            sm64_props: SM64_Properties = scene.fast64.sm64
            sm64_props.address_converter.upgrade_changed_props(scene)
            if sm64_props.version == SM64_Properties.cur_version:
                continue
            upgrade_old_prop(
                sm64_props,
                "export_type",
                scene,
                {
                    "animExportType",
                    "colExportType",
                    "DLExportType",
                    "geoExportType",
                },
            )
            for old, new in old_scene_props_to_new.items():
                upgrade_old_prop(sm64_props, new, scene, old)
            upgrade_old_prop(sm64_props, "show_importing_menus", sm64_props, "showImportingMenus")

            combined_props = scene.fast64.sm64.combined_export
            for new, old in old_export_props_to_new.items():
                upgrade_old_prop(combined_props, new, scene, old)
            sm64_props.version = SM64_Properties.cur_version

    def to_repo_settings(self):
        data = {}
        data["refresh_version"] = self.refresh_version
        data["compression_format"] = self.compression_format
        data["force_extended_ram"] = self.force_extended_ram
        data["matstack_fix"] = self.matstack_fix
        return data

    def from_repo_settings(self, data: dict):
        set_prop_if_in_data(self, "refresh_version", data, "refresh_version")
        set_prop_if_in_data(self, "compression_format", data, "compression_format")
        set_prop_if_in_data(self, "force_extended_ram", data, "force_extended_ram")
        set_prop_if_in_data(self, "matstack_fix", data, "matstack_fix")

    def draw_repo_settings(self, layout: UILayout):
        col = layout.column()
        if not self.binary_export:
            col.prop(self, "disable_scroll")
            prop_split(col, self, "compression_format", "Compression Format")
            prop_split(col, self, "refresh_version", "Refresh (Function Map)")
            col.prop(self, "force_extended_ram")
        col.prop(self, "matstack_fix")

    def draw_props(self, layout: UILayout, show_repo_settings: bool = True):
        col = layout.column()

        prop_split(col, self, "goal", "Goal")
        prop_split(col, self, "export_type", "Export type")
        col.separator()

        prop_split(col, self, "blender_to_sm64_scale", "Blender To SM64 Scale")

        if self.export_type == "Binary":
            col.prop(self, "export_rom")
            export_rom_ui_warnings(col, self.export_rom)
            col.prop(self, "output_rom")
            col.prop(self, "extend_bank_4")
        elif not self.binary_export:
            prop_split(col, self, "decomp_path", "Decomp Path")
            directory_ui_warnings(col, abspath(self.decomp_path))
        col.separator()

        if show_repo_settings:
            self.draw_repo_settings(col)
            col.separator()

        col.prop(self, "show_importing_menus")
        if self.show_importing_menus:
            prop_split(col, self, "import_rom", "Import ROM")
            import_rom_ui_warnings(col, self.import_rom)


classes = (SM64_Properties,)


def settings_props_register():
    for cls in classes:
        register_class(cls)


def settings_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
