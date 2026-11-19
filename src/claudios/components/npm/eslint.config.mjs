import security from "eslint-plugin-security";

export default [
  security.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "script" },
    rules: { "security/detect-object-injection": "off" },
  },
];