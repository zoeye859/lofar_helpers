"""
Example:
    python ~/scripts/lofar_helpers/make_new_image.py
        -from /disks/paradata/shimwell/LoTSS-DR2/archive_other/L626678
        -to /net/nieuwerijn/data2/jurjendejong/L626678/result
        -h5 complete_merged.h5
"""

__author__ = "Jurjen de Jong (jurjendejong@strw.leidenuniv.nl)"

import os
from glob import glob
from os import path
import casacore.tables as ct

TO='/net/nieuwerijn/data2/jurjendejong/L626678'
FROM='/disks/paradata/shimwell/LoTSS-DR2/archive_other/A399_DEEP'
IMAGER='DDF'

#CREATE DESTINATION DIRECTORY IF NOT EXISTS
if not path.exists(TO):
    os.system('mkdir {LOCATION}'.format(LOCATION=TO))
    print('Created {LOCATION}'.format(LOCATION=TO))

#CLEAN CACHE
os.system('CleanSHM.py')

#MOVE FILES
print('Moving files to '+TO)
command = 'cp -r '+FROM+'/image_full_ampphase_di_m.NS.mask01.fits '+TO+ ' && '+\
        'cp -r '+FROM+'/image_full_ampphase_di_m.NS.DicoModel '+TO+' && wait'
        # 'cp -r '+FROM+'/*_uv.pre-cal_*.pre-cal.ms.archive '+TO+' && wait'

# os.system(command)
print('Finished moving files')


#----------------------------------------------------------------------------------------------------------------------

#FLAG TIME AND FREQUENCY

# starting times fom measurement sets that have to be cutted for time
CUTTIMES = [5019387068.011121, 5019387064.005561, 5017577408.011121, 5017577404.005561, 5020506668.011121, 5020506664.005561]

#starting times for measurement sets that have to be cutted for freq
CUTFREQS = [5021107868.011121, 5021107864.005561]

# for MS in glob(FROM+'/L626678*.ms.archive'):
#     t = ct.table(MS)
#     time = t.getcol('TIME')[0]
#     t.close()
#     if time in CUTTIMES:
#         print('Cutting time for '+MS)
#         os.system("python /home/jurjendejong/scripts/lofar_helpers/supporting_scripts/flag_time.py -tf 0 3000 -msin " + MS + " -msout " + TO + '/' + MS.split('/')[-1] + '.goodtimes')
#     elif time in CUTFREQS:
#         print('Cutting freq for ' + MS)
#         if '127' not in MS:
#             os.system("cp -r " + MS + " " + TO)
#     else:
#         print('Copying for ' + MS)
#         os.system("cp -r " + MS + " " + TO)

#----------------------------------------------------------------------------------------------------------------------

#MAKE LIST WITH MEASUREMENT SETS
# os.system('ls -1d /net/nieuwerijn/data2/jurjendejong/L626678/*.pre-cal.ms.archive.goodtimes > /net/nieuwerijn/data2/jurjendejong/L626678/big-mslist.txt'.format(LOCATION=TO))

#----------------------------------------------------------------------------------------------------------------------

if IMAGER=='DDF':

    #MAKE DDF COMMAND
    with open('/'.join(__file__.split('/')[0:-1])+'/DDF_scripts/ddf.txt') as f:
        lines = [l.replace('\n','') for l in f.readlines()]
        lines+=['--Data-MS=/net/nieuwerijn/data2/jurjendejong/L626678/big-mslist.txt']
        lines+=['--Predict-InitDicoModel=/net/nieuwerijn/data2/jurjendejong/L626678/image_full_ampphase_di_m.NS.DicoModel']
        lines+=['--DDESolutions-DDSols=/net/nieuwerijn/data2/jurjendejong/L626678/all_directions*.h5:sol000/amplitude000+phase000']
        lines+=['--Mask-External=/net/nieuwerijn/data2/jurjendejong/L626678/image_full_ampphase_di_m.NS.mask01.fits']

    #RUN DDF COMMAND
    print('Running DDF COMMAND')
    os.system(' '.join(['cd', TO, '&&'] + lines))
elif IMAGER=='WSCLEAN':
    pass

print('Finished making new image')
