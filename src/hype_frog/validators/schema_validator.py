"""
Schema.org JSON-LD validation against required property definitions.
Validates structure, required fields, and data types without network calls.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

REQUIRED_PROPERTIES: dict[str, list[str]] = {
    "FAQPage": ["mainEntity"],
    "Question": ["name", "acceptedAnswer"],
    "Answer": ["text"],
    "Event": ["name", "startDate", "location"],
    "VirtualEvent": ["name", "startDate"],
    "Organization": ["name", "url"],
    "LocalBusiness": ["name", "address", "telephone"],
    "Person": ["name"],
    "Article": ["headline", "author", "datePublished"],
    "NewsArticle": ["headline", "author", "datePublished"],
    "BlogPosting": ["headline", "author", "datePublished"],
    "WebPage": ["name"],
    "Product": ["name", "offers"],
    "Offer": ["price", "priceCurrency"],
    "BreadcrumbList": ["itemListElement"],
    "ListItem": ["position", "name"],
    "SiteNavigationElement": ["name"],
    "WebSite": ["name", "url"],
    "ItemList": ["itemListElement"],
    "VideoObject": ["name", "description", "thumbnailUrl", "uploadDate"],
    "ImageObject": ["url"],
    "Course": ["name", "description", "provider"],
    "JobPosting": ["title", "description", "datePosted", "hiringOrganization"],
    "Recipe": ["name", "recipeIngredient", "recipeInstructions"],
    "Review": ["itemReviewed", "reviewRating", "author"],
    "AggregateRating": ["ratingValue", "reviewCount"],
    "HowTo": ["name", "step"],
    "HowToStep": ["text"],
    "SpeakableSpecification": [],
}

RECOMMENDED_PROPERTIES: dict[str, list[str]] = {
    "Article": ["image", "publisher", "dateModified"],
    "Event": ["description", "image", "offers", "organizer", "eventStatus"],
    "FAQPage": [],
    "Organization": ["logo", "sameAs", "contactPoint"],
    "Product": ["description", "image", "brand", "sku"],
    "LocalBusiness": ["openingHours", "geo", "image"],
    "Person": ["sameAs", "jobTitle", "affiliation"],
    "VideoObject": ["duration", "contentUrl", "embedUrl"],
    "WebSite": ["potentialAction"],
    "BreadcrumbList": [],
}


@dataclass
class SchemaIssue:
    schema_type: str
    issue_type: str
    property_name: str | None
    message: str
    severity: str


@dataclass
class SchemaValidationResult:
    url: str
    raw_schemas: list[dict[str, Any]] = field(default_factory=list)
    types_found: list[str] = field(default_factory=list)
    types_valid: list[str] = field(default_factory=list)
    types_with_errors: list[str] = field(default_factory=list)
    issues: list[SchemaIssue] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    has_any_schema: bool = False
    is_fully_valid: bool = False

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "Error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "Warning")

    @property
    def summary(self) -> str:
        if not self.has_any_schema:
            return "No schema"
        if self.is_fully_valid:
            return f"Valid ({', '.join(self.types_valid)})"
        return (
            f"{self.error_count} errors, {self.warning_count} warnings "
            f"({', '.join(self.types_found)})"
        )


def validate_schema_object(
    obj: dict[str, Any],
    schema_type: str,
    parent_path: str = "",
) -> list[SchemaIssue]:
    """Recursively validate a single schema object."""
    issues: list[SchemaIssue] = []
    required = REQUIRED_PROPERTIES.get(schema_type, [])
    recommended = RECOMMENDED_PROPERTIES.get(schema_type, [])

    for prop in required:
        if prop not in obj:
            issues.append(
                SchemaIssue(
                    schema_type=schema_type,
                    issue_type="missing_required",
                    property_name=prop,
                    message=f"{schema_type}: missing required property '{prop}'",
                    severity="Error",
                )
            )

    for prop in recommended:
        if prop not in obj:
            issues.append(
                SchemaIssue(
                    schema_type=schema_type,
                    issue_type="missing_recommended",
                    property_name=prop,
                    message=f"{schema_type}: missing recommended property '{prop}'",
                    severity="Warning",
                )
            )

    for key, val in obj.items():
        if isinstance(val, dict) and "@type" in val:
            nested_type = val["@type"]
            if isinstance(nested_type, str):
                issues.extend(
                    validate_schema_object(
                        val,
                        nested_type,
                        parent_path=f"{schema_type}.{key}",
                    )
                )
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "@type" in item:
                    nested_type = item["@type"]
                    if isinstance(nested_type, str):
                        issues.extend(
                            validate_schema_object(
                                item,
                                nested_type,
                                parent_path=f"{schema_type}.{key}[]",
                            )
                        )

    return issues


def _extract_type(obj: dict[str, Any]) -> str | None:
    schema_type = obj.get("@type")
    if isinstance(schema_type, list):
        return schema_type[0] if schema_type else None
    return schema_type if isinstance(schema_type, str) else None


def validate_schemas_from_html(
    url: str,
    json_ld_blocks: list[str],
) -> SchemaValidationResult:
    """Validate all JSON-LD schema blocks found on a page."""
    result = SchemaValidationResult(url=url)

    if not json_ld_blocks:
        return result

    result.has_any_schema = True
    all_valid = True

    for raw in json_ld_blocks:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            result.parse_errors.append(str(exc))
            result.issues.append(
                SchemaIssue(
                    schema_type="Unknown",
                    issue_type="parse_error",
                    property_name=None,
                    message=f"JSON-LD parse error: {exc}",
                    severity="Error",
                )
            )
            all_valid = False
            continue

        result.raw_schemas.append(parsed)

        objects_to_validate: list[dict[str, Any]] = []
        if isinstance(parsed, dict) and "@graph" in parsed:
            graph = parsed["@graph"]
            if isinstance(graph, list):
                objects_to_validate.extend(
                    [obj for obj in graph if isinstance(obj, dict)]
                )
        elif isinstance(parsed, dict) and "@type" in parsed:
            objects_to_validate.append(parsed)
        elif isinstance(parsed, list):
            objects_to_validate.extend(
                [obj for obj in parsed if isinstance(obj, dict)]
            )

        for obj in objects_to_validate:
            schema_type = _extract_type(obj)
            if not schema_type:
                continue

            result.types_found.append(schema_type)
            obj_issues = validate_schema_object(obj, schema_type)
            result.issues.extend(obj_issues)

            errors = [issue for issue in obj_issues if issue.severity == "Error"]
            if errors:
                result.types_with_errors.append(schema_type)
                all_valid = False
            else:
                result.types_valid.append(schema_type)

    result.is_fully_valid = all_valid and result.has_any_schema
    return result


def flatten_to_row(result: SchemaValidationResult) -> dict[str, Any]:
    """Convert validation result to flat dict for crawl row columns."""
    return {
        "Schema Present": result.has_any_schema,
        "Schema Valid": result.is_fully_valid,
        "Schema Types Found": ", ".join(result.types_found) if result.types_found else None,
        "Schema Types Valid": ", ".join(result.types_valid) if result.types_valid else None,
        "Schema Types With Errors": (
            ", ".join(result.types_with_errors) if result.types_with_errors else None
        ),
        "Schema Error Count": result.error_count,
        "Schema Warning Count": result.warning_count,
        "Schema Parse Error Detail": (
            "; ".join(result.parse_errors) if result.parse_errors else None
        ),
        "Schema Validation Summary": result.summary,
        "Schema Issues Detail": (
            " | ".join(issue.message for issue in result.issues[:5])
            if result.issues
            else None
        ),
    }
