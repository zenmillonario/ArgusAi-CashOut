// Frontend Profile Fixes
// Update your App.js with these changes

// 1. Enhanced state for profile management
const [editProfileForm, setEditProfileForm] = useState({
  username: '',
  real_name: '',
  email: '',
  avatar_file: null
});

// 2. File upload handler (NO URL option)
const handleAvatarUpload = async (file) => {
  if (!file) return;
  
  if (file.size > 2 * 1024 * 1024) {
    alert('Image too large. Please choose a file under 2MB.');
    return;
  }
  
  if (!file.type.startsWith('image/')) {
    alert('Please select an image file.');
    return;
  }
  
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await axios.post(`${API}/users/upload-avatar?user_id=${currentUser.id}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    // Update user with new avatar
    setCurrentUser({...currentUser, avatar_url: response.data.avatar_url});
    setShowEditProfile(false);
    alert('Profile picture updated successfully!');
  } catch (error) {
    alert('Error uploading profile picture: ' + (error.response?.data?.detail || error.message));
  }
};

// 3. Enhanced Profile Tab with Larger Avatar
const ProfileTab = () => (
  <div className="space-y-6">
    {/* Profile Header with LARGE Avatar */}
    <div className={`backdrop-blur-lg rounded-2xl border p-8 ${
      isDarkTheme ? 'bg-white/5 border-white/10' : 'bg-white/80 border-gray-200'
    }`}>
      <div className="flex items-center space-x-8">
        {/* LARGER Profile Picture - 150x150 */}
        <div className="relative">
          <div className="w-36 h-36 rounded-2xl overflow-hidden border-4 border-blue-400/50 shadow-xl">
            {currentUser?.avatar_url ? (
              <img 
                src={currentUser.avatar_url} 
                alt="Profile" 
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'flex';
                }}
              />
            ) : null}
            <div className={`w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-4xl ${currentUser?.avatar_url ? 'hidden' : 'flex'}`}>
              {currentUser?.real_name?.charAt(0).toUpperCase() || currentUser?.username?.charAt(0).toUpperCase()}
            </div>
          </div>
          
          {/* Upload Button */}
          <label className="absolute -bottom-3 -right-3 w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-white cursor-pointer hover:bg-blue-700 transition-colors shadow-lg">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => e.target.files[0] && handleAvatarUpload(e.target.files[0])}
              className="hidden"
            />
            📷
          </label>
        </div>
        
        {/* Profile Info */}
        <div className="flex-1">
          <h2 className={`text-3xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            {currentUser?.real_name || 'Full Name'}
          </h2>
          <p className={`text-xl ${isDarkTheme ? 'text-blue-400' : 'text-blue-600'}`}>
            @{currentUser?.username}
          </p>
          <p className={`${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
            {currentUser?.email}
          </p>
          <div className="flex items-center space-x-3 mt-3">
            {currentUser?.is_admin && (
              <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 text-sm rounded-full font-semibold">
                👑 Admin
              </span>
            )}
            {currentUser?.is_moderator && (
              <span className="px-3 py-1 bg-purple-500/20 text-purple-400 text-sm rounded-full font-semibold">
                🛡️ Moderator
              </span>
            )}
            <span className="text-green-400 text-sm font-semibold">
              📅 Member since {new Date(currentUser?.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        
        <div className="flex flex-col space-y-3">
          <button
            onClick={openEditProfile}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
          >
            ✏️ Edit Profile
          </button>
          <button
            onClick={() => setShowChangePassword(true)}
            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold"
          >
            🔐 Change Password
          </button>
        </div>
      </div>
    </div>
    
    {/* Performance Stats remain the same */}
  </div>
);

// 4. Enhanced Edit Profile Modal (File Upload Only)
const EditProfileModal = () => (
  <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 w-full max-w-lg border border-white/20">
      <h2 className="text-2xl font-bold text-white mb-6">✏️ Edit Profile</h2>
      
      <form onSubmit={updateProfile} className="space-y-6">
        {/* Profile Picture Upload */}
        <div>
          <label className="block text-gray-300 mb-3 font-semibold">Profile Picture</label>
          
          {/* Current Avatar Preview */}
          <div className="flex items-center space-x-6 mb-4">
            <div className="w-24 h-24 rounded-xl overflow-hidden border-2 border-white/20">
              {currentUser?.avatar_url ? (
                <img src={currentUser.avatar_url} alt="Current" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-xl">
                  {currentUser?.real_name?.charAt(0).toUpperCase() || 'U'}
                </div>
              )}
            </div>
            
            {/* Upload Button */}
            <div className="flex-1">
              <label className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors cursor-pointer font-semibold text-center block">
                📷 Choose New Picture
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => e.target.files[0] && handleAvatarUpload(e.target.files[0])}
                  className="hidden"
                />
              </label>
              <p className="text-gray-400 text-sm mt-2">
                JPG, PNG, GIF up to 2MB
              </p>
            </div>
          </div>
        </div>
        
        {/* Real Name */}
        <div>
          <label className="block text-gray-300 mb-2 font-semibold">Full Name</label>
          <input
            type="text"
            placeholder="John Doe"
            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={editProfileForm.real_name}
            onChange={(e) => setEditProfileForm({...editProfileForm, real_name: e.target.value})}
            required
          />
        </div>
        
        {/* Screen Name */}
        <div>
          <label className="block text-gray-300 mb-2 font-semibold">Screen Name</label>
          <input
            type="text"
            placeholder="johndoe123"
            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={editProfileForm.username}
            onChange={(e) => setEditProfileForm({...editProfileForm, username: e.target.value})}
            required
          />
        </div>
        
        {/* Email */}
        <div>
          <label className="block text-gray-300 mb-2 font-semibold">Email</label>
          <input
            type="email"
            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={editProfileForm.email}
            onChange={(e) => setEditProfileForm({...editProfileForm, email: e.target.value})}
            required
          />
        </div>
        
        <div className="flex space-x-4 pt-4">
          <button
            type="submit"
            className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200"
          >
            💾 Save Changes
          </button>
          <button
            type="button"
            onClick={() => setShowEditProfile(false)}
            className="flex-1 bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
          >
            ❌ Cancel
          </button>
        </div>
      </form>
    </div>
  </div>
);