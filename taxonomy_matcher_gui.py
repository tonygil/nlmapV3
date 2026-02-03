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
import tempfile
from datetime import datetime
from taxonomy_matcher import TaxonomyMatcher
from country_config import CountryConfig
from post_processor import PostProcessor, URL_EXCLUSION_PATTERNS
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
        self.root.geometry("1000x850")  # Fallback size
        self.root.resizable(True, True)
        # Start maximized on Windows
        self.root.state('zoomed')
        
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
        self.top_n = tk.IntVar(value=3)
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

        # Custom Taxonomy indicator and Reset button (hidden by default)
        self.custom_taxonomy_frame = tk.Frame(
            input_card,
            bg='#e0f2fe',  # Light blue background
            relief='solid',
            bd=1
        )

        custom_tax_content = tk.Frame(self.custom_taxonomy_frame, bg='#e0f2fe')
        custom_tax_content.pack(fill='x', padx=15, pady=8)

        self.custom_taxonomy_label = tk.Label(
            custom_tax_content,
            text="📁 Using custom taxonomy file",
            font=('Segoe UI', 9),
            bg='#e0f2fe',
            fg='#0369a1'  # Dark blue text
        )
        self.custom_taxonomy_label.pack(side='left', padx=(0, 15))

        self.reset_taxonomy_btn = tk.Button(
            custom_tax_content,
            text="Reset to Default",
            command=self.reset_taxonomy_to_default,
            font=('Segoe UI', 9),
            bg='#0ea5e9',  # Blue button
            fg='white',
            relief='flat',
            padx=15,
            pady=3,
            cursor='hand2'
        )
        self.reset_taxonomy_btn.pack(side='left')

        # Bind country change to auto-populate file paths
        self.selected_country.trace_add('write', self.on_country_changed)

        # Bind taxonomy file change to update custom indicator
        self.taxonomy_file.trace_add('write', lambda *args: self.update_custom_taxonomy_indicator())

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

        # Top N results per URL
        top_n_frame = tk.Frame(settings_card, bg=self.colors['card'])
        top_n_frame.pack(fill='x', padx=20, pady=(10, 0))

        tk.Label(
            top_n_frame,
            text="Top results per URL:",
            font=('Segoe UI', 10),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(side='left')

        self.top_n_label = tk.Label(
            top_n_frame,
            text=str(self.top_n.get()),
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['primary']
        )
        self.top_n_label.pack(side='right')

        top_n_slider = tk.Scale(
            settings_card,
            from_=1,
            to=10,
            orient='horizontal',
            variable=self.top_n,
            command=self.update_top_n,
            bg=self.colors['card'],
            fg=self.colors['text'],
            highlightthickness=0,
            troughcolor=self.colors['border']
        )
        top_n_slider.pack(fill='x', padx=20, pady=(0, 10))

        tk.Label(
            settings_card,
            text=" Limits output to N best-matching rows per URL",
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

        # Summary Column Option
        self.use_summary = tk.BooleanVar(value=False)
        summary_check = tk.Checkbutton(
            settings_card,
            text="Use Summary column for additional keywords (crawler output)",
            variable=self.use_summary,
            font=('Segoe UI', 10),
            bg=self.colors['card'],
            fg=self.colors['text'],
            selectcolor=self.colors['card'],
            activebackground=self.colors['card'],
            cursor='hand2'
        )
        summary_check.pack(anchor='w', padx=20, pady=(5, 10))

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

        self.postprocess_btn = tk.Button(
            btn_frame,
            text="🧹 Clean Output",
            command=self.run_post_processing,
            font=('Segoe UI', 10),
            bg='#8b5cf6',
            fg='white',
            relief='flat',
            padx=20,
            pady=12,
            cursor='hand2'
        )
        self.postprocess_btn.pack(side='left', padx=5)
        ToolTip(self.postprocess_btn, "Post-process the output file to remove noise and rank issues")

        self.url_pattern_btn = tk.Button(
            btn_frame,
            text="🔗 Filter URL Patterns",
            command=self.show_url_pattern_dialog,
            font=('Segoe UI', 10),
            bg='#f59e0b',
            fg='white',
            relief='flat',
            padx=20,
            pady=12,
            cursor='hand2'
        )
        self.url_pattern_btn.pack(side='left', padx=5)
        ToolTip(self.url_pattern_btn, "Preview and filter URLs matching exclusion patterns (Special pages, redirects, etc.)")

        self.remap_btn = tk.Button(
            btn_frame,
            text="🔄 Remap URLs",
            command=self.show_remap_dialog,
            font=('Segoe UI', 10),
            bg='#06b6d4',
            fg='white',
            relief='flat',
            padx=20,
            pady=12,
            cursor='hand2'
        )
        self.remap_btn.pack(side='left', padx=5)
        ToolTip(self.remap_btn, "Re-run matching on filtered URLs against a new taxonomy file")

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
        """Create reports tab for analysis tools with scrollable layout."""
        frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(frame, text='   Reports  ')

        # Create scrollable container
        canvas = tk.Canvas(frame, bg=self.colors['background'], highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['background'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Main content frame inside scrollable area
        main_content = tk.Frame(scrollable_frame, bg=self.colors['background'])
        main_content.pack(fill='both', expand=True, padx=10, pady=10)

        # ============ QUICK REPORTS ROW (Synonym, Quality, Unmapped) ============
        quick_reports_label = tk.Label(
            main_content,
            text="Quick Reports",
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        )
        quick_reports_label.pack(anchor='w', pady=(0, 10))

        # Three-column frame for quick reports
        quick_row = tk.Frame(main_content, bg=self.colors['background'])
        quick_row.pack(fill='x', pady=(0, 15))

        # Configure columns to expand equally
        quick_row.columnconfigure(0, weight=1)
        quick_row.columnconfigure(1, weight=1)
        quick_row.columnconfigure(2, weight=1)

        # --- Synonym Report Card ---
        synonym_card = tk.Frame(quick_row, bg=self.colors['card'], relief='solid', bd=1)
        synonym_card.grid(row=0, column=0, sticky='nsew', padx=(0, 5), pady=5)

        tk.Label(
            synonym_card,
            text="Proposed Synonyms",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=10, pady=(10, 5))

        tk.Label(
            synonym_card,
            text="Compare keywords with topics\nto propose new synonyms",
            font=('Segoe UI', 8),
            bg=self.colors['card'],
            fg=self.colors['text_light'],
            justify='left'
        ).pack(anchor='w', padx=10, pady=(0, 10))

        self.synonym_report_btn = tk.Button(
            synonym_card,
            text="Generate",
            command=self.generate_synonym_report,
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2'
        )
        self.synonym_report_btn.pack(anchor='w', padx=10, pady=(0, 5))

        self.report_status_label = tk.Label(
            synonym_card,
            text="",
            font=('Segoe UI', 8),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.report_status_label.pack(anchor='w', padx=10, pady=(0, 10))

        # --- Match Quality Report Card ---
        quality_card = tk.Frame(quick_row, bg=self.colors['card'], relief='solid', bd=1)
        quality_card.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

        tk.Label(
            quality_card,
            text="Match Quality",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=10, pady=(10, 5))

        tk.Label(
            quality_card,
            text="Analyze scores, rankings\nand relevance categories",
            font=('Segoe UI', 8),
            bg=self.colors['card'],
            fg=self.colors['text_light'],
            justify='left'
        ).pack(anchor='w', padx=10, pady=(0, 5))

        # Top N input
        topn_row = tk.Frame(quality_card, bg=self.colors['card'])
        topn_row.pack(anchor='w', padx=10, pady=(0, 10))
        tk.Label(topn_row, text="Top N:", font=('Segoe UI', 8), bg=self.colors['card']).pack(side='left')
        self.top_n_var = tk.StringVar(value="3")
        tk.Entry(topn_row, textvariable=self.top_n_var, font=('Segoe UI', 8), width=4).pack(side='left', padx=5)

        self.quality_report_btn = tk.Button(
            quality_card,
            text="Generate",
            command=self.generate_quality_report,
            font=('Segoe UI', 9, 'bold'),
            bg='#9b59b6',
            fg='white',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2'
        )
        self.quality_report_btn.pack(anchor='w', padx=10, pady=(0, 5))

        self.quality_report_status_label = tk.Label(
            quality_card,
            text="",
            font=('Segoe UI', 8),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.quality_report_status_label.pack(anchor='w', padx=10, pady=(0, 10))

        # --- Unmapped Reasons Report Card ---
        unmapped_card = tk.Frame(quick_row, bg=self.colors['card'], relief='solid', bd=1)
        unmapped_card.grid(row=0, column=2, sticky='nsew', padx=(5, 0), pady=5)

        tk.Label(
            unmapped_card,
            text="Unmapped Reasons",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=10, pady=(10, 5))

        tk.Label(
            unmapped_card,
            text="Diagnose why URLs\nfailed to match",
            font=('Segoe UI', 8),
            bg=self.colors['card'],
            fg=self.colors['text_light'],
            justify='left'
        ).pack(anchor='w', padx=10, pady=(0, 10))

        self.unmapped_report_btn = tk.Button(
            unmapped_card,
            text="Generate",
            command=self.generate_unmapped_report,
            font=('Segoe UI', 9, 'bold'),
            bg='#e67e22',
            fg='white',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2'
        )
        self.unmapped_report_btn.pack(anchor='w', padx=10, pady=(0, 5))

        self.unmapped_report_status_label = tk.Label(
            unmapped_card,
            text="",
            font=('Segoe UI', 8),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.unmapped_report_status_label.pack(anchor='w', padx=10, pady=(0, 10))

        # ============ TOPIC RECOMMENDATIONS REPORT (Full Width) ============
        tk.Label(
            main_content,
            text="Topic Recommendations Report",
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        ).pack(anchor='w', pady=(15, 10))

        topic_rec_card = tk.Frame(main_content, bg=self.colors['card'], relief='solid', bd=1)
        topic_rec_card.pack(fill='x', pady=(0, 10))

        topic_rec_content = tk.Frame(topic_rec_card, bg=self.colors['card'])
        topic_rec_content.pack(fill='x', padx=15, pady=15)

        tk.Label(
            topic_rec_content,
            text="Analyzes match results against taxonomy to identify gaps and recommend new topics.\n"
                 "Generates 8-sheet Excel: Summary, Quality Issues, Gaps, Recommendations, New Topics, URLs, Impact, Topics to Add.",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light'],
            justify='left'
        ).pack(anchor='w', pady=(0, 10))

        # File inputs in a grid
        inputs_grid = tk.Frame(topic_rec_content, bg=self.colors['card'])
        inputs_grid.pack(fill='x')

        # Row 1: Match File and Taxonomy File
        row1 = tk.Frame(inputs_grid, bg=self.colors['card'])
        row1.pack(fill='x', pady=3)

        tk.Label(row1, text="Match File:", font=('Segoe UI', 9), bg=self.colors['card'], width=12, anchor='w').pack(side='left')
        self.topic_rec_match_file = tk.StringVar()
        tk.Entry(row1, textvariable=self.topic_rec_match_file, font=('Segoe UI', 8), width=35).pack(side='left', padx=(0, 5))
        tk.Button(row1, text="Browse", command=lambda: self._browse_topic_rec_file(self.topic_rec_match_file, "Select Match File"),
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')

        tk.Label(row1, text="  Taxonomy:", font=('Segoe UI', 9), bg=self.colors['card'], anchor='w').pack(side='left', padx=(15, 0))
        self.topic_rec_taxonomy_file = tk.StringVar()
        tk.Entry(row1, textvariable=self.topic_rec_taxonomy_file, font=('Segoe UI', 8), width=35).pack(side='left', padx=(0, 5))
        tk.Button(row1, text="Browse", command=lambda: self._browse_topic_rec_file(self.topic_rec_taxonomy_file, "Select Taxonomy"),
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')

        # Row 2: Document Source and Output File
        row2 = tk.Frame(inputs_grid, bg=self.colors['card'])
        row2.pack(fill='x', pady=3)

        tk.Label(row2, text="Doc Source:", font=('Segoe UI', 9), bg=self.colors['card'], width=12, anchor='w').pack(side='left')
        self.topic_rec_doc_source = tk.StringVar()
        tk.Entry(row2, textvariable=self.topic_rec_doc_source, font=('Segoe UI', 8), width=35).pack(side='left', padx=(0, 5))
        tk.Button(row2, text="Browse", command=lambda: self._browse_topic_rec_file(self.topic_rec_doc_source, "Select Document Source"),
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')
        tk.Button(row2, text="Clear", command=lambda: self.topic_rec_doc_source.set(''),
                  font=('Segoe UI', 8), bg='#95a5a6', fg='white', relief='flat', padx=6).pack(side='left', padx=3)

        tk.Label(row2, text="  Output:", font=('Segoe UI', 9), bg=self.colors['card'], anchor='w').pack(side='left', padx=(5, 0))
        self.topic_rec_output_file = tk.StringVar(value='TOPIC_RECOMMENDATIONS.xlsx')
        tk.Entry(row2, textvariable=self.topic_rec_output_file, font=('Segoe UI', 8), width=35).pack(side='left', padx=(0, 5))
        tk.Button(row2, text="Browse", command=self._browse_topic_rec_output,
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')

        # Generate button row
        btn_row = tk.Frame(topic_rec_content, bg=self.colors['card'])
        btn_row.pack(anchor='w', pady=(15, 0))

        self.topic_rec_report_btn = tk.Button(
            btn_row,
            text="Generate Topic Recommendations Report",
            command=self.generate_topic_recommendations_report,
            font=('Segoe UI', 10, 'bold'),
            bg='#27ae60',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        self.topic_rec_report_btn.pack(side='left')

        self.topic_rec_status_label = tk.Label(
            btn_row,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.topic_rec_status_label.pack(side='left', padx=15)

        # ============ GAP ANALYSIS REPORT (Full Width) ============
        tk.Label(
            main_content,
            text="Taxonomy Gap Analysis Report",
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        ).pack(anchor='w', pady=(15, 10))

        gap_analysis_card = tk.Frame(main_content, bg=self.colors['card'], relief='solid', bd=1)
        gap_analysis_card.pack(fill='x', pady=(0, 10))

        gap_analysis_content = tk.Frame(gap_analysis_card, bg=self.colors['card'])
        gap_analysis_content.pack(fill='x', padx=15, pady=15)

        tk.Label(
            gap_analysis_content,
            text="Comprehensive analysis of taxonomy coverage: phantom topics, never-matched topics, synonym recommendations.\n"
                 "Generates 7-sheet Excel: Executive Summary, Phantom Topics, Never-Matched, Comparison, Synonym Recs, Product Breakdown, Actions.",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light'],
            justify='left'
        ).pack(anchor='w', pady=(0, 10))

        # File selection rows
        gap_row1 = tk.Frame(gap_analysis_content, bg=self.colors['card'])
        gap_row1.pack(fill='x', pady=2)
        tk.Label(gap_row1, text="Match File:", font=('Segoe UI', 9), bg=self.colors['card'], width=12, anchor='w').pack(side='left')
        self.gap_analysis_match_file = tk.StringVar()
        tk.Entry(gap_row1, textvariable=self.gap_analysis_match_file, font=('Segoe UI', 8), width=50).pack(side='left', padx=(0, 5))
        tk.Button(gap_row1, text="Browse", command=lambda: self._browse_gap_analysis_file(self.gap_analysis_match_file, "Select Match File"),
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')

        gap_row2 = tk.Frame(gap_analysis_content, bg=self.colors['card'])
        gap_row2.pack(fill='x', pady=2)
        tk.Label(gap_row2, text="Taxonomy:", font=('Segoe UI', 9), bg=self.colors['card'], width=12, anchor='w').pack(side='left')
        self.gap_analysis_taxonomy_file = tk.StringVar()
        tk.Entry(gap_row2, textvariable=self.gap_analysis_taxonomy_file, font=('Segoe UI', 8), width=50).pack(side='left', padx=(0, 5))
        tk.Button(gap_row2, text="Browse", command=lambda: self._browse_gap_analysis_file(self.gap_analysis_taxonomy_file, "Select Taxonomy File"),
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')

        gap_row3 = tk.Frame(gap_analysis_content, bg=self.colors['card'])
        gap_row3.pack(fill='x', pady=2)
        tk.Label(gap_row3, text="Semantic:", font=('Segoe UI', 9), bg=self.colors['card'], width=12, anchor='w').pack(side='left')
        self.gap_analysis_semantic_file = tk.StringVar()
        tk.Entry(gap_row3, textvariable=self.gap_analysis_semantic_file, font=('Segoe UI', 8), width=35).pack(side='left', padx=(0, 5))
        tk.Button(gap_row3, text="Browse", command=lambda: self._browse_gap_analysis_file(self.gap_analysis_semantic_file, "Select Semantic File"),
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')
        tk.Button(gap_row3, text="Clear", command=lambda: self.gap_analysis_semantic_file.set(''),
                  font=('Segoe UI', 8), bg='#95a5a6', fg='white', relief='flat', padx=6).pack(side='left', padx=3)
        tk.Label(gap_row3, text="(optional)", font=('Segoe UI', 8, 'italic'), bg=self.colors['card'], fg=self.colors['text_light']).pack(side='left', padx=3)

        gap_row4 = tk.Frame(gap_analysis_content, bg=self.colors['card'])
        gap_row4.pack(fill='x', pady=2)
        tk.Label(gap_row4, text="Output:", font=('Segoe UI', 9), bg=self.colors['card'], width=12, anchor='w').pack(side='left')
        self.gap_analysis_output_file = tk.StringVar(value='TAXONOMY_GAP_ANALYSIS_REPORT.xlsx')
        tk.Entry(gap_row4, textvariable=self.gap_analysis_output_file, font=('Segoe UI', 8), width=35).pack(side='left', padx=(0, 5))
        tk.Button(gap_row4, text="Browse", command=self._browse_gap_analysis_output,
                  font=('Segoe UI', 8), bg=self.colors['primary'], fg='white', relief='flat', padx=8).pack(side='left')

        # Generate button row
        gap_btn_row = tk.Frame(gap_analysis_content, bg=self.colors['card'])
        gap_btn_row.pack(anchor='w', pady=(15, 0))

        self.gap_analysis_report_btn = tk.Button(
            gap_btn_row,
            text="Generate Gap Analysis Report",
            command=self.generate_gap_analysis_report,
            font=('Segoe UI', 10, 'bold'),
            bg='#8e44ad',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        self.gap_analysis_report_btn.pack(side='left')

        self.gap_analysis_status_label = tk.Label(
            gap_btn_row,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        )
        self.gap_analysis_status_label.pack(side='left', padx=15)

        # ============ REQUIREMENTS INFO ============
        info_frame = tk.Frame(main_content, bg=self.colors['background'])
        info_frame.pack(fill='x', anchor='w', pady=(15, 10))

        tk.Label(
            info_frame,
            text="Requirements:",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        ).pack(anchor='w')

        tk.Label(
            info_frame,
            text="• Quick Reports: Select Semantic Carriers and Taxonomy files in Setup tab first\n"
                 "• Topic Recommendations: Select files directly above (uses cleaned match output)\n"
                 "• Gap Analysis: Select files above - identifies phantom topics, never-matched topics, and synonym suggestions",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
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

            # Check if using custom taxonomy and show/hide indicator
            self.update_custom_taxonomy_indicator()

        except Exception as e:
            self.log(f"Warning: Could not load files for {country_code}: {e}")

    def update_custom_taxonomy_indicator(self):
        """Show or hide the custom taxonomy indicator based on current file."""
        country_code = self.selected_country.get()
        current_taxonomy = self.taxonomy_file.get()

        # Check if we have a last used taxonomy that differs from default
        last_used = self.country_config.get_last_used_taxonomy(country_code)

        # Get the default taxonomy path (without last_used override)
        try:
            country = self.country_config.config['countries'].get(country_code, {})
            country_dir = self.country_config.project_root / 'countries' / country_code
            default_taxonomy = str(country_dir / country.get('files', {}).get('taxonomy', 'taxonomy.xlsx'))
        except Exception:
            default_taxonomy = ''

        # Show indicator if current file is not the default
        is_custom = current_taxonomy and default_taxonomy and \
                    os.path.normpath(current_taxonomy).lower() != os.path.normpath(default_taxonomy).lower()

        if is_custom and hasattr(self, 'custom_taxonomy_frame'):
            # Update label with file name
            filename = os.path.basename(current_taxonomy)
            self.custom_taxonomy_label.config(text=f"📁 Using: {filename}")
            self.custom_taxonomy_frame.pack(fill='x', padx=20, pady=(0, 10))
        elif hasattr(self, 'custom_taxonomy_frame'):
            self.custom_taxonomy_frame.pack_forget()

    def reset_taxonomy_to_default(self):
        """Reset taxonomy file to the default for the current country."""
        country_code = self.selected_country.get()

        # Clear the last used taxonomy from config
        if self.country_config.clear_last_used_taxonomy(country_code):
            self.log(f"Cleared custom taxonomy for {country_code}")

        # Get the default taxonomy path
        try:
            country = self.country_config.config['countries'].get(country_code, {})
            country_dir = self.country_config.project_root / 'countries' / country_code
            default_taxonomy = str(country_dir / country.get('files', {}).get('taxonomy', 'taxonomy.xlsx'))

            if os.path.exists(default_taxonomy):
                self.taxonomy_file.set(default_taxonomy)
                self.log(f"Reset to default taxonomy: {os.path.basename(default_taxonomy)}")
            else:
                self.log(f"Warning: Default taxonomy file not found: {default_taxonomy}")

        except Exception as e:
            self.log(f"Error resetting taxonomy: {e}")

        # Hide the custom indicator
        self.update_custom_taxonomy_indicator()

    def update_threshold(self, value):
        """Update threshold label."""
        self.threshold_label.config(text=f"{int(float(value))}%")

    def update_top_n(self, value):
        """Update top N label."""
        self.top_n_label.config(text=str(int(float(value))))

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
                consolidate_topics=True,  # Always use consolidated output
                include_summary=self.use_summary.get(),  # Use Summary column if checked
                top_n=self.top_n.get()
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

            # Save last used taxonomy file to config (for next session)
            taxonomy_path = self.taxonomy_file.get()
            country_code = self.selected_country.get()
            if taxonomy_path and country_code:
                if self.country_config.save_last_used_taxonomy(country_code, taxonomy_path):
                    self.log(f"Saved taxonomy file as default for {country_code}")

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

    # ==================== POST-PROCESSING METHODS ====================

    def run_post_processing(self):
        """Run post-processor on output file."""
        # Allow user to pick file or use current output
        output_path = self.output_file.get()
        if not output_path or not os.path.exists(output_path):
            output_path = filedialog.askopenfilename(
                title="Select taxonomy match output file to clean",
                filetypes=[("Excel files", "*.xlsx")]
            )
            if not output_path:
                return

        if self.is_processing:
            messagebox.showwarning("Warning", "Already processing")
            return

        self.is_processing = True
        self.postprocess_btn.config(state='disabled')
        self.progress.start(10)
        self.processing_status.config(text="🧹 Post-processing output...")
        self.status_label.config(text="Post-processing...")

        thread = threading.Thread(
            target=self._postprocess_worker, args=(output_path,), daemon=True
        )
        thread.start()

    def _postprocess_worker(self, input_path):
        """Background worker for post-processing."""
        try:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_cleaned{ext}"

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

            config = {
                'max_rank': self.top_n.get(),  # Use the Top N slider value
                'frequency_threshold': 0.20,
                'remove_low_confidence': False,
            }

            pp = PostProcessor(config)
            pp.load(input_path)
            pp.run_all()
            pp.print_stats()
            pp.export(output_path)

            sys.stdout = original_stdout

            self.root.after(0, lambda: messagebox.showinfo(
                "Post-Processing Complete",
                f"Cleaned output saved to:\n{output_path}\n\n"
                f"Rows before: {pp.stats.get('rows_before', '?')}\n"
                f"Rows after: {pp.stats.get('rows_after', '?')}\n"
                f"Removed: {pp.stats.get('rows_removed', '?')} ({pp.stats.get('pct_removed', 0):.1f}%)"
            ))

        except Exception as e:
            sys.stdout = sys.__stdout__
            self.log(f"Post-processing error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

        finally:
            self.root.after(0, self._postprocess_finish)

    def _postprocess_finish(self):
        """Finish post-processing."""
        self.progress.stop()
        self.processing_status.config(text="✓ Post-processing complete!")
        self.postprocess_btn.config(state='normal')
        self.is_processing = False
        self.status_label.config(text="Ready")
        self.root.after(3000, lambda: self.processing_status.config(text=""))

    # ==================== URL PATTERN FILTER METHODS ====================

    def show_url_pattern_dialog(self):
        """Show URL pattern filter dialog with checkboxes and preview counts."""
        # Always ask user to select file, but start in output directory if available
        initial_dir = None
        initial_file = None
        current_output = self.output_file.get()
        if current_output and os.path.exists(current_output):
            initial_dir = os.path.dirname(current_output)
            initial_file = os.path.basename(current_output)

        output_path = filedialog.askopenfilename(
            title="Select taxonomy match output file to filter",
            filetypes=[("Excel files", "*.xlsx")],
            initialdir=initial_dir,
            initialfile=initial_file
        )
        if not output_path:
            return

        if self.is_processing:
            messagebox.showwarning("Warning", "Already processing")
            return

        # Show progress on main screen
        self.is_processing = True
        self.url_pattern_btn.config(state='disabled')
        self.progress.start(10)
        self.processing_status.config(text=f"🔍 Analyzing: {os.path.basename(output_path)}...")
        self.status_label.config(text="Analyzing URL patterns...")
        self.log(f"Loading file for URL pattern analysis: {output_path}")

        # Load in background thread
        def load_and_show():
            try:
                pp = PostProcessor()
                pp.load(output_path)
                preview = pp.preview_url_patterns()
                row_count = len(pp.df)
                # Show dialog on main thread
                self.root.after(0, lambda: self._show_pattern_dialog_ui(output_path, preview, row_count))
            except Exception as e:
                self.root.after(0, lambda: self._pattern_load_error(str(e)))

        thread = threading.Thread(target=load_and_show, daemon=True)
        thread.start()

    def _pattern_load_error(self, error_msg):
        """Handle error loading file for pattern analysis."""
        self.progress.stop()
        self.processing_status.config(text="")
        self.status_label.config(text="Ready")
        self.url_pattern_btn.config(state='normal')
        self.is_processing = False
        messagebox.showerror("Error", f"Failed to load file: {error_msg}")

    def _show_pattern_dialog_ui(self, output_path, preview, row_count):
        """Show the pattern filter dialog after loading completes."""
        # Stop progress indicator
        self.progress.stop()
        self.processing_status.config(text="")
        self.status_label.config(text="Ready")
        self.url_pattern_btn.config(state='normal')
        self.is_processing = False

        # Create dialog - don't use transient to avoid affecting main window size
        dialog = tk.Toplevel(self.root)
        dialog.title("URL Pattern Filter")
        dialog.geometry("700x750")
        dialog.configure(bg=self.colors['background'])
        dialog.resizable(True, True)
        # Don't use transient - it can affect parent window state on some systems
        dialog.grab_set()
        dialog.focus_set()

        # Center the dialog without affecting main window
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (dialog.winfo_screenheight() // 2) - (750 // 2)
        # Ensure y is not negative
        if y < 0:
            y = 20
        dialog.geometry(f"700x750+{x}+{y}")

        # Header
        header = tk.Label(
            dialog,
            text="URL Pattern Filter",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        )
        header.pack(pady=(15, 5))

        # File info frame - more prominent
        file_frame = tk.Frame(dialog, bg=self.colors['primary'], padx=10, pady=8)
        file_frame.pack(fill='x', padx=20, pady=(5, 10))

        tk.Label(
            file_frame,
            text="Selected File:",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['primary'],
            fg='white'
        ).pack(side='left')

        tk.Label(
            file_frame,
            text=f"  {os.path.basename(output_path)}  ({row_count:,} rows)",
            font=('Segoe UI', 9),
            bg=self.colors['primary'],
            fg='white'
        ).pack(side='left')

        # Full path in smaller text
        tk.Label(
            dialog,
            text=output_path,
            font=('Segoe UI', 8),
            bg=self.colors['background'],
            fg=self.colors['text_light'],
            wraplength=600
        ).pack(pady=(0, 5))

        # Loading label - will be replaced with content
        loading_label = tk.Label(
            dialog,
            text="⏳ Loading pattern analysis...",
            font=('Segoe UI', 11),
            bg=self.colors['background'],
            fg=self.colors['primary']
        )
        loading_label.pack(pady=20)

        # Force dialog to display before loading patterns
        dialog.update()

        # Defer pattern loading to allow dialog to render first
        dialog.after(100, lambda: self._populate_pattern_dialog(
            dialog, output_path, preview, row_count, loading_label
        ))

    def _populate_pattern_dialog(self, dialog, output_path, preview, row_count, loading_label):
        """Populate the pattern dialog with checkboxes and controls."""
        # Remove loading label
        loading_label.destroy()

        # Instructions
        instructions = tk.Label(
            dialog,
            text="Select patterns to apply. URLs matching checked patterns will be removed.",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        )
        instructions.pack(pady=(0, 10))

        # Pattern checkboxes frame with scroll
        pattern_frame = tk.Frame(dialog, bg=self.colors['card'], relief='solid', borderwidth=1)
        pattern_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Store checkbox variables
        pattern_vars = {}
        total_count = tk.IntVar(value=0)

        def update_total():
            total = sum(preview[name]['count'] for name, var in pattern_vars.items() if var.get())
            total_count.set(total)
            total_label.config(text=f"Total URLs to remove: {total}")

        def show_sample_urls(pattern_name, pattern_desc, sample_urls, total_count):
            """Show popup with sample URLs for a pattern."""
            sample_dialog = tk.Toplevel(dialog)
            sample_dialog.title(f"Sample URLs - {pattern_desc}")
            sample_dialog.geometry("700x400")
            sample_dialog.configure(bg=self.colors['background'])
            sample_dialog.transient(dialog)
            sample_dialog.grab_set()

            # Center
            sample_dialog.update_idletasks()
            x = (sample_dialog.winfo_screenwidth() // 2) - (700 // 2)
            y = (sample_dialog.winfo_screenheight() // 2) - (400 // 2)
            sample_dialog.geometry(f"+{x}+{y}")

            # Header
            tk.Label(
                sample_dialog,
                text=f"{pattern_desc}",
                font=('Segoe UI', 12, 'bold'),
                bg=self.colors['background'],
                fg=self.colors['text']
            ).pack(pady=(15, 5))

            tk.Label(
                sample_dialog,
                text=f"Showing {len(sample_urls)} of {total_count} matching URLs",
                font=('Segoe UI', 9),
                bg=self.colors['background'],
                fg=self.colors['text_light']
            ).pack(pady=(0, 10))

            # URL list with vertical and horizontal scrollbars
            list_frame = tk.Frame(sample_dialog, bg=self.colors['background'])
            list_frame.pack(fill='both', expand=True, padx=20, pady=10)

            # Vertical scrollbar
            v_scrollbar = tk.Scrollbar(list_frame, orient='vertical')
            v_scrollbar.pack(side='right', fill='y')

            # Horizontal scrollbar
            h_scrollbar = tk.Scrollbar(list_frame, orient='horizontal')
            h_scrollbar.pack(side='bottom', fill='x')

            url_listbox = tk.Listbox(
                list_frame,
                font=('Consolas', 9),
                bg='#fafafa',
                fg=self.colors['text'],
                selectbackground=self.colors['primary'],
                relief='solid',
                borderwidth=1,
                yscrollcommand=v_scrollbar.set,
                xscrollcommand=h_scrollbar.set
            )
            url_listbox.pack(side='left', fill='both', expand=True)
            v_scrollbar.config(command=url_listbox.yview)
            h_scrollbar.config(command=url_listbox.xview)

            for url in sample_urls:
                url_listbox.insert('end', url)

            # Close button
            tk.Button(
                sample_dialog,
                text="Close",
                command=sample_dialog.destroy,
                font=('Segoe UI', 10),
                bg=self.colors['text_light'],
                fg='white',
                relief='flat',
                padx=20,
                pady=8,
                cursor='hand2'
            ).pack(pady=15)

        # Create checkboxes for each pattern
        for name, regex, desc in URL_EXCLUSION_PATTERNS:
            data = preview.get(name, {'count': 0, 'description': desc, 'sample_urls': []})
            count = data['count']
            samples = data.get('sample_urls', [])

            var = tk.BooleanVar(value=True)  # All checked by default
            pattern_vars[name] = var

            row_frame = tk.Frame(pattern_frame, bg=self.colors['card'])
            row_frame.pack(fill='x', padx=15, pady=5)

            cb = tk.Checkbutton(
                row_frame,
                text=f"{desc}",
                variable=var,
                command=update_total,
                font=('Segoe UI', 10),
                bg=self.colors['card'],
                fg=self.colors['text'],
                activebackground=self.colors['card'],
                selectcolor=self.colors['card']
            )
            cb.pack(side='left')

            count_label = tk.Label(
                row_frame,
                text=f"({count} URLs)" if count > 0 else "(0 URLs)",
                font=('Segoe UI', 9),
                bg=self.colors['card'],
                fg=self.colors['primary'] if count > 0 else self.colors['text_light']
            )
            count_label.pack(side='right')

            # Add View button if there are matching URLs
            if count > 0:
                view_btn = tk.Button(
                    row_frame,
                    text="View",
                    command=lambda n=name, d=desc, s=samples, c=count: show_sample_urls(n, d, s, c),
                    font=('Segoe UI', 8),
                    bg=self.colors['primary'],
                    fg='white',
                    relief='flat',
                    padx=8,
                    pady=2,
                    cursor='hand2'
                )
                view_btn.pack(side='right', padx=(0, 10))

        # Calculate initial total
        initial_total = sum(preview[name]['count'] for name in pattern_vars.keys())
        total_count.set(initial_total)

        # ============ CUSTOM PATTERNS SECTION ============
        custom_frame = tk.LabelFrame(
            dialog,
            text=" Custom Patterns (text contains) ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text'],
            padx=10,
            pady=10
        )
        custom_frame.pack(fill='x', padx=20, pady=(10, 5))

        # Store custom patterns: {pattern_text: {'count': N, 'var': BooleanVar, 'sample_urls': []}}
        custom_patterns = {}
        unique_urls = list(set(str(u) for u in preview.get(list(preview.keys())[0], {}).get('sample_urls', [])))
        # We need to get all URLs from the file - let's store them
        all_urls_for_custom = []
        try:
            import pandas as pd
            temp_df = pd.read_excel(output_path)
            all_urls_for_custom = [str(u) for u in temp_df['URL'].unique()]
        except:
            pass

        # Input row
        input_row = tk.Frame(custom_frame, bg=self.colors['background'])
        input_row.pack(fill='x', pady=(0, 10))

        tk.Label(
            input_row,
            text="URL contains:",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text']
        ).pack(side='left')

        custom_entry = tk.Entry(
            input_row,
            font=('Segoe UI', 10),
            width=30,
            relief='solid',
            borderwidth=1
        )
        custom_entry.pack(side='left', padx=10)

        validation_label = tk.Label(
            input_row,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        )
        validation_label.pack(side='left', padx=5)

        # Custom patterns list frame
        custom_list_frame = tk.Frame(custom_frame, bg=self.colors['background'])
        custom_list_frame.pack(fill='x')

        def validate_custom_pattern():
            """Validate custom pattern and show match count."""
            pattern_text = custom_entry.get().strip()
            if not pattern_text:
                validation_label.config(text="Enter a pattern", fg=self.colors['error'])
                return None, 0, []

            # Check for matches
            matching_urls = [url for url in all_urls_for_custom if pattern_text.lower() in url.lower()]
            count = len(matching_urls)

            if count == 0:
                validation_label.config(text="No matches found", fg=self.colors['error'])
            else:
                validation_label.config(text=f"✓ {count} URLs match", fg=self.colors['secondary'])

            return pattern_text, count, matching_urls[:20]

        def add_custom_pattern():
            """Add validated custom pattern to the list."""
            pattern_text, count, sample_urls = validate_custom_pattern()
            if not pattern_text or count == 0:
                return

            if pattern_text in custom_patterns:
                validation_label.config(text="Already added", fg=self.colors['error'])
                return

            # Add to custom patterns
            var = tk.BooleanVar(value=True)
            custom_patterns[pattern_text] = {
                'count': count,
                'var': var,
                'sample_urls': sample_urls
            }

            # Create row for this custom pattern
            row = tk.Frame(custom_list_frame, bg=self.colors['card'], relief='solid', borderwidth=1)
            row.pack(fill='x', pady=2)

            cb = tk.Checkbutton(
                row,
                text=f'Contains "{pattern_text}"',
                variable=var,
                command=update_total,
                font=('Segoe UI', 9),
                bg=self.colors['card'],
                fg=self.colors['text'],
                activebackground=self.colors['card'],
                selectcolor=self.colors['card']
            )
            cb.pack(side='left', padx=5)

            tk.Label(
                row,
                text=f"({count} URLs)",
                font=('Segoe UI', 8),
                bg=self.colors['card'],
                fg=self.colors['primary']
            ).pack(side='right', padx=5)

            # View button
            tk.Button(
                row,
                text="View",
                command=lambda p=pattern_text, s=sample_urls, c=count: show_sample_urls(
                    f"custom_{p}", f'URLs containing "{p}"', s, c
                ),
                font=('Segoe UI', 8),
                bg=self.colors['primary'],
                fg='white',
                relief='flat',
                padx=6,
                pady=1,
                cursor='hand2'
            ).pack(side='right', padx=2)

            # Remove button
            def remove_pattern(pattern=pattern_text, frame=row):
                del custom_patterns[pattern]
                frame.destroy()
                update_total()

            tk.Button(
                row,
                text="✕",
                command=remove_pattern,
                font=('Segoe UI', 8),
                bg=self.colors['error'],
                fg='white',
                relief='flat',
                padx=4,
                pady=1,
                cursor='hand2'
            ).pack(side='right', padx=2)

            # Clear entry and update total
            custom_entry.delete(0, 'end')
            validation_label.config(text="")
            update_total()

        # Buttons for custom pattern
        tk.Button(
            input_row,
            text="Validate",
            command=validate_custom_pattern,
            font=('Segoe UI', 8),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=10,
            pady=3,
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            input_row,
            text="Add",
            command=add_custom_pattern,
            font=('Segoe UI', 8),
            bg=self.colors['secondary'],
            fg='white',
            relief='flat',
            padx=10,
            pady=3,
            cursor='hand2'
        ).pack(side='left', padx=2)

        # Update the update_total function to include custom patterns
        def update_total():
            builtin_total = sum(preview[name]['count'] for name, var in pattern_vars.items() if var.get())
            custom_total = sum(data['count'] for data in custom_patterns.values() if data['var'].get())
            total = builtin_total + custom_total
            total_count.set(total)
            total_label.config(text=f"Total URLs to remove: {total}")

        # Total label
        total_label = tk.Label(
            dialog,
            text=f"Total URLs to remove: {initial_total}",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['primary']
        )
        total_label.pack(pady=10)

        # Button frame
        btn_frame = tk.Frame(dialog, bg=self.colors['background'])
        btn_frame.pack(pady=(10, 15))

        def select_all():
            for var in pattern_vars.values():
                var.set(True)
            for data in custom_patterns.values():
                data['var'].set(True)
            update_total()

        def deselect_all():
            for var in pattern_vars.values():
                var.set(False)
            for data in custom_patterns.values():
                data['var'].set(False)
            update_total()

        def apply_filter():
            enabled = [name for name, var in pattern_vars.items() if var.get()]
            # Get enabled custom patterns
            custom_enabled = [pattern for pattern, data in custom_patterns.items() if data['var'].get()]
            if not enabled and not custom_enabled:
                messagebox.showwarning("No Patterns", "Please select at least one pattern to apply")
                return
            dialog.destroy()
            self._run_url_pattern_filter(output_path, enabled, custom_enabled)

        tk.Button(
            btn_frame,
            text="Select All",
            command=select_all,
            font=('Segoe UI', 9),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame,
            text="Deselect All",
            command=deselect_all,
            font=('Segoe UI', 9),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame,
            text="Apply",
            command=apply_filter,
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=25,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=15)

        tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            font=('Segoe UI', 9),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

    def _run_url_pattern_filter(self, input_path, enabled_patterns, custom_patterns=None):
        """Run URL pattern filtering with selected patterns."""
        self.is_processing = True
        self.url_pattern_btn.config(state='disabled')
        self.progress.start(10)
        self.processing_status.config(text="🔗 Filtering URL patterns...")
        self.status_label.config(text="Filtering...")

        thread = threading.Thread(
            target=self._url_pattern_worker,
            args=(input_path, enabled_patterns, custom_patterns or []),
            daemon=True
        )
        thread.start()

    def _url_pattern_worker(self, input_path, enabled_patterns, custom_patterns):
        """Background worker for URL pattern filtering."""
        try:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_filtered{ext}"

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

            config = {
                'max_rank': self.top_n.get(),
                'frequency_threshold': 0.20,
                'remove_low_confidence': False,
            }

            pp = PostProcessor(config)
            pp.load(input_path)
            pp.run_all(url_patterns=enabled_patterns, custom_patterns=custom_patterns)
            pp.print_stats()
            pp.export(output_path)

            sys.stdout = original_stdout

            self.root.after(0, lambda: messagebox.showinfo(
                "URL Pattern Filter Complete",
                f"Filtered output saved to:\n{output_path}\n\n"
                f"Rows before: {pp.stats.get('rows_before', '?')}\n"
                f"Rows after: {pp.stats.get('rows_after', '?')}\n"
                f"Removed: {pp.stats.get('rows_removed', '?')} ({pp.stats.get('pct_removed', 0):.1f}%)"
            ))

        except Exception as e:
            sys.stdout = sys.__stdout__
            self.log(f"URL pattern filter error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

        finally:
            self.root.after(0, self._url_pattern_finish)

    def _url_pattern_finish(self):
        """Finish URL pattern filtering."""
        self.progress.stop()
        self.processing_status.config(text="✓ URL pattern filtering complete!")
        self.url_pattern_btn.config(state='normal')
        self.is_processing = False
        self.status_label.config(text="Ready")
        self.root.after(3000, lambda: self.processing_status.config(text=""))

    # ==================== REMAP URLs METHODS ====================

    def show_remap_dialog(self):
        """Show dialog for remapping filtered URLs against a new taxonomy."""
        if self.is_processing:
            messagebox.showwarning("Warning", "Already processing")
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Remap URLs with New Taxonomy")
        dialog.geometry("650x450")
        dialog.configure(bg=self.colors['background'])
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.focus_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (650 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        if y < 0:
            y = 20
        dialog.geometry(f"650x450+{x}+{y}")

        # Header
        tk.Label(
            dialog,
            text="🔄 Remap URLs with New Taxonomy",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        ).pack(pady=(15, 5))

        tk.Label(
            dialog,
            text="Re-run taxonomy matching on a filtered subset of URLs against a new taxonomy file.\n"
                 "Only URLs present in the filtered file will be processed.",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light'],
            justify='center'
        ).pack(pady=(0, 15))

        # File inputs frame
        inputs_frame = tk.Frame(dialog, bg=self.colors['card'], relief='solid', bd=1)
        inputs_frame.pack(fill='x', padx=20, pady=10)

        # Variables for file paths
        self.remap_filtered_file = tk.StringVar()
        self.remap_semantic_file = tk.StringVar()
        self.remap_taxonomy_file = tk.StringVar()
        self.remap_output_file = tk.StringVar(value='taxonomy_match_remapped.xlsx')

        # Row 1: Filtered/Cleaned file (URL source)
        row1 = tk.Frame(inputs_frame, bg=self.colors['card'])
        row1.pack(fill='x', padx=15, pady=10)

        tk.Label(
            row1,
            text="Filtered File (URL source):",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text'],
            width=22,
            anchor='w'
        ).pack(side='left')

        tk.Entry(
            row1,
            textvariable=self.remap_filtered_file,
            font=('Segoe UI', 9),
            width=40
        ).pack(side='left', padx=(0, 5))

        tk.Button(
            row1,
            text="Browse",
            command=lambda: self._browse_remap_file(self.remap_filtered_file, "Select Filtered/Cleaned File"),
            font=('Segoe UI', 8),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=10
        ).pack(side='left')

        # Row 2: Semantic carriers file (keyword source)
        row2 = tk.Frame(inputs_frame, bg=self.colors['card'])
        row2.pack(fill='x', padx=15, pady=10)

        tk.Label(
            row2,
            text="Semantic File (keywords):",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text'],
            width=22,
            anchor='w'
        ).pack(side='left')

        tk.Entry(
            row2,
            textvariable=self.remap_semantic_file,
            font=('Segoe UI', 9),
            width=40
        ).pack(side='left', padx=(0, 5))

        tk.Button(
            row2,
            text="Browse",
            command=lambda: self._browse_remap_file(self.remap_semantic_file, "Select Semantic Carriers File"),
            font=('Segoe UI', 8),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=10
        ).pack(side='left')

        # Row 3: New taxonomy file
        row3 = tk.Frame(inputs_frame, bg=self.colors['card'])
        row3.pack(fill='x', padx=15, pady=10)

        tk.Label(
            row3,
            text="New Taxonomy File:",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text'],
            width=22,
            anchor='w'
        ).pack(side='left')

        tk.Entry(
            row3,
            textvariable=self.remap_taxonomy_file,
            font=('Segoe UI', 9),
            width=40
        ).pack(side='left', padx=(0, 5))

        tk.Button(
            row3,
            text="Browse",
            command=lambda: self._browse_remap_file(self.remap_taxonomy_file, "Select New Taxonomy File"),
            font=('Segoe UI', 8),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=10
        ).pack(side='left')

        # Row 4: Output file
        row4 = tk.Frame(inputs_frame, bg=self.colors['card'])
        row4.pack(fill='x', padx=15, pady=10)

        tk.Label(
            row4,
            text="Output File:",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text'],
            width=22,
            anchor='w'
        ).pack(side='left')

        tk.Entry(
            row4,
            textvariable=self.remap_output_file,
            font=('Segoe UI', 9),
            width=40
        ).pack(side='left', padx=(0, 5))

        tk.Button(
            row4,
            text="Browse",
            command=self._browse_remap_output,
            font=('Segoe UI', 8),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=10
        ).pack(side='left')

        # Status label for URL count
        self.remap_status_label = tk.Label(
            dialog,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        )
        self.remap_status_label.pack(pady=10)

        # Buttons frame
        btn_frame = tk.Frame(dialog, bg=self.colors['background'])
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame,
            text="▶ Run Remap",
            command=lambda: self._run_remap(dialog),
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['secondary'],
            fg='white',
            relief='flat',
            padx=25,
            pady=10,
            cursor='hand2'
        ).pack(side='left', padx=10)

        tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            font=('Segoe UI', 10),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=25,
            pady=10,
            cursor='hand2'
        ).pack(side='left', padx=10)

        # Bind file selection to update status
        self.remap_filtered_file.trace_add('write', lambda *args: self._update_remap_status())
        self.remap_semantic_file.trace_add('write', lambda *args: self._update_remap_status())

    def _browse_remap_file(self, variable, title):
        """Browse for a remap input file."""
        filepath = filedialog.askopenfilename(
            title=title,
            filetypes=[("Excel files", "*.xlsx")]
        )
        if filepath:
            variable.set(filepath)

    def _browse_remap_output(self):
        """Browse for remap output file location."""
        filepath = filedialog.asksaveasfilename(
            title="Save Remapped Output As",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=self.remap_output_file.get()
        )
        if filepath:
            self.remap_output_file.set(filepath)

    def _update_remap_status(self):
        """Update status label showing URL counts."""
        filtered_path = self.remap_filtered_file.get()
        semantic_path = self.remap_semantic_file.get()

        if not filtered_path or not os.path.exists(filtered_path):
            self.remap_status_label.config(text="")
            return

        try:
            # Count URLs in filtered file
            df_filtered = pd.read_excel(filtered_path, usecols=['URL'])
            filtered_urls = set(df_filtered['URL'].dropna().unique())
            msg = f"📊 Filtered file: {len(filtered_urls):,} unique URLs"

            # If semantic file also selected, show overlap
            if semantic_path and os.path.exists(semantic_path):
                df_semantic = pd.read_excel(semantic_path, usecols=['URL'])
                semantic_urls = set(df_semantic['URL'].dropna().unique())
                overlap = filtered_urls & semantic_urls
                msg += f"  |  Semantic file: {len(semantic_urls):,} URLs  |  Match: {len(overlap):,} URLs"

            self.remap_status_label.config(text=msg, fg=self.colors['primary'])
        except Exception as e:
            self.remap_status_label.config(text=f"Error reading file: {str(e)}", fg=self.colors['error'])

    def _run_remap(self, dialog):
        """Validate inputs and run the remap process."""
        filtered_path = self.remap_filtered_file.get()
        semantic_path = self.remap_semantic_file.get()
        taxonomy_path = self.remap_taxonomy_file.get()
        output_path = self.remap_output_file.get()

        # Validate inputs
        errors = []
        if not filtered_path or not os.path.exists(filtered_path):
            errors.append("Please select a valid filtered file")
        if not semantic_path or not os.path.exists(semantic_path):
            errors.append("Please select a valid semantic carriers file")
        if not taxonomy_path or not os.path.exists(taxonomy_path):
            errors.append("Please select a valid taxonomy file")
        if not output_path:
            errors.append("Please specify an output file")

        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return

        # Close dialog
        dialog.destroy()

        # Start processing
        self.is_processing = True
        self.remap_btn.config(state='disabled')
        self.progress.start(10)
        self.processing_status.config(text="🔄 Remapping URLs with new taxonomy...")
        self.status_label.config(text="Remapping...")
        self.clear_log()

        thread = threading.Thread(
            target=self._remap_worker,
            args=(filtered_path, semantic_path, taxonomy_path, output_path),
            daemon=True
        )
        thread.start()

    def _remap_worker(self, filtered_path, semantic_path, taxonomy_path, output_path):
        """Background worker for remap process."""
        try:
            self.log("=" * 50)
            self.log("Starting URL Remap Process")
            self.log("=" * 50)

            # Step 1: Load URLs from filtered file
            self.log(f"\n[1/4] Loading URLs from filtered file...")
            self.log(f"  File: {os.path.basename(filtered_path)}")
            df_filtered = pd.read_excel(filtered_path)
            filtered_urls = set(df_filtered['URL'].dropna().unique())
            self.log(f"  Found {len(filtered_urls):,} unique URLs to process")

            # Step 2: Load semantic carriers and filter to matching URLs
            self.log(f"\n[2/4] Loading and filtering semantic carriers...")
            self.log(f"  File: {os.path.basename(semantic_path)}")
            df_semantic = pd.read_excel(semantic_path)
            original_count = len(df_semantic)
            self.log(f"  Original rows: {original_count:,}")

            # Filter to only URLs in the filtered file
            df_semantic_filtered = df_semantic[df_semantic['URL'].isin(filtered_urls)].copy()
            self.log(f"  After filtering: {len(df_semantic_filtered):,} rows")

            if len(df_semantic_filtered) == 0:
                raise ValueError("No matching URLs found between filtered file and semantic file")

            # Step 3: Create temporary filtered semantic file
            self.log(f"\n[3/4] Creating temporary filtered semantic file...")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False) as tmp:
                temp_semantic_path = tmp.name

            df_semantic_filtered.to_excel(temp_semantic_path, index=False)
            self.log(f"  Temporary file created with {len(df_semantic_filtered):,} rows")

            # Step 4: Run matching with new taxonomy
            self.log(f"\n[4/4] Running taxonomy matching...")
            self.log(f"  Taxonomy: {os.path.basename(taxonomy_path)}")

            # Redirect stdout to capture matcher output
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

            matcher = TaxonomyMatcher(
                country_code=self.selected_country.get(),
                semantic_file=temp_semantic_path,
                taxonomy_file=taxonomy_path,
                output_file=output_path,
                similarity_threshold=self.threshold.get(),
                consolidate_topics=True,
                include_summary=self.use_summary.get(),
                top_n=self.top_n.get()
            )
            matcher.run()

            sys.stdout = original_stdout

            # Cleanup temp file
            try:
                os.unlink(temp_semantic_path)
            except:
                pass

            self.log("\n" + "=" * 50)
            self.log("✓ Remap completed successfully!")
            self.log(f"  Output: {output_path}")
            self.log("=" * 50)

            self.root.after(0, lambda: messagebox.showinfo(
                "Remap Complete",
                f"URL remapping completed!\n\n"
                f"URLs processed: {len(filtered_urls):,}\n"
                f"Output saved to:\n{output_path}"
            ))

        except Exception as e:
            sys.stdout = sys.__stdout__
            self.log(f"\n❌ Error during remap: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Remap Error", str(e)))

        finally:
            self.root.after(0, self._remap_finish)

    def _remap_finish(self):
        """Finish remap processing."""
        self.progress.stop()
        self.processing_status.config(text="✓ URL remap complete!")
        self.remap_btn.config(state='normal')
        self.is_processing = False
        self.status_label.config(text="Ready")
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
            exportselection=False,
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
            exportselection=False,
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

        self.import_taxonomy_btn = tk.Button(
            topic_card,
            text="📥 Import from Taxonomy",
            command=self.import_topics_from_taxonomy,
            bg='#8b5cf6',  # Purple
            fg='white',
            **btn_style
        )
        self.import_taxonomy_btn.pack(padx=20, pady=5)
        ToolTip(self.import_taxonomy_btn, "Import missing topics from taxonomy file")

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

    def import_topics_from_taxonomy(self):
        """Import missing topics from a taxonomy file."""
        # Check if synonyms are loaded
        if not self.current_synonyms:
            messagebox.showwarning("No Synonyms Loaded", "Please load synonyms first by selecting a country.")
            return

        # Ask user to select taxonomy file
        taxonomy_path = filedialog.askopenfilename(
            title="Select Taxonomy File to Import Topics From",
            filetypes=[("Excel files", "*.xlsx")],
            initialdir=os.path.dirname(self.taxonomy_file.get()) if self.taxonomy_file.get() else None
        )

        if not taxonomy_path:
            return

        try:
            # Load taxonomy and extract all unique topics
            self.log(f"Loading taxonomy: {os.path.basename(taxonomy_path)}")
            df_taxonomy = pd.read_excel(taxonomy_path)

            # Find all Topic columns
            topic_cols = [col for col in df_taxonomy.columns if col.startswith('Topic')]
            if not topic_cols:
                messagebox.showerror("Invalid Taxonomy", "No Topic columns found in taxonomy file")
                return

            # Extract all unique topics
            taxonomy_topics = set()
            for col in topic_cols:
                for val in df_taxonomy[col].dropna():
                    topic = str(val).strip()
                    if topic:
                        taxonomy_topics.add(topic)

            self.log(f"Found {len(taxonomy_topics)} unique topics in taxonomy")

            # Get current synonym topics
            synonyms_dict = self.get_synonyms_dict()
            current_topics = set(synonyms_dict.keys())

            # Find missing topics (case-insensitive comparison)
            current_topics_lower = {t.lower(): t for t in current_topics}
            missing_topics = []
            for topic in sorted(taxonomy_topics):
                if topic.lower() not in current_topics_lower:
                    missing_topics.append(topic)

            if not missing_topics:
                messagebox.showinfo("No Missing Topics",
                    f"All {len(taxonomy_topics)} topics from taxonomy are already in synonyms file.")
                return

            self.log(f"Found {len(missing_topics)} topics missing from synonyms")

            # Show dialog to select which topics to import
            self._show_import_topics_dialog(missing_topics, len(taxonomy_topics))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load taxonomy: {str(e)}")
            self.log(f"Error loading taxonomy: {str(e)}")

    def _show_import_topics_dialog(self, missing_topics, total_taxonomy_topics):
        """Show dialog to select which missing topics to import."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Import Missing Topics")
        dialog.geometry("500x600")
        dialog.configure(bg=self.colors['background'])
        dialog.grab_set()
        dialog.focus_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"500x600+{x}+{y}")

        # Header
        tk.Label(
            dialog,
            text="📥 Import Missing Topics",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['background'],
            fg=self.colors['text']
        ).pack(pady=(15, 5))

        tk.Label(
            dialog,
            text=f"Found {len(missing_topics)} topics in taxonomy that are not in synonyms file.\n"
                 f"(Taxonomy has {total_taxonomy_topics} total topics)",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        ).pack(pady=(0, 10))

        # Select all / Deselect all buttons
        btn_frame = tk.Frame(dialog, bg=self.colors['background'])
        btn_frame.pack(fill='x', padx=20, pady=5)

        # Track checkboxes
        topic_vars = {}

        def select_all():
            for var in topic_vars.values():
                var.set(True)

        def deselect_all():
            for var in topic_vars.values():
                var.set(False)

        tk.Button(
            btn_frame,
            text="Select All",
            command=select_all,
            font=('Segoe UI', 9),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=10
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame,
            text="Deselect All",
            command=deselect_all,
            font=('Segoe UI', 9),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=10
        ).pack(side='left', padx=5)

        # Scrollable frame for checkboxes
        container = tk.Frame(dialog, bg=self.colors['card'], relief='solid', bd=1)
        container.pack(fill='both', expand=True, padx=20, pady=10)

        canvas = tk.Canvas(container, bg=self.colors['card'], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['card'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Create checkboxes for each topic (all selected by default)
        for topic in missing_topics:
            var = tk.BooleanVar(value=True)
            topic_vars[topic] = var

            cb = tk.Checkbutton(
                scrollable_frame,
                text=topic,
                variable=var,
                font=('Segoe UI', 9),
                bg=self.colors['card'],
                fg=self.colors['text'],
                selectcolor=self.colors['card'],
                activebackground=self.colors['card'],
                anchor='w'
            )
            cb.pack(fill='x', padx=10, pady=2)

        # Import button
        def do_import():
            selected = [topic for topic, var in topic_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("No Selection", "Please select at least one topic to import.")
                return

            # Add selected topics to synonyms
            synonyms_dict = self.get_synonyms_dict()
            added_count = 0
            for topic in selected:
                if topic not in synonyms_dict:
                    synonyms_dict[topic] = []
                    self.all_topics.append(topic)
                    added_count += 1

            # Sort and refresh
            self.all_topics.sort()
            self.populate_topic_list(self.all_topics)
            self.update_statistics()
            self.mark_as_changed()

            self.log(f"Imported {added_count} topics from taxonomy")
            dialog.destroy()

            messagebox.showinfo("Import Complete",
                f"Successfully imported {added_count} topics.\n\n"
                f"Remember to save changes to persist them.")

        # Bottom buttons
        bottom_frame = tk.Frame(dialog, bg=self.colors['background'])
        bottom_frame.pack(fill='x', padx=20, pady=15)

        tk.Button(
            bottom_frame,
            text="📥 Import Selected",
            command=do_import,
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['secondary'],
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

        tk.Button(
            bottom_frame,
            text="Cancel",
            command=dialog.destroy,
            font=('Segoe UI', 10),
            bg=self.colors['text_light'],
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        ).pack(side='left', padx=5)

        # Selection count label
        count_label = tk.Label(
            bottom_frame,
            text=f"{len(missing_topics)} selected",
            font=('Segoe UI', 9),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        )
        count_label.pack(side='right', padx=10)

        def update_count(*args):
            selected_count = sum(1 for var in topic_vars.values() if var.get())
            count_label.config(text=f"{selected_count} selected")

        # Bind count update to each checkbox
        for var in topic_vars.values():
            var.trace_add('write', update_count)

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

    def generate_quality_report(self):
        """Generate match quality report with similarity scores and rankings per URL."""
        from fuzzywuzzy import fuzz
        from collections import defaultdict

        # 1. Validate files are selected
        semantic_file = self.semantic_file.get()
        taxonomy_file = self.taxonomy_file.get()

        if not semantic_file or not os.path.exists(semantic_file):
            messagebox.showerror("Error", "Please select a valid Semantic Carriers file in Setup tab")
            return

        if not taxonomy_file or not os.path.exists(taxonomy_file):
            messagebox.showerror("Error", "Please select a valid Taxonomy file in Setup tab")
            return

        # Get Top N value
        try:
            top_n = int(self.top_n_var.get())
            if top_n < 1:
                top_n = 3
        except ValueError:
            top_n = 3

        # Get threshold from GUI
        try:
            threshold = int(self.threshold_var.get())
        except (ValueError, AttributeError):
            threshold = 80

        # Update status
        self.quality_report_status_label.config(text="Loading data...", fg=self.colors['primary'])
        self.root.update()

        try:
            # Load synonyms for current country
            country_code = self.selected_country.get()
            synonyms = self.country_config.load_synonyms(country_code)
            self.log(f"Loaded {len(synonyms)} synonym mappings for {country_code}")

            # Load semantic carriers
            self.log("Loading semantic carriers file...")
            sem_df = pd.read_excel(semantic_file)
            self.log(f"  Loaded {len(sem_df)} URLs")

            # Load taxonomy
            self.log("Loading taxonomy file...")
            tax_df = pd.read_excel(taxonomy_file)

            # Build taxonomy lookup (same as TaxonomyMatcher)
            topic_columns = [col for col in tax_df.columns if col.startswith('Topic')]
            self.log(f"  Detected {len(topic_columns)} topic columns")

            taxonomy_lookup = []
            for idx, row in tax_df.iterrows():
                product = row.get('Product', '')
                domain = row.get('Domain', '')
                segment = row.get('Segment', '')

                for topic_col in topic_columns:
                    topic = row.get(topic_col, '')
                    if pd.notna(topic) and topic.strip():
                        taxonomy_lookup.append({
                            'product': product if pd.notna(product) else '',
                            'domain': domain if pd.notna(domain) else '',
                            'segment': segment if pd.notna(segment) else '',
                            'topic': topic.strip()
                        })

            self.log(f"  Created {len(taxonomy_lookup)} searchable topic entries")

            # Helper function: expand keyword with synonyms
            def expand_with_synonyms(keyword):
                variations = [keyword.lower().strip()]
                keyword_lower = keyword.lower().strip()

                for key, syns in synonyms.items():
                    if key.startswith('_'):
                        continue
                    key_lower = key.lower()

                    if key_lower in keyword_lower:
                        variations.extend([s.lower() for s in syns])

                    for syn in syns:
                        syn_lower = syn.lower()
                        if syn_lower == keyword_lower or syn_lower in keyword_lower:
                            variations.append(key_lower)
                            break

                return list(set(variations))

            # Process matching with detailed tracking
            self.quality_report_status_label.config(text="Processing matches...", fg=self.colors['primary'])
            self.root.update()

            all_matches = []
            total_urls = len(sem_df)

            for idx, row in sem_df.iterrows():
                url = row.get('URL', '')

                # Extract keywords
                keywords = []
                for i in range(1, 11):
                    col_name = f'Keyword {i}'
                    if col_name in row.index and pd.notna(row[col_name]):
                        keywords.append(str(row[col_name]).strip())

                # Track unique matches for this URL (for deduplication)
                url_matches = {}  # (product, domain, segment, topic) -> best match info

                # Process each keyword
                for keyword in keywords:
                    keyword_variations = expand_with_synonyms(keyword)

                    for tax_entry in taxonomy_lookup:
                        topic = tax_entry['topic'].lower()
                        max_score = 0

                        for variation in keyword_variations:
                            score = fuzz.ratio(variation, topic)
                            max_score = max(max_score, score)

                        if max_score >= threshold:
                            combo_key = (tax_entry['product'], tax_entry['domain'],
                                        tax_entry['segment'], tax_entry['topic'])

                            # Keep best score per unique match
                            if combo_key not in url_matches or max_score > url_matches[combo_key]['score']:
                                url_matches[combo_key] = {
                                    'score': max_score,
                                    'keyword': keyword
                                }

                # Convert url_matches to results
                for (product, domain, segment, topic), match_info in url_matches.items():
                    all_matches.append({
                        'URL': url,
                        'Product': product,
                        'Domain': domain,
                        'Segment': segment,
                        'Topic': topic,
                        'Similarity_Score': match_info['score'],
                        'Matched_Keyword': match_info['keyword']
                    })

                # Progress indicator
                if (idx + 1) % 100 == 0:
                    self.quality_report_status_label.config(
                        text=f"Processing {idx + 1}/{total_urls}...",
                        fg=self.colors['primary']
                    )
                    self.root.update()

            self.log(f"Found {len(all_matches)} total matches")

            # Create DataFrame and add rankings
            df_all = pd.DataFrame(all_matches)

            if len(df_all) == 0:
                messagebox.showwarning("No Matches", "No matches found. Try lowering the threshold.")
                self.quality_report_status_label.config(text="No matches", fg=self.colors['text_light'])
                return

            # Sort by URL and Score (descending) to calculate rankings
            df_all = df_all.sort_values(['URL', 'Similarity_Score'], ascending=[True, False])

            # Add ranking per URL
            df_all['Rank_In_URL'] = df_all.groupby('URL').cumcount() + 1

            # Calculate the best score per URL for relative comparison
            best_scores = df_all.groupby('URL')['Similarity_Score'].transform('max')
            df_all['Score_Gap'] = best_scores - df_all['Similarity_Score']

            # Add Relevance column based on rank and score
            def calculate_relevance(row):
                rank = row['Rank_In_URL']
                score = row['Similarity_Score']
                score_gap = row['Score_Gap']

                if rank == 1:
                    return 'Best Match'
                elif rank <= 3 and score >= 90:
                    return 'Highly Relevant'
                elif rank <= 3 and score >= 85:
                    return 'Relevant'
                elif score >= 90:
                    return 'Relevant'
                elif score >= 85 and score_gap <= 10:
                    return 'Somewhat Relevant'
                elif score >= 85:
                    return 'Tangential'
                elif score_gap <= 5:
                    return 'Moderate'
                elif score_gap <= 10:
                    return 'Weak'
                else:
                    return 'Low Relevance'

            df_all['Relevance'] = df_all.apply(calculate_relevance, axis=1)

            # Drop the temporary Score_Gap column and reorder columns
            df_all = df_all.drop('Score_Gap', axis=1)
            df_all = df_all[['URL', 'Product', 'Domain', 'Segment', 'Topic',
                            'Similarity_Score', 'Matched_Keyword', 'Rank_In_URL', 'Relevance']]

            # Ask for save location
            self.quality_report_status_label.config(text="Saving...", fg=self.colors['primary'])
            self.root.update()

            output_file = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"Match_Quality_Report_{country_code}.xlsx",
                title="Save Match Quality Report As"
            )

            if not output_file:
                self.quality_report_status_label.config(text="Cancelled", fg=self.colors['text_light'])
                return

            self.log(f"Saving report to {output_file}...")

            # Save to Excel with multiple sheets
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet 1: All Matches with Scores
                df_all.to_excel(writer, sheet_name='All Matches', index=False)

                # Sheet 2: Top N Per URL
                df_top_n = df_all[df_all['Rank_In_URL'] <= top_n].copy()
                df_top_n.to_excel(writer, sheet_name=f'Top {top_n} Per URL', index=False)

                # Sheet 3: Match Statistics per URL
                stats = df_all.groupby('URL').agg({
                    'Similarity_Score': ['count', 'max', 'mean', 'min'],
                    'Segment': 'nunique'
                }).reset_index()
                stats.columns = ['URL', 'Total_Matches', 'Top_Score', 'Avg_Score', 'Min_Score', 'Unique_Segments']
                stats['Score_Spread'] = stats['Top_Score'] - stats['Min_Score']
                stats['Avg_Score'] = stats['Avg_Score'].round(1)
                stats = stats.sort_values('Total_Matches', ascending=False)
                stats.to_excel(writer, sheet_name='Match Statistics', index=False)

                # Sheet 4: Low Confidence Matches (80-85%)
                df_low_conf = df_all[(df_all['Similarity_Score'] >= threshold) &
                                     (df_all['Similarity_Score'] <= threshold + 5)].copy()
                df_low_conf = df_low_conf.sort_values('Similarity_Score')
                df_low_conf.to_excel(writer, sheet_name='Low Confidence', index=False)

                # Sheet 5: Relevance Summary
                relevance_order = ['Best Match', 'Highly Relevant', 'Relevant', 'Somewhat Relevant',
                                   'Tangential', 'Moderate', 'Weak', 'Low Relevance']
                relevance_counts = df_all['Relevance'].value_counts()
                relevance_summary = pd.DataFrame({
                    'Relevance': relevance_order,
                    'Count': [relevance_counts.get(r, 0) for r in relevance_order],
                    'Percentage': [f"{relevance_counts.get(r, 0) / len(df_all) * 100:.1f}%" for r in relevance_order],
                    'Description': [
                        'Rank 1 - highest score for this URL',
                        'Rank 2-3 with score >= 90%',
                        'Rank 2-3 with score >= 85% OR score >= 90%',
                        'Score >= 85% and within 10 points of best',
                        'Score >= 85% but far from best score',
                        'Score < 85% but within 5 points of best',
                        'Score < 85% and within 10 points of best',
                        'Score far below the best match for this URL'
                    ]
                })
                relevance_summary.to_excel(writer, sheet_name='Relevance Summary', index=False)

            # Calculate summary stats
            urls_with_matches = df_all['URL'].nunique()
            avg_matches_per_url = len(df_all) / urls_with_matches if urls_with_matches > 0 else 0
            low_conf_count = len(df_low_conf)

            self.log(f"Report saved successfully!")
            self.log(f"  - Total matches: {len(df_all)}")
            self.log(f"  - URLs with matches: {urls_with_matches}")
            self.log(f"  - Avg matches per URL: {avg_matches_per_url:.1f}")
            self.log(f"  - Top {top_n} matches: {len(df_top_n)}")
            self.log(f"  - Low confidence ({threshold}-{threshold+5}%): {low_conf_count}")

            self.quality_report_status_label.config(text="Complete!", fg=self.colors['secondary'])
            messagebox.showinfo("Success", f"Report saved to:\n{output_file}\n\n"
                                           f"Total matches: {len(df_all)}\n"
                                           f"URLs analyzed: {urls_with_matches}\n"
                                           f"Avg matches/URL: {avg_matches_per_url:.1f}\n"
                                           f"Top {top_n} matches: {len(df_top_n)}")

        except Exception as e:
            self.log(f"ERROR generating quality report: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.quality_report_status_label.config(text="Error", fg=self.colors['error'])
            messagebox.showerror("Error", f"Failed to generate report:\n{e}")

    def generate_unmapped_report(self):
        """Generate diagnostic report explaining why URLs are unmapped."""
        from fuzzywuzzy import fuzz
        from collections import Counter, defaultdict

        # 1. Validate files are selected
        semantic_file = self.semantic_file.get()
        taxonomy_file = self.taxonomy_file.get()

        if not semantic_file or not os.path.exists(semantic_file):
            messagebox.showerror("Error", "Please select a valid Semantic Carriers file in Setup tab")
            return

        if not taxonomy_file or not os.path.exists(taxonomy_file):
            messagebox.showerror("Error", "Please select a valid Taxonomy file in Setup tab")
            return

        # Get threshold from GUI
        try:
            threshold = int(self.threshold_var.get())
        except (ValueError, AttributeError):
            threshold = 80

        country_code = self.selected_country.get()

        # Update status
        self.unmapped_report_status_label.config(text="Analyzing unmapped URLs...", fg=self.colors['primary'])
        self.root.update()

        try:
            # Load synonyms
            existing_synonyms = self.country_config.load_synonyms(country_code)
            self.log(f"Loaded {len(existing_synonyms)} synonym mappings for {country_code}")

            # Load semantic file
            self.log("Loading semantic carriers file...")
            sem_df = pd.read_excel(semantic_file)
            self.log(f"Loaded {len(sem_df)} URLs")

            # Load taxonomy
            self.log("Loading taxonomy file...")
            tax_df = pd.read_excel(taxonomy_file)
            topic_cols = [c for c in tax_df.columns if c.startswith('Topic')]

            # Build flat taxonomy list
            taxonomy_entries = []
            for _, row in tax_df.iterrows():
                product = str(row.get('Product', '')).strip()
                domain = str(row.get('Domain', '')).strip()
                segment = str(row.get('Segment', '')).strip()
                for col in topic_cols:
                    val = row.get(col)
                    if pd.notna(val):
                        topic = str(val).strip()
                        taxonomy_entries.append({
                            'product': product,
                            'domain': domain,
                            'segment': segment,
                            'topic': topic
                        })

            self.log(f"Built {len(taxonomy_entries)} taxonomy topic entries")

            # Helper function: expand keyword with synonyms
            def expand_with_synonyms(keyword):
                variations = [keyword]
                kw_lower = keyword.lower()
                for topic, syns in existing_synonyms.items():
                    topic_lower = topic.lower()
                    # If keyword contains topic name, add synonyms
                    if topic_lower in kw_lower:
                        variations.extend(syns)
                    # If keyword matches a synonym, add the topic
                    for syn in syns:
                        if syn.lower() == kw_lower or syn.lower() in kw_lower:
                            variations.append(topic)
                return list(set(variations))

            # Helper function: check product filter
            def should_match_product(semantic_product, taxonomy_product):
                if not taxonomy_product or taxonomy_product.strip() == '':
                    return True  # Empty taxonomy product matches all
                if str(taxonomy_product).strip().lower() == 'something else':
                    return True  # "Something Else" is a generic/wildcard product
                if not semantic_product or semantic_product.strip() == '':
                    return True
                if str(semantic_product).lower() == 'other':
                    return True
                return str(semantic_product).strip().lower() == str(taxonomy_product).strip().lower()

            # Analyze each URL
            self.log("Analyzing URLs for unmapped reasons...")
            unmapped_summary = []
            detailed_analysis = []
            product_filter_data = []
            keyword_stats = defaultdict(lambda: {'count': 0, 'best_score': 0, 'best_topic': ''})

            total_urls = len(sem_df)
            for idx, row in sem_df.iterrows():
                if idx > 0 and idx % 100 == 0:
                    self.log(f"  Processed {idx}/{total_urls} URLs...")
                    self.unmapped_report_status_label.config(
                        text=f"Analyzing... {idx}/{total_urls}",
                        fg=self.colors['primary']
                    )
                    self.root.update()

                url = str(row.get('URL', ''))
                semantic_product = str(row.get('Product', ''))

                # Extract keywords
                keywords = []
                for i in range(1, 16):
                    col = f'Keyword {i}'
                    if col in row and pd.notna(row[col]):
                        keywords.append(str(row[col]).strip())

                if not keywords:
                    continue

                # Track best match for this URL
                best_overall = {'score': 0, 'topic': '', 'keyword': '', 'product': '', 'domain': '', 'segment': ''}
                product_blocked_count = 0
                product_blocked_examples = []
                keyword_scores = []

                for keyword in keywords:
                    variations = expand_with_synonyms(keyword)
                    best_for_keyword = {'score': 0, 'topic': '', 'blocked': False}

                    for entry in taxonomy_entries:
                        # Check product filter
                        product_match = should_match_product(semantic_product, entry['product'])

                        # Calculate best score across variations
                        max_score = 0
                        for var in variations:
                            score = fuzz.ratio(var.lower(), entry['topic'].lower())
                            max_score = max(max_score, score)

                        if not product_match and max_score >= threshold:
                            product_blocked_count += 1
                            if len(product_blocked_examples) < 3:
                                product_blocked_examples.append({
                                    'topic': entry['topic'],
                                    'topic_product': entry['product'],
                                    'score': max_score
                                })

                        if product_match:
                            if max_score > best_for_keyword['score']:
                                best_for_keyword = {'score': max_score, 'topic': entry['topic'], 'blocked': False}

                            if max_score > best_overall['score']:
                                best_overall = {
                                    'score': max_score,
                                    'topic': entry['topic'],
                                    'keyword': keyword,
                                    'product': entry['product'],
                                    'domain': entry['domain'],
                                    'segment': entry['segment']
                                }

                    keyword_scores.append({
                        'keyword': keyword,
                        'best_score': best_for_keyword['score'],
                        'best_topic': best_for_keyword['topic']
                    })

                    # Update keyword statistics
                    kw_lower = keyword.lower()
                    keyword_stats[kw_lower]['count'] += 1
                    if best_for_keyword['score'] > keyword_stats[kw_lower]['best_score']:
                        keyword_stats[kw_lower]['best_score'] = best_for_keyword['score']
                        keyword_stats[kw_lower]['best_topic'] = best_for_keyword['topic']

                # Determine if URL is unmapped (best score < threshold)
                if best_overall['score'] < threshold:
                    # Determine failure reason
                    if best_overall['score'] < 50:
                        reason = 'NO_SIMILAR_TOPICS'
                        recommendation = f"Add new taxonomy topic related to keywords: {', '.join(keywords[:3])}"
                    elif product_blocked_count > 0 and product_blocked_examples:
                        reason = 'PRODUCT_FILTER'
                        blocked_ex = product_blocked_examples[0]
                        recommendation = f"Add topic '{blocked_ex['topic']}' to product '{semantic_product}' OR add generic row with empty Product"
                    elif best_overall['score'] >= threshold - 10:
                        reason = 'BELOW_THRESHOLD'
                        recommendation = f"Lower threshold to {best_overall['score']}% OR add synonym '{best_overall['keyword']}' to topic '{best_overall['topic']}'"
                    else:
                        reason = 'TAXONOMY_GAP'
                        recommendation = f"Add synonym '{best_overall['keyword']}' to closest topic '{best_overall['topic']}' (score: {best_overall['score']}%)"

                    # Add to summary
                    unmapped_summary.append({
                        'URL': url,
                        'Product': semantic_product,
                        'Best_Score': best_overall['score'],
                        'Best_Topic': best_overall['topic'],
                        'Best_Keyword': best_overall['keyword'],
                        'Failure_Reason': reason,
                        'Recommendation': recommendation,
                        'Keywords_Count': len(keywords),
                        'Product_Filter_Blocked': product_blocked_count
                    })

                    # Add detailed analysis for each keyword
                    for ks in keyword_scores:
                        gap = threshold - ks['best_score']
                        detailed_analysis.append({
                            'URL': url,
                            'Keyword': ks['keyword'],
                            'Best_Topic_Match': ks['best_topic'],
                            'Score': ks['best_score'],
                            'Threshold': threshold,
                            'Gap': gap,
                            'Would_Match_At': f"{ks['best_score']}%" if ks['best_score'] > 0 else 'N/A'
                        })

                    # Add product filter data
                    if product_blocked_count > 0:
                        for blocked in product_blocked_examples:
                            product_filter_data.append({
                                'URL': url,
                                'Semantic_Product': semantic_product,
                                'Blocked_Topic': blocked['topic'],
                                'Topic_Product': blocked['topic_product'],
                                'Would_Score': blocked['score']
                            })

            # Create DataFrames
            df_summary = pd.DataFrame(unmapped_summary)
            df_detailed = pd.DataFrame(detailed_analysis)
            df_product_filter = pd.DataFrame(product_filter_data)

            # Create synonym suggestions from keyword stats
            synonym_suggestions = []
            for kw, stats in keyword_stats.items():
                if stats['count'] >= 3 and 50 <= stats['best_score'] < threshold:
                    synonym_suggestions.append({
                        'Keyword': kw,
                        'Frequency': stats['count'],
                        'Best_Topic': stats['best_topic'],
                        'Score': stats['best_score'],
                        'Suggested_Action': f"Add '{kw}' as synonym to '{stats['best_topic']}'"
                    })

            df_synonyms = pd.DataFrame(synonym_suggestions)
            if len(df_synonyms) > 0:
                df_synonyms = df_synonyms.sort_values('Frequency', ascending=False)

            # Calculate statistics
            total_unmapped = len(df_summary)
            reason_counts = df_summary['Failure_Reason'].value_counts().to_dict() if len(df_summary) > 0 else {}

            stats_data = [
                {'Metric': 'Total URLs Analyzed', 'Value': total_urls},
                {'Metric': 'Unmapped URLs', 'Value': total_unmapped},
                {'Metric': 'Unmapped Percentage', 'Value': f"{total_unmapped/total_urls*100:.1f}%" if total_urls > 0 else '0%'},
                {'Metric': 'Threshold Used', 'Value': f"{threshold}%"},
                {'Metric': '', 'Value': ''},
                {'Metric': 'Failure Reasons Breakdown:', 'Value': ''},
            ]
            for reason, count in reason_counts.items():
                stats_data.append({'Metric': f"  - {reason}", 'Value': count})

            if len(df_summary) > 0:
                avg_best_score = df_summary['Best_Score'].mean()
                stats_data.append({'Metric': '', 'Value': ''})
                stats_data.append({'Metric': 'Average Best Score (unmapped)', 'Value': f"{avg_best_score:.1f}%"})

                # Threshold recommendation
                if avg_best_score >= threshold - 10:
                    recommended_threshold = int(avg_best_score) - 5
                    stats_data.append({'Metric': 'Recommended Threshold', 'Value': f"{recommended_threshold}% (would match more URLs)"})

            df_stats = pd.DataFrame(stats_data)

            # Ask for save location
            self.unmapped_report_status_label.config(text="Saving...", fg=self.colors['primary'])
            self.root.update()

            output_file = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"Unmapped_Reasons_Report_{country_code}.xlsx",
                title="Save Unmapped Reasons Report As"
            )

            if not output_file:
                self.unmapped_report_status_label.config(text="Cancelled", fg=self.colors['text_light'])
                return

            self.log(f"Saving report to {output_file}...")

            # Save to Excel with multiple sheets
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet 1: Unmapped Summary
                if len(df_summary) > 0:
                    df_summary.to_excel(writer, sheet_name='Unmapped Summary', index=False)
                else:
                    pd.DataFrame({'Message': ['No unmapped URLs found!']}).to_excel(writer, sheet_name='Unmapped Summary', index=False)

                # Sheet 2: Detailed Analysis
                if len(df_detailed) > 0:
                    df_detailed.to_excel(writer, sheet_name='Detailed Analysis', index=False)
                else:
                    pd.DataFrame({'Message': ['No detailed analysis data']}).to_excel(writer, sheet_name='Detailed Analysis', index=False)

                # Sheet 3: Product Filter Impact
                if len(df_product_filter) > 0:
                    df_product_filter.to_excel(writer, sheet_name='Product Filter Impact', index=False)
                else:
                    pd.DataFrame({'Message': ['No product filter blocks detected']}).to_excel(writer, sheet_name='Product Filter Impact', index=False)

                # Sheet 4: Synonym Suggestions
                if len(df_synonyms) > 0:
                    df_synonyms.to_excel(writer, sheet_name='Synonym Suggestions', index=False)
                else:
                    pd.DataFrame({'Message': ['No synonym suggestions - keywords are too different from topics']}).to_excel(writer, sheet_name='Synonym Suggestions', index=False)

                # Sheet 5: Statistics
                df_stats.to_excel(writer, sheet_name='Statistics', index=False)

            self.log(f"Report saved successfully!")
            self.log(f"  - Unmapped URLs analyzed: {total_unmapped}")
            self.log(f"  - Failure reasons: {reason_counts}")
            self.log(f"  - Synonym suggestions: {len(df_synonyms)}")

            self.unmapped_report_status_label.config(text="Complete!", fg=self.colors['secondary'])

            # Build reason breakdown string
            reason_str = "\n".join([f"  {r}: {c}" for r, c in reason_counts.items()])

            messagebox.showinfo("Success", f"Report saved to:\n{output_file}\n\n"
                                           f"Unmapped URLs: {total_unmapped}\n"
                                           f"Synonym suggestions: {len(df_synonyms)}\n\n"
                                           f"Failure reasons:\n{reason_str}")

        except Exception as e:
            self.log(f"ERROR generating unmapped report: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.unmapped_report_status_label.config(text="Error", fg=self.colors['error'])
            messagebox.showerror("Error", f"Failed to generate report:\n{e}")

    # ==================== TOPIC RECOMMENDATIONS REPORT METHODS ====================

    def _browse_topic_rec_file(self, variable, title):
        """Browse for input file for topic recommendations report."""
        file = filedialog.askopenfilename(
            title=title,
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if file:
            variable.set(file)

    def _browse_topic_rec_output(self):
        """Browse for output file location."""
        file = filedialog.asksaveasfilename(
            title="Save Topic Recommendations Report",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=self.topic_rec_output_file.get()
        )
        if file:
            self.topic_rec_output_file.set(file)

    def generate_topic_recommendations_report(self):
        """Generate comprehensive topic recommendations report."""
        from collections import Counter
        from pathlib import Path

        # Validate inputs
        match_file = self.topic_rec_match_file.get()
        taxonomy_file = self.topic_rec_taxonomy_file.get()
        output_file = self.topic_rec_output_file.get()
        doc_source = self.topic_rec_doc_source.get()

        if not match_file or not os.path.exists(match_file):
            messagebox.showerror("Error", "Please select a valid Match File (cleaned)")
            return

        if not taxonomy_file or not os.path.exists(taxonomy_file):
            messagebox.showerror("Error", "Please select a valid Taxonomy File")
            return

        if not output_file:
            messagebox.showerror("Error", "Please specify an output file")
            return

        # Update status
        self.topic_rec_status_label.config(text="Generating report...", fg=self.colors['primary'])
        self.topic_rec_report_btn.config(state='disabled')
        self.root.update()

        try:
            self.log("=" * 50)
            self.log("TOPIC RECOMMENDATIONS REPORT")
            self.log("=" * 50)

            # Load match data
            self.log(f"Loading match file: {os.path.basename(match_file)}")
            try:
                df_match = pd.read_excel(match_file, sheet_name='Cleaned')
            except:
                df_match = pd.read_excel(match_file, sheet_name=0)
            self.log(f"  Loaded {len(df_match)} rows, {df_match['URL'].nunique()} unique URLs")

            # Load taxonomy
            self.log(f"Loading taxonomy: {os.path.basename(taxonomy_file)}")
            df_taxonomy = pd.read_excel(taxonomy_file)
            self.log(f"  Loaded {len(df_taxonomy)} taxonomy rows")

            # Import the report generation functions
            from generate_topic_recommendations import (
                analyze_data_quality,
                analyze_product_gaps,
                generate_topic_recommendations,
                generate_suggested_new_topics,
                generate_topics_from_document_source,
                generate_urls_by_product,
                generate_impact_summary,
                generate_topics_to_add,
                generate_executive_summary,
                sanitize_dataframe
            )

            # Generate all report components
            self.log("Analyzing data quality...")
            self.topic_rec_status_label.config(text="Analyzing data quality...", fg=self.colors['primary'])
            self.root.update()
            df_quality = analyze_data_quality(df_taxonomy, df_match)
            self.log(f"  Found {len(df_quality)} data quality issues")

            self.log("Analyzing product gaps...")
            self.topic_rec_status_label.config(text="Analyzing product gaps...", fg=self.colors['primary'])
            self.root.update()
            df_gaps = analyze_product_gaps(df_match, df_taxonomy)
            gaps_critical = len(df_gaps[df_gaps['Gap_Level'] == 'CRITICAL'])
            gaps_high = len(df_gaps[df_gaps['Gap_Level'] == 'HIGH'])
            self.log(f"  Found {gaps_critical} critical gaps, {gaps_high} high gaps")

            self.log("Generating topic recommendations...")
            self.topic_rec_status_label.config(text="Generating recommendations...", fg=self.colors['primary'])
            self.root.update()
            df_recs, all_taxonomy_topics = generate_topic_recommendations(df_match, df_taxonomy)
            self.log(f"  Generated {len(df_recs)} topic recommendations")

            self.log("Finding suggested new topics from match data...")
            df_new_topics_match = generate_suggested_new_topics(df_match, all_taxonomy_topics, top_n=5)
            self.log(f"  Found {len(df_new_topics_match)} from match data")

            # Document source analysis (if provided)
            if doc_source and os.path.exists(doc_source):
                self.log(f"Analyzing document source: {os.path.basename(doc_source)}")
                self.topic_rec_status_label.config(text="Analyzing document source...", fg=self.colors['primary'])
                self.root.update()
                df_new_topics_docs = generate_topics_from_document_source(doc_source, all_taxonomy_topics, top_n=10)
                self.log(f"  Found {len(df_new_topics_docs)} from document source")
                df_new_topics = pd.concat([df_new_topics_match, df_new_topics_docs], ignore_index=True)
            else:
                df_new_topics = df_new_topics_match
                if doc_source:
                    self.log(f"  Document source not found: {doc_source}")

            self.log(f"  Total suggested new topics: {len(df_new_topics)}")

            self.log("Generating URL breakdown by product...")
            df_urls = generate_urls_by_product(df_match)

            self.log("Generating impact summary...")
            df_impact = generate_impact_summary(df_gaps, df_quality)

            self.log("Generating specific topics to add...")
            df_topics_to_add = generate_topics_to_add(df_recs, df_gaps)
            self.log(f"  Generated {len(df_topics_to_add)} specific topic additions")

            self.log("Generating executive summary...")
            df_summary = generate_executive_summary(df_match, df_taxonomy, df_gaps, df_quality)

            # Write to Excel
            self.log(f"Writing report to: {output_file}")
            self.topic_rec_status_label.config(text="Writing Excel file...", fg=self.colors['primary'])
            self.root.update()

            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sanitize all DataFrames to prevent Excel corruption
                sanitize_dataframe(df_summary).to_excel(writer, sheet_name='Executive Summary', index=False)
                sanitize_dataframe(df_quality).to_excel(writer, sheet_name='Data Quality Issues', index=False)
                sanitize_dataframe(df_gaps).to_excel(writer, sheet_name='Product Gap Analysis', index=False)
                sanitize_dataframe(df_recs).to_excel(writer, sheet_name='Topic Recommendations', index=False)
                sanitize_dataframe(df_new_topics).to_excel(writer, sheet_name='Suggested New Topics', index=False)
                sanitize_dataframe(df_urls).to_excel(writer, sheet_name='URLs by Product', index=False)
                sanitize_dataframe(df_impact).to_excel(writer, sheet_name='Impact Summary', index=False)
                sanitize_dataframe(df_topics_to_add).to_excel(writer, sheet_name='Topics to Add', index=False)

                # Apply formatting
                try:
                    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                    from openpyxl.utils import get_column_letter

                    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                    header_font = Font(bold=True, color='FFFFFF')
                    thin_border = Border(
                        left=Side(style='thin'), right=Side(style='thin'),
                        top=Side(style='thin'), bottom=Side(style='thin')
                    )

                    for sheet_name in writer.sheets:
                        ws = writer.sheets[sheet_name]
                        for cell in ws[1]:
                            cell.fill = header_fill
                            cell.font = header_font
                            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                            cell.border = thin_border

                        for column in ws.columns:
                            max_length = 0
                            column_letter = get_column_letter(column[0].column)
                            for cell in column:
                                try:
                                    if len(str(cell.value)) > max_length:
                                        max_length = min(len(str(cell.value)), 50)
                                except:
                                    pass
                            ws.column_dimensions[column_letter].width = max_length + 2
                except Exception as fmt_error:
                    self.log(f"  Warning: Could not apply formatting: {fmt_error}")

            self.log("=" * 50)
            self.log("Report generated successfully!")
            self.log("=" * 50)

            self.topic_rec_status_label.config(text="Complete!", fg=self.colors['secondary'])

            # Show summary
            summary_text = "\n".join([f"{row['Metric']}: {row['Value']}" for _, row in df_summary.iterrows()])
            messagebox.showinfo(
                "Success",
                f"Report saved to:\n{output_file}\n\n"
                f"Summary:\n{summary_text}"
            )

        except Exception as e:
            self.log(f"ERROR generating topic recommendations report: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.topic_rec_status_label.config(text="Error", fg=self.colors['error'])
            messagebox.showerror("Error", f"Failed to generate report:\n{e}")

        finally:
            self.topic_rec_report_btn.config(state='normal')

    # ==================== GAP ANALYSIS REPORT METHODS ====================

    def _browse_gap_analysis_file(self, variable, title):
        """Browse for input file for gap analysis report."""
        file = filedialog.askopenfilename(
            title=title,
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if file:
            variable.set(file)

    def _browse_gap_analysis_output(self):
        """Browse for output file location."""
        file = filedialog.asksaveasfilename(
            title="Save Gap Analysis Report",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=self.gap_analysis_output_file.get()
        )
        if file:
            self.gap_analysis_output_file.set(file)

    def generate_gap_analysis_report(self):
        """Generate comprehensive taxonomy gap analysis report."""
        from collections import Counter, defaultdict
        from pathlib import Path
        from fuzzywuzzy import fuzz
        import re

        # Validate inputs
        match_file = self.gap_analysis_match_file.get()
        taxonomy_file = self.gap_analysis_taxonomy_file.get()
        semantic_file = self.gap_analysis_semantic_file.get()
        output_file = self.gap_analysis_output_file.get()

        if not match_file or not os.path.exists(match_file):
            messagebox.showerror("Error", "Please select a valid Match File")
            return

        if not taxonomy_file or not os.path.exists(taxonomy_file):
            messagebox.showerror("Error", "Please select a valid Taxonomy File")
            return

        if not output_file:
            messagebox.showerror("Error", "Please specify an output file")
            return

        # Disable button during processing
        self.gap_analysis_report_btn.config(state='disabled')
        self.gap_analysis_status_label.config(text="Generating...", fg=self.colors['text'])
        self.root.update()

        try:
            self.log("=" * 60)
            self.log("GENERATING GAP ANALYSIS REPORT")
            self.log("=" * 60)

            # Load match file
            self.log(f"Loading match file: {Path(match_file).name}")
            try:
                df_match = pd.read_excel(match_file, sheet_name='Cleaned')
                self.log(f"  Loaded 'Cleaned' sheet: {len(df_match)} rows")
            except:
                df_match = pd.read_excel(match_file, sheet_name=0)
                self.log(f"  Loaded first sheet: {len(df_match)} rows")

            # Load taxonomy
            self.log(f"Loading taxonomy: {Path(taxonomy_file).name}")
            df_taxonomy = pd.read_excel(taxonomy_file)
            self.log(f"  Loaded: {len(df_taxonomy)} rows")

            # Load semantic file (optional)
            df_semantic = None
            if semantic_file and os.path.exists(semantic_file):
                self.log(f"Loading semantic file: {Path(semantic_file).name}")
                df_semantic = pd.read_excel(semantic_file)
                self.log(f"  Loaded: {len(df_semantic)} rows")

            # Helper function to sanitize cell values
            import math
            def sanitize_cell_value(value):
                # Handle None, NaN, inf
                if value is None:
                    return ''
                if isinstance(value, float):
                    if pd.isna(value) or math.isinf(value):
                        return ''
                    return value
                if isinstance(value, (int, bool)):
                    return value

                s = str(value)

                # Return empty string for 'nan' or 'None' strings
                if s.lower() in ('nan', 'none', 'null', '<na>'):
                    return ''

                # Remove null bytes first
                s = s.replace('\x00', '')

                # Remove ALL control characters (0x00-0x1F except tab, newline, carriage return)
                # Also remove 0x7F (DEL) and 0x80-0x9F (C1 control codes)
                s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', s)

                # Remove Unicode surrogate pairs (invalid in XML)
                s = re.sub(r'[\ud800-\udfff]', '', s)

                # Remove other problematic Unicode characters
                s = re.sub(r'[\ufffe\uffff\ufeff]', '', s)

                # Remove any remaining non-printable characters
                s = ''.join(char for char in s if char.isprintable() or char in '\t\n\r')

                # Truncate very long strings
                if len(s) > 32000:
                    s = s[:32000] + '...'

                # Escape strings that look like formulas
                if s and s[0] in '=+-@':
                    s = "'" + s

                return s.strip()

            def sanitize_dataframe(df):
                df = df.copy()
                for col in df.columns:
                    df[col] = df[col].apply(lambda x: sanitize_cell_value(x))
                return df

            # Get all taxonomy topics
            self.log("Analyzing taxonomy topics...")
            topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]
            all_taxonomy_topics = set()
            topic_to_product = {}
            topic_to_segment = {}

            for _, row in df_taxonomy.iterrows():
                product = row.get('Product', 'Unknown')
                segment = row.get('Segment', 'Unknown')
                for col in topic_cols:
                    val = row[col]
                    if pd.notna(val) and str(val).strip():
                        topic = str(val).strip().lower()
                        all_taxonomy_topics.add(topic)
                        topic_to_product[topic] = product
                        topic_to_segment[topic] = segment

            self.log(f"  Found {len(all_taxonomy_topics)} unique topics in taxonomy")

            # Get matched topics from match file
            self.log("Analyzing matched topics...")
            match_topic_cols = [c for c in df_match.columns if c.startswith('Topic_') and c != 'Topic_Frequency_Penalty']
            matched_topics = set()
            topic_match_counts = Counter()

            for _, row in df_match.iterrows():
                for col in match_topic_cols:
                    val = row[col]
                    if pd.notna(val) and str(val).strip():
                        topic = str(val).strip().lower()
                        matched_topics.add(topic)
                        topic_match_counts[topic] += 1

            self.log(f"  Found {len(matched_topics)} unique topics in matches")

            # === SHEET 1: EXECUTIVE SUMMARY ===
            self.log("Generating Executive Summary...")
            total_urls = df_match['URL'].nunique()
            unmapped_urls = df_match[df_match['Domain'] == 'UNMAPPED']['URL'].nunique() if 'Domain' in df_match.columns else 0
            match_rate = round((total_urls - unmapped_urls) / total_urls * 100, 1) if total_urls > 0 else 0
            never_matched_count = len(all_taxonomy_topics - matched_topics)
            phantom_count = len(matched_topics - all_taxonomy_topics)

            df_summary = pd.DataFrame([
                {'Metric': 'Report Generated', 'Value': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')},
                {'Metric': '', 'Value': ''},
                {'Metric': '=== MATCH RESULTS ===', 'Value': ''},
                {'Metric': 'Total URLs Processed', 'Value': f'{total_urls:,}'},
                {'Metric': 'Matched URLs', 'Value': f'{total_urls - unmapped_urls:,}'},
                {'Metric': 'Unmapped URLs', 'Value': f'{unmapped_urls:,}'},
                {'Metric': 'Match Rate', 'Value': f'{match_rate}%'},
                {'Metric': '', 'Value': ''},
                {'Metric': '=== TAXONOMY ANALYSIS ===', 'Value': ''},
                {'Metric': 'Total Taxonomy Topics', 'Value': len(all_taxonomy_topics)},
                {'Metric': 'Topics That Matched', 'Value': len(matched_topics & all_taxonomy_topics)},
                {'Metric': 'Never-Matched Topics', 'Value': never_matched_count},
                {'Metric': 'Phantom Topics', 'Value': phantom_count},
                {'Metric': '', 'Value': ''},
                {'Metric': '=== KEY FINDINGS ===', 'Value': ''},
                {'Metric': 'Finding 1', 'Value': f'{never_matched_count} topics in taxonomy never matched any URL'},
                {'Metric': 'Finding 2', 'Value': f'{phantom_count} topics in matches not found in taxonomy'},
                {'Metric': 'Finding 3', 'Value': f'Match rate is {match_rate}%'},
            ])

            # === SHEET 2: PHANTOM TOPICS ===
            self.log("Identifying Phantom Topics...")
            phantom_data = []
            for topic in matched_topics:
                if topic not in all_taxonomy_topics:
                    phantom_data.append({
                        'Topic': topic.title(),
                        'Match_Count': topic_match_counts.get(topic, 0),
                        'Issue': 'Topic in matches but not in taxonomy',
                        'Recommendation': 'Add to taxonomy or investigate source'
                    })
            df_phantom = pd.DataFrame(phantom_data)
            if not df_phantom.empty:
                df_phantom = df_phantom.sort_values('Match_Count', ascending=False)
            self.log(f"  Found {len(df_phantom)} phantom topics")

            # === SHEET 3: NEVER-MATCHED TOPICS ===
            self.log("Identifying Never-Matched Topics...")
            never_matched_data = []
            for topic in all_taxonomy_topics:
                if topic not in matched_topics:
                    never_matched_data.append({
                        'Topic': topic.title(),
                        'Product': topic_to_product.get(topic, 'Unknown'),
                        'Segment': topic_to_segment.get(topic, 'Unknown'),
                        'Status': 'Never matched',
                        'Recommendation': 'Add synonyms or review relevance'
                    })
            df_never_matched = pd.DataFrame(never_matched_data)
            if not df_never_matched.empty:
                df_never_matched = df_never_matched.sort_values(['Product', 'Topic'])
            self.log(f"  Found {len(df_never_matched)} never-matched topics")

            # === SHEET 4: TAXONOMY COMPARISON ===
            self.log("Generating Taxonomy Comparison...")
            df_comparison = pd.DataFrame([
                {'Aspect': 'Total Topics in Taxonomy', 'Value': len(all_taxonomy_topics)},
                {'Aspect': 'Topics That Matched', 'Value': len(matched_topics & all_taxonomy_topics)},
                {'Aspect': 'Topics Never Matched', 'Value': never_matched_count},
                {'Aspect': 'Coverage Rate', 'Value': f'{round(len(matched_topics & all_taxonomy_topics) / len(all_taxonomy_topics) * 100, 1)}%'},
            ])

            # === SHEET 5: SYNONYM RECOMMENDATIONS ===
            self.log("Generating Synonym Recommendations...")
            never_matched_set = all_taxonomy_topics - matched_topics

            # Extract keywords from semantic file WITH URL tracking
            keyword_counts = Counter()
            keyword_urls = defaultdict(list)  # Track URLs for each keyword

            if df_semantic is not None:
                keyword_cols = [c for c in df_semantic.columns if 'keyword' in c.lower()]
                url_col = 'URL' if 'URL' in df_semantic.columns else df_semantic.columns[0]

                for _, row in df_semantic.iterrows():
                    url = str(row.get(url_col, ''))
                    for col in keyword_cols:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            kw = str(val).strip().lower()
                            keyword_counts[kw] += 1
                            # Store up to 5 sample URLs per keyword
                            if len(keyword_urls[kw]) < 5:
                                keyword_urls[kw].append(url)

            synonym_recs = []
            for topic in never_matched_set:
                suggested = []
                for kw, freq in keyword_counts.most_common():
                    if freq < 3:
                        continue
                    score = max(fuzz.ratio(topic, kw), fuzz.partial_ratio(topic, kw))
                    if score >= 60:
                        urls = keyword_urls.get(kw, [])
                        suggested.append((kw, freq, score, urls))
                suggested.sort(key=lambda x: (-x[2], -x[1]))

                if suggested:
                    kw_str = ', '.join([f"{kw} ({freq})" for kw, freq, _, _ in suggested[:5]])
                    best_score = suggested[0][2]
                    priority = 'HIGH' if best_score >= 75 else 'MEDIUM' if best_score >= 65 else 'LOW'

                    # Collect sample URLs from top suggested keywords
                    sample_urls = []
                    for kw, freq, score, urls in suggested[:5]:
                        sample_urls.extend(urls[:2])
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_urls = []
                    for u in sample_urls:
                        if u not in seen:
                            seen.add(u)
                            unique_urls.append(u)
                    unique_urls = unique_urls[:5]  # Keep up to 5 full URLs

                    rec = {
                        'Taxonomy_Topic': topic.title(),
                        'Status': 'In taxonomy - never matched',
                        'Suggested_Synonyms': kw_str,
                        'Priority': priority,
                    }
                    # Add up to 5 sample URLs as separate columns (clickable in Excel)
                    for i, url in enumerate(unique_urls, start=1):
                        rec[f'Sample_URL_{i}'] = url
                    # Fill remaining URL columns with empty string
                    for i in range(len(unique_urls) + 1, 6):
                        rec[f'Sample_URL_{i}'] = ''
                    synonym_recs.append(rec)

            df_synonym_recs = pd.DataFrame(synonym_recs)
            if not df_synonym_recs.empty:
                priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
                df_synonym_recs['_order'] = df_synonym_recs['Priority'].map(priority_order)
                df_synonym_recs = df_synonym_recs.sort_values('_order').drop('_order', axis=1)
            self.log(f"  Generated {len(df_synonym_recs)} synonym recommendations")

            # === SHEET 6: PRODUCT BREAKDOWN ===
            self.log("Generating Product Breakdown...")
            product_stats = []
            total_urls = df_match['URL'].nunique()
            for product in df_match['Product'].unique():
                if pd.isna(product):
                    continue
                product_data = df_match[df_match['Product'] == product]
                unique_urls = product_data['URL'].nunique()
                unmapped = len(product_data[product_data['Domain'] == 'UNMAPPED']) if 'Domain' in product_data.columns else 0
                product_stats.append({
                    'Product': product,
                    'Unique_URLs': unique_urls,
                    'Total_Rows': len(product_data),
                    'Unmapped_Rows': unmapped,
                    'Match_Rate': f'{round((len(product_data) - unmapped) / len(product_data) * 100, 1)}%' if len(product_data) > 0 else '0%',
                    'Pct_of_Total': f'{round(unique_urls / total_urls * 100, 1)}%'
                })
            df_products = pd.DataFrame(product_stats)
            if not df_products.empty:
                df_products = df_products.sort_values('Unique_URLs', ascending=False)

            # === SHEET 7: ACTION ITEMS ===
            self.log("Generating Action Items...")
            actions = []
            action_id = 1
            if len(df_phantom) > 0:
                actions.append({'ID': action_id, 'Priority': 'P1-CRITICAL', 'Category': 'Data Quality',
                               'Action': f'Investigate {len(df_phantom)} phantom topics', 'Impact': 'High'})
                action_id += 1
            high_priority_synonyms = len(df_synonym_recs[df_synonym_recs['Priority'] == 'HIGH']) if not df_synonym_recs.empty else 0
            if high_priority_synonyms > 0:
                actions.append({'ID': action_id, 'Priority': 'P1-HIGH', 'Category': 'Synonyms',
                               'Action': f'Add synonyms for {high_priority_synonyms} HIGH-priority topics', 'Impact': 'High'})
                action_id += 1
            if never_matched_count > 10:
                actions.append({'ID': action_id, 'Priority': 'P2-MEDIUM', 'Category': 'Review',
                               'Action': f'Review {never_matched_count} never-matched topics', 'Impact': 'Medium'})
            df_actions = pd.DataFrame(actions) if actions else pd.DataFrame([{'Message': 'No critical issues found'}])

            # Write to Excel
            self.log(f"Writing report to: {output_file}")
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                sanitize_dataframe(df_summary).to_excel(writer, sheet_name='Executive Summary', index=False)
                sanitize_dataframe(df_phantom).to_excel(writer, sheet_name='Phantom Topics', index=False)
                sanitize_dataframe(df_never_matched).to_excel(writer, sheet_name='Never-Matched Topics', index=False)
                sanitize_dataframe(df_comparison).to_excel(writer, sheet_name='Taxonomy Comparison', index=False)
                sanitize_dataframe(df_synonym_recs).to_excel(writer, sheet_name='Synonym Recommendations', index=False)
                sanitize_dataframe(df_products).to_excel(writer, sheet_name='Product Breakdown', index=False)
                sanitize_dataframe(df_actions).to_excel(writer, sheet_name='Action Items', index=False)

                # Apply formatting
                try:
                    from openpyxl.styles import Font, PatternFill, Alignment
                    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                    header_font = Font(bold=True, color='FFFFFF')
                    for sheet_name in writer.sheets:
                        ws = writer.sheets[sheet_name]
                        for cell in ws[1]:
                            cell.fill = header_fill
                            cell.font = header_font
                except:
                    pass

            self.log("=" * 60)
            self.log("GAP ANALYSIS REPORT GENERATED SUCCESSFULLY!")
            self.log(f"Output: {output_file}")
            self.log("=" * 60)

            self.gap_analysis_status_label.config(text="Complete!", fg=self.colors['secondary'])

            messagebox.showinfo(
                "Success",
                f"Gap Analysis Report saved to:\n{output_file}\n\n"
                f"Sheets generated:\n"
                f"1. Executive Summary\n"
                f"2. Phantom Topics ({len(df_phantom)})\n"
                f"3. Never-Matched Topics ({len(df_never_matched)})\n"
                f"4. Taxonomy Comparison\n"
                f"5. Synonym Recommendations ({len(df_synonym_recs)})\n"
                f"6. Product Breakdown ({len(df_products)})\n"
                f"7. Action Items ({len(df_actions)})"
            )

        except Exception as e:
            self.log(f"ERROR generating gap analysis report: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.gap_analysis_status_label.config(text="Error", fg=self.colors['error'])
            messagebox.showerror("Error", f"Failed to generate report:\n{e}")

        finally:
            self.gap_analysis_report_btn.config(state='normal')


def main():
    """Main entry point."""
    root = tk.Tk()
    app = TaxonomyMapperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()