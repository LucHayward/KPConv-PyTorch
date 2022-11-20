echo "Queuing up all jobs"

for file in KPConv-PyTorch/slurm_scripts/*.sh
do
  sbatch $file
done
