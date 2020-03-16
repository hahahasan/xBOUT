import numpy as np

from .utils import _set_attrs_on_all_vars


class Region:
    """
    Contains the global indices bounding a single topological region, i.e. a region with
    logically rectangular contiguous data.

    Also stores the names of any neighbouring regions.
    """
    def __init__(self, *, name, xinner_ind, xouter_ind, ylower_ind, yupper_ind, connect_inner=None,
                 connect_outer=None, connect_lower=None, connect_upper=None):
        self.name = name
        self.xinner_ind = xinner_ind
        self.xouter_ind = xouter_ind
        self.ylower_ind = ylower_ind
        self.yupper_ind = yupper_ind
        self.connection_inner = connect_inner
        self.connection_outer = connect_outer
        self.connection_lower = connect_lower
        self.connection_upper = connect_upper

    def getSlices(self, mxg=0, myg=0):
        """
        Return x- and y-dimension slices that select this region from the global
        DataArray.

        Returns
        -------
        xslice, yslice : slice, slice
        """
        xi = self.xinner_ind
        if self.connection_inner is not None:
            xi -= mxg

        xo = self.xouter_ind
        if self.connection_outer is not None:
            xi += mxg

        yl = self.ylower_ind
        if self.connection_lower is not None:
            yl -= myg

        yu = self.yupper_ind
        if self.connection_upper is not None:
            yu += myg

        return slice(xi, xo), slice(yl, yu)

    def getInnerGuardsSlices(self, mxg):
        """
        Return x- and y-dimension slices that select mxg guard cells on the inner-x side
        of this region from the global DataArray.

        Parameters
        ----------
        mxg : int
            Number of guard cells
        """
        return slice(self.xinner_ind - mxg, self.xinner_ind), slice(self.ylower_ind,
                self.yupper_ind)

    def getOuterGuardsSlices(self, mxg):
        """
        Return x- and y-dimension slices that select mxg guard cells on the outer-x side
        of this region from the global DataArray.

        Parameters
        ----------
        mxg : int
            Number of guard cells
        """
        return slice(self.xouter_ind, self.xouter_ind + mxg), slice(self.ylower_ind,
                self.yupper_ind)

    def getLowerGuardsSlices(self, myg):
        """
        Return x- and y-dimension slices that select myg guard cells on the lower-y side
        of this region from the global DataArray.

        Parameters
        ----------
        myg : int
            Number of guard cells
        """
        return slice(self.xinner_ind, self.xouter_ind), slice(self.ylower_ind - myg,
                self.ylower_ind)

    def getUpperGuardsSlices(self, myg):
        """
        Return x- and y-dimension slices that select myg guard cells on the upper-y side
        of this region from the global DataArray.

        Parameters
        ----------
        myg : int
            Number of guard cells
        """
        return slice(self.xinner_ind, self.xouter_ind), slice(self.yupper_ind,
                self.yupper_ind + myg)


def _in_range(val, lower, upper):
    if val < lower:
        return lower
    elif val > upper:
        return upper
    else:
        return val


def _order_vars(lower, upper):
    if upper < lower:
        return upper, lower
    else:
        return lower, upper


def _get_topology(ds):
    jys11 = ds.metadata['jyseps1_1']
    jys21 = ds.metadata['jyseps2_1']
    nyinner = ds.metadata['ny_inner']
    jys12 = ds.metadata['jyseps1_2']
    jys22 = ds.metadata['jyseps2_2']
    ny = ds.metadata['ny']
    ixs1 = ds.metadata['ixseps1']
    ixs2 = ds.metadata['ixseps2']
    nx = ds.metadata['nx']
    if jys21 == jys12:
        # No upper X-point
        if jys11 <= 0 and jys22 >= ny - 1:
            ix = min(ixs1, ixs2)
            if ix >= nx - 1:
                return 'core'
            elif ix <= 0:
                return 'sol'
            else:
                return 'limiter'

        return 'single-null'

    if jys11 == jys21 and jys12 == jys22:
        return 'xpoint'

    if ixs1 == ixs2:
        return 'connected-double-null'

    return 'disconnected-double-null'


def _create_connection_x(regions, inner, outer):
    regions[inner].connection_outer = outer
    regions[outer].connection_inner = inner


def _create_connection_y(regions, lower, upper):
    regions[lower].connection_upper = upper
    regions[upper].connection_lower = lower


def _create_regions_toroidal(ds):
    topology = _get_topology(ds)

    coordinates = {'t': ds.metadata.get('bout_tdim', None),
                   'x': ds.metadata.get('bout_xdim', None),
                   'y': ds.metadata.get('bout_ydim', None),
                   'z': ds.metadata.get('bout_zdim', None)}

    ixs1 = ds.metadata['ixseps1']
    ixs2 = ds.metadata['ixseps2']
    nx = ds.metadata['nx']

    jys11 = ds.metadata['jyseps1_1']
    jys21 = ds.metadata['jyseps2_1']
    nyinner = ds.metadata['ny_inner']
    jys12 = ds.metadata['jyseps1_2']
    jys22 = ds.metadata['jyseps2_2']
    ny = ds.metadata['ny']

    mxg = ds.metadata['MXG']
    myg = ds.metadata['MYG']
    # keep_yboundaries is 1 if there are y-boundaries and 0 if there are not
    ybndry = ds.metadata['keep_yboundaries']*myg

    # Make sure all sizes are sensible
    ixs1 = _in_range(ixs1, 0, nx)
    ixs2 = _in_range(ixs2, 0, nx)
    ixs1, ixs2 = _order_vars(ixs1, ixs2)
    jys11 = _in_range(jys11, 0, ny - 1)
    jys21 = _in_range(jys21, 0, ny - 1)
    jys12 = _in_range(jys12, 0, ny - 1)
    jys21, jys12 = _order_vars(jys21, jys12)
    nyinner = _in_range(nyinner, jys21 + 1, jys12 + 1)
    jys22 = _in_range(jys22, 0, ny - 1)

    # Adjust for boundary cells
    # keep_xboundaries is 1 if there are x-boundaries and 0 if there are not
    if not ds.metadata['keep_xboundaries']:
        ixs1 -= mxg
        ixs2 -= mxg
        nx -= 2*mxg
    jys11 += ybndry
    jys21 += ybndry
    nyinner += 2*ybndry
    jys12 += 3*ybndry
    jys22 += 3*ybndry
    ny += 4*ybndry

    # Note, include guard cells in the created regions, fill them later
    regions = {}
    if topology == 'disconnected-double-null':
        regions['lower_inner_PFR'] = Region(
                name='lower_inner_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['lower_inner_intersep'] = Region(
                name='lower_inner_intersep', xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['lower_inner_SOL'] = Region(
                name='lower_inner_SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['inner_core'] = Region(
                name='inner_core', xinner_ind=0, xouter_ind=ixs1, ylower_ind=jys11 + 1,
                yupper_ind=jys21 + 1)
        regions['inner_intersep'] = Region(
                name='inner_intersep', xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys11 + 1, yupper_ind=jys21 + 1)
        regions['inner_SOL'] = Region(
                name='inner_SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=jys11 + 1,
                yupper_ind=jys21 + 1)
        regions['upper_inner_PFR'] = Region(
                name='upper_inner_PFR', xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_inner_intersep'] = Region(
                name='upper_inner_intersep', xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_inner_SOL'] = Region(
                name='upper_inner_SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=jys21
                + 1, yupper_ind=nyinner)
        regions['upper_outer_PFR'] = Region(
                name='upper_outer_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=nyinner,
                yupper_ind=jys12 + 1)
        regions['upper_outer_intersep'] = Region(
                name='upper_outer_intersep', xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['upper_outer_SOL'] = Region(
                name='upper_outer_SOL', xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['outer_core'] = Region(
                name='outer_core', xinner_ind=0, xouter_ind=ixs1, ylower_ind=jys12 + 1,
                yupper_ind=jys22 + 1)
        regions['outer_intersep'] = Region(
                name='outer_intersep', xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys12 + 1, yupper_ind=jys22 + 1)
        regions['outer_SOL'] = Region(
                name='outer_SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=jys12 + 1,
                yupper_ind=jys22 + 1)
        regions['lower_outer_PFR'] = Region(
                name='lower_outer_PFR', xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_intersep'] = Region(
                name='lower_outer_intersep', xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_SOL'] = Region(
                name='lower_outer_SOL', xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        _create_connection_x(regions, 'lower_inner_PFR', 'lower_inner_intersep')
        _create_connection_x(regions, 'lower_inner_intersep', 'lower_inner_SOL')
        _create_connection_x(regions, 'inner_core', 'inner_intersep')
        _create_connection_x(regions, 'inner_intersep', 'inner_SOL')
        _create_connection_x(regions, 'upper_inner_PFR', 'upper_inner_intersep')
        _create_connection_x(regions, 'upper_inner_intersep', 'upper_inner_SOL')
        _create_connection_x(regions, 'upper_outer_PFR', 'upper_outer_intersep')
        _create_connection_x(regions, 'upper_outer_intersep', 'upper_outer_SOL')
        _create_connection_x(regions, 'outer_core', 'outer_intersep')
        _create_connection_x(regions, 'outer_intersep', 'outer_SOL')
        _create_connection_x(regions, 'lower_outer_PFR', 'lower_outer_intersep')
        _create_connection_x(regions, 'lower_outer_intersep', 'lower_outer_SOL')
        _create_connection_y(regions, 'lower_inner_PFR', 'lower_outer_PFR')
        _create_connection_y(regions, 'lower_inner_intersep', 'inner_intersep')
        _create_connection_y(regions, 'lower_inner_SOL', 'inner_SOL')
        _create_connection_y(regions, 'inner_core', 'outer_core')
        _create_connection_y(regions, 'outer_core', 'inner_core')
        _create_connection_y(regions, 'inner_intersep', 'outer_intersep')
        _create_connection_y(regions, 'inner_SOL', 'upper_inner_SOL')
        _create_connection_y(regions, 'upper_outer_intersep', 'upper_inner_intersep')
        _create_connection_y(regions, 'upper_outer_PFR', 'upper_inner_PFR')
        _create_connection_y(regions, 'upper_outer_SOL', 'outer_SOL')
        _create_connection_y(regions, 'outer_intersep', 'lower_outer_intersep')
        _create_connection_y(regions, 'outer_SOL', 'lower_outer_SOL')
    elif topology == 'connected-double-null':
        regions['lower_inner_PFR'] = Region(
                name='lower_inner_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['lower_inner_SOL'] = Region(
                name='lower_inner_SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['inner_core'] = Region(
                name='inner_core', xinner_ind=0, xouter_ind=ixs1, ylower_ind=jys11 + 1,
                yupper_ind=jys21 + 1)
        regions['inner_SOL'] = Region(
                name='inner_SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=jys11 + 1,
                yupper_ind=jys21 + 1)
        regions['upper_inner_PFR'] = Region(
                name='upper_inner_PFR', xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_inner_SOL'] = Region(
                name='upper_inner_SOL', xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_outer_PFR'] = Region(
                name='upper_outer_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=nyinner,
                yupper_ind=jys12 + 1)
        regions['upper_outer_SOL'] = Region(
                name='upper_outer_SOL', xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['outer_core'] = Region(
                name='outer_core', xinner_ind=0, xouter_ind=ixs1, ylower_ind=jys12 + 1,
                yupper_ind=jys22 + 1)
        regions['outer_SOL'] = Region(
                name='outer_SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=jys12 + 1,
                yupper_ind=jys22 + 1)
        regions['lower_outer_PFR'] = Region(
                name='lower_outer_PFR', xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_SOL'] = Region(
                name='lower_outer_SOL', xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        _create_connection_x(regions, 'lower_inner_PFR', 'lower_inner_SOL')
        _create_connection_x(regions, 'inner_core', 'inner_SOL')
        _create_connection_x(regions, 'upper_inner_PFR', 'upper_inner_SOL')
        _create_connection_x(regions, 'upper_outer_PFR', 'upper_outer_SOL')
        _create_connection_x(regions, 'outer_core', 'outer_SOL')
        _create_connection_x(regions, 'lower_outer_PFR', 'lower_outer_SOL')
        _create_connection_y(regions, 'lower_inner_PFR', 'lower_outer_PFR')
        _create_connection_y(regions, 'lower_inner_SOL', 'inner_SOL')
        _create_connection_y(regions, 'inner_core', 'outer_core')
        _create_connection_y(regions, 'outer_core', 'inner_core')
        _create_connection_y(regions, 'inner_SOL', 'upper_inner_SOL')
        _create_connection_y(regions, 'upper_outer_PFR', 'upper_inner_PFR')
        _create_connection_y(regions, 'upper_outer_SOL', 'outer_SOL')
        _create_connection_y(regions, 'outer_SOL', 'lower_outer_SOL')
    elif topology == 'single-null':
        regions['inner_PFR'] = Region(
                name='inner_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=0, yupper_ind=jys11 + 1)
        regions['inner_SOL'] = Region(
                name='inner_SOL', xinner_ind=ixs1, xouter_ind=nx, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['core'] = Region(
                name='core', xinner_ind=0, xouter_ind=ixs1, ylower_ind=jys11 + 1, yupper_ind=jys22 + 1)
        regions['SOL'] = Region(
                name='SOL', xinner_ind=ixs2, xouter_ind=nx, ylower_ind=jys11 + 1, yupper_ind=jys22 + 1)
        regions['outer_PFR'] = Region(
                name='lower_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=jys22 + 1,
                yupper_ind=ny)
        regions['outer_SOL'] = Region(
                name='lower_SOL', xinner_ind=ixs1, xouter_ind=nx, ylower_ind=jys22 + 1,
                yupper_ind=ny)
        _create_connection_x(regions, 'inner_PFR', 'inner_SOL')
        _create_connection_x(regions, 'core', 'SOL')
        _create_connection_x(regions, 'outer_PFR', 'outer_SOL')
        _create_connection_y(regions, 'inner_PFR', 'outer_PFR')
        _create_connection_y(regions, 'inner_SOL', 'SOL')
        _create_connection_y(regions, 'core', 'core')
        _create_connection_y(regions, 'SOL', 'outer_SOL')
    elif topology == 'limiter':
        regions['core'] = Region(
                name='core', xinner_ind=0, xouter_ind=ixs1, ylower_ind=0, yupper_ind=ny)
        regions['SOL'] = Region(
                name='SOL', xinner_ind=ixs1, xouter_ind=nx, ylower_ind=0, yupper_ind=ny)
        _create_connection_x(regions, 'core', 'SOL')
        _create_connection_y(regions, 'core', 'core')
    elif topology == 'core':
        regions['core'] = Region(
                name='core', xinner_ind=0, xouter_ind=nx, ylower_ind=0, yupper_ind=ny)
        _create_connection_y(regions, 'core', 'core')
    elif topology == 'sol':
        regions['sol'] = Region(
                name='sol', xinner_ind=0, xouter_ind=nx, ylower_ind=0, yupper_ind=ny)
    elif topology == 'xpoint':
        regions['lower_inner_PFR'] = Region(
                name='lower_inner_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['lower_inner_SOL'] = Region(
                name='lower_inner_SOL', xinner_ind=ixs1, xouter_ind=nx, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['upper_inner_PFR'] = Region(
                name='upper_inner_PFR', xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys11 + 1, yupper_ind=nyinner)
        regions['upper_inner_SOL'] = Region(
                name='upper_inner_SOL', xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=jys11 + 1, yupper_ind=nyinner)
        regions['upper_outer_PFR'] = Region(
                name='upper_outer_PFR', xinner_ind=0, xouter_ind=ixs1, ylower_ind=nyinner,
                yupper_ind=jys22 + 1)
        regions['upper_outer_SOL'] = Region(
                name='upper_outer_SOL', xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=nyinner, yupper_ind=jys22 + 1)
        regions['lower_outer_PFR'] = Region(
                name='lower_outer_PFR', xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_SOL'] = Region(
                name='lower_outer_SOL', xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        _create_connection_x(regions, 'lower_inner_PFR', 'lower_inner_SOL')
        _create_connection_x(regions, 'upper_inner_PFR', 'upper_inner_SOL')
        _create_connection_x(regions, 'upper_outer_PFR', 'upper_outer_SOL')
        _create_connection_x(regions, 'lower_outer_PFR', 'lower_outer_SOL')
        _create_connection_y(regions, 'lower_inner_PFR', 'lower_outer_PFR')
        _create_connection_y(regions, 'lower_inner_SOL', 'upper_inner_SOL')
        _create_connection_y(regions, 'upper_outer_PFR', 'upper_inner_PFR')
        _create_connection_y(regions, 'upper_outer_SOL', 'lower_outer_SOL')
    else:
        raise NotImplementedError("Topology '" + topology + "' is not implemented")

    ds = _set_attrs_on_all_vars(ds, 'regions', regions)

    return ds
