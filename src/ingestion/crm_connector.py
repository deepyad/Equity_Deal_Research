"""
CRM data connector and normalizer.

This module handles extraction and normalization of structured deal data
from CRM systems, including financial metrics, metadata, and categorical fields.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import logging

from src.models.deal import Deal, DealMetadata, StructuredFeatures

logger = logging.getLogger(__name__)


class CRMConnector:
    """
    Connector for extracting and normalizing CRM data.
    
    This class handles:
    - Loading deal data from CSV/JSON files
    - Normalizing currencies and date formats
    - Standardizing sector taxonomies
    - Validating and cleaning data
    """
    
    # Standard sector taxonomy mapping
    SECTOR_MAPPING = {
        "saas": "Software",
        "software": "Software",
        "healthcare_it": "Healthcare IT",
        "healthcare it": "Healthcare IT",
        "fintech": "Financial Technology",
        "ecommerce": "E-commerce",
        "manufacturing": "Manufacturing",
        "services": "Business Services"
    }
    
    # Deal type normalization
    DEAL_TYPE_MAPPING = {
        "growth": "Growth",
        "buyout": "Buyout",
        "minority": "Minority",
        "majority": "Majority"
    }
    
    def __init__(self, data_path: Optional[str] = None):
        """
        Initialize CRM connector.
        
        Args:
            data_path: Path to CRM data directory or file
        """
        self.data_path = Path(data_path) if data_path else None
        self.sector_stats: Dict[str, Dict[str, float]] = {}
    
    def load_from_csv(self, file_path: str) -> pd.DataFrame:
        """
        Load CRM data from CSV file.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            DataFrame with CRM data
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CRM data file not found: {file_path}")
        
        logger.info(f"Loading CRM data from {file_path}")
        df = pd.read_csv(file_path)
        logger.info(f"Loaded {len(df)} records")
        return df
    
    def load_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load CRM data from JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of deal dictionaries
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CRM data file not found: {file_path}")
        
        logger.info(f"Loading CRM data from {file_path}")
        with open(file_path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} records")
        return data
    
    def normalize_currency(self, value: Any, currency: str = "USD") -> Optional[float]:
        """
        Normalize currency values to USD.
        
        Args:
            value: Currency value (can be string or number)
            currency: Source currency code
            
        Returns:
            Normalized value in USD or None if invalid
        """
        if pd.isna(value) or value is None:
            return None
        
        try:
            # Convert to float if string (e.g., "$1.5M" -> 1500000)
            if isinstance(value, str):
                value = self._parse_currency_string(value)
            
            if value is None:
                return None
            
            # TODO: Implement actual currency conversion
            # For now, assume all values are in USD
            return float(value)
        
        except (ValueError, TypeError):
            logger.warning(f"Failed to normalize currency value: {value}")
            return None
    
    def _parse_currency_string(self, value: str) -> Optional[float]:
        """
        Parse currency string (e.g., "$1.5M", "2.3B") to float.
        
        Args:
            value: Currency string
            
        Returns:
            Numeric value or None
        """
        if not isinstance(value, str):
            return None
        
        # Remove currency symbols and whitespace
        value = value.replace("$", "").replace(",", "").strip().upper()
        
        # Handle multipliers
        multipliers = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
        
        for suffix, mult in multipliers.items():
            if value.endswith(suffix):
                try:
                    num = float(value[:-1])
                    return num * mult
                except ValueError:
                    return None
        
        try:
            return float(value)
        except ValueError:
            return None
    
    def normalize_sector(self, sector: str) -> str:
        """
        Normalize sector name to standard taxonomy.
        
        Args:
            sector: Raw sector name from CRM
            
        Returns:
            Normalized sector name
        """
        if not sector or pd.isna(sector):
            return "Unknown"
        
        sector_lower = str(sector).lower().strip()
        
        # Check direct mapping
        if sector_lower in self.SECTOR_MAPPING:
            return self.SECTOR_MAPPING[sector_lower]
        
        # Check partial matches
        for key, value in self.SECTOR_MAPPING.items():
            if key in sector_lower:
                return value
        
        # Return capitalized original if no match
        return sector.title()
    
    def normalize_deal_type(self, deal_type: str) -> str:
        """
        Normalize deal type to standard format.
        
        Args:
            deal_type: Raw deal type from CRM
            
        Returns:
            Normalized deal type
        """
        if not deal_type or pd.isna(deal_type):
            return "Growth"
        
        deal_type_lower = str(deal_type).lower().strip()
        
        if deal_type_lower in self.DEAL_TYPE_MAPPING:
            return self.DEAL_TYPE_MAPPING[deal_type_lower]
        
        return deal_type.title()
    
    def extract_deal(self, record: Dict[str, Any]) -> Deal:
        """
        Extract and normalize a Deal object from CRM record.
        
        Args:
            record: Dictionary containing deal data from CRM
            
        Returns:
            Normalized Deal object
        """
        # Extract metadata
        metadata = DealMetadata(
            deal_id=str(record.get("deal_id", record.get("id", "unknown"))),
            company_name=str(record.get("company_name", record.get("company", "Unknown"))),
            sector=self.normalize_sector(record.get("sector", "")),
            subsector=record.get("subsector"),
            geography=record.get("geography", record.get("region", "US")),
            deal_type=self.normalize_deal_type(record.get("deal_type", "")),
            deal_year=int(record.get("deal_year", record.get("year", 2024))),
            deal_size=self.normalize_currency(record.get("deal_size", record.get("deal_value"))),
            ownership_type=record.get("ownership_type"),
            outcome=record.get("outcome"),
            fund=record.get("fund", record.get("team"))
        )
        
        # Extract structured features
        structured_features = StructuredFeatures(
            revenue=self.normalize_currency(record.get("revenue", record.get("annual_revenue"))),
            ebitda=self.normalize_currency(record.get("ebitda")),
            growth_rate=self._parse_percentage(record.get("growth_rate", record.get("cagr"))),
            margin=self._parse_percentage(record.get("margin", record.get("ebitda_margin"))),
            enterprise_value=self.normalize_currency(record.get("enterprise_value", record.get("ev"))),
            leverage=record.get("leverage"),
            free_cash_flow=self.normalize_currency(record.get("free_cash_flow", record.get("fcf")))
        )
        
        # Text embeddings will be populated later by embedding service
        from src.models.deal import TextEmbeddings
        text_embeddings = TextEmbeddings()
        
        return Deal(
            metadata=metadata,
            structured_features=structured_features,
            text_embeddings=text_embeddings
        )
    
    def _parse_percentage(self, value: Any) -> Optional[float]:
        """
        Parse percentage value to decimal (e.g., "15%" -> 0.15).
        
        Args:
            value: Percentage value (can be string or number)
            
        Returns:
            Decimal value or None
        """
        if pd.isna(value) or value is None:
            return None
        
        try:
            if isinstance(value, str):
                value = value.replace("%", "").strip()
            return float(value) / 100.0 if abs(float(value)) > 1.0 else float(value)
        except (ValueError, TypeError):
            return None
    
    def load_all_deals(self, file_path: str) -> List[Deal]:
        """
        Load all deals from a data file.
        
        Args:
            file_path: Path to CSV or JSON file
            
        Returns:
            List of Deal objects
        """
        path = Path(file_path)
        
        if path.suffix.lower() == ".csv":
            df = self.load_from_csv(file_path)
            deals = []
            for _, row in df.iterrows():
                try:
                    deal = self.extract_deal(row.to_dict())
                    deals.append(deal)
                except Exception as e:
                    logger.error(f"Error extracting deal from row: {e}")
            return deals
        
        elif path.suffix.lower() == ".json":
            records = self.load_from_json(file_path)
            deals = []
            for record in records:
                try:
                    deal = self.extract_deal(record)
                    deals.append(deal)
                except Exception as e:
                    logger.error(f"Error extracting deal: {e}")
            return deals
        
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")


