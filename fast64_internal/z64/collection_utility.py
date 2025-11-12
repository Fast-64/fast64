import bpy

from bpy.types import Operator
from bpy.utils import register_class, unregister_class
from bpy.props import IntProperty, StringProperty
from ..utility import PluginError, ootGetSceneOrRoomHeader


class OOTCollectionAdd(Operator):
    bl_idname = "object.oot_collection_add"
    bl_label = "Add Item"
    bl_options = {"REGISTER", "UNDO"}

    option: IntProperty()
    collectionType: StringProperty(default="Actor")
    subIndex: IntProperty(default=0)
    collection_index: IntProperty(default=0)
    objName: StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex, self.collection_index)

        new_entry = collection.add()
        collection.move(len(collection) - 1, self.option)

        owner = bpy.data.objects[self.objName]
        if self.collectionType == "Actor CS" and owner.ootEmptyType == "Actor Cutscene":
            context.scene.fast64.oot.global_actor_cs_count = len(collection)

        if self.collectionType == "Scene":
            new_entry.internal_header_index = 4

        return {"FINISHED"}


class OOTCollectionRemove(Operator):
    bl_idname = "object.oot_collection_remove"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    option: IntProperty()
    collectionType: StringProperty(default="Actor")
    subIndex: IntProperty(default=0)
    collection_index: IntProperty(default=0)
    objName: StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex, self.collection_index)
        collection.remove(self.option)

        owner = bpy.data.objects[self.objName]
        if self.collectionType == "Actor CS" and owner.ootEmptyType == "Actor Cutscene":
            context.scene.fast64.oot.global_actor_cs_count = len(collection)

        return {"FINISHED"}


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
        return {"FINISHED"}


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
            props = getCollectionFromIndex(obj, "animated_material", subIndex, False)
        else:
            props = obj.fast64.oot.animated_materials.items[subIndex]

        if collectionType == "Animated Mat.":
            collection = props.entries
        elif collectionType == "Animated Mat. Color":
            collection = props.entries[collection_index].color_params.keyframes
        elif collectionType == "Animated Mat. Scroll":
            collection = props.entries[collection_index].tex_scroll_params.entries
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


def drawAddButton(layout, index, collectionType, subIndex, objName, collection_index: int = 0):
    if subIndex is None:
        subIndex = 0
    addOp = layout.operator(OOTCollectionAdd.bl_idname)
    addOp.option = index
    addOp.collectionType = collectionType
    addOp.subIndex = subIndex
    addOp.objName = objName
    addOp.collection_index = collection_index


def drawCollectionOps(
    layout, index, collectionType, subIndex, objName, allowAdd=True, compact=False, collection_index: int = 0
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

    removeOp = buttons.operator(OOTCollectionRemove.bl_idname, text="Delete" if not compact else "", icon="REMOVE")
    removeOp.option = index
    removeOp.collectionType = collectionType
    removeOp.subIndex = subIndex
    removeOp.objName = objName
    removeOp.collection_index = collection_index

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
)


def collections_register():
    for cls in collections_classes:
        register_class(cls)


def collections_unregister():
    for cls in reversed(collections_classes):
        unregister_class(cls)
