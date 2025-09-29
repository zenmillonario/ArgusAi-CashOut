# 🛡️ Admin User Management Guide
## Trial User Removal & Management

### 👥 **VIEWING TRIAL USERS**

#### See All Trial Users:
```
GET /api/admin/trial-users
```
**Returns:**
- Active trial users (with days remaining)
- Expired trial users (ready for conversion) 
- Total counts and statistics

#### See Users Needing Admin Attention:
```
GET /api/users/pending
```
**Shows:**
- Pending approval users
- Active trial users 
- Expired trial users
- Clear status indicators for each

### 🗑️ **REMOVING INDIVIDUAL USERS**

#### Remove Single User (Trial or Regular):
```
DELETE /api/users/{user_id}?admin_id={admin_id}
```

**What Gets Deleted:**
- ✅ User account
- ✅ All user messages
- ✅ User notifications
- ✅ Trading positions/history
- ✅ FCM tokens
- ✅ Cash prizes
- ✅ Social connections (followers/following)

**Safety Features:**
- ❌ Cannot remove admin users
- ✅ Comprehensive cleanup of all user data
- ✅ Detailed logging of removal
- ✅ Admin notification to other admins

#### Example (Remove Trial User):
```bash
curl -X DELETE "https://your-app.com/api/users/USER_ID_HERE?admin_id=ADMIN_ID_HERE"
```

**Response:**
```json
{
  "message": "User trial_user removed successfully",
  "user_details": {
    "username": "trial_user",
    "status": "trial", 
    "membership_plan": "14-Day Trial",
    "removed_by": "admin"
  },
  "cleanup_stats": {
    "messages_deleted": 5,
    "notifications_deleted": 2,
    "trades_deleted": 0,
    "positions_deleted": 0,
    "fcm_tokens_deleted": 1,
    "cash_prizes_deleted": 0
  }
}
```

### 🔥 **BULK REMOVAL (Multiple Trial Users)**

#### Remove Multiple Trial Users at Once:
```
DELETE /api/admin/trial-users/bulk
```

**Request Body:**
```json
{
  "admin_id": "admin-id-here",
  "user_ids": ["user1-id", "user2-id", "user3-id"]
}
```

**Safety Limits:**
- ✅ Maximum 50 users per bulk operation
- ✅ Only works on trial/trial_expired users
- ✅ Cannot bulk remove regular approved users
- ✅ Cannot bulk remove admin users

**Use Cases for Bulk Removal:**
- 🧪 Clean up test trial accounts
- 🚫 Remove spam trial registrations  
- 🧹 Periodic cleanup of expired trials

### 📊 **ADMIN DASHBOARD INTEGRATION**

#### Current Trial Statistics:
- **Active Trials**: Users currently in 14-day trial
- **Expired Trials**: Users who need manual conversion after payment
- **Conversion Ready**: Users who paid and need upgrade to member status

#### User Status Indicators:
- **🎯 ACTIVE TRIAL**: Auto-approved, X days remaining
- **⏰ TRIAL EXPIRED**: Needs manual conversion to member
- **👤 PENDING**: Needs admin approval for regular membership

### ⚠️ **IMPORTANT CONSIDERATIONS**

#### Before Removing Users:
1. **Trial Users**: Can be safely removed if spam/test accounts
2. **Paid Users**: Should only be removed for violations, not payment issues
3. **Data Loss**: Removal is permanent - all user data is deleted
4. **Conversion Option**: Consider converting expired trials to members instead

#### Best Practices:
- ✅ Review user activity before removal
- ✅ Use bulk removal for obvious spam/test accounts
- ✅ Convert legitimate expired trials to paid members
- ✅ Document reason for removals in admin notes

### 🔧 **COMMON ADMIN TASKS**

#### Clean Up Test Trial Accounts:
1. List active trials: `GET /api/admin/trial-users`
2. Identify test accounts (usernames like "trial_test_*")
3. Bulk remove: `DELETE /api/admin/trial-users/bulk`

#### Process Expired Trials:
1. Check expired trials: `GET /api/admin/trial-users` 
2. For paid users: Convert with `POST /api/admin/convert-trial`
3. For non-paying users: Remove with `DELETE /api/users/{id}`

#### Monitor Trial System:
- Daily check of active vs expired trial counts
- Weekly cleanup of obvious test accounts
- Monthly review of conversion rates

Your admin panel now has comprehensive tools for managing the entire trial user lifecycle! 🎯