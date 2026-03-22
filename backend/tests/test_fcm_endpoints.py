"""
FCM (Firebase Cloud Messaging) Endpoint Tests
Tests for push notification backend endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFCMEndpoints:
    """FCM endpoint tests for push notification functionality"""
    
    def test_health_endpoint(self):
        """Test health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert data.get("db") == "connected"
        print(f"✅ Health endpoint: {data}")
    
    def test_fcm_status_endpoint(self):
        """Test FCM status endpoint returns initialization status"""
        response = requests.get(f"{BASE_URL}/api/fcm/status")
        assert response.status_code == 200
        data = response.json()
        
        # FCM should be initialized (firebase-admin SDK loaded)
        assert "initialized" in data
        assert isinstance(data["initialized"], bool)
        
        # Should have credentials_configured field
        assert "credentials_configured" in data
        
        # Should have registered_tokens count
        assert "registered_tokens" in data
        assert isinstance(data["registered_tokens"], int)
        
        print(f"✅ FCM Status: initialized={data['initialized']}, tokens={data['registered_tokens']}")
    
    def test_fcm_register_token_success(self):
        """Test FCM token registration with valid data"""
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        test_token = f"test_fcm_token_{uuid.uuid4().hex}"
        
        response = requests.post(
            f"{BASE_URL}/api/fcm/register-token",
            json={"user_id": test_user_id, "token": test_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "Token registered successfully"
        print(f"✅ Token registration successful for user: {test_user_id}")
    
    def test_fcm_register_token_missing_user_id(self):
        """Test FCM token registration fails without user_id"""
        response = requests.post(
            f"{BASE_URL}/api/fcm/register-token",
            json={"token": "some_token"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "user_id" in data.get("detail", "").lower() or "required" in data.get("detail", "").lower()
        print(f"✅ Missing user_id correctly rejected: {data}")
    
    def test_fcm_register_token_missing_token(self):
        """Test FCM token registration fails without token"""
        response = requests.post(
            f"{BASE_URL}/api/fcm/register-token",
            json={"user_id": "some_user"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "token" in data.get("detail", "").lower() or "required" in data.get("detail", "").lower()
        print(f"✅ Missing token correctly rejected: {data}")
    
    def test_fcm_register_token_update_existing(self):
        """Test FCM token update for existing user"""
        test_user_id = f"test_update_user_{uuid.uuid4().hex[:8]}"
        
        # Register first token
        first_token = f"first_token_{uuid.uuid4().hex}"
        response1 = requests.post(
            f"{BASE_URL}/api/fcm/register-token",
            json={"user_id": test_user_id, "token": first_token}
        )
        assert response1.status_code == 200
        
        # Update with second token
        second_token = f"second_token_{uuid.uuid4().hex}"
        response2 = requests.post(
            f"{BASE_URL}/api/fcm/register-token",
            json={"user_id": test_user_id, "token": second_token}
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data.get("message") == "Token registered successfully"
        print(f"✅ Token update successful for user: {test_user_id}")
    
    def test_fcm_test_notification_with_invalid_token(self):
        """Test notification endpoint with invalid token returns appropriate response"""
        # Using a fake token - should return success:false since token is invalid
        response = requests.post(
            f"{BASE_URL}/api/fcm/test-notification",
            json={"token": "invalid_test_token_12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return success:false for invalid token (expected behavior)
        assert "success" in data
        # Invalid tokens will fail to send
        print(f"✅ Test notification response: {data}")
    
    def test_fcm_test_notification_missing_token(self):
        """Test notification endpoint fails without token"""
        response = requests.post(
            f"{BASE_URL}/api/fcm/test-notification",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "token" in data.get("detail", "").lower() or "required" in data.get("detail", "").lower()
        print(f"✅ Missing token correctly rejected: {data}")


class TestServiceWorkerEndpoint:
    """Test that firebase-messaging-sw.js is served correctly"""
    
    def test_service_worker_accessible(self):
        """Test firebase-messaging-sw.js is served at root"""
        response = requests.get(f"{BASE_URL}/firebase-messaging-sw.js")
        
        assert response.status_code == 200
        content = response.text
        
        # Verify it contains Firebase initialization
        assert "firebase" in content.lower()
        assert "messaging" in content.lower()
        assert "onBackgroundMessage" in content
        
        # Verify it does NOT contain AudioContext (was removed as fix)
        assert "AudioContext" not in content
        
        # Verify it does NOT have conflicting push event listener
        # The old problematic code had: self.addEventListener('push', ...)
        # Now it should only use messaging.onBackgroundMessage
        lines = content.split('\n')
        push_listener_count = sum(1 for line in lines if "addEventListener('push'" in line or 'addEventListener("push"' in line)
        assert push_listener_count == 0, "Should not have manual push event listener"
        
        print(f"✅ Service Worker accessible and properly configured")
        print(f"   - Contains Firebase messaging: ✓")
        print(f"   - No AudioContext (SW incompatible): ✓")
        print(f"   - No conflicting push listener: ✓")


class TestLoginAndAuth:
    """Test login functionality"""
    
    def test_login_with_admin_credentials(self):
        """Test login with admin/admin123 credentials"""
        response = requests.post(
            f"{BASE_URL}/api/users/login",
            json={"username": "admin", "password": "admin123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return user data
        assert "id" in data or "user" in data
        print(f"✅ Login successful with admin credentials")
    
    def test_login_with_invalid_credentials(self):
        """Test login fails with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/users/login",
            json={"username": "invalid_user", "password": "wrong_password"}
        )
        
        # Should return 401 or 404 for invalid credentials
        assert response.status_code in [401, 404]
        print(f"✅ Invalid credentials correctly rejected: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
