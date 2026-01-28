#!/usr/bin/env python3
"""Test XBRL ingestion with sample file."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from arelle import Cntlr

# Load the XBRL file
xbrl_path = "data_test/test_xbrl/entity00855093_2024-12-31.xbrl"

print(f"Loading XBRL file: {xbrl_path}")
print("=" * 80)

ctrl = Cntlr(logFileName="logToStdErr")
model_xbrl = ctrl.modelManager.load(xbrl_path)

if model_xbrl is None:
    print("ERROR: Failed to load XBRL file")
    sys.exit(1)

print(f"✓ XBRL loaded successfully")
print(f"Total facts: {len(model_xbrl.facts)}")
print()

# Extract text blocks
text_blocks = []
for fact in model_xbrl.facts:
    concept = fact.concept
    if concept is None or concept.type is None:
        continue
    
    if "textBlock" not in concept.type.name:
        continue
    
    concept_id = str(concept.qname)
    content = "" if fact.value is None else str(fact.value)
    title = concept.label() or concept_id
    context_ref = fact.contextID or ""
    
    text_blocks.append({
        "concept_id": concept_id,
        "title": str(title),
        "content": str(content),
        "context_ref": str(context_ref),
        "content_length": len(content)
    })

print(f"✓ Found {len(text_blocks)} text blocks")
print()

# Show first 10 text blocks
print("Text Blocks Found:")
print("=" * 80)
for i, block in enumerate(text_blocks[:10], 1):
    print(f"\n{i}. {block['title']}")
    print(f"   Concept ID: {block['concept_id']}")
    print(f"   Context: {block['context_ref']}")
    print(f"   Content Length: {block['content_length']:,} chars")
    if block['content_length'] > 0:
        preview = block['content'][:200].replace('\n', ' ')
        print(f"   Preview: {preview}...")

print()
print("=" * 80)
print(f"Summary: {len(text_blocks)} text blocks extracted")

# Cleanup
ctrl.modelManager.close(model_xbrl)
