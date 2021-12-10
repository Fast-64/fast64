import os, bpy, xml.etree.ElementTree as ET

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from ..utility import *

# Read the XML file, throws an error if the file is missing
try: tree = ET.parse(os.path.dirname(os.path.abspath(__file__)) + '/ActorList.xml')
except: PluginError("ERROR: File 'fast64_internal/oot/ActorList.xml' is missing.")
root = tree.getroot()

# General classes and functions
class OOT_SearchChestContentEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_chest_content_enum_operator"
    bl_label = "Select Chest Content"
    bl_property = "itemChest"
    bl_options = {'REGISTER', 'UNDO'}

    itemChest : bpy.props.EnumProperty(items = ootEnBoxContent, default = '0x48')
    objName : bpy.props.StringProperty()

    def execute(self, context):
        bpy.data.objects[self.objName].ootActorDetailedProperties.itemChest = self.itemChest
        bpy.context.region.tag_redraw()
        self.report({'INFO'}, "Selected: " + self.itemChest)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

class OOTActorDetailedProperties(bpy.types.PropertyGroup):
    pass

class OOTActorParams(bpy.types.PropertyGroup):
    param: str='0x0'
    transParam: str='0x0'
    XRot: str='0x0'
    YRot: str='0x0'
    ZRot: str='0x0'
    rotBool: bool=False

def getValues(self, actorID, field, customField):
    if actorID == 'Custom':
        setattr(OOTActorParams, field, customField)

    value = getattr(OOTActorParams, field)
    setattr(self, field + 'ToSave', value)

    return value

def genEnum(annotations, key, suffix, enumList, enumName):
    '''This function is used to generate the proper enum blender property'''
    objName = key + suffix
    prop = bpy.props.EnumProperty(name=enumName, items=enumList)
    annotations[objName] = prop

def genString(annotations, key, suffix, stringName):
    '''This function is used to generate the proper string blender property'''
    objName = key + suffix
    prop = bpy.props.StringProperty(name=stringName, default='0x0')
    annotations[objName] = prop

def getActorParameter(object, field, shift):
    attr = getattr(object, field, '0x0')
    if isinstance(attr, str):
        return int(attr, base=16) << shift
    elif isinstance(attr, bool) and attr:
        return 1 << shift
    else:
        return 0

def computeParams(elem, detailedProp, field, lenProp, lenSwitch, lenBool):
    params = shift = 0
    strMask = elem.get('Mask')
    if elem.tag != 'Parameter' and strMask is not None:
        mask = int(strMask, base=16)
        shift = len(f'{mask:016b}') - len(f'{mask:016b}'.rstrip('0'))
    if elem.tag == 'Flag':
        elemType = elem.get('Type')
        if elemType == 'Chest':
            params += getActorParameter(detailedProp, field + '.chestFlag', shift)
        if elemType == 'Collectible':
            params += getActorParameter(detailedProp, field + '.collectibleFlag', shift)
        if elemType == 'Switch':
            for i in range(1, (int(lenSwitch, base=10) + 1)):
                if i == int(elem.get('Index'), base=10):
                    params += getActorParameter(detailedProp, field + f'.switchFlag{i}', shift)
    if elem.tag == 'Property' and elem.get('Name') != 'None':
        for i in range(1, (int(lenProp, base=10) + 1)):
            if i == int(elem.get('Index'), base=10):
                params += getActorParameter(detailedProp, (field + f'.props{i}'), shift)
    if elem.tag == 'Item':
        params += int(detailedProp.itemChest, base=16) << shift
    if elem.tag == 'Collectible':
        params += getActorParameter(detailedProp, field + '.collectibleDrop', shift)
    if elem.tag == 'Bool':
        for i in range(1, (int(lenBool, base=10) + 1)):
            if i == int(elem.get('Index'), base=10):
                params += getActorParameter(detailedProp, (field + f'.bool{i}'), shift)
    return params

def drawCustomProps(actorIDBox, actorProp, paramField, rotBoolField, rotXField, rotYField, rotZField):
    if paramField is not None:
        prop_split(actorIDBox, actorProp, paramField, 'Actor Parameter')

    if rotBoolField is not None:
        actorIDBox.prop(actorProp, rotBoolField, text = 'Override Rotation (ignore Blender rot)')
        if actorProp.rotOverride:
            prop_split(actorIDBox, actorProp, rotXField, 'Rot X')
            prop_split(actorIDBox, actorProp, rotYField, 'Rot Y')
            prop_split(actorIDBox, actorProp, rotZField, 'Rot Z')

def getMaxIndex(actorKey, elemTag, flagType):
    # Looking for the highest Property/Switch index for the current actor
    length = '0'
    for actorNode in root:
        if actorNode.get('Key') == actorKey:
            for elem in actorNode:
                if elem.tag == elemTag:
                    if flagType is None or (flagType == 'Switch' and elem.get('Type') == flagType):
                        length = elem.get('Index')
    return length

def overrideBLRot(rotParam, rot, rotField):
    if rotParam is not None:
        if rotParam != 0:
            setattr(OOTActorParams, rot, f'0x{rotParam:X}')
            return rotField
        else:
            setattr(OOTActorParams, rot, '0x0')
            return f'{rotField}Custom'
    else:
        return rotField

def drawParams(box, detailedProp, key, elemField, elemName, elTag, elType, lenSwitch):
    for actorNode in root:
        i = 1
        name = 'None'
        if key == actorNode.get('Key'):
            for elem in actorNode:
                # Checks if there's at least 2 Switch Flags, in this case the
                # Name will be 'Switch Flag #[number]
                # If it's not a Switch Flag, change nothing to the name
                if lenSwitch is not None:
                    if int(lenSwitch) > 1: name = f'{elemName} #{i}'
                    else: name = elemName
                else: name = elemName

                # Set the name to none to use the element's name instead
                if elemName is None: name = elem.get('Name')

                # Add the index to get the proper attribute
                if elTag == 'Property' or (elTag == 'Flag' and elType == 'Switch') or elTag == 'Bool':
                    field = elemField + f'{i}'
                else:
                    field = elemField

                attr = getattr(detailedProp, field, None)
                if name != 'None' and elem.tag == elTag and elType == elem.get('Type') and attr is not None:
                    prop_split(box, detailedProp, field, name)

                    # Maximum warning
                    mask = int(elem.get('Mask'), base=16)
                    shift = len(f'{mask:016b}') - len(f'{mask:016b}'.rstrip('0'))
                    maximum = int(elem.get('Mask'), base=16) >> shift
                    params = getActorParameter(detailedProp, field, shift) >> shift
                    if params > maximum:
                        box.box().label(text= \
                            f"Warning: Maximum is 0x{int(elem.get('Mask'), base=16) >> shift:X}!")
                    i += 1

def editDetailedProperties():
    '''This function is used to edit the OOTActorDetailedProperties class before it's registered'''
    propAnnotations = getattr(OOTActorDetailedProperties, '__annotations__', None)
    if propAnnotations is None:
        propAnnotations = {}
        OOTActorDetailedProperties.__annotations__ = propAnnotations

    propAnnotations['actorID'] = bpy.props.EnumProperty(name='Actor ID', items=ootEnumActorID)
    propAnnotations['transActorID'] = bpy.props.EnumProperty(name='Transition Actor ID', items=ootEnumTransitionActorID)
    propAnnotations['actorKey'] = bpy.props.StringProperty(name='Actor Key', default='0000')
    propAnnotations['transActorKey'] = bpy.props.StringProperty(name='Transition Actor ID', default='0009')
    propAnnotations['itemChest'] = bpy.props.EnumProperty(name='Chest Content', items=ootEnBoxContent)

    # Generate the fields
    for actorNode in root:
        i = j = k = 1
        actorKey = actorNode.get('Key')
        for elem in actorNode:
            if elem.tag == 'Property' and elem.get('Name') != 'None':
                genString(propAnnotations, actorKey, f'.props{i}', actorKey)
                i += 1
            elif elem.tag == 'Flag':
                if elem.get('Type') == 'Chest':
                    genString(propAnnotations, actorKey, '.chestFlag', 'Chest Flag')
                elif elem.get('Type') == 'Collectible':
                    genString(propAnnotations, actorKey, '.collectibleFlag', 'Collectible Flag')
                elif elem.get('Type') == 'Switch':
                    genString(propAnnotations, actorKey, f'.switchFlag{j}', 'Switch Flag')
                    j += 1
            elif elem.tag == 'Collectible':
                if actorKey == '0112':
                    # ACTOR_EN_WONDER_ITEM uses a different drop table according to decomp
                    genEnum(propAnnotations, actorKey, '.collectibleDrop', ootEnWonderItemDrop, 'Collectible Drop')
                else:
                    genEnum(propAnnotations, actorKey, '.collectibleDrop', ootEnItem00Drop, 'Collectible Drop')
            elif elem.tag == 'Parameter':
                actorTypeList = [(elem2.get('Params'), elem2.text, elem2.get('Params')) \
                                for actorNode2 in root for elem2 in actorNode2 \
                                if actorNode2.get('Key') == actorKey and elem2.tag == 'Parameter']
                genEnum(propAnnotations, actorKey, '.type', actorTypeList, 'Actor Type')
            elif elem.tag == 'Bool':
                objName = actorKey + f'.bool{k}'
                prop = bpy.props.BoolProperty(default=False)
                propAnnotations[objName] = prop
                k += 1

def drawDetailedProperties(user, userProp, userLayout, userObj, userSearchOp, userIDField, userParamField, detailedProp, dpKey):
    userActor = 'Actor Property'
    userTransition = 'Transition Property'
    userEntrance = 'Entrance Property'
    entranceBool = None
    if user != userEntrance: userActorID = getattr(userProp, userIDField)

    if user != userEntrance:
        searchOp = userLayout.operator(userSearchOp.bl_idname, icon = 'VIEWZOOM')
        searchOp.objName = userObj
        if user == userActor:
            actorEnum = ootEnumActorID
        else:
            actorEnum = ootEnumTransitionActorID
        currentActor = "Actor: " + getEnumName(actorEnum, userActorID)
    else:
        userLayout.prop(userProp, "customActor")
        if userProp.customActor:
            prop_split(userLayout, userProp.actor, "actorIDCustom", "Actor ID Custom")

        roomObj = getRoomObj(userObj)
        if roomObj is not None:
            split = userLayout.split(factor = 0.5)
            split.label(text = "Room Index")
            split.label(text = str(roomObj.ootRoomHeader.roomIndex))
        else:
            userLayout.label(text = "This must be part of a Room empty's hierarchy.", icon = 'OUTLINER')

        prop_split(userLayout, userProp, "spawnIndex", "Spawn Index")
        entranceBool = userProp.customActor

    if (user != userEntrance and userActorID != 'ACTOR_CUSTOM') or (user == userEntrance and entranceBool is False):
        if user != userEntrance:
            userLayout.label(text = currentActor)
            typeText = 'Type'
        else:
            typeText = 'Spawn Type'

        propAnnot = getattr(detailedProp, dpKey + '.type', None)
        if propAnnot is not None:
            prop_split(userLayout, detailedProp, dpKey + '.type', typeText)

        if user == userActor:
            if userActorID == detailedProp.actorID and dpKey == '000A':
                searchOp = userLayout.operator(OOT_SearchChestContentEnumOperator.bl_idname, icon='VIEWZOOM')
                searchOp.objName = userObj
                split = userLayout.split(factor=0.5)
                split.label(text="Chest Content")
                split.label(text=getEnumName(ootEnBoxContent, detailedProp.itemChest))
                        
            propAnnot = getattr(detailedProp, dpKey + ('.collectibleDrop'), None)
            if propAnnot is not None:
                prop_split(userLayout, detailedProp, dpKey + '.collectibleDrop', 'Collectible Drop')

        lenProp = getMaxIndex(dpKey, 'Property', None)
        lenSwitch = getMaxIndex(dpKey, 'Flag', 'Switch')
        lenBool = getMaxIndex(dpKey, 'Bool', None)

        if user == userActor:
            drawParams(userLayout, detailedProp, dpKey, dpKey + '.chestFlag', 'Chest Flag', 'Flag', 'Chest', None)
            drawParams(userLayout, detailedProp, dpKey, dpKey + '.collectibleFlag', 'Collectible Flag', 'Flag', 'Collectible', None)

        drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.switchFlag', 'Switch Flag', 'Flag', 'Switch', lenSwitch)
        drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.props', None, 'Property', None, None)
        drawParams(userLayout, detailedProp, dpKey, f'{dpKey}.bool', None, 'Bool', None, None)

        # This next if handles the necessary maths to get the actor parameters from the detailed panel
        # Reads ActorList.xml and figures out the necessary bit shift and applies it to whatever is in the blender string field
        # Actor key refers to the hex ID of an actor
        # It was made like that to make it future proof as the OoT decomp isn't fully done yet so names can still change
        # For Switch Flags & <Property> we need to make sure the value corresponds to the mask, hence the index in the XML
        # For Chest Content (<Item>) we don't need the actor key because it's handled differently: it's a search box
        actorParams = XRotParams = YRotParams = ZRotParams = 0
        # if the user wants to use a custom actor this computation is pointless
        for actorNode in root:
            if actorNode.get('Key') == dpKey:
                for elem in actorNode:
                    paramTarget = elem.get('Target')
                    if paramTarget == 'Params' or paramTarget is None:
                        actorParams += computeParams(elem, detailedProp, dpKey, lenProp, lenSwitch, lenBool)

                    if user == userActor:
                        if paramTarget == 'XRot':
                            XRotParams += computeParams(elem, detailedProp, dpKey, lenProp, lenSwitch, lenBool)
                        elif paramTarget == 'YRot':
                            YRotParams += computeParams(elem, detailedProp, dpKey, lenProp, lenSwitch, lenBool)
                        elif paramTarget == 'ZRot':
                            ZRotParams += computeParams(elem, detailedProp, dpKey, lenProp, lenSwitch, lenBool)

        # Finally, add the actor type value, which is already shifted in the XML
        actorParams += getActorParameter(detailedProp, dpKey + '.type', 0)
        if user != userTransition:
            OOTActorParams.param = f'0x{actorParams:X}'
        else: OOTActorParams.transParam = f'0x{actorParams:X}'

        if user == userEntrance: userProp = userProp.actor
        prop_split(userLayout, userProp, userParamField, 'Actor Parameter')

        if user == userActor:
            if XRotParams != 0: rotXField = overrideBLRot(XRotParams, 'XRot', 'rotOverrideX')
            else: rotXField = 'rotOverrideXCustom'

            if YRotParams != 0: rotYField = overrideBLRot(YRotParams, 'YRot', 'rotOverrideY')
            else: rotYField = 'rotOverrideYCustom'

            if ZRotParams != 0: rotZField = overrideBLRot(ZRotParams, 'ZRot','rotOverrideZ')
            else: rotZField = 'rotOverrideZCustom'

            if XRotParams != 0 or YRotParams != 0 or ZRotParams != 0:
                OOTActorParams.rotBool = True
            else:
                OOTActorParams.rotBool = False
                OOTActorParams.XRot = OOTActorParams.YRot = OOTActorParams.ZRot = '0x0'
                rotXField = overrideBLRot(None, 'XRot', 'rotOverrideX')
                rotYField = overrideBLRot(None, 'YRot', 'rotOverrideY')
                rotZField = overrideBLRot(None, 'ZRot', 'rotOverrideZ')
            drawCustomProps(userLayout, userProp, None, 'rotOverride', rotXField, rotYField, rotZField)
    else:
        if user != userEntrance:
            prop_split(userLayout, userProp, userIDField + 'Custom', currentActor)
            if user == userActor:
                drawCustomProps(userLayout, userProp, 'actorParamCustom', 'rotOverrideCustom', \
                    'rotOverrideXCustom', 'rotOverrideYCustom', 'rotOverrideZCustom')
            else:
                drawCustomProps(userLayout, userProp, userParamField + 'Custom', None, None, None, None)
        else:
            drawCustomProps(userLayout, userProp.actor, userParamField + 'Custom', None, None, None, None)

# Actor Header Item Property
class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
    headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
    expandTab : bpy.props.BoolProperty(name = "Expand Tab")

def drawActorHeaderItemProperty(layout, propUser, headerItemProp, index, altProp, objName):
    box = layout.box()
    box.prop(headerItemProp, 'expandTab', text = 'Header ' + \
        str(headerItemProp.headerIndex), icon = 'TRIA_DOWN' if headerItemProp.expandTab else \
        'TRIA_RIGHT')
    
    if headerItemProp.expandTab:
        drawCollectionOps(box, index, propUser, None, objName)
        prop_split(box, headerItemProp, 'headerIndex', 'Header Index')
        if altProp is not None and headerItemProp.headerIndex >= len(altProp.cutsceneHeaders) + 4:
            box.label(text = "Header does not exist.", icon = 'QUESTION')

# Actor Header Property
class OOTActorHeaderProperty(bpy.types.PropertyGroup):
    sceneSetupPreset : bpy.props.EnumProperty(name = "Scene Setup Preset", items = ootEnumSceneSetupPreset, default = "All Scene Setups")
    childDayHeader : bpy.props.BoolProperty(name = "Child Day Header", default = True)
    childNightHeader : bpy.props.BoolProperty(name = "Child Night Header", default = True)
    adultDayHeader : bpy.props.BoolProperty(name = "Adult Day Header", default = True)
    adultNightHeader : bpy.props.BoolProperty(name = "Adult Night Header", default = True)
    cutsceneHeaders : bpy.props.CollectionProperty(type = OOTActorHeaderItemProperty)

def drawActorHeaderProperty(layout, headerProp, propUser, altProp, objName):
    headerSetup = layout.column()
    #headerSetup.box().label(text = "Alternate Headers")
    prop_split(headerSetup, headerProp, "sceneSetupPreset", "Scene Setup Preset")
    if headerProp.sceneSetupPreset == "Custom":
        headerSetupBox = headerSetup.column()
        headerSetupBox.prop(headerProp, 'childDayHeader', text = "Child Day")
        childNightRow = headerSetupBox.row()
        childNightRow.prop(headerProp, 'childNightHeader', text = "Child Night")
        adultDayRow = headerSetupBox.row()
        adultDayRow.prop(headerProp, 'adultDayHeader', text = "Adult Day")
        adultNightRow = headerSetupBox.row()
        adultNightRow.prop(headerProp, 'adultNightHeader', text = "Adult Night")

        childNightRow.enabled = not altProp.childNightHeader.usePreviousHeader if altProp is not None else True
        adultDayRow.enabled = not altProp.adultDayHeader.usePreviousHeader if altProp is not None else True
        adultNightRow.enabled = not altProp.adultNightHeader.usePreviousHeader if altProp is not None else True

        for i in range(len(headerProp.cutsceneHeaders)):
            drawActorHeaderItemProperty(headerSetup, propUser, headerProp.cutsceneHeaders[i], i, altProp, objName)
        drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), propUser, None, objName)

# Actor Property
class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_actor_id_enum_operator"
    bl_label = "Select Actor"
    bl_property = "actorID"
    bl_options = {'REGISTER', 'UNDO'}

    actorID : bpy.props.EnumProperty(items = ootEnumActorID, default = "ACTOR_PLAYER")
    objName : bpy.props.StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.objName]
        detailedProp = obj.ootActorDetailedProperties

        obj.ootActorProperty.actorID = self.actorID
        detailedProp.actorID = self.actorID
        for actorNode in root:
            if actorNode.get('ID') == self.actorID:
                detailedProp.actorKey = actorNode.get('Key')

        bpy.context.region.tag_redraw()
        self.report({'INFO'}, "Selected: " + self.actorID)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

class OOTActorProperty(bpy.types.PropertyGroup):
    # Normal Actors
    actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')

    actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000', \
        get=lambda self: getValues(self, self.actorID, 'param', self.actorParamCustom))

    rotOverride : bpy.props.BoolProperty(name = 'Override Rotation', default = False, \
        get=lambda self: getValues(self, self.actorID, 'rotBool', self.rotOverrideCustom))

    rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0x0', \
        get=lambda self: getValues(self, self.actorID, 'XRot', self.rotOverrideXCustom))

    rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0x0', \
        get=lambda self: getValues(self, self.actorID, 'YRot', self.rotOverrideYCustom))

    rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0x0', \
        get=lambda self: getValues(self, self.actorID, 'ZRot', self.rotOverrideZCustom))
    headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

    actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
    actorParamCustom : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
    rotOverrideCustom : bpy.props.BoolProperty(name = 'Override Rotation', default = False)
    rotOverrideXCustom : bpy.props.StringProperty(name = 'Rot X', default = '0x0')
    rotOverrideYCustom : bpy.props.StringProperty(name = 'Rot Y', default = '0x0')
    rotOverrideZCustom : bpy.props.StringProperty(name = 'Rot Z', default = '0x0')

    # Transition Actors (ACTORCAT_DOOR)
    transActorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumTransitionActorID, default = 'ACTOR_EN_DOOR')

    transActorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000', \
        get=lambda self: getValues(self, self.transActorID, 'transParam', self.transActorParamCustom))

    transActorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_EN_DOOR')
    transActorParamCustom : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')

    # The 'get=' option from Blender props don't actually save the data in the .blend
    # When the get function is called we have to save the data that'll be returned
    paramToSave: bpy.props.StringProperty()
    transParamToSave: bpy.props.StringProperty()
    XRotToSave: bpy.props.StringProperty()
    YRotToSave: bpy.props.StringProperty()
    ZRotToSave: bpy.props.StringProperty()
    rotBoolToSave: bpy.props.BoolProperty()

def drawActorProperty(layout, actorProp, altRoomProp, objName, detailedProp):
    actorIDBox = layout.column()

    drawDetailedProperties('Actor Property', actorProp, actorIDBox, objName, \
        OOT_SearchActorIDEnumOperator, 'actorID', 'actorParam', detailedProp, detailedProp.actorKey)

    drawActorHeaderProperty(actorIDBox, actorProp.headerSettings, "Actor", altRoomProp, objName)

# Transition Actor Property
class OOT_SearchTransActorIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_trans_actor_id_enum_operator"
    bl_label = "Select Transition Actor"
    bl_property = "transActorID"
    bl_options = {'REGISTER', 'UNDO'}

    transActorID: bpy.props.EnumProperty(items = ootEnumTransitionActorID, default = "ACTOR_EN_DOOR")
    objName : bpy.props.StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.objName]
        detailedProp = obj.ootActorDetailedProperties

        obj.ootTransitionActorProperty.actor.transActorID = self.transActorID
        detailedProp.transActorID = self.transActorID
        for actorNode in root:
            if actorNode.get('ID') == self.transActorID:
                detailedProp.transActorKey = actorNode.get('Key')

        bpy.context.region.tag_redraw()
        self.report({'INFO'}, "Selected: " + self.transActorID)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

class OOTTransitionActorProperty(bpy.types.PropertyGroup):
    roomIndex : bpy.props.IntProperty(min = 0)
    cameraTransitionFront : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
    cameraTransitionFrontCustom : bpy.props.StringProperty(default = '0x00')
    cameraTransitionBack : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
    cameraTransitionBackCustom : bpy.props.StringProperty(default = '0x00')

    actor : bpy.props.PointerProperty(type = OOTActorProperty)

def drawTransitionActorProperty(layout, transActorProp, altSceneProp, roomObj, objName, detailedProp):
    actorIDBox = layout.column()

    drawDetailedProperties('Transition Property', transActorProp.actor, actorIDBox, objName, \
        OOT_SearchTransActorIDEnumOperator, 'transActorID', 'transActorParam', detailedProp, detailedProp.transActorKey)

    if roomObj is None:
        actorIDBox.label(text = "This must be part of a Room empty's hierarchy.", icon = "ERROR")
    else:
        label_split(actorIDBox, "Room To Transition From", str(roomObj.ootRoomHeader.roomIndex))
    prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
    actorIDBox.label(text = "Y+ side of door faces toward the \"from\" room.", icon = "ERROR")
    drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
    drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

    drawActorHeaderProperty(actorIDBox, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName)

# Entrance Property
class OOTEntranceProperty(bpy.types.PropertyGroup):
    # This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
    spawnIndex : bpy.props.IntProperty(min = 0)
    customActor : bpy.props.BoolProperty(name = "Use Custom Actor")
    actor : bpy.props.PointerProperty(type = OOTActorProperty)

def drawEntranceProperty(layout, obj, altSceneProp, objName, detailedProp):
    box = layout.column()
    entranceProp = obj.ootEntranceProperty

    drawDetailedProperties('Entrance Property', entranceProp, box, None, \
        None, 'actorID', 'actorParam', detailedProp, '0000')

    drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
