from argparse import ArgumentParser
from glob import glob
import time
import os
import casacore.tables as ct

parser = ArgumentParser()
parser.add_argument('--box', type=str, help='Measurement set input')
args = parser.parse_args()

TO = "/project/lofarvwf/Share/jdejong/output/A399"

BOX = 'box_' + args.box

ms_archives = sorted([b.split('/')[-1] for b in glob(TO + '/extract/' + BOX+'/*' + BOX + '.dysco.sub.shift.avg.weights.ms.archive*')])

while len(ms_archives) != 6:
    time.sleep(5)

#starting times fom measurement sets that have to be cutted for time
CUTTIMES = [5019387068.011121, 5017577408.011121, 5020506668.011121]

#starting times for measurement sets that have to be cutted for freq
CUTFREQS = [5021107868.011121]

# os.system("mkdir " + TO + "/selfcal/" + BOX)
# for MS in ms_archives:
#     if ct.table(TO + "/extract/" + BOX + '/'+ MS).getcol('TIME')[0] in CUTTIMES:
#         print('Cutting time for '+MS)
#         os.system("python /home/lofarvwf-jdejong/scripts/lofar_helpers/supporting_scripts/flag_time.py -tf 0 1500 -msin " + TO + "/extract/" + BOX + '/' + MS + " -msout " + TO + "/selfcal/" + BOX + '/' + MS + '.goodtimes')
#     elif ct.table(TO + "/extract/" + BOX + '/' + MS).getcol('TIME')[0] in CUTFREQS:
#         print('Cutting freq for ' + MS)
#         os.system("python /home/lofarvwf-jdejong/scripts/lofar_helpers/supporting_scripts/flag_freq.py -ff='[15..19]' -msin " + TO + "/extract/" + BOX + '/' + MS+" -msout " + TO + "/selfcal/" + BOX + '/' + MS + '.goodfreq')
#     else:
#         os.system("cp -r " + TO + "/extract/" + BOX + '/' + MS + " " + TO + "/selfcal/" + BOX)

MS = [ms.split('/')[-1] for ms in glob(TO + '/selfcal/' + BOX + '/*' + BOX + '.dysco.sub.shift.avg.weights.ms.archive*')]
print(MS)
while len(MS) != 6:
    MS = [ms.split('/')[-1] for ms in glob(TO + '/selfcal/' + BOX + '/*' + BOX + '.dysco.sub.shift.avg.weights.ms.archive*')]

os.system("cd " + TO + "/selfcal/" + BOX + " && python /home/lofarvwf-jdejong/scripts/runwscleanLBautoR.py -b " + TO + "/boxes/" + BOX + ".reg --auto --imager=DDFACET --helperscriptspath=/home/lofarvwf-jdejong/scripts --autofrequencyaverage-calspeedup='True' ms " + ' '.join(MS))