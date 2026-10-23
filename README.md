<div align="center">

# OnePlus 📦 SukiSU Ultra Kernels

### Prebuilt AnyKernel3 kernels for OnePlus A14, A15 and A16

*Automated builds with **SukiSU built in**, plus KPM and SUSFS enabled in the standard configurations.*

[![Latest Release](https://img.shields.io/github/v/release/cyzrqh/6666?style=for-the-badge&logo=github&label=Latest%20Release&color=6C4AB6)](https://github.com/cyzrqh/6666/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/cyzrqh/6666/total?style=for-the-badge&logo=icloud&logoColor=white&label=Downloads&color=2E8B57)](https://github.com/cyzrqh/6666/releases)
[![Build](https://img.shields.io/github/actions/workflow/status/cyzrqh/6666/build-kernel-release.yml?style=for-the-badge&logo=githubactions&logoColor=white&label=Build)](https://github.com/cyzrqh/6666/actions)
[![Stars](https://img.shields.io/github/stars/cyzrqh/6666?style=for-the-badge&logo=github&color=E3B341)](https://github.com/cyzrqh/6666/stargazers)

**Based on [WildKernels/OnePlus_KernelSU_SUSFS](https://github.com/WildKernels/OnePlus_KernelSU_SUSFS)**

</div>

> [!WARNING]
> A custom kernel can disable hardware key-attestation, so **Google Wallet** tap-to-pay, Play Integrity **STRONG**, and some banking apps may stop working. Unlocking the bootloader **wipes your data**. Back up your stock `boot.img` first. Flash at your own risk.

---

## ✅ Standard build defaults

Features are selected when the kernel is built. Every checked-in A14, A15 and A16 configuration currently uses these defaults:

| Component | Standard default | Notes |
|---|---:|---|
| **SukiSU Ultra** | **Built in** | Kernel-level root is part of the kernel image. |
| **KPM** | **Enabled** | KPM support is compiled into the kernel. |
| **SUSFS** | **Enabled** | SUSFS support is compiled into the kernel. |
| **NoMount / NMS** | **Disabled** | The NoMount patch stack is not applied by the standard configurations. |
| **BBG** | **Disabled** | BBG is not compiled in by the standard configurations. |

> [!IMPORTANT]
> The AnyKernel3 (AK3) installer has **no volume-key feature selection**. It flashes the already-built kernel image and does not enable optional features during installation. In particular, NoMount/NMS and BBG remain disabled unless they were explicitly enabled at build time.

Other feature flags can vary by device and kernel base. Check the matching JSON file under `configs/` for the exact build-time selection.

---

## 📱 Supported releases and configuration count

This repository supports OnePlus **A14, A15 and A16** targets. The current inventory contains **159 configurations**:

| Target release | Configuration directory | Count |
|---|---|---:|
| **A14** | `configs/a14/` | **13** |
| **A15** | `configs/a15/` | **74** |
| **A16** | `configs/a16/` | **72** |

The release target, device model, kernel version and source branch must all match your phone. See [compatibility.md](compatibility.md) and the [latest release](https://github.com/cyzrqh/6666/releases/latest) before flashing.

---

## Installation

**Prerequisites:** an unlocked bootloader, a backed-up stock `boot.img`, and [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher/releases) or another compatible kernel flashing tool.

1. Open the [latest release](https://github.com/cyzrqh/6666/releases/latest).
2. Download the `AK3_…zip` that matches your exact device, A14/A15/A16 release and kernel base.
3. Flash the ZIP with Kernel Flasher or SukiSU Manager.
4. Reboot, then use the compatible SukiSU Manager version shown in the release notes.

The standard kernel ZIP already contains SukiSU, KPM and SUSFS support. NoMount/NMS and BBG are not enabled by default, and the AK3 installer does not offer a volume-key menu to turn them on.

---

## Updating and removing

- **Update** — flash a newer ZIP that still matches the same device, target release and kernel base.
- **After a major OTA** — do not reuse the previous kernel ZIP; wait for and flash a matching A14, A15 or A16 build.
- **Remove** — restore the stock boot image or take a compatible OTA that restores the stock kernel.

---

## FAQ

**Can I choose KPM, SUSFS, NoMount/NMS or BBG with the volume keys while flashing?** No. AK3 is non-interactive and contains no volume-key feature selector. KPM and SUSFS are already enabled in the standard image; NoMount/NMS and BBG are not.

**Can the installer enable a feature that was not built into the image?** No. Feature selection happens at build time. To change a build-time flag, use a custom configuration and build a new kernel ZIP.

**Will a custom kernel preserve Play Integrity STRONG or banking compatibility?** Not necessarily. A custom kernel cannot restore hardware key-attestation, and app behavior varies. Keep a stock boot image available for recovery and testing.

---

## Building it yourself

Via GitHub Actions:

```text
Actions → Build and Release OnePlus Kernels → Run workflow
```

SukiSU is the built-in root option:

```json
[{"type":"SUKISU","hash":"b20dee702035af09cb2ecb5f35443bbc1747f3e6"}]
```

This is the verified SukiSU `builtin` commit used with the pinned SUSFS revisions. SukiSU's build number follows the official `main` history rather than the branch-local count (which incorrectly appeared as 37987). An explicit ref can still be supplied for testing.

The standard configuration flags are:

```json
{
  "susfs": true,
  "kpm": true,
  "NMS": false,
  "bbg": false
}
```

These values are baked into the kernel image. The generated AK3 ZIP does not ask for volume-key choices and does not override them while flashing.

> **First run:** enable **Force toolchain sync before build** (auto-on for releases) — required once to populate the toolchain cache.

---

## 🔄 Syncing updates from the parent repository

### 手动同步上游（保留定制功能）

打开 [同步上游工作流](https://github.com/cyzrqh/6666/actions/workflows/sync-upstream.yml)，点击 **Run workflow**，选择 **NoMount** 分支，再点绿色的 **Run workflow**。

运行成功后，流程会直接更新 `NoMount`，不需要创建或合并 PR，也不需要额外填写 Token。重新打开仓库主页即可查看同步结果；重复运行时，如果没有新提交，会显示已经同步。

同步时保留本仓库的 KPM/SUSFS 默认开启、BBG/NoMount 默认关闭，以及 AK3 无音量键选择的刷写行为。上游文件使用 LF 或 CRLF 换行都可以；真实的未解决代码冲突和验证错误仍会停止发布，不会用“成功”掩盖失败。

**仓库主页的 Sync fork 是 GitHub 自带功能，不会调用本工作流的冲突处理。** 当上游和本仓库修改了相同内容时，它仍可能提示冲突；这不是权限不足。保留这些定制功能时，请使用上面的手动入口，不要点击 **Discard commits**，那会丢弃本仓库改动。

Use the guarded manual workflow:

```text
Actions → Sync upstream NoMount → Run workflow
```

After validation succeeds, the workflow directly fast-forwards `NoMount` to a merge commit containing both histories. No pull request, extra token, force push, or repository permission change is required. A concurrent branch update is rejected; rerun against the new base.

Ordinary A14/A15/A16 configuration conflicts are normalized back to this fork's standard KPM/SUSFS/BBG/NoMount policy. Known overlaps in the build workflow and README keep this fork's reviewed behavior while accepting upstream-only additions. Any conflict outside that narrow allowlist stops the sync and lists the affected files, so local compatibility and non-interactive AK3 protections are not silently overwritten.

The native GitHub **Sync fork** button cannot resolve genuine conflicts or run this workflow's policy. Use this workflow for customized builds. Do not discard the fork's commits to make the button available.

---

## 🔗 Links

- [SukiSU Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra) · [SukiSU Manager releases](https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases)
- [NoMount Suite](https://github.com/Bouteillepleine/NoMount-Suite) — optional integration; disabled in the standard configurations
- [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher)
- [Releases](https://github.com/cyzrqh/6666/releases)

---

## Donations

Appreciated, never expected.

- PayPal: [paypal.me/fatalcoder524](https://paypal.me/fatalcoder524)
- DM on Telegram for UPI donations!

## Acknowledgments

- **[NoMount Suite](https://github.com/Bouteillepleine/NoMount-Suite)** &amp; all contributors — optional NoMount integration (built on **[maxsteeel/nomount](https://github.com/maxsteeel/nomount)**)
- **SukiSU Ultra** — the root solution
- **AnyKernel3** by osm0sis and contributors
- **[WildKernels/OnePlus_KernelSU_SUSFS](https://github.com/WildKernels/OnePlus_KernelSU_SUSFS)** — the excellent OnePlus build framework this is forked from
- **[inforcqb/susfs4ksu-lkm](https://github.com/inforcqb/susfs4ksu-lkm)** — SUSFS as a loadable module, which is what each kernel here carries
- **OnePlusOSS** — kernel source
- Community testers and contributors
---

## License

[GPL-2.0](LICENSE), the same license as the kernel this builds.

Kernel source comes from **OnePlusOSS** (GPL-2.0); the build framework is forked from
**[WildKernels/OnePlus_KernelSU_SUSFS](https://github.com/WildKernels/OnePlus_KernelSU_SUSFS)**.
The optional **NoMount Suite** integration is a separate project and is disabled by default. See [NoMount Suite](https://github.com/Bouteillepleine/NoMount-Suite) for its own license.
