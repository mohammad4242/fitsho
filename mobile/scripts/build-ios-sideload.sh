#!/usr/bin/env bash

set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ios_dir="$root_dir/mobile/ios"
output_dir="${IOS_SIDELOAD_OUTPUT_DIR:-$root_dir/dist/ios}"
derived_data_dir="$output_dir/DerivedData"
staging_dir="$output_dir/.staging"
ipa_path="$output_dir/Fitician-unsigned.ipa"
metadata_path="$output_dir/fitician-ios-build-info.txt"

if [[ ! -d "$ios_dir" ]]; then
  echo "Generated iOS directory is missing: $ios_dir" >&2
  exit 1
fi

mkdir -p "$output_dir"
rm -rf "$derived_data_dir" "$staging_dir" "$ipa_path" "$metadata_path"

workspace_count="$(find "$ios_dir" -maxdepth 1 -type d -name '*.xcworkspace' -print | wc -l | tr -d ' ')"
if [[ "$workspace_count" != "1" ]]; then
  echo "Expected one generated iOS workspace, found $workspace_count" >&2
  find "$ios_dir" -maxdepth 1 -type d -name '*.xcworkspace' -print >&2
  exit 1
fi
workspace="$(find "$ios_dir" -maxdepth 1 -type d -name '*.xcworkspace' -print)"

workspace_list="$output_dir/xcode-workspace-list.json"
xcodebuild -list -json -workspace "$workspace" > "$workspace_list"
scheme="$(jq -r '.workspace.schemes[]? | select(ascii_downcase == "fitician")' "$workspace_list" | head -n 1)"
if [[ -z "$scheme" ]]; then
  scheme="$(jq -r '.workspace.schemes[0] // empty' "$workspace_list")"
fi
if [[ -z "$scheme" ]]; then
  echo "No Xcode scheme found in $workspace" >&2
  cat "$workspace_list" >&2
  exit 1
fi

entitlements_file="$(find "$ios_dir" -type f -name '*.entitlements' -print | head -n 1 || true)"
if [[ -n "$entitlements_file" ]]; then
  for capability in \
    "aps-environment" \
    "com.apple.developer.applesignin" \
    "com.apple.developer.associated-domains"; do
    if /usr/libexec/PlistBuddy -c "Print :$capability" "$entitlements_file" >/dev/null 2>&1; then
      echo "Unsupported sideload entitlement remains: $capability" >&2
      /usr/libexec/PlistBuddy -c "Print" "$entitlements_file" >&2
      exit 1
    fi
  done
fi

echo "Building workspace=$workspace scheme=$scheme destination=generic/platform=iOS"
xcodebuild \
  -workspace "$workspace" \
  -scheme "$scheme" \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$derived_data_dir" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY='' \
  DEVELOPMENT_TEAM='' \
  build

product_dir="$derived_data_dir/Build/Products/Release-iphoneos"
app_path=""
while IFS= read -r candidate; do
  candidate_bundle_id="$(plutil -extract CFBundleIdentifier raw -o - "$candidate/Info.plist")"
  if [[ "$candidate_bundle_id" == "com.fitician.app" ]]; then
    app_path="$candidate"
    break
  fi
done < <(find "$product_dir" -maxdepth 1 -type d -name '*.app' -print | sort)

if [[ -z "$app_path" ]]; then
  echo "Fitician app was not produced under $product_dir" >&2
  find "$product_dir" -maxdepth 2 -print >&2 || true
  exit 1
fi

executable_name="$(plutil -extract CFBundleExecutable raw -o - "$app_path/Info.plist")"
executable_path="$app_path/$executable_name"
if [[ ! -s "$executable_path" ]]; then
  echo "App executable is missing or empty: $executable_path" >&2
  exit 1
fi

build_platforms="$(xcrun otool -l "$executable_path" | awk '$1 == "platform" { print $2 }')"
if ! grep -Eq '(^|[[:space:]])2([[:space:]]|$)' <<< "$build_platforms"; then
  echo "The app executable is not an iOS device binary" >&2
  xcrun otool -l "$executable_path" | grep -A4 -B1 'LC_BUILD_VERSION' >&2 || true
  exit 1
fi
if grep -Eq '(^|[[:space:]])7([[:space:]]|$)' <<< "$build_platforms"; then
  echo "The app executable contains an iOS simulator platform" >&2
  exit 1
fi

js_bundle="$(find "$app_path" -type f \( -name '*.jsbundle' -o -name 'main.jsbundle' \) -print | head -n 1 || true)"
if [[ -z "$js_bundle" || ! -s "$js_bundle" ]]; then
  echo "Embedded React Native JavaScript bundle is missing" >&2
  exit 1
fi
for model in pose_landmarker_lite.task selfie_segmenter.tflite; do
  model_path="$(find "$app_path" -type f -name "$model" -print | head -n 1 || true)"
  if [[ -z "$model_path" || ! -s "$model_path" ]]; then
    echo "Bundled Body Vision model is missing: $model" >&2
    exit 1
  fi
done

resource_count="$(find "$app_path" -type f | wc -l | tr -d ' ')"
if [[ "$resource_count" -le 5 ]]; then
  echo "App resources are unexpectedly empty" >&2
  exit 1
fi

app_bundle_name="$(basename "$app_path")"
mkdir -p "$staging_dir/Payload"
ditto "$app_path" "$staging_dir/Payload/$app_bundle_name"
(cd "$staging_dir" && zip -qry "$ipa_path" Payload)

unzip -t "$ipa_path"
zip_listing="$(unzip -Z1 "$ipa_path")"
packaged_info_path="$(printf '%s\n' "$zip_listing" | grep -E '^Payload/[^/]+\.app/Info\.plist$' | head -n 1 || true)"
if [[ -z "$packaged_info_path" ]]; then
  echo "IPA does not contain Payload/*.app/Info.plist at its root" >&2
  printf '%s\n' "$zip_listing" >&2
  exit 1
fi
unzip -p "$ipa_path" "$packaged_info_path" > "$output_dir/packaged-info.plist"
packaged_bundle_id="$(plutil -extract CFBundleIdentifier raw -o - "$output_dir/packaged-info.plist")"
if [[ "$packaged_bundle_id" != "com.fitician.app" ]]; then
  echo "Packaged bundle identifier is $packaged_bundle_id" >&2
  exit 1
fi

ipa_size="$(stat -f '%z' "$ipa_path")"
ipa_sha256="$(shasum -a 256 "$ipa_path" | awk '{print $1}')"
git_sha="${GITHUB_SHA:-$(git -C "$root_dir" rev-parse HEAD)}"
git_branch="${GITHUB_REF_NAME:-$(git -C "$root_dir" branch --show-current)}"
git_branch="${git_branch:-detached}"
xcode_version="$(xcodebuild -version | tr '\n' ';' | sed 's/;$//')"
macos_version="$(sw_vers -productVersion)"
sdk_version="$(xcrun --sdk iphoneos --show-sdk-version)"
build_date="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
cat > "$metadata_path" <<EOF
git commit SHA: $git_sha
git branch: $git_branch
build date (UTC): $build_date
app name: Fitician
bundle identifier: com.fitician.app
configuration: Release
SDK: iphoneos
APP_VARIANT: ${APP_VARIANT:-development}
IOS_SIDELOAD_BUILD: ${IOS_SIDELOAD_BUILD:-0}
backend URL: ${EXPO_PUBLIC_API_BASE_URL:-}
frontend origin: ${EXPO_PUBLIC_FRONTEND_ORIGIN:-}
IPA filename: $(basename "$ipa_path")
IPA size: $ipa_size
SHA-256: $ipa_sha256
Xcode version: $xcode_version
macOS runner version: $macos_version
iphoneos SDK version: $sdk_version
workspace: $workspace
scheme: $scheme
app bundle: $app_bundle_name
embedded JS bundle: $js_bundle
EOF

echo "IPA: $ipa_path"
echo "Size: $ipa_size bytes"
echo "SHA-256: $ipa_sha256"
