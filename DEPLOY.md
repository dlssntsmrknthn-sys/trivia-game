# 🚀 Deploying TriviaBlast to Railway (Online)

Follow these steps to make the game playable worldwide.

---

## Step 1: Create a GitHub Repository

1. Go to **https://github.com** and sign in
2. Click the **"+"** icon (top right) → **"New repository"**
3. Fill in:
   - **Repository name:** `trivia-game`
   - **Visibility:** Public
   - ❌ Do NOT check "Add a README file"
4. Click **"Create repository"**
5. Keep this page open — you'll need the URL shown

---

## Step 2: Push Code to GitHub

Open **Command Prompt** (search "cmd" in Start menu) and run these commands one by one:

```
cd C:\Users\mrknt\Desktop\trivia-game

git init

git add .

git commit -m "Initial commit - TriviaBlast game"

git branch -M main

git remote add origin https://github.com/YOUR_GITHUB_USERNAME/trivia-game.git

git push -u origin main
```

> ⚠️ Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username!
> 
> When prompted, enter your GitHub username and password (or personal access token).

---

## Step 3: Deploy on Railway

1. Go to **https://railway.app**
2. Click **"Start a New Project"** → Sign up/in with GitHub
3. Click **"Deploy from GitHub repo"**
4. Select your **`trivia-game`** repository
5. Railway will auto-detect Python and start building
6. Wait ~2 minutes for the build to complete

---

## Step 4: Add the Google Credentials Environment Variable

This is the most important step — without it, questions won't load from Google Sheets.

1. In Railway, click on your deployed service
2. Go to the **"Variables"** tab
3. Click **"New Variable"**
4. Set:
   - **Name:** `GOOGLE_CREDENTIALS`
   - **Value:** *(paste the entire contents of your credentials.json file)*

To get the value, open `credentials.json` in Notepad and copy ALL the text (the entire JSON object from `{` to `}`).

5. Click **"Add"** → Railway will automatically redeploy

---

## Step 5: Get Your Public URL

1. In Railway, click on your service → **"Settings"** tab
2. Under **"Domains"**, click **"Generate Domain"**
3. You'll get a URL like: `https://trivia-game-production.up.railway.app`

**Share this URL with anyone in the world to play!** 🌍

---

## Step 6: Test It

1. Open your Railway URL in a browser
2. Click **"Create Session"** → note the 6-character code
3. Click **"Open Host Dashboard"** → **"Join as Host"**
4. On another device/browser, go to the same URL
5. Enter the session code + a username → Join
6. Host clicks **"Start Game!"**
7. Play! 🎮

---

## 🔄 Updating the Game Later

If you make changes to the code:

```
cd C:\Users\mrknt\Desktop\trivia-game
git add .
git commit -m "Update game"
git push
```

Railway will automatically redeploy within ~1 minute.

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| "Application error" on Railway | Check the Logs tab in Railway for error details |
| Questions not loading | Make sure GOOGLE_CREDENTIALS env var is set correctly |
| WebSocket not connecting | Railway supports WebSockets — check if your plan allows it |
| Build fails | Check that all files were pushed to GitHub |

---

## 📊 Viewing Game Logs

After games are played, scores are automatically written to your Google Sheet:
**https://docs.google.com/spreadsheets/d/1dexaAuVyMPB676q28CeP9sh52J3Vk0SSleWNAxgYj3U/**

Open the **"Log"** tab to see all session results.
