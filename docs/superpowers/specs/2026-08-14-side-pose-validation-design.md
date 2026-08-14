# View-Aware Pose Validation Design

## Goal

Reduce false client-side rejections for valid headless side and back photos while retaining
real, deterministic full-body and multiple-person checks.

## Landmark Rules

- Front views continue to require both visible shoulders, elbows, wrists, hips, knees,
  ankles, and feet.
- Back views require both shoulders and both arms. Each arm is valid when either its elbow
  or its wrist is visible at the existing confidence threshold. A hidden endpoint is excluded
  from frame and minimum-confidence checks when the other endpoint on that arm is valid.
- Back views continue to require both hips, knees, ankles, and feet.
- Side views require at least one visible shoulder, elbow, hip, knee, ankle, and foot.
- The most visible landmark in each required side-view group is used for visibility,
  frame-boundary, and minimum-confidence checks.
- A hidden far-side landmark does not cause `arms_not_visible`,
  `legs_or_feet_not_visible`, or `body_out_of_frame`.
- View classification remains conservative. Ambiguous semantics continue to AI preflight.

## Multiple-Person Rules

- MediaPipe may return up to two real pose candidates.
- The processor evaluates the candidates instead of treating every second output as a
  second person.
- A candidate is credible only when it contains enough non-face body structure for physique
  analysis: shoulders and hips plus sufficient arm and lower-body landmark groups.
- Strongly overlapping pose candidates are treated as duplicate detections of one person.
- A secondary candidate triggers `multiple_people_detected` only when it is credible,
  spatially distinct, and materially sized relative to the primary pose.
- Weak, duplicate, or small ambiguous candidates do not cause deterministic rejection;
  semantic AI preflight remains responsible for ambiguous scenes.

## Data Flow

`MediaPipe pose candidates -> credible candidate filtering -> duplicate suppression ->
primary pose selection / clear multiple-person rejection -> view-aware landmark validation ->
segmentation -> neutral-background normalization`

No face detector, head crop, generative editing, or fabricated confidence is introduced.

## Tests

- Accept a side photo when only one shoulder, elbow, hip, knee, ankle, and foot are visible.
- Ignore hidden far-side landmarks outside the frame.
- Reject a side photo when neither landmark in a required group is visible.
- Accept a back photo when each arm has a visible elbow or wrist.
- Reject a back photo when one arm has neither a visible elbow nor wrist.
- Treat overlapping duplicate pose candidates as one person.
- Ignore a weak secondary pose candidate.
- Reject two credible, spatially distinct full-body pose candidates.
- Preserve existing front, back, quality, segmentation, and privacy tests.
