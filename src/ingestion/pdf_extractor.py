"""
PDF document extractor and parser.

This module handles extraction of text content from PDF documents including:
- CIM (Confidential Information Memorandum) documents
- Investment committee memos
- Analyst notes and reports
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    Extractor for text content from PDF documents.
    
    This class handles:
    - Text extraction from PDF files
    - Section-level parsing (business overview, market, financials)
    - Layout-aware extraction preserving document structure
    - Error handling for corrupted or unreadable PDFs
    """
    
    # Common section headers to identify document structure
    SECTION_HEADERS = {
        "business_overview": [
            "business overview", "company overview", "business description",
            "about the company", "company background"
        ],
        "market": [
            "market", "market overview", "market opportunity", "industry",
            "competitive landscape", "market dynamics"
        ],
        "financial": [
            "financial", "financial highlights", "financial performance",
            "financial overview", "financials"
        ],
        "investment": [
            "investment thesis", "investment rationale", "investment memo",
            "investment committee", "ic memo"
        ]
    }
    
    def __init__(self, use_pdfplumber: bool = True):
        """
        Initialize PDF extractor.
        
        Args:
            use_pdfplumber: Whether to prefer pdfplumber over PyPDF2
        """
        self.use_pdfplumber = use_pdfplumber and PDFPLUMBER_AVAILABLE
        
        if not PDFPLUMBER_AVAILABLE and not PYPDF2_AVAILABLE:
            logger.warning("No PDF libraries available. PDF extraction will fail.")
    
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract all text from PDF document.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            RuntimeError: If extraction fails
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        logger.info(f"Extracting text from PDF: {pdf_path}")
        
        if self.use_pdfplumber:
            return self._extract_with_pdfplumber(pdf_path)
        elif PYPDF2_AVAILABLE:
            return self._extract_with_pypdf2(pdf_path)
        else:
            raise RuntimeError("No PDF extraction library available")
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """
        Extract text using pdfplumber (better for tables and layout).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        text_parts = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Error extracting page {page_num}: {e}")
            
            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} characters from PDF")
            return full_text
        
        except Exception as e:
            logger.error(f"Error extracting PDF with pdfplumber: {e}")
            raise RuntimeError(f"PDF extraction failed: {e}")
    
    def _extract_with_pypdf2(self, pdf_path: str) -> str:
        """
        Extract text using PyPDF2 (fallback method).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        text_parts = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Error extracting page {page_num}: {e}")
            
            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} characters from PDF")
            return full_text
        
        except Exception as e:
            logger.error(f"Error extracting PDF with PyPDF2: {e}")
            raise RuntimeError(f"PDF extraction failed: {e}")
    
    def extract_sections(self, pdf_path: str) -> Dict[str, str]:
        """
        Extract text content organized by sections.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary mapping section names to text content
        """
        full_text = self.extract_text(pdf_path)
        
        sections = {
            "overall": full_text,
            "business_overview": "",
            "market": "",
            "financial": "",
            "investment": ""
        }
        
        # Split text into sections based on headers
        lines = full_text.split("\n")
        current_section = "overall"
        current_text = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if line matches a section header
            section_found = False
            for section_name, headers in self.SECTION_HEADERS.items():
                for header in headers:
                    if header in line_lower and len(line_lower) < 100:  # Likely a header
                        # Save previous section
                        if current_section != "overall" and current_text:
                            sections[current_section] = "\n".join(current_text)
                        
                        current_section = section_name
                        current_text = []
                        section_found = True
                        break
                
                if section_found:
                    break
            
            if not section_found:
                current_text.append(line)
        
        # Save last section
        if current_section != "overall" and current_text:
            sections[current_section] = "\n".join(current_text)
        
        # Fallback: if no sections found, use overall text
        if not any(sections[sec] for sec in sections if sec != "overall"):
            sections["business_overview"] = full_text[:len(full_text)//2]
            sections["market"] = full_text[len(full_text)//2:]
        
        return sections
    
    def extract_cim_text(self, pdf_path: str) -> str:
        """
        Extract text from CIM document (convenience method).
        
        Args:
            pdf_path: Path to CIM PDF file
            
        Returns:
            Extracted text content
        """
        return self.extract_text(pdf_path)
    
    def extract_memo_text(self, pdf_path: str) -> str:
        """
        Extract text from investment memo document.
        
        Args:
            pdf_path: Path to investment memo PDF file
            
        Returns:
            Extracted text content
        """
        sections = self.extract_sections(pdf_path)
        
        # Prioritize investment section if available
        if sections.get("investment"):
            return sections["investment"]
        
        return sections.get("overall", "")


