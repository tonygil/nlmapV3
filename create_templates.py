"""
Create template Excel files for NL Taxonomy Mapper V3
"""
import pandas as pd

# Template 1: Semantic Carriers List
print("Creating semantic_carriers_list_TEMPLATE.xlsx...")

semantic_data = {
    'URL': [
        'https://example.com/help/banking/statements',
        'https://example.com/help/invoicing/create',
        'https://example.com/help/vat/filing',
        'https://example.com/help/reports/balance-sheet',
        'https://example.com/help/getting-started/setup'
    ],
    'Title': [
        'Bank Statements Guide',
        'Creating Invoices',
        'VAT Filing Instructions',
        'Balance Sheet Reports',
        'Getting Started with Setup'
    ],
    'Meta Description': [
        'Learn how to import and process bank statements',
        'Step-by-step guide to create invoices',
        'How to file VAT returns correctly',
        'Generate balance sheet reports',
        'Initial setup instructions'
    ],
    'Word Count': [450, 320, 580, 290, 410],
    'Keywords Extracted': [6, 5, 6, 4, 5],
    'Keywords Limit': [6, 6, 6, 6, 6],
    'Headings Count': [8, 6, 9, 5, 7],
    'Keyword 1': ['bankafschriften', 'facturatie', 'btw', 'rapportage', 'starten'],
    'Keyword 2': ['bankrekening', 'factuur maken', 'belasting', 'balans', 'setup'],
    'Keyword 3': ['transacties', 'klantgegevens', 'aangifte', 'financieel', 'installatie'],
    'Keyword 4': ['importeren', 'bedragen', 'periode', 'overzicht', 'configuratie'],
    'Keyword 5': ['verwerking', 'verzenden', 'indienen', 'export', 'gebruikers'],
    'Keyword 6': ['banken', 'creditnota', 'fiscaal', 'analyse', 'rechten'],
    'Keyword 7': [None, None, None, None, None],
    'Keyword 8': [None, None, None, None, None],
    'Keyword 9': [None, None, None, None, None],
    'Keyword 10': [None, None, None, None, None]
}

semantic_df = pd.DataFrame(semantic_data)
semantic_df.to_excel('semantic_carriers_list_TEMPLATE.xlsx', index=False)
print(f"[OK] Created with {len(semantic_df)} example rows")
print(f"  Columns: {', '.join(semantic_df.columns)}")

# Template 2: Taxonomy File
print("\nCreating NL_Taxonomy_V2_TEMPLATE.xlsx...")

taxonomy_data = {
    'Product': [None, None, None, None, None],
    'Productfamily': [None, None, None, None, None],
    'Domain': ['Welkom', 'General', 'Boekhouden', 'Boekhouden', 'Boekhouden'],
    'Segment': [
        'Educatie en service',
        'Starten met',
        'Bankzaken',
        'Facturatie',
        'BTW'
    ],
    'Topic 1': [
        'Wolters Kluwer account',
        'Starten met',
        'Bankafschriften',
        'Verkoopfacturen',
        'BTW-aangifte'
    ],
    'Topic 2': [
        'Consultancy & Services',
        'Overstapservice',
        'Bankboekingsinstructies',
        'Creditnota',
        'BTW-tarieven'
    ],
    'Topic 3': [
        'Opleidingsaanbod',
        'Navigatie',
        'Bankbetalingen',
        'Facturatieproces',
        'BTW-schema'
    ],
    'Topic 4': [
        'Het support portaal',
        'Wizard',
        'Bankkoppeling',
        'Factuurnummering',
        'BTW-verlegging'
    ],
    'Topic 5': [None, None, 'Bankrekeningbeheer', 'Factuursjablonen', None],
    'Topic 6': [None, None, None, 'Factuurgoedkeuring', None],
    'Topic 7': [None, None, None, None, None]
}

taxonomy_df = pd.DataFrame(taxonomy_data)
taxonomy_df.to_excel('NL_Taxonomy_V2_TEMPLATE.xlsx', index=False)
print(f"[OK] Created with {len(taxonomy_df)} example rows")
print(f"  Columns: {', '.join(taxonomy_df.columns)}")

print("\n" + "="*60)
print("Templates created successfully!")
print("="*60)
print("\nNext steps:")
print("1. Open the template files in Excel")
print("2. Replace example data with your actual data")
print("3. Save as: semantic_carriers_list.xlsx")
print("4. Save as: NL Taxonomy V2.xlsx")
print("5. Run the matcher application")
print("\nNotes:")
print("- Keywords 7-10 can be left empty if not needed")
print("- Topics can have 1-7 columns (adjust as needed)")
print("- Empty cells (None/NaN) are handled automatically")
print("- Product and Productfamily can be left empty")
