# PhoneDesk

PhoneDesk يشغّل تجربة سطح مكتب لهواتف Android عبر ADB وscrcpy، مع مسار خاص لأجهزة Samsung التي توفر واجهة الشاشة الثانوية الخاصة بـ DeX.

## الاكتشاف الرئيسي

على Galaxy S25 Ultra / Android 16 / One UI 8.5 أثبت الاختبار أن إنشاء Virtual Display مناسب يجعل النظام نفسه يشغّل تلقائيًا:

- Samsung `SecondaryLauncher`
- `DexTaskbarWindow` الأصلي
- Navigation Bar خاص بالشاشة الثانوية
- خلفية ونظام HOME مستقلين عن شاشة الهاتف

لذلك المسار الأساسي في PhoneDesk لا يقلّد شريط DeX؛ بل يستخدم واجهة Samsung الأصلية المتاحة على الهاتف عندما يدعمها الجهاز.

## المتطلبات

- Python 3.10 أو أحدث.
- `adb` في PATH.
- `scrcpy` 4.1 أو إصدار متوافق في PATH.
- ربط ADB لاسلكي أو سلكي مسبقًا.

## التشغيل على Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py run.py
```

## التشغيل على Linux / Fedora

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Native Samsung DeX profile

المسار الذي تم التحقق منه يستخدم Virtual Display بدقة وكثافة `1600x900/160` مع mouse/keyboard SDK injection. على الجهاز المختبر أدى ذلك إلى إنشاء واجهة Samsung الثانوية وشريط DeX تلقائيًا دون Root.

قسم التطبيقات داخل PhoneDesk أصبح خيارًا احتياطيًا، ويجلب كل التطبيقات التي لها `MAIN/LAUNCHER` بدل الاكتفاء بتطبيقات المستخدم.

## التوثيق التقني

راجع `docs/DEX_TECHNICAL_MAP.md` للحصول على المكونات التي تم اكتشافها والاختبارات والقيود.

## الخطة

نثبت أولًا نسخة Desktop: App Drawer، الماوس/لوحة المفاتيح، Multi-Window والنوافذ الحرة. بعد ذلك نبدأ نسخة ويب تعمل عبر رابط مع Agent محلي آمن يربط المتصفح بالهاتف.
