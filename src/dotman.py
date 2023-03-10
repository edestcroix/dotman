#! /usr/bin/env python

import os
import argparse
import re
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


class ConfigDict:
    def __init__(self, config_file):
        self.__set_key = None
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

    def flat_dotfiles(self):
        # return a dict with all dotfiles
        dotfiles = self.__config["dotfiles"]
        # flatten the dict, to remove catagories
        flat_dotfiles = {}
        for catagory in dotfiles.keys():
            flat_dotfiles |= dotfiles[catagory]
        return flat_dotfiles


def newer(dir_one, dir_two):
    diff = sp.run(["diff", "-q", dir_one, dir_two], capture_output=True)
    newest = lambda d1, d2: os.path.getmtime(d1) > os.path.getmtime(d2)
    return diff.returncode == 1 and newest(dir_one, dir_two)


def confirm_overwrite(dir_one, dir_two):
    if os.path.exists(dir_one) and os.path.exists(dir_two) and newer(dir_one, dir_two):
        print(f"{dir_one} has been modified since {dir_two} was stored")
        if input("Overwrite? [y/N] ").lower() != "y":
            print(f"Skipping {dir_one}")
            return False
    return True


def copy_file(src, dest, pad_out=0):
    trim_src = re.sub(r"^.*/home/[^/]+", "~", src)
    trim_dest = re.sub(r"^.*/home/[^/]+", "~", dest)
    if os.path.exists(src):
        if not os.path.exists(dirnm := os.path.dirname(dest)):
            os.makedirs(dirnm)
        if os.path.isdir(src):
            sh.copytree(src, dest, dirs_exist_ok=True)
            src = f"{src}/"
            dest = f"{dest}/"
        elif os.path.isfile(src):
            sh.copyfile(src, dest)
        else:
            print(f"Not copying {src} because it is not a file or directory")
        print(f"{trim_src:{pad_out}} -> {trim_dest}")
    else:
        print(f"Cannot copy because {src} does not exist")


def longest_dir_len(dirs):
    # get the longest string from the first element of
    # each tuple in dirs
    dirs = (re.sub(r"^.*/home/[^/]+", "~", dir[0]) for dir in dirs)
    return max(len(s) for s in dirs)


# since the only difference between deploy and retreive is the
# direction of the copy, we can use the same functions for both
# this function prepares the paths to copy, if outgoing is true,
# it swaps the positions of paths in the return list
# that is, if outgoing is true, the paths will be copied from
# the store to the deploy locations, and vice-versa if false
def prepare_copies(store_dir: str, dotfiles: dict, ignored: list, outgoing: bool):
    paths_to_copy = []
    for catagory, cur_dotfiles in dotfiles.items():
        if not os.path.exists(cat_dir := os.path.join(store_dir, catagory)):
            print(
                f"Cannot copy because directory {cat_dir}/ does not exist"
            ) if outgoing else os.makedirs(cat_dir)
            exit(1)

        for dotfile in cur_dotfiles.keys():
            if dotfile in ignored:
                print(f"Skipping {dotfile}")
            else:
                store_path = os.path.join(store_dir, catagory, dotfile)
                deploy_path = os.path.expanduser(cur_dotfiles[dotfile])
                paths_to_copy.append(
                    (store_path, deploy_path) if outgoing else (deploy_path, store_path)
                )
    return paths_to_copy


def deploy(store_dir: str, dotfiles: dict, ignored=()):
    paths_to_copy = prepare_copies(store_dir, dotfiles, ignored, True)
    pad_len = longest_dir_len(paths_to_copy)
    for store_path, deploy_path in paths_to_copy:
        copy_file(store_path, deploy_path, pad_len)


def retreive(store_dir: str, dotfiles: dict, ignored=()):
    paths_to_copy = prepare_copies(store_dir, dotfiles, ignored, False)
    pad_len = longest_dir_len(paths_to_copy)
    for retreive_path, store_path in paths_to_copy:
        copy_file(retreive_path, store_path, pad_len)


def diff(store_dir, dotfiles, ignored=()):
    store_dir = os.path.expanduser(store_dir)
    are_diffs = False
    for catagory, cur_dotfiles in dotfiles.items():
        for name, path in cur_dotfiles.items():
            if name in ignored:
                print(f"Skipping {name}")
                continue
            store_path = f"{store_dir}/{catagory}/{name}"
            source_path = os.path.expanduser(path)
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


def list(store_dir, dotfiles, flat_dotfiles):
    # iterate through dotfiles, check if they are currenty stored, and if deploy is true
    print_s = lambda x: print(x, end="")

    name_width = max(len(name) for name in flat_dotfiles.keys())
    dir_buf = 2

    # remove user portion, can be /home/user or /var/home/user
    short_store_dir = re.sub(r"^.*/home/[^/]+", "~", store_dir)

    print(f"Managed dotfiles ({len(flat_dotfiles)}/{len(dotfiles)}):")
    print("-" * (name_width + 60))
    for catagory, cur_dotfiles in dotfiles.items():
        print(f"{catagory}:")
        cur_store_dir = os.path.join(store_dir, catagory)
        for name, path in cur_dotfiles.items():
            store_path = os.path.join(cur_store_dir, name)
            d_name = f"{name}/" if os.path.isdir(store_path) else name
            deploy_path = os.path.expanduser(path)
            is_stored = os.path.exists(store_path)
            unstored_changes = int(newer(deploy_path, store_path))
            undeployed_changes = int(newer(store_path, deploy_path))
            space = unstored_changes + undeployed_changes
            print_s(f"  {name:{name_width}} ")
            print_s("[s" if is_stored else "[ ")
            print_s("!" if unstored_changes else "")
            print_s("*" if undeployed_changes else "")
            print_s(f"{']':{dir_buf - space}}")
            print_s(f" {short_store_dir}/{catagory}/{d_name}")
            print(f" -> {re.sub(r'^.*/home/[^/]+', '~', deploy_path)}")


def confirm_bulk_clean(dir, files):
    print("Removing untracked files:")
    for file in files:
        print(f"{dir}/{file}")
    return input("Are you sure you want to do this? [y/N] ").lower() in ["y", "yes"]


def clean_file_set(store_dir, to_clean, always_yes, catagory=""):
    cleaned = 0
    for file in to_clean:
        if always_yes or input(
            f"Remove untracked file {catagory}/{file}? [y/N] "
        ).lower() in ["y", "yes"]:
            print(f"Removing {catagory}/{file}")
            if os.path.isdir(os.path.join(store_dir, catagory, file)):
                sh.rmtree(os.path.join(store_dir, catagory, file))
            else:
                os.remove(os.path.join(store_dir, catagory, file))
            cleaned += 1
    return cleaned


def clean(store_dir, dotfiles, ignored, always_yes=False):
    ignored.append(".git")
    cleaned = 0
    get_untracked = lambda dir, files: [
        file for file in dir if file not in files and file not in ignored
    ]
    for catagory in dotfiles.keys():
        try:
            dir_files = os.listdir(os.path.join(store_dir, catagory))
        except FileNotFoundError:
            continue
        untracked = get_untracked(dir_files, dotfiles[catagory].keys())
        if untracked and always_yes and not confirm_bulk_clean(catagory, untracked):
            continue

        cleaned += clean_file_set(store_dir, untracked, always_yes, catagory)
        # check root dir too
    root_dir_files = os.listdir(store_dir)
    untracked = get_untracked(root_dir_files, dotfiles.keys())
    if untracked and always_yes and not confirm_bulk_clean(".", untracked):
        return

    cleaned += clean_file_set(store_dir, untracked, always_yes)

    print(
        f"Cleaned {cleaned} file{'s' if cleaned > 1 else ''}"
    ) if cleaned > 0 else print("Nothing to clean")


def git(
    store_dir, action, commit_msg="dotman commit", override_cmd="", add=".", ssh_path=""
):
    git_path = os.path.expanduser(f"{store_dir}")
    if action == Git.ADD:
        sp.run(["git", "-C", git_path, "add", *add.split(" ")])
    if action == Git.COMMIT:
        if (
            sp.run(
                ["git", "-C", git_path, "diff-index", "--quiet", "HEAD", "--"]
            ).returncode
            == 0
        ):
            print("No changes to commit")
        else:
            sp.run(["git", "-C", git_path, "commit", "-m", commit_msg])

    if action == Git.PUSH:
        output = sp.run(["git", "-C", git_path, "push"], capture_output=True)
        check = output.stderr.decode("utf-8")
        if "Permission denied (publickey)" in check:
            if ssh_path:
                sp.run(["ssh-add", os.path.expanduser(ssh_path)])
            elif ssh_key := input("SSH key not found, please enter path to ssh key: "):
                sp.run(["ssh-add", os.path.expanduser(ssh_key)])
            else:
                print("No SSH key provided, exiting")
            sp.run(["git", "-C", git_path, "push"])
        else:
            print(check)

    if action == Git.STATUS:
        sp.run(["git", "-C", git_path, "status"])

    if action == Git.CUSTOM:
        git = sp.run(["git", "-C", git_path, *override_cmd.split(" ")])
        if git.stdout:
            print(git.stdout)


def git_action(store_dir, args, ssh=""):
    # add, commit, and push can be specified together,
    # all others are mutually exclusive
    if args.add and args.commit:
        git(store_dir, Git.ADD, add=args.add)
        git(store_dir, Git.COMMIT, commit_msg=args.commit)
        if args.push:
            git(store_dir, Git.PUSH)
    elif args.commit:
        git(store_dir, Git.COMMIT, commit_msg=args.commit)
    elif args.status:
        git(store_dir, Git.STATUS)
    elif args.push:
        git(store_dir, Git.PUSH, ssh_path=ssh)
    elif args.command:
        git(store_dir, Git.CUSTOM, override_cmd=args.command)
    elif args.diff:
        git(store_dir, Git.CUSTOM, override_cmd="diff")
    elif args.add:
        git(store_dir, Git.ADD, add=args.add)
    elif args.restore:
        git(store_dir, Git.CUSTOM, override_cmd=f"restore --staged {args.restore}")


    parser = argparse.ArgumentParser(description="Dotman is a tool for managing dotfiles")
    parser.add_argument("-c", "--config", help="Specify config file", action="store")
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

    clean_parser = subparsers.add_parser("clean")
    clean_parser.add_argument("-a", "--all", help="Clean all dotfiles", action="store_true")


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


def main():
    args = get_args()

    config = ConfigDict(args.config or CONFIG_PATH)
    store_dir = os.path.expanduser(config['store_dir'])

    if args.subparser_name is None:
        if args.list:
            list(store_dir, config["dotfiles"], config.flat_dotfiles())
    elif args.subparser_name == "git":
        ssh = config["git"]["ssh_key_path"] if "ssh_key_path" in config["git"] else ''
        git_action(store_dir, args, ssh)
    elif args.subparser_name == "clean":
        clean(store_dir, config["dotfiles"], config["ignored_files"], args.all)
    else:
        actions = {"deploy": deploy, "retreive": retreive, "diff": diff}

        # if args.files is specified, filter out the dotfiles dict to only contain
        # the specified files, still in the same catagories
        if file := args.file:
            file = file.split(',')
            dotfiles = {
                catagory: {k: v for k, v in dotfiles_set.items() if k in file}
                for catagory, dotfiles_set in config['dotfiles'].items()
            }
        else:
            dotfiles = config['dotfiles']

        ignored = args.ignore.split(',') if args.ignore else []
        actions[args.subparser_name](store_dir, dotfiles, ignored=ignored)


if __name__ == "__main__":
    main()
