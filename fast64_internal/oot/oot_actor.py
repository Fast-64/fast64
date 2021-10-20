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
        for elem in actorNode:
            if attr == 'Key':
                    dict[actorNode.get(tag)] = actorNode.get(attr)
            elif elem.tag == tag:
                if attr == 'elem.text':
                    dict[actorNode.get('Key')].append(elem.text)
                else: 
                    dict[actorNode.get('Key')].append(elem.get(attr))

def genEnum(annotations, dict1, dict2, suffix, enumName):
    '''This function is used to generate the proper enum blender property'''
    for name, values in dict1.items():
        if name is None: name = 'None'
        objName = name + suffix
        actorTypeList = [(value, dict2[name].pop(0), value) for value in values]
        prop = bpy.props.EnumProperty(name=enumName, items=actorTypeList)
        annotations[objName] = prop

def genString(annotations, dict, suffix, stringName):
    '''This function is used to generate the proper enum blender property'''
    for id, key in dict.items():
        objName = key + suffix
        prop = bpy.props.StringProperty(name=stringName, default='0x0000')
        annotations[objName] = prop

def getKeys(dict):
    '''Generates tuples from dict keys'''
    return [(key, key, key) for key in dict.keys()]

def genBLProp(actorID, layout, data, field, suffix, name):
    '''Determines if it needs to show the option on the panel'''
    if data.actorID == actorID:
        prop_split(layout, data, field + suffix, name)

# Create editable dictionnaries
descParams = defaultdict(list) # contains texts from the <Parameter> tag in the XML
dataParams = defaultdict(list) # contains masks from the same
descProps = defaultdict(list)
dataProps = defaultdict(list)
dataActorID = defaultdict(list)

fillDicts(dataParams, 'Parameter', 'Params')
fillDicts(descParams, 'Parameter', 'elem.text')
fillDicts(dataProps, 'Property', 'Mask')
fillDicts(descProps, 'Property', 'Name')
fillDicts(dataActorID, 'ID', 'Key')
keysActorID = getKeys(dataActorID)
keysParams = getKeys(dataParams)
keysProps = getKeys(dataProps)

def editOOTActorDetailedProperties():
    '''This function is used to edit the OOTActorDetailedProperties class before it's registered'''
    propAnnotations = getattr(OOTActorDetailedProperties, '__annotations__', None)
    if propAnnotations is None:
        propAnnotations = {}
        OOTActorDetailedProperties.__annotations__ = propAnnotations

    propAnnotations['actorID'] = bpy.props.EnumProperty(name='Actor ID', items=keysActorID)
    propAnnotations['actorKey'] = bpy.props.StringProperty(name='Actor ID', default='0000')
    propAnnotations['type'] = bpy.props.EnumProperty(name='Actor Type', items=keysParams)
    propAnnotations['actorProps'] = bpy.props.EnumProperty(name='Properties', items=keysProps)
    propAnnotations['actorPropsValue'] = bpy.props.StringProperty(name='Value', default='0x0000')
    propAnnotations['switchFlag'] = bpy.props.StringProperty(name='Switch Flag', default='0x0000')
    propAnnotations['chestFlag'] = bpy.props.StringProperty(name='Chest Flag', default='0x0000')
    propAnnotations['collectibleFlag'] = bpy.props.StringProperty(name='Collectible Flag', default='0x0000')
    propAnnotations['itemChest'] = bpy.props.EnumProperty(name='Chest Content', items=ootEnBoxContent)

    genEnum(propAnnotations, dataParams, descParams, '.type', 'Actor Type')
    genEnum(propAnnotations, dataProps, descProps, '.props', 'Properties')
    genString(propAnnotations, dataActorID, '.propValue', 'Value')
    genString(propAnnotations, dataActorID, '.switchFlag', 'Switch Flag')
    genString(propAnnotations, dataActorID, '.chestFlag', 'Chest Flag')
    genString(propAnnotations, dataActorID, '.collectibleFlag', 'Collectible Flag')

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
            box.label(text = "Header does not exist.", icon = "ERROR")
        
class OOTActorProperty(bpy.types.PropertyGroup):
    actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')
    actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
    actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
    rotOverride : bpy.props.BoolProperty(name = 'Override Rotation', default = False)
    rotOverrideX : bpy.props.StringProperty(name = 'Rot X', default = '0')
    rotOverrideY : bpy.props.StringProperty(name = 'Rot Y', default = '0')
    rotOverrideZ : bpy.props.StringProperty(name = 'Rot Z', default = '0')
    headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)     

class OOT_SearchChestContentEnumOperator(bpy.types.Operator):
    bl_idname = "object.oot_search_chest_content_enum_operator"
    bl_label = "Select Chest Content"
    bl_property = "itemChest"
    bl_options = {'REGISTER', 'UNDO'}

    itemChest : bpy.props.EnumProperty(items = ootEnBoxContent, default = '0x48')
    objName : bpy.props.StringProperty()

    def execute(self, context):
        if self.objName in bpy.data.objects:
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

    genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey, '.type', 'Type')
    if actorProp.actorID == 'ACTOR_EN_BOX':
        searchOp = actorIDBox.operator(OOT_SearchChestContentEnumOperator.bl_idname, icon='VIEWZOOM')
        split = actorIDBox.split(factor=0.5)
        split.label(text="Chest Content")
        split.label(text=getEnumName(ootEnBoxContent, detailedProp.itemChest))

    propAnnot = getattr(detailedProp, detailedProp.actorKey + '.props', None) 
    if propAnnot is not None:
        genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey, '.props', 'Properties')
        if propAnnot != '0x0000':
            genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey, '.propValue', 'Value')

    flagList = root.findall('.//Flag')
    flagListID = [(actorNode.get('ID')) for actorNode in root for elem in actorNode if elem.tag == 'Flag']
    for i in range(len(flagList)):
        if flagListID[i] == actorProp.actorID:
            if flagList[i].get('Type') == 'Switch':
                genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey, '.switchFlag', 'Switch Flag')
            if flagList[i].get('Type') == 'Chest':
                genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey, '.chestFlag', 'Chest Flag')
            if flagList[i].get('Type') == 'Collectible':
                genBLProp(actorProp.actorID, actorIDBox, detailedProp, detailedProp.actorKey, '.collectibleFlag', 'Collectible Flag')

    #layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
    prop_split(actorIDBox, actorProp, "actorParam", 'Actor Parameter')
    
    actorIDBox.prop(actorProp, 'rotOverride', text = 'Override Rotation (ignore Blender rot)')
    if actorProp.rotOverride:
        prop_split(actorIDBox, actorProp, 'rotOverrideX', 'Rot X')
        prop_split(actorIDBox, actorProp, 'rotOverrideY', 'Rot Y')
        prop_split(actorIDBox, actorProp, 'rotOverrideZ', 'Rot Z')

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
        box.label(text = "This must be part of a Room empty's hierarchy.", icon = "ERROR")

    entranceProp = obj.ootEntranceProperty
    prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
    prop_split(box, entranceProp.actor, "actorParam", "Actor Param")
    box.prop(entranceProp, "customActor")
    if entranceProp.customActor:
        prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")
    
    drawActorHeaderProperty(box, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName)
