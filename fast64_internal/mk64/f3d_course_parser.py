import re
import traceback
from mathutils import Vector
from ..f3d.f3d_gbi import F3D
from ..f3d.f3d_material import RDPSettings
from ..f3d.f3d_parser import F3DParsedCommands, ParsedMacro, math_eval, parseDLData, parseVertexData
from ..f3d.f3d_writer import F3DVert
from ..utility import PluginError, float_from_u16_str, gammaInverseValue, int_from_s16_str, readFile, unpackNormal


def courseVertexFormatPatterns():
    # position, uv, color/normal
    return (
        # decomp format
        r"\{\s*"
        r"\{+([^,\}]*),([^,\}]*),([^,\}]*)\}\s*,\s*"
        r"\{([^,\}]*),([^,\}]*)\}\s*,\s*"
        r"\{MACRO_COLOR_FLAG\(([^,\}]*),([^,\}]*),([^,\}]*),([^,\}])*\),([^,\}]*)\}\s*"
        r"\}"
    )


def parseCourseVtx(path: str, f3d):
    data = readFile(path)
    pattern = courseVertexFormatPatterns()
    vertexData = []
    for values in re.findall(pattern, data, re.DOTALL):
        values = [math_eval(g, f3d) for g in values]
        vertexData.append(
            F3DVert(
                Vector(values[0:3]),
                Vector(values[3:5]),
                Vector(values[5:8]),
                unpackNormal(values[8]),
                values[9],
            )
        )
    return vertexData


class MK64F3DContext:
    def getVertexDataStart(vertexDataParam: str, f3d: F3D):
        matchResult = re.search(r"\&?([A-Za-z0-9\_]*)\s*(\[([^\]]*)\])?\s*(\+(.*))?", vertexDataParam)
        if matchResult is None:
            raise PluginError("SPVertex param " + vertexDataParam + " is malformed.")

        offset = 0
        if matchResult.group(3):
            offset += math_eval(matchResult.group(3), f3d)
        if matchResult.group(5):
            offset += math_eval(matchResult.group(5), f3d)

        name = matchResult.group(1)

        if matchResult.group(1).startswith("0x04"):
            offset = (int(matchResult.group(1), 16) - 0x04000000) // 16
            name = hex(0x04000000)
        return name, offset

    def processCommands(self, dlData: str, dlName: str, dlCommands: "list[ParsedMacro]"):
        callStack = [F3DParsedCommands(dlName, dlCommands, 0)]
        while len(callStack) > 0:
            currentCommandList = callStack[-1]
            command = currentCommandList.currentCommand()

            if currentCommandList.index >= len(currentCommandList.commands):
                raise PluginError("Cannot handle unterminated static display lists: " + currentCommandList.name)
            elif len(callStack) > 2**16:
                raise PluginError("DL call stack larger than 2**16, assuming infinite loop: " + currentCommandList.name)

            # print(command.name + " " + str(command.params))
            if command.name == "gsSPVertex":
                vertexDataName, vertexDataOffset = self.getVertexDataStart(command.params[0], self.f3d)
                parseVertexData(dlData, vertexDataName, self)
                self.addVertices(command.params[1], command.params[2], vertexDataName, vertexDataOffset)
            elif command.name == "gsSPMatrix":
                self.setCurrentTransform(command.params[0], command.params[1])
            elif command.name == "gsSPPopMatrix":
                print("gsSPPopMatrix not handled.")
            elif command.name == "gsSP1Triangle":
                self.addTriangle(command.params[0:3], dlData)
            elif command.name == "gsSP2Triangles":
                self.addTriangle(command.params[0:3] + command.params[4:7], dlData)
            elif command.name == "gsSPDisplayList" or command.name.startswith("gsSPBranch"):
                newDLName = self.processDLName(command.params[0])
                if newDLName is not None:
                    newDLCommands = parseDLData(dlData, newDLName)
                    # Use -1 index so that it will be incremented to 0 at end of loop
                    parsedCommands = F3DParsedCommands(newDLName, newDLCommands, -1)
                    if command.name == "gsSPDisplayList":
                        callStack.append(parsedCommands)
                    elif command.name.startswith("gsSPBranch"):  # TODO: Handle BranchZ?
                        callStack = callStack[:-1]
                        callStack.append(parsedCommands)
            elif command.name == "gsSPEndDisplayList":
                callStack = callStack[:-1]

            # Should we parse commands into f3d_gbi classes?
            # No, because some parsing involves reading C files, which is separate.

            # Assumes macros use variable names instead of values
            mat = self.mat()
            try:
                # Material Specific Commands
                materialNotChanged = False

                rdp_settings: "RDPSettings" = mat.rdp_settings

                if command.name == "gsSPClipRatio":
                    rdp_settings.clip_ratio = math_eval(command.params[0], self.f3d)
                elif command.name == "gsSPNumLights":
                    self.numLights = self.getLightCount(command.params[0])
                elif command.name == "gsSPLight":
                    self.setLight(dlData, command)
                elif command.name == "gsSPLightColor":
                    self.setLightColor(dlData, command)
                elif command.name[:13] == "gsSPSetLights":
                    self.setLights(dlData, command)
                elif command.name == "gsSPAmbOcclusionAmb":
                    mat.ao_ambient = float_from_u16_str(command.params[0])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionDir":
                    mat.ao_directional = float_from_u16_str(command.params[0])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionPoint":
                    mat.ao_point = float_from_u16_str(command.params[0])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionAmbDir":
                    mat.ao_ambient = float_from_u16_str(command.params[0])
                    mat.ao_directional = float_from_u16_str(command.params[1])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionDirPoint":
                    mat.ao_directional = float_from_u16_str(command.params[0])
                    mat.ao_point = float_from_u16_str(command.params[1])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusion":
                    mat.ao_ambient = float_from_u16_str(command.params[0])
                    mat.ao_directional = float_from_u16_str(command.params[1])
                    mat.ao_point = float_from_u16_str(command.params[2])
                    mat.set_ao = True
                elif command.name == "gsSPFresnel":
                    scale = int_from_s16_str(command.params[0])
                    offset = int_from_s16_str(command.params[1])
                    dotMax = ((0x7F - offset) << 15) // scale
                    dotMin = ((0x00 - offset) << 15) // scale
                    mat.fresnel_hi = dotMax / float(0x7FFF)
                    mat.fresnel_lo = dotMin / float(0x7FFF)
                    mat.set_fresnel = True
                elif command.name == "gsSPAttrOffsetST":
                    mat.attroffs_st = [
                        int_from_s16_str(command.params[0]) / 32,
                        int_from_s16_str(command.params[1]) / 32,
                    ]
                    mat.set_attroffs_st = True
                elif command.name == "gsSPAttrOffsetZ":
                    mat.attroffs_z = int_from_s16_str(command.params[0])
                    mat.set_attroffs_z = True
                elif command.name == "gsSPFogFactor":
                    pass
                elif command.name == "gsSPFogPosition":
                    mat.fog_position = [math_eval(command.params[0], self.f3d), math_eval(command.params[1], self.f3d)]
                    mat.set_fog = True
                elif command.name == "gsSPTexture" or command.name == "gsSPTextureL":
                    # scale_autoprop should always be false (set in init)
                    # This prevents issues with material caching where updating nodes on a material causes its key to change
                    if command.params[0] == 0xFFFF and command.params[1] == 0xFFFF:
                        mat.tex_scale = (1, 1)
                    else:
                        mat.tex_scale = [
                            math_eval(command.params[0], self.f3d) / (2**16),
                            math_eval(command.params[1], self.f3d) / (2**16),
                        ]
                    # command.params[2] is "lod level", and for clarity we store this is the number of mipmapped textures (which is +1)
                    rdp_settings.num_textures_mipmapped = 1 + math_eval(command.params[2], self.f3d)
                elif command.name == "gsSPSetGeometryMode":
                    self.setGeoFlags(command, True)
                elif command.name == "gsSPClearGeometryMode":
                    self.setGeoFlags(command, False)
                elif command.name == "gsSPLoadGeometryMode":
                    self.loadGeoFlags(command)
                elif command.name == "gsSPSetOtherMode":
                    self.setOtherModeFlags(command)
                elif command.name == "gsDPPipelineMode":
                    rdp_settings.g_mdsft_pipeline = command.params[0]
                elif command.name == "gsDPSetCycleType":
                    rdp_settings.g_mdsft_cycletype = command.params[0]
                elif command.name == "gsDPSetTexturePersp":
                    rdp_settings.g_mdsft_textpersp = command.params[0]
                elif command.name == "gsDPSetTextureDetail":
                    rdp_settings.g_mdsft_textdetail = command.params[0]
                elif command.name == "gsDPSetTextureLOD":
                    rdp_settings.g_mdsft_textlod = command.params[0]
                elif command.name == "gsDPSetTextureLUT":
                    self.setTLUTMode(command.params[0])
                elif command.name == "gsDPSetTextureFilter":
                    rdp_settings.g_mdsft_text_filt = command.params[0]
                elif command.name == "gsDPSetTextureConvert":
                    rdp_settings.g_mdsft_textconv = command.params[0]
                elif command.name == "gsDPSetCombineKey":
                    rdp_settings.g_mdsft_combkey = command.params[0]
                elif command.name == "gsDPSetColorDither":
                    rdp_settings.g_mdsft_color_dither = command.params[0]
                elif command.name == "gsDPSetAlphaDither":
                    rdp_settings.g_mdsft_alpha_dither = command.params[0]
                elif command.name == "gsDPSetAlphaCompare":
                    rdp_settings.g_mdsft_alpha_compare = command.params[0]
                elif command.name == "gsDPSetDepthSource":
                    rdp_settings.g_mdsft_zsrcsel = command.params[0]
                elif command.name == "gsDPSetRenderMode":
                    flags = math_eval(command.params[0] + " | " + command.params[1], self.f3d)
                    self.setRenderMode(flags)
                elif command.name == "gsDPSetTextureImage":
                    # Are other params necessary?
                    # The params are set in SetTile commands.
                    self.currentTextureName = command.params[3]
                elif command.name == "gsDPSetCombineMode":
                    self.setCombineMode(command)
                elif command.name == "gsDPSetCombineLERP":
                    self.setCombineLerp(command.params[0:8], command.params[8:16])
                elif command.name == "gsDPSetEnvColor":
                    mat.env_color = self.gammaInverseParam(command.params)
                    mat.set_env = True
                elif command.name == "gsDPSetBlendColor":
                    mat.blend_color = self.gammaInverseParam(command.params)
                    mat.set_blend = True
                elif command.name == "gsDPSetFogColor":
                    mat.fog_color = self.gammaInverseParam(command.params)
                    mat.set_fog = True
                elif command.name == "gsDPSetFillColor":
                    pass
                elif command.name == "gsDPSetPrimDepth":
                    pass
                elif command.name == "gsDPSetPrimColor":
                    mat.prim_lod_min = math_eval(command.params[0], self.f3d) / 255
                    mat.prim_lod_frac = math_eval(command.params[1], self.f3d) / 255
                    mat.prim_color = self.gammaInverseParam(command.params[2:6])
                    mat.set_prim = True
                elif command.name == "gsDPSetOtherMode":
                    print("gsDPSetOtherMode not handled.")
                elif command.name == "DPSetConvert":
                    mat.set_k0_5 = True
                    for i in range(6):
                        setattr(mat, "k" + str(i), gammaInverseValue(math_eval(command.params[i], self.f3d) / 255))
                elif command.name == "DPSetKeyR":
                    mat.set_key = True
                elif command.name == "DPSetKeyGB":
                    mat.set_key = True
                else:
                    materialNotChanged = True

                if not materialNotChanged:
                    self.materialChanged = True

                # Texture Commands
                # Assume file texture load
                # SetTextureImage -> Load command -> Set Tile (0 or 1)

                if command.name == "gsDPSetTileSize":
                    self.setTileSize(command.params)
                elif command.name == "gsDPLoadTile":
                    self.loadTile(command.params)
                elif command.name == "gsDPSetTile":
                    self.setTile(command.params, dlData)
                elif command.name == "gsDPLoadBlock":
                    self.loadTile(command.params)
                elif command.name == "gsDPLoadTLUTCmd":
                    self.loadTLUT(command.params, dlData)

                # This all ignores S/T high/low values
                # This is pretty bad/confusing
                elif command.name.startswith("gsDPLoadTextureBlock"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(
                            [command.params[0]]
                            + [0, "G_TX_RENDERTILE"]
                            + [command.params[1], "G_IM_SIZ_4b"]
                            + command.params[2:],
                            dlData,
                            True,
                        )
                    else:
                        self.loadMultiBlock(
                            [command.params[0]] + [0, "G_TX_RENDERTILE"] + command.params[1:], dlData, False
                        )
                elif command.name.startswith("gsDPLoadMultiBlock"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(command.params[:4] + ["G_IM_SIZ_4b"] + command.params[4:], dlData, True)
                    else:
                        self.loadMultiBlock(command.params, dlData, False)
                elif command.name.startswith("gsDPLoadTextureTile"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(
                            [command.params[0]]
                            + [0, "G_TX_RENDERTILE"]
                            + [command.params[1], "G_IM_SIZ_4b"]
                            + command.params[2:4]
                            + command.params[9:],
                            "4b",  # FIXME extra argument?
                            dlData,
                            True,
                        )
                    else:
                        self.loadMultiBlock(
                            [command.params[0]] + [0, "G_TX_RENDERTILE"] + command.params[1:5] + command.params[9:],
                            "4b",  # FIXME extra argument?
                            dlData,
                            False,
                        )
                elif command.name.startswith("gsDPLoadMultiTile"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(
                            command.params[:4] + ["G_IM_SIZ_4b"] + command.params[4:6] + command.params[10:],
                            dlData,
                            True,
                        )
                    else:
                        self.loadMultiBlock(command.params[:7] + command.params[11:], dlData, False)

                # TODO: Only handles palettes at tmem = 256
                elif command.name == "gsDPLoadTLUT_pal16":
                    self.loadTLUTPal(command.params[1], dlData, 15)
                elif command.name == "gsDPLoadTLUT_pal256":
                    self.loadTLUTPal(command.params[0], dlData, 255)
                else:
                    pass

            except TypeError as e:
                print(traceback.format_exc())
                # raise Exception(e)
                # print(e)

            # Don't use currentCommandList because some commands may change that
            if len(callStack) > 0:
                callStack[-1].index += 1
