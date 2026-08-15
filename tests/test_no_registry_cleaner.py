"""Safety and policy compliance test: ensure zero registry cleaning or snake-oil features exist."""

from crapcleaner.registry import get_all_categories


def test_zero_registry_cleaners_in_categories():
    """Assert no category claims to clean, optimize, defragment, or modify the Windows Registry."""
    categories = get_all_categories()
    forbidden_terms = [
        "registry",
        "regedit",
        "defrag",
        "hkey_",
        "registry cleaner",
        "registry fix",
        "registry optimizer",
    ]

    for cat in categories:
        name_lower = cat.name.lower()
        desc_lower = cat.description.lower()
        id_lower = cat.id.lower()

        for term in forbidden_terms:
            assert (
                term not in name_lower
            ), f"Forbidden term '{term}' found in category name: {cat.name}"
            assert term not in id_lower, f"Forbidden term '{term}' found in category id: {cat.id}"
            # Ensure description doesn't promise registry cleaning
            if "registry" in desc_lower:
                assert (
                    "never" in desc_lower
                    or "no " in desc_lower
                    or "not" in desc_lower
                    or "excludes" in desc_lower
                )


def test_no_registry_writing_modules():
    """Verify that winreg is never imported for write/delete operations in cleaners."""
    import importlib
    import pkgutil
    import crapcleaner.cleaners

    for _, modname, _ in pkgutil.iter_modules(crapcleaner.cleaners.__path__):
        mod = importlib.import_module(f"crapcleaner.cleaners.{modname}")
        # Cleaners should never have winreg write functions
        for attr in ["DeleteKey", "DeleteValue", "SetValue", "SetValueEx"]:
            assert not hasattr(
                mod, attr
            ), f"Cleaner module {modname} contains forbidden winreg attribute: {attr}"
