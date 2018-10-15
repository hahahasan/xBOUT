from xarray import register_dataset_accessor, save_mfdataset
from dask.diagnostics import ProgressBar
from numpy import asscalar
from pprint import pprint

from boutdata.data import BoutOptionsFile

from xcollect.collect import collect


def open_boutdataset(datapath='.', prefix='BOUT.dmp', slices={}, chunks={},
                     inputfilepath='.', gridfilepath=None, run_name=None, info=True):
    """
    Load a dataset from a set of BOUT output files, including the input options file.

    Parameters
    ----------
    datapath : str, optional
    prefix : str, optional
    slices : slice object, optional
    chunks : dict, optional
    inputfilepath : str, optional
    gridfilepath : str, optional
    run_name : str, optional
    info : bool, optional

    Returns
    -------
    ds : xarray.Dataset
    """

    ds_all = collect(vars='all', path=datapath, prefix=prefix, slices=slices, chunks=chunks, info=info)
    ds, metadata = _strip_metadata(ds_all)
    ds.attrs['metadata'] = metadata

    options = BoutOptionsFile(inputfilepath)
    ds.attrs['options'] = options

    # TODO This is where you would load the grid file as a separate object
    # (Ideally using xgcm but could also just store the grid.nc file as another dataset)

    if run_name:
        ds.name = run_name

    if info:
        print('Read in BOUT data:')
        print(ds)
        print('Read in BOUT metadata:')
        print(metadata)
        print('Read in BOUT options:')
        print(options)

    return ds


@register_dataset_accessor('bout')
class BoutAccessor(object):
    """
    Contains the BOUT output variables in the form of an xarray.Dataset, and optionally the input file.

    Standard xarray methods and attributes are accessed as if the BoutDataset were just an instance of an xarray.Dataset.
    BOUT-specific methods and attributes are accessed via the bout accessor, e.g. ds.bout.options returns a BoutOptionsFile instance.
    """

    # TODO a BoutDataarray class which uses the register_dataarray_accessor??

    def __init__(self, ds_object):

        # # Load data variables
        # # Should we just load whole dataset here?
        # self.datapath = datapath
        # self.prefix = prefix

        self.data, self.metadata = _strip_metadata(ds_object)
        self.options = None
        # if info:
        #     print('Read in BOUT data:')
        #     print(self.data)
        #     print('Read in BOUT metadata:')
        #     print(self.metadata)
        #
        # if run_name:
        #     self.run_name = run_name
        # else:
        #     self.run_name = datapath
        #
        # if input_file is True:
        #     # Load options from input file using Ben's classes
        #     self.options = BoutOptionsFile(datapath + 'BOUT.inp')
        #     if info:
        #         print('Read in options:\n')
        #         pprint(self.options.as_dict())
        # else:
        #     self.options = None
        #
        # # TODO This is where you would load the grid file as a separate object
        # # (Ideally using xgcm but could also just store the grid.nc file as another dataset)

    def test_method(self):
        print('Test successful!')

    def set_extra_data(self, extra_data):
        self.extra_data = extra_data

    def __str__(self):
        """
        String represenation of the BoutDataset.

        Accessed by print(ds.bout)
        """

        text = 'BoutDataset\n'
        text += 'Contains:\n'
        text += self.data.__str__()
        text += 'with metadata'
        text += self.metadata.__str__()
        if self.options:
            text += 'and options:\n'
            text += self.options.__str__()
        return text

    #def __repr__(self):
    #    return 'boutdata.BoutDataset(', {}, ',', {}, ')'.format(self.datapath, self.prefix)

    def save(self, savepath='.', filetype='NETCDF4', variables=None, save_dtype=None):
        """
        Save data variables.

        Parameters
        ----------
        savepath : str
        filetype : str
        variables : list of str
        """

        if variables is None:
            # Save all variables
            to_save = self.data
        else:
            to_save = self.data[variables]

        if save_dtype is not None:
            to_save = to_save.astype(save_dtype)

        # Store the metadata in the attributes dictionary rather than as data variables in the dataset
        to_save.attrs['metadata'] = self.metadata

        # TODO How should I store other data? In the attributes dict?
        # TODO Convert Ben's options class to a (flattened) nested dictionary then store it in ds.attrs?

        # Save data to a single file
        # TODO option to save each variable to a different netCDF file?
        with ProgressBar():
            # Should give it a descriptive filename (using the run name?)
            if variables is None:
                # Save all variables
                to_save.to_netcdf(path=savepath, format=filetype, compute=True)
            else:
                to_save.data[variables].to_netcdf(path=savepath, engine=filetype, compute=True)

        return

    def save_restart(self, savepath='.', nxpe=None, nype=None, original_decomp=False):
        """
        Write out final timestep as a set of netCDF BOUT.restart files.

        If processor decomposition is not specified then data will be saved used the decomposition it had when loaded.

        Parameters
        ----------
        savepath : str
        nxpe : int
        nype : int
        """

        # Set processor decomposition if not given
        if original_decomp:
            if any([nxpe, nype]):
                raise ValueError('Inconsistent choices for domain decomposition.')
            else:
                nxpe, nype = self.metadata['NXPE'], self.metadata['NYPE']

        # Is this even possible without saving the ghost cells? Can they be recreated?
        restart_datasets, paths = _split_into_restarts(self.data, savepath, nxpe, nype)
        with ProgressBar():
            save_mfdataset(restart_datasets, paths, compute=True)
        return

    # TODO BOUT-specific plotting functionality would be implemented as methods here, e.g. ds.bout.plot_poloidal
    # TODO Could trial a 2D surface plotting method here
    # TODO Could also prototype animated plotting methods here


def _strip_metadata(ds):
    """
    Extract the metadata (nxpe, myg etc.) from the Dataset.

    Assumes that all scalar variables are metadata, not physical data!
    """

    # Find only the scalar variables
    variables = list(ds.variables)
    scalar_vars = [var for var in variables if not any(dim in ['t', 'x', 'y', 'z'] for dim in ds[var].dims)]

    # Save metadata as a dictionary
    metadata_vals = [asscalar(ds[var].values) for var in scalar_vars]
    metadata = dict(zip(scalar_vars, metadata_vals))

    return ds.drop(scalar_vars), metadata
