CODE_DIRS_TO_MOUNT = [
    '/home/vitchyr/git/railrl/',
    # '/home/vitchyr/git/multiworld/',
    # '/home/vitchyr/git/softlearning/',
    # '/home/vitchyr/git/sac_envs_railrl/',
]
DIR_AND_MOUNT_POINT_MAPPINGS = [
    dict(
        local_dir='/home/vitchyr/.mujoco/',
        mount_point='/root/.mujoco',
    ),
]
LOCAL_LOG_DIR = '/home/vitchyr/res'
RUN_DOODAD_EXPERIMENT_SCRIPT_PATH = (
    '/home/vitchyr/git/railrl/scripts/run_experiment_from_doodad.py'
)

# This really shouldn't matter and in theory could be whatever
OUTPUT_DIR_FOR_DOODAD_TARGET = '/tmp/doodad-output/'


"""
AWS Settings
"""
AWS_S3_PATH = 's3://2-12-2017.railrl.vitchyr.rail.bucket/doodad/logs'

REGION_TO_GPU_AWS_AVAIL_ZONE = {
    'us-east-1': "us-east-1b",
}

# You probably don't need to change things below
# Specifically, the docker image is looked up on dockerhub.com.
# DOODAD_DOCKER_IMAGE = 'vitchyr/railrl-torch4cuda9'
# DOODAD_DOCKER_IMAGE = 'stevenlin598/torch3np16'
DOODAD_DOCKER_IMAGE = 'vitchyr/railrl_v12_cuda10-1_mj2-0-2-2_torch1-1-0_gym0-12-5_py3-6-5:latest'
INSTANCE_TYPE = 'c5.large'
SPOT_PRICE = 0.1

# GPU_DOODAD_DOCKER_IMAGE = 'vitchyr/railrl-torch4cuda9'
# GPU_DOODAD_DOCKER_IMAGE = 'stevenlin598/cuda9nvidia396'
# GPU_DOODAD_DOCKER_IMAGE = 'vitchyr/railrl_v11_cuda10-1_mj2-0-2-2_torch0-3-1_gym0-10-5_py3-5-2'
# GPU_DOODAD_DOCKER_IMAGE = 'stevenlin598/torch3np16'
GPU_DOODAD_DOCKER_IMAGE = 'vitchyr/railrl_v12_cuda10-1_mj2-0-2-2_torch1-1-0_gym0-12-5_py3-6-5:latest'
GPU_INSTANCE_TYPE = 'g3.4xlarge'
GPU_SPOT_PRICE = 0.5
REGION_TO_GPU_AWS_IMAGE_ID = {
    'us-west-1': "ami-874378e7",
    'us-east-1': "ami-ce73adb1",
}
FILE_TYPES_TO_SAVE = (
    '*.txt', '*.csv', '*.json', '*.gz', '*.tar',
    '*.log', '*.pkl', '*.mp4', '*.png', '*.jpg',
    '*.jpeg', '*.patch', '*.html'
)


"""
SSH Settings
"""
SSH_HOSTS = dict(
    vitchyr=dict(
        username='vitchyr',
        hostname='ari.banatao.berkeley.edu',
    ),
    newton5=dict(
        username='vitchyr',
        hostname='newton5.banatao.berkeley.edu',
    ),
    newton6=dict(
        username='vitchyr',
        hostname='newton6.banatao.berkeley.edu',
    ),
    newton7=dict(
        username='vitchyr',
        hostname='newton7.banatao.berkeley.edu',
    ),
)
SSH_DEFAULT_HOST = 'vitchyr'
SSH_PRIVATE_KEY = '~/.ssh/id_rsa'
SSH_LOG_DIR = '~/shared/res'
SSH_TMP_DIR = '~/shared/tmp'


"""
Slurm Settings
"""
SINGULARITY_IMAGE = '/home/vitchyr/singularity/railrl-torch4cuda8-v7.img'
# SINGULARITY_IMAGE = '/home/vitchyr/singularity/railrl-vitchyr-v5.img'
# SINGULARITY_IMAGE = '/home/vitchyr/singularity/railrl-torch4cuda9-v3.img'
# SINGULARITY_IMAGE = '/home/vitchyr/singularity/railrl-tmp.img'
SINGULARITY_PRE_CMDS = [
    'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$HOME/.mujoco/mjpro150/bin'
]
SLURM_CPU_CONFIG = dict(
    account_name='fc_rail',
    partition='savio',
    nodes=1,
    n_tasks=1,
    n_gpus=1,
    qos='savio_normal',
    extra_args='--writable -B /usr/lib64 -B /var/lib/dcv-gl',
)
SLURM_GPU_CONFIG = dict(
    account_name='fc_rail',
    partition='savio2_1080ti',
    nodes=1,
    n_tasks=1,
    n_gpus=1,
    qos='savio_normal',
    extra_args='--writable -B /usr/lib64 -B /var/lib/dcv-gl',
)

"""
Slurm Script Settings

These are basically the same settings as above, but for the remote machine
where you will be running the generated script.
"""
SSS_CODE_DIRS_TO_MOUNT = [
    '/global/home/users/vitchyr/git/railrl',
    '/global/home/users/vitchyr/git/multiworld',
    '/global/home/users/vitchyr/git/doodad',
    '/global/home/users/vitchyr/git/sac_envs_railrl',
]
SSS_DIR_AND_MOUNT_POINT_MAPPINGS = [
    dict(
        local_dir='/global/home/users/vitchyr/.mujoco',
        mount_point='/root/.mujoco',
    ),
]
SSS_LOG_DIR = '/global/scratch/vitchyr/doodad-log'

# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl-torch4cuda8-v7.img'
SSS_GPU_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl_v12_cuda10-1_mj2-0-2-2_torch1-1-0_gym0-12-5_py3-6-5_touch_nvidia3.img'
SSS_CPU_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl_v12_cuda10-1_mj2-0-2-2_torch1-1-0_gym0-12-5_py3-6-5_cpu.img'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl_v12_cuda10-1_mj2-0-2-2_torch1-1-0_gym0-12-5_py3-6-5_moved.img'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/no_mj_lock.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/no_mj_lock_only_mk_dir.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl-ray-05-04-2019-gym12.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl-sss-05-15-2019-gym12.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl-sss-05-15-2019' \
#             '-gym12-v2.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl-should-work-gym-12.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl-mj-1-50-1-59-working.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/test.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl_v10_cuda10-1_mj2-0-2-2_torch0-4-1_gym0-10-5_py3-5-2.simg'
# SSS_IMAGE = '/global/scratch/vitchyr/singularity_imgs/railrl_v11_cuda10-1_mj2-0-2-2_torch0-3-1_gym0-10-5_py3-5-2.simg'
SSS_RUN_DOODAD_EXPERIMENT_SCRIPT_PATH = (
    '/global/home/users/vitchyr/git/railrl/scripts/run_experiment_from_doodad.py'
)
SSS_PRE_CMDS = [
    'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH'
    ':/global/home/users/vitchyr/.mujoco/mjpro150/bin'
    ':/global/home/users/vitchyr/.mujoco/mujoco200/bin',
    'export PATH=/global/home/users/vitchyr/railrl/bin:/opt/conda/envs/railrl/bin/:$PATH',
]

"""
GCP Settings

To see what zones support GPU, go to https://cloud.google.com/compute/docs/gpus/
"""
GCP_IMAGE_NAME = 'railrl-torch-4-cpu'
GCP_GPU_IMAGE_NAME = 'railrl-torch4cuda9'
# GCP_BUCKET_NAME = 'railrl-11-05-2018'
GCP_BUCKET_NAME = 'railrl-vitchyr-11-05-2018'

GCP_DEFAULT_KWARGS = dict(
    zone='us-west2-c',
    # zone='us-east1-b',
    # zone='us-east4-a',
    # zone='us-west1-a',
    # zone='us-east1-c',  # Has K80s
    # zone='us-east1-d',  # Has K80s
    # zone='us-west1-b',  # Has K80s
    # zone='us-central1-a',  # Has K80s
    # zone='us-central1-c',  # Has K80s
    instance_type='n1-standard-4',
    image_project='railrl-private-gcp',
    terminate=True,
    preemptible=False,
    gpu_kwargs=dict(
        # gpu_model='nvidia-tesla-p4',
        gpu_model='nvidia-tesla-k80',
        num_gpu=1,
    )
)
