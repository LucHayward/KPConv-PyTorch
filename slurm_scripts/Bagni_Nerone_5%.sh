#!/bin/sh

#SBATCH --account=a100free
#SBATCH --partition=a100
#SBATCH --nodes=1 --ntasks=10 --gres=gpu:a100-3g-20gb:1
#SBATCH --time=12:00:00
#SBATCH --job-name="Bagni_Nerone_5%"
#SBATCH --mail-user=hywluc001@myuct.ac.za
#SBATCH --mail-type=ALL
#SBATCH -e slurm-Bagni_Nerone_5%.err
#SBATCH -o slurm-Bagni_Nerone_5%.out

CUDA_VISIBLE_DEVICES=$(ncvd)

module load python/miniconda3-py39
source activate kpconv

cd KPConv-PyTorch
python3 train_Masters.py Bagni_Nerone_5% Bagni_Nerone 5%

