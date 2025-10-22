"""
resource_pairs.py

Identify pairs of resource management functions such as allocation/deallocation
and locking/unlocking. This information is used to retrogress local resources
when generating patches.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

@dataclass
class ResourcePair:
    """Represents a pair of resource management functions."""
    acquire: str
    release: str

class ResourcePairs:
    """
    Holds the mapping of resource acquisition functions to their corresponding
    release functions. Provides methods to detect missing releases in functions.
    """

    def __init__(self):
        # Hard-code some common resource pairs. These can be extended or loaded from config.
        self.pairs: List[ResourcePair] = [
            ResourcePair(acquire='malloc', release='free'),
            ResourcePair(acquire='calloc', release='free'),
            ResourcePair(acquire='realloc', release='free'),
            ResourcePair(acquire='new', release='delete'),
            ResourcePair(acquire='pthread_mutex_lock', release='pthread_mutex_unlock'),
            ResourcePair(acquire='spin_lock', release='spin_unlock'),
            ResourcePair(acquire='read_lock', release='read_unlock'),
        ]
        # Build reverse mapping for quick lookup
        self.acquire_to_release: Dict[str, str] = {pair.acquire: pair.release for pair in self.pairs}
        self.release_to_acquire: Dict[str, str] = {pair.release: pair.acquire for pair in self.pairs}

    def get_release(self, acquire_func: str) -> Optional[str]:
        """Return the corresponding release function, if any."""
        return self.acquire_to_release.get(acquire_func)

    def get_acquire(self, release_func: str) -> Optional[str]:
        """Return the corresponding acquire function, if any."""
        return self.release_to_acquire.get(release_func)

    def find_missing_releases(self, function_decl) -> List[Tuple[str, int]]:
        """
        Identify resource acquisitions that are not followed by their matching release within
        the same function.

        :param function_decl: FunctionDecl object.
        :return: List of tuples (acquire_function_name, line_number).
        """
        missing = []
        if not function_decl.body:
            return missing
        acquire_calls: List[Tuple[str, int]] = []
        release_calls: List[Tuple[str, int]] = []
        for node in function_decl.body.walk():
            if node.kind == 'CallExpr':
                callee = node.spelling
                line = node.location[1]
                if callee in self.acquire_to_release:
                    acquire_calls.append((callee, line))
                if callee in self.release_to_acquire:
                    release_calls.append((callee, line))
        # Check for each acquire if there is a release later
        for acquire, line in acquire_calls:
            release_func = self.get_release(acquire)
            # Find any release call after this line
            found = False
            for rel, rel_line in release_calls:
                if rel == release_func and rel_line > line:
                    found = True
                    break
            if not found:
                missing.append((acquire, line))
        return missing
