import os, re
from ..utility import getImportData


def getNonLinkActorFilepath(basePath: str, overlayName: str, checkDataPath: bool = False) -> str:
    actorFilePath = os.path.join(basePath, f"src/overlays/actors/{overlayName}/z_{overlayName[4:].lower()}.c")
    actorFileDataPath = f"{actorFilePath[:-2]}_data.c"  # some bosses store texture arrays here

    if checkDataPath and os.path.exists(actorFileDataPath):
        actorFilePath = actorFileDataPath

    return actorFilePath


def getLinkColliderFilepath(basePath: str) -> str:
    return os.path.join(basePath, f"src/overlays/actors/ovl_player_actor/z_player.c")


def getLinkTextureFilepath(basePath: str) -> str:
    return os.path.join(basePath, f"src/code/z_player_lib.c")

    # read included asset data


def ootGetIncludedAssetData(basePath: str, currentPaths: list[str], data: str) -> str:
    includeData = ""
    searchedPaths = currentPaths[:]

    print("Included paths:")

    # search assets
    for includeMatch in re.finditer(r"\#include\s*\"(assets/objects/(.*?))\.h\"", data):
        path = os.path.join(basePath, includeMatch.group(1) + ".c")
        if path in searchedPaths:
            continue
        searchedPaths.append(path)
        subIncludeData = getImportData([path]) + "\n"
        includeData += subIncludeData
        print(path)

        for subIncludeMatch in re.finditer(r"\#include\s*\"(((?![/\"]).)*)\.c\"", subIncludeData):
            subPath = os.path.join(os.path.dirname(path), subIncludeMatch.group(1) + ".c")
            if subPath in searchedPaths:
                continue
            searchedPaths.append(subPath)
            print(subPath)
            includeData += getImportData([subPath]) + "\n"

    # search same directory c includes, both in current path and in included object files
    # these are usually fast64 exported files
    for includeMatch in re.finditer(r"\#include\s*\"(((?![/\"]).)*)\.c\"", data):
        sameDirPaths = [
            os.path.join(os.path.dirname(currentPath), includeMatch.group(1) + ".c") for currentPath in currentPaths
        ]
        sameDirPathsToSearch = []
        for sameDirPath in sameDirPaths:
            if sameDirPath not in searchedPaths:
                sameDirPathsToSearch.append(sameDirPath)

        for sameDirPath in sameDirPathsToSearch:
            print(sameDirPath)

        includeData += getImportData(sameDirPathsToSearch) + "\n"
    return includeData


def ootGetActorDataPaths(basePath: str, overlayName: str) -> list[str]:
    actorFilePath = os.path.join(basePath, f"src/overlays/actors/{overlayName}/z_{overlayName[4:].lower()}.c")
    actorFileDataPath = f"{actorFilePath[:-2]}_data.c"  # some bosses store texture arrays here

    return [actorFileDataPath, actorFilePath]


# read actor data
def ootGetActorData(basePath: str, overlayName: str) -> str:
    actorData = getImportData(ootGetActorDataPaths(basePath, overlayName))
    return actorData


def ootGetLinkTextureData(basePath: str) -> str:
    linkFilePath = os.path.join(basePath, f"src/code/z_player_lib.c")
    actorData = getImportData([linkFilePath])

    return actorData


def ootGetLinkColliderData(basePath: str) -> str:
    linkFilePath = os.path.join(basePath, f"src/overlays/actors/ovl_player_actor/z_player.c")
    actorData = getImportData([linkFilePath])

    return actorData
