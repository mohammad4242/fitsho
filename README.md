# Fitsho

## AI model administration

The OpenCode Zen key remains only in `backend/.env`:

```env
OPENCODE_ZEN_API_KEY="your-key"
```

An administrator can open `/admin/ai-models` and manage workout-generation
models without restarting the backend:

1. Select **Sync Zen** to fetch the current Zen model catalogue.
2. Classify every newly discovered disabled model with its API kind and billing class.
3. Test the model, then enable it when the test succeeds.
4. Choose **Manual** and select one enabled model, or choose **Automatic** and order
   enabled free models for fallback.

The next workout-generation request reads the saved routing setting directly from
the database. Automatic routing tries enabled free models in the configured order.
