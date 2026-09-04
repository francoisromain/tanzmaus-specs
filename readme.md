# MFB Tanzmaus specs

> An attempt to document the **MFB Tanzmaus** drum machine specifications

> Disclaimer: this was made with the help of an AI (Big Pickle, free from Opencode). 
> I don't unerstand everything and there might be some errors. 

- [`sysex.md`](sysex.md): Sample Upload SysEx protocol
- [`midi-cc.md`](midi-cc.md): MIDI CC assignments for all voices, extracted from the manual

### `reverse/` reverse-engineering notes 

The Tanzmaus uses a STM32F303 CCT6 chip

- [`firmware.md`](reverse/firmware.md) from the [MFB firmwares](mfb/firmware/)
- [`tool.md`](reverse/tool.md) from the [source code of the MFB sample tool app](mfb/tool/TanzmausSampleTool/) (macOS + Windows) and the [sample-tool manual](mfb/tool/user_manual_sample_tool.pdf)
- [`factory-samples.md`](reverse/factory-samples.md): factory sample specs and slot mapping
- [`tanzmaus-app.md`](reverse/tanzmaus-app.md) from [linuxbender/tanzmaus-app](https://github.com/linuxbender/tanzmaus-app), a web-app to upload samples to the Tanzmaus
- [`tanzmaus-reversing.md`](reverse/tanzmaus-reversing.md) from [Windfisch/tanzmaus-reversing](https://github.com/Windfisch/tanzmaus-reversing), a reverse engineering attempt at the sysex **dump** protocol
- [`sample-rate.md`](reverse/sample-rate.md): sample playback-rate measurements

### `mfb/` official MFB source

A few files from the mfberlin.de website (now offline)

Still available at [archive.org](https://web.archive.org/web/20190825160258/http://mfberlin.de/en/device/mfb-tanzmaus_en/) (click on the midi icon under OS to download the full archive)

Property of MFB Manfred Fricke Berlin ©2015

- [Tanzmaus user manual](mfb/Tanzmaus_en.pdf)
- [source code of the MFB sample tool app](mfb/tool/TanzmausSampleTool/)
- [sample-tool manual](mfb/tool/user_manual_sample_tool.pdf)
- [MFB firmwares](mfb/firmware/)
- [32 factory samples](mfb/factory_samples/)

## Contributions

Contributions are welcome

