#!/bin/bash
#SBATCH -p taniu
#SBATCH -t 1-0
#SBATCH --mem=36G
#SBATCH -c 12
#SBATCH --gres=gpu:4

# Run processes in parallel, each assigned to a specific GPU
CUDA_VISIBLE_DEVICES=0 python run_habitization_experiment.py --beta_o 0.3 --seed 0 &
CUDA_VISIBLE_DEVICES=0 python run_habitization_experiment.py --beta_o 0.3 --seed 1 &
CUDA_VISIBLE_DEVICES=0 python run_habitization_experiment.py --beta_o 0.3 --seed 2 &
CUDA_VISIBLE_DEVICES=1 python run_habitization_experiment.py --beta_o 0.3 --seed 3 &
CUDA_VISIBLE_DEVICES=1 python run_habitization_experiment.py --beta_o 0.3 --seed 4 &
CUDA_VISIBLE_DEVICES=1 python run_habitization_experiment.py --beta_o 0.3 --seed 5 &
CUDA_VISIBLE_DEVICES=2 python run_habitization_experiment.py --beta_o 0.3 --seed 6 &
CUDA_VISIBLE_DEVICES=2 python run_habitization_experiment.py --beta_o 0.3 --seed 7 &
CUDA_VISIBLE_DEVICES=2 python run_habitization_experiment.py --beta_o 0.3 --seed 8 &
CUDA_VISIBLE_DEVICES=3 python run_habitization_experiment.py --beta_o 0.3 --seed 9 &
CUDA_VISIBLE_DEVICES=3 python run_habitization_experiment.py --beta_o 0.3 --seed 10 &
CUDA_VISIBLE_DEVICES=3 python run_habitization_experiment.py --beta_o 0.3 --seed 11 &

# Wait for all processes to finish before exiting the job
wait

