"""
Feedback logger for analyst interactions.

This module handles logging of analyst feedback on similarity search results,
enabling continuous learning and model improvement.

According to the consolidated document, this module:
- Logs feedback labels (+1 useful, -1 not useful)
- Captures context (query deal, result deal, similarity context)
- Tracks interaction details (pins, overrides, weight adjustments)
- Stores feedback for batch training triggers (Decision Point D4)
"""

import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict

from src.models.deal import Deal
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class FeedbackLabel(Enum):
    """Feedback labels from analysts."""
    USEFUL = 1  # Deal was useful
    NOT_USEFUL = -1  # Deal was not useful
    PINNED = 2  # Deal was pinned/favorited
    OVERRIDE = 3  # Analyst manually selected this deal


@dataclass
class FeedbackEntry:
    """
    Represents a single feedback entry.
    
    Attributes:
        query_deal_id: ID of the query deal
        result_deal_id: ID of the result deal that was feedbacked on
        label: Feedback label (USEFUL, NOT_USEFUL, PINNED, OVERRIDE)
        context: Similarity context (screening, risk, etc.)
        similarity_score: Original similarity score
        analyst_id: Optional analyst identifier
        notes: Optional notes from analyst
        timestamp: When feedback was recorded
    """
    query_deal_id: str
    result_deal_id: str
    label: FeedbackLabel
    context: str
    similarity_score: float
    analyst_id: Optional[str] = None
    notes: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()


class FeedbackLogger:
    """
    Logger for analyst feedback on similarity results.
    
    This class handles:
    - Logging feedback entries with context
    - Storing feedback in database for training
    - Querying feedback for batch processing
    - Tracking feedback statistics
    
    Decision Point D4: Triggers feedback logging when analyst provides
    useful/not useful, pins, or adjusts weights.
    
    Feedback is used for:
    - Contrastive learning (pull useful pairs closer, push apart irrelevant)
    - Weight re-tuning (w_struct, w_text adjustments)
    - Projection layer updates
    - Normalization parameter updates
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize feedback logger.
        
        Args:
            db_path: Path to feedback database file
        """
        if db_path is None:
            config = get_config()
            paths_config = config.get_paths_config()
            db_path = paths_config.get("feedback_db", "data/feedback.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        logger.info(f"FeedbackLogger initialized with database at {self.db_path}")
    
    def _init_database(self):
        """Initialize feedback database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_deal_id TEXT NOT NULL,
                result_deal_id TEXT NOT NULL,
                label INTEGER NOT NULL,
                context TEXT NOT NULL,
                similarity_score REAL,
                analyst_id TEXT,
                notes TEXT,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for efficient querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_deal_id ON feedback(query_deal_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_result_deal_id ON feedback(result_deal_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_context ON feedback(context)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON feedback(timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def log_feedback(
        self,
        query_deal_id: str,
        result_deal_id: str,
        label: FeedbackLabel,
        context: str,
        similarity_score: float,
        analyst_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Log analyst feedback.
        
        Args:
            query_deal_id: ID of query deal
            result_deal_id: ID of result deal
            label: Feedback label
            context: Similarity context
            similarity_score: Original similarity score
            analyst_id: Optional analyst identifier
            notes: Optional notes
            
        Returns:
            True if successful
        """
        entry = FeedbackEntry(
            query_deal_id=query_deal_id,
            result_deal_id=result_deal_id,
            label=label,
            context=context,
            similarity_score=similarity_score,
            analyst_id=analyst_id,
            notes=notes
        )
        
        return self._store_entry(entry)
    
    def _store_entry(self, entry: FeedbackEntry) -> bool:
        """
        Store feedback entry in database.
        
        Args:
            entry: FeedbackEntry object
            
        Returns:
            True if successful
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO feedback (
                    query_deal_id, result_deal_id, label, context,
                    similarity_score, analyst_id, notes, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.query_deal_id,
                entry.result_deal_id,
                entry.label.value,
                entry.context,
                entry.similarity_score,
                entry.analyst_id,
                entry.notes,
                entry.timestamp.isoformat()
            ))
            
            conn.commit()
            logger.debug(
                f"Logged feedback: {entry.query_deal_id} -> {entry.result_deal_id}, "
                f"label={entry.label.name}"
            )
            return True
        
        except Exception as e:
            logger.error(f"Error storing feedback entry: {e}")
            conn.rollback()
            return False
        
        finally:
            conn.close()
    
    def get_feedback_for_training(
        self,
        min_feedback_count: int = 100,
        context: Optional[str] = None
    ) -> List[FeedbackEntry]:
        """
        Get feedback entries for training (Decision Point P1 trigger).
        
        Args:
            min_feedback_count: Minimum number of feedback entries to retrieve
            context: Optional context filter
            
        Returns:
            List of FeedbackEntry objects
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM feedback WHERE 1=1"
        params = []
        
        if context:
            query += " AND context = ?"
            params.append(context)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(min_feedback_count * 2)  # Get more for filtering
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        entries = []
        for row in rows:
            entry = FeedbackEntry(
                query_deal_id=row["query_deal_id"],
                result_deal_id=row["result_deal_id"],
                label=FeedbackLabel(row["label"]),
                context=row["context"],
                similarity_score=row["similarity_score"],
                analyst_id=row["analyst_id"],
                notes=row["notes"],
                timestamp=datetime.fromisoformat(row["timestamp"])
            )
            entries.append(entry)
        
        logger.info(f"Retrieved {len(entries)} feedback entries for training")
        return entries
    
    def get_positive_pairs(self, context: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        Get positive pairs (deals marked as useful together).
        
        Args:
            context: Optional context filter
            
        Returns:
            List of (query_deal_id, result_deal_id) tuples
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = """
            SELECT DISTINCT query_deal_id, result_deal_id
            FROM feedback
            WHERE label IN (?, ?)
        """
        params = [FeedbackLabel.USEFUL.value, FeedbackLabel.PINNED.value]
        
        if context:
            query += " AND context = ?"
            params.append(context)
        
        cursor.execute(query, params)
        pairs = cursor.fetchall()
        conn.close()
        
        return [(qid, rid) for qid, rid in pairs]
    
    def get_negative_pairs(self, context: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        Get negative pairs (deals marked as not useful).
        
        Args:
            context: Optional context filter
            
        Returns:
            List of (query_deal_id, result_deal_id) tuples
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = """
            SELECT DISTINCT query_deal_id, result_deal_id
            FROM feedback
            WHERE label = ?
        """
        params = [FeedbackLabel.NOT_USEFUL.value]
        
        if context:
            query += " AND context = ?"
            params.append(context)
        
        cursor.execute(query, params)
        pairs = cursor.fetchall()
        conn.close()
        
        return [(qid, rid) for qid, rid in pairs]
    
    def get_feedback_stats(self, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Get feedback statistics.
        
        Args:
            context: Optional context filter
            
        Returns:
            Dictionary with statistics
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = "SELECT label, COUNT(*) as count FROM feedback WHERE 1=1"
        params = []
        
        if context:
            query += " AND context = ?"
            params.append(context)
        
        query += " GROUP BY label"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        stats = {
            "total_feedback": 0,
            "useful": 0,
            "not_useful": 0,
            "pinned": 0,
            "overridden": 0
        }
        
        for label_value, count in rows:
            stats["total_feedback"] += count
            
            if label_value == FeedbackLabel.USEFUL.value:
                stats["useful"] = count
            elif label_value == FeedbackLabel.NOT_USEFUL.value:
                stats["not_useful"] = count
            elif label_value == FeedbackLabel.PINNED.value:
                stats["pinned"] = count
            elif label_value == FeedbackLabel.OVERRIDE.value:
                stats["overridden"] = count
        
        conn.close()
        return stats

