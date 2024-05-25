import os
import bpy
from bpy.types import PropertyGroup, UILayout, Scene, Context
from bpy.props import BoolProperty, StringProperty, EnumProperty, IntProperty, FloatProperty, PointerProperty
from bpy.path import abspath
from bpy.utils import register_class, unregister_class

from ...render_settings import on_update_render_settings
from ...utility import directory_path_checks, directory_ui_warnings, prop_split
from ..sm64_constants import defaultExtendSegment4
from ..sm64_utility import export_rom_ui_warnings, import_rom_ui_warnings
from ..tools import SM64_AddrConvProperties

from .constants import (
    enum_refresh_versions,
    enum_compression_formats,
    enum_export_type,
    enum_sm64_goal_type,
)


def decomp_path_update(self, context: Context):
    directory_path_checks(abspath(self.decomp_path))
    context.scene.fast64.settings.repo_settings_path = os.path.join(abspath(self.decomp_path), "fast64.json")


class SM64_Properties(PropertyGroup):
    """Global SM64 Scene Properties found under scene.fast64.sm64"""

    version: IntProperty(name="SM64_Properties Version", default=0)
    cur_version = 2  # version after property migration

    # UI Selection
    show_importing_menus: BoolProperty(name="Show Importing Menus", default=False)
    export_type: EnumProperty(items=enum_export_type, name="Export Type", default="C")
    goal: EnumProperty(items=enum_sm64_goal_type, name="Goal", default="All")

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
    refresh_version: EnumProperty(items=enum_refresh_versions, name="Refresh", default="Refresh 13")
    compression_format: EnumProperty(
        items=enum_compression_formats,
        name="Compression",
        default="mio0",
    )
    force_extended_ram: BoolProperty(name="Force Extended Ram", default=True)
    matstack_fix: BoolProperty(
        name="Matstack Fix",
        description="Exports account for matstack fix requirements",
    )

    @property
    def binary_export(self):
        return self.export_type in ["Binary", "Insertable Binary"]

    def get_legacy_export_type(self, scene: Scene):
        legacy_export_types = ("C", "Binary", "Insertable Binary")

        for export_key in ["animExportType", "colExportType", "DLExportType", "geoExportType"]:
            export_type = legacy_export_types[scene.get(export_key, 0)]
            if export_type != "C":
                return export_type

        return "C"

    def upgrade_version_1(self, scene: Scene):
        old_scene_props_to_new = {
            "importRom": "import_rom",
            "exportRom": "export_rom",
            "outputRom": "output_rom",
            "convertibleAddr": "convertible_addr",
            "levelConvert": "level_convert",
            "disableScroll": "disable_scroll",
            "blenderToSM64Scale": "blender_to_sm64_scale",
            "decompPath": "decomp_path",
            "extendBank4": "extend_bank_4",
        }
        for old, new in old_scene_props_to_new.items():
            setattr(self, new, scene.get(old, getattr(self, new)))

        refresh_version = scene.get("refreshVer", None)
        if refresh_version is not None:
            self.refresh_version = enum_refresh_versions[refresh_version][0]

        self.show_importing_menus = self.get("showImportingMenus", self.show_importing_menus)

        export_type = self.get("exportType", None)
        if export_type is not None:
            self.export_type = enum_export_type[export_type][0]

        self.version = 2

    @staticmethod
    def upgrade_changed_props():
        for scene in bpy.data.scenes:
            sm64_props: SM64_Properties = scene.fast64.sm64
            if sm64_props.version == 0:
                sm64_props.export_type = sm64_props.get_legacy_export_type(scene)
                print("Upgraded global SM64 settings to version 1")
            if sm64_props.version == 1:
                sm64_props.upgrade_version_1(scene)
                print("Upgraded global SM64 settings to version 2")

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

        if not self.binary_export:
            col.prop(self, "disable_scroll")
            if show_repo_settings:
                prop_split(col, self, "compression_format", "Compression Format")
                prop_split(col, self, "refresh_version", "Refresh (Function Map)")
                col.prop(self, "force_extended_ram")
                col.prop(self, "matstack_fix")
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
