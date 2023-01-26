import bpy, os, mathutils, copy
from typing import Iterable
from ..utility import attemptModifierApply, checkIsSM64InlineGeoLayout, selectSingleObject, get_obj_temp_mesh
from .sm64_objects import InlineGeolayoutObjConfig, inlineGeoLayoutObjects, check_obj_is_room
from .sm64_geolayout_classes import *
from ..f3d.f3d_writer import FModel, TriangleConverterInfo, saveStaticModel, getInfoDict

def starSelectWarning(operator, fileStatus):
    if fileStatus is not None and not fileStatus.starSelectC:
        operator.report({"WARNING"}, "star_select.c not found, skipping star select scrolling.")


def cameraWarning(operator, fileStatus):
    if fileStatus is not None and not fileStatus.cameraC:
        operator.report({"WARNING"}, "camera.c not found, skipping camera volume and zoom mask exporting.")


ULTRA_SM64_MEMORY_C = "src/boot/memory.c"
SM64_MEMORY_C = "src/game/memory.c"


def getMemoryCFilePath(decompDir):
    isUltra = os.path.exists(os.path.join(decompDir, ULTRA_SM64_MEMORY_C))
    relPath = ULTRA_SM64_MEMORY_C if isUltra else SM64_MEMORY_C
    return os.path.join(decompDir, relPath)




enumSM64EmptyWithGeolayout_TWO = {"Area Root", "Switch"}

def sm64_object_uses_geolayout(obj: bpy.types.Object, ignoreAttr: str):
    if ignoreAttr is not None and getattr(obj, ignoreAttr):
        return False

    if isinstance(obj.data, bpy.types.Mesh):
        return True

    if (
        # TODO: ADD SHARED CHILDREN HOW
        check_obj_is_room(obj) or
        obj.sm64_obj_type in enumSM64EmptyWithGeolayout_TWO or
        checkIsSM64InlineGeoLayout(obj.sm64_obj_type)
    ):
        return True
    for child in obj.children:
        # return true if child has a mesh
        if isinstance(child.data, bpy.types.Mesh):
            return True
        # recursive check
        if sm64_object_uses_geolayout(child):
            return True
    return False

def select_geolayout_children(obj: bpy.types.Object, ignoreAttr: str):
    if sm64_object_uses_geolayout(obj, ignoreAttr):
        obj.select_set(True)
        obj.original_name = obj.name
    for child in obj.children:
        select_geolayout_children(child, ignoreAttr)

def duplicate_geolayout_candidates(obj: bpy.types.Object, ignoreAttr: str):
    bpy.ops.object.select_all(action="DESELECT")
    select_geolayout_children(obj, ignoreAttr)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()

def apply_objects_modifiers(allObjs: Iterable[bpy.types.Object]):
    # first apply modifiers so that any objects that affect each other are taken into consideration
    for selectedObj in allObjs:
        selectSingleObject(selectedObj)

        for modifier in selectedObj.modifiers:
            attemptModifierApply(modifier)

def apply_object_transformations(obj: bpy.types.Object):
    selectSingleObject(obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)

GEO_SHOULD_TRANSLATE = "TRANSLATE"
GEO_SHOULD_ROTATE = "ROTATE"
GEO_SHOULD_SCALE = "SCALE"
GEO_NO_TRANSFORMS = set()
mapInlineGeoLayoutObjectsAppliedTransforms = {
    "Geo ASM": GEO_NO_TRANSFORMS,
    "Geo Branch": GEO_NO_TRANSFORMS,
    "Geo Translate/Rotate": {GEO_SHOULD_TRANSLATE, GEO_SHOULD_ROTATE},
    "Geo Translate Node": {GEO_SHOULD_TRANSLATE},
    "Geo Rotation Node": {GEO_SHOULD_ROTATE},
    "Geo Billboard": {GEO_SHOULD_TRANSLATE},
    "Geo Scale": {GEO_SHOULD_SCALE},
    "Geo Displaylist": GEO_NO_TRANSFORMS,
    "Custom Geo Command": GEO_NO_TRANSFORMS,
}


def get_obj_transformations(obj: bpy.types.Object):
    if isinstance(obj.data, bpy.types.Mesh):
        if obj.get("instanced_mesh_name") is not None and obj.data.users > 1: # check > 1 as an extra sanity check
            # technically these should be "can translate/rotate/scale", logic in process_geolayout
            # decides how it should be transformed most efficiently
            return {GEO_SHOULD_TRANSLATE, GEO_SHOULD_ROTATE, GEO_SHOULD_SCALE}
        if obj.geo_cmd_static == "Optimal" and not obj.use_render_range:
            return GEO_NO_TRANSFORMS
        # elif obj.geo_cmd_static == "DisplayListWithOffset":
            # return {GEO_SHOULD_TRANSLATE}
        # elif obj.geo_cmd_static == "Billboard":
            # return {GEO_SHOULD_TRANSLATE}
        return {GEO_SHOULD_TRANSLATE}
    if checkIsSM64InlineGeoLayout(obj.sm64_obj_type):
        return mapInlineGeoLayoutObjectsAppliedTransforms[obj.sm64_obj_type]
    return GEO_NO_TRANSFORMS

def return_obj_or_get_children(obj: bpy.types.Object):
    next_children = []
    if obj.data is None and len(get_obj_transformations(obj)) == 0 and not check_obj_is_room(obj):
        next_children.extend(return_obj_or_get_children(obj.children))


inline_geo_objects_with_transform = {
    "Geo Translate/Rotate",
    "Geo Translate Node",
    "Geo Rotation Node",
    "Geo Billboard",
    "Geo Scale",
}
inline_geo_objects_with_no_transform = {"Geo ASM", "Geo Branch", "Geo Displaylist", "Custom Geo Command"}
inline_geo_object_types = (inline_geo_objects_with_transform | inline_geo_objects_with_no_transform)
class GeoObject():
    ignore = False
    children: list["GeoObject"] = []
    parent: "GeoObject" = None
    has_rotation = False # gets set in process_geolayout
    has_translation = False # gets set in process_geolayout
    has_scaling = False # gets set in process_geolayout

    def __init__(self, obj: bpy.types.Object, index: int, is_root: bool = False):
        self.parent = self # default to self
        self.obj = obj
        self.index = index # TODO: if unused, remove this and enumerations!!!!!

        if not obj.ignore_render:
            children = self.create_geo_children(sorted(obj.children, key=lambda childObj: childObj.original_name.lower()))
            if check_obj_is_room(obj):
                room_data = obj.fast64.sm64.room
                pre_render_children, post_render_children = room_data.get_room_objects()
                #! TODO: need to duplicate these children i think
                children = (
                    self.create_geo_children(pre_render_children)
                    + children
                    + self.create_geo_children(post_render_children)
                )
            self.children = children
        else:
            self.ignore = True
            return

        sm64_obj_type = obj.sm64_obj_type
        self.is_root = is_root
        self.is_mesh = isinstance(obj.data, bpy.types.Mesh)
        self.is_switch_option = obj.parent and obj.parent.sm64_obj_type == "Switch"
        self.is_switch = obj.sm64_obj_type == "Switch"

        # TODO: add instanced nodes to this
        self.transformations = get_obj_transformations(obj)
        self.should_transform_children = bool(len(self.transformations))
        self.is_instanced = bool(obj.get("instanced_mesh_name"))

        self.should_render_with_children = sm64_obj_type in inline_geo_objects_with_no_transform
        self.is_inline_geo = sm64_obj_type in inline_geo_object_types
        self.is_room = check_obj_is_room(obj)
        
        self.is_area = obj.sm64_obj_type == "Area Root"
        self.is_area_with_rooms = self.is_area and obj.enableRoomSwitch

        self.is_geo = is_root or self.is_mesh or self.is_switch_option or self.is_inline_geo or self.is_switch or self.is_room
        # children already have set the above properties by this point
        self.has_geo_children = self.check_has_child_with_geo()
        if not self.is_geo and not self.has_geo_children:
            self.ignore = True
            self.children = []
            return

    def yield_recursive_children(self):
        yield self
        for child in self.children:
            if child.ignore:
                continue
            yield from child.yield_recursive_children()

    def get_recursive_children(self):
        for child in self.yield_recursive_children():
            if child is self: # skip yourself
                continue
            yield child

    def check_has_child_with_geo(self):
        for child in self.get_recursive_children():
            if child.is_geo:
                return True
        return False

    def create_geo_child(self, obj: bpy.types.Object, index: int):
        c = GeoObject(obj, index)
        c.parent = self
        return c

    def create_geo_children(self, children: Iterable[bpy.types.Object]):
        return [self.create_geo_child(c, i) for i, c in enumerate(children)]

    def get_flattened(self):
        if self.ignore:
            return []
        if self.is_geo:
            return [self]
        if self.has_geo_children:
            return self.children
        return []

    def flatten(self):
        new_children = []
        for child in self.children:
            # flatten from bottom up
            child.flatten()
            flat = child.get_flattened()
            new_children.extend(flat)
        self.children = new_children
        for child in self.children:
            child.parent = self

    def realize_new_hierarchy(self):
        for child in self.children:
            # set all immediate children to be this object
            if child.obj.parent is not self.obj:
                selectSingleObject(child.obj)
                bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
                self.obj.select_set(True)
                bpy.context.view_layer.objects.active = self.obj
                bpy.ops.object.parent_set(keep_transform=True)

        # then all children should do the same
        for child in self.children:
            child.realize_new_hierarchy()

    def realize_transformations(self):
        # then all children should do the same
        for child in self.children:
            selectSingleObject(child.obj)
            # bpy.ops.object.transform_apply(properties=False)
            bpy.ops.object.transform_apply(
                location=GEO_SHOULD_TRANSLATE not in self.transformations,
                rotation=GEO_SHOULD_ROTATE not in self.transformations,
                scale=GEO_SHOULD_SCALE not in self.transformations,
                properties=False
            )

            child.realize_transformations()


def duplicate_and_create_initial_geolayout_hierarchy(
    obj: bpy.types.Object,
    ignoreAttr: str
):
    # TODO: try and cleanup on failure
    # TODO: also duplicate room pseudo children?
    duplicate_geolayout_candidates(obj, ignoreAttr)
    duped_root: bpy.types.Object = None
    all_objs = bpy.context.selected_objects[:]
    for duped_obj in all_objs:
        if duped_obj.original_name == obj.name:
            duped_root = duped_obj
            break
    if not duped_root:
        # TODO: better message lol!!
        raise Exception("We fucked up")

    apply_objects_modifiers(all_objs)

    geo_root = GeoObject(duped_root, 0, is_root=True)
    geo_root.flatten() # template structure

    selectSingleObject(geo_root.obj)
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    selectSingleObject(geo_root.obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)

    geo_root.realize_new_hierarchy()
    geo_root.realize_transformations()

    return geo_root

def check_has_rotation(rotate: mathutils.Quaternion):
    eulerRot = rotate.to_euler(geoNodeRotateOrder)
    return not(
        convertEulerFloatToShort(eulerRot[0]) == 0
        and convertEulerFloatToShort(eulerRot[1]) == 0
        and convertEulerFloatToShort(eulerRot[2]) == 0
    )

def check_has_translation(translate: mathutils.Vector):
    return not (
        convertFloatToShort(translate[0]) == 0
        and convertFloatToShort(translate[1]) == 0
        and convertFloatToShort(translate[2]) == 0
    )


def check_has_scaling(scale: mathutils.Vector):
    return not (
        int(round(scale[0] * 0x10000)) == 0x10000
        and int(round(scale[1] * 0x10000)) == 0x10000
        and int(round(scale[2] * 0x10000)) == 0x10000
    )

def add_transform_node_to_parent(parent_transform_node: TransformNode, new_node):
    transformNode = TransformNode(new_node)
    transformNode.parent = parent_transform_node
    parent_transform_node.children.append(transformNode)
    return transformNode

def process_pre_inline_geo(
    obj: bpy.types.Object,
    parent_transform_node: TransformNode
):
    inline_geo_conf: InlineGeolayoutObjConfig = inlineGeoLayoutObjects.get(obj.sm64_obj_type)
    if inline_geo_conf.name == "Geo ASM":
        node = FunctionNode(obj.fast64.sm64.geo_asm.func, obj.fast64.sm64.geo_asm.param)
    elif inline_geo_conf.name == "Geo Branch":
        node = JumpNode(True, None, obj.geoReference)
    elif inline_geo_conf.name == "Geo Displaylist":
        node = DisplayListNode(int(obj.draw_layer_static), obj.dlReference)
    elif inline_geo_conf.name == "Custom Geo Command":
        node = CustomNode(obj.customGeoCommand, obj.customGeoCommandArgs)
    node.hasDL = False
    parent_transform_node.children.append(node)

class ProcessGeolayoutContext:
    """Data related to processing a geolayout thats consistent and doesn't typically change"""
    def __init__(self,
        fModel: FModel, 
        geolayout: Geolayout,
        geolayout_graph: GeolayoutGraph,
        convert_textures: bool,
        base_transform_matrix: mathutils.Matrix
    ) -> None:
        self.fModel: FModel = fModel
        self.geolayout: Geolayout = geolayout
        self.geolayout_graph: GeolayoutGraph = geolayout_graph
        self.convert_textures: bool = convert_textures
        self.base_transform_matrix: mathutils.Matrix = base_transform_matrix
        pass
    
    def clone_with_new_geolayout(self, new_geolayout):
        return self.__class__(self.fModel, new_geolayout, self.geolayout_graph, self.convert_textures, self.base_transform_matrix)

def process_geo_switch(
    process_context: ProcessGeolayoutContext,
    geo_obj: GeoObject,
    parent_transform_node: TransformNode,
    switch_func: str,
    switch_param: str
):
    pre_switch_parent_node = parent_transform_node
    parent_transform_node = add_transform_node_to_parent(
        parent_transform_node,
        SwitchNode(switch_func, switch_param, geo_obj.obj.original_name)
    )

    print(geo_obj.obj.original_name)
    for i, child in enumerate(geo_obj.children):
        print(i, child.obj.original_name)
        if i == 0:
            process_geolayout(
                process_context,
                child,
                pre_switch_parent_node
            )
            continue

        option_geolayout = process_context.geolayout_graph.addGeolayout(
            child.obj, process_context.fModel.name + "_" + child.obj.original_name + "_geo"
        )
        process_context.geolayout_graph.addJumpNode(parent_transform_node, process_context.geolayout, option_geolayout)
        start_node = TransformNode(StartNode())
        option_geolayout.nodes.append(start_node)
        child_ctx = process_context.clone_with_new_geolayout(option_geolayout)
        process_geolayout(
            child_ctx,
            child,
            start_node,
        )

def process_inline_geo_node(
    obj: bpy.types.Object,
    translate: mathutils.Vector,
    rotate: mathutils.Quaternion,
    scale: mathutils.Vector,
):
    inline_geo_conf: InlineGeolayoutObjConfig = inlineGeoLayoutObjects.get(obj.sm64_obj_type)

    if inline_geo_conf.name == "Geo Translate/Rotate":
        return TranslateRotateNode(obj.draw_layer_static, 0, obj.useDLReference, translate, rotate, obj.dlReference)
    elif inline_geo_conf.name == "Geo Billboard":
        return BillboardNode(obj.draw_layer_static, obj.useDLReference, translate, obj.dlReference)
    elif inline_geo_conf.name == "Geo Translate Node":
        return TranslateNode(obj.draw_layer_static, obj.useDLReference, translate, obj.dlReference)
    elif inline_geo_conf.name == "Geo Rotation Node":
        return RotateNode(obj.draw_layer_static, obj.useDLReference, rotate, obj.dlReference)
    elif inline_geo_conf.name == "Geo Scale":
        return ScaleNode(obj.draw_layer_static, scale, obj.useDLReference, obj.dlReference)
    else:
        raise PluginError(f"Ooops! Didnt implement inline geo exporting for {inline_geo_conf.name}")

def get_optimal_node(
    geo_obj: GeoObject,
    translation: mathutils.Vector,
    rotation: mathutils.Quaternion,
    draw_layer: int
):
    if geo_obj.has_rotation and geo_obj.has_translation:
        return TranslateRotateNode(draw_layer, 0, False, translation, rotation)
    elif geo_obj.has_translation:
        return TranslateNode(draw_layer, False, translation)
    elif geo_obj.has_rotation:
        return RotateNode(draw_layer, False, rotation)
    else:
        return DisplayListNode(draw_layer)

def get_optimal_instanced_node(
    geo_obj: GeoObject,
    translation: mathutils.Vector,
    rotation: mathutils.Quaternion,
    scale: mathutils.Vector,
    parent_transform_node: TransformNode
):
    draw_layer = int(geo_obj.obj.draw_layer_static)
    node = get_optimal_node(geo_obj, translation, rotation, draw_layer)
    if not geo_obj.has_scaling:
        return node, parent_transform_node

    if geo_obj.has_rotation or geo_obj.has_translation:
        parent_transform_node = add_transform_node_to_parent(parent_transform_node, node)
    return ScaleNode(draw_layer, scale[0], True), parent_transform_node

def process_geolayout(
    process_context: ProcessGeolayoutContext,
    geo_obj: GeoObject,
    parent_transform_node: TransformNode,
):
    obj: bpy.types.Object = geo_obj.obj
    
    if geo_obj.ignore: # ignore hierarchy and bail
        return

    if geo_obj.should_render_with_children:
        process_pre_inline_geo(obj, parent_transform_node)
        for child in geo_obj.children:
            process_geolayout(process_context, child, parent_transform_node)
        return
    
    if geo_obj.is_switch or geo_obj.is_area_with_rooms:
        if geo_obj.is_switch:
            switch_func = obj.switchFunc
            switch_param = obj.switchParam
        else:
            switch_func = "geo_switch_area"
            switch_param = len(geo_obj.children)
        process_geo_switch(
            process_context,
            geo_obj,
            parent_transform_node,
            switch_func,
            switch_param
        )
        return

    if geo_obj.should_transform_children:
        translation, rotation, scale = obj.matrix_local.decompose()
        geo_obj.has_rotation = check_has_rotation(rotation)
        geo_obj.has_translation = check_has_translation(translation)
        geo_obj.has_scaling = check_has_scaling(scale)
    else:
        translation = mathutils.Vector((0, 0, 0))
        rotation = mathutils.Quaternion()
        scale = mathutils.Vector((1, 1, 1))
    
    node: BaseDisplayListNode = None
    if geo_obj.is_inline_geo:
        node = process_inline_geo_node(
            geo_obj.obj, translation, rotation, scale
        )
    elif obj.geo_cmd_static == "Optimal":
        # Allow geo transformations with instanced nodes
        if geo_obj.has_rotation or geo_obj.has_scaling or geo_obj.has_translation:
            if geo_obj.is_instanced:
                node, parent_transform_node = get_optimal_instanced_node(
                    geo_obj,
                    translation,
                    rotation,
                    scale,
                    parent_transform_node)
            else:
                #! TODO: better error message: explain its a bug in fast64
                raise Exception(f"Optimal node ({obj.original_name}) has good error message")
        else:
            node = DisplayListNode(int(obj.draw_layer_static))
    elif obj.geo_cmd_static == "DisplayListWithOffset":
        if geo_obj.has_rotation or geo_obj.has_scaling:
            # i strongly suspect nobody uses this because its for armatures primarily (its incorrectly named) -
            # should be "AnimatedPartNode". its not worth the bloat atm
            if geo_obj.is_instanced:
                raise Exception(
                    f"Unimplemented Error: DisplayListWithOffset node ({obj.original_name}) cannot be instanced (detected rotation and/or scale), please report to Fast64.")
            #! TODO: better error message: explain its a bug in fast64
            raise Exception(f"DisplayListWithOffset node ({obj.original_name}) has good error message")
        node = DisplayListWithOffsetNode(int(obj.draw_layer_static), True, translation)
    else:  # Billboard
        if geo_obj.has_rotation or geo_obj.has_scaling:
            if geo_obj.is_instanced:
                # order here MUST be billboard with translation -> rotation -> scale -> displaylist
                node = DisplayListNode(int(obj.draw_layer_static))
                parent_transform_node = add_transform_node_to_parent(
                    parent_transform_node, BillboardNode(int(obj.draw_layer_static), False, translation))
                if geo_obj.has_rotation:
                    parent_transform_node = add_transform_node_to_parent(
                        parent_transform_node, RotateNode(int(obj.draw_layer_static), False, rotation))
                if geo_obj.has_scaling:
                    parent_transform_node = add_transform_node_to_parent(
                        parent_transform_node, ScaleNode(int(obj.draw_layer_static), scale[0], False))
            else:
                #! TODO: Better error message: explain its a bug in fast64
                raise Exception(f"Billboard node ({obj.original_name}) has good error message")
        else:
            node = BillboardNode(int(obj.draw_layer_static), True, translation)

    if obj.data is not None and (obj.use_render_range or obj.add_shadow or obj.add_func):
        # the ordering here is weird.
        # the node created above is determining transformations, and since its created first, 
        # these object properties create a new DL node so that the parent one is the old dl node (wtf)
        # so this may be because TransformNode.to_c replies on DisplayListNode with hasDL == False to return null
        # from DisplayListNode.to_c, which skips writing it
        # might be worth considering rethinking the reliance on that behavior, and just only do
        # this next line or two if `type(node) != DisplayListNode`
        parent_transform_node = add_transform_node_to_parent(parent_transform_node, node)
        parent_transform_node.hasDL = False

        #! why???
        #! BECAUSE THIS GETS ASSIGNED THE MESH BIIIIIIIIITCH WTF
        node = DisplayListNode(int(obj.draw_layer_static))
        transform_node = TransformNode(node)
        
        if obj.use_render_range:
            # needs to be above the DLs in order to not render
            parent_transform_node = add_transform_node_to_parent(
                parent_transform_node, RenderRangeNode(obj.render_range[0], obj.render_range[1])
            )

        if obj.add_shadow:
            # might require being above open/close node if the current active animation was a translation
            parent_transform_node = add_transform_node_to_parent(
                parent_transform_node, ShadowNode(obj.shadow_type, obj.shadow_solidity, obj.shadow_scale)
            )

        if obj.add_func:
            geo_asm = obj.fast64.sm64.geo_asm
            add_transform_node_to_parent(parent_transform_node, FunctionNode(geo_asm.func, geo_asm.param))
    else:
        transform_node = TransformNode(node)
    
    if obj.data is None:
        fMeshes = {}
    elif geo_obj.is_instanced:
        temp_obj = get_obj_temp_mesh(obj)
        if temp_obj is None:
            raise ValueError(
                "The source of an instanced mesh could not be found. Please contact a Fast64 maintainer for support."
            )
        
        src_meshes = temp_obj.get("src_meshes", [])
        if len(src_meshes):
            fMeshes = {}
            node.dlRef = src_meshes[0]["name"]
            node.drawLayer = src_meshes[0]["layer"]

            for src_mesh in src_meshes[1:]:
                additional_node = (
                    DisplayListNode(src_mesh["layer"], src_mesh["name"])
                    if not isinstance(node, BillboardNode)
                    else BillboardNode(src_mesh["layer"], True, [0, 0, 0], src_mesh["name"])
                )
                additional_transform_node = TransformNode(additional_node)
                transform_node.children.append(additional_transform_node)
                additional_transform_node.parent = transform_node

        else:
            triConverterInfo = TriangleConverterInfo(
                temp_obj, None, process_context.fModel.f3d, process_context.base_transform_matrix, getInfoDict(temp_obj)
            )
            fMeshes = saveStaticModel(
                triConverterInfo,
                process_context.fModel,
                temp_obj,
                process_context.base_transform_matrix,
                process_context.fModel.name,
                process_context.convert_textures,
                False,
                "sm64"
            )
            if fMeshes:
                temp_obj["src_meshes"] = [
                    ({"name": fMesh.draw.name, "layer": drawLayer}) for drawLayer, fMesh in fMeshes.items()
                ]
                node.dlRef = temp_obj["src_meshes"][0]["name"]
            else:
                # TODO: Display warning to the user that there is an object that doesn't have polygons
                print("Object", obj.original_name, "does not have any polygons.")
    else:
        triConverterInfo = TriangleConverterInfo(obj, None, process_context.fModel.f3d, process_context.base_transform_matrix, getInfoDict(obj))
        fMeshes = saveStaticModel(
            triConverterInfo,
            process_context.fModel,
            obj,
            process_context.base_transform_matrix,
            process_context.fModel.name,
            process_context.convert_textures,
            False,
            "sm64"
        )
    
    if fMeshes is None or len(fMeshes) == 0:
        #! explain in comment
        #! i think its because i control that directly
        if not geo_obj.is_inline_geo:
            node.hasDL = False
        # if a mesh object DOESNT have a dl.. why render it at all? seems like it should just move on
    else:
        first_node_processed = False
        for drawLayer, fMesh in fMeshes.items():
            #! explain (ohhhh cus additional draw nodes cant use the base one)
            if not first_node_processed:
                node.DLmicrocode = fMesh.draw
                node.fMesh = fMesh
                node.drawLayer = drawLayer  # previous drawLayer assignments useless?
                first_node_processed = True
            else:
                #! explain
                dl_node = (
                    DisplayListNode(drawLayer)
                    if not isinstance(node, BillboardNode)
                    else BillboardNode(drawLayer, True, [0, 0, 0])
                )
                dl_node.DLmicrocode = fMesh.draw
                dl_node.fMesh = fMesh
                new_dl_transform_node = TransformNode(dl_node)
                transform_node.children.append(new_dl_transform_node)
                new_dl_transform_node.parent = transform_node
    
    parent_transform_node.children.append(transform_node)
    for child in geo_obj.children:
        process_geolayout(process_context, child, parent_transform_node)
    
    