import bpy

from bpy.utils import register_class, unregister_class
from bpy.types import Operator
from bpy.props import BoolProperty
from bpy.path import abspath

from ...operators import AddWaterBox
from ...utility import PluginError, checkExpanded, decodeSegmentedAddr, encodeSegmentedAddr, raisePluginError

from ..sm64_constants import level_pointers
from ..sm64_level_parser import parseLevelAtPointer
from ..sm64_geolayout_utility import createBoneGroups
from ..sm64_geolayout_parser import generateMetarig


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


class AddBoneGroups(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "Add bone groups respresenting other node types in " + "SM64 geolayouts (ex. Shadow, Switch, Function)."
    )
    bl_idname = "object.add_bone_groups"
    bl_label = "Add Bone Groups"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT" and context.mode != "POSE":
                raise PluginError("Operator can only be used in object or pose mode.")
            elif context.mode == "POSE":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            createBoneGroups(armatureObj)
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created bone groups.")
        return {"FINISHED"}  # must return a set


class CreateMetarig(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "SM64 imported armatures are usually not good for "
        + "rigging. There are often intermediate bones between deform bones "
        + "and they don't usually point to their children. This operator "
        + "creates a metarig on armature layer 4 useful for IK."
    )
    bl_idname = "object.create_metarig"
    bl_label = "Create Animatable Metarig"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            generateMetarig(armatureObj)
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created metarig.")
        return {"FINISHED"}  # must return a set


class SM64_AddWaterBox(AddWaterBox):
    bl_idname = "object.sm64_add_water_box"

    scale: bpy.props.FloatProperty(default=10)
    preset: bpy.props.StringProperty(default="Shaded Solid")
    matName: bpy.props.StringProperty(default="sm64_water_mat")

    def setEmptyType(self, emptyObj):
        emptyObj.sm64_obj_type = "Water Box"


classes = (
    SM64_AddrConv,
    AddBoneGroups,
    CreateMetarig,
    AddWaterBox,
)


def tools_operators_register():
    for cls in classes:
        register_class(cls)


def tools_operators_unregister():
    for cls in classes:
        unregister_class(cls)
