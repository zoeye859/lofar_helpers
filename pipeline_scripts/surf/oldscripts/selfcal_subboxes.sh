#!/bin/bash
#SBATCH -c 20
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=jurjendejong@strw.leidenuniv.nl
#SBATCH --array=1-6

SOURCE=$1 #L626678
TO=/project/lofarvwf/Share/jdejong/output/${SOURCE}/selfcal
N=$2 #box number

until [[ -f "${TO}/box_${N}.${SLURM_ARRAY_TASK_ID}/command.sh" ]]
do
  sleep 5
done
START="$(date -u +%s)"
srun ${TO}/box_${N}.${SLURM_ARRAY_TASK_ID}/command.sh
END="$(date -u +%s)"
echo "Selfcal in $((${END}-${START})) seconds" > ${TO}/finished/box_${N}.${SLURM_ARRAY_TASK_ID}.txt