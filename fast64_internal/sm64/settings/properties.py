import bpy
from bpy.types import PropertyGroup, Scene
from bpy.props import BoolProperty, StringProperty, EnumProperty, IntProperty, FloatProperty
from bpy.utils import register_class, unregister_class

from ...render_settings import on_update_render_settings
from ..sm64_constants import (
    level_enums,
    defaultExtendSegment4,
)
from .constants import enumRefreshVer, enumExportType, enumCompressionFormat, sm64GoalTypeEnum

def get_legacy_export_type():
    legacy_export_types = ("C", "Binary", "Insertable Binary")
    scene = bpy.context.scene

    for exportKey in ["animExportType", "colExportType", "DLExportType", "geoExportType"]:
        eType = scene.pop(exportKey, None)
        if eType is not None and legacy_export_types[eType] != "C":
            return legacy_export_types[eType]

    return "C"


class SM64_Properties(PropertyGroup):
    """Global SM64 Scene Properties found under scene.fast64.sm64"""

    version: IntProperty(name="SM64_Properties Version", default=0)
    cur_version = 1  # version after property migration

    # UI Selection
    showImportingMenus: BoolProperty(name="Show Importing Menus", default=False)
    exportType: EnumProperty(items=enumExportType, name="Export Type", default="C")
    goal: EnumProperty(items=sm64GoalTypeEnum, name="Export Goal", default="All")

    # TODO: Utilize these across all exports
    # C exporting
    # useCustomExportLocation = BoolProperty(name = 'Use Custom Export Path')
    # customExportPath: StringProperty(name = 'Custom Export Path', subtype = 'FILE_PATH')
    # exportLocation: EnumProperty(items = enumExportHeaderType, name = 'Export Location', default = 'Actor')
    # useSelectedObjectName = BoolProperty(name = 'Use Name From Selected Object', default=False)
    # exportName: StringProperty(name='Name', default='mario')
    # exportGeolayoutName: StringProperty(name='Name', default='mario_geo')

    # Actor exports
    # exportGroup: StringProperty(name='Group', default='group0')

    # Level exports
    # exportLevelName: StringProperty(name = 'Level', default = 'bob')
    # exportLevelOption: EnumProperty(items = enumLevelNames, name = 'Level', default = 'bob')

    # Insertable Binary
    # exportInsertableBinaryPath: StringProperty(name = 'Filepath', subtype = 'FILE_PATH')

    @staticmethod
    def upgrade_changed_props():
        if bpy.context.scene.fast64.sm64.version != SM64_Properties.cur_version:
            bpy.context.scene.fast64.sm64.exportType = get_legacy_export_type()
            bpy.context.scene.fast64.sm64.version = SM64_Properties.cur_version


classes = (SM64_Properties,)


def settings_props_register():
    for cls in classes:
        register_class(cls)

    Scene.importRom = StringProperty(name="Import ROM", subtype="FILE_PATH")
    Scene.exportRom = StringProperty(name="Export ROM", subtype="FILE_PATH")
    Scene.outputRom = StringProperty(name="Output ROM", subtype="FILE_PATH")
    Scene.extendBank4 = BoolProperty(
        name="Extend Bank 4 on Export?",
        default=True,
        description="Sets bank 4 range to ("
        + hex(defaultExtendSegment4[0])
        + ", "
        + hex(defaultExtendSegment4[1])
        + ") and copies data from old bank",
    )
    Scene.convertibleAddr = StringProperty(name="Address")
    Scene.levelConvert = EnumProperty(items=level_enums, name="Level", default="IC")
    Scene.refreshVer = EnumProperty(items=enumRefreshVer, name="Refresh", default="Refresh 13")
    Scene.disableScroll = BoolProperty(name="Disable Scrolling Textures")
    Scene.blenderToSM64Scale = FloatProperty(
        name="Blender To SM64 Scale", default=100, update=on_update_render_settings
    )
    Scene.decompPath = StringProperty(name="Decomp Folder", subtype="FILE_PATH")

    Scene.compressionFormat = EnumProperty(items=enumCompressionFormat, name="Compression", default="mio0")


def settings_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    del Scene.importRom
    del Scene.exportRom
    del Scene.outputRom
    del Scene.extendBank4

    del Scene.convertibleAddr
    del Scene.levelConvert
    del Scene.refreshVer

    del Scene.disableScroll

    del Scene.blenderToSM64Scale
    del Scene.decompPath
    del Scene.compressionFormat
