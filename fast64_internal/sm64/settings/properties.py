import bpy
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, EnumProperty, IntProperty
from bpy.utils import register_class, unregister_class

from .constants import enumExportType, sm64GoalTypeEnum


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


def settings_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
