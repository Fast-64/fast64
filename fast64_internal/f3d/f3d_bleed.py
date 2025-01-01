from __future__ import annotations

import copy
import bpy

from dataclasses import dataclass, field

from ..utility import create_or_get_world
from .f3d_gbi import (
    GfxTag,
    GfxListTag,
    SPMatrix,
    SPVertex,
    SPViewport,
    SPDisplayList,
    SPBranchList,
    SP1Triangle,
    SPLine3D,
    SPLineW3D,
    SP2Triangles,
    SPCullDisplayList,
    SPSegment,
    SPBranchLessZraw,
    SPModifyVertex,
    SPEndDisplayList,
    SPLoadGeometryMode,
    SPSetGeometryMode,
    SPClearGeometryMode,
    SPSetOtherMode,
    DPLoadBlock,
    DPLoadTLUTCmd,
    DPFullSync,
    DPSetRenderMode,
    DPSetTextureImage,
    DPPipeSync,
    DPLoadSync,
    DPTileSync,
    DPSetTile,
    DPLoadTile,
    FModel,
    FMesh,
    FMaterial,
    FAreaData,
    F3D,
    GfxList,
    FTriGroup,
    GbiMacro,
)


class BleedGraphics:
    # bleed_state "enums"
    bleed_start = 1
    bleed_in_progress = 2
    # tells bleed logic to check against itself instead of last list
    bleed_self_conflict = 3

    def __init__(self):
        self.bled_gfx_lists = dict()
        # build world default cmds to compare against, f3d types needed for reset cmd building
        self.is_f3d_old = bpy.context.scene.f3d_type == "F3D"
        self.is_f3dex2 = "F3DEX2" in bpy.context.scene.f3d_type
        self.build_default_geo()
        self.build_default_othermodes()

    def build_default_geo(self):
        defaults = create_or_get_world(bpy.context.scene).rdp_defaults

        setGeo = SPSetGeometryMode([])
        clearGeo = SPClearGeometryMode([])

        def place_in_flaglist(flag: bool, enum: str, set_list: SPSetGeometryMode, clear_list: SPClearGeometryMode):
            if flag:
                set_list.flagList.append(enum)
            else:
                clear_list.flagList.append(enum)

        place_in_flaglist(defaults.g_zbuffer, "G_ZBUFFER", setGeo, clearGeo)
        place_in_flaglist(defaults.g_shade, "G_SHADE", setGeo, clearGeo)
        place_in_flaglist(defaults.g_cull_front, "G_CULL_FRONT", setGeo, clearGeo)
        place_in_flaglist(defaults.g_cull_back, "G_CULL_BACK", setGeo, clearGeo)
        place_in_flaglist(defaults.g_fog, "G_FOG", setGeo, clearGeo)
        place_in_flaglist(defaults.g_lighting, "G_LIGHTING", setGeo, clearGeo)
        place_in_flaglist(defaults.g_tex_gen, "G_TEXTURE_GEN", setGeo, clearGeo)
        place_in_flaglist(defaults.g_tex_gen_linear, "G_TEXTURE_GEN_LINEAR", setGeo, clearGeo)
        place_in_flaglist(defaults.g_shade_smooth, "G_SHADING_SMOOTH", setGeo, clearGeo)
        if bpy.context.scene.f3d_type == "F3DEX_GBI_2" or bpy.context.scene.f3d_type == "F3DEX_GBI":
            place_in_flaglist(defaults.g_clipping, "G_CLIPPING", setGeo, clearGeo)

        self.default_load_geo = SPLoadGeometryMode(setGeo.flagList)
        self.default_set_geo = setGeo
        self.default_clear_geo = clearGeo

    def build_default_othermodes(self):
        defaults = create_or_get_world(bpy.context.scene).rdp_defaults

        othermode_H = SPSetOtherMode("G_SETOTHERMODE_H", 4, 20 - self.is_f3d_old, [])
        # if the render mode is set, it will be consider non-default a priori
        othermode_L = SPSetOtherMode("G_SETOTHERMODE_L", 0, 3 - self.is_f3d_old, [])

        othermode_L.flagList.append(defaults.g_mdsft_alpha_compare)
        othermode_L.flagList.append(defaults.g_mdsft_zsrcsel)

        othermode_H.flagList.append(defaults.g_mdsft_rgb_dither)
        othermode_H.flagList.append(defaults.g_mdsft_alpha_dither)
        othermode_H.flagList.append(defaults.g_mdsft_combkey)
        othermode_H.flagList.append(defaults.g_mdsft_textconv)
        othermode_H.flagList.append(defaults.g_mdsft_text_filt)
        othermode_H.flagList.append(defaults.g_mdsft_textlut)
        othermode_H.flagList.append(defaults.g_mdsft_textlod)
        othermode_H.flagList.append(defaults.g_mdsft_textdetail)
        othermode_H.flagList.append(defaults.g_mdsft_textpersp)
        othermode_H.flagList.append(defaults.g_mdsft_cycletype)
        othermode_H.flagList.append(defaults.g_mdsft_pipeline)

        self.default_othermode_L = othermode_L
        self.default_othermode_H = othermode_H

    def bleed_fModel(self, fModel: FModel, fMeshes: dict[FMesh]):
        # walk fModel, no order to drawing is observed, so last_mat is not kept track of
        for drawLayer, fMesh in fMeshes.items():
            self.bleed_fmesh(fMesh, None, fMesh.draw, fModel.getAllMaterials().items(), fModel.getRenderMode(drawLayer))
        self.clear_gfx_lists(fModel)

    # clear the gfx lists so they don't export
    def clear_gfx_lists(self, fModel: FModel):
        for fMaterial, texDimensions in fModel.materials.values():
            fMaterial.material.tag |= GfxListTag.NoExport
            if fMaterial.revert:
                fMaterial.revert.tag |= GfxListTag.NoExport
        for fMesh in fModel.meshes.values():
            for tri_list in fMesh.triangleGroups:
                tri_list.triList.tag |= GfxListTag.NoExport

    def bleed_fmesh(
        self,
        fMesh: FMesh,
        last_mat: FMaterial,
        cmd_list: GfxList,
        fmodel_materials,
        default_render_mode: list[str] = None,
    ):
        if bled_mat := self.bled_gfx_lists.get(cmd_list, None):
            return bled_mat

        bleed_state = self.bleed_start
        cur_fmat = None
        reset_cmd_dict = dict()
        bleed_gfx_lists = BleedGfxLists()
        fmesh_static_cmds, fmesh_jump_cmds = self.on_bleed_start(cmd_list)
        for jump_list_cmd in fmesh_jump_cmds:
            # bleed mat and tex
            if jump_list_cmd.displayList.tag & GfxListTag.Material:
                # update last_mat
                if cur_fmat:
                    last_mat = cur_fmat
                _, cur_fmat = find_material_from_jump_cmd(fmodel_materials, jump_list_cmd)
                if not cur_fmat:
                    # make better error msg
                    print("could not find material used in fmesh draw")
                    continue
                bleed_gfx_lists.bled_mats = self.bleed_mat(cur_fmat, last_mat, bleed_state)
                if not (cur_fmat.isTexLarge[0] or cur_fmat.isTexLarge[1]):
                    bleed_gfx_lists.bled_tex = self.bleed_textures(cur_fmat, last_mat, bleed_state)
                else:
                    bleed_gfx_lists.bled_tex = cur_fmat.texture_DL.commands
            # bleed tri group (for large textures) and to remove other unnecessary cmds
            if jump_list_cmd.displayList.tag & GfxListTag.Geometry:
                tri_list = jump_list_cmd.displayList
                self.bleed_tri_group(tri_list, cur_fmat, bleed_state)
                self.inline_triGroup(tri_list, bleed_gfx_lists, cmd_list, reset_cmd_dict)
                self.on_tri_group_bleed_end(tri_list, cur_fmat, bleed_gfx_lists)
                # reset bleed gfx lists after inlining
                bleed_gfx_lists = BleedGfxLists()
            # set bleed state for cmd reverts
            bleed_state = self.bleed_in_progress

        last_mat = cur_fmat
        self.on_bleed_end(last_mat, cmd_list, fmesh_static_cmds, reset_cmd_dict, default_render_mode)
        return last_mat

    def build_tmem_dict(self, cmd_list: GfxList):
        im_buffer = None
        tmem_dict = dict()
        tile_dict = {i: 0 for i in range(8)}  # an assumption that hopefully never needs correction
        for cmd in cmd_list.commands:
            if type(cmd) == DPSetTextureImage:
                im_buffer = cmd
                continue
            if type(cmd) == DPSetTile:
                tile_dict[cmd.tile] = cmd.tmem
            if type(cmd) in (DPLoadTLUTCmd, DPLoadTile, DPLoadBlock):
                tmem_dict[tile_dict[cmd.tile]] = im_buffer
                continue
        return tmem_dict

    def bleed_textures(self, cur_fmat: FMaterial, last_mat: FMaterial, bleed_state: int):
        if last_mat:
            # bleed cmds if matching tile has duplicate cmds
            # deep copy breaks on Image objects so I will only copy the levels needed
            commands_bled = copy.copy(cur_fmat.texture_DL)
            commands_bled.commands = copy.copy(cur_fmat.texture_DL.commands)  # copy the commands also
            # eliminate set tex images, but only if there is an overlap of the same image at the same tmem location
            last_im_loads = self.build_tmem_dict(last_mat.texture_DL)
            new_im_loads = self.build_tmem_dict(commands_bled)
            removable_images = []
            for tmem, image in new_im_loads.items():
                if tmem in last_im_loads and last_im_loads[tmem] == image:
                    removable_images.append(image)
            # now go through list and cull out loads for the specific cmds
            # this will be the set tex image, and the loading cmds
            rm_load = False
            for j, cmd in enumerate(cur_fmat.texture_DL.commands):
                # remove set tex explicitly
                if cmd in removable_images:
                    commands_bled.commands[j] = None
                    rm_load = True
                    continue
                if rm_load and type(cmd) == DPSetTile:
                    commands_bled.commands[j] = None
                if rm_load and type(cmd) in (DPLoadTLUTCmd, DPLoadTile, DPLoadBlock):
                    commands_bled.commands[j] = None
                    rm_load = None
                    continue
            # now eval as normal conditionals
            for j, cmd in enumerate(cur_fmat.texture_DL.commands):
                if not cmd:
                    continue  # some cmds are None from previous step
                if self.bleed_individual_cmd(commands_bled, cmd, bleed_state, last_mat.texture_DL.commands) is True:
                    commands_bled.commands[j] = None
            # remove Nones from list
            while None in commands_bled.commands:
                commands_bled.commands.remove(None)
            bled_tex = commands_bled
        else:
            bled_tex = cur_fmat.texture_DL
        return bled_tex.commands

    def bleed_mat(self, cur_fmat: FMaterial, last_mat: FMaterial, bleed_state: int):
        if last_mat:
            gfx = cur_fmat.mat_only_DL
            # deep copy breaks on Image objects so I will only copy the levels needed
            commands_bled = copy.copy(gfx)
            commands_bled.commands = copy.copy(gfx.commands)  # copy the commands also
            last_cmd_list = last_mat.mat_only_DL.commands
            for j, cmd in enumerate(gfx.commands):
                if self.bleed_individual_cmd(commands_bled, cmd, bleed_state, last_cmd_list):
                    commands_bled.commands[j] = None
            # remove Nones from list
            while None in commands_bled.commands:
                commands_bled.commands.remove(None)
        else:
            commands_bled = self.bleed_cmd_list(cur_fmat.mat_only_DL, bleed_state)
        # some syncs may become redundant after bleeding
        self.optimize_syncs(commands_bled, bleed_state)
        # remove SPEndDisplayList
        while SPEndDisplayList() in commands_bled.commands:
            commands_bled.commands.remove(SPEndDisplayList())
        return commands_bled.commands

    def bleed_tri_group(self, tri_list: GfxList, cur_fmat: fMaterial, bleed_state: int):
        # remove SPEndDisplayList from triGroup
        while SPEndDisplayList() in tri_list.commands:
            tri_list.commands.remove(SPEndDisplayList())
        if not cur_fmat or (cur_fmat.isTexLarge[0] or cur_fmat.isTexLarge[1]):
            tri_list = self.bleed_cmd_list(tri_list, bleed_state)

    # this is a little less versatile than comparing by last used material
    def bleed_cmd_list(self, target_cmd_list: GfxList, bleed_state: int):
        usage_dict = dict()
        commands_bled = copy.copy(target_cmd_list)  # copy the commands
        commands_bled.commands = copy.copy(target_cmd_list.commands)  # copy the commands
        for j, cmd in enumerate(target_cmd_list.commands):
            # some cmds you can bleed vs world defaults, others only if they repeat within this gfx list
            bleed_cmd_status = self.bleed_individual_cmd(commands_bled, cmd, bleed_state)
            if not bleed_cmd_status:
                continue
            last_use = usage_dict.get((type(cmd), getattr(cmd, "tile", None)), None)
            usage_dict[(type(cmd), getattr(cmd, "tile", None))] = cmd
            if last_use == cmd or bleed_cmd_status != self.bleed_self_conflict:
                commands_bled.commands[j] = None
        # remove Nones from list
        while None in commands_bled.commands:
            commands_bled.commands.remove(None)
        return commands_bled

    # Put triGroup bleed gfx in the FMesh.draw object
    def inline_triGroup(
        self, tri_list: GfxList, bleed_gfx_lists: BleedGfxLists, cmd_list: GfxList, reset_cmd_dict: dict[GbiMacro]
    ):
        # add material
        cmd_list.commands.extend(bleed_gfx_lists.bled_mats)
        # add textures
        cmd_list.commands.extend(bleed_gfx_lists.bled_tex)
        # add in triangles
        cmd_list.commands.extend(tri_list.commands)
        # skinned meshes don't draw tris sometimes, use this opportunity to save a sync
        tri_cmds = [c for c in tri_list.commands if type(c) == SP1Triangle or type(c) == SP2Triangles]
        if tri_cmds:
            reset_cmd_dict[DPPipeSync] = DPPipeSync()
        [bleed_gfx_lists.add_reset_cmd(cmd, reset_cmd_dict) for cmd in bleed_gfx_lists.bled_mats]

    # pre processes cmd_list and removes cmds deemed useless. subclass and override if this causes a game specific issue
    def on_bleed_start(self, cmd_list: GfxList):
        # remove SPDisplayList and SPEndDisplayList from FMesh.draw
        # place static cmds after SPDisplay lists aside and append them to the end after inline
        sp_dl_start = False
        non_jump_dl_cmds = []
        jump_dl_cmds = []
        for j, cmd in enumerate(cmd_list.commands):
            if type(cmd) == SPEndDisplayList:
                cmd_list.commands[j] = None
            # get rid of geo mode cmds those will all be reset via bleed
            elif type(cmd) == SPClearGeometryMode and sp_dl_start:
                cmd_list.commands[j] = None
            elif type(cmd) == SPSetGeometryMode and sp_dl_start:
                cmd_list.commands[j] = None
            # bleed will handle all syncs after inlining starts, but won't destroy syncs at gfxList start
            elif type(cmd) == DPPipeSync and sp_dl_start:
                cmd_list.commands[j] = None
            elif type(cmd) == SPDisplayList:
                cmd_list.commands[j] = None
                sp_dl_start = True
                jump_dl_cmds.append(cmd)
                continue
            elif sp_dl_start and cmd is not None:
                cmd_list.commands[j] = None
                non_jump_dl_cmds.append(cmd)
        # remove Nones from list
        while None in cmd_list.commands:
            cmd_list.commands.remove(None)
        return non_jump_dl_cmds, jump_dl_cmds

    def on_tri_group_bleed_end(self, triGroup: FTriGroup, last_mat: FMaterial, bleed_gfx_lists: BleedGfxLists):
        return

    def on_bleed_end(
        self,
        last_mat: FMaterial,
        cmd_list: GfxList,
        fmesh_static_cmds: list[GbiMacro],
        reset_cmd_dict: dict[GbiMacro],
        default_render_mode: list[str] = None,
    ):
        # revert certain cmds for extra safety
        reset_cmds = self.create_reset_cmds(reset_cmd_dict, default_render_mode)
        # if pipe sync in reset list, make sure it is the first cmd
        if DPPipeSync in reset_cmds:
            reset_cmds.remove(DPPipeSync)
            reset_cmds.insert(0, DPPipeSync)
        cmd_list.commands.extend(reset_cmds)
        cmd_list.commands.extend(fmesh_static_cmds)  # this is troublesome
        cmd_list.commands.append(SPEndDisplayList())
        self.bled_gfx_lists[cmd_list] = last_mat

    # remove syncs if first material, or if no gsDP cmds in material
    def optimize_syncs(self, cmd_list: GfxList, bleed_state: int):
        no_syncs_needed = {"DPSetPrimColor", "DPSetPrimDepth"}  # will not affect rdp
        syncs_needed = {"SPSetOtherMode"}  # will affect rdp
        if bleed_state == self.bleed_start:
            while DPPipeSync() in cmd_list.commands:
                cmd_list.commands.remove(DPPipeSync())
        for cmd in cmd_list.commands:
            cmd_name = type(cmd).__name__
            if cmd == DPPipeSync():
                continue
            if "DP" in cmd_name and cmd_name not in no_syncs_needed:
                return
            if cmd_name in syncs_needed:
                return
        while DPPipeSync() in cmd_list.commands:
            cmd_list.commands.remove(DPPipeSync())

    def create_reset_cmds(self, reset_cmd_dict: dict[GbiMacro], default_render_mode: list[str]):
        reset_cmds = []
        for cmd_type, cmd_use in reset_cmd_dict.items():
            if cmd_type == DPPipeSync:
                reset_cmds.append(DPPipeSync())

            # generally either loadgeo, or a combo of set/clear is used based on microcode selected
            # if you are in f3d, any selection different from the default will add a set/clear
            if cmd_type == SPLoadGeometryMode and cmd_use != self.default_load_geo:
                reset_cmds.append(self.default_load_geo)

            elif cmd_type == SPSetGeometryMode and cmd_use != self.default_set_geo:
                reset_cmds.append(self.default_set_geo)

            elif cmd_type == SPClearGeometryMode and cmd_use != self.default_clear_geo:
                reset_cmds.append(self.default_clear_geo)

            elif cmd_type == "G_SETOTHERMODE_H":
                if cmd_use != self.default_othermode_H:
                    reset_cmds.append(self.default_othermode_H)

            # render mode takes up most bits of the lower half, so seeing high bit usage is enough to determine render mode was used
            elif cmd_type == DPSetRenderMode or (cmd_type == "G_SETOTHERMODE_L" and cmd_use.length >= 31):
                if default_render_mode:
                    reset_cmds.append(
                        SPSetOtherMode(
                            "G_SETOTHERMODE_L",
                            0,
                            32 - self.is_f3d_old,
                            [*self.default_othermode_L.flagList, *default_render_mode],
                        )
                    )

            elif cmd_type == "G_SETOTHERMODE_L":
                if cmd_use != self.default_othermode_L:
                    reset_cmds.append(self.default_othermode_L)
        return reset_cmds

    def bleed_individual_cmd(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None):
        # never bleed these cmds
        if type(cmd) in [
            SPMatrix,
            SPVertex,
            SPViewport,
            SPDisplayList,
            SPBranchList,
            SP1Triangle,
            SPLine3D,
            SPLineW3D,
            SP2Triangles,
            SPCullDisplayList,
            SPSegment,
            SPBranchLessZraw,
            SPModifyVertex,
            SPEndDisplayList,
            DPSetTextureImage,
            DPLoadBlock,
            DPLoadTile,
            DPLoadTLUTCmd,
            DPFullSync,
        ]:
            return False

        # if no last list then calling func will own behavior of bleeding
        if not last_cmd_list:
            return self.bleed_self_conflict

        # apply specific logic to these cmds, see functions below, otherwise default behavior is to bleed if cmd is in the last list
        bleed_func = getattr(self, (f"bleed_{type(cmd).__name__}"), None)
        if bleed_func:
            return bleed_func(cmd_list, cmd, bleed_state, last_cmd_list)
        else:
            return cmd in last_cmd_list

    # bleed these cmds only if it is the second call and cmd was in the last use list, or if they match world defaults and it is the first call
    def bleed_SPLoadGeometryMode(
        self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None
    ):
        if bleed_state != self.bleed_start:
            return cmd in last_cmd_list
        else:
            return cmd == self.default_load_geo

    def bleed_SPSetGeometryMode(
        self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None
    ):
        if bleed_state != self.bleed_start:
            return cmd in last_cmd_list
        else:
            return cmd == self.default_set_geo

    def bleed_SPClearGeometryMode(
        self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None
    ):
        if bleed_state != self.bleed_start:
            return cmd in last_cmd_list
        else:
            return cmd == self.default_clear_geo

    def bleed_SPSetOtherMode(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None):
        if bleed_state != self.bleed_start:
            return cmd in last_cmd_list
        else:
            if cmd.cmd == "G_SETOTHERMODE_H":
                return cmd == self.default_othermode_H
            else:
                return cmd == self.default_othermode_L

    # Don´t bleed if the cmd is used for scrolling or if the last cmd's tags are not the same (those are not hashed)
    def bleed_DPSetTileSize(self, _cmd_list: GfxList, cmd: GbiMacro, _bleed_state: int, last_cmd_list: GfxList = None):
        if cmd.tags == GfxTag.TileScroll0 or cmd.tags == GfxTag.TileScroll1:
            return False
        if cmd in last_cmd_list:
            last_size_cmd = last_cmd_list[last_cmd_list.index(cmd)]
            if last_size_cmd.tags == cmd.tags:
                return True
        return False

    # At most, only one sync is needed after drawing tris. The f3d writer should
    # already have placed the appropriate sync type required. If a second sync is
    # detected between drawing cmds, then remove that sync. Remove the latest sync
    # not the first seen sync.
    def bleed_DPTileSync(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None):
        return self.bleed_between_tris(cmd_list, cmd, bleed_state, [DPLoadSync, DPPipeSync, DPTileSync])

    def bleed_DPPipeSync(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None):
        return self.bleed_between_tris(cmd_list, cmd, bleed_state, [DPLoadSync, DPPipeSync, DPTileSync])

    def bleed_DPLoadSync(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, last_cmd_list: GfxList = None):
        return self.bleed_between_tris(cmd_list, cmd, bleed_state, [DPLoadSync, DPPipeSync, DPTileSync])

    def bleed_between_tris(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int, conflict_cmds: list[GbiMacro]):
        tri_buffered = False
        for parse_cmd in cmd_list.commands:
            if parse_cmd is cmd:
                return tri_buffered
            if type(parse_cmd) in [SP2Triangles, SP1Triangle, SPLine3D, SPLineW3D]:
                tri_buffered = False
                continue
            if type(parse_cmd) in conflict_cmds:
                if not tri_buffered:
                    tri_buffered = True
                else:
                    return True
        return False


# small containers for data used in inline Gfx
@dataclass
class BleedGfxLists:
    bled_mats: GfxList = field(default_factory=list)
    bled_tex: GfxList = field(default_factory=list)

    def add_reset_cmd(self, cmd: GbiMacro, reset_cmd_dict: dict[GbiMacro]):
        reset_cmd_list = (
            SPLoadGeometryMode,
            SPSetGeometryMode,
            SPClearGeometryMode,
            DPSetRenderMode,
        )
        # separate other mode H and othermode L
        if type(cmd) == SPSetOtherMode:
            reset_cmd_dict[cmd.cmd] = cmd

        if type(cmd) in reset_cmd_list:
            reset_cmd_dict[type(cmd)] = cmd


# helper function used for sm64
def find_material_from_jump_cmd(
    material_list: tuple[tuple[bpy.types.Material, str], tuple[FMaterial, tuple[int, int]]],
    dl_jump: SPDisplayList,
):
    if dl_jump.displayList.tag & GfxListTag.Geometry:
        return None, None
    for mat in material_list:
        fmaterial = mat[1][0]
        bpy_material = mat[0][0]
        if dl_jump.displayList.tag == GfxListTag.MaterialRevert and fmaterial.revert == dl_jump.displayList:
            return bpy_material, fmaterial
        elif fmaterial.material == dl_jump.displayList:
            return bpy_material, fmaterial
    return None, None
