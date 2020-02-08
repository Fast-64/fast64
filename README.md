
# Fast64

This requires Blender 2.81.

![alt-text](https://bitbucket.org/kurethedead/fast64/raw/master/images/mario_running.gif)

This is a Blender plugin that allows one to export display lists, geolayouts, and animations to Super Mario 64, either directly into a ROM or to C code. It supports custom color combiners / geometry modes, and different geolayout node types. It is also possible to use exported C code in homebrew applications.

Make sure to save often, as this plugin is prone to crashing when creating materials / undoing material creation. This is a Blender issue.

<https://developer.blender.org/T70574>

<https://developer.blender.org/T68406>


![alt-text](https://bitbucket.org/kurethedead/fast64/raw/master/images/mat_inspector.png)

![alt-text](https://bitbucket.org/kurethedead/fast64/raw/master/images/bone_inspector.png)

### Features (import means import into Blender)  
-   Geolayout import/export 
-   Display List import/export 
-   Animation import/export
-   Collision export
-   Object Placement export (decomp only)
-   Skinned mesh support
-   Custom normals

### Restrictions
-   No YUV textures supported.
-   When importing display lists / geolayouts from SM64 to Blender, only the mesh/UVs are imported (no material)

### Credits
Thanks to anonymous_moose, Cheezepin, Rovert, and especially InTheBeef for testing.
Thanks to InTheBeef for LowPolySkinnedMario.

# Instructions
### Installation
Unzip and drag the entire folder into your blender addons folder (usually at C:\Program Files\Blender Foundation\Blender\2.80\scripts\addons). Note that you must drag the ENTIRE folder, not just the 'fast64_internal' folder. Then in Blender, go to Edit -> Preferences -> Add-Ons and find/check the 'Fast64' plugin. If it does not show up, go to Edit -> Preferences -> Save&Load and make sure 'Auto Run Python Scripts' is enabled.

### F3D Materials
Any exported mesh must use an F3D Material, which can be added by the 'Create F3D Material' button in the material inspector window. You CANNOT use regular blender materials, and you must remove any blender materials / empty materials slots from any mesh.

### ROM File Settings
When importing from a ROM, the plugin will import from the ROM at filepath 'Import ROM', When exporting to a ROM, the plugin will make a copy of the file at 'Export ROM', modify it, and save the file to 'Output ROM'. The ROM must be expanded.

### Where Can I Export To?
By default, when exporting to ROM, the plugin will copy the contents of bank 4 to the range (0x11A35B8 - 0x11FFF00). This will leave you with free space to export assets to range (0x11D8930 - 0x11FFF00).

### Tool Locations
The tools can be found in the properties sidebar under the 'Tools' tab (toggled by pressing N).
The F3D material inspector can be found in the properties editor under the material tab.
The armature geolayout inspector can be found in the properties editor under the bone tab in Pose Mode.
The object geolayout inspector can be found in the properties editor under the object tab.
The level camera settings can be found in the properties editor under the camera tab.
The RDP default settings can be found in the properties editor under the world tab.

### Vertex Colors
To use vertex colors, select the "Vertex Colored Texture" preset and add two vertex color layers to your mesh named 'Col' and 'Alpha'. The alpha layer will use the greyscale value of the vertex color to determine alpha.

### RDP State Optimization
A material will not set every single geometry mode / other mode option. Instead, each property will be checked against the default settings located in the world tab in the properties sidebar. If the values are the same, then the code to change it is not added. 

### Geolayouts (Armature)
There are many different geolayout node types. In Blender, each node corresponds to a bone, whose type is defined in the armature geolayout inspector (properties editor under the bone tab in Pose Mode). Any imported bone is also added to a bone group, for the sake of color coding different types. These groups are for visuals only, and don't determine the node type. Imported geolayouts will already have these bone groups, but if you want to add them to your own armature use the 'Add Bone Groups' operator in the SM64 Armature Tools header. All regular bones (aka 0x13 commands) and 0x15 command bones are placed on armature layer 0. All other geolayout commands are placed on layer 1. Metarig generated bones are placed on layers 3 and 4 (see 'Animating Existing Geolayouts'). If you change a bone's geolayout command type and it dissapears, it might have been moved to a different layer. Make sure to go to the armature properties editor and set both layers 0 and 1 to be visible. Geolayout command types can be edited in the properties editor under the bone tab in pose mode.

### Geolayouts (Object)
Alternatively, for simple static geolayouts you can export object hierarchies. Geolayout properties such as draw layer can be located in the object properties tab. 

### Exporting Geolayouts and Skinned Meshes
The N64 supports binary skinning, meaning each vertex will be influenced by one bone only. When skinning an exported geolayout, do NOT use automatic skinning, as this results in a smooth weight falloff. Instead, when weight painting set the weight to either 1 or 0, and set the brush Falloff to square. Skinning can only occur between an immediate parent and a child deform bone, not between siblings / across ancestors.

### Importing/Exporting SM64 Geolayouts
Download these documents by VL Tone:

[SM64MainLevelScripts.txt](http://qubedstudios.rustedlogic.net/SM64MainLevelScripts.txt)

[SM64GeoLayoutPtrsByLevels.txt](http://qubedstudios.rustedlogic.net/SM64GeoLayoutPtrsByLevels.txt)

For importing/exporting geolayouts:

-   In SM64GeoLayoutPtrsByLevels.txt, search the name of the model.
    -   There you can get the modelID (Obj) and geolayout start (ROM Address start + offset)
    -   Note that these are decimal values, and must be converted to hex when used as inputs for fast64.
-   In SM64MainLevelScripts, search '22 08 00 MM' where MM = modelID.
    -   There may be multiple instances, in which case you must use the offset field from before and check if it matches the last 3 bytes of the line.
    -   There you can get the level command, which is the first number before the slash on that line.

Plug these values into the SM64 Geolayout Exporter/Importer panels.

### Replacing Existing SM64 Geolayout Geometry
SM64 geolayouts are often in strange rest poses, which makes it hard to modify their geometry. It often helps to import an animation belonging to that geolayout to see what the idle pose of a geolayout should be. Once you know, you can rotate the bones of the armature in pose mode to a usable position and then use the 'Apply as Rest Pose' operator under the SM64 Armature Tools header. Skin your new mesh to that armature, then rotate the bones back to the original position and use 'Apply as Rest Pose' again. You can now export the geolayout to SM64 and it will be able to use existing animations.

### Importing/Exporting SM64 Animations (Not Mario)

-   Download Quad64, open the desired level, and go to Misc -> Script Dumps.
-   Go to the objects header, find the object you want, and view the Behaviour Script tab.
-   For most models with animation, you can will see a 27 command, and optionally a 28 command.

For importing:

-   The last 4 bytes of the 27 command will be the animation list pointer.
    -   Make sure 'Is DMA Animation' is unchecked, 'Is Anim List' is checked, and 'Is Segmented Pointer' is checked. 
    -   Set the animation importer start address as those 4 bytes.
    -   If a 28 command exists, then the second byte will be the anim list index.
    -   Otherwise, the anim list index is usually 0.

For exporting:

-   Make sure 'Set Anim List Entry' is checked.
-   Copy the addresses of the 27 command, which is the first number before the slash on that line.
-   Optionally do the same for the 28 command, which may not exist.
-   If a 28 command exists, then the second byte will be the anim list index.
-   Otherwise, the anim list index is usually 0.

Select an armature for the animation, and press 'Import/Export animation'. Note that the armature's root 0x13 (i.e. regular) bone must be named 'root'.

### Importing/Exporting Mario Animations
Mario animations use a DMA table, which contains 8 byte entries of (offset from table start, animation size). Documentation about this table is here:
https://dudaw.webs.com/sm64docs/sm64_marios_animation_table.txt.
Basically, Mario's DMA table starts at 0x4EC000. There is an 8 byte header, and then the animation entries afterward. Thus the 'climb up ledge' DMA entry is at 0x4EC008. The first 4 bytes at that address indicate the offset from 0x4EC000 at which the actual animation exists. Thus the 'climb up ledge' animation address is at 0x4EC690. Using this table you can find animations you want to overwrite. Make sure the 'Is DMA Animation' option is checked and 'Is Segmented Pointer' is unchecked when importing/exporting.

### Animating Existing Geolayouts
Often times it is hard to rig an existing SM64 geolayout, as there are many intermediate non-deform bones and bones don't point to their children. To make this easier you can use the 'Create Animatable Metarig' operator in the SM64 Armature Tools header. This will generate a metarig which can be used with IK. The metarig bones will be placed on armature layers 3 and 4.

### C Exporting 
When exporting data to C, a folder will be created (if it does not yet exist) and will be named after the user-provided name. The C files will be saved within this new folder. Any previous C files of the same name will be overwritten.

### Decomp And Extended RAM
By default decomp uses 4MB of RAM which means space runs out quickly when exporting custom assets. To handle this, make sure to add "#define USE_EXT_RAM" at the top of include/segments.h after the include guards.

### Exporting Geolayouts to C
To replace an actor model in decomp, make sure "Write Headers for Actor" is checked and set the correct group name. Make sure the "Name" field is the folder name of the actor, and the directory is the /actors folder.

To replace an actor model manually, replace its geo.inc.c and model.inc.c contents with the geolayout file and the dl file respectively. Use the contents of the header file to replace existing extern declarations in one of the group header files (ex. mario is in group0.h). Make sure that the name of your geolayout is the same the name of the geolayout you're replacing. Note that any function addresses in geolayout nodes will be converted to decomp function names if possible. Make sure to also use extended RAM as described in the sections above.

### Exporting Levels to C
Add an Empty and check its SM64 object type in the object properties sidebar. Change the type to "Level Root."
Add another Empty and change its type to "Area Root", and parent it to the level root object. You can now add any geometry/empties as child of the area root and it will be exported with the area. Empties are also used for placing specials, macros, and objects. Backgrounds are set in level root options, and warp nodes are set in area root options. Make sure to also use extended RAM as described in the sections above.

The directory field should be the /levels directory if exporting directly to decomp, and the name should be the level folder name. 

To replace a level manually, replace the contents of a level folder with your exported folder. Then,

Add '#include "levels/mylevel/geo.inc.c"' to geo.c.

Add '#include "levels/mylevel/leveldata.inc.c"' to leveldata.c.

Add '#include "levels/mylevel/header.inc.h"' to header.h.

Add '#include "levels/mylevel/texture_include.inc.c"' to texture.inc.c. (If saving textures as PNGs.)

Comment out any AREA() commands and their contents in script.c and add '#include "levels/mylevel/script.inc.c"' in their place.

Change the LOAD_MIO0() command for segment 0x0A to get the correct skybox segment as defined in include/segment_symbols.h.


### Switch Statements
To create a switch node, and a bone to your armature and set its geolayout type to "Switch". Any bones that will be switched should be parented to this switch bone. The switch bone can do either material, draw layer, or mesh switching.

To add a mesh switch option node, duplicate and separate your switch bone into its own armature and move it off to the side. Set the bone geolayout command to "Switch Option". This bone must be the root bone of all other bones in the armature. Skin your switch option geometry to this armature, then add your switch option armature to the switch bone options in your original armature.

### Insertable Binary Exporting
Insertable Binary exporting will generate a binary file, with a header containing metadata about pointer locations. It is formatted as such:

    0x00-0x04 : Data Type
        0 = Display List
        1 = Geolayout
        2 = Animation
        3 = Collision

    0x04-0x08 : Data Size (size in bytes of Data Section)
    0x08-0x0C : Start Address (start address of data, relative to start of Data Section)
    0x0C-0x10 : Number of Pointer Addresses (number of pointer addresses to be resolved)
    0x10-N    : List of 4-byte pointer addresses. Each address relative to start of Data Section.
    N-end     : Data Section (actual binary data)

To resolve pointer addresses, for each pointer address,

    # Get data section only
    data = fileData[N:]

    # Get current offset
    current_offset = data[pointer_address]

    # Convert offset to segmented address
    data[pointer_address] = encode_segmented_address(export_address + current_offset)

### Decomp vs Homebrew Compatibility
There may occur cases where code is formatted differently based on the code use case. In the tools panel under the SM64 File Settings subheader, you can toggle decomp compatibility.

### Common Issues
Game crashes: Invalid function address for switch/function/held object bones.
