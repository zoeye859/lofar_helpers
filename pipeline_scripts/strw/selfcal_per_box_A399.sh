#!/bin/bash

BOX=$1
SING_IMAGE=/net/rijn/data2/rvweeren/data/pill-latest.simg
SING_BIND=/tmp,/dev/shm,/disks/paradata,/data1,/net/lofar1,/net/rijn,/net/nederrijn/,/net/bovenrijn,/net/botlek,/net/para10,/net/lofar2,/net/lofar3,/net/lofar4,/net/lofar5,/net/lofar6,/net/lofar7,/disks/ftphome,/net/krommerijn,/net/voorrijn,/net/achterrijn,/net/tussenrijn,/net/ouderijn,/net/nieuwerijn,/net/lofar8,/net/lofar9,/net/rijn8,/net/rijn7,/net/rijn5,/net/rijn4,/net/rijn3,/net/rijn2
SCRIPT_FOLDER=/home/jurjendejong/scripts/lofar_helpers

#cp -r /net/nieuwerijn/data2/jurjendejong/box_33_new_extract/Abell* /net/nieuwerijn/data2/jurjendejong/box_33_new_selfcal/
cp -r /net/nieuwerijn/data2/jurjendejong/box_33_new_extract/box_33_new.reg /net/nieuwerijn/data2/jurjendejong/box_33_new_selfcal/selfcal_A399_new
cd /net/nieuwerijn/data2/jurjendejong/box_33_new_selfcal
singularity exec -B ${SING_BIND} ${SING_IMAGE} python ${SCRIPT_FOLDER}/pipeline_scripts/strw/prepare_data_A399.py --box ${BOX}
cd selfcal_A399_new
singularity exec -B ${SING_BIND} /net/lofar1/data1/sweijen/software/LOFAR/singularity/lofar_sksp_fedora31_ddf.sif python /net/rijn/data2/rvweeren/LoTSS_ClusterCAL/runwscleanLBautoR.py -b box_${BOX}.reg --auto --imager=DDFACET --helperscriptspath=/net/rijn/data2/rvweeren/LoTSS_ClusterCAL --autofrequencyaverage-calspeedup --useaoflagger --uvmin=750 --tecfactorsolint=1.5 --gainfactorsolint=2.0 *box_${BOX}.dysco.sub.shift.avg.weights.ms.archive*