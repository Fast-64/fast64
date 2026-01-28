import os
from typing import NamedTuple

import bpy
from bpy.types import PropertyGroup, Action, UILayout, Scene, Context

if bpy.app.version >= (5, 0, 0):
    from bpy.types import ActionSlot

from bpy.utils import register_class, unregister_class
from bpy.props import (
    BoolProperty,
    StringProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.path import abspath, clean_name

from ...utility import (
    decompFolderMessage,
    directory_ui_warnings,
    run_and_draw_errors,
    path_ui_warnings,
    draw_and_check_tab,
    multilineLabel,
    prop_split,
    intToHex,
    upgrade_old_prop,
    toAlnum,
)
from ...utility_anim import get_slots, getFrameInterval, AddSubAction

from ..sm64_utility import import_rom_ui_warnings, int_from_str, string_int_prop, string_int_warning
from ..sm64_constants import MAX_U16, MIN_S16, MAX_S16, enumLevelNames

from .operators import (
    OperatorBase,
    SM64_PreviewAnim,
    SM64_AnimTableOps,
    SM64_AnimVariantOps,
    SM64_ImportAnim,
    SM64_SetActionSlotFromObj,
    SM64_SearchAnimPresets,
    SM64_SearchAnimatedBhvs,
    SM64_SearchAnimTablePresets,
)
from .constants import enum_anim_import_types, enum_anim_binary_import_types, enum_animated_behaviours, enum_anim_tables
from .classes import SM64_AnimFlags
from .utility import (
    dma_structure_context,
    get_action_props,
    get_dma_anim_name,
    get_dma_header_name,
    is_obj_animatable,
    anim_name_to_enum_name,
    action_name_to_anim_name,
    duplicate_name,
    table_name_to_enum,
    check_for_action_in_table,
    check_for_headers_in_table,
    get_active_diff_slot,
)
from .importing import get_enum_from_import_preset, update_table_preset


def draw_custom_or_auto(holder, layout: UILayout, prop: str, default: str, factor=0.5, **kwargs):
    use_custom_prop = "use_custom_" + prop
    name_split = layout.split(factor=factor)
    name_split.prop(holder, use_custom_prop, **kwargs)
    if getattr(holder, use_custom_prop):
        name_split.prop(holder, "custom_" + prop, text="")
    else:
        prop_size_label(name_split, text=default, icon="LOCKED")


def draw_forced(layout: UILayout, holder, prop: str, forced: bool):
    row = layout.row(align=True) if forced else layout.column()
    if forced:
        prop_size_label(row, text="", icon="LOCKED")
    row.alignment = "LEFT"
    row.enabled = not forced
    row.prop(holder, prop, invert_checkbox=not getattr(holder, prop) if forced else False)


def prop_size_label(layout: UILayout, **label_args):
    box = layout.box()
    box.scale_y = 0.5
    box.label(**label_args)
    return box


def draw_list_op(layout: UILayout, op_cls: OperatorBase, op_name: str, index=-1, text="", icon="", **op_args):
    col = layout.column()
    icon = icon or {"MOVE_UP": "TRIA_UP", "MOVE_DOWN": "TRIA_DOWN", "CLEAR": "TRASH"}.get(op_name) or op_name
    return op_cls.draw_props(col, icon, text, index=index, op_name=op_name, **op_args)


def draw_list_ops(layout: UILayout, op_cls: OperatorBase, index: int, **op_args):
    layout.label(text=str(index))
    ops = ("MOVE_UP", "MOVE_DOWN", "ADD", "REMOVE")
    for op_name in ops:
        draw_list_op(layout, op_cls, op_name, index, **op_args)


def set_if_different(owner, prop: str, value):
    if getattr(owner, prop) != value:
        setattr(owner, prop, value)


def on_flag_update(self: "SM64_AnimHeaderProperties", context: Context):
    use_int = context.scene.fast64.sm64.binary_export or dma_structure_context(context)
    self.set_flags(self.get_flags(not use_int), set_custom=not self.use_custom_flags)


class SM64_AnimHeaderProperties(PropertyGroup):
    expand_tab_in_action: BoolProperty(name="Header Properties", default=True)
    header_variant: IntProperty(name="Header Variant Number", min=0)

    use_custom_name: BoolProperty(name="Name")
    custom_name: StringProperty(name="Name", default="anim_00")
    use_custom_enum: BoolProperty(name="Enum")
    custom_enum: StringProperty(name="Enum", default="ANIM_00")
    use_manual_loop: BoolProperty(name="Manual Loop Points")
    start_frame: IntProperty(name="Start", min=0, max=MAX_S16)
    loop_start: IntProperty(name="Loop Start", min=0, max=MAX_S16)
    loop_end: IntProperty(name="End", min=0, max=MAX_S16)
    trans_divisor: IntProperty(
        name="Translation Divisor",
        description="(animYTransDivisor)\n"
        "If set to 0, the translation multiplier will be 1. "
        "Otherwise, the translation multiplier is determined by "
        "dividing the object's translation dividend (animYTrans) by this divisor",
        min=MIN_S16,
        max=MAX_S16,
    )
    use_custom_flags: BoolProperty(name="Set Custom Flags")
    custom_flags: StringProperty(name="Flags", default="ANIM_NO_LOOP", update=on_flag_update)
    # Some flags are inverted in the ui for readability, descriptions match ui behavior
    no_loop: BoolProperty(
        name="No Loop",
        description="(ANIM_FLAG_NOLOOP)\n"
        "When disabled, the animation will not repeat from the loop start after reaching the loop "
        "end frame",
        update=on_flag_update,
    )
    backwards: BoolProperty(
        name="Loop Backwards",
        description="(ANIM_FLAG_FORWARD/ANIM_FLAG_BACKWARD)\n"
        "When enabled, the animation will loop (or stop if looping is disabled) after reaching "
        "the loop start frame.\n"
        "Tipically used with animations which use acceleration to play an animation backwards",
        update=on_flag_update,
    )
    no_acceleration: BoolProperty(
        name="No Acceleration",
        description="(ANIM_FLAG_NO_ACCEL/ANIM_FLAG_2)\n"
        "When disabled, acceleration will not be used when calculating which animation frame is "
        "next",
        update=on_flag_update,
    )
    disabled: BoolProperty(
        name="No Shadow Translation",
        description="(ANIM_FLAG_DISABLED/ANIM_FLAG_5)\n"
        "When disabled, the animation translation will not be applied to shadows",
        update=on_flag_update,
    )
    only_vertical: BoolProperty(
        name="Only Vertical Translation",
        description="(ANIM_FLAG_HOR_TRANS)\n"
        "When enabled, only the animation vertical translation will be applied during rendering (takes priority over no translation and only horizontal)\n"
        "(shadows included), the horizontal translation will still be exported and included",
        update=on_flag_update,
    )
    only_horizontal: BoolProperty(
        name="Only Horizontal Translation",
        description="(ANIM_FLAG_VERT_TRANS)\n"
        "When enabled, only the animation horizontal translation will be applied during rendering (takes priority over no translation)\n"
        "(shadows included) the vertical translation will still be exported and included",
        update=on_flag_update,
    )
    no_trans: BoolProperty(
        name="No Translation",
        description="(ANIM_FLAG_NO_TRANS/ANIM_FLAG_6)\n"
        "When disabled, the animation translation will not be used during rendering\n"
        "(shadows included), the translation will still be exported and included",
        update=on_flag_update,
    )
    # Binary
    table_index: IntProperty(name="Table Index", min=0)

    def get_flags(self, allow_str: bool) -> SM64_AnimFlags | str:
        if self.use_custom_flags:
            result = SM64_AnimFlags.evaluate(self.custom_flags)
            if not allow_str and isinstance(result, str):
                raise ValueError("Failed to evaluate custom flags")
            return result
        value = SM64_AnimFlags(0)
        for prop, flag in SM64_AnimFlags.props_to_flags().items():
            if getattr(self, prop, False):
                value |= flag
        return value

    @property
    def int_flags(self):
        return self.get_flags(allow_str=False)

    def set_flags(self, value: SM64_AnimFlags | str, set_custom=True):
        if isinstance(value, SM64_AnimFlags):  # the value was fully evaluated
            for prop, flag in SM64_AnimFlags.props_to_flags().items():  # set prop flags
                set_if_different(self, prop, flag in value)
            if set_custom:
                if value not in SM64_AnimFlags.all_flags_with_prop():  # if a flag does not have a prop
                    set_if_different(self, "use_custom_flags", True)
                set_if_different(self, "custom_flags", intToHex(value, 2))
        elif isinstance(value, str):
            if set_custom:
                set_if_different(self, "custom_flags", value)
                set_if_different(self, "use_custom_flags", True)
        else:  # invalid
            raise ValueError(f"Invalid type: {value}")

    @property
    def manual_loop_range(self) -> tuple[int, int, int]:
        if self.use_manual_loop:
            return (self.start_frame, self.loop_start, self.loop_end)

    def get_loop_points(self, action: Action):
        if self.use_manual_loop:
            return self.manual_loop_range
        loop_start, loop_end = getFrameInterval(action, get_action_props(action).get_slot(action))
        return (0, loop_start, loop_end + 1)

    def get_name(self, actor_name: str, action: Action, dma=False) -> str:
        if dma:
            return get_dma_header_name(self.table_index)
        elif self.use_custom_name:
            return self.custom_name
        elif self.header_variant == 0:
            return toAlnum(f"{actor_name}_anim_{action.name}")
        else:
            main_header_name = get_action_props(action).headers[0].get_name(actor_name, action, dma)
            return toAlnum(f"{main_header_name}_{self.header_variant}")

    def get_enum(self, actor_name: str, action: Action) -> str:
        if self.use_custom_enum:
            return self.custom_enum
        elif self.use_custom_name:
            return anim_name_to_enum_name(self.get_name(actor_name, action))
        elif self.header_variant == 0:
            anim_name = action_name_to_anim_name(action.name)
            return anim_name_to_enum_name(f"{actor_name}_anim_{anim_name}")
        else:
            main_enum = get_action_props(action).headers[0].get_enum(actor_name, action)
            return f"{main_enum}_{self.header_variant}"

    def draw_flag_props(self, layout: UILayout, use_int_flags: bool = False):
        col = layout.column()
        custom_split = col.split()
        custom_split.prop(self, "use_custom_flags")
        if self.use_custom_flags:
            custom_split.prop(self, "custom_flags", text="")
            if use_int_flags:
                run_and_draw_errors(col, self.get_flags, False)
            return
        else:
            prop_size_label(custom_split, text=intToHex(self.int_flags, 2), icon="LOCKED")
        # Draw flag toggles
        row = col.row(align=True)
        row.prop(self, "no_loop", invert_checkbox=True, text="Loop", toggle=1)
        row.prop(self, "backwards", toggle=1)
        row.prop(self, "no_acceleration", invert_checkbox=True, text="Acceleration", toggle=1)
        if self.no_acceleration and self.backwards:
            col.label(text="Backwards has no porpuse without acceleration.", icon="INFO")

        trans_row = col.row(align=True)
        no_row = trans_row.row()
        no_row.enabled = not self.only_vertical and not self.only_horizontal
        no_row.prop(self, "no_trans", invert_checkbox=True, text="Translate", toggle=1)

        vert_row = trans_row.row()
        vert_row.prop(self, "only_vertical", text="Only Vertical", toggle=1)

        hor_row = trans_row.row()
        hor_row.enabled = not self.only_vertical
        hor_row.prop(self, "only_horizontal", text="Only Horizontal", toggle=1)
        if self.only_vertical and self.only_horizontal:
            multilineLabel(
                layout=col,
                text='"Only Vertical" takes priority, only vertical\n translation will be used.',
                icon="INFO",
            )
        if (self.only_vertical or self.only_horizontal) and self.no_trans:
            multilineLabel(
                layout=col,
                text='"Only Horizontal" and "Only Vertical" take\n priority over no translation.',
                icon="INFO",
            )

        disabled_row = trans_row.row()
        disabled_row.enabled = not self.no_trans and not self.only_vertical
        disabled_row.prop(self, "disabled", invert_checkbox=True, text="Shadow", toggle=1)

    def draw_frame_range(self, layout: UILayout, action: Action):
        split = layout.split()
        split.prop(self, "use_manual_loop")
        if self.use_manual_loop:
            split = layout.split()
            split.prop(self, "start_frame")
            split.prop(self, "loop_start")
            split.prop(self, "loop_end")
        else:
            start, loop_start, end = self.get_loop_points(action)
            prop_size_label(split, text=f"Start {start}, Loop Start {loop_start}, End {end}", icon="LOCKED")

    def draw_names(self, layout: UILayout, action: Action, actor_name: str, gen_enums: bool, dma: bool):
        col = layout.column()
        if gen_enums:
            draw_custom_or_auto(self, col, "enum", self.get_enum(actor_name, action))
        draw_custom_or_auto(self, col, "name", self.get_name(actor_name, action, dma))

    def draw_props(
        self,
        layout: UILayout,
        action: Action,
        in_table: bool,
        table_elements: list["SM64_AnimTableElementProperties"],
        updates_table: bool,
        dma: bool,
        export_type: str,
        actor_name: str,
        gen_enums: bool,
    ):
        col = layout.column()
        split = col.split()
        preview_op = SM64_PreviewAnim.draw_props(split)
        preview_op.played_header = self.header_variant
        preview_op.played_action = action.name
        # Don´t show index or name in table props
        if not in_table:
            draw_list_op(
                split,
                SM64_AnimTableOps,
                "ADD",
                text="Add To Table (Again)"
                if check_for_headers_in_table([self], table_elements, dma)
                else "Add To Table",
                icon="LINKED",
                action_name=action.name,
                header_variant=self.header_variant,
            )
            if (export_type == "C" and dma) or (export_type == "Binary" and updates_table):
                prop_split(col, self, "table_index", "Table Index")
        if not dma and export_type == "C":
            self.draw_names(col, action, actor_name, gen_enums, dma)
        col.separator()

        prop_split(col, self, "trans_divisor", "Translation Divisor")
        self.draw_frame_range(col, action)
        self.draw_flag_props(col, use_int_flags=dma or export_type.endswith("Binary"))


# workaround for garbage collector bug
get_slot_enum_items_cache = []


def get_slot_enum(self, context):
    """Generate enum items from the current action’s slots."""
    global get_slot_enum_items_cache

    action = self.id_data

    get_slot_enum_items_cache.clear()
    for i, slot in enumerate(get_slots(action).values()):
        get_slot_enum_items_cache.append(
            (
                str(slot.identifier),
                str(slot.name_display),
                f"Slot {i}",
                "OBJECT_DATA",
                i,
            ),
        )

    return get_slot_enum_items_cache


def get_current_slot(self):
    action = self.id_data
    slot_keys = list(get_slots(action).keys())
    if self.slot_identifier in slot_keys:
        return slot_keys.index(self.slot_identifier)
    return 0


def set_current_slot(self, value):
    self.slot_identifier = list(get_slots(self.id_data).keys())[value]


class SM64_ActionAnimProperty(PropertyGroup):
    """Properties in Action.fast64.sm64.animation"""

    slot_identifier: StringProperty(name="Slot Identifier")
    slot_enum: EnumProperty(name="Action Slot", items=get_slot_enum, get=get_current_slot, set=set_current_slot)

    header: PointerProperty(type=SM64_AnimHeaderProperties)
    variants_tab: BoolProperty(name="Header Variants")
    header_variants: CollectionProperty(type=SM64_AnimHeaderProperties)
    use_custom_file_name: BoolProperty(name="File Name")
    custom_file_name: StringProperty(name="File Name", default="anim_00.inc.c")
    use_custom_max_frame: BoolProperty(name="Max Frame")
    custom_max_frame: IntProperty(name="Max Frame", min=1, max=MAX_U16, default=1)
    reference_tables: BoolProperty(name="Reference Tables")
    indices_table: StringProperty(name="Indices Table", default="anim_00_indices")
    values_table: StringProperty(name="Value Table", default="anim_00_values")
    # Binary, toad anim 0 for defaults
    indices_address: StringProperty(name="Indices Table", default=intToHex(0x00A42150))
    values_address: StringProperty(name="Value Table", default=intToHex(0x00A40CC8))
    start_address: StringProperty(name="Start Address", default=intToHex(0x00A40CC8))
    end_address: StringProperty(name="End Address", default=intToHex(0x00A42265))

    @property
    def headers(self) -> list[SM64_AnimHeaderProperties]:
        return [self.header] + list(self.header_variants)

    @property
    def dma_name(self):
        return get_dma_anim_name([header.table_index for header in self.headers])

    def get_name(self, action: Action, dma=False) -> str:
        if dma:
            return self.dma_name
        return toAlnum(f"anim_{action.name}")

    def get_file_name(self, action: Action, export_type: str, dma=False) -> str:
        if not export_type in {"C", "Insertable Binary"}:
            return ""
        if export_type == "C" and dma:
            return f"{self.dma_name}.inc.c"
        elif self.use_custom_file_name:
            return self.custom_file_name
        else:
            name = clean_name(f"anim_{action.name}", replace=" ")
            return name + (".inc.c" if export_type == "C" else ".insertable")

    def get_slot(self, action: Action):
        if bpy.app.version < (5, 0, 0):
            return None
        slots = get_slots(action)
        if len(slots) == 1:
            return next(iter(slots.values()))
        return slots.get(get_action_props(action).slot_identifier)

    def get_max_frame(self, action: Action) -> int:
        if self.use_custom_max_frame:
            return self.custom_max_frame
        loop_ends: list[int] = [getFrameInterval(action, self.get_slot(action))[1]]
        header_props: SM64_AnimHeaderProperties
        for header_props in self.headers:
            loop_ends.append(header_props.get_loop_points(action)[2])

        return max(loop_ends)

    def update_variant_numbers(self):
        for i, variant in enumerate(self.headers):
            variant.header_variant = i

    def draw_variants(
        self,
        layout: UILayout,
        action: Action,
        dma: bool,
        actor_name: str,
        header_args: list,
    ):
        col = layout.column()
        op_row = col.row()
        op_row.label(text=f"Header Variants ({len(self.headers)})", icon="NLA")
        draw_list_op(op_row, SM64_AnimVariantOps, "CLEAR", action_name=action.name)

        for i, header_props in enumerate(self.headers):
            if i != 0:
                col.separator()

            row = col.row()
            if draw_and_check_tab(
                row,
                header_props,
                "expand_tab_in_action",
                header_props.get_name(actor_name, action, dma),
            ):
                header_props.draw_props(col, *header_args)
            op_row = row.row()
            op_row.alignment = "RIGHT"
            draw_list_ops(op_row, SM64_AnimVariantOps, i, action_name=action.name)

    def draw_references(self, layout: UILayout, is_binary: bool = False):
        col = layout.column()
        col.prop(self, "reference_tables")
        if not self.reference_tables:
            return
        if is_binary:
            string_int_prop(col, self, "indices_address", "Indices Table")
            string_int_prop(col, self, "values_address", "Value Table")
        else:
            prop_split(col, self, "indices_table", "Indices Table")
            prop_split(col, self, "values_table", "Value Table")

    def draw_props(
        self,
        layout: UILayout,
        action: Action,
        specific_variant: int | None,
        in_table: bool,
        updates_table: bool,
        export_seperately: bool,
        export_type: str,
        actor_name: str,
        gen_enums: bool,
        dma: bool,
        table_elements: list["SM64_AnimTableElementProperties"] = None,
    ):
        table_elements = table_elements or []
        # Args to pass to the headers
        header_args = (action, in_table, table_elements, updates_table, dma, export_type, actor_name, gen_enums)

        col = layout.column()
        if specific_variant is not None:
            col.label(text="Action Properties", icon="ACTION")

        if bpy.app.version >= (5, 0, 0):
            slots = get_slots(action)
            if len(slots) > 1:
                prop_split(col, self, "slot_enum", "Action Slot", icon="ACTION_SLOT")
                slot = get_active_diff_slot(bpy.context, action)
                text = None
                if slot is not None:
                    text = f"Set to active slot ({slot.name_display})"
                SM64_SetActionSlotFromObj.draw_props(col, text=text, action_name=action.name)
            elif len(slots) == 1:
                col.label(text=f"Action Slot: {list(slots.values())[0].name_display}", icon="ACTION_SLOT")
            else:
                box = col.box()
                box.alert = True
                box.label(text="Action has no object slots.", icon="ERROR")
                box.alert = False
                AddSubAction.draw_props(box, action_name=action.name)
            col.separator()

        if not in_table:
            if check_for_action_in_table(action, table_elements, dma):
                if not check_for_headers_in_table(self.headers, table_elements, dma):
                    draw_list_op(
                        col,
                        SM64_AnimTableOps,
                        "ADD_ALL",
                        text="Add Remaining Variants To Table",
                        icon="LINKED",
                        action_name=action.name,
                    )
                    col.separator()
            else:
                draw_list_op(
                    col,
                    SM64_AnimTableOps,
                    "ADD_ALL",
                    text="Add All Variants To Table",
                    icon="LINKED",
                    action_name=action.name,
                )
                col.separator()
            if export_type == "Binary" and not dma:
                string_int_prop(col, self, "start_address", "Start Address")
                string_int_prop(col, self, "end_address", "End Address")
        if export_type != "Binary" and (export_seperately or not in_table):
            if not dma or export_type == "Insertable Binary":  # not c dma or insertable
                text = "File Name"
                if not in_table and not export_seperately:
                    text = "File Name (individual action export)"
                draw_custom_or_auto(self, col, "file_name", self.get_file_name(action, export_type), text=text)
            elif not in_table:  # C DMA forced auto name
                split = col.split(factor=0.5)
                split.label(text="File Name")
                file_name = self.get_file_name(action, export_type, dma)
                prop_size_label(split, text=file_name, icon="LOCKED")
        if dma or not self.reference_tables:  # DMA tables don´t allow references
            draw_custom_or_auto(self, col, "max_frame", str(self.get_max_frame(action)))
        if not dma:
            self.draw_references(col, is_binary=export_type.endswith("Binary"))
        col.separator()

        if specific_variant is not None:
            if specific_variant < 0 or specific_variant >= len(self.headers):
                col.box().label(text="Header variant does not exist.", icon="ERROR")
            else:
                col.label(text="Variant Properties", icon="NLA")
                self.headers[specific_variant].draw_props(col, *header_args)
        else:
            self.draw_variants(col, action, dma, actor_name, header_args)


class ActionHeaderTuple(NamedTuple):
    action: Action
    header: SM64_AnimHeaderProperties


class SM64_AnimTableElementProperties(PropertyGroup):
    expand_tab: BoolProperty()
    action_prop: PointerProperty(name="Action", type=Action)

    variant: IntProperty(name="Variant", min=0)
    reference: BoolProperty(name="Reference")
    # Toad example
    header_name: StringProperty(name="Header Reference", default="toad_seg6_anim_0600B66C")
    header_address: StringProperty(name="Header Reference", default=intToHex(0x0600B75C))
    use_custom_enum: BoolProperty(name="Enum")
    custom_enum: StringProperty(name="Enum Name")

    def get_enum(self, can_reference: bool, actor_name: str, prev_enums: dict[str, int]):
        """Updates prev_enums"""
        enum = ""
        if self.use_custom_enum:
            self.custom_enum: str
            enum = self.custom_enum
        elif can_reference and self.reference:
            enum = duplicate_name(anim_name_to_enum_name(self.header_name), prev_enums)
        else:
            action, header = self.get_action_header(can_reference)
            if header and action:
                enum = duplicate_name(header.get_enum(actor_name, action), prev_enums)
        return enum

    def get_action_header(self, can_reference: bool):
        self.variant: int
        self.action_prop: Action
        if (not can_reference or not self.reference) and self.action_prop:
            action_props = get_action_props(self.action_prop)
            headers = action_props.headers
            if self.variant < len(headers):
                return ActionHeaderTuple(self.action_prop, headers[self.variant])
        return ActionHeaderTuple(None, None)

    def get_action(self, can_reference: bool) -> Action | None:
        return self.get_action_header(can_reference).action

    def get_header(self, can_reference: bool) -> SM64_AnimHeaderProperties | None:
        return self.get_action_header(can_reference).header

    def set_variant(self, action: Action, variant: int):
        self.action_prop = action
        self.variant = variant

    def draw_reference(
        self, layout: UILayout, export_type: str = "C", gen_enums: bool = False, prev_enums: dict[str, int] = None
    ):
        if export_type.endswith("Binary"):
            string_int_prop(layout, self, "header_address", "Header Address")
            return
        split = layout.split()
        if gen_enums:
            draw_custom_or_auto(self, split, "enum", self.get_enum(True, "", prev_enums), factor=0.3)
        split.prop(self, "header_name", text="")

    def draw_props(
        self,
        row: UILayout,  # left side of the row for table ops
        prop_layout: UILayout,
        index: int,
        dma: bool,
        updates_table: bool,
        export_seperately: bool,
        export_type: str,
        gen_enums: bool,
        actor_name: str,
        prev_enums: dict[str, int],
    ):
        can_reference = not dma
        col = prop_layout.column()
        if can_reference:
            reference_row = row.row()
            reference_row.alignment = "LEFT"
            reference_row.prop(self, "reference")
            if self.reference:
                self.draw_reference(col, export_type, gen_enums, prev_enums)
                return
        action_row = row.row()
        action_row.alignment = "EXPAND"
        action_row.prop(self, "action_prop", text="")

        if not self.action_prop:
            col.box().label(text="Header´s action does not exist.", icon="ERROR")
            return
        action = self.action_prop
        action_props = get_action_props(action)

        variant_split = col.split(factor=0.3)
        variant_split.prop(self, "variant")

        if 0 <= self.variant < len(action_props.headers):
            header_props = self.get_header(can_reference)
            if dma:
                name = get_dma_header_name(index)
            else:
                name = header_props.get_name(actor_name, action, dma)
            if gen_enums:
                draw_custom_or_auto(
                    self,
                    variant_split,
                    "enum",
                    self.get_enum(can_reference, actor_name, prev_enums),
                    factor=0.3,
                )
            tab_name = name + (f" (Variant {self.variant})" if self.variant > 0 else "")
            if not draw_and_check_tab(col, self, "expand_tab", tab_name):
                return

        action_props.draw_props(
            layout=col,
            action=action,
            specific_variant=self.variant,
            in_table=True,
            updates_table=updates_table,
            export_seperately=export_seperately,
            export_type=export_type,
            actor_name=actor_name,
            gen_enums=gen_enums,
            dma=dma,
        )


class SM64_AnimImportProperties(PropertyGroup):
    run_decimate: BoolProperty(name="Run Decimate (Allowed Change)", default=True)
    decimate_margin: FloatProperty(
        name="Error Margin",
        default=0.025,
        min=0.0,
        max=0.025,
        description="Use blender's builtin decimate (allowed change) operator to clean up all the "
        "keyframes, generally the better option compared to clean keyframes but can be slow",
    )

    continuity_filter: BoolProperty(name="Continuity Filter", default=True)
    force_quaternion: BoolProperty(
        name="Force Quaternions",
        description="Changes bones to quaternion rotation mode, can break existing actions",
    )

    clear_table: BoolProperty(name="Clear Table On Import", default=True)
    import_type: EnumProperty(items=enum_anim_import_types, name="Import Type", default="C")
    preset: bpy.props.EnumProperty(
        items=enum_anim_tables,
        name="Preset",
        update=update_table_preset,
        default="Mario",
    )
    decomp_path: StringProperty(name="Decomp Path", subtype="FILE_PATH", default="")
    binary_import_type: EnumProperty(
        items=enum_anim_binary_import_types,
        name="Binary Import Type",
        default="Table",
    )
    read_entire_table: BoolProperty(name="Read Entire Table", default=True)
    check_null: BoolProperty(name="Check NULL Delimiter", default=True)
    table_size_prop: IntProperty(name="Size", min=1)
    table_index_prop: IntProperty(name="Index", min=0)
    ignore_bone_count: BoolProperty(
        name="Ignore bone count",
        description="The armature bone count won´t be used when importing, a safety check will be skipped and old "
        "fast64 animations won´t import, needed to import bowser's broken animation",
    )
    preset_animation: EnumProperty(name="Preset Animation", items=get_enum_from_import_preset)

    rom: StringProperty(name="Import ROM", subtype="FILE_PATH")
    table_address: StringProperty(name="Address", default=intToHex(0x0600FC48))  # Toad
    animation_address: StringProperty(name="Address", default=intToHex(0x0600B75C))
    is_segmented_address_prop: BoolProperty(name="Is Segmented Address", default=True)
    level: EnumProperty(items=enumLevelNames, name="Level", default="castle_inside")
    dma_table_address: StringProperty(name="DMA Table Address", default="0x4EC000")

    read_from_rom: BoolProperty(
        name="Read From Import ROM",
        description="When enabled, the importer will read from the import ROM given an "
        "address not included in the insertable file's defined pointers",
    )

    path: StringProperty(name="Path", subtype="FILE_PATH", default="anims/")
    use_custom_name: BoolProperty(name="Use Custom Name", default=True)

    @property
    def binary(self) -> bool:
        return self.import_type.endswith("Binary")

    @property
    def table_index(self):
        if self.read_entire_table:
            return
        elif self.preset_animation == "Custom" or not self.use_preset:
            return self.table_index_prop
        else:
            return int_from_str(self.preset_animation)

    @property
    def address(self):
        if self.import_type != "Binary":
            return
        elif self.binary_import_type == "DMA":
            return int_from_str(self.dma_table_address)
        elif self.binary_import_type == "Table":
            return int_from_str(self.table_address)
        else:
            return int_from_str(self.animation_address)

    @property
    def is_segmented_address(self):
        if self.import_type != "Binary":
            return
        return (
            self.is_segmented_address_prop
            if self.import_type == "Binary" and self.binary_import_type in {"Table", "Animation"}
            else False
        )

    @property
    def table_size(self):
        return None if self.check_null else self.table_size_prop

    @property
    def use_preset(self):
        return self.import_type != "Insertable Binary" and self.preset != "Custom"

    def upgrade_old_props(self, scene: Scene):
        upgrade_old_prop(
            self,
            "animation_address",
            scene,
            "animStartImport",
            fix_forced_base_16=True,
        )
        upgrade_old_prop(self, "is_segmented_address_prop", scene, "animIsSegPtr")
        upgrade_old_prop(self, "level", scene, "levelAnimImport")
        upgrade_old_prop(self, "table_index_prop", scene, "animListIndexImport")
        if scene.pop("isDMAImport", False):
            self.binary_import_type = "DMA"
        elif scene.pop("animIsAnimList", True):
            self.binary_import_type = "Table"

    def draw_clean_up(self, layout: UILayout):
        col = layout.column()
        col.prop(self, "run_decimate")
        if self.run_decimate:
            prop_split(col, self, "decimate_margin", "Error Margin")
            col.box().label(text="While very useful and stable, it can be very slow", icon="INFO")
        col.separator()

        row = col.row()
        row.prop(self, "force_quaternion")
        continuity_row = row.row()
        continuity_row.enabled = not self.force_quaternion
        continuity_row.prop(
            self,
            "continuity_filter",
            text="Continuity Filter" + (" (Always on)" if self.force_quaternion else ""),
            invert_checkbox=not self.continuity_filter if self.force_quaternion else False,
        )

    def draw_path(self, layout: UILayout):
        prop_split(layout, self, "path", "Directory or File Path")
        path_ui_warnings(layout, abspath(self.path))

    def draw_c(self, layout: UILayout, decomp: os.PathLike = ""):
        col = layout.column()
        if self.preset == "Custom":
            self.draw_path(col)
        else:
            col.label(text="Uses scene decomp path by default", icon="INFO")
            prop_split(col, self, "decomp_path", "Decomp Path")
            directory_ui_warnings(col, abspath(self.decomp_path or decomp))
        col.prop(self, "use_custom_name")

    def draw_import_rom(self, layout: UILayout, import_rom: os.PathLike = ""):
        col = layout.column()
        col.label(text="Uses scene import ROM by default", icon="INFO")
        prop_split(col, self, "rom", "Import ROM")
        return import_rom_ui_warnings(col, abspath(self.rom or import_rom))

    def draw_table_settings(self, layout: UILayout):
        row = layout.row(align=True)
        left_row = row.row(align=True)
        left_row.alignment = "LEFT"
        left_row.prop(self, "read_entire_table")
        left_row.prop(self, "check_null")
        right_row = row.row(align=True)
        right_row.alignment = "EXPAND"
        if not self.read_entire_table:
            right_row.prop(self, "table_index_prop", text="Index")
        elif not self.check_null:
            right_row.prop(self, "table_size_prop")

    def draw_binary(self, layout: UILayout, import_rom: os.PathLike):
        col = layout.column()
        self.draw_import_rom(col, import_rom)
        col.separator()

        if self.preset != "Custom":
            split = col.split()
            split.prop(self, "read_entire_table")
            if not self.read_entire_table:
                SM64_SearchAnimPresets.draw_props(split, self, "preset_animation", "")
                if self.preset_animation == "Custom":
                    split.prop(self, "table_index_prop", text="Index")
            return
        col.prop(self, "ignore_bone_count")
        prop_split(col, self, "binary_import_type", "Animation Type")
        if self.binary_import_type == "DMA":
            string_int_prop(col, self, "dma_table_address", "DMA Table Address")
            split = col.split()
            split.prop(self, "read_entire_table")
            if not self.read_entire_table:
                split.prop(self, "table_index_prop", text="Index")
            return

        split = col.split()
        split.prop(self, "is_segmented_address_prop")
        if self.binary_import_type == "Table":
            split.prop(self, "table_address", text="")
            string_int_warning(col, self.table_address)
        elif self.binary_import_type == "Animation":
            split.prop(self, "animation_address", text="")
            string_int_warning(col, self.animation_address)
        prop_split(col, self, "level", "Level")
        if self.binary_import_type == "Table":  # Draw settings after level
            self.draw_table_settings(col)

    def draw_insertable_binary(self, layout: UILayout, import_rom: os.PathLike):
        col = layout.column()
        self.draw_path(col)
        col.separator()

        col.label(text="Animation type will be read from the files", icon="INFO")

        table_box = col.column()
        table_box.label(text="Table Imports", icon="ANIM")
        self.draw_table_settings(table_box)
        col.separator()

        col.prop(self, "read_from_rom")
        if self.read_from_rom:
            self.draw_import_rom(col, import_rom)
            prop_split(col, self, "level", "Level")

        col.prop(self, "ignore_bone_count")

    def draw_props(self, layout: UILayout, import_rom: os.PathLike = "", decomp: os.PathLike = ""):
        col = layout.column()

        prop_split(col, self, "import_type", "Type")

        if self.import_type in {"C", "Binary"}:
            SM64_SearchAnimTablePresets.draw_props(col, self, "preset", "Preset")
            col.separator()

        if self.import_type == "C":
            self.draw_c(col, decomp)
        elif self.binary:
            if self.import_type == "Binary":
                self.draw_binary(col, import_rom)
            elif self.import_type == "Insertable Binary":
                self.draw_insertable_binary(col, import_rom)
        col.separator()

        self.draw_clean_up(col)
        col.prop(self, "clear_table")
        SM64_ImportAnim.draw_props(col)


class SM64_AnimProperties(PropertyGroup):
    version: IntProperty(name="SM64_AnimProperties Version", default=0)
    cur_version = 1  # version after property migration

    played_header: IntProperty(min=0)
    played_action: PointerProperty(name="Action", type=Action)
    played_cached_start: IntProperty(min=0)
    played_cached_loop_start: IntProperty(min=0)
    played_cached_loop_end: IntProperty(min=0)

    importing: PointerProperty(type=SM64_AnimImportProperties)

    def upgrade_old_props(self, scene: Scene):
        self.importing.upgrade_old_props(scene)

        # Export
        loop = scene.pop("loopAnimation", None)
        start_address = scene.pop("animExportStart", None)
        end_address = scene.pop("animExportEnd", None)

        for action in bpy.data.actions:
            action_props: SM64_ActionAnimProperty = get_action_props(action)
            action_props.header: SM64_AnimHeaderProperties
            if loop is not None:
                action_props.header.set_flags(SM64_AnimFlags(0) if loop else SM64_AnimFlags.ANIM_FLAG_NOLOOP)
            if start_address is not None:
                action_props.start_address = intToHex(int(start_address, 16))
            if end_address is not None:
                action_props.end_address = intToHex(int(end_address, 16))

        insertable_path = scene.pop("animInsertableBinaryPath", "")
        is_dma = scene.pop("loopAnimation", None)
        update_table = scene.pop("animExportStart", None)
        update_behavior = scene.pop("animExportEnd", None)
        beginning_animation = scene.pop("animListIndexExport", None)
        for obj in bpy.data.objects:
            if not is_obj_animatable(obj):
                continue
            anim_props: SM64_ArmatureAnimProperties = obj.fast64.sm64.animation
            if is_dma is not None:
                anim_props.is_dma = is_dma
            if update_table is not None:
                anim_props.update_table = update_table
            if update_behavior is not None:
                anim_props.update_behavior = update_behavior
            if beginning_animation is not None:
                anim_props.beginning_animation = beginning_animation
            if insertable_path is not None:  # Ignores directory
                anim_props.use_custom_file_name = True
                anim_props.custom_file_name = os.path.split(insertable_path)[0]

        # Deprecated:
        # - addr 0x27 was a pointer to a load anim cmd that would be used to update table pointers
        # the actual table pointer is used instead
        # - addr 0x28 was a pointer to a animate cmd that would be updated to the beggining
        # animation a behavior script pointer is used instead so both load an animate can be updated
        # easily without much thought

        self.version = 1

    def upgrade_changed_props(self, scene):
        if self.version != self.cur_version:
            self.upgrade_old_props(scene)
            self.version = SM64_AnimProperties.cur_version


class SM64_ArmatureAnimProperties(PropertyGroup):
    version: IntProperty(name="SM64_AnimProperties Version", default=0)
    cur_version = 1  # version after property migration

    is_dma: BoolProperty(name="Is DMA Export")
    dma_folder: StringProperty(name="DMA Folder", default="assets/anims/")
    update_table: BoolProperty(
        name="Update Table On Action Export",
        description="Update table outside of table exports",
        default=True,
    )

    # Table
    elements: CollectionProperty(type=SM64_AnimTableElementProperties)

    export_seperately_prop: BoolProperty(name="Export All Seperately")
    write_data_seperately: BoolProperty(name="Write Data Seperately")
    null_delimiter: BoolProperty(name="Add Null Delimiter")
    override_files_prop: BoolProperty(name="Override Table and Data Files", default=True)
    gen_enums: BoolProperty(name="Generate Enums", default=True)
    use_custom_table_name: BoolProperty(name="Table Name")
    custom_table_name: StringProperty(name="Table Name", default="mario_anims")
    # Binary, Toad animation table example
    data_address: StringProperty(
        name="Data Address",
        default=intToHex(0x00A3F7E0),
    )
    data_end_address: StringProperty(
        name="Data End",
        default=intToHex(0x00A466C0),
    )
    address: StringProperty(name="Table Address", default=intToHex(0x00A46738))
    end_address: StringProperty(name="Table End", default=intToHex(0x00A4675C))
    update_behavior: BoolProperty(name="Update Behavior", default=True)
    behaviour: bpy.props.EnumProperty(items=enum_animated_behaviours, default=intToHex(0x13002EF8))
    behavior_address_prop: StringProperty(name="Behavior Address", default=intToHex(0x13002EF8))
    beginning_animation: StringProperty(name="Begining Animation", default="0x00")
    # Mario animation table
    dma_address: StringProperty(name="DMA Table Address", default=intToHex(0x4EC000))
    dma_end_address: StringProperty(name="DMA Table End", default=intToHex(0x4EC000 + 0x8DC20))

    use_custom_file_name: BoolProperty(name="File Name")
    custom_file_name: StringProperty(name="File Name", default="toad.insertable")

    @property
    def behavior_address(self) -> int:
        if self.behaviour == "Custom":
            return int_from_str(self.behavior_address_prop)
        return int_from_str(self.behaviour)

    @property
    def export_seperately(self):
        return self.is_dma or self.export_seperately_prop

    @property
    def override_files(self) -> bool:
        return not self.export_seperately or self.override_files_prop

    @property
    def actions(self) -> list[Action]:
        actions = []
        for element_props in self.elements:
            action = element_props.get_action(not self.is_dma)
            if action and action not in actions:
                actions.append(action)
        return actions

    def get_table_name(self, actor_name: str) -> str:
        if self.use_custom_table_name:
            return self.custom_table_name
        return f"{actor_name}_anims"

    def get_enum_name(self, actor_name: str):
        return table_name_to_enum(self.get_table_name(actor_name))

    def get_enum_end(self, actor_name: str):
        table_name = self.get_table_name(actor_name)
        return f"{table_name.upper()}_END"

    def get_table_file_name(self, actor_name: str, export_type: str) -> str:
        if not export_type in {"C", "Insertable Binary"}:
            return ""
        elif export_type == "Insertable Binary":
            if self.use_custom_file_name:
                return self.custom_file_name
            return clean_name(actor_name + ("_dma_table" if self.is_dma else "_table")) + ".insertable"
        else:
            return "table.inc.c"

    def draw_element(
        self,
        layout: UILayout,
        index: int,
        table_element: SM64_AnimTableElementProperties,
        export_type: str,
        actor_name: str,
        prev_enums: dict[str, int],
    ):
        col = layout.column()
        row = col.row()
        left_row = row.row()
        left_row.alignment = "EXPAND"
        op_row = row.row()
        op_row.alignment = "RIGHT"
        draw_list_ops(op_row, SM64_AnimTableOps, index)

        table_element.draw_props(
            left_row,
            col,
            index,
            self.is_dma,
            self.update_table,
            self.export_seperately,
            export_type,
            export_type == "C" and self.gen_enums and not self.is_dma,
            actor_name,
            prev_enums,
        )

    def draw_table(self, layout: UILayout, export_type: str, actor_name: str):
        col = layout.column()

        op_row = col.row()
        op_row.label(
            text="Headers " + (f"({len(self.elements)})" if self.elements else "(Empty)"),
            icon="NLA",
        )
        draw_list_op(op_row, SM64_AnimTableOps, "ADD")
        draw_list_op(op_row, SM64_AnimTableOps, "CLEAR")

        if not self.elements:
            return

        box = col.box().column()
        actions_dups: dict[Action, list[int]] = {}
        if self.is_dma:
            actions_repeats: dict[Action, list[int]] = {}  # possible dups
            last_action = None
            for i, element_props in enumerate(self.elements):
                action: Action = element_props.get_action(can_reference=False)
                if action != last_action:
                    if action in actions_repeats:
                        actions_repeats[action].append(i)
                        if action not in actions_dups:
                            actions_dups[action] = actions_repeats[action]
                    else:
                        actions_repeats[action] = [i]
                last_action = action

        if actions_dups:
            lines = [f'Action "{a.name}", Headers: {i}' for a, i in actions_dups.items()]
            warn_box = box.box()
            warn_box.alert = True
            multilineLabel(
                warn_box,
                "In DMA tables, headers for each action must be \n"
                "in one sequence or the data will be duplicated.\n"
                "This will be handeled automatically but is undesirable.\n"
                f'Data duplicate{"s" if len(actions_dups) > 1 else ""} in:\n' + "\n".join(lines),
                "INFO",
            )

        prev_enums = {}
        element_props: SM64_AnimTableElementProperties
        for i, element_props in enumerate(self.elements):
            if i != 0:
                box.separator()
            element_box = box.column()
            action = element_props.get_action(not self.is_dma)
            if action in actions_dups:
                other_actions = [j for j in actions_dups[action] if j != i]
                element_box.box().label(text=f"Action duplicates at {other_actions}")
            self.draw_element(element_box, i, element_props, export_type, actor_name, prev_enums)

    def draw_c_settings(self, layout: UILayout, header_type: str):
        col = layout.column()
        if self.is_dma:
            prop_split(col, self, "dma_folder", "Folder", icon="FILE_FOLDER")
            if header_type == "Custom":
                col.label(text="This folder will be relative to your custom path")
            else:
                decompFolderMessage(col)
            return

    def draw_props(self, layout: UILayout, export_type: str, header_type: str, actor_name: str, bhv_export: bool):
        col = layout.column()
        col.prop(self, "is_dma")
        if export_type == "C":
            self.draw_c_settings(col, header_type)
        if export_type != "Insertable Binary" and not self.is_dma:
            col.prop(self, "update_table")

        if self.is_dma:
            if export_type == "Binary":
                string_int_prop(col, self, "dma_address", "Table Address")
                string_int_prop(col, self, "dma_end_address", "Table End")
            elif export_type == "C":
                multilineLabel(
                    col,
                    "The export will follow the vanilla DMA naming\n"
                    "conventions (anim_xx.inc.c, anim_xx, anim_xx_values, etc).",
                    icon="INFO",
                )
        else:
            if export_type == "C":
                draw_custom_or_auto(self, col, "table_name", self.get_table_name(actor_name))
                col.prop(self, "gen_enums")
                if self.gen_enums:
                    multilineLabel(
                        col.box(),
                        f"Enum List Name: {self.get_enum_name(actor_name)}\n"
                        f"End Enum: {self.get_enum_end(actor_name)}",
                    )
                col.separator()
                col.prop(self, "export_seperately_prop")
                draw_forced(col, self, "override_files_prop", not self.export_seperately)
                if bhv_export:
                    prop_split(col, self, "beginning_animation", "Beginning Animation")
            elif export_type == "Binary":
                string_int_prop(col, self, "address", "Table Address")
                string_int_prop(col, self, "end_address", "Table End")

                box = col.box().column()
                box.prop(self, "update_behavior")
                if self.update_behavior:
                    multilineLabel(
                        box,
                        "Will update the LOAD_ANIMATIONS and ANIMATE commands.\n"
                        "Does not raise an error if there is no ANIMATE command",
                        "INFO",
                    )
                    SM64_SearchAnimatedBhvs.draw_props(box, self, "behaviour", "Behaviour")
                    if self.behaviour == "Custom":
                        prop_split(box, self, "behavior_address_prop", "Behavior Address")
                    prop_split(box, self, "beginning_animation", "Beginning Animation")

                col.prop(self, "write_data_seperately")
                if self.write_data_seperately:
                    string_int_prop(col, self, "data_address", "Data Address")
                    string_int_prop(col, self, "data_end_address", "Data End")
            col.prop(self, "null_delimiter")
        if export_type == "Insertable Binary":
            draw_custom_or_auto(self, col, "file_name", self.get_table_file_name(actor_name, export_type))


classes = (
    SM64_AnimHeaderProperties,
    SM64_AnimTableElementProperties,
    SM64_ActionAnimProperty,
    SM64_AnimImportProperties,
    SM64_AnimProperties,
    SM64_ArmatureAnimProperties,
)


def anim_props_register():
    for cls in classes:
        register_class(cls)


def anim_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
