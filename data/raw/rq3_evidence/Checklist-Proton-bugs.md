# Checklist Proton bugs

This is a checklist to help you find relevant error messages in your Proton log.

## General guidance

Search the Proton log for the following prefixes to find errors/warnings:
  - ```fixme:```
  - ```err:``` 
  - ```warn:```
  - ```error:```
  
---

## Game won't start at all:

### Steam2.dll
Tracked at https://github.com/ValveSoftware/Proton/issues/2613
- ```warn:module:load_builtin_dll cannot open .so lib for builtin L"Steam2.dll":```

### Valve CEG DRM
Currently Steam for Linux does not generate the custom executable for games using Valve's CEG DRM, this is tracked at https://github.com/ValveSoftware/Proton/issues/753

You can look for `cegpublickey` on `https://steamdb.info/app/<appid>/config/` to check if a game is using this.

---

## Missing cinematic/cutscenes:

Problems with missing cinematics/cutscenes are most likely due to Media Foundation, Quartz or WMVcore issues. 
These are tracked at https://github.com/ValveSoftware/Proton/issues/1464

### Media Foundation
- ```mfplat.dll```
- ```mfplay.dll```
- ```mfreadwrite.dll```
- ```mfstartup.dll```

### Quartz
- ```quartz.dll```
- ```fixme:quartz:MPEGSplitter_QueryInterface```
- ```err:quartz:GetClassMediaFile Media class not found```

### WMVcore
- ```WMVcore.dll```
- ```fixme:wmvcore:WMReader_Open```
- ```fixme:wmvcore:WMCreateSyncReader```

### XNA

- ```Microsoft.Xna.Framework.Video.dll```

---

## Audio playback issues:

### Xaudio2
Xaudio2 issues are labeled "XAudio2" by the moderator.
The Proton log typically includes one of the following:

- ```XAudio2_7.dll```
- ```xaudio2_8.dll```

---

## Other errors:

### .net
.net issues are labeled appropriately by the moderator. 
These include:
- .NET-UE3 (Unreal Engine 3.)
- .NET-winforms (System.Windows.forms toolkit)
- .NET-WPF (PresentationFramework)
- .NET-XNA (Uses XNA framework, implies Xaudio2 and possibly WMP)

---
