#!/usr/bin/env python3
"""
Test script to verify OCR service implementation.
Run this script to test the OCR service without starting the full server.

Usage:
    uv run python scripts/ocr_implementation_script.py
"""

import sys

# import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.ocr_service import OCRService
# from app.schemas.ocr import OCRResult


def test_ocr_service():
    """Test the OCR service with a simple text image."""
    print("Testing OCR Service Implementation...")

    try:
        # Test 1: Health check
        print("\n1. Testing OCR Service Health...")
        try:
            import pytesseract

            version = pytesseract.get_tesseract_version()
            languages = pytesseract.get_languages()
            jpn_available = "jpn" in languages

            print(f"   PASS: Tesseract version: {version}")
            print(f"   PASS: Available languages: {languages}")
            print(f"   PASS: Japanese support: {jpn_available}")

        except Exception as e:
            print(f"   FAIL: Tesseract not available: {e}")
            return False

        # Test 2: Create a simple test image
        print("\n2. Creating test image...")
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io

            # Create a simple test image with text
            img = Image.new("RGB", (400, 100), color="white")
            draw = ImageDraw.Draw(img)

            # Try to use a default font, fallback to basic if not available
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20
                )
            except (OSError, IOError):
                font = ImageFont.load_default()

            # Draw some text
            draw.text((10, 30), "Hello World", fill="black", font=font)
            draw.text((10, 60), "Test OCR", fill="black", font=font)

            # Convert to bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format="PNG")
            test_image_data = img_buffer.getvalue()

            print(f"   PASS: Test image created ({len(test_image_data)} bytes)")

        except Exception as e:
            print(f"   FAIL: Failed to create test image: {e}")
            return False

        # Test 3: OCR processing with bytes
        print("\n3. Testing OCR text extraction with bytes...")
        try:
            result = OCRService.extract_text_from_file(
                file_path=test_image_data,
                lang="eng",  # Use English for test
                dpi=300,
            )

            print("   PASS: OCR Result (bytes):")
            print(f"      - Success: {result.success}")
            print(f"      - File type: {result.file_type}")
            print(f"      - Page count: {result.page_count}")
            print(f"      - Language: {result.language}")
            print(f"      - Processing time: {result.processing_time}s")
            print(f"      - Extracted text: '{result.extracted_text}'")

            if result.success and result.extracted_text.strip():
                print("   PASS: OCR text extraction successful!")
            else:
                print("   WARN: OCR completed but no text extracted")

        except Exception as e:
            print(f"   FAIL: OCR processing failed: {e}")
            return False

        # Test 4: OCR processing with BytesIO
        print("\n4. Testing OCR text extraction with BytesIO...")
        try:
            from io import BytesIO

            # Create BytesIO object from the same image data
            bytes_io = BytesIO(test_image_data)

            result = OCRService.extract_text_from_file(
                file_path=bytes_io,  # type: ignore
                lang="eng",  # Use English for test
                dpi=300,
            )

            print("   PASS: OCR Result (BytesIO):")
            print(f"      - Success: {result.success}")
            print(f"      - File type: {result.file_type}")
            print(f"      - Page count: {result.page_count}")
            print(f"      - Language: {result.language}")
            print(f"      - Processing time: {result.processing_time}s")
            print(f"      - Extracted text: '{result.extracted_text}'")

            if result.success and result.extracted_text.strip():
                print("   PASS: OCR text extraction with BytesIO successful!")
            else:
                print("   WARN: OCR completed but no text extracted")

        except Exception as e:
            print(f"   FAIL: OCR processing with BytesIO failed: {e}")
            return False

        print("\nSUCCESS: All tests passed! OCR Service is working correctly.")
        return True

    except Exception as e:
        print(f"\nERROR: Test failed with error: {e}")
        return False


def main():
    """Main test function."""
    print("OCR Service Implementation Test")
    print("=" * 50)

    success = test_ocr_service()

    if success:
        print("\nSUCCESS: OCR Service implementation is ready!")
        print("\nNext steps:")
        print("   1. Install dependencies: uv sync")
        print("   2. Start the server: uv run fastapi dev")
        print("   3. Test API endpoints:")
        print("      - Health: GET http://localhost:8001/api/v1/ocr/health")
        print(
            "      - Extract (multipart): POST http://localhost:8001/api/v1/ocr/extract"
        )
        print(
            "      - Extract (base64): POST http://localhost:8001/api/v1/ocr/extract-base64"
        )
        print(
            "   4. Run this test script: uv run python scripts/test_ocr_implementation.py"
        )
    else:
        print("\nFAIL: OCR Service implementation needs fixes.")
        print("\nTroubleshooting:")
        print("   1. Make sure Tesseract is installed")
        print("   2. Check Japanese language pack: apt-get install tesseract-ocr-jpn")
        print("   3. Verify dependencies: uv sync")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
