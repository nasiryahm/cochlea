# Description: Model of auditory periphery of: Zilany, M.S.A., Bruce,
# I.C., Nelson, P.C., and Carney, L.H. (manuscript in preparation) 2009

from __future__ import division
from __future__ import print_function

__author__ = "Marek Rudnicki"

import numpy as np
import scipy.interpolate
import pandas as pd
import os
import warnings
import itertools

from cochlea.pycat import _pycat
from cochlea.zilany2009 import _run_channel


def run_zilany2009_human(
        sound,
        fs,
        anf_num,
        seed,
        cf,
        cohc=1,
        cihc=1,
        powerlaw_implnt='approx',
        middle_ear=True,
):




    assert np.max(sound) < 1000, "Signal should be given in Pa"
    assert sound.ndim == 1


    np.random.seed(seed)


    cfs = _calc_cfs(cf)



    ### Run Middle Ear filter
    if middle_ear:
        meout = _run_human_me_filter_for_zilany2009(
            signal=sound,
            fs=fs
        )
    else:
        meout = sound


    channel_args = [
        {
            'signal': meout,
            'cf': freq,
            'fs': fs,
            'cohc': cohc,
            'cihc': cihc,
            'anf_num': anf_num,
            'powerlaw_implnt': powerlaw_implnt,
            'seed': seed
        }
        for freq in cfs
    ]



    nested = map(_run_channel, channel_args)


    trains = itertools.chain(*nested)
    spike_trains = pd.DataFrame(
        list(trains)
    )

    np.fft.fftpack._fft_cache = {}

    return spike_trains





def _calc_cfs(cf):

    if np.isscalar(cf):
        cfs = [float(cf)]

    elif isinstance(cf, tuple):
        # Based on GenerateGreenwood_CFList() from DSAM
        # Liberman (1982)
        aA = 165.4
        k = 0.88
        a = 2.1

        freq_min, freq_max, freq_num = cf

        xmin = np.log10( freq_min / aA + k) / a
        xmax = np.log10( freq_max / aA + k) / a

        x_map = np.linspace(xmin, xmax, freq_num)
        cfs = aA * ( 10**( a*x_map ) - k)

    elif isinstance(cf, list) or isinstance(cf, np.ndarray):
        cfs = cf

    else:
        raise RuntimeError("CF must be a scalar, a tuple or a list.")

    return cfs









def _run_human_me_filter_for_zilany2009(signal, fs):
    assert fs > 40e3

    signal_fft = np.fft.rfft(signal)
    freqs = np.linspace(0, fs/2, len(signal_fft))

    me_filter = pd.read_csv(
        _data_dir('me_filter.csv')
    )



    # Interpolate the filter to fit signal's FFT
    h = scipy.interpolate.interp1d(
        x=me_filter.freq,
        y=me_filter.h,
        kind='cubic',
        bounds_error=False,
        fill_value=0
    )



    # Convert dB to amplitude ratio
    h_ratio = 10 ** (h(freqs) / 20)



    # Apply the filter
    signal_fft *= h_ratio


    # Go back to time domain
    filtered = np.fft.irfft(signal_fft)


    return filtered


def _data_dir(par_file):
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, 'data', par_file)





class Zilany2009_Human(object):
    name = 'Zilany2009'

    def __init__(self,
                 anf_num=(1,1,1),
                 cf=1000,
                 cohc=1.,
                 cihc=1.,
                 powerlaw_implnt='approx'):
        """ Auditory periphery model of a cat (Zilany et al. 2009)

        anf_num: (hsr_num, msr_num, lsr_num)
        cf: CF
        powerlaw_implnt: 'approx' or 'actual' implementation of the power-law
        with_ffGn: enable/disable Gausian noise

        """
        warnings.warn("Obsolited: use run_zilany2009() instead")


        self._anf_num = anf_num
        self._cf = cf
        self._powerlaw_implnt = powerlaw_implnt
        self._with_ffGn = with_ffGn
        self._cohc = cohc
        self._cihc = cihc


    def run(self, sound, fs, seed):
        """ Run the model.

        fs: sampling frequency of the signal; model is run at the same frequency
        sound: input signal

        """

        trains = run_zilany2009_human(
            sound=sound,
            fs=fs,
            anf_num=self._anf_num,
            seed=seed,
            cf=self._cf,
            cohc=self._cohc,
            cihc=self._cihc,
            powerlaw_implnt=self._powerlaw_implnt,
        )

        return trains