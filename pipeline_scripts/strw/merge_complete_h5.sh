#!/bin/bash

#merge all best solutions from LoTSS and own selfcal

OBSERVATION=$1
FOLDER=/net/tussenrijn/data2/jurjendejong/${OBSERVATION}
SING_IMAGE=/net/rijn/data2/rvweeren/data/pill-latest.simg
SING_BIND=/tmp,/dev/shm,/disks/paradata,/data1,/net/lofar1,/net/rijn,/net/nederrijn/,/net/bovenrijn,/net/botlek,/net/para10,/net/lofar2,/net/lofar3,/net/lofar4,/net/lofar5,/net/lofar6,/net/lofar7,/disks/ftphome,/net/krommerijn,/net/voorrijn,/net/achterrijn,/net/tussenrijn,/net/ouderijn,/net/nieuwerijn,/net/lofar8,/net/lofar9,/net/rijn8,/net/rijn7,/net/rijn5,/net/rijn4,/net/rijn3,/net/rijn2
SCRIPT_FOLDER=~/scripts/lofar_helpers

OUTPUT_FOLDER=${FOLDER}/result_filtered
mkdir ${OUTPUT_FOLDER}

cd ${OUTPUT_FOLDER}

#converging and merging .npz to .h5 files from LoTSS output
singularity exec -B ${SING_BIND} ${SING_IMAGE} killMS2H5parm.py lotss_slow.h5 ${FOLDER}/extract/DDS3_full_slow*merged.npz --nofulljones
singularity exec -B ${SING_BIND} ${SING_IMAGE} killMS2H5parm.py lotss_smoothed.h5 ${FOLDER}/extract/DDS3_full*smoothed.npz --nofulljones
singularity exec -B ${SING_BIND} ${SING_IMAGE} python ${SCRIPT_FOLDER}/h5_merger.py -out lotss_full_merged.h5 -in lotss_*.h5 -ms '/net/tussenrijn/data2/jurjendejong/L626678/result/*.goodtimes' --convert_tec 0

#h5 filter
singularity exec -B ${SING_BIND} ${SING_IMAGE} python ${SCRIPT_FOLDER}/supporting_scripts/h5_filter.py -f ${FOLDER}/extract/image_full_ampphase_di_m.NS.app.restored.fits -ac 2.5 -in false -h5out lotss_full_merged_filtered.h5 -h5in lotss_full_merged.h5
#singularity exec -B ${SING_BIND} ${SING_IMAGE} python ${SCRIPT_FOLDER}/supporting_scripts/h5_filter.py -f ${FOLDER}/extract/image_full_ampphase_di_m.NS.app.restored.fits -ac 2.5 -in true -h5out all_directions_filtered.h5 -h5in ${FOLDER}/result/all_directions.h5

#merging h5 files
singularity exec -B ${SING_BIND} ${SING_IMAGE} python ${SCRIPT_FOLDER}/h5_merger.py -out complete_merged.h5 -in lotss_full_merged_filtered.h5 all_directions_filtered.h5 --convert_tec 0