# Author: Marek Rudnicki
# Time-stamp: <2009-09-08 13:02:06 marek>
#
# Description: Model of auditory periphery as described by Sumner et
# al. (2002) returning vesicles timings instead of ANF spikes.

import numpy as np
import os

import thorns as th
import dsam

from auditory_periphery import AuditoryPeriphery, par_dir


class Sumner2002_Vesicles(AuditoryPeriphery):
    def __init__(self, hsr=1, msr=1, lsr=1, freq=1000.0, animal='gp'):
        """
        hsr, msr, lsr: number of HSR/MSR/LSR fibers

        freq: int => single CF
        tuple => (min_freq, max_freq, how_many_channels)

        animal: gp, human
        """
        assert (hsr in (0,1)) and (msr in (0,1)) and (lsr in (0,1))

        self.hsr = hsr
        self.msr = msr
        self.lsr = lsr
        self.animal = animal

        # Outer/middle ear filter
        if self.animal == 'gp':
            self.outer_middle_ear = dsam.EarModule("Filt_MultiBPass")
            self.outer_middle_ear.read_pars(par_dir("filt_GP_A.par"))

            self.outer_middle_ear_B = dsam.EarModule("Filt_MultiBPass")
            self.outer_middle_ear_B.read_pars(par_dir("filt_GP_B.par"))
            dsam.connect(self.outer_middle_ear, self.outer_middle_ear_B)
        elif self.animal == 'human':
            self.outer_middle_ear = dsam.EarModule("Filt_MultiBPass")
            self.outer_middle_ear.read_pars(par_dir("filt_Human.par"))
        else:
            assert False


        # Stapes velocity [Pa -> m/s]
        self.stapes_velocity = dsam.EarModule("Util_mathOp")
        if self.animal == 'gp':
            self.stapes_velocity.read_pars(par_dir("stapes_Meddis2005.par"))
            dsam.connect(self.outer_middle_ear_B, self.stapes_velocity)
        elif self.animal == 'human':
            self.stapes_velocity.set_par("OPERATOR", "SCALE")
            self.stapes_velocity.set_par("OPERAND", 1.7e-11)
            dsam.connect(self.outer_middle_ear, self.stapes_velocity)
        else:
            assert False


        # Basilar membrane
        if self.animal == 'gp':
            self.bm = dsam.EarModule("BM_DRNL")
            self.bm.read_pars(par_dir("bm_drnl_gp.par"))
            self.set_freq(freq)
            dsam.connect(self.stapes_velocity, self.bm)
        elif self.animal == 'human':
            self.bm = dsam.EarModule("BM_DRNL")
            self.bm.read_pars(par_dir("drnl_human_Lopez-Poveda2001.par"))
            self.set_freq(freq)
            dsam.connect(self.stapes_velocity, self.bm)
        else:
            assert False


        # IHC receptor potential
        self.ihcrp = dsam.EarModule("IHCRP_Shamma3StateVelIn")
        self.ihcrp.read_pars(par_dir("ihcrp_Meddis2005_modified.par"))
        dsam.connect(self.bm, self.ihcrp)

        if self.hsr != 0:
            self.ihc_hsr = dsam.EarModule("IHC_Meddis2000")
            self.ihc_hsr.read_pars(par_dir("ihc_hsr_Meddis2002_spike.par"))
            dsam.connect(self.ihcrp, self.ihc_hsr)

        if self.msr != 0:
            self.ihc_msr = dsam.EarModule("IHC_Meddis2000")
            self.ihc_msr.read_pars(par_dir("ihc_msr_Meddis2002_spike.par"))
            dsam.connect(self.ihcrp, self.ihc_msr)

        if self.lsr != 0:
            self.ihc_lsr = dsam.EarModule("IHC_Meddis2000")
            self.ihc_lsr.read_pars(par_dir("ihc_lsr_Meddis2002_spike.par"))
            dsam.connect(self.ihcrp, self.ihc_lsr)



    def set_freq(self, freq):
        # Test for `freq' type, should be either float or tuple
        # flaot: single BM frequency
        # tuple: (min_freq, max_freq, freq_num)
        if isinstance(freq, int):
            freq = float(freq)
        assert (isinstance(freq, tuple) or
                isinstance(freq, float))

        if isinstance(freq, float):
            self.bm.set_par("CF_MODE", "single")
            self.bm.set_par("SINGLE_CF", freq)
        elif isinstance(freq, tuple):
            if self.animal == 'gp':
                self.bm.set_par("CF_MODE", "guinea_pig")
            elif self.animal == 'human':
                self.bm.set_par("CF_MODE", "human")
            else:
                assert False
            self.bm.set_par("MIN_CF", freq[0])
            self.bm.set_par("MAX_CF", freq[1])
            self.bm.set_par("CHANNELS", freq[2])


    def run(self, fs, sound, times=1, output_format='spikes'):
        """
        Run auditory periphery model.

        sound: audio signal

        fs: sampling frequency

        times: how many many trials

        output_format: format of the output 'spikes' (for spiking
        times), 'signals' (for time function)
        """
        if output_format == 'signals':
            assert times == 1

        fs = float(fs)
        input_module = dsam.EarModule(fs, sound)

        dsam.connect(input_module, self.outer_middle_ear)

        if self.animal == 'gp':
            self.outer_middle_ear.run()
            self.outer_middle_ear_B.run()
        elif self.animal == 'human':
            self.outer_middle_ear.run()
        else:
            self.outer_middle_ear.run()

        dsam.disconnect(input_module, self.outer_middle_ear)

        self.stapes_velocity.run()
        self.bm.run()
        self.ihcrp.run()

        if self.hsr > 0:
            hsr_db = self._run_ihc(self.ihc_hsr, fs, times, output_format)
        else:
            hsr_db = None

        if self.msr > 0:
            msr_db = self._run_ihc(self.ihc_msr, fs, times, output_format)
        else:
            msr_db = None

        if self.lsr > 0:
            lsr_db = self._run_ihc(self.ihc_lsr, fs, times, output_format)
        else:
            lsr_db = None

        return hsr_db, msr_db, lsr_db



    def _run_ihc(self, ihc, fs, times, output_format):
        """
        Run vesicles releace several times.
        """
        if output_format == 'spikes':
            ihc_db = []
            for run_idx in range(times):
                ihc.run()
                ihc_signal = ihc.get_signal()
                ihc_spikes = th.signal_to_spikes(fs, ihc_signal)

                for freq_idx,each_freq in enumerate(ihc_spikes):
                    ihc_db.append( (freq_idx, run_idx, each_freq) )

            ihc_output = np.array(ihc_db, dtype=[ ('freq', int),
                                                  ('trial', int),
                                                  ('spikes', np.ndarray) ])
        elif output_format == 'signals':
            ihc.run()
            ihc_output = ihc.get_signal()
        else:
            assert False


        return ihc_output
