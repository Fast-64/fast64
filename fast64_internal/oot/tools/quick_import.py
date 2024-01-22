from pathlib import Path
import os
import re

import bpy

from ..f3d.properties import OOTDLImportSettings
from ..skeleton.properties import OOTSkeletonImportSettings
from ..animation.properties import OOTAnimImportSettingsProperty


class QuickImportAborted(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def quick_import_exec(context: bpy.types.Context, sym_name: str):
    sym_name = sym_name.strip()
    if sym_name == "":
        raise QuickImportAborted("No symbol name given")
    if not all(
        (
            "a" <= c <= "z"
            or "A" <= c <= "Z"
            or "0" <= c <= "9"
            or c
            in {
                "_",
            }
        )
        for c in sym_name
    ):
        raise QuickImportAborted("Symbol names only have characters a-zA-Z0-9_")

    sym_def_pattern = re.compile(rf"([^\s]+)\s+{sym_name}\s*(\[[^\]]*\])?\s*=")

    base_dir_p = Path(context.scene.ootDecompPath)
    assets_objects_dir_p = base_dir_p / "assets" / "objects"

    all_found_defs: dict[Path, list[tuple[str, str]]] = dict()

    for dirpath, dirnames, filenames in os.walk(assets_objects_dir_p):
        dirpath_p = Path(dirpath)
        for filename in filenames:
            file_p = dirpath_p / filename
            # Only look into C files
            if file_p.suffix != ".c":
                continue
            source = file_p.read_text()
            # Simple check to see if we should look into this file any further
            if sym_name not in source:
                continue
            found_defs = sym_def_pattern.findall(source)
            print(file_p, f"{found_defs=}")
            all_found_defs[file_p] = found_defs

    # Ideally if for example sym_name was gLinkAdultHookshotTipDL,
    # all_found_defs now contains:
    # {Path('.../assets/objects/object_link_boy/object_link_boy.c'): [('Gfx', '[]')]}
    # or with gButterflySkel:
    # {Path('.../assets/objects/gameplay_field_keep/gameplay_field_keep.c'): [('SkeletonHeader', '')]}

    if len(all_found_defs) == 0:
        raise QuickImportAborted(f"Couldn't find a definition of {sym_name}")
    if len(all_found_defs) > 1:
        raise QuickImportAborted(
            f"Found definitions of {sym_name} in several files: "
            + ", ".join(str(p.relative_to(assets_objects_dir_p)) for p in all_found_defs.keys())
        )
    assert len(all_found_defs) == 1
    sym_file_p, sym_defs = list(all_found_defs.items())[0]
    if len(sym_defs) > 1:
        raise QuickImportAborted(
            f"Found several definitions of {sym_name} in {sym_file_p.relative_to(assets_objects_dir_p)}"
        )

    # We found a single definition of the symbol
    sym_def_type, sym_def_array_decl = sym_defs[0]
    is_array = sym_def_array_decl != ""
    object_name = sym_file_p.relative_to(assets_objects_dir_p).parts[0]

    if sym_def_type == "Gfx" and is_array:
        settings: OOTDLImportSettings = context.scene.fast64.oot.DLImportSettings
        settings.name = sym_name
        settings.folder = object_name
        settings.actorOverlayName = ""
        settings.isCustom = False
        bpy.ops.object.oot_import_dl()
    elif sym_def_type in {"SkeletonHeader", "FlexSkeletonHeader"} and not is_array:
        settings: OOTSkeletonImportSettings = context.scene.fast64.oot.skeletonImportSettings
        settings.isCustom = False
        if sym_name == "gLinkAdultSkel":
            settings.mode = "Adult Link"
        elif sym_name == "gLinkChildSkel":
            settings.mode = "Child Link"
        else:
            settings.mode = "Generic"
            settings.name = sym_name
            settings.folder = object_name
            settings.actorOverlayName = ""
        bpy.ops.object.oot_import_skeleton()
    elif sym_def_type == "AnimationHeader" and not is_array:
        settings: OOTAnimImportSettingsProperty = context.scene.fast64.oot.animImportSettings
        settings.isCustom = False
        settings.isLink = False
        settings.animName = sym_name
        settings.folderName = object_name
        bpy.ops.object.oot_import_anim()
    else:
        raise QuickImportAborted(
            f"Don't know how to import {sym_def_type}"
            + ("[]" if is_array else "")
            + f" (symbol found in {object_name})"
        )
