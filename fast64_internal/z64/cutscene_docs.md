# Cutscene Documentation

### Dictionnary
- Cutscene "Command/Commands": Cutscene "Commands" are macros that will tell the game what to do in your cutscene. It can be anything from stopping the cutscene at a certain frame, doing scene transitions or even manipulating Actors during the cutscene. The array containing the commands is called a cutscene "script". You can find more informations about each commands below.
- Camera "AT/Eye": AT means "look-at", it defines where the camera is looking, "Eye" is the position of the camera. For a person, "Eye" would be where they are and "AT" the object they are currently looking at. On Blender, the AT is a bone's tail and the Eye is a bone's head.
- "Spline": it's the movement the camera will follow.
- Actor "Cue": This is a system that triggers an Actor's code to make some action. Every Actor that has an implementation for this listens to the channel (defined by the "Actor Cue List" command) and will execute the action depending on the cue's action ID. This system is far from perfect, for instance two actors using the same channel will execute their actions at the same time.
- "Seq": Sequence, it refers to the audio (most of the time it's the background music)

### Commands
More detailed informations and commands' parameters can be found [here](https://github.com/zeldaret/oot/blob/master/include/z64cutscene_commands.h)

- ``CS_HEADER``: defines the length and the total number of command entries for a cutscene script
- ``CS_END_OF_SCRIPT``: defines the end of a command list in a cutscene script 
- ``CS_CAM_POINT``: defines a single camera point, it can be used with any of the "eye" or "at" camera commands
- ``CS_CAM_EYE``: defines a single eye point, this feature is not used in the final game and lacks polish
- ``CS_CAM_EYE_SPLINE``: declares a list of "eye" camera points that forms a spline
- ``CS_CAM_AT_SPLINE``: declares a list of "at" camera points that forms a spline
- ``CS_CAM_EYE_SPLINE_REL_TO_PLAYER`` and ``CS_CAM_AT_SPLINE_REL_TO_PLAYER``: same as the 2 above except these are relative to the player's position and yaw.
- ``CS_MISC_LIST``: declares a list of various miscellaneous commands, they're all self-explanatory, you can find the list [here](https://github.com/zeldaret/oot/blob/master/include/z64cutscene.h#L167-L204)
- ``CS_MISC``: defines a single misc command
- ``CS_LIGHT_SETTING_LIST``: declares a list of light settings commands
- ``CS_LIGHT_SETTING``: changes the light settings to the specified index, the lighting is defined in the scene
- ``CS_RUMBLE_CONTROLLER_LIST``: declares a list of controller rumble settings
- ``CS_RUMBLE_CONTROLLER``: makes the controller rumble, you can control the duration and the strength
- ``CS_ACTOR_CUE_LIST`` and ``CS_PLAYER_CUE_LIST``: declares an actor cue list, this also defines the channel to use (except for player cues)
- ``CS_ACTOR_CUE`` and ``CS_PLAYER_CUE``: defines the action to execute at the desired frame, also defines the position/rotation
- ``CS_TEXT_LIST``: declares a list of textboxes to display on-screen, when a textbox is present the cutscene won't continue until it's closed if the textbox isn't closing automatically
- ``CS_TEXT``: starts a textbox at the desired frame
- ``CS_TEXT_NONE``:
- ``CS_TEXT_OCARINA_ACTION``: defines an ocarina action, this is used when learning new songs during a cutscene
- ``CS_TRANSITION``: fills the screen with a single color to create transitions, "half" types are used in the intro cutscene to make that "night" effect in Link's house, "trigger instance" is used in the intro part where the Deku Tree talks to Navi to keep the screen white for the duration of the command
- ``CS_START_SEQ_LIST``: declares a list of ``CS_START_SEQ`` commands
- ``CS_START_SEQ``: starts a sequence
- ``CS_STOP_SEQ_LIST``: declares a list of ``CS_STOP_SEQ`` commands
- ``CS_STOP_SEQ``: stops a sequence
- ``CS_FADE_OUT_SEQ_LIST``: declares a list of ``CS_FADE_OUT_SEQ`` commands
- ``CS_FADE_OUT_SEQ``: fades out a sequence player on the specified frame range
- ``CS_TIME_LIST``: declares a list of ``CS_TIME`` commands
- ``CS_TIME``: changes the time of day to the specified hour and minute
- ``CS_DESTINATION``: defines a scene change (a new destination), specific destination types are doing other actions like changing the player's age or setting flags

### Cutscene Motion with Fast64
Fast64 has an implementation for creating camera shots and actor cues.

- A camera shot is defined by an Armature object and the camera motion is defined by the armature's bones. Due to the game's spline algorithm for camera motion, you always need one more key point at each end, to define how the camera is moving when it approaches the last normal point. So, the minimum number of bones in the armature is 4, if you want the camera to move between the positions indicated by bones 2 to 3.

When the shot / armature is selected, in the Object Properties pane there are controls for the start frame of that shot and whether it's normal, relative to Link, or the single Eye/AT point mode. When a particular key point / bone is selected, you have controls for the number of frames, view angle (FoV), and roll of the camera at that position.

At export, camera shots are sorted by name, so you should name them with something they will be in the correct order with at export (e.g. Shot01, Shot02, etc.). The bones / key frames are also sorted by name, so their names must be in the order you want the motion to have. These should both be previewed correctly (i.e. if it looks right in Blender, it should work right in game)

When you add a new bone by duplicating the last bone in the sequence, you must switch out of edit mode and back in for the previewer to properly handle that new bone. This only needs to be done after adding bones; you can preview while editing bones normally. This is due to how Blender represents bones differently in edit mode vs. object mode.

- An Actor Cue list is defined by an empty object and child objects. The list object lets you control which the "command type" (defines the channel to use) and each child object defines the action ID. Those child objects are called "Actor Cue Point". Each cue's ending frame is defined by the next cue's starting frame. The next one also defines the end position of the previous cue, this is the design made by the original OoT devs that's why it can look a bit weird at first glance.

### Details about the camera
Additional informations about the camera, you can skip reading this. This is ported from [zcamedit's readme](https://github.com/sauraen/zcamedit#details).

The camera system in game is weird, this is partly why the previewer exists. If the previewer is not behaving as you expect, it's probably working correctly! (Of course if the behavior differs between Blender and in-game, please report a bug.)

First of all, the system is based on four-point spline interpolation. This means, in the simplest case you have four values A-B-C-D, and the output changes from B to C over the duration, except with the initial trajectory based on A-B and with the final trajectory based on C-D so you get a nice curve. This is used separately to interpolate eye (camera position) and at (target look-at position) as well as camera roll and view angle. If you have more values (with the caveats below), the system will move through all the values except the start and end values. So basically you need an extra camera point at the beginning and at the end to set how the camera is starting and stopping.

Now, the game's version of this is weird for two reasons:

<details closed>
<summary>1. Continue flag checking bug</summary>
If you don't care about the coding and just want to make cutscenes, you don't have to worry about this, Fast64 takes care of it at import/export. Just make sure every cutscene command has at least 4 key points (bones).

There is a bug (in the actual game) where when incrementing to the next set of key points, the key point which is checked for whether it's the last point or not is the last point of the new set, not the last point of the old set. This means that you always need an additional extra point at the end (except for the case of exactly four points, see below). This is in addition to the extra point at the end (and the one at the beginning) which are used for the spline interpolation to set how the camera behaves at the start or the end. No data whatsoever is read from this second extra point (except for the flag that it's the last point, which is set up automatically on export).

For the case of 4 points, the camera motion from B to C works correctly, but when it gets to C, it reads the continue flag out of bounds (which will be an unspecified value). In most cases that byte won't be 0xFF, which means that on the following frame it will take the case for 1/2/3 points, and not initialize the camera position values at all, potentially leading to garbage values being used for them.

So in summary:
- Command has 0 points: Will fail to export, but probably crash in game
- Command has 1/2/3 points: Command will immediately end; the position and look will be uninitialized values, whatever was last on the stack (may cause a floating-point exception)
- Command has 4 points: Works, but don't let the cutscene get to the end of this command
- Command has 5 points: Works as if it had 4 points
- Command has 6 points: Works as if it had 5 points
- Etc.

Fast64 will automatically add this second extra point at the end on export, and also automatically remove the extra point at the end on import unless the command has only four points.
</details>

<details closed>
<summary>2. Frames interpolation</summary>
The number of frames actually spent between key points is interpolated in reciprocals and in a varying way between the key points. This makes predicting the number of frames actually spent extremely difficult unless the frames values are the same. In fact it's so difficult that this plugin actually just simulates the cutscene frame-by-frame up to the current frame every time the Blender frame changes, because solving for the position at some future time without actually stepping through all the frames up to there is too hard.

Note: It's a discretized differential equation, if time was continuous, i.e. the frame rate was infinite, it could be solved with calculus, but since it moves in discrete steps at the frames, even the calculus solution would be only approximate. On top of that, when it changes from going between B-C and going between C-D, the initial position near C depends on what happened at B, and so on.

You can think of it as it will spend *about* ``N frames`` around each key point. So, if the camera moves from point B to C but B has a larger ``frames`` value than C, the camera will move more slowly near B and more quickly near C. Also, a value of 0 means infinity, not zero, if C has ``frames=0`` the camera will approach C but never reach it.

Only the ``frames`` values of points B and C affect the result when the camera is between B and C. So, the ``frames`` values of the one extra points at the beginning and the end (in this case A and D) can be arbitrary.

The actual algorithm is:
- Compute the increment in ``t`` value (percentage of the way from point B to C) at point B by 1 / ``B.frames``, or 0 if ``B.frames`` is 0
- Compute the increment in ``t`` value at point C by 1 / ``C.frames`` or 0.
- Linearly interpolate between these based on the current ``t`` value.
- Add this increment to ``t``.

So you can think of it like, if ``B.frames`` is 10 and ``C.frames`` is 30, the camera moves 1/10th of the way from B to C per frame when it's at B, and 1/30th of the way from B to C per frame when it's nearly at C. But, when it's halfway between B and C, it doesn't move 1/20th of the way per frame, it moves (1/10)/2 + (1/30)/2 = 1/15th of the way. And on top of that, it will cross that positional halfway point less than half the total number of frames it actually takes to get from B to C.
</details>

###
There is also an ``endFrame`` parameter in the cutscene data, however it is almost useless, so it is not included as a custom property in the armature. The ``endFrame`` parameter does not end or stop the camera command, running out of key points or another camera command starting does. It's only checked when the camera command starts. In a normal cutscene where time starts from 0 and advances one frame at a time, as long as ``endFrame`` >= start_frame + 2, the command will work the same.

So, this plugin just sets it to a "reasonable value" on export, and just asserted for validity on import. It seems the original developers' tool used the sum of all the points, including the second extra point, as the ``endFrame`` parameter for ``CS_CAM_AT_SPLINE``, and used the sum of all the points without the second extra point, plus 1, for the ``CS_CAM_EYE_SPLINE`` (oh yeah, did I mention they're different?), so Fast64 replicates this behavior.
