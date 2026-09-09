module.exports = {
  preset: "jest-expo",
  rootDir: __dirname,
  moduleNameMapper: {
    "^@fitician/core$": "<rootDir>/../packages/fitician-core/dist/index.js",
    "^@fitician/core/(.*)$": "<rootDir>/../packages/fitician-core/dist/$1.js",
  },
  testMatch: [
    "<rootDir>/**/*.rntl.test.ts",
    "<rootDir>/**/*.rntl.test.tsx",
  ],
};
