import json
import os
from os.path import join
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

from astrodask.convenience import _determine_type
from astrodask.helpers_misc import hash_path
from astrodask.misc import map_interface_args, return_cachefile_path
from astrodask.registries import dataseries_type_registry


def delay_init(cls):
    class Delay(cls):
        def __init__(self, *arg, **kwarg):
            self._arg = arg
            self._kwarg = kwarg

        def __getattribute__(self, name):
            self.__class__ = cls
            arg = self._arg
            kwarg = self._kwarg
            del self._arg
            del self._kwarg
            self.__init__(*arg, **kwarg)
            return getattr(self, name)

    return Delay


class DatasetSeries(object):
    """A container for collection of interface instances"""

    def __init__(
        self,
        paths: Union[List[str], List[Path]],
        *interface_args,
        datasetclass=None,
        **interface_kwargs
    ):
        self._dataset_cls = datasetclass
        self.hash = hash_path("".join([str(p) for p in paths]))
        self._metadata = None
        # self.metadata = self._metadatacache()
        # print(self.metadata)
        for p in paths:
            if not (isinstance(p, Path)):
                p = Path(p)
            if not (p.exists()):
                raise ValueError("Specified path '%s' does not exist." % p)
        gen = map_interface_args(paths, *interface_args, **interface_kwargs)
        dec = delay_init
        if self.metadata is None:
            # have to fetch metadata first => no lazy load
            def dec(x):
                return x

        self.datasets = [dec(datasetclass)(p, *a, **kw) for p, a, kw in gen]
        if self.metadata is None:
            dct = {}
            for i, d in enumerate(self.datasets):
                dct[i] = d.metadata
            self.metadata = dct

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        dataseries_type_registry[cls.__name__] = cls

    @classmethod
    def validate_path(cls, path, *args, **kwargs):
        # estimate whether we have a valid path for this dataseries
        return False

    @classmethod
    def from_directory(
        cls, path, *interface_args, datasetclass=None, pattern=None, **interface_kwargs
    ):
        p = Path(path)
        if not (p.exists()):
            raise ValueError("Specified path does not exist.")
        if pattern is None:
            pattern = "*"
        paths = [f for f in p.glob(pattern)]
        return cls(
            paths, *interface_args, datasetclass=datasetclass, **interface_kwargs
        )

    def get_dataset(self, index: Optional[int] = None, reltol=1e-2, **kwargs):
        """Get dataset by some metadata property. In the base class, we go by list index."""
        if index is None and len(kwargs) == 0:
            raise ValueError("Specify index or some parameter to select for.")
        if index is not None:
            return self.datasets[index]
        candidates = []
        candidates_props = {}
        props_compare = set()  # save names of fields we want to compare
        for k, v in kwargs.items():
            candidates_props[k] = []
        for i, (j, dm) in enumerate(self.metadata.items()):
            assert int(i) == int(j)
            is_candidate = True
            for k, v in kwargs.items():
                if k not in dm:
                    is_candidate = False
                    continue
                if isinstance(v, int) or isinstance(v, float):
                    candidates_props[k].append(dm[k])
                    print(candidates_props[k])
                    props_compare.add(k)
                elif v != dm[k]:
                    is_candidate = False
            if is_candidate:
                candidates.append(i)
            else:  # unroll changes
                for p, lst in candidates_props.items():
                    if len(lst) > len(candidates):
                        lst.pop()
        # find candidate closest to request
        idxlist = []
        for k in props_compare:
            print("Ccc", candidates_props[k])
            idx = np.argmin(np.abs(np.array(candidates_props[k]) - kwargs[k]))
            idxlist.append(idx)
        print("idxlist", idxlist)
        if len(set(idxlist)) != 1:
            raise ValueError("Ambiguous selection request")
        index = candidates[idxlist[0]]
        # TODO: reintroduce tolerance check
        return self.get_dataset(index=index)

    def _metadatacache(self, overwrite=False):
        fp = return_cachefile_path(os.path.join(self.hash, "data.json"))
        if os.path.exists(fp) and not overwrite:
            return None  # read config from file
        return None

    @property
    def metadata(self):
        if self._metadata is not None:
            return self._metadata
        fp = return_cachefile_path(os.path.join(self.hash, "data.json"))
        if os.path.exists(fp):
            self._metadata = json.load(open(fp, "r"))
            return self._metadata
        return None

    @metadata.setter
    def metadata(self, dct):
        self._metadata = dct
        fp = return_cachefile_path(os.path.join(self.hash, "data.json"))
        if not os.path.exists(fp):
            json.dump(dct, open(fp, "w"))


class DirectoryCatalog(object):
    """A catalog consisting of interface instances contained in a directory."""

    def __init__(self, path):
        self.path = path


class HomogeneousSeries(DatasetSeries):
    """Series consisting of same-type data sets."""

    def __init__(self, path, **interface_kwargs):
        super().__init__()
        pass  # TODO


class ArepoSimulation(DatasetSeries):
    """A container for an arepo simulation."""

    def __init__(self, path, **interface_kwargs):
        self.path = path
        self.name = os.path.basename(path)
        p = Path(path)
        if not (p.exists()):
            raise ValueError("Specified path '%s' does not exist." % path)
        outpath = join(path, "output")
        gpaths = sorted([p for p in Path(outpath).glob("groups_*")])
        spaths = sorted([p for p in Path(outpath).glob("snapdir_*")])

        assert len(gpaths) == len(spaths)
        dscls = _determine_type(spaths[0])[1][0]
        super().__init__(spaths, datasetclass=dscls, catalog=gpaths, **interface_kwargs)

        # get redshifts
        # self.redshifts = np.array([ds.redshift for ds in self.datasets])

    @classmethod
    def validate_path(cls, path, *args, **kwargs):
        if not os.path.isdir(path):
            return False
        fns = os.listdir(path)
        if "output" in fns:
            opath = join(path, "output")
            folders = os.listdir(opath)
            folders = [f for f in folders if os.path.isdir(join(opath, f))]
            return any([f.startswith("snapdir") for f in folders])
        return False
