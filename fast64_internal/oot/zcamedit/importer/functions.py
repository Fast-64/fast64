from .classes import CFileImport


def ImportCFile(context, filename):
    im = CFileImport(context)
    return im.ImportCFile(filename)
