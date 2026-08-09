import { useState } from "react";
import * as api from "../nutrition/api";

export function AdminSupplementsPage() {
  const [slug, setSlug] = useState(""); const [name, setName] = useState(""); const [saved, setSaved] = useState(false);
  async function save() { await api.saveSupplementCatalogue({ slug, name_fa: name, name_en: name, verification_status: "verified", source_name: "Admin verified source", source_reference: "https://", active_ingredients: [{ name }], nutrient_contribution_per_unit: {}, contraindication_codes: [], allergen_codes: [], interaction_codes: [], upper_bound_rules: [] }); setSaved(true); }
  return <main><h1>Supplement catalogue</h1><label>Slug<input value={slug} onChange={(e) => setSlug(e.target.value)} /></label><label>Name<input value={name} onChange={(e) => setName(e.target.value)} /></label><button onClick={() => void save()}>Save verified supplement</button>{saved && <p>Saved</p>}</main>;
}
