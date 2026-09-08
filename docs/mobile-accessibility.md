# Fitician mobile accessibility acceptance

The native UI contract is verified by the shared component and contrast tests:

- screen-reader controls expose the native button/text-input semantics and
  stable Persian labels;
- interactive controls use the 48dp minimum touch target;
- text controls and button labels preserve system font scaling;
- focus traversal follows the declared React Native tree order;
- modal sheets and dialogs keep the native modal accessibility boundary;
- audited ink, muted, aqua, coral, and amber text colors meet the 4.5:1
  normal-text contrast threshold on the dark canvas.

Run the automated checks with:

```bash
npm --prefix mobile run test -- ui/components.test.ts ui/accessibility.test.ts
npm --prefix mobile run test:native
npm --prefix mobile run typecheck
```

The release acceptance pass must also exercise TalkBack with 200% font scale,
contrast settings, RTL traversal, keyboard focus, and touch exploration on API
24, 29, 33, and 36. Those device checks require an Android development build;
they are not claimed by the repository-only test run.
