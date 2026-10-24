import functools
import logging

from django.core.cache.backends.db import DatabaseCache
from django.db import DatabaseError

logger = logging.getLogger(__name__)


def _fail_soft(fallback):
    """Turn database errors into a cache miss/no-op instead of a 500."""
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except DatabaseError:
                # Usually the cache table is missing because `migrate` hasn't run
                logger.exception("Cache %s failed; continuing without the cache", method.__name__)
                return fallback(*args, **kwargs)
        return wrapper
    return decorator


class SafeDatabaseCache(DatabaseCache):
    """
    DatabaseCache that keeps the site up when the cache table is unavailable:
    reads behave like misses and writes are skipped.
    """

    get = _fail_soft(lambda key, default=None, version=None: default)(DatabaseCache.get)
    get_many = _fail_soft(lambda keys, version=None: {})(DatabaseCache.get_many)
    has_key = _fail_soft(lambda key, version=None: False)(DatabaseCache.has_key)
    set = _fail_soft(lambda *args, **kwargs: None)(DatabaseCache.set)
    add = _fail_soft(lambda *args, **kwargs: False)(DatabaseCache.add)
    touch = _fail_soft(lambda *args, **kwargs: False)(DatabaseCache.touch)
    delete = _fail_soft(lambda *args, **kwargs: False)(DatabaseCache.delete)
    delete_many = _fail_soft(lambda *args, **kwargs: None)(DatabaseCache.delete_many)
    clear = _fail_soft(lambda *args, **kwargs: None)(DatabaseCache.clear)

    @_fail_soft(lambda data, timeout=None, version=None: list(data))
    def set_many(self, data, timeout=None, version=None):
        return super().set_many(data, timeout, version)
