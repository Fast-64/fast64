import bpy

from bpy.utils import register_class, unregister_class
from bpy.types import Context, Object
from bpy.props import EnumProperty, BoolProperty, IntProperty, FloatProperty, StringProperty
from bpy.path import abspath

from ...operators import OperatorBase, AddWaterBox
from ...utility import PluginError, decodeSegmentedAddr, encodeSegmentedAddr
from ...f3d.f3d_material import getDefaultMaterialPreset, createF3DMat, add_f3d_mat_to_obj
from ...utility import parentObject, intToHex, bytesToHex

from ..sm64_constants import level_pointers, levelIDNames, level_enums
from ..sm64_utility import import_rom_checks, int_from_str
from ..sm64_level_parser import parseLevelAtPointer
from ..sm64_geolayout_utility import createBoneGroups
from ..sm64_geolayout_parser import generateMetarig

enum_address_conversion_options = [
    ("TO_VIR", "Segmented To Virtual", "Convert address from segmented to virtual"),
    ("TO_SEG", "Virtual To Segmented", "Convert address from virtual to segmented"),
]


class SM64_AddrConv(OperatorBase):
    bl_idname = "scene.sm64_addr_conv"
    bl_label = "Convert SM64 Address"
    bl_description = "Converts a segmented address to a virtual address or vice versa"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    rom: StringProperty(name="ROM", subtype="FILE_PATH")
    # Using an enum here looks cleaner when using this as an operator
    option: EnumProperty(name="Conversion type", items=enum_address_conversion_options)
    level: EnumProperty(items=level_enums, name="Level", default="IC")
    addr: StringProperty(name="Address")
    clipboard: BoolProperty(name="Copy to clipboard", default=True)
    result: StringProperty(name="Result")

    def execute_operator(self, context: Context):
        addr = int_from_str(self.addr)
        import_rom_path = abspath(self.rom)
        import_rom_checks(import_rom_path)
        with open(import_rom_path, "rb") as romfile:
            level_parsed = parseLevelAtPointer(romfile, level_pointers[self.level])
            segment_data = level_parsed.segmentData
        if self.option == "TO_VIR":
            result = intToHex(decodeSegmentedAddr(addr.to_bytes(4, "big"), segment_data))
            self.report({"INFO"}, f"Virtual pointer is {result}")
        elif self.option == "TO_SEG":
            result = bytesToHex(encodeSegmentedAddr(addr, segment_data))
            self.report({"INFO"}, f"Segmented pointer is {result}")
        else:
            raise NotImplementedError(f"Non implement conversion option {self.option}")
        self.result = result
        if self.clipboard:
            context.window_manager.clipboard = result


class SM64_AddBoneGroups(OperatorBase):
    bl_description = (
        "Add bone groups respresenting other node types in " + "SM64 geolayouts (ex. Shadow, Switch, Function)."
    )
    bl_idname = "object.add_bone_groups"
    bl_label = "Add Bone Groups"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "GROUP_BONE"

    def execute_operator(self, context: Context):
        if len(context.selected_objects) == 0:
            raise PluginError("Armature not selected.")
        elif len(context.selected_objects) > 1:
            raise PluginError("More than one object selected.")
        elif context.selected_objects[0].type != "ARMATURE":
            raise PluginError("Selected object is not an armature.")

        armature_obj: Object = context.selected_objects[0]
        createBoneGroups(armature_obj)

        self.report({"INFO"}, "Created bone groups.")


class SM64_CreateMetarig(OperatorBase):
    bl_description = (
        "SM64 imported armatures are usually not good for "
        + "rigging. There are often intermediate bones between deform bones "
        + "and they don't usually point to their children. This operator "
        + "creates a metarig on armature layer 4 useful for IK."
    )
    bl_idname = "object.sm64_create_metarig"
    bl_label = "Create Animatable Metarig"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "BONE_DATA"

    def execute_operator(self, context: Context):
        if len(context.selected_objects) == 0:
            raise PluginError("Armature not selected.")
        elif len(context.selected_objects) > 1:
            raise PluginError("More than one object selected.")
        elif context.selected_objects[0].type != "ARMATURE":
            raise PluginError("Selected object is not an armature.")

        armature_obj: Object = context.selected_objects[0]
        generateMetarig(armature_obj)

        self.report({"INFO"}, "Created metarig.")


def get_clean_obj_duplicate_name(name: str):
    objects = bpy.data.objects
    num = 1
    while (num == 1 and name in objects) or f"{name} {num}" in objects:
        num += 1
    if num > 1:
        name = f"{name} {num}"
    return name


def create_sm64_empty(
    name: str,
    obj_type: str,
    empty_type: str = "CUBE",
    location=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
) -> Object:
    bpy.ops.object.empty_add(type=empty_type, align="CURSOR", location=location, rotation=rotation)
    obj = bpy.context.view_layer.objects.active
    obj.name, obj.sm64_obj_type = get_clean_obj_duplicate_name(name), obj_type
    return obj


class SM64_CreateSimpleLevel(OperatorBase):
    bl_idname = "scene.sm64_create_simple_level"
    bl_label = "Create Level Layout"
    bl_description = "Creates a simple SM64 level layout"
    "with a user defined area amount and death plane"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "CUBE"

    area_amount: IntProperty(name="Area Amount", default=1, min=1, max=8)
    add_death_plane: BoolProperty(name="Add Death Plane")
    set_as_start_level: BoolProperty(name="Set As Start Level")
    respawn_in_level: BoolProperty(name="Respawn In The Same Level")

    def execute_operator(self, context: Context):
        scene = context.scene
        combined_export = scene.fast64.sm64.combined_export

        level_object = create_sm64_empty("Level", "Level Root", "PLAIN_AXES", (0, 0, 0))
        level_object.setAsStartLevel = self.set_as_start_level

        preset = getDefaultMaterialPreset("Shaded Solid")
        example_mat = createF3DMat(None, preset)

        example_mat.name = "Grass Example"
        example_mat.f3d_mat.default_light_color = (0, 1, 0, 1)
        example_mat.collision_type_simple = (
            example_mat.collision_type
        ) = example_mat.collision_custom = "SURFACE_NOISE_DEFAULT"

        preset = getDefaultMaterialPreset("Shaded Solid")

        if self.add_death_plane:
            death_mat = createF3DMat(None, preset)
            death_mat.name = "Death Plane"
            death_mat.collision_type_simple = (
                death_mat.collision_type
            ) = death_mat.collision_custom = "SURFACE_DEATH_PLANE"

        scale = context.scene.fast64.sm64.blender_to_sm64_scale
        mario_scale = (50 / scale, 50 / scale, 160 / 2 / scale)
        mario_height = mario_scale[2]

        for i in range(self.area_amount):
            y_offset = 4000 / scale * i
            location_offset = (0, y_offset, 0)

            area_num = i + 1
            area_object = create_sm64_empty(f"Area {area_num}", "Area Root", "PLAIN_AXES", location_offset)
            area_object.areaIndex = area_num

            custom_level_id = "LEVEL_BOB"
            for key, value in levelIDNames.items():
                if value == combined_export.level_name:
                    custom_level_id = key

            area_object.warpNodes.add()
            area_object.warpNodes[-1].warpID = "0x0A"  # Spin warp
            area_object.warpNodes[-1].destLevel = custom_level_id
            area_object.warpNodes[-1].destLevelEnum = combined_export.export_level_name
            area_object.warpNodes[-1].destNode = "0x0A"

            area_object.warpNodes.add()
            area_object.warpNodes[-1].warpID = "0xF0"  # Default
            area_object.warpNodes[-1].destLevelEnum = "castle_inside"
            area_object.warpNodes[-1].destNode = "0x32"

            area_object.warpNodes.add()
            area_object.warpNodes[-1].warpID = "0xF1"  # Death
            if self.respawn_in_level:
                area_object.warpNodes[-1].destLevelEnum = combined_export.export_level_name
                area_object.warpNodes[-1].destLevel = custom_level_id
                area_object.warpNodes[-1].destNode = "0x0A"
            else:
                area_object.warpNodes[-1].destLevelEnum = "castle_inside"
                area_object.warpNodes[-1].destNode = "0x64"

            parentObject(level_object, area_object)

            bpy.ops.mesh.primitive_plane_add(
                size=1000 / scale, align="CURSOR", location=location_offset, rotation=(0, 0, 0)
            )
            plane_object = context.view_layer.objects.active
            plane_object.name = get_clean_obj_duplicate_name("Level Mesh")
            plane_object.data.name = "Mesh"
            add_f3d_mat_to_obj(plane_object, example_mat)
            parentObject(area_object, plane_object)

            if self.add_death_plane:
                bpy.ops.mesh.primitive_plane_add(
                    size=2500 / scale, align="CURSOR", location=(0, y_offset, -2500 / scale), rotation=(0, 0, 0)
                )
                death_plane_obj = context.view_layer.objects.active
                death_plane_obj.name = get_clean_obj_duplicate_name("(Collision Only) Death Plane")
                death_plane_obj.data.name = "Death Plane"
                death_plane_obj.ignore_render = True
                add_f3d_mat_to_obj(death_plane_obj, death_mat)
                parentObject(area_object, death_plane_obj)

            if i == 0:
                mario_start_object = create_sm64_empty(
                    "Hardcoded Level Start Position", "Mario Start", location=(0, y_offset, mario_height)
                )
                mario_start_object.scale = mario_scale
                parentObject(area_object, mario_start_object)

            warp_object = create_sm64_empty("Warp", "Object", location=(0, y_offset, mario_height))
            parentObject(area_object, warp_object)
            warp_object.scale = mario_scale
            warp_object.sm64_behaviour_enum, warp_object.sm64_obj_behaviour = "13002f74", "bhvSpinAirborneWarp"
            warp_game_object = warp_object.fast64.sm64.game_object
            warp_game_object.use_individual_params = True
            warp_game_object.bparam2 = "0x0A"
            warp_game_object.bparams = "0x000A0000"

        bpy.ops.object.select_all(action="DESELECT")
        level_object.select_set(True)
        bpy.context.view_layer.objects.active = level_object


class SM64_AddWaterBox(AddWaterBox):
    bl_idname = "object.sm64_add_water_box"

    scale: FloatProperty(default=10)
    preset: StringProperty(default="Shaded Solid")
    matName: StringProperty(default="sm64_water_mat")

    def setEmptyType(self, empty_object: Object):
        empty_object.sm64_obj_type = "Water Box"


classes = (
    SM64_AddrConv,
    SM64_CreateSimpleLevel,
    SM64_AddBoneGroups,
    SM64_CreateMetarig,
    SM64_AddWaterBox,
)


def tools_operators_register():
    for cls in classes:
        register_class(cls)


def tools_operators_unregister():
    for cls in classes:
        unregister_class(cls)
