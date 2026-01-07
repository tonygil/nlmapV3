"""
NL Taxonomy Mapper V2 - Beautiful GUI Application
Modern and intuitive user interface for taxonomy matching
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
from datetime import datetime
from taxonomy_matcher import TaxonomyMatcher
import sys


class TaxonomyMapperGUI:
    """Modern GUI application for NL Taxonomy Mapper."""
    
    def __init__(self, root):
        """Initialize the GUI application."""
        self.root = root
        self.root.title("NL Taxonomy Mapper V2")
        self.root.geometry("900x700")
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
            text=" Sitecore Taxonomy Mapper",
            font=('Segoe UI', 24, 'bold'),
            bg=self.colors['primary'],
            fg='white'
        ).pack(side='left', padx=30, pady=20)
        
        tk.Label(
            header,
            text="V2.0",
            font=('Segoe UI', 12),
            bg=self.colors['primary'],
            fg='white'
        ).pack(side='left', pady=20)
        
    def create_main_content(self):
        """Create main content area."""
        main = tk.Frame(self.root, bg=self.colors['background'])
        main.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Style notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=self.colors['background'], borderwidth=0)
        style.configure('TNotebook.Tab', padding=[20, 10], font=('Segoe UI', 10))
        
        notebook = ttk.Notebook(main)
        notebook.pack(fill='both', expand=True)
        
        self.create_setup_tab(notebook)
        self.create_log_tab(notebook)
        self.create_about_tab(notebook)
        
    def create_setup_tab(self, notebook):
        """Create setup tab."""
        frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(frame, text='   Setup  ')
        
        # Input Files Card
        input_card = self.create_card(frame, " Input Files")
        input_card.pack(fill='x', padx=10, pady=10)
        
        self.create_file_row(
            input_card,
            "URL Keywords file:",
            self.semantic_file,
            "Select semantic_carriers_list.xlsx"
        )
        
        self.create_file_row(
            input_card,
            "Taxonomy File:",
            self.taxonomy_file,
            "Select NL Taxonomy V2.xlsx"
        )
        
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
        ).pack(padx=20, pady=(0, 15))
        
        # Buttons
        btn_frame = tk.Frame(frame, bg=self.colors['background'])
        btn_frame.pack(fill='x', pady=20)
        
        self.run_btn = tk.Button(
            btn_frame,
            text="  Run Matching",
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
            text=" Reset",
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
        
    def create_about_tab(self, notebook):
        """Create about tab."""
        frame = tk.Frame(notebook, bg=self.colors['background'])
        notebook.add(frame, text='   About  ')
        
        card = self.create_card(frame, " About This Application")
        card.pack(fill='both', expand=True, padx=10, pady=10)
        
        content = tk.Frame(card, bg=self.colors['card'])
        content.pack(fill='both', expand=True, padx=30, pady=20)
        
        info = [
            ("Application:", "NL Taxonomy Mapper V2"),
            ("Version:", "2.0.0"),
            ("Purpose:", "Match URLs to taxonomy topics using fuzzy matching"),
            ("", ""),
            ("Features:", " Fuzzy string matching\n Dutch synonym support\n Auto deduplication\n Dynamic topic detection"),
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
        
        self.progress = ttk.Progressbar(footer, mode='indeterminate', length=200)
        self.progress.pack(side='right', padx=20)
        
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
        
    def create_file_row(self, parent, label, variable, title, save=False):
        """Create a file input row."""
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
            command=lambda: self.browse_file(variable, title, save),
            font=('Segoe UI', 9),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            padx=15,
            pady=5
        )
        btn.pack(side='right')
        
    def browse_file(self, variable, title, save=False):
        """Browse for file."""
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
        """Validate inputs."""
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
        self.progress.start()
        self.status_label.config(text="Processing...")
        self.clear_log()
        
        thread = threading.Thread(target=self.process, daemon=True)
        thread.start()
        
    def process(self):
        """Process matching."""
        try:
            self.log("=" * 50)
            self.log("Starting NL Taxonomy Mapper V2")
            self.log("=" * 50)
            
            matcher = TaxonomyMatcher(
                semantic_file=self.semantic_file.get(),
                taxonomy_file=self.taxonomy_file.get(),
                output_file=self.output_file.get(),
                similarity_threshold=self.threshold.get()
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
        self.run_btn.config(state='normal')
        self.is_processing = False
        self.status_label.config(text="Ready")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = TaxonomyMapperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()