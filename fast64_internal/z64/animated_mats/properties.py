from bpy.props import (
    IntProperty,
    PointerProperty,
    BoolProperty,
    EnumProperty,
    StringProperty,
    CollectionProperty,
    FloatVectorProperty,
)
from bpy.utils import register_class, unregister_class
from bpy.types import PropertyGroup, UILayout, Object
from ...utility import prop_split
from ..utility import drawCollectionOps, drawAddButton, get_list_tab_text


# no custom since we only need to know where to export the data
enum_mode = [
    ("Scene", "Scene", "Scene"),
    ("Actor", "Actor", "Actor"),
]

# see `sMatAnimDrawHandlers` in `z_scene_proc.c`
enum_anim_mat_type = [
    ("Custom", "Custom", "Custom"),
    ("tex_scroll", "Draw Texture Scroll", "Draw Texture Scroll"),
    ("two_tex_scroll", "Draw Two Texture Scroll", "Draw Two Texture Scroll"),
    ("color", "Draw Color", "Draw Color"),
    ("color_lerp", "Draw Color Lerp", "Draw Color Lerp"),
    ("color_nonlinear_interp", "Draw Color Non-Linear Interp", "Draw Color Non-Linear Interp"),
    ("tex_cycle", "Draw Texture Cycle", "Draw Texture Cycle"),
]


class Z64_AnimatedMatColorKeyFrame(PropertyGroup):
    frame_num: IntProperty(name="Frame No.", min=0)

    prim_lod_frac: IntProperty(name="Primitive LOD Frac", min=0, max=255)
    prim_color: FloatVectorProperty(
        name="Primitive Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
    )

    env_color: FloatVectorProperty(
        name="Environment Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
    )

    def draw_props(self, layout: UILayout, owner: Object, parent_index: int, index: int):
        drawCollectionOps(layout, index, "Animated Mat. Color", None, owner.name, collection_index=parent_index)
        prop_split(layout, self, "frame_num", "Frame No.")
        prop_split(layout, self, "prim_lod_frac", "Primitive LOD Frac")
        prop_split(layout, self, "prim_color", "Primitive Color")
        prop_split(layout, self, "env_color", "Environment Color")


class Z64_AnimatedMatColorParams(PropertyGroup):
    frame_count: IntProperty(name="Frame Count", min=0)
    keyframes: CollectionProperty(type=Z64_AnimatedMatColorKeyFrame)

    # ui only props
    show_entries: BoolProperty(default=False)

    def draw_props(self, layout: UILayout, owner: Object, parent_index: int):
        prop_split(layout, self, "frame_count", "Frame Count")

        prop_text = get_list_tab_text("Keyframes", len(self.keyframes))
        layout.prop(self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            for i, keyframe in enumerate(self.keyframes):
                keyframe.draw_props(layout, owner, parent_index, i)

            drawAddButton(layout, len(self.keyframes), "Animated Mat. Color", None, owner.name, parent_index)


class Z64_AnimatedMatTexScrollItem(PropertyGroup):
    step_x: IntProperty(default=0)
    step_y: IntProperty(default=0)
    width: IntProperty(min=0)
    height: IntProperty(min=0)

    def draw_props(self, layout: UILayout, owner: Object, parent_index: int, index: int):
        drawCollectionOps(layout, index, "Animated Mat. Scroll", None, owner.name, collection_index=parent_index)
        prop_split(layout, self, "step_x", "Step X")
        prop_split(layout, self, "step_y", "Step Y")
        prop_split(layout, self, "width", "Texture Width")
        prop_split(layout, self, "height", "Texture Height")


class Z64_AnimatedMatTexScrollParams(PropertyGroup):
    entries: CollectionProperty(type=Z64_AnimatedMatTexScrollItem)

    # ui only props
    show_entries: BoolProperty(default=False)

    def draw_props(self, layout: UILayout, owner: Object, parent_index: int):
        prop_text = get_list_tab_text("Tex. Scroll", len(self.entries))
        layout.prop(self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            for i, item in enumerate(self.entries):
                item.draw_props(layout, owner, parent_index, i)

            drawAddButton(layout, len(self.entries), "Animated Mat. Scroll", None, owner.name, parent_index)


class Z64_AnimatedMatTexCycleKeyFrame(PropertyGroup):
    frame_num: IntProperty(name="Frame No.", min=0)
    texture: StringProperty(name="Texture Symbol")

    def draw_props(self, layout: UILayout, owner: Object, parent_index: int, index: int):
        drawCollectionOps(layout, index, "Animated Mat. Cycle", None, owner.name, collection_index=parent_index)
        prop_split(layout, self, "frame_num", "Frame No.")
        prop_split(layout, self, "texture", "Texture Symbol")


class Z64_AnimatedMatTexCycleParams(PropertyGroup):
    frame_count: IntProperty(name="Frame Count", min=0)
    keyframes: CollectionProperty(type=Z64_AnimatedMatTexCycleKeyFrame)

    # ui only props
    show_entries: BoolProperty(default=False)

    def draw_props(self, layout: UILayout, owner: Object, parent_index: int):
        prop_split(layout, self, "frame_count", "Frame Count")

        prop_text = get_list_tab_text("Keyframes", len(self.keyframes))
        layout.prop(self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            for i, keyframe in enumerate(self.keyframes):
                keyframe.draw_props(layout, owner, parent_index, i)

            drawAddButton(layout, len(self.keyframes), "Animated Mat. Cycle", None, owner.name, parent_index)


class Z64_AnimatedMaterialItem(PropertyGroup):
    """see the `AnimatedMaterial` struct from `z64scene.h`"""

    segment_num: IntProperty(name="Segment Number", min=8, max=13, default=8)
    type: EnumProperty(
        name="Draw Handler Type", items=enum_anim_mat_type, default=2, description="Index to `sMatAnimDrawHandlers`"
    )
    type_custom: StringProperty(name="Custom Draw Handler Index", default="2")

    color_params: PointerProperty(type=Z64_AnimatedMatColorParams)
    tex_scroll_params: PointerProperty(type=Z64_AnimatedMatTexScrollParams)
    tex_cycle_params: PointerProperty(type=Z64_AnimatedMatTexCycleParams)

    # ui only props
    show_item: BoolProperty(default=False)

    def draw_props(self, layout: UILayout, owner: Object, index: int):
        layout.prop(
            self, "show_item", text=f"Item No.{index + 1}", icon="TRIA_DOWN" if self.show_item else "TRIA_RIGHT"
        )

        if self.show_item:
            drawCollectionOps(layout, index, "Animated Mat.", None, owner.name)

            prop_split(layout, self, "segment_num", "Segment Number")

            layout_type = layout.column()
            prop_split(layout_type, self, "type", "Draw Handler Type")

            if self.type == "Custom":
                layout_type.label(
                    text="This only allows you to choose a custom index for the function handler.", icon="ERROR"
                )
                prop_split(layout_type, self, "type_custom", "Custom Draw Handler Index")
            elif self.type in {"tex_scroll", "two_tex_scroll"}:
                self.tex_scroll_params.draw_props(layout_type, owner, index)
            elif self.type in {"color", "color_lerp", "color_nonlinear_interp"}:
                self.color_params.draw_props(layout_type, owner, index)
            elif self.type == "tex_cycle":
                self.tex_cycle_params.draw_props(layout_type, owner, index)


class Z64_AnimatedMaterial(PropertyGroup):
    """Defines an Animated Material array"""

    header_index: IntProperty(name="Header Index", min=-1, default=-1, description="Header Index, -1 means all headers")
    entries: CollectionProperty(type=Z64_AnimatedMaterialItem)

    # ui only props
    show_list: BoolProperty(default=True)
    show_entries: BoolProperty(default=True)

    def draw_props(self, layout: UILayout, owner: Object, index: int):
        layout.prop(
            self, "show_list", text=f"List No.{index + 1}", icon="TRIA_DOWN" if self.show_list else "TRIA_RIGHT"
        )

        if self.show_list:
            drawCollectionOps(layout, index, "Animated Mat. List", None, owner.name)
            prop_split(layout, self, "header_index", "Header Index")

            prop_text = get_list_tab_text("Animated Materials", len(self.entries))
            layout_entries = layout.column()
            layout_entries.prop(
                self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT"
            )

            if self.show_entries:
                for i, item in enumerate(self.entries):
                    item.draw_props(layout_entries.box().column(), owner, i)

                drawAddButton(layout_entries, len(self.entries), "Animated Mat.", None, owner.name)


class Z64_AnimatedMaterialProperty(PropertyGroup):
    """List of Animated Material arrays"""

    mode: EnumProperty(name="Export To", items=enum_mode)

    # this is probably useless since usually you wouldn't use different animated materials
    # on different headers but it's better to give users the choice
    items: CollectionProperty(type=Z64_AnimatedMaterial)

    # ui only props
    show_entries: BoolProperty(default=True)

    def draw_props(self, layout: UILayout, owner: Object):
        layout = layout.column()

        prop_split(layout, self, "mode", "Export To")

        prop_text = get_list_tab_text("Animated Materials List", len(self.items))
        layout_entries = layout.box().column()
        layout_entries.prop(
            self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT"
        )

        if self.show_entries:
            for i, item in enumerate(self.items):
                item.draw_props(layout_entries.box().column(), owner, i)

            drawAddButton(layout_entries, len(self.items), "Animated Mat. List", None, owner.name)


classes = (
    Z64_AnimatedMatColorKeyFrame,
    Z64_AnimatedMatColorParams,
    Z64_AnimatedMatTexScrollItem,
    Z64_AnimatedMatTexScrollParams,
    Z64_AnimatedMatTexCycleKeyFrame,
    Z64_AnimatedMatTexCycleParams,
    Z64_AnimatedMaterialItem,
    Z64_AnimatedMaterial,
    Z64_AnimatedMaterialProperty,
)


def animated_mats_register():
    for cls in classes:
        register_class(cls)

    Object.z64_anim_mats_property = PointerProperty(type=Z64_AnimatedMaterialProperty)


def animated_mats_unregister():
    del Object.z64_anim_mats_property

    for cls in reversed(classes):
        unregister_class(cls)
