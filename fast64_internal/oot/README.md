# Ocarina Of Time

## Table of Contents
1. [Getting Started](#getting-started)
2. [Scene Overview](#scene-overview)
3. [Actors](#actors)
4. [Exits](#exits)
5. [Draw Config and Dynamic Material Properties](#scene-draw-configuration-and-dynamic-material-properties)
6. [Collision](#collision)
7. [Skeletons and Animations](#skeletons-and-animations)
8. [Flipbook Textures](#flipbook-textures)
9. [Custom Link Process](#custom-link-process)
10. [Custom Skeleton Mesh Process](#custom-skeleton-mesh-process)
11. [Cutscenes](#cutscenes)

### Getting Started
1. In the 3D view properties sidebar (default hotkey to show this is `n` in the viewport), go to the ``Fast64`` tab, then ``Fast64 Global Settings`` and set ``Game`` to ``OOT``.
2. Switch to the ``OOT`` tab. In ``OOT File Settings``, set your decomp path to the path of your [HackerOoT (recommended)](https://github.com/HackerN64/HackerOoT) or [OoT Decomp](https://github.com/zeldaret/oot/) repository on disk. Check `Enable HackerOoT Features` if using HackerOoT.
3. In ``OOT Tools``, click `Add Scene` to create a basic scene.
4. Press `a` so that everything is selected, then click `Clear Transform`.
5. In ``OOT Scene Exporter`` you can choose the scene to replace or add. Some scenes have some hardcoded things that will cause them to break, so choose something like ``Market Entrance (Child Day) (Entra)``.
- To add a custom scene choose ``Custom`` in the scene search box, then choose in which folder you want to export the scene and which name you want it to be (note that Fast64 will force the scene name to be lower-case).
- Enable ``Export as Single File`` if you want to have your scene in the same format as the other ones in decomp.
6. Make sure you selected the right scene in ``Scene Object`` then click "Export Scene" to export it. When you click ``Add Scene`` this is set automatically.
7. Compile and run the game.
8. (Optional) In the ``View`` tab you may want to increase the ``Clip End`` value.
9. Note: You can read [this code](https://github.com/Dragorn421/oot/tree/mod_base_for_mods) to take a glance at what you can do for quality of life for testing.

### Scene Overview
In Blender, the "empty" object type is used to define different types of OOT data, including scenes and rooms.
For scenes, there must be a specific parenting hierarchy:

![](/images/oot_scene_hierarchy.png)

This means that any geometry/actors/etc. not parented to the scene hierarchy will NOT be included in the export.
Note that geometry/actors/etc. do not have to be directly parented to the room empty, as long as its in a descendant's hierachy somewhere. Cutscene empty objects needs to be parented to nothing.

Properties for empties/meshes can be found in the Blender object properties window.

![](/images/oot_object_inspector.png)

Read the "Getting Started" section for information on scene exporting.

### Actors
To add an actor you need to create a new empty object in Blender, the shape doesn't matter.
When the empty object is created you can set the ``Actor`` object type in the ``Object Properties`` panel.

To add actors to a scene, create a new Empty and parent it to a Room, otherwise they will not be exported in the room C code. Then in the Object Properties panel select ``Actor`` as the Object Type. Use the ``Select Actor ID`` button to choose an actor, and then set the Actor Parameter value as desired (see the list of Actor Parameters below).

Finally, every actors you are using needs their assets. In OoT they're called "Objects", if an actor is missing an object the code will not spawn the actor. To do this select the Room that your actor is parented to, select the "Objects" tab in its Object Properties window, and click "Add Item".

Then "Search Object ID" to find the actor object you need. For example, if adding a Deku Baba actor (EN_DEKUBABA) you need to add the "Dekubaba" object to the Room's object dependencies. Note that the object list must not contain more than 15 items.

#### Actor Parameters
Actor parameters can be found at https://wiki.cloudmodding.com/oot/Actor_List_(Variables). This documentation is NOT 100% accurate, you can get more informations with the OoT Decomp. Look for ``rot.z`` and ``params`` in the actor you want, some actors may use ``rot.x`` and ``rot.y``.

### Exits
The debug menu scene select can be found at ``SceneSelectEntry sScenes[]`` in ``src/overlays/gamestates/ovl_select/z_select.c``.
The last field of a ``SceneSelectEntry`` is the index into ``gEntranceTable`` (found in ``src/code/z_scene_table.c``).
All exits are basically an index into this table. Due to the way it works it makes it difficult to add/remove entries without breaking everything. For now the user will have to manually manage this table. For more info check out https://wiki.cloudmodding.com/oot/Entrance_Table.

### Scene Draw Configuration And Dynamic Material Properties
The scene object has a property called ``Draw Config``. This is an index into ``sSceneDrawHandlers`` in ``src/code/z_scene_table.c``.
Each function in this table will load certain Gfx commands such as scrolling textures or setting color registers into the beginning of a RAM segment using ``gsSPSegment()``. In Blender, in the material properties window you can choose which commands are called at the beginning of the material drawing. For example, to get animated water you need to use segment 9 with the draw config 19 (0x13).

![](/images/oot_dynamic_material.png)

Note that there are different segments loaded between the OPA (opaque) and XLU (transparent) draw layers.
Additionally, for functions like ``Gfx_TexScroll()``, the x,y inputs are pre-shifted by <<2. For example, a % 128 means a repeat of the texture every 32 pixels.

### Collision
Collision properties are found underneath the material properties. Water boxes and collision properties will have references the properties "Camera", "Lighting", and "Exit", which reference the indices of the scene cameras, scene light list, and scene exit list respectively. If you want separate visual/collision geometry, you can set per mesh object "Ignore Collision" or "Ignore Render" in object inspector window.

### Skeletons And Animations
For bones, there are 3 bone types: Default, Custom DL, and Ignore. This can be set in the bone properties window.
Default is a regular deformation bone. Ignore will not be handled by the exporter/importer. Custom DL lets you define the name of a DL that you want a bone to draw instead of drawing geometry from the armature. There is also an option for billboarding the specific geometry associated with the bone.

The armature properties window also has the option to set a LOD armature. This armature must have the same bone structure as your current armature.

To export a skeletal mesh, select an armature and then click "Export" for the armature exporter. Make sure there is only one bone without a parent (the root bone), as the exporter will choose the first parentless bone as the start bone of the armature.

To import a skeletal mesh, just click "Import" for the armature importer. You may encounter a couple issues:

![](/images/oot_imported_gerudo_textured.png)
![](/images/oot_imported_gerudo_solid.png)

1. Certain colors are white/different: Some graphical effects are achieved through dynamic Gfx commands, such as tinting white textures. These effects will not be imported.
2. Strange imported normals: Due to the behaviour of rotating vertices on a skinned triangle that differs between Blender and the N64, normals may look strange. Note that these normals will look correct if re exported back into the game (assuming the rest pose is not changed).

Note that rest pose rotations are zeroed out on export, so you can modify the rest pose of imported armature while still preserving its structure. You can do this by using the "Apply As Rest Pose" operator under the Fast64 tab or the OOT Skeleton Exporter section. Note that imported animations however still require the imported rest pose to work correctly.

There may also be an issue where some meshes import completely black due to the assumption that the F3D cycle mode is set to 2-Cycle, when it should really be 1-Cycle. Try changing the cycle type to 1-Cycle in cases where a dynamic texture pointer is not expected.

To import an animation, select the armature the animation belongs to then click "Import" on the animation importer.
To export an animation, select an armature and click "Export", which will export the active animation of the armature.

### Flipbook Textures
Many actors in OOT will animate textures through code using a flipbook method, like with Link's eyes/mouth. A flipbook material will use a texture reference pointing to an address formatted as 0x0?000000. You can find the flipbook texture frames in the material properties tab underneath the dynamic material section.
![](/images/oot_flipbook.png)
On import, Fast64 will try to read the provided actors code for flipbook textures. On export, Fast64 will try to modify texture arrays used for flipbook textures.

For Link, the eyes/mouth materials use flipbook textures. For Link animations you can animate these flipbook indices in the Link Animation Inspector, located in the object properties tab for an armature object. Note that the 0 index is reserved for the "auto" setting, and that flipbook texture indices start at 1.
![](/images/oot_link_texture_anim.png)

### Custom Link Process
1. In the OOT Skeleton Exporter window, go to the Import Skeleton section, select "Mode" and switch it to "Adult Link."
2. Click "Import Skeleton" to import the skeleton from your decomp repo set up in the the "Getting Started" intro.
3. Replace/modify the mesh. When applying weights, make sure there is geometry weighted to every bone that is set to "deformable". Otherwise Link's skeleton may break in game, due to the way Link's actor handles some of its drawing code.
4. For any new materials, make sure to go to material properties -> OOT Dynamic Material Properties -> enable segment C. This handles rendering for Link's reflection.
5. To add your own eye/mouth materials, create a new F3D material, then go to material properties -> F3D Material Inspector -> Sources -> Texture 0 Properties:
    - Set "Use Texture Reference".
    - Set the texture size to the size of your textures.
    - Ignore palette reference/size, those will be auto-generated if using CI textures.
    - Set the texture reference to 0x08000000 (eyes) or 0x09000000 (mouth)
6. To add different eye/mouth texture frames, go to the material properties tab, then scroll down to the Flipbook Properties.
7. Once you've modified Link's mesh, go the OOT Skeleton Exporter window, go to the Export Skeleton section, select "Mode" and switch it to "Adult Link".
8. Select Link's armature and then hit "Export Skeleton".
9. If you're not using HackerOOT, make sure to set NON_MATCHING to 1 in the Makefile in the decomp repo.
10. Most of Link's items are combined with his hand mesh. There are plans to simplify the process, but for now these models must be manually replaced using the display list importer/exporter. You'll also have to modify the DL arrays at the start of src/code/z_player_lib.c to include your own DLs if you're appending and not replacing.
11. Common Issues:
    - Corrupted mesh: Make sure the root, upper control, and lower control bones are the only bones set to non-deform.
    - Incorrect waist DL: Go to src/code/z_player_lib.c and modify sPlayerWaistDLs to include your own waist DL.

Note on Link's bone-weighting requirements in depth:
Heavy modifications of Links model can cause his matrices array to shift from what many display lists in the game expect. Changing the amount of display lists Link's skeleton has can cause some references to matrices in segment 0xD to break, and those display lists must be updated to reflect your changes.

### Custom Skeleton Mesh Process
1. Import the character you want to modify.
    - Skeleton: The name of the skeleton struct, of type FlexSkeletonHeader or SkeletonHeader. Usually found in the object files.
    - Object: The "asset group" the skeleton belongs to. The name will be from "assets/objects/\<name\>/"
    - Overlay: The location of the actor code, if necessary. The name will be from "src/overlays/actors/\<name\>/"
2. Put it into a suitable rest pose, then click the "Apply As Rest Pose" button at the bottom of the OOT Skeleton Exporter section to apply it. It helps to import an existing animation to see how a good rest pose would look like.
    - Animation Header Name: struct of type AnimationHeader or LinkAnimationHeader, found in the object files.
3. Replace the existing mesh with your own.
4. Export the skeleton back into the game. It is not necessary to re-fold the armature before export.
5. If "Replace Vanilla Headers On Export" is enabled, then any reference conflicts should be removed.
6. In the actor header file, (in src/overlays/actors/\<name\>/), set the joint/morph table sizes to be (number of bones + 1)
7. In the actor source file, this value should also be used for the limbCount argument in SkelAnime_InitFlex().

### Cutscenes
For more informations about cutscenes [click here](cutscene_docs.md)

**Creating the cutscene itself:**

1. Start with using the ``Add Cutscene`` button from the OOT Panel. Name it ``Cutscene.YOUR_CS_NAME``, ``YOUR_CS_NAME`` being the name of your choice, it can be something like: ``Cutscene.fireTempleIntroCS``. Note that this object can't be parented to any object, also this will automatically create a new camera and it will also set the Blender scene's active camera to this one.
2. Select the scene where you want to add the cutscene, and in the object properties go in the ``Cutscene`` tab then enable ``Write Cutscene``. In ``Data`` select ``Object`` and in ``Cutscene Object`` select the cutscene empty object you just created.
3. Now you can create the camera shot. The ``Create Camera Shot`` button from the cutscene object's properties panel will add a basic shot with 4 bones that you can edit. To have a better idea of the position/angle of one point of the shot, you can change the display of the armature in the ``Object Data Properties`` panel (select the shot object first), choose ``Octahedral`` in ``Viewport Display`` then ``Display As``.
4. The first and last bone of the shot won't be actual camera points, it defines the start and the end of a camera shot, this means a basic shot will only have 2 actual camera points. Either duplicate (``SHIFT+D``) or add a new bone to add more camera points. Note that these points will be exported in the order you can see in the view layer.
5. You can edit the position and rotation of each bone in the ``Edit Mode`` after selecting the shot object. The "tail" (less large point) of a bone is the direction (the "look-at", or AT), and "head" (larger point) is the origin (the "eye").
7. When you're done with your cutscene, exporting the scene will also export the camera shot and actor cue data. If you don't want to re-export the scene everytime, select the cutscene object you want to export and use ``Export Cutscene`` from ``OOT Cutscene Exporter`` in the OOT panel. In the ``File`` field, you can choose the scene of your choice (note that it can export into actors too). You can toggle the usage of decomp's names and macros with the ``Use Decomp for Export`` checkbox, you can also choose to insert the motion data in an existing cutscene (it will create a new array if it can't find it, it's based on the name of the object you selected). This is done by toggling the ``Export Motion Data Only`` checkbox.
8. Compile the game.

<details closed>
<summary>Armature Data Properties Panel</summary>
<img src="/images/oot_armature_data_properties.png" width=500/>
</details>


**Watching the cutscene in-game**

To be able to actually watch your cutscene you need to have a way to trigger it, this can be done by an actor (for instance) or using the entrance cutscene table. This guide will be explaining how to use an entrance.

1. Open ``src/code/z_demo.c`` and add an ``#include`` with the path of the file containing your cutscene.
2. Add an entry at the end of ``EntranceCutscene sEntranceCutsceneTable[]``, the format is:
``{ ENTRANCE_NUMBER, AGE_RESTRICTION, FLAG, SEGMENT_ADDRESS }``
- ``ENTRANCE_NUMBER`` is the entrance index in ``gEntranceTable``
- ``AGE_RESTRICTION`` defines if you want to play your cutscene only as child (set it to 1), as adult (set it to 0) or both (set it to 2)
- ``FLAG`` is the ``event_chk_inf`` flag that will prevent playing the cutscene everytime, you can use something unused like ``0x0F`` (https://wiki.cloudmodding.com/oot/Save_Format#event_chk_inf for more informations)
- ``SEGMENT_ADDRESS`` is the important part. This is the memory address where your cutscene is located. Using the ``#include`` will allow you to use the name of the array containing the cutscene commands in the file you exported you're cutscene, if you named the cutscene object ``Cutscene.YOUR_CS_NAME`` then this array will be named ``YOUR_CS_NAME``, use that name for the segment address.
3. Example with: ``{ ENTR_SPOT00_3, 2, EVENTCHKINF_A0, gHyruleFieldIntroCs },``
- ``ENTR_SPOT00_3`` is the Hyrule Field entrance from Lost Woods, see ``entrance_table.h`` to view/add entrances
- ``2`` means this cutscene can be watched as child AND as adult
- ``EVENTCHKINF_A0`` is the flag set in the ``event_chk_inf`` table, this is a macro but you can use raw hex: ``0xA0``
- ``gHyruleFieldIntroCs`` is the name of the array with the cutscene commands, as defined in ``extracted/VERSION/assets/scenes/overworld/spot00_scene.c``, ``CutsceneData gHyruleFieldIntroCs[]``
4. Compile the game again and use the entrance you chose for ``sEntranceCutsceneTable`` and your cutscene should play.

Alternatively, you can use the map select to watch your cutscene, though note that this won't make it watchable during normal gameplay:

1. Open ``src/overlays/gamestates/ovl_select/z_select.c``
2. Either edit or add an entry inside ``SceneSelectEntry sScenes[]``, for instance: ``{ "My Scene", MapSelect_LoadGame, ENTR_MYSCENE_0 },`` (note that the entrance used is the first of the block you need to have for the scene)
3. Compile the game, you may or may not need to run ``make clean`` first if you edited the entrance table
4. Get on the map select then scroll until you see your new entry (in the previous example is will be called "My Scene") then press R to change the header, on the vanilla map select the first cutscene header will be called ``ﾃﾞﾓ00``, on HackerOoT it will be ``Cutscene 0`` then press A to start the cutscene.

Note that you can have the actual address of your cutscene if you use ``sym_info.py`` from decomp. Example with ``gHyruleFieldIntroCs``:
- Command: ``./sym_info.py gHyruleFieldIntroCs``
- Result: ``Symbol gHyruleFieldIntroCs (RAM: 0x02013AA0, ROM: 0x27E9AA0, build/assets/scenes/overworld/spot00/spot00_scene.o)``

If you have a softlock in-game then you probably did something wrong when creating the cutscene. Make sure you set up the bones properly. The softlock means the game is playing a cutscene but it's probably reading wrong data. Make sure the cutscene is exported, if it's not export it again.

If the camera preview in Blender isn't following where you have the bones or if the cutscene sort of works in-game but the positions are all wrong:

1. Make sure your scene empty object, room empty object, and cutscene empty object are all at the Blender origin. You can usually do this with a combination of Object > Clear > Origin and Alt+G. Maybe Object > Apply > All Transforms if that doesn't work. If your room empty object is 1 meter below your scene empty object, as fast64 does by default, that offset will be applied to everything in game and then the zcamedit stuff will not be at the correct relative position.

2. If you moved / rotated / etc. one of the camera shots / armatures in object mode, this transformation will be ignored. You can fix this by selecting the shot / armature in object mode and clicking Object > Apply > All Transforms. That will convert the transform to actual changed positions for each bone.

If the game crashes check the transitions if you use the transition command (check both the ones from the entrance table and your cutscene script), also it will crash if you try to use the map select without having a 5th entrance (or more depending on the number of cutscenes you have) in the group for your scene.
