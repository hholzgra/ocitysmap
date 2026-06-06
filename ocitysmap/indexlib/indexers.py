# -*- coding: utf-8 -*-

from ocitysmap.indexlib.StreetIndex import StreetIndex
from ocitysmap.indexlib.HealthIndex import HealthIndex
from ocitysmap.indexlib.NotesIndex import NotesIndex
from ocitysmap.indexlib.TreeIndex import TreeIndex

_INDEXERS = [
    StreetIndex,
    HealthIndex,
    NotesIndex,
    TreeIndex,
    # do not include special PoiIndex or generic GeneralIndex here!
    ]

def get_indexer_class_by_name(name):
    """Retrieves an indexer class, by name."""
    for indexer in _INDEXERS:
        if indexer.name == name:
            return indexer
    raise LookupError('The requested indexer %s was not found!' % name)

def get_indexers():
    """Returns the list of available indexers' names."""
    return _INDEXERS
