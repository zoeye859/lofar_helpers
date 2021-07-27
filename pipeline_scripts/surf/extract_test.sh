#!/bin/bash
#SBATCH -c 32
#SBATCH --ntaks-per-node=1
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=jurjendejong@strw.leidenuniv.nl
#SBATCH --array=1-200%10

SOURCE=$1 #L626678
TO=/project/lofarvwf/Share/jdejong/output/${SOURCE}
SCRIPT_FOLDER=/home/lofarvwf-jdejong/scripts

SING_IMAGE=/project/lofarvwf/Software/lofar_sksp_fedora27_ddf_slurmfix.sif
SING_BIND=/project/lofarvwf/Share/jdejong

#LAST BOX NUMBER
TOTAL_BOXES=$(ls -dq ${TO}/boxes/box*.reg | wc -l)
echo "There are ${END_N} boxes to extract"

echo "-----STARTED EXTRACT-----"
if [[ ! ${SLURM_ARRAY_TASK_ID} > ${TOTAL_BOXES} ]]
then
  sleep 10
  echo "box_${SLURM_ARRAY_TASK_ID}" > ${TO}/test/test_${SLURM_ARRAY_TASK_ID}.txt
  echo "Extracted box_${BOX}"
else
  :
fi
echo "-----FINISHED EXTRACT-----"