import os
from pathlib import Path
import bpy
from bpy.types import PropertyGroup, UILayout, Context
from bpy.props import (
    BoolProperty,
    StringProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
    PointerProperty,
    CollectionProperty,
)
from bpy.path import abspath
from bpy.utils import register_class, unregister_class

from ...render_settings import on_update_render_settings
from ...utility import (
    directory_path_checks,
    directory_ui_warnings,
    draw_directory,
    prop_split,
    set_prop_if_in_data,
    upgrade_old_prop,
    get_first_set_prop,
)
from ..sm64_constants import defaultExtendSegment4, OLD_BINARY_LEVEL_ENUMS
from ..sm64_objects import SM64_CombinedObjectProperties
from ..custom_cmd.properties import SM64_CustomCmdProperties, draw_custom_cmd_presets
from ..sm64_utility import export_rom_ui_warnings, import_rom_ui_warnings
from ..tools import SM64_AddrConvProperties
from ..animation.properties import SM64_AnimProperties

from .constants import (
    enum_refresh_versions,
    enum_compression_formats,
    enum_export_type,
    enum_sm64_goal_type,
)


def decomp_path_update(self, context: Context):
    fast64_settings = context.scene.fast64.settings
    if fast64_settings.repo_settings_path and Path(abspath(fast64_settings.repo_settings_path)).exists():
        return
    directory_path_checks(self.abs_decomp_path)
    fast64_settings.repo_settings_path = str(self.abs_decomp_path / "fast64.json")


class SM64_Properties(PropertyGroup):
    """Global SM64 Scene Properties found under scene.fast64.sm64"""

    version: IntProperty(name="SM64_Properties Version", default=0)
    cur_version = 6  # version after property migration

    # UI Selection
    show_importing_menus: BoolProperty(name="Show Importing Menus", default=False)
    export_type: EnumProperty(items=enum_export_type, name="Export Type", default="C")
    goal: EnumProperty(items=enum_sm64_goal_type, name="Goal", default="All")
    combined_export: bpy.props.PointerProperty(type=SM64_CombinedObjectProperties)
    animation: PointerProperty(type=SM64_AnimProperties)
    custom_cmds: CollectionProperty(type=SM64_CustomCmdProperties)
    custom_cmds_tab: BoolProperty(default=True, name="Custom Commands")
    address_converter: PointerProperty(type=SM64_AddrConvProperties)

    blender_to_sm64_scale: FloatProperty(
        name="Blender To SM64 Scale",
        default=100,
        update=on_update_render_settings,
    )
    import_rom: StringProperty(name="Import ROM", subtype="FILE_PATH")

    # binary
    export_rom: StringProperty(name="Export ROM", subtype="FILE_PATH")
    output_rom: StringProperty(name="Output ROM", subtype="FILE_PATH")
    extend_bank_4: BoolProperty(
        name="Extend Bank 4 on Export?",
        default=True,
        description=f"Sets bank 4 range to ({hex(defaultExtendSegment4[0])}, "
        f"{hex(defaultExtendSegment4[1])}) and copies data from old bank",
    )

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
    lighting_engine_presets: BoolProperty(name="Lighting Engine Presets")
    write_all: BoolProperty(
        name="Write All",
        description="Write single load geo and set othermode commands instead of writting the difference to defaults. Can result in smaller displaylists but may introduce issues",
    )
    # could be used for other properties outside animation
    designated_prop: BoolProperty(
        name="Designated Initialization for Animation Tables",
        description="Extremely recommended but must be off when compiling with IDO. Included in Repo Setting file",
    )

    actors_folder: StringProperty(name="Actors Folder", default="actors", subtype="FILE_PATH")
    levels_folder: StringProperty(name="Levels Folder", default="levels", subtype="FILE_PATH")
    dma_anims_folder: StringProperty(name="DMA Animations Folder", default="assets/anims", subtype="FILE_PATH")

    @property
    def binary_export(self):
        return self.export_type in {"Binary", "Insertable Binary"}

    @property
    def abs_decomp_path(self) -> Path:
        return Path(abspath(self.decomp_path))

    @property
    def hackersm64(self) -> bool:
        return self.refresh_version.startswith("HackerSM64")

    @property
    def designated(self) -> bool:
        return self.designated_prop or self.hackersm64

    @property
    def gfx_write_method(self):
        from ...f3d.f3d_gbi import GfxMatWriteMethod

        return GfxMatWriteMethod.WriteAll if self.write_all else GfxMatWriteMethod.WriteDifferingAndRevert

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
            "custom_level_name": {"levelName", "geoLevelName", "colLevelName", "animLevelName", "DLLevelName"},
            "custom_export_path": {"geoExportPath", "colExportPath", "animExportPath", "DLExportPath"},
            "object_name": {"geoName", "colName", "animName"},
            "group_name": {"geoGroupName", "colGroupName", "animGroupName", "DLGroupName"},
            "level_name": {"levelOption", "geoLevelOption", "colLevelOption", "animLevelOption", "DLLevelOption"},
            "non_decomp_level": {"levelCustomExport"},
            "export_header_type": {"geoExportHeaderType", "colExportHeaderType", "animExportHeaderType"},
            "custom_include_directory": {"geoTexDir"},
            "binary_level": {"levelAnimExport"},
            # as the others binary props get carried over to here we need to update the cur_version again
        }
        binary_level_names = {"levelAnimExport", "colExportLevel", "levelDLExport", "levelGeoExport"}
        old_custom_props = {"animCustomExport", "colCustomExport", "geoCustomExport", "DLCustomExport"}
        for scene in bpy.data.scenes:
            sm64_props: SM64_Properties = scene.fast64.sm64
            sm64_props.address_converter.upgrade_changed_props(scene)
            sm64_props.animation.upgrade_changed_props(scene)
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

            combined_props: SM64_CombinedObjectProperties = sm64_props.combined_export
            for new, old in old_export_props_to_new.items():
                upgrade_old_prop(combined_props, new, scene, old)

            insertable_directory = get_first_set_prop(scene, "animInsertableBinaryPath")
            if insertable_directory is not None:  # Ignores file name
                combined_props.insertable_directory = os.path.split(insertable_directory)[1]

            if get_first_set_prop(combined_props, old_custom_props):
                combined_props.export_header_type = "Custom"
            upgrade_old_prop(combined_props, "level_name", scene, binary_level_names, old_enum=OLD_BINARY_LEVEL_ENUMS)
            sm64_props.version = SM64_Properties.cur_version

    def to_repo_settings(self):
        data = {}
        data["refresh_version"] = self.refresh_version
        data["compression_format"] = self.compression_format
        data["force_extended_ram"] = self.force_extended_ram
        data["matstack_fix"] = self.matstack_fix
        if self.matstack_fix:
            data["lighting_engine_presets"] = self.lighting_engine_presets
        data["write_all"] = self.write_all
        if not self.hackersm64:
            data["designated"] = self.designated_prop
        data["actors_folder"] = self.actors_folder
        data["levels_folder"] = self.levels_folder
        data["dma_anims_folder"] = self.dma_anims_folder
        if self.custom_cmds:
            data["custom_cmds"] = [preset.to_dict("PRESET_EDIT") for preset in self.custom_cmds]
        return data

    def from_repo_settings(self, data: dict):
        set_prop_if_in_data(self, "refresh_version", data, "refresh_version")
        set_prop_if_in_data(self, "compression_format", data, "compression_format")
        set_prop_if_in_data(self, "force_extended_ram", data, "force_extended_ram")
        set_prop_if_in_data(self, "matstack_fix", data, "matstack_fix")
        set_prop_if_in_data(self, "lighting_engine_presets", data, "lighting_engine_presets")
        set_prop_if_in_data(self, "write_all", data, "write_all")
        set_prop_if_in_data(self, "designated_prop", data, "designated")
        set_prop_if_in_data(self, "actors_folder", data, "actors_folder")
        set_prop_if_in_data(self, "levels_folder", data, "levels_folder")
        set_prop_if_in_data(self, "dma_anims_folder", data, "dma_anims_folder")
        if "custom_cmds" in data:
            self.custom_cmds.clear()
            for preset_data in data.get("custom_cmds", []):
                self.custom_cmds.add()
                self.custom_cmds[-1].from_dict(preset_data)

    def draw_repo_settings(self, layout: UILayout):
        col = layout.column()
        if not self.binary_export:
            col.prop(self, "disable_scroll")
            prop_split(col, self, "compression_format", "Compression Format")
            prop_split(col, self, "refresh_version", "Refresh (Function Map)")
            col.prop(self, "force_extended_ram")
        col.prop(self, "matstack_fix")
        if self.matstack_fix:
            col.prop(self, "lighting_engine_presets")
        col.prop(self, "write_all")
        draw_directory(col, self, "actors_folder", name="Actors", base_dir=self.abs_decomp_path)
        draw_directory(col, self, "levels_folder", name="Levels", base_dir=self.abs_decomp_path)
        draw_directory(col, self, "dma_anims_folder", name="DMA Anims", base_dir=self.abs_decomp_path)
        draw_custom_cmd_presets(self, col.box())

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
            directory_ui_warnings(col, self.abs_decomp_path)
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
