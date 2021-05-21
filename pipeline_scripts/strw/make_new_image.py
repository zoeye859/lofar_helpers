import os
from argparse import ArgumentParser
from glob import glob

parser = ArgumentParser()
parser.add_argument('-from', '--from_where', type=str, help='data from where')
parser.add_argument('-to', '--to_where', type=str, help='to where')
args = parser.parse_args()

LOCATION=args.to_where+'/result'#/net/tussenrijn/data2/jurjendejong/L626678
LOCATION_BACKUP=args.to_where+'/result_backup'
FROM=args.from_where #/disks/paradata/shimwell/LoTSS-DR2/archive_other/L626678
SING_IMAGE='/net/rijn/data2/rvweeren/data/pill-latestMay2021.simg'
SING_BIND='/tmp,/dev/shm,/disks/paradata,/data1,/net/lofar1,/net/rijn,/net/nederrijn/,/net/bovenrijn,/net/botlek,/net/para10,/net/lofar2,/net/lofar3,/net/lofar4,/net/lofar5,/net/lofar6,/net/lofar7,/disks/ftphome,/net/krommerijn,/net/voorrijn,/net/achterrijn,/net/tussenrijn,/net/ouderijn,/net/nieuwerijn,/net/lofar8,/net/lofar9,/net/rijn8,/net/rijn7,/net/rijn5,/net/rijn4,/net/rijn3,/net/rijn2'
SINGULARITY=' '.join(['singularity execute -B', SING_BIND, SING_IMAGE])
RUN = [SINGULARITY, 'python']

#MAKE RESULT FOLDER
os.system('mkdir '+LOCATION)
os.system('mkdir '+LOCATION_BACKUP)
print('Made '+LOCATION)

#MOVE FILES
print('Moving files to '+LOCATION)
os.system('scp -r lofarvwf-jdejong@spider.surfsara.nl:/project/lofarvwf/Share/jdejong/output/L626678/selfcal/all_solutions.h5 '+LOCATION)
os.system('~/scripts/lofar_helpers/pipeline_scripts/strw/move_original_files.sh '+FROM+' '+LOCATION)
os.system('cp -r '+FROM+'/image_full_ampphase_di_m.NS.mask01.fits'+LOCATION)
os.system('cp -r '+FROM+'/image_full_ampphase_di_m_masked.DicoModel'+LOCATION)
os.system('cp -r '+FROM+'/*_uv.pre-cal_*.pre-cal.ms.archive '+LOCATION)
print('Finished moving files')

#CUT TIME FOR MESSY END PART (ONLY FOR THIS CASE APPLICABLE)
print('Making goodtimes')
os.system('cd '+LOCATION)
for MS in glob('*_uv.pre-cal_*.pre-cal.ms.archive'):
    os.system(SINGULARITY+' DPPP msin='+MS+'msout.storagemanager=dysco msout='+MS+'.goodtimes msin.ntimes=1500 steps=[]')
    os.system('mv '+MS+' '+LOCATION_BACKUP)
    print('Made '+MS+'.goodtimes')

#MAKE LIST WITH MEASUREMENT SETS
os.system('ls -1d *.goodtimes > big-mslist.txt')

with open('ddf.txt') as f:
    lines = [l.replace('\n','') for l in f.readlines()]

#MAKE DDF COMMAND READY TO RUN
RUN += lines
DDF_COMMAND = ' '.join(RUN)

#RUN DDF COMMAND
print('Running '+DDF_COMMAND)
os.system(DDF_COMMAND)
print('Finished making new image')