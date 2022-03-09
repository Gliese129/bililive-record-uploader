import json
import os
from shutil import copy, rmtree
import yaml


def YmlReader(path: str) -> dict:
    """ Read yaml file

    :param path: file path
    :return: dictionary
    """
    with open(path, 'r', encoding='utf-8') as f:
        result = yaml.load(f.read(), Loader=yaml.Loader)
    return result


def ReadJson(path: str) -> dict:
    """ Read json file

    :param path: file path
    :return: json dictionary
    """
    if not os.path.exists(path):
        folder_path = os.path.dirname(path)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('{}')
    with open(path, 'r', encoding='utf-8') as f:
        result = json.load(f)
    return result


def WriteDict(path: str, obj: dict):
    """  Write dict to json file

    :param path: file path
    :param obj: object need to write
    """
    if not os.path.exists(path):
        folder_path = os.path.dirname(path)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f)


def CopyFiles(files: list[str], target: str, types: list[str]) -> list[str]:
    """ Copy files to target folder

    :param files: files need to copy(no extension)
    :param target: target folder
    :param types: file extensions
    :return: files copied(no extension)
    """
    if not os.path.exists(target):
        os.makedirs(target)
    new_files = []
    for file in files:
        for file_type in types:
            copy(src=file + '.' + file_type, dst=target)
        new_files.append(os.path.join(target, os.path.split(file)[1]))
    return new_files


def CopyFile(file: str, target: str) -> str:
    """ Copy file to target folder

    :param file: files need to copy
    :param target: target folder
    :return: files copied
    """
    if not os.path.exists(target):
        os.makedirs(target)
    new_file = os.path.join(target, os.path.split(file)[1])
    if not os.path.exists(new_file):
        copy(src=file, dst=target)
    return new_file


def DeleteFolder(folder: str):
    """ Delete a folder and files in it

    :param folder: folder path
    """
    if os.path.exists(folder):
        rmtree(folder)


def DeleteFiles(file_stems: list[str], types: list[str]):
    """ Delete files

    :param file_stems: files need to delete(no extension)
    :param types: file extensions
    """
    for file_stem in file_stems:
        for file_type in types:
            if os.path.exists(file_stem + '.' + file_type):
                file = f'{file_stem}.{file_type}'
                os.remove(file)
