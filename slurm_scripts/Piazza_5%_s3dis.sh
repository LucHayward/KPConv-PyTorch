#!/bin/sh

#SBATCH --account=a100free
#SBATCH --partition=a100
#SBATCH --nodes=1 --ntasks=10 --gres=gpu:a100-2g-10gb:1
#SBATCH --time=12:00:00
#SBATCH --job-name="Piazza_5%-s3dis"
#SBATCH --mail-user=hywluc001@myuct.ac.za
#SBATCH --mail-type=ALL
#SBATCH -e slurm-Piazza_5%-s3dis.err
#SBATCH -o slurm-Piazza_5%-s3dis.out

CUDA_VISIBLE_DEVICES=$(ncvd)

module load python/miniconda3-py39
source activate /scratch/hywluc001/conda-envs/kpconv

cd KPConv-PyTorch
python3 train_Masters.py Piazza_5% Piazza 5% s3dis-xyz

