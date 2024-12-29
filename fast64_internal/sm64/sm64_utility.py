import dataclasses
from typing import NamedTuple, Optional
from pathlib import Path
from io import StringIO
import random
import string
import os
import re

import bpy
from bpy.types import UILayout

from ..utility import (
    filepath_checks,
    run_and_draw_errors,
    multilineLabel,
    prop_split,
    as_posix,
    PluginError,
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


def temp_file_path(path: Path):
    """Generates a temporary file path that does not exist from the given path."""
    result, size = path.with_suffix(".tmp"), 0
    for size in range(5, 15):
        if not result.exists():
            return result
        random_suffix = "".join(random.choice(string.ascii_letters) for _ in range(size))
        result = path.with_suffix(f".{random_suffix}.tmp")
        size += 1
    raise PluginError("Cannot create unique temporary file. 10 tries exceeded.")


class ModifyFoundDescriptor:
    string: str
    regex: str

    def __init__(self, string: str, regex: str = ""):
        self.string = string
        if regex:
            self.regex = regex.replace(r"\h", r"[^\v\S]")  # /h is invalid... for some reason
        else:
            self.regex = re.escape(string) + r"\n?"


@dataclasses.dataclass
class DescriptorMatch:
    string: str
    start: int
    end: int

    def __iter__(self):
        return iter((self.string, self.start, self.end))


class CommentMatch(NamedTuple):
    commentless_pos: int
    size: int


def adjust_start_end(starting_start: int, starting_end: int, comment_map: list[CommentMatch]):
    """
    Adjust start and end positions in a commentless string to account for comments positions
    in comment_map.
    """
    start, end = starting_start, starting_end
    for commentless_pos, comment_size in comment_map:
        if starting_start >= commentless_pos:
            start += comment_size
        if starting_end >= commentless_pos or starting_start > commentless_pos:
            end += comment_size
    return start, end


def find_descriptor_in_text(
    value: ModifyFoundDescriptor,
    commentless: str,
    comment_map: list[CommentMatch],
    start=0,
    end=-1,
    adjust=True,
):
    """
    Find all matches of a descriptor in a commentless string with respect to comment positions
    in comment_map.
    """
    matches: list[DescriptorMatch] = []
    for match in re.finditer(value.regex, commentless[start:end]):
        match_start, match_end = match.start() + start, match.end() + start
        if adjust:
            match_start, match_end = adjust_start_end(match_start, match_end, comment_map)
        matches.append(DescriptorMatch(match.group(0), match_start, match_end))
    return matches


def get_comment_map(text: str):
    """Get a string without comments and a list of the removed comment positions."""
    comment_map: list[CommentMatch] = []
    commentless, last_pos, commentless_pos = StringIO(), 0, 0
    for match in re.finditer(COMMENT_PATTERN, text):
        commentless_pos += commentless.write(text[last_pos : match.start()])  # add text before comment
        match_string = match.group(0)
        if match_string.startswith("/"):  # actual comment
            comment_map.append(CommentMatch(commentless_pos, len(match_string) - 1))
            commentless_pos += commentless.write(" ")
        else:  # stuff like strings
            commentless_pos += commentless.write(match_string)
        last_pos = match.end()

    commentless.write(text[last_pos:])  # add any remaining text after the last match
    return commentless.getvalue(), comment_map


def find_descriptors(
    text: str,
    descriptors: list[ModifyFoundDescriptor],
    error_if_no_header=False,
    header: Optional[ModifyFoundDescriptor] = None,
    error_if_no_footer=False,
    footer: Optional[ModifyFoundDescriptor] = None,
    ignore_comments=True,
):
    """Returns: The found matches mapped to the descriptors, the footer pos
    (the end of the text if none)"""
    if ignore_comments:
        commentless, comment_map = get_comment_map(text)
    else:
        commentless, comment_map = text, []

    header_matches = (
        find_descriptor_in_text(header, commentless, comment_map, adjust=False) if header is not None else []
    )
    footer_matches = (
        find_descriptor_in_text(footer, commentless, comment_map, adjust=False) if footer is not None else []
    )

    header_pos = 0
    if len(header_matches) > 0:
        _, header_pos, _ = header_matches[0]
    elif header is not None and error_if_no_header:
        raise PluginError(f"Header {header.string} does not exist.")

    # find first footer after the header
    if footer_matches:
        if header_matches:
            footer_pos = next((pos for _, pos, _ in footer_matches if pos >= header_pos), footer_matches[-1].start)
        else:
            _, footer_pos, _ = footer_matches[-1]
    else:
        if footer is not None and error_if_no_footer:
            raise PluginError(f"Footer {footer.string} does not exist.")
        footer_pos = len(commentless)

    found_matches: dict[ModifyFoundDescriptor, list[DescriptorMatch]] = {}
    for descriptor in descriptors:
        matches = find_descriptor_in_text(descriptor, commentless, comment_map, header_pos, footer_pos)
        if matches:
            found_matches.setdefault(descriptor, []).extend(matches)
    return found_matches, adjust_start_end(footer_pos, footer_pos, comment_map)[0]


def write_or_delete_if_found(
    path: Path,
    to_add: Optional[list[ModifyFoundDescriptor]] = None,
    to_remove: Optional[list[ModifyFoundDescriptor]] = None,
    path_must_exist=False,
    create_new=False,
    error_if_no_header=False,
    header: Optional[ModifyFoundDescriptor] = None,
    error_if_no_footer=False,
    footer: Optional[ModifyFoundDescriptor] = None,
    ignore_comments=True,
):
    """
    This function reads the content of a file at the given path and modifies it by either
    adding or removing descriptors (using regex).
    path_must_exist will raise an error if the file does not exist, while create_new will
    always replace the file.
    error_if_no_header/error_if_no_footer will raise errors if the header/footer is not found.
    ignore_comments will ignore comments in the file, possibly breaking the search for matches.

    Returns True if the file was modified.
    """

    changed = False
    to_add, to_remove = to_add or [], to_remove or []

    assert not (path_must_exist and create_new), "path_must_exist and create_new"
    if path_must_exist:
        filepath_checks(path)
    if not create_new and not to_add and not to_remove:
        return False

    if os.path.exists(path) and not create_new:
        text = path.read_text()
        if text and text[-1] not in {"\n", "\r"}:  # add end new line if not there
            text += "\n"
        found_matches, footer_pos = find_descriptors(
            text, to_add + to_remove, error_if_no_header, header, error_if_no_footer, footer, ignore_comments
        )
    else:
        text, found_matches, footer_pos = "", {}, 0

    for descriptor in to_remove:
        matches = found_matches.get(descriptor)
        if matches is None:
            continue
        print(f"Removing {descriptor.string} in {str(path)}")
        for match in matches:
            changed = True
            text = text[: match.start] + text[match.end :]  # Remove match
            diff = match.end - match.start
            for other_match in (other_match for matches in found_matches.values() for other_match in matches):
                if other_match.start > match.start:
                    other_match.start -= diff
                    other_match.end -= diff
            if footer_pos > match.start:
                footer_pos -= diff

    additions = ""
    if text and text[footer_pos - 1] not in {"\n", "\r"}:  # add new line if not there
        additions += "\n"
    for descriptor in to_add:
        if descriptor in found_matches:
            continue
        print(f"Adding {descriptor.string} in {str(path)}")
        additions += f"{descriptor.string}\n"
        changed = True
    text = text[:footer_pos] + additions + text[footer_pos:]

    if changed or create_new:
        path.write_text(text)
        return True
    return False


def to_include_descriptor(include: Path, *alternatives: Path):
    """
    Returns a ModifyFoundDescriptor for an include, string being the include for the path
    while the regex matches for the path or any of the alternatives.
    """
    base_regex = r'\n?#\h*?include\h*?"{0}"'
    regex = base_regex.format(as_posix(include))
    for alternative in alternatives:
        regex += f"|{base_regex.format(as_posix(alternative))}"
    return ModifyFoundDescriptor(f'#include "{as_posix(include)}"', regex)


END_IF_FOOTER = ModifyFoundDescriptor("#endif", r"#\h*?endif")


def write_includes(
    path: Path, includes: Optional[list[Path]] = None, path_must_exist=False, create_new=False, before_endif=False
):
    """
    Write includes to the path. path_must_exist will raise an error if the file does not exist,
    while create_new will always replace the file. before_endif will add the includes before the
    endif if it exists.
    """
    to_add = []
    for include in includes or []:
        to_add.append(to_include_descriptor(include))
    return write_or_delete_if_found(
        path,
        to_add,
        path_must_exist=path_must_exist,
        create_new=create_new,
        footer=END_IF_FOOTER if before_endif else None,
    )


def update_actor_includes(
    header_type: str,
    group_name: str,
    header_dir: Path,
    dir_name: str,
    level_name: str | None = None,  # for backwards compatibility
    data_includes: Optional[list[Path]] = None,
    header_includes: Optional[list[Path]] = None,
    geo_includes: Optional[list[Path]] = None,
):
    """
    Update actor data, header, and geo includes for "Actor" and "Level" header types.
    group_name is used for actors, level_name for levels (tho for backwards compatibility).
    header_dir is the base path where the function expects to find the group/level specific headers.
    dir_name is the actor's folder name.
    """
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

    def write_includes_with_alternate(path: Path, includes: Optional[list[Path]], before_endif=False):
        if includes is None:
            return False
        if header_type == "Level":
            path_and_alternates = [
                [
                    Path(dir_name, include),
                    Path("levels", level_name, dir_name, include),  # backwards compatability
                ]
                for include in includes
            ]
        else:
            path_and_alternates = [[Path(dir_name, include)] for include in includes]
        return write_or_delete_if_found(
            path,
            [to_include_descriptor(*paths) for paths in path_and_alternates],
            path_must_exist=True,
            footer=END_IF_FOOTER if before_endif else None,
        )

    if write_includes_with_alternate(data_path, data_includes):
        print(f"Updated data includes at {header_path}.")
    if write_includes_with_alternate(header_path, header_includes, before_endif=True):
        print(f"Updated header includes at {header_path}.")
    if write_includes_with_alternate(geo_path, geo_includes):
        print(f"Updated geo data at {geo_path}.")


def write_material_headers(decomp: Path, c_include: Path, h_include: Path):
    write_includes(decomp / "src/game/materials.c", [c_include])
    write_includes(decomp / "src/game/materials.h", [h_include], before_endif=True)
