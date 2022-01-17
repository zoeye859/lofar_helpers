__author__ = "Jurjen de Jong (jurjendejong@strw.leidenuniv.nl)"

import os
import sys
import tables
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--N', type=str, help='archive number', required=True)
parser.add_argument('--nmiter', type=str, default=None, help='max major iterations')
parser.add_argument('--h5', type=str, default=None, help='max major iterations')
parser.add_argument('--ms', type=str, default=None, help='max major iterations')

args = parser.parse_args()

N = args.N
if not args.nmiter:
    nmiter = '8'
else:
    nmiter = args.nmiter

MS = args.ms
H5 = args.h5
FACET = 'tess.reg'

TO='/net/nieuwerijn/data2/jurjendejong/Abell399-401_' + N + '_60'
FROM='/net/tussenrijn/data2/jurjendejong/A399_extracted_avg'


f = open(TO+'/'+FACET)
tess = f.read()
f.close()
H = tables.open_file(TO+'/'+H5)
if len(H.root.sol000.phase000.dir[:])!=len(tess.split('polygon'))-1:
    sys.exit('ERROR: H5 and tess.reg do not match')

#----------------------------------------------------------------------------------------------------------------------

#MAKE WSCLEAN COMMAND
# with open('/'.join(__file__.split('/')[0:-1])+'/WSCLEAN_scripts/wsclean.txt') as f:
#     lines = [l.replace('\n', '') for l in f.readlines()]
#     lines += ['-facet-regions '+TO+'/tess.reg']
#     lines += ['-apply-facet-solutions '+TO+'/'+H5+' amplitude000,phase000']
#     lines += ['-name image_test_L626678']
#     lines += ['-size 1500 1500']
#     lines += ['-scale 6arcsec']
#     lines += ['-nmiter '+nmiter]
#     lines += ['-taper-gaussian 60 arcsec']
#     lines += [TO+'/'+MS]

lines = ['wsclean -size 1500 1500 -use-wgridder -no-update-model-required -reorder -weight briggs -0.5 -weighting-rank-filter 3 ' \
        '-clean-border 1 -parallel-reordering 6 -padding 1.2 -auto-mask 2.5 -auto-threshold 0.5 -pol i -name image_test_A399_60 ' \
        '-scale 6arcsec -niter 50000 -mgain 0.8 -fit-beam -multiscale -channels-out 6 -join-channels -multiscale-max-scales 10 -nmiter ' + nmiter + \
        ' -log-time -multiscale-scale-bias 0.7 -facet-regions '+TO+'/'+FACET+ \
        ' -minuv-l 80.0' \
        '-parallel-gridding 6 -fit-spectral-pol 3 -taper-gaussian 60arcsec ' \
        '-apply-facet-solutions '+TO+'/'+H5+' amplitude000,phase000 '+ TO + \
        '/'+MS]

os.system('aoflagger '+TO+'/'+MS+' && wait')

cmd = ' '.join(['cd', TO, '&&'] + lines)
#RUN DDF COMMAND
print('Running WSCLEAN COMMAND')
print(cmd)
os.system(cmd + ' > '+TO+'/log.txt')
print('Finished making new image')