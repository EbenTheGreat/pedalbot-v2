"""
Quick test for identity resolution fix.

This tests that "GT-1 eng03 W" → "Boss GT-1" when manufacturer is available.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.services.pedal_registry import PedalRegistry

# Test canonical name extraction
registry = PedalRegistry()

# Test 1: With manufacturer
test_cases = [
    ("GT-1 eng03 W", "Boss", "Boss GT-1"),
    ("Helix 3.80 Owner's Manual", "Line 6", "Line 6 Helix 3.80"),
    ("DS-1 Distortion Manual v2.0", "Boss", "Boss DS-1 Distortion"),
    ("Zoom G3Xn User Guide", "Zoom", "Zoom G3Xn User Guide"),
]

print("Testing canonical name extraction:\n")
for pedal_name, manufacturer, expected in test_cases:
    result = registry._extract_canonical_name(pedal_name, manufacturer)
    status = "✅" if expected.lower() in result.lower() else "❌"
    print(f"{status} '{pedal_name}' + '{manufacturer}' → '{result}'")
    if expected.lower() not in result.lower():
        print(f"   Expected to contain: '{expected}'")

print("\n" + "="*60 + "\n")

# Test 2: Without manufacturer
print("Testing without manufacturer:\n")
no_mfr_cases = [
    ("GT-1 eng03 W", None, "GT-1"),
    ("Pod Go Manual v1.2", None, "Pod Go"),
]

for pedal_name, manufacturer, expected_contains in no_mfr_cases:
    result = registry._extract_canonical_name(pedal_name, manufacturer)
    status = "✅" if expected_contains in result else "❌"
    print(f"{status} '{pedal_name}' → '{result}'")
    if expected_contains not in result:
        print(f"   Expected to contain: '{expected_contains}'")

print("\n✨ Canonical name extraction test complete!")
