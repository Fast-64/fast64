from .....utility import CData
from ....oot_level_classes import OOTScene, OOTLight
from ...data import indent


def getColorValues(vector: tuple[int, int, int]):
    """Returns a string from 3 integers"""
    return ", ".join([f"{v}" for v in vector])


def getDirectionValues(vector: tuple[int, int, int]):
    """Returns a string from 3 integers but apply signed int behavior"""
    return ", ".join([f"{v - 0x100 if v > 0x7F else v}" for v in vector])


def getLightSettingsEntry(light: OOTLight, lightMode: str, index: int):
    """Returns the light settings array's data"""
    vectors = [
        (light.ambient, "Ambient Color", getColorValues),
        (light.diffuseDir0, "Diffuse0 Direction", getDirectionValues),
        (light.diffuse0, "Diffuse0 Color", getColorValues),
        (light.diffuseDir1, "Diffuse1 Direction", getDirectionValues),
        (light.diffuse1, "Diffuse1 Color", getColorValues),
        (light.fogColor, "Fog Color", getColorValues),
    ]

    fogData = [
        (light.getBlendFogNear(), "Blend Rate & Fog Near"),
        (f"{light.fogFar}", "Fog Far"),
    ]

    lightDescs = ["Dawn", "Day", "Dusk", "Night"]
    if lightMode == "0x00":
        lightDesc = f"// {lightDescs[index]} Lighting\n"
    else:
        lightDesc = f"// {'Indoor' if lightMode == '0x01' else 'Custom'} n°{index + 1} Lighting\n"

    lightData = (
        (indent + "{\n")
        + (indent * 2 + lightDesc)
        + "".join([indent * 2 + f"{'{ ' + vecToC(vector) + ' },':21} // {desc}\n" for vector, desc, vecToC in vectors])
        + "".join([indent * 2 + f"{fogValue + ',':21} // {fogDesc}\n" for fogValue, fogDesc in fogData])
        + (indent + "},\n")
    )

    return lightData


def convertLightSettings(outScene: OOTScene, headerIndex: int):
    """Returns the light settings array"""
    lightSettingsData = CData()
    lightName = f"LightSettings {outScene.getLightSettingsListName(headerIndex)}[{len(outScene.lights)}]"

    # .h
    lightSettingsData.header = f"extern {lightName};\n"

    # .c
    lightSettingsData.source = (
        (lightName + " = {\n")
        + "".join([getLightSettingsEntry(light, outScene.lightMode, i) for i, light in enumerate(outScene.lights)])
        + "};\n\n"
    )

    return lightSettingsData
