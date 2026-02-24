"""
Country Configuration Loader for Taxonomy Mapper V3
Handles loading and validation of country-specific settings
"""

import yaml
import json
import os
import sys
from typing import Dict, List, Optional
from pathlib import Path


def get_application_path() -> Path:
    """
    Get the application root path, handling both normal Python and PyInstaller exe.

    Search order for config.yaml:
    1. PyInstaller bundle (sys._MEIPASS) - for bundled data files
    2. Next to the exe (sys.executable.parent) - for external config
    3. Script directory - for normal Python execution

    Returns:
        Path to the application root directory
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        # First check if config exists in PyInstaller's bundled data
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            bundled_path = Path(meipass)
            if (bundled_path / 'config.yaml').exists():
                return bundled_path

        # Otherwise check next to the exe
        exe_dir = Path(sys.executable).parent
        if (exe_dir / 'config.yaml').exists():
            return exe_dir

        # Fallback to exe directory even if config not found (will error later with clear message)
        return exe_dir
    else:
        # Running as normal Python script
        return Path(__file__).parent


class CountryConfig:
    """Manages country-specific configuration and file paths."""

    def __init__(self, config_file: str = None):
        """
        Initialize configuration loader.

        Args:
            config_file: Path to YAML config file (default: config.yaml in app directory)
        """
        self.project_root = get_application_path()

        if config_file is None:
            self.config_file = self.project_root / 'config.yaml'
        else:
            self.config_file = Path(config_file)

        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load YAML configuration file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file '{self.config_file}' not found. "
                "Please ensure config.yaml exists in project root."
            )
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config: {e}")

    def _save_config(self) -> bool:
        """Save current configuration to YAML file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            print(f"Warning: Could not save config: {e}")
            return False

    def add_country(self, code: str, name: str, language: str,
                    threshold: int = 80, description: str = "") -> bool:
        """Add a new country entry to config.yaml."""
        code = code.upper()
        if code in self.config.get('countries', {}):
            raise ValueError(f"Country '{code}' already exists in configuration")
        entry = {
            'name': name, 'language': language, 'code': code, 'enabled': True,
            'files': {
                'semantic_carriers': 'semantic_carriers_list.xlsx',
                'taxonomy': 'taxonomy.xlsx',
                'synonyms': 'synonyms.json',
            },
            'settings': {'similarity_threshold': int(threshold)}
        }
        if description:
            entry['settings']['description'] = description
        if 'countries' not in self.config:
            self.config['countries'] = {}
        self.config['countries'][code] = entry
        return self._save_config()

    def save_last_used_taxonomy(self, country_code: str, taxonomy_path: str) -> bool:
        """
        Save the last used taxonomy file path for a country.

        Args:
            country_code: Two-letter country code (e.g., 'GB')
            taxonomy_path: Absolute path to the taxonomy file that was used

        Returns:
            True if saved successfully, False otherwise
        """
        if country_code not in self.config['countries']:
            return False

        # Verify the file exists before saving
        if not os.path.exists(taxonomy_path):
            return False

        # Initialize last_used_files section if not present
        if 'last_used_files' not in self.config:
            self.config['last_used_files'] = {}

        if country_code not in self.config['last_used_files']:
            self.config['last_used_files'][country_code] = {}

        # Save the taxonomy path
        self.config['last_used_files'][country_code]['taxonomy'] = taxonomy_path

        return self._save_config()

    def get_last_used_taxonomy(self, country_code: str) -> Optional[str]:
        """
        Get the last used taxonomy file path for a country.

        Args:
            country_code: Two-letter country code

        Returns:
            Path to last used taxonomy file, or None if not set or file doesn't exist
        """
        try:
            last_used = self.config.get('last_used_files', {})
            if country_code in last_used:
                taxonomy_path = last_used[country_code].get('taxonomy')
                if taxonomy_path and os.path.exists(taxonomy_path):
                    return taxonomy_path
        except Exception:
            pass
        return None

    def clear_last_used_taxonomy(self, country_code: str) -> bool:
        """Clear the last used taxonomy file for a country (revert to default)."""
        try:
            if 'last_used_files' in self.config:
                if country_code in self.config['last_used_files']:
                    if 'taxonomy' in self.config['last_used_files'][country_code]:
                        del self.config['last_used_files'][country_code]['taxonomy']
                        return self._save_config()
        except Exception:
            pass
        return False

    def get_available_countries(self) -> List[Dict[str, str]]:
        """
        Get list of available countries.

        Returns:
            List of dicts with 'code', 'name', 'language' keys
        """
        countries = []
        for code, details in self.config['countries'].items():
            if details.get('enabled', True):
                countries.append({
                    'code': code,
                    'name': details['name'],
                    'language': details['language']
                })
        return countries

    def get_default_country(self) -> str:
        """Get default country code."""
        return self.config.get('default_country', 'NL')

    def get_country_files(self, country_code: str) -> Dict[str, str]:
        """
        Get absolute file paths for a country.

        Args:
            country_code: Two-letter country code (e.g., 'NL')

        Returns:
            Dict with 'semantic_carriers', 'taxonomy', 'synonyms' paths

        Raises:
            ValueError: If country not found or files missing
        """
        if country_code not in self.config['countries']:
            raise ValueError(f"Country '{country_code}' not found in config")

        country = self.config['countries'][country_code]

        # Check for backward compatibility (NL legacy files in root)
        if (country_code == 'NL' and
            self.config['backward_compatibility']['check_root_for_legacy']):
            legacy = self.config['backward_compatibility']
            legacy_semantic = self.project_root / legacy['legacy_semantic_file']
            legacy_taxonomy = self.project_root / legacy['legacy_taxonomy_file']

            if legacy_semantic.exists() and legacy_taxonomy.exists():
                # Use legacy files from root directory
                return {
                    'semantic_carriers': str(legacy_semantic),
                    'taxonomy': str(legacy_taxonomy),
                    'synonyms': str(self.project_root / 'countries' / country_code /
                                  country['files']['synonyms'])
                }

        # Standard path: countries/{code}/
        country_dir = self.project_root / 'countries' / country_code

        # Build default paths
        result = {
            'semantic_carriers': str(country_dir / country['files']['semantic_carriers']),
            'taxonomy': str(country_dir / country['files']['taxonomy']),
            'synonyms': str(country_dir / country['files']['synonyms'])
        }

        # Check for last used taxonomy file (overrides default if exists)
        last_used_taxonomy = self.get_last_used_taxonomy(country_code)
        if last_used_taxonomy:
            result['taxonomy'] = last_used_taxonomy

        return result

    def load_synonyms(self, country_code: str) -> Dict[str, List[str]]:
        """
        Load synonyms from JSON file for a country.

        Args:
            country_code: Two-letter country code

        Returns:
            Dictionary of synonym mappings
        """
        files = self.get_country_files(country_code)
        synonyms_file = files['synonyms']

        # Fallback to empty dict if synonyms file doesn't exist
        if not os.path.exists(synonyms_file):
            print(f"Warning: Synonyms file not found for {country_code}, using empty dict")
            return {}

        try:
            with open(synonyms_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('synonyms', {})
        except json.JSONDecodeError as e:
            print(f"Warning: Error parsing synonyms JSON for {country_code}: {e}")
            return {}

    def load_product_synonyms(self, country_code: str) -> Dict[str, List[str]]:
        """
        Load product synonyms from synonyms.json for a country.

        Product synonyms allow alternative product names in semantic files to match
        canonical taxonomy product names. Stored under 'product_synonyms' key in
        synonyms.json, keyed by canonical taxonomy product name.

        Example:
            {"Adsolut boekhouding": ["Adsolut boekhouden", "Adsolut Accounting"]}

        Args:
            country_code: Two-letter country code

        Returns:
            Dict mapping canonical taxonomy product name -> list of aliases
        """
        files = self.get_country_files(country_code)
        synonyms_file = files['synonyms']

        if not os.path.exists(synonyms_file):
            return {}

        try:
            with open(synonyms_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('product_synonyms', {})
        except json.JSONDecodeError:
            return {}

    def get_country_settings(self, country_code: str) -> dict:
        """
        Get settings for a country (includes global + country-specific).

        Args:
            country_code: Two-letter country code

        Returns:
            Dict of settings
        """
        if country_code not in self.config['countries']:
            raise ValueError(f"Country '{country_code}' not found")

        # Start with global settings
        settings = self.config.get('global_settings', {}).copy()

        # Override with country-specific settings
        country_settings = self.config['countries'][country_code].get('settings', {})
        settings.update(country_settings)

        return settings

    def validate_country_files(self, country_code: str) -> tuple:
        """
        Validate that all required files exist for a country.

        Args:
            country_code: Two-letter country code

        Returns:
            (is_valid: bool, missing_files: List[str])
        """
        try:
            files = self.get_country_files(country_code)
            missing = []

            for file_type, file_path in files.items():
                # Synonyms file is optional
                if file_type == 'synonyms' and not os.path.exists(file_path):
                    continue

                if not os.path.exists(file_path):
                    missing.append(f"{file_type}: {file_path}")

            return (len(missing) == 0, missing)

        except Exception as e:
            return (False, [str(e)])
