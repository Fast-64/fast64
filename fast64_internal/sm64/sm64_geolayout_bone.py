import bpy
from bpy.utils import register_class, unregister_class
from .sm64_geolayout_utility import createBoneGroups, addBoneToGroup
from ..utility import prop_split, PluginError
from ..f3d.f3d_material import *

enumBoneType = [
    ("Switch", "Switch (0x0E)", "Switch"),
    ("Start", "Start (0x0B)", "Start"),
    ("TranslateRotate", "Translate Rotate (0x10)", "Translate Rotate"),
    ("Translate", "Translate (0x11)", "Translate"),
    ("Rotate", "Rotate (0x12)", "Rotate"),
    ("Billboard", "Billboard (0x14)", "Billboard"),
    ("DisplayList", "Display List (0x15)", "Display List"),
    ("Shadow", "Shadow (0x16)", "Shadow"),
    ("Function", "Function (0x18)", "Function"),
    ("HeldObject", "Held Object (0x1C)", "Held Object"),
    ("Scale", "Scale (0x1D)", "Scale"),
    ("StartRenderArea", "Start Render Area (0x20)", "Start Render Area"),
    ("Ignore", "Ignore", "Ignore bones when exporting."),
    ("SwitchOption", "Switch Option", "Switch Option"),
    ("DisplayListWithOffset", "Animated Part (0x13)", "Animated Part (Animatable Bone)"),
    ("CustomAnimated", "Custom Animated", "Custom Bone used for animation"),
    ("CustomNonAnimated", "Custom (Non-animated)", "Custom geolayout bone, non animated"),
]

animatableBoneTypes = {"DisplayListWithOffset", "CustomAnimated"}

enumGeoStaticType = [
    ("Billboard", "Billboard (0x14)", "Billboard"),
    ("DisplayListWithOffset", "Animated Part (0x13)", "Animated Part (Animatable Bone)"),
    ("Optimal", "Optimal", "Optimal"),
]

enumFieldLayout = [
    ("0", "Translate And Rotate", "Translate And Rotate"),
    ("1", "Translate", "Translate"),
    ("2", "Rotate", "Rotate"),
    # ('3', 'Rotate Y', 'Rotate Y'),
    # Rotate Y complicates exporting code, so we treat it as Rotate.
]

enumShadowType = [
    ("0", "Circle Scalable (9 verts)", "Circle Scalable (9 verts)"),
    ("1", "Circle Scalable (4 verts)", "Circle Scalable (4 verts)"),
    ("2", "Circle Permanent (4 verts)", "Circle Permanent (4 verts)"),
    ("10", "Square Permanent", "Square Permanent"),
    ("11", "Square Scalable", "Square Scalable"),
    ("12", "Square Togglable", "Square Togglable"),
    ("50", "Rectangle", "Rectangle"),
    ("99", "Circle Player", "Circle Player"),
]

enumSwitchOptions = [
    ("Mesh", "Mesh Override", "Switch to a different mesh hierarchy."),
    (
        "Material",
        "Material Override",
        "Use the same mesh hierarchy, but override material on ALL meshes. Optionally override draw layer.",
    ),
    ("Draw Layer", "Draw Layer Override", "Override draw layer only."),
]

enumMatOverrideOptions = [
    ("All", "All", "Override every material with this one."),
    ("Specific", "Specific", "Only override instances of give material."),
]


def drawGeoInfo(panel: bpy.types.Panel, bone: bpy.types.Bone):

    panel.layout.box().label(text="Geolayout Inspector")
    if bone is None:
        panel.layout.label(text="Edit geolayout properties in Pose mode.")
        return

    col = panel.layout.column()

    prop_split(col, bone, "geo_cmd", "Geolayout Command")

    if bone.geo_cmd in [
        "TranslateRotate",
        "Translate",
        "Rotate",
        "Billboard",
        "DisplayList",
        "Scale",
        "DisplayListWithOffset",
        "CustomAnimated",
    ]:
        drawLayerWarningBox(col, bone, "draw_layer")

    if bone.geo_cmd == "Scale":
        prop_split(col, bone, "geo_scale", "Scale")

    elif bone.geo_cmd == "HeldObject":
        prop_split(col, bone, "geo_func", "Function")

    elif bone.geo_cmd == "Switch":
        prop_split(col, bone, "geo_func", "Function")
        prop_split(col, bone, "func_param", "Parameter")
        col.label(text="Switch Option 0 is always this bone's children.")
        col.operator(AddSwitchOption.bl_idname).option = len(bone.switch_options)
        for i in range(len(bone.switch_options)):
            drawSwitchOptionProperty(col, bone.switch_options[i], i)

    elif bone.geo_cmd == "Function":
        prop_split(col, bone, "geo_func", "Function")
        prop_split(col, bone, "func_param", "Parameter")
        infoBox2 = col.box()
        infoBox2.label(text="This affects the next sibling bone in " + "alphabetical order.")

    elif bone.geo_cmd == "TranslateRotate":
        prop_split(col, bone, "field_layout", "Field Layout")

    elif bone.geo_cmd == "Shadow":
        prop_split(col, bone, "shadow_type", "Type")
        prop_split(col, bone, "shadow_solidity", "Alpha")
        prop_split(col, bone, "shadow_scale", "Scale")

    elif bone.geo_cmd == "StartRenderArea":
        infoBoxRenderArea = col.box()
        infoBoxRenderArea.label(text="WARNING: This command is deprecated for bones.")
        infoBoxRenderArea.label(text="See the object properties window for the armature instead.")
        prop_split(col, bone, "culling_radius", "Culling Radius")

    elif bone.geo_cmd in {"CustomAnimated", "CustomNonAnimated"}:
        prop_split(col, bone.fast64.sm64, "custom_geo_cmd_macro", "Geo Command Macro")
        if bone.geo_cmd == "CustomNonAnimated":
            prop_split(col, bone.fast64.sm64, "custom_geo_cmd_args", "Geo Command Args")
        else:  # It's animated
            infobox = col.box()
            infobox.label(text="Command's args will be filled with layer, translate, and rotate", icon="INFO")
            infobox.label(text="e.g. `GEO_CUSTOM(layer, tX, tY, tZ, rX, rY, rZ, displayList)`")

    # if bone.geo_cmd == 'SwitchOption':
    # 	prop_split(col, bone, 'switch_bone', 'Switch Bone')

    layerInfoBox = panel.layout.box()
    layerInfoBox.label(text="Regular bones (0x13) are on armature layer 0.")
    layerInfoBox.label(text="Other bones are on armature layer 1.")
    layerInfoBox.label(text="'Ignore' bones are on any layer.")


class GeolayoutBonePanel(bpy.types.Panel):
    bl_label = "Geolayout Inspector"
    bl_idname = "BONE_PT_SM64_Geolayout_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "SM64"

    def draw(self, context):
        drawGeoInfo(self, context.bone)


class GeolayoutArmaturePanel(bpy.types.Panel):
    bl_label = "Geolayout Armature Inspector"
    bl_idname = "OBJECT_PT_SM64_Armature_Geolayout_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene.gameEditorMode == "SM64"
            and context.object is not None
            and isinstance(context.object.data, bpy.types.Armature)
        )

    def draw(self, context):
        obj = context.object
        col = self.layout.column().box()
        col.box().label(text="Armature Geolayout Inspector")

        col.prop(obj, "use_render_area")
        if obj.use_render_area:
            col.box().label(text="This is in blender units.")
            prop_split(col, obj, "culling_radius", "Culling Radius")


def drawLayerWarningBox(layout, prop, data):
    warningBox = layout.box().column()
    prop_split(warningBox, prop, data, "Draw Layer (v3)")
    warningBox.label(text="This applies to v3 materials and down only.", icon="LOOP_FORWARDS")
    warningBox.label(text="This is moved to material settings in v4+.")


class GeolayoutObjectPanel(bpy.types.Panel):
    bl_label = "Object Geolayout Inspector"
    bl_idname = "OBJECT_PT_SM64_Object_Geolayout_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene.gameEditorMode == "SM64"
            and context.object is not None
            and isinstance(context.object.data, bpy.types.Mesh)
        )

    def draw(self, context):
        obj = context.object
        col = self.layout.column().box()
        col.box().label(text="Object Geolayout Inspector")

        prop_split(col, obj, "geo_cmd_static", "Geolayout Command")
        drawLayerWarningBox(col, obj, "draw_layer_static")
        col.prop(obj, "use_render_area")
        if obj.use_render_area:
            renderAreaBox = col.box()
            renderAreaBox.label(text="This is in blender units.")
            renderAreaBox.label(text="This only applies if this is the root object of an object geolayout.")
            renderAreaBox.label(text="For armature geolayouts, see the armature's object properties instead.")
            prop_split(col, obj, "culling_radius", "Culling Radius")
        col.prop(obj, "use_render_range")
        if obj.use_render_range:
            col.box().label(text="This is in blender units.")
            prop_split(col, obj, "render_range", "Render Range")
        col.prop(obj, "add_shadow")
        if obj.add_shadow:
            prop_split(col, obj, "shadow_type", "Type")
            prop_split(col, obj, "shadow_solidity", "Alpha")
            prop_split(col, obj, "shadow_scale", "Scale")
        col.prop(obj, "add_func")
        if obj.add_func:
            geo_asm = obj.fast64.sm64.geo_asm
            prop_split(col, geo_asm, "func", "Function")
            prop_split(col, geo_asm, "param", "Parameter")
        col.prop(obj, "ignore_render")
        col.prop(obj, "ignore_collision")
        col.prop(obj, "use_f3d_culling")
        if obj_scale_is_unified(obj) and len(obj.modifiers) == 0:
            col.prop(obj, "scaleFromGeolayout")
        # prop_split(col, obj, 'room_num', 'Room')


class MaterialPointerProperty(bpy.types.PropertyGroup):
    material: bpy.props.PointerProperty(type=bpy.types.Material)


class SwitchOptionProperty(bpy.types.PropertyGroup):
    switchType: bpy.props.EnumProperty(name="Option Type", items=enumSwitchOptions)
    optionArmature: bpy.props.PointerProperty(name="Option Armature", type=bpy.types.Object)
    materialOverride: bpy.props.PointerProperty(type=bpy.types.Material, name="Material Override")
    materialOverrideType: bpy.props.EnumProperty(name="Material Override Type", items=enumMatOverrideOptions)
    specificOverrideArray: bpy.props.CollectionProperty(
        type=MaterialPointerProperty, name="Specified Materials To Override"
    )
    specificIgnoreArray: bpy.props.CollectionProperty(
        type=MaterialPointerProperty, name="Specified Materials To Ignore"
    )
    overrideDrawLayer: bpy.props.BoolProperty()
    drawLayer: bpy.props.EnumProperty(items=sm64EnumDrawLayers, name="Draw Layer")
    expand: bpy.props.BoolProperty()


def drawSwitchOptionProperty(layout, switchOption, index):
    box = layout.box()
    # box.box().label(text = 'Switch Option ' + str(index + 1))
    box.prop(
        switchOption,
        "expand",
        text="Switch Option " + str(index + 1),
        icon="TRIA_DOWN" if switchOption.expand else "TRIA_RIGHT",
    )
    if switchOption.expand:
        prop_split(box, switchOption, "switchType", "Type")
        if switchOption.switchType == "Material":
            prop_split(box, switchOption, "materialOverride", "Material")
            prop_split(box, switchOption, "materialOverrideType", "Material Override Type")
            if switchOption.materialOverrideType == "Specific":
                matArrayBox = box.box()
                matArrayBox.label(text="Specified Materials To Override")
                drawMatArray(matArrayBox, index, switchOption, switchOption.specificOverrideArray, True)
            else:
                matArrayBox = box.box()
                matArrayBox.label(text="Specified Materials To Ignore")
                drawMatArray(matArrayBox, index, switchOption, switchOption.specificIgnoreArray, False)
            prop_split(box, switchOption, "overrideDrawLayer", "Override Draw Layer")
            if switchOption.overrideDrawLayer:
                prop_split(box, switchOption, "drawLayer", "Draw Layer")
        elif switchOption.switchType == "Draw Layer":
            prop_split(box, switchOption, "drawLayer", "Draw Layer")
        else:
            prop_split(box, switchOption, "optionArmature", "Option Armature")
        buttons = box.row(align=True)
        buttons.operator(RemoveSwitchOption.bl_idname, text="Remove Option").option = index
        buttons.operator(AddSwitchOption.bl_idname, text="Add Option").option = index + 1

        moveButtons = box.row(align=True)
        moveUp = moveButtons.operator(MoveSwitchOption.bl_idname, text="Move Up")
        moveUp.option = index
        moveUp.offset = -1
        moveDown = moveButtons.operator(MoveSwitchOption.bl_idname, text="Move Down")
        moveDown.option = index
        moveDown.offset = 1


def drawMatArray(layout, option, switchOption, matArray, isSpecific):
    addOp = layout.operator(AddSwitchOptionMat.bl_idname, text="Add Material")
    addOp.option = option
    addOp.isSpecific = isSpecific

    for i in range(len(matArray)):
        drawMatArrayProperty(layout, matArray[i], option, i, isSpecific)


def drawMatArrayProperty(layout, materialPointer, option, index, isSpecific):
    row = layout.box().row()
    row.prop(materialPointer, "material", text="")
    removeOp = row.operator(RemoveSwitchOptionMat.bl_idname, text="Remove Material")
    removeOp.option = option
    removeOp.index = index
    removeOp.isSpecific = isSpecific


class AddSwitchOptionMat(bpy.types.Operator):
    bl_idname = "bone.add_switch_option_mat"
    bl_label = "Add Switch Option Material"
    bl_options = {"REGISTER", "UNDO"}
    option: bpy.props.IntProperty()
    isSpecific: bpy.props.BoolProperty()

    def execute(self, context):
        bone = context.bone
        if self.isSpecific:
            bone.switch_options[self.option].specificOverrideArray.add()
        else:
            bone.switch_options[self.option].specificIgnoreArray.add()
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class RemoveSwitchOptionMat(bpy.types.Operator):
    bl_idname = "bone.remove_switch_option_mat"
    bl_label = "Remove Switch Option Material"
    bl_options = {"REGISTER", "UNDO"}
    option: bpy.props.IntProperty()
    index: bpy.props.IntProperty()
    isSpecific: bpy.props.BoolProperty()

    def execute(self, context):
        if self.isSpecific:
            context.bone.switch_options[self.option].specificOverrideArray.remove(self.index)
        else:
            context.bone.switch_options[self.option].specificIgnoreArray.remove(self.index)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class AddSwitchOption(bpy.types.Operator):
    bl_idname = "bone.add_switch_option"
    bl_label = "Add Switch Option"
    bl_options = {"REGISTER", "UNDO"}
    option: bpy.props.IntProperty()

    def execute(self, context):
        bone = context.bone
        bone.switch_options.add()
        bone.switch_options.move(len(bone.switch_options) - 1, self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class RemoveSwitchOption(bpy.types.Operator):
    bl_idname = "bone.remove_switch_option"
    bl_label = "Remove Switch Option"
    bl_options = {"REGISTER", "UNDO"}
    option: bpy.props.IntProperty()

    def execute(self, context):
        context.bone.switch_options.remove(self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class MoveSwitchOption(bpy.types.Operator):
    bl_idname = "bone.move_switch_option"
    bl_label = "Move Switch Option"
    bl_options = {"REGISTER", "UNDO"}
    option: bpy.props.IntProperty()
    offset: bpy.props.IntProperty()

    def execute(self, context):
        bone = context.bone
        bone.switch_options.move(self.option, self.option + self.offset)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


"""
class GeolayoutBoneSidePanel(bpy.types.Panel):
	bl_idname = "SM64_Geolayout_Inspector_Side"
	bl_label = "SM64 Geolayout Inspector"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Item'

	@classmethod
	def poll(cls, context):
		return context.selected_bones is not None and \
			len(context.selected_bones) > 0

	def draw(self, context):
		drawGeoInfo(self, context.selected_bones[0])
"""


def getSwitchOptionBone(switchArmature):
    optionBones = []
    for poseBone in switchArmature.pose.bones:
        if poseBone.bone_group is not None and poseBone.bone_group.name == "SwitchOption":
            optionBones.append(poseBone.name)
    if len(optionBones) > 1:
        raise PluginError("There should only be one switch option bone in " + switchArmature.name + ".")
    elif len(optionBones) < 1:
        raise PluginError(
            "Could not find a switch option bone in "
            + switchArmature.name
            + ", which should be the root bone in the hierarchy."
        )
    return optionBones[0]


def updateBone(self, context):
    if not hasattr(context, "bone"):
        print("No bone in context.")
        return
    armatureObj = context.object

    createBoneGroups(armatureObj)
    if context.bone.geo_cmd not in animatableBoneTypes:
        addBoneToGroup(armatureObj, context.bone.name, context.bone.geo_cmd)
        bpy.ops.object.mode_set(mode="POSE")
    else:
        addBoneToGroup(armatureObj, context.bone.name, None)
        bpy.ops.object.mode_set(mode="POSE")


class SM64_BoneProperties(bpy.types.PropertyGroup):
    version: bpy.props.IntProperty(name="SM64_BoneProperties Version", default=0)

    custom_geo_cmd_macro: bpy.props.StringProperty(name="Geo Command Macro", default="GEO_BONE")
    custom_geo_cmd_args: bpy.props.StringProperty(name="Geo Command Args", default="")


sm64_bone_classes = (
    AddSwitchOption,
    RemoveSwitchOption,
    AddSwitchOptionMat,
    RemoveSwitchOptionMat,
    MoveSwitchOption,
    MaterialPointerProperty,
    SwitchOptionProperty,
    SM64_BoneProperties,
)

sm64_bone_panel_classes = (
    GeolayoutBonePanel,
    GeolayoutObjectPanel,
    GeolayoutArmaturePanel,
)


def sm64_bone_panel_register():
    for cls in sm64_bone_panel_classes:
        register_class(cls)


def sm64_bone_panel_unregister():
    for cls in sm64_bone_panel_classes:
        unregister_class(cls)


def sm64_bone_register():
    for cls in sm64_bone_classes:
        register_class(cls)

    bpy.types.Bone.geo_cmd = bpy.props.EnumProperty(
        name="Geolayout Command", items=enumBoneType, default="DisplayListWithOffset", update=updateBone
    )

    bpy.types.Bone.draw_layer = bpy.props.EnumProperty(name="Draw Layer", items=sm64EnumDrawLayers, default="1")

    # Scale
    bpy.types.Bone.geo_scale = bpy.props.FloatProperty(name="Scale", min=2 ** (-16), max=2 ** (16), default=1)

    # Function, HeldObject, Switch
    # 8027795C for HeldObject
    bpy.types.Bone.geo_func = bpy.props.StringProperty(
        name="Function", default="", description="Name of function for C, hex address for binary."
    )

    # Function
    bpy.types.Bone.func_param = bpy.props.IntProperty(
        name="Function Parameter", min=-(2 ** (15)), max=2 ** (15) - 1, default=0
    )

    # TranslateRotate
    bpy.types.Bone.field_layout = bpy.props.EnumProperty(name="Field Layout", items=enumFieldLayout, default="0")

    # Shadow
    bpy.types.Bone.shadow_type = bpy.props.EnumProperty(name="Shadow Type", items=enumShadowType, default="1")

    bpy.types.Bone.shadow_solidity = bpy.props.FloatProperty(name="Shadow Alpha", min=0, max=1, default=1)

    bpy.types.Bone.shadow_scale = bpy.props.IntProperty(
        name="Shadow Scale", min=-(2 ** (15)), max=2 ** (15) - 1, default=100
    )

    # bpy.types.Bone.switch_bone = bpy.props.StringProperty(
    # 	name = 'Switch Bone')

    # StartRenderArea
    bpy.types.Bone.culling_radius = bpy.props.FloatProperty(name="Culling Radius", default=10)

    bpy.types.Bone.switch_options = bpy.props.CollectionProperty(type=SwitchOptionProperty)

    # Static Geolayout
    bpy.types.Object.geo_cmd_static = bpy.props.EnumProperty(
        name="Geolayout Command", items=enumGeoStaticType, default="Optimal"
    )
    bpy.types.Object.draw_layer_static = bpy.props.EnumProperty(
        name="Draw Layer", items=sm64EnumDrawLayers, default="1"
    )
    bpy.types.Object.use_render_area = bpy.props.BoolProperty(name="Use Render Area")
    bpy.types.Object.culling_radius = bpy.props.FloatProperty(name="Culling Radius", default=10)

    bpy.types.Object.add_shadow = bpy.props.BoolProperty(name="Add Shadow")
    bpy.types.Object.shadow_type = bpy.props.EnumProperty(name="Shadow Type", items=enumShadowType, default="1")

    bpy.types.Object.shadow_solidity = bpy.props.FloatProperty(name="Shadow Alpha", min=0, max=1, default=1)

    bpy.types.Object.shadow_scale = bpy.props.IntProperty(
        name="Shadow Scale", min=-(2 ** (15)), max=2 ** (15) - 1, default=100
    )

    bpy.types.Object.add_func = bpy.props.BoolProperty(name="Add Function Node")

    bpy.types.Object.use_render_range = bpy.props.BoolProperty(name="Use Render Range (LOD)")
    bpy.types.Object.render_range = bpy.props.FloatVectorProperty(name="Render Range", size=2, default=(0, 100))

    bpy.types.Object.scaleFromGeolayout = bpy.props.BoolProperty(
        name="Scale from Geolayout",
        description="If scale is all a single value (e.g. 2, 2, 2), do not apply scale when exporting, and instead use GeoLayout to scale. Can be used to enhance precision by setting scaling values to a value less than 1.",
        default=False,
    )

    # Used during object duplication on export
    bpy.types.Object.original_name = bpy.props.StringProperty()


def sm64_bone_unregister():
    for cls in reversed(sm64_bone_classes):
        unregister_class(cls)

    del bpy.types.Bone.geo_cmd
    del bpy.types.Bone.draw_layer
    del bpy.types.Bone.geo_scale
    del bpy.types.Bone.geo_func
    del bpy.types.Bone.func_param
    del bpy.types.Bone.field_layout
    del bpy.types.Bone.shadow_type
    del bpy.types.Bone.shadow_solidity
    del bpy.types.Bone.shadow_scale
    del bpy.types.Bone.culling_radius
    del bpy.types.Bone.switch_options

    del bpy.types.Object.geo_cmd_static
    del bpy.types.Object.draw_layer_static
    del bpy.types.Object.use_render_area
    del bpy.types.Object.culling_radius

    del bpy.types.Object.add_shadow
    del bpy.types.Object.shadow_type
    del bpy.types.Object.shadow_solidity
    del bpy.types.Object.shadow_scale
    del bpy.types.Object.add_func

    del bpy.types.Object.use_render_range
    del bpy.types.Object.render_range

    del bpy.types.Object.scaleFromGeolayout
