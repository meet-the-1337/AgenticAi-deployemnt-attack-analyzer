# Deploying ReconMind to Vercel / GitHub Pages

This guide walks you through deploying the ReconMind security SOC dashboard to free hosting platforms like **Vercel** or **GitHub Pages**. 

Since free static hosts cannot run Python backends, we have pre-packaged all SQLite run history and telemetry data into static JSON files under `frontend/public/api/`. The frontend's API client (`client.js`) has been optimized to automatically detect when the backend is offline and fall back to these static datasets seamlessly.

---

## ⚡ Option 1: Deploy to Vercel (Recommended)

Vercel is the easiest platform for React apps. It offers single-command deployments and handles client-side routing automatically.

### Step 1: Install Vercel CLI (if not already installed)
```bash
npm install -g vercel
```

### Step 2: Deploy from the Frontend Directory
Navigate to the `frontend/` directory and run the deploy command:
```bash
cd frontend
vercel
```
1. When asked `Set up and deploy?`, type **`y`**.
2. Select your Vercel account.
3. Link to an existing project? Type **`N`**.
4. Name your project (e.g. `reconmind-soc`).
5. For directory, choose the default (`./`).
6. When asked to modify build settings, type **`N`** (Vercel automatically detects Vite and configures the build settings correctly).

### Step 3: Deploy to Production
To make your deployment public and accessible:
```bash
vercel --prod
```

> [!NOTE]
> We have pre-configured `frontend/vercel.json` to handle client-side React Routing. If you reload on a page like `/history`, Vercel will correctly route the request without showing a 404.

---

## 🐙 Option 2: Deploy to GitHub Pages

To host on GitHub Pages for free, you can build the site and deploy the `dist/` folder using the `gh-pages` package.

### Step 1: Install `gh-pages` helper
```bash
cd frontend
npm install --save-dev gh-pages
```

### Step 2: Update `vite.config.js`
Ensure your base path matches your GitHub repository name. For example, if your repository is `github.com/username/reconmind`, add the base configuration:
```javascript
// vite.config.js
export default defineConfig({
  base: '/reconmind/', // Replace with your repository name
  // ... other configurations
})
```

### Step 3: Add Deploy Scripts to `package.json`
Add these scripts to `frontend/package.json`:
```json
"scripts": {
  "predeploy": "npm run build",
  "deploy": "gh-pages -d dist"
}
```

### Step 4: Deploy
Initialize a git repository in your project root, push it to GitHub, then run:
```bash
npm run deploy
```

---

## 🔄 Re-Exporting Database Changes
If you generate new runs or update your local SQLite database and want to update the deployed website:
1. Run the exporter script from the project root:
   ```bash
   python scripts/export_static_api.py
   ```
2. Re-deploy the frontend:
   ```bash
   cd frontend
   vercel --prod # Or npm run deploy for GitHub Pages
   ```
