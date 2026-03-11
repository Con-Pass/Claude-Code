#!/usr/bin/env python3
"""
Test script for Google Document AI integration.
Tests the Document AI service functionality without starting the full server.
"""

# mypy: ignore-errors
import sys
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


def create_test_image():
    """Create a test image with Japanese text for Document AI testing."""
    try:
        # Create a simple test image
        img = Image.new("RGB", (400, 200), color="white")
        draw = ImageDraw.Draw(img)

        # Try to use a Japanese font, fallback to default
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20
            )
        except Exception:
            font = ImageFont.load_default()

        # Add some test text
        test_text = "Test Document AI Integration"
        draw.text((50, 50), test_text, fill="black", font=font)

        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        return img_bytes.getvalue()

    except Exception as e:
        logger.error(f"Failed to create test image: {e}")
        return None


def test_document_ai_service():
    """Test the Google Document AI service."""
    print("Testing Google Document AI Service...")
    print("=" * 50)

    try:
        # Test 1: Service initialization
        print("1. Testing service initialization...")
        GoogleDocumentAIService()
        print("   PASS: Service initialized successfully")

        # Test 2: Create test image
        print("\n2. Creating test image...")
        test_image_data = create_test_image()
        if test_image_data:
            print(f"   PASS: Test image created ({len(test_image_data)} bytes)")
        else:
            print("   FAIL: Failed to create test image")
            return False

        # Test 3: Test Document AI processing (if configured)
        print("\n3. Testing Document AI processing...")
        try:
            result = GoogleDocumentAIService.extract_text_from_file(
                file_path=test_image_data, lang="jpn"
            )
            print("   PASS: Document AI processing successful")
            print(f"   Result: {result.text[:100]}...")
            print(f"   Confidence: {result.confidence:.2f}")
            print(f"   Processing time: {result.processing_time:.2f}s")
            print(f"   Engine: {result.engine}")

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

        # Test 4: Test unified OCR service
        print("\n4. Testing unified OCR service with Document AI...")
        try:
            from app.services.ocr_service import OCRService

            result = OCRService.extract_text_from_file(
                file_path=test_image_data, lang="jpn", engine="document_ai"
            )
            print("   PASS: Unified OCR service with Document AI successful")
            print(f"   Result type: {type(result).__name__}")

        except Exception as e:
            print(f"   ERROR: Unified OCR service failed: {e}")
            return False

        print("\nSUCCESS: All Document AI tests passed!")
        return True

    except Exception as e:
        print(f"\nFAIL: Document AI testing failed: {e}")
        return False


def test_tesseract_fallback():
    """Test Tesseract as fallback when Document AI is not available."""
    print("\nTesting Tesseract Fallback...")
    print("=" * 30)

    try:
        from app.services.ocr_service import OCRService

        # Create test image
        test_image_data = create_test_image()
        if not test_image_data:
            print("   FAIL: Could not create test image")
            return False

        # Test Tesseract engine
        result = OCRService.extract_text_from_file(
            file_path=test_image_data, lang="jpn", engine="tesseract"
        )

        print("   PASS: Tesseract fallback successful")
        print(f"   Result: {result.extracted_text[:100]}...")
        print(f"   Confidence: {result.confidence_score:.2f}")
        print("   Engine: Tesseract")

        return True

    except Exception as e:
        print(f"   ERROR: Tesseract fallback failed: {e}")
        return False


def main():
    """Main test function."""
    print("Google Document AI Integration Test")
    print("=" * 50)

    # Test Document AI service
    doc_ai_success = test_document_ai_service()

    # Test Tesseract fallback
    tesseract_success = test_tesseract_fallback()

    print("\n" + "=" * 50)
    print("Test Summary:")
    print(f"- Document AI Service: {'PASS' if doc_ai_success else 'FAIL/SKIP'}")
    print(f"- Tesseract Fallback: {'PASS' if tesseract_success else 'FAIL'}")

    if tesseract_success:
        print("\nSUCCESS: OCR service integration is working!")
        print("\nNext steps:")
        print("1. Configure Google Cloud Document AI for advanced features")
        print("2. Set up environment variables for Document AI")
        print("3. Test with real documents")
    else:
        print("\nFAIL: OCR service integration needs fixes.")
        print("\nTroubleshooting:")
        print("1. Ensure Tesseract is installed and configured")
        print("2. Check Japanese language pack availability")
        print("3. Verify file permissions and dependencies")


if __name__ == "__main__":
    main()
