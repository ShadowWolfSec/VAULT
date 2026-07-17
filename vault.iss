; ══════════════════════════════════════════════════════════
;  VAULT — Inno Setup Script
;  م.رشيد منصور الراجحي
; ══════════════════════════════════════════════════════════

#define AppName      "VAULT"
#define AppVersion   "1.0.0"
#define AppPublisher "م.رشيد منصور الراجحي"
#define AppURL       ""
#define AppExeName   "VAULT.exe"
#define AppDataDir   "{localappdata}\VAULT"

[Setup]
; معلومات التطبيق
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}

; مجلد التثبيت
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; لا يحتاج Admin — يُثبَّت للمستخدم الحالي فقط
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; ملف الإخراج
OutputDir=Output
OutputBaseFilename=VAULT_Setup
SetupIconFile=vault.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=no

; لغة وبيانات
ShowLanguageDialog=no

; خيارات إضافية
AlwaysShowComponentsList=no
DisableWelcomePage=no
DisableReadyPage=no
AllowNoIcons=yes

; معلومات الإصدار في EXE
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} - خزنة كلمات المرور الآمنة
VersionInfoProductName={#AppName}

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "إنشاء اختصار على سطح المكتب";    GroupDescription: "اختصارات إضافية:"; Flags: unchecked
Name: "startupicon";    Description: "تشغيل VAULT عند بدء Windows";     GroupDescription: "اختصارات إضافية:"; Flags: unchecked

[Files]
; ملف EXE الرئيسي
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; أيقونة (اختياري)
Source: "vault.ico"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; قائمة Start
Name: "{group}\{#AppName}";              Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\vault.ico"
Name: "{group}\إلغاء تثبيت {#AppName}"; Filename: "{uninstallexe}"

; سطح المكتب (اختياري)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\vault.ico"; Tasks: desktopicon

[Run]
; تشغيل التطبيق بعد التثبيت
Filename: "{app}\{#AppExeName}"; Description: "تشغيل {#AppName} الآن"; Flags: nowait postinstall skipifsilent

[Registry]
; تسجيل التطبيق للتشغيل عند بدء Windows (اختياري)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[UninstallDelete]
; عند إلغاء التثبيت — نحذف ملفات EXE فقط ونترك بيانات المستخدم
Type: filesandordirs; Name: "{app}"

[Code]
// ── رسالة إلغاء التثبيت ────────────────────────────────
function InitializeUninstall(): Boolean;
var
  DataPath: String;
begin
  DataPath := ExpandConstant('{localappdata}\VAULT');
  if DirExists(DataPath) then
  begin
    if MsgBox(
      'هل تريد حذف بيانات الخزنة (vault.dat والنسخ الاحتياطية)؟' + #13#10 +
      'المسار: ' + DataPath + #13#10 + #13#10 +
      'اختر "لا" للاحتفاظ بالبيانات.',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(DataPath, True, True, True);
    end;
  end;
  Result := True;
end;
