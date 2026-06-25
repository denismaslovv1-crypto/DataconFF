from __future__ import annotations


GENERIC_MARKERS = ("*", "[*]", "R#", " R ", "Ar")


def generic_structure_reason(smiles: str | None, molfile: str | None = None) -> str | None:
    if smiles and "*" in smiles:
        return "wildcard_atom_in_smiles"
    if molfile:
        if "\nR " in molfile or " R   " in molfile:
            return "r_group_atom_in_molfile"
        if "\nA    " in molfile:
            return "atom_alias_in_molfile"
    return None


def is_generic_structure(smiles: str | None, molfile: str | None = None) -> bool:
    return generic_structure_reason(smiles, molfile) is not None
