# Template Exercise Library Links Design

## Goal

Give every training-template exercise an admin-visible detail link and turn
missing template exercises into safe, editable catalog records.

## Design

The template seed will derive one catalog-placeholder exercise for every
unresolved template slot. A placeholder has target muscles, movement pattern,
equipment hint, exercise type, bilingual draft guidance, placeholder media,
`needs_review=true`, and `is_programmable=false`. It remains an active catalog
record so its detail route works, but the workout engine cannot select it.

The template seed prefers a reviewed catalog exercise over a template
placeholder when an imported alias later becomes available. It never overwrites
an existing placeholder, preserving an admin's GIF, metadata, and review work.

The admin template card shows a turquoise icon link named "Details" beside each
exercise. It opens the existing exercise-detail route, which already displays
media, instructions, and safety notes. Review-needed records carry a visible
media/review note.

## Tests

Backend tests prove all template slots link to an exercise, generated records
remain non-programmable, and reseeding preserves edited placeholder media.
API and React tests prove the link is returned and rendered.
