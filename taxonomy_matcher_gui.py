"""
NL Taxonomy Mapper V3 - Beautiful GUI Application
Modern interface with multi-country support
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import os
import copy
import json
from datetime import datetime
from taxonomy_matcher import TaxonomyMatcher
from country_config import CountryConfig
import sys
import pandas as pd


# ==================== TOOLTIP HELPER CLASS ====================

class ToolTip:
    """Create a tooltip for a widget."""

    def __init__(self, widget, text=''):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        """Display tooltip."""
        if self.tooltip_window or not self.text:
            return

        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify='left',
            background='#ffffe0',
            foreground='#000000',
            relief='solid',
            borderwidth=1,
            font=('Segoe UI', 9),
            padx=8,
            pady=6
        )
        label.pack()

    def hide_tooltip(self, event=None):
        """Hide tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def update_text(self, new_text):
        """Update tooltip text."""
        self.text = new_text


# ==================== FILE VALIDATION FUNCTIONS ====================

def validate_semantic_file(file_path):
    """
    Validate semantic carriers file structure (headers only for performance).

    Returns:
        tuple: (is_valid: bool, issues: list, file_type: str)
            - is_valid: True if file has correct structure for semantic carriers
            - issues: List of validation error messages
            - file_type: "semantic", "taxonomy", "output", or "unknown"
    """
    issues = []
    file_type = "unknown"

    try:
        # Only read headers (nrows=0) for fast validation
        df = pd.read_excel(file_path, nrows=0)
        columns = df.columns.tolist()

        # Required columns for semantic carriers
        has_url = 'URL' in columns

        # Check for Keyword columns
        keyword_cols = [col for col in columns if col.startswith('Keyword ')]
        has_keywords = len(keyword_cols) > 0

        # Warning signs - looks like taxonomy or output file
        has_product = 'Product' in columns
        has_domain = 'Domain' in columns
        has_segment = 'Segment' in columns
        has_topic = any(col.startswith('Topic') for col in columns)

        # Determine file type
        if has_url and has_product and has_domain and has_segment and has_topic:
            # This is an OUTPUT file (has URL + taxonomy structure)
            file_type = "output"
            issues.append("This looks like an output/results file (has URL + Product/Domain/Segment/Topic columns)")
            issues.append("Use the original semantic carriers file instead, not the mapping output")
        elif has_product and has_domain and has_segment and has_topic:
            file_type = "taxonomy"
            issues.append("This looks like a taxonomy file (has Product/Domain/Segment/Topic columns)")
        elif has_url and has_keywords:
            file_type = "semantic"
        else:
            file_type = "unknown"

        # Validation checks
        if not has_url:
            issues.append("Missing required column: URL")

        if not has_keywords:
            issues.append("Missing Keyword columns (expected Keyword 1, Keyword 2, etc.)")

        # CRITICAL: Semantic files should NOT have Product/Domain/Segment/Topic columns
        if has_product or has_domain or has_segment:
            if file_type != "output":
                issues.append("Semantic carriers should NOT have Product/Domain/Segment columns")

        is_valid = has_url and has_keywords and file_type == "semantic"

        return (is_valid, issues, file_type)

    except FileNotFoundError:
        return (False, ["File not found"], "unknown")
    except Exception as e:
        return (False, [f"Unable to read file: {str(e)}"], "unknown")


def validate_taxonomy_file(file_path):
    """
    Validate taxonomy file structure (headers only for performance).

    Returns:
        tuple: (is_valid: bool, issues: list, file_type: str)
            - is_valid: True if file has correct structure for taxonomy
            - issues: List of validation error messages
            - file_type: "semantic", "taxonomy", "output", or "unknown"
    """
    issues = []
    file_type = "unknown"

    try:
        # Only read headers (nrows=0) for fast validation
        df = pd.read_excel(file_path, nrows=0)
        columns = df.columns.tolist()

        # Required columns for taxonomy
        has_product = 'Product' in columns
        has_domain = 'Domain' in columns
        has_segment = 'Segment' in columns

        # Check for Topic columns
        topic_cols = [col for col in columns if col.startswith('Topic')]
        has_topics = len(topic_cols) > 0

        # Warning signs - looks like semantic file
        has_url = 'URL' in columns
        has_keywords = any(col.startswith('Keyword ') for col in columns)

        # Determine file type
        if has_url and has_keywords:
            file_type = "semantic"
            issues.append("This looks like a semantic carriers file (has URL and Keyword columns)")
        elif has_url and has_product and has_domain and has_segment and has_topics:
            # This is an OUTPUT file (has URL + taxonomy structure)
            file_type = "output"
            issues.append("This looks like an output/results file (has URL + Product/Domain/Segment/Topic columns)")
            issues.append("Use the original taxonomy file instead, not the mapping output")
        elif has_product and has_domain and has_segment and has_topics:
            file_type = "taxonomy"
        else:
            file_type = "unknown"

        # Validation checks
        missing_cols = []
        if not has_product:
            missing_cols.append("Product")
        if not has_domain:
            missing_cols.append("Domain")
        if not has_segment:
            missing_cols.append("Segment")

        if missing_cols:
            issues.append(f"Missing required columns: {', '.join(missing_cols)}")

        if not has_topics:
            issues.append("No Topic columns detected (expected Topic 1, Topic 2, etc.)")

        # CRITICAL: Taxonomy files should NOT have a URL column
        if has_url and file_type != "semantic":
            issues.append("Taxonomy files should NOT have a URL column")

        is_valid = has_product and has_domain and has_segment and has_topics and file_type == "taxonomy" and not has_url

        return (is_valid, issues, file_type)

    except FileNotFoundError:
        return (False, ["File not found"], "unknown")
    except Exception as e:
        return (False, [f"Unable to read file: {str(e)}"], "unknown")


def detect_file_swap(semantic_path, taxonomy_path):
    """
    Detect if semantic and taxonomy files appear to be swapped.

    Args:
        semantic_path: Path to file in semantic carriers slot
        taxonomy_path: Path to file in taxonomy slot

    Returns:
        tuple: (is_swapped: bool, confidence: str)
            - is_swapped: True if files appear swapped
            - confidence: "high", "medium", or "none"
    """
    if not semantic_path or not taxonomy_path:
        return (False, "none")

    if not os.path.exists(semantic_path) or not os.path.exists(taxonomy_path):
        return (False, "none")

    _, _, semantic_type = validate_semantic_file(semantic_path)
    _, _, taxonomy_type = validate_taxonomy_file(taxonomy_path)

    # High confidence: both files are swapped
    if semantic_type == "taxonomy" and taxonomy_type == "semantic":
        return (True, "high")

    # Medium confidence: only one is wrong
    if semantic_type == "taxonomy" or taxonomy_type == "semantic":
        return (True, "medium")

    return (False, "none")


class TaxonomyMapperGUI:
    """Modern GUI application for NL Taxonomy Mapper."""
    
    def __init__(self, root):
        """Initialize the GUI application."""
        self.root = root
        self.root.title("NL Taxonomy Mapper V3")
        self.root.geometry("1000x850")  # Increased size for better fit
        self.root.resizable(True, True)
        
        # Modern color scheme
        self.colors = {
            'primary': '#2563eb',
            'primary_dark': '#1e40af',
            'secondary': '#10b981',
            'background': '#f8fafc',
            'card': '#ffffff',
            'text': '#1e293b',
            'text_light': '#64748b',
            'border': '#e2e8f0',
            'error': '#ef4444'
        }
        
        self.root.configure(bg=self.colors['background'])
        
        # Variables
        self.semantic_file = tk.StringVar()
        self.taxonomy_file = tk.StringVar()
        self.output_file = tk.StringVar(value='taxonomy_match.xlsx')
        self.threshold = tk.IntVar(value=80)
        self.is_processing = False

        # Validation UI components
        self.semantic_validation_label = None
        self.taxonomy_validation_label = None
        self.semantic_tooltip = None
        self.taxonomy_tooltip = None
        self.swap_warning_frame = None
        self.swap_button = None

        # Synonym editor state
        self.current_synonyms = {}  # Loaded synonym data
        self.original_synonyms = {}  # For revert functionality
        self.has_unsaved_changes = False
        self.current_synonym_file = None
        self.all_topics = []  # Full list for search/filter
        self.filtered_topics = []  # Currently displayed topics

        # Country configuration
        try:
            self.country_config = CountryConfig()
            self.available_countries = self.country_config.get_available_countries()
            default_country = self.country_config.get_default_country()
        except Exception as e:
            messagebox.showerror(
                "Configuration Error",
                f"Failed to load country configuration:\n{e}\n\n"
                "Please check config.yaml exists and is valid."
            )
            self.root.quit()
            return

        self.selected_country = tk.StringVar(value=default_country)

        # Create UI
        self.create_header()
        self.create_main_content()
        self.create_footer()

        self.center_window()
        
    def center_window(self):
        """Center window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def create_header(self):
        """Create header section."""
        header = tk.Frame(self.root, bg=self.colors['primary'], height=80)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="🌍 Sitecore Taxonomy Mapper V3",
            font=('Segoe UI', 24, 'bold'),
            bg=self.colors['primary'],
            fg='white'
        ).pack(side='left', padx=30, pady=20)

        tk.Label(
            header,
            text="V3.0 Multi-Country",
            font=('Segoe UI', 12),
            bg=self.colors['primary'],
            fg='white'
        ).pack(side='left', pady=20)
        
    def create_main_content(self):
        """Create main content area."""
        main = tk.Frame(self.root, bg=self.colors['background'])
        main.pack(fill='both', expand=True, padx=15, pady=10)
        
        # Style notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=self.colors['background'], borderwidth=0)
        style.configure('TNotebook.Tab', padding=[20, 10], font=('Segoe UI', 10))
        
        notebook = ttk.Notebook(main)
        notebook.pack(fill='both', expand=True)
        
        self.create_setup_tab(notebook)
        self.create_log_tab(notebook)
        self.create_synonym_editor_tab(notebook)
        self.create_reports_tab(notebook)
        self.create_about_tab(notebook)
        
    def create_setup_tab(self, notebook):
        """Create setup tab."""
        frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(frame, text='   Setup  ')
        
        # Input Files Card
        input_card = self.create_card(frame, " Input Files")
        input_card.pack(fill='x', padx=10, pady=10)

        # Country/Language Selector
        self.create_country_selector(input_card)

        self.create_file_row(
            input_card,
            "URL Keywords file:",
            self.semantic_file,
            "Select semantic_carriers_list.xlsx",
            file_type="semantic"
        )

        self.create_file_row(
            input_card,
            "Taxonomy File:",
            self.taxonomy_file,
            "Select NL Taxonomy V2.xlsx",
            file_type="taxonomy"
        )

        # Bind country change to auto-populate file paths
        self.selected_country.trace_add('write', self.on_country_changed)

        # Swap Warning UI (hidden by default)
        self.swap_warning_frame = tk.Frame(
            input_card,
            bg='#fef3c7',  # Light yellow background
            relief='solid',
            bd=1
        )
        # Pack it but we'll control visibility later

        warning_content = tk.Frame(self.swap_warning_frame, bg='#fef3c7')
        warning_content.pack(fill='x', padx=15, pady=10)

        tk.Label(
            warning_content,
            text="⚠ Files appear to be swapped!",
            font=('Segoe UI', 10, 'bold'),
            bg='#fef3c7',
            fg='#92400e'  # Dark yellow text
        ).pack(side='left', padx=(0, 15))

        self.swap_button = tk.Button(
            warning_content,
            text="Swap Files",
            command=self.swap_files_clicked,
            font=('Segoe UI', 9, 'bold'),
            bg='#f59e0b',  # Orange button
            fg='white',
            relief='flat',
            padx=20,
            pady=5,
            cursor='hand2'
        )
        self.swap_button.pack(side='left')

        # Hide swap warning initially
        self.swap_warning_frame.pack_forget()

        # Output Card
        output_card = self.create_card(frame, " Output Settings")
        output_card.pack(fill='x', padx=10, pady=10)
        
        self.create_file_row(
            output_card,
            "Output File:",
            self.output_file,
            "Save As",
            save=True
        )
        
        # Settings Card
        settings_card = self.create_card(frame, " Matching Settings")
        settings_card.pack(fill='x', padx=10, pady=10)
        
        # Threshold
        threshold_frame = tk.Frame(settings_card, bg=self.colors['card'])
        threshold_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(
            threshold_frame,
            text="Similarity Threshold:",
            font=('Segoe UI', 10),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(side='left')
        
        self.threshold_label = tk.Label(
            threshold_frame,
            text=f"{self.threshold.get()}%",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['primary']
        )
        self.threshold_label.pack(side='right')
        
        slider = tk.Scale(
            settings_card,
            from_=50,
            to=100,
            orient='horizontal',
            variable=self.threshold,
            command=self.update_threshold,
            bg=self.colors['card'],
            fg=self.colors['text'],
            highlightthickness=0,
            troughcolor=self.colors['border']
        )
        slider.pack(fill='x', padx=20, pady=(0, 10))
        
        tk.Label(
            settings_card,
            text=" Recommended: 75-85. Higher = stricter matching",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        ).pack(padx=20, pady=(0, 8))

        # Topic Consolidation Option
        # Output is always consolidated (one row per URL-Segment with Topic_1, Topic_2, etc.)
        tk.Label(
            settings_card,
            text="ℹ Output format: Consolidated (one row per URL-Segment with Topic_1, Topic_2, etc.)",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        ).pack(padx=20, pady=(5, 8))

        # Buttons and Progress Bar
        btn_frame = tk.Frame(frame, bg=self.colors['background'])
        btn_frame.pack(fill='x', pady=10, padx=10)

        self.run_btn = tk.Button(
            btn_frame,
            text="▶ Run Matching",
            command=self.run_matching,
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['secondary'],
            fg='white',
            relief='flat',
            padx=30,
            pady=12,
            cursor='hand2'
        )
        self.run_btn.pack(side='left', padx=5)

        reset_btn = tk.Button(
            btn_frame,
            text="↻ Reset",
            command=self.reset_form,
            font=('Segoe UI', 10),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=20,
            pady=12,
            cursor='hand2'
        )
        reset_btn.pack(side='left', padx=5)

        # Modern Progress Bar Section
        progress_container = tk.Frame(btn_frame, bg=self.colors['background'])
        progress_container.pack(side='left', fill='x', expand=True, padx=(20, 0))

        # Processing status label
        self.processing_status = tk.Label(
            progress_container,
            text="",
            font=('Segoe UI', 10),
            bg=self.colors['background'],
            fg=self.colors['primary']
        )
        self.processing_status.pack(side='top', anchor='w')

        # Style the progress bar with modern look
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'Modern.Horizontal.TProgressbar',
            troughcolor='#e2e8f0',
            background='#10b981',  # Green color
            bordercolor='#e2e8f0',
            lightcolor='#34d399',
            darkcolor='#059669',
            thickness=20
        )

        # Create beautiful progress bar
        self.progress = ttk.Progressbar(
            progress_container,
            mode='indeterminate',
            length=300,
            style='Modern.Horizontal.TProgressbar'
        )
        self.progress.pack(side='top', fill='x', pady=(5, 0))
        
    def create_log_tab(self, notebook):
        """Create log tab."""
        frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(frame, text='   Console  ')
        
        log_card = self.create_card(frame, " Processing Log")
        log_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(
            log_card,
            font=('Consolas', 9),
            bg='#1e293b',
            fg='#e2e8f0',
            insertbackground='white',
            relief='flat',
            padx=10,
            pady=10
        )
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Buttons
        btn_frame = tk.Frame(log_card, bg=self.colors['card'])
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(
            btn_frame,
            text=" Clear",
            command=self.clear_log,
            font=('Segoe UI', 9),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=15,
            pady=5
        ).pack(side='left', padx=5)
        
        tk.Button(
            btn_frame,
            text=" Copy",
            command=self.copy_log,
            font=('Segoe UI', 9),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=15,
            pady=5
        ).pack(side='left', padx=5)
        
    def create_reports_tab(self, notebook):
        """Create reports tab for analysis tools."""
        frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(frame, text='   Reports  ')

        # Main card for reports
        card = self.create_card(frame, " Analysis Reports")
        card.pack(fill='both', expand=True, padx=10, pady=10)

        content = tk.Frame(card, bg=self.colors['card'])
        content.pack(fill='both', expand=True, padx=30, pady=20)

        # Synonym Report Section
        section = tk.Frame(content, bg=self.colors['card'])
        section.pack(fill='x', pady=10, anchor='w')

        tk.Label(
            section,
            text="Proposed Synonyms Report",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(anchor='w')

        tk.Label(
            section,
            text="Compares semantic keywords with taxonomy topics to propose new synonym mappings.\n"
                 "Generates an Excel report with 4 sheets: All Synonyms, HIGH Priority, Summary, Unmapped Keywords.",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light'],
            justify='left'
        ).pack(anchor='w', pady=(5, 15))

        # Button row
        btn_row = tk.Frame(section, bg=self.colors['card'])
        btn_row.pack(anchor='w')

        self.synonym_report_btn = tk.Button(
            btn_row,
            text="Generate Synonym Report",
            command=self.generate_synonym_report,
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        self.synonym_report_btn.pack(side='left')

        # Status label
        self.report_status_label = tk.Label(
            btn_row,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.report_status_label.pack(side='left', padx=15)

        # Separator
        tk.Frame(content, bg=self.colors['border'], height=1).pack(fill='x', pady=20)

        # Info section
        info_frame = tk.Frame(content, bg=self.colors['card'])
        info_frame.pack(fill='x', anchor='w')

        tk.Label(
            info_frame,
            text="Requirements:",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(anchor='w')

        tk.Label(
            info_frame,
            text="- Select a Semantic Carriers file (URL Keywords) in Setup tab\n"
                 "- Select a Taxonomy file in Setup tab\n"
                 "- Click 'Generate Synonym Report' to analyze",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light'],
            justify='left'
        ).pack(anchor='w', pady=(5, 0))

    def create_about_tab(self, notebook):
        """Create about tab."""
        frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(frame, text='   About  ')
        
        card = self.create_card(frame, " About This Application")
        card.pack(fill='both', expand=True, padx=10, pady=10)
        
        content = tk.Frame(card, bg=self.colors['card'])
        content.pack(fill='both', expand=True, padx=30, pady=20)
        
        # Build country list string
        countries_list = ", ".join([c['code'] for c in self.available_countries])

        info = [
            ("Application:", "NL Taxonomy Mapper V3"),
            ("Version:", "3.0.0 Multi-Country"),
            ("Purpose:", "Match URLs to taxonomy topics using fuzzy matching"),
            ("", ""),
            ("Features:", "✓ Multi-country support\n✓ Fuzzy string matching\n✓ Language-specific synonyms\n✓ Auto deduplication\n✓ Dynamic topic detection"),
            ("", ""),
            ("Countries:", countries_list),
        ]
        
        for label, value in info:
            if not label:
                tk.Frame(content, bg=self.colors['card'], height=10).pack()
                continue
                
            row = tk.Frame(content, bg=self.colors['card'])
            row.pack(fill='x', pady=5, anchor='w')
            
            if label:
                tk.Label(
                    row,
                    text=label,
                    font=('Segoe UI', 10, 'bold'),
                    bg=self.colors['card'],
                    anchor='w'
                ).pack(side='left')
            
            tk.Label(
                row,
                text=value,
                font=('Segoe UI', 10),
                bg=self.colors['card'],
                fg=self.colors['text_light'],
                anchor='w',
                justify='left'
            ).pack(side='left', padx=10)
        
    def create_footer(self):
        """Create footer."""
        footer = tk.Frame(self.root, bg=self.colors['card'], height=40)
        footer.pack(fill='x', side='bottom')
        footer.pack_propagate(False)

        border = tk.Frame(footer, bg=self.colors['border'], height=1)
        border.pack(fill='x')

        self.status_label = tk.Label(
            footer,
            text="Ready",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.status_label.pack(side='left', padx=20)
        
    def create_card(self, parent, title):
        """Create a card container."""
        card = tk.Frame(parent, bg=self.colors['card'], relief='flat', bd=0)
        card.configure(highlightbackground=self.colors['border'], highlightthickness=1)
        
        tk.Label(
            card,
            text=title,
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=20, pady=(15, 10))
        
        return card
        
    def create_file_row(self, parent, label, variable, title, save=False, file_type=None):
        """Create a file input row with optional validation indicator."""
        row = tk.Frame(parent, bg=self.colors['card'])
        row.pack(fill='x', padx=20, pady=8)

        tk.Label(
            row,
            text=label,
            font=('Segoe UI', 10),
            bg=self.colors['card'],
            width=18,
            anchor='w'
        ).pack(side='left')

        entry = tk.Entry(
            row,
            textvariable=variable,
            font=('Segoe UI', 9),
            relief='solid',
            bd=1
        )
        entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        btn = tk.Button(
            row,
            text="Browse",
            command=lambda: self.browse_file(variable, title, save, file_type),
            font=('Segoe UI', 9),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=15,
            pady=5
        )
        btn.pack(side='right', padx=(0, 5))

        # Add validation indicator label (if file_type specified)
        if file_type:
            validation_label = tk.Label(
                row,
                text="",
                font=('Segoe UI', 14),
                bg=self.colors['card'],
                width=2
            )
            validation_label.pack(side='right')

            # Store reference and create tooltip
            tooltip = ToolTip(validation_label, "")

            if file_type == "semantic":
                self.semantic_validation_label = validation_label
                self.semantic_tooltip = tooltip
            elif file_type == "taxonomy":
                self.taxonomy_validation_label = validation_label
                self.taxonomy_tooltip = tooltip
        
    def browse_file(self, variable, title, save=False, file_type=None):
        """Browse for file and validate immediately if file_type specified."""
        if save:
            file = filedialog.asksaveasfilename(
                title=title,
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
        else:
            file = filedialog.askopenfilename(
                title=title,
                filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
            )

        if file:
            variable.set(file)

            # Validate immediately if file_type specified
            if file_type:
                self.validate_file_input(file_type)
                self.check_for_file_swap()

    def validate_file_input(self, file_type):
        """Validate a specific file input and update UI indicators."""
        if file_type == "semantic":
            file_path = self.semantic_file.get()
            if not file_path:
                return

            is_valid, issues, detected_type = validate_semantic_file(file_path)
            self.update_validation_indicator(
                self.semantic_validation_label,
                self.semantic_tooltip,
                is_valid,
                issues,
                detected_type,
                "semantic"
            )

        elif file_type == "taxonomy":
            file_path = self.taxonomy_file.get()
            if not file_path:
                return

            is_valid, issues, detected_type = validate_taxonomy_file(file_path)
            self.update_validation_indicator(
                self.taxonomy_validation_label,
                self.taxonomy_tooltip,
                is_valid,
                issues,
                detected_type,
                "taxonomy"
            )

    def update_validation_indicator(self, label, tooltip, is_valid, issues, detected_type, expected_type):
        """Update validation indicator label with icon, color, and tooltip."""
        if not label or not tooltip:
            return

        # Build tooltip message
        if is_valid:
            # Valid file
            label.config(text="✓", fg="#10b981")  # Green checkmark
            tooltip_text = f"✓ Valid {expected_type} file structure"
        elif detected_type == "output":
            # Output file used as input - clear error
            label.config(text="✗", fg="#ef4444")  # Red X
            tooltip_text = "✗ This is an OUTPUT file (mapping results)\n\n" + "\n".join(f"• {issue}" for issue in issues)
        elif detected_type != expected_type and detected_type != "unknown":
            # Wrong file type (swapped)
            label.config(text="⚠", fg="#f59e0b")  # Orange warning
            tooltip_text = f"⚠ This looks like a {detected_type} file, not {expected_type}\n\nIssues:\n" + "\n".join(f"• {issue}" for issue in issues)
        else:
            # Invalid file
            label.config(text="✗", fg="#ef4444")  # Red X
            tooltip_text = f"✗ Issues found:\n" + "\n".join(f"• {issue}" for issue in issues)

        tooltip.update_text(tooltip_text)

    def check_for_file_swap(self):
        """Check if files appear swapped and show/hide auto-fix option."""
        semantic_path = self.semantic_file.get()
        taxonomy_path = self.taxonomy_file.get()

        if not semantic_path or not taxonomy_path:
            self.hide_swap_warning()
            return

        is_swapped, confidence = detect_file_swap(semantic_path, taxonomy_path)

        if is_swapped:
            self.show_swap_warning()
        else:
            self.hide_swap_warning()

    def show_swap_warning(self):
        """Show file swap warning and fix button."""
        if self.swap_warning_frame:
            self.swap_warning_frame.pack(fill='x', padx=20, pady=(0, 10))

    def hide_swap_warning(self):
        """Hide file swap warning."""
        if self.swap_warning_frame:
            self.swap_warning_frame.pack_forget()

    def swap_files_clicked(self):
        """Handle swap files button click - swap the file paths."""
        # Swap the file paths
        semantic_temp = self.semantic_file.get()
        taxonomy_temp = self.taxonomy_file.get()

        self.semantic_file.set(taxonomy_temp)
        self.taxonomy_file.set(semantic_temp)

        # Re-validate both files
        self.validate_file_input("semantic")
        self.validate_file_input("taxonomy")
        self.check_for_file_swap()

        self.log("Files swapped successfully")

    def create_country_selector(self, parent):
        """Create country/language selection dropdown."""
        row = tk.Frame(parent, bg=self.colors['card'])
        row.pack(fill='x', padx=20, pady=12)

        tk.Label(
            row,
            text="Country/Language:",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card'],
            width=18,
            anchor='w'
        ).pack(side='left')

        # Country dropdown
        country_dropdown = ttk.Combobox(
            row,
            textvariable=self.selected_country,
            values=[c['code'] for c in self.available_countries],
            state='readonly',
            font=('Segoe UI', 10),
            width=15
        )
        country_dropdown.pack(side='left', padx=(0, 10))

        # Display full name as label
        self.country_label = tk.Label(
            row,
            text=self._get_country_display_name(self.selected_country.get()),
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.country_label.pack(side='left', fill='x', expand=True)

    def _get_country_display_name(self, code):
        """Get full display name for country code."""
        for c in self.available_countries:
            if c['code'] == code:
                return f"{c['name']} ({c['language']})"
        return code

    def on_country_changed(self, *args):
        """Handle country selection change - auto-populate file paths."""
        country_code = self.selected_country.get()

        # Update display label
        self.country_label.config(text=self._get_country_display_name(country_code))

        # Auto-populate file paths from config
        try:
            files = self.country_config.get_country_files(country_code)

            # Only update if fields are empty or contain default paths
            if not self.semantic_file.get() or 'semantic_carriers' in self.semantic_file.get():
                self.semantic_file.set(files['semantic_carriers'])

            if not self.taxonomy_file.get() or 'taxonomy' in self.taxonomy_file.get().lower():
                self.taxonomy_file.set(files['taxonomy'])

            # Update output filename with country code
            current_output = self.output_file.get()
            if current_output:
                # Remove old country code if present
                base = current_output.replace('.xlsx', '')
                for c in self.available_countries:
                    base = base.replace(f"_{c['code']}", "")
                # Add new country code
                self.output_file.set(f"{base}_{country_code}.xlsx")
            else:
                self.output_file.set(f'taxonomy_match_{country_code}.xlsx')

            self.log(f"Switched to {self._get_country_display_name(country_code)}")

        except Exception as e:
            self.log(f"Warning: Could not load files for {country_code}: {e}")

    def update_threshold(self, value):
        """Update threshold label."""
        self.threshold_label.config(text=f"{int(float(value))}%")
        
    def log(self, message):
        """Add message to log."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{timestamp}] {message}\n')
        self.log_text.see('end')
        self.root.update()
        
    def clear_log(self):
        """Clear log."""
        self.log_text.delete('1.0', 'end')
        
    def copy_log(self):
        """Copy log to clipboard."""
        content = self.log_text.get('1.0', 'end-1c')
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Success", "Log copied to clipboard!")
        
    def reset_form(self):
        """Reset form."""
        self.semantic_file.set('')
        self.taxonomy_file.set('')
        self.output_file.set('taxonomy_match.xlsx')
        self.threshold.set(80)
        self.clear_log()
        self.log("Form reset")
        
    def validate_inputs(self):
        """Validate inputs with deep file structure validation."""
        # Basic existence checks
        if not self.semantic_file.get():
            messagebox.showerror("Error", "Please select semantic carriers file")
            return False
        if not self.taxonomy_file.get():
            messagebox.showerror("Error", "Please select taxonomy file")
            return False
        if not self.output_file.get():
            messagebox.showerror("Error", "Please specify output file")
            return False
        if not os.path.exists(self.semantic_file.get()):
            messagebox.showerror("Error", "Semantic file not found")
            return False
        if not os.path.exists(self.taxonomy_file.get()):
            messagebox.showerror("Error", "Taxonomy file not found")
            return False

        # Deep validation of file structure
        semantic_valid, semantic_issues, _ = validate_semantic_file(self.semantic_file.get())
        taxonomy_valid, taxonomy_issues, _ = validate_taxonomy_file(self.taxonomy_file.get())

        if not semantic_valid:
            error_msg = "Semantic carriers file has issues:\n\n" + "\n".join(f"• {issue}" for issue in semantic_issues)
            messagebox.showerror("Invalid Semantic File", error_msg)
            return False

        if not taxonomy_valid:
            error_msg = "Taxonomy file has issues:\n\n" + "\n".join(f"• {issue}" for issue in taxonomy_issues)
            messagebox.showerror("Invalid Taxonomy File", error_msg)
            return False

        # Check for swapped files one more time
        is_swapped, confidence = detect_file_swap(
            self.semantic_file.get(),
            self.taxonomy_file.get()
        )

        if is_swapped:
            result = messagebox.askyesno(
                "Files May Be Swapped",
                "The selected files appear to be swapped.\n\n"
                "Would you like to continue anyway?\n\n"
                "(Click 'No' to cancel and use the 'Swap Files' button to fix)"
            )
            if not result:
                return False

        return True
        
    def run_matching(self):
        """Run matching."""
        if self.is_processing:
            messagebox.showwarning("Warning", "Already processing")
            return
            
        if not self.validate_inputs():
            return
            
        self.run_btn.config(state='disabled')
        self.is_processing = True
        self.progress.start(10)  # Speed: higher = faster animation
        self.processing_status.config(text="⚙ Processing taxonomy matching...")
        self.status_label.config(text="Processing...")
        self.clear_log()

        thread = threading.Thread(target=self.process, daemon=True)
        thread.start()
        
    def process(self):
        """Process matching."""
        try:
            self.log("=" * 50)
            self.log("Starting NL Taxonomy Mapper V3")
            self.log("=" * 50)

            matcher = TaxonomyMatcher(
                country_code=self.selected_country.get(),
                semantic_file=self.semantic_file.get(),
                taxonomy_file=self.taxonomy_file.get(),
                output_file=self.output_file.get(),
                similarity_threshold=self.threshold.get(),
                consolidate_topics=True  # Always use consolidated output
            )
            
            # Redirect print to log
            original_stdout = sys.stdout
            
            class LogWriter:
                def __init__(self, log_func):
                    self.log_func = log_func
                def write(self, text):
                    if text.strip():
                        self.log_func(text.strip())
                def flush(self):
                    pass
            
            sys.stdout = LogWriter(self.log)
            matcher.run()
            sys.stdout = original_stdout
            
            self.log("=" * 50)
            self.log(" Completed successfully!")
            self.log("=" * 50)
            
            self.root.after(0, lambda: messagebox.showinfo(
                "Success",
                f"Matching completed!\n\nOutput: {self.output_file.get()}"
            ))
            
        except Exception as e:
            self.log(f" Error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            
        finally:
            self.root.after(0, self.finish)
            
    def finish(self):
        """Finish processing."""
        self.progress.stop()
        self.processing_status.config(text="✓ Completed successfully!")
        self.run_btn.config(state='normal')
        self.is_processing = False
        self.status_label.config(text="Ready")

        # Clear the status after 3 seconds
        self.root.after(3000, lambda: self.processing_status.config(text=""))

    # ==================== SYNONYM EDITOR METHODS ====================

    def create_synonym_editor_tab(self, notebook):
        """Create synonym editor interface."""
        editor_frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(editor_frame, text='   📝 Synonym Editor  ')

        # Three-column layout
        left_panel = self.create_left_panel_syn(editor_frame)
        left_panel.pack(side='left', fill='both', expand=False, padx=10, pady=10)

        middle_panel = self.create_middle_panel_syn(editor_frame)
        middle_panel.pack(side='left', fill='both', expand=True, padx=10, pady=10)

        right_panel = self.create_right_panel_syn(editor_frame)
        right_panel.pack(side='right', fill='both', expand=False, padx=10, pady=10)

    def create_left_panel_syn(self, parent):
        """Create topic browser panel."""
        panel = tk.Frame(parent, bg=self.colors['background'], width=250)
        panel.pack_propagate(False)

        card = self.create_card(panel, "📚 Topics")
        card.pack(fill='both', expand=True)

        # Country selector
        country_frame = tk.Frame(card, bg=self.colors['card'])
        country_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(country_frame, text="Country:", bg=self.colors['card']).pack(side='left')
        self.synonym_country = tk.StringVar(value='GB')

        # Extract just country codes from available_countries (which is a list of dicts)
        country_codes = [c['code'] if isinstance(c, dict) else c for c in self.available_countries]

        country_dropdown = ttk.Combobox(
            country_frame,
            textvariable=self.synonym_country,
            values=country_codes,
            state='readonly',
            width=10
        )
        country_dropdown.pack(side='left', padx=10)
        country_dropdown.bind('<<ComboboxSelected>>', self.load_synonyms_for_editor)

        # Search box
        search_frame = tk.Frame(card, bg=self.colors['card'])
        search_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(search_frame, text="🔍 Search:", bg=self.colors['card']).pack(anchor='w')
        self.topic_search = tk.StringVar()
        self.topic_search.trace_add('write', self.filter_topics)
        search_entry = tk.Entry(search_frame, textvariable=self.topic_search)
        search_entry.pack(fill='x', pady=5)

        # Topic listbox with scrollbar
        list_frame = tk.Frame(card, bg=self.colors['card'])
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.topic_listbox = tk.Listbox(
            list_frame,
            font=('Segoe UI', 10),
            yscrollcommand=scrollbar.set,
            selectmode='single',
            bg=self.colors['card'],
            fg=self.colors['text'],
            selectbackground=self.colors['primary'],
            selectforeground='white'
        )
        self.topic_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.topic_listbox.yview)

        self.topic_listbox.bind('<<ListboxSelect>>', self.on_topic_selected)

        # Statistics label
        self.topic_stats = tk.Label(
            card,
            text="0 topics, 0 variations",
            font=('Segoe UI', 9),
            fg=self.colors['text_light'],
            bg=self.colors['card']
        )
        self.topic_stats.pack(pady=10)

        return panel

    def create_middle_panel_syn(self, parent):
        """Create synonym list editor panel."""
        panel = tk.Frame(parent, bg=self.colors['background'])

        card = self.create_card(panel, "✏️ Synonyms")
        card.pack(fill='both', expand=True)

        # Header: Selected topic name
        self.selected_topic_label = tk.Label(
            card,
            text="Select a topic to edit",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        )
        self.selected_topic_label.pack(anchor='w', padx=20, pady=(10, 5))

        # Subtext: variation count
        self.variation_count_label = tk.Label(
            card,
            text="",
            font=('Segoe UI', 9),
            fg=self.colors['text_light'],
            bg=self.colors['card']
        )
        self.variation_count_label.pack(anchor='w', padx=20, pady=(0, 10))

        # Action buttons row
        button_frame = tk.Frame(card, bg=self.colors['card'])
        button_frame.pack(fill='x', padx=20, pady=10)

        self.add_synonym_btn = tk.Button(
            button_frame,
            text="➕ Add Synonym",
            command=self.add_synonym,
            bg=self.colors['secondary'],
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            cursor='hand2',
            padx=15,
            pady=8
        )
        self.add_synonym_btn.pack(side='left', padx=(0, 10))
        self.add_synonym_btn.config(state='disabled')

        self.delete_synonym_btn = tk.Button(
            button_frame,
            text="🗑️ Delete Selected",
            command=self.delete_synonym,
            bg=self.colors['error'],
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            cursor='hand2',
            padx=15,
            pady=8
        )
        self.delete_synonym_btn.pack(side='left')
        self.delete_synonym_btn.config(state='disabled')

        self.bulk_import_btn = tk.Button(
            button_frame,
            text="📋 Bulk Import",
            command=self.bulk_import_synonyms,
            bg='#8b5cf6',  # Purple color
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            cursor='hand2',
            padx=15,
            pady=8
        )
        self.bulk_import_btn.pack(side='left', padx=(10, 0))
        self.bulk_import_btn.config(state='disabled')

        # Synonym listbox with scrollbar
        list_frame = tk.Frame(card, bg=self.colors['card'])
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.synonym_listbox = tk.Listbox(
            list_frame,
            font=('Consolas', 10),
            yscrollcommand=scrollbar.set,
            selectmode='extended',
            bg='#fafafa',
            fg=self.colors['text'],
            selectbackground=self.colors['primary'],
            selectforeground='white',
            height=20
        )
        self.synonym_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.synonym_listbox.yview)

        self.synonym_listbox.bind('<Double-Button-1>', self.edit_synonym_inline)

        return panel

    def create_right_panel_syn(self, parent):
        """Create action panel."""
        panel = tk.Frame(parent, bg=self.colors['background'], width=200)
        panel.pack_propagate(False)

        # Topic Management Card
        topic_card = self.create_card(panel, "🏷️ Topic Actions")
        topic_card.pack(fill='x', pady=(0, 10))

        btn_style = {
            'font': ('Segoe UI', 9, 'bold'),
            'relief': 'flat',
            'cursor': 'hand2',
            'padx': 10,
            'pady': 8,
            'width': 15
        }

        self.add_topic_btn = tk.Button(
            topic_card,
            text="➕ Add Topic",
            command=self.add_new_topic,
            bg=self.colors['secondary'],
            fg='white',
            **btn_style
        )
        self.add_topic_btn.pack(padx=20, pady=(10, 5))

        self.rename_topic_btn = tk.Button(
            topic_card,
            text="✏️ Rename Topic",
            command=self.rename_topic,
            bg=self.colors['primary'],
            fg='white',
            **btn_style
        )
        self.rename_topic_btn.pack(padx=20, pady=5)
        self.rename_topic_btn.config(state='disabled')

        self.delete_topic_btn = tk.Button(
            topic_card,
            text="🗑️ Delete Topic",
            command=self.delete_topic,
            bg=self.colors['error'],
            fg='white',
            **btn_style
        )
        self.delete_topic_btn.pack(padx=20, pady=(5, 10))
        self.delete_topic_btn.config(state='disabled')

        # File Operations Card
        file_card = self.create_card(panel, "💾 File Operations")
        file_card.pack(fill='x', pady=(0, 10))

        self.save_syn_btn = tk.Button(
            file_card,
            text="💾 Save Changes",
            command=self.save_synonyms,
            bg=self.colors['secondary'],
            fg='white',
            **btn_style
        )
        self.save_syn_btn.pack(padx=20, pady=(10, 5))
        self.save_syn_btn.config(state='disabled')

        self.revert_btn = tk.Button(
            file_card,
            text="↩️ Revert Changes",
            command=self.revert_synonyms,
            bg='#6b7280',
            fg='white',
            **btn_style
        )
        self.revert_btn.pack(padx=20, pady=5)
        self.revert_btn.config(state='disabled')

        self.export_btn = tk.Button(
            file_card,
            text="📤 Export Backup",
            command=self.export_synonyms_backup,
            bg=self.colors['primary'],
            fg='white',
            **btn_style
        )
        self.export_btn.pack(padx=20, pady=(5, 10))

        # Status Indicator Card
        status_card = self.create_card(panel, "📊 Status")
        status_card.pack(fill='x', pady=(0, 10))

        self.changes_indicator = tk.Label(
            status_card,
            text="✓ No unsaved changes",
            font=('Segoe UI', 9),
            fg=self.colors['secondary'],
            bg=self.colors['card']
        )
        self.changes_indicator.pack(padx=20, pady=10)

        self.validation_indicator = tk.Label(
            status_card,
            text="",
            font=('Segoe UI', 9),
            fg=self.colors['text_light'],
            bg=self.colors['card'],
            wraplength=150,
            justify='left'
        )
        self.validation_indicator.pack(padx=20, pady=(0, 10))

        # Help/Info Card
        help_card = self.create_card(panel, "ℹ️ Quick Help")
        help_card.pack(fill='both', expand=True)

        help_text = (
            "• Select topic to view synonyms\n"
            "• Double-click synonym to edit\n"
            "• Bulk Import: paste many at once\n"
            "• Use search to filter topics\n"
            "• Save often to preserve work"
        )
        tk.Label(
            help_card,
            text=help_text,
            font=('Segoe UI', 9),
            fg=self.colors['text_light'],
            bg=self.colors['card'],
            justify='left'
        ).pack(anchor='w', padx=20, pady=10)

        return panel

    def load_synonyms_for_editor(self, event=None):
        """Load synonym file for selected country."""
        country_code = self.synonym_country.get()

        try:
            files = self.country_config.get_country_files(country_code)
            synonym_file = files['synonyms']
            self.current_synonym_file = synonym_file

            with open(synonym_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.current_synonyms = data
            self.original_synonyms = copy.deepcopy(data)

            synonyms_dict = data.get('synonyms', {})
            self.all_topics = [k for k in synonyms_dict.keys() if not k.startswith('_comment')]
            self.all_topics.sort()

            self.populate_topic_list(self.all_topics)

            total_variations = sum(len(v) for k, v in synonyms_dict.items() if not k.startswith('_comment'))
            self.topic_stats.config(text=f"{len(self.all_topics)} topics, {total_variations} variations")

            self.has_unsaved_changes = False
            self.update_save_buttons()
            self.log(f"Loaded synonyms for {country_code}: {len(self.all_topics)} topics")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load synonyms: {e}")
            self.log(f"ERROR: {e}")

    def on_topic_selected(self, event):
        """Handle topic selection from listbox."""
        selection = self.topic_listbox.curselection()
        if not selection:
            return

        topic_name = self.topic_listbox.get(selection[0])

        self.selected_topic_label.config(text=topic_name)

        synonyms_dict = self.current_synonyms.get('synonyms', {})
        synonyms = synonyms_dict.get(topic_name, [])

        self.synonym_listbox.delete(0, 'end')
        for synonym in synonyms:
            self.synonym_listbox.insert('end', synonym)

        self.variation_count_label.config(text=f"{len(synonyms)} variations")

        self.add_synonym_btn.config(state='normal')
        self.delete_synonym_btn.config(state='normal')
        self.bulk_import_btn.config(state='normal')
        self.rename_topic_btn.config(state='normal')
        self.delete_topic_btn.config(state='normal')

    def add_synonym(self):
        """Add new synonym to selected topic."""
        selection = self.topic_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a topic first")
            return

        topic_name = self.topic_listbox.get(selection[0])

        new_synonym = simpledialog.askstring(
            "Add Synonym",
            f"Enter new synonym for '{topic_name}':",
            parent=self.root
        )

        if not new_synonym:
            return

        new_synonym = new_synonym.strip()
        if not new_synonym:
            return

        synonyms_dict = self.get_synonyms_dict()

        # Ensure topic exists in dict (create if needed)
        if topic_name not in synonyms_dict:
            synonyms_dict[topic_name] = []

        # Check for duplicate
        if new_synonym.lower() in [s.lower() for s in synonyms_dict[topic_name]]:
            messagebox.showinfo("Duplicate", f"'{new_synonym}' already exists for this topic")
            return

        synonyms_dict[topic_name].append(new_synonym)
        self.synonym_listbox.insert('end', new_synonym)

        count = len(synonyms_dict[topic_name])
        self.variation_count_label.config(text=f"{count} variations")

        self.mark_as_changed()
        self.log(f"Added synonym '{new_synonym}' to topic '{topic_name}'")

    def bulk_import_synonyms(self):
        """Bulk import synonyms via copy/paste dialog."""
        selection = self.topic_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a topic first")
            return

        topic_name = self.topic_listbox.get(selection[0])

        # Create bulk import dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Bulk Import Synonyms - {topic_name}")
        dialog.geometry("500x450")
        dialog.configure(bg=self.colors['background'])
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        header = tk.Label(
            dialog,
            text=f"Bulk Import Synonyms for '{topic_name}'",
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        )
        header.pack(pady=(15, 5))

        # Instructions
        instructions = tk.Label(
            dialog,
            text="Paste synonyms below (one per line).\nDuplicates will be skipped automatically.",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        )
        instructions.pack(pady=(0, 10))

        # Text area with scrollbar
        text_frame = tk.Frame(dialog, bg=self.colors['background'])
        text_frame.pack(fill='both', expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')

        text_area = tk.Text(
            text_frame,
            font=('Consolas', 10),
            wrap='word',
            yscrollcommand=scrollbar.set,
            bg='#fafafa',
            fg=self.colors['text'],
            relief='solid',
            borderwidth=1,
            padx=10,
            pady=10
        )
        text_area.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=text_area.yview)

        # Status label
        status_label = tk.Label(
            dialog,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        )
        status_label.pack(pady=5)

        # Button frame
        btn_frame = tk.Frame(dialog, bg=self.colors['background'])
        btn_frame.pack(pady=(10, 15))

        def do_import():
            """Process and import the pasted synonyms."""
            text_content = text_area.get("1.0", "end-1c")
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]

            if not lines:
                status_label.config(text="No synonyms to import", fg=self.colors['error'])
                return

            synonyms_dict = self.get_synonyms_dict()
            if topic_name not in synonyms_dict:
                synonyms_dict[topic_name] = []

            existing = [s.lower() for s in synonyms_dict[topic_name]]
            added = 0
            skipped = 0

            for line in lines:
                if line.lower() in existing:
                    skipped += 1
                else:
                    synonyms_dict[topic_name].append(line)
                    self.synonym_listbox.insert('end', line)
                    existing.append(line.lower())
                    added += 1

            count = len(synonyms_dict[topic_name])
            self.variation_count_label.config(text=f"{count} variations")

            if added > 0:
                self.mark_as_changed()
                self.log(f"Bulk imported {added} synonyms to '{topic_name}' ({skipped} duplicates skipped)")

            status_label.config(
                text=f"Imported {added} synonyms, {skipped} duplicates skipped",
                fg=self.colors['secondary'] if added > 0 else self.colors['text_light']
            )

            # Close dialog after short delay if successful
            if added > 0:
                dialog.after(1500, dialog.destroy)

        def paste_from_clipboard():
            """Paste from clipboard."""
            try:
                clipboard = dialog.clipboard_get()
                text_area.delete("1.0", "end")
                text_area.insert("1.0", clipboard)
                lines = [l.strip() for l in clipboard.split('\n') if l.strip()]
                status_label.config(text=f"Pasted {len(lines)} lines from clipboard", fg=self.colors['text_light'])
            except tk.TclError:
                status_label.config(text="Clipboard is empty", fg=self.colors['error'])

        # Paste button
        tk.Button(
            btn_frame,
            text="📋 Paste from Clipboard",
            command=paste_from_clipboard,
            font=('Segoe UI', 10),
            bg='#6b7280',
            fg='white',
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

        # Import button
        tk.Button(
            btn_frame,
            text="✓ Import All",
            command=do_import,
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['secondary'],
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

        # Cancel button
        tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            font=('Segoe UI', 10),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

        # Focus the text area
        text_area.focus_set()

    def delete_synonym(self):
        """Delete selected synonym(s) from topic."""
        selection = self.synonym_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select synonym(s) to delete")
            return

        topic_selection = self.topic_listbox.curselection()
        if not topic_selection:
            return
        topic_name = self.topic_listbox.get(topic_selection[0])

        count = len(selection)
        if not messagebox.askyesno("Confirm Delete", f"Delete {count} synonym(s)?"):
            return

        synonyms_dict = self.get_synonyms_dict()
        for idx in reversed(selection):
            synonym_to_delete = self.synonym_listbox.get(idx)
            if topic_name in synonyms_dict:
                try:
                    synonyms_dict[topic_name].remove(synonym_to_delete)
                except ValueError:
                    pass
            self.synonym_listbox.delete(idx)

        count = len(synonyms_dict.get(topic_name, []))
        self.variation_count_label.config(text=f"{count} variations")

        self.mark_as_changed()
        self.log(f"Deleted {len(selection)} synonym(s) from '{topic_name}'")

    def edit_synonym_inline(self, event):
        """Edit synonym via double-click."""
        selection = self.synonym_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        old_synonym = self.synonym_listbox.get(idx)

        topic_selection = self.topic_listbox.curselection()
        if not topic_selection:
            return
        topic_name = self.topic_listbox.get(topic_selection[0])

        new_synonym = simpledialog.askstring(
            "Edit Synonym",
            "Edit synonym:",
            initialvalue=old_synonym,
            parent=self.root
        )

        if not new_synonym or new_synonym == old_synonym:
            return

        synonyms_dict = self.get_synonyms_dict()
        if topic_name in synonyms_dict:
            try:
                idx_in_list = synonyms_dict[topic_name].index(old_synonym)
                synonyms_dict[topic_name][idx_in_list] = new_synonym
            except ValueError:
                pass

        self.synonym_listbox.delete(idx)
        self.synonym_listbox.insert(idx, new_synonym)
        self.synonym_listbox.selection_set(idx)

        self.mark_as_changed()
        self.log(f"Edited synonym: '{old_synonym}' → '{new_synonym}'")

    def add_new_topic(self):
        """Add new topic to synonym file."""
        new_topic = simpledialog.askstring(
            "Add Topic",
            "Enter new topic name:",
            parent=self.root
        )

        if not new_topic:
            return

        synonyms_dict = self.get_synonyms_dict()
        if new_topic in synonyms_dict:
            messagebox.showwarning("Duplicate Topic", f"Topic '{new_topic}' already exists")
            return

        synonyms_dict[new_topic] = []

        self.all_topics.append(new_topic)
        self.all_topics.sort()
        self.populate_topic_list(self.all_topics)

        idx = self.all_topics.index(new_topic)
        self.topic_listbox.selection_clear(0, 'end')
        self.topic_listbox.selection_set(idx)
        self.topic_listbox.see(idx)
        self.on_topic_selected(None)

        self.update_statistics()

        self.mark_as_changed()
        self.log(f"Added new topic: '{new_topic}'")

    def rename_topic(self):
        """Rename selected topic."""
        selection = self.topic_listbox.curselection()
        if not selection:
            return

        old_topic = self.topic_listbox.get(selection[0])

        new_topic = simpledialog.askstring(
            "Rename Topic",
            f"Rename topic '{old_topic}' to:",
            initialvalue=old_topic,
            parent=self.root
        )

        if not new_topic or new_topic == old_topic:
            return

        synonyms_dict = self.get_synonyms_dict()
        if new_topic in synonyms_dict:
            messagebox.showwarning("Duplicate Topic", f"Topic '{new_topic}' already exists")
            return

        synonyms_dict[new_topic] = synonyms_dict.pop(old_topic, [])

        self.all_topics.remove(old_topic)
        self.all_topics.append(new_topic)
        self.all_topics.sort()
        self.populate_topic_list(self.all_topics)

        idx = self.all_topics.index(new_topic)
        self.topic_listbox.selection_set(idx)
        self.topic_listbox.see(idx)
        self.on_topic_selected(None)

        self.mark_as_changed()
        self.log(f"Renamed topic: '{old_topic}' → '{new_topic}'")

    def delete_topic(self):
        """Delete selected topic."""
        selection = self.topic_listbox.curselection()
        if not selection:
            return

        topic_name = self.topic_listbox.get(selection[0])

        if not messagebox.askyesno("Confirm Delete", f"Delete topic '{topic_name}' and all its synonyms?"):
            return

        synonyms_dict = self.get_synonyms_dict()
        if topic_name in synonyms_dict:
            del synonyms_dict[topic_name]

        self.all_topics.remove(topic_name)
        self.populate_topic_list(self.all_topics)

        self.selected_topic_label.config(text="Select a topic to edit")
        self.variation_count_label.config(text="")
        self.synonym_listbox.delete(0, 'end')

        self.add_synonym_btn.config(state='disabled')
        self.delete_synonym_btn.config(state='disabled')
        self.rename_topic_btn.config(state='disabled')
        self.delete_topic_btn.config(state='disabled')

        self.update_statistics()

        self.mark_as_changed()
        self.log(f"Deleted topic: '{topic_name}'")

    def save_synonyms(self):
        """Save synonym changes to JSON file with atomic write for safety."""
        if not self.has_unsaved_changes:
            messagebox.showinfo("No Changes", "No unsaved changes to save")
            return

        # Safety check: ensure file path is set
        if not self.current_synonym_file:
            messagebox.showerror("Error", "No synonym file loaded. Please select a country first.")
            return

        try:
            import shutil
            import tempfile

            # Validate data structure before saving
            if 'synonyms' not in self.current_synonyms:
                self.current_synonyms['synonyms'] = {}
                self.log("Warning: Created missing 'synonyms' key")

            # Ensure synonyms is a dict
            if not isinstance(self.current_synonyms.get('synonyms'), dict):
                messagebox.showerror("Error", "Synonym data is corrupted. Please reload the file.")
                return

            # Update metadata
            self.current_synonyms['last_updated'] = datetime.now().strftime('%Y-%m-%d')
            synonyms_dict = self.current_synonyms['synonyms']
            self.current_synonyms['total_mappings'] = len([k for k in synonyms_dict.keys() if not k.startswith('_')])

            # Create backup of existing file
            if os.path.exists(self.current_synonym_file):
                backup_file = self.current_synonym_file.replace('.json', '_backup.json')
                shutil.copy2(self.current_synonym_file, backup_file)
                self.log(f"Created backup: {backup_file}")

            # Atomic write: write to temp file first, then rename
            # This prevents corruption if the process crashes mid-write
            dir_path = os.path.dirname(self.current_synonym_file)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', dir=dir_path,
                                              delete=False, encoding='utf-8') as temp_file:
                json.dump(self.current_synonyms, temp_file, indent=2, ensure_ascii=False)
                temp_path = temp_file.name

            # Replace original file with temp file (atomic on most systems)
            if os.path.exists(self.current_synonym_file):
                os.remove(self.current_synonym_file)
            shutil.move(temp_path, self.current_synonym_file)

            self.original_synonyms = copy.deepcopy(self.current_synonyms)

            self.has_unsaved_changes = False
            self.update_save_buttons()

            messagebox.showinfo("Success", "Synonyms saved successfully!")
            self.log("✓ Synonyms saved successfully")

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            self.log(f"ERROR saving: {e}")
            # Clean up temp file if it exists
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

    def revert_synonyms(self):
        """Revert to last saved version."""
        if not self.has_unsaved_changes:
            messagebox.showinfo("No Changes", "No changes to revert")
            return

        if not messagebox.askyesno("Confirm Revert", "Discard all unsaved changes?"):
            return

        self.current_synonyms = copy.deepcopy(self.original_synonyms)

        self.load_synonyms_for_editor()

        self.has_unsaved_changes = False
        self.update_save_buttons()

        messagebox.showinfo("Reverted", "Changes reverted to last saved version")
        self.log("↩️ Changes reverted")

    def export_synonyms_backup(self):
        """Export backup of current synonyms."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"synonyms_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.current_synonyms, f, indent=2, ensure_ascii=False)

            messagebox.showinfo("Success", f"Backup exported to:\n{filename}")
            self.log(f"Exported backup to: {filename}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")
            self.log(f"ERROR exporting: {e}")

    def get_synonyms_dict(self):
        """
        Safely get the synonyms dictionary, ensuring it exists in current_synonyms.
        This prevents orphaned dict references that could cause data loss.
        """
        if 'synonyms' not in self.current_synonyms:
            self.current_synonyms['synonyms'] = {}
            self.log("Warning: Created missing 'synonyms' key in data structure")
        return self.current_synonyms['synonyms']

    def filter_topics(self, *args):
        """Filter topic list based on search text."""
        search_text = self.topic_search.get().lower()

        if not search_text:
            self.populate_topic_list(self.all_topics)
            return

        filtered = [t for t in self.all_topics if search_text in t.lower()]
        self.populate_topic_list(filtered)

        synonyms_dict = self.current_synonyms.get('synonyms', {})
        total_variations = sum(len(synonyms_dict.get(t, [])) for t in filtered)
        self.topic_stats.config(text=f"{len(filtered)} topics (filtered), {total_variations} variations")

    def populate_topic_list(self, topics):
        """Populate topic listbox with given topics."""
        self.topic_listbox.delete(0, 'end')
        for topic in topics:
            if not topic.startswith('_comment'):
                self.topic_listbox.insert('end', topic)

    def mark_as_changed(self):
        """Mark editor as having unsaved changes."""
        self.has_unsaved_changes = True
        self.update_save_buttons()

    def update_save_buttons(self):
        """Update save/revert button states."""
        state = 'normal' if self.has_unsaved_changes else 'disabled'
        self.save_syn_btn.config(state=state)
        self.revert_btn.config(state=state)

        if self.has_unsaved_changes:
            self.changes_indicator.config(
                text="⚠️ Unsaved changes",
                fg=self.colors['error']
            )
        else:
            self.changes_indicator.config(
                text="✓ No unsaved changes",
                fg=self.colors['secondary']
            )

    def update_statistics(self):
        """Update topic/variation count statistics."""
        synonyms_dict = self.current_synonyms.get('synonyms', {})
        topics = [k for k in synonyms_dict.keys() if not k.startswith('_comment')]
        total_variations = sum(len(v) for k, v in synonyms_dict.items() if not k.startswith('_comment'))
        self.topic_stats.config(text=f"{len(topics)} topics, {total_variations} variations")

    def generate_synonym_report(self):
        """Generate proposed synonyms report from semantic keywords vs taxonomy topics."""
        from collections import Counter, defaultdict
        from fuzzywuzzy import fuzz

        # 1. Validate files are selected
        semantic_file = self.semantic_file.get()
        taxonomy_file = self.taxonomy_file.get()

        if not semantic_file or not os.path.exists(semantic_file):
            messagebox.showerror("Error", "Please select a valid Semantic Carriers file in Setup tab")
            return

        if not taxonomy_file or not os.path.exists(taxonomy_file):
            messagebox.showerror("Error", "Please select a valid Taxonomy file in Setup tab")
            return

        # Update status
        self.report_status_label.config(text="Generating report...", fg=self.colors['primary'])
        self.root.update()

        try:
            # Load existing synonyms for current country
            country_code = self.selected_country.get()
            existing_synonyms = self.country_config.load_synonyms(country_code)
            self.log(f"Loaded {len(existing_synonyms)} existing synonym mappings for {country_code}")

            # Build reverse lookup: synonym (lowercase) -> set of topics it maps to
            synonym_to_topics = defaultdict(set)
            for topic, syns in existing_synonyms.items():
                topic_lower = topic.lower()
                synonym_to_topics[topic_lower].add(topic)  # Topic itself
                for syn in syns:
                    synonym_to_topics[syn.lower()].add(topic)

            self.log("Loading semantic carriers file...")
            sem_df = pd.read_excel(semantic_file)

            # Collect all keywords with frequencies
            all_keywords = []
            for i in range(1, 16):
                col = f'Keyword {i}'
                if col in sem_df.columns:
                    all_keywords.extend(sem_df[col].dropna().astype(str).tolist())

            keyword_counts = Counter([k.lower().strip() for k in all_keywords])
            self.log(f"Found {len(keyword_counts)} unique keywords")

            # Load taxonomy topics
            self.log("Loading taxonomy file...")
            tax_df = pd.read_excel(taxonomy_file)
            topic_cols = [c for c in tax_df.columns if c.startswith('Topic')]

            all_topics = set()
            topic_to_product = {}
            for _, row in tax_df.iterrows():
                product = row.get('Product', '')
                for col in topic_cols:
                    val = row.get(col)
                    if pd.notna(val):
                        topic = str(val).strip()
                        all_topics.add(topic)
                        topic_to_product[topic] = product

            self.log(f"Found {len(all_topics)} unique topics")

            # Get top 300 keywords by frequency
            top_keywords = [kw for kw, count in keyword_counts.most_common(300)]

            self.log("Finding keyword matches for each topic (this may take a moment)...")

            # Build Topic -> Keywords mapping
            results = []
            for topic in sorted(all_topics):
                topic_lower = topic.lower()

                for kw in top_keywords:
                    # Calculate match scores
                    score1 = fuzz.ratio(kw, topic_lower)
                    score2 = fuzz.partial_ratio(kw, topic_lower)
                    score3 = fuzz.token_set_ratio(kw, topic_lower)
                    best_score = max(score1, score2, score3)

                    if best_score >= 70:
                        freq = keyword_counts[kw]
                        # Check if this keyword is already a synonym for this topic
                        already_added = topic in synonym_to_topics.get(kw, set())
                        results.append({
                            'Topic': topic,
                            'Product': topic_to_product.get(topic, ''),
                            'Proposed_Synonym': kw,
                            'Match_Score': best_score,
                            'Keyword_Frequency': freq,
                            'Priority': 'HIGH' if best_score >= 85 and freq >= 50 else 'MEDIUM' if best_score >= 75 else 'LOW',
                            'Already_Added': 'Yes' if already_added else 'No'
                        })

            # Create DataFrame
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values(['Topic', 'Match_Score', 'Keyword_Frequency'], ascending=[True, False, False])

            # Ask for save location
            output_file = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile="Proposed_Synonyms_Report.xlsx",
                title="Save Synonym Report As"
            )

            if not output_file:
                self.report_status_label.config(text="Cancelled", fg=self.colors['text_light'])
                return

            self.log(f"Saving report to {output_file}...")

            # Save to Excel with multiple sheets
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet 1: All proposed synonyms
                df_results.to_excel(writer, sheet_name='All Proposed Synonyms', index=False)

                # Sheet 2: High priority only
                high_priority = df_results[df_results['Priority'] == 'HIGH']
                high_priority.to_excel(writer, sheet_name='HIGH Priority', index=False)

                # Sheet 3: Summary by topic
                summary = df_results.groupby('Topic').agg({
                    'Proposed_Synonym': 'count',
                    'Match_Score': 'max',
                    'Keyword_Frequency': 'sum'
                }).reset_index()
                summary.columns = ['Topic', 'Synonym_Count', 'Best_Match_Score', 'Total_Keyword_Frequency']
                summary = summary.sort_values('Total_Keyword_Frequency', ascending=False)
                summary.to_excel(writer, sheet_name='Summary by Topic', index=False)

                # Sheet 4: NEW synonyms only (not yet in synonyms.json)
                new_only = df_results[df_results['Already_Added'] == 'No']
                new_only.to_excel(writer, sheet_name='NEW Only', index=False)

                # Sheet 5: Top unmapped keywords
                matched_keywords = set(df_results['Proposed_Synonym'].unique())
                unmapped = [(kw, freq) for kw, freq in keyword_counts.most_common(100) if kw not in matched_keywords]
                df_unmapped = pd.DataFrame(unmapped, columns=['Keyword', 'Frequency'])
                df_unmapped['Recommendation'] = 'Consider adding as new topic or synonym'
                df_unmapped.to_excel(writer, sheet_name='Unmapped Keywords', index=False)

            # Calculate already added vs new counts
            already_added_count = len(df_results[df_results['Already_Added'] == 'Yes'])
            new_count = len(df_results[df_results['Already_Added'] == 'No'])
            high_priority_new = len(high_priority[high_priority['Already_Added'] == 'No'])

            self.log(f"Report saved successfully!")
            self.log(f"  - Total proposed synonyms: {len(df_results)}")
            self.log(f"  - Already in synonyms.json: {already_added_count}")
            self.log(f"  - NEW (not yet added): {new_count}")
            self.log(f"  - HIGH priority (total): {len(high_priority)}")
            self.log(f"  - HIGH priority (new): {high_priority_new}")
            self.log(f"  - Topics with synonyms: {df_results['Topic'].nunique()}")
            self.log(f"  - Unmapped high-freq keywords: {len(unmapped)}")

            self.report_status_label.config(text="Complete!", fg=self.colors['secondary'])
            messagebox.showinfo("Success", f"Report saved to:\n{output_file}\n\n"
                                           f"Total synonyms proposed: {len(df_results)}\n"
                                           f"Already added: {already_added_count}\n"
                                           f"NEW to add: {new_count}\n"
                                           f"HIGH priority (new): {high_priority_new}")

        except Exception as e:
            self.log(f"ERROR generating report: {e}")
            self.report_status_label.config(text="Error", fg=self.colors['error'])
            messagebox.showerror("Error", f"Failed to generate report:\n{e}")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = TaxonomyMapperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()