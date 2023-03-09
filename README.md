# Dotman
A dotfiles manager

## Installing
Download from the releases or build from source:
```
pip3 install setuptools
python -m build
pip3 install ./dist/dotman-0.0.1-py3-none-any.whl
```

## Usage
`dotman` reads its config from a `.config/dotman/config.json` file to determine which files to manage. It does not create this file for you, so you must create it yourself.

### Config
The configuration file is a JSON file with the following structure:
```json
{
    "store_dir": "/path/to/store/dotfiles",
    "ignored_files": [
        "file1",
        "file2"
    ],
    "git": {
        "ssh-key-path": "/path/to/ssh/key", (optional)
    }
    "dotfiles":{
        "category1": {
            "file1": "/path/to/file1",
            "file2": "/path/to/file2"
        },
        "category2": {
            "file3": "/path/to/file3",
            "file4": "/path/to/file4"
        }
    }
}
```
Currently, at least one category must be defined. Files will be stored in directories named after the category they are in,
under the filename specified by their key in the config file.
(eg. `dotfiles/category1/file1`). Files can be either regular files or directories, and file paths can be absolute or relative to the user's home directory (prefixed with '`~/`').

### Commands
`dotman` has the following commands:
- `dotman -h` or `dotman --help` - shows the help message.
- `dotman -l` or `dotman --list` - lists all files in the config file, along with their respective locations, and whether or not the stored file is different from the deployed file.
- `dotman deploy` - deploys all files in the config file to their respective locations, overwriting any existing files.
    - `-a` or `--all` - deploys all files. This is the default behaviour when no files are specified.
    - `-f` or `--file` - deploys the specified file. For multiple files, pass a comma-separated list of files.
    - `-i` or `--ignore` - ignore the specified file. For multiple files, pass a space-separated list of files. (Yes, this is inconsistent with the `-f` flag, I'll fix it later)
- `dotman retrieve` - retrieves all files in the config file from their respective locations, overwriting any existing files. It supports the same flags as `dotman deploy`.
- `dotman diff` - shows the differences between the stored files and the deployed files. It supports the same flags as `dotman deploy` and `dotman retrieve`.
- `dotman clean` Cleans up the store directory, removing any files that are not in the config file. Confirms deletion for each file one by one, unless `-a` or `--all` is specified, in which case it will confirm once for each category.
- `dotman git` allows controlling the git repo in the dotfile store directory. The git repo must be initialized manually before using this command.
    - `-a` or `--add` - adds files to the git repo. For multiple files, pass a space-separated list of files. For all files, pass `-a '.'` 
    - `-c` or `--commit` - commits staged files to the git repo. Pass a commit message as the argument.
    - `-p` or `--push` - pushes the current branch to the remote. Requires a remote to be set up manually.
    - `-s` or `--status` - shows the status of the git repo.
    - `-r` or `--restore` - works like `-a`, but unstages files instead of staging them.
    - `-C` or `--Command` runs a custom git command. Pass the command as the argument, without `git`. For example, `dotman git -C 'checkout master'` will run `git checkout master` in the dotfile store directory.
