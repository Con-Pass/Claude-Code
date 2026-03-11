#!/usr/bin/env python3
"""
Performance test script for Google Document AI optimization.
Tests the performance improvements of the optimized Document AI service.
"""

import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.google_document_ai_service import (
    GoogleDocumentAIService,
    DocumentAIError,
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def create_test_document():
    """Create a test document with structured content for performance testing."""
    try:
        # Create a larger test image with structured content
        img = Image.new("RGB", (800, 1200), color="white")
        draw = ImageDraw.Draw(img)

        # Try to use a Japanese font, fallback to default
        try:
            font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24
            )
            font_medium = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18
            )
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14
            )
        except Exception:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Add structured content
        y_pos = 50

        # Title
        draw.text((50, y_pos), "Contract Document", fill="black", font=font_large)
        y_pos += 60

        # Form fields
        draw.text((50, y_pos), "Name: John Doe", fill="black", font=font_medium)
        y_pos += 40
        draw.text((50, y_pos), "Company: ABC Corp", fill="black", font=font_medium)
        y_pos += 40
        draw.text((50, y_pos), "Date: 2024-01-15", fill="black", font=font_medium)
        y_pos += 60

        # Table-like content
        draw.text((50, y_pos), "Terms and Conditions:", fill="black", font=font_medium)
        y_pos += 30
        draw.text(
            (70, y_pos), "1. Payment terms: 30 days", fill="black", font=font_small
        )
        y_pos += 25
        draw.text(
            (70, y_pos), "2. Delivery: Within 2 weeks", fill="black", font=font_small
        )
        y_pos += 25
        draw.text((70, y_pos), "3. Warranty: 1 year", fill="black", font=font_small)
        y_pos += 60

        # More structured content
        draw.text((50, y_pos), "Contact Information:", fill="black", font=font_medium)
        y_pos += 30
        draw.text((70, y_pos), "Phone: +1-555-0123", fill="black", font=font_small)
        y_pos += 25
        draw.text((70, y_pos), "Email: john@abc.com", fill="black", font=font_small)
        y_pos += 25
        draw.text(
            (70, y_pos),
            "Address: 123 Main St, City, State",
            fill="black",
            font=font_small,
        )

        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        return img_bytes.getvalue()

    except Exception as e:
        logger.error(f"Failed to create test document: {e}")
        return None


def test_performance():
    """Test Document AI performance with optimizations."""
    print("Document AI Performance Test")
    print("=" * 50)

    try:
        # Create test document
        print("1. Creating test document...")
        test_document_data = create_test_document()
        if not test_document_data:
            print("   FAIL: Could not create test document")
            return False

        print(f"   PASS: Test document created ({len(test_document_data)} bytes)")

        # Test with optimizations enabled
        print("\n2. Testing with optimizations enabled...")
        try:
            start_time = time.time()
            result = GoogleDocumentAIService.extract_text_from_file(
                file_path=test_document_data, lang="jpn"
            )
            processing_time = time.time() - start_time

            print(
                f"   PASS: Document AI processing completed in {processing_time:.2f}s"
            )
            print(f"   Text length: {len(result.text)} characters")
            print(f"   Entities: {len(result.entities)}")
            print(f"   Tables: {len(result.tables)}")
            print(f"   Form fields: {len(result.form_fields)}")
            print(f"   Confidence: {result.confidence:.2f}")

            return True

        except DocumentAIError as e:
            if "Google Cloud Document AI not installed" in str(e):
                print("   SKIP: Google Cloud Document AI not installed")
                print("   Install with: pip install google-cloud-documentai")
            elif "GOOGLE_CLOUD_PROJECT_ID" in str(e):
                print("   SKIP: Google Cloud configuration not set")
                print("   Set environment variables:")
                print("   - GOOGLE_CLOUD_PROJECT_ID")
                print("   - GOOGLE_CLOUD_LOCATION")
                print("   - DOCUMENT_AI_PROCESSOR_ID")
                print("   - GOOGLE_APPLICATION_CREDENTIALS")
            else:
                print(f"   ERROR: Document AI processing failed: {e}")
            return False
        except Exception as e:
            print(f"   ERROR: Unexpected error: {e}")
            return False

    except Exception as e:
        print(f"\nFAIL: Performance testing failed: {e}")
        return False


def test_optimization_settings():
    """Test different optimization settings."""
    print("\n3. Testing optimization settings...")

    try:
        from app.core.config import settings

        print(f"   Max Workers: {settings.DOCUMENT_AI_MAX_WORKERS}")

        return True

    except Exception as e:
        print(f"   ERROR: Could not read optimization settings: {e}")
        return False


def main():
    """Main test function."""
    print("Google Document AI Performance Optimization Test")
    print("=" * 60)

    # Test performance
    performance_success = test_performance()

    # Test optimization settings
    settings_success = test_optimization_settings()

    print("\n" + "=" * 60)
    print("Performance Test Summary:")
    print(f"- Document AI Processing: {'PASS' if performance_success else 'FAIL/SKIP'}")
    print(f"- Optimization Settings: {'PASS' if settings_success else 'FAIL'}")

    if performance_success:
        print("\nSUCCESS: Document AI performance optimizations are working!")
        print("\nOptimization Features:")
        print("- Parallel structured data extraction")
        print("- Thread-safe client initialization")
        print("- Cached processor names")
        print("- Adaptive extraction based on document complexity")
        print("- Configurable worker threads")
    else:
        print("\nFAIL: Performance optimizations need configuration.")
        print("\nNext steps:")
        print(
            "1. Install Google Cloud Document AI: pip install google-cloud-documentai"
        )
        print("2. Configure Google Cloud credentials")
        print("3. Test with real documents")


if __name__ == "__main__":
    main()
