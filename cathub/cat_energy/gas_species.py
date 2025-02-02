"""
Module for computing energetics of gaseous species.

This module provides classes and methods to calculate and return the energetics of gaseous species
using data from the ASE database and other sources, including corrections for thermodynamic properties
and external effects.

Classes:
--------
GasAnalysis : Inherits from EnergeticAnalysis and performs specific computations for gaseous species.
"""

import json
import numpy as np
import pandas as pd
from ase.db import connect
from ase.thermochemistry import IdealGasThermo
from tabulate import tabulate

from .io import NUM_DECIMAL_PLACES, write_columns
from .conversion import formula_to_chemical_symbols, CM2EV, get_rhe_contribution
from .core import EnergeticAnalysis

class GasAnalysis(EnergeticAnalysis):
    """
    Perform energetic analysis for gaseous state species.

    This class inherits from EnergeticAnalysis and provides methods to compute
    the energetics of gaseous species, including corrections for thermodynamic
    properties and external effects.

    Methods:
    --------
    write_gas_energies(df_out)
        Compute and return energetics of gaseous species and store the results in a DataFrame.
    """

    def __init__(self, parent_instance):
        self.__dict__.update(parent_instance.__dict__)

    def write_gas_energies(self, df_out):
        """
        Compute and return energetics of gaseous species.

        This method calculates the energetics of gaseous species using various
        corrections and stores the results in a provided DataFrame.

        Parameters:
        -----------
        df_out : pandas.DataFrame
            DataFrame to store the computed energies.

        Returns:
        --------
        pandas.DataFrame
            DataFrame containing the computed energetics of the gaseous species.
        """
        db = connect(str(self.db_filepath))
        gas_atoms_rows = list(db.select(state='gas'))

        surface, site, species, raw_energy, elec_energy_calc = [], [], [], [], []
        dft_corr, helm_offset, zpe, enthalpy, entropy = [], [], [], [], []
        rhe_corr, formation_energy, energy_vector, xyz = [], [], [], []
        frequencies, references = [], []

        temp = self.system_parameters['temp']
        u_rhe = self.system_parameters['u_rhe']

        # Load vibrational data
        with open(self.gas_jsondata_filepath, encoding='utf8') as f:
            gas_vibration_data = json.load(f)

        vibrational_energies = {}
        species_list = [species_data['species']
                        for species_data in gas_vibration_data]
        for species_data in gas_vibration_data:
            gas_species = species_data['species']
            vibrational_energies[gas_species] = []
            for vibration in species_data['frequencies']:
                vibrational_energies[gas_species].append(vibration * CM2EV)

        reference_gas_energies = {}
        for row in gas_atoms_rows:
            if row.formula in self.dft_corrections_gases:
                reference_gas_energies[row.formula] = (
                                    row.energy + self.dft_corrections_gases[row.formula])
            else:
                reference_gas_energies[row.formula] = row.energy

        # build dataframe data for dummy gases
        dummy_gas_energy = 0.0
        for dummy_gas in self.dummy_gases:
            surface.append('None')
            site.append('gas')
            species.append(dummy_gas)
            xyz.append([])
            raw_energy.append(0.0)
            elec_energy_calc.append(0.0)
            dft_corr.append(0.0)
            helm_offset.append(0.0)
            zpe.append(0.0)
            enthalpy.append(0.0)
            entropy.append(0.0)
            rhe_corr.append(0.0)
            formation_energy.append(0.0)
            energy_vector.append([0.0, 0.0, 0.0, 0.0, 0.0])
            frequencies.append([])
            references.append('')

        # build dataframe data for gaseous species
        for row in gas_atoms_rows:
            species_name = row.formula
            if species_name == 'H2' and 'H2_ref' in species_list:
                species_names = ['H2', 'H2_ref']
            else:
                species_names = [species_name]
            for species_name in species_names:
                surface.append('None')
                site.append('gas')
                species.append(species_name)

                chemical_symbols_dict = formula_to_chemical_symbols(
                                                species_name.replace('_ref', ''))

                # xCO + (x-z+y/2)H2 --> CxHyOz + (x-z)H2O
                if 'C' in chemical_symbols_dict:
                    x = chemical_symbols_dict['C']
                else:
                    x = 0
                if 'H' in chemical_symbols_dict:
                    y = chemical_symbols_dict['H']
                else:
                    y = 0
                if 'O' in chemical_symbols_dict:
                    z = chemical_symbols_dict['O']
                else:
                    z = 0
                xyz.append([x, y, z])
                raw_energy.append(row.energy)

                # CO2 Reduction Reaction
                if set(self.reference_gases) == set(['CO2', 'H2_ref', 'H2O']):
                    elec_energy_calc.append(
                        row.energy + (2 * x - z) * reference_gas_energies['H2O']
                        - x * reference_gas_energies['CO2']
                        - (2 * x - z + y / 2) * reference_gas_energies['H2'])
                # CO Reduction Reaction
                elif set(self.reference_gases) == set(['CO', 'H2_ref', 'H2O']):
                    elec_energy_calc.append(
                        row.energy + (x - z) * reference_gas_energies['H2O']
                        - x * reference_gas_energies['CO']
                        - (x - z + y / 2) * reference_gas_energies['H2'])

                dft_corr.append(self.dft_corrections_gases[species_name]
                                if species_name in self.dft_corrections_gases else 0.0)
                helm_offset.append(self.beef_dft_helmholtz_offset[species_name]
                            if species_name in self.beef_dft_helmholtz_offset else 0.0)

                if species_name in species_list:
                    species_index = species_list.index(species_name)
                    thermo = IdealGasThermo(
                        vib_energies=vibrational_energies[species_name],
                        geometry=gas_vibration_data[species_index]['geometry'],
                        atoms=row.toatoms(),
                        symmetrynumber=gas_vibration_data[species_index]['symmetry'],
                        spin=gas_vibration_data[species_index]['spin'])
                    # zero point energy correction
                    zpe.append(thermo.get_ZPE_correction())
                    # enthalpic temperature correction
                    enthalpy.append(thermo.get_enthalpy(temp, verbose=False))
                    non_temp_entropy = thermo.get_entropy(
                        temp, gas_vibration_data[species_index]['fugacity'],
                        verbose=False)
                    # entropy contribution
                    entropy.append(- temp * non_temp_entropy)
                else:
                    zpe.append(0.0)
                    enthalpy.append(0.0)
                    entropy.append(0.0)

                rhe_energy_contribution = get_rhe_contribution(u_rhe, species_name,
                                                            self.reference_gases)
                rhe_corr.append(rhe_energy_contribution)

                # compute energy vector
                term1 = elec_energy_calc[-1] + dft_corr[-1]
                term2 = enthalpy[-1] + entropy[-1]
                term3 = rhe_corr[-1]
                species_key = species_name + '_g'
                if species_key in self.external_effects:
                    term4 = np.poly1d(self.external_effects[species_key])(self.system_parameters['u_she'])
                else:
                    term4 = 0.0
                term4 += helm_offset[-1]
                mu = term1 + term2 + term3 + term4
                energy_vector.append([term1, term2, term3, term4, mu])

                # formation energy
                formation_energy.append(term1 + term4)

                if species_name in species_list:
                    frequencies.append(gas_vibration_data[species_list.index(
                                                    species_name)]['frequencies'])
                    references.append(gas_vibration_data[species_list.index(
                                                        species_name)]['reference'])
                else:
                    frequencies.append([])
                    references.append('')

        reference_mu = {}
        for species_name in self.reference_gases:
            species_index = species.index(species_name)
            reference_mu[species_name] = energy_vector[species_index][-1]

        for species_index, species_name in enumerate(species):
            if species_name in self.dummy_gases or species_name in self.reference_gases:
                G = 0.0
            else:
                [x, y, z] = xyz[species_index]
                # CO2 Reduction Reaction
                if set(self.reference_gases) == set(['CO2', 'H2_ref', 'H2O']):
                    G = (energy_vector[species_index][-1]
                        + (2 * x - z) * reference_mu['H2O']
                        - x * reference_mu['CO2']
                        - (2 * x - z + y / 2) * reference_mu['H2_ref'])
                # CO Reduction Reaction
                elif set(self.reference_gases) == set(['CO', 'H2_ref', 'H2O']):
                    G = (energy_vector[species_index][-1]
                        + (x - z) * reference_mu['H2O']
                        - x * reference_mu['CO']
                        - (x - z + y / 2) * reference_mu['H2_ref'])
            energy_vector[species_index].append(G)

        df = pd.DataFrame(list(zip(surface, site, species, raw_energy,
                                elec_energy_calc, dft_corr, zpe, enthalpy,
                                entropy, rhe_corr, formation_energy,
                                energy_vector, frequencies, references)),
                        columns=write_columns)
        df_out = df_out.append(df, ignore_index=True, sort=False)

        if self.verbose:
            gas_phase_header = 'Gas Phase Free Energy Correction:'
            print(gas_phase_header)
            print('-' * len(gas_phase_header))

            table = []
            table_headers = ["Species", "Term1 (eV)", "Term2 (eV)", "Term3 (eV)",
                            "Term4 (eV)", "µ (eV)", "∆G (eV)", "∆G at U_RHE=0 (eV)"
                            ]
            for index, species_name in enumerate(df['species_name']):
                sub_table = []
                delg_at_zero_u_rhe = (df["energy_vector"][index][5]
                                    - df["energy_vector"][index][2])
                sub_table.extend(
                    [species_name,
                    f'{df["energy_vector"][index][0]:.{NUM_DECIMAL_PLACES}f}',
                    f'{df["energy_vector"][index][1]:.{NUM_DECIMAL_PLACES}f}',
                    f'{df["energy_vector"][index][2]:.{NUM_DECIMAL_PLACES}f}',
                    f'{df["energy_vector"][index][3]:.{NUM_DECIMAL_PLACES}f}',
                    f'{df["energy_vector"][index][4]:.{NUM_DECIMAL_PLACES}f}',
                    f'{df["energy_vector"][index][5]:.{NUM_DECIMAL_PLACES}f}',
                    f'{delg_at_zero_u_rhe:.{NUM_DECIMAL_PLACES}f}'])
                table.append(sub_table)
            if self.latex:
                print(tabulate(table, headers=table_headers, tablefmt='latex',
                            colalign=("right", ) * len(table_headers),
                            disable_numparse=True))
            else:
                print(tabulate(table, headers=table_headers, tablefmt='psql',
                            colalign=("right", ) * len(table_headers),
                            disable_numparse=True))
            print('\n')
        return df_out
