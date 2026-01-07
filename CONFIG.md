# Configuration Settings for NL Taxonomy Mapper V2

## File Paths
# Modify these paths if your input files are in different locations

INPUT_SEMANTIC_FILE = 'semantic_carriers_list.xlsx'
INPUT_TAXONOMY_FILE = 'NL Taxonomy V2.xlsx'
OUTPUT_FILE = 'taxonomy_match.xlsx'

## Matching Settings

# Similarity threshold (0-100)
# Higher = stricter matching, Lower = more lenient
# Recommended: 75-85
SIMILARITY_THRESHOLD = 80

## Synonym Dictionary
# Add Dutch language variations and synonyms here
# Format: 'main_term': ['synonym1', 'synonym2', ...]

SYNONYMS = {
    'bankzaken': ['bank', 'banken', 'bankafschriften', 'bankrekeningen', 'bankenmodule'],
    'betalen': ['betaling', 'betalingen'],
    'incasseren': ['incasso'],
    'facturatie': ['facturen', 'factuur', 'facturering'],
    'jaarafsluiting': ['jaarrekening', 'jaarafsluiten'],
    'btw': ['belasting', 'belastingaangifte'],
    'relatiebeheer': ['klanten', 'leveranciers', 'debiteuren', 'crediteuren'],
    'grootboek': ['grootboekrekeningen'],
    'vaste activa': ['activa', 'activum'],
}

## Processing Options

# Enable deduplication (recommended: True)
# Prevents same URL-Topic combination appearing multiple times
ENABLE_DEDUPLICATION = True

# Progress update frequency (every N URLs)
PROGRESS_UPDATE_INTERVAL = 50

## Output Options

# Include similarity scores in output (for debugging)
INCLUDE_SIMILARITY_SCORES = False

# Sort output by URL (recommended: True)
SORT_OUTPUT_BY_URL = True
