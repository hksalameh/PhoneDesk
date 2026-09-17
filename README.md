# PhoneDesk

تجربة سطح مكتب للهاتف على Windows وLinux بالاعتماد على ADB وscrcpy.

## الهدف

PhoneDesk لا يكتفي بعرض شاشة الهاتف، بل يبني فوق scrcpy واجهة واحدة لإدارة:

- الاتصال اللاسلكي عبر ADB.
- عرض شاشة الهاتف مع الصوت والتحكم.
- إنشاء Virtual Display قابل لتغيير الحجم.
- تشغيل تطبيق Android في نافذة مستقلة على الكمبيوتر.
- حفظ عنوان الهاتف والإعدادات محليًا.

## خط الأساس الحالي

المشروع مستهدف حاليًا لهاتف Galaxy S25 Ultra يعمل بـ Android 16 / One UI 8.5،
مع scrcpy 4.1 واتصال ADB لاسلكي.

## المتطلبات

- Python 3.11 أو أحدث.
- `adb` موجود في PATH.
- `scrcpy` موجود في PATH.
- الهاتف سبق ربطه لاسلكيًا مع ADB.

## التشغيل

### Linux / Fedora

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py run.py
```

## الوظائف في MVP

1. فحص وجود ADB وscrcpy.
2. الاتصال بعنوان الهاتف مثل `192.168.1.2:5555`.
3. تشغيل العرض العادي للهاتف.
4. تشغيل Desktop Virtual Display.
5. جلب حزم تطبيقات المستخدم.
6. تشغيل تطبيق محدد في نافذة Virtual Display مستقلة.
7. إيقاف جلسات PhoneDesk المفتوحة.

## ملاحظات

قد يكون الـ Virtual Display فارغًا على بعض الأجهزة إذا لم يوفّر النظام Launcher للعرض الثانوي.
في هذه الحالة استخدم قسم "تشغيل تطبيق في نافذة" واختر حزمة تطبيق.

لا يحتاج المشروع Root.
