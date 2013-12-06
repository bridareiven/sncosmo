# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Functions to plot light curve data and models."""
from __future__ import division

import math
import numpy as np

from astropy.utils.misc import isiterable

from .models import ObsModel
from .spectral import get_bandpass, get_magsystem
from .photdata import standardize_data, normalize_data
from .utils import value_error_str

__all__ = ['plot_lc', 'plot_param_samples', 'animate_model']

_model_ls = ['-', '--', ':', '-.']

# TODO: cleanup names: data_bands, etc 
# TODO: standardize docs for `data` in this and other functions.
def plot_lc(data=None, model=None, bands=None, zp=25., zpsys='ab', pulls=True,
            offsets=None, xfigsize=None, yfigsize=None, figtext=None,
            errors=None, figtextsize=1., fname=None, **kwargs):
    """Plot light curve data or model light curves.

    Parameters
    ----------
    data : `~numpy.ndarray` or dict of list_like, optional
        Structured array or dictionary of arrays or lists.
    model : `~sncosmo.ObsModel` or list thereof
        If given, model light curve is plotted. If a string, the corresponding
        model is fetched from the registry. If a list or tuple of
        `~sncosmo.ObsModel`, multiple models are plotted.
    bands : list, optional
        List of Bandpasses, or names thereof, to plot.
    zp : float, optional
        Zeropoint to normalize the flux. Default is 25.
    zpsys : str or `~sncosmo.MagSystem`, optional
        Zeropoint system for `zp`. Default is 'ab'.
    pulls : bool, optional
        If True (and if model and data are given), plot pulls. Default is
        ``True``.
    offsets : list, optional
        Offsets in flux for given bandpasses.
    figtext : str, optional
        Text to add to top of figure. If a list of strings, each item is
        placed in a separate "column". Use newline separators for multiple
        lines.
    xfigsize, yfigsize : float, optional
        figure size in inches in x or y. Specify one or the other, not both.
        Default is xfigsize=8.
    figtextsize : float, optional
        Space to reserve at top of figure for figtext (if not None).
        Default is 1 inch.
    fname : str, optional
        Filename to pass to savefig. If `None` (default), plot is shown
        using `~matplotlib.pyplot.show()`.
    kwargs :
        Any additional keyword args are passed to `~matplotlib.pyplot.savefig`.
        Popular options include ``dpi``, ``format``, ``transparent``. See
        matplotlib docs for full list.

    Examples
    --------

    Load some example data::

        >>> data = sncosmo.load_example_data()

    Plot the data::

        >>> sncosmo.plot_lc(data)

    Plot a model along with the data::
    
        >>> model = sncosmo.ObsModel('salt2')
        >>> model.set(z=0.5, c=0.2, t0=55100., x0=1.547e-5, x1=0.5)
        >>> sncosmo.plot_lc(data, model=model, fname='output.png')

    .. image:: /pyplots/plotlc_example.png

    Plot just the model, for selected bands::

        >>> sncosmo.plot_lc(model=model,
        ...                 bands=['sdssg', 'sdssr', 'sdssi', 'sdssz'],
        ...                 fname='output.png')

    Show the plot instead of saving to a file::

        >>> sncosmo.plot_lc(data)

    Plot figures on a multipage pdf::

        >>> from matplotlib.backends.backend_pdf import PdfPages
        >>> pp = PdfPages('output.pdf')
        >>> 
        >>> # Do the following as many times as you like:
        >>> sncosmo.plot_lc(data, fname=pp, format='pdf')
        >>>
        >>> pp.close()  # don't forget to close at the end!

    """

    from matplotlib import pyplot as plt
    from matplotlib import cm
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    # Get colormap and define wavelengths corresponding to (blue, red)
    cmap = cm.get_cmap('gist_rainbow')
    cm_wave_range = (3000., 10000.)

    if data is None and model is None:
        raise ValueError('must specify at least one of: data, model')
    if data is None and bands is None:
        raise ValueError('must specify bands to plot for model(s)')

    # Get the model(s).
    if model is None:
        models = []
    elif isinstance(model, (tuple, list)):
        models = model
    else:
        models = [model]
    if not all([isinstance(m, ObsModel) for m in models]):
        raise TypeError('model(s) must be ObsModel instance(s)')

    # Standardize and normalize data.
    if data is not None:
        data = standardize_data(data)
        data = normalize_data(data, zp=zp, zpsys=zpsys)

    # Bands to plot
    if data is None:
        bands = set([get_bandpass(band) for band in bands])
    else:
        data_bands = np.array([get_bandpass(band) for band in data['band']])
        unique_data_bands = set(data_bands)
        if bands is None:
            bands = unique_data_bands
        else:
            bands = set([get_bandpass(band) for band in bands])
            bands = bands & unique_data_bands
    bands = list(bands)
    waves = [b.wave_eff for b in bands]

    # offsets for each band, if any.
    if offsets is not None:
        for key, value in offsets.iteritems():
            offsets[get_bandpass(key)] = offsets.pop(key)
        for band in bands:
            if band not in offsets:
                offsets[band] = 0.

    # Initialize errors
    if errors is None:
        errors = {}

    # Build figtext if not given explicitly
    if figtext is None:
        figtext = []
    elif isinstance(figtext, basestring):
        figtext = [figtext]
        
    if len(models) == 1:
        model = models[0]
        lines = []
        for i in range(len(model.param_names)):
            name = model.param_names[i]
            lname = model.param_names_latex[i]
            if name in errors:
                v = value_error_str(model.parameters[i], errors[name],
                                    latex=True)
            else:
                v = '{:.4f}'.format(model.parameters[i])
            lines.append('${} = {}$'.format(lname, v))

        # split lines into two columns
        n = len(model.param_names) - len(model.param_names) // 2
        figtext.append('\n'.join(lines[:n]))
        figtext.append('\n'.join(lines[n:]))

    # Calculate layout of figure (columns, rows, figure size)
    nsubplots = len(bands)
    ncol = 2
    nrow = (nsubplots - 1) // ncol + 1

    if xfigsize is None and yfigsize is None:
        figsize = (4. * ncol, 3. * nrow)
    elif yfigsize is None:
        figsize = (xfigsize, 3. / 4. * nrow / ncol * xfigsize)
    elif xfigsize is None:
        figsize = (4. / 3. * ncol / nrow * yfigsize, yfigsize)
    else:
        raise ValueError('cannot specify both xfigsize and yfigsize')

    # Adjust figure size for figtext
    if len(figtext) > 0:
        figsize = (figsize[0], figsize[1] + figtextsize)
    else:
        figtextsize = 0.

    # Create the figure
    fig = plt.figure(figsize=figsize)

    # Write figtext
    if len(figtext) > 0:
        for i in range(len(figtext)):
            if figtext[i] is None:
                continue
            xpos = 0.05 + 0.9 * (i / len(figtext))
            t = fig.text(xpos, 0.95, figtext[i],
                         va="top", ha="left", multialignment="left")

    # Loop over bands
    axnum = 0
    for wave, band in sorted(zip(waves, bands)):
        axnum += 1

        color = cmap((cm_wave_range[1] - wave) /
                     (cm_wave_range[1] - cm_wave_range[0]))

        ax = plt.subplot(nrow, ncol, axnum)
        if axnum % 2:
            plt.ylabel('flux ($ZP_{' + get_magsystem(zpsys).name.upper() +
                       '} = ' + str(zp) + '$)')

        xlabel_text = 'time'
        if len(models) > 0 and models[0].parameters[1] != 0.:
            xlabel_text += ' - {:.2f}'.format(models[0].parameters[1])

        # Plot data if there is any.
        if data is not None:
            idx = data_bands == band
            time = data['time'][idx]
            flux = data['flux'][idx]
            fluxerr = data['fluxerr'][idx]

            if len(models) == 0:
                plotted_time = time
            else:
                plotted_time = time - models[0].parameters[1]

            plt.errorbar(plotted_time, flux, fluxerr, ls='None',
                         color=color, marker='.', markersize=3.)

        # Plot model(s) if there are any.
        if len(models) > 0:
            mflux_mins = []
            mflux_maxes = []
            for i, model in enumerate(models):
                if not model.bandoverlap(band):
                    continue

                plotted_time = model.times - models[0].parameters[1]
                mflux = model.bandflux(band, zp=zp, zpsys=zpsys)

                if offsets is not None and band in offsets:
                    mflux = mflux + offsets[band]

                plt.plot(plotted_time, mflux, ls=_model_ls[i%len(_model_ls)],
                         marker='None', color=color, label=model.name)

                mflux_mins.append(mflux.min())
                mflux_maxes.append(mflux.max())

            # If we plotted any models, reset axes limits accordingly:
            if len(mflux_mins) > 0 and len(mflux_maxes) > 0:
                mflux_min = min(mflux_mins)
                mflux_max = max(mflux_maxes)
                ymin, ymax = ax.get_ylim()
                ymax = min(ymax, 2. * mflux_max)
                ymin = max(ymin, mflux_min - (ymax - mflux_max))
                ax.set_ylim(ymin, ymax)

            # Add a legend, if this is the first axes and there are two
            # or more models to distinguish between.
            if axnum == 1 and len(models) >= 2:
                leg = plt.legend(loc='upper right',
                                 fontsize='small', frameon=True)

        # Band name in corner: upper right if there is no legend, otherwise
        # upper left.
        if (axnum == 1 and len(models) > 1):
            plt.text(0.08, 0.92, band.name, color='k', ha='left', va='top',
                     transform=ax.transAxes)
        else:
            plt.text(0.92, 0.92, band.name, color='k', ha='right', va='top',
                     transform=ax.transAxes)

        # plot a horizontal line at flux=0.
        ax.axhline(y=0., ls='--', c='k')

        # steal part of the axes and plot pulls
        if (pulls and data is not None and len(models) == 1 and
            models[0].bandoverlap(band)):
            divider = make_axes_locatable(ax)
            axpulls = divider.append_axes("bottom", size=0.7, pad=0.1,
                                          sharex=ax)
            mflux = models[0].bandflux(band, time, zp=zp, zpsys=zpsys) 
            if offsets is not None and band in offsets:
                mflux = mflux + offsets[band]
            fluxpulls = (flux - mflux) / fluxerr
            plt.plot(time - models[0].parameters[1], fluxpulls, marker='.',
                     markersize=5., color=color, ls='None')
            plt.axhline(y=0., color=color)
            plt.setp(ax.get_xticklabels(), visible=False)
            if axnum % 2:
                plt.ylabel('pull')

        # label the most recent Axes x-axis
        plt.xlabel(xlabel_text)

    plt.tight_layout(rect=(0., 0., 1., 1. - figtextsize / figsize[1]))

    if fname is None:
        plt.show()
    else:
        plt.savefig(fname, **kwargs)
    plt.close()


def plot_param_samples(param_names, samples, weights=None, fname=None,
                       bins=25, panelsize=2.5, **kwargs):
    """Plot PDFs of parameter values.
    
    Parameters
    ----------
    param_names : list of str
        Parameter names.
    samples : `~numpy.ndarray` (nsamples, nparams)
        Parameter values.
    weights : `~numpy.ndarray` (nsamples)
        Weight of each sample.
    fname : str
        Output filename.
    bins : int
        Number of bins between -5*std and +5*std where std is the standard
        deviation of the samples for a given parameter.
    """
    from matplotlib import pyplot as plt
    from matplotlib.ticker import (NullFormatter, ScalarFormatter,
                                   NullLocator, AutoLocator)
    nullformatter = NullFormatter()
    formatter = ScalarFormatter()
    formatter.set_powerlimits((-2, 3))

    npar = len(param_names)

    # calculate average and std. dev. of each parameter
    avg = np.average(samples, weights=weights, axis=0)
    if weights is None:
        std = np.std(samples, axis=0)
    else:
        std = np.sqrt(np.sum(weights[:, np.newaxis] * samples**2, axis=0) -
                      avg**2)

    # Create figure
    figsize = (npar*panelsize, npar*panelsize)
    fig = plt.figure(figsize=figsize)

    for j in range(npar):
        ylims = (avg[j] - 5*std[j], avg[j] + 5*std[j])
        for i in range(j + 1):
            xlims = (avg[i] - 5*std[i], avg[i] + 5*std[i])

            ax = plt.subplot(npar, npar, j * npar + i + 1)

            # On diagonal, show a histogram.
            if i == j:
                plt.hist(samples[:, i], weights=weights, range=xlims,
                         bins=bins)

                # Write the average and standard deviation.
                text = '${0:s} = {1:s}$'.format(
                    param_names[i],
                    value_error_str(avg[i], std[i], latex=True)
                    )
                plt.text(0.9, 0.9, text, color='k', ha='right', va='top',
                         transform=ax.transAxes)

                # Make room for the text by pushing up the y limit.
                ymin, ymax = ax.get_ylim()
                ax.set_ylim(ymax=1.2*ymax)

            # Otherwise, show a countour plot
            else:
                H, xedges, yedges = np.histogram2d(samples[:, i],
                                                   samples[:, j],
                                                   bins=bins,
                                                   weights=weights,
                                                   range=[xlims, ylims])
                X = 0.5 * (xedges[:-1] + xedges[1:])
                Y = 0.5 * (yedges[:-1] + yedges[1:])
                plt.contour(X, Y, H)
                plt.ylim(ylims)

            plt.xlim(xlims)

            # Tick locations
            xlocator = AutoLocator()
            xlocator.set_params(nbins=6)
            ax.xaxis.set_major_locator(xlocator)
            if i == j:
                ylocator = NullLocator()
            else:
                ylocator = AutoLocator()
                ylocator.set_params(nbins=6)
            ax.yaxis.set_major_locator(ylocator)

            # X axis labels & formatting
            if j < npar - 1:
                ax.xaxis.set_major_formatter(nullformatter)
            else:
                ax.xaxis.set_major_formatter(formatter)
                plt.xlabel(param_names[i])

            # Y axis labels & formatting
            if j == 0 or i > 0:
                ax.yaxis.set_major_formatter(nullformatter)
            else:
                ax.yaxis.set_major_formatter(formatter)
                plt.ylabel(param_names[j])

    plt.tight_layout()

    if fname is None:
        plt.show()
    else:
        plt.savefig(fname, **kwargs)
    plt.close()

def animate_model(model_or_models, fps=30, length=20.,
                  time_range=(None, None), disp_range=(None, None),
                  match_refphase=True, match_flux=True, fname=None):
    """Animate a model's SED using matplotlib.animation. (requires
    matplotlib v1.1 or higher).

    Parameters
    ----------
    model_or_models : `~sncosmo.Model` or str or iterable thereof
        The model to animate or list of models to animate.
    fps : int, optional
        Frames per second. Default is 30.
    length : float, optional
        Movie length in seconds. Default is 15.
    time_range : (float, float), optional
        Time range to plot (in the timeframe of the first model if multiple
        models are given). `None` indicates to use the maximum extent of the
        model(s).
    disp_range : (float, float), optional
        Dispersion range to plot. `None` indicates to use the maximum extent
        of the model(s).
    match_flux : bool, optional
        For multiple models, scale fluxes so that the peak of the spectrum
        at the reference phase matches that of the first model. Default is
        False.
    match_refphase : bool, optional
        For multiple models, shift additional models so that the model's
        reference phase matches that of the first model.
    fname : str, optional
        If not `None`, save animation to file `fname`. Requires ffmpeg
        to be installed with the appropriate codecs: If `fname` has
        the extension '.mp4' the libx264 codec is used. If the
        extension is '.webm' the VP8 codec is used. Otherwise, the
        'mpeg4' codec is used. The first frame is also written to a
        png.

    Examples
    --------

    Compare the salt2 and hsiao models::

        animate_model(['salt2', 'hsiao'],  time_range=(None, 30.),
                      disp_range=(2000., 9200.))

    Compare the salt2 model with x1 = 1. to the same model with x1 = 0.::

        m1 = sncosmo.get_model('salt2')
        m1.set(x1=1.)
        m2 = sncosmo.get_model('salt2')
        m2.set(x1=0.)
        animate_model([m1, m2])

    """

    from matplotlib import pyplot as plt
    from matplotlib import animation

    # get the model(s)
    if (not isiterable(model_or_models) or
        isinstance(model_or_models, basestring)):
        model_or_models = [model_or_models]
    models = [get_model(m) for m in model_or_models]

    # time offsets needed to match refphases
    time_offsets = [model.refphase - models[0].refphase for model in models]
    if not match_refphase:
        time_offsets = [0.] * len(models)

    # determine times to display
    model_min_times = [models[i].times()[0] - time_offsets[i] for
                       i in range(len(models))]
    model_max_times = [models[i].times()[-1] - time_offsets[i] for
                       i in range(len(models))]
    min_time, max_time = time_range
    if min_time is None:
        min_time = min(model_min_times)
    if max_time is None:
        max_time = max(model_max_times)

    
    # determine the min and max dispersions
    disps = [model.disp() for model in models]
    min_disp, max_disp = disp_range
    if min_disp is None:
        min_disp = min([d[0] for d in disps])
    if max_disp is None:
        max_disp = max([d[-1] for d in disps])

    # model time interval between frames
    time_interval = (max_time - min_time) / (length * fps)

    # maximum flux density of each model at the refphase
    max_fluxes = [np.max(model.flux(model.refphase)) for model in models]

    # scaling factors
    if match_flux:
        max_bandfluxes = [model.bandflux(model.refband, model.refphase)
                          for model in models]
        scaling_factors = [max_bandfluxes[0] / f for f in max_bandfluxes]
        global_max_flux = max_fluxes[0]
    else:
        scaling_factors = [1.] * len(models)
        global_max_flux = max(max_fluxes)

    ymin = -0.06 * global_max_flux
    ymax = 1.1 * global_max_flux

    # Set up the figure, the axis, and the plot element we want to animate
    fig = plt.figure()
    ax = plt.axes(xlim=(min_disp, max_disp), ylim=(ymin, ymax))
    plt.axhline(y=0., c='k')
    plt.xlabel('Wavelength ($\\AA$)') 
    plt.ylabel('Flux Density ($F_\lambda$)')
    time_text = ax.text(0.05, 0.95, '', ha='left', va='top',
                        transform=ax.transAxes)
    empty_lists = 2 * len(models) * [[]]
    lines = ax.plot(*empty_lists, lw=1)
    for line, model in zip(lines, models):
        line.set_label(model.name)
    legend = plt.legend(loc='upper right')

    def init():
        for line in lines:
            line.set_data([], [])
        time_text.set_text('')
        return tuple(lines) + (time_text,)

    def animate(i):
        current_time = min_time + time_interval * i
        for j in range(len(models)):
            y = models[j].flux(current_time + time_offsets[j])
            lines[j].set_data(disps[j], y * scaling_factors[j])
        time_text.set_text('time (days) = {:.1f}'.format(current_time))
        return tuple(lines) + (time_text,)

    # Call the animator.
    ani = animation.FuncAnimation(fig, animate, init_func=init,
                                  frames=int(fps*length), interval=(1000./fps),
                                  blit=True)

    # Save the animation as an mp4. This requires that ffmpeg is installed.
    if fname is not None:
        i = fname.rfind('.')
        stillfname = fname[:i] + '.png'
        plt.savefig(stillfname) 

        ext = fname[i+1:]
        codec = {'mp4': 'libx264', 'webm': 'libvpx'}.get(ext, 'mpeg4')
        ani.save(fname, fps=fps, codec=codec, extra_args=['-vcodec', codec],
                 writer='ffmpeg_file', bitrate=1800)

    else:
        plt.show()
    plt.clf()
