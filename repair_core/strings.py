# -*- coding: utf-8 -*-
"""Complete AR/EN localization table.

Invariants enforced by unit tests:
* AR and EN dictionaries expose the exact same key set (no missing
  translations can ever ship).
* Placeholders are positional ({0}, {1}) and rendered with str.format.
"""

STRINGS = {
    "AR": {
        # ---- window / chrome -------------------------------------------------
        "title_win": "Windows Repair Tool",
        "header": "Windows LTSC Repair",
        "subheader": "إصلاح أعطال الشبكة والتحديثات والوقت وملفات النظام والقرص",
        "sys_lbl": "النظام المستهدف: {0}",
        "status_ready": "الحالة: جاهز",
        "status_busy": "الحالة: جارٍ تنفيذ عملية… يرجى الانتظار",
        "log_lbl": "مربع مراقبة الأحداث وسجل العمليات:",
        # ---- buttons -----------------------------------------------------------
        "btn_net": "إصلاح الشبكة والنواة",
        "btn_upd": "إصلاح تحديثات الويندوز",
        "btn_time": "إصلاح الوقت والتزامن",
        "btn_sys": "إصلاح ملفات النظام (SFC/DISM)",
        "btn_disk": "فحص صحة القرص (CHKDSK)",
        "btn_reboot": "إعادة تشغيل الجهاز",
        "lang_btn": "English",
        # ---- operation lifecycle ------------------------------------------------
        "start_msg": "=== تم تشغيل البرنامج بنجاح بصلاحيات المسؤول ===",
        "net_start": "جارٍ بدء عملية إصلاح الشبكة العميقة…",
        "net_end": "إصلاح الشبكة: اكتمل بنجاح. ملاحظة: يتطلب تطبيقاً كاملاً إعادة تشغيل النظام.",
        "upd_start": "جارٍ بدء عملية صيانة وتصفير خدمات التحديثات…",
        "upd_end": "إصلاح التحديثات: تمت أرشفة قواعد البيانات التالفة وإعادة بناء الخدمات بنجاح.",
        "time_start": "جارٍ بدء إصلاح وتزامن الوقت مع الخوادم العالمية…",
        "time_end": "إصلاح الوقت: اكتملت العملية.",
        "sys_start": "جارٍ بدء الفحص والإصلاح العميق لملفات النظام…",
        "sys_end": "إصلاح ملفات النظام: اكتملت العملية.",
        "disk_start": "جارٍ بدء فحص صحة القرص والتحقق من نظام الملفات…",
        "disk_end": "فحص القرص: اكتملت العملية.",
        "reboot_required_note": "ملاحظة: هذه الإصلاحات تتطلب إعادة تشغيل النظام لتطبيقها بالكامل.",
        # ---- network module --------------------------------------------------
        "net_winsock": "تصفير مكدس Winsock…",
        "net_ip_reset": "تصفير مكدس IPv4/IPv6…",
        "net_flushdns": "مسح ذاكرة DNS المؤقتة…",
        "adapters_probe_failed": "تعذر تفعيل بطاقات الشبكة (PowerShell وWMIC غير متاحين).",
        "service_missing": "تم تخطي الخدمة غير الموجودة في هذا الإصدار: {0}",
        "appx_register": "إعادة تسجيل حزمة واجهة النظام (ShellExperienceHost)…",
        "appx_skip": "تم تخطي إعادة تسجيل AppX (غير متوفرة في هذا الإصدار مثل LTSC).",
        # ---- update module -----------------------------------------------------
        "upd_stopping": "إيقاف سلسلة خدمات التحديث مع التحقق من توقفها الفعلي…",
        "dir_missing": "المجلد غير موجود (سيعيد النظام إنشاءه تلقائياً): {0}",
        "dir_archived": "تمت أرشفة المجلد القديم إلى: {0}",
        "dir_archive_failed": "تعذر أرشفة المجلد (قد يكون مقفلاً) وسيتم تخطيه بأمان: {0}",
        "upd_starting": "إعادة تشغيل سلسلة خدمات التحديث…",
        "upd_rebuilt": "تمت استعادة أوضاع الخدمات الافتراضية بنجاح.",
        # ---- time module ---------------------------------------------------------
        "time_stopping": "إيقاف خدمة الوقت وإعادة ضبط نوع التشغيل…",
        "time_reregister": "إعادة تسجيل خدمة w32time لدى النظام…",
        "time_service_failed": "تعذر تشغيل خدمة الوقت - تحقق من اعتماديات الخدمة.",
        "time_config": "ضبط خوادم التوقيت الرسمية (time.windows.com + time.nist.gov)…",
        "time_resynced": "تمت مزامنة الوقت بنجاح مع {0}.",
        "time_resync_failed": "فشلت المزامنة بعد عدة محاولات - تحقق من الاتصال بالإنترنت.",
        # ---- system module --------------------------------------------------------
        "dism_start": "بدء إصلاح مخزن مكونات النظام (DISM /RestoreHealth)… قد يستغرق عدة دقائق.",
        "dism_ok": "DISM: تم إصلاح مخزن المكونات بنجاح.",
        "dism_failed": "DISM: انتهى برمز {0} - سيُستأنف الفحص عبر SFC على أي حال.",
        "dism_missing": "لم يتم العثور على Dism.exe في مجلد النظام.",
        "sfc_start": "بدء فحص وفحص سلامة ملفات النظام (sfc /scannow)… قد يستغرق وقتاً.",
        "sfc_ok": "SFC: لم يتم العثور على أي انتهاكات لسلامة ملفات النظام.",
        "sfc_fixed": "SFC: تم العثور على ملفات تالفة وإصلاحها بنجاح.",
        "sfc_partial": "SFC: توجد ملفات تالفة تعذر إصلاحها - راجع سجل CBS.log.",
        "sfc_unknown": "SFC: انتهى الفحص (راجع المخرجات أدناه).",
        # ---- disk module ------------------------------------------------------
        "sys_drive": "القرص النظام المستهدف: {0}",
        "disk_smart": "قراءة حالة صحة الأقراص الفيزيائية (SMART)…",
        "disk_smart_na": "تعذر قراءة بيانات SMART (شائع في الأجهزة الافتراضية) - سيُستأنف فحص CHKDSK.",
        "disk_scan_start": "بدء الفحص الفوري الآمن للقرص النظام (chkdsk /scan) - بدون فصل أو إعادة تشغيل…",
        "disk_ok": "CHKDSK: لم يتم العثور على أي أخطاء في نظام الملفات.",
        "disk_fixed": "CHKDSK: تم العثور على أخطاء وإصلاحها.",
        "disk_errors": "CHKDSK: تم العثور على أخطاء لم تُصلح عبر الفحص الفوري.",
        "disk_scheduled": "تمت جدولة إصلاح كامل للقرص {0} عند إعادة تشغيل النظام.",
        "disk_failed": "تعذر تنفيذ/جدولة فحص القرص (رمز {0}).",
        # ---- runner / infra --------------------------------------------------------
        "cmd_timeout": "انتهت المهلة الزمنية للأمر بعد {1} ثانية: {0}",
        "cmd_missing": "تعذر تشغيل الأمر (غير موجود أو محظور): {0}",
        "cmd_failed": "فشل الأمر (رمز {0}): {1}",
        "service_stop_timeout": "تعذر إيقاف الخدمة خلال المهلة: {0}",
        "service_start_failed": "تعذر تشغيل الخدمة (قد تكون من النوع اليدوي بلا مهام): {0}",
        # ---- reboot dialog -----------------------------------------------------------
        "reboot_title": "مطلوب إعادة تشغيل النظام",
        "reboot_msg": "لتطبيق الإصلاحات العميقة بنجاح،\nيجب إعادة تشغيل الكمبيوتر الآن.",
        "reboot_yes": "نعم، أعد التشغيل",
        "reboot_no": "إلغاء",
        # ---- fatal errors -------------------------------------------------------------
        "err_admin_title": "صلاحيات غير كافية",
        "err_admin_msg": "تم رفض طلب صلاحيات المسؤول.\nأعد تشغيل الأداة ووافق على نافذة UAC.",
        "err_unsupported_title": "نظام غير مدعوم",
        "err_unsupported_msg": "هذه الأداة مخصصة لأنظمة Windows 10/11 فقط.",
        "err_generic": "حدث خطأ غير متوقع: {0}",
        # ---- layout direction -----------------------------------------------------------
        "side_btn": "right",
        "side_log": "left",
        "anchor": "e",
        "justify": "right",
    },

    "EN": {
        # ---- window / chrome -------------------------------------------------
        "title_win": "Windows Repair Tool",
        "header": "Windows LTSC Repair",
        "subheader": "Fixer for Network, Windows Update, Time, System Files and Disk Health",
        "sys_lbl": "Target system: {0}",
        "status_ready": "Status: Ready",
        "status_busy": "Status: Operation in progress… please wait",
        "log_lbl": "Event Monitor & Operations Log:",
        # ---- buttons -----------------------------------------------------------
        "btn_net": "Fix Network & Core",
        "btn_upd": "Fix Windows Updates",
        "btn_time": "Fix Time Synchronization",
        "btn_sys": "Repair System Files (SFC/DISM)",
        "btn_disk": "Check Disk Health (CHKDSK)",
        "btn_reboot": "Reboot System",
        "lang_btn": "العربية",
        # ---- operation lifecycle ------------------------------------------------
        "start_msg": "=== Program started successfully with Admin privileges ===",
        "net_start": "Starting deep network stack repair…",
        "net_end": "Network fix completed. Note: a system reboot is required to fully apply it.",
        "upd_start": "Starting Windows Update maintenance and reset…",
        "upd_end": "Update fix: corrupt databases archived and services rebuilt successfully.",
        "time_start": "Starting time synchronization with global servers…",
        "time_end": "Time fix: operation completed.",
        "sys_start": "Starting deep system file verification and repair…",
        "sys_end": "System file repair: operation completed.",
        "disk_start": "Starting disk health and file system verification…",
        "disk_end": "Disk check: operation completed.",
        "reboot_required_note": "Note: these fixes require a system reboot to fully apply.",
        # ---- network module --------------------------------------------------
        "net_winsock": "Resetting the Winsock catalog…",
        "net_ip_reset": "Resetting the IPv4/IPv6 stack…",
        "net_flushdns": "Flushing the DNS resolver cache…",
        "adapters_probe_failed": "Could not re-enable network adapters (PowerShell and WMIC unavailable).",
        "service_missing": "Skipped service not present on this edition: {0}",
        "appx_register": "Re-registering the Shell Experience Host package…",
        "appx_skip": "Skipped AppX re-registration (not present on this edition, e.g. LTSC).",
        # ---- update module -----------------------------------------------------
        "upd_stopping": "Stopping the update service chain with verified waits…",
        "dir_missing": "Directory not found (Windows will recreate it): {0}",
        "dir_archived": "Archived old directory to: {0}",
        "dir_archive_failed": "Could not archive directory (possibly locked) - safely skipped: {0}",
        "upd_starting": "Restarting the update service chain…",
        "upd_rebuilt": "Default service start modes restored successfully.",
        # ---- time module ---------------------------------------------------------
        "time_stopping": "Stopping the time service and restoring its start type…",
        "time_reregister": "Re-registering the w32time service…",
        "time_service_failed": "Could not start the time service - check its dependencies.",
        "time_config": "Configuring official time servers (time.windows.com + time.nist.gov)…",
        "time_resynced": "Time synchronized successfully with {0}.",
        "time_resync_failed": "Resync failed after several attempts - check your Internet connection.",
        # ---- system module --------------------------------------------------------
        "dism_start": "Starting component store repair (DISM /RestoreHealth)… this may take several minutes.",
        "dism_ok": "DISM: component store repaired successfully.",
        "dism_failed": "DISM: exited with code {0} - continuing with SFC anyway.",
        "dism_missing": "Dism.exe was not found in the system directory.",
        "sfc_start": "Starting system file integrity scan (sfc /scannow)… this may take a while.",
        "sfc_ok": "SFC: no integrity violations were found.",
        "sfc_fixed": "SFC: corrupt files were found and successfully repaired.",
        "sfc_partial": "SFC: some corrupt files could not be fixed - see CBS.log.",
        "sfc_unknown": "SFC: scan finished (see output below).",
        # ---- disk module ------------------------------------------------------
        "sys_drive": "Target system volume: {0}",
        "disk_smart": "Reading physical disk health (SMART)…",
        "disk_smart_na": "SMART data unavailable (common on virtual machines) - continuing with CHKDSK.",
        "disk_scan_start": "Starting safe online verification of the system volume (chkdsk /scan) - no dismount, no reboot…",
        "disk_ok": "CHKDSK: no file system errors were found.",
        "disk_fixed": "CHKDSK: errors were found and repaired.",
        "disk_errors": "CHKDSK: errors were found that the online scan could not repair.",
        "disk_scheduled": "A full repair of volume {0} has been scheduled for the next reboot.",
        "disk_failed": "Could not run/schedule the disk check (code {0}).",
        # ---- runner / infra --------------------------------------------------------
        "cmd_timeout": "Command timed out after {1}s: {0}",
        "cmd_missing": "Could not launch command (missing or blocked): {0}",
        "cmd_failed": "Command failed (code {0}): {1}",
        "service_stop_timeout": "Service could not be stopped in time: {0}",
        "service_start_failed": "Service could not be started (may be on-demand with no tasks): {0}",
        # ---- reboot dialog -----------------------------------------------------------
        "reboot_title": "System Reboot Required",
        "reboot_msg": "To apply the deep core fixes successfully,\nthe computer must be restarted now.",
        "reboot_yes": "Yes, Restart Now",
        "reboot_no": "Cancel",
        # ---- fatal errors -------------------------------------------------------------
        "err_admin_title": "Insufficient privileges",
        "err_admin_msg": "The UAC elevation request was declined.\nRe-run the tool and accept the UAC prompt.",
        "err_unsupported_title": "Unsupported OS",
        "err_unsupported_msg": "This tool is designed for Windows 10/11 only.",
        "err_generic": "Unexpected error: {0}",
        # ---- layout direction -----------------------------------------------------------
        "side_btn": "left",
        "side_log": "right",
        "anchor": "w",
        "justify": "left",
    },
}



def for_lang(lang):
    """Return the table for a language code (defaults to EN)."""
    return STRINGS.get(lang, STRINGS["EN"])


def render(strings, key, params=()):
    """Format an entry safely; unknown keys fall back to the key itself so
    a missing translation can never crash the GUI."""
    template = strings.get(key, key)
    try:
        return template.format(*params)
    except (IndexError, KeyError, ValueError):
        return template

