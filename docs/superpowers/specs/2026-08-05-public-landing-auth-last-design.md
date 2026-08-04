# Fitsho public landing and auth-last onboarding

## Approved experience

- The landing uses one fixed background video while text sections reveal on scroll.
- The expected local asset is `frontend/public/image&videos/film.mp4`; a dark fallback is shown when absent.
- Get Started opens product-mode selection before any account form.
- Training, nutrition, and combined onboarding remain page-by-page with back and skip controls.
- Pre-auth answers live only in `sessionStorage` and are cleared after successful server hydration.
- The final step offers email registration or login. Google, Apple, and phone are disabled as upcoming.
- Public safety preview reuses the backend's versioned deterministic policy without persisting medical data.
- Store and social destinations remain labelled upcoming until real URLs are supplied.

## Persistence order after authentication

1. Product mode
2. Shared profile
3. Safety profile
4. Training profile when selected
5. Nutrition profile when the safety result permits it

The draft remains available if any persistence request fails.
