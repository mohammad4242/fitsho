# Fitician mobile observability

Mobile telemetry is provider-neutral. `MobileTelemetryLogger` sends only fixed
event names and an allowlisted scalar context to `SentryCompatibleAdapter`.
Exceptions are represented by a generic error; the original error message,
request path, request body, tokens, images, laboratory documents, and medical
text are never forwarded. Every event has a correlation ID.

## Release artifacts

Generate the Android JavaScript bundle and external source map with:

```bash
npm --prefix mobile run export:android:source-maps
```

The command writes ignored artifacts under `mobile/dist/android-release/`:

- `index.android.js` and `index.android.js.map` for the JavaScript release.
- `assets/` for the bundle assets.

Release Android builds enable R8 shrinking through the CNG plugin. The signed
build must retain `android/app/build/outputs/mapping/release/mapping.txt` and
native symbol files for the provider upload step. Upload source maps, mapping,
and native symbols to the configured provider before distributing the binary;
do not package them in the app.
