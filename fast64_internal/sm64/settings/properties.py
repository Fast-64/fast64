import os
import bpy
from bpy.types import PropertyGroup, UILayout, Scene, Context
from bpy.props import BoolProperty, StringProperty, EnumProperty, IntProperty, FloatProperty, PointerProperty
from bpy.path import abspath
from bpy.utils import register_class, unregister_class

from ...render_settings import on_update_render_settings
from ..sm64_constants import (
    level_enums,
    enum_refresh_versions,
    defaultExtendSegment4,
    enum_export_type,
    enum_compression_formats,
    enum_sm64_goal_type,
)
from ..sm64_utility import export_rom_checks, import_rom_checks
from ...utility import (
    directory_path_checks,
    directory_ui_warnings,
    multilineLabel,
    prop_split,
)


def decomp_path_update(self, context: Context):
    try:
        directory_path_checks(abspath(self.decomp_path))
        context.scene.fast64.settings.repo_settings_path = os.path.join(
            os.path.dirname(abspath(self.decomp_path)), "fast64.json"
        )
    except:
        return


class SM64_Properties(PropertyGroup):
    """Global SM64 Scene Properties found under scene.fast64.sm64"""

    version: IntProperty(name="SM64_Properties Version", default=0)
    cur_version = 2  # version after property migration

    # UI Selection
    show_importing_menus: BoolProperty(name="Show Importing Menus", default=False)
    export_type: EnumProperty(items=enum_export_type, name="Export Type", default="C")
    goal: EnumProperty(items=enum_sm64_goal_type, name="Goal", default="All")

    export_rom: StringProperty(name="Export ROM", subtype="FILE_PATH")
    output_rom: StringProperty(name="Output ROM", subtype="FILE_PATH")

    extend_bank_4: BoolProperty(
        name="Extend Bank 4 on Export?",
        default=True,
        description=f"\
Sets bank 4 range to ({hex(defaultExtendSegment4[0])}, {hex(defaultExtendSegment4[1])}) and copies data from old bank",
    )

    import_rom: StringProperty(name="Import ROM", subtype="FILE_PATH")
    convertible_addr: StringProperty(name="Address")
    level_convert: EnumProperty(items=level_enums, name="Level", default="IC")

    decomp_path: StringProperty(name="Decomp Folder", subtype="FILE_PATH", update=decomp_path_update)

    blender_to_sm64_scale: FloatProperty(name="Blender To SM64 Scale", default=100, update=on_update_render_settings)

    # C
    repo_settings_tab: bpy.props.BoolProperty(default=True)
    refresh_version: EnumProperty(items=enum_refresh_versions, name="Refresh", default="Refresh 13")
    compression_format: EnumProperty(items=enum_compression_formats, name="Compression", default="mio0")
    disable_scroll: BoolProperty(name="Disable Scrolling Textures")

    def is_binary_export(self):
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
        col.scale_y = 1.1

        prop_split(col, self, "goal", "Goal")
        prop_split(col, self, "export_type", "Export type")

        col.separator()

        prop_split(col, self, "blender_to_sm64_scale", "Blender To SM64 Scale")

        if self.export_type == "Binary":
            col.prop(self, "export_rom")
            try:
                export_rom_checks(abspath(self.export_rom))
            except Exception as e:
                multilineLabel(layout.box(), str(e), "ERROR")
            col.prop(self, "output_rom")
            col.prop(self, "extend_bank_4")
        elif not self.is_binary_export():
            # C and (in the future) glTF
            prop_split(col, self, "decomp_path", "Decomp Path")
            directory_ui_warnings(col, abspath(self.decomp_path))

        col.separator()

        if not self.is_binary_export():
            col.prop(self, "disable_scroll")
            if show_repo_settings:
                prop_split(col, self, "compression_format", "Compression Format")
                prop_split(col, self, "refresh_version", "Refresh (Function Map)")

        col.separator()

        col.prop(self, "show_importing_menus")
        if self.show_importing_menus:
            prop_split(col, self, "import_rom", "Import ROM")
            try:
                import_rom_checks(abspath(self.import_rom))
            except Exception as e:
                multilineLabel(layout.box(), str(e), "ERROR")


classes = (SM64_Properties,)


def settings_props_register():
    for cls in classes:
        register_class(cls)


def settings_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
