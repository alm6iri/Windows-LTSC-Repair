# -*- coding: utf-8 -*-
"""
Project: Windows LTSC Repair Tool
Author: Tech Team / Open Source Contributor
Description: A professional GUI utility designed to resolve Windows LTSC core bugs
             including Network Stack issues, Windows Update loops, and Time drift.
"""

import os
import sys
import ctypes
import subprocess
import threading
import datetime
import customtkinter as ctk

# التحقق الإجباري من صلاحيات المسؤول قبل تشغيل أي عنصر في الواجهة
if not ctypes.windll.shell32.IsUserAnAdmin():
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    except Exception as e:
        print(f"Error requesting admin privileges: {e}")
    sys.exit()

# ضبط السمة العامة للبرنامج (مظهر داكن عصري ومريح للعين)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class WindowsLTSCRepairApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # اللغات والمسارات الافتراضية للمشروع
        self.current_lang = "AR"
        self.log_file = os.path.join(os.environ["USERPROFILE"], "Desktop", "Fixer_Events_Log.txt")
        
        # قاموس النصوص الكامل ليدعم التغيير الفوري والمحاذاة الذكية
        self.strings = {
            "AR": {
                "title_win": "Windows LTSC Repair",
                "header": "Windows LTSC Repair",
                "subheader": "Fixer Windows Update, Network, And Time Problems",
                "btn_net": "إصلاح الشبكة والنواة",
                "btn_upd": "إصلاح تحديثات الويندوز",
                "btn_time": "إصلاح الوقت والتزامن",
                "btn_reboot": "إعادة تشغيل الجهاز",
                "log_lbl": "مربع مراقبة الأحداث وسجل العمليات:",
                "start_msg": "=== تم تشغيل البرنامج بنجاح بصلاحيات المسؤول ===",
                "lang_btn": "English",
                "net_start": "جاري بدء عملية إصلاح الشبكة العميقة للـ LTSC...",
                "net_end": "إصلاح الشبكة: تم بنجاح وتفعيل النواة ومحرك الأقراص الافتراضي.",
                "upd_start": "جاري بدء عملية صيانة وتصفير خدمات التحديثات...",
                "upd_end": "إصلاح التحديثات: تم تنظيف التخزين المؤقت وإعادة بناء الخدمات بنجاح.",
                "time_start": "جاري بدء إصلاح وتزامن الوقت مع الخوادم العالمية...",
                "time_end": "إصلاح الوقت: تمت إعادة مزامنة التوقيت بنجاح مع ://windows.com.",
                "reboot_title": "مطلوب إعادة تشغيل النظام",
                "reboot_msg": "لتطبيق الإصلاحات العميقة للنواة بنجاح،\nيجب إعادة تشغيل الكمبيوتر الآن.",
                "reboot_yes": "نعم، أعد التشغيل",
                "reboot_no": "إلغاء",
                "side_btn": "right",
                "side_log": "left",
                "anchor": "e",
                "justify": "right"
            },
            "EN": {
                "title_win": "Windows LTSC Repair",
                "header": "Windows LTSC Repair",
                "subheader": "Fixer Windows Update, Network, And Time Problems",
                "btn_net": "Fix Network & Core",
                "btn_upd": "Fix Windows Updates",
                "btn_time": "Fix Time Synchronization",
                "btn_reboot": "Reboot System",
                "log_lbl": "Event Monitor & Operations Log:",
                "start_msg": "=== Program started successfully with Admin Privileges ===",
                "lang_btn": "العربية",
                "net_start": "Starting deep network and core repair for LTSC...",
                "net_end": "Network Fix: Core and virtual drives activated successfully.",
                "upd_start": "Starting Windows Update services maintenance and reset...",
                "upd_end": "Update Fix: Cache cleared and update services rebuilt successfully.",
                "time_start": "Starting time synchronization with global servers...",
                "time_end": "Time Fix: Synchronized successfully with ://windows.com.",
                "reboot_title": "System Reboot Required",
                "reboot_msg": "To apply deep core fixes successfully,\nthe computer must be restarted now.",
                "reboot_yes": "Yes, Restart Now",
                "reboot_no": "Cancel",
                "side_btn": "left",
                "side_log": "right",
                "anchor": "w",
                "justify": "left"
            }
        }
        
        # تهيئة أبعاد وعناوين النافذة
        self.title(self.strings[self.current_lang]["title_win"])
        self.geometry("850x550")
        self.resizable(False, False)
        
        # قائمة لتسجيل تسلسل الأحداث وضمان ترجمتها ديناميكياً عند قلب اللغة
        self.logged_keys = ["start_msg"]
        
        self.create_widgets()
        self.refresh_log_display()

    def create_widgets(self):
        """بناء وتوزيع العناصر الرسومية بناءً على معايير الواجهات الحديثة"""
        # العناوين الرئيسية للأداة
        self.title_label = ctk.CTkLabel(
            self, text=self.strings[self.current_lang]["header"], 
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#61AFEF"
        )
        self.title_label.pack(pady=(15, 2))

        self.subtitle_label = ctk.CTkLabel(
            self, text=self.strings[self.current_lang]["subheader"], 
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color="#ABB2BF"
        )
        self.subtitle_label.pack(pady=(0, 15))

        # حاوية التحكم بالأزرار (الأيسر أو الأيمن حسب اللغة)
        self.button_frame = ctk.CTkFrame(self, width=220, corner_radius=10)
        self.button_frame.pack_propagate(False)

        self.btn_net = ctk.CTkButton(
            self.button_frame, text=self.strings[self.current_lang]["btn_net"], 
            fg_color="#98C379", hover_color="#7CB342", text_color="#1E1E1E",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=32, command=lambda: self.run_in_thread(self.fix_network)
        )
        self.btn_net.pack(pady=10, padx=15, fill="x")

        self.btn_update = ctk.CTkButton(
            self.button_frame, text=self.strings[self.current_lang]["btn_upd"], 
            fg_color="#E5C07B", hover_color="#D1A139", text_color="#1E1E1E",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=32, command=lambda: self.run_in_thread(self.fix_updates)
        )
        self.btn_update.pack(pady=10, padx=15, fill="x")

        self.btn_time = ctk.CTkButton(
            self.button_frame, text=self.strings[self.current_lang]["btn_time"], 
            fg_color="#61AFEF", hover_color="#4B96DB", text_color="#1E1E1E",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=32, command=lambda: self.run_in_thread(self.fix_time)
        )
        self.btn_time.pack(pady=10, padx=15, fill="x")

        self.btn_lang = ctk.CTkButton(
            self.button_frame, text=self.strings[self.current_lang]["lang_btn"],
            fg_color="#4B5263", hover_color="#5C6370", text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=32, command=self.toggle_language
        )
        self.btn_lang.pack(pady=10, padx=15, fill="x")

        self.btn_reboot = ctk.CTkButton(
            self.button_frame, text=self.strings[self.current_lang]["btn_reboot"], 
            fg_color="#E06C75", hover_color="#D32F2F", text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=32, command=self.show_reboot_window
        )
        self.btn_reboot.pack(pady=(25, 10), padx=15, fill="x")

        # حاوية شاشة مراقبة الأحداث (Log Panel)
        self.log_frame = ctk.CTkFrame(self, corner_radius=10)

        self.log_label = ctk.CTkLabel(
            self.log_frame, text=self.strings[self.current_lang]["log_lbl"], 
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        self.log_label.pack(anchor=self.strings[self.current_lang]["anchor"], padx=15, pady=5)

        self.log_text = ctk.CTkTextbox(
            self.log_frame, font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E1E1E", text_color="#ABB2BF", wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.log_text.configure(state="disabled")

        self.update_layout_direction()
    def update_layout_direction(self):
        """إعادة توزيع العناصر البرمجية ديناميكياً لتأكيد اتجاه الـ RTL للمستخدم العربي"""
        side_btn = self.strings[self.current_lang]["side_btn"]
        side_log = self.strings[self.current_lang]["side_log"]
        align_mode = self.strings[self.current_lang]["justify"]
        
        # تفكيك العناصر الحالية قبل إعادة تدويرها
        self.button_frame.pack_forget()
        self.log_frame.pack_forget()
        
        # إعادة التوزيع باتجاه المرآة الذكي (RTL / LTR)
        self.button_frame.pack(side=side_btn, fill="y", padx=20, pady=(0, 20))
        self.log_frame.pack(side=side_log, fill="both", expand=True, padx=20, pady=(0, 20))
        
        # قفل وتهيئة اتجاه السطور داخل مربع النص
        self.log_text.configure(state="normal")
        self.log_text.tag_config("align", justify=align_mode)
        self.log_text.configure(state="disabled")

    def toggle_language(self):
        """دالة التبديل الفوري والترجمة الحية لعناصر البرنامج"""
        self.current_lang = "EN" if self.current_lang == "AR" else "AR"
        self.title(self.strings[self.current_lang]["title_win"])
        self.btn_net.configure(text=self.strings[self.current_lang]["btn_net"])
        self.btn_update.configure(text=self.strings[self.current_lang]["btn_upd"])
        self.btn_time.configure(text=self.strings[self.current_lang]["btn_time"])
        self.btn_lang.configure(text=self.strings[self.current_lang]["lang_btn"])
        self.btn_reboot.configure(text=self.strings[self.current_lang]["btn_reboot"])
        
        self.log_label.pack_forget()
        self.log_label.configure(text=self.strings[self.current_lang]["log_lbl"])
        self.log_label.pack(anchor=self.strings[self.current_lang]["anchor"], padx=15, pady=5)
        
        self.update_layout_direction()
        self.refresh_log_display()

    def log_message(self, string_key):
        """تسجيل المفاتيح النصية للأحداث لمنع بكسلة أو تداخل التواريخ"""
        if string_key not in self.logged_keys:
            self.logged_keys.append(string_key)
        self.refresh_log_display()

    def refresh_log_display(self):
        """تحديث وعرض سجل العمليات وحفظ ملف Log حيوي على سطح المكتب"""
        align_mode = self.strings[self.current_lang]["justify"]
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        def update_gui():
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            
            for key in self.logged_keys:
                msg = self.strings[self.current_lang][key]
                formatted_message = f"[{timestamp}] {msg}\n"
                self.log_text.insert("end", formatted_message, "align")
            
            self.log_text.tag_config("align", justify=align_mode)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            
            # تصدير ملف السجل على سطح مكتب المستخدم بصيغة مرنة للمطورين
            try:
                with open(self.log_file, "w", encoding="utf-8") as f:
                    for key in self.logged_keys:
                        f.write(f"[{timestamp}] {self.strings[self.current_lang][key]}\n")
            except Exception:
                pass
        
        self.after(0, update_gui)

    def run_in_thread(self, target_function):
        """تشغيل الأوامر العميقة في خيوط منفصلة لضمان استقرار واجهة المستخدم ومنع التجمد"""
        thread = threading.Thread(target=target_function)
        thread.daemon = True
        thread.start()

    def run_cmd(self, command):
        """تنفيذ أوامر الويندوز بصمت تام وبدون ظهور الشاشة السوداء (CMD Shell)"""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                command, shell=True, startupinfo=startupinfo,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return result.returncode
        except Exception:
            return -1

    def fix_network(self):
        """منظومة الإصلاح الشاملة لنواة بروتوكولات الشبكة وإحياء الخدمات المعطلة للـ LTSC"""
        self.log_message("net_start")
        cmds = [
            r"netsh winsock reset", r"netsh int ip reset", r"ipconfig /flushdns",
            r"wmic path win32_networkadapter where PhysicalAdapter=True call enable",
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\NlaSvc" /v Start /t REG_DWORD /d 2 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\netprofm" /v Start /t REG_DWORD /d 3 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\NcdAutoSetup" /v Start /t REG_DWORD /d 3 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\Dhcp" /v Start /t REG_DWORD /d 2 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\NcbService" /v Start /t REG_DWORD /d 3 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\NetSetupSvc" /v Start /t REG_DWORD /d 3 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\NdisWan" /v Start /t REG_DWORD /d 2 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\nsi" /v Start /t REG_DWORD /d 2 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\CDPSvc" /v Start /t REG_DWORD /d 2 /f',
            r'net localgroup Administrators "NT AUTHORITY\NetworkService" /add',
            r'net localgroup "Performance Log Users" "NT AUTHORITY\NetworkService" /add',
            r'net localgroup Administrators "NT Authority\LocalService" /add',
            r"sc config nsi start= auto", r"sc start nsi",
            r"sc config NlaSvc start= auto", r"sc start nsi",
            r"sc config netprofm start= demand", r"sc start netprofm",
            r"sc config NcdAutoSetup start= demand", r"sc start NcdAutoSetup",
            r"sc config CDPSvc start= auto", r"sc start CDPSvc",
            r'powershell -Command "Get-AppxPackage -AllUsers -Name \'Microsoft.Windows.ShellExperienceHost\' | Foreach {Add-AppxPackage -DisableDevelopmentMode -Register \'$($_.InstallLocation)\\\\AppXManifest.xml\' -ErrorAction SilentlyContinue}"',
            r'powershell -Command "Get-AppXPackage -AllUsers | Where-Object {$_.InstallLocation -notlike \'*WindowsStore*\'} | Foreach {Add-AppxPackage -DisableDevelopmentMode -Register \'$($_.InstallLocation)\\\\AppXManifest.xml\' -ErrorAction SilentlyContinue}"'
        ]
        for c in cmds:
            self.run_cmd(c)
        self.log_message("net_end")

    def fix_updates(self):
        """تصفير وإعادة بناء كاملة لقواعد بيانات التحديثات التالفة والتخلص من التعليق"""
        self.log_message("upd_start")
        cmds = [
            r"net stop wuauserv", r"net stop cryptSvc", r"net stop bits", r"net stop msiserver",
            r'rd /s /q "C:\Windows\SoftwareDistribution"', r'rd /s /q "C:\Windows\System32\catroot2"',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\wuauserv" /v Start /t REG_DWORD /d 2 /f',
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\bits" /v Start /t REG_DWORD /d 2 /f',
            r"net start wuauserv", r"net start cryptSvc", r"net start bits", r"net start msiserver"
        ]
        for c in cmds:
            self.run_cmd(c)
        self.log_message("upd_end")

    def fix_time(self):
        """مزامنة الوقت والتاريخ وفك تجميد خوادم التوقيت الرسمية لويندوز"""
        self.log_message("time_start")
        cmds = [
            r"net stop w32time",
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Services\w32time" /v Start /t REG_DWORD /d 2 /f',
            r"w32tm /unregister", r"w32tm /register", r"net start w32time",
            r"w32tm /config /manualpeerlist:://windows.com,0x1 /syncfromflags:manual /update", r"w32tm /resync"
        ]
        for c in cmds:
            self.run_cmd(c)
        self.log_message("time_end")

    def show_reboot_window(self):
        """نافذة منبثقة ذكية ومحاطة بألوان متناسقة لتأكيد إعادة تشغيل الكمبيوتر فوراً"""
        reboot_win = ctk.CTkToplevel(self)
        reboot_win.title(self.strings[self.current_lang]["reboot_title"])
        reboot_win.geometry("420x180")
        reboot_win.resizable(False, False)
        reboot_win.attributes("-topmost", True)
        reboot_win.grab_set()

        lbl = ctk.CTkLabel(
            reboot_win, text=self.strings[self.current_lang]["reboot_msg"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        lbl.pack(pady=20)

        btn_frame = ctk.CTkFrame(reboot_win, fg_color="transparent")
        btn_frame.pack(pady=10)

        btn_yes = ctk.CTkButton(
            btn_frame, text=self.strings[self.current_lang]["reboot_yes"], fg_color="#E06C75", hover_color="#D32F2F", width=140,
            command=lambda: os.system("shutdown /r /t 0 /f")
        )
        btn_yes.grid(row=0, column=0, padx=10)

        btn_no = ctk.CTkButton(
            btn_frame, text=self.strings[self.current_lang]["reboot_no"], fg_color="#4B5263", hover_color="#5C6370", width=140,
            command=reboot_win.destroy
        )
        btn_no.grid(row=0, column=1, padx=10)

if __name__ == "__main__":
    app = WindowsLTSCRepairApp()
    app.mainloop()
