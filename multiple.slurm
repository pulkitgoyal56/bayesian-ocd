#!/bin/bash
#SBATCH -p taniu
#SBATCH -t 1-6
#SBATCH --mem=36G
#SBATCH -c 14
#SBATCH --gres=gpu:2
#SBATCH --array=0-10  # This will create 11 different jobs

# Define beta_o values for each job
# beta_o_values=(0 0.01 0.03 0.05 0.06 0.08 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 -1.0 -0.9 -0.8 -0.7 -0.6 -0.5 -0.4 -0.3 -0.2 -0.1 -0.08 -0.06 -0.05 -0.03 -0.01)
beta_o_values=(0 5.0 10.0 50.0 100.0 500.0 -5.0 -10.0 -50.0 -100.0 -500.0)

# Get the beta_o value for this job
beta_o=${beta_o_values[$SLURM_ARRAY_TASK_ID]}

# # Run the 6 processes in parallel, assigning each to a specific GPU
# CUDA_VISIBLE_DEVICES=0 python run_habitization_experiment.py --beta_o $beta_o --seed 0 &
python run_habitization_experiment.py --beta_o $beta_o --seed 0 --n_seed 6

# Wait for all processes to finish before exiting the job
wait

