"""
ClaimLens AI - Document Processing Service
Parses, cleans, and extracts structured entities from claim documents.
"""

import re
from typing import Dict, Any, List


class DocumentService:
    """
    Handles parsing and normalization of input claim documents:
    1. Claim form
    2. Repair estimate or FIR
    3. Customer incident description
    """

    @staticmethod
    def clean_text(text: str) -> str:
        """Removes duplicate whitespace and normalizes text encoding."""
        if not text:
            return ""
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    @staticmethod
    def extract_key_fields(claim_text: str) -> Dict[str, Any]:
        """
        Extracts foundational entities (dates, amounts, vehicle numbers, registration numbers).
        """
        extracted = {}

        # Look for dates
        date_matches = re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})\b", claim_text)
        if date_matches:
            extracted["detected_dates"] = date_matches

        # Look for monetary amounts
        amount_matches = re.findall(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)", claim_text, re.IGNORECASE)
        if amount_matches:
            cleaned_amounts = []
            for amt in amount_matches:
                try:
                    cleaned_amounts.append(float(amt.replace(",", "")))
                except ValueError:
                    continue
            if cleaned_amounts:
                extracted["detected_amounts"] = cleaned_amounts

        # Look for vehicle reg numbers (e.g. DL01AB1234, MH 12 CD 3456)
        vehicle_reg = re.findall(r"\b[A-Z]{2}[-\s]?[0-9]{1,2}[-\s]?[A-Z]{1,3}[-\s]?[0-9]{4}\b", claim_text)
        if vehicle_reg:
            extracted["detected_vehicle_numbers"] = vehicle_reg

        return extracted
