#!/bin/bash

cd /home/luc/PycharmProjects/KPConv-PyTorch
for dataset in Church Lunnahoja Monument Bagni_Nerone Montelupo Piazza
do
  for split in "2.5%" "5%" "25%" "50%"
  do
# echo python3 train_Masters.py saving_path dataset splits previous_training_path (s3dis-xyz=finetuning, last_savepath=resume)

echo "#!/bin/sh

#SBATCH --account=a100free
#SBATCH --partition=a100
#SBATCH --nodes=1 --ntasks=10 --gres=gpu:a100-2g-10gb:1
#SBATCH --time=12:00:00
#SBATCH --job-name=\"${dataset}_${split}\"
#SBATCH --mail-user=hywluc001@myuct.ac.za
#SBATCH --mail-type=ALL
#SBATCH -e slurm-${dataset}_${split}.err
#SBATCH -o slurm-${dataset}_${split}.out

CUDA_VISIBLE_DEVICES=\$(ncvd)

module load python/miniconda3-py39
source activate kpconv

cd KPConv-PyTorch
python3 train_Masters.py ${dataset}_${split} ${dataset} ${split} s3dis-xyz
" > slurm_scripts/${dataset}_${split}.sh

echo "#!/bin/sh

#SBATCH --account=a100free
#SBATCH --partition=a100
#SBATCH --nodes=1 --ntasks=10 --gres=gpu:a100-2g-10gb:1
#SBATCH --time=12:00:00
#SBATCH --job-name=\"${dataset}_${split}\"
#SBATCH --mail-user=hywluc001@myuct.ac.za
#SBATCH --mail-type=ALL
#SBATCH -e slurm-${dataset}_${split}-s3dis.err
#SBATCH -o slurm-${dataset}_${split}-s3dis.out

CUDA_VISIBLE_DEVICES=\$(ncvd)

module load python/miniconda3-py39
source activate kpconv

cd KPConv-PyTorch
python3 train_Masters.py ${dataset}_${split} ${dataset} ${split}
" > slurm_scripts/${dataset}_${split}_'s3dis'.sh
  done
done

