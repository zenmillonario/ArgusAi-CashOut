#!/usr/bin/env python3

import requests
import json

def test_wrong_password():
    """Test that wrong passwords are properly rejected"""
    print("🔍 Testing Wrong Password Rejection")
    
    # Use the environment variable for the backend URL if available
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    base_url = line.strip().split('=')[1].strip('"\'')
                    break
    except:
        base_url = "http://localhost:8001"
        
    api_url = f"{base_url}/api"
    
    print(f"🔗 Using API URL: {api_url}")
    
    # Test wrong passwords
    wrong_passwords = ["admin", "wrongpass", "123456", "password", ""]
    
    for wrong_pass in wrong_passwords:
        print(f"\n🔐 Testing login with admin/{wrong_pass}")
        
        try:
            response = requests.post(f"{api_url}/users/login", json={
                "username": "admin",
                "password": wrong_pass
            })
            
            if response.status_code == 401:
                print(f"✅ Correctly rejected wrong password: {wrong_pass}")
            elif response.status_code == 200:
                print(f"❌ SECURITY ISSUE: Wrong password accepted: {wrong_pass}")
                print(f"   Response: {response.json()}")
            else:
                print(f"⚠️ Unexpected status {response.status_code} for password: {wrong_pass}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error testing password {wrong_pass}: {str(e)}")
    
    # Test correct password
    print(f"\n🔐 Testing login with admin/admin123 (correct password)")
    
    try:
        response = requests.post(f"{api_url}/users/login", json={
            "username": "admin",
            "password": "admin123"
        })
        
        if response.status_code == 200:
            print(f"✅ Correctly accepted correct password: admin123")
            data = response.json()
            print(f"   User ID: {data.get('id')}")
            print(f"   Session ID: {data.get('active_session_id')}")
        else:
            print(f"❌ ISSUE: Correct password rejected")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing correct password: {str(e)}")

if __name__ == "__main__":
    test_wrong_password()