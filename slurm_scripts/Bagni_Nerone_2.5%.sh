#!/bin/sh

#SBATCH --account=a100free
#SBATCH --partition=a100
#SBATCH --nodes=1 --ntasks=10 --gres=gpu:a100-2g-10gb:1
#SBATCH --time=12:00:00
#SBATCH --job-name="Bagni_Nerone_2.5%"
#SBATCH --mail-user=hywluc001@myuct.ac.za
#SBATCH --mail-type=ALL

CUDA_VISIBLE_DEVICES=$(ncvd)

module load python/miniconda3-py39
source activate kpconv

cd KPConv-PyTorch
python3 train_Masters.py Bagni_Nerone_2.5% Bagni_Nerone 2.5% s3dis-xyz

