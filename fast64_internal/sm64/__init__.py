import bpy
from bpy.types import Operator, PropertyGroup, Scene
from bpy.props import BoolProperty, StringProperty, EnumProperty, IntProperty, FloatProperty
from bpy.utils import register_class, unregister_class
from bpy.path import abspath
from ..panels import SM64_Panel, sm64GoalTypeEnum, sm64GoalImport
from ..render_settings import on_update_render_settings
from .sm64_level_parser import parseLevelAtPointer
from .sm64_constants import level_enums, level_pointers, defaultExtendSegment4

from ..utility import (
    prop_split,
    checkExpanded,
    decodeSegmentedAddr,
    encodeSegmentedAddr,
    raisePluginError,
    enumExportType,
    enumCompressionFormat,
)

from .sm64_collision import (
    sm64_col_panel_register,
    sm64_col_panel_unregister,
    sm64_col_register,
    sm64_col_unregister,
)

from .sm64_geolayout_bone import (
    sm64_bone_panel_register,
    sm64_bone_panel_unregister,
    sm64_bone_register,
    sm64_bone_unregister,
)

from .sm64_camera import (
    sm64_cam_panel_register,
    sm64_cam_panel_unregister,
    sm64_cam_register,
    sm64_cam_unregister,
)

from .sm64_objects import (
    sm64_obj_panel_register,
    sm64_obj_panel_unregister,
    sm64_obj_register,
    sm64_obj_unregister,
)

from .sm64_geolayout_parser import (
    sm64_geo_parser_panel_register,
    sm64_geo_parser_panel_unregister,
    sm64_geo_parser_register,
    sm64_geo_parser_unregister,
)

from .sm64_geolayout_writer import (
    sm64_geo_writer_panel_register,
    sm64_geo_writer_panel_unregister,
    sm64_geo_writer_register,
    sm64_geo_writer_unregister,
)

from .sm64_level_writer import (
    sm64_level_panel_register,
    sm64_level_panel_unregister,
    sm64_level_register,
    sm64_level_unregister,
)

from .sm64_spline import (
    sm64_spline_panel_register,
    sm64_spline_panel_unregister,
    sm64_spline_register,
    sm64_spline_unregister,
)

from .sm64_f3d_parser import (
    sm64_dl_parser_panel_register,
    sm64_dl_parser_panel_unregister,
    sm64_dl_parser_register,
    sm64_dl_parser_unregister,
)

from .sm64_f3d_writer import (
    sm64_dl_writer_panel_register,
    sm64_dl_writer_panel_unregister,
    sm64_dl_writer_register,
    sm64_dl_writer_unregister,
)

from .sm64_anim import (
    sm64_anim_panel_register,
    sm64_anim_panel_unregister,
    sm64_anim_register,
    sm64_anim_unregister,
)


enumRefreshVer = [
    ("Refresh 3", "Refresh 3", "Refresh 3"),
    ("Refresh 4", "Refresh 4", "Refresh 4"),
    ("Refresh 5", "Refresh 5", "Refresh 5"),
    ("Refresh 6", "Refresh 6", "Refresh 6"),
    ("Refresh 7", "Refresh 7", "Refresh 7"),
    ("Refresh 8", "Refresh 8", "Refresh 8"),
    ("Refresh 10", "Refresh 10", "Refresh 10"),
    ("Refresh 11", "Refresh 11", "Refresh 11"),
    ("Refresh 12", "Refresh 12", "Refresh 12"),
    ("Refresh 13", "Refresh 13", "Refresh 13"),
]


class SM64_AddrConv(Operator):
    # set bl_ properties
    bl_idname = "object.addr_conv"
    bl_label = "Convert Address"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    segToVirt: BoolProperty()

    def execute(self, context):
        romfileSrc = None
        try:
            address = int(context.scene.convertibleAddr, 16)
            importRom = context.scene.importRom
            romfileSrc = open(abspath(importRom), "rb")
            checkExpanded(abspath(importRom))
            levelParsed = parseLevelAtPointer(romfileSrc, level_pointers[context.scene.levelConvert])
            segmentData = levelParsed.segmentData
            if self.segToVirt:
                ptr = decodeSegmentedAddr(address.to_bytes(4, "big"), segmentData)
                self.report({"INFO"}, "Virtual pointer is 0x" + format(ptr, "08X"))
            else:
                ptr = int.from_bytes(encodeSegmentedAddr(address, segmentData), "big")
                self.report({"INFO"}, "Segmented pointer is 0x" + format(ptr, "08X"))
            romfileSrc.close()
            return {"FINISHED"}
        except Exception as e:
            if romfileSrc is not None:
                romfileSrc.close()
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


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


class SM64_AddressConvertPanel(SM64_Panel):
    bl_idname = "SM64_PT_addr_conv"
    bl_label = "SM64 Address Converter"
    goal = sm64GoalImport

    def draw(self, context):
        col = self.layout.column()
        segToVirtOp = col.operator(SM64_AddrConv.bl_idname, text="Convert Segmented To Virtual")
        segToVirtOp.segToVirt = True
        virtToSegOp = col.operator(SM64_AddrConv.bl_idname, text="Convert Virtual To Segmented")
        virtToSegOp.segToVirt = False
        prop_split(col, context.scene, "convertibleAddr", "Address")
        col.prop(context.scene, "levelConvert")


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


sm64_classes = (
    SM64_AddrConv,
    SM64_Properties,
)

sm64_panel_classes = (
    SM64_MenuVisibilityPanel,
    SM64_FileSettingsPanel,
    SM64_AddressConvertPanel,
)


def sm64_panel_register():
    for cls in sm64_panel_classes:
        register_class(cls)

    sm64_col_panel_register()
    sm64_bone_panel_register()
    sm64_cam_panel_register()
    sm64_obj_panel_register()
    sm64_geo_parser_panel_register()
    sm64_geo_writer_panel_register()
    sm64_level_panel_register()
    sm64_spline_panel_register()
    sm64_dl_writer_panel_register()
    sm64_dl_parser_panel_register()
    sm64_anim_panel_register()


def sm64_panel_unregister():
    for cls in sm64_panel_classes:
        unregister_class(cls)

    sm64_col_panel_unregister()
    sm64_bone_panel_unregister()
    sm64_cam_panel_unregister()
    sm64_obj_panel_unregister()
    sm64_geo_parser_panel_unregister()
    sm64_geo_writer_panel_unregister()
    sm64_level_panel_unregister()
    sm64_spline_panel_unregister()
    sm64_dl_writer_panel_unregister()
    sm64_dl_parser_panel_unregister()
    sm64_anim_panel_unregister()


def sm64_register(registerPanels):
    for cls in sm64_classes:
        register_class(cls)

    sm64_col_register()  # register first, so panel goes above mat panel
    sm64_bone_register()
    sm64_cam_register()
    sm64_obj_register()
    sm64_geo_parser_register()
    sm64_geo_writer_register()
    sm64_level_register()
    sm64_spline_register()
    sm64_dl_writer_register()
    sm64_dl_parser_register()
    sm64_anim_register()

    if registerPanels:
        sm64_panel_register()

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


def sm64_unregister(unregisterPanels):
    for cls in reversed(sm64_classes):
        unregister_class(cls)

    sm64_col_unregister()  # register first, so panel goes above mat panel
    sm64_bone_unregister()
    sm64_cam_unregister()
    sm64_obj_unregister()
    sm64_geo_parser_unregister()
    sm64_geo_writer_unregister()
    sm64_level_unregister()
    sm64_spline_unregister()
    sm64_dl_writer_unregister()
    sm64_dl_parser_unregister()
    sm64_anim_unregister()

    if unregisterPanels:
        sm64_panel_unregister()

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
