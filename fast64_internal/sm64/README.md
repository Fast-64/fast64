# Super Mario 64

### Tool Locations (SM64)
The armature geolayout inspector can be found in the properties editor under the bone tab in Pose Mode.
The object geolayout inspector can be found in the properties editor under the object tab.
The level camera settings can be found in the properties editor under the camera tab.
The RDP default settings can be found in the properties editor under the world tab.


### ROM File Settings
When importing from a ROM, the plugin will import from the ROM at filepath 'Import ROM', When exporting to a ROM, the plugin will make a copy of the file at 'Export ROM', modify it, and save the file to 'Output ROM'. The ROM must be expanded.

### Where Can I Export To (Binary)?
By default, when exporting to ROM, the plugin will copy the contents of bank 4 to the range (0x11A35B8 - 0x11FFF00). This will leave you with free space to export assets to range (0x11D8930 - 0x11FFF00).

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

For example, for Mario you would rotate the four limb joints around the Y-axis 180 degrees, then just the arms 90/-90 degrees as such:

![alt-text](/images/mario_t_pose.gif)

Then after applying the rest pose and skinning, you would apply those operations in reverse order then apply rest pose again.

### Importing/Exporting Binary SM64 Animations (Not Mario)
-   Note: SM64 animations only allow for rotations, and translation only on the root bone.

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

Select an armature for the animation, and press 'Import/Export animation'.

### Importing/Exporting Binary Mario Animations
Mario animations use a DMA table, which contains 8 byte entries of (offset from table start, animation size). Documentation about this table is here:
https://dudaw.webs.com/sm64docs/sm64_marios_animation_table.txt
Basically, Mario's DMA table starts at 0x4EC000. There is an 8 byte header, and then the animation entries afterward. Thus the 'climb up ledge' DMA entry is at 0x4EC008. The first 4 bytes at that address indicate the offset from 0x4EC000 at which the actual animation exists. Thus the 'climb up ledge' animation entry address is at 0x4EC690. Using this table you can find animations you want to overwrite. Make sure the 'Is DMA Animation' option is checked and 'Is Segmented Pointer' is unchecked when importing/exporting. Check "Overwrite DMA Entry", set the start address to 4EC000 (for Mario), and set the entry address to the DMA entry obtained previously.

### Animating Existing Geolayouts
Often times it is hard to rig an existing SM64 geolayout, as there are many intermediate non-deform bones and bones don't point to their children. To make this easier you can use the 'Create Animatable Metarig' operator in the SM64 Armature Tools header. This will generate a metarig which can be used with IK. The metarig bones will be placed on armature layers 3 and 4.

## Decomp
To start, set your base decomp folder in SM64 General Settings. This allows the plugin to automatically add headers/includes to the correct locations. You can always choose to export to a custom location, although headers/includes won't be written.

## Repo settings
Fast64 can save and load repo settings files. By default, they're named fast64.json. These files have RDP defaults, microcode, and more. They also have game-specific settings (OOT will support these in the future). Fast64 will set the path for the settings and auto-load them if auto-load is enabled as soon as the user picks an sm64 decomp path.

### Decomp Export Types
Most exports will let you choose an export type. 

"Actor" will export data to an actor folder. The headers modified will be:

- actors/my\_group.h
- actors/my\_group.c
- actors/my\_group\_geo.c (for geolayouts)

"Level" will export data to a level folder. The headers modified will be:

- levels/my\_level/leveldata.c
- levels/my\_level/header.h

### Decomp And Extended RAM
By default decomp uses 4MB of RAM which means space runs out quickly when exporting custom assets. To handle this Fast64 will automatically add "#define USE\_EXT\_RAM" at the top of include/segments.h after the include guards.

### Exporting Geolayouts to C
Set the "Name" field to the actor folder name.
To replace an actor model, set the enum to "Actor" and set the correct group name. To find the group name, look at the group or common header files in actors/ to see where the actor is defined in.

To replace an actor model manually, replace its geo.inc.c and model.inc.c contents with the geolayout file and the dl file respectively. Use the contents of the header file to replace existing extern declarations in one of the group header files (ex. mario is in group0.h). Make sure that the name of your geolayout is the same the name of the geolayout you're replacing. Note that any function addresses in geolayout nodes will be converted to decomp function names if possible.

### Exporting Levels to C
Add an Empty and check its SM64 object type in the object properties sidebar. Change the type to "Level Root."
Add another Empty and change its type to "Area Root", and parent it to the level root object. You can now add any geometry/empties/splines as children of the area root and it will be exported with the area. They do not have to directly parent to the area root, just to something within the area root's descendants. Empties are also used for placing specials, macros, objects, water boxes, and camera volumes. You can search the available options using the relevant search operators, or set an option to "Custom" to write in your own values. NURBS curves are used to export spline data. Backgrounds are set in level root options, and warp nodes are set in area root options.

To replace a level manually, replace the contents of a level folder with your exported folder. Then,

- Add '#include "levels/mylevel/geo.inc.c"' to geo.c.
- Add '#include "levels/mylevel/leveldata.inc.c"' to leveldata.c.
- Add '#include "levels/mylevel/header.inc.h"' to header.h.
- Add '#include "levels/mylevel/texture\_include.inc.c"' to texture.inc.c. (If saving textures as PNGs.)

The level exporter will modify these files:
- src/game/camera.c (sZoomOutAreaMasks)
- levels/level\_defines.h
- levels/course\_defines.h

### Exporting HUD to C
The HUD exporter will export a texture and a function to draw it to the screen as a texture rectangle. The data will be written to segment2, and the headers modified will be:

- src/game/segment2.h (texture declaration) 
- bin/segment2.c (texture definition)
- textures/segment2 (texture file, if saving pngs separately) 

This will also write the drawing function to either src/game/hud.c or src/game/ingame_menu.c depending on the "Export Type". Note that this operator can be called multiple times and it will replace the old code from previous exports. It will not delete old textures in the textures/segment2 folder, although they won't be built in the project. It also won't delete any palette data.

The draw function will be in the format "void myfunc(x, y, width, height, s, t)". Width and height are used to take advantage of texture clamp/repeating, or to mask parts of the texture (ex. a health meter). s and t are the rectangles start UVs, which can be used to scroll the image. Negative positions are automatically handled. For basic texture drawing, set width/height to your texture dimensions and s/t to 0.

### Scrolling Textures in Decomp
Scrolling texture settings can be found in the material properties window before the "Geomtry Mode Settings" tab.
If you want to disable scrolling texture code generation, you can do so in the SM64 General Settings.
This is the process for how scrolling textures is implemented:

- Add a sSegmentROMTable to src/game/memory.c/h in order to keep track of which ROM locations are loaded into memory. ROM locations will be stored in this table during segment loading function calls.
- Add src/game/texscroll.c/h which will scroll any vertex data that is currently loaded.
- Add src/game/texscroll/ which contains segment specific texture scroll files (Ex. group0_texscroll.inc.c/h). These will be included in the texscroll.c/h file.
- The segment specific files will include texscroll.inc.c/h files from all the geometry within it that uses scrolling. These files will be generated in the same location as the vertex data being scrolled (Ex. where model.inc.c, leveldata.c is).
- Add a function call to update_level in src/game/level_update.c which calls the main scroll function.

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

### Common Issues
Game crashes: Invalid function address for switch/function/held object bones.
Animation root translation/rotation not exporting: Make sure you are animating the root bone, not the armature object.
