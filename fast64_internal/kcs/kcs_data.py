# -------------------------------------------------------------------------------
# Shared Data
# -------------------------------------------------------------------------------

HS = 0x80057DB0

# type dicts for writing to file only
# values are (data type, then name, is arr (only as needed))

# -------------------------------------------------------------------------------
# Geometry Block Structs/Data
# -------------------------------------------------------------------------------

geo_block_includes = """#include <ultra64.h>
#include "geo_block_header.h"
#include "stages.h"
#include "geo.h"

"""

geo_block_header_struct = {
    0x00: ("struct Layout", "*layout[]", "ptr"),
    0x04: ("struct TextureScroll", "*tex_scroll[]", "ptr"),
    0x08: ("u32", "rendering_mode", ""),
    0x0C: ("void", "*img_refs[]", "ptr"),
    0x10: ("void", "*vtx_refs[]", "ptr"),
    0x14: ("u32", "Num_Anims", ""),
    0x18: ("void", "*Anims[]", "ptr"),
    0x1C: ("u32", "Num_Layouts", ""),
}


layout_struct = {
    0x00: ("u16", "Flag", ""),
    0x02: ("u16", "Depth", ""),
    0x04: ("struct Entry_Point", "Entry Points", "ptr"),
    0x08: ("f32", "Translation[3]", "arr"),
    0x14: ("f32", "Rotation[3]", "arr"),
    0x20: ("f32", "Scale[3]", "arr"),
}


# use for extraction,
texture_scroll_struct = {
    0x00: [">H", "field_0x0", 2],
    0x02: [">B", "fmt1", 1],
    0x03: [">B", "siz1", 1],
    0x04: [">L", "textures", 4],
    0x08: [">H", "stretch", 2],
    0x0A: [">H", "sharedOffset", 2],
    0x0C: [">H", "t0_w", 2],
    0x0E: [">H", "t0_h", 2],
    0x10: [">L", "halve", 4],
    0x14: [">f", "t0_xShift", 4],
    0x18: [">f", "t0_yShift", 4],
    0x1C: [">f", "xScale", 4],
    0x20: [">f", "yScale", 4],
    0x24: [">f", "field_0x24", 4],
    0x28: [">f", "field_0x28", 4],
    0x2C: [">L", "palettes", 4],
    0x30: [">H", "flags", 2],
    0x32: [">B", "fmt2", 1],
    0x33: [">B", "siz2", 1],
    0x34: [">H", "w2", 2],
    0x36: [">H", "h2", 2],
    0x38: [">H", "t1_w", 2],
    0x3A: [">H", "t1_h", 2],
    0x3C: [">f", "t1_xShift", 4],
    0x40: [">f", "t1_yShift", 4],
    0x44: [">f", "field_0x44", 4],
    0x48: [">f", "field_0x48", 4],
    0x4C: [">L", "field_0x4c", 4],
    0x50: [">4B", "prim_col", 4, "arr"],
    0x54: [">B", "primLODFrac", 1],
    0x55: [">B", "field_0x55", 1],
    0x56: [">B", "field_0x56", 1],
    0x57: [">B", "field_0x57", 1],
    0x58: [">4B", "env_col", 4, "arr"],
    0x5C: [">4B", "blend_col", 4, "arr"],
    0x60: [">4B", "light1_col", 4, "arr"],
    0x64: [">4B", "light2_col", 4, "arr"],
    0x68: [">L", "field_0x68", 4],
    0x6C: [">L", "field_0x6c", 4],
    0x70: [">L", "field_0x70", 4],
    0x74: [">L", "field_0x74", 4],
}

TextureScrollW = {
    0x00: ["u16", "field_0x0"],
    0x02: ["u8", "fmt1"],
    0x03: ["u8", "siz1"],
    0x04: ["u32", "textures", "ptr"],
    0x08: ["u16", "stretch"],
    0x0A: ["u16", "sharedOffset"],
    0x0C: ["u16", "t0_w"],
    0x0E: ["u16", "t0_h"],
    0x10: ["u32", "halve"],
    0x14: ["f32", "t0_xShift"],
    0x18: ["f32", "t0_yShift"],
    0x1C: ["f32", "xScale"],
    0x20: ["f32", "yScale"],
    0x24: ["f32", "field_0x24"],
    0x28: ["f32", "field_0x28"],
    0x2C: ["u32", "palettes", "ptr"],
    0x30: ["u16", "flags"],
    0x32: ["u8", "fmt2"],
    0x33: ["u8", "siz2"],
    0x34: ["u16", "w2"],
    0x36: ["u16", "h2"],
    0x38: ["u16", "t1_w"],
    0x3A: ["u16", "t1_h"],
    0x3C: ["f32", "t1_xShift"],
    0x40: ["f32", "t1_yShift"],
    0x44: ["f32", "field_0x44"],
    0x48: ["f32", "field_0x48"],
    0x4C: ["u32", "field_0x4c"],
    0x50: ["u8", "prim_col[]", "arr"],
    0x54: ["u8", "primLODFrac"],
    0x55: ["u8", "field_0x55"],
    0x56: ["u8", "field_0x56"],
    0x57: ["u8", "field_0x57"],
    0x58: ["u8", "env_col[]", "arr"],
    0x5C: ["u8", "blend_col[]", "arr"],
    0x60: ["u8", "light1_col[]", "arr"],
    0x64: ["u8", "light2_col[]", "arr"],
    0x68: ["u32", "field_0x68"],
    0x6C: ["u32", "field_0x6c"],
    0x70: ["u32", "field_0x70"],
    0x74: ["u32", "field_0x74"],
}

# -------------------------------------------------------------------------------
# Level Settings Structs/data
# -------------------------------------------------------------------------------

level_block_includes = """#include <ultra64.h>
#include "level_settings_structs.h"
#include "stages.h"
#include "level.h"

"""

LevelHeader = {
    0x0: ("u32", "*CollisionHeader", "ptr"),
    0x4: ("u32", "*NodeHeader", "ptr"),
    0x8: ("u32", "*Entities[]", "ptr"),
}


CollisionHeader = {
    0x0: ("struct Triangle", "*Triangles[]", "ptr"),
    0x4: ("u32", "Num_Triangles", ""),
    0x8: ("struct Vertices", "*Vertices[]", "ptr"),
    0xC: ("u32", "Num_Vertices", ""),
    0x10: ("f32", "*Tri_Normas[4][]", "ptr"),
    0x14: ("u32", "Num_Tri_Norms", ""),
    0x18: ("u16", "*Triangle_Cells[]", "ptr"),
    0x1C: ("u16", "Num_Tri_Cells", ""),
    0x20: ("u16", "*Tri_Norm_Cells[]", "ptr"),
    0x24: ("u16", "Num_Tri_Norm_Cells", ""),
    0x28: ("u32", "Norm_Cell_Root", ""),
    0x2C: ("u16", "*Dyn_Geo_Groups[3][]", "ptr"),
    0x30: ("u16", "*Dyn_Geo_Indices[]", "ptr"),
    0x34: ("struct WaterData", "*Water_Box_Data[]", "ptr"),
    0x38: ("u32", "Num_Water_Boxes", ""),
    0x3C: ("f32", "*Water_Normals[4][]", "ptr"),
    0x40: ("u32", "Num_Water_Normals", ""),
}


Triangles = {
    0x0: ("u16", "Vert_IDs[3]", "arr"),
    0x6: ("u16", "Norm_ID", ""),
    0x8: ("u16", "Norm_Type", ""),
    0xA: ("u16", "Dyn_Geo_ID", ""),
    0xC: ("u16", "Paticle_ID", ""),
    0xE: ("u16", "Stop", ""),
    0x10: ("u16", "Col_Param", ""),
    0x12: ("u16", "Col_Type", ""),
}


Water_Quads = {
    0x0: ("u16", "Number Normals", 2),
    0x2: ("u16", "Normals Array Offset", 2),
    0x4: ("u8", "Water Box Active", "arr"),
    0x5: ("u8", "Activate Water Flow", "arr"),
    0x6: ("u8", "Water Flow Direction", "arr"),
    0x7: ("u8", "Water Flow Speed", "arr"),
    0x8: ("f32", "Pos1", 4),
    0xC: ("f32", "Pos2", 4),
    0x10: ("f32", "Pos3", 4),
    0x14: ("f32", "Pos4", 4),
}


NodeHeader = {
    0x0: ("u32", "Num Path Nodes", ""),
    0x4: ("struct PathHeader", "*Path_Headers[]", "ptr"),
    0x8: ("u8", "*Node_Traversals[]", "ptr"),
    0xC: ("", "*Node_Dists[]", "ptr"),
}


PathHeader = {
    0x0: ["u32", "Kirby_Node", "ptr"],
    0x4: ["u32", "Path_Footer", "ptr"],
    0x8: ["u32", "Node_Connector", "ptr"],
    0xC: ["u16", "Num Connections", ""],
    0xE: ["u16", "Self Connected", ""],
}


Camera_Node = {
    0x0: ("u8", "Profile View", ""),
    0x1: ("u8", "Unused", ""),
    0x2: ("u8", "Lock H pos", ""),
    0x3: ("u8", "Lock Y pos", ""),
    0x4: ("u8", "Lock Z pos?", ""),
    0x5: ("u8", "Unused2", ""),
    0x6: ("u8", "Not Camera Pan Phi Above/Below", ""),
    0x7: ("u8", "Not Camera Pan Phi Below", ""),
    0x8: ("u8", "Camera Pan Theta", ""),
    0x9: ("u8", "unused3", ""),
    0xA: ("u16", "unused4", ""),
    0xC: ("f32", "Focus X pos", ""),
    0x10: ("f32", "Focus Y pos", ""),
    0x14: ("f32", "Focus Z pos", ""),
    0x18: ("f32", "Near Clip Plane", ""),
    0x1C: ("f32", "Far Clip Plane", ""),
    0x20: ("f32", "Cam R Scale[2]", "arr"),
    0x28: ("f32", "Cam Theta Rot[2]", "arr"),
    0x30: ("f32", "Cam Radius[2]", "arr"),
    0x38: ("f32", "FOV pair[2]", "arr"),
    0x40: ("f32", "Cam Phi Rot[2]", "arr"),
    0x48: ("f32", "Cam X Pos Lock Bounds[2]", "arr"),
    0x50: ("f32", "Cam Y Pos Lock Bounds[2]", "arr"),
    0x58: ("f32", "Cam Z Pos Lock Bounds[2]", "arr"),
    0x60: ("f32", "Cam Yaw Lock Bounds[2]", "arr"),
    0x68: ("f32", "Cam Pitch Lock Bounds[2]", "arr"),
}


Kirby_Settings_Node = {
    0x0: ("u16", "node", ""),
    0x2: ("u16", "entrance_act", ""),
    0x4: ("u8", "warp[4]", "arr"),
    0x8: ("u8", "pad1", ""),
    0x9: ("u8", "Shade[3]", "arr"),
    0xC: ("u16", "pad2", ""),
    0xE: ("u16", "Flags", ""),
    0x10: ("u16", "opt1", ""),
    0x12: ("u16", "opt2", ""),
    0x14: ("f32", "opt3", ""),
    0x18: ("f32", "opt4", ""),
    0x1C: ("f32", "pad3", ""),
}


Path_Footer = {
    0x0: ("u16", "Has_Curl", ""),
    0x2: ("u16", "Num_Pts", ""),
    0x4: ("f32", "Force", ""),
    0x8: ("u32", "*Path_Matrix", "ptr"),
    0xC: ("f32", "Node_Length", ""),
    0x10: ("u32", "*Path_Bounds", "ptr"),
    0x14: ("u32", "*Path_Curl(?)", "ptr"),
}


EntityStruct = {
    0x00: ("u8", "Node Num", ""),
    0x01: ("u8", "Bank", ""),
    0x02: ("u8", "ID", ""),
    0x03: ("u8", "Action", ""),
    0x04: ("u8", "Res_Flag", ""),
    0x05: ("u8", "Spawn_Flag", ""),
    0x06: ("u16", "Eeprom", ""),
    0x08: ("f32", "Location", "arr"),
    0x14: ("f32", "Rot", "arr"),
    0x20: ("f32", "Scale", "arr"),
}

entity_enum = [
    ("0,0", "N-Z", ""),
    ("0,1", "Rocky", ""),
    ("0,2", "Bronto Burt", ""),
    ("0,3", "Skud", ""),
    ("0,4", "Gordo", ""),
    ("0,5", "Shotzo", ""),
    ("0,6", "Spark-i", ""),
    ("0,7", "Bouncy", ""),
    ("0,8", "Glunk", ""),
    ("0,9", "?? explodes]", ""),
    ("0,10", "Chilly", ""),
    ("0,11", "Propeller", ""),
    ("0,12", "Glom", ""),
    ("0,13", "Mahall", ""),
    ("0,14", "Poppy Bros. Jr.", ""),
    ("0,19", "Bivolt", ""),
    ("0,16", "Splinter", ""),
    ("0,17", "Gobblin", ""),
    ("0,18", "Kany", ""),
    ("0,19", "Bivolt again?", ""),
    ("0,20", "Sirkibble", ""),
    ("0,21", "Gabon", ""),
    ("0,22", "Mariel", ""),
    ("0,23", "Large I3", ""),
    ("0,24", "Snipper", ""),
    ("0,25", "?? explodes again?]", ""),
    ("0,26", "Bonehead", ""),
    ("0,27", "Squibbly", ""),
    ("0,28", "Bobo", ""),
    ("0,29", "Bo", ""),
    ("0,30", "Punc", ""),
    ("0,31", "Mite", ""),
    ("0,32", "Sandman", ""),
    ("0,33", "Flopper", ""),
    ("0,34", "Kapar", ""),
    ("0,35", "Maw", ""),
    ("0,36", "Drop", ""),
    ("0,37", "Pedo", ""),
    ("0,38", "Noo", ""),
    ("0,39", "Tick", ""),
    ("0,40", "Cairn", ""),
    ("0,41", "?? invisible]", ""),
    ("0,42", "Pompey", ""),
    ("0,43", "Hack", ""),
    ("0,44", "Burnis", ""),
    ("0,45", "Fishbone", ""),
    ("0,46", "Frigis", ""),
    ("0,47", "Sawyer", ""),
    ("0,48", "Turbite", ""),
    ("0,49", "Plugg", ""),
    ("0,50", "Ghost knight", ""),
    ("0,51", "Zoos", ""),
    ("0,52", "Kakti", ""),
    ("0,53", "Rockn", ""),
    ("0,54", "Chacha", ""),
    ("0,55", "Galbo", ""),
    ("0,56", "Bumber", ""),
    ("0,57", "Scarfy", ""),
    ("0,58", "Nruff", ""),
    ("0,59", "Emp", ""),
    ("0,60", "Magoo", ""),
    ("0,61", "Yariko", ""),
    ("0,62", "invisible?", ""),
    ("0,63", "Wall Shotzo", ""),
    ("0,64", "Keke", ""),
    ("0,65", "Sparky", ""),
    ("0,66", "Ignus", ""),
    ("0,67", "Flora", ""),
    ("0,68", "Putt", ""),
    ("0,69", "Pteran", ""),
    ("0,70", "Mumbies", ""),
    ("0,71", "Pupa", ""),
    ("0,72", "Mopoo", ""),
    ("0,73", "Zebon", ""),
    ("0,74", "invisible?]", ""),
    ("0,75", "falling rocks sometimes blue]", ""),
    ("0,76", "falling rocks sometimes blue bigger?]", ""),
    ("1,0", "Waddle Dee Boss", ""),
    ("1,1", "Ado Boss", ""),
    ("1,2", "DeeDeeDee Boss", ""),
    ("2,0", "Whispy Woods", ""),
    ("2,1", "Waddle Dee Boss)", ""),
    ("3,0", "Maxim Tomato", ""),
    ("3,1", "Sandwich", ""),
    ("3,2", "Cake", ""),
    ("3,3", "Steak", ""),
    ("3,4", "Ice Cream Bar", ""),
    ("3,5", "Invinsible Candy", ""),
    ("3,6", "Yellow Star", ""),
    ("3,7", "Blue Star", ""),
    ("3,10", "crashes]", ""),
    ("3,9", "1up", ""),
    ("3,11", "Flower", ""),
    ("3,12", "School of fish", ""),
    ("3,13", "Butterfly", ""),
    ("5,0", "warps", ""),
    ("5,31", "Door", ""),
    ("5,32", "Door 2", ""),
    ("7,1", "Ado (Gives maxim tomato)", ""),
    ("8,0", "N-Z Boss", ""),
    ("8,1", "Bouncy Boss", ""),
    ("8,2", "Kakti Boss", ""),
    ("8,3", "?", ""),
    ("8,4", "Spark-i Boss", ""),
    ("8,5", "Tick Boss", ""),
    ("8,6", "Kany Boss", ""),
    ("8,7", "Kapar Boss", ""),
    ("8,8", "Blowfish boss", ""),
    ("8,9", "Galbo boss", ""),
    ("8,10", "drop monster room", ""),
    ("8,15", "Sawyer Boss", ""),
]