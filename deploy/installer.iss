; FabBot 4.4.1 Windows 安装器 (Inno Setup 6.x)
; 前置: 先运行 deploy\desktop-package.ps1 -Version 4.4.1 生成 dist\FabBot-4.4.1
;   布局: 根目录 = C# 壳发布产物 (FabBot.exe 等), backend\FabBotBackend\ = PyInstaller sidecar
; 编译: iscc deploy\installer.iss  ->  dist\Setup-FabBot-4.4.1.exe
; 注意: 壳为 net8.0-windows 框架依赖发布, 目标机另需 .NET 8 Desktop Runtime

#define MyAppName "FabBot"
#define MyAppVersion "4.4.1"
#define MyAppExeName "FabBot.exe"
#define PackageDir "..\dist\FabBot-" + MyAppVersion

[Setup]
; 固定 AppId: 升级安装沿用同一 GUID, 勿随版本改动
AppId={{6C2E9A44-7B3D-4F5E-9A1C-D58E0F2B3A47}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\FabBot
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\dist
OutputBaseFilename=Setup-FabBot-{#MyAppVersion}
SetupIconFile=..\desktop\shell\Assets\fabbot.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; 递归打包组装目录; FabBotData 是运行时用户数据 (打包冒烟检查也会生成), 不入安装包
Source: "{#PackageDir}\*"; DestDir: "{app}"; Excludes: "FabBotData"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; 用户数据目录 (backend_runner 运行时落位 config.yaml / data / knowledge / ui_dist)
; uninsneveruninstall: 卸载时永不删除, 保留用户数据
Name: "{app}\backend\FabBotBackend\FabBotData"; Flags: uninsneveruninstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 安装完成后可选立即启动
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2ClientKey = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2ClientKeyWow = 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

// 读取 EdgeUpdate 客户端 pv 值; 空串或 0.0.0.0 视为未安装
function HasWebView2PV(RootKey: Integer; const SubKey: String): Boolean;
var
  PV: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', PV) and (PV <> '') and (PV <> '0.0.0.0');
end;

function IsWebView2Installed: Boolean;
begin
  // 按机器 (64/32 位注册表视图) + 按用户, 任一命中即已安装
  Result := HasWebView2PV(HKLM, WebView2ClientKey)
    or HasWebView2PV(HKLM, WebView2ClientKeyWow)
    or HasWebView2PV(HKCU, WebView2ClientKey);
end;

function InitializeSetup(): Boolean;
var
  Msg: String;
begin
  Result := True;
  if not IsWebView2Installed then
  begin
    Msg := '未检测到 Microsoft Edge WebView2 运行时, FabBot 桌面界面依赖它。'#13#10#13#10 +
      '建议先下载并安装 Evergreen Bootstrapper:'#13#10 +
      'https://go.microsoft.com/fwlink/p/?LinkId=2124703'#13#10#13#10 +
      '是否仍要继续安装? (选"否"退出安装器)';
    Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  // 卸载只移除安装时记录的文件; FabBotData 已标 uninsneveruninstall, 不会被删除。
  // 卸载完成后确认用户数据仍在, 并告知保留位置。
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{app}\backend\FabBotBackend\FabBotData');
    if DirExists(DataDir) then
      MsgBox('用户数据 (配置 / 知识库 / 会话库) 已保留在:'#13#10 + DataDir +
        #13#10#13#10 + '如需彻底清除, 请手动删除该目录。', mbInformation, MB_OK);
  end;
end;