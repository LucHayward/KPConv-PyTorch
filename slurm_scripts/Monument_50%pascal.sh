#!/bin/sh

#SBATCH --account=gpumk
#SBATCH --partition=gpumk
#SBATCH --nodes=1 --ntasks=8 --gres=gpu:pascal:1
#SBATCH --time=12:00:00
#SBATCH --job-name="Monument_50%"
#SBATCH --mail-user=hywluc001@myuct.ac.za
#SBATCH --mail-type=ALL
#SBATCH -e slurm-Monument_50%.err
#SBATCH -o slurm-Monument_50%.out

module load python/miniconda3-py39
source activate /scratch/hywluc001/conda-envs/kpconv-pascal

cd KPConv-PyTorch
python3 train_Masters.py Monument_50% Monument 50%
