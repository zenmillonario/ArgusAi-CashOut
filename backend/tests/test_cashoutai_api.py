"""
CashOutAI Backend API Tests
Tests for:
1. Stock price API (/api/stock/{symbol}) - using FMP stable endpoint
2. Messages API (/api/messages) - with increased limit and aggregation pipeline
3. Login endpoint (/api/users/login)
"""

import pytest
import requests
import os
import time

# Get BASE_URL from environment - this is the public URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://notification-system-18.preview.emergentagent.com"


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        print(f"API Root response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "message" in data
        print(f"API is running: {data}")


class TestStockPriceAPI:
    """Test stock price API using FMP stable endpoint"""
    
    def test_stock_price_aapl(self):
        """Test stock price for AAPL - should return real price data"""
        response = requests.get(f"{BASE_URL}/api/stock/AAPL")
        print(f"AAPL Stock API response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"AAPL stock data: {data}")
        
        # Verify response has required fields
        assert "price" in data, "Response missing 'price' field"
        assert "formatted_price" in data, "Response missing 'formatted_price' field"
        assert "change" in data, "Response missing 'change' field"
        
        # Verify price is a reasonable value for AAPL (should be > $100)
        price = data["price"]
        assert isinstance(price, (int, float)), "Price should be numeric"
        assert price > 50, f"AAPL price seems too low: {price}"
        assert price < 500, f"AAPL price seems too high: {price}"
        
        print(f"✅ AAPL price: ${price} (formatted: {data['formatted_price']})")
    
    def test_stock_price_tsla(self):
        """Test stock price for TSLA - should return valid price data"""
        response = requests.get(f"{BASE_URL}/api/stock/TSLA")
        print(f"TSLA Stock API response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"TSLA stock data: {data}")
        
        # Verify response structure
        assert "price" in data, "Response missing 'price' field"
        assert "symbol" in data, "Response missing 'symbol' field"
        
        price = data["price"]
        assert isinstance(price, (int, float)), "Price should be numeric"
        assert price > 0, f"Price should be positive: {price}"
        
        print(f"✅ TSLA price: ${price}")
    
    def test_stock_price_invalid_symbol(self):
        """Test stock price for invalid symbol"""
        response = requests.get(f"{BASE_URL}/api/stock/INVALIDXYZ123")
        print(f"Invalid symbol response: {response.status_code}")
        
        # Should return 404 or 500 for invalid symbol
        assert response.status_code in [404, 500], f"Expected error status, got {response.status_code}"
        print(f"✅ Invalid symbol correctly returns error")


class TestMessagesAPI:
    """Test messages API with increased limit and aggregation pipeline"""
    
    def test_get_messages_default_limit(self):
        """Test GET /api/messages with default limit (500)"""
        response = requests.get(f"{BASE_URL}/api/messages")
        print(f"Messages API response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ Retrieved {len(data)} messages with default limit")
    
    def test_get_messages_high_limit(self):
        """Test GET /api/messages?limit=500 - should work without memory errors"""
        response = requests.get(f"{BASE_URL}/api/messages?limit=500")
        print(f"Messages API (limit=500) response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ Retrieved {len(data)} messages with limit=500 (aggregation pipeline working)")
        
        # Check if we have messages spanning multiple days
        if len(data) > 0:
            first_msg = data[0]
            last_msg = data[-1]
            
            assert "timestamp" in first_msg, "Message should have timestamp"
            assert "content" in first_msg, "Message should have content"
            
            print(f"First message timestamp: {first_msg.get('timestamp')}")
            print(f"Last message timestamp: {last_msg.get('timestamp')}")
    
    def test_messages_structure(self):
        """Test messages have correct structure for date separators"""
        response = requests.get(f"{BASE_URL}/api/messages?limit=50")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            msg = data[0]
            
            # Verify message fields
            assert "id" in msg, "Message should have id"
            assert "timestamp" in msg, "Message should have timestamp"
            assert "content" in msg or "content_type" in msg, "Message should have content"
            
            print(f"✅ Message structure verified with required fields")


class TestLoginAPI:
    """Test login API"""
    
    def test_login_valid_credentials(self):
        """Test login with admin/admin123 credentials"""
        response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": "admin",
            "password": "admin123"
        })
        print(f"Login response: {response.status_code}")
        
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        
        data = response.json()
        print(f"Login data keys: {data.keys()}")
        
        # Verify user data returned
        assert "id" in data, "Response missing user id"
        assert "username" in data, "Response missing username"
        assert data["username"] == "admin", f"Expected username 'admin', got '{data['username']}'"
        
        print(f"✅ Login successful for user: {data['username']} (id: {data['id']})")
        
        return data
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": "invalid_user",
            "password": "wrong_password"
        })
        print(f"Invalid login response: {response.status_code}")
        
        assert response.status_code in [401, 404], f"Expected auth error, got {response.status_code}"
        print(f"✅ Invalid credentials correctly rejected")


class TestUserProfile:
    """Test user profile API"""
    
    @pytest.fixture
    def logged_in_user(self):
        """Get logged in user data"""
        response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json()
        pytest.skip("Login failed - skipping profile tests")
    
    def test_user_profile_get(self, logged_in_user):
        """Test GET user profile - for Twitter/X style layout"""
        user_id = logged_in_user["id"]
        
        response = requests.get(f"{BASE_URL}/api/users/{user_id}/profile")
        print(f"Profile response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Profile data keys: {data.keys()}")
        
        # Verify profile fields needed for Twitter/X style
        profile_fields = ["id", "username"]
        for field in profile_fields:
            assert field in data, f"Profile missing field: {field}"
        
        # Check optional profile fields
        optional_fields = ["bio", "profile_banner", "avatar_url", "follower_count", 
                          "following_count", "achievements", "location"]
        for field in optional_fields:
            if field in data:
                print(f"  - {field}: present")
        
        print(f"✅ Profile retrieved with Twitter/X style fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
