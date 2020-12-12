import re

function_map_path = './sm64.us.map'
output_map_path = './output.py'
model_id_path = 'E://sm64/include/model_ids.h'
macros_path = 'E://sm64/include/macro_preset_names.h'
specials_path = 'E://sm64/include/special_preset_names.h'

levelNamePrefixes = ['TTC', 'DDD', 'SL']
uncapitalizedLevels = ['Lll', 'Ttc', 'Jrb', 'Thi', 'Ttm', 'Wdw', 'Wf', 'Rr', 'Bbh', 'Hmc', 'Ddd', 'Bitfs', 'Ssl', 'Ccm', 'Bits', 'Bitdw'] # NOT Bob

def handleUncapitalizedNames(name):
    for uncapitalizedLevel in uncapitalizedLevels:
        capitalizeRegex = ''
        for charVal in uncapitalizedLevel:
            #capitalizeRegex += '[' + charVal.lower() + charVal.upper() + ']'
            capitalizeRegex += charVal
        name = re.sub(capitalizeRegex, uncapitalizedLevel.upper(), name)
    return name

# Special cases are for refresh 8
def parse_enum():
    outfile = open(output_map_path, 'w')

    # Behaviours
    mapfile = open(function_map_path, 'r')
    mapData = mapfile.read()
    mapfile.close()
    bhvList = []

    bhvEnum = 'enumBehaviourPresets = [\n\t(\'Custom\', \'Custom\', \'Custom\'),\n'
    for match in re.finditer( '([a-f0-9]{8})\s*bhv([a-zA-Z0-9]\w*)', mapData):
        name = re.sub(r"([a-z])([A-Z0-9])", r"\1 \2", match.group(2))
        name = re.sub("Mr", "Mr.", name)
        name = re.sub("Mr\. I", "Mr. I ", name)
        name = re.sub("120Stars", "120 Stars", name)
        name = re.sub("1[Uu]p", "1 Up", name)
        name = re.sub("2DRotator", "2D Rotator", name)
        name = re.sub("Bob ", "BOB ", name)
        for levelNamePrefix in levelNamePrefixes:
            if name[:len(levelNamePrefix)] == levelNamePrefix:
                name = name[:len(levelNamePrefix)] + ' ' + name[len(levelNamePrefix):]
        name = handleUncapitalizedNames(name)
        bhvList.append((match.group(1), name))
    
    bhvList.sort(key=lambda tup: tup[1])
    for (val, name) in bhvList:
        bhvEnum += '\t(\'' + val + '\', \'' + name + '\', \'' + name + '\'),\n'
    bhvEnum += ']\n'
    outfile.write(bhvEnum)
    
    # Model IDs
    modelFile = open(model_id_path, 'r')
    modelData = modelFile.read()
    modelFile.close()
    modelList = []
    
    for match in re.finditer( 'MODEL_(\w*)', modelData):
        if match.group(0) == 'MODEL_IDS_H':
            continue
        name = match.group(1)
        name = re.sub("_", " ", name)
        name = name.title()
        name = handleUncapitalizedNames(name)
        name = re.sub("Mr", "Mr.", name)
        name = re.sub("Bob ", "BOB ", name)
        name = re.sub("Sl ", "SL ", name)
        name = re.sub("Dl", "DL", name)
        name = re.sub("Marios", "Mario\\\'s", name)
        name = re.sub("Unknown Ac", "Unknown AC", name)
        name = re.sub(" W ", " With ", name)
        name = re.sub("1[Uu]p", "1 Up", name)
        modelList.append((match.group(0), name))

    modelList.sort(key=lambda tup: tup[1])
    modelEnum = 'enumModelIDs = [\n\t(\'Custom\', \'Custom\', \'Custom\'),\n'
    for (val, name) in modelList:
        modelEnum += '\t(\'' + val + '\', \'' + name + '\', \'' + name + '\'),\n'
    modelEnum += ']\n'
    outfile.write(modelEnum)

    # Specials
    specialsFile = open(specials_path, 'r')
    specialsData = specialsFile.read()
    specialsFile.close()
    specialsList = []

    specialsEnum = 'enumSpecialsNames = [\n\t(\'Custom\', \'Custom\', \'Custom\'),\n'
    for match in re.finditer('special_(\w*)', specialsData):
        name = match.group(1)
        name = re.sub("_", " ", name)
        name = name.title()
        name = handleUncapitalizedNames(name)
        name = re.sub("Mr", "Mr.", name)
        name = re.sub("([0-9])Star", r'\1 Star', name)
        name = re.sub("1[Uu]p", "1 Up", name)
        specialsList.append((match.group(0), name))

    specialsList.sort(key=lambda tup: tup[1])
    for (val, name) in specialsList:
        specialsEnum += '\t(\'' + val + '\', \'' + name + '\', \'' + name + '\'),\n'
    specialsEnum += ']\n'
    outfile.write(specialsEnum)

    # Macros
    macrosFile = open(macros_path, 'r')
    macrosData = macrosFile.read()
    macrosFile.close()
    macrosList = []

    macrosEnum = 'enumMacrosNames = [\n\t(\'Custom\', \'Custom\', \'Custom\'),\n'
    for match in re.finditer('macro_(\w*)', macrosData):
        name = match.group(1)
        name = re.sub("_", " ", name)
        name = name.title()
        name = handleUncapitalizedNames(name)
        name = re.sub("Mr", "Mr.", name)
        name = re.sub("1[Uu]p", "1 Up", name)
        macrosList.append((match.group(0), name))

    macrosList.sort(key=lambda tup: tup[1])
    for (val, name) in macrosList:
        macrosEnum += '\t(\'' + val + '\', \'' + name + '\', \'' + name + '\'),\n'
    macrosEnum += ']\n'
    
    outfile.write(macrosEnum)
    outfile.close()