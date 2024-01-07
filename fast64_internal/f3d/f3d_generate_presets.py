import os

basePath = "presets/f3d"
data = ""
presetList = "material_presets = {\n"

for subdir in os.listdir(basePath):
    subPath = os.path.join(basePath, subdir)
    if subdir != "__pycache__" and subdir != "user" and os.path.isdir(subPath):
        presetList += '\t"' + subdir + '" : {\n'
        for filename in os.listdir(subPath):
            presetPath = os.path.join(subPath, filename)
            if os.path.isfile(presetPath):
                print(presetPath)
                presetFile = open(presetPath, "r")
                presetData = presetFile.read()
                presetFile.close()

                data += filename[:-3] + " = '''\n" + presetData + "'''\n\n"
                presetList += '\t\t"' + filename[:-3] + '" : ' + filename[:-3] + ",\n"
        presetList += "\t},\n"

presetList += "}\n"

data += presetList

outFile = open("f3d_material_presets.py", "w")
outFile.write(data)
outFile.close()
