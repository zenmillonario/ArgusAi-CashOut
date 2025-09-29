#!/usr/bin/env python3

import requests
import json
import os
import pymongo
from pymongo import MongoClient
import hashlib

class AdminLoginDebugger:
    def __init__(self):
        # Use the environment variable for the backend URL if available
        try:
            with open('/app/frontend/.env', 'r') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        base_url = line.strip().split('=')[1].strip('"\'')
                        break
        except:
            base_url = "http://localhost:8001"
            
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        
        print(f"🔗 Using API URL: {self.api_url}")
        
    def run_test(self, name, method, endpoint, expected_status, data=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        
        print(f"\n🔍 Testing {name}...")
        print(f"URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url)
            elif method == 'POST':
                response = requests.post(url, json=data)
            
            success = response.status_code == expected_status
            if success:
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"Response: {response.json()}")
                except:
                    print(f"Response: {response.text}")
                return False, {}
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}
    
    def debug_admin_login(self):
        """Debug the admin login authentication error"""
        print("\n🔍 DEBUGGING: Admin Login Authentication Error")
        
        # Test 1: Check if admin user exists in database
        print("\n📊 Test 1: Checking Admin User in Database")
        
        try:
            # Get MongoDB URL from environment
            mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/emergent_db')
            client = MongoClient(mongo_url)
            db = client['emergent_db']
            
            # Find all admin users
            admin_users = list(db.users.find({"is_admin": True}))
            print(f"✅ Found {len(admin_users)} admin users in database")
            
            for admin in admin_users:
                print(f"   - Username: {admin.get('username')}")
                print(f"   - Email: {admin.get('email')}")
                print(f"   - Status: {admin.get('status')}")
                print(f"   - Role: {admin.get('role')}")
                print(f"   - Has password_hash: {'password_hash' in admin}")
                print(f"   - Created: {admin.get('created_at')}")
                print("   ---")
            
            # Check if there's a user with username 'admin'
            admin_user = db.users.find_one({"username": "admin"})
            if admin_user:
                print(f"✅ Found user with username 'admin':")
                print(f"   - ID: {admin_user.get('id')}")
                print(f"   - Email: {admin_user.get('email')}")
                print(f"   - Status: {admin_user.get('status')}")
                print(f"   - Role: {admin_user.get('role')}")
                print(f"   - Is Admin: {admin_user.get('is_admin')}")
                print(f"   - Has password_hash: {'password_hash' in admin_user}")
                
                # Check password hash if it exists
                if 'password_hash' in admin_user:
                    # Test if admin123 matches the stored hash
                    test_password = "admin123"
                    test_hash = hashlib.sha256(test_password.encode()).hexdigest()
                    stored_hash = admin_user.get('password_hash')
                    
                    print(f"   - Password hash matches 'admin123': {test_hash == stored_hash}")
                    
                    # Also test 'admin' password
                    test_password2 = "admin"
                    test_hash2 = hashlib.sha256(test_password2.encode()).hexdigest()
                    print(f"   - Password hash matches 'admin': {test_hash2 == stored_hash}")
                    
                    # Show the actual hashes for debugging
                    print(f"   - Stored hash: {stored_hash}")
                    print(f"   - admin123 hash: {test_hash}")
                    print(f"   - admin hash: {test_hash2}")
                    
            else:
                print("❌ No user with username 'admin' found")
            
            client.close()
            
        except Exception as e:
            print(f"❌ Error checking database: {str(e)}")
            return False
        
        # Test 2: Test login endpoint with admin/admin123
        print("\n🔐 Test 2: Testing Login Endpoint with admin/admin123")
        
        success, response = self.run_test(
            "Login with admin/admin123",
            "POST",
            "users/login",
            200,
            data={"username": "admin", "password": "admin123"}
        )
        
        if success:
            print("✅ Login with admin/admin123 successful")
            print(f"   - User ID: {response.get('id')}")
            print(f"   - Session ID: {response.get('active_session_id')}")
            print(f"   - Status: {response.get('status')}")
            print(f"   - Is Admin: {response.get('is_admin')}")
            return True
        else:
            print("❌ Login with admin/admin123 failed")
            print("   Trying with admin/admin...")
            
            # Test 3: Test login endpoint with admin/admin
            success2, response2 = self.run_test(
                "Login with admin/admin",
                "POST",
                "users/login",
                200,
                data={"username": "admin", "password": "admin"}
            )
            
            if success2:
                print("✅ Login with admin/admin successful")
                print(f"   - User ID: {response2.get('id')}")
                print(f"   - Session ID: {response2.get('active_session_id')}")
                print(f"   - Status: {response2.get('status')}")
                print(f"   - Is Admin: {response2.get('is_admin')}")
                return True
            else:
                print("❌ Login with admin/admin also failed")
        
        # Test 4: Test with case variations
        print("\n🔤 Test 4: Testing Case Variations")
        
        test_combinations = [
            ("Admin", "admin123"),
            ("ADMIN", "admin123"),
            ("admin", "Admin123"),
            ("admin", "ADMIN123")
        ]
        
        for username, password in test_combinations:
            success, response = self.run_test(
                f"Login with {username}/{password}",
                "POST",
                "users/login",
                200,
                data={"username": username, "password": password}
            )
            
            if success:
                print(f"✅ Login successful with {username}/{password}")
                return True
            else:
                print(f"❌ Login failed with {username}/{password}")
        
        print("\n📋 SUMMARY:")
        print("❌ All login attempts failed")
        print("🔍 Check the database admin user setup and password hash")
        print("🔍 Verify the login endpoint is working correctly")
        
        return False

if __name__ == "__main__":
    print("🚀 Starting ArgusAI CashOut Admin Login Debug")
    
    debugger = AdminLoginDebugger()
    result = debugger.debug_admin_login()
    
    if result:
        print("\n✅ Admin Login Debug Complete - Login Working")
    else:
        print("\n❌ Admin Login Debug Complete - Login Issues Found")