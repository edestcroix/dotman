#! /usr/bin/env python

import os
import argparse
import shutil as sh
import json
import subprocess as sp
from enum import Enum

class Git(Enum):
    ADD = 0
    COMMIT = 1
    PUSH = 2
    STATUS = 3
    RESTORE = 4
    CUSTOM = 5

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

def deploy(store_dir, dotfiles: tuple, ignored=()):
    for dotfile in dotfiles:
        if dotfile['store_name'] in ignored:
            print(f"Skipping {dotfile['store_name']}")
            continue
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


def retreive(store_dir, dotfiles: tuple, ignored=()):
    store_dir = os.path.expanduser(store_dir)
    for dotfile in dotfiles:
        if dotfile['store_name'] in ignored:
            print(f"Skipping {dotfile['store_name']}")
            continue
        retreive_file(store_dir, dotfile)


def diff(store_dir, dotfiles, ignored=()):
    store_dir = os.path.expanduser(store_dir)
    are_diffs = False
    for dotfile in dotfiles:
        if dotfile['store_name'] in ignored:
            print(f"Skipping {dotfile['store_name']}")
            continue
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
    print_s = lambda x: print(x, end="")

    name_width = max(len(dotfile['store_name']) for dotfile in dotfiles.values())
    short_store_dir = store_dir
    store_dir = os.path.expanduser(store_dir)

    print(f"Managed dotfiles ({len(dotfiles)}):")
    print("-" * (name_width + 60))
    for dotfile in dotfiles.values():
        store_path = f"{store_dir}/{dotfile['store_name']}"
        is_stored = os.path.exists(store_path)
        changes_pending = newer(store_path, os.path.expanduser(dotfile['source_path']))
        print_s('*' if changes_pending else ' ')
        print_s(f"{dotfile['store_name']:{name_width}} ")
        print_s("[")
        print_s("s" if is_stored else " ")
        print_s("d" if dotfile['deploy'] else " ")
        print_s("] ")
        print_s(f"{short_store_dir}/{dotfile['store_name']} <->")
        print(f" {dotfile['source_path']} ")


def clean(store_dir, dotfiles, ignored):
    files = os.listdir(os.path.expanduser(store_dir))
    store_path = os.path.expanduser(store_dir)
    cleaned = 0
    is_dir  = False
    for file in files:
        # check if file is in a store_name value in dotfiles
        if file == (".git") or file in ignored: 
            print(f"Skipping {'directory ' if os.path.isdir(file) else 'file '}{file}")
            continue
        if (
            file not in [dotfile['store_name'] for dotfile in dotfiles.values()]
            and input(f"Remove unmanaged {'directory' if is_dir else 'file'} {file}? (y/N): ") == 'y'
        ):
            print(f"Removing {store_path}/{file}")
            sh.rmtree(f"{store_path}/{file}") if is_dir else os.remove(f"{store_path}/{file}")
            cleaned += 1
    print(f"Cleaned up {cleaned} unmanaged files" if cleaned else "Nothing to do")
        

def get_args():

    parser = argparse.ArgumentParser(description="Dotman is a tool for managing dotfiles")
    parser.add_argument("-c", "--config", help="Specify config file", action="store")
    parser.add_argument("-C", "--clean", help="Remove unmanaged dotfiles", action="store_true")
    parser.add_argument("-l", "--list", help="List managed dotfiles", action="store_true")
    subparsers = parser.add_subparsers(dest="subparser_name")

    deploy_parser = subparsers.add_parser("deploy")
    deploy_parser.add_argument("-a", "--all", help="Deploy all dotfiles", action="store_true")
    deploy_parser.add_argument("-f", "--file", help="Deploy a specific dotfile", action="store")
    deploy_parser.add_argument("-i", "--ignore", help="Ignore a specific dotfile", action="store")

    retreive_parser = subparsers.add_parser("retreive")
    retreive_parser.add_argument("-a", "--all", help="Retreive all dotfiles", action="store_true")
    retreive_parser.add_argument("-f", "--file", help="Retreive a specific dotfile", action="store")
    retreive_parser.add_argument("-i", "--ignore", help="Ignore a specific dotfile", action="store")

    diff_parser = subparsers.add_parser("diff")
    diff_parser.add_argument("-a", "--all", help="Diff all dotfiles", action="store_true")
    diff_parser.add_argument("-f", "--file", help="Diff a specific dotfile", action="store")
    diff_parser.add_argument("-i", "--ignore", help="Ignore a specific dotfile", action="store")


    git_parser = subparsers.add_parser("git")
    git_parser.add_argument("-a", "--add", help="Add dotfiles to dotfile repo", action="store", default="")
    git_parser.add_argument('-r', "--restore", help="restore staged dotfiles", action="store", default='')
    git_parser.add_argument("-c", "--commit", help="commit dotfiles to dotfile repo", action="store", type=str)
    git_parser.add_argument("-p", "--push", help="push dotfiles to dotfile repo", action="store_true")
    git_parser.add_argument("-s", "--status", help="show git status of dotfile repo", action="store_true")
    git_parser.add_argument("-C", "--command", help="run specific git command", action="store")
    # add diff argument
    git_parser.add_argument("-d", "--diff", help="show git diff of dotfile repo", action="store_true")

    return parser.parse_args()


def git(store_dir, action, commit_msg='dotman commit', override_cmd='', add='.'):
    git_path = os.path.expanduser(f"{store_dir}")
    if action == Git.ADD:
        sp.run(["git", "-C", git_path, "add", *add.split(' ')])
    if action == Git.COMMIT:
        if sp.run(["git", "-C", git_path, "diff-index", "--quiet", "HEAD", "--"]).returncode == 0:
            print("No changes to commit")
        else:
            sp.run(["git", "-C", git_path, "commit", "-m", commit_msg]) 

    if action == Git.PUSH:
        output = sp.run(["git", "-C", git_path, "push"], capture_output=True)
        check = output.stderr.decode('utf-8')
        if "Permission denied (publickey)" in check:
            if ssh_key := input(
                "SSH key not found, please enter path to ssh key: "
            ):
                sp.run(["ssh-add", os.path.expanduser(ssh_key)])
            else:
                print("No SSH key provided, exiting")
            sp.run(["git", "-C", git_path, "push"])
        else:
            print(check)

    if action == Git.STATUS:
        sp.run(["git", "-C", git_path, "status"])

    if action == Git.CUSTOM:
        git = sp.run(["git", "-C", git_path, *override_cmd.split(' ')])
        if git.stdout:
            print(git.stdout)


def git_action(config, args):
    # add, commit, and push can be specified together,
    # all others are mutually exclusive
    if args.add and args.commit:
        git(config['store_dir'], Git.ADD, add=args.add)
        git(config['store_dir'], Git.COMMIT, commit_msg=args.commit)
        if args.push:
            git(config['store_dir'], Git.PUSH)

    elif args.commit:
        git(config['store_dir'], Git.COMMIT, commit_msg=args.commit)
    elif args.status:
        git(config['store_dir'], Git.STATUS)
    elif args.push:
        git(config['store_dir'], Git.PUSH)
    elif args.command:
        git(config['store_dir'], Git.CUSTOM, override_cmd=args.command)
    elif args.diff:
        git(config['store_dir'], Git.CUSTOM, override_cmd='diff')
    elif args.add:
        git(config['store_dir'], Git.ADD, add=args.add)
    elif args.restore:
        git(config['store_dir'], Git.CUSTOM, override_cmd=f'restore --staged {args.restore}')
            
def main():
    args = get_args()

    config = ConfigDict(args.config or CONFIG_PATH)

    select_files = lambda x: tuple(config['dotfiles'].values()) if x else (config[f'dotfiles.{args.file}'], )

    if args.subparser_name is None:
        if args.clean: 
            clean(config['store_dir'], config["dotfiles"], config['ignored'])
        elif args.list:
            list(config['store_dir'], config["dotfiles"])
    elif args.subparser_name == "git":
        git_action(config, args)

    else:
        actions = {'deploy': deploy, 'retreive': retreive, 'diff': diff}
        files = select_files (args.all or (args.file is None))
        ignored = args.ignore.split(',') if args.ignore else []
        actions[args.subparser_name](config['store_dir'], files, ignored)


if __name__ == "__main__":
    main()
