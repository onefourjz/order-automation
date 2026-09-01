"""
Spectacle Order Automation App
Desktop application for scanning VSP spectacle order PDFs and
automating order entry on Eyefinity.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import threading
from typing import Dict, Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_parser import SpectacleOrderParser
from eyefinity_automation import EyefinityAutomation


class SpectacleOrderApp:
    """Main desktop application for spectacle order automation."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Spectacle Order Automation - VSP to Eyefinity")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        # Set icon if available
        try:
            self.root.iconbitmap(default="icon.ico")
        except:
            pass

        # State
        self.current_pdf_path: Optional[str] = None
        self.extracted_data: Dict[str, str] = {}
        self.automation: Optional[EyefinityAutomation] = None
        self.is_automation_running = False

        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Header.TLabel", font=("Arial", 16, "bold"))
        self.style.configure("Section.TLabel", font=("Arial", 12, "bold"))
        self.style.configure("Success.TLabel", foreground="green", font=("Arial", 10, "bold"))
        self.style.configure("Error.TLabel", foreground="red", font=("Arial", 10, "bold"))
        self.style.configure("Action.TButton", font=("Arial", 10, "bold"), padding=10)

        self._build_ui()

    def _build_ui(self):
        """Build the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ========== Header ==========
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            header_frame,
            text="👓 Spectacle Order Automation",
            style="Header.TLabel"
        ).pack(side=tk.LEFT)

        ttk.Label(
            header_frame,
            text="VSP PDF → Eyefinity",
            font=("Arial", 10),
            foreground="gray"
        ).pack(side=tk.RIGHT)

        # Separator
        ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=(0, 15))

        # ========== Step 1: PDF Selection ==========
        step1_frame = ttk.LabelFrame(main_frame, text="Step 1: Select Spectacle Order PDF", padding="10")
        step1_frame.pack(fill=tk.X, pady=(0, 10))

        pdf_row = ttk.Frame(step1_frame)
        pdf_row.pack(fill=tk.X)

        self.pdf_path_var = tk.StringVar()
        pdf_entry = ttk.Entry(pdf_row, textvariable=self.pdf_path_var, width=70)
        pdf_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)

        ttk.Button(
            pdf_row,
            text="Browse PDF...",
            command=self._browse_pdf,
            style="Action.TButton"
        ).pack(side=tk.RIGHT)

        # ========== Step 2: Parse & Review ==========
        step2_frame = ttk.LabelFrame(main_frame, text="Step 2: Review Extracted Data", padding="10")
        step2_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Parse button
        parse_row = ttk.Frame(step2_frame)
        parse_row.pack(fill=tk.X, pady=(0, 10))

        self.parse_btn = ttk.Button(
            parse_row,
            text="🔍 Parse PDF",
            command=self._parse_pdf,
            state="disabled"
        )
        self.parse_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.parse_status_var = tk.StringVar(value="No PDF loaded")
        ttk.Label(parse_row, textvariable=self.parse_status_var).pack(side=tk.LEFT)

        # Data display - use notebook with tabs
        data_notebook = ttk.Notebook(step2_frame)
        data_notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Formatted view
        formatted_frame = ttk.Frame(data_notebook)
        data_notebook.add(formatted_frame, text="Formatted View")

        self.formatted_text = scrolledtext.ScrolledText(
            formatted_frame,
            wrap=tk.WORD,
            font=("Courier New", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            height=15
        )
        self.formatted_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 2: Editable fields
        fields_frame = ttk.Frame(data_notebook)
        data_notebook.add(fields_frame, text="Edit Fields")

        # Create scrollable field editor
        fields_canvas = tk.Canvas(fields_frame, highlightthickness=0)
        fields_scrollbar = ttk.Scrollbar(fields_frame, orient="vertical", command=fields_canvas.yview)
        fields_scrollable = ttk.Frame(fields_canvas)

        fields_scrollable.bind(
            "<Configure>",
            lambda e: fields_canvas.configure(scrollregion=fields_canvas.bbox("all"))
        )

        fields_canvas.create_window((0, 0), window=fields_scrollable, anchor="nw")
        fields_canvas.configure(yscrollcommand=fields_scrollbar.set)

        fields_canvas.pack(side="left", fill="both", expand=True)
        fields_scrollbar.pack(side="right", fill="y")

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            fields_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        fields_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.field_widgets = {}
        self._build_field_editor(fields_scrollable)

        # ========== Step 3: Eyefinity Actions ==========
        step3_frame = ttk.LabelFrame(main_frame, text="Step 3: Eyefinity Automation", padding="10")
        step3_frame.pack(fill=tk.X, pady=(0, 10))

        action_row = ttk.Frame(step3_frame)
        action_row.pack(fill=tk.X, pady=(0, 10))

        self.login_btn = ttk.Button(
            action_row,
            text="🔑 Login to Eyefinity",
            command=self._login_eyefinity,
            state="disabled",
            style="Action.TButton"
        )
        self.login_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.populate_btn = ttk.Button(
            action_row,
            text="📝 Populate Order Form",
            command=self._populate_order,
            state="disabled",
            style="Action.TButton"
        )
        self.populate_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.submit_btn = ttk.Button(
            action_row,
            text="✅ Submit Order",
            command=self._submit_order,
            state="disabled",
            style="Action.TButton"
        )
        self.submit_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.close_btn = ttk.Button(
            action_row,
            text="❌ Close Browser",
            command=self._close_browser,
            state="disabled"
        )
        self.close_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Automation status
        self.automation_status_var = tk.StringVar(value="Not connected")
        ttk.Label(
            step3_frame,
            textvariable=self.automation_status_var,
            style="Error.TLabel"
        ).pack(anchor=tk.W)

        # ========== Log Output ==========
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="5")
        log_frame.pack(fill=tk.X, pady=(0, 5))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=8,
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Arial", 9),
            foreground="gray"
        ).pack(side=tk.LEFT)

        # Version
        ttk.Label(
            status_frame,
            text="v1.0.0",
            font=("Arial", 9),
            foreground="gray"
        ).pack(side=tk.RIGHT)

    def _build_field_editor(self, parent: ttk.Frame):
        """Build the editable field editor in the given parent frame."""
        fields = [
            ("Patient Information", [
                ("patient_name", "Patient Name"),
                ("patient_dob", "Date of Birth"),
                ("patient_id", "Patient/Member ID"),
                ("doctor_name", "Doctor Name"),
                ("date_of_exam", "Exam Date"),
            ]),
            ("Right Eye (OD)", [
                ("od_sph", "Sphere (SPH)"),
                ("od_cyl", "Cylinder (CYL)"),
                ("od_axis", "Axis"),
                ("od_add", "Add"),
                ("od_prism", "Prism"),
            ]),
            ("Left Eye (OS)", [
                ("os_sph", "Sphere (SPH)"),
                ("os_cyl", "Cylinder (CYL)"),
                ("os_axis", "Axis"),
                ("os_add", "Add"),
                ("os_prism", "Prism"),
            ]),
            ("Measurements", [
                ("pd_distance", "PD (Distance)"),
                ("pd_near", "PD (Near)"),
            ]),
            ("Frame", [
                ("frame_manufacturer", "Manufacturer"),
                ("frame_model", "Model"),
                ("frame_color", "Color"),
                ("frame_size", "Size"),
            ]),
            ("Lens", [
                ("lens_type", "Type"),
                ("lens_material", "Material"),
                ("lens_coatings", "Coatings"),
            ]),
            ("Other", [
                ("comments", "Comments/Notes"),
            ]),
        ]

        for section_name, section_fields in fields:
            # Section header
            section_label = ttk.Label(
                parent,
                text=section_name,
                font=("Arial", 10, "bold"),
                foreground="#0078d4"
            )
            section_label.pack(anchor=tk.W, pady=(10, 5), padx=5)

            # Section separator
            sep = ttk.Separator(parent, orient="horizontal")
            sep.pack(fill=tk.X, padx=5)

            for field_key, field_label in section_fields:
                row = ttk.Frame(parent)
                row.pack(fill=tk.X, pady=2, padx=10)

                ttk.Label(row, text=field_label, width=20, anchor=tk.W).pack(side=tk.LEFT)

                var = tk.StringVar()
                entry = ttk.Entry(row, textvariable=var, width=40)
                entry.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)

                self.field_widgets[field_key] = var

    def _browse_pdf(self):
        """Open file dialog to select a PDF."""
        file_path = filedialog.askopenfilename(
            title="Select VSP Spectacle Order PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.current_pdf_path = file_path
            self.pdf_path_var.set(file_path)
            self.parse_btn.config(state="normal")
            self.parse_status_var.set("PDF selected. Click 'Parse PDF' to extract data.")
            self.log(f"Selected PDF: {file_path}")

    def _parse_pdf(self):
        """Parse the selected PDF and display extracted data."""
        if not self.current_pdf_path:
            return

        self.log("Parsing PDF...")
        self.parse_btn.config(state="disabled")
        self.parse_status_var.set("Parsing...")

        def parse_task():
            try:
                parser = SpectacleOrderParser()
                data = parser.parse(self.current_pdf_path)

                self.root.after(0, lambda: self._on_parse_complete(data, parser))
            except Exception as e:
                self.root.after(0, lambda: self._on_parse_error(str(e)))

        threading.Thread(target=parse_task, daemon=True).start()

    def _on_parse_complete(self, data: Dict[str, str], parser: SpectacleOrderParser):
        """Handle successful PDF parsing."""
        self.extracted_data = data

        # Update formatted view
        self.formatted_text.delete(1.0, tk.END)
        self.formatted_text.insert(1.0, parser.get_formatted_prescription())

        # Update field editor
        for key, var in self.field_widgets.items():
            var.set(data.get(key, ""))

        # Update status
        num_fields = len(data)
        self.parse_status_var.set(f"✓ Extracted {num_fields} fields from PDF")
        self.parse_status_var.configure(foreground="green")
        self.parse_btn.config(state="normal")

        # Enable login button
        self.login_btn.config(state="normal")

        self.log(f"✓ Successfully parsed PDF. Extracted {num_fields} fields.")
        self.status_var.set(f"Ready - {num_fields} fields extracted")

    def _on_parse_error(self, error_msg: str):
        """Handle PDF parsing error."""
        self.parse_status_var.set(f"✗ Error: {error_msg}")
        self.parse_btn.config(state="normal")
        self.log(f"✗ Error parsing PDF: {error_msg}")
        messagebox.showerror("Parse Error", f"Failed to parse PDF:\n{error_msg}")

    def _get_edited_data(self) -> Dict[str, str]:
        """Get the current data from the field editor."""
        data = {}
        for key, var in self.field_widgets.items():
            value = var.get().strip()
            if value:
                data[key] = value
        return data

    def _login_eyefinity(self):
        """Log in to Eyefinity."""
        if self.is_automation_running:
            return

        self.is_automation_running = True
        self.login_btn.config(state="disabled")
        self.automation_status_var.set("Logging in...")
        self.automation_status_var.configure(foreground="blue")
        self.log("Starting Eyefinity login...")

        def login_task():
            try:
                if not self.automation:
                    self.automation = EyefinityAutomation()

                success = self.automation.login()

                self.root.after(0, lambda: self._on_login_result(success))
            except Exception as e:
                self.root.after(0, lambda: self._on_login_error(str(e)))

        threading.Thread(target=login_task, daemon=True).start()

    def _on_login_result(self, success: bool):
        """Handle login result."""
        self.is_automation_running = False
        self.login_btn.config(state="normal")

        if success:
            self.automation_status_var.set("✓ Logged in to Eyefinity")
            self.automation_status_var.configure(style="Success.TLabel")
            self.populate_btn.config(state="normal")
            self.close_btn.config(state="normal")
            self.log("✓ Successfully logged in to Eyefinity")
            self.status_var.set("Logged in - Ready to populate order")

            # Try to navigate to order form
            self._navigate_to_order()
        else:
            self.automation_status_var.set("✗ Login failed - Check credentials")
            self.automation_status_var.configure(style="Error.TLabel")
            self.log("✗ Eyefinity login failed")
            messagebox.showerror(
                "Login Failed",
                "Could not log in to Eyefinity.\n"
                "Please check your credentials in config.yaml\n"
                "and ensure you have internet access."
            )

    def _on_login_error(self, error_msg: str):
        """Handle login error."""
        self.is_automation_running = False
        self.login_btn.config(state="normal")
        self.automation_status_var.set(f"✗ Error: {error_msg}")
        self.automation_status_var.configure(style="Error.TLabel")
        self.log(f"✗ Login error: {error_msg}")

    def _navigate_to_order(self):
        """Navigate to the order form."""
        if not self.automation:
            return

        self.log("Navigating to order form...")

        def nav_task():
            try:
                success = self.automation.navigate_to_order_form()
                self.root.after(0, lambda: self._on_nav_result(success))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"Navigation error: {e}"))

        threading.Thread(target=nav_task, daemon=True).start()

    def _on_nav_result(self, success: bool):
        """Handle navigation result."""
        if success:
            self.log("✓ Navigated to order form")
            self.status_var.set("Order form ready")
        else:
            self.log("⚠ Could not auto-navigate. You may need to navigate manually.")

    def _populate_order(self):
        """Populate the Eyefinity order form with extracted data."""
        if not self.automation or not self.automation.logged_in:
            messagebox.showwarning("Not Logged In", "Please log in to Eyefinity first.")
            return

        # Get current data (edited fields)
        data = self._get_edited_data()
        if not data:
            messagebox.showwarning("No Data", "No data to populate. Parse a PDF first.")
            return

        self.populate_btn.config(state="disabled")
        self.log("Populating order form...")

        def populate_task():
            try:
                success = self.automation.populate_order_form(data)
                self.root.after(0, lambda: self._on_populate_result(success))
            except Exception as e:
                self.root.after(0, lambda: self._on_populate_error(str(e)))

        threading.Thread(target=populate_task, daemon=True).start()

    def _on_populate_result(self, success: bool):
        """Handle form population result."""
        self.populate_btn.config(state="normal")

        if success:
            self.submit_btn.config(state="normal")
            self.log("✓ Order form populated successfully")
            self.status_var.set("Form populated - Review and submit")
            messagebox.showinfo(
                "Form Populated",
                "The order form has been populated.\n"
                "Please review the data in the browser,\n"
                "then click 'Submit Order' or submit manually."
            )
        else:
            self.log("⚠ Some fields may not have been filled")
            messagebox.showwarning(
                "Partial Fill",
                "Some fields could not be automatically filled.\n"
                "Please check the browser and fill in any missing fields manually."
            )

    def _on_populate_error(self, error_msg: str):
        """Handle form population error."""
        self.populate_btn.config(state="normal")
        self.log(f"✗ Error populating form: {error_msg}")

    def _submit_order(self):
        """Submit the order on Eyefinity."""
        if not self.automation:
            return

        confirm = messagebox.askyesno(
            "Confirm Submit",
            "Are you sure you want to submit this order?\n"
            "Please verify all data is correct first."
        )
        if not confirm:
            return

        self.submit_btn.config(state="disabled")
        self.log("Submitting order...")

        def submit_task():
            try:
                success = self.automation.submit_order()
                self.root.after(0, lambda: self._on_submit_result(success))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"Submit error: {e}"))
                self.root.after(0, lambda: self.submit_btn.config(state="normal"))

        threading.Thread(target=submit_task, daemon=True).start()

    def _on_submit_result(self, success: bool):
        """Handle submit result."""
        self.submit_btn.config(state="normal")

        if success:
            self.log("✓ Order submitted successfully!")
            self.status_var.set("Order submitted!")
            messagebox.showinfo("Success", "Order has been submitted successfully!")
        else:
            self.log("⚠ Could not auto-submit. Please submit manually.")
            messagebox.showwarning(
                "Submit Manual",
                "Could not find the submit button automatically.\n"
                "Please submit the order manually in the browser."
            )

    def _close_browser(self):
        """Close the browser."""
        if self.automation:
            self.automation.close()
            self.automation = None
            self.login_btn.config(state="normal")
            self.populate_btn.config(state="disabled")
            self.submit_btn.config(state="disabled")
            self.close_btn.config(state="disabled")
            self.automation_status_var.set("Browser closed")
            self.automation_status_var.configure(style="Error.TLabel")
            self.log("Browser closed")
            self.status_var.set("Ready")

    def log(self, message: str):
        """Add a message to the log output."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)


def main():
    """Main entry point."""
    root = tk.Tk()
    app = SpectacleOrderApp(root)

    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()