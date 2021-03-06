#! /usr/bin/env python

"""
Module with the function of merit definitions for the NEGFC optimization.
"""


__all__ = []

import numpy as np
from hciplot import plot_frames
from skimage.draw import circle
from ..metrics import cube_inject_companions
from ..var import frame_center
from ..pca import pca_annulus, pca_annular
from ..preproc import cube_crop_frames


def chisquare(modelParameters, cube, angs, plsc, psfs_norm, fwhm, annulus_width,  
              aperture_radius, initialState, ncomp, cube_ref=None, 
              svd_mode='lapack', scaling=None, fmerit='sum', collapse='median',
              algo=pca_annulus, delta_rot=1, imlib='opencv', 
              interpolation='lanczos4', debug=False):
    """
    Calculate the reduced chi2:
    \chi^2_r = \frac{1}{N-3}\sum_{j=1}^{N} |I_j|,
    where N is the number of pixels within a circular aperture centered on the 
    first estimate of the planet position, and I_j the j-th pixel intensity.
    
    Parameters
    ----------    
    modelParameters: tuple
        The model parameters, typically (r, theta, flux).
    cube: numpy.array
        The cube of fits images expressed as a numpy.array.
    angs: numpy.array
        The parallactic angle fits image expressed as a numpy.array. 
    plsc: float
        The platescale, in arcsec per pixel.
    psfs_norm: numpy.array
        The scaled psf expressed as a numpy.array.    
    fwhm : float
        The FHWM in pixels.
    annulus_width: int, optional
        The width in pixels of the annulus on which the PCA is done.       
    aperture_radius: int, optional
        The radius of the circular aperture in terms of the FWHM.
    initialState: numpy.array
        Position (r, theta) of the circular aperture center.
    ncomp: int
        The number of principal components.
    cube_ref : numpy ndarray, 3d, optional
        Reference library cube. For Reference Star Differential Imaging.
    svd_mode : {'lapack', 'randsvd', 'eigen', 'arpack'}, str optional
        Switch for different ways of computing the SVD and selected PCs.         
    scaling : {'temp-mean', 'temp-standard'} or None, optional
        With None, no scaling is performed on the input data before SVD. With 
        "temp-mean" then temporal px-wise mean subtraction is done and with 
        "temp-standard" temporal mean centering plus scaling to unit variance 
        is done. 
    fmerit : {'sum', 'stddev'}, string optional
        Chooses the figure of merit to be used. stddev works better for close in
        companions sitting on top of speckle noise.
    collapse : {'median', 'mean', 'sum', 'trimmean', None}, str or None, optional
        Sets the way of collapsing the frames for producing a final image. If
        None then the cube of residuals is used when measuring the function of
        merit (instead of a single final frame).
    algo: vip function, optional {pca_annulus, pca_annular}
        Post-processing algorithm used.
    delta_rot: float, optional
        If algo is set to pca_annular, delta_rot is the angular threshold used
        to select frames in the PCA library (see description of pca_annular).
    imlib : str, optional
        See the documentation of the ``vip_hci.preproc.frame_shift`` function.
    interpolation : str, optional
        See the documentation of the ``vip_hci.preproc.frame_shift`` function.
        
    Returns
    -------
    out: float
        The reduced chi squared.
        
    """    
    try:
        r, theta, flux = modelParameters
    except TypeError:
        msg = 'modelParameters must be a tuple, {} was given'
        print(msg.format(type(modelParameters)))

    # Create the cube with the negative fake companion injected
    cube_negfc = cube_inject_companions(cube, psfs_norm, angs, flevel=-flux,
                                        plsc=plsc, rad_dists=[r], n_branches=1,
                                        theta=theta, imlib=imlib, verbose=False,
                                        interpolation=interpolation)
                                      
    # Perform PCA and extract the zone of interest
    res = get_values_optimize(cube_negfc, angs, ncomp, annulus_width,
                              aperture_radius, fwhm, initialState[0],
                              initialState[1], cube_ref=cube_ref,
                              svd_mode=svd_mode, scaling=scaling, algo=algo,
                              delta_rot=delta_rot, collapse=collapse, 
                              debug=debug)
    if debug and collapse is not None:
        values, frpca = res
        plot_frames(frpca)
    else:
        values = res
    
    # Function of merit
    if fmerit == 'sum':
        values = np.abs(values)
        chi2 = np.sum(values[values > 0])
        N = len(values[values > 0])
        return chi2 / (N-3)
    elif fmerit == 'stddev':
        return np.std(values[values != 0])
    else:
        raise RuntimeError('`fmerit` choice not recognized')


def get_values_optimize(cube, angs, ncomp, annulus_width, aperture_radius, 
                        fwhm, r_guess, theta_guess, cube_ref=None, 
                        svd_mode='lapack', scaling=None, algo=pca_annulus, 
                        delta_rot=1, imlib='opencv', interpolation='lanczos4',
                        collapse='median', debug=False):
    """ Extracts a PCA-ed annulus from the cube and returns the flux values of
    the pixels included in a circular aperture centered at a given position.
    
    Parameters
    ----------
    cube: numpy.array
        The cube of fits images expressed as a numpy.array.
    angs: numpy.array
        The parallactic angle fits image expressed as a numpy.array.
    ncomp: int
        The number of principal component.
    annulus_width: float
        The width in pixels of the annulus on which the PCA is performed.
    aperture_radius: float
        The radius in fwhm of the circular aperture.
    fwhm: float
        Value of the FWHM of the PSF.
    r_guess: float
        The radial position of the center of the circular aperture. This 
        parameter is NOT the radial position of the candidate associated to the 
        Markov chain, but should be the fixed initial guess.
    theta_guess: float
        The angular position of the center of the circular aperture. This 
        parameter is NOT the angular position of the candidate associated to the 
        Markov chain, but should be the fixed initial guess.  
    cube_ref : numpy ndarray, 3d, optional
        Reference library cube. For Reference Star Differential Imaging.
    svd_mode : {'lapack', 'randsvd', 'eigen', 'arpack'}, str optional
        Switch for different ways of computing the SVD and selected PCs.
    scaling : {None, 'temp-mean', 'temp-standard'}
        With None, no scaling is performed on the input data before SVD. With 
        "temp-mean" then temporal px-wise mean subtraction is done and with 
        "temp-standard" temporal mean centering plus scaling to unit variance 
        is done.
    algo: vip function, optional {pca_annulus, pca_annular}
        Post-processing algorithm used.
    delta_rot: float, optional
        If algo is set to pca_annular, delta_rot is the angular threshold used
        to select frames in the PCA library (see description of pca_annular).
    imlib : str, optional
        See the documentation of the ``vip_hci.preproc.frame_rotate`` function.
    interpolation : str, optional
        See the documentation of the ``vip_hci.preproc.frame_rotate`` function.
    collapse : {'median', 'mean', 'sum', 'trimmean', None}, str or None, optional
        Sets the way of collapsing the frames for producing a final image. If
        None then the cube of residuals is returned.
    debug: boolean
        If True, the cube is returned along with the values.        
        
    Returns
    -------
    values: numpy.array
        The pixel values in the circular aperture after the PCA process.

    If debug is True the PCA frame is returned (in case when collapse is not None)
        
    """
    centy_fr, centx_fr = frame_center(cube[0])
    posy = r_guess * np.sin(np.deg2rad(theta_guess)) + centy_fr
    posx = r_guess * np.cos(np.deg2rad(theta_guess)) + centx_fr
    halfw = max(aperture_radius*fwhm, annulus_width/2)

    # Checking annulus/aperture sizes. Assuming square frames
    msg = 'The annulus and/or the circular aperture used by the NegFC falls '
    msg += 'outside the FOV. Try increasing the size of your frames or '
    msg += 'decreasing the annulus or aperture size.'
    msg += 'rguess: {:.0f}px; centx_fr: {:.0f}px'.format(r_guess,centx_fr)
    msg += 'halfw: {:.0f}px'.format(halfw)
    if r_guess > centx_fr-halfw or r_guess <= halfw:
        raise RuntimeError(msg)
                          
    if algo == pca_annulus:
        pca_res = pca_annulus(cube, angs, ncomp, annulus_width, r_guess, cube_ref,
                              svd_mode, scaling, imlib=imlib,
                              interpolation=interpolation, collapse=collapse)
    elif algo == pca_annular:
        radius_int = int(np.floor(r_guess-annulus_width/2))
        # crop cube to just be larger than annulus => FASTER PCA
        crop_sz = int(np.ceil(r_guess+annulus_width))
        if not crop_sz %2:
            crop_sz+=1
        if crop_sz < cube.shape[1] and crop_sz < cube.shape[2]:
            pad = int((cube.shape[1]-crop_sz)/2)
            crop_cube = cube_crop_frames(cube, crop_sz, verbose=False)
        else:
            crop_cube = cube

        pca_res_tmp = pca_annular(crop_cube, angs, radius_int=radius_int, fwhm=fwhm, 
                                  asize=annulus_width, delta_rot=delta_rot, 
                                  ncomp=ncomp, svd_mode=svd_mode, scaling=scaling, 
                                  imlib=imlib, interpolation=interpolation,
                                  collapse=collapse, full_output=False, 
                                  verbose=False)
        # pad again now                      
        pca_res = np.pad(pca_res_tmp,pad,mode='constant',constant_values=0)
        
                                  
    indices = circle(posy, posx, radius=aperture_radius*fwhm)
    yy, xx = indices

    if collapse is None:
        values = pca_res[:, yy, xx].ravel()
    else:
        values = pca_res[yy, xx].ravel()

    if debug and collapse is not None:
        return values, pca_res
    else:
        return values

