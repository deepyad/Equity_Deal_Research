"""
Data ingestion layer for the Deal Similarity System.

This package handles data extraction and normalization from various sources:
- CRM systems (structured data)
- PDF documents (CIMs, investment memos, notes)
- Data validation and quality checks

According to the consolidated document, the ingestion layer includes:
- CRM Connector: Field mapping, currency conversion, date normalization
- Document Parser: PDF OCR/LayoutLM, section extraction, table parsing
- Data Validator: Schema validation, completeness check, quality scoring (Decision Point D1)
"""

from .crm_connector import CRMConnector
from .pdf_extractor import PDFExtractor
from .validator import DataValidator, ValidationResult, ValidationIssue, ValidationSeverity

__all__ = [
    "CRMConnector",
    "PDFExtractor",
    "DataValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity"
]


