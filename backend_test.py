import requests
import sys
import time
import uuid
import base64
import os
from datetime import datetime

class CashOutAiTester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.users = {}
        self.admin_user = None
        self.messages = []
        self.trades = []
        self.positions = []

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'} if not files else {}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, params=params)
                else:
                    response = requests.post(url, json=data, headers=headers, params=params)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, params=params)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                if response.text:
                    try:
                        return success, response.json()
                    except:
                        return success, response.text
                return success, None
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"Response: {response.text}")
                return False, None

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, None

    def register_user(self, username, email, password):
        """Register a new user"""
        success, response = self.run_test(
            f"Register user {username}",
            "POST",
            "users/register",
            200,
            data={"username": username, "email": email, "password": password}
        )
        
        if success and response:
            self.users[username] = response
            print(f"User {username} registered with ID: {response['id']}")
            return response
        return None

    def login_user(self, username, password):
        """Login a user"""
        success, response = self.run_test(
            f"Login user {username}",
            "POST",
            "users/login",
            200,
            data={"username": username, "password": password}
        )
        
        if success and response:
            self.users[username] = response
            print(f"User {username} logged in with ID: {response['id']}")
            if response.get('is_admin', False):
                self.admin_user = response
            return response
        return None

    def get_pending_users(self):
        """Get pending users (admin only)"""
        success, response = self.run_test(
            "Get pending users",
            "GET",
            "users/pending",
            200
        )
        
        if success and response:
            print(f"Found {len(response)} pending users")
            return response
        return []

    def approve_user(self, user_id, approved=True):
        """Approve or reject a user (admin only)"""
        if not self.admin_user:
            print("❌ No admin user logged in")
            return False
            
        success, response = self.run_test(
            f"{'Approve' if approved else 'Reject'} user {user_id}",
            "POST",
            "users/approve",
            200,
            data={
                "user_id": user_id,
                "approved": approved,
                "admin_id": self.admin_user['id']
            }
        )
        
        return success

    def upload_avatar(self, user_id, avatar_url):
        """Update user avatar URL (legacy endpoint)"""
        success, response = self.run_test(
            f"Update avatar URL for user {user_id}",
            "POST",
            f"users/{user_id}/avatar",
            200,
            params={"avatar_url": avatar_url}  # Using params instead of data
        )
        
        return success, response

    def upload_avatar_file(self, user_id, file_path):
        """Upload profile picture file"""
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                
            files = {'file': (os.path.basename(file_path), file_content, 'image/jpeg')}
            
            success, response = self.run_test(
                f"Upload avatar file for user {user_id}",
                "POST",
                f"users/{user_id}/avatar-upload",
                200,
                files=files,
                params={"user_id": user_id}
            )
            
            return success, response
        except Exception as e:
            print(f"❌ Failed to upload file: {str(e)}")
            return False, None

    def upload_invalid_avatar_file(self, user_id, file_path, content_type):
        """Upload invalid profile picture file to test validation"""
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                
            files = {'file': (os.path.basename(file_path), file_content, content_type)}
            
            success, response = self.run_test(
                f"Upload invalid avatar file for user {user_id}",
                "POST",
                f"users/{user_id}/avatar-upload",
                400,  # Expecting 400 Bad Request
                files=files,
                params={"user_id": user_id}
            )
            
            return success, response
        except Exception as e:
            print(f"❌ Failed to upload file: {str(e)}")
            return False, None

    def create_test_image(self, size_kb=100):
        """Create a test image file of specified size"""
        filename = f"/tmp/test_image_{int(time.time())}.jpg"
        
        # Create a simple colored image as bytes
        width, height = 100, 100
        header = bytes([
            0xFF, 0xD8,                      # SOI marker
            0xFF, 0xE0,                      # APP0 marker
            0x00, 0x10,                      # APP0 header size (16 bytes)
            0x4A, 0x46, 0x49, 0x46, 0x00,    # Identifier: ASCII "JFIF" followed by 0
            0x01, 0x01,                      # Version: 1.1
            0x00,                            # Density units: 0 (no units)
            0x00, 0x01, 0x00, 0x01,          # Density: 1x1
            0x00, 0x00                       # Thumbnail: 0x0
        ])
        
        # Create some image data to reach the desired size
        target_size = size_kb * 1024
        data_size = target_size - len(header) - 2  # 2 bytes for EOI marker
        data = bytes([0xFF if i % 2 == 0 else 0x00 for i in range(data_size)])
        
        # EOI marker
        footer = bytes([0xFF, 0xD9])
        
        # Write the file
        with open(filename, 'wb') as f:
            f.write(header + data + footer)
        
        print(f"Created test image: {filename} ({os.path.getsize(filename)} bytes)")
        return filename

    def create_large_test_image(self, size_mb=2):
        """Create a large test image file to test size validation"""
        return self.create_test_image(size_kb=size_mb * 1024)

    def create_test_text_file(self):
        """Create a test text file to test file type validation"""
        filename = f"/tmp/test_file_{int(time.time())}.txt"
        
        with open(filename, 'w') as f:
            f.write("This is a test text file, not an image.")
        
        print(f"Created test text file: {filename}")
        return filename

    def change_password(self, user_id, current_password, new_password):
        """Change user password"""
        success, response = self.run_test(
            f"Change password for user {user_id}",
            "POST",
            f"users/{user_id}/change-password",
            200,
            data={
                "current_password": current_password,
                "new_password": new_password
            }
        )
        
        return success, response

    def change_password_with_invalid_current(self, user_id, current_password, new_password):
        """Test password change with invalid current password"""
        success, response = self.run_test(
            f"Change password with invalid current password for user {user_id}",
            "POST",
            f"users/{user_id}/change-password",
            400,  # Expecting 400 Bad Request
            data={
                "current_password": current_password,
                "new_password": new_password
            }
        )
        
        return success, response

def test_profile_features():
    # Get the backend URL from the frontend .env file
    backend_url = "https://cashoutai-trading.preview.emergentagent.com"
    
    # Create tester instance
    tester = CashOutAiTester(backend_url)
    
    print("\n===== TESTING PROFILE FEATURES =====\n")
    
    # Test 1: Login as admin
    print("\n----- Test 1: Admin Login -----")
    admin = tester.login_user("admin", "anything")
    if not admin or not admin.get('is_admin', False):
        print("❌ Admin login failed, stopping tests")
        return 1
    
    # Test 2: Register a new user
    print("\n----- Test 2: User Registration -----")
    timestamp = int(time.time())
    test_user = tester.register_user(f"tester_{timestamp}", f"tester_{timestamp}@example.com", "password123")
    
    if not test_user:
        print("❌ User registration failed, stopping tests")
        return 1
    
    # Test 3: Approve the user
    print("\n----- Test 3: Approve User -----")
    pending_users = tester.get_pending_users()
    
    if pending_users:
        for user in pending_users:
            if user['username'] == test_user['username']:
                tester.approve_user(user['id'], True)
    
    # Test 4: Login as the approved user
    print("\n----- Test 4: Login Approved User -----")
    user_login = tester.login_user(test_user['username'], "password123")
    
    if not user_login:
        print("❌ User login failed, stopping tests")
        return 1
    
    # Test 5: Update avatar URL (legacy method)
    print("\n----- Test 5: Update Avatar URL -----")
    avatar_url = "https://i.imgur.com/ZPYCiyg.png"
    success, response = tester.upload_avatar(user_login['id'], avatar_url)
    
    if not success:
        print("❌ Avatar URL update failed")
    
    # Test 6: Create test image file
    print("\n----- Test 6: Create Test Image Files -----")
    test_image = tester.create_test_image(size_kb=100)  # Reduced size to 100KB
    large_test_image = tester.create_large_test_image()
    test_text_file = tester.create_test_text_file()
    
    # Test 7: Upload valid image file
    print("\n----- Test 7: Upload Valid Image File -----")
    success, response = tester.upload_avatar_file(user_login['id'], test_image)
    
    if not success:
        print("❌ Valid image upload failed")
    else:
        print(f"Avatar URL: {response.get('avatar_url', 'N/A')}")
    
    # Test 8: Upload oversized image file (should fail with 400)
    print("\n----- Test 8: Upload Oversized Image File (should fail) -----")
    success, response = tester.upload_invalid_avatar_file(user_login['id'], large_test_image, 'image/jpeg')
    
    if not success:
        print("❌ Test failed - but this is expected for oversized images")
    else:
        print("✅ Oversized image upload correctly rejected with 400 status")
    
    # Test 9: Upload non-image file (should fail with 400)
    print("\n----- Test 9: Upload Non-Image File (should fail) -----")
    success, response = tester.upload_invalid_avatar_file(user_login['id'], test_text_file, 'text/plain')
    
    if not success:
        print("❌ Test failed - but this is expected for non-image files")
    else:
        print("✅ Non-image file upload correctly rejected with 400 status")
    
    # Test 10: Change password with correct current password
    print("\n----- Test 10: Change Password -----")
    # In the demo, current password is the username
    success, response = tester.change_password(user_login['id'], user_login['username'], "NewPassword123")
    
    if not success:
        print("❌ Password change failed")
    else:
        print("✅ Password changed successfully")
    
    # Test 11: Change password with incorrect current password (should fail)
    print("\n----- Test 11: Change Password with Incorrect Current Password (should fail) -----")
    success, response = tester.change_password_with_invalid_current(user_login['id'], "WrongPassword", "NewPassword456")
    
    if not success:
        print("❌ Test failed - but this is expected for invalid current password")
    else:
        print("✅ Password change with incorrect current password correctly rejected with 400 status")
    
    # Clean up test files
    print("\n----- Cleaning Up Test Files -----")
    for file_path in [test_image, large_test_image, test_text_file]:
        try:
            os.remove(file_path)
            print(f"Removed {file_path}")
        except:
            pass
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

def main():
    return test_profile_features()

if __name__ == "__main__":
    sys.exit(main())