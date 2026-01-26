from __future__ import annotations

import bpy
from struct import pack
from copy import copy, deepcopy

from ..utility import (
    PluginError,
    CData,
    toAlnum,
    encodeSegmentedAddr,
    writeVectorToShorts,
    convertFloatToShort,
    writeEulerVectorToShorts,
    writeFloatToShort,
    convertEulerFloatToShort,
    join_c_args,
    radians_to_s16,
    geoNodeRotateOrder,
)
from ..f3d.f3d_bleed import BleedGraphics
from ..f3d.f3d_gbi import FMaterial, FModel, GbiMacro, GfxList

from .sm64_geolayout_constants import (
    nodeGroupCmds,
    GEO_END,
    GEO_RETURN,
    GEO_NODE_OPEN,
    GEO_NODE_CLOSE,
    GEO_BRANCH,
    GEO_CALL_ASM,
    GEO_HELD_OBJECT,
    GEO_START,
    GEO_SWITCH,
    GEO_TRANSLATE_ROTATE,
    GEO_TRANSLATE,
    GEO_ROTATE,
    GEO_BILLBOARD,
    GEO_LOAD_DL,
    GEO_START_W_SHADOW,
    GEO_START_W_RENDERAREA,
    GEO_SET_RENDER_RANGE,
    GEO_LOAD_DL_W_OFFSET,
    GEO_SCALE,
    GEO_SET_RENDER_AREA,
    GEO_SET_ORTHO,
    GEO_SET_CAMERA_FRUSTRUM,
    GEO_SET_Z_BUF,
    GEO_CAMERA,
    GEO_SETUP_OBJ_RENDER,
    GEO_SET_BG,
)
from .sm64_geolayout_utility import BaseDisplayListNode
from .custom_cmd.exporting import CustomCmd
from .sm64_utility import convert_addr_to_func

drawLayerNames = {
    0: "LAYER_FORCE",
    1: "LAYER_OPAQUE",
    2: "LAYER_OPAQUE_DECAL",
    3: "LAYER_OPAQUE_INTER",
    4: "LAYER_ALPHA",
    5: "LAYER_TRANSPARENT",
    6: "LAYER_TRANSPARENT_DECAL",
    7: "LAYER_TRANSPARENT_INTER",
}


def getDrawLayerName(drawLayer):
    layer = drawLayer
    if drawLayer is not None:
        try:
            # Cast draw layer to int so it can be mapped to a name
            layer = int(drawLayer)
        except ValueError:
            pass
    if layer in drawLayerNames:
        return drawLayerNames[layer]
    else:
        return str(drawLayer)


def addFuncAddress(command, func):
    try:
        command.extend(bytes.fromhex(func))
    except ValueError:
        raise PluginError('In geolayout node, could not convert function "' + str(func) + '" to hexadecimal.')


class GeolayoutGraph:
    def __init__(self, name):
        self.startGeolayout = Geolayout(name, True)
        # dict of Object : Geolayout
        self.secondary_geolayouts: list[Geolayout] = []
        self.secondary_geolayouts_dict: dict[object, Geolayout] = {}
        # dict of Geolayout : Geolayout List (which geolayouts are called)
        self.geolayoutCalls = {}
        self.sortedList = []
        self.sortedListGenerated = False

    def checkListSorted(self):
        if not self.sortedListGenerated:
            raise PluginError("Must generate sorted geolayout list first " + "before calling this function.")

    @property
    def names(self):
        for geolayout in [self.startGeolayout] + self.secondary_geolayouts:
            yield geolayout.name

    def get_ptr_addresses(self):
        self.checkListSorted()
        addresses = []
        for geolayout in self.sortedList:
            addresses.extend(geolayout.get_ptr_addresses())
        return addresses

    def size(self):
        self.checkListSorted()
        size = 0
        for geolayout in self.sortedList:
            size += geolayout.size()

        return size

    def addGeolayout(self, obj: object | None, start_name: str):
        name, i = start_name, 0
        while True:
            if name not in self.names:
                break
            i += 1
            name = f"{start_name}_{i}"
        geolayout = Geolayout(name, False)
        self.secondary_geolayouts.append(geolayout)
        if obj is not None:
            self.secondary_geolayouts_dict[obj] = geolayout
        return geolayout

    def addJumpNode(self, parentNode, caller, callee, index=None):
        if index is None:
            parentNode.children.append(TransformNode(JumpNode(True, callee)))
        else:
            parentNode.children.insert(index, TransformNode(JumpNode(True, callee)))
        self.addGeolayoutCall(caller, callee)

    def addGeolayoutCall(self, caller, callee):
        if caller not in self.geolayoutCalls:
            self.geolayoutCalls[caller] = []
        self.geolayoutCalls[caller].append(callee)

    def sortGeolayouts(self, geolayoutList, geolayout, callOrder):
        if geolayout in self.geolayoutCalls:
            for calledGeolayout in self.geolayoutCalls[geolayout]:
                geoIndex = geolayoutList.index(geolayout)
                if calledGeolayout in geolayoutList:
                    callIndex = geolayoutList.index(calledGeolayout)
                    if callIndex < geoIndex:
                        continue
                    else:
                        raise PluginError("Circular geolayout dependency." + str(callOrder))
                else:
                    geolayoutList.insert(geolayoutList.index(geolayout), calledGeolayout)
                    callOrder = copy(callOrder)
                    callOrder.append(calledGeolayout)
                    self.sortGeolayouts(geolayoutList, calledGeolayout, callOrder)
        return geolayoutList

    def generateSortedList(self):
        self.sortedList = self.sortGeolayouts([self.startGeolayout], self.startGeolayout, [self.startGeolayout])
        self.sortedListGenerated = True

    def set_addr(self, address):
        self.checkListSorted()
        for geolayout in self.sortedList:
            geolayout.startAddress = address
            address += geolayout.size()
            print(geolayout.name + " - " + str(geolayout.startAddress))
        return address

    def to_binary(self, segmentData):
        self.checkListSorted()
        data = bytearray(0)
        for geolayout in self.sortedList:
            data += geolayout.to_binary(segmentData)
        return data

    def save_binary(self, romfile, segmentData):
        for geolayout in self.sortedList:
            geolayout.save_binary(romfile, segmentData)

    def to_c(self):
        data = CData()
        self.checkListSorted()
        data.source = '#include "src/game/envfx_snow.h"\n\n'
        for geolayout in self.sortedList:
            data.append(geolayout.to_c())
        return data

    def toTextDump(self, segmentData):
        self.checkListSorted()
        data = ""
        for geolayout in self.sortedList:
            data += geolayout.toTextDump(segmentData) + "\n"
        return data

    def convertToDynamic(self):
        self.checkListSorted()
        for geolayout in self.sortedList:
            for node in geolayout.nodes:
                node.convertToDynamic()

    def getDrawLayers(self):
        drawLayers = self.startGeolayout.getDrawLayers()
        for geolayout in self.secondary_geolayouts:
            drawLayers |= geolayout.getDrawLayers()

        return drawLayers


class Geolayout:
    def __init__(self, name, isStartGeo):
        self.nodes: list[TransformNode] = []
        self.name = toAlnum(name)
        self.startAddress = 0
        self.isStartGeo = isStartGeo

    def size(self):
        size = 4  # end command
        for node in self.nodes:
            size += node.size()
        return size

    def get_ptr_addresses(self):
        address = self.startAddress
        addresses = []
        for node in self.nodes:
            address, ptrs = node.get_ptr_addresses(address)
            addresses.extend(ptrs)
        return addresses

    def has_data(self):
        for node in self.nodes:
            if node.has_data():
                return True
        return False

    def to_binary(self, segmentData):
        endCmd = GEO_END if self.isStartGeo else GEO_RETURN
        data = bytearray(0)
        for node in self.nodes:
            data += node.to_binary(segmentData)
        data += bytearray([endCmd, 0x00, 0x00, 0x00])
        return data

    def save_binary(self, romfile, segmentData):
        romfile.seek(self.startAddress)
        romfile.write(self.to_binary(segmentData))

    def to_c(self):
        endCmd = "GEO_END" if self.isStartGeo else "GEO_RETURN"
        data = CData()
        data.header = "extern const GeoLayout " + self.name + "[];\n"
        data.source = "const GeoLayout " + self.name + "[] = {\n"
        for node in self.nodes:
            data.source += node.to_c(1)
        data.source += "\t" + endCmd + "(),\n"
        data.source += "};\n"
        return data

    def toTextDump(self, segmentData):
        endCmd = "01" if self.isStartGeo else "03"
        data = ""
        for node in self.nodes:
            data += node.toTextDump(0, segmentData)
        data += endCmd + " 00 00 00\n"
        return data

    def getDrawLayers(self):
        drawLayers = set()
        for node in self.nodes:
            drawLayers |= node.getDrawLayers()
        return drawLayers


class TransformNode:
    def __init__(self, node):
        self.node = node
        self.children: list[TransformNode] = []
        self.parent = None
        self.skinned = False
        self.skinnedWithoutDL = False
        # base behavior, can be changed with obj boolProp
        self.revert_previous_mat = False
        self.revert_after_mat = False

    def do_export_checks(self):
        if self.node is not None:
            if hasattr(self.node, "do_export_checks"):
                self.node.do_export_checks(len(self.children))

    @property
    def groups(self):
        if isinstance(self.node, tuple(nodeGroupClasses)):
            return True
        if hasattr(self.node, "group_children"):
            return self.node.group_children
        return False

    def convertToDynamic(self):
        if self.node.hasDL:
            funcNode = FunctionNode(self.node.DLmicrocode.name, self.node.drawLayer)

            if isinstance(self.node, DisplayListNode):
                self.node = funcNode
            else:
                self.node.hasDL = False
                transformNode = TransformNode(funcNode)
                self.children.insert(0, transformNode)

        for child in self.children:
            child.convertToDynamic()

    def get_ptr_addresses(self, address):
        addresses = []
        if self.node is not None:
            if type(self.node) in DLNodes:
                for offset in self.node.get_ptr_offsets():
                    addresses.append(address + offset)
            else:
                addresses = []
            address += self.node.size()
        if len(self.children) > 0:
            address += 4
            for node in self.children:
                address, ptrs = node.get_ptr_addresses(address)
                addresses.extend(ptrs)
            address += 4
        return address, addresses

    def has_data(self):
        if self.node is not None:
            if getattr(self.node, "hasDL", False):
                return True
            if type(self.node) in (JumpNode, SwitchNode, FunctionNode, ShadowNode, CustomCmd):
                return True
        for child in self.children:
            if child.has_data():
                return True
        return False

    def size(self):
        size = self.node.size() if self.node is not None else 0
        if len(self.children) > 0 and self.groups:
            size += 8  # node open/close
        for child in self.children:
            size += child.size()

        return size

    # Function commands usually effect the following command, so it is similar
    # to a parent child relationship.
    def to_binary(self, segmentData):
        self.do_export_checks()
        if self.node is not None:
            data = self.node.to_binary(segmentData)
        else:
            data = bytearray(0)
        if len(self.children) > 0:
            if type(self.node) is FunctionNode:
                raise PluginError("An FunctionNode cannot have children.")

            if self.groups:
                data.extend(bytearray([GEO_NODE_OPEN, 0x00, 0x00, 0x00]))
            for child in self.children:
                data.extend(child.to_binary(segmentData))
            if self.groups:
                data.extend(bytearray([GEO_NODE_CLOSE, 0x00, 0x00, 0x00]))
        elif type(self.node) is SwitchNode:
            raise PluginError("A switch bone must have at least one child bone.")
        return data

    def to_c(self, depth):
        self.do_export_checks()
        if self.node is not None:
            nodeC = self.node.to_c(depth)
            if nodeC is not None:  # Should only be the case for DisplayListNode with no DL
                data = ("\t" * depth) + f"{nodeC},\n"
            else:
                data = ""
        else:
            data = ""
        if len(self.children) > 0:
            if self.groups:
                data += ("\t" * depth) + "GEO_OPEN_NODE(),\n"
            for child in self.children:
                data += child.to_c(depth + (1 if self.groups else 0))
            if self.groups:
                data += ("\t" * depth) + "GEO_CLOSE_NODE(),\n"
        elif type(self.node) is SwitchNode:
            raise PluginError("A switch bone must have at least one child bone.")
        return data

    def toTextDump(self, nodeLevel, segmentData):
        self.do_export_checks()
        data = ""
        if self.node is not None:
            command = self.node.to_binary(segmentData)
        else:
            command = bytearray(0)

        data += "\t" * nodeLevel
        for byteVal in command:
            data += format(byteVal, "02X") + " "
        data += "\n"

        if len(self.children) > 0:
            if self.groups:
                data += "\t" * nodeLevel + "04 00 00 00\n"
            for child in self.children:
                data += child.toTextDump(nodeLevel + (1 if self.groups else 0), segmentData)
            if self.groups:
                data += "\t" * nodeLevel + "05 00 00 00\n"
        elif type(self.node) is SwitchNode:
            raise PluginError("A switch bone must have at least one child bone.")
        return data

    def getDrawLayers(self):
        if self.node is not None and self.node.hasDL:
            drawLayers = set([self.node.drawLayer])
        else:
            drawLayers = set()
        for child in self.children:
            if hasattr(child, "getDrawLayers"):  # not every child will have draw layers (e.g. GEO_ASM)
                drawLayers |= child.getDrawLayers()
        return drawLayers


class SwitchOverrideNode:
    def __init__(self, material, specificMat, drawLayer, overrideType, texDimensions):
        self.material = material
        self.specificMat = specificMat
        self.drawLayer = drawLayer
        self.overrideType = overrideType
        self.texDimensions = texDimensions  # None implies a draw layer override
        self.hasDL = False


class JumpNode:
    def __init__(self, storeReturn, geolayout: Geolayout, geoRef: str = None):
        self.geolayout = geolayout
        self.storeReturn = storeReturn
        self.hasDL = False
        self.geoRef = geoRef

    def size(self):
        return 8

    def get_ptr_offsets(self):
        return [4]

    def to_binary(self, segmentData):
        if segmentData is not None:
            address = self.geoRef or self.geolayout.startAddress
            startAddress = encodeSegmentedAddr(address, segmentData)
        else:
            startAddress = bytearray([0x00] * 4)
        command = bytearray([GEO_BRANCH, 0x01 if self.storeReturn else 0x00, 0x00, 0x00])
        command.extend(startAddress)
        return command

    def to_c(self, _depth=0):
        geo_name = self.geoRef or self.geolayout.name
        return "GEO_BRANCH(" + ("1, " if self.storeReturn else "0, ") + geo_name + ")"


LastMaterials = dict[int, tuple[FMaterial | None, list[tuple[GfxList, dict[type, GbiMacro]]]]]


class GeoLayoutBleed(BleedGraphics):
    def bleed_geo_layout_graph(self, fModel: FModel, geo_layout_graph: GeolayoutGraph, use_rooms: bool = False):
        # last used material, last used cmd list and resets per layer
        last_materials = {}

        def copy_last(last_materials: LastMaterials) -> LastMaterials:
            return {dl: [lm, [(c, deepcopy(r)) for c, r in lcr]] for dl, (lm, lcr) in last_materials.items()}

        def reset_layer(last_materials: LastMaterials, draw_layer: int) -> LastMaterials:
            _, cmds_resets = last_materials.get(draw_layer, (None, []))
            for i, (cmd_list, reset_cmd_dict) in enumerate(copy(cmds_resets)):
                # only discard reset if the reset was actually applied
                if self.add_reset_cmds(
                    cmd_list, reset_cmd_dict, fModel.matWriteMethod, fModel.getRenderMode(draw_layer)
                ):
                    cmds_resets[i] = None
            while None in cmds_resets:
                cmds_resets.remove(None)
            if not cmds_resets:
                last_materials.pop(draw_layer, 0)
            return last_materials

        def reset_all_layers(last_materials: LastMaterials) -> LastMaterials:
            for draw_layer in copy(list(last_materials.keys())):
                last_materials = reset_layer(last_materials, draw_layer)
            return last_materials

        def walk(node, last_materials: LastMaterials) -> LastMaterials:
            last_materials = copy_last(last_materials)
            base_node = node.node
            if type(base_node) == JumpNode:
                if base_node.geolayout:
                    for node in base_node.geolayout.nodes:
                        last_materials = walk(node, last_materials)

            fMesh = getattr(base_node, "fMesh", None)
            last_mat, last_cmds_resets = None, []

            if node.revert_previous_mat:
                if fMesh is not None:
                    # add reset commands to previous cmd lists, reset last mat and reset dict
                    last_materials = reset_layer(last_materials, base_node.drawLayer)
                else:
                    last_materials = reset_all_layers(last_materials)

            if fMesh is not None:
                last_mat, last_cmds_resets = last_materials.get(base_node.drawLayer, (None, []))

                base_node: BaseDisplayListNode
                cmd_list = base_node.DLmicrocode
                default_render_mode = fModel.getRenderMode(base_node.drawLayer)

                reset_cmd_dict = {typ: cmd for _, reset_cmds in last_cmds_resets for typ, cmd in reset_cmds.items()}
                last_mat = self.bleed_fmesh(
                    last_mat,
                    reset_cmd_dict,
                    cmd_list,
                    fModel.getAllMaterials().items(),
                    fModel.matWriteMethod,
                    default_render_mode,
                )
                last_materials[base_node.drawLayer] = [last_mat, [(cmd_list, reset_cmd_dict)]]
                # if the mesh has culling, we must revert to avoid bleed issues
                if fMesh.cullVertexList or node.revert_after_mat:
                    last_materials = reset_layer(last_materials, base_node.drawLayer)
            elif node.revert_after_mat:  # if no mesh but still forced revert, revert all
                last_materials = reset_all_layers(last_materials)

            cur_last_materials = copy_last(last_materials)
            set_layers = set()
            is_switch = type(base_node) in {SwitchNode}
            for child in node.children:
                if is_switch:  # parent node is switch or function
                    new_materials = walk(child, cur_last_materials)  # last material info from current switch option
                    # add switch option reverts, to either revert at the end or in the option itself
                    for draw_layer, (last_mat, cmds_resets) in new_materials.items():
                        # resets were added or removed in the option, therefor the option can reset that layer
                        if cmds_resets != cur_last_materials.get(draw_layer, (None, []))[1]:
                            set_layers.add(draw_layer)
                        last_materials.setdefault(draw_layer, [last_mat, []])[1].extend(cmds_resets)
                        last_materials[draw_layer][0] = None  # reset last material
                else:
                    last_materials = walk(child, last_materials)
            if is_switch:
                # if a switch took up the responsability of its reset, remove any previous reset of that layer
                for draw_layer in set_layers:
                    last_mat, cmds_resets = cur_last_materials.get(draw_layer, (None, []))
                    for i in range(len(cmds_resets)):
                        last_materials[draw_layer][1][i] = None
                    while None in last_materials[draw_layer][1]:
                        last_materials[draw_layer][1].remove(None)
            return last_materials

        for node in geo_layout_graph.startGeolayout.nodes:
            last_materials = walk(node, last_materials)
        reset_all_layers(last_materials)
        self.clear_gfx_lists(fModel)


# We add Function commands to nonDeformTransformData because any skinned
# 0x15 commands should go before them, as they are usually preceding
# an empty transform command (of which they modify?)
class FunctionNode:
    def __init__(self, geo_func, func_param):
        self.geo_func = geo_func
        self.func_param = func_param
        self.hasDL = False

    def do_export_checks(self, children_count: int):
        if children_count > 0:
            raise PluginError(
                "Function bones cannot have children. They instead affect the next sibling bone in alphabetical order."
            )

    def size(self):
        return 8

    def to_binary(self, segmentData):
        command = bytearray([GEO_CALL_ASM, 0x00])
        func_param = int(self.func_param)
        command.extend(func_param.to_bytes(2, "big", signed=True))
        addFuncAddress(command, self.geo_func)
        return command

    def to_c(self, _depth=0):
        return "GEO_ASM(" + str(self.func_param) + ", " + convert_addr_to_func(self.geo_func) + ")"


class HeldObjectNode:
    def __init__(self, geo_func, translate):
        self.geo_func = geo_func
        self.translate = translate
        self.hasDL = False

    def size(self):
        return 12

    def to_binary(self, segmentData):
        command = bytearray([GEO_HELD_OBJECT, 0x00])
        command.extend(bytearray([0x00] * 6))
        writeVectorToShorts(command, 2, self.translate)
        addFuncAddress(command, self.geo_func)
        return command

    def to_c(self, _depth=0):
        return (
            "GEO_HELD_OBJECT(0, "
            + str(convertFloatToShort(self.translate[0]))
            + ", "
            + str(convertFloatToShort(self.translate[1]))
            + ", "
            + str(convertFloatToShort(self.translate[2]))
            + ", "
            + convert_addr_to_func(self.geo_func)
            + ")"
        )


class StartNode:
    def __init__(self):
        self.hasDL = False

    def size(self):
        return 4

    def to_binary(self, segmentData):
        command = bytearray([GEO_START, 0x00, 0x00, 0x00])
        return command

    def to_c(self, _depth=0):
        return "GEO_NODE_START()"


class EndNode:
    def __init__(self):
        self.hasDL = False

    def size(self):
        return 4

    def to_binary(self, segmentData):
        command = bytearray([GEO_END, 0x00, 0x00, 0x00])
        return command

    def to_c(self, _depth=0):
        return "GEO_END()"


# Geolayout node hierarchy is first generated without material/draw layer
# override options, but with material override DL's being generated.
# Afterward, for each switch node the node hierarchy is duplicated and
# the correct diplsay lists are added.
class SwitchNode:
    def __init__(self, geo_func, func_param, name):
        self.switchFunc = geo_func
        self.defaultCase = func_param
        self.hasDL = False
        self.name = name

    def size(self):
        return 8

    def to_binary(self, segmentData):
        command = bytearray([GEO_SWITCH, 0x00])
        defaultCase = int(self.defaultCase)
        command.extend(defaultCase.to_bytes(2, "big", signed=True))
        addFuncAddress(command, self.switchFunc)
        return command

    def to_c(self, _depth=0):
        return "GEO_SWITCH_CASE(" + str(self.defaultCase) + ", " + convert_addr_to_func(self.switchFunc) + ")"


class TranslateRotateNode(BaseDisplayListNode):
    def __init__(self, drawLayer, fieldLayout, hasDL, translate, rotate, dlRef: str = None):
        self.drawLayer = drawLayer
        self.fieldLayout = fieldLayout
        self.hasDL = hasDL

        self.translate = translate
        self.rotate = rotate

        self.fMesh = None

        self.dlRef = dlRef
        # exists to get the override DL from an fMesh

    def get_ptr_offsets(self):
        if self.hasDL:
            if self.fieldLayout == 0:
                return [16]
            elif self.fieldLayout == 1:
                return [8]
            elif self.fieldLayout == 2:
                return [8]
            elif self.fieldLayout == 3:
                return [4]
        else:
            return []

    def size(self):
        if self.fieldLayout == 0:
            size = 16
        elif self.fieldLayout == 1:
            size = 8
        elif self.fieldLayout == 2:
            size = 8
        elif self.fieldLayout == 3:
            size = 4

        if self.hasDL:
            size += 4
        return size

    def to_binary(self, segmentData):
        params = ((1 if self.hasDL else 0) << 7) & (self.fieldLayout << 4) | int(self.drawLayer)

        start_address = self.get_dl_address()

        command = bytearray([GEO_TRANSLATE_ROTATE, params])
        if self.fieldLayout == 0:
            command.extend(bytearray([0x00] * 14))
            writeVectorToShorts(command, 4, self.translate)
            writeEulerVectorToShorts(command, 10, self.rotate.to_euler(geoNodeRotateOrder))
        elif self.fieldLayout == 1:
            command.extend(bytearray([0x00] * 6))
            writeVectorToShorts(command, 2, self.translate)
        elif self.fieldLayout == 2:
            command.extend(bytearray([0x00] * 6))
            writeEulerVectorToShorts(command, 2, self.rotate.to_euler(geoNodeRotateOrder))
        elif self.fieldLayout == 3:
            command.extend(bytearray([0x00] * 2))
            writeFloatToShort(command, 2, self.rotate.to_euler(geoNodeRotateOrder).y)
        if start_address:
            if segmentData is not None:
                command.extend(encodeSegmentedAddr(start_address, segmentData))
            else:
                command.extend(bytearray([0x00] * 4))
        return command

    def to_c(self, _depth=0):
        if self.fieldLayout == 0:
            return self.c_func_macro(
                "GEO_TRANSLATE_ROTATE",
                getDrawLayerName(self.drawLayer),
                str(convertFloatToShort(self.translate[0])),
                str(convertFloatToShort(self.translate[1])),
                str(convertFloatToShort(self.translate[2])),
                str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[0])),
                str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[1])),
                str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[2])),
            )
        elif self.fieldLayout == 1:
            return self.c_func_macro(
                "GEO_TRANSLATE",
                getDrawLayerName(self.drawLayer),
                str(convertFloatToShort(self.translate[0])),
                str(convertFloatToShort(self.translate[1])),
                str(convertFloatToShort(self.translate[2])),
            )
        elif self.fieldLayout == 2:
            return self.c_func_macro(
                "GEO_ROTATE",
                getDrawLayerName(self.drawLayer),
                str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[0])),
                str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[1])),
                str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[2])),
            )
        elif self.fieldLayout == 3:
            return self.c_func_macro(
                "GEO_ROTATE_Y",
                getDrawLayerName(self.drawLayer),
                str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[1])),
            )


class TranslateNode(BaseDisplayListNode):
    def __init__(self, drawLayer, useDeform, translate, dlRef: str = None):
        self.drawLayer = drawLayer
        self.hasDL = useDeform
        self.translate = translate
        self.fMesh = None

        self.dlRef = dlRef
        # exists to get the override DL from an fMesh

    def get_ptr_offsets(self):
        return [8] if self.hasDL else []

    def size(self):
        return 12 if self.hasDL else 8

    def to_binary(self, segmentData):
        params = ((1 if self.hasDL else 0) << 7) | int(self.drawLayer)
        command = bytearray([GEO_TRANSLATE, params])
        command.extend(bytearray([0x00] * 6))
        writeVectorToShorts(command, 2, self.translate)

        if self.hasDL:
            start_address = self.get_dl_address()
            if segmentData is not None:
                command.extend(encodeSegmentedAddr(start_address, segmentData))
            else:
                command.extend(bytearray([0x00] * 4))
        return command

    def to_c(self, _depth=0):
        return self.c_func_macro(
            "GEO_TRANSLATE_NODE",
            getDrawLayerName(self.drawLayer),
            str(convertFloatToShort(self.translate[0])),
            str(convertFloatToShort(self.translate[1])),
            str(convertFloatToShort(self.translate[2])),
        )


class RotateNode(BaseDisplayListNode):
    def __init__(self, drawLayer, hasDL, rotate, dlRef: str = None):
        # In the case for automatically inserting rotate nodes between
        # 0x13 bones.

        self.drawLayer = drawLayer
        self.hasDL = hasDL
        self.rotate = rotate
        self.fMesh = None

        self.dlRef = dlRef
        # exists to get the override DL from an fMesh

    def get_ptr_offsets(self):
        return [8] if self.hasDL else []

    def size(self):
        return 12 if self.hasDL else 8

    def to_binary(self, segmentData):
        params = ((1 if self.hasDL else 0) << 7) | int(self.drawLayer)
        command = bytearray([GEO_ROTATE, params])
        command.extend(bytearray([0x00] * 6))
        writeEulerVectorToShorts(command, 2, self.rotate.to_euler(geoNodeRotateOrder))
        if self.hasDL:
            start_address = self.get_dl_address()
            if segmentData is not None:
                command.extend(encodeSegmentedAddr(start_address, segmentData))
            else:
                command.extend(bytearray([0x00] * 4))
        return command

    def to_c(self, _depth=0):
        return self.c_func_macro(
            "GEO_ROTATION_NODE",
            getDrawLayerName(self.drawLayer),
            str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[0])),
            str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[1])),
            str(convertEulerFloatToShort(self.rotate.to_euler(geoNodeRotateOrder)[2])),
        )


class BillboardNode(BaseDisplayListNode):
    dl_ext = "AND_DL"

    def __init__(self, drawLayer, hasDL, translate, dlRef: str = None):
        self.drawLayer = drawLayer
        self.hasDL = hasDL
        self.translate = translate
        self.fMesh = None

        self.dlRef = dlRef
        # exists to get the override DL from an fMesh

    def get_ptr_offsets(self):
        return [8] if self.hasDL else []

    def size(self):
        return 12 if self.hasDL else 8

    def to_binary(self, segmentData):
        params = ((1 if self.hasDL else 0) << 7) | int(self.drawLayer)
        command = bytearray([GEO_BILLBOARD, params])
        command.extend(bytearray([0x00] * 6))
        writeVectorToShorts(command, 2, self.translate)
        if self.hasDL:
            start_address = self.get_dl_address()
            if segmentData is not None:
                command.extend(encodeSegmentedAddr(start_address, segmentData))
            else:
                command.extend(bytearray([0x00] * 4))
        return command

    def to_c(self, _depth=0):
        return self.c_func_macro(
            "GEO_BILLBOARD_WITH_PARAMS",
            getDrawLayerName(self.drawLayer),
            str(convertFloatToShort(self.translate[0])),
            str(convertFloatToShort(self.translate[1])),
            str(convertFloatToShort(self.translate[2])),
        )


class DisplayListNode(BaseDisplayListNode):
    def __init__(self, drawLayer, dlRef: str = None):
        self.drawLayer = drawLayer
        self.hasDL = True
        self.fMesh = None

        self.dlRef = dlRef
        # exists to get the override DL from an fMesh

    def get_ptr_offsets(self):
        return [4]

    def size(self):
        return 8

    def to_binary(self, segmentData):
        command = bytearray([GEO_LOAD_DL, int(self.drawLayer), 0x00, 0x00])
        start_address = self.get_dl_address()
        if start_address and segmentData is not None:
            command.extend(encodeSegmentedAddr(start_address, segmentData))
        else:
            command.extend(bytearray([0x00] * 4))
        return command

    def to_c(self, _depth=0):
        if not self.hasDL:
            return None
        args = [getDrawLayerName(self.drawLayer), self.get_dl_name()]
        return f"GEO_DISPLAY_LIST({join_c_args(args)})"


class ShadowNode:
    def __init__(self, shadow_type, shadow_solidity, shadow_scale):
        self.shadowType = int(shadow_type)
        self.shadowSolidity = int(round(shadow_solidity * 0xFF))
        self.shadowScale = shadow_scale
        self.hasDL = False

    def size(self):
        return 8

    def to_binary(self, segmentData):
        command = bytearray([GEO_START_W_SHADOW, 0x00])
        command.extend(self.shadowType.to_bytes(2, "big"))
        command.extend(self.shadowSolidity.to_bytes(2, "big"))
        command.extend(self.shadowScale.to_bytes(2, "big"))
        return command

    def to_c(self, _depth=0):
        return (
            "GEO_SHADOW(" + str(self.shadowType) + ", " + str(self.shadowSolidity) + ", " + str(self.shadowScale) + ")"
        )


class ScaleNode(BaseDisplayListNode):
    def __init__(self, drawLayer, geo_scale, use_deform, dlRef: str = None):
        self.drawLayer = drawLayer
        self.scaleValue = geo_scale
        self.hasDL = use_deform
        self.fMesh = None

        self.dlRef = dlRef
        # exists to get the override DL from an fMesh

    def get_ptr_offsets(self):
        return [8] if self.hasDL else []

    def size(self):
        return 12 if self.hasDL else 8

    def to_binary(self, segmentData):
        params = ((1 if self.hasDL else 0) << 7) | int(self.drawLayer)
        command = bytearray([GEO_SCALE, params, 0x00, 0x00])
        command.extend(int(self.scaleValue * 0x10000).to_bytes(4, "big"))
        if self.hasDL:
            if segmentData is not None:
                command.extend(encodeSegmentedAddr(self.get_dl_address(), segmentData))
            else:
                command.extend(bytearray([0x00] * 4))
        return command

    def to_c(self, _depth=0):
        return self.c_func_macro(
            "GEO_SCALE", getDrawLayerName(self.drawLayer), str(int(round(self.scaleValue * 0x10000)))
        )


class StartRenderAreaNode:
    def __init__(self, cullingRadius):
        self.cullingRadius = cullingRadius
        self.hasDL = False

    def size(self):
        return 4

    def to_binary(self, segmentData):
        command = bytearray([GEO_START_W_RENDERAREA, 0x00])
        command.extend(convertFloatToShort(self.cullingRadius).to_bytes(2, "big"))
        return command

    def to_c(self, _depth=0):
        cullingRadius = convertFloatToShort(self.cullingRadius)
        # if abs(cullingRadius) > 2**15 - 1:
        # 	raise PluginError("A render area node has a culling radius that does not fit an s16.\n Radius is " +\
        # 		str(cullingRadius) + ' when converted to SM64 units.')
        return "GEO_CULLING_RADIUS(" + str(convertFloatToShort(self.cullingRadius)) + ")"


class RenderRangeNode:
    def __init__(self, minDist, maxDist):
        self.minDist = minDist
        self.maxDist = maxDist
        self.hasDL = False

    def size(self):
        return 8

    def to_binary(self, segmentData):
        command = bytearray([GEO_SET_RENDER_RANGE, 0x00, 0x00, 0x00])
        command.extend(convertFloatToShort(self.minDist).to_bytes(2, "big"))
        command.extend(convertFloatToShort(self.maxDist).to_bytes(2, "big"))
        return command

    def to_c(self, _depth=0):
        minDist = convertFloatToShort(self.minDist)
        maxDist = convertFloatToShort(self.maxDist)
        # if (abs(minDist) > 2**15 - 1) or (abs(maxDist) > 2**15 - 1):
        # 	raise PluginError("A render range (LOD) node has a range that does not fit an s16.\n Range is " +\
        # 		str(minDist) + ', ' + str(maxDist) + ' when converted to SM64 units.')
        return "GEO_RENDER_RANGE(" + str(minDist) + ", " + str(maxDist) + ")"


class DisplayListWithOffsetNode(BaseDisplayListNode):
    def __init__(self, drawLayer, use_deform, translate, dlRef: str = None):
        self.drawLayer = drawLayer
        self.hasDL = use_deform
        self.translate = translate
        self.fMesh = None

        self.dlRef = dlRef
        # exists to get the override DL from an fMesh

    def size(self):
        return 12

    def get_ptr_offsets(self):
        return [8] if self.hasDL else []

    def to_binary(self, segmentData):
        command = bytearray([GEO_LOAD_DL_W_OFFSET, int(self.drawLayer)])
        command.extend(bytearray([0x00] * 6))
        writeVectorToShorts(command, 2, self.translate)
        start_address = self.get_dl_address()
        if start_address is not None and segmentData is not None:
            command.extend(encodeSegmentedAddr(start_address, segmentData))
        else:
            command.extend(bytearray([0x00] * 4))
        return command

    def to_c(self, _depth=0):
        args = [
            getDrawLayerName(self.drawLayer),
            str(convertFloatToShort(self.translate[0])),
            str(convertFloatToShort(self.translate[1])),
            str(convertFloatToShort(self.translate[2])),
            self.get_dl_name(),  # This node requires 'NULL' if there is no DL
        ]
        return f"GEO_ANIMATED_PART({join_c_args(args)})"


class ScreenAreaNode:
    def __init__(self, useDefaults, entryMinus2Count, position, dimensions):
        self.useDefaults = useDefaults
        self.entryMinus2Count = entryMinus2Count
        self.position = position
        self.dimensions = dimensions
        self.hasDL = False

    def size(self):
        return 12

    def to_binary(self, segmentData):
        position = [160, 120] if self.useDefaults else self.position
        dimensions = [160, 120] if self.useDefaults else self.dimensions
        entryMinus2Count = 0xA if self.useDefaults else self.entryMinus2Count
        command = bytearray([GEO_SET_RENDER_AREA, 0x00])
        command.extend(entryMinus2Count.to_bytes(2, "big", signed=False))
        command.extend(position[0].to_bytes(2, "big", signed=True))
        command.extend(position[1].to_bytes(2, "big", signed=True))
        command.extend(dimensions[0].to_bytes(2, "big", signed=True))
        command.extend(dimensions[1].to_bytes(2, "big", signed=True))
        return command

    def to_c(self, _depth=0):
        if self.useDefaults:
            return (
                "GEO_NODE_SCREEN_AREA(10, " + "SCREEN_WIDTH/2, SCREEN_HEIGHT/2, " + "SCREEN_WIDTH/2, SCREEN_HEIGHT/2)"
            )
        else:
            return (
                "GEO_NODE_SCREEN_AREA("
                + str(self.entryMinus2Count)
                + ", "
                + str(self.position[0])
                + ", "
                + str(self.position[1])
                + ", "
                + str(self.dimensions[0])
                + ", "
                + str(self.dimensions[1])
                + ")"
            )


class OrthoNode:
    def __init__(self, scale):
        self.scale = scale
        self.hasDL = False

    def size(self):
        return 4

    def to_binary(self, segmentData):
        command = bytearray([GEO_SET_ORTHO, 0x00])
        # FIX: This should be f32.
        command.extend(bytearray(pack(">f", self.scale)))
        return command

    def to_c(self, _depth=0):
        return "GEO_NODE_ORTHO(" + format(self.scale, ".4f") + ")"


class FrustumNode:
    def __init__(self, fov, near, far):
        self.fov = fov
        self.near = int(round(near))
        self.far = int(round(far))
        self.useFunc = True  # Always use function?
        self.hasDL = False

    def size(self):
        return 12 if self.useFunc else 8

    def to_binary(self, segmentData):
        command = bytearray([GEO_SET_CAMERA_FRUSTRUM, 0x01 if self.useFunc else 0x00])
        command.extend(bytearray(pack(">f", self.fov)))
        command.extend(self.near.to_bytes(2, "big", signed=True))  # Conversion?
        command.extend(self.far.to_bytes(2, "big", signed=True))  # Conversion?

        if self.useFunc:
            command.extend(bytes.fromhex("8029AA3C"))
        return command

    def to_c(self, _depth=0):
        if not self.useFunc:
            return "GEO_CAMERA_FRUSTUM(" + format(self.fov, ".4f") + ", " + str(self.near) + ", " + str(self.far) + ")"
        else:
            return (
                "GEO_CAMERA_FRUSTUM_WITH_FUNC("
                + format(self.fov, ".4f")
                + ", "
                + str(self.near)
                + ", "
                + str(self.far)
                + ", geo_camera_fov)"
            )


class ZBufferNode:
    def __init__(self, enable):
        self.enable = enable
        self.hasDL = False

    def size(self):
        return 4

    def to_binary(self, segmentData):
        command = bytearray([GEO_SET_Z_BUF, 0x01 if self.enable else 0x00, 0x00, 0x00])
        return command

    def to_c(self, _depth=0):
        return "GEO_ZBUFFER(" + ("1" if self.enable else "0") + ")"


class CameraNode:
    def __init__(self, camType, position, lookAt):
        self.camType = camType
        self.position = [int(round(value * bpy.context.scene.fast64.sm64.blender_to_sm64_scale)) for value in position]
        self.lookAt = [int(round(value * bpy.context.scene.fast64.sm64.blender_to_sm64_scale)) for value in lookAt]
        self.geo_func = "80287D30"
        self.hasDL = False

    def size(self):
        return 20

    def to_binary(self, segmentData):
        command = bytearray([GEO_CAMERA, 0x00])
        command.extend(self.camType.to_bytes(2, "big", signed=True))
        command.extend(self.position[0].to_bytes(2, "big", signed=True))
        command.extend(self.position[1].to_bytes(2, "big", signed=True))
        command.extend(self.position[2].to_bytes(2, "big", signed=True))
        command.extend(self.lookAt[0].to_bytes(2, "big", signed=True))
        command.extend(self.lookAt[1].to_bytes(2, "big", signed=True))
        command.extend(self.lookAt[2].to_bytes(2, "big", signed=True))
        addFuncAddress(command, self.geo_func)
        return command

    def to_c(self, _depth=0):
        return (
            "GEO_CAMERA("
            + str(self.camType)
            + ", "
            + str(self.position[0])
            + ", "
            + str(self.position[1])
            + ", "
            + str(self.position[2])
            + ", "
            + str(self.lookAt[0])
            + ", "
            + str(self.lookAt[1])
            + ", "
            + str(self.lookAt[2])
            + ", "
            + convert_addr_to_func(self.geo_func)
            + ")"
        )


class RenderObjNode:
    def __init__(self):
        self.hasDL = False
        pass

    def size(self):
        return 4

    def to_binary(self, segmentData):
        command = bytearray([GEO_SETUP_OBJ_RENDER, 0x00, 0x00, 0x00])
        return command

    def to_c(self, _depth=0):
        return "GEO_RENDER_OBJ()"


class BackgroundNode:
    def __init__(self, isColor, backgroundValue):
        self.isColor = isColor
        self.backgroundValue = backgroundValue
        self.geo_func = "802763D4"
        self.hasDL = False

    def size(self):
        return 8

    def to_binary(self, segmentData):
        command = bytearray([GEO_SET_BG, 0x00])
        command.extend(self.backgroundValue.to_bytes(2, "big", signed=False))
        if self.isColor:
            command.extend(bytes.fromhex("00000000"))
        else:
            addFuncAddress(command, self.geo_func)
        return command

    def to_c(self, _depth=0):
        if self.isColor:
            return "GEO_BACKGROUND_COLOR(0x" + format(self.backgroundValue, "04x").upper() + ")"
        else:
            return "GEO_BACKGROUND(" + str(self.backgroundValue) + ", " + convert_addr_to_func(self.geo_func) + ")"


nodeGroupClasses = [
    StartNode,
    SwitchNode,
    TranslateRotateNode,
    TranslateNode,
    RotateNode,
    DisplayListWithOffsetNode,
    BillboardNode,
    ShadowNode,
    ScaleNode,
    StartRenderAreaNode,
    ScreenAreaNode,
    OrthoNode,
    FrustumNode,
    ZBufferNode,
    CameraNode,
    RenderRangeNode,
]

DLNodes = [
    JumpNode,
    TranslateRotateNode,
    TranslateNode,
    RotateNode,
    ScaleNode,
    DisplayListNode,
    DisplayListWithOffsetNode,
]
