"""
Simple usage examples for the Qdrant Filter Tool.

This demonstrates basic usage patterns for querying contracts
using natural language.
"""

# mypy: ignore-errors
import asyncio

from app.core.model_settings import init_model_settings
from app.services.chatbot.tools.metadata_search.metadata_search_tool import (
    metadata_search,
)

# Example directory IDs you are authorized to query.
# Replace with real directory IDs for your environment.
DIRECTORY_IDS = [1]


async def example_simple_queries():
    """Examples of simple metadata queries."""

    print("\n=== Simple Metadata Queries ===\n")

    # Initialize model
    init_model_settings()

    # Example 1: Find contracts by company
    print("1. Find contracts with a specific company:")
    # result = await metadata_search(query="Get me contracts that doesnt auto renew")
    result = await metadata_search(
        directory_ids=DIRECTORY_IDS, query="Get me contracts from 2024"
    )
    print(result)
    print("\n" + "-" * 80 + "\n")

    # Example 2: Find contracts by date range
    print("2. Find contracts ending in 2024:")
    result = await metadata_search(
        directory_ids=DIRECTORY_IDS, query="Find contracts ending in 2024", page=1
    )
    print(result)
    print("\n" + "-" * 80 + "\n")

    # Example 3: Find contracts with auto-renewal
    print("3. Find auto-renewal contracts:")
    result = await metadata_search(
        directory_ids=DIRECTORY_IDS, query="Show contracts with auto-renewal enabled"
    )
    print(result)
    print("\n" + "-" * 80 + "\n")


async def example_complex_queries():
    """Examples of complex queries with multiple conditions."""

    print("\n=== Complex Queries ===\n")

    init_model_settings()

    # Example 1: Multiple conditions (AND)
    print("1. Find contracts with company AND date condition:")
    result = await metadata_search(
        directory_ids=DIRECTORY_IDS,
        query="Show contracts with 株式会社ABC that end after 2024-06-01",
    )
    print(result)
    print("\n" + "-" * 80 + "\n")

    # Example 2: OR conditions
    print("2. Find contracts with multiple companies (OR):")
    result = await metadata_search(
        directory_ids=DIRECTORY_IDS,
        query="Find contracts with 株式会社ABC or 株式会社XYZ",
    )
    print(result)
    print("\n" + "-" * 80 + "\n")

    # Example 3: NOT conditions
    print("3. Find contracts excluding a company:")
    result = await metadata_search(
        directory_ids=DIRECTORY_IDS,
        query="Show contracts ending in 2024 but not with 株式会社ABC",
    )
    print(result)
    print("\n" + "-" * 80 + "\n")


async def main():
    """Run all examples."""

    try:
        # Run simple queries
        await example_simple_queries()

        # Run complex queries
        await example_complex_queries()

    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure:")
        print("1. QDRANT_URL is set in .env")
        print("2. QDRANT_COLLECTION is set in .env")
        print("3. QDRANT_API_KEY is set (if required)")
        print("4. OpenAI API key is configured")


if __name__ == "__main__":
    asyncio.run(main())
