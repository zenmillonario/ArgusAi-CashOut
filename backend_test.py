import requests
import unittest
import json
import time
import random
import string
from datetime import datetime

# Get the backend URL from the frontend .env file
BACKEND_URL = "https://1494341d-df84-483f-b635-19d168bdc5cc.preview.emergentagent.com"
API_URL = f"{BACKEND_URL}/api"

def random_string(length=8):
    """Generate a random string for testing"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class CashoutAIAPITest(unittest.TestCase):
    """Test suite for CashoutAI API endpoints"""
    
    def setUp(self):
        """Set up test data and login as admin"""
        self.admin_credentials = {
            "username": "admin",
            "password": "admin"  # Default admin password for demo
        }
        
        # Login as admin
        response = requests.post(f"{API_URL}/users/login", json=self.admin_credentials)
        self.assertEqual(response.status_code, 200, "Admin login failed")
        self.admin_user = response.json()
        
        # Generate test user data
        timestamp = int(time.time())
        self.test_user_data = {
            "username": f"testuser_{timestamp}",
            "email": f"test_{timestamp}@example.com",
            "real_name": f"Test User {timestamp}",
            "password": "testpassword123"
        }
        
        # Create a test user
        response = requests.post(f"{API_URL}/users/register", json=self.test_user_data)
        self.assertEqual(response.status_code, 200, "Test user registration failed")
        self.test_user_id = response.json()["id"]
        
        # Approve the test user
        approval_data = {
            "user_id": self.test_user_id,
            "approved": True,
            "admin_id": self.admin_user["id"],
            "role": "member"
        }
        response = requests.post(f"{API_URL}/users/approve", json=approval_data)
        self.assertEqual(response.status_code, 200, "Test user approval failed")
        
        # Login as test user
        login_data = {
            "username": self.test_user_data["username"],
            "password": self.test_user_data["password"]
        }
        response = requests.post(f"{API_URL}/users/login", json=login_data)
        self.assertEqual(response.status_code, 200, "Test user login failed")
        self.test_user = response.json()
    
    def test_01_user_registration_with_real_name(self):
        """Test user registration with real_name field"""
        timestamp = int(time.time())
        user_data = {
            "username": f"newuser_{timestamp}",
            "email": f"new_{timestamp}@example.com",
            "real_name": f"New User {timestamp}",
            "password": "newpassword123"
        }
        
        response = requests.post(f"{API_URL}/users/register", json=user_data)
        self.assertEqual(response.status_code, 200, "User registration failed")
        self.assertEqual(response.json()["real_name"], user_data["real_name"], "Real name not saved correctly")
    
    def test_02_user_login(self):
        """Test user login functionality"""
        login_data = {
            "username": self.test_user_data["username"],
            "password": self.test_user_data["password"]
        }
        
        response = requests.post(f"{API_URL}/users/login", json=login_data)
        self.assertEqual(response.status_code, 200, "User login failed")
        self.assertEqual(response.json()["username"], login_data["username"], "Username mismatch in login response")
    
    def test_03_profile_update(self):
        """Test profile update with real_name and screen_name"""
        profile_data = {
            "real_name": f"Updated Real Name {random_string()}",
            "screen_name": f"screen_{random_string()}"
        }
        
        response = requests.put(f"{API_URL}/users/{self.test_user['id']}/profile", json=profile_data)
        self.assertEqual(response.status_code, 200, "Profile update failed")
        self.assertEqual(response.json()["real_name"], profile_data["real_name"], "Real name not updated correctly")
        self.assertEqual(response.json()["screen_name"], profile_data["screen_name"], "Screen name not updated correctly")
    
    def test_04_admin_approval_with_role(self):
        """Test admin approval with role assignment"""
        # Create a new user to approve
        timestamp = int(time.time())
        new_user_data = {
            "username": f"approvaltest_{timestamp}",
            "email": f"approval_{timestamp}@example.com",
            "real_name": f"Approval Test {timestamp}",
            "password": "approvalpass123"
        }
        
        response = requests.post(f"{API_URL}/users/register", json=new_user_data)
        self.assertEqual(response.status_code, 200, "User registration for approval test failed")
        new_user_id = response.json()["id"]
        
        # Approve with moderator role
        approval_data = {
            "user_id": new_user_id,
            "approved": True,
            "admin_id": self.admin_user["id"],
            "role": "moderator"
        }
        
        response = requests.post(f"{API_URL}/users/approve", json=approval_data)
        self.assertEqual(response.status_code, 200, "User approval failed")
        
        # Verify the user's role
        response = requests.get(f"{API_URL}/users")
        users = response.json()
        approved_user = next((user for user in users if user["id"] == new_user_id), None)
        self.assertIsNotNone(approved_user, "Approved user not found")
        self.assertEqual(approved_user["role"], "moderator", "Role not assigned correctly")
    
    def test_05_position_actions(self):
        """Test position actions (buy more, sell partial, sell all)"""
        # Create a position first
        trade_data = {
            "symbol": "TSLA",
            "action": "BUY",
            "quantity": 10,
            "price": 250.0,
            "notes": "Test position"
        }
        
        response = requests.post(f"{API_URL}/trades?user_id={self.test_user['id']}", json=trade_data)
        self.assertEqual(response.status_code, 200, "Failed to create initial position")
        
        # Get positions
        response = requests.get(f"{API_URL}/positions/{self.test_user['id']}")
        self.assertEqual(response.status_code, 200, "Failed to get positions")
        positions = response.json()
        self.assertTrue(len(positions) > 0, "No positions found after creating one")
        
        position_id = positions[0]["id"]
        
        # Test buy more
        buy_more_data = {
            "action": "BUY_MORE",
            "quantity": 5,
            "price": 255.0
        }
        
        response = requests.post(f"{API_URL}/positions/{position_id}/action?user_id={self.test_user['id']}", json=buy_more_data)
        self.assertEqual(response.status_code, 200, "Buy more action failed")
        
        # Get updated positions
        response = requests.get(f"{API_URL}/positions/{self.test_user['id']}")
        positions = response.json()
        updated_position = next((pos for pos in positions if pos["id"] == position_id), None)
        self.assertIsNotNone(updated_position, "Position not found after buy more")
        self.assertEqual(updated_position["quantity"], 15, "Quantity not updated correctly after buy more")
        
        # Test sell partial
        sell_partial_data = {
            "action": "SELL_PARTIAL",
            "quantity": 3,
            "price": 260.0
        }
        
        response = requests.post(f"{API_URL}/positions/{position_id}/action?user_id={self.test_user['id']}", json=sell_partial_data)
        self.assertEqual(response.status_code, 200, "Sell partial action failed")
        
        # Get updated positions
        response = requests.get(f"{API_URL}/positions/{self.test_user['id']}")
        positions = response.json()
        updated_position = next((pos for pos in positions if pos["id"] == position_id), None)
        self.assertIsNotNone(updated_position, "Position not found after sell partial")
        self.assertEqual(updated_position["quantity"], 12, "Quantity not updated correctly after sell partial")
        
        # Test sell all
        sell_all_data = {
            "action": "SELL_ALL",
            "price": 265.0
        }
        
        response = requests.post(f"{API_URL}/positions/{position_id}/action?user_id={self.test_user['id']}", json=sell_all_data)
        self.assertEqual(response.status_code, 200, "Sell all action failed")
        
        # Get updated positions
        response = requests.get(f"{API_URL}/positions/{self.test_user['id']}")
        positions = response.json()
        closed_position = next((pos for pos in positions if pos["id"] == position_id), None)
        self.assertIsNone(closed_position, "Position still found after sell all")
    
    def test_06_message_creation_with_content_types(self):
        """Test message creation with different content types"""
        # Test text message
        text_message = {
            "content": "This is a test message with $TSLA ticker",
            "content_type": "text",
            "user_id": self.test_user["id"]
        }
        
        response = requests.post(f"{API_URL}/messages", json=text_message)
        self.assertEqual(response.status_code, 200, "Text message creation failed")
        self.assertEqual(response.json()["content_type"], "text", "Content type not set correctly")
        self.assertEqual(len(response.json()["highlighted_tickers"]), 1, "Ticker not extracted correctly")
        
        # Test image message
        image_message = {
            "content": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9/KKKKAP/2Q==",
            "content_type": "image",
            "user_id": self.test_user["id"]
        }
        
        response = requests.post(f"{API_URL}/messages", json=image_message)
        self.assertEqual(response.status_code, 200, "Image message creation failed")
        self.assertEqual(response.json()["content_type"], "image", "Content type not set correctly for image")
    
    def test_07_user_role_management(self):
        """Test user role management"""
        # Create a new user
        timestamp = int(time.time())
        new_user_data = {
            "username": f"roletest_{timestamp}",
            "email": f"role_{timestamp}@example.com",
            "real_name": f"Role Test {timestamp}",
            "password": "rolepass123"
        }
        
        response = requests.post(f"{API_URL}/users/register", json=new_user_data)
        self.assertEqual(response.status_code, 200, "User registration for role test failed")
        new_user_id = response.json()["id"]
        
        # Approve the user
        approval_data = {
            "user_id": new_user_id,
            "approved": True,
            "admin_id": self.admin_user["id"],
            "role": "member"
        }
        
        response = requests.post(f"{API_URL}/users/approve", json=approval_data)
        self.assertEqual(response.status_code, 200, "User approval for role test failed")
        
        # Change role to moderator
        role_update_data = {
            "user_id": new_user_id,
            "role": "moderator",
            "admin_id": self.admin_user["id"]
        }
        
        response = requests.post(f"{API_URL}/users/{new_user_id}/role", json=role_update_data)
        self.assertEqual(response.status_code, 200, "Role update to moderator failed")
        
        # Verify role change
        response = requests.get(f"{API_URL}/users")
        users = response.json()
        role_user = next((user for user in users if user["id"] == new_user_id), None)
        self.assertIsNotNone(role_user, "Role test user not found")
        self.assertEqual(role_user["role"], "moderator", "Role not updated to moderator correctly")
        
        # Change role to admin
        role_update_data = {
            "user_id": new_user_id,
            "role": "admin",
            "admin_id": self.admin_user["id"]
        }
        
        response = requests.post(f"{API_URL}/users/{new_user_id}/role", json=role_update_data)
        self.assertEqual(response.status_code, 200, "Role update to admin failed")
        
        # Verify role change and admin status
        response = requests.get(f"{API_URL}/users")
        users = response.json()
        role_user = next((user for user in users if user["id"] == new_user_id), None)
        self.assertIsNotNone(role_user, "Role test user not found")
        self.assertEqual(role_user["role"], "admin", "Role not updated to admin correctly")
        self.assertTrue(role_user["is_admin"], "is_admin flag not set correctly")
    
    def test_08_user_removal(self):
        """Test user removal"""
        # Create a new user to remove
        timestamp = int(time.time())
        new_user_data = {
            "username": f"removetest_{timestamp}",
            "email": f"remove_{timestamp}@example.com",
            "real_name": f"Remove Test {timestamp}",
            "password": "removepass123"
        }
        
        response = requests.post(f"{API_URL}/users/register", json=new_user_data)
        self.assertEqual(response.status_code, 200, "User registration for removal test failed")
        new_user_id = response.json()["id"]
        
        # Approve the user
        approval_data = {
            "user_id": new_user_id,
            "approved": True,
            "admin_id": self.admin_user["id"],
            "role": "member"
        }
        
        response = requests.post(f"{API_URL}/users/approve", json=approval_data)
        self.assertEqual(response.status_code, 200, "User approval for removal test failed")
        
        # Remove the user
        response = requests.delete(f"{API_URL}/users/{new_user_id}?admin_id={self.admin_user['id']}")
        self.assertEqual(response.status_code, 200, "User removal failed")
        
        # Verify user is removed
        response = requests.get(f"{API_URL}/users")
        users = response.json()
        removed_user = next((user for user in users if user["id"] == new_user_id), None)
        self.assertIsNone(removed_user, "User still exists after removal")
    
    def tearDown(self):
        """Clean up after tests"""
        # Logout test user
        requests.post(f"{API_URL}/users/logout?user_id={self.test_user['id']}")
        
        # Remove test user
        requests.delete(f"{API_URL}/users/{self.test_user['id']}?admin_id={self.admin_user['id']}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
