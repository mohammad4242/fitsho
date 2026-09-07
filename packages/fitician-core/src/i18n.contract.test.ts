import en from "./i18n/en.js";
import fa from "./i18n/fa.js";

const resources = { en, fa } as const;
const languages = Object.keys(resources) as Array<keyof typeof resources>;

void languages;
void resources.en;
void resources.fa;
