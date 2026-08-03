# Firebase Authentication Error: network-request-failed

## Overview
The error **"Firebase: Error (auth/network-request-failed)"** occurs in the **client** (Expo/React Native app), not the backend. This means the app cannot communicate with Firebase's authentication servers.

## Root Causes

### 1. **Network Connectivity** (Most Common)
- Device/emulator doesn't have internet access
- Network is behind a corporate firewall/proxy that blocks Firebase domains
- WiFi/cellular connection is unstable or not active

### 2. **Incorrect Firebase Configuration**
- Missing or invalid environment variables in `frontend/.env`
- Invalid API key that's been revoked or restricted
- Project ID mismatch between client and backend

### 3. **Device/Time Issues**
- **Android**: Device date/time is incorrect (SSL certificate validation fails)
- **iOS**: Clock skew or certificate pinning issues with outdated SDK

### 4. **SDK Version Issues**
- Outdated Firebase SDK
- Incompatible Expo version
- Missing React Native persistence module

## Diagnostic Steps

### Step 1: Check Console Logs
When you try to sign in, look for these enhanced error messages:

```
[ Firebase config incomplete!firebaseConfig] 
```

This now logs which config fields are missing:
```json
{
  " set",apiKey": "
  " set",authDomain": "
  " set",projectId": "
  " set",storageBucket": "
  " set",messagingSenderId": "
  " set"appId": "
}
```

And during sign-in attempts:
```
[firebaseConfig] Sign in failed: {
  "code": "auth/network-request-failed",
  "message": "A network error (such as timeout, interrupted connection...",
  "firebaseConfigStatus": {
    "",apiKey": "
    "",authDomain": "
    ""projectId": "
  }
}
```

### Step 2: Verify Environment Configuration

**Check `frontend/.env`:**
```bash
cat frontend/.env
```

Ensure these are set:
```
EXPO_PUBLIC_FIREBASE_API_KEY=YOUR_FIREBASE_API_KEY_HERE
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=tripmiind.firebaseapp.com
EXPO_PUBLIC_FIREBASE_PROJECT_ID=tripmiind
EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET=tripmiind.firebasestorage.app
EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=461435283582
EXPO_PUBLIC_FIREBASE_APP_ID=1:461435283582:web:71f1aeff57aa5e16dc502f
```

### Step 3: Test Network Connectivity

**On your device/emulator, test basic connectivity:**
```bash
# If on Android emulator
adb shell ping 8.8.8.8

# If on iOS simulator
# Use Xcode console or make a simple HTTP request
```

**Test Firebase endpoint directly:**
```bash
curl -v https://tripmiind.firebaseapp.com
```

### Step 4: Verify Firebase API Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select project: **tripmiind**
3. Go to **Settings > Project Settings**
4. Check the **API Key** tab:
 API key is active (not disabled)   - 
 No IP/HTTP referer restrictions that block your app   - 
 Has "Cloud Firestore API" and "Authentication" enabled   - 

### Step 5: Check Device Date/Time

**For Android:**
- Go to Settings > System > Date & Time
- Verify time is automatically set and correct

**For iOS:**
- Go to Settings > General > Date & Time
- Verify time is automatically set

Incorrect time causes SSL certificate validation failures.

## Fixes

### Fix 1: Reinstall Firebase SDK
```bash
cd frontend
npm install firebase@latest
cd ..
```

### Fix 2: Clear App Cache & Reinstall
```bash
# For Expo Go
expo start --clear

# For custom dev client
eas build --platform ios --profile development
eas build --platform android --profile development
```

### Fix 3: Update Environment Variables
If you changed the API key in Firebase Console:
1. Update `frontend/.env`
2. Restart your app (hard refresh)
3. Clear Expo cache: `expo start --clear`

### Fix 4: Network Configuration
If behind a corporate firewall:
- Whitelist these Firebase domains:
  - `*.firebase.com`
  - `*.firebaseapp.com`
  - `*.firebasestorage.app`

### Fix 5: Check Firestore Security Rules
While this shouldn't affect auth, verify rules aren't blocking initial connection:

```bash
# Deploy updated rules
firebase deploy --only firestore:rules
```

## Enhanced Error Tracking

The code has been updated with better error logging. When sign-in fails, you'll see:

```typescript
[firebaseConfig] Sign in failed: {
  code: "auth/network-request-failed",
  message: "Network error description",
  email: "user@example.com",
  timestamp: "2026-05-20T10:07:08.375+03:00",
  firebaseConfigStatus: {
    ",apiKey: "
    ",authDomain: "
    "projectId: "
  }
}
```

The `useAuth` hook also now returns an `authError` state:
```typescript
const { authError, signInWithEmail } = useAuth();

// Display error to user
{authError && <Text style={{color: 'red'}}>{authError}</Text>}
```

## Validation Checklist

- [ ] `frontend/.env` has all 6 Firebase config fields
- [ ] Firebase API key is active (not disabled)
- [ ] Device/emulator has internet access
- [ ] Device date/time is correct
- [ ] Firebase SDK is up to date
- [ ] You can `curl` Firebase endpoints from your network
- [ ] Firestore rules are deployed

## Backend Status

 Backend is working correctly (confirmed by user)
- Firebase Admin SDK initialized properly
- Service account credentials valid
- Session endpoints functioning

The issue is isolated to the **client-side authentication**, not backend infrastructure.

## Next Steps

1. **Enable console logging**: Check your app's console for the enhanced error messages
2. **Run diagnostics**: Follow Step 1-5 above
3. **Try basic connectivity**: `curl` Firebase endpoints
4. **Clear app cache**: `expo start --clear`
5. **Reinstall SDK**: `npm install firebase@latest`

If issues persist, you'll have detailed error logs showing exactly which part of the auth flow is failing and why.
