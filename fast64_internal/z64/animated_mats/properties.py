import bpy

from bpy.utils import register_class, unregister_class
from bpy.types import PropertyGroup, UILayout, Object, Material
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

from ...game_data import game_data
from ...utility import prop_split
from ..collection_utility import drawCollectionOps, draw_utility_ops
from ..collision.properties import OOTMaterialCollisionProperty
from ..hackeroot.properties import HackerOoT_EventProperty
from ..utility import get_list_tab_text, getEnumIndex, is_oot_features, is_hackeroot
from .operators import Z64_ExportAnimatedMaterials, Z64_ImportAnimatedMaterials


# no custom since we only need to know where to export the data
enum_mode = [
    ("Scene", "Scene", "Scene"),
    ("Actor", "Actor", "Actor"),
]


class Z64_AnimatedMatColorKeyFrame(PropertyGroup):
    frame_num: IntProperty(
        name="Frame No.",
        min=0,
        set=lambda self, value: self.on_frame_num_set(value),
        get=lambda self: self.on_frame_num_get(),
    )
    internal_frame_num: IntProperty(min=0)
    internal_length: IntProperty(min=0)

    def validate_frame_num(self):
        if self.internal_frame_num >= self.internal_length:
            # TODO: figure out if having the same value is fine
            self.internal_frame_num = self.internal_length - 1

    def on_frame_num_set(self, value):
        self.internal_frame_num = value
        self.validate_frame_num()

    def on_frame_num_get(self):
        self.validate_frame_num()
        return self.internal_frame_num

    prim_lod_frac: IntProperty(name="Primitive LOD Frac", min=0, max=255, default=128)
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
        color_type: str,
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

        is_draw_color = color_type in {"anim_mat_type_color", "anim_mat_type_color_cycle"}

        # "draw color" type don't need this
        if not is_draw_color or color_type == "anim_mat_type_color_cycle":
            prop_split(layout, self, "frame_num", "Duration" if is_draw_color else "Frame No.")

        prop_split(layout, self, "prim_lod_frac", "Primitive LOD Frac")
        prop_split(layout, self, "prim_color", "Primitive Color")

        if not is_draw_color or use_env_color:
            prop_split(layout, self, "env_color", "Environment Color")


class Z64_AnimatedMatColorParams(PropertyGroup):
    keyframe_length: IntProperty(
        name="Keyframe Length",
        min=0,
        set=lambda self, value: self.on_length_set(value),
        get=lambda self: self.on_length_get(),
    )
    internal_keyframe_length: IntProperty(min=0)

    keyframes: CollectionProperty(type=Z64_AnimatedMatColorKeyFrame)
    use_env_color: BoolProperty()

    # ui only props
    show_entries: BoolProperty(default=False)

    internal_color_type: StringProperty()

    def update_keyframes(self):
        for keyframe in self.keyframes:
            keyframe.internal_length = self.internal_keyframe_length

    def on_length_set(self, value):
        self.internal_keyframe_length = value
        self.update_keyframes()

    def on_length_get(self):
        self.update_keyframes()
        return self.internal_keyframe_length

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int):
        is_draw_color = self.internal_color_type in {"anim_mat_type_color", "anim_mat_type_color_cycle"}

        if not is_draw_color:
            prop_split(layout, self, "keyframe_length", "Keyframe Length")

        if is_draw_color:
            layout.prop(self, "use_env_color", text="Use Environment Color")

        prop_text = get_list_tab_text("Keyframes", len(self.keyframes))
        layout.prop(self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            for i, keyframe in enumerate(self.keyframes):
                keyframe.draw_props(
                    layout,
                    owner,
                    header_index,
                    parent_index,
                    i,
                    self.internal_color_type,
                    not is_draw_color or self.use_env_color,
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

    def set_from_data(self, raw_data: list[str]):
        self.step_x = int(raw_data[0], base=0)
        self.step_y = int(raw_data[1], base=0)
        self.width = int(raw_data[2], base=0)
        self.height = int(raw_data[3], base=0)

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

    internal_scroll_type: StringProperty(default="anim_mat_type_two_tex_scroll")

    def draw_props(self, layout: UILayout):
        tab_text = "Two-Texture Scroll" if "two_tex" in self.internal_scroll_type else "Texture Scroll"
        layout.prop(self, "show_entries", text=tab_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            if self.internal_scroll_type == "anim_mat_type_two_tex_scroll":
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


class Z64_AnimatedMatTexTimedCycleKeyFrame(PropertyGroup):
    symbol: StringProperty()
    duration: IntProperty(min=0)

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int, index: int):
        drawCollectionOps(
            layout,
            index,
            "Animated Mat. Timed Cycle",
            header_index,
            owner.name,
            collection_index=parent_index,
            ask_for_copy=True,
            ask_for_amount=True,
        )
        prop_split(layout, self, "symbol", "Texture Symbol")
        prop_split(layout, self, "duration", "Duration")


class Z64_AnimatedMatTexTimedCycleParams(PropertyGroup):
    keyframes: CollectionProperty(type=Z64_AnimatedMatTexTimedCycleKeyFrame)

    # ui only props
    show_entries: BoolProperty(default=False)

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int):
        index_box = layout.box()
        prop_text = get_list_tab_text("Keyframes", len(self.keyframes))
        index_box.prop(self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")
        if self.show_entries:
            for i, keyframe in enumerate(self.keyframes):
                keyframe.draw_props(index_box.column(), owner, header_index, parent_index, i)
            draw_utility_ops(
                index_box.row(),
                len(self.keyframes),
                "Animated Mat. Timed Cycle",
                header_index,
                owner.name,
                parent_index,
                ask_for_amount=True,
            )


class Z64_AnimatedMatTextureParams(PropertyGroup):
    texture_1: StringProperty(description="Default Texture")
    texture_2: StringProperty(description="Texture to draw when the event script is completed")

    # ui only props
    show_entries: BoolProperty(default=False)

    def draw_props(self, layout: UILayout):
        layout.prop(self, "show_entries", text="Texture", icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

        if self.show_entries:
            texture_box = layout.box().column()
            prop_split(texture_box, self, "texture_1", "Texture 1")
            prop_split(texture_box, self, "texture_2", "Texture 2")


class Z64_AnimatedMatMultiTextureParams(PropertyGroup):
    min_prim_alpha: IntProperty(min=0, max=255)
    max_prim_alpha: IntProperty(min=0, max=255)
    min_env_alpha: IntProperty(min=0, max=255)
    max_env_alpha: IntProperty(min=0, max=255)
    speed: IntProperty(min=0, description="Transition or blending speed, can be 0 to disable blending.")

    use_texture_refs: BoolProperty(
        default=False,
        description="Optionally, you can use texture references, you'll need to provide symbols and segment numbers.",
    )
    texture_1: StringProperty(description="Symbol for Texture Reference No. 1")
    texture_2: StringProperty(description="Symbol for Texture Reference No. 2")
    segment_1: IntProperty(min=8, max=13, default=8, description="Segment corresponding to the Texture Reference No. 1")
    segment_2: IntProperty(min=8, max=13, default=8, description="Segment corresponding to the Texture Reference No. 2")

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "min_prim_alpha", "Min. Primitive Alpha")
        prop_split(layout, self, "max_prim_alpha", "Max. Primitive Alpha")
        prop_split(layout, self, "min_env_alpha", "Min. Environment Alpha")
        prop_split(layout, self, "max_env_alpha", "Max. Environment Alpha")
        prop_split(layout, self, "speed", "Transition Speed")

        tex_box = layout.box().column()
        tex_box.prop(self, "use_texture_refs", text="Use Texture References")
        if self.use_texture_refs:
            prop_split(tex_box, self, "texture_1", "Texture Symbol 1")
            prop_split(tex_box, self, "segment_1", "Segment Number 1")

            prop_split(tex_box, self, "texture_2", "Texture Symbol 2")
            prop_split(tex_box, self, "segment_2", "Segment Number 2")


class Z64_AnimatedMatTriIndexItem(PropertyGroup):
    mesh_obj: PointerProperty(type=Object, poll=lambda self, obj: self.on_poll(obj))

    def on_poll(self, obj: Object):
        active_obj = bpy.context.view_layer.objects.active
        assert active_obj is not None
        return (
            active_obj.type == "EMPTY"
            and active_obj.ootEmptyType == "Scene"
            and obj.type == "MESH"
            and obj in active_obj.children_recursive
        )

    def draw_props(self, layout: UILayout, owner: Object, index: int, header_index: int, parent_index: int):
        layout.prop(self, "mesh_obj", text="")

        drawCollectionOps(
            layout,
            index,
            "Animated Mat. Surface",
            header_index,
            owner.name,
            compact=True,
            collection_index=parent_index,
            ask_for_copy=True,
            ask_for_amount=True,
        )


class Z64_AnimatedMatSurfaceSwapParams(PropertyGroup):
    col_settings: PointerProperty(type=OOTMaterialCollisionProperty)

    use_tris: BoolProperty(default=False)
    material: PointerProperty(
        type=Material, poll=lambda self, obj: self.on_poll(obj), description="Can be left empty if using tri indices"
    )
    meshes: CollectionProperty(type=Z64_AnimatedMatTriIndexItem)

    use_multitexture: BoolProperty(default=False)
    multitexture_params: PointerProperty(
        type=Z64_AnimatedMatMultiTextureParams,
        description="Can be left empty if you just want to swap the surface type",
    )

    # ui only props
    show_entries: BoolProperty(default=False)

    def on_poll(self, obj: Material):
        # TODO
        return True

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, parent_index: int):
        self.col_settings.draw_props(layout.box().column())

        tri_box = layout.box().column()
        tri_box.prop(self, "use_tris", text="Use Triangle Indices")

        if self.use_tris:
            tri_box.prop(self, "show_entries", text="Meshes", icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT")

            if self.show_entries:
                for i, entry in enumerate(self.meshes):
                    entry.draw_props(tri_box.row(align=True), owner, i, header_index, parent_index)

                draw_utility_ops(
                    tri_box.row(),
                    len(self.meshes),
                    "Animated Mat. Surface",
                    header_index,
                    owner.name,
                    parent_index,
                    ask_for_amount=True,
                )
        else:
            prop_split(tri_box, self, "material", "Replace Surface Type from")

        multi_box = layout.box().column()
        multi_box.prop(self, "use_multitexture", text="Use Multi-Texture")
        if self.use_multitexture:
            multi_box.label(text="The above segment number will be used for this.", icon="QUESTION")
            self.multitexture_params.draw_props(multi_box)


class Z64_AnimatedMaterialItem(PropertyGroup):
    """see the `AnimatedMaterial` struct from `z64scene.h`"""

    segment_num: IntProperty(name="Segment Number", min=8, max=13, default=8)

    user_type: EnumProperty(
        name="Draw Handler Type",
        items=lambda self, context: game_data.z64.get_enum("anim_mats_type"),
        default=2,
        description="Index to `sMatAnimDrawHandlers`",
        get=lambda self: getEnumIndex(game_data.z64.get_enum("anim_mats_type"), self.type),
        set=lambda self, value: self.on_type_set(value),
    )
    type: StringProperty(default=game_data.z64.enums.enum_anim_mats_type[2][0])
    type_custom: StringProperty(name="Custom Draw Handler Index", default="2")

    color_params: PointerProperty(type=Z64_AnimatedMatColorParams)
    tex_scroll_params: PointerProperty(type=Z64_AnimatedMatTexScrollParams)
    tex_cycle_params: PointerProperty(type=Z64_AnimatedMatTexCycleParams)
    tex_timed_cycle_params: PointerProperty(type=Z64_AnimatedMatTexTimedCycleParams)
    texture_params: PointerProperty(type=Z64_AnimatedMatTextureParams)
    multitexture_params: PointerProperty(type=Z64_AnimatedMatMultiTextureParams)
    surface_params: PointerProperty(type=Z64_AnimatedMatSurfaceSwapParams)

    events: PointerProperty(type=HackerOoT_EventProperty)

    # ui only props
    show_item: BoolProperty(default=False)

    def on_type_set(self, value: int):
        self.type = game_data.z64.enums.enum_anim_mats_type[value][0]

        if "tex_scroll" in self.type:
            self.tex_scroll_params.internal_scroll_type = self.type
        elif "color" in self.type:
            self.color_params.internal_color_type = self.type

    def draw_props(self, layout: UILayout, owner: Object, header_index: int, index: int):
        layout.prop(
            self, "show_item", text=f"Item No.{index + 1}", icon="TRIA_DOWN" if self.show_item else "TRIA_RIGHT"
        )

        vanilla_types = [
            "anim_mat_type_tex_scroll",
            "anim_mat_type_two_tex_scroll",
            "anim_mat_type_color",
            "anim_mat_type_color_lerp",
            "anim_mat_type_color_non_linear_interp",
            "anim_mat_type_tex_cycle",
            "anim_mat_type_none",
        ]

        if self.show_item:
            drawCollectionOps(layout, index, "Animated Mat.", header_index, owner.name, ask_for_amount=True)

            prop_split(layout, self, "segment_num", "Segment Number")

            layout_type = layout.column()
            prop_split(layout_type, self, "user_type", "Draw Handler Type")

            if self.type not in vanilla_types and not is_hackeroot():
                layout_type.label(text="This requires HackerOoT features.", icon="ERROR")
                return

            self.events.draw_props(layout.column(), owner, "EventManager (Embed)", header_index, index)

            if self.type == "Custom":
                layout_type.label(
                    text="This only allows you to choose a custom index for the function handler.", icon="ERROR"
                )
                prop_split(layout_type, self, "type_custom", "Custom Draw Handler Index")
            elif "tex_scroll" in self.type or self.type == "anim_mat_type_oscillating_two_tex":
                self.tex_scroll_params.draw_props(layout_type)
            elif "color" in self.type:
                self.color_params.draw_props(layout_type, owner, header_index, index)
            elif self.type == "anim_mat_type_tex_cycle":
                self.tex_cycle_params.draw_props(layout_type, owner, header_index, index)
            elif self.type == "anim_mat_type_tex_timed_cycle":
                self.tex_timed_cycle_params.draw_props(layout_type, owner, header_index, index)
            elif self.type == "anim_mat_type_texture":
                self.texture_params.draw_props(layout_type)
            elif self.type == "anim_mat_type_multitexture":
                self.multitexture_params.draw_props(layout_type)
            elif self.type == "anim_mat_type_event":
                layout_type.label(text="This don't use parameters.")
                layout_type.label(text="It will draw/hide based on the event.")
            elif self.type == "anim_mat_type_surface_swap":
                self.surface_params.draw_props(layout_type, owner, header_index, index)
            elif self.type == "anim_mat_type_none":
                layout_type.label(text="This won't be exported.", icon="ERROR")


class Z64_AnimatedMaterial(PropertyGroup):
    """Defines an Animated Material array"""

    entries: CollectionProperty(type=Z64_AnimatedMaterialItem)

    # ui only props
    show_list: BoolProperty(default=True)
    show_entries: BoolProperty(default=True)

    def draw_props(
        self,
        layout: UILayout,
        owner: Object,
        index: Optional[int],
        sub_index: Optional[int] = None,
        is_scene: bool = True,
    ):
        if is_oot_features() and not is_hackeroot():
            layout.label(text="This requires MM features.", icon="ERROR")
            return

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
                    sub_index,
                    owner.name,
                    ask_for_copy=False,
                    ask_for_amount=False,
                )

            prop_text = get_list_tab_text("Animated Materials", len(self.entries))
            layout_entries = layout.column()
            layout_entries.prop(
                self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT"
            )

            if self.show_entries:
                for i, item in enumerate(self.entries):
                    item.draw_props(layout_entries.box().column(), owner, sub_index, i)

                draw_utility_ops(
                    layout_entries.row(),
                    len(self.entries),
                    "Animated Mat.",
                    sub_index,
                    owner.name,
                    do_copy=is_scene,
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

        if is_oot_features() and not is_hackeroot():
            layout.label(text="This requires MM features.", icon="ERROR")
            return

        prop_text = get_list_tab_text("Animated Materials List", len(self.items))
        layout_entries = layout.column()
        layout_entries.prop(
            self, "show_entries", text=prop_text, icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT"
        )

        if self.show_entries:
            for i, item in enumerate(self.items):
                item.draw_props(layout_entries.box().column(), owner, i, i, is_scene=False)

            draw_utility_ops(
                layout_entries.row(), len(self.items), "Animated Mat. List", None, owner.name, do_copy=False
            )


class Z64_AnimatedMaterialExportSettings(PropertyGroup):
    object_name: StringProperty(default="gameplay_keep")

    include_name: StringProperty(default="animated_materials.h")
    is_custom_inc: BoolProperty(default=False)

    export_path: StringProperty(name="File", subtype="DIR_PATH")
    export_obj: PointerProperty(type=Object, poll=lambda self, obj: self.filter(obj))
    is_custom_path: BoolProperty(default=False)

    def filter(self, obj):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Animated Materials"

    def get_include_name(self):
        if is_hackeroot():
            return "animated_materials.h"

        if self.is_custom_inc:
            return self.include_name if self.include_name.endswith(".h") else f"{self.include_name}.h"

        if bpy.context.scene.fast64.oot.is_z64sceneh_present():
            return "z64scene.h"

        return "scene.h"

    def draw_props(self, layout: UILayout):
        layout = layout.column()
        layout.label(text="Animated Materials Exporter")
        prop_split(layout, self, "export_obj", "Export Object")

        if not is_hackeroot():
            inc_box = layout.box()
            inc_box.prop(self, "is_custom_inc", text="Custom Include")
            if self.is_custom_inc:
                prop_split(inc_box, self, "include_name", "Include")

        path_box = layout.box()
        path_box.prop(self, "is_custom_path", text="Custom Path")
        if self.is_custom_path:
            path_box.label(text="The object name will be the file name", icon="QUESTION")
            prop_split(path_box, self, "export_path", "Export To")
        else:
            prop_split(path_box, self, "object_name", "Object Name")

        layout.operator(Z64_ExportAnimatedMaterials.bl_idname)


class Z64_AnimatedMaterialImportSettings(PropertyGroup):
    import_path: StringProperty(name="File", subtype="FILE_PATH")

    def draw_props(self, layout: UILayout):
        layout = layout.column()
        layout.label(text="Animated Materials Importer")
        prop_split(layout, self, "import_path", "Import From")
        layout.operator(Z64_ImportAnimatedMaterials.bl_idname)


classes = (
    Z64_AnimatedMatColorKeyFrame,
    Z64_AnimatedMatColorParams,
    Z64_AnimatedMatTexScrollItem,
    Z64_AnimatedMatTexScrollParams,
    Z64_AnimatedMatTexCycleTexture,
    Z64_AnimatedMatTexCycleKeyFrame,
    Z64_AnimatedMatTexCycleParams,
    Z64_AnimatedMatTexTimedCycleKeyFrame,
    Z64_AnimatedMatTexTimedCycleParams,
    Z64_AnimatedMatTextureParams,
    Z64_AnimatedMatMultiTextureParams,
    Z64_AnimatedMatTriIndexItem,
    Z64_AnimatedMatSurfaceSwapParams,
    Z64_AnimatedMaterialItem,
    Z64_AnimatedMaterial,
    Z64_AnimatedMaterialProperty,
    Z64_AnimatedMaterialExportSettings,
    Z64_AnimatedMaterialImportSettings,
)


def animated_mats_props_register():
    for cls in classes:
        register_class(cls)


def animated_mats_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
