#! /usr/bin/env python

import os
import argparse
import re
import shutil as sh
import json
import subprocess as sp


CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config", "dotman", "config.json")
BACKUP_PATH = os.path.join(os.path.expanduser("~"), ".local/share", "dotman")


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


# diff the stored file with the deploy file
# if returns the result of the diff if there is a diff
# None otherwise
def diff_status(store, deploy):
    diff = sp.run(["diff", "-bur", store, deploy], capture_output=True)
    return diff.stdout.decode("utf-8")


def confirm_overwrite(dir_one, dir_two):
    if (
        os.path.exists(dir_one)
        and os.path.exists(dir_two)
        and diff_status(dir_one, dir_two)
    ):
        print(
            f"{collapse_user(dir_one)} has been modified since {collapse_user(dir_two)} was stored"
        )
        if input("Overwrite? [y/N] ").lower() != "y":
            print(f"Skipping {collapse_user(dir_one)}")
            return False
    return True


def collapse_user(string):
    return re.sub(r"^.*/home/[^/]+", "~", string)


def copy_file(src, dest, pad_out=0, silent=False):
    s_print = lambda *args: None if silent else print(*args)
    trim_src = collapse_user(src)
    trim_dest = collapse_user(dest)
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
            s_print(f"Not copying {src} because it is not a file or directory")
        s_print(f"{trim_src:{pad_out}} -> {trim_dest}")
    else:
        s_print(f"Cannot copy because {src} does not exist")


def longest_dir_len(dirs):
    # get the longest string from the first element of
    # each tuple in dirs
    dirs = (collapse_user(dir[0]) for dir in dirs)
    return max(len(s) for s in dirs)


# since the only difference between deploy and retreive is the
# direction of the copy, we can use the same functions for both.
# this function prepares the paths to copy, if outgoing is true,
# it swaps the positions of paths in the return list
# that is, if outgoing is true, the paths will be copied from
# the store to the deploy locations, and vice-versa if false
# additionally, when outgoing, asks for comfirmation before copying if
# the files have been modified since they were last stored
# (assumed use of dotman is that the store-files shouldn't be edited,
#   so if the files are different, assume it's the deployed one)
def prepare_copies(
    store_dir: str, dotfiles: dict, ignored: list, outgoing: bool, backup=None
):
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

                if backup:
                    deploy_path = os.path.join(backup, catagory, dotfile)
                else:
                    deploy_path = os.path.expanduser(cur_dotfiles[dotfile])
                # confirm overwrite if both files exist and the deployment
                # file has been modified since the last time the store file
                # was updated
                if outgoing and confirm_overwrite(deploy_path, store_path):
                    paths_to_copy.append((store_path, deploy_path))
                elif not outgoing:
                    paths_to_copy.append((deploy_path, store_path))

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
            diff = sp.run(["diff", "-u", store_path, source_path], capture_output=True)
            if diff.returncode == 1:
                are_diffs = True
                print(diff.stdout.decode("utf-8"))
    if not are_diffs:
        print("All dotfiles are up to date")


def list_dotfiles(store_dir, dotfiles, flat_dotfiles):
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
            state = 1 if diff_status(store_path, deploy_path) else 0
            print_s(f"  {name:{name_width}} ")
            print_s("[s" if is_stored else "[ ")
            print_s("<" if state else "")
            print_s(f"{']':{dir_buf - state}}")
            print_s(f" {short_store_dir}/{catagory}/{d_name}")
            print(f" -> {re.sub(r'^.*/home/[^/]+', '~', deploy_path)}")


def clean_file_set(store_dir, to_clean, always_yes):
    cleaned = 0
    for file in to_clean:
        short_file = collapse_user(file)
        if always_yes or input(
            f"Remove untracked file {short_file}? (y/N): "
        ).lower() in ["y", "yes"]:
            print(f"Removing {short_file}")
            if os.path.isdir(os.path.join(store_dir, file)):
                sh.rmtree(os.path.join(store_dir, file))
            else:
                os.remove(os.path.join(store_dir, file))
            cleaned += 1
    print(f"Removed {cleaned} untracked files")


def get_untracked(store_dir, dir, ignored):
    return [f"{store_dir}/{file}" for file in dir if file not in ignored]


def clean(store_dir, dotfiles, ignored, all_one_shot=False, verbose=False):
    ignored.append(".git")
    untracked = []
    for catagory in dotfiles.keys():
        try:
            dir_files = os.listdir(os.path.join(store_dir, catagory))
        except FileNotFoundError:
            continue
        cur_ignored = ignored + list(dotfiles[catagory].keys())
        untracked += get_untracked(f"{store_dir}/{catagory}", dir_files, cur_ignored)

    cur_ignored = ignored + list(dotfiles.keys())
    untracked += get_untracked(store_dir, os.listdir(store_dir), cur_ignored)

    if verbose:
        print("Ignored files:")
        for file in ignored:
            print(file)

    if all_one_shot and untracked:
        print("Removing untracked files:")
        for file in untracked:
            print(collapse_user(file))
        if input("Are you sure (y/N): ").lower() in ("y" or "yes"):
            clean_file_set(store_dir, untracked, True)
    elif untracked:
        clean_file_set(store_dir, untracked, False)
    else:
        print("No untracked files to clean")


def git(store_dir, cmd="", ssh_path="", commit_msg=""):
    cmd = cmd.strip()
    git_path = os.path.expanduser(f"{store_dir}")
    if cmd == "push":
        git = sp.run(
            ["git", "-C", git_path, "push", "origin", "main"], capture_output=True
        )
    elif commit_msg:
        git = sp.run(
            ["git", "-C", git_path, *cmd.split(" "), commit_msg], capture_output=True
        )
    else:
        git = sp.run(["git", "-C", git_path, *cmd.split(" ")], capture_output=True)

    git_err = git.stderr.decode("utf-8").strip()
    if git_output := git.stdout.decode("utf-8").strip():
        print(git_output)

    if "Permission denied (publickey)" in git_err:
        if ssh_path:
            sp.run(["ssh-add", os.path.expanduser(ssh_path)])
        elif ssh_key := input("SSH key not found, please enter path to ssh key: "):
            sp.run(["ssh-add", os.path.expanduser(ssh_key)])
        else:
            print("No SSH key provided, exiting")
        sp.run(["git", "-C", git_path, "push", "origin", "main"])

    elif git_err:
        print(git_err)


def git_action(store_dir, args, ssh=""):
    if args.add or args.commit or args.push:
        # add, commit, and push can be specified together,
        # all others are mutually exclusive
        if args.add:
            git(store_dir, f"add {args.add}")
        if args.commit:
            git(store_dir, "commit -m", commit_msg=args.commit)
        if args.push:
            git(store_dir, "push", ssh_path=ssh)
    # every other action is mutually exclusive
    elif args.status:
        git(store_dir, "status")
    elif args.diff:
        git(store_dir, "diff")
    elif args.restore:
        git(store_dir, f"restore --staged {args.restore}")
    elif args.command:
        git(store_dir, args.command)


def get_args():
    parser = argparse.ArgumentParser(
        description="Dotman is a tool for managing dotfiles"
    )
    cur_parser = parser
    # simple wrapper to make adding arguments easier
    add_arg = lambda arg, **kwargs: cur_parser.add_argument(arg[1:3], arg, **kwargs)

    # global arguments
    add_arg("--config", help="Specify config file", action="store")
    add_arg("--list", help="List managed dotfiles", action="store_true")

    # subparsers
    subparsers = parser.add_subparsers(dest="subparser_name")

    # deploy, retreive, diff share the exact same arguments.
    for parser_name in ["deploy", "retreive", "diff"]:
        cur_parser = subparsers.add_parser(parser_name)
        add_arg("--all", help="Operate on all dotfiles", action="store_true")
        add_arg("--file", help="Operate on a specific dotfile", action="store")
        add_arg("--ignore", help="Ignore a specific dotfile", action="store")

    cur_parser = subparsers.add_parser("clean")
    add_arg("--all", help="Clean all dotfiles", action="store_true")
    add_arg("--ignore", help="Ignore specific dotfiles", action="store")
    add_arg("--verbose", help="Show ignored files", action="store_true")

    cur_parser = subparsers.add_parser("git")
    add_arg("--add", help="Add dotfiles to dotfile repo", action="store", default="")
    add_arg("--restore", help="restore staged dotfiles", action="store", default="")
    add_arg("--commit", help="commit dotfiles to dotfile repo", action="store")
    add_arg("--push", help="push dotfiles to dotfile repo", action="store_true")
    add_arg("--status", help="show git status of dotfile repo", action="store_true")
    add_arg("--diff", help="show git diff of dotfile repo", action="store_true")

    # this one can't be added with add_arg because it's single letter flag
    # needs to be capitalized.
    cur_parser.add_argument(
        "-C", "--command", help="run specific git command", action="store"
    )

    return parser.parse_args()


def main():
    args = get_args()

    config = ConfigDict(args.config or CONFIG_PATH)
    store_dir = os.path.expanduser(config["store_dir"])

    if args.subparser_name is None:
        if args.list:
            list_dotfiles(store_dir, config["dotfiles"], config.flat_dotfiles())
    elif args.subparser_name == "git":
        ssh = (
            config["git"]["ssh_key_path"]
            if config["git"] and "ssh_key_path" in config["git"]
            else ""
        )
        git_action(store_dir, args, ssh)
    elif args.subparser_name == "clean":
        ignore = args.ignore.split(",") if args.ignore else []
        ignore = ignore + config["ignored_files"]
        clean(store_dir, config["dotfiles"], ignore, args.all, args.verbose)
    else:
        actions = {"deploy": deploy, "retreive": retreive, "diff": diff}

        # if args.files is specified, filter out the dotfiles dict to only contain
        # the specified files, still in the same catagories
        if file := args.file:
            file = file.split(",")
            dotfiles = {
                catagory: {k: v for k, v in dotfiles_set.items() if k in file}
                for catagory, dotfiles_set in config["dotfiles"].items()
            }
        else:
            dotfiles = config["dotfiles"]

        ignored = args.ignore.split(",") if args.ignore else []
        actions[args.subparser_name](store_dir, dotfiles, ignored=ignored)


if __name__ == "__main__":
    main()
