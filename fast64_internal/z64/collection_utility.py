import bpy

from bpy.types import Operator, UILayout
from bpy.utils import register_class, unregister_class
from bpy.props import IntProperty, StringProperty, BoolProperty, EnumProperty
from typing import Optional

from ..game_data import game_data
from ..utility import PluginError, ootGetSceneOrRoomHeader, copyPropertyCollection, copyPropertyGroup


class OOTCollectionAdd(Operator):
    bl_idname = "object.oot_collection_add"
    bl_label = "Add Item"
    bl_options = {"REGISTER", "UNDO"}

    option: IntProperty()
    collectionType: StringProperty(default="Actor")
    subIndex: IntProperty(default=0)
    collection_index: IntProperty(default=0)
    objName: StringProperty()

    ask_for_copy: BoolProperty(default=False)
    do_copy_previous: BoolProperty(default=True)

    ask_for_amount: BoolProperty(default=False)
    amount: IntProperty(min=1, default=1)

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex, self.collection_index)

        for i in range(self.amount):
            new_entry = collection.add()
            collection.move(len(collection) - 1, self.option + i)

            if self.ask_for_copy and self.do_copy_previous:
                copyPropertyGroup(collection[self.option - 1 + i], new_entry)

            if not self.ask_for_amount:
                # should always default to 1 but just in case force a break
                break

        owner = bpy.data.objects[self.objName]
        if self.collectionType == "Actor CS" and owner.ootEmptyType == "Actor Cutscene":
            context.scene.fast64.oot.global_actor_cs_count = len(collection)

        if self.collectionType == "Scene":
            new_entry.internal_header_index = 4

        context.region.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, _):
        if self.ask_for_copy or self.ask_for_amount:
            return context.window_manager.invoke_props_dialog(self, width=300)
        return self.execute(context)

    def draw(self, _):
        layout = self.layout
        if self.ask_for_copy:
            layout.prop(self, "do_copy_previous", text="Copy Previous Entry")

        if self.ask_for_amount:
            layout.prop(self, "amount", text="Number of items to add")


class OOTCollectionRemove(Operator):
    bl_idname = "object.oot_collection_remove"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    option: IntProperty()
    collectionType: StringProperty(default="Actor")
    subIndex: IntProperty(default=0)
    collection_index: IntProperty(default=0)
    objName: StringProperty()

    ask_for_amount: BoolProperty(default=False)
    amount: IntProperty(
        min=0,
        default=0,
        set=lambda self, value: OOTCollectionRemove.on_amount_set(self, value),
        get=lambda self: OOTCollectionRemove.on_amount_get(self),
    )
    internal_amount: IntProperty(min=0, default=0)

    @staticmethod
    def on_amount_set(owner, value):
        owner.internal_amount = value

    @staticmethod
    def on_amount_get(owner):
        collection = getCollection(owner.objName, owner.collectionType, owner.subIndex, owner.collection_index)
        maximum = len(collection) - owner.option

        if owner.internal_amount >= maximum:
            owner.internal_amount = maximum

        return owner.internal_amount

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex, self.collection_index)

        if self.amount > 0:
            for _ in range(self.amount):
                if not self.ask_for_amount or self.option >= len(collection):
                    break

                collection.remove(self.option)
        else:
            collection.remove(self.option)

        owner = bpy.data.objects[self.objName]
        if self.collectionType == "Actor CS" and owner.ootEmptyType == "Actor Cutscene":
            context.scene.fast64.oot.global_actor_cs_count = len(collection)

        context.region.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, _):
        collection = getCollection(self.objName, self.collectionType, self.subIndex, self.collection_index)
        if self.ask_for_amount and self.option + 1 < len(collection):
            return context.window_manager.invoke_props_dialog(self, width=300)
        return self.execute(context)

    def draw(self, _):
        layout = self.layout

        if self.ask_for_amount:
            layout.prop(self, "amount", text="Number of following items to remove")

            if self.amount == 0:
                text = f"Will remove Item No. {self.option + 1}."
            elif self.amount == 1:
                text = f"Will remove Item No. {self.option + 1} and the next one."
            else:
                text = f"Will remove Item No. {self.option + 1} and the next {self.amount - 1}."

            layout.label(text=text)


class OOTCollectionMove(Operator):
    bl_idname = "object.oot_collection_move"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}

    option: IntProperty()
    offset: IntProperty()
    subIndex: IntProperty(default=0)
    collection_index: IntProperty(default=0)
    objName: StringProperty()

    collectionType: StringProperty(default="Actor")

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex, self.collection_index)
        collection.move(self.option, self.option + self.offset)
        context.region.tag_redraw()
        return {"FINISHED"}


class OOTCollectionClear(Operator):
    bl_idname = "object.oot_collection_clear"
    bl_label = "Clear All Items"
    bl_options = {"REGISTER", "UNDO"}

    collection_type: StringProperty(default="Actor")
    sub_index: IntProperty(default=0)
    collection_index: IntProperty(default=0)
    obj_name: StringProperty()

    def execute(self, context):
        collection = getCollection(self.obj_name, self.collection_type, self.sub_index, self.collection_index)
        collection.clear()
        context.region.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, _):
        layout = self.layout
        layout.label(text="Are you sure you want to clear this collection?")


class OOTCollectionCopy(Operator):
    bl_idname = "object.oot_collection_copy"
    bl_label = "Copy Items"
    bl_options = {"REGISTER", "UNDO"}

    collection_type: StringProperty(default="Actor")
    sub_index: IntProperty(default=0)
    collection_index: IntProperty(default=0)
    obj_name: StringProperty()

    from_cs_index: IntProperty(min=game_data.z64.cs_index_start, default=game_data.z64.cs_index_start)
    from_header_index: EnumProperty(items=lambda self, _: OOTCollectionCopy.get_items(self))
    do_clear: BoolProperty(default=True)

    @staticmethod
    def get_items(owner: "OOTCollectionCopy"):
        enum = [
            ("0", "Child Day", "Child Day"),
            ("1", "Child Night", "Child Night"),
            ("2", "Adult Day", "Adult Day"),
            ("3", "Adult Night", "Adult Night"),
            ("4", "Cutscene", "Cutscene"),
        ]
        enum.pop(owner.sub_index if owner.sub_index < 4 else 4)
        return enum

    def execute(self, context):
        from_header_index = int(self.from_header_index) if self.from_header_index != "4" else self.from_cs_index

        def try_get_collection(obj_name, collection_type, sub_index: int, collection_index: int):
            try:
                return getCollection(obj_name, collection_type, sub_index, collection_index)
            except AttributeError:
                return None

        col_from = try_get_collection(self.obj_name, self.collection_type, from_header_index, self.collection_index)
        col_to = try_get_collection(self.obj_name, self.collection_type, self.sub_index, self.collection_index)

        if col_from is None:
            self.report({"ERROR"}, "The selected header cannot be used because it's using the previous header.")
            return {"CANCELLED"}

        if col_to is None:
            self.report({"ERROR"}, "Unexpected error occurred.")
            return {"CANCELLED"}

        copyPropertyCollection(col_from, col_to, do_clear=self.do_clear)
        context.region.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, _):
        layout = self.layout
        layout.prop(self, "from_header_index", text="Copy From")

        if self.from_header_index == "4":
            layout.prop(self, "from_cs_index", text="Cutscene Index")

        layout.prop(self, "do_clear", text="Clear the destination collection before copying")


def getCollectionFromIndex(obj, prop, subIndex, isRoom):
    header = ootGetSceneOrRoomHeader(obj, subIndex, isRoom)
    return getattr(header, prop)


# Operators cannot store mutable references (?), so to reuse PropertyCollection modification code we do this.
# Save a string identifier in the operator, then choose the member variable based on that.
# subIndex is for a collection within a collection element
def getCollection(objName, collectionType, subIndex: int, collection_index: int = 0):
    obj = bpy.data.objects[objName]
    if collectionType == "Actor":
        collection = obj.ootActorProperty.headerSettings.cutsceneHeaders
    elif collectionType == "Transition Actor":
        collection = obj.ootTransitionActorProperty.actor.headerSettings.cutsceneHeaders
    elif collectionType == "Entrance":
        collection = obj.ootEntranceProperty.actor.headerSettings.cutsceneHeaders
    elif collectionType == "Room":
        collection = obj.ootAlternateRoomHeaders.cutsceneHeaders
    elif collectionType == "Scene":
        collection = obj.ootAlternateSceneHeaders.cutsceneHeaders
    elif collectionType == "Light":
        collection = getCollectionFromIndex(obj, "lightList", subIndex, False)
    elif collectionType == "Exit":
        collection = getCollectionFromIndex(obj, "exitList", subIndex, False)
    elif collectionType == "Object":
        collection = getCollectionFromIndex(obj, "objectList", subIndex, True)
    elif collectionType == "Animated Mat. List":
        collection = obj.fast64.oot.animated_materials.items
    elif collectionType.startswith("Animated Mat."):
        if obj.ootEmptyType == "Scene":
            header = ootGetSceneOrRoomHeader(obj, subIndex, False)
            props = header.animated_material
        else:
            props = obj.fast64.oot.animated_materials.items[subIndex]

        if collectionType == "Animated Mat.":
            collection = props.entries
        elif collectionType == "Animated Mat. Color":
            collection = props.entries[collection_index].color_params.keyframes
        elif collectionType == "Animated Mat. Cycle (Index)":
            collection = props.entries[collection_index].tex_cycle_params.keyframes
        elif collectionType == "Animated Mat. Cycle (Texture)":
            collection = props.entries[collection_index].tex_cycle_params.textures
    elif collectionType == "Curve":
        collection = obj.ootSplineProperty.headerSettings.cutsceneHeaders
    elif collectionType.startswith("CSHdr."):
        # CSHdr.HeaderNumber[.ListType]
        # Specifying ListType means uses subIndex
        toks = collectionType.split(".")
        assert len(toks) in [2, 3]
        hdrnum = int(toks[1])
        collection = getCollectionFromIndex(obj, "csLists", hdrnum, False)
        if len(toks) == 3:
            collection = getattr(collection[subIndex], toks[2])
    elif collectionType.startswith("Cutscene."):
        # Cutscene.ListType
        toks = collectionType.split(".")
        assert len(toks) == 2
        collection = obj.ootCutsceneProperty.csLists
        collection = getattr(collection[subIndex], toks[1])
    elif collectionType == "Cutscene":
        collection = obj.ootCutsceneProperty.csLists
    elif collectionType == "extraCutscenes":
        collection = obj.ootSceneHeader.extraCutscenes
    elif collectionType == "BgImage":
        collection = obj.ootRoomHeader.bgImageList
    else:
        raise PluginError("Invalid collection type: " + collectionType)

    return collection


def drawAddButton(
    layout,
    index,
    collectionType,
    subIndex,
    objName,
    collection_index: int = 0,
    ask_for_copy: bool = False,
    ask_for_amount: bool = False,
):
    if subIndex is None:
        subIndex = 0
    addOp = layout.operator(OOTCollectionAdd.bl_idname)
    addOp.option = index
    addOp.collectionType = collectionType
    addOp.subIndex = subIndex
    addOp.objName = objName
    addOp.collection_index = collection_index
    addOp.ask_for_copy = ask_for_copy
    addOp.ask_for_amount = ask_for_amount


def draw_clear_button(
    layout: UILayout, collection_type: str, sub_index: Optional[int], obj_name: str, collection_index: int = 0
):
    if sub_index is None:
        sub_index = 0
    copy_op: OOTCollectionClear = layout.operator(OOTCollectionClear.bl_idname)
    copy_op.collection_type = collection_type
    copy_op.sub_index = sub_index
    copy_op.obj_name = obj_name
    copy_op.collection_index = collection_index


def draw_copy_button(
    layout: UILayout, collection_type: str, sub_index: Optional[int], obj_name: str, collection_index: int = 0
):
    if sub_index is None:
        sub_index = 0
    copy_op: OOTCollectionCopy = layout.operator(OOTCollectionCopy.bl_idname)
    copy_op.collection_type = collection_type
    copy_op.sub_index = sub_index
    copy_op.obj_name = obj_name
    copy_op.collection_index = collection_index


def draw_utility_ops(
    layout: bpy.types.UILayout,
    index: int,
    collection_type: str,
    header_index: Optional[int],
    obj_name: str,
    collection_index: int = 0,
    ask_for_copy: bool = False,
    ask_for_amount: bool = False,
):
    drawAddButton(
        layout, index, collection_type, header_index, obj_name, collection_index, ask_for_copy, ask_for_amount
    )
    draw_clear_button(layout, collection_type, header_index, obj_name, collection_index)
    draw_copy_button(layout, collection_type, header_index, obj_name, collection_index)


def drawCollectionOps(
    layout,
    index,
    collectionType,
    subIndex,
    objName,
    allowAdd=True,
    compact=False,
    collection_index: int = 0,
    ask_for_copy: bool = False,
    ask_for_amount: bool = False,
):
    if subIndex is None:
        subIndex = 0

    if not compact:
        buttons = layout.row(align=True)
    else:
        buttons = layout

    if allowAdd:
        addOp = buttons.operator(OOTCollectionAdd.bl_idname, text="Add" if not compact else "", icon="ADD")
        addOp.option = index + 1
        addOp.collectionType = collectionType
        addOp.subIndex = subIndex
        addOp.objName = objName
        addOp.collection_index = collection_index
        addOp.ask_for_copy = ask_for_copy
        addOp.ask_for_amount = ask_for_amount

    removeOp = buttons.operator(OOTCollectionRemove.bl_idname, text="Delete" if not compact else "", icon="REMOVE")
    removeOp.option = index
    removeOp.collectionType = collectionType
    removeOp.subIndex = subIndex
    removeOp.objName = objName
    removeOp.collection_index = collection_index
    removeOp.ask_for_amount = ask_for_amount

    moveUp = buttons.operator(OOTCollectionMove.bl_idname, text="Up" if not compact else "", icon="TRIA_UP")
    moveUp.option = index
    moveUp.offset = -1
    moveUp.collectionType = collectionType
    moveUp.subIndex = subIndex
    moveUp.objName = objName
    moveUp.collection_index = collection_index

    moveDown = buttons.operator(OOTCollectionMove.bl_idname, text="Down" if not compact else "", icon="TRIA_DOWN")
    moveDown.option = index
    moveDown.offset = 1
    moveDown.collectionType = collectionType
    moveDown.subIndex = subIndex
    moveDown.objName = objName
    moveDown.collection_index = collection_index


collections_classes = (
    OOTCollectionAdd,
    OOTCollectionRemove,
    OOTCollectionMove,
    OOTCollectionClear,
    OOTCollectionCopy,
)


def collections_register():
    for cls in collections_classes:
        register_class(cls)


def collections_unregister():
    for cls in reversed(collections_classes):
        unregister_class(cls)
