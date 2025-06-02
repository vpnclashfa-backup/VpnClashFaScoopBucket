# مخزن Scoop شخصی VpnClashFa

به مخزن شخصی من برای نرم‌افزارهای Scoop خوش آمدید!
در اینجا مجموعه‌ای از مانیفست‌ها برای نصب آسان نرم‌افزارهای کاربردی، به خصوص ابزارهای مرتبط با شبکه و حریم خصوصی، قرار دارد. این مخزن به طور خودکار با استفاده از GitHub Actions به‌روزرسانی می‌شود.

## scoop

برای اضافه کردن این مخزن (Bucket) به Scoop خود و استفاده از نرم‌افزارهای آن، دستور زیر را در PowerShell اجرا کنید:

```powershell
scoop bucket add VpnClashFa https://github.com/vpnclashfa-backup/VpnClashFaScoopBucket.git
scoop install VpnClashFa/<program-name>
```

پس از اضافه کردن مخزن، برای نصب یک نرم‌افزار از لیست زیر، از دستور `scoop install <نام_نرم‌افزار>` استفاده کنید. به عنوان مثال:

```powershell
scoop install VpnClashFa/clash-verge-rev
```

می‌توانید وضعیت و تاریخچه به‌روزرسانی‌های خودکار این مخزن را در صفحه Actions ما مشاهده کنید:
[صفحه وضعیت Actions](https://github.com/vpnclashfa-backup/VpnClashFaScoopBucket/actions)

## Packages
```text
(این لیست به طور خودکار توسط اسکریپت پایتون به‌روزرسانی خواهد شد. اگر این پیام را می‌بینید، یعنی اکشن هنوز اجرا نشده یا مشکلی در شناسایی پلیس‌هولدرها وجود داشته است.)
```
---

اگر پیشنهاد یا مشکلی در مورد این مخزن دارید، لطفاً یک Issue جدید در صفحه گیت‌هاب این ریپازیتوری باز کنید.
