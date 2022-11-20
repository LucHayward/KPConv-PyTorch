#!/bin/bash

cd /home/luc/PycharmProjects/KPConv-PyTorch
for dataset in Church Lunnahoja Monument Bagni_Nerone Montelupo Piazza
do
  for split in "2.5%" "5%" "25%" "50%"
  do
# echo python3 train_Masters.py saving_path dataset splits previous_training_path (s3dis-xyz=finetuning, last_savepath=resume)
  echo python3 train_Masters.py ${dataset}_${split} ${dataset} ${split} s3dis-xyz
  echo python3 train_Masters.py ${dataset}_${split} ${dataset} ${split}
  done
done
