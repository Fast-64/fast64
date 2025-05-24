from __future__ import annotations

import copy
import bpy

from dataclasses import dataclass, field

from ..utility import create_or_get_world
from .f3d_gbi import (
    DPPipelineMode,
    DPSetAlphaCompare,
    DPSetAlphaDither,
    DPSetColorDither,
    DPSetCombineKey,
    DPSetCycleType,
    DPSetDepthSource,
    DPSetTextureConvert,
    DPSetTextureDetail,
    DPSetTextureFilter,
    DPSetTextureLOD,
    DPSetTextureLUT,
    DPSetTexturePersp,
    GfxMatWriteMethod,
    GfxTag,
    GfxListTag,
    SPGeometryMode,
    SPMatrix,
    SPSetOtherModeSub,
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
    DPSetTileSize,
    DPLoadTile,
    FModel,
    FMesh,
    FMaterial,
    FAreaData,
    F3D,
    GfxList,
    FTriGroup,
    GbiMacro,
    get_F3D_GBI,
)


def get_geo_cmds(
    clear_modes: set[str], set_modes: set[str], is_ex2: bool, matWriteMethod: GfxMatWriteMethod
) -> tuple[
    list[SPLoadGeometryMode | SPGeometryMode | SPSetGeometryMode | SPClearGeometryMode],
    list[SPGeometryMode | SPSetGeometryMode | SPClearGeometryMode],
]:
    set_modes, clear_modes = set(set_modes), set(clear_modes)
    if len(clear_modes) == 0 and len(set_modes) == 0:
        return ([], [])
    if is_ex2:
        if matWriteMethod == GfxMatWriteMethod.WriteAll:
            return ([SPLoadGeometryMode(set_modes)], [])
        elif len(set_modes) > 0 and len(clear_modes) > 0:
            return ([SPGeometryMode(clear_modes, set_modes)], [SPGeometryMode(set_modes, clear_modes)])
    material, revert = [], []
    if len(set_modes) > 0:
        material.append(SPSetGeometryMode(set_modes))
        revert.append(SPClearGeometryMode(set_modes))
    if len(clear_modes) > 0:
        material.append(SPClearGeometryMode(clear_modes))
        revert.append(SPSetGeometryMode(clear_modes))
    return (material, revert)


GEO_CMDS = (SPGeometryMode, SPSetGeometryMode, SPClearGeometryMode, SPLoadGeometryMode)
WRITE_DIFF_OTHERMODE_CMDS = (SPSetOtherModeSub, DPSetRenderMode)


def get_flags(
    set_modes: set[str], clear_modes: set[str], cmd: GEO_CMDS, default_clear: SPClearGeometryMode | None = None
):
    if type(cmd) == SPGeometryMode:
        set_modes.update(cmd.setFlagList)
        clear_modes.update(cmd.clearFlagList)
        clear_modes.difference_update(set_modes)
        set_modes.difference_update(clear_modes)
    elif type(cmd) == SPSetGeometryMode:
        set_modes.update(cmd.flagList)
        clear_modes.difference_update(set_modes)
    elif type(cmd) == SPClearGeometryMode:
        clear_modes.update(cmd.flagList)
        set_modes.difference_update(clear_modes)
    elif type(cmd) == SPLoadGeometryMode:
        clear_modes.update(set_modes)
        clear_modes.difference_update(cmd.flagList)
        if default_clear is not None:
            clear_modes.update(default_clear.flagList - cmd.flagList)
        set_modes.clear()
        set_modes.update(cmd.flagList)


class BleedGraphics:
    # bleed_state "enums"
    bleed_start = 1
    bleed_in_progress = 2
    # tells bleed logic to check against itself instead of last list
    bleed_self_conflict = 3

    def __init__(self):
        self.bled_gfx_lists = dict()
        self.reset_gfx_lists = set()
        # build world default cmds to compare against, f3d types needed for reset cmd building
        self.f3d = get_F3D_GBI()
        self.is_f3d_old = bpy.context.scene.f3d_type == "F3D"
        self.is_f3dex2 = "F3DEX2" in bpy.context.scene.f3d_type
        self.build_default_geo()
        self.build_default_othermodes()

    def build_default_geo(self):
        defaults = create_or_get_world(bpy.context.scene).rdp_defaults

        setGeo = SPSetGeometryMode()
        clearGeo = SPClearGeometryMode()

        def place_in_flaglist(flag: bool, enum: str, set_list: SPSetGeometryMode, clear_list: SPClearGeometryMode):
            if flag:
                set_list.flagList.add(enum)
            else:
                clear_list.flagList.add(enum)

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

        othermode_L: dict[SPSetOtherModeSub:str] = {}
        othermode_L[DPSetAlphaCompare] = defaults.g_mdsft_alpha_compare
        othermode_L[DPSetDepthSource] = defaults.g_mdsft_zsrcsel

        othermode_H: dict[SPSetOtherModeSub:str] = {}
        othermode_H[DPSetColorDither] = defaults.g_mdsft_rgb_dither
        othermode_H[DPSetAlphaDither] = defaults.g_mdsft_alpha_dither
        othermode_H[DPSetCombineKey] = defaults.g_mdsft_combkey
        othermode_H[DPSetTextureConvert] = defaults.g_mdsft_textconv
        othermode_H[DPSetTextureFilter] = defaults.g_mdsft_text_filt
        othermode_H[DPSetTextureLUT] = defaults.g_mdsft_textlut
        othermode_H[DPSetTextureLOD] = defaults.g_mdsft_textlod
        othermode_H[DPSetTextureDetail] = defaults.g_mdsft_textdetail
        othermode_H[DPSetTexturePersp] = defaults.g_mdsft_textpersp
        othermode_H[DPSetCycleType] = defaults.g_mdsft_cycletype
        othermode_H[DPPipelineMode] = defaults.g_mdsft_pipeline
        self.default_othermode_dict = othermode_L | othermode_H
        self.default_othermode_H = SPSetOtherMode(
            "G_SETOTHERMODE_H", 4, 20 - self.is_f3d_old, set(othermode_H.values())
        )
        # if the render mode is set, it will be consider non-default a priori
        self.default_othermode_L = SPSetOtherMode("G_SETOTHERMODE_L", 0, 3 - self.is_f3d_old, set(othermode_L.values()))

    def bleed_fModel(self, fModel: FModel, fMeshes: dict[FMesh]):
        # walk fModel, no order to drawing is observed, so last_mat is not kept track of
        for drawLayer, fMesh in fMeshes.items():
            reset_cmd_dict = {}
            self.bleed_fmesh(
                None,
                reset_cmd_dict,
                fMesh.draw,
                fModel.getAllMaterials().items(),
                fModel.matWriteMethod,
                fModel.getRenderMode(drawLayer),
            )
            self.add_reset_cmds(fMesh.draw, reset_cmd_dict, fModel.matWriteMethod, fModel.getRenderMode(drawLayer))
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

    def add_reset_cmd(
        self, f3d: F3D, cmd: GbiMacro, reset_cmd_dict: dict[GbiMacro], mat_write_method: GfxMatWriteMethod
    ):
        reset_cmd_list = (DPSetRenderMode,)
        if SPGeometryMode not in reset_cmd_dict:
            if mat_write_method == GfxMatWriteMethod.WriteAll:
                reset_cmd_dict[SPGeometryMode] = (
                    self.default_set_geo.flagList.copy(),
                    self.default_clear_geo.flagList.copy(),
                )
            else:
                reset_cmd_dict[SPGeometryMode] = set(), set()
        get_flags(*reset_cmd_dict[SPGeometryMode], cmd)
        if isinstance(cmd, SPSetOtherModeSub):
            l: SPSetOtherMode = reset_cmd_dict.get("G_SETOTHERMODE_L")
            h: SPSetOtherMode = reset_cmd_dict.get("G_SETOTHERMODE_H")
            if l or h:  # should never be reached, but if we reach it we are prepared
                if h and cmd.is_othermodeh:
                    for existing_mode in [mode for mode in h.flagList if str(mode).startswith(cmd.mode_prefix)]:
                        h.flagList.remove(existing_mode)
                    h.flagList.add(cmd.mode)
                if l and not cmd.is_othermodeh:
                    for existing_mode in [mode for mode in l.flagList if str(mode).startswith(cmd.mode_prefix)]:
                        l.flagList.remove(existing_mode)
                    l.flagList.add(cmd.mode)
            else:
                reset_cmd_dict[type(cmd)] = cmd

        # separate other mode H and othermode L
        elif type(cmd) == SPSetOtherMode:
            if cmd.cmd in reset_cmd_dict:
                reset_cmd_dict[cmd.cmd].add_other(f3d, cmd)
            else:
                reset_cmd_dict[cmd.cmd] = copy.deepcopy(cmd)

        elif type(cmd) in reset_cmd_list:
            reset_cmd_dict[type(cmd)] = cmd

    def bleed_fmesh(
        self,
        last_mat: FMaterial,
        reset_cmd_dict: dict[type, GbiMacro],
        cmd_list: GfxList,
        fmodel_materials,
        mat_write_method: GfxMatWriteMethod,
        default_render_mode: tuple[str] = None,
    ):
        if bled_mat := self.bled_gfx_lists.get(id(cmd_list)):
            return bled_mat
        bleed_state = self.bleed_start
        cur_fmat = None
        bleed_gfx_lists = BleedGfxLists()
        fmesh_static_cmds, fmesh_jump_cmds = self.on_bleed_start(cmd_list)
        start_cmds = cmd_list.commands  # commands that preceed any jump list
        for jump_list_cmd in fmesh_jump_cmds:
            # bleed mat and tex
            if jump_list_cmd.displayList.tag & GfxListTag.Material:
                _, cur_fmat = find_material_from_jump_cmd(fmodel_materials, jump_list_cmd)
                if not cur_fmat:
                    # make better error msg
                    print("could not find material used in fmesh draw")
                    continue
                if not (cur_fmat.isTexLarge[0] or cur_fmat.isTexLarge[1]):
                    bleed_gfx_lists.bled_tex = self.bleed_textures(cur_fmat, last_mat, bleed_state)
                else:
                    bleed_gfx_lists.bled_tex = cur_fmat.texture_DL.commands
                bleed_gfx_lists.bled_mats = self.bleed_mat(
                    cur_fmat, last_mat, start_cmds, mat_write_method, default_render_mode, bleed_state
                )
                start_cmds = []
            # bleed tri group (for large textures) and to remove other unnecessary cmds
            if jump_list_cmd.displayList.tag & GfxListTag.Geometry:
                tri_list = jump_list_cmd.displayList
                self.bleed_tri_group(tri_list, cur_fmat, bleed_state)
                self.inline_triGroup(tri_list, bleed_gfx_lists, cmd_list)
                self.on_tri_group_bleed_end(tri_list, cur_fmat, bleed_gfx_lists)
                # reset bleed gfx lists after inlining
                bleed_gfx_lists = BleedGfxLists()
            # set bleed state for cmd reverts
            bleed_state = self.bleed_in_progress
            last_mat = cur_fmat
        cmd_list.commands.extend(fmesh_static_cmds)  # this is troublesome
        cmd_list.commands.append(SPEndDisplayList())
        self.optimize_syncs(cmd_list)  # some syncs may become redundant after bleeding
        [self.add_reset_cmd(self.f3d, cmd, reset_cmd_dict, mat_write_method) for cmd in cmd_list.commands]
        self.bled_gfx_lists[id(cmd_list)] = cur_fmat
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
                if self.bleed_individual_cmd(commands_bled, cmd, last_mat.texture_DL.commands) is True:
                    commands_bled.commands[j] = None
            # remove Nones from list
            while None in commands_bled.commands:
                commands_bled.commands.remove(None)
            bled_tex = commands_bled
        else:
            bled_tex = cur_fmat.texture_DL
        return bled_tex.commands

    def bleed_mat(
        self,
        cur_fmat: FMaterial,
        last_mat: FMaterial,
        start_cmds: list[GbiMacro],
        mat_write_method: GfxMatWriteMethod,
        default_render_mode: list[str],
        bleed_state: int,
    ):
        if mat_write_method == GfxMatWriteMethod.WriteAll:
            new_sets, new_clears = self.default_set_geo.flagList.copy(), self.default_clear_geo.flagList.copy()
            previous_sets, previous_clears = (
                self.default_set_geo.flagList.copy(),
                self.default_clear_geo.flagList.copy(),
            )
            revert_sets, revert_clears = self.default_set_geo.flagList.copy(), self.default_clear_geo.flagList.copy()
        else:
            new_sets, new_clears = set(), set()
            previous_sets, previous_clears = set(), set()
            revert_sets, revert_clears = set(), set()
        revert_other_diff_cmd, revert_other_load_cmd, othermode_diff_cmds, last_cmd_list = [], [], [], []
        [get_flags(new_sets, new_clears, cmd, self.default_clear_geo) for cmd in cur_fmat.mat_only_DL.commands]

        if last_mat:
            gfx = cur_fmat.mat_only_DL
            # deep copy breaks on Image objects so I will only copy the levels needed
            commands_bled = copy.copy(gfx)
            commands_bled.commands = copy.copy(gfx.commands)  # copy the commands also
            last_cmd_list = last_mat.mat_only_DL.commands + start_cmds
            [get_flags(previous_sets, previous_clears, cmd, self.default_clear_geo) for cmd in last_cmd_list]

            # handle write diff reverts
            othermode_diff_cmds = [c for c in commands_bled.commands if isinstance(c, WRITE_DIFF_OTHERMODE_CMDS)]
            if last_mat.revert:
                [get_flags(revert_sets, revert_clears, cmd, self.default_clear_geo) for cmd in last_mat.revert.commands]
                revert_other_diff_cmd = [
                    c for c in last_mat.revert.commands if isinstance(c, WRITE_DIFF_OTHERMODE_CMDS)
                ]
                revert_other_load_cmd = [
                    copy.deepcopy(c) for c in last_mat.revert.commands if isinstance(c, SPSetOtherMode)
                ]
            # while load mode is always written, they may not set the same range of values and therefor need revert
            for revert_cmd in revert_other_load_cmd:
                othermode_cmd = next(
                    (c for c in commands_bled.commands if type(c) == type(revert_cmd) and c.cmd == revert_cmd.cmd), None
                )
                if othermode_cmd is None:
                    commands_bled.commands.insert(0, revert_cmd)
                else:
                    index = commands_bled.commands.index(othermode_cmd)
                    revert_cmd.add_other(self.f3d, othermode_cmd)
                    commands_bled.commands[index] = revert_cmd
            commands_bled.commands = [
                cmd
                for cmd in commands_bled.commands
                if not self.bleed_individual_cmd(commands_bled, cmd, last_cmd_list, default_render_mode)
            ]
        else:
            [get_flags(previous_sets, previous_clears, cmd, self.default_clear_geo) for cmd in start_cmds]
            commands_bled = self.bleed_cmd_list(cur_fmat.mat_only_DL, default_render_mode, bleed_state)

        # remove all geo cmds to add later
        commands_bled.commands = [cmd for cmd in commands_bled.commands if not isinstance(cmd, GEO_CMDS)]

        # remove clears and sets from revert if they will be set later in start or this material
        revert_clears, revert_sets = (
            revert_clears - previous_clears - new_sets,
            revert_sets - previous_sets - new_clears,
        )
        if mat_write_method == GfxMatWriteMethod.WriteAll:
            if previous_clears != new_clears or previous_sets != new_sets:
                set_modes, clear_modes = new_sets | revert_sets, new_clears | revert_clears
                # add back removed geo cmds, reverts and start cmds
                for cmd in get_geo_cmds(clear_modes, set_modes, self.f3d.F3DEX_GBI_2, mat_write_method)[0]:
                    commands_bled.commands.insert(0, cmd)
        else:
            # remove clears and sets from the material if set in start
            new_clears, new_sets = new_clears - previous_clears, new_sets - previous_sets
            # combine
            set_modes, clear_modes = new_sets | revert_sets, new_clears | revert_clears
            clear_modes, set_modes = clear_modes - set_modes, set_modes - clear_modes

            # add back removed geo cmds and reverts
            for cmd in get_geo_cmds(clear_modes, set_modes, self.f3d.F3DEX_GBI_2, mat_write_method)[0]:
                commands_bled.commands.insert(0, cmd)

        # if there is no equivelent othermode cmd, it must be using the revert
        for revert_cmd in revert_other_diff_cmd:
            othermode_cmd = next((cmd for cmd in othermode_diff_cmds if type(cmd) == type(revert_cmd)), None)
            if othermode_cmd is None:
                commands_bled.commands.insert(0, revert_cmd)

        # remove SPEndDisplayList
        while SPEndDisplayList() in commands_bled.commands:
            commands_bled.commands.remove(SPEndDisplayList())
        return commands_bled.commands

    def bleed_tri_group(self, tri_list: GfxList, cur_fmat: fMaterial, bleed_state: int):
        # remove SPEndDisplayList from triGroup
        while SPEndDisplayList() in tri_list.commands:
            tri_list.commands.remove(SPEndDisplayList())
        if not cur_fmat or (cur_fmat.isTexLarge[0] or cur_fmat.isTexLarge[1]):
            tri_list = self.bleed_cmd_list(tri_list, None, bleed_state)

    # this is a little less versatile than comparing by last used material
    def bleed_cmd_list(self, target_cmd_list: GfxList, default_render_mode: list[str], bleed_state: int):
        usage_dict = dict()
        commands_bled = copy.copy(target_cmd_list)  # copy the commands
        commands_bled.commands = copy.copy(target_cmd_list.commands)  # copy the commands
        for j, cmd in enumerate(target_cmd_list.commands):
            # some cmds you can bleed vs world defaults, others only if they repeat within this gfx list
            bleed_cmd_status = self.bleed_individual_cmd(commands_bled, cmd, default_render_mode=default_render_mode)
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
    def inline_triGroup(self, tri_list: GfxList, bleed_gfx_lists: BleedGfxLists, cmd_list: GfxList):
        # add material
        cmd_list.commands.extend(bleed_gfx_lists.bled_mats)
        # add textures
        cmd_list.commands.extend(bleed_gfx_lists.bled_tex)
        # add in triangles
        cmd_list.commands.extend(tri_list.commands)

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

    def add_reset_cmds(
        self,
        cmd_list: GfxList,
        reset_cmd_dict: dict[GbiMacro],
        mat_write_method: GfxMatWriteMethod,
        default_render_mode: tuple[str] = None,
    ):
        if not cmd_list or not reset_cmd_dict or id(cmd_list) in self.reset_gfx_lists:
            return False
        # revert certain cmds for extra safety
        reset_cmds = self.create_reset_cmds(reset_cmd_dict, mat_write_method, default_render_mode)
        while SPEndDisplayList() in cmd_list.commands:
            cmd_list.commands.remove(SPEndDisplayList())
        cmd_list.commands.extend(reset_cmds)
        cmd_list.commands.append(SPEndDisplayList())
        self.optimize_syncs(cmd_list)
        self.reset_gfx_lists.add(id(cmd_list))
        return True

    # remove syncs if first material, or if no gsDP cmds in material
    def optimize_syncs(self, cmd_list: GfxList):
        no_syncs_needed = {"DPSetPrimColor", "DPSetPrimDepth"}  # will not affect rdp
        syncs_needed = {"SPSetOtherMode", "SPTexture"}  # will affect rdp

        tri_buffered = True
        last_load_sync = None
        old_cmds = cmd_list.commands
        new_cmds = []
        cmd_list.commands = new_cmds

        for cmd in old_cmds:
            cmd_name = type(cmd).__name__
            is_dp_cmd = ("DP" in cmd_name and cmd_name not in no_syncs_needed) or cmd_name in syncs_needed
            if isinstance(cmd, (DPPipeSync, DPLoadSync, DPTileSync)):
                continue
            elif isinstance(cmd, (DPLoadBlock, DPLoadTile, DPLoadTLUTCmd, DPSetTile, DPSetTileSize)) and tri_buffered:
                last_load_sync = len(new_cmds)
                new_cmds.append(DPLoadSync())
                tri_buffered = False
            elif tri_buffered and is_dp_cmd:
                tri_buffered = False
                if last_load_sync is not None:
                    new_cmds[last_load_sync] = DPPipeSync()
                    last_load_sync = None
                else:
                    new_cmds.append(DPPipeSync())
            elif not is_dp_cmd and isinstance(cmd, (SP2Triangles, SP1Triangle, SPLine3D, SPLineW3D)):
                tri_buffered = True
                last_load_sync = None
            new_cmds.append(cmd)

    def create_reset_cmds(
        self, reset_cmd_dict: dict[GbiMacro], mat_write_method: GfxMatWriteMethod, default_render_mode: list[str]
    ):
        reset_cmds = []
        for cmd_type, cmd_use in reset_cmd_dict.items():
            if cmd_type == SPGeometryMode:  # revert cmd includes everything from the start
                set_list, clear_list = cmd_use
                if mat_write_method == GfxMatWriteMethod.WriteDifferingAndRevert:
                    clear_list = clear_list - self.default_clear_geo.flagList
                    set_list = set_list - self.default_set_geo.flagList
                    reset_cmds.extend(get_geo_cmds(clear_list, set_list, self.f3d.F3DEX_GBI_2, mat_write_method)[1])
                elif clear_list != self.default_clear_geo.flagList or set_list != self.default_set_geo.flagList:
                    reset_cmds.append(self.default_load_geo)
            elif cmd_type == "G_SETOTHERMODE_H":
                if cmd_use != self.default_othermode_H:
                    reset_cmds.append(self.default_othermode_H)

            elif cmd_type == DPSetRenderMode:
                if default_render_mode and cmd_use.flagList != default_render_mode:
                    reset_cmds.append(DPSetRenderMode(tuple(default_render_mode)))

            elif cmd_type == "G_SETOTHERMODE_L":
                flag_list = copy.copy(self.default_othermode_L.flagList)
                if cmd_use.sets_rendermode(self.f3d):
                    flag_list.update(default_render_mode)
                default_othermode_l = SPSetOtherMode(
                    "G_SETOTHERMODE_L",
                    0,
                    (32 if cmd_use.sets_rendermode(self.f3d) else 3) - self.is_f3d_old,
                    flag_list,
                )
                if cmd_use != default_othermode_l:
                    reset_cmds.append(default_othermode_l)

            elif isinstance(cmd_use, SPSetOtherModeSub):
                default = self.default_othermode_dict[cmd_type]
                if cmd_use.mode != default:
                    reset_cmds.append(cmd_type(default))
        return reset_cmds

    def bleed_individual_cmd(
        self,
        cmd_list: GfxList,
        cmd: GbiMacro,
        last_cmd_list: GfxList = None,
        default_render_mode: tuple[str] = None,
    ):
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

        if last_cmd_list is None:
            if isinstance(cmd, SPSetOtherModeSub):
                return cmd.mode == self.default_othermode_dict[type(cmd)]
            elif isinstance(cmd, DPSetRenderMode):
                return cmd.flagList == default_render_mode and cmd.blender is None

        # apply specific logic to these cmds, see functions below, otherwise default behavior is to bleed if cmd is in the last list
        bleed_func = getattr(self, (f"bleed_{type(cmd).__name__}"), None)
        if bleed_func:
            return bleed_func(cmd_list, cmd, last_cmd_list)
        else:
            return last_cmd_list is not None and cmd in last_cmd_list

    # bleed these cmds only if it is the second call and cmd was in the last use list, or if they match world defaults and it is the first call
    def bleed_SPLoadGeometryMode(self, cmd_list: GfxList, cmd: GbiMacro, last_cmd_list: GfxList = None):
        if last_cmd_list is not None:
            return cmd in last_cmd_list
        else:
            return cmd == self.default_load_geo

    def bleed_SPSetOtherMode(self, cmd_list: GfxList, cmd: GbiMacro, last_cmd_list: GfxList = None):
        if last_cmd_list is not None:
            return cmd in last_cmd_list
        else:
            if cmd.cmd == "G_SETOTHERMODE_H":
                return cmd == self.default_othermode_H
            else:
                return cmd == self.default_othermode_L

    # Don´t bleed if the cmd is used for scrolling or if the last cmd's tags are not the same (those are not hashed)
    def bleed_DPSetTileSize(self, _cmd_list: GfxList, cmd: GbiMacro, last_cmd_list: GfxList = None):
        if cmd.tags == GfxTag.TileScroll0 or cmd.tags == GfxTag.TileScroll1:
            return False
        if last_cmd_list is not None and cmd in last_cmd_list:
            last_size_cmd = last_cmd_list[last_cmd_list.index(cmd)]
            if last_size_cmd.tags == cmd.tags:
                return True
        return False


# small containers for data used in inline Gfx
@dataclass
class BleedGfxLists:
    bled_mats: GfxList = field(default_factory=list)
    bled_tex: GfxList = field(default_factory=list)


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
