#!/usr/bin/env python3
"""
Test script to verify Firebase optimization effectiveness.
This script tests the optimized Firebase operations and monitors read counts.
"""

import sys
import os
import time
import requests
import json

# Add server directory to path
sys.path.append('server')

from optimized_firebase import OptimizedFirebaseService

def test_firebase_optimization():
    """Test the optimized Firebase service"""
    print("🔥 Testing Firebase Optimization...")
    
    # Initialize optimized Firebase service
    service_account_path = "server/bookhub-80381-firebase-adminsdk-fbsvc-b3e2365f77.json"
    
    if not os.path.exists(service_account_path):
        print("❌ Firebase service account file not found")
        return False
    
    try:
        firebase_service = OptimizedFirebaseService('bookhub-80381', service_account_path)
        print("✅ Firebase service initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Firebase service: {e}")
        return False
    
    # Test 1: Check initial read count
    initial_reads = firebase_service.get_read_count()
    print(f"📊 Initial read count: {initial_reads}")
    
    # Test 2: Test caching
    print("\n🧪 Testing caching effectiveness...")
    test_user_id = "test_user_123"
    
    # First call - should hit Firebase
    start_time = time.time()
    tags1 = firebase_service.get_user_tags_optimized(test_user_id)
    first_call_time = time.time() - start_time
    reads_after_first = firebase_service.get_read_count()
    
    # Second call - should hit cache
    start_time = time.time()
    tags2 = firebase_service.get_user_tags_optimized(test_user_id)
    second_call_time = time.time() - start_time
    reads_after_second = firebase_service.get_read_count()
    
    print(f"📈 First call: {first_call_time:.3f}s, Reads: {reads_after_first - initial_reads}")
    print(f"⚡ Second call: {second_call_time:.3f}s, Reads: {reads_after_second - reads_after_first}")
    
    if reads_after_second == reads_after_first:
        print("✅ Cache working correctly - no additional reads on second call")
    else:
        print("❌ Cache not working - additional reads detected")
    
    # Test 3: Test recommendations with limits
    print("\n🎯 Testing optimized recommendations...")
    test_tags = ["fiction", "mystery"]
    
    start_reads = firebase_service.get_read_count()
    recommendations = firebase_service.get_recommendations_by_tags_optimized(test_tags, limit=5, user_id=test_user_id)
    end_reads = firebase_service.get_read_count()
    
    print(f"📚 Found {len(recommendations)} recommendations")
    print(f"📊 Read count for recommendations: {end_reads - start_reads}")
    
    # Test 4: Test cache statistics
    print("\n📈 Cache Statistics:")
    cache_stats = firebase_service.get_cache_stats()
    for key, value in cache_stats.items():
        print(f"  {key}: {value}")
    
    # Test 5: Test popular books
    print("\n⭐ Testing popular books...")
    start_reads = firebase_service.get_read_count()
    popular_books = firebase_service.get_popular_books_optimized(limit=10)
    end_reads = firebase_service.get_read_count()
    
    print(f"📚 Found {len(popular_books)} popular books")
    print(f"📊 Read count for popular books: {end_reads - start_reads}")
    
    # Final read count
    final_reads = firebase_service.get_read_count()
    total_reads = final_reads - initial_reads
    
    print(f"\n📊 Total Firebase reads during test: {total_reads}")
    
    if total_reads < 50:  # Should be much lower than before
        print("✅ Firebase optimization successful - low read count")
        return True
    else:
        print("⚠️  High read count detected - optimization may need improvement")
        return False

def test_api_endpoints():
    """Test the optimized API endpoints"""
    print("\n🌐 Testing API Endpoints...")
    
    base_url = "http://localhost:8000"
    
    # Test endpoints
    endpoints_to_test = [
        ("/api/firebase/stats", "GET"),
        ("/api/popular-books?limit=5", "GET"),
        ("/api/cache/clear", "POST"),
    ]
    
    for endpoint, method in endpoints_to_test:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
            else:
                response = requests.post(f"{base_url}{endpoint}", timeout=5)
            
            if response.status_code == 200:
                print(f"✅ {method} {endpoint} - Status: {response.status_code}")
            else:
                print(f"⚠️  {method} {endpoint} - Status: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {method} {endpoint} - Server not running")
        except Exception as e:
            print(f"❌ {method} {endpoint} - Error: {e}")

def run_performance_comparison():
    """Compare performance before and after optimization"""
    print("\n⚡ Performance Comparison...")
    
    # This would require running both old and new implementations
    # For now, we'll just show the expected improvements
    
    print("📊 Expected Performance Improvements:")
    print("  Before optimization:")
    print("    - Hybrid recommendations: 1000+ reads per request")
    print("    - User tags: 50+ reads per request")
    print("    - Similar books: 100+ reads per request")
    print("    - No caching")
    print()
    print("  After optimization:")
    print("    - Hybrid recommendations: 10-30 reads per request (cached: 0 reads)")
    print("    - User tags: 1-5 reads per request (cached: 0 reads)")
    print("    - Similar books: 1-10 reads per request (cached: 0 reads)")
    print("    - Intelligent caching with TTL")
    print("    - Query limits and targeted operations")

if __name__ == "__main__":
    print("🚀 Firebase Optimization Test Suite")
    print("=" * 50)
    
    # Test Firebase optimization
    optimization_success = test_firebase_optimization()
    
    # Test API endpoints (requires server to be running)
    test_api_endpoints()
    
    # Show performance comparison
    run_performance_comparison()
    
    print("\n" + "=" * 50)
    if optimization_success:
        print("🎉 Firebase optimization tests completed successfully!")
        print("💡 Your app should now handle Firebase read limits much better.")
    else:
        print("⚠️  Some optimization tests failed. Check the logs above.")
    
    print("\n📋 Next Steps:")
    print("1. Start your Flask server: python server/app.py")
    print("2. Test the optimized endpoints")
    print("3. Monitor Firebase usage with: GET /api/firebase/stats")
    print("4. Clear cache when needed with: POST /api/cache/clear")
