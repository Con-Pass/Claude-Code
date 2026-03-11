"""
Constants for the ConPass Agent application.
Centralized location for all magic numbers, literals, and configuration values.
"""


# OCR Service Constants
class OCRConstants:
    """Constants related to OCR service."""

    # Default values
    DEFAULT_LANGUAGE = "jpn"
    DEFAULT_DPI = 300

    # DPI constraints
    MIN_DPI = 100
    MAX_DPI = 600

    # File size limits
    MAX_FILE_SIZE_MB = 10

    # Supported file types
    SUPPORTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/tiff"]
    SUPPORTED_PDF_TYPE = "application/pdf"

    # OCR languages
    SUPPORTED_LANGUAGES = ["eng", "jpn", "eng+jpn"]

    # Health check status
    HEALTH_STATUS_HEALTHY = "healthy"
    HEALTH_STATUS_UNHEALTHY = "unhealthy"

    # File types
    FILE_TYPE_PDF = "pdf"
    FILE_TYPE_IMAGE = "image"

    # Processing constraints
    MIN_PAGE_COUNT = 0
    MIN_PROCESSING_TIME = 0.0

    # Quality thresholds
    MIN_CONFIDENCE = 70.0
    MIN_HIRAGANA_ACCURACY = 85.0
    MIN_KATAKANA_ACCURACY = 80.0
    MIN_KANJI_ACCURACY = 75.0
    MAX_CHARACTER_ERROR_RATE = 15.0
    MAX_PROCESSING_TIME = 30.0

    # Script weight factors for Japanese confidence
    SCRIPT_WEIGHTS = {"hiragana": 0.3, "katakana": 0.3, "kanji": 0.4}

    # Quality grades
    QUALITY_GRADES = {
        "A": {"min_accuracy": 95, "min_confidence": 90},
        "B": {"min_accuracy": 85, "min_confidence": 80},
        "C": {"min_accuracy": 75, "min_confidence": 70},
        "D": {"min_accuracy": 65, "min_confidence": 60},
        "F": {"min_accuracy": 0, "min_confidence": 0},
    }

    # Performance optimization settings
    MAX_PARALLEL_WORKERS = 4
    ADAPTIVE_DPI_ENABLED = True

    # DPI optimization strategies
    DPI_STRATEGIES = {
        "text_dense": 200,  # Lower DPI for dense text
        "text_normal": 300,  # Standard DPI for normal text
        "image_heavy": 400,  # Higher DPI for image-heavy content
        "mixed_content": 300,  # Standard DPI for mixed content
    }
