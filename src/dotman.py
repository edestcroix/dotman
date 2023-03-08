#! /usr/bin/env python

import os
import argparse
import shutil as sh
import json
import subprocess as sp

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config", "dotman", "config.json")

class ConfigDict():
    def __init__(self, config_file):
        self.__set_key = None;
        # load config file with json
        with open(config_file, "r") as config_file:
            self.__config = json.load(config_file)

    def __getitem__(self, key):
        if self.__set_key:
            return self.__config[self.__set_key][key]    
        # if a dot is in the key, we are trying to access a nested key
        if "." in key:
            keys = key.split(".")
            return self.__config[keys[0]][keys[1]]
        return self.__config[key]

    def ck(self, key):
        # set the current key, so future __getattr__'s retreive
        # only sub keys of the current key' 
        self.__set_key = key
    def rk(self):
        self.__set_key = None


def newer(dir_one, dir_two):
    diff = sp.run(["diff", "-q", dir_one, dir_two], capture_output=True)
    return diff.returncode == 1 and os.path.getmtime(
        dir_one
    ) > os.path.getmtime(dir_two)


def confirm_overwrite(dir_one, dir_two):
    if (
        os.path.exists(dir_one)
        and os.path.exists(dir_two)
        and newer(dir_one, dir_two)
    ):
        print(f"{dir_one} has been modified since {dir_two} was stored")
        if input("Overwrite? [y/N] ").lower() != "y":
            print(f"Skipping {dir_one}")
            return False
    return True



def deploy_file(store_dir, dotfile):
    deploy_path = os.path.expanduser(dotfile['source_path'])
    store_path = f"{os.path.expanduser(store_dir)}/" + dotfile['store_name']
    if not os.path.exists(store_path):
        print(f"Cannot deploy {store_path} because it does not exist")
    elif dotfile["deploy"]:
        # check if deployed files have been modified after the stored ones
        # do a diff and ask if the user wants to overwrite the deployed files
        if not confirm_overwrite(deploy_path, store_path):
            return
        if dotfile['is_dir']:
            if os.path.exists(deploy_path):
                sh.rmtree(deploy_path)
            sh.copytree(store_path, deploy_path)
        else:
            if os.path.exists(deploy_path):
                os.remove(deploy_path)
            # get the directory of the file, and create if it doesn't exits 
            os.makedirs(os.path.dirname(deploy_path), exist_ok=True)
            sh.copy(store_path, deploy_path)
        print(f"Deployed {store_path} to {deploy_path}")

def deploy(store_dir, dotfiles: tuple, single_file=None):
    if single_file:
        dotfile = dotfiles[single_file]
        deploy_file(store_dir, dotfile)
    else:
        for dotfile in dotfiles:
            deploy_file(store_dir, dotfile)


def retreive_file(store_dir, dotfile):
    source_path = os.path.expanduser(dotfile['source_path'])
    store_path = f"{store_dir}/{dotfile['store_name']}"
    if not os.path.exists(source_path):
        print(f"Cannot retreive {source_path} because it does not exist")
    else:
        os.makedirs(store_dir, exist_ok=True)
        if dotfile['is_dir']:
            if os.path.exists(store_path):
                if os.path.isdir(store_path):
                    sh.rmtree(store_path)
                else: os.remove(store_path)
            sh.copytree(source_path, store_path)
        else:
            sh.copy(source_path, store_path)
       # shorten user home directory to ~ 
        temp_souce = source_path.replace(os.path.expanduser("~"), "~")
        temp_store = store_path.replace(os.path.expanduser("~"), "~")
        print(f"Retreived {temp_souce} as {temp_store}")


def retreive(store_dir, dotfiles: tuple, single_file=None):
    store_dir = os.path.expanduser(store_dir)
    if single_file:
        retreive_file(store_dir, dotfiles[single_file])
    else:
        for dotfile in dotfiles:
            retreive_file(store_dir, dotfile)


def diff(store_dir, dotfiles):
    store_dir = os.path.expanduser(store_dir)
    are_diffs = False
    for dotfile in dotfiles:
        store_path = f"{store_dir}/{dotfile['store_name']}"
        source_path = os.path.expanduser(dotfile['source_path'])
        if not os.path.exists(store_path):
            print(f"Cannot diff {store_path} because it does not exist")
            continue
        if not os.path.exists(source_path):
            print(f"Cannot diff {source_path} because it does not exist")
            continue
        diff = sp.run(["diff", "-u", source_path, store_path], capture_output=True)
        if diff.returncode == 1:
            are_diffs = True
            print(diff.stdout.decode("utf-8"))
    if not are_diffs:
        print("All dotfiles are up to date")


def list(store_dir, dotfiles):
    # iterate through dotfiles, check if they are currenty stored, and if deploy is true
    printsingle = lambda x: print(x, end="")

    name_width = max(len(dotfile['store_name']) for dotfile in dotfiles.values())
    short_store_dir = store_dir
    store_dir = os.path.expanduser(store_dir)

    print(f"Managed dotfiles ({len(dotfiles)}):")
    print("-" * (name_width + 60))
    for dotfile in dotfiles.values():
        store_path = f"{store_dir}/{dotfile['store_name']}"
        is_stored = os.path.exists(store_path)
        changes_pending = newer(store_path, os.path.expanduser(dotfile['source_path']))
        printsingle('*' if changes_pending else ' ')
        printsingle(f"{dotfile['store_name']:{name_width}} ")
        printsingle("[")
        printsingle("s" if is_stored else " ")
        printsingle("d" if dotfile['deploy'] else " ")
        printsingle("] ")
        printsingle(f"{short_store_dir}/{dotfile['store_name']} <->")
        print(f" {dotfile['source_path']} ")


def clean(store_dir, dotfiles, ignored):
    files = os.listdir(os.path.expanduser(store_dir))
    cleaned = False
    is_dir  = False
    for file in files:
        file, is_dir = (f"{file}/", True) if os.path.isdir(file) else (file, False)
        # check if file is in a store_name value in dotfiles
        if file == ".git/" or file in ignored: 
            print(f"Skipping {file}")
            continue
        if (
            file not in [dotfile['store_name'] for dotfile in dotfiles.values()]
            and input(f"Remove unmanaged {'directory' if is_dir else 'file'} {file}? (y/N)") == 'y'
        ):
            sh.rmtree(f"{store_dir}/{file}")
            cleaned = True
    print("Cleaned up unmanaged files" if cleaned else "No unmanaged files found")
        
            
def main():
    parser = argparse.ArgumentParser(description="Dotman is a tool for managing dotfiles")
    parser.add_argument("-d", "--deploy", help="Deploy dotfiles", default="")
    parser.add_argument("-r", "--retreive", help="Retreive dotfiles from repo", default="")
    parser.add_argument("-c", "--config", help="Specify config file", action="store")
    parser.add_argument("-D", "--diff", help="View diff between deployed and stored dotfiles", action="store_true")
    parser.add_argument("-l", "--list", help="List all stored dotfiles", action="store_true")
    parser.add_argument("-C", "--clean", help="Remove unmanaged dotfiles", action="store_true")
    args = parser.parse_args()


    if args.deploy and args.retreive:
        print("Cannot deploy and retreive at the same time")
        exit(1)

    config = ConfigDict(args.config or CONFIG_PATH)
    # already checked that deploy and retreive are not both set,
    # so only one of them can have a specified file
    dotfile = (args.deploy or args.retreive) or "all"
    # if dotfile is all operate on all dotfiles, otherwise only the one specified
    files = tuple(config["dotfiles"].values()) if dotfile == "all" else (config[f'dotfiles.{dotfile}'], )
    if args.deploy:
        deploy(config["store_dir"], files)
    elif args.retreive:
        retreive(config["store_dir"], files)

    if args.diff:
        diff(config["store_dir"], config["dotfiles"])

    if args.list:
        list(config["store_dir"], config["dotfiles"])

    if args.clean:
        clean(config["store_dir"], config["dotfiles"], config['ignored_files'])

if __name__ == "__main__":
    main()
