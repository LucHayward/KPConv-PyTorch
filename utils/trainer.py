#
#
#      0=================================0
#      |    Kernel Point Convolutions    |
#      0=================================0
#
#
# ----------------------------------------------------------------------------------------------------------------------
#
#      Class handling the training of any model
#
# ----------------------------------------------------------------------------------------------------------------------
#
#      Hugues THOMAS - 11/06/2018
#


# ----------------------------------------------------------------------------------------------------------------------
#
#           Imports and global variables
#       \**********************************/
#


# Basic libs
import torch
import torch.nn as nn
import numpy as np
import pickle
import os
from os import makedirs, remove
from os.path import exists, join
import time
import sys

from sklearn.metrics import confusion_matrix, f1_score, jaccard_score, accuracy_score
from scipy.stats import mode

# PLY reader
from utils.ply import read_ply, write_ply

# Metrics
from utils.metrics import IoU_from_confusions, fast_confusion
from utils.config import Config
from sklearn.neighbors import KDTree

from models.blocks import KPConv
import wandb


# ----------------------------------------------------------------------------------------------------------------------
#
#           Trainer Class
#       \*******************/
#


class ModelTrainer:

    # Initialization methods
    # ------------------------------------------------------------------------------------------------------------------

    def __init__(self, net, config, chkp_path=None, finetune=False, on_gpu=True):
        """
        Initialize training parameters and reload previous model for restore/finetune
        :param net: network object
        :param config: configuration object
        :param chkp_path: path to the checkpoint that needs to be loaded (None for new training)
        :param finetune: finetune from checkpoint (True) or restore training from checkpoint (False)
        :param on_gpu: Train on GPU or CPU
        """

        ############
        # Parameters
        ############

        # Epoch index
        self.epoch = 0
        self.step = 0

        # Best IoU
        self.best_train_mIoU = 0
        self.best_val_mIoU = 0

        # Optimizer with specific learning rate for deformable KPConv
        deform_params = [v for k, v in net.named_parameters() if 'offset' in k]
        other_params = [v for k, v in net.named_parameters() if 'offset' not in k]
        deform_lr = config.learning_rate * config.deform_lr_factor
        self.optimizer = torch.optim.SGD([{'params': other_params},
                                          {'params': deform_params, 'lr': deform_lr}],
                                         lr=config.learning_rate,
                                         momentum=config.momentum,
                                         weight_decay=config.weight_decay)

        # Choose to train on CPU or GPU
        if on_gpu and torch.cuda.is_available():
            self.device = torch.device("cuda:0")
        else:
            self.device = torch.device("cpu")
        net.to(self.device)

        ##########################
        # Load previous checkpoint
        ##########################

        if (chkp_path is not None):
            if finetune:
                checkpoint = torch.load(chkp_path)
                if 'criterion.weight' not in checkpoint['model_state_dict'].keys():
                    checkpoint['model_state_dict']['criterion.weight'] = net.criterion.weight
                net.load_state_dict(checkpoint['model_state_dict'])
                net.train()
                print("Model restored and ready for finetuning.")
            else:
                checkpoint = torch.load(chkp_path)
                net.load_state_dict(checkpoint['model_state_dict'])
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                self.epoch = checkpoint['epoch']
                net.train()
                print("Model and training state restored.")

        # Path of the result folder
        if config.saving:
            if config.saving_path is None:
                config.saving_path = time.strftime('results/Log_%Y-%m-%d_%H-%M-%S', time.gmtime())
                # wandb.config.update({'saving_path': config.saving_path}, allow_val_change=True)
            if not exists(config.saving_path):
                makedirs(config.saving_path)
            config.save()

        return

    # Training main method
    # ------------------------------------------------------------------------------------------------------------------

    def train(self, net, training_loader, val_loader, config):
        """
        Train the model on a particular dataset.
        """

        ################
        # Initialization
        ################
        wandb.watch(net, log_freq=10)

        def _save_batch_vis(batch, outputs=None):
            lengths = np.cumsum(batch.lengths[0].detach().cpu().numpy())[:-1]
            points = batch.points[0].detach().cpu().numpy()
            labels = batch.labels.detach().cpu().numpy()
            if outputs is not None:
                outputs = torch.argmax(outputs.data, dim=1).detach().cpu().numpy()
                result = np.array_split(np.column_stack((points, labels, outputs)), lengths)
                np.save('batch_points', result)
            else:
                result = np.array_split(np.column_stack((points, labels)), lengths)
                np.save('batch_points', result)
            return result

        if False and config.saving:
            # Training log file
            with open(join(config.saving_path, 'training.txt'), "w") as file:
                file.write('epochs steps out_loss offset_loss train_accuracy, train_f1, time\n')

            # Killing file (simply delete this file when you want to stop the training)
            PID_file = join(config.saving_path, 'running_PID.txt')
            if not exists(PID_file):
                with open(PID_file, "w") as file:
                    file.write('Launched with PyCharm')

            # Checkpoints directory
            checkpoint_directory = join(config.saving_path, 'checkpoints')
            if not exists(checkpoint_directory):
                makedirs(checkpoint_directory)
        else:
            checkpoint_directory = None
            PID_file = None

        # Loop variables
        t0 = time.time()
        t = [time.time()]
        last_display = time.time()
        mean_dt = np.zeros(1)

        # Start training loop
        for epoch in range(config.max_epoch):

            # Remove File for kill signal
            if epoch == config.max_epoch - 1 and exists(PID_file):
                remove(PID_file)

            self.step = 0
            results = []
            # for batch in training_loader:
            #
            #     # Check kill signal (running_PID.txt deleted)
            #     if config.saving and not exists(PID_file):
            #         continue
            #
            #     ##################
            #     # Processing batch
            #     ##################
            #
            #     # New time
            #     t = t[-1:]  # previous time
            #     t += [time.time()]  # start time
            #
            #     if 'cuda' in self.device.type:
            #         batch.to(self.device)
            #
            #     # zero the parameter gradients
            #     self.optimizer.zero_grad()
            #
            #     # Forward pass
            #     outputs = net(batch, config)
            #     loss = net.loss(outputs, batch.labels)
            #     acc = net.accuracy(outputs, batch.labels)
            #     f1 = net.f1(outputs, batch.labels)
            #
            #     # _save_batch_vis(batch,outputs)
            #     results.append([batch.input_inds.detach().cpu().numpy(), batch.labels.detach().cpu().numpy(),
            #                     torch.argmax(outputs.data, dim=1).cpu().numpy()])
            #     t += [time.time()]  # Forward pass time
            #
            #     # Backward + optimize
            #     loss.backward()
            #
            #     if config.grad_clip_norm > 0:
            #         # torch.nn.utils.clip_grad_norm_(net.parameters(), config.grad_clip_norm)
            #         torch.nn.utils.clip_grad_value_(net.parameters(), config.grad_clip_norm)
            #     self.optimizer.step()
            #
            #     torch.cuda.empty_cache()
            #     torch.cuda.synchronize(self.device)
            #
            #     t += [time.time()]  # backward pass time
            #
            #     # Average timing
            #     if self.step < 2:
            #         mean_dt = np.array(t[1:]) - np.array(t[:-1])
            #     else:
            #         mean_dt = 0.9 * mean_dt + 0.1 * (np.array(t[1:]) - np.array(t[:-1]))
            #
            #     # Console display (only one per second)
            #     if (t[-1] - last_display) > 1.0:
            #         last_display = t[-1]
            #         message = 'e{:03d}-i{:04d} => L={:.3f} acc={:3.0f}% f1 = {:3.0f}% / t(ms): {:5.1f} {:5.1f} {:5.1f})'
            #         print(message.format(self.epoch, self.step,
            #                              loss.item(),
            #                              100 * acc, 100 * f1,
            #                              1000 * mean_dt[0],
            #                              1000 * mean_dt[1],
            #                              1000 * mean_dt[2]))
            #
            #     # Log file
            #     if config.saving:
            #         with open(join(config.saving_path, 'training.txt'), "a") as file:
            #             message = '{:d} {:d} {:.3f} {:.3f} {:.3f} {:.3f} {:.3f}\n'
            #             file.write(message.format(self.epoch,
            #                                       self.step,
            #                                       net.output_loss,
            #                                       net.reg_loss,
            #                                       acc, f1,
            #                                       t[-1] - t0))
            #     #wandb.log({'Train/epoch': self.epoch,
            #     #           'Train/step': self.step,
            #     #           'Train/inner_output_loss': net.output_loss,
            #     #           'Train/inner_reg_loss': net.reg_loss,
            #     #           'Train/inner_sum_loss': loss.item(),
            #     #           'Train/inner_accuracy': acc,
            #      #          'Train/inner_f1': f1})
            #     self.step += 1
            #
            # ##############
            # # End of epoch
            # ##############
            #
            # # Check kill signal (running_PID.txt deleted)
            # if config.saving and not exists(PID_file):
            #     break
            #
            # # Update learning rate
            # if self.epoch in config.lr_decays:
            #     for param_group in self.optimizer.param_groups:
            #         param_group['lr'] *= config.lr_decays[self.epoch]
            #
            # # Update epoch
            # self.epoch += 1
            #
            # def _format_results(results):
            #     results = np.hstack(results)
            #     argsort_idxs = results[0].argsort()
            #     results = results[:, argsort_idxs]
            #     # point_idxs for indexing into the tree (sorted unique indexes),
            #     # unique_idxs to match up the labels/preds (idxs of results that create the unique array)
            #     # inverse_idxs (idxs of point_idxs that reconstruct results)
            #     point_idxs, unique_idxs, inverse_idxs, counts = np.unique(results[0], return_index=True,
            #                                                               return_inverse=True,
            #                                                               return_counts=True)
            #
            #     pts = training_loader.dataset.input_trees[0].data.base[point_idxs]
            #     lbls = results[1, unique_idxs]
            #     # prds = results[2, unique_idxs]
            #
            #     # TODO Voting (for idx in unique_idxs get
            #     splt_res = np.split(results[2], np.cumsum(counts)[:-1])
            #     pred_votes = np.array([mode(s)[0] for s in splt_res]).squeeze()
            #
            #     tn, fp, fn, tp = confusion_matrix(lbls, pred_votes).ravel()
            #     percentage_category_confusion = [round(tp / (tp + fn), 3), round(fp / (tn + fp), 3),
            #                                      round(fn / (tp + fn), 3), round(tn / (tn + fp), 3)]
            #     f1 = f1_score(lbls, pred_votes)
            #     mIoU = jaccard_score(lbls, pred_votes, average='macro')
            #     accuracy = accuracy_score(lbls, pred_votes)
            #     print(f"Training merged results:\n"
            #           f"{f1=:.3f}\n"
            #           f"{mIoU=:.3f}\n"
            #           f"{accuracy=:.3f}\n")
            #     wandb.log({'Train/epoch': self.epoch,
            #                'Train/TN': tn,
            #                'Train/FP': fp,
            #                'Train/FN': fn,
            #                'Train/FP': tp,
            #                'Train/category-TP': percentage_category_confusion[0],
            #                'Train/category-FP': percentage_category_confusion[1],
            #                'Train/category-FN': percentage_category_confusion[2],
            #                'Train/category-TN': percentage_category_confusion[3],
            #                'Train/F1': f1,
            #                'Train/mIoU': mIoU,
            #                'Train/accuracy': accuracy})
            #     if mIoU > self.best_train_mIoU:
            #         self.best_train_mIoU = mIoU
            #         return np.column_stack([pts, lbls, pred_votes, counts]), True
            #     else:
            #         return np.column_stack([pts, lbls, pred_votes, counts]), False
            #
            # # Saving
            # if config.saving:
            #     # Get current state dict
            #     save_dict = {'epoch': self.epoch,
            #                  'model_state_dict': net.state_dict(),
            #                  'optimizer_state_dict': self.optimizer.state_dict(),
            #                  'saving_path': config.saving_path}
            #
            #     # Save current state of the network (for restoring purposes)
            #     checkpoint_path = join(checkpoint_directory, 'current_chkp.tar')
            #     torch.save(save_dict, checkpoint_path)
            #     results, new_best_mIoU = _format_results(results) # lbls, preds, counts
            #     np.save(join(checkpoint_directory, 'current_chkp_results'), results)
            #     # wandb.save(checkpoint_path)
            #
            #     # Save checkpoints occasionally
            #     if (self.epoch + 1) % config.checkpoint_gap == 0:
            #         checkpoint_path = join(checkpoint_directory, 'chkp_{:04d}.tar'.format(self.epoch + 1))
            #         torch.save(save_dict, checkpoint_path)
            #     #     np.save(join(checkpoint_directory, f'chkp_{self.epoch+1}_results'), results)
            #     #     # wandb.save(checkpoint_path)
            #     # if new_best_mIoU:
            #     #     checkpoint_path = join(checkpoint_directory, 'best_train_chkp.tar'.format(self.epoch + 1))
            #     #     torch.save(save_dict, checkpoint_path)
            #     #     np.save(join(checkpoint_directory, f'best_train_chkp_results'), results)

            # Validation
            net.eval()
            self.validation(net, val_loader, config)
            net.train()
            exit(0)

        print('Finished Training')
        return

    # Validation methods
    # ------------------------------------------------------------------------------------------------------------------

    def validation(self, net, val_loader, config: Config):

        if config.dataset_task == 'cloud_segmentation':
            self.cloud_segmentation_validation(net, val_loader, config)
        else:
            raise ValueError('No validation method implemented for this network type')

    def cloud_segmentation_validation(self, net, val_loader, config, debug=False):
        """
        Validation method for cloud segmentation models
        """

        ############
        # Initialize
        ############

        t0 = time.time()

        # Choose validation smoothing parameter (0 for no smothing, 0.99 for big smoothing)
        val_smooth = 0.95
        softmax = torch.nn.Softmax(-1)

        # Do not validate if dataset has no validation cloud
        if val_loader.dataset.validation_split not in val_loader.dataset.all_splits:
            return

        # Number of classes including ignored labels
        nc_tot = val_loader.dataset.num_classes

        # Number of classes predicted by the model
        nc_model = config.num_classes

        # print(nc_tot)
        # print(nc_model)

        # Initiate global prediction over validation clouds
        if not hasattr(self, 'validation_probs'):
            self.validation_probs = [np.zeros((l.shape[0], nc_model))
                                     for l in val_loader.dataset.input_labels]
            self.val_proportions = np.zeros(nc_model, dtype=np.float32)
            i = 0
            for label_value in val_loader.dataset.label_values:
                if label_value not in val_loader.dataset.ignored_labels:
                    self.val_proportions[i] = np.sum([np.sum(labels == label_value)
                                                      for labels in val_loader.dataset.validation_labels])
                    i += 1

        #####################
        # Network predictions
        #####################

        predictions = []
        targets = []

        t = [time.time()]
        last_display = time.time()
        mean_dt = np.zeros(1)

        t1 = time.time()

        # Start validation loop
        for i, batch in enumerate(val_loader):

            # New time
            t = t[-1:]
            t += [time.time()]

            if 'cuda' in self.device.type:
                batch.to(self.device)

            # Forward pass
            outputs = net(batch, config, do_AL=config.active_learning)

            # Get probs and labels
            stacked_probs = softmax(outputs).cpu().detach().numpy() # regularly this has shape (P,2), in AL it has shape (R,P,2)
            # Probably want to change this to get the probs -> preds now and then get the variances
            labels = batch.labels.cpu().numpy()
            lengths = batch.lengths[0].cpu().numpy()
            in_inds = batch.input_inds.cpu().numpy()
            cloud_inds = batch.cloud_inds.cpu().numpy()
            torch.cuda.synchronize(self.device)

            # Get predictions and labels per instance
            # ***************************************

            i0 = 0
            for b_i, length in enumerate(lengths):
                # Get prediction
                target = labels[i0:i0 + length]
                probs = stacked_probs[i0:i0 + length]
                inds = in_inds[i0:i0 + length]
                c_i = cloud_inds[b_i]

                # Update current probs in whole cloud
                self.validation_probs[c_i][inds] = val_smooth * self.validation_probs[c_i][inds] \
                                                   + (1 - val_smooth) * probs

                # Stack all prediction for this epoch
                predictions.append(probs)
                targets.append(target)
                i0 += length

            # Average timing
            t += [time.time()]
            mean_dt = 0.95 * mean_dt + 0.05 * (np.array(t[1:]) - np.array(t[:-1]))

            # Display
            if (t[-1] - last_display) > 1.0:
                last_display = t[-1]
                message = 'Validation : {:.1f}% (timings : {:4.2f} {:4.2f})'
                print(message.format(100 * i / config.validation_size,
                                     1000 * (mean_dt[0]),
                                     1000 * (mean_dt[1])))

        t2 = time.time()

        # # Confusions for our subparts of validation set
        # Confs = np.zeros((len(predictions), nc_tot, nc_tot), dtype=np.int32)
        # for i, (probs, truth) in enumerate(zip(predictions, targets)):
        #
        #     # Insert false columns for ignored labels
        #     for l_ind, label_value in enumerate(val_loader.dataset.label_values):
        #         if label_value in val_loader.dataset.ignored_labels:
        #             probs = np.insert(probs, l_ind, 0, axis=1)
        #
        #     # Predicted labels
        #     preds = val_loader.dataset.label_values[np.argmax(probs, axis=1)]
        #
        #     # Confusions
        #     Confs[i, :, :] = fast_confusion(truth, preds, val_loader.dataset.label_values).astype(np.int32)
        #
        # t3 = time.time()
        #
        # # Sum all confusions
        # C = np.sum(Confs, axis=0).astype(np.float32)
        #
        # # Remove ignored labels from confusions
        # for l_ind, label_value in reversed(list(enumerate(val_loader.dataset.label_values))):
        #     if label_value in val_loader.dataset.ignored_labels:
        #         C = np.delete(C, l_ind, axis=0)
        #         C = np.delete(C, l_ind, axis=1)
        #
        # # Balance with real validation proportions
        # C *= np.expand_dims(self.val_proportions / (np.sum(C, axis=1) + 1e-6), 1)
        #
        # t4 = time.time()
        #
        # # Objects IoU
        # IoUs = IoU_from_confusions(C)
        #
        # t5 = time.time()
        #
        # # Saving (optionnal)
        # if config.saving:
        #
        #     # Name of saving file
        #     test_file = join(config.saving_path, 'val_IoUs.txt')
        #
        #     # Line to write:
        #     line = ''
        #     for IoU in IoUs:
        #         line += '{:.3f} '.format(IoU)
        #     line = line + '\n'
        #
        #     # Write in file
        #     if exists(test_file):
        #         with open(test_file, "a") as text_file:
        #             text_file.write(line)
        #     else:
        #         with open(test_file, "w") as text_file:
        #             text_file.write(line)
        #
        #     # Save potentials
        #     pot_path = join(config.saving_path, 'potentials')
        #     if not exists(pot_path):
        #         makedirs(pot_path)
        #     files = val_loader.dataset.files
        #     for i, file_path in enumerate(files):
        #         pot_points = np.array(val_loader.dataset.pot_trees[i].data, copy=False)
        #         cloud_name = file_path.split('/')[-1]
        #         pot_name = join(pot_path, cloud_name)
        #         pots = val_loader.dataset.potentials[i].numpy().astype(np.float32)
        #         write_ply(pot_name,
        #                   [pot_points.astype(np.float32), pots],
        #                   ['x', 'y', 'z', 'pots'])
        #
        # t6 = time.time()
        #
        # # Print instance mean
        # mIoU = 100 * np.mean(IoUs)
        # print('{:s} mean IoU = {:.1f}%'.format(config.dataset, mIoU))
        #
        # # Save predicted cloud occasionally
        # if config.saving and (self.epoch + 1) % config.checkpoint_gap == 0:
        #     val_path = join(config.saving_path, 'val_preds_{:d}'.format(self.epoch + 1))
        #     if not exists(val_path):
        #         makedirs(val_path)
        #     files = val_loader.dataset.files
        #     for i, file_path in enumerate(files):
        #
        #         # Get points
        #         points = val_loader.dataset.load_evaluation_points(file_path)
        #
        #         # Get probs on our own ply points
        #         sub_probs = self.validation_probs[i]
        #
        #         # Insert false columns for ignored labels
        #         for l_ind, label_value in enumerate(val_loader.dataset.label_values):
        #             if label_value in val_loader.dataset.ignored_labels:
        #                 sub_probs = np.insert(sub_probs, l_ind, 0, axis=1)
        #
        #         # Get the predicted labels
        #         sub_preds = val_loader.dataset.label_values[np.argmax(sub_probs, axis=1).astype(np.int32)]
        #
        #         # Reproject preds on the evaluations points
        #         preds = (sub_preds[val_loader.dataset.test_proj[i]]).astype(np.int32)
        #
        #         # Path of saved validation file
        #         cloud_name = file_path.split('/')[-1]
        #         val_name = join(val_path, cloud_name)
        #
        #         # Save file
        #         labels = val_loader.dataset.validation_labels[i].astype(np.int32)
        #         write_ply(val_name,
        #                   [points, preds, labels],
        #                   ['x', 'y', 'z', 'preds', 'class'])

        # # Confusions for our subparts of validation set
        # Confs = np.zeros((len(predictions), nc_tot, nc_tot), dtype=np.int32)
        # for i, (probs, truth) in enumerate(zip(predictions, targets)):
        #
        #     # Insert false columns for ignored labels
        #     for l_ind, label_value in enumerate(val_loader.dataset.label_values):
        #         if label_value in val_loader.dataset.ignored_labels:
        #             probs = np.insert(probs, l_ind, 0, axis=1)
        #
        #     # Predicted labels
        #     preds = val_loader.dataset.label_values[np.argmax(probs, axis=1)]
        #
        #     # Confusions
        #     Confs[i, :, :] = fast_confusion(truth, preds, val_loader.dataset.label_values).astype(np.int32)

        # Convert ground truth and prediction labels
        targets = np.hstack(targets)
        preds = np.vstack(predictions)
        preds = val_loader.dataset.label_values[np.argmax(preds, axis=1)]
        tn, fp, fn, tp = confusion_matrix(targets, preds).ravel()
        percentage_category_confusion = [round(tp / (tp + fn), 3), round(fp / (tn + fp), 3),
                                         round(fn / (tp + fn), 3), round(tn / (tn + fp), 3)]

        f1 = f1_score(targets, preds)
        keepIoU, discardIoU = jaccard_score(targets, preds, average=None)
        mIoU = jaccard_score(targets, preds, average='macro')
        accuracy = accuracy_score(targets, preds)
        t3 = time.time()

        new_best_mIoU = False
        if mIoU > self.best_val_mIoU:
            self.best_val_mIoU = mIoU
            new_best_mIoU = True
        # # Sum all confusions
        # C = np.sum(Confs, axis=0).astype(np.float32)
        #
        # # Remove ignored labels from confusions
        # for l_ind, label_value in reversed(list(enumerate(val_loader.dataset.label_values))):
        #     if label_value in val_loader.dataset.ignored_labels:
        #         C = np.delete(C, l_ind, axis=0)
        #         C = np.delete(C, l_ind, axis=1)
        #
        # # Balance with real validation proportions
        # # Multiply actual_neg (top row) and actual_pos by proportion in dataset. CHECK I have no idea why this is here
        # C *= np.expand_dims(self.val_proportions / (np.sum(C, axis=1) + 1e-6), 1)

        t4 = time.time()

        # Objects IoU
        # IoUs, _f1 = IoU_from_confusions(C, calculate_f1=True)
        t5 = time.time()

        # Saving (optional)
        if False and config.saving:

            # Name of saving file
            test_file = join(config.saving_path, 'val_IoUs.txt')

            # Line to write:
            line = ''
            for IoU in [keepIoU, discardIoU]:
                line += '{:.3f} '.format(IoU)
            # line = line + f'{f1}' + '\n'

            # Write in file
            if exists(test_file):
                with open(test_file, "a") as text_file:
                    text_file.write(line)
            else:
                with open(test_file, "w") as text_file:
                    text_file.write(line)

            # Save potentials
            if val_loader.dataset.use_potentials:
                pot_path = join(config.saving_path, 'potentials')
                if not exists(pot_path):
                    makedirs(pot_path)
                files = val_loader.dataset.files
                for i, file_path in enumerate(files):
                    pot_points = np.array(val_loader.dataset.pot_trees[i].data, copy=False)
                    cloud_name = file_path.split('/')[-1]
                    pot_name = join(pot_path, cloud_name)
                    pots = val_loader.dataset.potentials[i].numpy().astype(np.float32)
                    write_ply(pot_name,
                              [pot_points.astype(np.float32), pots],
                              ['x', 'y', 'z', 'pots'])

        t6 = time.time()

        # Print instance mean
        print('{:s} mean IoU = {:.1f}%, F1 = {:.1f}%'.format(config.dataset, mIoU*100, f1*100))
        wandb.log({'Validation/TN': tn,
                   'Validation/FP': fp,
                   'Validation/FN': fn,
                   'Validation/TP': tp,
                   'Validation/category-TP': percentage_category_confusion[0],
                   'Validation/category-FP': percentage_category_confusion[1],
                   'Validation/category-FN': percentage_category_confusion[2],
                   'Validation/category-TN': percentage_category_confusion[3],
                   'Validation/F1': f1,
                   'Validation/accuracy': accuracy,
                   'Validation/mIoU': mIoU,
                   })

        def gather_validation_save_data():
            # Get points
            points = val_loader.dataset.load_evaluation_points(file_path)

            # Get probs on our own ply points
            sub_probs = self.validation_probs[i]

            # Insert false columns for ignored labels
            for l_ind, label_value in enumerate(val_loader.dataset.label_values):
                if label_value in val_loader.dataset.ignored_labels:
                    sub_probs = np.insert(sub_probs, l_ind, 0, axis=1)

            # Get the predicted labels
            sub_preds = val_loader.dataset.label_values[np.argmax(sub_probs, axis=1).astype(np.int32)]

            # Reproject preds on the evaluations points
            preds = (sub_preds[val_loader.dataset.test_proj[i]]).astype(np.int32)

            # Path of saved validation file
            cloud_name = file_path.split('/')[-1]
            val_name = join(val_path, cloud_name)

            # Save file
            labels = val_loader.dataset.validation_labels[i].astype(np.int32)

            return val_name, points, preds, labels

        # Save predicted cloud occasionally NOTE this is where we save the validation results occasionally
        if False and config.saving and (self.epoch + 1) % config.checkpoint_gap == 0 or new_best_mIoU:
            val_path = join(config.saving_path, 'val_preds_{:d}'.format(self.epoch + 1))
            if not exists(val_path):
                makedirs(val_path)
            files = val_loader.dataset.files
            for i, file_path in enumerate(files):
                val_name, points, preds, labels = gather_validation_save_data()
                if (self.epoch + 1) % config.checkpoint_gap == 0:
                    write_ply(val_name,
                              [points, preds, labels],
                              ['x', 'y', 'z', 'preds', 'class'])
                if new_best_mIoU:
                    write_ply(val_name, # TODO Check how to fix this correctly
                              [points, preds, labels],
                              ['x', 'y', 'z', 'preds', 'class'])
        #         TODO Active Learning
        #         Need to output points, preds, targets, variance, and features.
        #         Variance must be normalised [-1,1]
        #         Variances and Features must be aggregated into cells.

        # Display timings
        t7 = time.time()
        if debug:
            print('\n************************\n')
            print('Validation timings:')
            print('Init ...... {:.1f}s'.format(t1 - t0))
            print('Loop ...... {:.1f}s'.format(t2 - t1))
            print('Confs ..... {:.1f}s'.format(t3 - t2))
            print('Confs bis . {:.1f}s'.format(t4 - t3))
            print('IoU ....... {:.1f}s'.format(t5 - t4))
            print('Save1 ..... {:.1f}s'.format(t6 - t5))
            print('Save2 ..... {:.1f}s'.format(t7 - t6))
            print('\n************************\n')

        return

