#
#
#      0=================================0
#      |    Kernel Point Convolutions    |
#      0=================================0
#
#
# ----------------------------------------------------------------------------------------------------------------------
#
#      Callable script to start a training on Masters dataset
#
# ----------------------------------------------------------------------------------------------------------------------
#
#      Hugues THOMAS - 06/03/2020
#


# ----------------------------------------------------------------------------------------------------------------------
#
#           Imports and global variables
#       \**********************************/
#

# Common libs
import signal
import os
import sys
from pathlib import Path

import wandb

# Dataset
from datasets.Masters import *
from torch.utils.data import DataLoader

from utils.config import Config
from utils.trainer import ModelTrainer
from models.architectures import KPFCNN


# ----------------------------------------------------------------------------------------------------------------------
#
#           Config Class
#       \******************/
#

class MastersConfig(Config):
    """
    Override the parameters you want to modify for this dataset
    """

    ####################
    # Dataset parameters
    ####################

    # Dataset name
    dataset = 'Masters'

    # Dataset folder
    dataset_folder = ''

    # Number of classes in the dataset (This value is overwritten by dataset class when Initializating dataset).
    num_classes = None

    # Type of task performed on this dataset (also overwritten)
    dataset_task = ''

    # Number of CPU threads for the input pipeline
    input_threads = 8

    # Active Learning
    active_learning = False
    al_repeats = 5

    #########################
    # Architecture definition
    #########################

    # # Define layers
    architecture_deformable = ['simple',
                    'resnetb',
                    'resnetb_strided',
                    'resnetb',
                    'resnetb',
                    'resnetb_strided',
                    'resnetb',
                    'resnetb',
                    'resnetb_strided',
                    'resnetb_deformable',
                    'resnetb_deformable',
                    'resnetb_deformable_strided',
                    'resnetb_deformable',
                    'resnetb_deformable',
                    'nearest_upsample',
                    'unary',
                    'nearest_upsample',
                    'unary',
                    'nearest_upsample',
                    'unary',
                    'nearest_upsample',
                    'unary']

    # Define layers (we use nondeformable because the author suggests this on github)
    architecture = ['simple',
                    'resnetb',
                    'resnetb_strided',
                    'resnetb',
                    'resnetb',
                    'resnetb_strided',
                    'resnetb',
                    'resnetb',
                    'resnetb_strided',
                    'resnetb',
                    'resnetb',
                    'resnetb_strided',
                    'resnetb',
                    'resnetb',
                    'nearest_upsample',
                    'unary',
                    'nearest_upsample',
                    'unary',
                    'nearest_upsample',
                    'unary',
                    'nearest_upsample',
                    'unary']

    ###################
    # KPConv parameters
    ###################

    # Number of kernel points
    num_kernel_points = 15

    # Radius of the input sphere (decrease value to reduce memory cost)
    in_radius = 1.2

    # Size of the first subsampling grid in meters (increase value to reduce memory cost)
    # Reducing this on denser datasets allow shapes with finer details. Should also reduce in_radius to compensate.
    # Will be better on small objects but could be worse on very big objects. If you want big objects and have very
    # dense data consider that it may not be useful and a higher first_subsampling_dl and in_radius could be used.
    first_subsampling_dl = 0.02

    # Radius of convolution/neighbourhood (for rigid KPConv) in "number grid cell". (2.5 is the standard value)
    # e.g. 2.5*0.03 = 7.5cm
    conv_radius = 2.5

    # Radius of deformable convolution in "number grid cell". Larger so that deformed kernel can spread out
    deform_radius = 5.0

    # Radius of the area of influence of each kernel point in "number grid cell". (1.0 is the standard value) σ in paper
    KP_extent = 1.2

    # Behavior of convolutions in ('constant', 'linear', 'gaussian')
    KP_influence = 'linear'

    # Aggregation function of KPConv in ('closest', 'sum')
    aggregation_mode = 'sum'

    # Choice of input features
    first_features_dim = 128
    in_features_dim = 1

    # Can the network learn modulations
    modulated = False

    # Batch normalization parameters
    use_batch_norm = True
    batch_norm_momentum = 0.02

    # Deformable offset loss
    # 'point2point' fitting geometry by penalizing distance from deform point to input points
    # 'point2plane' fitting geometry by penalizing distance from deform point to input point triplet (not implemented)
    deform_fitting_mode = 'point2point'
    deform_fitting_power = 1.0  # Multiplier for the fitting/repulsive loss
    deform_lr_factor = 0.1  # Multiplier for learning rate applied to the deformations
    repulse_extent = 1.2  # Distance of repulsion for deformed kernel points

    #####################
    # Training parameters
    #####################

    # Maximal number of epochs
    # max_epoch = 500
    max_epoch = 100

    # Learning rate management
    learning_rate = 1e-2
    momentum = 0.98
    lr_decays = {i: 0.1 ** (1 / 150) for i in range(1, max_epoch)}
    grad_clip_norm = 100.0

    # Number of batch (decrease to reduce memory cost, but it should remain > 3 for stability)
    batch_num = 6

    # Number of steps per epochs
    epoch_steps = 500
    # epoch_steps = 50

    # Number of validation examples per epoch
    validation_size = 50

    # Number of epoch between each checkpoint
    checkpoint_gap = 10

    # Augmentations
    augment_scale_anisotropic = True
    augment_symmetries = [True, False, False]
    augment_rotation = 'vertical'
    augment_scale_min = 0.9
    augment_scale_max = 1.1
    augment_noise = 0.001
    augment_color = 0.8

    # The way we balance segmentation loss
    #   > 'none': Each point in the whole batch has the same contribution.
    #   > 'class': Each class has the same contribution (points are weighted according to class balance)
    #   > 'batch': Each cloud in the batch has the same contribution (points are weighted according cloud sizes)
    segloss_balance = 'none'

    # Do we need to save convergence
    saving = True
    saving_path = None


# ----------------------------------------------------------------------------------------------------------------------
#
#           Main Call
#       \***************/
#

def define_wandb_metrics():
    wandb.define_metric('Train/TP', summary='max')
    wandb.define_metric('Train/FP', summary='min')
    wandb.define_metric('Train/TN', summary='max')
    wandb.define_metric('Train/FN', summary='min')

    wandb.define_metric('Train/category-TP', summary='max')
    wandb.define_metric('Train/category-FP', summary='min')
    wandb.define_metric('Train/category-TN', summary='max')
    wandb.define_metric('Train/category-FN', summary='min')

    # wandb.define_metric('Train/Precision', summary='max')
    # wandb.define_metric('Train/Recall', summary='max')
    wandb.define_metric('Train/F1', summary='max')
    wandb.define_metric('Train/mIoU', summary='max')
    wandb.define_metric('Train/accuracy', summary='max')
    wandb.define_metric('Train/inner_reg_loss', summary='min')
    wandb.define_metric('Train/inner_output_loss', summary='min')
    wandb.define_metric('Train/inner_sum_loss', summary='min')

    # Validation Classification metrics
    wandb.define_metric('validation/TP', summary='max')
    wandb.define_metric('validation/FP', summary='min')
    wandb.define_metric('validation/TN', summary='max')
    wandb.define_metric('validation/FN', summary='min')

    wandb.define_metric('validation/category-TP', summary='max')
    wandb.define_metric('validation/category-FP', summary='min')
    wandb.define_metric('validation/category-TN', summary='max')
    wandb.define_metric('validation/category-FN', summary='min')

    # wandb.define_metric('Validation/Precision', summary='max')
    # wandb.define_metric('Validation/Recall', summary='max')
    wandb.define_metric('Validation/F1', summary='max')
    wandb.define_metric('Validation/mIoU', summary='max')
    wandb.define_metric('Validation/accuracy', summary='max')
    # wandb.define_metric('Validation/eval_point_avg_class_accuracy', summary='max')
    # wandb.define_metric('Validation/eval_mean_loss', summary='min')
    print("Wandb metrics defined")


if __name__ == '__main__':
    # Initialise wandb
    # os.environ["WANDB_MODE"] = "dryrun"
    name = (sys.argv[1] if len(sys.argv) < 5 else sys.argv[1]+'_'+sys.argv[-1])+"-50%Validation"
    wandb.init(project="kpconv", name=name, group="50%Validation")
    wandb.run.log_code("./train_Masters.py")
    define_wandb_metrics()

    ############################
    # Initialize the environment
    ############################

    # Set which gpu is going to be used
    GPU_ID = '0'
    # Set GPU visible device
    os.environ['CUDA_VISIBLE_DEVICES'] = GPU_ID

    ###############
    # Previous chkp
    ###############

    # Choose here if you want to start training from a previous snapshot (None for new training)
    # previous_training_path = 'Log_2020-03-19_19-53-27'
    previous_training_path = ''
    if len(sys.argv) == 5:
        previous_training_path = sys.argv[-1]
    if len(previous_training_path) > 0:
        print("Starting from ", previous_training_path)

    # Choose index of checkpoint to start from. If None, uses the latest chkp
    chkp_idx = None
    if previous_training_path:

        # Find all snapshot in the chosen training folder
        chkp_path = os.path.join('results', previous_training_path, 'checkpoints')
        chkps = [f for f in os.listdir(chkp_path) if f[:4] == 'chkp']

        # Find which snapshot to restore
        if chkp_idx is None:
            if previous_training_path == 's3dis-xyz':
                chosen_chkp = 's3dis-xyz.pth'
            else:
                # chosen_chkp = 'current_chkp.tar'
                chosen_chkp = 'chkp_0050.tar'
        else:
            chosen_chkp = np.sort(chkps)[chkp_idx]
        chosen_chkp = os.path.join('results', previous_training_path, 'checkpoints', chosen_chkp)
        if not Path(chosen_chkp).exists():
            chosen_chkp = np.sort(chkps)[-1]
            chosen_chkp = os.path.join('results', previous_training_path, 'checkpoints', chosen_chkp)
            print("Restoring from ", chosen_chkp)

    else:
        chosen_chkp = None

    ##############
    # Prepare Data
    ##############

    print()
    print('Data Preparation')
    print('****************')

    # Initialize configuration class
    config = MastersConfig()
    if len(previous_training_path) > 0:
        if previous_training_path != 's3dis-xyz':
            config.load(os.path.join('results', previous_training_path))
            config.saving_path = None
        else:
            config.architecture = config.architecture_deformable

    # Get path from argument if given
    if len(sys.argv) > 1:
        config.saving_path = f"results/{sys.argv[1]}"
        # if len(sys.argv) == 5:
        #     config.saving_path = f"results/{sys.argv[1]}_{sys.argv[-1]}"
        if len(sys.argv) > 2:
            config.dataset_folder = f"Data/PatrickData/{sys.argv[2]}/{sys.argv[3]}"

    # Initialize datasets
    training_dataset = MastersDataset(config, set='train', use_potentials=False)  # Don't use potentials if imbalanced # https://github.com/HuguesTHOMAS/KPConv-PyTorch/issues/2
    test_dataset = MastersDataset(config, set='validate', use_potentials=True)  # It is better to use potentials here to ensure the entire scene is seen https://github.com/HuguesTHOMAS/KPConv-PyTorch/issues/72
    print(f"{training_dataset.use_potentials=}\n{test_dataset.use_potentials=}")
    class_weights, _ = np.histogram(training_dataset.input_labels, np.arange(training_dataset.label_values.max() + 2))
    class_weights = class_weights / np.sum(class_weights)
    class_weights = np.amax(class_weights) / class_weights
    # Cube root of labelweights has log-like effect for when labels are very imbalanced
    config.class_w = np.power(class_weights, 1 / 3)

    # Initialize samplers
    training_sampler = MastersSampler(training_dataset)
    test_sampler = MastersSampler(test_dataset)

    # Initialize the dataloader
    training_loader = DataLoader(training_dataset,
                                 batch_size=1,
                                 sampler=training_sampler,
                                 collate_fn=MastersCollate,
                                 num_workers=config.input_threads,
                                 pin_memory=True)
    test_loader = DataLoader(test_dataset,
                             batch_size=1,
                             sampler=test_sampler,
                             collate_fn=MastersCollate,
                             num_workers=config.input_threads,
                             pin_memory=True)
    print(f"{len(training_loader)=}\n{len(test_loader)=}")

    # Calibrate samplers
    training_sampler.calibration(training_loader, verbose=True)
    test_sampler.calibration(test_loader, verbose=True)

    # Optional debug functions
    # debug_timing(training_dataset, training_loader)
    # debug_timing(test_dataset, test_loader)
    # debug_upsampling(training_dataset, training_loader)

    print('\nModel Preparation')
    print('*****************')

    # Define network model
    t1 = time.time()
    net = KPFCNN(config, training_dataset.label_values, training_dataset.ignored_labels)

    debug = False
    if debug:
        print('\n*************************************\n')
        print(net)
        print('\n*************************************\n')
        for param in net.parameters():
            if param.requires_grad:
                print(param.shape)
        print('\n*************************************\n')
        print("Model size %i" % sum(param.numel() for param in net.parameters() if param.requires_grad))
        print('\n*************************************\n')

    config_dict = dict(vars(MastersConfig))
    config_dict.update(vars(config))
    wandb.config.update(config_dict)
    print("Config:")
    import pprint

    pprint.pprint(config_dict)
    # Define a trainer class
    trainer = ModelTrainer(net, config, chkp_path=chosen_chkp, finetune=(previous_training_path == "s3dis-xyz"))
    print('Done in {:.1f}s\n'.format(time.time() - t1))

    print('\nStart training')
    print('**************')

    # Training
    trainer.train(net, training_loader, test_loader, config)

    # print('Forcing exit now')
    # os.kill(os.getpid(), signal.SIGINT)
    print("Reached end of training script")
