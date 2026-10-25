import functools
import logging

from django.core.cache.backends.db import DatabaseCache
from django.core.cache.backends.locmem import LocMemCache
from django.db import DatabaseError

logger = logging.getLogger(__name__)


def _with_fallback(method):
    """On a database error, run the same operation against the in-memory fallback cache."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            result = method(self, *args, **kwargs)
        except DatabaseError:
            if not self._outage_logged:
                # Usually the cache table is missing because `migrate` hasn't run
                logger.exception("Database cache unavailable; using in-memory cache instead")
                self._outage_logged = True
            return getattr(self._fallback, method.__name__)(*args, **kwargs)
        if self._outage_logged:
            logger.warning("Database cache is available again")
            self._outage_logged = False  # log the next outage too
        return result
    return wrapper


class SafeDatabaseCache(DatabaseCache):
    """
    DatabaseCache that keeps the site up when the cache table is unavailable.

    Instead of raising (a 500 on every page that reads the cache), operations
    fall back to a per-process in-memory cache. That still caches OMDb
    responses within a running instance, so an outage doesn't turn every page
    view into dozens of API calls and burn through the daily OMDb quota.
    """

    def __init__(self, table, params):
        super().__init__(table, params)
        self._outage_logged = False
        self._fallback = LocMemCache('watchit-db-cache-fallback', {
            'TIMEOUT': params.get('TIMEOUT', 300),
            'OPTIONS': {'MAX_ENTRIES': params.get('OPTIONS', {}).get('MAX_ENTRIES', 300)},
        })

    get = _with_fallback(DatabaseCache.get)
    get_many = _with_fallback(DatabaseCache.get_many)
    has_key = _with_fallback(DatabaseCache.has_key)
    set = _with_fallback(DatabaseCache.set)
    set_many = _with_fallback(DatabaseCache.set_many)
    add = _with_fallback(DatabaseCache.add)
    touch = _with_fallback(DatabaseCache.touch)
    delete = _with_fallback(DatabaseCache.delete)
    delete_many = _with_fallback(DatabaseCache.delete_many)
    clear = _with_fallback(DatabaseCache.clear)
