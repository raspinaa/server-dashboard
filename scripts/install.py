#!/usr/bin/env python3
"""Compatibility entry point: application installation is offline only."""
from offline_install import supported, existing
if __name__ == '__main__':
    import runpy
    runpy.run_module('offline_install', run_name='__main__')
