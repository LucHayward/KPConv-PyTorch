#!/bin/bash

cd /home/luc/PycharmProjects/KPConv-PyTorch
#for dataset in Church Lunnahoja Monument Bagni_Nerone Montelupo Piazza
for dataset in Piazza
do
#  for split in "2.5%" "5%" "25%" "50%"
  for split in "50%"
  do
# echo python3 train_Masters.py saving_path dataset splits previous_training_path (s3dis-xyz=finetuning, last_savepath=resume)
#  echo python3 train_Masters.py ${dataset}_${split} ${dataset} ${split} s3dis-xyz
#  echo python3 train_Masters.py ${dataset}_${split} ${dataset} ${split}

  python3 train_Masters.py ${dataset}_${split} ${dataset} 50% ${dataset}_${split}
#  python3 train_Masters.py ${dataset}_${split}_s3dis-xyz ${dataset} 50% ${dataset}_${split}_s3dis-xyz

  done
done


