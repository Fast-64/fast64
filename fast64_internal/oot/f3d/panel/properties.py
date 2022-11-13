from bpy.types import Panel, PropertyGroup, Object, World, Material, Armature, Mesh
from bpy.props import PointerProperty, StringProperty, BoolProperty, EnumProperty
from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from ....f3d.f3d_parser import ootEnumDrawLayers
from ...oot_f3d_writer import drawOOTMaterialProperty


################
# DL Inspector #
################
class OOT_DisplayListPanel(Panel):
    bl_label = "Display List Inspector"
    bl_idname = "OBJECT_PT_OOT_DL_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (
            context.object is not None and isinstance(context.object.data, Mesh)
        )

    def draw(self, context):
        box = self.layout.box().column()
        box.box().label(text="OOT DL Inspector")
        obj = context.object

        # prop_split(box, obj, "ootDrawLayer", "Draw Layer")
        box.prop(obj, "ignore_render")
        box.prop(obj, "ignore_collision")

        if not (obj.parent is not None and isinstance(obj.parent.data, Armature)):
            actorScaleBox = box.box().column()
            prop_split(actorScaleBox, obj, "ootActorScale", "Actor Scale")
            actorScaleBox.label(text="This applies to actor exports only.", icon="INFO")

        # Doesn't work since all static meshes are pre-transformed
        # box.prop(obj.ootDynamicTransform, "billboard")
        # drawParentSceneRoom(box, obj)


######################
# Material Inspector #
######################
class OOTDynamicMaterialDrawLayerProperty(PropertyGroup):
    segment8: BoolProperty()
    segment9: BoolProperty()
    segmentA: BoolProperty()
    segmentB: BoolProperty()
    segmentC: BoolProperty()
    segmentD: BoolProperty()
    customCall0: BoolProperty()
    customCall0_seg: StringProperty(description="Segment address of a display list to call, e.g. 0x08000010")
    customCall1: BoolProperty()
    customCall1_seg: StringProperty(description="Segment address of a display list to call, e.g. 0x08000010")

    def key(self):
        return (
            self.segment8,
            self.segment9,
            self.segmentA,
            self.segmentB,
            self.segmentC,
            self.segmentD,
            self.customCall0_seg if self.customCall0 else None,
            self.customCall1_seg if self.customCall1 else None,
        )


# The reason these are separate is for the case when the user changes the material draw layer, but not the
# dynamic material calls. This could cause crashes which would be hard to detect.
class OOTDynamicMaterialProperty(PropertyGroup):
    opaque: PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)
    transparent: PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)

    def key(self):
        return (self.opaque.key(), self.transparent.key())


class OOT_MaterialPanel(Panel):
    bl_label = "OOT Material"
    bl_idname = "MATERIAL_PT_OOT_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.material is not None and context.scene.gameEditorMode == "OOT"

    def draw(self, context):
        layout = self.layout
        mat = context.material
        col = layout.column()

        if (
            hasattr(context, "object")
            and context.object is not None
            and context.object.parent is not None
            and isinstance(context.object.parent.data, Armature)
        ):
            drawLayer = context.object.parent.ootDrawLayer
            if drawLayer != mat.f3d_mat.draw_layer.oot:
                col.label(text="Draw layer is being overriden by skeleton.", icon="OUTLINER_DATA_ARMATURE")
        else:
            drawLayer = mat.f3d_mat.draw_layer.oot

        drawOOTMaterialProperty(col.box().column(), mat, drawLayer)


###############
# Draw Layers #
###############
class OOTDefaultRenderModesProperty(PropertyGroup):
    expandTab: BoolProperty()
    opaqueCycle1: StringProperty(default="G_RM_AA_ZB_OPA_SURF")
    opaqueCycle2: StringProperty(default="G_RM_AA_ZB_OPA_SURF2")
    transparentCycle1: StringProperty(default="G_RM_AA_ZB_XLU_SURF")
    transparentCycle2: StringProperty(default="G_RM_AA_ZB_XLU_SURF2")
    overlayCycle1: StringProperty(default="G_RM_AA_ZB_OPA_SURF")
    overlayCycle2: StringProperty(default="G_RM_AA_ZB_OPA_SURF2")


class OOT_DrawLayersPanel(Panel):
    bl_label = "OOT Draw Layers"
    bl_idname = "WORLD_PT_OOT_Draw_Layers_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT"

    def draw(self, context):
        ootDefaultRenderModeProp = context.scene.world.ootDefaultRenderModes
        layout = self.layout

        inputGroup = layout.column()
        inputGroup.prop(
            ootDefaultRenderModeProp,
            "expandTab",
            text="Default Render Modes",
            icon="TRIA_DOWN" if ootDefaultRenderModeProp.expandTab else "TRIA_RIGHT",
        )
        if ootDefaultRenderModeProp.expandTab:
            prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle1", "Opaque Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle2", "Opaque Cycle 2")
            prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle1", "Transparent Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle2", "Transparent Cycle 2")
            prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle1", "Overlay Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle2", "Overlay Cycle 2")


oot_dl_writer_classes = (
    OOTDefaultRenderModesProperty,
    OOTDynamicMaterialDrawLayerProperty,
    OOTDynamicMaterialProperty,
)

oot_dl_writer_panel_classes = (
    OOT_DisplayListPanel,
    OOT_DrawLayersPanel,
    OOT_MaterialPanel,
)


def f3d_props_panel_register():
    for cls in oot_dl_writer_panel_classes:
        register_class(cls)


def f3d_props_panel_unregister():
    for cls in oot_dl_writer_panel_classes:
        unregister_class(cls)


def f3d_props_classes_register():
    ootEnumObjectMenu = [
        ("Scene", "Parent Scene Settings", "Scene"),
        ("Room", "Parent Room Settings", "Room"),
    ]

    for cls in oot_dl_writer_classes:
        register_class(cls)

    Object.ootDrawLayer = EnumProperty(items=ootEnumDrawLayers, default="Opaque")

    # Doesn't work since all static meshes are pre-transformed
    # Object.ootDynamicTransform = PointerProperty(type = OOTDynamicTransformProperty)
    World.ootDefaultRenderModes = PointerProperty(type=OOTDefaultRenderModesProperty)
    Material.ootMaterial = PointerProperty(type=OOTDynamicMaterialProperty)
    Object.ootObjectMenu = EnumProperty(items=ootEnumObjectMenu)


def f3d_props_classes_unregister():
    for cls in reversed(oot_dl_writer_classes):
        unregister_class(cls)

    del Material.ootMaterial
    del Object.ootObjectMenu
