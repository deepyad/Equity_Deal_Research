"""
Data validator for deal ingestion.

This module handles validation of deal data according to schema requirements,
completeness checks, and quality scoring. Failed validations trigger manual
review queues and error logging.

According to the consolidated document, this is part of Decision Point D1:
Data quality gate that determines if data should proceed to embedding
generation or be routed to manual review queue.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from src.models.deal import Deal, DealMetadata, StructuredFeatures

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"  # Blocks processing
    WARNING = "warning"  # Allows processing but logs issue
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """
    Represents a single validation issue.
    
    Attributes:
        field: Field name where issue was found
        severity: Severity level (ERROR, WARNING, INFO)
        message: Human-readable error message
        code: Machine-readable error code
    """
    field: str
    severity: ValidationSeverity
    message: str
    code: str


@dataclass
class ValidationResult:
    """
    Result of data validation.
    
    Attributes:
        is_valid: Whether validation passed (no ERROR-level issues)
        quality_score: Overall quality score [0.0, 1.0]
        issues: List of validation issues found
        should_manual_review: Whether data should be sent to manual review queue
    """
    is_valid: bool
    quality_score: float
    issues: List[ValidationIssue]
    should_manual_review: bool


class DataValidator:
    """
    Validator for deal data quality and schema compliance.
    
    This class handles:
    - Schema validation: Ensures all required fields are present and correctly typed
    - Completeness check: Verifies data completeness thresholds are met
    - Quality scoring: Computes overall data quality score [0.0, 1.0]
    
    Decision Point D1: If validation passes (is_valid=True, quality_score > threshold),
    data proceeds to embedding generation. Otherwise, it's routed to manual review queue.
    
    According to the consolidated document, validation should check:
    - Required metadata fields (deal_id, company_name, sector, etc.)
    - Financial data completeness and reasonableness
    - Date format and range validity
    - Sector taxonomy standardization
    - Currency normalization status
    """
    
    def __init__(self, quality_threshold: float = 0.6, require_essential_fields: bool = True):
        """
        Initialize data validator.
        
        Args:
            quality_threshold: Minimum quality score to pass validation (0.0-1.0)
            require_essential_fields: Whether to require essential fields (deal_id, company_name)
        """
        self.quality_threshold = quality_threshold
        self.require_essential_fields = require_essential_fields
        
        # Required fields for validation
        self.required_metadata_fields = ["deal_id", "company_name", "sector"]
        self.essential_financial_fields = ["revenue"]  # At least one financial metric
        
        logger.info(f"DataValidator initialized with quality_threshold={quality_threshold}")
    
    def validate_deal(self, deal: Deal) -> ValidationResult:
        """
        Validate a Deal object.
        
        Performs comprehensive validation including:
        1. Schema validation (required fields present)
        2. Completeness check (sufficient data for embedding)
        3. Quality scoring (overall data quality assessment)
        
        Args:
            deal: Deal object to validate
            
        Returns:
            ValidationResult with validation status, quality score, and issues
        """
        issues: List[ValidationIssue] = []
        
        # 1. Schema validation
        schema_issues = self._validate_schema(deal)
        issues.extend(schema_issues)
        
        # 2. Completeness check
        completeness_issues = self._check_completeness(deal)
        issues.extend(completeness_issues)
        
        # 3. Data quality checks
        quality_issues = self._check_data_quality(deal)
        issues.extend(quality_issues)
        
        # 4. Calculate quality score
        quality_score = self._calculate_quality_score(deal, issues)
        
        # 5. Determine if valid (no ERROR-level issues and quality score passes threshold)
        error_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.ERROR)
        is_valid = error_count == 0 and quality_score >= self.quality_threshold
        
        # 6. Determine if manual review needed
        should_manual_review = (
            error_count > 0 or
            quality_score < self.quality_threshold or
            any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        )
        
        result = ValidationResult(
            is_valid=is_valid,
            quality_score=quality_score,
            issues=issues,
            should_manual_review=should_manual_review
        )
        
        if not is_valid:
            logger.warning(
                f"Deal {deal.metadata.deal_id if deal.metadata else 'unknown'} "
                f"validation failed: quality_score={quality_score:.2f}, "
                f"issues={len(issues)}"
            )
        
        return result
    
    def _validate_schema(self, deal: Deal) -> List[ValidationIssue]:
        """
        Validate schema compliance (required fields present).
        
        Args:
            deal: Deal object to validate
            
        Returns:
            List of validation issues
        """
        issues: List[ValidationIssue] = []
        
        if not deal.metadata:
            issues.append(ValidationIssue(
                field="metadata",
                severity=ValidationSeverity.ERROR,
                message="Deal metadata is missing",
                code="MISSING_METADATA"
            ))
            return issues
        
        metadata = deal.metadata
        
        # Check required metadata fields
        if not metadata.deal_id or not metadata.deal_id.strip():
            issues.append(ValidationIssue(
                field="metadata.deal_id",
                severity=ValidationSeverity.ERROR,
                message="Deal ID is required",
                code="MISSING_DEAL_ID"
            ))
        
        if not metadata.company_name or not metadata.company_name.strip():
            issues.append(ValidationIssue(
                field="metadata.company_name",
                severity=ValidationSeverity.ERROR,
                message="Company name is required",
                code="MISSING_COMPANY_NAME"
            ))
        
        if not metadata.sector or not metadata.sector.strip():
            issues.append(ValidationIssue(
                field="metadata.sector",
                severity=ValidationSeverity.WARNING,
                message="Sector is missing, will default to 'Unknown'",
                code="MISSING_SECTOR"
            ))
        
        # Check deal_year validity
        if metadata.deal_year:
            if metadata.deal_year < 2000 or metadata.deal_year > 2050:
                issues.append(ValidationIssue(
                    field="metadata.deal_year",
                    severity=ValidationSeverity.WARNING,
                    message=f"Deal year {metadata.deal_year} seems unreasonable",
                    code="INVALID_YEAR"
                ))
        
        return issues
    
    def _check_completeness(self, deal: Deal) -> List[ValidationIssue]:
        """
        Check data completeness (sufficient data for meaningful embedding).
        
        Args:
            deal: Deal object to validate
            
        Returns:
            List of validation issues
        """
        issues: List[ValidationIssue] = []
        
        if not deal.structured_features:
            issues.append(ValidationIssue(
                field="structured_features",
                severity=ValidationSeverity.WARNING,
                message="Structured features missing, only text embeddings will be used",
                code="MISSING_STRUCTURED_FEATURES"
            ))
            return issues
        
        features = deal.structured_features
        
        # Check if any financial metrics are present
        has_financial_data = any([
            features.revenue is not None,
            features.ebitda is not None,
            features.enterprise_value is not None,
            features.growth_rate is not None,
            features.margin is not None
        ])
        
        if not has_financial_data and self.require_essential_fields:
            issues.append(ValidationIssue(
                field="structured_features",
                severity=ValidationSeverity.WARNING,
                message="No financial data available, similarity search will rely on text only",
                code="NO_FINANCIAL_DATA"
            ))
        
        # Check if text embeddings exist
        has_text_data = (
            deal.text_embeddings and
            deal.text_embeddings.get_primary_embedding() is not None
        )
        
        if not has_text_data and not has_financial_data:
            issues.append(ValidationIssue(
                field="text_embeddings",
                severity=ValidationSeverity.ERROR,
                message="Neither text embeddings nor financial data available",
                code="NO_DATA_AVAILABLE"
            ))
        
        return issues
    
    def _check_data_quality(self, deal: Deal) -> List[ValidationIssue]:
        """
        Check data quality and reasonableness.
        
        Args:
            deal: Deal object to validate
            
        Returns:
            List of validation issues
        """
        issues: List[ValidationIssue] = []
        
        if not deal.structured_features:
            return issues
        
        features = deal.structured_features
        
        # Check for unreasonable financial values
        if features.revenue is not None and features.revenue < 0:
            issues.append(ValidationIssue(
                field="structured_features.revenue",
                severity=ValidationSeverity.WARNING,
                message="Revenue is negative, may be data error",
                code="NEGATIVE_REVENUE"
            ))
        
        if features.growth_rate is not None:
            if features.growth_rate < -1.0 or features.growth_rate > 5.0:
                issues.append(ValidationIssue(
                    field="structured_features.growth_rate",
                    severity=ValidationSeverity.WARNING,
                    message=f"Growth rate {features.growth_rate:.2%} seems extreme",
                    code="EXTREME_GROWTH_RATE"
                ))
        
        if features.margin is not None:
            if features.margin < -1.0 or features.margin > 1.0:
                issues.append(ValidationIssue(
                    field="structured_features.margin",
                    severity=ValidationSeverity.WARNING,
                    message=f"Margin {features.margin:.2%} outside normal range",
                    code="INVALID_MARGIN"
                ))
        
        # Check consistency between related fields
        if features.revenue is not None and features.ebitda is not None:
            if features.revenue > 0 and abs(features.ebitda) > features.revenue * 2:
                issues.append(ValidationIssue(
                    field="structured_features.ebitda",
                    severity=ValidationSeverity.INFO,
                    message="EBITDA seems inconsistent with revenue",
                    code="INCONSISTENT_EBITDA"
                ))
        
        return issues
    
    def _calculate_quality_score(self, deal: Deal, issues: List[ValidationIssue]) -> float:
        """
        Calculate overall data quality score [0.0, 1.0].
        
        Scoring factors:
        - Presence of required fields (30%)
        - Financial data completeness (30%)
        - Text data availability (20%)
        - Data quality/reasonableness (20%)
        
        Args:
            deal: Deal object
            issues: List of validation issues
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 1.0
        
        # Deduct points for issues
        for issue in issues:
            if issue.severity == ValidationSeverity.ERROR:
                score -= 0.3  # Significant penalty for errors
            elif issue.severity == ValidationSeverity.WARNING:
                score -= 0.1  # Moderate penalty for warnings
            elif issue.severity == ValidationSeverity.INFO:
                score -= 0.05  # Small penalty for info
        
        # Bonus for data completeness
        if deal.structured_features:
            features = deal.structured_features
            financial_fields = [
                features.revenue, features.ebitda, features.growth_rate,
                features.margin, features.enterprise_value
            ]
            completeness = sum(1 for f in financial_fields if f is not None) / len(financial_fields)
            score += completeness * 0.1  # Up to 10% bonus
        
        # Bonus for text embeddings
        if deal.text_embeddings and deal.text_embeddings.get_primary_embedding():
            score += 0.1  # 10% bonus for text data
        
        return max(0.0, min(1.0, score))  # Clamp to [0.0, 1.0]
    
    def validate_batch(self, deals: List[Deal]) -> List[Tuple[Deal, ValidationResult]]:
        """
        Validate multiple deals in batch.
        
        Args:
            deals: List of Deal objects to validate
            
        Returns:
            List of (deal, validation_result) tuples
        """
        results = []
        for deal in deals:
            result = self.validate_deal(deal)
            results.append((deal, result))
        return results

