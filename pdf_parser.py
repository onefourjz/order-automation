"""
PDF Parser for Carl Zeiss Vision / VSP Spectacle Order Forms
Extracts structured data from spectacle order PDFs using pdfplumber.
"""

import re
import pdfplumber
from typing import Dict, Optional


class SpectacleOrderParser:
    """Parses spectacle order PDFs and extracts prescription data."""

    def __init__(self):
        self.extracted_data: Dict[str, str] = {}

    def parse(self, pdf_path: str) -> Dict[str, str]:
        self.extracted_data = {}
        text = self._extract_text(pdf_path)
        if not text:
            return self.extracted_data
        self._parse_patient_info(text)
        self._parse_prescription(text)
        self._parse_frame_info(text)
        self._parse_lens_info(text)
        self._parse_misc(text)
        return self.extracted_data

    def _extract_text(self, pdf_path: str) -> Optional[str]:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                return "\n".join(text_parts)
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None

    def _parse_patient_info(self, text: str):
        lines = text.split('\n')

        # Practice name - first line
        if lines:
            m = re.match(r'^([A-Za-z][A-Za-z\s]+?)(?:Spectacle|Optometry)', lines[0])
            if m:
                self.extracted_data["practice_name"] = m.group(1).strip()

        # Doctor name - line with ", OD" (single line only)
        for line in lines:
            m = re.search(r'([A-Za-z][A-Za-z \-\.\']+?),\s*OD', line)
            if m:
                self.extracted_data["doctor_name"] = m.group(1).strip()
                break

        # Patient name - line before DOB
        for i, line in enumerate(lines):
            if 'DOB:' in line:
                if i > 0:
                    prev = lines[i-1].strip()
                    # Extract just the name (first two words max, before any other data)
                    m = re.match(r'^([A-Za-z][A-Za-z\']+(?:\s+[A-Za-z][A-Za-z\']+)?)', prev)
                    if m:
                        self.extracted_data["patient_name"] = m.group(1).strip()
                break

        # DOB
        for line in lines:
            m = re.search(r'DOB[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', line)
            if m:
                self.extracted_data["patient_dob"] = m.group(1).strip()
                break

        # Patient ID
        for line in lines:
            m = re.search(r'Patient\s*#(\d+)', line)
            if m:
                self.extracted_data["patient_id"] = m.group(1).strip()
                break

        # Order number
        for line in lines:
            m = re.search(r'Order\s*#:\s*(\d+)', line)
            if m:
                self.extracted_data["order_number"] = m.group(1).strip()
                break

        # Order date
        for line in lines:
            m = re.search(r'Order\s*Date[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', line)
            if m:
                self.extracted_data["order_date"] = m.group(1).strip()
                break

        # VSP Authorization # - from "Tray: Auth# 50039014" format
        for line in lines:
            m = re.search(r'Auth#\s*(\d+)', line)
            if m:
                self.extracted_data["vsp_auth"] = m.group(1).strip()
                break

        # Created By
        for line in lines:
            m = re.search(r'Created\s*By[:\s]*(\w+\s+\w+)', line)
            if m:
                self.extracted_data["created_by"] = m.group(1).strip()
                break

        # Supplier
        for line in lines:
            m = re.search(r'Supplier[:\s]*([A-Za-z0-9\s\-\.]+)', line)
            if m:
                val = m.group(1).strip().rstrip('-').strip()
                if val:
                    self.extracted_data["supplier"] = val
                break

    def _parse_prescription(self, text: str):
        lines = text.split('\n')

        # Standard spaced format: "OD +2.00 -0.25 065 +2.50" (with ADD)
        # Or: "OD -0.50 -0.25 040" (no ADD - single vision)
        for line in lines:
            line = line.strip()
            # OD line - ADD is optional
            m = re.match(r'OD\s+([\+\-]?\d+\.?\d*)\s+([\+\-]?\d+\.?\d*)\s+(\d+)(?:\s+([\+\-]?\d+\.?\d*))?', line)
            if m:
                self.extracted_data["od_sph"] = m.group(1)
                self.extracted_data["od_cyl"] = m.group(2)
                self.extracted_data["od_axis"] = m.group(3)
                if m.group(4):
                    self.extracted_data["od_add"] = m.group(4)
                continue

            # OS line - ADD is optional
            m = re.match(r'OS\s+([\+\-]?\d+\.?\d*)\s+([\+\-]?\d+\.?\d*)\s+(\d+)(?:\s+([\+\-]?\d+\.?\d*))?', line)
            if m:
                self.extracted_data["os_sph"] = m.group(1)
                self.extracted_data["os_cyl"] = m.group(2)
                self.extracted_data["os_axis"] = m.group(3)
                if m.group(4):
                    self.extracted_data["os_add"] = m.group(4)
                continue

        # Fallback: Carl Zeiss compact format (no spaces)
        if "od_sph" not in self.extracted_data:
            m = re.search(r'OD([\+\-]\d+\.\d+)([\+\-]\d+\.\d+)(\d{3})([\+\-]\d+\.?\d*)', text)
            if m:
                self.extracted_data["od_sph"] = m.group(1)
                self.extracted_data["od_cyl"] = m.group(2)
                self.extracted_data["od_axis"] = m.group(3)
                self.extracted_data["od_add"] = m.group(4)

        if "os_sph" not in self.extracted_data:
            m = re.search(r'OS([\+\-]\d+\.\d+)([\+\-]\d+\.\d+)(\d{3})([\+\-]\d+\.?\d*)', text)
            if m:
                self.extracted_data["os_sph"] = m.group(1)
                self.extracted_data["os_cyl"] = m.group(2)
                self.extracted_data["os_axis"] = m.group(3)
                self.extracted_data["os_add"] = m.group(4)

        # PD from MPD-D and MPD-N columns (monocular values)
        # MPD-D = Monocular Pupillary Distance (Distance)
        # MPD-N = Seg Height (NOT near PD - it's the segment height)
        # Binocular Dist/Near PD come from "Dist PD:" and "Near PD:" labels
        for i, line in enumerate(lines):
            if 'MPD-D' in line and 'MPD-N' in line:
                # Next lines should be OD and OS with values
                if i + 1 < len(lines):
                    od_line = lines[i+1]
                    # MPD-D value: "OD 31.0 25.0 Panto: Dist PD: 66.0"
                    # Or:        "OD 14.0          Panto: Dist PD: 66.0"
                    m_od = re.match(r'OD\s+(\d+\.?\d*)(?:\s+(\d+\.?\d*))?', od_line)
                    if m_od:
                        self.extracted_data["od_pd_distance"] = m_od.group(1)
                        # The second value (MPD-N) is Seg Height for OD
                        if m_od.group(2):
                            self.extracted_data["od_seg_height"] = m_od.group(2)
                    
                    # Extract binocular Dist PD if present
                    m_dist = re.search(r'Dist\s*PD[:\s]*(\d+\.?\d*)', od_line)
                    if m_dist:
                        self.extracted_data["pd_distance"] = m_dist.group(1)
                
                if i + 2 < len(lines):
                    os_line = lines[i+2]
                    m_os = re.match(r'OS\s+(\d+\.?\d*)(?:\s+(\d+\.?\d*))?', os_line)
                    if m_os:
                        self.extracted_data["os_pd_distance"] = m_os.group(1)
                        # Second value is Seg Height for OS
                        if m_os.group(2):
                            self.extracted_data["os_seg_height"] = m_os.group(2)
                    
                    # Extract binocular Near PD if present (from label, not MPD-N)
                    m_near = re.search(r'Near\s*PD[:\s]*(\d+\.?\d*)', os_line)
                    if m_near:
                        self.extracted_data["pd_near"] = m_near.group(1)
                break

        # Fallback: if no monocular MPD-D values, derive from binocular PD
        # by dividing it in half for each eye.
        # Prefer Near PD over Dist PD if Near PD has a value.
        if ("od_pd_distance" not in self.extracted_data or 
            "os_pd_distance" not in self.extracted_data):
            # Choose which binocular value to use: Near PD first, then Dist PD
            source_value = None
            if "pd_near" in self.extracted_data:
                source_value = self.extracted_data["pd_near"]
            elif "pd_distance" in self.extracted_data:
                source_value = self.extracted_data["pd_distance"]
            
            if source_value:
                try:
                    half = round(float(source_value) / 2.0, 1)
                    half_str = f"{half:.1f}"
                    if "od_pd_distance" not in self.extracted_data:
                        self.extracted_data["od_pd_distance"] = half_str
                    if "os_pd_distance" not in self.extracted_data:
                        self.extracted_data["os_pd_distance"] = half_str
                except (ValueError, TypeError):
                    pass

    def _parse_frame_info(self, text: str):
        lines = text.split('\n')

        for line in lines:
            # Style/Model
            m = re.search(r'Style[:\s]*([A-Za-z0-9][A-Za-z0-9 \-\.\/]+?)(?:\s+A:|$)', line)
            if m:
                self.extracted_data["frame_model"] = m.group(1).strip()
                continue
            
            # Manuf., Bridg, Eye all on same line: "Manuf.: Safilo USA Bridg 16.0 Eye: 53.0"
            # Or: "Manuf.: New Millennium Bridg 19.0 Eye: 55.0"
            m_mfg = re.search(r'Manuf\.:\s*([A-Za-z][A-Za-z ]+?)(?:\s+Bridg|\s+Color|$)', line)
            if m_mfg:
                self.extracted_data["frame_manufacturer"] = m_mfg.group(1).strip()
            
            # Bridge value (may follow manufacturer on same line)
            m = re.search(r'Bridg\s+(\d+\.?\d*)', line)
            if m:
                self.extracted_data["frame_bridge"] = m.group(1).strip()
            
            # Eye size
            m = re.search(r'Eye[:\s]*(\d+\.?\d*)', line)
            if m:
                self.extracted_data["frame_eye"] = m.group(1).strip()
                continue

            # Color
            m = re.search(r'Color[:\s]*([A-Za-z0-9][A-Za-z0-9 \-\.\(\)]+?)(?:\s+Circ|\s+Dbl|$)', line)
            if m:
                self.extracted_data["frame_color"] = m.group(1).strip()
                continue

            # Temple
            m = re.search(r'Temple[:\s]*(\d+\.?\d*)', line)
            if m:
                self.extracted_data["frame_temple"] = m.group(1).strip()
                continue

    def _parse_lens_info(self, text: str):
        lines = text.split('\n')

        for line in lines:
            # Lens type - look for "Custom Progressives" or similar
            # Stop before BIF:/TRIF:/PAL: labels which may follow on same line
            # Note: include / in allowed chars for values like "4.00/.12"
            m = re.search(r'OD\s*Lens[:\s]*([A-Za-z0-9][A-Za-z0-9\s\-\.\/\(\)]+?)(?:\s+BIF:|\s+TRIF:|\s+PAL:|$)', line)
            if m:
                lens_type = m.group(1).strip()
                if lens_type and lens_type not in ['BIF:', 'TRIF:', 'PAL:']:
                    self.extracted_data["lens_type"] = lens_type

            # Material - just the first word/value (stop at space, paren, or tab)
            # Don't continue - other lens info may be on same line
            m = re.search(r'Material[:\s]*([A-Za-z][A-Za-z0-9\-\.]+)', line)
            if m:
                val = m.group(1).strip()
                if val and 'Tint' not in val:
                    self.extracted_data["lens_material"] = val

            # AR Coating
            m = re.search(r'AR\s*Coating[:\s]*([A-Za-z0-9\s\-\.\(\)]*)', line)
            if m:
                val = m.group(1).strip()
                if val:
                    self.extracted_data["lens_coatings"] = val

            # Tint Factor - just the first word
            m = re.search(r'Tint\s*Factor[:\s]*([A-Za-z][A-Za-z0-9\-\.]+)', line)
            if m:
                val = m.group(1).strip()
                if val and 'AR' not in val and 'Coating' not in val:
                    self.extracted_data["lens_tint"] = val

            # Photochromic - only when "Photochromatics" appears as a value
            # after the "Photochr.:" label (not just the label itself)
            if re.search(r'Photochr\.?:\s*Photochromatics', line, re.IGNORECASE):
                self.extracted_data["lens_photochromic"] = "Yes"

            # Polarized - only when a value follows the label
            # "Polarized: UV Treats:" means NO polarized value (next label follows)
            # Require at least one space after colon so lookahead sees the next word
            if re.search(r'Polarized:\s+(?!UV\s*Treats|Mirror\s*Coat|Other\s*Coat|Scr\.?\s*Coat)', line, re.IGNORECASE):
                self.extracted_data["lens_polarized"] = "Yes"

            # Scratch Coat
            m = re.search(r'Scr\.?\s*Coat[:\s]*([A-Za-z0-9\-\.]*)', line)
            if m:
                val = m.group(1).strip()
                if val:
                    self.extracted_data["lens_scratch_coat"] = val

            # UV Protection
            if re.search(r'UV\s*Protection', line, re.IGNORECASE):
                if "lens_coatings" in self.extracted_data:
                    if "UV" not in self.extracted_data["lens_coatings"]:
                        self.extracted_data["lens_coatings"] += ", UV Protection"
                else:
                    self.extracted_data["lens_coatings"] = "UV Protection"

    def _parse_misc(self, text: str):
        lines = text.split('\n')

        # Special Instructions - look for text after "Special Instructions" line
        for i, line in enumerate(lines):
            if 'Special Instructions' in line:
                if i + 1 < len(lines):
                    instr = lines[i+1].strip()
                    if instr:
                        self.extracted_data["comments"] = instr
                break

        # Source
        for line in lines:
            m = re.search(r'Source[:\s]*([A-Za-z0-9\s\-\.]+)', line)
            if m:
                self.extracted_data["source"] = m.group(1).strip()
                break

    def get_formatted_prescription(self) -> str:
        lines = []
        lines.append("=" * 50)
        lines.append("EXTRACTED SPECTACLE ORDER DATA")
        lines.append("=" * 50)

        if "practice_name" in self.extracted_data:
            lines.append(f"Practice: {self.extracted_data['practice_name']}")
        if "patient_name" in self.extracted_data:
            lines.append(f"Patient: {self.extracted_data['patient_name']}")
        if "patient_dob" in self.extracted_data:
            lines.append(f"DOB: {self.extracted_data['patient_dob']}")
        if "patient_id" in self.extracted_data:
            lines.append(f"Patient ID: {self.extracted_data['patient_id']}")
        if "doctor_name" in self.extracted_data:
            lines.append(f"Doctor: {self.extracted_data['doctor_name']}")
        if "order_number" in self.extracted_data:
            lines.append(f"Order #: {self.extracted_data['order_number']}")
        if "order_date" in self.extracted_data:
            lines.append(f"Order Date: {self.extracted_data['order_date']}")

        lines.append("")
        lines.append("--- Prescription ---")
        lines.append(f"  {'':>10} {'SPH':>8} {'CYL':>8} {'AXIS':>6} {'ADD':>8}")
        od_sph = self.extracted_data.get("od_sph", "")
        od_cyl = self.extracted_data.get("od_cyl", "")
        od_axis = self.extracted_data.get("od_axis", "")
        od_add = self.extracted_data.get("od_add", "")
        lines.append(f"  {'OD (R)':>10} {od_sph:>8} {od_cyl:>8} {od_axis:>6} {od_add:>8}")

        os_sph = self.extracted_data.get("os_sph", "")
        os_cyl = self.extracted_data.get("os_cyl", "")
        os_axis = self.extracted_data.get("os_axis", "")
        os_add = self.extracted_data.get("os_add", "")
        lines.append(f"  {'OS (L)':>10} {os_sph:>8} {os_cyl:>8} {os_axis:>6} {os_add:>8}")

        lines.append("")
        lines.append("--- Pupillary Distance & Seg Height ---")
        if "od_pd_distance" in self.extracted_data:
            lines.append(f"  OD (R) Dist PD (MPD-D): {self.extracted_data['od_pd_distance']}")
        if "os_pd_distance" in self.extracted_data:
            lines.append(f"  OS (L) Dist PD (MPD-D): {self.extracted_data['os_pd_distance']}")
        if "pd_distance" in self.extracted_data:
            lines.append(f"  Binocular Dist PD: {self.extracted_data['pd_distance']}")
        if "pd_near" in self.extracted_data:
            lines.append(f"  Binocular Near PD: {self.extracted_data['pd_near']}")
        if "od_seg_height" in self.extracted_data or "os_seg_height" in self.extracted_data:
            lines.append(f"  OD (R) Seg Height: {self.extracted_data.get('od_seg_height', '')}")
            lines.append(f"  OS (L) Seg Height: {self.extracted_data.get('os_seg_height', '')}")

        lines.append("")
        lines.append("--- Frame ---")
        for field in ["frame_manufacturer", "frame_model", "frame_color", "frame_eye", "frame_bridge", "frame_temple"]:
            if field in self.extracted_data:
                label = field.replace("frame_", "").replace("_", " ").title()
                lines.append(f"  {label}: {self.extracted_data[field]}")

        lines.append("")
        lines.append("--- Lens ---")
        for field in ["lens_type", "lens_material", "lens_coatings", "lens_tint", "lens_photochromic", "lens_polarized", "lens_scratch_coat"]:
            if field in self.extracted_data:
                label = field.replace("lens_", "").replace("_", " ").title()
                lines.append(f"  {label}: {self.extracted_data[field]}")

        if "comments" in self.extracted_data:
            lines.append(f"\nSpecial Instructions: {self.extracted_data['comments']}")

        lines.append("=" * 50)
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parser = SpectacleOrderParser()
        data = parser.parse(sys.argv[1])
        print(parser.get_formatted_prescription())
        print("\nRaw extracted data:")
        for key, value in data.items():
            print(f"  {key}: {value}")
    else:
        print("Usage: python pdf_parser.py <path_to_pdf>")