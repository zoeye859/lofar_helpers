#!/bin/bash
#SBATCH -c 4
#SBATCH -p normal
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=jurjendejong@strw.leidenuniv.nl
#SBATCH --job-name=merge
#SBATCH --array=0-5%1

SOURCE=$1
SING_IMAGE=/home/lofarvwf-jdejong/singularities/pill-latest.simg
SING_BIND=/project/lofarvwf/Share/jdejong,/home/lofarvwf-jdejong/scripts
SCRIPT_FOLDER=/home/lofarvwf-jdejong/scripts/lofar_helpers/merge_selfcals
SELFCAL=/project/lofarvwf/Share/jdejong/output/${SOURCE}/selfcal

cd ${SELFCAL} && singularity exec -B ${SING_BIND} ${SING_IMAGE} python ${SCRIPT_FOLDER}/merge_selfcals.py -d ${SELFCAL} -a ${SLURM_ARRAY_TASK_ID}
singularity exec -B ${SING_BIND} ${SING_IMAGE} losoto ${SELFCAL}/all_directions${SLURM_ARRAY_TASK_ID}.h5 ~/scripts/lofar_helpers/supporting_scripts/parsets/plot${SLURM_ARRAY_TASK_ID}.parset