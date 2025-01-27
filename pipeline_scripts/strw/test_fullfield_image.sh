#!/bin/bash

#EXTRACT THE FULL FIELD ON 2.5 DEGREES

SING_IMAGE=/net/lofar1/data1/sweijen/software/LOFAR/singularity/lofar_sksp_fedora31_ddf.sif
SING_BIND=/tmp,/dev/shm,/disks/paradata,/data1,/net/lofar1,/net/rijn,/net/nederrijn/,/net/bovenrijn,/net/botlek,/net/para10,/net/lofar2,/net/lofar3,/net/lofar4,/net/lofar5,/net/lofar6,/net/lofar7,/disks/ftphome,/net/krommerijn,/net/voorrijn,/net/achterrijn,/net/tussenrijn,/net/ouderijn,/net/nieuwerijn,/net/lofar8,/net/lofar9,/net/rijn8,/net/rijn7,/net/rijn5,/net/rijn3,/net/rijn2
SCRIPT_FOLDER=/home/jurjendejong/scripts/lofar_helpers

#PREPARE
singularity exec -B ${SING_BIND} /net/rijn/data2/rvweeren/data/pill-latest.simg python ${SCRIPT_FOLDER}/move_files/move_extract_files.py --frm /disks/paradata/shimwell/LoTSS-DR2/archive_other/A399_DEEP --to /net/nieuwerijn/data2/jurjendejong/A399_extracted
cp -r /disks/paradata/shimwell/LoTSS-DR2/archive_other/A399_DEEP/*ms.archive /net/nieuwerijn/data2/jurjendejong/A399_extracted/
cp /net/nieuwerijn/data2/jurjendejong/extracted.reg /net/nieuwerijn/data2/jurjendejong/A399_extracted/
cd /net/nieuwerijn/data2/jurjendejong/A399_extracted

#EXTRACT
singularity exec -B ${SING_BIND} ${SING_IMAGE} python ~/scripts/lofar_helpers/supporting_scripts/reinout/sub-sources-outside-region_noconcat.py --boxfile extracted.reg --freqavg=1 --timeavg=1 --overwriteoutput --noconcat --nophaseshift --adjustboxrotation=False --prefixname extr
rm -rf /net/nieuwerijn/data2/jurjendejong/A399_extracted/L6*.ms
rm -rf /net/nieuwerijn/data2/jurjendejong/A399_extracted/L6*.ms.archive

#MAKE DICOMODEL
singularity exec -B ${SING_BIND} ${SING_IMAGE} python /home/jurjendejong/scripts/lofar_helpers/supporting_scripts/make_new_dicomodel.py

#MAKE NEW IMAGE
singularity exec -B ${SING_BIND} /net/rijn/data2/rvweeren/data/pill-latest.simg python ~/scripts/lofar_helpers/imaging/make_new_image_A399_test.py