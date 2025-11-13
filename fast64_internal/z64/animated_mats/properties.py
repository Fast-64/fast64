from bpy.utils import register_class, unregister_class
from bpy.types import PropertyGroup, UILayout, Object
from bpy.props import (
    IntProperty,
    PointerProperty,
    BoolProperty,
    EnumProperty,
    StringProperty,
    CollectionProperty,
    FloatVectorProperty,
)

from typing import Optional

from ...utility import prop_split
from ..collection_utility import drawAddButton, drawCollectionOps, draw_utility_ops
from ..utility import get_list_tab_text, getEnumIndex


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

    def draw_props(
        self,
        layout: UILayout,
        owner: Object,
        header_index: int,
        parent_index: int,
        index: int,
        is_draw_color: bool,
        use_env_color: bool,
    ):
        drawCollectionOps(
            layout,
            index,
            "Animated Mat. Color",
            header_index,
            owner.name,
            collection_index=parent_index,
            ask_for_copy=True,
            ask_for_amount=True,
        )

        # "draw color" type don't need this
        if not is_draw_color:
            prop_split(layout, self, "frame_num", "Frame No.")

        prop_split(layout, self, "prim_lod_frac", "Primitive LOD Frac")
        prop_split(layout, self, "prim_color", "Primitive Color")

        if not is_draw_color or use_env_color:
            prop_split(layout, self, "env_color", "Environment Color")


class Z64_AnimatedMatColorParams(PropertyGroup):
    keyframe_length: IntProperty(name="Keyframe Length", min=0)
    keyframes: CollectionProperty(type=Z64_AnimatedMatColorKeyFrame)
    use_env_color: BoolProperty()

    # ui only props
    show_entries: BoolProperty(default=False)

    internal_color_type: StringProperty()

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int):
        is_draw_color = self.internal_color_type == "color"

        if not is_draw_color:
            prop_split(layout, self, "keyframe_length", "Keyframe Length")

        if is_draw_color:
            layout.prop(self, "use_env_color", text="Use Environment Color")

        prop_text = get_list_tab_text("Keyframes", len(self.keyframes))
        layout.prop(self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            for i, keyframe in enumerate(self.keyframes):
                keyframe.draw_props(
                    layout, owner, header_index, parent_index, i, is_draw_color, not is_draw_color or self.use_env_color
                )

            draw_utility_ops(
                layout.row(),
                len(self.keyframes),
                "Animated Mat. Color",
                header_index,
                owner.name,
                parent_index,
                ask_for_amount=True,
            )


class Z64_AnimatedMatTexScrollItem(PropertyGroup):
    step_x: IntProperty(default=0)
    step_y: IntProperty(default=0)
    width: IntProperty(min=0)
    height: IntProperty(min=0)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "step_x", "Step X")
        prop_split(layout, self, "step_y", "Step Y")
        prop_split(layout, self, "width", "Texture Width")
        prop_split(layout, self, "height", "Texture Height")


class Z64_AnimatedMatTexScrollParams(PropertyGroup):
    texture_1: PointerProperty(type=Z64_AnimatedMatTexScrollItem)
    texture_2: PointerProperty(type=Z64_AnimatedMatTexScrollItem)

    # ui only props
    show_entries: BoolProperty(default=False)

    internal_scroll_type: StringProperty(default="two_tex_scroll")

    def draw_props(self, layout: UILayout):
        tab_text = "Two-Texture Scroll" if self.internal_scroll_type == "two_tex_scroll" else "Texture Scroll"
        layout.prop(self, "show_entries", text=tab_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            if self.internal_scroll_type == "two_tex_scroll":
                tex1_box = layout.box().column()
                tex1_box.label(text="Texture 1")
                self.texture_1.draw_props(tex1_box)

                tex2_box = layout.box().column()
                tex2_box.label(text="Texture 2")
                self.texture_2.draw_props(tex2_box)
            else:
                self.texture_1.draw_props(layout)


class Z64_AnimatedMatTexCycleTexture(PropertyGroup):
    symbol: StringProperty(name="Texture Symbol")

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int, index: int):
        drawCollectionOps(
            layout,
            index,
            "Animated Mat. Cycle (Texture)",
            header_index,
            owner.name,
            collection_index=parent_index,
            ask_for_copy=True,
            ask_for_amount=True,
        )
        prop_split(layout, self, "symbol", "Texture Symbol")


class Z64_AnimatedMatTexCycleKeyFrame(PropertyGroup):
    texture_index: IntProperty(min=0)

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int, index: int):
        drawCollectionOps(
            layout,
            index,
            "Animated Mat. Cycle (Index)",
            header_index,
            owner.name,
            collection_index=parent_index,
            ask_for_copy=True,
            ask_for_amount=True,
        )
        prop_split(layout, self, "texture_index", "Texture Symbol")


class Z64_AnimatedMatTexCycleParams(PropertyGroup):
    keyframes: CollectionProperty(type=Z64_AnimatedMatTexCycleKeyFrame)
    textures: CollectionProperty(type=Z64_AnimatedMatTexCycleTexture)

    # ui only props
    show_entries: BoolProperty(default=False)
    show_textures: BoolProperty(default=False)

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int):
        texture_box = layout.box()
        prop_text = get_list_tab_text("Textures", len(self.textures))
        texture_box.prop(
            self, "show_textures", text=prop_text, icon="TRIA_DOWN" if self.show_textures else "TRIA_RIGHT"
        )
        if self.show_textures:
            for i, texture in enumerate(self.textures):
                texture.draw_props(texture_box, owner, header_index, parent_index, i)
            draw_utility_ops(
                texture_box.row(),
                len(self.textures),
                "Animated Mat. Cycle (Texture)",
                header_index,
                owner.name,
                parent_index,
                ask_for_amount=True,
            )

        index_box = layout.box()
        prop_text = get_list_tab_text("Keyframes", len(self.keyframes))
        index_box.prop(self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")
        if self.show_entries:
            for i, keyframe in enumerate(self.keyframes):
                keyframe.draw_props(index_box, owner, header_index, parent_index, i)
            draw_utility_ops(
                index_box.row(),
                len(self.keyframes),
                "Animated Mat. Cycle (Index)",
                header_index,
                owner.name,
                parent_index,
                ask_for_amount=True,
            )


class Z64_AnimatedMaterialItem(PropertyGroup):
    """see the `AnimatedMaterial` struct from `z64scene.h`"""

    segment_num: IntProperty(name="Segment Number", min=8, max=13, default=8)

    user_type: EnumProperty(
        name="Draw Handler Type",
        items=enum_anim_mat_type,
        default=2,
        description="Index to `sMatAnimDrawHandlers`",
        get=lambda self: getEnumIndex(enum_anim_mat_type, self.type),
        set=lambda self, value: self.on_type_set(value),
    )
    type: StringProperty(default=enum_anim_mat_type[2][0])
    type_custom: StringProperty(name="Custom Draw Handler Index", default="2")

    color_params: PointerProperty(type=Z64_AnimatedMatColorParams)
    tex_scroll_params: PointerProperty(type=Z64_AnimatedMatTexScrollParams)
    tex_cycle_params: PointerProperty(type=Z64_AnimatedMatTexCycleParams)

    # ui only props
    show_item: BoolProperty(default=False)

    def on_type_set(self, value: str):
        self.type = enum_anim_mat_type[value][0]

        if "tex_scroll" in self.type:
            self.tex_scroll_params.internal_scroll_type = self.type
        elif "color" in self.type:
            self.color_params.internal_color_type = self.type

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, index: int):
        layout.prop(
            self, "show_item", text=f"Item No.{index + 1}", icon="TRIA_DOWN" if self.show_item else "TRIA_RIGHT"
        )

        if self.show_item:
            drawCollectionOps(layout, index, "Animated Mat.", header_index, owner.name, ask_for_amount=True)

            prop_split(layout, self, "segment_num", "Segment Number")

            layout_type = layout.column()
            prop_split(layout_type, self, "user_type", "Draw Handler Type")

            if self.type == "Custom":
                layout_type.label(
                    text="This only allows you to choose a custom index for the function handler.", icon="ERROR"
                )
                prop_split(layout_type, self, "type_custom", "Custom Draw Handler Index")
            elif self.type in {"tex_scroll", "two_tex_scroll"}:
                self.tex_scroll_params.draw_props(layout_type)
            elif self.type in {"color", "color_lerp", "color_nonlinear_interp"}:
                self.color_params.draw_props(layout_type, owner, header_index, index)
            elif self.type == "tex_cycle":
                self.tex_cycle_params.draw_props(layout_type, owner, header_index, index)


class Z64_AnimatedMaterial(PropertyGroup):
    """Defines an Animated Material array"""

    entries: CollectionProperty(type=Z64_AnimatedMaterialItem)

    # ui only props
    show_list: BoolProperty(default=True)
    show_entries: BoolProperty(default=True)

    def draw_props(self, layout: UILayout, owner: Object, index: Optional[int], header_index: Optional[int] = None):
        if index is not None:
            layout.prop(
                self, "show_list", text=f"List No.{index + 1}", icon="TRIA_DOWN" if self.show_list else "TRIA_RIGHT"
            )

        if self.show_list:
            if index is not None:
                drawCollectionOps(
                    layout,
                    index,
                    "Animated Mat. List",
                    header_index,
                    owner.name,
                    ask_for_copy=True,
                    ask_for_amount=True,
                )

            prop_text = get_list_tab_text("Animated Materials", len(self.entries))
            layout_entries = layout.column()
            layout_entries.prop(
                self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT"
            )

            if self.show_entries:
                for i, item in enumerate(self.entries):
                    item.draw_props(layout_entries.box().column(), owner, header_index, i)

                draw_utility_ops(
                    layout_entries.row(),
                    len(self.entries),
                    "Animated Mat.",
                    header_index,
                    owner.name,
                    ask_for_amount=True,
                )


class Z64_AnimatedMaterialProperty(PropertyGroup):
    """List of Animated Material arrays"""

    # this is probably useless since usually you wouldn't use different animated materials
    # on different headers but it's better to give users the choice
    items: CollectionProperty(type=Z64_AnimatedMaterial)

    # ui only props
    show_entries: BoolProperty(default=True)

    def draw_props(self, layout: UILayout, owner: Object):
        layout = layout.column()

        prop_text = get_list_tab_text("Animated Materials List", len(self.items))
        layout_entries = layout.column()
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
    Z64_AnimatedMatTexCycleTexture,
    Z64_AnimatedMatTexCycleKeyFrame,
    Z64_AnimatedMatTexCycleParams,
    Z64_AnimatedMaterialItem,
    Z64_AnimatedMaterial,
    Z64_AnimatedMaterialProperty,
)


def animated_mats_props_register():
    for cls in classes:
        register_class(cls)


def animated_mats_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
