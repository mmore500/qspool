#!/bin/bash
#SBATCH -n 1
#SBATCH --time=00:30:00

echo "hello from example2.slurm.sh"
touch "/tmp/touched-by-example2.slurm.sh"

# additional line to differentiate $(wc -l)
