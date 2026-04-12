"""
Backend API Tests for CashOutAI Trading App
Tests for:
1. Forgot Password (direct reset) flow
2. Login flow
3. Messages with text_content for image messages
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_EMAIL = "admin@cashoutai.com"


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """Test that the API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"✅ Health check passed: {data}")


class TestLoginFlow:
    """Login endpoint tests"""
    
    def test_login_with_valid_credentials(self):
        """Test login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["username"] == ADMIN_USERNAME
        assert data["email"] == ADMIN_EMAIL
        print(f"✅ Login successful for user: {data['username']}")
        return data
    
    def test_login_with_invalid_password(self):
        """Test login with wrong password"""
        response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": ADMIN_USERNAME,
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Invalid password correctly rejected")
    
    def test_login_with_nonexistent_user(self):
        """Test login with non-existent username - returns 401 (security best practice)"""
        response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": "nonexistentuser12345",
            "password": "anypassword"
        })
        # API returns 401 for non-existent users (security best practice - don't reveal if user exists)
        assert response.status_code in [401, 404], f"Expected 401 or 404, got {response.status_code}"
        print("✅ Non-existent user correctly rejected")


class TestDirectPasswordReset:
    """Direct password reset endpoint tests"""
    
    def test_reset_password_with_correct_credentials(self):
        """Test password reset with correct username and email"""
        # First, reset to a new password
        new_password = "newpassword123"
        response = requests.post(f"{BASE_URL}/api/users/reset-password-direct", json={
            "username": ADMIN_USERNAME,
            "email": ADMIN_EMAIL,
            "new_password": new_password
        })
        assert response.status_code == 200, f"Password reset failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert "successfully" in data["message"].lower()
        print(f"✅ Password reset successful: {data['message']}")
        
        # Verify login with new password works
        login_response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": ADMIN_USERNAME,
            "password": new_password
        })
        assert login_response.status_code == 200, f"Login with new password failed: {login_response.text}"
        print("✅ Login with new password successful")
        
        # Reset back to original password
        reset_back = requests.post(f"{BASE_URL}/api/users/reset-password-direct", json={
            "username": ADMIN_USERNAME,
            "email": ADMIN_EMAIL,
            "new_password": ADMIN_PASSWORD
        })
        assert reset_back.status_code == 200, f"Failed to reset back to original password: {reset_back.text}"
        print("✅ Password reset back to original")
    
    def test_reset_password_with_wrong_email(self):
        """Test password reset with wrong email"""
        response = requests.post(f"{BASE_URL}/api/users/reset-password-direct", json={
            "username": ADMIN_USERNAME,
            "email": "wrong@email.com",
            "new_password": "newpassword123"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "email" in data.get("detail", "").lower() or "match" in data.get("detail", "").lower()
        print(f"✅ Wrong email correctly rejected: {data.get('detail')}")
    
    def test_reset_password_with_nonexistent_username(self):
        """Test password reset with non-existent username"""
        response = requests.post(f"{BASE_URL}/api/users/reset-password-direct", json={
            "username": "nonexistentuser12345",
            "email": "any@email.com",
            "new_password": "newpassword123"
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent username correctly rejected")
    
    def test_reset_password_too_short(self):
        """Test password reset with password less than 6 characters"""
        response = requests.post(f"{BASE_URL}/api/users/reset-password-direct", json={
            "username": ADMIN_USERNAME,
            "email": ADMIN_EMAIL,
            "new_password": "12345"  # Only 5 characters
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "6 characters" in data.get("detail", "")
        print(f"✅ Short password correctly rejected: {data.get('detail')}")


class TestMessagesWithTextContent:
    """Tests for messages endpoint with text_content field for image messages"""
    
    @pytest.fixture
    def admin_user(self):
        """Get admin user data by logging in"""
        response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()
    
    def test_send_text_message(self, admin_user):
        """Test sending a regular text message"""
        test_content = f"Test message {uuid.uuid4()}"
        response = requests.post(f"{BASE_URL}/api/messages", json={
            "content": test_content,
            "content_type": "text",
            "user_id": admin_user["id"]
        })
        assert response.status_code == 200, f"Failed to send message: {response.text}"
        data = response.json()
        assert data["content"] == test_content
        assert data["content_type"] == "text"
        assert data["user_id"] == admin_user["id"]
        print(f"✅ Text message sent successfully: {data['id']}")
    
    def test_send_image_message_with_text_content(self, admin_user):
        """Test sending an image message with text_content caption"""
        # Using a small base64 placeholder for testing
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        test_caption = f"Test caption {uuid.uuid4()}"
        
        response = requests.post(f"{BASE_URL}/api/messages", json={
            "content": test_image,
            "content_type": "image",
            "user_id": admin_user["id"],
            "text_content": test_caption
        })
        assert response.status_code == 200, f"Failed to send image message: {response.text}"
        data = response.json()
        assert data["content_type"] == "image"
        assert data["text_content"] == test_caption, f"text_content not saved: expected '{test_caption}', got '{data.get('text_content')}'"
        print(f"✅ Image message with text_content sent successfully: {data['id']}")
        print(f"   Caption: {data['text_content']}")
    
    def test_send_image_message_without_text_content(self, admin_user):
        """Test sending an image message without text_content"""
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        response = requests.post(f"{BASE_URL}/api/messages", json={
            "content": test_image,
            "content_type": "image",
            "user_id": admin_user["id"]
        })
        assert response.status_code == 200, f"Failed to send image message: {response.text}"
        data = response.json()
        assert data["content_type"] == "image"
        # text_content should be None or not present
        assert data.get("text_content") is None, f"text_content should be None, got: {data.get('text_content')}"
        print(f"✅ Image message without text_content sent successfully: {data['id']}")
    
    def test_send_reply_message(self, admin_user):
        """Test sending a reply to another message"""
        # First send a message to reply to
        original_content = f"Original message {uuid.uuid4()}"
        original_response = requests.post(f"{BASE_URL}/api/messages", json={
            "content": original_content,
            "content_type": "text",
            "user_id": admin_user["id"]
        })
        assert original_response.status_code == 200
        original_message = original_response.json()
        
        # Now send a reply
        reply_content = f"Reply message {uuid.uuid4()}"
        reply_response = requests.post(f"{BASE_URL}/api/messages", json={
            "content": reply_content,
            "content_type": "text",
            "user_id": admin_user["id"],
            "reply_to_id": original_message["id"]
        })
        assert reply_response.status_code == 200, f"Failed to send reply: {reply_response.text}"
        reply_data = reply_response.json()
        assert reply_data["reply_to_id"] == original_message["id"]
        assert reply_data["reply_to"] is not None
        assert reply_data["reply_to"]["id"] == original_message["id"]
        print(f"✅ Reply message sent successfully: {reply_data['id']}")
        print(f"   Replying to: {reply_data['reply_to']['id']}")


class TestGetMessages:
    """Tests for retrieving messages"""
    
    def test_get_messages(self):
        """Test getting messages list"""
        response = requests.get(f"{BASE_URL}/api/messages")
        assert response.status_code == 200, f"Failed to get messages: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Retrieved {len(data)} messages")
        
        # Check that messages have expected fields
        if len(data) > 0:
            msg = data[0]
            assert "id" in msg
            assert "content" in msg
            assert "user_id" in msg
            assert "content_type" in msg
            print(f"   Sample message: {msg.get('content', '')[:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
