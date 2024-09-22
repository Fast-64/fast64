# Fast64

This requires Blender 3.2+. Blender 4.0+ is recommended.

Forked from [kurethedead/fast64 on BitBucket](https://bitbucket.org/kurethedead/fast64/src).

![alt-text](/images/mario_running.gif)

This is a Blender plugin that allows one to export F3D display lists. It also has the ability to export assets for Super Mario 64 and Ocarina of Time decompilation projects. It supports custom color combiners / geometry modes / etc. It is also possible to use exported C code in homebrew applications.

Make sure to save often, as this plugin is prone to crashing when creating materials / undoing material creation. This is a Blender issue.

<https://developer.blender.org/T70574>

### Example models can be found [here](https://github.com/Fast-64/fast64-models)

![alt-text](/images/mat_inspector.png)

### Credits
Thanks to anonymous_moose, Cheezepin, Rovert, and especially InTheBeef for testing.

### Discord Server
We have a Discord server for support as well as development [here](https://discord.gg/ny7PDcN2x8).

### Links to Docs / Guides for Each Game
1. [ Super Mario 64 ](/fast64_internal/sm64/README.md)
2. [ Ocarina Of Time ](/fast64_internal/oot/README.md)

### Installation
Download the repository as a zip file. In Blender, go to Edit -> Preferences -> Add-Ons and click the "Install" button to install the plugin from the zip file. Find the Fast64 addon in the addon list and enable it. If it does not show up, go to Edit -> Preferences -> Save&Load and make sure 'Auto Run Python Scripts' is enabled.

### Tool Locations
The tools can be found in the properties sidebar under the 'Fast64' tab (toggled by pressing N).
The F3D material inspector can be found in the properties editor under the material tab.

### F3D Materials
Any exported mesh must use an F3D Material, which can be added by the 'Create F3D Material' button in the material inspector window. You CANNOT use regular blender materials. If you have a model with Principled BSDF materials, you can use the Principled BSDF to F3D conversion operator to automatically convert them. The image in the "Base Color" slot will be set as texture 0, while the image in the "Subsurface Color" slot will be set as texture 1.

### Vertex Colors
To use vertex colors, select a vertex colored texture preset and add two vertex color layers to your mesh named 'Col' and 'Alpha'. The alpha layer will use the greyscale value of the vertex color to determine alpha.

### Large Texture Mode
In F3D material properties, you can enable "Large Texture Mode". This will let you use textures up to 1024x1024 as long as each triangle in the mesh has UVs that can fit within a single tile load. Fast64 will categorize triangles into shared tile loads and load the portion of the texture when necessary.

### Decomp vs Homebrew Compatibility
There may occur cases where code is formatted differently based on the code use case. In the tools panel under the Fast64 File Settings subheader, you can toggle homebrew compatibility.

### Converting To F3D v5 Materials
A new optimized shader graph was introduced to decrease processing times for material creation and exporting. If you have a project that still uses old materials, you may want to convert them to v5. To convert an old project, click the "Recreate F3D Materials As V5" operator near the top of the Fast64 tab in 3D view. This may take a while depending on the number of materials in the project. Then go to the outliner, change the display mode to "Orphan Data" (broken heart icon), then click "Purge" in the top right corner. Purge multiple times until all of the old node groups are gone.

### F3DEX3 Features

Fast64 supports exporting data for [F3DEX3](https://github.com/HackerN64/F3DEX3), a modded microcode which brings many new features and higher performance. **Preview of these new features in the 3D view is not currently supported**, but they will be exported correctly. To modify the vertex colors of an object with a material which is using packed normals (shading/lighting and vertex colors together), temporarily switch to a vertex colored preset or uncheck `Lighting` in the material geometry mode settings. Once the vertex colors are painted how you want them, re-enable `Lighting` and `Packed Normals`.

Selecting F3DEX3 as your microcode unlocks a large number of additional presets based on F3DEX3 features. For more information on all these features, see the F3DEX3 readme, GBI, and [these videos](https://www.youtube.com/playlist?list=PLU2OUGtyQi6QswDQOXWIMaYFUcgQ9Psvm). The preset names get very long and are abbreviated as follows:
- `Shaded`: Computes lighting, which normally affects shade color.
- `Vcol`: Vertex colors are enabled in addition to lighting; normally these are multiplied together to become shade color.
- `Ao`: Ambient occlusion.
- `Cel`: Cel shading. If followed by a number, this is the number of cel levels.
- `Ltcol`: Cel shading tints are loaded from light colors.
- `Blend` vs. `Mul` for cel shading: Whether to apply the tint in the blender with linear interpolation, or by multiplication in the CC. The latter sometimes looks better, but does not support vertex colors.
- `Lerp` vs. `Mult` for multitexture (water): Whether the two textures are combined by linear interpolation or multiplication.

For cel shading, it is recommended to start with one of the cel shading presets, then modify the settings under the `Use Cel Shading` panel. Hover over each UI control for additional information about how that setting works.

### Updater

Fast64 features an updater ([CGCookie/blender-addon-updater](https://github.com/CGCookie/blender-addon-updater)).

It can be found in the addon preferences:

![How the updater in the addon preferences looks, right after addon install](/images/updater_initially.png)

Click the "Check now for fast64 update" button to check for updates.

![Updater preferences after clicking the "check for updates" button](/images/updater_after_check.png)

Click "Install main / old version" and choose "Main" if it isn't already selected:

![Updater: install main](/images/updater_install_main.png)

Click OK, there should be a message "Addon successfully installed" and prompting you to restart Blender:

![Updater: successful install, must restart](/images/updater_success_restart.png)

Clicking the red button will close Blender. After restarting, fast64 will be up-to-date with the latest main revision.

### Fast64 Development
If you'd like to develop in VSCode, follow this tutorial to get proper autocomplete. Skip the linter for now, we'll need to make sure the entire project gets linted before enabling autosave linting because the changes will be massive.
https://b3d.interplanety.org/en/using-microsoft-visual-studio-code-as-external-ide-for-writing-blender-scripts-add-ons/

#### Formatting

We use [Black](https://black.readthedocs.io/en/stable/index.html), version 23.

To install it, run `pip install 'black>=23,<24'`.

To make VS Code use it, change the `python.formatting.provider` setting to "black".

To format the whole repo, run `black .` (or `python3 -m black .` depending on how it is installed) from the root of the repo.

The (minimal) configuration for Black is in `/pyproject.toml`.

There is a GitHub action set up to check that PRs and the main branch are formatted: `/.github/workflows/black-lint.yml`

If you see a message such as

```
Oh no! 💥 💔 💥 The required version `23` does not match the running version `24.1.0`!
```

Make sure the `black --version` is 23. Install a 23 version with `pip install 'black>=23,<24'`.

#### Updater notes

Be careful if testing the updater when using git, it may mess up the .git folder in some cases.

Also see the extensive documentation in the https://github.com/CGCookie/blender-addon-updater README.

The "Update directly to main" button uses `bl_info["version"]` as the current version, and versions parsed from git tags as other versions. This means that to create a new version, the `bl_info` version should be bumped and a corresponding tag should be created (for example `"version": (1, 0, 2),` and a `v1.0.2` tag). This tag will then be available to update to, if it denotes a version that is more recent than the current version.

The "Install main / old version" button will install the latest revision from the `main` branch.
