# Touri Mobile (Expo)

React Native + Expo Router client for the Touri FastAPI backend. Lives
alongside the existing Vite web app at `../frontend`.

## Setup

```bash
cd mobile
cp .env.example .env             # then fill in OAuth client IDs
npm install                       # or: pnpm install / bun install
npm start                         # NOT `npx expo start` — see note below
```

Press `i` for iOS simulator, `a` for Android, `w` for web, or scan the QR code with **Expo Go** on your phone.

> **Why `npm start` and not `npx expo start`?**
> macOS's default per-process file descriptor limit (often 256) is too small for Metro's
> file watcher and you'll see `EMFILE: too many open files, watch`. The `start` script
> in `package.json` runs `ulimit -n 65536` first to raise the limit.
>
> A more permanent fix is to install [watchman](https://facebook.github.io/watchman/):
> ```bash
> brew install watchman              # if you have Homebrew
> ```
> Metro picks it up automatically.

### iOS Simulator
`Press i` requires Xcode + an installed iOS Simulator runtime (Mac App Store → Xcode →
Settings → Components). If you don't have it, just use `w` (web) or scan the QR with
Expo Go on your phone.

### Backend on physical phone
Your iPhone needs to reach the FastAPI server. Set `EXPO_PUBLIC_API_BASE_URL` to your
Mac's LAN IP (not `localhost`):

```
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.88:8000
```

Run the backend with `--host 0.0.0.0` so it accepts LAN connections:

```bash
cd ../BackEnd
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment

All public env vars must be prefixed `EXPO_PUBLIC_` so Expo bundles them
into the JS payload. See `.env.example`.

| Var | Purpose |
|-----|---------|
| `EXPO_PUBLIC_FIREBASE_*` | Firebase web config — used by `config/firebaseConfig.ts` |
| `EXPO_PUBLIC_GOOGLE_*_CLIENT_ID` | OAuth client IDs from Google Cloud Console (Web, iOS, Android) |
| `EXPO_PUBLIC_API_BASE_URL` | FastAPI base URL (default `http://localhost:8000`) |

## Structure

```
mobile/
├── app/                # expo-router screens
│   ├── _layout.tsx     # Stack navigator + Firebase boot
│   └── index.tsx       # Chat home screen + Google Sign-In gate
├── config/
│   └── firebaseConfig.ts   # Firebase init w/ AsyncStorage persistence
├── hooks/
│   └── useAuth.ts      # Firebase + expo-auth-session Google flow
├── services/
│   └── api.ts          # Typed FastAPI client
├── app.json
├── babel.config.js
├── package.json
└── tsconfig.json
```

## Google Sign-In

1. In Google Cloud Console → Credentials, create OAuth Client IDs for **Web**, **iOS**, **Android**.
2. Set the iOS Bundle ID to `com.touri.app` and the Android package to `com.touri.app` (matches `app.json`).
3. Paste the client IDs into `.env`.
4. The `useAuth` hook in `hooks/useAuth.ts` handles the rest.
