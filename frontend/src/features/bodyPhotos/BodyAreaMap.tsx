import { useTranslation } from "react-i18next";

import type { BodyAnalysisFinding, BodyArea } from "./types";

const areaCoordinates: Record<BodyArea, [number, number]> = {
  shoulders: [100, 58],
  chest: [100, 78],
  back: [100, 84],
  lats: [80, 88],
  arms: [62, 98],
  forearms: [48, 126],
  waist_midsection: [100, 118],
  glutes: [100, 144],
  quads: [82, 172],
  hamstrings: [118, 172],
  calves: [82, 218],
  symmetry: [100, 104],
  visible_alignment_or_posture: [100, 132],
};

export function BodyAreaMap({ findings }: { findings: BodyAnalysisFinding[] }) {
  const { i18n, t } = useTranslation();
  const number = new Intl.NumberFormat(i18n.resolvedLanguage === "en" ? "en-US" : "fa-IR");

  return (
    <section className="body-area-map" aria-label={t("bodyPhotos.results.bodyMapLabel")}>
      <div className="body-area-map__figure" aria-hidden="true">
        <svg viewBox="0 0 200 270" role="presentation">
          <circle className="body-area-map__outline" cx="100" cy="27" r="17" />
          <path className="body-area-map__outline" d="M72 58 Q100 45 128 58 L139 117 Q126 142 121 150 L128 247 M128 72 L153 132 M72 72 L47 132 M72 58 L61 117 Q74 142 79 150 L72 247 M79 150 Q100 161 121 150" />
          <path className="body-area-map__center" d="M100 48V151" />
          {findings.map((finding) => {
            const [cx, cy] = areaCoordinates[finding.body_area];
            return <circle className="body-area-map__marker" data-classification={finding.classification} cx={cx} cy={cy} r="6" key={finding.body_area} />;
          })}
        </svg>
      </div>
      <div>
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.results.bodyMapEyebrow")}</p>
        <h2>{t("bodyPhotos.results.bodyMapTitle")}</h2>
        <ul>
          {findings.map((finding) => (
            <li data-classification={finding.classification} key={finding.body_area}>
              <span aria-hidden="true" />
              <div>
                <strong>{t(`bodyPhotos.results.areas.${finding.body_area}`)}</strong>
                <small>{t(`bodyPhotos.results.classifications.${finding.classification}`)}</small>
              </div>
              <b>{number.format(Math.round(finding.confidence * 100))}%</b>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
