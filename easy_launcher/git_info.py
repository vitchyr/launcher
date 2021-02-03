import os
import os.path as osp
from collections import namedtuple

import doodad
from easy_launcher import config

GitInfo = namedtuple(
    'GitInfo',
    [
        'directory',
        'code_diff',
        'code_diff_staged',
        'commit_hash',
        'branch_name',
    ],
)


def save_git_info(logdir, git_infos):
    if git_infos is not None:
        for (
                directory, code_diff, code_diff_staged, commit_hash, branch_name
        ) in git_infos:
            if directory[-1] == '/':
                diff_file_name = directory[1:-1].replace("/", "-") + ".patch"
                diff_staged_file_name = (
                        directory[1:-1].replace("/", "-") + "_staged.patch"
                )
            else:
                diff_file_name = directory[1:].replace("/", "-") + ".patch"
                diff_staged_file_name = (
                        directory[1:].replace("/", "-") + "_staged.patch"
                )
            if code_diff is not None and len(code_diff) > 0:
                with open(osp.join(logdir, diff_file_name), "w") as f:
                    f.write(code_diff + '\n')
            if code_diff_staged is not None and len(code_diff_staged) > 0:
                with open(osp.join(logdir, diff_staged_file_name), "w") as f:
                    f.write(code_diff_staged + '\n')
            with open(osp.join(logdir, "git_infos.txt"), "a") as f:
                f.write("directory: {}".format(directory))
                f.write('\n')
                f.write("git hash: {}".format(commit_hash))
                f.write('\n')
                f.write("git branch name: {}".format(branch_name))
                f.write('\n\n')


def get_git_info():
    try:
        import git
        doodad_path = osp.abspath(osp.join(
            osp.dirname(doodad.__file__),
            os.pardir
        ))
        dirs = config.CODE_DIRS_TO_MOUNT + [doodad_path]

        git_infos = []
        for directory in dirs:
            # Idk how to query these things, so I'm just doing try-catch
            try:
                repo = git.Repo(directory)
                try:
                    branch_name = repo.active_branch.name
                except TypeError:
                    branch_name = '[DETACHED]'
                git_infos.append(GitInfo(
                    directory=directory,
                    code_diff=repo.git.diff(None),
                    code_diff_staged=repo.git.diff('--staged'),
                    commit_hash=repo.head.commit.hexsha,
                    branch_name=branch_name,
                ))
            except git.exc.InvalidGitRepositoryError:
                pass
    except ImportError:
        git_infos = None
    return git_infos
