from __future__ import annotations
from dataclasses import dataclass, field
import copy

from .f3d_gbi import (
    GfxTag,
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
    SPGeometryMode,
    SPSetOtherMode,
    DPLoadBlock,
    DPLoadTLUTCmd,
    DPFullSync,
    DPSetRenderMode,
    DPSetTextureLUT,
    DPSetCycleType,
    DPSetTextureImage,
    DPPipeSync,
    DPLoadSync,
    DPTileSync,
    DPSetTile,
    DPLoadTile,
)


class BleedGraphics:

    # bleed_state "enums"
    bleed_start = 1
    bleed_in_progress = 2

    def __init__(self):
        self.bled_gfx_lists = dict()

    def bleed_fModel(self, fModel: FModel, fMeshes: dict[FMesh]):
        # walk fModel, no order to drawing is observed, so lastMat is not kept track of
        for drawLayer, fMesh in fMeshes.items():
            self.bleed_fmesh(fModel.f3d, fMesh, None, fMesh.draw, fModel.getRenderMode(drawLayer))
        self.clear_gfx_lists(fModel)

    # clear the gfx lists so they don't export
    def clear_gfx_lists(self, fModel: FModel):
        for (fMaterial, texDimensions) in fModel.materials.values():
            fMaterial.material = None
            fMaterial.revert = None
        for fMesh in fModel.meshes.values():
            for tri_list in fMesh.triangleGroups:
                tri_list.triList = None

    def bleed_fmesh(self, f3d: F3D, fMesh: FMesh, lastMat: FMaterial, cmd_list: GfxList, default_render_mode=None):
        if bled_mat := self.bled_gfx_lists.get(cmd_list, None):
            return bled_mat
        self.on_bleed_start(f3d, lastMat, cmd_list)
        bleed_state = self.bleed_start
        for triGroup in fMesh.triangleGroups:
            # bleed mat and tex
            bleed_gfx_lists = BleedGfxLists()
            if triGroup.fMaterial:
                bleed_gfx_lists.bled_mats = self.bleed_mat(triGroup.fMaterial, lastMat, cmd_list, bleed_state)
                if not (triGroup.fMaterial.isTexLarge[0] or triGroup.fMaterial.isTexLarge[1]):
                    bleed_gfx_lists.bled_tex = self.bleed_textures(triGroup.fMaterial, lastMat, cmd_list, bleed_state)
                else:
                    bleed_gfx_lists.bled_tex = triGroup.fMaterial.texture_DL.commands
            lastMat = triGroup.fMaterial
            # bleed tri group (for large textures) and to remove other unnecessary cmds
            self.bleed_tri_group(f3d, triGroup, bleed_gfx_lists, cmd_list, bleed_state)
            self.inline_triGroup(f3d, triGroup, bleed_gfx_lists, cmd_list)
            self.on_tri_group_bleed_end(f3d, triGroup, lastMat, bleed_gfx_lists)
            bleed_state = self.bleed_in_progress
        self.on_bleed_end(f3d, lastMat, bleed_gfx_lists, cmd_list, default_render_mode)
        return lastMat

    def build_tmem_dict(self, cmd_list: GfxList):
        im_buffer = None
        tmem_dict = dict()
        tile_dict = {i:0 for i in range(8)} # an assumption that hopefully never needs correction
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
    
    def bleed_textures(self, curMat: FMaterial, lastMat: FMaterial, cmd_list: GfxList, bleed_state: int):
        if lastMat:
            # bleed cmds if matching tile has duplicate cmds
            # deep copy breaks on Image objects so I will only copy the levels needed
            commands_bled = copy.copy(curMat.texture_DL)
            commands_bled.commands = copy.copy(curMat.texture_DL.commands)  # copy the commands also
            # eliminate set tex images, but only if there is an overlap of the same image at the same tmem location
            last_im_loads = self.build_tmem_dict(lastMat.texture_DL)
            new_im_loads = self.build_tmem_dict(commands_bled)
            removable_images = []
            for tmem, image in new_im_loads.items():
                if tmem in last_im_loads and last_im_loads[tmem] == image:
                    removable_images.append(image)
            # now go through list and cull out loads for the specific cmds
            # this will be the set tex image, and the loading cmds
            rm_load = False
            for j, cmd in enumerate(curMat.texture_DL.commands):
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
            for j, cmd in enumerate(curMat.texture_DL.commands):
                if not cmd:
                    continue # some cmds are None from previous step
                if self.bleed_individual_cmd(commands_bled, cmd, bleed_state):
                    if cmd in lastMat.texture_DL.commands:
                        commands_bled.commands[j] = None
            # remove Nones from list
            while None in commands_bled.commands:
                commands_bled.commands.remove(None)
            bled_tex = commands_bled
        else:
            bled_tex = curMat.texture_DL
        return bled_tex.commands

    def bleed_mat(self, curMat: FMaterial, lastMat: FMaterial, cmd_list: GfxList, bleed_state: int):
        if lastMat:
            gfx = curMat.mat_only_DL
            # deep copy breaks on Image objects so I will only copy the levels needed
            commands_bled = copy.copy(gfx)
            commands_bled.commands = copy.copy(gfx.commands)  # copy the commands also
            LastList = lastMat.mat_only_DL.commands
            for j, cmd in enumerate(gfx.commands):
                if self.bleed_individual_cmd(commands_bled, cmd, bleed_state):
                    if cmd in LastList:
                        commands_bled.commands[j] = None
            # remove Nones from list
            while None in commands_bled.commands:
                commands_bled.commands.remove(None)
        else:
            commands_bled = curMat.mat_only_DL
        # remove SPEndDisplayList
        while SPEndDisplayList() in commands_bled.commands:
            commands_bled.commands.remove(SPEndDisplayList())
        return commands_bled.commands

    def bleed_tri_group(
        self, f3d: F3D, triGroup: FTriGroup, bleed_gfx_lists: BleedGfxLists, cmd_list: GfxList, bleed_state: int
    ):
        # remove SPEndDisplayList from triGroup
        while SPEndDisplayList() in triGroup.triList.commands:
            triGroup.triList.commands.remove(SPEndDisplayList())
        if (triGroup.fMaterial.isTexLarge[0] or triGroup.fMaterial.isTexLarge[1]):
            triGroup.triList = self.bleed_cmd_list(triGroup.triList, bleed_state)

    # this is a little less versatile than comparing by last used material
    def bleed_cmd_list(self, target_cmd_list: GfxList, bleed_state: int):
        usage_dict = dict()
        commands_bled = copy.copy(target_cmd_list)  # copy the commands
        commands_bled.commands = copy.copy(target_cmd_list.commands)  # copy the commands
        for j, cmd in enumerate(target_cmd_list.commands):
            if not self.bleed_individual_cmd(commands_bled, cmd, bleed_state):
                continue
            last_use = usage_dict.get((type(cmd), getattr(cmd, "tile", None)), None)
            usage_dict[(type(cmd), getattr(cmd, "tile", None))] = cmd
            if last_use == cmd:
                commands_bled.commands[j] = None
        # remove Nones from list
        while None in commands_bled.commands:
            commands_bled.commands.remove(None)
        return commands_bled

    # Put triGroup bleed gfx in the FMesh.draw object
    def inline_triGroup(self, f3d: F3D, triGroup: FTriGroup, bleed_gfx_lists: BleedGfxLists, cmd_list: GfxList):
        # add material
        cmd_list.commands.extend(bleed_gfx_lists.bled_mats)
        # add textures
        cmd_list.commands.extend(bleed_gfx_lists.bled_tex)
        # add in triangles
        cmd_list.commands.extend(triGroup.triList.commands)
        # skinned meshes don't draw tris sometimes, use this opportunity to save a sync
        tri_cmds = [c for c in triGroup.triList.commands if type(c) == SP1Triangle or type(c) == SP2Triangles]
        if tri_cmds:
            bleed_gfx_lists.reset_cmds.add(DPPipeSync)

    def on_bleed_start(self, f3d: F3D, lastMat: FMaterial, cmd_list: GfxList):
        # remove SPDisplayList and SPEndDisplayList from FMesh.draw
        iter_cmds = copy.copy(cmd_list.commands)
        spDLCmds = (c for c in iter_cmds if type(c) == SPDisplayList)
        spEndCmds = (c for c in iter_cmds if type(c) == SPEndDisplayList)
        for spDL in spDLCmds:
            cmd_list.commands.remove(spDL)
        for spEnd in spEndCmds:
            cmd_list.commands.remove(spEnd)

    def on_tri_group_bleed_end(self, f3d: F3D, triGroup: FTriGroup, lastMat: FMaterial, bleed_gfx_lists: BleedGfxLists):
        return

    def on_bleed_end(
        self, f3d: F3D, lastMat: FMaterial, bleed_gfx_lists: BleedGfxLists, cmd_list: GfxList, default_render_mode=None
    ):
        [bleed_gfx_lists.add_reset_cmd(cmd) for cmd in cmd_list.commands]
        # revert certain cmds for extra safety
        reset_cmds = [reset_cmd for cmd in bleed_gfx_lists.reset_cmds if (reset_cmd := bleed_gfx_lists.create_reset_cmd(cmd, default_render_mode))]
        # if pipe sync in rest list, make sure it is the first cmd
        if DPPipeSync in reset_cmds:
            reset_cmds.remove(DPPipeSync)
            reset_cmds.insert(0, DPPipeSync)
        cmd_list.commands.extend(reset_cmds)
        cmd_list.commands.append(SPEndDisplayList())
        self.bled_gfx_lists[cmd_list] = lastMat

    def bleed_individual_cmd(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int):
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

        bleed_func = getattr(self, (f"bleed_{type(cmd).__name__}"), None)
        if bleed_func:
            return bleed_func(cmd_list, cmd, bleed_state)

        return True

    def bleed_SPSetOtherMode(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int):
        if bleed_state != self.bleed_start:
            return True

    def bleed_DPSetTileSize(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int):
        return cmd.tags != GfxTag.TileScroll0 and cmd.tags != GfxTag.TileScroll1

    def bleed_DPSetTile(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int):
        # should only be removed if there is no other set tile in this list
        # that is on the same tile, and has different settings
        for parse_cmd in cmd_list.commands:
            if type(parse_cmd) is DPSetTile and parse_cmd is not cmd:
                if cmd != self:
                    return False
        return True

    def bleed_DPTileSync(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int):
        # will be bled if there are two of these syncs, at most only one tilesync
        # is ever required after rendering triangles, and before subsequent cmds rdp attr changes
        for parse_cmd in cmd_list.commands:
            if type(parse_cmd) is DPTileSync and parse_cmd is not cmd:
                return True
        return False

    def bleed_DPPipeSync(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int):
        # will be bled if there are two of these syncs, at most only one pipesync
        # is ever required after rendering triangles, and before subsequent cmds rdp attr changes
        for parse_cmd in cmd_list.commands:
            if type(parse_cmd) is DPPipeSync and parse_cmd is not cmd:
                return True
        return False

    def bleed_DPLoadSync(self, cmd_list: GfxList, cmd: GbiMacro, bleed_state: int):
        # will be bled if there are two of these syncs, at most only one pipesync
        # is ever required after rendering triangles, and before subsequent cmds rdp attr changes
        for parse_cmd in cmd_list.commands:
            if type(parse_cmd) is DPLoadSync and parse_cmd is not cmd:
                return True
        return False


# small containers for data used in inline Gfx
@dataclass
class BleedGfxLists:
    bled_mats: GfxList = field(default_factory=list)
    bled_tex: GfxList = field(default_factory=list)
    reset_cmds: set[GbiMacro] = field(default_factory=set)  # set of cmds to reset

    def __post_init__(self):
        # this cmds always reset
        self.reset_cmds.add(DPSetCycleType)

    def create_reset_cmd(self, cmd, default_render_mode):
        if cmd == DPSetRenderMode:
            if not default_render_mode:
                return
            else:
                return cmd(default_render_mode, None)
        return cmd(*self.reset_command_dict.get(cmd, []))
    
    @property
    def reset_command_dict(self):
        return {
            SPGeometryMode: (["G_TEXTURE_GEN"], ["G_LIGHTING"]),
            DPSetCycleType: ("G_CYC_1CYCLE",),
            DPSetTextureLUT: ("G_TT_NONE",),
            DPSetRenderMode: (None, None),
        }

    def add_reset_cmd(self, cmd: GbiMacro):
        if type(cmd) in self.reset_command_dict.keys():
            self.reset_cmds.add(type(cmd))
        if type(cmd) is SPSetOtherMode:
            if any(["G_RM" in flag for flag in cmd.flagList]):
                self.reset_cmds.add(DPSetRenderMode)
