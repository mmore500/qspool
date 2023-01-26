#!/bin/bash
#SBATCH -n 1
#SBATCH --time=00:30:00

echo "hello from example1.slurm.sh"
touch "/tmp/touched-by-example1.slurm.sh"
