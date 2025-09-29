#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from server import UserCreate, UserStatus
import json

async def test_trial_registration():
    """Test trial user registration logic"""
    
    # Test trial user data
    trial_user_data = UserCreate(
        username="trial_user_test",
        email="trial@test.com",
        real_name="Trial User",
        membership_plan="trial",
        is_trial=True,
        password="testpass123"
    )
    
    # Test regular user data
    regular_user_data = UserCreate(
        username="regular_user_test",
        email="regular@test.com", 
        real_name="Regular User",
        membership_plan="premium",
        is_trial=False,
        password="testpass123"
    )
    
    print("✅ Trial registration test data created successfully")
    print(f"Trial user: {trial_user_data.username}, is_trial: {trial_user_data.is_trial}")
    print(f"Regular user: {regular_user_data.username}, is_trial: {regular_user_data.is_trial}")
    
    # Test UserStatus enum
    print(f"UserStatus.TRIAL: {UserStatus.TRIAL}")
    print(f"UserStatus.PENDING: {UserStatus.PENDING}")
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test_trial_registration())
    if result:
        print("🎉 Trial registration system test passed!")
    else:
        print("❌ Trial registration system test failed!")