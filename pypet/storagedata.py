__author__ = 'robert'

import os

from pypet import pypetconstants
from pypet.parameter import Result
import pypet.compat as compat
import pypet.utils.ptcompat as ptcompat
import pypet.pypetconstants as pypetconstants
from pypet.naturalnaming import NNLeafNode

def check_hdf5_init(storage_data):
    file_created = False
    item_created = False
    filename = '__tmp__.hdf5'
    try:
        with ptcompat.open_file(filename, mode='a') as file:
            file_created = True
            factory_dict = {pypetconstants.TABLE: ptcompat.create_table,
                            pypetconstants.CARRAY: ptcompat.create_carray,
                            pypetconstants.EARRAY: ptcompat.create_earray,
                            pypetconstants.VLARRAY: ptcompat.create_vlarray}
            factory = factory_dict[storage_data._type]
            kwargs = storage_data._kwargs
            factory(file, where='/', name='__test__', **kwargs)
        item_created = True
    finally:
        if file_created:
            os.remove(filename)
    return item_created

class StorageData(object):
    def __init__(self, item_type=None, **kwargs):
        self._traj = None
        self._path_to_data = None
        self._item_name = None
        self._item = None
        self.f_set_init_args(item_type, **kwargs)

    def f_set_init_args(self, item_type=None, **kwargs):
        self._type = item_type
        self._kwargs = kwargs
        if item_type is None:
            self._guess_type(kwargs)

    def _guess_type(self, kwargs):
        if 'description' in kwargs or 'first_row' in kwargs:
            self._type = pypetconstants.TABLE
        else:
            self._type = pypetconstants.CARRAY

    def _set_dependencies(self, trajectory, full_name, data_name):
        self._traj = trajectory
        self._path_to_data = full_name
        self._item_name = data_name

    @property
    def v_type(self):
        return self._type

    def f_free_item(self):
        self._item = None

    @property
    def v_item(self):
        if not self._traj.v_storage_service.is_open:
            self.f_free_item()
        else:
            self._request_data()
        return self._item

    @property
    def v_uses_store(self):
        return self._item is not None

    def _request_data(self):
        service = self._traj.v_storage_service
        if not service.is_open:
            self.f_free_item()
            raise AttributeError('The storage service is not open, please open it '
                                 'with a `StorageDataResult` via the `f_open_storage`.')
        if self._item is None or not self._item._v_isopen:
            self._item = service.store(pypetconstants.STORAGE_DATA, self)

    def __getattr__(self, item):
        self._request_data()
        return getattr(self._item, item)

    def __getitem__(self, item):
        self._request_data()
        return self._item.__getitem__(item)

    def __iter__(self):
        self._request_data()
        return self._item.__iter__()

    def __setitem__(self, key, value):
        self._request_data()
        return self._item.__setitem__(key, value)

    def __del__(self):
        self.f_free_item()

    def __dir__(self):
        result = dir(type(self)) + compat.listkeys(self.__dict__)
        if self.v_item is not None:
            result = result + dir(self._item)
        return result


class KnowsTrajectory(NNLeafNode):
    KNOWS_TRAJECTORY = True


class StorageContextManager(object):
    def __init__(self, storage_result):
        self._storage_result = storage_result

    def __enter__(self):
        self._storage_result.f_open_store()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._storage_result.f_close_store()

    def f_flush_store(self):
        self._storage_result.f_flush_store()


class StorageDataResult(Result, KnowsTrajectory):
    def __init__(self, full_name, trajectory, *args, **kwargs):
        self._traj = trajectory
        super(StorageDataResult, self).__init__(full_name, *args, **kwargs)

    def _supports(self, data):
        if isinstance(data, StorageData):
            return True
        else:
            return super(StorageDataResult, self)._supports(data)

    def f_set_single(self, name, item):
        try:
            item._set_dependencies(self._traj, self.v_full_name, name)
        except AttributeError:
            pass
        super(StorageDataResult, self).f_set_single(name, item)

    def f_close_store(self):
        service = self._traj.v_storage_service
        if not service.is_open:
            raise RuntimeError('The storage service is not open, '
                               'please open via `f_open_storage`.')
        service.store(pypetconstants.CLOSE_FILE, None)
        if service.multiproc_safe:
            service.keep_locked = False
            service.release_lock()

    def f_open_store(self):
        service = self._traj.v_storage_service
        if service.is_open:
            raise RuntimeError('Your service is already open, there is no need to re-open it.')
        if service.multiproc_safe:
            service.keep_locked = True
            service.acquire_lock()
        service.store(pypetconstants.OPEN_FILE, None,
                      trajectory_name=self._traj.v_name)

    def f_context(self):
        return StorageContextManager(self)

    def f_flush_store(self):
        service = self._traj.v_storage_service
        if not service.is_open:
            raise RuntimeError('The storage service is not open, '
                               'please open via `f_open_storage`.')
        service.store(pypetconstants.FLUSH, None)

    def _load(self, load_dict):
        for name in load_dict:
            item = load_dict[name]
            try:
                item._set_dependencies(self._traj, self.v_full_name, name)
            except AttributeError:
                pass
            super(StorageDataResult, self)._load(load_dict)

