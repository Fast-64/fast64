# TODO: document XML file (<parameter>), QoL buttons and stuff

import math, os, bpy, bmesh, mathutils, xml.etree.ElementTree as ET
from collections import defaultdict
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *

from ..utility import *


# Read the XML file, throws an error if the file is missing
try: tree = ET.parse(os.path.dirname(os.path.abspath(__file__)) + '/ActorList.xml')
except: PluginError("ERROR: File 'fast64_internal/oot/ActorList.xml' is missing.")
root = tree.getroot()

# Create an empty class for the attributes later
class OOTActorDetailedProperties(bpy.types.PropertyGroup):
    pass

def fillDicts(dict, tag, attr):
    '''This function is used to fill the dictionnaries from the ActorList.XML data'''
    for actorNode in root:
        if attr == 'Key':
            dict[actorNode.get(tag)] = actorNode.get(attr)
        else:
            for elem in actorNode:
                if elem.tag == tag:
                    if attr == 'elem.text':
                        dict[actorNode.get('Key')].append(elem.text)
                    else: 
                        dict[actorNode.get('Key')].append(elem.get(attr))

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

def genBLProp(actorID, layout, data, field, name):
    '''Determines if it needs to show the option on the panel'''
    if data.actorID == actorID:
        prop_split(layout, data, field, name)

def getActorParameter(object, field, shift):
    return int(getattr(object, field, '0x0'), base=16) << shift

def getShift(elem):
    mask = int(elem.get('Mask'), base=16)
    return len(f'{mask:016b}') - len(f'{mask:016b}'.rstrip('0'))

def setActorValues(self, field, customField):
    if self.actorID == 'Custom':
        setattr(OOTSetParamOp, field, customField)
    return getattr(OOTSetParamOp, field)

def computeParams(elem, detailedProp, lenProp, lenSwitch):
    params = 0
    if elem.tag == 'Flag':
        shift = getShift(elem)
        elemType = elem.get('Type')
        if elemType == 'Chest':
            params += getActorParameter(detailedProp, detailedProp.actorKey + '.chestFlag', shift)
        if elemType == 'Collectible':
            params += getActorParameter(detailedProp, detailedProp.actorKey + '.collectibleFlag', shift)
        if elemType == 'Switch':
            for i in range(1, (int(lenSwitch, base=10) + 1)):
                if i == int(elem.get('Index'), base=10):
                    params += getActorParameter(detailedProp, detailedProp.actorKey + '.switchFlag' + f'{i}', shift)
    if elem.tag == 'Property' and elem.get('Name') != 'None':
        for j in range(1, (int(lenProp, base=10) + 1)):
            if j == int(elem.get('Index'), base=10):
                params += getActorParameter(detailedProp, (detailedProp.actorKey + '.props' + f'{j}'), getShift(elem))
    if elem.tag == 'Item':
        params += int(detailedProp.itemChest, base=16) << getShift(elem)
    if elem.tag == 'Collectible':
        params += getActorParameter(detailedProp, detailedProp.actorKey + '.collectibleDrop', getShift(elem))
    return params

def showBLProps(actorIDBox, actorProp, paramField, rotBoolField, rotXField, rotYField, rotZField):
    #layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
    prop_split(actorIDBox, actorProp, paramField, 'Actor Parameter')

    actorIDBox.prop(actorProp, rotBoolField, text = 'Override Rotation (ignore Blender rot)')
    if actorProp.rotOverride:
        prop_split(actorIDBox, actorProp, rotXField, 'Rot X')
        prop_split(actorIDBox, actorProp, rotYField, 'Rot Y')
        prop_split(actorIDBox, actorProp, rotZField, 'Rot Z')

class OOTSetParamOp():
    param: '0x0'
    XRot: '0x0'
    YRot: '0x0'
    ZRot: '0x0'
    rotBool: bool=False

# defaultdict(list) is like an editable dictionnary
dataActorID = defaultdict(list)
fillDicts(dataActorID, 'ID', 'Key')
keysActorID = [(f"{key}", f"{key}", f"{key}") for key in dataActorID.keys()]

def editOOTActorDetailedProperties():
    '''This function is used to edit the OOTActorDetailedProperties class before it's registered'''
    propAnnotations = getattr(OOTActorDetailedProperties, '__annotations__', None)
    if propAnnotations is None:
        propAnnotations = {}
        OOTActorDetailedProperties.__annotations__ = propAnnotations

    propAnnotations['actorID'] = bpy.props.EnumProperty(name='Actor ID', items=keysActorID)
    propAnnotations['actorKey'] = bpy.props.StringProperty(name='Actor ID', default='0000')
    propAnnotations['itemChest'] = bpy.props.EnumProperty(name='Chest Content', items=ootEnBoxContent)

    # Generate the fields
    for actorNode in root:
        i = j = 1
        actorKey = actorNode.get('Key')
        for elem in actorNode:
            if elem.tag == 'Property' and elem.get('Name') != 'None':
                genString(propAnnotations, actorKey, ('.props' + f'{i}'), actorKey)
                i += 1
            elif elem.tag == 'Flag':
                if elem.get('Type') == 'Chest':
                    genString(propAnnotations, actorKey, '.chestFlag', 'Chest Flag')
                elif elem.get('Type') == 'Collectible':
                    genString(propAnnotations, actorKey, '.collectibleFlag', 'Collectible Flag')
                elif elem.get('Type') == 'Switch':
                    genString(propAnnotations, actorKey, ('.switchFlag' + f'{j}'), 'Switch Flag')
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

class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_actor_id_enum_operator"
    bl_label = "Select Actor ID"
    bl_property = "actorID"
    bl_options = {'REGISTER', 'UNDO'}

    actorID : bpy.props.EnumProperty(items = ootEnumActorID, default = "ACTOR_PLAYER")
    actorUser : bpy.props.StringProperty(default = "Actor")
    objName : bpy.props.StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.objName]
        detailedProp = obj.ootActorDetailedProperties

        if self.actorUser == "Transition Actor":
            obj.ootTransitionActorProperty.actor.actorID = self.actorID
        elif self.actorUser == "Actor":
            tmp = list(dataActorID.items())
            for i in range(len(keysActorID)):
                if keysActorID[i][0] == self.actorID:
                    detailedProp.actorID = self.actorID
                    detailedProp.actorKey = tmp[i][1]
                obj.ootActorProperty.actorID = self.actorID

        elif self.actorUser == "Entrance":
            obj.ootEntranceProperty.actor.actorID = self.actorID
        else:
            raise PluginError("Invalid actor user for search: " + str(self.actorUser))

        bpy.context.region.tag_redraw()
        self.report({'INFO'}, "Selected: " + self.actorID)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
    headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
    expandTab : bpy.props.BoolProperty(name = "Expand Tab")

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

class OOTActorProperty(bpy.types.PropertyGroup):
    actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')
    actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000', get=lambda self: setActorValues(self, 'param', self.actorIDCustom))
    rotOverride : bpy.props.BoolProperty(name = 'Override Rotation', default = False, get=lambda self: setActorValues(self, 'rotBool', self.rotOverrideCustom))
    rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0x0', get=lambda self: setActorValues(self, 'XRot', self.rotOverrideXCustom))
    rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0x0', get=lambda self: setActorValues(self, 'YRot', self.rotOverrideYCustom))
    rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0x0', get=lambda self: setActorValues(self, 'ZRot', self.rotOverrideZCustom))
    headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

    actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
    actorParamCustom : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
    rotOverrideCustom : bpy.props.BoolProperty(name = 'Override Rotation', default = False)
    rotOverrideXCustom : bpy.props.StringProperty(name = 'Rot X', default = '0x0')
    rotOverrideYCustom : bpy.props.StringProperty(name = 'Rot Y', default = '0x0')
    rotOverrideZCustom : bpy.props.StringProperty(name = 'Rot Z', default = '0x0')

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

def drawActorProperty(layout, actorProp, altRoomProp, objName, detailedProp):
    #prop_split(layout, actorProp, 'actorID', 'Actor')
    actorIDBox = layout.column()
    #actorIDBox.box().label(text = "Settings")
    searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon = 'VIEWZOOM')
    searchOp.actorUser = "Actor"
    searchOp.objName = objName

    split = actorIDBox.split(factor = 0.5)
    split.label(text = "Actor ID")
    split.label(text = getEnumName(ootEnumActorID, actorProp.actorID))

    if actorProp.actorID == 'Custom':
        #actorIDBox.prop(actorProp, 'actorIDCustom', text = 'Actor ID')
        prop_split(actorIDBox, actorProp, 'actorIDCustom', '')
                    
    propAnnot = getattr(detailedProp, detailedProp.actorKey + ('.type'), None)
    if propAnnot is not None:
        genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey + '.type', 'Type')

    if actorProp.actorID == 'ACTOR_EN_BOX':
        searchOp = actorIDBox.operator(OOT_SearchChestContentEnumOperator.bl_idname, icon='VIEWZOOM')
        searchOp.objName = objName
        split = actorIDBox.split(factor=0.5)
        split.label(text="Chest Content")
        split.label(text=getEnumName(ootEnBoxContent, detailedProp.itemChest))
                    
    propAnnot = getattr(detailedProp, detailedProp.actorKey + ('.collectibleDrop'), None)
    if propAnnot is not None:
        genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey + '.collectibleDrop', 'Collectible Drop')

    for actorNode in root:
        i = j = 1
        if detailedProp.actorKey == actorNode.get('Key'):
            for elem in actorNode:
                if elem.get('Name') != 'None':
                    if elem.tag == 'Property':
                        propAnnot = getattr(detailedProp, detailedProp.actorKey + ('.props' + f'{i}'), None)
                        if propAnnot is not None:
                            genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey + '.props' + f'{i}', elem.get('Name'))
                        i += 1
                    elif elem.get('Type') == 'Switch':
                        propAnnot = getattr(detailedProp, detailedProp.actorKey + '.switchFlag' + f'{i}', None)
                        if propAnnot is not None:
                            genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey + '.switchFlag' + f'{j}', 'Switch Flag #' + f'{j}')
                        j += 1

    flagList = root.findall('.//Flag')
    flagListID = [(actorNode.get('ID')) for actorNode in root for elem in actorNode if elem.tag == 'Flag']
    for i in range(len(flagList)):
        if flagListID[i] == actorProp.actorID:
            if flagList[i].get('Type') == 'Chest':
                genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey + '.chestFlag', 'Chest Flag')
            if flagList[i].get('Type') == 'Collectible':
                genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey + '.collectibleFlag', 'Collectible Flag')

    # This next if handles the necessary maths to get the actor parameters from the detailed panel
    # Reads ActorList.xml and figures out the necessary bit shift and applies it to whatever is in the blender string field
    # Actor key refers to the hex ID of an actor
    # It was made like that to make it future proof as the OoT decomp isn't fully done yet so names can still change
    # For Switch Flags & <Property> we need to make sure the value corresponds to the mask, hence the index in the XML
    # For Chest Content (<Item>) we don't need the actor key because it's handled differently: it's a search box
    actorParams = XRotParams = YRotParams = ZRotParams = lenProp = lenSwitch = 0
    i = j = 1
    if actorProp.actorID != 'Custom':
        # if the user wants to use a custom actor this computation is pointless

        # Looking for the highest Property/Switch index for the current actor
        for actorNode in root:
            if actorNode.get('Key') == detailedProp.actorKey:
                for elem in actorNode:
                    if elem.tag == 'Property':
                        lenProp = elem.get('Index')
                    if elem.tag == 'Flag' and elem.get('Type') == 'Switch':
                        lenSwitch = elem.get('Index')

        for actorNode in root:
            if actorNode.get('Key') == detailedProp.actorKey:
                for elem in actorNode:
                    paramTarget = elem.get('Target')
                    if paramTarget == 'Params' or paramTarget is None:
                        actorParams += computeParams(elem, detailedProp, lenProp, lenSwitch)
                    elif paramTarget == 'XRot':
                        XRotParams += computeParams(elem, detailedProp, lenProp, lenSwitch)
                    elif paramTarget == 'YRot':
                        YRotParams += computeParams(elem, detailedProp, lenProp, lenSwitch)
                    elif paramTarget == 'ZRot':
                        ZRotParams += computeParams(elem, detailedProp, lenProp, lenSwitch)

        # Finally, add the actor type value, which is already shifted in the XML
        actorParams += getActorParameter(detailedProp, detailedProp.actorKey + '.type', 0)
        OOTSetParamOp.param = f'0x{actorParams:X}'

        if XRotParams != 0 or YRotParams != 0 or ZRotParams != 0:
            OOTSetParamOp.rotBool = True
            OOTSetParamOp.XRot = f'0x{XRotParams:X}'
            OOTSetParamOp.YRot = f'0x{YRotParams:X}'
            OOTSetParamOp.ZRot = f'0x{ZRotParams:X}'
        else:
            OOTSetParamOp.rotBool = False
            OOTSetParamOp.XRot = OOTSetParamOp.YRot = OOTSetParamOp.ZRot = '0x0'
        showBLProps(actorIDBox, actorProp, 'actorParam', 'rotOverride', 'rotOverrideX', 'rotOverrideY', 'rotOverrideZ')
    else:
        showBLProps(actorIDBox, actorProp, 'actorParamCustom', 'rotOverrideCustom', 'rotOverrideXCustom', 'rotOverrideYCustom', 'rotOverrideZCustom')

    drawActorHeaderProperty(actorIDBox, actorProp.headerSettings, "Actor", altRoomProp, objName)

class OOTTransitionActorProperty(bpy.types.PropertyGroup):
    roomIndex : bpy.props.IntProperty(min = 0)
    cameraTransitionFront : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
    cameraTransitionFrontCustom : bpy.props.StringProperty(default = '0x00')
    cameraTransitionBack : bpy.props.EnumProperty(items = ootEnumCamTransition, default = '0x00')
    cameraTransitionBackCustom : bpy.props.StringProperty(default = '0x00')
    
    actor : bpy.props.PointerProperty(type = OOTActorProperty)

def drawTransitionActorProperty(layout, transActorProp, altSceneProp, roomObj, objName):
    actorIDBox = layout.column()
    #actorIDBox.box().label(text = "Properties")
    #prop_split(actorIDBox, transActorProp, 'actorID', 'Actor')
    #actorIDBox.box().label(text = "Actor ID: " + getEnumName(ootEnumActorID, transActorProp.actor.actorID))
    searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon = 'VIEWZOOM')
    searchOp.actorUser = "Transition Actor"
    searchOp.objName = objName

    split = actorIDBox.split(factor = 0.5)
    split.label(text = "Actor ID")
    split.label(text = getEnumName(ootEnumActorID, transActorProp.actor.actorID))

    if transActorProp.actor.actorID == 'Custom':
        prop_split(actorIDBox, transActorProp.actor, 'actorIDCustom', '')

    #layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
    prop_split(actorIDBox, transActorProp.actor, "actorParam", 'Actor Parameter')

    if roomObj is None:
        actorIDBox.label(text = "This must be part of a Room empty's hierarchy.", icon = "ERROR")
    else:
        label_split(actorIDBox, "Room To Transition From", str(roomObj.ootRoomHeader.roomIndex))
    prop_split(actorIDBox, transActorProp, "roomIndex", "Room To Transition To")
    actorIDBox.label(text = "Y+ side of door faces toward the \"from\" room.", icon = "ERROR")
    drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionFront", "Camera Transition Front", "")
    drawEnumWithCustom(actorIDBox, transActorProp, "cameraTransitionBack", "Camera Transition Back", "")

    drawActorHeaderProperty(actorIDBox, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName)
    
class OOTEntranceProperty(bpy.types.PropertyGroup):
    # This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
    spawnIndex : bpy.props.IntProperty(min = 0)
    customActor : bpy.props.BoolProperty(name = "Use Custom Actor")
    actor : bpy.props.PointerProperty(type = OOTActorProperty)

def drawEntranceProperty(layout, obj, altSceneProp, objName):
    box = layout.column()
    #box.box().label(text = "Properties")
    roomObj = getRoomObj(obj)
    if roomObj is not None:
        split = box.split(factor = 0.5)
        split.label(text = "Room Index")
        split.label(text = str(roomObj.ootRoomHeader.roomIndex))
    else:
        box.label(text = "This must be part of a Room empty's hierarchy.", icon = 'OUTLINER')

    entranceProp = obj.ootEntranceProperty
    prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
    prop_split(box, entranceProp.actor, "actorParam", "Actor Param")
    box.prop(entranceProp, "customActor")
    if entranceProp.customActor:
        prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")
    
    drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
