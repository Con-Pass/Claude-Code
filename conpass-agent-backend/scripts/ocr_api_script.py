#!/usr/bin/env python3
"""
Test script to verify OCR API endpoints.
Tests both health check and text extraction endpoints.

Usage:
    uv run python scripts/ocr_api_script.py
"""

import requests
from PIL import Image, ImageDraw, ImageFont
import io


def create_test_image():
    """Create a test image for OCR testing."""
    # Create a simple test image with text
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)

    # Try to use a default font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Draw some text
    draw.text((10, 30), "Hello World", fill="black", font=font)
    draw.text((10, 60), "Test OCR", fill="black", font=font)

    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    return img_buffer.getvalue()


def test_health_endpoint(base_url="http://localhost:8000"):
    """Test the OCR health endpoint."""
    print(" Testing OCR Health Endpoint...")

    try:
        response = requests.get(f"{base_url}/api/v1/ocr/health")

        if response.status_code == 200:
            data = response.json()
            print("   PASS: Health check successful!")
            print(f"    Status: {data.get('status')}")
            print(f"    Tesseract available: {data.get('tesseract_available')}")
            print(f"    Japanese support: {data.get('jpn_language_available')}")
            print(f"     OCR configured: {data.get('ocr_configured')}")
            print(f"    Version: {data.get('version')}")
            return True
        else:
            print(f"   FAIL: Health check failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return False

    except Exception as e:
        print(f"   FAIL: Health check error: {e}")
        return False


def test_extract_endpoint(base_url="http://localhost:8000", token=None):
    """Test the OCR extract endpoint."""
    print("\n Testing OCR Extract Endpoint...")

    try:
        # Create test image
        test_image = create_test_image()

        # Prepare headers
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Prepare files
        files = {"file": ("test.png", test_image, "image/png")}

        # Prepare data
        data = {"lang": "eng", "dpi": 300}

        response = requests.post(
            f"{base_url}/api/v1/ocr/extract", headers=headers, files=files, data=data
        )

        if response.status_code == 200:
            result = response.json()
            print("   PASS: Text extraction successful!")
            print(f"    Extracted text: '{result.get('extracted_text')}'")
            print(f"    Success: {result.get('success')}")
            print(f"    File type: {result.get('file_type')}")
            print(f"    Page count: {result.get('page_count')}")
            print(f"     Processing time: {result.get('processing_time')}s")
            print(f"    Confidence Score: {result.get('confidence_score', 0):.1f}%")
            print(f"    Raw Confidence: {result.get('raw_confidence', 0):.1f}%")
            print(f"    Character Count: {result.get('character_count', 0)}")
            return True
        else:
            print(f"   FAIL: Text extraction failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return False

    except Exception as e:
        print(f"   FAIL: Text extraction error: {e}")
        return False


def main():
    """Main test function."""
    print(" OCR API Endpoint Test")
    print("=" * 50)

    base_url = "http://localhost:8001"  # OCR agent backend runs on port 8001

    # Test health endpoint (no auth required)
    health_success = test_health_endpoint(base_url)

    # Test extract endpoint (no auth required for OCR endpoints)
    print("\n" + "=" * 50)
    print(" Testing OCR Extract Endpoint (no authentication required)")
    print("=" * 50)

    extract_success = test_extract_endpoint(base_url, None)

    # Summary
    print("\n" + "=" * 50)
    if health_success and extract_success:
        print("PASS: All tests passed!")
    else:
        print("FAIL: Some tests failed!")
        if not health_success:
            print("   - Health endpoint failed")
        if not extract_success:
            print("   - Extract endpoint failed")

    return 0 if (health_success and extract_success) else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
