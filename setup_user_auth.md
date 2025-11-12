# Setup User Authentication for Vertex AI

Instead of service account, use your Google account (smaan2011@gmail.com) for authentication.

## Step 1: Login with Application Default Credentials

```bash
gcloud auth application-default login --project=amadds102025
```

This will:
1. Open browser for you to login with `smaan2011@gmail.com`
2. Create application default credentials
3. Store credentials locally

## Step 2: Update .env

Remove the service account key path:

```bash
# Comment out or remove
# GOOGLE_CLOUD_KEY_PATH=secrets/gcp-service-key.json
```

## Step 3: Update Services to Use Application Default Credentials

The code will automatically use your user credentials when `GOOGLE_CLOUD_KEY_PATH` is not set.

## Step 4: Restart and Test

```bash
docker-compose restart
python TEST_REAL_PRODUCTION_MA_ANALYSIS.py
```

---

## Why This Works:

- User accounts generate proper access tokens (not just ID tokens)
- No need to manage service account keys
- Easier for development/testing
- Uses your email: smaan2011@gmail.com

## For Production:

For actual commercial deployment, you'll want to switch back to service account, but using your user account for now will unblock testing!
