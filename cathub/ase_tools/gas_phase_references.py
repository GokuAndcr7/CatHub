import ase
from ase import Atoms
import ase.atoms
import ase.data
import numpy as np
import optparse
import pprint

from cathub.tools import extract_atoms


def molecules2symbols(molecules, add_hydrogen=True):
    """Take a list of molecules and return just a list of atomic
    symbols, possibly adding hydrogen
    """
    symbols = sorted(
        list(set(
            ase.symbols.string2symbols(''.join(
                map(
                    lambda _x:
                    ''.join(ase.symbols.string2symbols(_x)), molecules)
            ))
        )),
        key=lambda _y: ase.data.atomic_numbers[_y])

    if add_hydrogen and 'H' not in symbols:
        symbols.insert(0, 'H')

    return symbols


def construct_reference_system(formula,
                               candidates=None):
    """
    Construct appropriate gas phase references for specified formula,
    from a set of specified candidates.

    Parameters:

    formula: str
      chemical formula of adsorbate
    candidates: list of str
      chemical formulas of requested gas phase reference

    Returns:

    list of reference formulas, list of prefactors

    """

    sorted_candidates = [
        'H2',
        'H2O',
        'N2',
        'NH3',
        'CH4',
        'CO2',
        'CO',
        'H2S',
        #    'HCl',
        'O2',
        'F2']

    preffered_references = {
        'O': ['H2O', 'O2'],
        'C': ['CH4', 'CO2', 'CO'],
        'N': ['N2', 'NH3'],
        'S': ['H2S'],
        'H': ['H2'],
        'F': ['F2', 'HF']
    }

    if candidates is None:
        candidates = sorted_candidates

    if formula in candidates:
        return [formula], [1]

    atoms = Atoms(formula)
    all_symbols = list(atoms.symbols)
    symbols = list(set(all_symbols))
    references = []
    if 'H' in symbols:
        symbols.remove('H')
        symbols += ['H']
    residual_symbols = list(symbols.copy())
    prefactors = []
    counts_tmp = {}

    remove = []
    add = []

    i = 0
    while len(residual_symbols) > 0 and i < 10:
        residual_symbols += add
        for r in remove:
            try:
                residual_symbols.remove(r)
            except:
                pass
        remove = []
        add = []
        for symbol in residual_symbols:
            if symbol in remove:
                continue
            if not symbol in counts_tmp:
                counts_tmp[symbol] = 0
            symbol_candidates = [c for c in candidates if symbol in Atoms(c).symbols
                                 and not c in references]
            ref_list = preffered_references.get(symbol, [])
            symbol_candidates = [c for c in candidates if symbol in Atoms(c).symbols
                                 and not c in references
                                 and not c in ref_list]
            ref_list += symbol_candidates
            ref_list = [r for r in ref_list if r in candidates]
            if len(ref_list) == 0:
                raise UserWarning(
                    "No gas phase reference found for {symbol}."
                    "\nInclude additional folders with"
                    " 'cathub organize -d foldername/'\n"
                    "    All elements: {symbols}\n"
                    "    Supplied references: {candidates}\n"
                    "    Prefered references: {pref}\n".format(
                        symbol=symbol,
                        symbols=symbols,
                        candidates=candidates,
                        pref=[preffered_references.get(s, '') for s in symbols]))
            for ref in ref_list:
                ref_atoms = list(Atoms(ref).symbols)
                count_ref = ref_atoms.count(symbol)
                count = all_symbols.count(symbol)
                prefactor = (count - counts_tmp[symbol]) / count_ref
                if prefactor == 0:
                    remove += [symbol]
                    break

                for a in set(ref_atoms):
                    if not a in counts_tmp:
                        counts_tmp[a] = 0
                    count_ref = ref_atoms.count(a)
                    counts_tmp[a] += prefactor * count_ref
                references += [ref]
                prefactors += [prefactor]
                residual = set(
                    [atom for atom in ref_atoms if not atom == symbol])
                remove += [symbol]

                for r in residual:
                    if not r in residual_symbols or r in remove:
                        add += [r]

                break
        i += 1
    if not len(residual_symbols) == 0:
        references = None
        prefactors = None

    return references, prefactors


def get_atomic_stoichiometry(references):
    """Given a list of references (tuples of (symbol, molecule))
    return stoichiometry matrix that connects atomic symbols
    to its molecular references.
    """
    n = len(references)
    stoichiometry = np.ndarray((n, n), float)
    stoichiometry[:] = 0.
    key_index = {}
    for i, (key, species) in enumerate(references):
        # in case species uses a suffix like _gas
        species = species.split('_')[0]
        key_index[key] = i

    for i, (key, species) in enumerate(references):
        composition = ase.symbols.string2symbols(species)
        for j, symbol in enumerate(composition):
            stoichiometry[i, key_index[symbol]] += 1
    istoichiometry = np.linalg.inv(stoichiometry)

    return istoichiometry.tolist()


def get_stoichiometry_factors(adsorbates, references):
    """Take a list of adsorabtes and a corresponding reference
    system and return a list of dictionaries encoding the
    stoichiometry factors converting between adsorbates and
    reference molecules.
    """
    stoichiometry = get_atomic_stoichiometry(references)
    stoichiometry_factors = {}
    for adsorbate in adsorbates:
        for symbol in ase.symbols.string2symbols(adsorbate):
            symbol_index = list(
                map(lambda _x: _x[0], references)).index(symbol)

            for (factor, (ref_symbol, ref_molecule)) in zip(
                    stoichiometry[symbol_index], references):
                stoichiometry_factors.setdefault(
                    adsorbate,
                    {})[ref_molecule] = stoichiometry_factors.setdefault(
                    adsorbate,
                    {}).get(
                    ref_molecule,
                    0) + factor

        nonzero_factors = {}
        for key, value in stoichiometry_factors[adsorbate].items():
            if not np.isclose(value, 0.):
                nonzero_factors[key] = value
        stoichiometry_factors[adsorbate] = nonzero_factors

    return stoichiometry_factors


if __name__ == '__main__':

    # store previously create test results
    test_results = [
        {'adsorbates': ['SNOCHO', 'SCl', 'H2O', 'CH4'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O'),
                        ('S', 'H2S'),
                        ('Cl', 'HCl')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, -0.0, -0.0, -0.0, -0.0],
                           [-1.5, -0.0, 1.0, -0.0, -0.0, -0.0],
                           [-1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
                           [-1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                           [-0.5, 0.0, 0.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {'CH4': {'CH4': 1.0},
                                   'H2O': {'H2O': 1.0},
                                   'SCl': {'H2': -1.5, 'H2S': 1.0, 'HCl': 1.0},
                                   'SNOCHO': {'CH4': 1.0,
                                              'H2': -6.0,
                                              'H2O': 2.0,
                                              'H2S': 1.0,
                                              'NH3': 1.0}},
         'symbols': ['H', 'C', 'N', 'O', 'S', 'Cl']},
        {'adsorbates': ['NOCHO'],
         'references': [('H', 'H2'), ('C', 'CH4'), ('N', 'NH3'), ('O', 'H2O')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, -0.0, -0.0],
                           [-1.5, -0.0, 1.0, -0.0],
                           [-1.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {'NOCHO': {'CH4': 1.0,
                                             'H2': -5.0,
                                             'H2O': 2.0,
                                             'NH3': 1.0}},
         'symbols': ['H', 'C', 'N', 'O']},
        {'adsorbates': ['CO', 'OCHO'],
         'references': [('H', 'H2'), ('C', 'CH4'), ('O', 'H2O')],
         'stoichiometry': [[0.5, 0.0, 0.0], [-2.0, 1.0, -0.0], [-1.0, 0.0, 1.0]],
         'stoichiometry_factors': {'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
                                   'OCHO': {'CH4': 1.0, 'H2': -3.5, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'O']},
        {'adsorbates': ['CO', 'H', 'CHO'],
         'references': [('H', 'H2'), ('C', 'CH4'), ('O', 'H2O')],
         'stoichiometry': [[0.5, 0.0, 0.0], [-2.0, 1.0, -0.0], [-1.0, 0.0, 1.0]],
         'stoichiometry_factors': {'CHO': {'CH4': 1.0, 'H2': -2.5, 'H2O': 1.0},
                                   'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
                                   'H': {'H2': 0.5}},
         'symbols': ['H', 'C', 'O']},
        {'adsorbates': ['NH', 'CO', 'O', 'SH', 'OH', 'CH3'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O'),
                        ('S', 'H2S')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0, 0.0],
                           [-1.0, 0.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {'CH3': {'CH4': 1.0, 'H2': -0.5},
                                   'CO': {'CH4': 1.0,
                                          'H2': -3.0,
                                          'H2O': 1.0},
                                   'NH': {'H2': -1.0,
                                          'NH3': 1.0},
                                   'O': {'H2': -1.0,
                                         'H2O': 1.0},
                                   'OH': {'H2': -0.5,
                                          'H2O': 1.0},
                                   'SH': {'H2': -0.5,
                                          'H2S': 1.0}},
         'symbols': ['H', 'C', 'N', 'O', 'S']},
        {'adsorbates': ['CO', 'O'],
         'references': [('H', 'H2'), ('C', 'CH4'), ('O', 'H2O')],
         'stoichiometry': [[0.5, 0.0, 0.0],
                           [-2.0, 1.0, 0.0],
                           [-1.0, 0.0, 1.0]],
         'stoichiometry_factors': {'CO':
                                   {'CH4': 1.0,
                                    'H2': -3.0,
                                    'H2O': 1.0},
                                   'O': {'H2': -1.0, 'H2O': 1.0}},
         'symbols': ['H', 'C', 'O']},
        {'adsorbates': ['CO', 'N'],
         'references': [
            ('H', 'H2'),
            ('C', 'CH4'),
            ('N', 'NH3'),
            ('O', 'H2O')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {
            'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
            'N': {'H2': -1.5, 'NH3': 1.0}},
         'symbols': ['H', 'C', 'N', 'O']},
        {'adsorbates': ['NO', 'O2', 'CO', 'CO2'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {'CO':
                                   {'CH4': 1.0,
                                    'H2': -3.0,
                                    'H2O': 1.0},
                                   'CO2':
                                   {'CH4': 1.0,
                                    'H2': -4.0,
                                    'H2O': 2.0},
                                   'NO':
                                   {'H2': -2.5,
                                    'H2O': 1.0,
                                    'NH3': 1.0},
                                   'O2': {'H2': -2.0, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'N', 'O']},
        {'adsorbates': ['NO', 'O2', 'CO'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'), ('N', 'NH3'), ('O', 'H2O')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {
            'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
            'NO': {'H2': -2.5, 'H2O': 1.0, 'NH3': 1.0},
            'O2': {'H2': -2.0, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'N', 'O']},
        {'adsorbates': ['NO', 'O2', 'CO', 'Cl'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O'),
                        ('Cl', 'HCl')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0, 0.0],
                           [-0.5, 0.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {
            'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
            'Cl': {'H2': -0.5, 'HCl': 1.0},
            'NO': {'H2': -2.5, 'H2O': 1.0, 'NH3': 1.0},
            'O2': {'H2': -2.0, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'N', 'O', 'Cl']},
        {'adsorbates': ['NO', 'O2', 'CO', 'Cl', 'HCl', 'Cl2'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O'),
                        ('Cl', 'HCl')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0, 0.0],
                           [-0.5, 0.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {
            'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
            'Cl': {'H2': -0.5, 'HCl': 1.0},
            'Cl2': {'H2': -1.0, 'HCl': 2.0},
            'HCl': {'HCl': 1.0},
            'NO': {'H2': -2.5, 'H2O': 1.0, 'NH3': 1.0},
            'O2': {'H2': -2.0, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'N', 'O', 'Cl']},
        {'adsorbates': ['NO', 'O2', 'CO', 'Cl', 'HCl', 'CH4'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O'),
                        ('Cl', 'HCl')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0, 0.0],
                           [-0.5, 0.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {
            'CH4': {'CH4': 1.0},
            'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
            'Cl': {'H2': -0.5, 'HCl': 1.0},
            'HCl': {'HCl': 1.0},
            'NO': {'H2': -2.5, 'H2O': 1.0, 'NH3': 1.0},
            'O2': {'H2': -2.0, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'N', 'O', 'Cl']},
        {'adsorbates':
         ['NO', 'O2', 'CO', 'CO2', 'Cl', 'HCl', 'CH4', 'H2O'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O'),
                        ('Cl', 'HCl')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0, 0.0],
                           [-0.5, 0.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {
             'CH4': {'CH4': 1.0},
             'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
             'CO2': {'CH4': 1.0, 'H2': -4.0, 'H2O': 2.0},
             'Cl': {'H2': -0.5, 'HCl': 1.0},
             'H2O': {'H2O': 1.0},
             'HCl': {'HCl': 1.0},
             'NO': {'H2': -2.5, 'H2O': 1.0, 'NH3': 1.0},
             'O2': {'H2': -2.0, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'N', 'O', 'Cl']},
        {'adsorbates':
         ['H3', 'NO', 'O2', 'CO', 'CO2',
                      'Cl', 'HCl', 'CH4', 'H2O'],
         'references': [('H', 'H2'),
                        ('C', 'CH4'),
                        ('N', 'NH3'),
                        ('O', 'H2O'),
                        ('Cl', 'HCl')],
         'stoichiometry': [[0.5, 0.0, 0.0, 0.0, 0.0],
                           [-2.0, 1.0, 0.0, 0.0, 0.0],
                           [-1.5, 0.0, 1.0, 0.0, 0.0],
                           [-1.0, 0.0, 0.0, 1.0, 0.0],
                           [-0.5, 0.0, 0.0, 0.0, 1.0]],
         'stoichiometry_factors': {
             'CH4': {'CH4': 1.0},
             'CO': {'CH4': 1.0, 'H2': -3.0, 'H2O': 1.0},
             'CO2': {'CH4': 1.0, 'H2': -4.0, 'H2O': 2.0},
             'Cl': {'H2': -0.5, 'HCl': 1.0},
             'H2O': {'H2O': 1.0},
             'H3': {'H2': 1.5},
             'HCl': {'HCl': 1.0},
             'NO': {'H2': -2.5, 'H2O': 1.0, 'NH3': 1.0},
             'O2': {'H2': -2.0, 'H2O': 2.0}},
         'symbols': ['H', 'C', 'N', 'O', 'Cl']}]

    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', dest='verbose',
                      action='store_true', default=False)
    parser.add_option('-e', '--extra-verbose',
                      dest='extra_verbose', action='store_true', default=False)
    parser.add_option('-n', '--no-test', dest='test',
                      action='store_false', default=True)
    options, args = parser.parse_args()
    verbose = options.verbose
    extra_verbose = options.extra_verbose

    examples = [
        ['SNOCHO', 'SCl', 'H2O', 'CH4'],
        ['NOCHO'],
        ['CO', 'OCHO'],
        ['CO', 'H', 'CHO'],
        ['NH', 'CO', 'O', 'SH', 'OH', 'CH3'],
        # (['CO'], ['CO'], False), Won't work
        ['CO', 'O'],
        ['CO', 'N'],
        ['NO', 'O2', 'CO', 'CO2'],
        ['NO', 'O2', 'CO'],
        ['NO', 'O2', 'CO', 'Cl'],
        ['NO', 'O2', 'CO', 'Cl', 'HCl', 'Cl2'],
        ['NO', 'O2', 'CO', 'Cl', 'HCl', 'CH4'],
        ['NO', 'O2', 'CO', 'CO2', 'Cl', 'HCl', 'CH4', 'H2O'],
        ['H3', 'NO', 'O2', 'CO', 'CO2', 'Cl', 'HCl', 'CH4', 'H2O'],
    ]

    results = []
    for adsorbates in examples:
        if type(adsorbates) is tuple:
            adsorbates, candidates, add_hydrogen = adsorbates
        else:
            candidates = None
            add_hydrogen = True

        result = {}
        results.append(result)

        if verbose:
            print(
                "\n\n\n\n\n--------------------------------------------------")
            print("ADSORBATES {adsorbates}".format(**locals()))
        result['adsorbates'] = adsorbates

        symbols = molecules2symbols(adsorbates, add_hydrogen=add_hydrogen)
        if verbose:
            print("SYMBOlS {symbols}".format(**locals()))
        result['symbols'] = symbols

        references = construct_reference_system(
            symbols=symbols,
            candidates=candidates,
        )
        if verbose:
            print("REFERENCES {references}".format(**locals()))
        result['references'] = references

        stoichiometry = get_atomic_stoichiometry(references)
        if verbose:
            print("STOICHIOMETRY MATRIX")
            pprint.pprint(stoichiometry)
        result['stoichiometry'] = stoichiometry

        stoichiometry_factors = get_stoichiometry_factors(
            adsorbates, references)
        if verbose:
            print("STOICHIOMETRY FACTORS")
            pprint.pprint(stoichiometry_factors)
        result['stoichiometry_factors'] = stoichiometry_factors

    if extra_verbose:
        print('\n\n\n\n\n\n')
        pprint.pprint(results)

    if options.test:
        assert results == test_results, \
            '\n\n---\n' \
            + str(pprint.pformat(results))  \
            + "\n---------------------------------------------------\n" \
            + str(pprint.pformat(test_results))
