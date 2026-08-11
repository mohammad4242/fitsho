# Food Catalogue Redesign Design

## Goal

Redesign the existing Food Catalogue to closely match `Foodcattalog.png` while adding optional, admin-managed food images without changing nutrition calculations, catalogue data, search behavior, filtering, or pagination.

## Architecture

Add a nullable `image_path` column to `nutrition_catalogue_foods`. Store uploaded public images below `var/media/food-catalogue/` and persist only their `/media/food-catalogue/<generated-name>` path. Extend the existing validated media storage code with a scoped image-only upload function rather than creating a separate attachment system.

Expose `image_url` from both member and admin catalogue item schemas. Keep member and admin response models separate so member responses never serialize a `price` key. Existing nutrition values, portions, provenance, aliases, category filtering, and pagination remain unchanged.

## Admin Image Flow

Add a trusted-origin, admin-only upload endpoint for one food slug. It accepts one uploaded JPEG, PNG, WebP, or GIF image and rejects external URLs, empty files, invalid signatures, unsupported MIME types, and non-image media.

The upload is written to `var/media/food-catalogue/` with a generated filename. The database path is updated only after validation succeeds. If persistence fails, the new file is removed and the previous database value remains. After a successful replacement, the previous file is removed when it is inside the managed food catalogue media directory.

Food creation remains JSON-based. An admin may create a food without an image and upload its image afterward from the catalogue card. Existing Add Food and Edit Price flows remain available.

## Member and Admin API Contracts

Both catalogue read endpoints return:

- `image_url: string | null`
- all existing identity, macro, nutrient, portion, and source fields

Only the admin endpoint returns `price`. The member endpoint must omit `price` entirely, including when accepted or overridden price records exist.

## Interface Design

The page remains dark and Fitsho-branded, using the reference's compact mobile composition rather than copying its application chrome.

- A concise page title and back action sit above the catalogue.
- Search remains bilingual and alias-aware through the unchanged backend query.
- Categories become horizontally scrollable chips. The active chip uses Fitsho turquoise, with `All` first.
- Cards use a single-column list on mobile and a restrained multi-column layout only when space permits.
- Each card shows a circular food image, Persian and English names, a turquoise calorie value aligned to the inline end, the current serving basis, and only Protein, Carbs, and Fat.
- Cards without an image show a polished neutral food fallback that does not make an extra network request.
- Fibre, all micronutrients, portions, measurement basis, and provenance remain in More Details.
- Admin-only image and price actions remain compact and visually secondary. Members do not render any price information or price controls.
- Existing pagination stays below the cards.

The design is mobile-first, supports Persian RTL and English LTR, preserves visible keyboard focus, uses touch targets of at least 44 CSS pixels for primary controls, and avoids required motion.

## Components and Boundaries

- `FoodCataloguePage` owns loading, query, category, pagination, dialogs, and reload state.
- `FoodCard` owns the compact visual summary and missing-image fallback.
- `FoodDetails` owns all secondary nutrition, portion, and provenance data.
- A focused admin image dialog owns file selection, preview, upload state, and errors.
- The API client owns the multipart upload request and typed `image_url` contract.
- Backend media storage owns file validation and lifecycle; catalogue routing owns authorization and food lookup; catalogue serialization owns member/admin response boundaries.

## Error Handling

- Invalid uploads return a validation response and do not alter the current image.
- Unknown or retired foods return not found.
- Failed persistence removes the newly uploaded file.
- A broken or missing image URL switches the card to the same local fallback.
- Failed catalogue loads and failed uploads retain the existing retry/error patterns.

## Testing

Backend tests cover migration/model persistence, successful image upload, replacement and old-file cleanup, invalid image rejection, admin authorization, `image_url` in both catalogue APIs, nullable images, and member price-key absence.

Frontend tests cover image rendering, broken/missing-image fallback, category chips and preserved filtering, three-macro card content, More Details retention, admin upload/replace controls, successful reload after upload, and absence of all price content for members.

Run focused backend and frontend tests first, then backend Ruff and mypy, frontend lint and build, and the full relevant test suites. Apply the migration and perform a browser-sized RTL smoke check against the reference when the local stack is available.

## Git Scope

Commit only Food Catalogue design, migration, backend catalogue/media/API files, frontend catalogue/API files, and their tests. Preserve all unrelated modified and untracked files already present in the worktree.
