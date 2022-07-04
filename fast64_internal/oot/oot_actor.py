import bpy

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from ..utility import *
from .oot_operators import *

# TODO use OOT_ObjectProperties.cur_version instead when imports are cleaned up
OOT_ObjectProperties_cur_version = 1

# General classes


class OOT_SearchChestContentEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_chest_content_enum_operator"
    bl_label = "Select Chest Content"
    bl_property = "itemChest"
    bl_options = {"REGISTER", "UNDO"}

    itemChest: bpy.props.EnumProperty(items=ootChestContent, default="item_heart")
    objName: bpy.props.StringProperty()

    def execute(self, context):
        bpy.data.objects[self.objName].fast64.oot.actor.itemChest = self.itemChest
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.itemChest)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_SearchNaviMsgIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_navi_msg_id_enum_operator"
    bl_label = "Select Message ID"
    bl_property = "naviMsgID"
    bl_options = {"REGISTER", "UNDO"}

    naviMsgID: bpy.props.EnumProperty(items=ootNaviMsgID, default="msg_00")
    objName: bpy.props.StringProperty()

    def execute(self, context):
        bpy.data.objects[self.objName].fast64.oot.actor.naviMsgID = self.naviMsgID
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.naviMsgID)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOTActorProperties(bpy.types.PropertyGroup):
    # Each prop has its 'custom' variant
    # because of the get and set functions

    ### Actors/Entrance Actor ###

    # The actor key is an identifier that will always have the same name
    # The idea is to avoid breaking any blend
    # when we need to update any outdated information
    # because of decomp's changes
    actorKey: bpy.props.EnumProperty(name="Actor Key", items=ootEnumActorID)

    actorParam: bpy.props.StringProperty(
        name="Actor Parameter",
        default="0x0000",
        get=lambda self: getActorValues(self, "Params"),
        set=lambda self, value: setActorValues(self, value, "Params"),
    )
    actorIDCustom: bpy.props.StringProperty(name="Actor ID", default="ACTOR_PLAYER")
    actorParamCustom: bpy.props.StringProperty(name="Actor Parameter", default="0x0000")

    ### Rotations ###
    rotOverride: bpy.props.BoolProperty(name="Rot Override", default=False)
    rotOverrideX: bpy.props.StringProperty(
        name="Rot X",
        default="0x0",
        get=lambda self: getActorValues(self, "XRot"),
        set=lambda self, value: setActorValues(self, value, "XRot"),
    )
    rotOverrideY: bpy.props.StringProperty(
        name="Rot Y",
        default="0x0",
        get=lambda self: getActorValues(self, "YRot"),
        set=lambda self, value: setActorValues(self, value, "YRot"),
    )
    rotOverrideZ: bpy.props.StringProperty(
        name="Rot Z",
        default="0x0",
        get=lambda self: getActorValues(self, "ZRot"),
        set=lambda self, value: setActorValues(self, value, "ZRot"),
    )
    rotOverrideXCustom: bpy.props.StringProperty(name="Rot X", default="0x0")
    rotOverrideYCustom: bpy.props.StringProperty(name="Rot Y", default="0x0")
    rotOverrideZCustom: bpy.props.StringProperty(name="Rot Z", default="0x0")

    ### Transition Actors ###
    transActorKey: bpy.props.EnumProperty(name="Transition Actor ID", items=ootEnumTransitionActorID)
    transActorParam: bpy.props.StringProperty(
        name="Actor Parameter",
        default="0x0000",
        get=lambda self: getTransActorValues(self, "Params"),
        set=lambda self, value: setTransActorValues(self, value, "Params"),
    )
    transActorIDCustom: bpy.props.StringProperty(name="Transition Actor ID", default="ACTOR_EN_DOOR")
    transActorParamCustom: bpy.props.StringProperty(name="Actor Parameter", default="0x0000")

    ### Other ###
    itemChest: bpy.props.StringProperty(name="Chest Content", default="item_heart")
    naviMsgID: bpy.props.StringProperty(name="Navi Message ID", default="msg_00")

    # called if the object props version is outdated
    @staticmethod
    def upgrade_object(obj):
        # if obj is a fast64 oot empty object
        if obj.type == "EMPTY" and obj.ootEmptyType != "None":
            # if obj is an "actor-like" empty
            if obj.ootEmptyType in {"Actor", "Transition Actor", "Entrance"}:
                # upgrade the empty to the newest version
                upgradeActorInit(obj)


# Get functions


def getCustomActorValues(self, target):
    """Returns custom actor values"""
    # Return the custom parameter if the target is parameters
    # else return one of the 3 rotations based on ``target``
    if target == "Params":
        return self.actorParamCustom
    if self.rotOverride:
        if target == "XRot":
            return self.rotOverrideXCustom
        if target == "YRot":
            return self.rotOverrideYCustom
        if target == "ZRot":
            return self.rotOverrideZCustom


def getCustomTransActorValues(self, target):
    """Returns custom actor values"""
    # Return the custom parameter if the target is parameters
    # else return the YRot since it's the only rotation that can be set
    # for transition actors
    if target == "Params":
        return self.transActorParamCustom
    if self.rotOverride and target == "YRot":
        return self.rotOverrideYCustom


def getParameterValue(self, actorKey, target, user):
    """Returns the actor's parameters"""
    value = ""
    actorIndex = getIndexFromKey(actorKey, ootEnumActorID)
    for elem in actorRoot[actorIndex]:
        paramTarget = elem.get("Target", "Params")
        # if the target of the current element matches
        # the target defined in the function parameters
        if paramTarget == target:
            tiedActorTypes = elem.get("TiedActorTypes")
            actorType = getActorType(self, actorKey)
            # check if the element is tied to a specific type
            if (tiedActorTypes is None or actorType is None) or hasActorTiedParams(tiedActorTypes, actorType):
                # get the param value
                value = getActorParameter(self, actorKey, paramTarget, user)
    return value


def getAccurateParameter(self, target, user):
    """Returns the custom parameters if it's a custom actor, otherwise the detailed panel parameters are returned"""
    # if this is a custom actor return either custom transition actor values
    # or custom entrance/regular actor values
    # else, get the parameter from the props' values
    if isActorCustom(self):
        if not (user == "default"):
            return getCustomTransActorValues(self, target)
        else:
            return getCustomActorValues(self, target)
    else:
        if user == "default":
            actorKey = self.actorKey
        else:
            actorKey = self.transActorKey
        return getParameterValue(self, actorKey, target, user)


def getActorValues(self, target):
    """Returns the right value depending on the version"""
    # if the blend has been upgraded return the detailed parameter
    # else return the parameter stored in the blend
    if isLatestVersion():
        return getAccurateParameter(self, target, "default")
    else:
        return getattr(bpy.context.object.ootActorProperty, getLegacyPropName(target))


def getTransActorValues(self, target):
    """Same as ``getActorValues`` but for transition actors"""
    if isLatestVersion():
        return getAccurateParameter(self, target, "transition")
    else:
        return getattr(bpy.context.object.ootTransitionActorProperty.actor, getLegacyPropName(target))


# Set functions


def setCustomActorValues(self, value, target):
    """Sets the custom actor's values"""
    # we can directly set the values for custom actors
    if target == "Params":
        self.actorParamCustom = value
    if self.rotOverride:
        if target == "XRot":
            self.rotOverrideXCustom = value
        if target == "YRot":
            self.rotOverrideYCustom = value
        if target == "ZRot":
            self.rotOverrideZCustom = value


def setCustomTransActorValues(self, value, target):
    """Sets the custom actor's values"""
    if target == "Params":
        self.transActorParamCustom = value
    if self.rotOverride and target == "YRot":
        self.rotOverrideYCustom = value


def setActorParameterValues(self, value, actorKey, target):
    """Sets the actor's parameters"""
    actorIndex = getIndexFromKey(actorKey, ootEnumActorID)
    for elem in actorRoot[actorIndex]:
        index = int(elem.get("Index", "1"), base=10)
        tiedActorTypes = elem.get("TiedActorTypes")
        actorType = getActorType(self, actorKey)
        # check if the element is tied to a specific type
        if (tiedActorTypes is None or actorType is None) or hasActorTiedParams(tiedActorTypes, actorType) is True:
            setActorParameter(elem, evalActorParams(value), self, actorKey, target, index)


def setActorValues(self, value, target):
    """
    Check if the actor is custom and set actor parameters
    for non-transition actors
    """
    if isActorCustom(self):
        setCustomActorValues(self, value, target)
    else:
        setActorParameterValues(self, value, self.actorKey, target)


def setTransActorValues(self, value, target):
    """
    Check if the actor is custom and set actor parameters
    for transition actors
    """
    if isActorCustom(self):
        setCustomTransActorValues(self, value, target)
    else:
        setActorParameterValues(self, value, self.transActorKey, target)


# General functions


def drawParams(layout, actor, elemField, name, tag, type, user):
    """This function handles the drawing of a single prop

    :param layout: UILayout, the layout where we will draw the props
    :param actor: PointerProperty, ``OOTActorProperties`` properties
    :param elemField: String, element inside ``actor`` to display
    :param name: String, name of the prop
    :param tag: String, name of the XML sub-element node
    :param type: String, flag/collectible type
    :param user: String, defines which type of actor this is
    :rtype: None
    """

    # Get the number of switch flags
    if name == "Switch Flag":
        lenSwitch = getActorLastElemIndex(getActorKey(actor, user), "Flag", "Switch")
    else:
        lenSwitch = None

    # Draw the prop
    actorIndex = getIndexFromKey(getActorKey(actor, user), ootEnumActorID)
    for elem in actorRoot[actorIndex]:
        i = int(elem.get("Index", "1"), base=10)

        # Checks if there's at least 2 Switch Flags, in this case the
        # name will be 'Switch Flag #[number]
        # If it's not a Switch Flag, change nothing to the name
        displayName = name
        if lenSwitch is not None and int(lenSwitch) > 1:
            displayName = f"{name} #{i}"

        # Set the name to none to use the element's name instead
        # Set the name to the element's name if it's a flag and its name is set
        curName = elem.get("Name")
        if name is None or (tag == "Flag" and curName is not None):
            displayName = curName

        # Add the index to get the proper attribute
        field = elemField + f"{i}"
        if tag == "Type":
            field = elemField

        attr = getattr(actor, field, None)
        actorType = getActorType(actor, getActorKey(actor, user))
        # Look for tied params, if there are any the props will display depending on ``actorType``
        tiedActorTypes = elem.get("TiedActorTypes")

        # Finally, display the prop
        # First, check if the display name exists, if the current element from the loop is the right one
        # and if the prop to display exists, then check if the element is tied to a specific type
        if displayName is not None and elem.tag == tag and type == elem.get("Type") and attr is not None:
            if (tiedActorTypes is None or actorType is None) or hasActorTiedParams(tiedActorTypes, actorType) is True:
                prop_split(layout, actor, field, displayName)
            i += 1


def editOOTActorProperties():
    """This function is used to edit the OOTActorProperties class before it's registered"""
    propAnnotations = getattr(OOTActorProperties, "__annotations__", None)
    if propAnnotations is None:
        OOTActorProperties.__annotations__ = propAnnotations = {}

    # Collectible Drops List
    itemDrops = [
        (elem.get("Key"), elem.get("Name"), elem.get("Name"))
        for listNode in actorRoot
        for elem in listNode
        if listNode.tag == "List" and listNode.get("Name") == "Collectibles"
    ]

    # for each element and sub-element in the XML
    # which is an actor, generate the corresponding Blender props
    for actorNode in actorRoot:
        actorTypes = []
        actorEnums = []
        actorEnumNames = []
        actorKey = actorNode.get("Key")

        for elem in actorNode:
            index = int(elem.get("Index", "1"), base=10)
            if elem.tag == "Property":
                propAnnotations[(actorKey + f".props{index}")] = bpy.props.StringProperty(name=actorKey, default="0x0")
            elif elem.tag == "Flag":
                flagType = elem.get("Type")
                if flagType == "Chest":
                    propAnnotations[(actorKey + f".chestFlag{index}")] = bpy.props.StringProperty(
                        name="Chest Flag", default="0x0"
                    )
                elif flagType == "Collectible":
                    propAnnotations[(actorKey + f".collectibleFlag{index}")] = bpy.props.StringProperty(
                        name="Collectible Flag", default="0x0"
                    )
                elif flagType == "Switch":
                    propAnnotations[(actorKey + f".switchFlag{index}")] = bpy.props.StringProperty(
                        name="Switch Flag", default="0x0"
                    )
            elif elem.tag == "Collectible":
                propAnnotations[(actorKey + f".collectibleDrop{index}")] = bpy.props.EnumProperty(
                    name="Collectible Drop", items=itemDrops
                )
            elif elem.tag == "Type":
                actorTypes.append([(item.get("Params"), item.text, item.get("Params")) for item in elem])
            elif elem.tag == "Bool":
                propAnnotations[(actorKey + f".bool{index}")] = bpy.props.BoolProperty(default=False)
            elif elem.tag == "Enum":
                actorEnums.append([(item.get("Value"), item.get("Name"), item.get("Value")) for item in elem])
                actorEnumNames.append(elem.get("Name"))
        if actorNode.tag == "Actor":
            for index, elem in enumerate(actorTypes, 1):
                propAnnotations[(actorKey + f".type{index}")] = bpy.props.EnumProperty(name="Actor Type", items=elem)
            for index, elem in enumerate(actorEnums, 1):
                propAnnotations[(actorKey + f".enum{index}")] = bpy.props.EnumProperty(
                    name=actorEnumNames[index - 1], items=elem
                )


def drawDetailedProperties(user, prop, layout, objName, actor):
    """This function handles the drawing of the detailed actor panel.

    :param user: String, indicates the type of actor, if it's a transition actor, an entrance or a regular one
    :param prop: PointerProperty, ``OOTActorPropertiesLegacy`` properties
    :param layout: UILayout, the layout where we will draw the props
    :param objName: String, the empty object's name
    :param actor: PointerProperty, ``OOTActorProperties`` properties
    :rtype: None
    """

    ### Draw basic stuff ###

    userActor = "Actor Property"
    userEntrance = "Entrance Property"
    isCustomEntrance = None
    isActorEntrance = user == userEntrance
    customField = "actorIDCustom"
    paramField = "actorParam"
    if not isActorEntrance:
        if user == userActor:
            actorEnum = ootEnumActorID
            enumOp = OOT_SearchActorIDEnumOperator
        else:
            actorEnum = ootEnumTransitionActorID
            enumOp = OOT_SearchTransActorIDEnumOperator
            customField = "transActorIDCustom"
            paramField = "transActorParam"
        actorKey = getActorKey(actor, user)
        actorID = getIDFromKey(actorKey, actorRoot, ootEnumActorID)
        searchOp = layout.operator(enumOp.bl_idname, icon="VIEWZOOM")
        searchOp.objName = objName
        currentActor = "Actor: " + getEnumName(actorEnum, actorKey)
    else:
        # Entrance prop has specific fields to display
        actorKey = "player"
        layout.prop(prop, "customActor")
        if prop.customActor:
            prop_split(layout, actor, "actorIDCustom", "Actor ID Custom")

        roomObj = getRoomObj(bpy.context.object)
        if roomObj is not None:
            split = layout.split(factor=0.5)
            split.label(text="Room Index")
            split.label(text=str(roomObj.ootRoomHeader.roomIndex))
        else:
            layout.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")

        prop_split(layout, prop, "spawnIndex", "Spawn Index")
        isCustomEntrance = prop.customActor

    ### Draw the props ###

    # if this is a normal actor
    if (not isActorEntrance and actorID is not None and actorID != "Custom") or (
        user == userEntrance and not isCustomEntrance
    ):
        # Adapt the text for the type enum
        if isActorEntrance:
            typeText = "Spawn Type"
        else:
            layout.label(text=currentActor)
            typeText = "Type"

        # Draw the actor type
        actorType = getActorType(actor, actorKey)
        if actorType is not None:
            actorIndex = getIndexFromKey(actorKey, ootEnumActorID)
            for elem in actorRoot[actorIndex]:
                if elem.tag == "Type":
                    index = elem.get("Index", "1")
                    prop_split(layout, actor, actorKey + ".type" + index, typeText)

        # Draw regular actor unique props
        if user == userActor:
            # Draw chest content searchbox
            if actorKey == "en_box":
                searchOp = layout.operator(OOT_SearchChestContentEnumOperator.bl_idname, icon="VIEWZOOM")
                searchOp.objName = objName
                split = layout.split(factor=0.5)
                split.label(text="Chest Content")
                split.label(text=getItemAttrFromKey("Chest Content", actor.itemChest, "Name"))

            # Draw Navi message ID searchbox
            if actorKey == "elf_msg":
                searchOp = layout.operator(OOT_SearchNaviMsgIDEnumOperator.bl_idname, icon="VIEWZOOM")
                searchOp.objName = objName
                split = layout.split(factor=0.5)
                split.label(text="Message ID")
                split.label(text=getItemAttrFromKey("Elf_Msg Message ID", actor.naviMsgID, "Value"))

        # Draw other props
        drawParams(layout, actor, f"{actorKey}.collectibleDrop", "Collectible Drop", "Collectible", "Drop", user)
        drawParams(layout, actor, f"{actorKey}.chestFlag", "Chest Flag", "Flag", "Chest", user)
        drawParams(layout, actor, f"{actorKey}.collectibleFlag", "Collectible Flag", "Flag", "Collectible", user)
        drawParams(layout, actor, f"{actorKey}.switchFlag", "Switch Flag", "Flag", "Switch", user)
        drawParams(layout, actor, f"{actorKey}.enum", None, "Enum", None, user)
        drawParams(layout, actor, f"{actorKey}.props", None, "Property", None, user)
        drawParams(layout, actor, f"{actorKey}.bool", None, "Bool", None, user)

        # Draw actor parameters box
        paramBox = layout.box()
        params = getattr(actor, paramField, "")
        paramBox.label(text=f"Actor Parameter (0x{evalActorParams(params):X})")
        if params != "":
            paramBox.prop(actor, paramField, text="")
        else:
            paramBox.label(text="This Actor doesn't have parameters.")

        # Draw rotations overrides (when you use a rotation variable to store parameters)
        if user == userActor:
            rotXBool = rotYBool = rotZBool = False
            actorIndex = getIndexFromKey(actorKey, ootEnumActorID)
            for elem in actorRoot[actorIndex]:
                target = elem.get("Target")
                actorType = getActorType(actor, actorKey)
                tiedActorTypes = elem.get("TiedActorTypes")
                # check if the element is tied to a specific type
                if (tiedActorTypes is None or actorType is None) or hasActorTiedParams(tiedActorTypes, actorType):
                    if target == "XRot":
                        rotXBool = True
                    elif target == "YRot":
                        rotYBool = True
                    elif target == "ZRot":
                        rotZBool = True

            # Draw the prop if the sub-element has one of the 3 rotations in the target
            if rotXBool:
                prop_split(
                    paramBox,
                    actor,
                    "rotOverrideX",
                    f'Rot X (0x{evalActorParams(getattr(actor, "rotOverrideX", "")):X})',
                )
            if rotYBool:
                prop_split(
                    paramBox,
                    actor,
                    "rotOverrideY",
                    f'Rot Y (0x{evalActorParams(getattr(actor, "rotOverrideY", "")):X})',
                )
            if rotZBool:
                prop_split(
                    paramBox,
                    actor,
                    "rotOverrideZ",
                    f'Rot Z (0x{evalActorParams(getattr(actor, "rotOverrideZ", "")):X})',
                )
    else:
        # If the current actor is custom
        # Draw basic props
        if not isActorEntrance:
            prop_split(layout, actor, customField, currentActor)
            prop_split(layout, actor, paramField, "Actor Parameter")
            layout.prop(actor, "rotOverride", text="Override Rotation (ignore Blender rot)")
            if actor.rotOverride:
                if user == userActor:
                    prop_split(layout, actor, "rotOverrideX", "Rot X")
                prop_split(layout, actor, "rotOverrideY", "Rot Y")
                if user == userActor:
                    prop_split(layout, actor, "rotOverrideZ", "Rot Z")
        else:
            prop_split(layout, actor, paramField, "Actor Parameter")


# Actor Header Item Property
class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
    headerIndex: bpy.props.IntProperty(name="Scene Setup", min=4, default=4)
    expandTab: bpy.props.BoolProperty(name="Expand Tab")


def drawActorHeaderItemProperty(layout, propUser, headerItemProp, index, altProp, objName):
    box = layout.box()
    box.prop(
        headerItemProp,
        "expandTab",
        text="Header " + str(headerItemProp.headerIndex),
        icon="TRIA_DOWN" if headerItemProp.expandTab else "TRIA_RIGHT",
    )

    if headerItemProp.expandTab:
        drawCollectionOps(box, index, propUser, None, objName)
        prop_split(box, headerItemProp, "headerIndex", "Header Index")
        if altProp is not None and headerItemProp.headerIndex >= len(altProp.cutsceneHeaders) + 4:
            box.label(text="Header does not exist.", icon="QUESTION")


# Actor Header Property
class OOTActorHeaderProperty(bpy.types.PropertyGroup):
    sceneSetupPreset: bpy.props.EnumProperty(
        name="Scene Setup Preset", items=ootEnumSceneSetupPreset, default="All Scene Setups"
    )
    childDayHeader: bpy.props.BoolProperty(name="Child Day Header", default=True)
    childNightHeader: bpy.props.BoolProperty(name="Child Night Header", default=True)
    adultDayHeader: bpy.props.BoolProperty(name="Adult Day Header", default=True)
    adultNightHeader: bpy.props.BoolProperty(name="Adult Night Header", default=True)
    cutsceneHeaders: bpy.props.CollectionProperty(type=OOTActorHeaderItemProperty)


def drawActorHeaderProperty(layout, headerProp, propUser, altProp, objName):
    headerSetup = layout.column()
    # headerSetup.box().label(text = "Alternate Headers")
    prop_split(headerSetup, headerProp, "sceneSetupPreset", "Scene Setup Preset")
    if headerProp.sceneSetupPreset == "Custom":
        headerSetupBox = headerSetup.column()
        headerSetupBox.prop(headerProp, "childDayHeader", text="Child Day")
        prevHeaderName = "childDayHeader"
        childNightRow = headerSetupBox.row()
        if altProp is None or altProp.childNightHeader.usePreviousHeader:
            # Draw previous header checkbox (so get previous state), but labeled
            # as current one and grayed out
            childNightRow.prop(headerProp, prevHeaderName, text="Child Night")
            childNightRow.enabled = False
        else:
            childNightRow.prop(headerProp, "childNightHeader", text="Child Night")
            prevHeaderName = "childNightHeader"
        adultDayRow = headerSetupBox.row()
        if altProp is None or altProp.adultDayHeader.usePreviousHeader:
            adultDayRow.prop(headerProp, prevHeaderName, text="Adult Day")
            adultDayRow.enabled = False
        else:
            adultDayRow.prop(headerProp, "adultDayHeader", text="Adult Day")
            prevHeaderName = "adultDayHeader"
        adultNightRow = headerSetupBox.row()
        if altProp is None or altProp.adultNightHeader.usePreviousHeader:
            adultNightRow.prop(headerProp, prevHeaderName, text="Adult Night")
            adultNightRow.enabled = False
        else:
            adultNightRow.prop(headerProp, "adultNightHeader", text="Adult Night")

        headerSetupBox.row().label(text="Cutscene headers to include this actor in:")
        for i in range(len(headerProp.cutsceneHeaders)):
            drawActorHeaderItemProperty(headerSetup, propUser, headerProp.cutsceneHeaders[i], i, altProp, objName)
        drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), propUser, None, objName)


# Actor Property
class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_actor_id_enum_operator"
    bl_label = "Select Actor"
    bl_property = "actorKey"
    bl_options = {"REGISTER", "UNDO"}

    actorKey: bpy.props.EnumProperty(items=ootEnumActorID, default="player")
    objName: bpy.props.StringProperty()

    def execute(self, context):
        bpy.data.objects[self.objName].fast64.oot.actor.actorKey = self.actorKey
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.actorKey)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOTActorPropertiesLegacy(bpy.types.PropertyGroup):
    # Normal Actors
    # We can't delete this (for now) as it'd ignore data in older blend files
    actorID: bpy.props.EnumProperty(name="Actor", items=ootEnumActorIDLegacy, default="ACTOR_PLAYER")
    actorIDCustom: bpy.props.StringProperty(name="Actor ID", default="ACTOR_PLAYER")
    actorParam: bpy.props.StringProperty(name="Actor Parameter", default="0x0000")
    rotOverride: bpy.props.BoolProperty(name="Override Rotation", default=False)
    rotOverrideX: bpy.props.StringProperty(name="Rot X", default="0x0")
    rotOverrideY: bpy.props.StringProperty(name="Rot Y", default="0x0")
    rotOverrideZ: bpy.props.StringProperty(name="Rot Z", default="0x0")
    headerSettings: bpy.props.PointerProperty(type=OOTActorHeaderProperty)


def drawActorProperty(layout, actorProp, altRoomProp, objName, actor):
    actorIDBox = layout.column()

    if actor.version == OOT_ObjectProperties_cur_version:
        drawDetailedProperties("Actor Property", actorProp, actorIDBox, objName, actor.actor)
        drawActorHeaderProperty(actorIDBox, actorProp.headerSettings, "Actor", altRoomProp, objName)


# Transition Actor Property
class OOT_SearchTransActorIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_trans_actor_id_enum_operator"
    bl_label = "Select Transition Actor"
    bl_property = "transActorKey"
    bl_options = {"REGISTER", "UNDO"}

    transActorKey: bpy.props.EnumProperty(items=ootEnumTransitionActorID, default="en_door")
    objName: bpy.props.StringProperty()

    def execute(self, context):
        bpy.data.objects[self.objName].fast64.oot.actor.transActorKey = self.transActorKey
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.transActorKey)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOTTransitionActorProperty(bpy.types.PropertyGroup):
    roomIndex: bpy.props.IntProperty(min=0)
    cameraTransitionFront: bpy.props.EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionFrontCustom: bpy.props.StringProperty(default="0x00")
    cameraTransitionBack: bpy.props.EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionBackCustom: bpy.props.StringProperty(default="0x00")
    actor: bpy.props.PointerProperty(type=OOTActorPropertiesLegacy)


def drawTransitionActorProperty(layout, transActorProp, altSceneProp, roomObj, objName, actor):
    actorIDBox = layout.column()

    if actor.version == OOT_ObjectProperties_cur_version:
        drawDetailedProperties("Transition Property", actor.actor, actorIDBox, objName, actor.actor)
        if roomObj is None:
            actorIDBox.label(text="This must be part of a Room empty's hierarchy.", icon="ERROR")
        else:
            label_split(actorIDBox, "Room To Transition From", str(roomObj.ootRoomHeader.roomIndex))
        prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
        actorIDBox.label(text='Y+ side of door faces toward the "from" room.', icon="ERROR")
        drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
        drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

        drawActorHeaderProperty(
            actorIDBox, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName
        )


# Entrance Property
class OOTEntranceProperty(bpy.types.PropertyGroup):
    # This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
    spawnIndex: bpy.props.IntProperty(min=0)
    customActor: bpy.props.BoolProperty(name="Use Custom Actor")
    actor: bpy.props.PointerProperty(type=OOTActorPropertiesLegacy)


def drawEntranceProperty(layout, obj, altSceneProp, objName, actor):
    box = layout.column()
    entranceProp = obj.ootEntranceProperty

    if actor.version == OOT_ObjectProperties_cur_version:
        drawDetailedProperties("Entrance Property", entranceProp, box, objName, actor.actor)
        drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
