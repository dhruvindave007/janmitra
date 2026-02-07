#!/usr/bin/env python
"""
Test script for AppVersion API and model.

Run with: python test_app_version.py
"""
import os
import sys
import django

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'janmitra_backend.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from core.models import AppVersion

def test_app_version():
    """Test AppVersion model and API."""
    print("=" * 60)
    print("Testing AppVersion System")
    print("=" * 60)
    
    # Clear any existing versions
    AppVersion.objects.all().delete()
    print("✓ Cleared existing versions")
    
    # Test 1: Create a version
    version = AppVersion.objects.create(
        latest_version="1.0.0",
        minimum_supported_version="1.0.0",
        is_active=True
    )
    print(f"\n✓ Test 1: Created test version: {version}")
    
    # Test 2: Retrieve active version
    active = AppVersion.get_active_version()
    print(f"✓ Test 2: Retrieved active version: {active}")
    assert active is not None, "Failed to retrieve active version"
    assert active.latest_version == "1.0.0", "Version mismatch"
    
    # Test 3: Create multiple versions and switch active
    version2 = AppVersion.objects.create(
        latest_version="1.1.0",
        minimum_supported_version="1.0.0",
        is_active=False
    )
    print(f"✓ Test 3: Created second version: {version2}")
    
    # Activate version 2
    AppVersion.objects.filter(is_active=True).update(is_active=False)
    version2.is_active = True
    version2.save(update_fields=['is_active', 'updated_at'])
    
    active2 = AppVersion.get_active_version()
    print(f"✓ Test 4: Switched active version to: {active2}")
    assert active2.latest_version == "1.1.0", "Failed to switch active version"
    
    # Test 5: Test API endpoint response format
    from core.serializers import AppVersionSerializer
    serializer = AppVersionSerializer(active2, context={})
    data = serializer.data
    print(f"\n✓ Test 5: Serializer output:")
    print(f"  - latest_version: {data['latest_version']}")
    print(f"  - minimum_supported_version: {data['minimum_supported_version']}")
    print(f"  - apk_url: {data['apk_url']}")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    print("\nAPI Endpoint: GET /api/v1/app/version/")
    print("Expected response (no APK file):")
    print(data)

if __name__ == '__main__':
    test_app_version()
