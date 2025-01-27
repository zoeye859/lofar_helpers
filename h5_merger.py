"""
USE THIS SCRIPT PREFERABLY WITH PYTHON 3, AS ALL TESTS ARE DONE WITH PYTHON 3.

After one has created solution files from self calling on the extracted boxes,
one can use this script to merge solution files
Do this by importing the function merge_h5 from this script:
-------------------------
EXAMPLE:

from h5_merger import merge_h5
merge_h5(h5_out='test.h5',
        h5_tables='*.h5',
        ms_files='*.ms',
        convert_tec=True)
"""

# TODO: test convert_tec==False  ---> now they are deleted if convert_tec==false
# TODO: test circ2lin and vice versa

__author__ = "Jurjen de Jong (jurjendejong@strw.leidenuniv.nl)"

import os
from casacore import tables as ct
from glob import glob
from losoto.h5parm import h5parm
from losoto.lib_operations import reorderAxes
from scipy.interpolate import interp1d
import sys
import re
import tables
from collections import OrderedDict
import warnings
from numpy import zeros, ones, round, unique, array_equal, append, where, isfinite, expand_dims, pi, array, all, complex128, exp, angle, sort, power, sum, argmin, float64

warnings.filterwarnings('ignore')

__all__ = ['merge_h5', 'output_check', 'move_source_in_sourcetable']

def remove_numbers(inp):
    return "".join(re.findall("[a-zA-z]+", inp))

def overwrite_table(T, solset, table, values, title=None):
    """
    Create table for given solset, opened with the package tables.
    Best to use for antenna or source table.

    :param T: Table opeend with tables
    :param solset: solution set of the table (f.ex. sol000)
    :param table: table name (f.ex. antenna or source)
    :param values: new values
    :param title: title of new table
    """

    try:
        T.root
    except:
        sys.exit('ERROR: Create table failed. Given table not opened with the package "tables" (https://pypi.org/project/tables/).')

    if 'sol' not in solset:
        print('WARNING: Usual input have sol*** as solset name.')

    ss = T.root._f_get_child(solset)
    ss._f_get_child(table)._f_remove()
    if table == 'source':
        values = array(values, dtype=[('name', 'S128'), ('dir', '<f4', (2,))])
        title = 'Source names and directions'
    elif table == 'antenna':
        title = 'Antenna names and positions'
        values = array(values, dtype=[('name', 'S16'), ('position', '<f4', (3,))])
    else:
        try: # check if numpy structure
            values.shape
        except:
            values = array(values)
    T.create_table(ss, table, values, title=title)

def copy_antennas_from_MS_to_h5(MS, h5, solset):
    """
    Copy the antennas from an MS to an h5 file

    :param MS: measurement set
    :param h5: h5 file
    """
    t = ct.table(MS + "::ANTENNA", ack=False)
    new_antlist = t.getcol('NAME')
    new_antpos = t.getcol('POSITION')
    antennas_ms = list(zip(new_antlist, new_antpos))
    t.close()

    T = tables.open_file(h5, 'r+')
    ss = T.root._f_get_child(solset)
    ants_h5 = [a.decode('utf8') if type(a)!=str else a for a in T.root._f_get_child(solset)._f_get_child(list(ss._v_groups.keys())[0]).ant[:]]
    if ants_h5 == new_antlist:
        overwrite_table(T, solset, 'antenna', antennas_ms, title=None)
    else:
        new_antennas = list(zip(ants_h5, [[0., 0., 0.]]*len(ants_h5)))
        for n, ant in enumerate(antennas_ms):
            if type(ant[0])!=str:
                a = ant[0].decode('utf8')
            else:
                a = ant[0]
            if a in list(ants_h5):
                new_antennas[ants_h5.index(a)] = ant
        ss.antenna._f_remove()
        T.create_table(ss, 'antenna', array(new_antennas, dtype=[('name', 'S16'), ('position', '<f4', (3,))]), title='Antenna names and positions')
    T.close()


class MergeH5:
    """Merge multiple h5 tables"""

    def __init__(self, h5_out, h5_tables=None, ms_files=None, h5_time_freq=None, convert_tec=True, merge_all_in_one=False, solset='sol000', filtered_dir=None):
        """
        :param h5_out: name of merged output h5 table
        :param files: h5 tables to merge, can be both list and string
        :param ms_files: read time and frequency from measurement set
        :param h5_time_freq: read time and frequency from h5
        :param convert_tec: convert TEC to phase or not
        :param merge_all_in_one: merge all in one direction
        :param solset: solset number
        """

        self.h5name_out = h5_out
        self.solset = solset # for now this is standard sol0000

        if type(ms_files) == list:
            self.ms = ms_files
        elif type(ms_files) == str:
            self.ms = glob(ms_files)
        else:
            self.ms = []

        if type(h5_tables) == list:
            self.h5_tables = h5_tables
        elif type(h5_tables) == str:
            self.h5_tables = glob(h5_tables)
        else:
            print('No h5 table given. We will use all h5 tables in current folder.')
            self.h5_tables = glob('*.h5')
        if h5_time_freq:
            if len(self.ms)>0:
                print('Ignore MS for time and freq axis, as --h5_time_freq is given.')
            print('Take the time and freq from the following h5 solution file:\n'+h5_time_freq)
            T = tables.open_file(h5_time_freq)
            self.ax_time = T.root.sol000.phase000.time[:]
            self.ax_freq = T.root.sol000.phase000.freq[:]
            T.close()

        elif len(self.ms)>0: # if there are multiple ms files
            print('Take the time and freq from the following measurement sets:\n'+'\n'.join(self.ms))
            self.ax_time = array([])
            self.ax_freq = array([])
            for m in self.ms:
                t = ct.taql('SELECT CHAN_FREQ, CHAN_WIDTH FROM ' + m + '::SPECTRAL_WINDOW')
                self.ax_freq = append(self.ax_freq, t.getcol('CHAN_FREQ')[0])
                t.close()

                t = ct.table(m)
                self.ax_time = append(self.ax_time, t.getcol('TIME'))
                t.close()
            self.ax_time = array(sorted(unique(self.ax_time)))
            self.ax_freq = array(sorted(unique(self.ax_freq)))

        else:  # if we dont have ms files, we use the time and frequency axis of the longest h5 table
            print('No MS or h5 file given for time/freq axis.\nWill make a frequency and time axis by combining all input h5 tables.')
            self.ax_time = array([])
            self.ax_freq = array([])
            for h5_name in self.h5_tables:
                h5 = h5parm(h5_name)
                ss = h5.getSolset(self.solset)
                for soltab in ss.getSoltabNames():
                    st = ss.getSoltab(soltab)
                    try:
                        if len(st.getAxisValues('time')) > len(self.ax_time):
                            self.ax_time = st.getAxisValues('time')
                    except:
                        print('No time axis in {solset}/{soltab}'.format(solset=solset, soltab=soltab))
                    try:
                        if len(st.getAxisValues('freq')) > len(self.ax_freq):
                            self.ax_freq = st.getAxisValues('freq')
                    except:
                        print('No freq axis in {solset}/{soltab}'.format(solset=solset, soltab=soltab))
                h5.close()

        if len(self.ax_freq) == 0:
            sys.exit('ERROR: Cannot read frequency axis from input MS set or input H5.')
        if len(self.ax_time) == 0:
            sys.exit('ERROR: Cannot read time axis from input MS or input H5.')
        if not self.have_same_antennas:
            sys.exit('ERROR: Antenna tables are not the same')

        self.convert_tec = convert_tec  # convert tec or not
        self.merge_all_in_one = merge_all_in_one
        if filtered_dir:
            self.filtered_dir = filtered_dir
        else:
            self.filtered_dir = None

        self.solaxnames = ['pol', 'dir', 'ant', 'freq', 'time']  # standard solax order to do our manipulations

        self.directions = OrderedDict()  # directions in a dictionary

    @property
    def have_same_antennas(self):
        """
        Compare antenna tables with each other.
        These should be the same.
        """

        for h5_name1 in self.h5_tables:
            H_ref = tables.open_file(h5_name1, 'r+')
            for solset1 in H_ref.root._v_groups.keys():
                ss1 = H_ref.root._f_get_child(solset1)
                if 'antenna' not in list(ss1._v_children.keys()):
                    H_ref.create_table(ss1, 'antenna',
                                       array([], dtype=[('name', 'S16'), ('position', '<f4', (3,))]),
                                       title='Antenna names and positions')
                if len(ss1._f_get_child('antenna')[:]) == 0:
                    print('Antenna table ('+'/'.join([solset1, 'antenna'])+') in '+h5_name1+' is empty')
                    if len(self.ms)>0:
                        print('WARNING: '+'/'.join([solset1, 'antenna'])+' in '+h5_name1+' is empty.'
                                '\nWARNING: Trying to fill antenna table with measurement set')
                        H_ref.close()
                        copy_antennas_from_MS_to_h5(self.ms[0], h5_name1, solset1)
                    else:
                        sys.exit('ERROR: '+'/'.join([solset1, 'antenna'])+' in '+h5_name1+' is empty.'
                                '\nAdd --ms to add a measurement set to fill up the antenna table')
            H_ref.close()

        for h5_name1 in self.h5_tables:
            H_ref = tables.open_file(h5_name1)
            for solset1 in H_ref.root._v_groups.keys():
                ss1 = H_ref.root._f_get_child(solset1)
                antennas_ref = ss1.antenna[:]
                for soltab1 in ss1._v_groups.keys():
                    if (len(antennas_ref['name']) != len(ss1._f_get_child(soltab1).ant[:])) or \
                            (not all(antennas_ref['name'] == ss1._f_get_child(soltab1).ant[:])):
                        print('\nMismatch in antenna tables in '+h5_name1)
                        print('Antennas from '+'/'.join([solset1, 'antenna']))
                        print(antennas_ref['name'])
                        print('Antennas from '+'/'.join([solset1, soltab1, 'ant']))
                        print(ss1._f_get_child(soltab1).ant[:])
                        H_ref.close()
                        return False
                    for soltab2 in ss1._v_groups.keys():
                        if (len(ss1._f_get_child(soltab1).ant[:]) !=
                            len(ss1._f_get_child(soltab2).ant[:])) or \
                                (not all(ss1._f_get_child(soltab1).ant[:] ==
                                         ss1._f_get_child(soltab2).ant[:])):
                            print('\nMismatch in antenna tables in ' + h5_name1)
                            print('Antennas from ' + '/'.join([solset1, soltab1, 'ant']))
                            print(ss1._f_get_child(soltab1).ant[:])
                            print('Antennas from ' + '/'.join([solset1, soltab2, 'ant']))
                            print(ss1._f_get_child(soltab2).ant[:])
                            H_ref.close()
                            return False
                for h5_name2 in self.h5_tables:
                    H = tables.open_file(h5_name2)
                    for solset2 in H.root._v_groups.keys():
                        ss2 = H.root._f_get_child(solset2)
                        antennas = ss2.antenna[:]
                        if (len(antennas_ref['name']) != len(antennas['name'])) \
                                or (not all(antennas_ref['name'] == antennas['name'])):
                            print('\nMismatch between antenna tables from '+h5_name1+' and '+h5_name2)
                            print('Antennas from '+h5_name1+':')
                            print(antennas_ref['name'])
                            print('Antennas from '+h5_name2+':')
                            print(antennas['name'])
                            H.close()
                            H_ref.close()
                            return False
                    H.close()
            H_ref.close()

        return True

    def _get_and_check_values(self, st, solset, soltab):
        """
        Get the values from the h5 table to merge.
        Also do some checks on the time and frequency axis.

        :param st: solution table
        :param solset: solset name
        :param soltab: soltab name

        :return: values, time axis, frequency axis
        """

        if 'pol' in st.getAxesNames():
            print("polarization is in {solset}/{soltab}".format(solset=solset, soltab=soltab))
        else:
            print("polarization is not in {solset}/{soltab}".format(solset=solset, soltab=soltab))

        time_axes = st.getAxisValues('time')

        if 'freq' in st.getAxesNames():
            freq_axes = st.getAxisValues('freq')
        else:
            freq_axes = self.ax_freq

        print('Value shape before --> {values}'.format(values=st.getValues()[0].shape))

        if self.ax_time[0] > time_axes[-1] or time_axes[0] > self.ax_time[-1]:
            print("WARNING: Time axes of h5 and MS are not overlapping.")
        if self.ax_freq[0] > freq_axes[-1] or freq_axes[0] > self.ax_freq[-1]:
            print("WARNING: Frequency axes of h5 and MS are not overlapping.")
        if float(soltab[-3:]) > 0:
            print("WARNING: {soltab} does not end on 000".format(soltab=soltab))
        for av in self.axes_final:
            if av in st.getAxesNames() and st.getAxisLen(av) == 0:
                print("No {av} in {solset}/{soltab}".format(av=av, solset=solset, soltab=soltab))

        if len(st.getAxesNames()) != len(st.getValues()[0].shape):
            sys.exit('ERROR: Axes ({axlen}) and Value dimensions ({vallen}) are not equal'.format(axlen=len(st.getAxesNames()), vallen=len(st.getValues()[0].shape)))

        axes_current = [an for an in self.solaxnames if an in st.getAxesNames()]
        if 'dir' in st.getAxesNames():
            values = reorderAxes(st.getValues()[0], st.getAxesNames(), axes_current)
        else:
            print('No direction axis, we will add this.')
            origin_values = st.getValues()[0]
            values = reorderAxes(origin_values.reshape(origin_values.shape+(1,)), st.getAxesNames()+['dir'], axes_current)

        return values, time_axes, freq_axes

    def _sort_soltabs(self, soltabs):
        """
        Sort solution tables.
        This is important to run the steps and add directions according to our algorithm.
        Dont touch if you dont have to.

        :param soltabs: solutions tables
        """

        soltabs = set(soltabs)
        if self.convert_tec:
            tp_phasetec = [li for li in soltabs if 'tec' in li or 'phase' in li]
            tp_amplitude = [li for li in soltabs if 'amplitude' in li]
            tp_rotation = [li for li in soltabs if 'rotation' in li]
            return [sorted(tp_amplitude, key=lambda x: float(x[-3:])),
                    sorted(tp_rotation, key=lambda x: float(x[-3:])),
                    sorted(sorted(tp_phasetec), key=lambda x: float(x[-3:]))]
        else:
            tp_phase = [li for li in soltabs if 'phase' in li]
            tp_tec = [li for li in soltabs if 'tec' in li]
            tp_amplitude = [li for li in soltabs if 'amplitude' in li]
            tp_rotation = [li for li in soltabs if 'rotation' in li]
            return [sorted(tp_phase, key=lambda x: float(x[-3:])),
                    # sorted(tp_tec, key=lambda x: float(x[-3:])),
                    sorted(tp_amplitude, key=lambda x: float(x[-3:])),
                    sorted(tp_rotation, key=lambda x: float(x[-3:]))]

    @staticmethod
    def has_integer(input):
        try:
            for s in str(input):
                if s.isdigit():
                    return True
            return False
        except:
            return False

    def get_allkeys(self):
        """
        Get all solution sets, solutions tables, and ax names in lists.
        """

        self.all_soltabs, self.all_solsets, self.all_axes, self.ant = [], [], [], []

        for h5_name in self.h5_tables:
            h5 = h5parm(h5_name)
            for solset in h5.getSolsetNames():
                self.all_solsets += [solset]
                ss = h5.getSolset(solset)
                for n, soltab in enumerate(ss.getSoltabNames()):
                    self.all_soltabs += [soltab]
                    st = ss.getSoltab(soltab)
                    self.all_axes += ['/'.join([solset, soltab, an]) for an in st.getAxesNames()]
                    if n == 0:
                        self.ant = st.getAxisValues('ant')  # check if same for all h5
                    elif list(self.ant) != list(st.getAxisValues('ant')):
                        sys.exit('ERROR: antennas not the same')
            h5.close()
        self.all_soltabs = self._sort_soltabs(self.all_soltabs)
        self.all_solsets = set(self.all_solsets)
        self.all_axes = set(self.all_axes)
        return self

    def _get_template_values(self, soltab, st):
        """
        Get default values, based on model h5 table

        :param soltab: solution table name
        :param st: solution table itself
        """

        num_dir = max(len(self.directions), 1)

        if 'pol' in st.getAxesNames():
            self.polarizations = st.getAxisValues('pol')
        else:
            self.polarizations = []

        if 'amplitude' in soltab and 'pol' in st.getAxesNames():
            self.gains = ones(
                (len(self.polarizations), num_dir, len(self.ant), len(self.ax_freq), len(self.ax_time)))
        else:
            self.gains = ones((1, len(self.ant), len(self.ax_freq), len(self.ax_time)))

        if 'phase' in soltab and 'pol' in st.getAxesNames():
            self.phases = zeros(
                (max(len(self.polarizations), 1), num_dir, len(self.ant), len(self.ax_freq), len(self.ax_time)))

        elif 'rotation' in soltab:
            self.phases = zeros((num_dir, len(self.ant), len(self.ax_freq), len(self.ax_time)))

        elif 'tec' in soltab:
            self.phases = zeros((2, num_dir, len(self.ant), len(self.ax_freq), len(self.ax_time)))
        else:
            self.phases = zeros((num_dir, len(self.ant), len(self.ax_freq), len(self.ax_time)))

        self.n = 0  # direction number reset

        return self

    @staticmethod
    def tecphase_conver(tec, freqs):
        """
        convert tec to phase

        :param tec: TEC
        :param freqs: frequencies

        :return: tec phase converted values
        """
        return -8.4479745e9 * tec / freqs

    @staticmethod
    def _interp_along_axis(x, interp_from, interp_to, axis):
        """
        Interpolate along axis

        :param x: frequency or time axis. Must be equal to the length of interp_from.
        :param interp_from: interpolate from this axis.
        :param interp_to: interpolate to this axis
        :param axis: interpolation axis

        :return: the interpolated result
        """

        # axis with length 1
        if len(interp_from) == 1:
            new_vals = x
            for _ in range(len(interp_to)-1):
                new_vals = append(new_vals, x, axis=axis)
        else:
            interp_vals = interp1d(interp_from, x, axis=axis, kind='nearest', fill_value='extrapolate')
            new_vals = interp_vals(interp_to)
        return new_vals

    def get_model_h5(self, solset, soltab):
        """
        Get model (clean) h5 table

        :param solset: solution set name (sol000)
        :param soltab: solution table name
        """

        if '000' in soltab:

            for h5_name_to_merge in self.h5_tables:  # make template

                h5_to_merge = h5parm(h5_name_to_merge)

                if solset not in h5_to_merge.getSolsetNames():
                    h5_to_merge.close()
                    sys.exit('ERROR ' + solset + ' does not exist in '+h5_name_to_merge)
                else:
                    ss = h5_to_merge.getSolset(solset)
                if soltab not in ss.getSoltabNames():
                    h5_to_merge.close()
                    continue  # use other h5 table with soltab
                else:
                    st = ss.getSoltab(soltab)

                if not self.convert_tec or (self.convert_tec and 'tec' not in soltab):
                    self._get_template_values(soltab, st)
                    self.axes_final = [an for an in self.solaxnames if an in st.getAxesNames()]
                elif 'tec' in soltab and self.convert_tec:
                    for st_group in self.all_soltabs:
                        if soltab in st_group and ('phase000' not in st_group and 'phase{n}'.format(n=soltab[-3:])):
                            self._get_template_values(soltab, st)
                            self.axes_final = [an for an in self.solaxnames if an in st.getAxesNames()]

                # add dir if missing
                if 'dir' not in self.axes_final:
                    if 'pol' in self.axes_final:
                        self.axes_final.insert(1, 'dir')
                    else:
                        self.axes_final.inser(0, 'dir')

                h5_to_merge.close()
                break

    @staticmethod
    def get_number_of_directions(st):
        """
        Get number of directions in solution table

        :param st: solution table
        """

        if 'dir' in st.getAxesNames():
            dir_index = st.getAxesNames().index('dir')
            return st.getValues()[0].shape[dir_index]
        else:
            return 1

    def add_direction(self, source):
        self.directions.update(source)
        self.directions = OrderedDict(sorted(self.directions.items()))


    @staticmethod
    def _expand_poldim(values, dim_pol, type, haspol):
        """
        Add extra polarization dimensions

        :param values: values which need to get a polarization
        :param dim_pol: number of dimensions
        :param type: phase or amplitude
        :param hasnopol: has polarization

        :return: input values with extra polarization axis
        """

        if dim_pol == 4:
            print("Make fulljones type with 4 polarizations")

        if values.ndim < 5 and not haspol:
            if type == 'amplitude':
                values_new = ones((dim_pol,) + values.shape)
            elif type == 'phase':
                values_new = zeros((dim_pol,) + values.shape)
            else:
                sys.exit('ERROR: Only type in [amplitude, phase] allowed')
            for i in range(dim_pol):
                values_new[i, ...] = values
        elif values.shape[0] in [1, 2] and dim_pol in [2, 4] and haspol:
            if type == 'amplitude':
                values_new = ones((dim_pol,) + values.shape[1:])
            elif type == 'phase':
                values_new = zeros((dim_pol,) + values.shape[1:])
            else:
                sys.exit('ERROR: Only type in [amplitude, phase] allowed')
            values_new[0, ...] = values[0, ...]
            if values.shape[0] == 2:
                values_new[-1, ...] = values[1, ...]
            elif values.shape[0] == 1:
                values_new[-1, ...] = values[0, ...]
        else:
            print('WARNING: No pol ax dimension changed.')
            return values

        return values_new

    def merge_files(self, solset, soltab):
        """
        Merge the h5 files

        :param solset: solution set name
        :param soltab: solution table name
        """

        for h5_name in self.h5_tables:

            print(h5_name)

            h5 = h5parm(h5_name)
            if solset not in h5.getSolsetNames():
                h5.close()
                continue

            ss = h5.getSolset(solset)

            if soltab not in ss.getSoltabNames():
                h5.close()
                continue

            st = ss.getSoltab(soltab)

            print('Solution table from {table}'.format(table=h5_name.split('/')[-1]))
            num_dirs = self.get_number_of_directions(st)  # number of directions
            print('This table has {dircount} direction(s)'.format(dircount=num_dirs))

            # get values, time, and freq axis from h5 file
            table_values, time_axes, freq_axes = self._get_and_check_values(st, solset, soltab)

            for dir_idx in range(num_dirs): # loop over all directions in h5

                if self.filtered_dir != None:
                    if len(self.filtered_dir) > 0 and dir_idx not in self.filtered_dir:
                        continue

                if 'pol' not in st.getAxesNames():
                    values = table_values[dir_idx, ...]
                    # adding direction dimension
                    values = expand_dims(values, axis=0)
                else:
                    values = table_values[:, dir_idx, ...]
                    # adding direction dimension
                    values = expand_dims(values, axis=1)

                # current axes for reordering of axes
                self.axes_current = [an for an in self.solaxnames if an in st.getAxesNames()]

                if 'dir' not in self.axes_current:
                    if 'pol' in self.axes_current:
                        self.axes_current.insert(1, 'dir')
                    else:
                        self.axes_current.insert(0, 'dir')

                idxnan = where((~isfinite(values)))
                values[idxnan] = 0.0

                # get source coordinates
                dirs = ss.getSou()
                if 'dir' in list(dirs.keys())[0].lower() and list(dirs.keys())[0][-1].isnumeric():
                    dirs = OrderedDict(sorted(dirs.items()))
                elif len(dirs)>1 and (sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor<6)):
                    print('WARNING: Order of source directions from h5 table might not be ordered. This is an old Python issue.'
                          '\nSuggest to switch to Python 3.6 or higher')
                source_coords = dirs[list(dirs.keys())[dir_idx]]

                if self.merge_all_in_one and self.n == 1:
                    idx = 0
                    print('Merging direction {:f},{:f} with previous direction'.format(*source_coords))
                    if abs(self.directions['Dir00'][0])>0 and abs(self.directions['Dir00'][1])>0:
                        self.add_direction({'Dir00': source_coords}) # 0.0 coordinate bug
                        print('Adding new direction {:f},{:f}'.format(*source_coords))
                elif any([array_equal(source_coords, list(sv)) for sv in self.directions.values()]):
                    # Direction already exists, add to the existing solutions.
                    print('Direction {:f},{:f} already exists. Adding to this direction.'.format(*source_coords))
                    # We are matching on 5 decimals rounding
                    idx = list([[round(l[0],5), round(l[1],5)] for l in self.directions.values()]).\
                        index([round(source_coords[0], 5), round(source_coords[1], 5)])
                else:  # new direction
                    if abs(source_coords[0]) > 0 and abs(source_coords[1]) > 0:
                        print('Adding new direction {:f},{:f}'.format(*source_coords))
                    idx = self.n
                    self.add_direction({'Dir{:02d}'.format(self.n): source_coords})
                    if not self.merge_all_in_one:
                        self.n += 1
                    if self.n > 1:  # for self.n==1 we dont have to do anything
                        if st.getType() in ['tec', 'phase', 'rotation']:
                            shape = list(self.phases.shape)
                            dir_index = self.phases.ndim - 4
                            if dir_index < 0:
                                sys.exit('ERROR: Missing axes')
                            if self.n > shape[dir_index]:
                                shape[dir_index] = 1
                                self.phases = append(self.phases, zeros(shape),
                                                        axis=dir_index)  # add clean phase to merge with
                        elif st.getType() == 'amplitude':
                            shape = list(self.gains.shape)
                            dir_index = self.gains.ndim - 4
                            if dir_index < 0:
                                sys.exit('ERROR: Missing axes')
                            if self.n > shape[dir_index]:
                                shape[dir_index] = 1
                                self.gains = append(self.gains, ones(shape),
                                                       axis=dir_index)  # add clean gain to merge with

                # Now we will add the solution table axis --> tec, phase, rotation, or amplitude

                if st.getType() == 'tec':

                    # add frequencies
                    if 'freq' not in st.getAxesNames():
                        ax = self.axes_final.index('freq') - len(self.axes_final)
                        values = expand_dims(values, axis=ax)
                        self.axes_current.insert(-1, 'freq')
                        valuestmp = values
                        for _ in range(len(self.ax_freq)-1):
                            values = append(values, valuestmp, axis=-2)

                    # convert tec to phase
                    if self.convert_tec:

                        shape = [1 for _ in range(values.ndim)]
                        shape[-2] = -1
                        values = self.tecphase_conver(values, self.ax_freq.reshape(shape))

                        # check and correct pol axis
                        if 'pol' in self.axes_current and 'pol' in self.axes_final:
                            if st.getAxisLen('pol') > self.phases.shape[0]:
                                self.phases = self._expand_poldim(self.phases, st.getAxisLen('pol'), 'phase', True)
                            elif self.phases.shape[0] > st.getAxisLen('pol'):
                                values = self._expand_poldim(values, self.phases.shape[0], 'phase', True)
                        elif 'pol' not in self.axes_current and 'pol' in self.axes_final:
                            values = self._expand_poldim(values, self.phases.shape[0], 'phase', False)
                            self.axes_current.insert(0, 'pol')
                        elif 'pol' in self.axes_current and 'pol' not in self.axes_final:
                            self.phases = self._expand_poldim(self.phases, st.getAxisLen('pol'), 'phase', False)
                            self.axes_final.insert(0, 'pol')
                        elif 'pol' not in self.axes_current and 'pol' not in self.axes_final:
                            self.phases = self._expand_poldim(self.phases, 2, 'phase', False)
                            values = self._expand_poldim(values, 2, 'phase', False)
                            self.axes_current.insert(0, 'pol')
                            self.axes_final.insert(0, 'pol')

                        # interpolate time axis
                        newvals = self._interp_along_axis(values, time_axes, self.ax_time,
                                                          self.axes_current.index('time'))

                        # add values
                        self.phases[:, idx, ...] += newvals[:, 0, ...]

                    # TODO: this part needs an update
                    else:
                        if 'dir' in self.axes_current:  # this line is trivial and could maybe be removed
                            values = values[0, :, 0, :]

                        newvals = self._interp_along_axis(values, time_axes, self.ax_time, -1)
                        newvals = newvals.reshape((1, newvals.shape[0], 1, newvals.shape[1]))
                        # Now add the tecs to the total phase correction for this direction.
                        if 'dir' in self.axes_current:  # this line is trivial and could be removed
                            self.phases[idx, ...] += newvals[0, ...]
                        else:
                            self.phases[idx, :, :] += newvals

                elif st.getType() == 'phase' or st.getType() == 'rotation':

                    # check and correct pol axis
                    if 'pol' in self.axes_current and 'pol' in self.axes_final:
                        if st.getAxisLen('pol') > self.phases.shape[0]:
                            self.phases = self._expand_poldim(self.phases, st.getAxisLen('pol'), 'phase', True)
                        elif self.phases.shape[0] > st.getAxisLen('pol'):
                            values = self._expand_poldim(values, self.phases.shape[0], 'phase', True)
                    elif 'pol' not in self.axes_current and 'pol' in self.axes_final:
                        values = self._expand_poldim(values, self.phases.shape[0], 'phase', False)
                        self.axes_current.insert(0, 'pol')
                    elif 'pol' in self.axes_current and 'pol' not in self.axes_final:
                        self.phases = self._expand_poldim(self.phases, st.getAxisLen('pol'), 'phase', False)
                        self.axes_final.insert(0, 'pol')
                    elif 'pol' not in self.axes_current and 'pol' not in self.axes_final:
                        self.phases = self._expand_poldim(self.phases, 2, 'phase', False)
                        values = self._expand_poldim(values, 2, 'phase', False)
                        self.axes_current.insert(0, 'pol')
                        self.axes_final.insert(0, 'pol')

                    # interpolate time axis
                    newvals = self._interp_along_axis(values, time_axes, self.ax_time,
                                                self.axes_current.index('time'))

                    # interpolate freq axis
                    newvals = self._interp_along_axis(newvals, freq_axes, self.ax_freq,
                                                self.axes_current.index('freq'))

                    # add values
                    self.phases[:, idx, ...] += newvals[:, 0, ...]


                elif st.getType() == 'amplitude':

                    # check and correct pol axis
                    if 'pol' in self.axes_current and 'pol' in self.axes_final:
                        if st.getAxisLen('pol') > self.gains.shape[0]:
                            self.gains = self._expand_poldim(self.gains, st.getAxisLen('pol'), 'amplitude', True)
                        elif self.gains.shape[0] > st.getAxisLen('pol'):
                            values = self._expand_poldim(values, self.gains.shape[0], 'amplitude', True)
                    elif 'pol' not in self.axes_current and 'pol' in self.axes_final:
                        values = self._expand_poldim(values, self.gains.shape[0], 'amplitude', False)
                        self.axes_current.insert(0, 'pol')
                    elif 'pol' in self.axes_current and 'pol' not in self.axes_final:
                        self.gains = self._expand_poldim(self.gains, st.getAxisLen('pol'), 'amplitude', False)
                        self.axes_final.insert(0, 'pol')
                    elif 'pol' not in self.axes_current and 'pol' not in self.axes_final:
                        self.gains = self._expand_poldim(self.gains, 2, 'amplitude', False)
                        values = self._expand_poldim(values, 2, 'amplitude', False)
                        self.axes_current.insert(0, 'pol')
                        self.axes_final.insert(0, 'pol')

                    # interpolate time axis
                    newvals = self._interp_along_axis(values, time_axes, self.ax_time,
                                                      self.axes_current.index('time'))

                    # interpolate freq axis
                    newvals = self._interp_along_axis(newvals, freq_axes, self.ax_freq,
                                                      self.axes_current.index('freq'))

                    # add values
                    self.gains[:, idx, ...] *= newvals[:, 0, ...]


            h5.close()

        return self

    def _DPPP_style(self, soltab):
        """
        Reorder the axes in DPPP style because that is needed in most LOFAR software

        :param soltab: solution table
        """

        if 'pol' in self.axes_final and len(self.axes_final) == 5:
            DPPP_axes = ['time', 'freq', 'ant', 'dir', 'pol']
        elif 'pol' not in self.axes_final and len(self.axes_final) == 4:
            DPPP_axes = ['time', 'ant', 'dir', 'freq']
            if self.phases.ndim == 5:
                self.phases = self.phases[0]
        else:
            DPPP_axes = []

        if 'phase' in soltab or 'tec' in soltab or 'rotation' in soltab:
            self.phases = reorderAxes(self.phases, self.axes_final, DPPP_axes)
        elif 'amplitude' in soltab:
            self.gains = reorderAxes(self.gains, self.axes_final, DPPP_axes)

        return DPPP_axes

    def reorder_directions(self):
        """
        This method will be called when the user is using Python 2, as there was a bug in the direction that we can resolve
        with this extra step.
        """

        H = tables.open_file(self.h5name_out, 'r+')
        for solset in H.root._v_groups.keys():
            ss = H.root._f_get_child(solset)
            #Not needed if only 1 source
            if len(ss.source[:]) == 1:
                H.close()
                return self
            #Problem when source table is empty
            elif len(ss.source[:]) == 0:
                H.close()
                sys.exit('ERROR: No sources in output table '+'/'.join([solset, 'source']))
            #No reordering needed
            elif all(ss.source[:]['name'] == ss._f_get_child(list(ss._v_groups.keys())[0]).dir[:]):
                H.close()
                return self
            #Reordering needed
            else:
                sources = array(sort(ss.source[:]), dtype=[('name', 'S128'), ('dir', '<f4', (2,))])
                overwrite_table(H, solset, 'source', sources)
                for soltab in ss._v_groups.keys():
                    st = ss._f_get_child(soltab)
                    st.dir._f_remove()
                    H.create_array(st, 'dir', array(sources['name'], dtype='|S5'))
        H.close()
        return self

    def reduce_memory_source(self):
        """
        We need to store the data in 136 bytes per directions.
        Python 3 saves it automatically in more than that number.
        """

        T = tables.open_file(self.h5name_out, 'r+')
        for solset in T.root._v_groups.keys():
            ss = T.root._f_get_child(solset)
            if ss.source[:][0].nbytes > 140:
                overwrite_table(T, solset, 'source', ss.source[:])
        T.close()
        return self

    @staticmethod
    def keep_new_sources(current_sources, new_sources):
        """
        Remove sources from new_sources that are already in current_sources

        :param current_sources: current sources that we need to compare with new_sources
        :param new_sources: new sources to be add

        :return: New unique sources
        """

        current_sources_dir = [source[0].decode('UTF-8') for source in current_sources]
        current_sources_coor = [source[1] for source in current_sources]
        new_sources = [source for source in new_sources if source[0] not in current_sources_dir]
        del_index = []
        for coor in current_sources_coor:
            for n, source in enumerate(new_sources):
                if round(coor[0], 4) == round(new_sources[1][0], 4) and round(coor[1], 4) == round(new_sources[1][1], 4):
                    del_index.append(n)

        return [source for i, source in enumerate(new_sources) if i not in del_index]

    def create_new_dataset(self, solset, soltab):
        """
        Create a new dataset in the h5 table

        :param solset: solution set name
        :param soltab: solution table name
        """

        if len(self.directions.keys()) == 0:  # return if no directions
            return self

        self.h5_out = h5parm(self.h5name_out, readonly=False)
        if solset in self.h5_out.getSolsetNames():
            solsetout = self.h5_out.getSolset(solset)
        else:
            solsetout = self.h5_out.makeSolset(solset)

        new_sources = self.keep_new_sources(solsetout.obj.source[:], list(self.directions.items()))

        if len(new_sources) > 0:
            solsetout.obj.source.append(new_sources)

        axes_vals = {'dir': list(self.directions.keys()),
                     'ant': self.ant,
                     'freq': self.ax_freq,
                     'time': self.ax_time}

        DPPP_axes = self._DPPP_style(soltab)  # reorder the axis to DPPP style

        if 'pol' in self.axes_final:
            if len(self.polarizations) > 1:
                axes_vals.update({'pol': self.polarizations})
            else:
                axes_vals.update({'pol': ['XX', 'YY']})  # need to be updated for rotation where len(pol)==4
            self.axes_final = DPPP_axes
        elif len(self.axes_final) == 4 and len(DPPP_axes) > 0:
            self.axes_final = DPPP_axes

        # right order vals
        axes_vals = [v[1] for v in sorted(axes_vals.items(), key=lambda pair: self.axes_final.index(pair[0]))]

        # make new solution table
        if 'phase' in soltab:
            weights = ones(self.phases.shape)
            print('Value shape after --> {values}'.format(values=weights.shape))
            solsetout.makeSoltab('phase', axesNames=self.axes_final, axesVals=axes_vals, vals=self.phases,
                                 weights=weights)
        if 'amplitude' in soltab:
            weights = ones(self.gains.shape)
            print('Value shape after --> {values}'.format(values=weights.shape))
            solsetout.makeSoltab('amplitude', axesNames=self.axes_final, axesVals=axes_vals, vals=self.gains,
                                 weights=weights)
        if 'tec' in soltab:
            print('ADD TEC')
            if self.axes_final.index('freq') == 1:
                self.phases = self.phases[:, 0, :, :]
            elif self.axes_final.index('freq') == 3:
                self.phases = self.phases[:, :, :, 0]
            else:
                self.phases = self.phases[:, :, 0, :]
            weights = ones(self.phases.shape)
            print('Value shape after --> {values}'.format(values=weights.shape))
            solsetout.makeSoltab('tec', axesNames=['dir', 'ant', 'time'],
                                 axesVals=[self.ax_time, self.ant, list(self.directions.keys())],
                                 vals=self.phases, weights=weights)

        print('DONE: {solset}/{soltab}'.format(solset=solset, soltab=soltab))

        self.h5_out.close()

        return self

    def add_empty_directions(self, add_directions=None):
        """
        Add default directions (phase all zeros, amplitude all ones)

        :param add_directions: list with directions
        """

        if not add_directions:
            return self

        h5 = h5parm(self.h5name_out, readonly=True)
        filetemp = self.h5name_out.replace('.h5','_temp.h5')
        h5_temp = h5parm(filetemp, readonly=False)
        solset = h5.getSolset(self.solset)
        solsettemp = h5_temp.makeSolset(self.solset)
        if type(add_directions[0]) == list:
            sources = list([source[1] for source in solset.obj.source[:]]) + add_directions
        else:
            sources = list([source[1] for source in solset.obj.source[:]]) + [add_directions]
        sources = [(bytes('Dir' + str(n).zfill(2), 'utf-8'), list(ns)) for n, ns in enumerate(sources)]
        if len(sources) > 0:
            solsettemp.obj.source.append(sources)

        for st in h5.getSolset(self.solset).getSoltabNames():
            solutiontable = h5.getSolset(self.solset).getSoltab(st)
            axes = solutiontable.getValues()[1]
            values = solutiontable.getValues()[0]
            axes['dir'] = [ns[0] for ns in sources]
            dir_index = solutiontable.getAxesNames().index('dir')
            new_shape = list(values.shape)
            last_idx = new_shape[dir_index]
            new_idx = last_idx+len(add_directions)-1
            new_shape[dir_index] = new_idx

            if 'phase' in st:
                values_new = zeros(tuple(new_shape))
            elif 'amplitude' in st:
                values_new = ones(tuple(new_shape))
            else:
                values_new = zeros(tuple(new_shape))

            if dir_index == 0:
                values_new[0:last_idx, ...] = values
            elif dir_index == 1:
                values_new[:, 0:last_idx, ...] = values
            elif dir_index == 2:
                values_new[:, :, 0:last_idx, ...] = values
            elif dir_index == 3:
                values_new[:, :, :, 0:last_idx, ...] = values
            elif dir_index == 4:
                values_new[:, :, :, :, 0:last_idx, ...] = values

            weights = ones(values_new.shape)
            solsettemp.makeSoltab(remove_numbers(st), axesNames=list(axes.keys()), axesVals=list(axes.values()), vals=values_new,
                             weights=weights)

            print('Default directions added for '+self.solset+'/'+st)
            print('Shape change: '+str(values.shape)+' ---> '+str(values_new.shape))

        h5.close()
        h5_temp.close()

        os.system('rm '+self.h5name_out +' && mv '+filetemp+' '+self.h5name_out)

        return self

    def remove_pol(self, single=False):
        """
        Reduce table to one single polarization

        :param single: if single==True we leave a single pole such that values have shape=(..., 1), if False we remove pol-axis entirely
        """

        T = tables.open_file(self.h5name_out, 'r+')

        for solset in T.root._v_groups.keys():
            ss = T.root._f_get_child(solset)
            for soltab in ss._v_groups.keys():
                st = ss._f_get_child(soltab)
                st.pol._f_remove()
                if single:
                    T.create_array(st, 'pol', array([b'I'], dtype='|S2'))
                for axes in ['val', 'weight']:
                    if not all(st._f_get_child(axes)[:,:,:,:,0] == \
                            st._f_get_child(axes)[:,:,:,:,-1]):
                        sys.exit('WARNING: ' + '/'.join([soltab, axes]) +
                                 ' has not the same values for XX and YY polarization.'
                                 '\nERROR: No polarization reduction will be done.'
                                 '\nERROR: Do not use --no_pol or --single_pol')
                    if single:
                        print('/'.join([soltab, axes])+' has same values for XX and YY polarization.\nReducing into one Polarization I.')
                    else:
                        print('/'.join([soltab, axes])+' has same values for XX and YY polarization.\nRemoving Polarization.')
                    if single:
                        newval = st._f_get_child(axes)[:, :, :, :, 0:1]
                    else:
                        newval = st._f_get_child(axes)[:, :, :, :, 0]

                    valtype = str(st._f_get_child(axes).dtype)
                    if '16' in valtype:
                        atomtype = tables.Float16Atom()
                    elif '32' in valtype:
                        atomtype = tables.Float32Atom()
                    elif '64' in valtype:
                        atomtype = tables.Float64Atom()
                    else:
                        atomtype = tables.Float64Atom()

                    st._f_get_child(axes)._f_remove()
                    T.create_array(st, axes, newval.astype(valtype), atom=atomtype)

                    if single:
                        st._f_get_child(axes).attrs['AXES'] = b'time,freq,ant,dir,pol'
                    else:
                        st._f_get_child(axes).attrs['AXES'] = b'time,freq,ant,dir'
                    print('Value shape after --> '+str(st._f_get_child(axes)[:].shape))
        T.close()

        return self

    def add_h5_antennas(self):
        """
        Add antennas to output table from H5 list
        """

        print('Add antenna table from '+self.h5_tables[0])
        T = tables.open_file(self.h5_tables[0])
        antennas = T.root.sol000.antenna[:]
        T.close()
        H = tables.open_file(self.h5name_out, 'r+')
        for solset in H.root._v_groups.keys():
            overwrite_table(H, solset, 'antenna', antennas)
        H.close()

        return self

    def add_ms_antennas(self, keepLB=None):
        """
        Add antennas from MS

        :param keepLB: keep long baseline stations from h5
        """

        print('Add antenna table from '+self.ms[0])
        if len(self.ms) == 0:
            sys.exit("ERROR: Measurement set needed to add antennas. Use --ms.")

        t = ct.table(self.ms[0] + "::ANTENNA", ack=False)
        try:
            ms_antlist = [n.decode('utf8') for n in t.getcol('NAME')]
        except AttributeError:
            ms_antlist = t.getcol('NAME')
        ms_antpos = t.getcol('POSITION')
        ms_antennas = array([list(zip(*(ms_antlist, ms_antpos)))], dtype=[('name', 'S16'), ('position', '<f4', (3,))])
        t.close()

        H = tables.open_file(self.h5name_out, 'r+')

        for solset in H.root._v_groups.keys():
            ss = H.root._f_get_child(solset)

            F = tables.open_file(self.h5_tables[0])
            h5_antennas = F.root._f_get_child(solset).antenna[:]
            F.close()

            for soltab in ss._v_groups.keys():
                st = ss._f_get_child(soltab)
                attrsaxes = st.val.attrs['AXES']
                antenna_index = attrsaxes.decode('utf8').split(',').index('ant')
                h5_antlist = [v.decode('utf8') for v in list(st.ant[:])]

                if keepLB:  # keep international stations if these are not in MS
                    new_antlist = [station for station in ms_antlist if 'CS' in station] + \
                                  [station for station in h5_antlist if 'ST' not in station]
                    all_antennas = [a for a in unique(append(ms_antennas, h5_antennas), axis=0) if a[0] != 'ST001']
                    antennas_new = [all_antennas[[a[0].decode('utf8') for a in all_antennas].index(a)] for a in new_antlist] # sorting
                    # if len(new_antlist)!=len(antennas_new):
                    #     print('ERROR: core stations could not be added due to bug or incorrect antenna tables from h5 and MS files')
                else:
                    new_antlist = ms_antlist
                    antennas_new = ms_antennas

                st.ant._f_remove()
                overwrite_table(H, solset, 'antenna', antennas_new)
                H.create_array(st, 'ant', array(list(new_antlist), dtype='|S16'))

                try:
                    superstation_index = h5_antlist.index('ST001')
                except ValueError:
                    sys.exit('ERROR: No super station in antennas (denoted by ST001)')

                for axes in ['val', 'weight']:
                    assert axes in list(st._v_children.keys()), axes+' not in .root.'+solset+'.'+soltab+' (not in axes)'
                    h5_values = st._f_get_child(axes)[:]
                    shape = list(h5_values.shape)
                    shape[antenna_index] = len(new_antlist)
                    ms_values = zeros(shape)

                    for idx, a in enumerate(new_antlist):
                        if a in h5_antlist:
                            idx_h5 = h5_antlist.index(a)
                            if antenna_index == 0:
                                ms_values[idx, ...] += h5_values[idx_h5, ...]
                            elif antenna_index == 1:
                                ms_values[:, idx, ...] += h5_values[:, idx_h5, ...]
                            elif antenna_index == 2:
                                ms_values[:, :, idx, ...] += h5_values[:, :, idx_h5, ...]
                            elif antenna_index == 3:
                                ms_values[:, :, :, idx, ...] += h5_values[:, :, :, idx_h5, ...]
                            elif antenna_index == 4:
                                ms_values[:, :, :, :, idx, ...] += h5_values[:, :, :, :, idx_h5, ...]
                        elif 'CS' in a: # core stations
                            if antenna_index == 0:
                                ms_values[idx, ...] += h5_values[superstation_index, ...]
                            elif antenna_index == 1:
                                ms_values[:, idx, ...] += h5_values[:, superstation_index, ...]
                            elif antenna_index == 2:
                                ms_values[:, :, idx, ...] += h5_values[:, :, superstation_index, ...]
                            elif antenna_index == 3:
                                ms_values[:, :, :, idx, ...] += h5_values[:, :, :, superstation_index, ...]
                            elif antenna_index == 4:
                                ms_values[:, :, :, :, idx, ...] += h5_values[:, :, :, :, superstation_index, ...]

                    valtype = str(st._f_get_child(axes).dtype)
                    if '16' in valtype:
                        atomtype = tables.Float16Atom()
                    elif '32' in valtype:
                        atomtype = tables.Float32Atom()
                    elif '64' in valtype:
                        atomtype = tables.Float64Atom()
                    else:
                        atomtype = tables.Float64Atom()

                    st._f_get_child(axes)._f_remove()
                    H.create_array(st, axes, ms_values.astype(valtype), atom=atomtype)
                    st._f_get_child(axes).attrs['AXES'] = attrsaxes
                print('Value shape after --> '+str(st.val.shape))

        H.close()

        return self

    def create_missing_template(self):
        """
        Make template for phase000 and/or amplitude000 if missing
        """

        H = tables.open_file(self.h5name_out, 'r+')
        soltabs = list(H.root.sol000._v_groups.keys())
        H.close()
        if 'amplitude000' not in soltabs:
            self.gains = ones((2, len(self.directions.keys()), len(self.ant), len(self.ax_freq), len(self.ax_time)))
            self.axes_final = ['time', 'freq', 'ant', 'dir', 'pol']
            self.polarizations = ['XX', 'YY']
            self.gains = reorderAxes(self.gains, self.solaxnames, self.axes_final)
            self.create_new_dataset('sol000', 'amplitude')
        if 'phase000' not in soltabs:
            self.phases = zeros((2, len(self.directions.keys()), len(self.ant), len(self.ax_freq), len(self.ax_time)))
            self.axes_final = ['time', 'freq', 'ant', 'dir', 'pol']
            self.polarizations = ['XX', 'YY']
            self.phases = reorderAxes(self.phases, self.solaxnames, self.axes_final)
            self.create_new_dataset('sol000', 'phase')

        return self

    def check_stations(self):
        for input_h5 in self.h5_tables:
            T = tables.open_file(input_h5)
            for solset in T.root._v_groups.keys():
                ss = T.root._f_get_child(solset)
                for soltab in ss._v_groups.keys():
                    st = ss._f_get_child(soltab)
                    weight = st.weight
                    ant_index = str(weight.attrs['AXES']).split(',').index('ant')
                    for a in range(weight.shape[ant_index]):
                        if ant_index==0:
                            if sum(weight[a, ...])==0.:
                                H = tables.open_file(self.h5name_out, 'r+')
                                H.root._f_get_child(solset)._f_get_child(soltab).weight[a, ...] = 0.
                                H.close()
                        elif ant_index==1:
                            if sum(weight[:, a, ...])==0.:
                                H = tables.open_file(self.h5name_out, 'r+')
                                H.root._f_get_child(solset)._f_get_child(soltab).weight[:, a, ...] = 0.
                                H.close()
                        elif ant_index==2:
                            if sum(weight[:, :, a, ...])==0.:
                                H = tables.open_file(self.h5name_out, 'r+')
                                H.root._f_get_child(solset)._f_get_child(soltab).weight[:, :, a, ...] = 0.
                                H.close()
                        elif ant_index==3:
                            if sum(weight[:, :, :, a, ...])==0.:
                                H = tables.open_file(self.h5name_out, 'r+')
                                H.root._f_get_child(solset)._f_get_child(soltab).weight[:, :, :, a, ...] = 0.
                                H.close()
                        elif ant_index==4:
                            if sum(weight[:, :, :, :, a, ...])==0.:
                                H = tables.open_file(self.h5name_out, 'r+')
                                H.root._f_get_child(solset)._f_get_child(soltab).weight[:, :, :, :, a, ...] = 0.
                                H.close()
        return self



def _create_h5_name(h5_name):
    if '.h5' != h5_name[-3:]:
        h5_name += '.h5'
    return h5_name

def _change_solset(h5, solset_in, solset_out, delete=True, overwrite=True):
    """
    This function is to change the solset numbers.

    1) Copy solset_in to solset_out (overwriting if overwrite==True)
    2) Delete solset_in if delete==True
    """

    H = tables.open_file(h5, 'r+')
    H.root._f_get_child(solset_in)._f_copy(H.root, newname=solset_out, overwrite=overwrite, recursive=True)
    print('Succesfully copied ' + solset_in + ' to ' + solset_out)
    if delete:
        H.root._f_get_child(solset_in)._f_remove(recursive=True)
        print('Removed ' + solset_in)
    H.close()

def output_check(h5):

    print('\nChecking output...')

    H = tables.open_file(h5)

    #check number of solset
    assert len(list(H.root._v_groups.keys())) == 1, \
        'More than 1 solset in '+str(list(H.root._v_groups.keys()))+'. Only 1 is allowed for h5_merger.py.'

    for solset in H.root._v_groups.keys():

        #check sol00.. name
        assert 'sol' in solset, solset+' is a wrong solset name, should be sol***'
        ss = H.root._f_get_child(solset)

        #check antennas
        antennas = ss.antenna
        assert antennas.attrs.FIELD_0_NAME == 'name', 'No name in '+'/'.join([solset,'antenna'])
        assert antennas.attrs.FIELD_1_NAME == 'position', 'No coordinate in '+'/'.join([solset,'antenna'])

        #check sources
        sources = ss.source
        assert sources.attrs.FIELD_0_NAME == 'name', 'No name in '+'/'.join([solset,'source'])
        assert sources.attrs.FIELD_1_NAME == 'dir', 'No coordinate in '+'/'.join([solset,'source'])

        for soltab in ss._v_groups.keys():
            st = ss._f_get_child(soltab)
            assert st.val.shape == st.weight.shape, \
                'weight '+str(st.weight.shape)+' and values '+str(st.val.shape)+' do not have same shape'

            #check if pol and/or dir are not missing
            for pd in ['pol', 'dir']:
                assert not (st.val.ndim == 5 and pd not in list(st._v_children.keys())), \
                    '/'.join([solset, soltab, pd])+' is missing'

            #check if freq, time, and ant arrays are not missing
            for fta in ['freq', 'time', 'ant']:
                assert fta in list(st._v_children.keys()), \
                    '/'.join([solset, soltab, fta])+' is missing'

            #check if val and weight have AXES
            for vw in ['val', 'weight']:
                assert 'AXES' in st._f_get_child(vw).attrs._f_list("user"), \
                    'AXES missing in '+'/'.join([solset, soltab, vw])

            #check if dimensions of values match with length of arrays
            for ax_index, ax in enumerate(st.val.attrs['AXES'].decode('utf8').split(',')):
                assert st.val.shape[ax_index] == len(st._f_get_child(ax)[:]), \
                    ax+' length is not matching with dimension from val in ' + '/'.join([solset, soltab, ax])

                #check if ant and antennas have equal sizes
                if ax == 'ant':
                    assert len(antennas[:]) == len(st._f_get_child(ax)[:]), \
                        '/'.join([solset, 'antenna'])+' and '+'/'.join([solset, soltab, ax])+ ' do not have same length'

                # check if dir and sources have equal sizes
                if ax == 'dir':
                    assert len(sources[:]) == len(st._f_get_child(ax)[:]), \
                        '/'.join([solset, 'source'])+' and '+'/'.join([solset, soltab, ax])+ ' do not have same length'

            #check if phase and amplitude have same shapes
            for soltab1 in ss._v_groups.keys():
                if ('phase' in soltab or 'amplitude' in soltab) and ('phase' in soltab1 or 'amplitude' in soltab1):
                    st1 = ss._f_get_child(soltab1)
                    assert st.val.shape == st1.val.shape, \
                        '/'.join([solset, soltab, 'val']) + ' shape: '+str(st.weight.shape)+\
                        '/'.join([solset, soltab1, 'val']) + ' shape: '+str(st1.weight.shape)

    H.close()

    print('...Output has all necessary information and correct dimensions')

    return True

class PolChange:
    """
    This Python class helps to convert polarization from linear to circular or vice versa.
    """

    def __init__(self, h5_in, h5_out):
        """
        :param h5_in: h5 input name
        :param h5_out: h5 output name
        """
        self.h5in_name = h5_in
        self.h5out_name = h5_out
        self.h5_in = h5parm(h5_in, readonly=True)
        self.h5_out = h5parm(h5_out, readonly=False)
        self.axes_names = ['time', 'freq', 'ant', 'dir', 'pol']

    @staticmethod
    def lin2circ(G):
        """
        Convert linear polarization to circular polarization

        RR = XX - iXY + iYX + YY
        RL = XX + iXY + iYX - YY
        LR = XX - iXY - iYX - YY
        LL = XX + iXY - iYX + YY

        :param G: Linear polarized Gain

        :return: Circular polarized Gain
        """

        RR = (G[..., 0] + G[..., -1]).astype(complex128)
        RL = (G[..., 0] - G[..., -1]).astype(complex128)
        LR = (G[..., 0] - G[..., -1]).astype(complex128)
        LL = (G[..., 0] + G[..., -1]).astype(complex128)

        if G.shape[-1] == 4:
            RR += 1j * (G[..., 2] - G[..., 1]).astype(complex128)
            RL += 1j * (G[..., 2] + G[..., 1]).astype(complex128)
            LR -= 1j * (G[..., 2] + G[..., 1]).astype(complex128)
            LL += 1j * (G[..., 1] - G[..., 2]).astype(complex128)

        RR /= 2
        RL /= 2
        LR /= 2
        LL /= 2

        G_new = zeros(G.shape[0:-1] + (4,)).astype(complex128)
        G_new[..., 0] += RR
        G_new[..., 1] += RL
        G_new[..., 2] += LR
        G_new[..., 3] += LL
        return G_new

    @staticmethod
    def circ2lin(G):
        """
        Convert circular polarization to linear polarization

        XX = RR + RL + LR + LL
        XY = iRR - iRL + iLR - iLL
        YX = -iRR - iRL + iLR + iLL
        YY = RR - RL - LR + LL

        :param G: Circular polarized Gain

        :return: linear polarized Gain
        """

        XX = (G[..., 0] + G[..., -1]).astype(complex128)
        XY = 1j * (G[..., 0] - G[..., -1]).astype(complex128)
        YX = 1j * (G[..., -1] - G[..., 0]).astype(complex128)
        YY = (G[..., 0] + G[..., -1]).astype(complex128)


        if G.shape[-1] == 4:
            XX += (G[..., 2] + G[..., 1]).astype(complex128)
            XY += 1j * (G[..., 2] - G[..., 1]).astype(complex128)
            YX += 1j * (G[..., 2] - G[..., 1]).astype(complex128)
            YY -= (G[..., 1] + G[..., 2]).astype(complex128)

        XX /= 2
        XY /= 2
        YX /= 2
        YY /= 2

        G_new = zeros(G.shape[0:-1] + (4,)).astype(complex128)
        G_new[..., 0] += XX
        G_new[..., 1] += XY
        G_new[..., 2] += YX
        G_new[..., 3] += YY

        return G_new

    @staticmethod
    def add_polarization(values, dim_pol):
        """
        Add extra polarization if there is no polarization

        :param values: values which need to get a polarization
        :param dim_pol: number of dimensions

        :return: input values with extra polarization axis
        """

        values_new = ones(values.shape+(dim_pol,))
        for i in range(dim_pol):
            values_new[..., i] = values

        return values_new


    def create_template(self, soltab):
        """
        Make template of the Gain matrix with only ones
        :param soltab: solution table (phase, amplitude)
        """

        self.G, self.axes_vals = array([]), OrderedDict()
        for ss in self.h5_in.getSolsetNames():
            for st in self.h5_in.getSolset(ss).getSoltabNames():
                solutiontable = self.h5_in.getSolset(ss).getSoltab(st)
                if soltab in st:
                    try:
                        if 'pol' in solutiontable.getAxesNames():
                            values = reorderAxes(solutiontable.getValues()[0], solutiontable.getAxesNames(), self.axes_names)
                            self.G = ones(values.shape).astype(complex128)
                        else:
                            values = reorderAxes(solutiontable.getValues()[0], solutiontable.getAxesNames(), self.axes_names[0:-1])
                            self.G = ones(values.shape+(2,)).astype(complex128)
                    except:
                        sys.exit('ERROR: Received '+str(solutiontable.getAxesNames())+', but expect at least [time, freq, ant, dir] or [time, freq, ant, dir, pol]')

                    self.axes_vals = {'time': solutiontable.getAxisValues('time'),
                                 'freq': solutiontable.getAxisValues('freq'),
                                 'ant': solutiontable.getAxisValues('ant'),
                                 'dir': solutiontable.getAxisValues('dir'),
                                 'pol': ['XX', 'XY', 'YX', 'YY']}
                    break

        print('Value shape {soltab} before --> {shape}'.format(soltab=soltab, shape=self.G.shape))

        return self

    def add_tec(self, solutiontable):
        """
        :param solutiontable: the solution table for the TEC
        """

        tec_axes_names = [ax for ax in self.axes_names if solutiontable.getAxesNames()]
        tec = reorderAxes(solutiontable.getValues()[0], solutiontable.getAxesNames(), tec_axes_names)
        if 'freq' in solutiontable.getAxesNames():
            axes_vals_tec = {'time': solutiontable.getAxisValues('time'),
                             'freq': solutiontable.getAxisValues('freq'),
                             'ant': solutiontable.getAxisValues('ant'),
                             'dir': solutiontable.getAxisValues('dir')}
        else:
            axes_vals_tec = {'dir': solutiontable.getAxisValues('dir'),
                             'ant': solutiontable.getAxisValues('ant'),
                             'time': solutiontable.getAxisValues('time')}
        if 'pol' in solutiontable.getAxesNames():
            if tec.shape[-1] == 2:
                axes_vals_tec.update({'pol': ['XX', 'YY']})
            elif tec.shape[-1] == 4:
                axes_vals_tec.update({'pol': ['XX', 'XY', 'YX', 'YY']})
        axes_vals_tec = [v[1] for v in
                         sorted(axes_vals_tec.items(), key=lambda pair: self.axes_names.index(pair[0]))]
        self.solsetout.makeSoltab('tec', axesNames=tec_axes_names, axesVals=axes_vals_tec, vals=tec, weights=ones(tec.shape))

        return self

    def create_new_gains(self, lin2circ, circ2lin):
        """
        :param lin2circ: boolean for linear to circular conversion
        :param circ2lin: boolean for circular to linear conversion
        """

        for ss in self.h5_in.getSolsetNames():

            self.solsetout = self.h5_out.makeSolset(ss)

            for st in self.h5_in.getSolset(ss).getSoltabNames():
                solutiontable = self.h5_in.getSolset(ss).getSoltab(st)
                print('{ss}/{st} from {h5}'.format(ss=ss, st=st, h5=self.h5in_name))
                if 'phase' in st:
                    if 'pol' in solutiontable.getAxesNames():
                        values = reorderAxes(solutiontable.getValues()[0], solutiontable.getAxesNames(), self.axes_names)
                        self.G *= exp(values * 1j)
                    else:
                        values = reorderAxes(solutiontable.getValues()[0], solutiontable.getAxesNames(), self.axes_names[0:-1])
                        self.G *= exp(self.add_polarization(values, 2) * 1j)

                elif 'amplitude' in st:
                    if 'pol' in solutiontable.getAxesNames():
                        values = reorderAxes(solutiontable.getValues()[0], solutiontable.getAxesNames(), self.axes_names)
                        self.G *= values
                    else:
                        values = reorderAxes(solutiontable.getValues()[0], solutiontable.getAxesNames(), self.axes_names[0:-1])
                        self.G *= self.add_polarization(values, 2)

                elif 'tec' in st:
                    self.add_tec(solutiontable)
                else:
                    print("Didn't include {st} in this version yet".format(st=st))
                    print("Let me (Jurjen) know if you need to include this.")

            if lin2circ:
                print('Convert linear polarization to circular polarization')
                G_new = self.lin2circ(self.G)
            elif circ2lin:
                print('Convert circular polarization to linear polarization')
                G_new = self.circ2lin(self.G)
            else:
                sys.exit('ERROR: No conversion given')
            print('Value shape after --> {shape}'.format(shape=G_new.shape))

            phase = angle(G_new)
            amplitude = abs(G_new)

            self.axes_vals = [v[1] for v in sorted(self.axes_vals.items(), key=lambda pair: self.axes_names.index(pair[0]))]

            self.solsetout.makeSoltab('phase', axesNames=self.axes_names, axesVals=self.axes_vals, vals=phase, weights=ones(phase.shape))
            print('Created new phase solutions')

            self.solsetout.makeSoltab('amplitude', axesNames=self.axes_names, axesVals=self.axes_vals, vals=amplitude, weights=ones(amplitude.shape))
            print('Created new amplitude solutions')

        self.h5_in.close()
        self.h5_out.close()

        return self

    def create_extra_tables(self):

        T = tables.open_file(self.h5in_name)
        H = tables.open_file(self.h5out_name, 'r+')

        for solset in T.root._v_groups.keys():
            ss = T.root._f_get_child(solset)
            overwrite_table(H, solset, 'antenna', ss.antenna[:])
            overwrite_table(H, solset, 'source', ss.source[:])

        T.close()
        H.close()


def _test_h5_output(h5_out, tables_to_merge):
    """

    ##########      NEEDS UPDATE!!       ##########

    With this function we test if the output has the expected output by going through source coordinates and compare in and output H5.
    This only works when the phase000 and amplitude000 haven't changed. So, when tec000 is not merged with phase000,
    otherwise only amplitude000 are compared.

    :param h5_out: the output H5
    :param tables_to_merge: list of tables that have been merged together
    """

    H5out = tables.open_file(h5_out)
    sources_out = array([s[1] for s in H5out.root.sol000.source[:]])
    source_count=0
    for h5 in tables_to_merge:
        H5in = tables.open_file(h5)
        source_count+=len(H5in.root.sol000.source[:])
        H5in.close()
    if len(sources_out) == source_count:
        if type(tables_to_merge) != list:
            sys.exit('h5_tables type is not list. Might be bug in code.')
        for h5 in tables_to_merge:
            H5in = tables.open_file(h5)
            sources = H5in.root.sol000.source[:]
            for n, source in enumerate(sources):
                m = argmin(sum(power(sources_out-source[1], 2), axis=1))
                try:
                    try:
                        H5out.root.sol000._f_get_child('tec000')
                    except:
                        # No tec000, so it hasn't been merged with phase000 and changed the values
                        if H5out.root.sol000.phase000.val[0, 0, 0, m, 0] != H5in.root.sol000.phase000.val[0, 0, 0, n, 0] or \
                            H5out.root.sol000.phase000.val[-1, 0, 0, m, 0] != H5in.root.sol000.phase000.val[-1, 0, 0, n, 0]:
                            print('ERROR: Merge bug. Source table does not correspond with index for phase000. Please check.')
                except:
                    pass
                try:
                    if H5out.root.sol000.ampltiude000.val[0, 0, 0, m, 0] != H5in.root.sol000.ampltiude000.val[0, 0, 0, n, 0] or \
                        H5out.root.sol000.ampltiude000.val[-1, 0, 0, m, 0] != H5in.root.sol000.ampltiude000.val[-1, 0, 0, n, 0]:
                        print('ERROR: Merge bug. Source table does not correspond with index for ampltiude000. Please check.')
                except:
                    pass
            H5in.close()
    else:
        print('Received at least once the same source coordinates of two directions, which have been merged together.')
    H5out.close()

def _degree_to_radian(d):
    return pi*d/180

def move_source_in_sourcetable(h5, overwrite=False, dir_idx=None, dra_degrees=0, ddec_degrees=0):
    """
    Change source table for specific direction

    :param overwrite: overwrite input file. If False -> add replace .h5 with _update.h5
    :param dir_idx: directions index
    :param ra_degrees: change right ascension degrees
    :param dec_degrees: change declination degrees
    """
    if not overwrite:
        os.system('cp '+h5+' '+h5.replace('.h5', '_upd.h5'))
        h5 = h5.replace('.h5', '_upd.h5')
    H = tables.open_file(h5, 'r+')
    sources = H.root.sol000.source[:]
    sources[dir_idx][1][0] += _degree_to_radian(dra_degrees)
    sources[dir_idx][1][1] += _degree_to_radian(ddec_degrees)
    overwrite_table(H, 'sol000', 'source', sources)
    H.close()

def merge_h5(h5_out=None, h5_tables=None, ms_files=None, h5_time_freq=None, convert_tec=True, merge_all_in_one=False,
             lin2circ=False, circ2lin=False, add_directions=None, single_pol=None, no_pol=None, use_solset='sol000',
             filtered_dir=None, add_cs=None, use_ants_from_ms=None, check_output=None, freq_av=None, time_av=None,
             check_flagged_station=True):
    """
    Main function that uses the class MergeH5 to merge h5 tables.

    :param h5_out (string): h5 table name out
    :param h5_tables (string or list): h5 tables to merge
    :param ms_files (string or list): ms files
    :param h5_time_freq (str or list): h5 file to take freq and time axis from
    :param freq_av (int): averaging of frequency axis
    :param time_av (int): averaging of time axis
    :param convert_tec (boolean): convert TEC to phase or not
    :param merge_all_in_one: merge all in one direction
    :param lin2circ: boolean for linear to circular conversion
    :param circ2lin: boolean for circular to linear conversion
    :param add_directions: add default directions by giving a list of directions (coordinates)
    :param single_pol: only one polarization
    :param use_solset: use specific solset number
    :param filtered_dir: filter a specific list of directions from h5 file. Only lists allowed.
    :param add_cs: use MS to replace super station with core station
    :param use_ants_from_ms: use only stations from Measurement set
    :param check_output: check if output has all correct output information
    :param check_flagged_station: check if input stations are flagged, if so flag same stations in output
    """

    print('\n##################################\nSTART MERGE HDF5 TABLES FOR LOFAR\n##################################\n\nMerging the following tables:\n'+'\n'.join(h5_tables)+'\n')

    h5_out = _create_h5_name(h5_out)

    if h5_out in h5_tables:
        sys.exit('ERROR: output h5 file cannot be in the list of input h5 files.\n'
                 'Change your --h5_out and --h5_tables input.')
    elif h5_out.split('/')[-1] in [f.split('/')[-1] for f in glob(h5_out)]:
        os.system('rm {}'.format(h5_out))

    #if alternative solset number is given, we will make a temp h5 file that has the alternative solset number because the code runs on sol000
    if use_solset != 'sol000':
        for h5_ind, h5 in enumerate(h5_tables):
            temph5 = h5.replace('.h5', 'temp.h5')
            print('Using different solset. Make temporary h5 file: '+temph5)
            os.system('cp '+h5+' '+temph5)
            _change_solset(temph5, use_solset, 'sol000')
            h5_tables[h5_ind] = temph5

    merge = MergeH5(h5_out=h5_out, h5_tables=h5_tables, ms_files=ms_files, convert_tec=convert_tec,
                    merge_all_in_one=merge_all_in_one, h5_time_freq=h5_time_freq, filtered_dir=filtered_dir)

    if time_av:
        merge.ax_time = merge.ax_time[::int(time_av)]

    if freq_av:
        merge.ax_freq = merge.ax_freq[::int(freq_av)]

    merge.get_allkeys()

    for st_group in merge.all_soltabs:
        if len(st_group) > 0:
            for st in st_group:
                merge.get_model_h5('sol000', st)
                merge.merge_files('sol000', st)
            if merge.convert_tec and (('phase' in st_group[0]) or ('tec' in st_group[0])):
                merge.create_new_dataset('sol000', 'phase')
            else:
                merge.create_new_dataset('sol000', st)
    tables.file._open_files.close_all()

    #If amplitude000 or phase000 are missing, we can add a template for these
    merge.create_missing_template()

    #Add antennas
    if (add_cs or use_ants_from_ms) and len(merge.ms)==0:
        sys.exit('ERROR: --add_CS needs MS, given with --ms')
    if add_cs:
        merge.add_ms_antennas(keepLB=True)
    elif use_ants_from_ms:
        merge.add_ms_antennas(keepLB=False)
    else:
        merge.add_h5_antennas()

    if add_directions:
        merge.add_empty_directions(add_directions)

    #Reorder directions for Python 2
    if sys.version_info.major == 2:
        merge.reorder_directions()

    #Check if stations are fully flagged in input and flag in output as well
    if check_flagged_station:
        merge.check_stations()

    #Check table source size
    merge.reduce_memory_source()

    #remove polarization axis if double
    if single_pol:
        print('Make a single polarization')
        merge.remove_pol(single=True)
    elif no_pol:
        print('Remove polarization')
        merge.remove_pol()

    if lin2circ and circ2lin:
        sys.exit('Both polarization conversions are given, please choose 1.')

    elif lin2circ or circ2lin:

        if lin2circ:
            h5_polchange = h5_out[0:-3]+'_circ.h5'
            print('\nPolarization will be converted from linear to circular')
        else:
            h5_polchange = h5_out[0:-3]+'_lin.h5'
            print('\nPolarization will be converted from circular to linear')

        Pol = PolChange(h5_in=h5_out, h5_out=h5_polchange)

        Pol.create_template('phase')
        if Pol.G.ndim > 1:
            Pol.create_template('amplitude')

        Pol.create_new_gains(lin2circ, circ2lin)
        Pol.create_extra_tables()

        os.system('rm '+h5_out+' && cp '+h5_polchange+' '+h5_out+' && rm '+h5_polchange)


    # brief test of output
    # if not merge_all_in_one:
    #     _test_h5_output(h5_out, h5_tables)

    if use_solset != 'sol000':
        for h5 in h5_tables:
            if 'temp.h5' in h5:
                os.system('rm '+h5)

    if check_output:
        output_check(h5_out)

    print('\nSee output file --> '+h5_out+'\n\n###################\nEND MERGE H5 TABLES \n###################\n')


if __name__ == '__main__':
    from argparse import ArgumentParser

    if sys.version_info.major == 2:
        print('WARNING: This code is optimized for Python 3. Please switch to Python 3 if possible.')

    parser = ArgumentParser()
    parser.add_argument('-out', '--h5_out', type=str, help='h5 table name for output.', required=True)
    parser.add_argument('-in', '--h5_tables', type=str, nargs='+', help='h5 tables to merge.', required=True)
    parser.add_argument('-ms', '--ms', type=str, help='ms files input.')
    parser.add_argument('--h5_time_freq', type=str, help='h5 file to use time and frequency arrays from.')
    parser.add_argument('--time_av', type=int, help='time averaging')
    parser.add_argument('--freq_av', type=int, help='frequency averaging')
    parser.add_argument('--not_convert_tec', action='store_true', help='convert tec to phase.')
    parser.add_argument('--merge_all_in_one', action='store_true', help='merge all solutions in one direction.')
    parser.add_argument('--lin2circ', action='store_true', help='transform linear polarization to circular.')
    parser.add_argument('--circ2lin', action='store_true', help='transform circular polarization to linear.')
    parser.add_argument('--add_direction', default=None, help='add direction with amplitude 1 and phase 0 [ex: --add_direction [0.73,0.12]')
    parser.add_argument('--single_pol', action='store_true', default=None, help='Return only a single polarization axis if both polarizations are the same.')
    parser.add_argument('--no_pol', action='store_true', default=None, help='Remove polarization axis if both polarizations are the same.')
    parser.add_argument('--combine_h5', action='store_true', default=None, help='Combine h5 with different time axis into 1.')
    parser.add_argument('--usesolset', type=str, default='sol000', help='Choose a solset to merge from your input h5 files.')
    parser.add_argument('--filter_directions', type=str, default=None, help='Filter a specific list of directions from h5 file. Only lists allowed.')
    parser.add_argument('--add_cs', action='store_true', default=None, help='Add core stations to antenna output')
    parser.add_argument('--use_ants_from_ms', action='store_true', default=None, help='Use only antenna stations from measurement set (use --ms)')
    parser.add_argument('--check_output', action='store_true', default=None, help='Check if the output has all the correct output information.')
    parser.add_argument('--not_flagstation', action='store_true', default=None, help='Do not flag any station if station is flagged in input h5')
    args = parser.parse_args()

    # check if solset name is accepted
    if 'sol' not in args.usesolset or sum([c.isdigit() for c in args.usesolset]) != 3:
        sys.exit(args.usesolse+' not an accepted name. Only sol000, sol001, sol002, ... are accepted names for solsets.')

    if args.filter_directions:
        if (args.filter_directions.startswith("[") and args.filter_directions.endswith("]")):
            filtered_dir = args.filter_directions.replace(' ', '').replace('[', '').replace(']', '').split(',')
            for n, v in enumerate(filtered_dir):
                if not v.isdigit():
                    sys.exit('--filter_directions can only have integers in the list.')
                else:
                    filtered_dir[n] = int(v)
        else:
            sys.exit('--filter_directions given but no list format. Please pass a list to --filter_directions.')
    else:
        filtered_dir = []

    # make sure h5 tables in right format
    if '[' in args.h5_tables:
        h5tables = args.h5_tables.replace('[', '').replace(']', '').replace(' ', '').split(',')
    elif ' ' in args.h5_tables:
        h5tables = args.h5_tables.split()
    else:
        h5tables = args.h5_tables

    if type(h5tables) == str:
        h5tables = glob(h5tables)
    elif type(h5tables) == list and len(h5tables) == 1:
        h5tables = glob(h5tables[0])
    elif type(h5tables) == list:
        h5tablestemp=[]
        for h5 in h5tables:
            h5tablestemp+=glob(h5)

    if args.add_direction:
        add_direction = args.add_direction.replace('[','').replace(']','').split(',')
        add_direction = [float(add_direction[0]), float(add_direction[1])]
        if add_direction[0]>pi*6 or add_direction[1]>pi*6:
            sys.exit('ERROR: Please give values in radian')
    else:
        add_direction = None

    converttec = not args.not_convert_tec

    merge_h5(h5_out=args.h5_out,
             h5_tables=h5tables,
             ms_files=args.ms,
             h5_time_freq=args.h5_time_freq,
             convert_tec=converttec,
             merge_all_in_one=args.merge_all_in_one,
             lin2circ=args.lin2circ,
             circ2lin=args.circ2lin,
             add_directions=add_direction,
             single_pol=args.single_pol,
             no_pol=args.no_pol,
             use_solset=args.usesolset,
             filtered_dir=filtered_dir,
             add_cs=args.add_cs,
             use_ants_from_ms=args.use_ants_from_ms,
             check_output=args.check_output,
             time_av=args.time_av,
             freq_av=args.freq_av,
             check_flagged_station=not args.not_flagstation)