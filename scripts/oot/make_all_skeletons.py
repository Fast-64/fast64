import re
import subprocess
import sys
import shutil

from pathlib import Path
from typing import List

"""
A test script to try import skeletons (and optionally animations) in a decomp
folder, generating .blend files for file, and report on successes & failures.

WARNING: the specified output folder is unconditionally deleted before generating 
new output!

Usage:
python3 make_all_skeletons.py <path to decomp> <output folder>  ["1" to import animations too]

Example:
python3 make_all_skeletons.py ~/git/mm blend-files 1 
"""


def main():
    filePaths: List[Path] = []
    failFiles: List[Path] = []
    successFiles: List[Path] = []

    print(f"args {sys.argv}")
    decompPath = Path(sys.argv[1])
    outputPath = Path(sys.argv[2])
    importAnimations = len(sys.argv) > 3 and sys.argv[3] == "1"

    # Delete the output folder if it already exists
    if outputPath.exists():
        shutil.rmtree(outputPath)

    # populate filePaths with paths to all files in the decomp
    # that appear to contain a skeleton
    for inPath in (Path(decompPath) / "assets" / "objects").rglob("*.c"):
        with open(inPath, "r") as file:
            contents = file.read()
            if re.search(r"(Flex)?SkeletonHeader\s*(?P<name>[A-Za-z0-9\_]+)\s*=", contents) is not None:
                filePaths.append(inPath)

    for i, inPath in enumerate(filePaths):
        # Generate the output path as a subdir in the output folder with the same structure
        #  as the file's location in the decomp
        outPath: Path = outputPath.joinpath(*inPath.parts[len(decompPath.parts) :]).with_suffix(".blend")
        objectName = inPath.parts[-2]

        # Make sure all the subdirs exist
        outPath.parent.mkdir(parents=True, exist_ok=True)

        # Run make_skeletons.py in blender to build the .blend file
        args = [
            "blender",
            "--background",
            "--python-exit-code",  # note: python-exit-code MUST come before python, or you'll always get 0!
            "1",
            "--python",
            "make_skeletons.py",
            "--",
            decompPath,
            inPath,
            outPath,
            objectName,
        ]

        if importAnimations:
            args.append("1")

        res = subprocess.run(args)

        if res.returncode == 0:
            successFiles.append(inPath)
        else:
            failFiles.append(inPath)
            print("! Failed")

        # Report progress
        print(f"Progress: {i + 1}/{len(filePaths)} done")
        percentSuccessful = round(len(successFiles) / len(filePaths) * 100, 1)
        percentFailed = round(len(failFiles) / len(filePaths) * 100, 1)
        print(f"\tSuccessful:  {len(successFiles)} {percentSuccessful:.1f}%")
        print(f"\tFailed:  {len(failFiles)} {percentFailed:.1f}%", flush=True)

    # After all imports have been tried, list all the files with any failures
    print("Files with failures:")
    print("\n".join(str(f) for f in failFiles))


if __name__ == "__main__":
    main()
