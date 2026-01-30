#!/usr/bin/env python3
"""
Lead Scoring Engine - Main Entry Point

This is a convenience wrapper that imports and runs the pipeline.
For more control, use scripts/run_pipeline.py directly.

Usage:
    python main.py

Environment Variables:
    GOOGLE_PLACES_API_KEY: Required. Your Google Places API key.
"""

from scripts.run_pipeline import main

if __name__ == "__main__":
    main()
