import json
import os
import os.path as osp
import pickle
import random
import sys
import time
import uuid

import __main__ as main
import datetime
import dateutil.tz
import numpy as np
from easy_launcher.git_info import get_git_info, save_git_info
from easy_launcher import util

from easy_logger import logger
import pythonplusplus.python_util as ppp
from easy_launcher import config


ec2_okayed = False
gpu_ec2_okayed = False
slurm_config = None

import doodad.mount as mount
from doodad.slurm.slurm_util import SlurmConfig
CODE_MOUNTS = [
    mount.MountLocal(local_dir=util.REPO_DIR, pythonpath=True),
]
for code_dir in config.CODE_DIRS_TO_MOUNT:
    CODE_MOUNTS.append(mount.MountLocal(local_dir=code_dir, pythonpath=True))

NON_CODE_MOUNTS = []
for non_code_mapping in config.DIR_AND_MOUNT_POINT_MAPPINGS:
    NON_CODE_MOUNTS.append(mount.MountLocal(**non_code_mapping))

SSS_CODE_MOUNTS = []
SSS_NON_CODE_MOUNTS = []
if hasattr(config, 'SSS_DIR_AND_MOUNT_POINT_MAPPINGS'):
    for non_code_mapping in config.SSS_DIR_AND_MOUNT_POINT_MAPPINGS:
        SSS_NON_CODE_MOUNTS.append(mount.MountLocal(**non_code_mapping))
if hasattr(config, 'SSS_CODE_DIRS_TO_MOUNT'):
    for code_dir in config.SSS_CODE_DIRS_TO_MOUNT:
        SSS_CODE_MOUNTS.append(
            mount.MountLocal(local_dir=code_dir, pythonpath=True)
        )

target_mount = None
_global_target_mount = None
_global_is_first_launch = True
_global_n_tasks_total = 0
_global_launch_uuid = str(uuid.uuid4())


def run_experiment(
        method_call,
        target_script=None,
        mode='local',
        exp_name='default',
        variant=None,
        exp_id=0,
        use_gpu=False,
        gpu_id=0,
        seed=None,
        # logger info
        prepend_date_to_exp_name=False,
        snapshot_mode='last',
        snapshot_gap=1,
        base_log_dir=None,
        local_input_dir_to_mount_point_dict=None,  # TODO(vitchyr): test this
        # local settings
        skip_wait=False,
        # ec2 settings
        sync_interval=180,
        region='us-east-1',
        instance_type=None,
        spot_price=None,
        verbose=False,
        trial_dir_suffix=None,
        num_exps_per_instance=1,
        # sss settings
        time_in_mins=None,
        # ssh settings
        ssh_host=None,
        # gcp
        gcp_kwargs=None,
):
    """
    Usage:
    ```
    def foo(variant):
        x = variant['x']
        y = variant['y']
        logger.log("sum", x+y)
    variant = {
        'x': 4,
        'y': 3,
    }
    run_experiment(foo, variant, exp_name="my-experiment")
    ```
    Results are saved to
    `base_log_dir/<date>-my-experiment/<date>-my-experiment-<unique-id>`
    By default, the base_log_dir is determined by
    `config.LOCAL_LOG_DIR/`
    :param method_call: a function that takes in a dictionary as argument
    :param mode: A string:
     - 'local'
     - 'local_docker'
     - 'ec2'
     - 'here_no_doodad': Run without doodad call
    :param exp_name: name of experiment
    :param seed: Seed for this specific trial.
    :param variant: Dictionary
    :param exp_id: One experiment = one variant setting + multiple seeds
    :param prepend_date_to_exp_name: If False, do not prepend the date to
    the experiment directory.
    :param use_gpu:
    :param snapshot_mode: See easy_logger.logging.logger
    :param snapshot_gap: See easy_logger.logging.logger
    :param base_log_dir: Will over
    :param sync_interval: How often to sync s3 data (in seconds).
    :param local_input_dir_to_mount_point_dict: Dictionary for doodad.
    :param ssh_host: the name of the host you want to ssh onto, should correspond to an entry in
    config.py of the following form:
    SSH_HOSTS=dict(
        ssh_host=dict(
            username='username',
            hostname='hostname/ip address',
        )
    )
    - if ssh_host is set to None, you will use ssh_host specified by
    config.SSH_DEFAULT_HOST
    :return:
    """
    try:
        import doodad
        import doodad.mode
        import doodad.ssh
    except ImportError:
        print("Doodad not set up! Running experiment here.")
        mode = 'here_no_doodad'
    global ec2_okayed
    global gpu_ec2_okayed
    global slurm_config
    global _global_target_mount
    global _global_is_first_launch
    global _global_n_tasks_total

    """
    Sanitize inputs as needed
    """
    if seed is None:
        seed = random.randint(0, 100000)
    if variant is None:
        variant = {}
    if mode == 'ssh' and base_log_dir is None:
        base_log_dir = config.SSH_LOG_DIR
    if base_log_dir is None:
        if mode == 'sss':
            base_log_dir = config.SSS_LOG_DIR
        else:
            base_log_dir = config.LOCAL_LOG_DIR

    for key, value in ppp.recursive_items(variant):
        # This check isn't really necessary, but it's to prevent myself from
        # forgetting to pass a variant through dot_map_dict_to_nested_dict.
        if "." in key:
            raise Exception(
                "Variants should not have periods in keys. Did you mean to "
                "convert {} into a nested dictionary?".format(key)
            )
    variant['base_exp_name'] = exp_name
    if prepend_date_to_exp_name:
        exp_name = time.strftime("%y-%m-%d") + "-" + exp_name
    variant['seed'] = seed
    variant['exp_id'] = str(exp_id)
    variant['exp_name'] = str(exp_name)
    variant['instance_type'] = str(instance_type)

    git_infos = get_git_info()
    run_experiment_kwargs = dict(
        exp_name=exp_name,
        variant=variant,
        exp_id=exp_id,
        seed=seed,
        use_gpu=use_gpu,
        gpu_id=gpu_id,
        snapshot_mode=snapshot_mode,
        snapshot_gap=snapshot_gap,
        git_infos=git_infos,
        script_name=main.__file__,
        trial_dir_suffix=trial_dir_suffix,
    )
    if mode == 'here_no_doodad':
        run_experiment_kwargs['base_log_dir'] = base_log_dir
        return run_experiment_here(
            method_call,
            **run_experiment_kwargs
        )

    """
    Safety Checks
    """

    if mode == 'ec2' or mode == 'gcp':
        if _global_is_first_launch and not ec2_okayed and not util.query_yes_no(
                "{} costs money. Are you sure you want to run?".format(mode)
        ):
            sys.exit(1)
        if _global_is_first_launch and not gpu_ec2_okayed and use_gpu:
            if not util.query_yes_no(
                    "{} is more expensive with GPUs. Confirm?".format(mode)
            ):
                sys.exit(1)
            gpu_ec2_okayed = True
        ec2_okayed = True

    """
    GPU vs normal configs
    """
    if use_gpu:
        docker_image = config.GPU_DOODAD_DOCKER_IMAGE
        if instance_type is None:
            instance_type = config.GPU_INSTANCE_TYPE
        else:
            assert instance_type[0] == 'g'
        if spot_price is None:
            spot_price = config.GPU_SPOT_PRICE
        variant['docker_image'] = docker_image
    else:
        docker_image = config.DOODAD_DOCKER_IMAGE
        if instance_type is None:
            instance_type = config.INSTANCE_TYPE
        if spot_price is None:
            spot_price = config.SPOT_PRICE
        variant['docker_image'] = docker_image
    if mode in {'sss', 'htp'}:
        if use_gpu:
            singularity_image = config.SSS_GPU_IMAGE
        else:
            singularity_image = config.SSS_CPU_IMAGE
        variant['singularity_image'] = singularity_image
    elif mode in ['local_singularity', 'slurm_singularity']:
        singularity_image = config.SINGULARITY_IMAGE
        variant['singularity_image'] = singularity_image
    else:
        singularity_image = None


    """
    Get the mode
    """
    mode_kwargs = {}
    if use_gpu and mode == 'ec2':
        image_id = config.REGION_TO_GPU_AWS_IMAGE_ID[region]
        if region == 'us-east-1':
            avail_zone = config.REGION_TO_GPU_AWS_AVAIL_ZONE.get(region, "us-east-1b")
            mode_kwargs['extra_ec2_instance_kwargs'] = dict(
                Placement=dict(
                    AvailabilityZone=avail_zone,
                ),
            )
    else:
        image_id = None
    if hasattr(config, "AWS_S3_PATH"):
        aws_s3_path = config.AWS_S3_PATH
    else:
        aws_s3_path = None

    if "run_id" in variant and variant["run_id"] is not None:
        run_id, exp_id = variant["run_id"], variant["exp_id"]
        s3_log_name = "run{}/id{}".format(run_id, exp_id)
    else:
        s3_log_name = "{}-id{}-s{}".format(exp_name, exp_id, seed)
    if trial_dir_suffix is not None:
        s3_log_name = s3_log_name + "-" + trial_dir_suffix

    """
    Create mode
    """
    if mode == 'local':
        dmode = doodad.mode.Local(skip_wait=skip_wait)
    elif mode == 'local_docker':
        dmode = doodad.mode.LocalDocker(
            image=docker_image,
            gpu=use_gpu,
        )
    elif mode == 'ssh':
        if ssh_host == None:
            ssh_dict = config.SSH_HOSTS[config.SSH_DEFAULT_HOST]
        else:
            ssh_dict = config.SSH_HOSTS[ssh_host]
        credentials = doodad.ssh.credentials.SSHCredentials(
            username=ssh_dict['username'],
            hostname=ssh_dict['hostname'],
            identity_file=config.SSH_PRIVATE_KEY
        )
        dmode = doodad.mode.SSHDocker(
            credentials=credentials,
            image=docker_image,
            gpu=use_gpu,
            tmp_dir=config.SSH_TMP_DIR,
        )
    elif mode == 'local_singularity':
        dmode = doodad.mode.LocalSingularity(
            image=singularity_image,
            gpu=use_gpu,
            pre_cmd=config.SINGULARITY_PRE_CMDS,
        )
    elif mode in {'slurm_singularity', 'sss', 'htp'}:
        assert time_in_mins is not None, "Must approximate/set time in minutes"
        if slurm_config is None:
            if use_gpu:
                slurm_config = SlurmConfig(
                    time_in_mins=time_in_mins, **config.SLURM_GPU_CONFIG)
            else:
                slurm_config = SlurmConfig(
                    time_in_mins=time_in_mins, **config.SLURM_CPU_CONFIG)
        if mode == 'slurm_singularity':
            dmode = doodad.mode.SlurmSingularity(
                image=singularity_image,
                gpu=use_gpu,
                skip_wait=skip_wait,
                pre_cmd=config.SINGULARITY_PRE_CMDS,
                extra_args=config.BRC_EXTRA_SINGULARITY_ARGS,
                slurm_config=slurm_config,
            )
        elif mode == 'htp':
            dmode = doodad.mode.BrcHighThroughputMode(
                image=singularity_image,
                gpu=use_gpu,
                pre_cmd=config.SSS_PRE_CMDS,
                extra_args=config.BRC_EXTRA_SINGULARITY_ARGS,
                slurm_config=slurm_config,
                taskfile_dir_on_brc=config.TASKFILE_DIR_ON_BRC,
                overwrite_task_script=_global_is_first_launch,
                n_tasks_total=_global_n_tasks_total,
                launch_id=_global_launch_uuid
            )
        else:
            dmode = doodad.mode.ScriptSlurmSingularity(
                image=singularity_image,
                gpu=use_gpu,
                pre_cmd=config.SSS_PRE_CMDS,
                extra_args=config.BRC_EXTRA_SINGULARITY_ARGS,
                slurm_config=slurm_config,
            )
    elif mode == 'ec2':
        # Do this separately in case someone does not have EC2 configured
        dmode = doodad.mode.EC2AutoconfigDocker(
            image=docker_image,
            image_id=image_id,
            region=region,
            instance_type=instance_type,
            spot_price=spot_price,
            s3_log_prefix=exp_name,
            # Ask Vitchyr or Steven from an explanation, but basically we
            # will start just making the sub-directories within railrl rather
            # than relying on doodad to do that.
            s3_log_name="",
            gpu=use_gpu,
            aws_s3_path=aws_s3_path,
            num_exps=num_exps_per_instance,
            **mode_kwargs
        )
    elif mode == 'gcp':
        image_name = config.GCP_IMAGE_NAME
        if use_gpu:
            image_name = config.GCP_GPU_IMAGE_NAME

        if gcp_kwargs is None:
            gcp_kwargs = {}
        config_kwargs = {
            **config.GCP_DEFAULT_KWARGS,
            **dict(image_name=image_name),
            **gcp_kwargs
        }
        dmode = doodad.mode.GCPDocker(
            image=docker_image,
            gpu=use_gpu,
            gcp_bucket_name=config.GCP_BUCKET_NAME,
            gcp_log_prefix=exp_name,
            gcp_log_name="",
            num_exps=num_exps_per_instance,
            **config_kwargs
        )
    else:
        raise NotImplementedError("Mode not supported: {}".format(mode))

    """
    Get the mounts
    """
    mounts = create_mounts(
        base_log_dir=base_log_dir,
        mode=mode,
        sync_interval=sync_interval,
        local_input_dir_to_mount_point_dict=local_input_dir_to_mount_point_dict,
    )

    """
    Get the outputs
    """
    launch_locally = None
    target = target_script or osp.join(util.REPO_DIR, 'easy_launcher/run_experiment.py')
    if mode == 'ec2':
        # Ignored since I'm setting the snapshot dir directly
        base_log_dir_for_script = None
        run_experiment_kwargs['randomize_seed'] = True
        # The snapshot dir needs to be specified for S3 because S3 will
        # automatically create the experiment director and sub-directory.
        snapshot_dir_for_script = config.OUTPUT_DIR_FOR_DOODAD_TARGET
    elif mode == 'local':
        base_log_dir_for_script = base_log_dir
        # The snapshot dir will be automatically created
        snapshot_dir_for_script = None
    elif mode == 'local_docker':
        base_log_dir_for_script = config.OUTPUT_DIR_FOR_DOODAD_TARGET
        # The snapshot dir will be automatically created
        snapshot_dir_for_script = None
    elif mode == 'ssh':
        base_log_dir_for_script = config.OUTPUT_DIR_FOR_DOODAD_TARGET
        # The snapshot dir will be automatically created
        snapshot_dir_for_script = None
    elif mode in ['local_singularity', 'slurm_singularity', 'sss', 'htp']:
        base_log_dir_for_script = base_log_dir
        # The snapshot dir will be automatically created
        snapshot_dir_for_script = None
        launch_locally = True
        if mode in {'sss', 'htp'}:
            target = config.SSS_RUN_DOODAD_EXPERIMENT_SCRIPT_PATH
    elif mode == 'here_no_doodad':
        base_log_dir_for_script = base_log_dir
        # The snapshot dir will be automatically created
        snapshot_dir_for_script = None
    elif mode == 'gcp':
        # Ignored since I'm setting the snapshot dir directly
        base_log_dir_for_script = None
        run_experiment_kwargs['randomize_seed'] = True
        snapshot_dir_for_script = config.OUTPUT_DIR_FOR_DOODAD_TARGET
    else:
        raise NotImplementedError("Mode not supported: {}".format(mode))
    run_experiment_kwargs['base_log_dir'] = base_log_dir_for_script
    _global_target_mount = doodad.launch_python(
        target=target,
        mode=dmode,
        mount_points=mounts,
        python_cmd=config.MODE_TO_PYTHON_CMD[mode],
        args={
            'method_call': method_call,
            'output_dir': snapshot_dir_for_script,
            'run_experiment_kwargs': run_experiment_kwargs,
            'mode': mode,
        },
        use_cloudpickle=True,
        target_mount=_global_target_mount,
        verbose=verbose,
        launch_locally=launch_locally,
    )
    _global_is_first_launch = False
    _global_n_tasks_total += 1


def create_mounts(
        mode,
        base_log_dir,
        sync_interval=180,
        local_input_dir_to_mount_point_dict=None,
):
    if mode in {'sss', 'htp'}:
        code_mounts = SSS_CODE_MOUNTS
        non_code_mounts = SSS_NON_CODE_MOUNTS
    else:
        code_mounts = CODE_MOUNTS
        non_code_mounts = NON_CODE_MOUNTS

    if local_input_dir_to_mount_point_dict is None:
        local_input_dir_to_mount_point_dict = {}
    else:
        raise NotImplementedError("TODO(vitchyr): Implement this")

    mounts = [m for m in code_mounts]
    for dir, mount_point in local_input_dir_to_mount_point_dict.items():
        mounts.append(mount.MountLocal(
            local_dir=dir,
            mount_point=mount_point,
            pythonpath=False,
        ))

    if mode != 'local':
        for m in non_code_mounts:
            mounts.append(m)

    if mode == 'ec2':
        output_mount = mount.MountS3(
            s3_path='',
            mount_point=config.OUTPUT_DIR_FOR_DOODAD_TARGET,
            output=True,
            sync_interval=sync_interval,
            include_types=('*.txt', '*.csv', '*.json', '*.gz', '*.tar',
                           '*.log', '*.pkl', '*.mp4', '*.png', '*.jpg',
                           '*.jpeg', '*.patch'),
        )
    elif mode == 'gcp':
        output_mount = mount.MountGCP(
            gcp_path='',
            mount_point=config.OUTPUT_DIR_FOR_DOODAD_TARGET,
            output=True,
            gcp_bucket_name=config.GCP_BUCKET_NAME,
            sync_interval=sync_interval,
            include_types=('*.txt', '*.csv', '*.json', '*.gz', '*.tar',
                           '*.log', '*.pkl', '*.mp4', '*.png', '*.jpg',
                           '*.jpeg', '*.patch'),
        )

    elif mode in ['local', 'local_singularity', 'slurm_singularity', 'sss', 'htp']:
        # To save directly to local files (singularity does this), skip mounting
        output_mount = mount.MountLocal(
            local_dir=base_log_dir,
            mount_point=None,
            output=True,
        )
    elif mode == 'local_docker':
        output_mount = mount.MountLocal(
            local_dir=base_log_dir,
            mount_point=config.OUTPUT_DIR_FOR_DOODAD_TARGET,
            output=True,
        )
    elif mode == 'ssh':
        output_mount = mount.MountLocal(
            local_dir=base_log_dir,
            mount_point=config.OUTPUT_DIR_FOR_DOODAD_TARGET,
            output=True,
        )
    else:
        raise NotImplementedError("Mode not supported: {}".format(mode))
    mounts.append(output_mount)
    return mounts


def save_experiment_data(dictionary, log_dir):
    with open(log_dir + '/experiment.pkl', 'wb') as handle:
        pickle.dump(dictionary, handle, protocol=pickle.HIGHEST_PROTOCOL)


def continue_experiment(load_experiment_dir, resume_function):
    import joblib
    path = os.path.join(load_experiment_dir, 'experiment.pkl')
    if osp.exists(path):
        data = joblib.load(path)
        mode = data['mode']
        exp_name = data['exp_name']
        variant = data['variant']
        variant['params_file'] = load_experiment_dir + '/extra_data.pkl' # load from snapshot directory
        exp_id = data['exp_id']
        seed = data['seed']
        use_gpu = data['use_gpu']
        snapshot_mode = data['snapshot_mode']
        snapshot_gap = data['snapshot_gap']
        diff_string = data['diff_string']
        commit_hash = data['commit_hash']
        base_log_dir = data['base_log_dir']
        log_dir = data['log_dir']
        if mode == 'local':
            run_experiment_here(
                resume_function,
                variant=variant,
                exp_name=exp_name,
                exp_id=exp_id,
                seed=seed,
                use_gpu=use_gpu,
                snapshot_mode=snapshot_mode,
                snapshot_gap=snapshot_gap,
                code_diff=diff_string,
                commit_hash=commit_hash,
                base_log_dir=base_log_dir,
                log_dir=log_dir,
            )
    else:
        raise Exception('invalid experiment_file')


def continue_experiment_simple(load_experiment_dir, resume_function):
    import joblib
    path = os.path.join(load_experiment_dir, 'experiment.pkl')
    data = joblib.load(path)
    run_experiment_here_kwargs = data['run_experiment_here_kwargs']
    run_experiment_here_kwargs['log_dir'] = load_experiment_dir
    run_experiment_here_kwargs['variant']['params_file'] = (
        os.path.join(load_experiment_dir, 'extra_data.pkl')
    )
    run_experiment_here(
        resume_function,
        **run_experiment_here_kwargs
    )


def run_experiment_here(
        experiment_function,
        variant=None,
        exp_id=0,
        seed=0,
        use_gpu=True,
        gpu_id=0,
        # Logger params:
        exp_name="default",
        snapshot_mode='last',
        snapshot_gap=1,
        git_infos=None,
        script_name=None,
        trial_dir_suffix=None,
        randomize_seed=False,
        **setup_logger_kwargs
):
    """
    Run an experiment locally without any serialization.
    :param experiment_function: Function. `variant` will be passed in as its
    only argument.
    :param exp_name: Experiment prefix for the save file.
    :param variant: Dictionary passed in to `experiment_function`.
    :param exp_id: Experiment ID. Should be unique across all
    experiments. Note that one experiment may correspond to multiple seeds,.
    :param seed: Seed used for this experiment.
    :param use_gpu: Run with GPU. By default False.
    :param script_name: Name of the running script
    :param log_dir: If set, set the log directory to this. Otherwise,
    the directory will be auto-generated based on the exp_name.
    :return:
    """
    if variant is None:
        variant = {}
    variant['exp_id'] = str(exp_id)

    if randomize_seed or (seed is None and 'seed' not in variant):
        seed = random.randint(0, 100000)
        variant['seed'] = seed
    reset_execution_environment()

    actual_log_dir = setup_logger(
        exp_name=exp_name,
        variant=variant,
        exp_id=exp_id,
        seed=seed,
        snapshot_mode=snapshot_mode,
        snapshot_gap=snapshot_gap,
        git_infos=git_infos,
        script_name=script_name,
        trial_dir_suffix=trial_dir_suffix,
        **setup_logger_kwargs
    )

    set_seed(seed)
    os.environ['gpu_id'] = str(gpu_id)
    run_experiment_here_kwargs = dict(
        variant=variant,
        exp_id=exp_id,
        seed=seed,
        use_gpu=use_gpu,
        exp_name=exp_name,
        snapshot_mode=snapshot_mode,
        snapshot_gap=snapshot_gap,
        git_infos=git_infos,
        script_name=script_name,
        **setup_logger_kwargs
    )
    save_experiment_data(
        dict(
            run_experiment_here_kwargs=run_experiment_here_kwargs
        ),
        actual_log_dir
    )
    return experiment_function(variant)


def create_trial_name(exp_name, exp_id=0, seed=0):
    """
    Create a semi-unique experiment name that has a timestamp
    :param exp_name:
    :param exp_id:
    :return:
    """
    now = datetime.datetime.now(dateutil.tz.tzlocal())
    timestamp = now.strftime('%Y_%m_%d_%H_%M_%S')
    return "%s_%s_id%03d--s%d" % (exp_name, timestamp, exp_id, seed)


def create_log_dir(
        exp_name,
        exp_id=0,
        seed=0,
        base_log_dir=None,
        variant=None,
        trial_dir_suffix=None,
        include_exp_name_sub_dir=True,
):
    """
    Creates and returns a unique log directory.
    :param exp_name: All experiments with this prefix will have log
    directories be under this directory.
    :param exp_id: Different exp_ids will be in different directories.
    :return:
    """
    if variant and "run_id" in variant and variant["run_id"] is not None:
        run_id, exp_id = variant["run_id"], variant["exp_id"]
        if variant.get("num_exps_per_instance", 0) > 1:
            now = datetime.datetime.now(dateutil.tz.tzlocal())
            timestamp = now.strftime('%Y_%m_%d_%H_%M_%S')
            trial_name = "run%s/id%s/%s--s%d" % (run_id, exp_id, timestamp, seed)
        else:
            trial_name = "run{}/id{}".format(run_id, exp_id)
    else:
        trial_name = create_trial_name(exp_name, exp_id=exp_id,
                                       seed=seed)
    if trial_dir_suffix is not None:
        trial_name = "{}-{}".format(trial_name, trial_dir_suffix)
    if base_log_dir is None:
        base_log_dir = config.LOCAL_LOG_DIR
    if include_exp_name_sub_dir:
        log_dir = osp.join(base_log_dir, exp_name.replace("_", "-"), trial_name)
    else:
        log_dir = osp.join(base_log_dir, trial_name)
    if osp.exists(log_dir):
        print("WARNING: Log directory already exists {}".format(log_dir))
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logger(
        exp_name="default",
        variant=None,
        text_log_file="debug.log",
        variant_log_file="variant.json",
        tabular_log_file="progress.csv",
        snapshot_mode="last",
        snapshot_gap=1,
        log_tabular_only=False,
        log_dir=None,
        git_infos=None,
        script_name=None,
        **create_log_dir_kwargs
):
    """
    Set up logger to have some reasonable default settings.
    Will save log output to
        based_log_dir/exp_name/exp_name.
    exp_name will be auto-generated to be unique.
    If log_dir is specified, then that directory is used as the output dir.
    :param exp_name: The sub-directory for this specific experiment.
    :param exp_id: The number of the specific experiment run within this
    experiment.
    :param variant:
    :param base_log_dir: The directory where all log should be saved.
    :param text_log_file:
    :param variant_log_file:
    :param tabular_log_file:
    :param snapshot_mode:
    :param log_tabular_only:
    :param snapshot_gap:
    :param log_dir:
    :param git_infos:
    :param script_name: If set, save the script name to this.
    :return:
    """
    first_time = log_dir is None
    if first_time:
        log_dir = create_log_dir(
            exp_name,
            variant=variant,
            **create_log_dir_kwargs
        )

    if variant is not None:
        if 'unique_id' not in variant:
            variant['unique_id'] = str(uuid.uuid4())
        logger.log("Variant:")
        logger.log(
            json.dumps(ppp.dict_to_safe_json(variant, sort=True), indent=2)
        )
        variant_log_path = osp.join(log_dir, variant_log_file)
        logger.log_variant(variant_log_path, variant)

    tabular_log_path = osp.join(log_dir, tabular_log_file)
    text_log_path = osp.join(log_dir, text_log_file)

    logger.add_text_output(text_log_path)
    if first_time:
        logger.add_tabular_output(tabular_log_path)
    else:
        logger._add_output(tabular_log_path, logger._tabular_outputs,
                           logger._tabular_fds, mode='a')
        for tabular_fd in logger._tabular_fds:
            logger._tabular_header_written.add(tabular_fd)
    logger.set_snapshot_dir(log_dir)
    logger.set_snapshot_mode(snapshot_mode)
    logger.set_snapshot_gap(snapshot_gap)
    logger.set_log_tabular_only(log_tabular_only)
    exp_name = log_dir.split("/")[-1]
    logger.push_prefix("[%s] " % exp_name)

    save_git_info(log_dir, git_infos)
    if script_name is not None:
        with open(osp.join(log_dir, "script_name.txt"), "w") as f:
            f.write(script_name)
    return log_dir


def set_seed(seed):
    """
    Set the seed for all the possible random number generators.
    """
    seed = int(seed)
    random.seed(seed)
    np.random.seed(seed)


def reset_execution_environment():
    """
    Call this between calls to separate experiments.
    """
    logger.reset()


