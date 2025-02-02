#!/usr/bin/env python

import subprocess
import sys
import os
import collections

import cathub.organize

print(os.path.abspath(__file__))
path = os.path.abspath(os.path.join(os.path.dirname(__file__)))


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

# def test_debugging():
    #raise UserWarning(sys.path)


def test_file_organization():

    subprocess.call(
        ('python {path}/make_test_slabs.py'.format(path=path)).split())
    subprocess.call(
        ('cathub organize {path}/unorganized --adsorbates O,H2 --max-density-slab 0.06'.format(path=path)).split())


def test_file_organization_module():
    options = Struct(**{
        'adsorbates': ['O', 'H2'],
        'file_extensions': 'traj',
        'foldername': '{path}/unorganized'.format(path=path),
        'verbose': True,
        'include_pattern': '.',
        'dft_code': '',
        'structure': '',
        'xc_functional': '',
        'exclude_pattern': '%%$^#$',
        'facet_name': '111',
        'max_density_gas': 0.002,
        'max_density_slab': 0.06,
        'exclude_reference': '',
        'max_energy': 10,
        'keep_all_energies': True,
        'keep_all_slabs': True,
        'reorganization_tol': 1,
        'interactive': False,
        'out_folder': None,
        'gas_dir': '',
        'use_cache': False,
        'energy_corrections': {},
        'skip_parameters': '',
        'skip_constraints': '',

    })

    subprocess.call(
        ('python {path}/make_test_slabs.py'.format(path=path)).split())
    cathub.organize.main(options)


def test_file_organization_module_non_keep():
    options = Struct(**{
        'adsorbates': ['O', 'H2'],
        'file_extensions': 'traj',
        'foldername': '{path}/unorganized'.format(path=path),
        'verbose': True,
        'dft_code': '',
        'structure': '',
        'xc_functional': '',
        'include_pattern': '.',
        'exclude_pattern': '%%$^#$',
        'facet_name': '111',
        'max_density_gas': 0.002,
        'max_density_slab': 0.06,
        'exclude_reference': '',
        'max_energy': 10,
        'keep_all_energies': False,
        'keep_all_slabs': False,
        'reorganization_tol': 1,
        'interactive': False,
        'out_folder': None,
        'gas_dir': '',
        'use_cache': False,
        'energy_corrections': {},
        'skip_parameters': '',
        'skip_constraints': '',

    })

    subprocess.call(
        ('python {path}/make_test_slabs.py'.format(path=path)).split())
    cathub.organize.main(options)


def test_file_organization_module_collect_only():
    options = Struct(**{
        'adsorbates': ['O', 'H2'],
        'foldername': '{path}/unorganized'.format(path=path),
        'file_extensions': 'traj',
        'verbose': True,
        'dft_code': '',
        'structure': '',
        'xc_functional': '',
        'include_pattern': '.',
        'exclude_pattern': '%%$^#$',
        'facet_name': '111',
        'max_density_gas': 0.002,
        'max_density_slab': 0.06,
        'exclude_reference': '',
        'max_energy': 10,
        'keep_all_energies': False,
        'keep_all_slabs': False,
        'reorganization_tol': 1,
        'interactive': False,
        'out_folder': None,
        'gas_dir': '',
        'use_cache': False,
        'energy_corrections': {}

    })

    subprocess.call(
        ('python {path}/make_test_slabs.py'.format(path=path)).split())
    cathub.organize.collect_structures(options.foldername, options)


if __name__ == '__main__':
    test_file_organization()
    test_file_organization_module()
