from bpy.types import PropertyGroup, Operator, Object
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from bpy.utils import register_class, unregister_class
from ....utility import PluginError, prop_split
from ...oot_constants import ootEnumCSTextboxType, ootEnumCSListType, ootEnumCSTransitionType
from ...oot_utility import drawCollectionOps, getCollection


#############
# Operators #
#############
class OOTCSTextboxAdd(Operator):
    bl_idname = "object.oot_cstextbox_add"
    bl_label = "Add CS Textbox"
    bl_options = {"REGISTER", "UNDO"}

    collectionType: StringProperty()
    textboxType: EnumProperty(items=ootEnumCSTextboxType)
    listIndex: IntProperty()
    objName: StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.listIndex)
        newTextboxElement = collection.add()
        newTextboxElement.textboxType = self.textboxType
        return {"FINISHED"}


class OOTCSListAdd(Operator):
    bl_idname = "object.oot_cslist_add"
    bl_label = "Add CS List"
    bl_options = {"REGISTER", "UNDO"}

    collectionType: StringProperty()
    listType: EnumProperty(items=ootEnumCSListType)
    objName: StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, None)
        newList = collection.add()
        newList.listType = self.listType
        return {"FINISHED"}


##############
# Properties #
##############

# Perhaps this should have been called something like OOTCSParentPropertyType,
# but now it needs to keep the same name to not break existing scenes which use
# the cutscene system.
class OOTCSProperty:
    propName = None
    attrName = None
    subprops = ["startFrame", "endFrame"]
    expandTab: BoolProperty(default=True)
    startFrame: IntProperty(name="", default=0, min=0)
    endFrame: IntProperty(name="", default=1, min=0)

    def getName(self):
        return self.propName

    def filterProp(self, name, listProp):
        return True

    def filterName(self, name, listProp):
        return name

    def draw(self, layout, listProp, listIndex, cmdIndex, objName, collectionType):
        layout.prop(
            self,
            "expandTab",
            text=self.getName() + " " + str(cmdIndex),
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if not self.expandTab:
            return
        box = layout.box().column()
        drawCollectionOps(box, cmdIndex, collectionType + "." + self.attrName, listIndex, objName)
        for p in self.subprops:
            if self.filterProp(p, listProp):
                prop_split(box, self, p, self.filterName(p, listProp))


class OOTCSTextboxProperty(OOTCSProperty, PropertyGroup):
    propName = "Textbox"
    attrName = "textbox"
    subprops = [
        "messageId",
        "ocarinaSongAction",
        "startFrame",
        "endFrame",
        "type",
        "topOptionBranch",
        "bottomOptionBranch",
        "ocarinaMessageId",
    ]
    textboxType: EnumProperty(items=ootEnumCSTextboxType)
    messageId: StringProperty(name="", default="0x0000")
    ocarinaSongAction: StringProperty(name="", default="0x0000")
    type: StringProperty(name="", default="0x0000")
    topOptionBranch: StringProperty(name="", default="0x0000")
    bottomOptionBranch: StringProperty(name="", default="0x0000")
    ocarinaMessageId: StringProperty(name="", default="0x0000")

    def getName(self):
        return self.textboxType

    def filterProp(self, name, listProp):
        if self.textboxType == "Text":
            return name not in ["ocarinaSongAction", "ocarinaMessageId"]
        elif self.textboxType == "None":
            return name in ["startFrame", "endFrame"]
        elif self.textboxType == "LearnSong":
            return name in ["ocarinaSongAction", "startFrame", "endFrame", "ocarinaMessageId"]
        else:
            raise PluginError("Invalid property name for OOTCSTextboxProperty")


class OOTCSLightingProperty(OOTCSProperty, PropertyGroup):
    propName = "Lighting"
    attrName = "lighting"
    subprops = ["index", "startFrame"]
    index: IntProperty(name="", default=1, min=1)


class OOTCSTimeProperty(OOTCSProperty, PropertyGroup):
    propName = "Time"
    attrName = "time"
    subprops = ["startFrame", "hour", "minute"]
    hour: IntProperty(name="", default=23, min=0, max=23)
    minute: IntProperty(name="", default=59, min=0, max=59)


class OOTCSBGMProperty(OOTCSProperty, PropertyGroup):
    propName = "BGM"
    attrName = "bgm"
    subprops = ["value", "startFrame", "endFrame"]
    value: StringProperty(name="", default="0x0000")

    def filterProp(self, name, listProp):
        return name != "endFrame" or listProp.listType == "FadeBGM"

    def filterName(self, name, listProp):
        if name == "value":
            return "Fade Type" if listProp.listType == "FadeBGM" else "Sequence"
        return name


class OOTCSMiscProperty(OOTCSProperty, PropertyGroup):
    propName = "Misc"
    attrName = "misc"
    subprops = ["operation", "startFrame", "endFrame"]
    operation: IntProperty(name="", default=1, min=1, max=35)


class OOTCS0x09Property(OOTCSProperty, PropertyGroup):
    propName = "0x09"
    attrName = "nine"
    subprops = ["startFrame", "unk2", "unk3", "unk4"]
    unk2: StringProperty(name="", default="0x00")
    unk3: StringProperty(name="", default="0x00")
    unk4: StringProperty(name="", default="0x00")


class OOTCSUnkProperty(OOTCSProperty, PropertyGroup):
    propName = "Unk"
    attrName = "unk"
    subprops = ["unk1", "unk2", "unk3", "unk4", "unk5", "unk6", "unk7", "unk8", "unk9", "unk10", "unk11", "unk12"]
    unk1: StringProperty(name="", default="0x00000000")
    unk2: StringProperty(name="", default="0x00000000")
    unk3: StringProperty(name="", default="0x00000000")
    unk4: StringProperty(name="", default="0x00000000")
    unk5: StringProperty(name="", default="0x00000000")
    unk6: StringProperty(name="", default="0x00000000")
    unk7: StringProperty(name="", default="0x00000000")
    unk8: StringProperty(name="", default="0x00000000")
    unk9: StringProperty(name="", default="0x00000000")
    unk10: StringProperty(name="", default="0x00000000")
    unk11: StringProperty(name="", default="0x00000000")
    unk12: StringProperty(name="", default="0x00000000")


class OOTCSListProperty(PropertyGroup):
    expandTab: BoolProperty(default=True)

    listType: EnumProperty(items=ootEnumCSListType)
    textbox: CollectionProperty(type=OOTCSTextboxProperty)
    lighting: CollectionProperty(type=OOTCSLightingProperty)
    time: CollectionProperty(type=OOTCSTimeProperty)
    bgm: CollectionProperty(type=OOTCSBGMProperty)
    misc: CollectionProperty(type=OOTCSMiscProperty)
    nine: CollectionProperty(type=OOTCS0x09Property)
    unk: CollectionProperty(type=OOTCSUnkProperty)

    unkType: StringProperty(name="", default="0x0001")
    fxType: EnumProperty(items=ootEnumCSTransitionType)
    fxStartFrame: IntProperty(name="", default=0, min=0)
    fxEndFrame: IntProperty(name="", default=1, min=0)


class OOTCutsceneProperty(PropertyGroup):
    csEndFrame: IntProperty(name="End Frame", min=0, default=100)
    csWriteTerminator: BoolProperty(name="Write Terminator (Code Execution)")
    csTermIdx: IntProperty(name="Index", min=0)
    csTermStart: IntProperty(name="Start Frm", min=0, default=99)
    csTermEnd: IntProperty(name="End Frm", min=0, default=100)
    csLists: CollectionProperty(type=OOTCSListProperty, name="Cutscene Lists")


classes = (
    OOTCSTextboxAdd,
    OOTCSListAdd,
    OOTCSTextboxProperty,
    OOTCSLightingProperty,
    OOTCSTimeProperty,
    OOTCSBGMProperty,
    OOTCSMiscProperty,
    OOTCS0x09Property,
    OOTCSUnkProperty,
    OOTCSListProperty,
    OOTCutsceneProperty,
)


def cutscene_props_classes_register():
    for cls in classes:
        register_class(cls)

    Object.ootCutsceneProperty = PointerProperty(type=OOTCutsceneProperty)


def cutscene_props_classes_unregister():
    del Object.ootCutsceneProperty

    for cls in reversed(classes):
        unregister_class(cls)
