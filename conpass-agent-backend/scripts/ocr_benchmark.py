#!/usr/bin/env python3
"""
Japanese OCR Benchmark System for accuracy testing and performance evaluation.

Usage:
    uv run python scripts/ocr_benchmark.py
"""

# mypy: ignore-errors
import sys
from typing import Dict, List, cast
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import difflib

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ocr_service import OCRService
from app.core.constants import OCRConstants
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class JapaneseOCRBenchmark:
    """Japanese OCR benchmark system for accuracy testing."""

    def __init__(self):
        self.test_cases = [
            {
                "text": "こんにちは世界",
                "script": "hiragana",
                "difficulty": "easy",
                "expected_accuracy": 95.0,
            },
            {
                "text": "カタカナテスト",
                "script": "katakana",
                "difficulty": "easy",
                "expected_accuracy": 90.0,
            },
            {
                "text": "日本語の文字認識テスト",
                "script": "kanji",
                "difficulty": "medium",
                "expected_accuracy": 85.0,
            },
            {
                "text": "ひらがな、カタカナ、漢字の混在テスト",
                "script": "mixed",
                "difficulty": "hard",
                "expected_accuracy": 80.0,
            },
        ]

    def generate_test_images(self, output_dir: str = "test_data") -> List[Dict]:
        """Generate test images with known Japanese text."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        generated_cases = []

        for i, case in enumerate(self.test_cases):
            try:
                # Create test image
                image_path = output_path / f"test_case_{i + 1}_{case['script']}.png"
                self._create_test_image(case["text"], str(image_path))  # type: ignore

                generated_cases.append(
                    {
                        "image_path": str(image_path),
                        "expected_text": case["text"],
                        "script": case["script"],
                        "difficulty": case["difficulty"],
                        "expected_accuracy": case["expected_accuracy"],
                    }
                )

            except Exception as e:
                logger.error(f"Failed to generate test image for case {i + 1}: {e}")

        return generated_cases

    def _create_test_image(self, text: str, output_path: str):
        """Create a test image with Japanese text."""
        try:
            # Try to use Japanese font
            font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
            if not Path(font_path).exists():
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

            font = ImageFont.truetype(font_path, 40)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Create image
        img = Image.new("RGB", (600, 100), color="white")
        draw = ImageDraw.Draw(img)

        # Draw text
        draw.text((20, 30), text, fill="black", font=font)

        # Save image
        img.save(output_path, "PNG")

    def _cleanup_test_images(self, test_cases: List[Dict]):
        """Clean up test images after benchmark completion."""
        try:
            for test_case in test_cases:
                image_path = test_case.get("image_path")
                if image_path and Path(image_path).exists():
                    Path(image_path).unlink()

            # Also clean up the test_data directory if it's empty
            test_data_dir = Path("test_data")
            if test_data_dir.exists() and not any(test_data_dir.iterdir()):
                test_data_dir.rmdir()

        except Exception as e:
            logger.warning(f"Failed to clean up test images: {e}")

    def run_benchmark(self, test_cases: List[Dict] = None) -> Dict:
        """Run comprehensive Japanese OCR benchmark with performance optimizations."""
        cleanup_needed = False
        if test_cases is None:
            test_cases = self.generate_test_images()
            cleanup_needed = True

        results = []
        total_accuracy = 0
        total_confidence = 0
        total_processing_time = 0

        try:
            for i, test_case in enumerate(test_cases):
                try:
                    # Extract text using OCR service with optimizations
                    result = OCRService.extract_text_from_file(
                        file_path=test_case["image_path"], lang="jpn"
                    )

                    # Calculate accuracy metrics
                    accuracy_metrics = self._calculate_japanese_accuracy(
                        result.extracted_text, test_case["expected_text"]
                    )

                    # Calculate quality grade
                    quality_grade = self._calculate_quality_grade(
                        accuracy_metrics["overall_accuracy"], result.confidence_score
                    )

                    test_result = {
                        "test_case": test_case,
                        "extracted_text": result.extracted_text,
                        "expected_text": test_case["expected_text"],
                        "accuracy_metrics": accuracy_metrics,
                        "confidence_score": result.confidence_score,
                        "raw_confidence": result.raw_confidence,
                        "quality_grade": quality_grade,
                        "processing_time": result.processing_time,
                        "character_count": result.character_count,
                    }

                    results.append(test_result)
                    total_accuracy += accuracy_metrics["overall_accuracy"]
                    total_confidence += result.confidence_score
                    total_processing_time += result.processing_time

                except Exception as e:
                    logger.error(f"Benchmark failed for test case {i + 1}: {e}")
                    results.append(
                        {
                            "test_case": test_case,
                            "error": str(e),
                            "accuracy_metrics": {"overall_accuracy": 0},
                            "confidence_score": 0,
                            "quality_grade": "F",
                            "processing_time": 0,
                        }
                    )

            # Calculate overall metrics
            avg_accuracy = total_accuracy / len(results) if results else 0
            avg_confidence = total_confidence / len(results) if results else 0
            avg_processing_time = total_processing_time / len(results) if results else 0

            return {
                "test_results": results,
                "overall_metrics": {
                    "average_accuracy": avg_accuracy,
                    "average_confidence": avg_confidence,
                    "average_processing_time": avg_processing_time,
                    "total_processing_time": total_processing_time,
                    "total_tests": len(results),
                    "passed_tests": len(
                        [
                            r
                            for r in results
                            if r.get("quality_grade", "F") in ["A", "B", "C"]
                        ]
                    ),
                },
            }

        finally:
            # Clean up test images if they were generated by this run
            if cleanup_needed:
                self._cleanup_test_images(test_cases)

    def _calculate_japanese_accuracy(self, extracted: str, expected: str) -> Dict:
        """Calculate Japanese-specific accuracy metrics."""
        try:
            # Character-level accuracy
            char_accuracy = self._calculate_character_accuracy(extracted, expected)

            # Japanese script-specific accuracy
            hiragana_accuracy = self._calculate_script_accuracy(
                extracted, expected, "hiragana"
            )
            katakana_accuracy = self._calculate_script_accuracy(
                extracted, expected, "katakana"
            )
            kanji_accuracy = self._calculate_script_accuracy(
                extracted, expected, "kanji"
            )

            # Character Error Rate (CER)
            cer = self._calculate_cer(extracted, expected)

            return {
                "overall_accuracy": char_accuracy,
                "hiragana_accuracy": hiragana_accuracy,
                "katakana_accuracy": katakana_accuracy,
                "kanji_accuracy": kanji_accuracy,
                "character_error_rate": cer,
            }
        except Exception as e:
            logger.error(f"Accuracy calculation failed: {e}")
            return {
                "overall_accuracy": 0,
                "hiragana_accuracy": 0,
                "katakana_accuracy": 0,
                "kanji_accuracy": 0,
                "character_error_rate": 100,
            }

    def _calculate_character_accuracy(self, extracted: str, expected: str) -> float:
        """Calculate character-level accuracy using edit distance."""
        if not expected:
            return 100.0 if not extracted else 0.0

        # Use difflib for character-level comparison
        matcher = difflib.SequenceMatcher(None, expected, extracted)
        similarity = matcher.ratio()
        return similarity * 100

    def _calculate_script_accuracy(
        self, extracted: str, expected: str, script_type: str
    ) -> float:
        """Calculate accuracy for specific Japanese script types."""
        script_ranges = {
            "hiragana": ("\u3040", "\u309f"),
            "katakana": ("\u30a0", "\u30ff"),
            "kanji": ("\u4e00", "\u9faf"),
        }

        start, end = script_ranges[script_type]
        extracted_script = [c for c in extracted if start <= c <= end]
        expected_script = [c for c in expected if start <= c <= end]

        if not expected_script:
            return 100.0

        # Calculate accuracy using edit distance
        matcher = difflib.SequenceMatcher(None, expected_script, extracted_script)
        similarity = matcher.ratio()
        return similarity * 100

    def _calculate_cer(self, extracted: str, expected: str) -> float:
        """Calculate Character Error Rate."""
        if not expected:
            return 100.0 if extracted else 0.0

        # Calculate edit distance
        matcher = difflib.SequenceMatcher(None, expected, extracted)
        distance = (
            len(expected) - matcher.matching_blocks[0].size  # type: ignore
            if matcher.matching_blocks  # type: ignore
            else len(expected)
        )
        cer = (distance / len(expected)) * 100 if expected else 0
        return min(100, max(0, cer))

    def _calculate_quality_grade(self, accuracy: float, confidence: float) -> str:
        """Calculate quality grade based on accuracy and confidence."""
        for grade, thresholds in OCRConstants.QUALITY_GRADES.items():
            if (
                accuracy >= thresholds["min_accuracy"]
                and confidence >= thresholds["min_confidence"]
            ):
                return grade
        return "F"

    def run_performance_test(self) -> Dict:
        """Run performance test to measure optimization benefits."""
        # Ensure test_data directory exists
        test_data_dir = Path("test_data")
        test_data_dir.mkdir(exist_ok=True)

        # Generate multiple test images to simulate multi-page processing
        test_cases = []
        for i in range(8):  # Create 8 test cases to test parallel processing
            for case in self.test_cases:
                test_cases.append(
                    {
                        "image_path": f"test_data/performance_test_{i}_{case['script']}.png",
                        "expected_text": case["text"],
                        "script": case["script"],
                        "difficulty": case["difficulty"],
                        "expected_accuracy": case["expected_accuracy"],
                    }
                )

        # Generate all test images
        for i, case in enumerate(test_cases):
            self._create_test_image(
                cast(str, case["expected_text"]), cast(str, case["image_path"])
            )

        try:
            # Run benchmark with multiple test cases
            results = self.run_benchmark(test_cases)

            # Calculate performance metrics
            total_time = results["overall_metrics"]["total_processing_time"]
            total_tests = results["overall_metrics"]["total_tests"]

            print(
                f"Performance Test: {total_tests} tests in {total_time:.3f}s ({total_tests / total_time:.1f} tests/sec)"
            )

            return results

        finally:
            # Clean up performance test images
            for case in test_cases:
                path = cast(str, case["image_path"])
                if Path(path).exists():
                    Path(path).unlink()


def run_benchmark_test():
    """Run a comprehensive benchmark test with performance optimizations."""
    benchmark = JapaneseOCRBenchmark()

    print("Japanese OCR Benchmark (Optimized)")
    print("=" * 50)

    # Run standard benchmark
    results = benchmark.run_benchmark()

    for i, result in enumerate(results["test_results"]):
        if "error" in result:
            print(f"Test {i + 1}: ERROR - {result['error']}")
        else:
            print(
                f"Test {i + 1}: {result['test_case']['script']} - {result['accuracy_metrics']['overall_accuracy']:.1f}% accuracy, {result['processing_time']:.3f}s"
            )

    print(
        f"\nResults: {results['overall_metrics']['average_accuracy']:.1f}% accuracy, {results['overall_metrics']['average_processing_time']:.3f}s avg time"
    )

    # Run performance test
    benchmark.run_performance_test()

    # Overall analysis
    avg_time = results["overall_metrics"]["average_processing_time"]
    if avg_time < 0.2:
        print("Status: EXCELLENT - Highly optimized")
    elif avg_time < 0.3:
        print("Status: GOOD - Well optimized")
    else:
        print(f"Status: MODERATE - {avg_time:.3f}s per test")


if __name__ == "__main__":
    run_benchmark_test()
