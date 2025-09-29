#!/usr/bin/env python3

import os
import pymongo
from pymongo import MongoClient
import hashlib

def hash_password(password: str) -> str:
    """Hash a password for storing in database"""
    return hashlib.sha256(password.encode()).hexdigest()

def fix_admin_password():
    """Fix the admin user by adding proper password hash"""
    print("🔧 Fixing Admin User Password Hash")
    
    try:
        # Get MongoDB URL from environment
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/emergent_db')
        client = MongoClient(mongo_url)
        db = client['emergent_db']
        
        # Find the admin user
        admin_user = db.users.find_one({"username": "admin"})
        if not admin_user:
            print("❌ Admin user not found")
            return False
        
        print(f"✅ Found admin user: {admin_user.get('id')}")
        print(f"   - Current has password_hash: {'password_hash' in admin_user}")
        
        # Set the password to admin123
        password = "admin123"
        password_hash = hash_password(password)
        
        print(f"   - Setting password to: {password}")
        print(f"   - Generated hash: {password_hash}")
        
        # Update the admin user with password hash
        result = db.users.update_one(
            {"username": "admin"},
            {"$set": {"password_hash": password_hash}}
        )
        
        if result.modified_count > 0:
            print("✅ Admin user password hash updated successfully")
            
            # Verify the update
            updated_admin = db.users.find_one({"username": "admin"})
            if updated_admin and 'password_hash' in updated_admin:
                stored_hash = updated_admin['password_hash']
                if stored_hash == password_hash:
                    print("✅ Password hash verification successful")
                    print(f"   - Stored hash matches generated hash")
                else:
                    print("❌ Password hash verification failed")
                    print(f"   - Stored: {stored_hash}")
                    print(f"   - Expected: {password_hash}")
            else:
                print("❌ Could not verify password hash update")
        else:
            print("❌ Failed to update admin user password hash")
            return False
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error fixing admin password: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Admin Password Fix")
    
    result = fix_admin_password()
    
    if result:
        print("\n✅ Admin Password Fix Complete")
        print("   - Admin user now has proper password hash")
        print("   - Password is set to: admin123")
        print("   - Login should now work securely")
    else:
        print("\n❌ Admin Password Fix Failed")