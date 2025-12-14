"""
Metadata store for deal information.

This module handles storage and retrieval of deal metadata using SQLite.
Can be extended to use PostgreSQL for production.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
from datetime import datetime

from src.models.deal import Deal, DealMetadata, StructuredFeatures
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class MetadataStore:
    """
    Metadata database for storing deal information.
    
    Uses SQLite for simplicity. Stores:
    - Deal metadata (sector, geography, deal type, etc.)
    - Structured features (financial metrics)
    - Qualitative tags
    - Timestamps
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize metadata store.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            config = get_config()
            paths_config = config.get_paths_config()
            db_path = paths_config.get("metadata", "data/metadata.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create deals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                deal_id TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                sector TEXT,
                subsector TEXT,
                geography TEXT,
                deal_type TEXT,
                deal_year INTEGER,
                deal_size REAL,
                ownership_type TEXT,
                outcome TEXT,
                fund TEXT,
                revenue REAL,
                ebitda REAL,
                growth_rate REAL,
                margin REAL,
                enterprise_value REAL,
                leverage REAL,
                free_cash_flow REAL,
                qualitative_tags TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sector ON deals(sector)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deal_type ON deals(deal_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deal_year ON deals(deal_year)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_outcome ON deals(outcome)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Metadata database initialized at {self.db_path}")
    
    def add_deal(self, deal: Deal) -> bool:
        """
        Add a deal to the metadata store.
        
        Args:
            deal: Deal object to store
            
        Returns:
            True if successful
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            metadata = deal.metadata
            features = deal.structured_features
            tags = deal.text_embeddings.qualitative_tags if deal.text_embeddings else []
            
            cursor.execute("""
                INSERT OR REPLACE INTO deals (
                    deal_id, company_name, sector, subsector, geography,
                    deal_type, deal_year, deal_size, ownership_type,
                    outcome, fund, revenue, ebitda, growth_rate, margin,
                    enterprise_value, leverage, free_cash_flow,
                    qualitative_tags, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.deal_id,
                metadata.company_name,
                metadata.sector,
                metadata.subsector,
                metadata.geography,
                metadata.deal_type,
                metadata.deal_year,
                metadata.deal_size,
                metadata.ownership_type,
                metadata.outcome,
                metadata.fund,
                features.revenue,
                features.ebitda,
                features.growth_rate,
                features.margin,
                features.enterprise_value,
                features.leverage,
                features.free_cash_flow,
                json.dumps(tags),
                deal.created_at.isoformat(),
                deal.updated_at.isoformat()
            ))
            
            conn.commit()
            logger.debug(f"Added deal {metadata.deal_id} to metadata store")
            return True
        
        except Exception as e:
            logger.error(f"Error adding deal to metadata store: {e}")
            conn.rollback()
            return False
        
        finally:
            conn.close()
    
    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a deal by ID.
        
        Args:
            deal_id: Deal identifier
            
        Returns:
            Deal dictionary or None if not found
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_deals_by_ids(self, deal_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve multiple deals by IDs.
        
        Args:
            deal_ids: List of deal identifiers
            
        Returns:
            List of deal dictionaries
        """
        if not deal_ids:
            return []
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(deal_ids))
        cursor.execute(f"SELECT * FROM deals WHERE deal_id IN ({placeholders})", deal_ids)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def search_deals(self, filters: Optional[Dict[str, Any]] = None,
                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search deals with optional filters.
        
        Args:
            filters: Dictionary of filter criteria (sector, deal_type, etc.)
            limit: Maximum number of results
            
        Returns:
            List of matching deal dictionaries
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM deals WHERE 1=1"
        params = []
        
        if filters:
            if "sector" in filters:
                query += " AND sector = ?"
                params.append(filters["sector"])
            
            if "deal_type" in filters:
                query += " AND deal_type = ?"
                params.append(filters["deal_type"])
            
            if "geography" in filters:
                query += " AND geography = ?"
                params.append(filters["geography"])
            
            if "min_year" in filters:
                query += " AND deal_year >= ?"
                params.append(filters["min_year"])
            
            if "max_year" in filters:
                query += " AND deal_year <= ?"
                params.append(filters["max_year"])
            
            if "outcome" in filters:
                query += " AND outcome = ?"
                params.append(filters["outcome"])
        
        query += " ORDER BY deal_year DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_total_deals(self) -> int:
        """Get total number of deals in the store."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM deals")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def delete_deal(self, deal_id: str) -> bool:
        """
        Delete a deal from the store.
        
        Args:
            deal_id: Deal identifier
            
        Returns:
            True if successful
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM deals WHERE deal_id = ?", (deal_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Error deleting deal: {e}")
            conn.rollback()
            conn.close()
            return False


