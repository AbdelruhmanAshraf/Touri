# Touri Frontend Client (Expo)

This is the React Native + Expo Router client application for Touri. It interfaces with the FastAPI backend to provide discovery, chat streaming, interactive planning checklists, and a trace view of the backend AI agents.

---

## 🚀 Setup & Launch

Ensure you have **Node.js 18+** installed.

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Configure environment variables
cp .env.example .env
# Fill in your Firebase web config credentials and target backend URL in .env

# 3. Install packages
npm install

# 4. Start the Metro bundler
npm start
```

Press:
*   `w` to run in a desktop web browser.
*   `i` to launch in the iOS Simulator (requires Xcode).
*   `a` to launch in the Android Emulator.
*   Or scan the QR code in your terminal with the **Expo Go** app on your physical phone.

> **⚠️ Note for macOS users:**
> The default per-process file descriptor limit on macOS can be too small for Metro's file watcher, causing `EMFILE: too many open files` errors.
> The `npm start` script runs `ulimit -n 65536` first to prevent this. To solve this permanently, install watchman:
> ```bash
> brew install watchman
> ```

---

## 🌐 Environment Variables Configuration

Create a `.env` file using the keys outlined in `.env.example`:

| Variable | Purpose |
|---|---|
| `EXPO_PUBLIC_FIREBASE_*` | Firebase web config variables used by `config/firebaseConfig.ts` |
| `EXPO_PUBLIC_GOOGLE_*_CLIENT_ID` | OAuth Client IDs for Web, iOS, and Android Google login flows |
| `EXPO_PUBLIC_API_BASE_URL` | Base URL of the FastAPI backend (e.g. `http://localhost:8000`) |

---

## 📂 Project Structure

```
frontend/
├── app/                  # Expo Router filesystem routing
│   ├── (tabs)/           # Main tab bar routes (Home, Plan, Discover, Chat, Profile)
│   ├── _layout.tsx       # Root layout, stack routing, and Firebase init
│   ├── index.tsx         # Initial gate / authentication routing
│   ├── onboarding.tsx    # 8-step user onboarding wizard
│   ├── place.tsx         # Place detail modal sheet
│   └── itinerary.tsx     # Legacy route redirect
│
├── components/           # Reusable UI components
│   ├── AgentTracePanel.tsx  # Interactive visualizer for sub-agent hops
│   ├── NotionAvatar.tsx  # Deterministic SVG Notion-style avatar generator
│   ├── ScreenHeader.tsx  # Reusable flat header with RTL options
│   └── TimelineItinerary.tsx # Day timeline rendering activities
│
├── config/               # Firebase setup
│   └── firebaseConfig.ts # Firebase client and auth init
│
├── constants/            # Styling constants
│   ├── Colors.ts         # Global app colors
│   └── Governorates.ts   # List of 27 Egyptian governorates
│
├── hooks/                # React custom hooks
│   ├── useAuth.ts        # Wraps Firebase + Google Auth Providers
│   └── useProfile.ts     # Syncs onboarding flag with local cache & Firestore
│
├── i18n/                 # Localization configurations
│   ├── locales/          # Localization JSON bundles (English and Arabic)
│   └── index.ts          # i18next setup and soft RTL toggling
│
├── services/             # Core API clients
│   ├── api.ts            # REST and WebSocket streams for chat
│   ├── secureStore.ts    # Keychain/AsyncStorage wrapper
│   └── wikipedia.ts      # Fetching destination header images
│
└── theme/                # Global styles
    └── tokens.ts         # Tonal flat iOS-style layout tokens
```
