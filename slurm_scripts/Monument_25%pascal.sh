#!/bin/sh

#SBATCH --account=gpumk
#SBATCH --partition=gpumk
#SBATCH --nodes=1 --ntasks=8 --gres=gpu:pascal:1
#SBATCH --time=12:00:00
#SBATCH --job-name="Monument_25%"
#SBATCH --mail-user=hywluc001@myuct.ac.za
#SBATCH --mail-type=ALL
#SBATCH -e slurm-Monument_25%.err
#SBATCH -o slurm-Monument_25%.out

module load python/miniconda3-py39
source activate /scratch/hywluc001/conda-envs/kpconv-pascal

cd KPConv-PyTorch
python3 train_Masters.py Monument_25% Monument 25%
