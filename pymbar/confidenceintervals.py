##############################################################################
# pymbar: A Python Library for MBAR
#
# Copyright 2010-2014 University of Virginia, Memorial Sloan-Kettering Cancer Center
#
# Authors: Michael Shirts, John Chodera
# Contributors: Kyle Beauchamp
#
# pymbar is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 2.1
# of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with pymbar. If not, see <http://www.gnu.org/licenses/>.
##############################################################################

import numpy
import scipy
import scipy.special
import scipy.stats

def OrderReplicates(replicates, K):

    ''' Inputs: An array of replicates, and the size of the data.

        Outputs: a Nxdims arrary of the data in the replicates, normalized by the standard deviation

    '''

    dims = np.shape(replicates[0]['destimated'])

    sigma = replicates[0]['destimated']
    zerosigma = (sigma == 0)
    sigmacorr = zerosigma  # we need to avoid errors with zero standard errors.  We will ignore them later.
    sigma += sigmacorr

    yi = []
    for (replicate_index, replicate) in enumerate(replicates):
        yi.append(replicate['error']/sigma)
    yiarray = np.asarray(yi)
    sortedyi = np.zeros(np.shape(yiarray))
    if len(dims) == 0:
        sortedyi[:] = np.sort(yiarray)
    elif len(dims) == 1:
        for i in range(K):
            sortedyi[:,i] = np.sort(yiarray[:,i])
    elif len(dims) == 2:
        for i in range(K):
            for j in range(K):
                sortedyi[:,i,j] = np.sort(yiarray[:,i,j])

    # remove the correction so we have zero sigmas again
    sigma -= sigmacorr
    return sortedyi

def AndersonDarling(replicates, K):

    # inputs:
    #      replicates: list of replicates
    #      K: number of replicates
    # outputs: Anderson-Darling statistics.
    # http://en.wikipedia.org/wiki/Anderson%E2%80%93Darling_test
    #
    # Since both sigma and mu are known (mu exactly, sigma as an estimate from mbar),
    # we can apply the case 1 test.
    #
    # Because sigma is not precise, we should accept a higher threshold than the 1%
    # threshold listed below to throw an error:
    #
    # 15%  1.610
    # 10%  1.933
    # 5%   2.492
    # 2.5% 3.070
    # 1%   3.857
    #
    # So we choose something like 4.5.  Note that for lower numbers of
    # samples, it's more likely.  2000 samples for each of the
    # harmonic_oscillators_distributions.py seems to give good
    # results.
    #
    # for now, the standard deviation we use is the one from the
    # _first_ replicate.

    sortedyi = OrderReplicates(replicates, K)
    zerosigma = (replicates[0]['destimated'] == 0) # ignore the ones with zero values of the std

    N = len(replicates)
    dims = np.shape(replicates[0]['destimated'])
    sum = np.zeros(dims)
    for i in range(N):
        cdfi = scipy.stats.norm.cdf(sortedyi[i])
        sum += (2*i-1)*np.log(cdfi) + (2*(N-i)+1)*np.log(1-cdfi)
    A2 = -N - sum/N
    A2[zerosigma] = 0
    return A2

def QQPlot(replicates, K, title='Generic Q-Q plot', filename = 'qq.pdf'):

    import matplotlib
    import matplotlib.pyplot as plt

    sortedyi = OrderReplicates(replicates, K)
    N = len(replicates)
    dim = len(np.shape(replicates[0]['error']))
    xvals = scipy.stats.norm.ppf((np.arange(0,N)+0.5)/N)  # inverse pdf

    if dim == 0:
        nplots = 1
    elif dim == 1:
        nplots = K
    elif dim == 2:
        nplots = K*K

    yy = np.zeros([N,nplots])

    labelij = dict()
    if dim == 0:
        yy[:,0] = sortedyi[:]
    elif dim == 1:
        nplots = K
        for i in range(K):
            yy[:,i] = sortedyi[:,i]
    elif dim == 2:
        nplots = K*(K-1)
        k = 0
        for i in range(K):
            for j in range(K):
                if i!=j:
                    yy[:,k] = sortedyi[:,i,j]
                    labelij[k] = [i,j]
                    k+=1

    sq = (nplots)**0.5
    labelsize = 30.0/sq
    matplotlib.rc('axes', facecolor = '#E3E4FA')
    matplotlib.rc('axes', edgecolor = 'white')
    matplotlib.rc('xtick', labelsize = labelsize)
    matplotlib.rc('ytick', labelsize = labelsize)
    h = int(sq)
    w = h + 1 + 1*(sq-h>0.5)
    fig = plt.figure(figsize = (8,6))
    for i in range(nplots):
        ax = plt.subplot(h, w, i+1)
        ms = 75.0/len(yy[:,i])
        ax.plot(xvals, yy[:,i], color='r', ms=ms, marker='o', mec='r')
        ax.plot(xvals, xvals, color='b', ls = '-')
        plt.xlim(xvals.min(), xvals.max())
        if dim==1:
            ax.annotate(r'State $\mathrm{%d}$' % (i), xy=(0.5, 0.9), xycoords=('axes fraction', 'axes fraction'), xytext=(0, -2), size=labelsize, textcoords='offset points', va='top', ha='center', color='#151B54', bbox = dict(fc='w', ec='none', alpha=0.5))
        if dim==2:
            ax.annotate(r'State $\mathrm{%d-%d}$' % (labelij[i][0], labelij[i][1]), xy=(0.5, 0.9), xycoords=('axes fraction', 'axes fraction'), xytext=(0, -2), size=labelsize, textcoords='offset points', va='top', ha='center', color='#151B54', bbox = dict(fc='w', ec='none', alpha=0.5))
    plt.suptitle(title, fontsize=20)
    plt.savefig(filename)
    plt.close(fig)

    return

def generateConfidenceIntervals(replicates, K):
    # inputs:
    #      replicates: list of replicates
    #      K: number of replicates
    #=============================================================================================
    # Analyze data.
    #=============================================================================================
    #
    # By Chebyshev's inequality, we should have
    #   P(error >= alpha sigma) <= 1 / alpha^2
    # so that a lower bound will be
    #   P(error < alpha sigma) > 1 - 1 / alpha^2
    # for any real multiplier 'k', where 'sigma' represents the computed uncertainty (as one standard deviation).
    #
    # If the error is normal, we should have
    #   P(error < alpha sigma) = erf(alpha / sqrt(2))

    print "The uncertainty estimates are tested in this section."
    print "If the error is normally distributed, the actual error will be less than a"
    print "multiplier 'alpha' times the computed uncertainty 'sigma' a fraction of"
    print "time given by:"
    print "P(error < alpha sigma) = erf(alpha / sqrt(2))"
    print "For example, the true error should be less than 1.0 * sigma"
    print "(one standard deviation) a total of 68% of the time, and"
    print "less than 2.0 * sigma (two standard deviations) 95% of the time."
    print "The observed fraction of the time that error < alpha sigma, and its"
    print "uncertainty, is given as 'obs' (with uncertainty 'obs err') below."
    print "This should be compared to the column labeled 'normal'."
    print "A weak lower bound that holds regardless of how the error is distributed is given"
    print "by Chebyshev's inequality, and is listed as 'cheby' below."
    print "Uncertainty estimates are tested for both free energy differences and expectations."
    print ""

    # error bounds

    min_alpha = 0.1
    max_alpha = 4.0
    nalpha = 40
    alpha_values = numpy.linspace(min_alpha, max_alpha, num=nalpha)
    Pobs = numpy.zeros([nalpha], dtype=numpy.float64)
    dPobs = numpy.zeros([nalpha], dtype=numpy.float64)
    Plow = numpy.zeros([nalpha], dtype=numpy.float64)
    Phigh = numpy.zeros([nalpha], dtype=numpy.float64)
    nreplicates = len(replicates)
    dim = len(numpy.shape(replicates[0]['estimated']))
    for alpha_index in range(0, nalpha):
        # Get alpha value.
        alpha = alpha_values[alpha_index]
        # Accumulate statistics across replicates
        a = 1.0
        b = 1.0
        # how many dimensions in the data?

        for (replicate_index, replicate) in enumerate(replicates):
            # Compute fraction of free energy differences where error <= alpha sigma
            # We only count differences where the analytical difference is larger than a cutoff, so that the results will not be limited by machine precision.
            if (dim == 0):
                if numpy.isnan(replicate['error']) or numpy.isnan(replicate['destimated']):
                    print "replicate %d" % replicate_index
                    print "error"
                    print replicate['error']
                    print "destimated"
                    print replicate['destimated']
                    raise "isnan"
                else:
                    if abs(replicate['error']) <= alpha * replicate['destimated']:
                        a += 1.0
                    else:
                        b += 1.0

            elif (dim == 1):
                for i in range(0, K):
                    if numpy.isnan(replicate['error'][i]) or numpy.isnan(replicate['destimated'][i]):
                        print "replicate %d" % replicate_index
                        print "error"
                        print replicate['error']
                        print "destimated"
                        print replicate['destimated']
                        raise "isnan"
                    else:
                        if abs(replicate['error'][i]) <= alpha * replicate['destimated'][i]:
                            a += 1.0
                        else:
                            b += 1.0

            elif (dim == 2):
                for i in range(0, K):
                    for j in range(0, i):
                        if numpy.isnan(replicate['error'][i, j]) or numpy.isnan(replicate['destimated'][i, j]):
                            print "replicate %d" % replicate_index
                            print "ij_error"
                            print replicate['error']
                            print "ij_estimated"
                            print replicate['destimated']
                            raise "isnan"
                        else:
                            if abs(replicate['error'][i, j]) <= alpha * replicate['destimated'][i, j]:
                                a += 1.0
                            else:
                                b += 1.0

        Pobs[alpha_index] = a / (a + b)
        Plow[alpha_index] = scipy.stats.beta.ppf(0.025, a, b)
        Phigh[alpha_index] = scipy.stats.beta.ppf(0.975, a, b)
        dPobs[alpha_index] = numpy.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))

    # Write error as a function of sigma.
    print "Error vs. alpha"
    print "%5s %10s %10s %16s %17s" % ('alpha', 'cheby', 'obs', 'obs err', 'normal')
    Pnorm = scipy.special.erf(alpha_values / numpy.sqrt(2.))
    for alpha_index in range(0, nalpha):
        alpha = alpha_values[alpha_index]
        print "%5.1f %10.6f %10.6f (%10.6f,%10.6f) %10.6f" % (alpha, 1. - 1. / alpha ** 2, Pobs[alpha_index], Plow[alpha_index], Phigh[alpha_index], Pnorm[alpha_index])

    # compute bias, average, etc - do it by replicate, not by bias
    if dim == 0:
        vals = numpy.zeros([nreplicates], dtype=numpy.float64)
        vals_error = numpy.zeros([nreplicates], dtype=numpy.float64)
        vals_std = numpy.zeros([nreplicates], dtype=numpy.float64)
    elif dim == 1:
        vals = numpy.zeros([nreplicates, K], dtype=numpy.float64)
        vals_error = numpy.zeros([nreplicates, K], dtype=numpy.float64)
        vals_std = numpy.zeros([nreplicates, K], dtype=numpy.float64)
    elif dim == 2:
        vals = numpy.zeros([nreplicates, K, K], dtype=numpy.float64)
        vals_error = numpy.zeros([nreplicates, K, K], dtype=numpy.float64)
        vals_std = numpy.zeros([nreplicates, K, K], dtype=numpy.float64)

    rindex = 0
    for replicate in replicates:
        if dim == 0:
            vals[rindex] = replicate['estimated']
            vals_error[rindex] = replicate['error']
            vals_std[rindex] = replicate['destimated']
        elif dim == 1:
            for i in range(0, K):
                vals[rindex,:] = replicate['estimated']      
                vals_error[rindex,:] = replicate['error']      
                vals_std[rindex,:] = replicate['destimated']
        elif dim == 2:
            for i in range(0, K):
                for j in range(0, i):
                    vals[rindex,:,:] = replicate['estimated']      
                    vals_error[rindex,:,:] = replicate['error']      
                    vals_std[rindex,:,:] = replicate['destimated']
        rindex += 1

    aveval = numpy.average(vals, axis=0)
    standarddev = numpy.std(vals, axis=0)
    bias = numpy.average(vals_error, axis=0)
    aveerr = numpy.average(vals_error, axis=0)
    d2 = vals_error ** 2
    rms_error = (numpy.average(d2, axis=0)) ** (1.0 / 2.0)
    d2 = vals_std ** 2
    ave_std = (numpy.average(d2, axis=0)) ** (1.0 / 2.0)

    # for now, just print out the data at the end for each
    print ""
    print "     i      average    bias      rms_error     stddev  ave_analyt_std"
    print "---------------------------------------------------------------------"
    if dim == 0:
        pave = aveval
        pbias = bias
        prms = rms_error
        pstdev = standarddev
        pavestd = ave_std
    elif dim == 1:
        for i in range(0, K):
            pave = aveval[i]
            pbias = bias[i]
            prms = rms_error[i]
            pstdev = standarddev[i]
            pavestd = ave_std[i]
            print "%7d %10.4f  %10.4f  %10.4f  %10.4f %10.4f" % (i, pave, pbias, prms, pstdev, pavestd)
    elif dim == 2:
        for i in range(0, K):
            pave = aveval[0, i]
            pbias = bias[0, i]
            prms = rms_error[0, i]
            pstdev = standarddev[0, i]
            pavestd = ave_std[0, i]
            print "%7d %10.4f  %10.4f  %10.4f  %10.4f %10.4f" % (i, pave, pbias, prms, pstdev, pavestd)

    print "Totals: %10.4f  %10.4f  %10.4f  %10.4f %10.4f" % (pave, pbias, prms, pstdev, pavestd)

    return alpha_values, Pobs, Plow, Phigh, dPobs, Pnorm
