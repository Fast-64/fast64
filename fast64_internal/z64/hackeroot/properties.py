import bpy

from typing import Optional, TYPE_CHECKING

from bpy.types import PropertyGroup, UILayout, Object
from bpy.utils import register_class, unregister_class
from bpy.props import PointerProperty, EnumProperty, StringProperty, BoolProperty, IntProperty, CollectionProperty

from ...game_data import game_data
from ...utility import PluginError, CData, prop_split, indent
from ..collection_utility import drawCollectionOps, draw_utility_ops
from ..utility import is_oot_features, is_hackeroot
from .operators import HackerOoT_ClearBootupScene

if TYPE_CHECKING:
    from ..scene.properties import OOTBootupSceneOptions


def bool_to_c(value: bool):
    return "true" if value else "false"


class HackerOoT_EventConditionProperty(PropertyGroup):
    type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("event_condition"), default=1)
    type_custom: StringProperty()

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "type", "Condition Type")

        if self.type == "Custom":
            prop_split(layout, self, "type_custom", "Custom Condition Type")

    def export(self):
        return game_data.z64.get_enum_value("event_condition", self.type)


class HackerOoT_EventFlagProperty(PropertyGroup):
    type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("event_flag_type"), default=1)
    type_custom: StringProperty()
    value: StringProperty()

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "type", "Flag Type")

        if self.type == "Custom":
            prop_split(layout, self, "type_custom", "Custom Flag Type")

        prop_split(layout, self, "value", "Flag Value")

    def export(self):
        type_to_cmd = {
            "event_flag_type_switch_flag": "EVENT_SWITCH_FLAG",
            "event_flag_type_eventchkinf_flag": "EVENT_EVENTCHKINF_FLAG",
            "event_flag_type_inf_flag": "EVENT_INF_FLAG",
            "event_flag_type_collectible_flag": "EVENT_COLLECTIBLE_FLAG",
            "event_flag_type_treasure_flag": "EVENT_TREASURE_FLAG",
            "event_flag_type_tempclear_flag": "EVENT_TEMPCLEAR_FLAG",
            "event_flag_type_clear_flag": "EVENT_CLEAR_FLAG",
        }

        if self.type == "Custom":
            return f"EVENT_FLAG({self.type_custom}, {self.value})"

        return f"{type_to_cmd[self.type]}({self.value})"


class HackerOoT_EventInventoryProperty(PropertyGroup):
    type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("event_inv_type"), default=1)

    item_id: EnumProperty(items=lambda self, context: game_data.z64.get_enum("inventory_items"), default=1)
    upgrade_type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("upgrade_type"), default=1)
    quest_item: EnumProperty(items=lambda self, context: game_data.z64.get_enum("quest_items"), default=1)
    equipment_item: EnumProperty(items=lambda self, context: game_data.z64.get_enum("equipment_items"), default=1)
    item_id_custom: StringProperty()
    upgrade_type_custom: StringProperty()
    quest_item_custom: StringProperty()
    equipment_item_custom: StringProperty()
    scene_id: StringProperty()

    is_upgrade: BoolProperty()
    obtained: BoolProperty(name="Must be obtained")
    check_ammo: BoolProperty()
    amount: IntProperty(min=0)
    check_sword_health: BoolProperty()
    sword_health: IntProperty(min=0)
    upgrade_value: StringProperty()
    gs_tokens: IntProperty(min=0)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "type", "Inventory Type")

        if self.type == "Custom":
            layout.label(text="Custom type is not supported yet.")
            return

        if self.type == "event_inv_type_items":
            layout.prop(self, "obtained")

            prop_split(layout, self, "item_id", "Item ID")

            if self.item_id == "Custom":
                prop_split(layout, self, f"item_id_custom", "Item ID Custom")

            layout.prop(self, "check_ammo", text="Check Amount")

            if self.check_ammo:
                prop_split(layout, self, "amount", "Amount")
        elif self.type == "event_inv_type_equipment":
            layout.prop(self, "obtained")

            if not self.is_upgrade and not self.check_sword_health:
                prop_split(layout, self, "equipment_item", "Item ID")

                if self.equipment_item == "Custom":
                    prop_split(layout, self, f"equipment_item_custom", "Item ID Custom")

            layout.prop(self, "is_upgrade", text="Upgrade Item")

            if self.is_upgrade:
                prop_split(layout, self, "upgrade_type", "Upgrade Type")

                if self.upgrade_type == "Custom":
                    prop_split(layout, self, f"upgrade_type_custom", "Upgrade Type Custom")

                prop_split(layout, self, "upgrade_value", "Upgrade Value")
            else:
                layout.prop(self, "check_sword_health", text="Check Sword Health")

                if self.check_sword_health:
                    prop_split(layout, self, "sword_health", "Sword Health")
        elif self.type == "event_inv_type_quest":
            layout.prop(self, "obtained")
            prop_split(layout, self, "quest_item", "Quest Item")

            if self.quest_item == "Custom":
                prop_split(layout, self, f"quest_item_custom", "Quest Item Custom")
        elif self.type == "event_inv_type_gs_tokens":
            prop_split(layout, self, "gs_tokens", "Gold Skulltula Tokens")
        else:
            layout.label(text="Not implemented yet.", icon="ERROR")

    def export(self, cond: str):
        type_to_cmd = {
            "event_inv_type_items": "EVENT_ITEM",
            "event_inv_type_equipment": "EVENT_EQUIPMENT",
            "event_inv_type_quest": "EVENT_QUEST_ITEM",
            "event_inv_type_gs_tokens": "EVENT_GS_TOKEN",
        }

        cmd = type_to_cmd[self.type]

        if self.type in {"event_inv_type_items", "event_inv_type_equipment"}:
            prop_name = "item_id" if self.type == "event_inv_type_items" else "equipment_item"
            enum_name = "inventory_items" if self.type == "event_inv_type_items" else "equipment_items"

            if getattr(self, prop_name) == "Custom":
                item_id = getattr(self, f"{prop_name}_custom")
            else:
                item_id = game_data.z64.get_enum_value(enum_name, getattr(self, prop_name))

            if self.type == "event_inv_type_items":
                if self.check_ammo:
                    assert "none" not in cond.lower(), "ERROR: item amount events must have a condition"
                    return f"{cmd}_AMMO({cond}, {item_id}, {self.amount})"
            else:
                if self.check_sword_health:
                    assert "none" not in cond.lower(), "ERROR: sword health events must have a condition"
                    return f"{cmd}_BGS({cond}, {self.sword_health})"

                if self.is_upgrade:
                    assert "none" not in cond.lower(), "ERROR: upgrade events must have a condition"
                    if self.upgrade_type == "Custom":
                        item_id = self.upgrade_type_custom
                    else:
                        item_id = game_data.z64.get_enum_value("upgrade_type", self.upgrade_type)
                    return f"{cmd}_UPG({cond}, {item_id}, {self.upgrade_value})"

            return f"{cmd}({item_id}, {bool_to_c(self.obtained)})"
        elif self.type == "event_inv_type_quest":
            if self.quest_item == "Custom":
                item_id = self.quest_item_custom
            else:
                item_id = game_data.z64.get_enum_value("quest_items", self.quest_item)
            return f"{cmd}({item_id}, {bool_to_c(self.obtained)})"
        elif self.type == "event_inv_type_gs_tokens":
            assert "none" not in cond.lower(), "ERROR: tokens events must have a condition"
            return f"{cmd}({cond}, {self.gs_tokens})"

        raise PluginError(f"ERROR: type {repr(self.type)} not implemented yet.")


class HackerOoT_EventGameProperty(PropertyGroup):
    type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("event_game_type"), default=1)
    condition: PointerProperty(type=HackerOoT_EventConditionProperty)

    is_adult: BoolProperty(default=False)
    health: IntProperty(min=0)
    rupees: IntProperty(min=0)
    magic: IntProperty(min=0)
    inventory: PointerProperty(type=HackerOoT_EventInventoryProperty)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "type", "Game Type")

        if self.type == "Custom":
            layout.label(text="Custom type is not supported yet.")
            return

        is_bgs = self.inventory.type == "event_inv_type_equipment" and self.inventory.check_sword_health
        is_upg = self.inventory.type == "event_inv_type_equipment" and self.inventory.is_upgrade
        is_ammo = self.inventory.type == "event_inv_type_items" and self.inventory.check_ammo
        is_gs = self.inventory.type == "event_inv_type_gs_tokens"
        is_player = self.type in {"event_game_type_health", "event_game_type_rupees", "event_game_type_magic"}
        if is_player or is_bgs or is_upg or is_ammo or is_gs:
            self.condition.draw_props(layout)

        if self.type == "event_game_type_age":
            layout.prop(self, "is_adult", text="Is Adult")
        elif self.type == "event_game_type_health":
            prop_split(layout, self, "health", "Health Amount")
        elif self.type == "event_game_type_rupees":
            prop_split(layout, self, "rupees", "Rupee Amount")
        elif self.type == "event_game_type_magic":
            prop_split(layout, self, "magic", "Magic Amount")
        elif self.type == "event_game_type_inventory":
            self.inventory.draw_props(layout)

    def export(self):
        cond = self.condition.export()

        if self.type == "event_game_type_age":
            age = "LINK_AGE_ADULT" if self.is_adult else "LINK_AGE_CHILD"
            return f"EVENT_AGE({age})"
        elif self.type == "event_game_type_health":
            assert "none" not in cond.lower(), "ERROR: health events must have a condition"
            return f"EVENT_HEALTH({cond}, {self.health})"
        elif self.type == "event_game_type_rupees":
            assert "none" not in cond.lower(), "ERROR: rupee events must have a condition"
            return f"EVENT_RUPEES({cond}, {self.rupees})"
        elif self.type == "event_game_type_magic":
            assert "none" not in cond.lower(), "ERROR: magic events must have a condition"
            return f"EVENT_MAGIC({cond}, {self.magic})"
        elif self.type == "event_game_type_inventory":
            return self.inventory.export(cond)

        raise PluginError(f"ERROR: type {repr(self.type)} not implemented yet.")


class HackerOoT_EventClockProperty(PropertyGroup):
    condition: PointerProperty(type=HackerOoT_EventConditionProperty)
    hour: IntProperty(min=0, max=24)
    minute: IntProperty(min=0, max=59)

    def draw_props(self, layout: UILayout, name: Optional[str]):
        if name is not None:
            layout.label(text=name)

        self.condition.draw_props(layout)
        prop_split(layout, self, "hour", "Hour")
        prop_split(layout, self, "minute", "Minute")

    def export(self):
        return f"{self.condition.export()}, {self.hour}, {self.minute}"


class HackerOoT_EventTimeProperty(PropertyGroup):
    type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("event_time_type"), default=1)
    type_custom: StringProperty()
    clock_1: PointerProperty(type=HackerOoT_EventClockProperty)
    clock_2: PointerProperty(type=HackerOoT_EventClockProperty)

    is_night: BoolProperty(default=False)
    is_clock: BoolProperty()
    is_range: BoolProperty()

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "type", "Time Type")
        is_custom = self.type == "Custom"

        if is_custom:
            prop_split(layout, self, "type_custom", "Custom Time Type")

        if is_custom:
            self.clock_1.draw_props(layout.box().column(), "Clock 1")
            self.clock_2.draw_props(layout.box().column(), "Clock 2")
            layout.prop(self, "is_clock", text="Is Clock")
            layout.prop(self, "is_range", text="Is Range")

            if not self.is_range:
                layout.prop(self, "is_night", text="Is Night")
        else:
            if self.type in {"event_time_type_clock", "event_time_type_conditional"}:
                if self.type == "event_time_type_clock":
                    box_1 = layout
                    name = None
                else:
                    box_1 = layout.box().column()
                    name = "Clock 1"

                self.clock_1.draw_props(box_1, name)

                if self.type == "event_time_type_conditional":
                    self.clock_2.draw_props(layout.box().column(), "Clock 2")

    def export(self):
        type_to_cmd = {
            "event_time_type_clock": "EVENT_TIME_CLOCK",
            "event_time_type_conditional": "EVENT_TIME_CONDITIONAL",
            "event_time_type_day": "EVENT_TIME_DAY",
            "event_time_type_night": "EVENT_TIME_NIGHT",
        }

        if self.type == "Custom":
            range_or_night = self.is_range if self.is_range else self.is_night
            return f"EVENT_TIME({self.type_custom}, {bool_to_c(self.is_clock)}, {range_or_night}, {self.clock_1.export()}, {self.clock_2.export()})"

        cmd = type_to_cmd[self.type]

        if self.type == "event_time_type_clock":
            return f"{cmd}({self.clock_1.export()})"

        if self.type == "event_time_type_conditional":
            return f"{cmd}({self.clock_1.export()}, {self.clock_2.export()})"

        return f"{cmd}()"


class HackerOoT_EventItemProperty(PropertyGroup):
    type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("event_type"), default=2)
    flag: PointerProperty(type=HackerOoT_EventFlagProperty)
    game: PointerProperty(type=HackerOoT_EventGameProperty)
    time: PointerProperty(type=HackerOoT_EventTimeProperty)

    # ui only props
    show_item: BoolProperty(default=False)

    def draw_props(
        self, layout: UILayout, owner: Object, collec_type: str, index: int, header_index: int, parent_index: int
    ):
        layout.prop(
            self,
            "show_item",
            text=f"Trigger Event No. {index + 1}",
            icon="TRIA_DOWN" if self.show_item else "TRIA_RIGHT",
        )

        if self.show_item:
            drawCollectionOps(layout, index, collec_type, header_index, owner.name, collection_index=parent_index)
            prop_split(layout, self, "type", "Event Type")

            if self.type == "Custom":
                layout.label(text="Custom type is not supported yet.")
                return

            if self.type == "event_type_flag":
                self.flag.draw_props(layout)
            elif self.type == "event_type_game":
                self.game.draw_props(layout)
            elif self.type == "event_type_time":
                self.time.draw_props(layout)

    def export(self):
        if self.type == "event_type_flag":
            return self.flag.export()
        elif self.type == "event_type_game":
            return self.game.export()
        elif self.type == "event_type_time":
            return self.time.export()

        raise PluginError(f"ERROR: type {repr(self.type)} not implemented yet.")


class HackerOoT_EventProperty(PropertyGroup):
    entries: CollectionProperty(type=HackerOoT_EventItemProperty)
    action_type: EnumProperty(items=lambda self, context: game_data.z64.get_enum("event_action_type"), default=1)
    action_type_custom: StringProperty()

    # ui only props
    show_entries: BoolProperty(default=False)

    def draw_props(
        self, layout: UILayout, owner: Object, collec_type: str, header_index: int, collection_index: int = 0
    ):
        layout.prop(
            self, "show_entries", text=f"Trigger Events", icon="TRIA_DOWN" if self.show_entries else "TRIA_RIGHT"
        )

        if self.show_entries:
            if is_oot_features() and not is_hackeroot():
                layout.label(text="This requires HackerOoT features.", icon="ERROR")
                return

            prop_split(layout, self, "action_type", "Action Type")

            if self.action_type == "Custom":
                prop_split(layout, self, "action_type_custom", "Action Type Custom")

            for i, entry in enumerate(self.entries):
                entry.draw_props(layout.box().column(), owner, collec_type, i, header_index, collection_index)

            draw_utility_ops(
                layout.row(),
                len(self.entries),
                collec_type,
                header_index,
                owner.name,
                collection_index,
                ask_for_amount=True,
                do_copy=False,
            )

        if is_hackeroot() and len(self.entries) == 0:
            layout.label(text="This animated material will always draw.", icon="QUESTION")

    def get_symbols(self, base_name: str, index: int):
        data_name = f"{base_name}_EventData_{index:02}"
        script_name = f"{base_name}_EventScriptEntry_{index:02}"
        return data_name, script_name

    def export(self, base_name: str, index: int):
        if len(self.entries) == 0 or not is_hackeroot():
            return None

        data = CData()

        cmd_data = "".join(indent + f"{entry.export()},\n" for entry in self.entries) + indent + "EVENT_END(),\n"
        data_name, script_name = self.get_symbols(base_name, index)

        # .h
        data.header = f"extern EventData {data_name}[];\n" + f"extern EventScriptEntry {script_name};\n"

        if self.action_type == "Custom":
            action_type = self.action_type_custom
        else:
            action_type = game_data.z64.get_enum_value("event_action_type", self.action_type)

        # .c
        data.source = (
            f"EventData {data_name}[]"
            + " = {\n"
            + cmd_data
            + "};\n\n"
            + f"EventScriptEntry {script_name}"
            + " = {\n"
            + indent
            + f"{data_name}, {action_type},\n"
            + "};\n\n"
        )

        return data


class HackerOoTSettings(PropertyGroup):
    export_ifdefs: bpy.props.BoolProperty(default=True)

    def draw_props(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        export_box = layout.box()
        export_box.label(text="Export Settings")
        export_box.prop(self, "export_ifdefs", text="Export ifdefs")

        boot_box = export_box.box().column()

        bootOptions: "OOTBootupSceneOptions" = context.scene.fast64.oot.bootupSceneOptions
        bootOptions.draw_props(boot_box)

        boot_box.label(text="Note: Scene boot config changes aren't detected by the make process.", icon="ERROR")
        boot_box.operator(HackerOoT_ClearBootupScene.bl_idname, text="Undo Boot To Scene (HackerOOT Repo)")


classes = (
    HackerOoT_EventConditionProperty,
    HackerOoT_EventFlagProperty,
    HackerOoT_EventInventoryProperty,
    HackerOoT_EventGameProperty,
    HackerOoT_EventClockProperty,
    HackerOoT_EventTimeProperty,
    HackerOoT_EventItemProperty,
    HackerOoT_EventProperty,
    HackerOoTSettings,
)


def hackeroot_props_register():
    for cls in classes:
        register_class(cls)


def hackeroot_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
