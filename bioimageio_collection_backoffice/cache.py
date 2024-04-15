import collections.abc
from functools import wraps
from typing import (
    Callable,
    NamedTuple,
    Optional,
    OrderedDict,
    Sized,
    Tuple,
    TypeVar,
)

from typing_extensions import TypeVarTuple, Unpack

Ks = TypeVarTuple("Ks")
V = TypeVar("V")


class CacheInfo(NamedTuple):
    hits: int
    misses: int
    maxsize: int
    currsize: int


class UpdatetableLRU(collections.abc.Mapping[Tuple[Unpack[Ks]], V]):
    "LRU Cache that allows to pop and update cache entries."

    def __init__(self, maxsize: int = 128):
        super().__init__()
        self._cache: OrderedDict[Tuple[Unpack[Ks]], V] = collections.OrderedDict()
        self.maxsize = maxsize
        self._hits = 0
        self._misses = 0

    def __call__(self, func: Callable[[Unpack[Ks]], V]):
        @wraps(func)
        def wrapper(*args: Unpack[Ks]):
            if args in self._cache:
                self._cache.move_to_end(args)
                return self._cache[args]

            result = func(*args)
            self._cache[args] = result
            self._pop_for_size()
            return result

        return wrapper

    def __len__(self) -> int:
        return len(self._cache)

    def _pop_for_size(self):
        if len(self) > self.maxsize:
            _ = self._cache.popitem(last=False)

    @property
    def cache_info(self):
        return CacheInfo(self._hits, self._misses, self.maxsize, len(self))

    def update(
        self,
        key: Tuple[Unpack[Ks]],
        value: V,
        only_if_cached: bool = True,
        keep_order: bool = False,
    ):
        """update cache (also counts as 'recently used', unless `keep_order is True`)"""
        if only_if_cached and key not in self._cache:
            return

        self._cache[key] = value
        if not keep_order:
            self._cache.move_to_end(key)

        self._pop_for_size()

    def pop(self, key: Tuple[Unpack[Ks]]):
        _ = self._cache.pop(key, None)


V_Sized = TypeVar("V_Sized", bound=Optional[Sized])


class SizedValueLRU(UpdatetableLRU[Unpack[Ks], V_Sized]):
    """`UpdatetableLRU` with a limit on the sum of cache entry lengths,
    not the number of cache entries"""

    def __len__(self):
        return sum((1 if v is None else len(v) for v in self._cache.values()))

    def _pop_for_size(self):
        size = len(self)
        while size > self.maxsize:
            _, v = self._cache.popitem(last=False)
            size -= 1 if v is None else len(v)
