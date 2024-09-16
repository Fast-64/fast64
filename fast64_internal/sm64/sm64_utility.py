from pathlib import Path
import os
import re

import bpy
from bpy.types import UILayout

from ..utility import (
    PluginError,
    filepath_checks,
    removeComments,
    run_and_draw_errors,
    multilineLabel,
    prop_split,
    COMMENT_PATTERN,
)
from .sm64_function_map import func_map


def starSelectWarning(operator, fileStatus):
    if fileStatus is not None and not fileStatus.starSelectC:
        operator.report({"WARNING"}, "star_select.c not found, skipping star select scrolling.")


def cameraWarning(operator, fileStatus):
    if fileStatus is not None and not fileStatus.cameraC:
        operator.report({"WARNING"}, "camera.c not found, skipping camera volume and zoom mask exporting.")


ULTRA_SM64_MEMORY_C = "src/boot/memory.c"
SM64_MEMORY_C = "src/game/memory.c"


def getMemoryCFilePath(decompDir):
    isUltra = os.path.exists(os.path.join(decompDir, ULTRA_SM64_MEMORY_C))
    relPath = ULTRA_SM64_MEMORY_C if isUltra else SM64_MEMORY_C
    return os.path.join(decompDir, relPath)


MIB = 1024.0**2.0
SIZE_8MIB = 8 * MIB


def check_expanded(rom: os.PathLike, include_path=True):
    filepath_checks(rom, include_path=include_path)
    size = os.path.getsize(rom)
    if size <= SIZE_8MIB:
        raise PluginError(
            "ROM " + (f"at {rom} " if include_path else "") + "is vanilla sized (8.38 MB).\n"
            "You may be using an unexpanded ROM.\n"
            "You can expand it using ROM Manager or sm64Extend."
        )


def import_rom_checks(rom: os.PathLike, include_path=True):
    filepath_checks(
        rom,
        "Import ROM path is empty.",
        "Import ROM path {}does not exist.",
        "Import ROM path {}is not a file.",
        include_path,
    )
    check_expanded(rom, include_path)


def export_rom_checks(rom: os.PathLike, include_path=True):
    filepath_checks(
        rom,
        "Export ROM path is empty.",
        "Export ROM path {}does not exist.",
        "Export ROM path {}is not a file.",
        include_path,
    )
    check_expanded(rom, include_path)


def import_rom_ui_warnings(layout: UILayout, rom: os.PathLike):
    return run_and_draw_errors(layout, import_rom_checks, rom, False)


def export_rom_ui_warnings(layout: UILayout, rom: os.PathLike):
    return run_and_draw_errors(layout, export_rom_checks, rom, False)


def int_from_str(value: str):
    """Better errors than int(x, 0), supports hex, binary, octal and decimal."""
    bases = {
        "0x": (16, "hexadecimal value. \nOnly use characters [0-F] when representing base 16."),
        "0b": (2, "binary value. \nOnly use 0 or 1 when representing base 2."),
        "0o": (8, "octal value. \nOnly use characters [0-7] when representing base 8."),
    }
    decimal = (10, "decimal value. \nUse 0x for hexadecimal, 0b for binary, and 0o for octal.")

    value = value.strip()
    prefix = value[:2].lower() if len(value) > 1 else ""
    number_part = value[2:] if prefix in bases else value
    if not number_part:
        raise ValueError("Empty value.")

    base_and_error = bases.get(prefix, decimal)
    try:
        return int(number_part, base_and_error[0])
    except ValueError as exc:
        raise ValueError(f"{value} is not a valid " + base_and_error[1]) from exc


def string_int_warning(layout: UILayout, value: str) -> bool:
    try:
        int_from_str(value)
        return True
    except Exception as exc:
        multilineLabel(layout.box(), str(exc), "ERROR")
        return False


def string_int_prop(layout: UILayout, data, prop: str, name="", split=True, **prop_kwargs):
    if split:
        prop_split(layout, data, prop, name, **prop_kwargs)
    else:
        layout.prop(data, prop, text=name, **prop_kwargs)
    return string_int_warning(layout, getattr(data, prop))


def convert_addr_to_func(addr: str):
    if addr == "":
        raise PluginError("Empty function name/address.")
    refresh_version: str = bpy.context.scene.fast64.sm64.refresh_version
    if refresh_version.startswith("HackerSM64"):  # hacker uses refresh 13
        refresh_version = "Refresh 13"
    assert refresh_version in func_map, "Refresh version not found in function map"
    refresh_func_map = func_map[refresh_version]
    if addr.lower() in refresh_func_map:
        return refresh_func_map[addr.lower()]
    else:
        return addr


# \h is invalid because the python devs don´t believe in god
INCLUDE_EXTERN_PATTERN = re.compile(
    r"""
    # expects comments to be removed before running, we don´t need index
    ^\h*\#\h*include\h*(.*?)\h*$| # catch includes
    extern\s*(.*?)\s*; # catch externs
    """.replace(
        r"\h", r"[^\v\S]"
    ).replace(
        "COMMENT_PATTERN", COMMENT_PATTERN.pattern
    ),
    re.MULTILINE | re.VERBOSE,
)
ENDIF_PATTERN = re.compile(
    r"""
    (?:COMMENT_PATTERN)*?| # can't be a negative lookbehind, size is unknown
    (?P<endif>^\h*\#\h*endif) # catch endif
    """.replace(
        r"\h", r"[^\v\S]"
    ).replace(
        "COMMENT_PATTERN", COMMENT_PATTERN.pattern
    ),
    re.MULTILINE | re.VERBOSE,
)


def find_includes_and_externs(text: str) -> tuple[set[str], set[str]]:
    text = removeComments(text)
    matches = re.findall(INCLUDE_EXTERN_PATTERN, text)
    if matches:
        existing_includes, existing_externs = zip(*re.findall(INCLUDE_EXTERN_PATTERN, text))
        return set(existing_includes), set(existing_externs)
    return {}, {}


def write_includes(
    path: Path,
    includes: list[str] = None,
    externs: list[str] = None,
    path_must_exist=False,
    create_new=False,
    before_endif=False,
) -> bool:
    """Smarter version of writeIfNotFound, handles comments and all kinds of weird formatting
    but most importantly files without a trailing newline.
    Returns true if something was added.
    Example arguments: includes=['"mario/anims/data.inc.c"'],
    externs=["const struct Animation *const mario_anims[]"]
    """
    assert not (path_must_exist and create_new), "path_must_exist and create_new"
    if path_must_exist:
        filepath_checks(path)
    if not create_new and not includes and not externs:
        return False
    includes, externs = includes or [], externs or []

    if os.path.exists(path) and not create_new:
        text = path.read_text()
        commentless = removeComments(text)
        if commentless and commentless[-1] not in {"\n", "\r"}:  # add end new line if not there
            text += "\n"
        changed = False
    else:
        text, commentless, changed = "", "", True
    existing_includes, existing_externs = find_includes_and_externs(commentless)

    new_text = ""
    for include in includes:
        if include not in existing_includes:
            new_text += f"#include {include}\n"
            changed = True
    for extern in externs:
        if extern not in existing_externs:
            new_text += f"extern {extern};\n"
            changed = True
    if not changed:
        return False

    pos = len(text)
    if before_endif:  # don't error if there is no endif as the user may just be using #pragma once
        for match in re.finditer(ENDIF_PATTERN, text):
            if match.group("endif"):
                pos = match.start()
    text = text[:pos] + new_text + text[pos:]
    path.write_text(text)
    return True


def update_actor_includes(
    header_type: str,
    group_name: str,
    header_dir: Path,
    dir_name: str,
    data_includes: list[Path] = None,
    header_includes: list[Path] = None,
    geo_includes: list[Path] = None,
):
    data_includes, header_includes, geo_includes = data_includes or [], header_includes or [], geo_includes or []
    if header_type == "Actor":
        if not group_name:
            raise PluginError("Empty group name")
        data_path = header_dir / f"{group_name}.c"
        header_path = header_dir / f"{group_name}.h"
        geo_path = header_dir / f"{group_name}_geo.c"
    elif header_type == "Level":
        data_path = header_dir / "leveldata.c"
        header_path = header_dir / "header.h"
        geo_path = header_dir / "geo.c"
    elif header_type == "Custom":
        return  # Custom doesn't update includes
    else:
        raise PluginError(f'Unknown header type "{header_type}"')

    if write_includes(
        data_path, [f'"{(Path(dir_name) / include).as_posix()}"' for include in data_includes], path_must_exist=True
    ):
        print(f"Updated data includes at {header_path}.")
    if write_includes(
        header_path,
        [f'"{(Path(dir_name) / include).as_posix()}"' for include in header_includes],
        path_must_exist=True,
        before_endif=True,
    ):
        print(f"Updated header includes at {header_path}.")
    if write_includes(
        geo_path, [f'"{(Path(dir_name) / include).as_posix()}"' for include in geo_includes], path_must_exist=True
    ):
        print(f"Updated geo data at {geo_path}.")


def writeMaterialHeaders(exportDir, matCInclude, matHInclude):
    write_includes(Path(exportDir) / "src/game/materials.c", [matCInclude])
    write_includes(Path(exportDir) / "src/game/materials.h", [matHInclude], before_endif=True)
