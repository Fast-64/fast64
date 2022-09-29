from ....utility import CData

from ...oot_level_classes import OOTScene, OOTLight
from ...oot_utility import indent


def ootGetVectorToC(vector: tuple[int, int, int]):
    """Returns a string from 3 integers"""
    return ", ".join([f"{v}" for v in vector])


def ootGetLightDirectionToC(vector: tuple[int, int, int]):
    """Returns a string from 3 integers but apply signed int behavior"""
    return ", ".join([f"{v - 0x100 if v > 0x7F else v}" for v in vector])


def ootLightToC(light: OOTLight):
    """Returns the light settings array's data"""
    vectors = [
        (light.ambient, "Ambient Color", ootGetVectorToC),
        (light.diffuseDir0, "Diffuse0 Direction", ootGetLightDirectionToC),
        (light.diffuse0, "Diffuse0 Color", ootGetVectorToC),
        (light.diffuseDir1, "Diffuse1 Direction", ootGetLightDirectionToC),
        (light.diffuse1, "Diffuse1 Color", ootGetVectorToC),
        (light.fogColor, "Fog Color", ootGetVectorToC),
    ]
    fogData = [
        (light.getBlendFogShort(), "Blend Rate & Fog Near"),
        (f"{light.fogFar}", "Fog Far"),
    ]
    lightData = (
        (indent + "{\n")
        + "".join([indent * 2 + f"{'{ ' + vecToC(vector) + ' },':21} // {desc}\n" for vector, desc, vecToC in vectors])
        + "".join([indent * 2 + f"{fogValue + ',':21} // {fogDesc}\n" for fogValue, fogDesc in fogData])
        + (indent + "},\n")
    )

    return lightData


def ootLightSettingsToC(scene: OOTScene, headerIndex: int):
    """Returns the light settings array"""
    lightSettingsData = CData()
    lightName = f"LightSettings {scene.lightListName(headerIndex)}[{len(scene.lights)}]"

    # .h
    lightSettingsData.header = f"extern {lightName};\n"

    # .c
    lightSettingsData.source = (
        (f"LightSettings {lightName}" + " = {\n") + "".join([ootLightToC(light) for light in scene.lights]) + "};\n\n"
    )

    return lightSettingsData
