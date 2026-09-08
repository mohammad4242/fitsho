import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PublicPageFrame } from "./PublicPageFrame";
import "./publicAccount.css";

export function PrivacyPolicyPage() {
  const { i18n } = useTranslation();
  const english = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => english ? en : fa;

  return (
    <PublicPageFrame>
      <article className="public-account-card public-account-card--reading">
        <p className="public-account-card__eyebrow">{l("حریم خصوصی", "Privacy")}</p>
        <h1 className="fitsho-display">{l("سیاست حریم خصوصی", "Privacy policy")}</h1>
        <p className="public-account-card__lead">
          {l(
            "فیتشو برای کمک به برنامه‌ریزی تمرین و تغذیه، اطلاعاتی را که خودت در حساب وارد می‌کنی پردازش می‌کند.",
            "Fitsho processes the information you enter in your account to help plan training and nutrition.",
          )}
        </p>

        <section>
          <h2>{l("چه اطلاعاتی پردازش می‌شود؟", "What information is processed?")}</h2>
          <p>
            {l(
              "اطلاعات ورود، مشخصات پروفایل، ترجیحات تمرینی و تغذیه‌ای، سابقه برنامه‌ها و داده‌هایی که برای استفاده از قابلیت‌های فیتشو ثبت می‌کنی پردازش می‌شوند. تصاویر خصوصی بدن، عکس‌های غذا و مدارک آزمایشگاهی به عنوان داده خصوصی نگهداری می‌شوند و فقط برای قابلیت مربوط به خودشان استفاده می‌شوند.",
              "Account credentials, profile details, training and nutrition preferences, program history, and data you submit to use Fitsho features are processed. Private body images, food photos, and laboratory documents are kept as private data and used only for their related feature.",
            )}
          </p>
        </section>

        <section>
          <h2>{l("استفاده و اشتراک‌گذاری", "Use and sharing")}</h2>
          <p>
            {l(
              "این داده‌ها برای ارائه، ایمن‌سازی و بهبود سرویس استفاده می‌شوند. فیتشو داده‌های حساب را برای تبلیغات شخصی‌سازی‌شده نمی‌فروشد. هر پردازش متخصص یا سرویس بیرونی باید فقط در محدوده قابلیت مربوط و با کنترل‌های دسترسی فیتشو انجام شود.",
              "This data is used to provide, secure, and improve the service. Fitsho does not sell account data for personalized advertising. Specialist or external-service processing must remain within the related feature and Fitsho access controls.",
            )}
          </p>
        </section>

        <section>
          <h2>{l("کنترل‌های تو", "Your controls")}</h2>
          <p>
            {l(
              "می‌توانی از داخل حساب به داده‌های خود دسترسی داشته باشی و درخواست حذف حساب بدهی. حذف حساب پس از پایان مهلت بازگشت انجام می‌شود؛ داده‌های خصوصی و رکوردهای شخصی حذف می‌شوند و فقط مواردی که طبق ماتریس نگهداری مصوب لازم باشند، با حداقل داده باقی می‌مانند.",
              "You can access your data from your account and request account deletion. Deletion takes place after the grace period; private data and personal records are deleted, while only the minimum data required by an approved retention matrix may remain.",
            )}
          </p>
          <Link className="public-account-card__text-link" to="/delete-account">
            {l("مدیریت یا درخواست حذف حساب", "Manage or request account deletion")}
          </Link>
        </section>

        <p className="public-account-card__updated">
          {l("آخرین به‌روزرسانی: ۸ سپتامبر ۱۴۰۵", "Last updated: September 8, 2026")}
        </p>
      </article>
    </PublicPageFrame>
  );
}
