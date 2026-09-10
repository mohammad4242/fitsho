# Mobile video release on navigation blur

## Goal

Release native exercise-video resources when the user leaves the current mobile
route, preventing hidden tab screens from retaining `expo-video` players and
causing Android heap exhaustion.

## Scope

- Update `mobile/exercises/ExerciseMedia.tsx`.
- Add focused React Native rendering tests for focused and unfocused video media.
- Keep image media, API contracts, playback controls, and route behavior unchanged.

## Design

`ExerciseMedia` reads the current Expo Router focus state. Video media renders
`Media` only while its route is focused. On blur, the `Media` subtree unmounts;
the existing `useVideoPlayer` cleanup then releases the native ExoPlayer. When
the route is focused again, the video player is created again from the same
source. Non-video media remains mounted and unchanged.

## Verification

- Focused video media mounts a native video view.
- Unfocused video media does not mount a native video view.
- Existing mobile workout and media tests pass.
- Run a physical-device smoke check after rebuilding the development APK; no
  backend or persisted-data changes are required.
