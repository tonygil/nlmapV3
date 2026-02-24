#!/usr/bin/env python3
"""
generate_country_guides.py
Generates country-specific TAXONOMY_TOOLS_GUIDE_{CC}.html files from the
base TAXONOMY_TOOLS_GUIDE.html (which is the BE version).

Run:  python generate_country_guides.py
Output: TAXONOMY_TOOLS_GUIDE_BE.html, TAXONOMY_TOOLS_GUIDE_NL.html, TAXONOMY_TOOLS_GUIDE_SE.html
"""

import os
import re

BASE = os.path.join(os.path.dirname(__file__), 'TAXONOMY_TOOLS_GUIDE.html')
OUT  = os.path.dirname(__file__)

# ─────────────────────────────────────────────────────────────────────────────
# Country configuration
# ─────────────────────────────────────────────────────────────────────────────

COUNTRIES = {

    # ── Belgium ───────────────────────────────────────────────────────────────
    'BE': {
        'name':        'Belgium',
        'lang':        'Dutch (NL / FR)',
        'code':        'BE',
        'cover_meta':  'Belgium (BE)',
        'file_match':  'taxonomy_match_BE_*.xlsx',
        'file_gap':    'TAXONOMY_GAP_ANALYSIS_REPORT_BE*.xlsx',
        'file_patch':  'synonym_patch_BE_2026-02-19.json',
        'syns_path':   'countries/BE/synonyms.json',
        'syns_dir':    'countries/BE/',
        'ex_match':    'taxomony_match_BE_19thFeb_BE.xlsx',

        # Intro paragraph topic examples
        'topics_intro': (
            '<em>BTW aangifte</em>, <em>Jaarrekening</em>, '
            '<em>CODA bestanden</em>, <em>Peppol E-invoicing</em>'
        ),
        # Language-gap example
        'kw_example':  '"aangifte"',
        'cat_example': '"BTW aangifte"',
        'kw_score':    '62%',
        'syn_phrase':  '<em>"aangifte"</em> as a synonym for <em>BTW aangifte</em>',

        # Real Results section
        'results_h2':  'Real Results: Belgium',
        'results_intro': (
            'The BE taxonomy was launched with minimal synonyms. '
            'The progress below shows how quickly the match rate can move '
            'once the right tools are applied:'
        ),
        'results_bars': '''\
  <div class="progress-row">
    <div class="progress-label">18 Feb · Baseline</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill bar-24">24%</div></div>
    <div class="progress-note">Almost no synonyms</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">18 Feb · Product mapping fixes</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill bar-26">26%</div></div>
    <div class="progress-note">Configuration corrected</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">19 Feb · System fix applied</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill bar-61">61%</div></div>
    <div class="progress-note">+35pp · no new synonyms needed</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">Target · synonym sessions</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill bar-80">80%</div></div>
    <div class="progress-note">~40 approved synonyms needed</div>
  </div>''',

        # Approve / reject list items
        'approve_items': [
            'A shorter form of the category name (<em>&ldquo;btw aangifte&rdquo;</em> for <em>BTW aangifte</em>)',
            'A longer phrase clearly meaning the same thing (<em>&ldquo;jaarrekening opmaken&rdquo;</em>)',
            'A product-specific prefix + topic (<em>&ldquo;adsolut fiscaal dossier&rdquo;</em>)',
            'A consistent abbreviation (<em>&ldquo;coda import&rdquo;</em> for <em>CODA bestanden</em>)',
            '2+ sample URLs clearly about the suggested category',
        ],
        'reject_items': [
            'UI phrases (<em>&ldquo;artikel lees&rdquo;</em>, <em>&ldquo;raadpleeg dit artikel&rdquo;</em>, <em>&ldquo;klik hier&rdquo;</em>)',
            'Navigation phrases (<em>&ldquo;alle artikelen&rdquo;</em>, <em>&ldquo;een overzicht van&rdquo;</em>)',
            'Brand / footer text (<em>&ldquo;wolters kluwer&rdquo;</em>, <em>&ldquo;kluwer taa software&rdquo;</em>)',
            'Single generic words (<em>&ldquo;beheer&rdquo;</em>, <em>&ldquo;aanmaken&rdquo;</em>, <em>&ldquo;instelling&rdquo;</em>)',
            'Frequency 1&ndash;2 &middot; or URLs don&rsquo;t relate to the category',
        ],

        # paths in FAQ
        'faq_syns_dir': 'countries/BE/',
    },

    # ── Netherlands ───────────────────────────────────────────────────────────
    'NL': {
        'name':        'Netherlands',
        'lang':        'Dutch (NL)',
        'code':        'NL',
        'cover_meta':  'Netherlands (NL)',
        'file_match':  'taxonomy_match_NL_*.xlsx',
        'file_gap':    'TAXONOMY_GAP_ANALYSIS_REPORT_NL*.xlsx',
        'file_patch':  'synonym_patch_NL_2026-02-19.json',
        'syns_path':   'countries/NL/synonyms.json',
        'syns_dir':    'countries/NL/',
        'ex_match':    'taxonomy_match_NL_19thFeb_NL.xlsx',

        'topics_intro': (
            '<em>facturatie</em>, <em>bankzaken</em>, '
            '<em>jaarafsluiting</em>, <em>btw</em>'
        ),
        'kw_example':  '"factuur"',
        'cat_example': '"facturatie"',
        'kw_score':    '64%',
        'syn_phrase':  '<em>&ldquo;factuur&rdquo;</em> as a synonym for <em>facturatie</em>',

        'results_h2':  'Match Rate History: Netherlands',
        'results_intro': (
            'The NL taxonomy has been built up through systematic synonym iterations. '
            'Starting from minimal coverage, each synonym session delivered a clear step-up '
            'in the match rate, reaching the target and beyond:'
        ),
        'results_bars': '''\
  <div class="progress-row">
    <div class="progress-label">Starting point</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:30%;background:linear-gradient(90deg,#c62828,#e53935);height:100%;border-radius:4px 0 0 4px;display:flex;align-items:center;padding-left:8px;font-size:8pt;font-weight:700;color:#fff">30%</div></div>
    <div class="progress-note">Minimal synonyms</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">After round 1 synonyms</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:55%;background:linear-gradient(90deg,#e65100,#f57c00);height:100%;border-radius:4px 0 0 4px;display:flex;align-items:center;padding-left:8px;font-size:8pt;font-weight:700;color:#fff">55%</div></div>
    <div class="progress-note">Core topics mapped</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">After round 2 synonyms</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill bar-80">80%</div></div>
    <div class="progress-note">Target reached</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">Current state (mature)</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:94%;background:linear-gradient(90deg,#1b7f4a,#2e7d32);height:100%;border-radius:4px;display:flex;align-items:center;padding-left:8px;font-size:8pt;font-weight:700;color:#fff">94%</div></div>
    <div class="progress-note">Maintenance mode</div>
  </div>''',

        'approve_items': [
            'A shorter form of the category name (<em>&ldquo;factuur&rdquo;</em> for <em>facturatie</em>)',
            'A longer phrase clearly meaning the same thing (<em>&ldquo;jaarrekening afsluiten&rdquo;</em>)',
            'A product-specific prefix + topic (<em>&ldquo;e-boekhouden bankzaken&rdquo;</em>)',
            'A consistent abbreviation (<em>&ldquo;belastingaangifte&rdquo;</em> for <em>btw</em>)',
            '2+ sample URLs clearly about the suggested category',
        ],
        'reject_items': [
            'UI phrases (<em>&ldquo;artikel lees&rdquo;</em>, <em>&ldquo;raadpleeg dit artikel&rdquo;</em>, <em>&ldquo;klik hier&rdquo;</em>)',
            'Navigation phrases (<em>&ldquo;alle artikelen&rdquo;</em>, <em>&ldquo;een overzicht&rdquo;</em>)',
            'Brand / footer text (<em>&ldquo;wolters kluwer&rdquo;</em>, <em>&ldquo;exact software&rdquo;</em>)',
            'Single generic words (<em>&ldquo;beheer&rdquo;</em>, <em>&ldquo;aanmaken&rdquo;</em>, <em>&ldquo;instelling&rdquo;</em>)',
            'Frequency 1&ndash;2 &middot; or URLs don&rsquo;t relate to the category',
        ],

        'faq_syns_dir': 'countries/NL/',
    },

    # ── Sweden ─────────────────────────────────────────────────────────────────
    'SE': {
        'name':        'Sweden',
        'lang':        'Swedish (SV)',
        'code':        'SE',
        'cover_meta':  'Sweden (SE)',
        'file_match':  'taxonomy_match_SE_*.xlsx',
        'file_gap':    'TAXONOMY_GAP_ANALYSIS_REPORT_SE*.xlsx',
        'file_patch':  'synonym_patch_SE_2026-02-19.json',
        'syns_path':   'countries/SE/synonyms.json',
        'syns_dir':    'countries/SE/',
        'ex_match':    'taxonomy_match_SE_19thFeb_SE.xlsx',

        'topics_intro': (
            '<em>fakturering</em>, <em>bokf&ouml;ring</em>, '
            '<em>redovisning</em>, <em>moms</em>'
        ),
        'kw_example':  '"faktura"',
        'cat_example': '"fakturering"',
        'kw_score':    '61%',
        'syn_phrase':  '<em>&ldquo;faktura&rdquo;</em> as a synonym for <em>fakturering</em>',

        'results_h2':  'Starting Point: Sweden',
        'results_intro': (
            'The SE taxonomy is in the early stages of synonym development, '
            'with 7 topics and 14 synonyms currently registered. '
            'The path below shows the expected improvement journey as synonym sessions progress:'
        ),
        'results_bars': '''\
  <div class="progress-row">
    <div class="progress-label">Current baseline</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill bar-24">~25%</div></div>
    <div class="progress-note">7 topics, 14 synonyms</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">After round 1 synonyms</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:45%;background:linear-gradient(90deg,#e65100,#f57c00);height:100%;border-radius:4px 0 0 4px;display:flex;align-items:center;padding-left:8px;font-size:8pt;font-weight:700;color:#fff">~45%</div></div>
    <div class="progress-note">HIGH items approved</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">After round 2 synonyms</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:65%;background:linear-gradient(90deg,#e65100,#f57c00);height:100%;border-radius:4px 0 0 4px;display:flex;align-items:center;padding-left:8px;font-size:8pt;font-weight:700;color:#fff">~65%</div></div>
    <div class="progress-note">Ongoing synonym work</div>
  </div>
  <div class="progress-row">
    <div class="progress-label">Target &middot; 3&ndash;4 sessions</div>
    <div class="progress-bar-wrap"><div class="progress-bar-fill bar-80">80%</div></div>
    <div class="progress-note">~50 approved synonyms</div>
  </div>''',

        'approve_items': [
            'A shorter form of the category name (<em>&ldquo;faktura&rdquo;</em> for <em>fakturering</em>)',
            'A longer phrase clearly meaning the same thing (<em>&ldquo;bokf&ouml;ra transaktioner&rdquo;</em>)',
            'A product-specific prefix + topic (<em>&ldquo;fortnox bokf&ouml;ring&rdquo;</em>)',
            'A consistent abbreviation (<em>&ldquo;moms&rdquo;</em> for <em>merv&auml;rdeskatt</em>)',
            '2+ sample URLs clearly about the suggested category',
        ],
        'reject_items': [
            'UI phrases (<em>&ldquo;l&auml;s artikel&rdquo;</em>, <em>&ldquo;se den h&auml;r artikeln&rdquo;</em>, <em>&ldquo;klicka h&auml;r&rdquo;</em>)',
            'Navigation phrases (<em>&ldquo;alla artiklar&rdquo;</em>, <em>&ldquo;en &ouml;versikt av&rdquo;</em>)',
            'Brand / footer text (<em>&ldquo;wolters kluwer&rdquo;</em>, <em>&ldquo;visma&rdquo;</em>)',
            'Single generic words (<em>&ldquo;hantera&rdquo;</em>, <em>&ldquo;skapa&rdquo;</em>, <em>&ldquo;inst&auml;llning&rdquo;</em>)',
            'Frequency 1&ndash;2 &middot; or URLs don&rsquo;t relate to the category',
        ],

        'faq_syns_dir': 'countries/SE/',
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Transformation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_ar_list(items):
    """Build <ul class="ar-list"> HTML from a list of item strings."""
    lis = '\n'.join(f'        <li>{item}</li>' for item in items)
    return f'<ul class="ar-list">\n{lis}\n      </ul>'


def transform(html: str, cc: str) -> str:
    cfg = COUNTRIES[cc]

    # ── Title ─────────────────────────────────────────────────────────────────
    html = html.replace(
        '<title>Taxonomy Improvement Tools — User &amp; Stakeholder Guide</title>',
        f'<title>Taxonomy Improvement Tools — {cfg["name"]} ({cc}) · User &amp; Stakeholder Guide</title>',
    )

    # ── Cover brand name ──────────────────────────────────────────────────────
    html = html.replace(
        'Wolters Kluwer · Tax &amp; Accounting · Taxonomy Mapper V3',
        f'Wolters Kluwer · Tax &amp; Accounting · Taxonomy Mapper V3 &mdash; {cfg["name"]}',
    )

    # ── Cover meta: Applies to ────────────────────────────────────────────────
    html = html.replace(
        '<strong>Applies to</strong> BE · NL · GB · SE',
        f'<strong>Applies to</strong> {cfg["cover_meta"]}',
    )

    # ── Cover meta: Files ─────────────────────────────────────────────────────
    # Keep generic — same files for all countries

    # ── Intro paragraph — taxonomy examples ──────────────────────────────────
    html = html.replace(
        '<em>BTW aangifte</em>, <em>Jaarrekening</em>, '
        '<em>CODA bestanden</em>, <em>Peppol E-invoicing</em>',
        cfg['topics_intro'],
    )

    # ── Language-gap example ─────────────────────────────────────────────────
    html = html.replace(
        'If an article discusses <strong>&ldquo;aangifte&rdquo;</strong> but the category\n'
        '  is called <strong>&ldquo;BTW aangifte&rdquo;</strong>, the tool scores them at only 62%',
        f'If an article discusses <strong>{cfg["kw_example"]}</strong> but the category\n'
        f'  is called <strong>{cfg["cat_example"]}</strong>, the tool scores them at only {cfg["kw_score"]}',
    )
    # Also handle the inline callout version
    html = html.replace(
        'if the category\n  is called <strong>"BTW aangifte"</strong>',
        f'if the category\n  is called <strong>{cfg["cat_example"]}</strong>',
    )

    # Synonym phrase
    html = html.replace(
        'Adding <em>&ldquo;aangifte&rdquo;</em> as a synonym for\n'
        '  <em>BTW aangifte</em>',
        f'Adding {cfg["syn_phrase"]}',
    )

    # ── Real Results section ─────────────────────────────────────────────────
    # Replace from <h2>Real Results: Belgium</h2> up to (not including) <h2>Time Investment
    pattern = re.compile(
        r'<h2>Real Results: Belgium</h2>.*?<div style="margin:14px 0">.*?</div>\s*(?=<h2>Time Investment)',
        re.DOTALL,
    )
    new_results = (
        f'<h2>{cfg["results_h2"]}</h2>\n'
        f'<p>{cfg["results_intro"]}</p>\n\n'
        f'<div style="margin:14px 0">\n'
        f'{cfg["results_bars"]}\n'
        f'</div>\n\n'
    )
    html = pattern.sub(new_results, html)

    # ── Approve / reject examples ─────────────────────────────────────────────
    # Approve box list
    approve_pattern = re.compile(
        r'(<div class="ar-box ar-approve">.*?<ul class="ar-list">).*?(</ul>)',
        re.DOTALL,
    )
    approve_list_html = '\n'.join(
        f'        <li>{item}</li>' for item in cfg['approve_items']
    )
    html = approve_pattern.sub(
        rf'\g<1>\n{approve_list_html}\n      \g<2>',
        html,
    )

    # Reject box list
    reject_pattern = re.compile(
        r'(<div class="ar-box ar-reject">.*?<ul class="ar-list">).*?(</ul>)',
        re.DOTALL,
    )
    reject_list_html = '\n'.join(
        f'        <li>{item}</li>' for item in cfg['reject_items']
    )
    html = reject_pattern.sub(
        rf'\g<1>\n{reject_list_html}\n      \g<2>',
        html,
    )

    # ── File name examples ────────────────────────────────────────────────────
    # match output file example in callout
    html = html.replace('taxomony_match_BE_19thFeb_BE.xlsx', cfg['ex_match'])
    html = html.replace('taxonomy_match_BE_*.xlsx', cfg['file_match'])
    html = html.replace('synonym_patch_BE_2026-02-19.json', cfg['file_patch'])

    # ── synonyms.json paths ───────────────────────────────────────────────────
    html = html.replace('countries/BE/synonyms.json', cfg['syns_path'])
    html = html.replace('countries/BE/', cfg['syns_dir'])

    # ── Gap analysis report file ──────────────────────────────────────────────
    html = html.replace(
        'TAXONOMY_GAP_ANALYSIS_REPORT*.xlsx',
        cfg['file_gap'],
    )

    # ── Footer ────────────────────────────────────────────────────────────────
    html = html.replace(
        'Taxonomy Mapper V3.25 &nbsp;·&nbsp; Wolters Kluwer Tax &amp; Accounting &nbsp;·&nbsp; February 2026',
        f'Taxonomy Mapper V3.25 &nbsp;·&nbsp; Wolters Kluwer Tax &amp; Accounting &nbsp;·&nbsp; {cfg["name"]} ({cc}) &nbsp;·&nbsp; February 2026',
    )

    return html


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    with open(BASE, encoding='utf-8') as f:
        base_html = f.read()

    for cc in ('BE', 'NL', 'SE'):
        out_html = transform(base_html, cc)
        out_path = os.path.join(OUT, f'TAXONOMY_TOOLS_GUIDE_{cc}.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(out_html)
        size_kb = len(out_html) // 1024
        print(f'  Written: TAXONOMY_TOOLS_GUIDE_{cc}.html  ({size_kb} KB)')

    print('\nDone. Open each file in a browser to preview.')
    print('To save as PDF: Ctrl+P → Save as PDF → A4 → Background graphics.')


if __name__ == '__main__':
    main()
