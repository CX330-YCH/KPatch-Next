# KernelPatch compatibility backports

This fork keeps KPatch-Next's arm64, root-manager-independent KPM runtime. It is
based on KPatch-Next `456744b29efb9989445463ab29e368fa59a103c4` and reviews upstream
KernelPatch through `d4c88d6672687456b299e4b5153c24dc979d789b` (2026-10-29).
It is **not a full merge of KernelPatch 0.13.9**. Runtime version remains 0.13.5;
revision 3 identifies this compatibility update, with the exact Git commit in
build manifests.

## Included upstream changes

| Upstream commit | Change |
| --- | --- |
| `5910dcac0260c7451c2c5ce42b5ade6a7583e2e7` | Correct ARM64 relative relocation analysis in kptools. |
| `b6f63d7ba17ba37f268d9cbe9eecbd314763497e` | Permit KPM version strings up to 32 bytes. |
| `0bdbf61edb240cc9dca7f122dc0a58a987f23e4b` | Bound KPM list copy to the produced buffer, preserve empty-list behavior. |
| `e566135b3ed551e506614c129564421c66b92add` | Run KPM exit outside RCU; balance missing-module RCU unlock. |
| `112434fe7460019c8aa068ad0ed04a9a3521a6e9` | Bound credential/task-structure probes. |
| `406c85ce79a5e1c19b53be34c04baadc1ec68bc5` | Bound live credential probes by MTE tags. |
| `87f4dab2da53eca64af5175c8bdd36ca046fb875` | Handle inlined ARM64 kCFI failures for KP/KPM addresses. |
| `60020829dc5e5fab357356b9e545e4d80728af3e` | Preserve a BTI landing pad at paging_init. |
| `7688cf806f25b408529ae985222a083e0e0d0ed6` | Resolve missing CFI-handler symbols at runtime. |
| `a404438ef30e7ed2b7f5af2902a8f1b7567d15e7` | Private spinlock fallback, adapted to Next's existing kstorage list; excludes upstream's different task-extension design. |
| `9e034e0bf159c732325c269d1f4f5194de67370c` | Reserve relocated core in ARM64 image_size, restore original size before repatch/unpatch. |
| `55c439fa4d9c945ceeb57a3610b8a9a988647cb5` | Validate saved preset and restore entry before header parsing, adapted to the unchanged Next disk layout. |

Additional integration fixes make synchronize_rcu call the correct kernel
symbol, reject absent KPM control callbacks, bound module metadata formatting,
validate embedded-item ranges/counts/strings, and zero-pad embedded arguments
without reading beyond the caller's argument string.

## Preserved interfaces and intentionally excluded changes

- KP2026 magic, hello2026/0x20262026, root-only supercall access, the existing
  no-superkey CLI, rehook and exclude commands are unchanged.
- `MAP_SYMBOL_NUM=5`, `header_backup` at offset 144 and `additional` at offset 728
  in `setup_preset_t` remain unchanged. Compile-time assertions lock the layout.
  `make -C kernel TARGET_COMPILE=unused hdr` generates the identical tools header.
- APatch SU/manager authorization, SELinux policy hiding, init.rc/AP daemon
  integration, x86 and LKM builds are not imported.
- Upstream's new syscall dispatcher, BTF/Kconfig/event-notification interfaces,
  kernel boot/map-layout redesign, and compressed boot.img parser are deferred.
  The module continues to use Magisk's magiskboot for unpack/repack. Existing
  KPM interfaces remain supported; this does not claim support for KPMs requiring
  those new upstream features.
- KP1158/APatch images are not accepted as KP2026/Next presets. They require their
  own unpatcher and are not a supported in-place migration path.

## Validation

`make -C kernel TARGET_COMPILE=unused hdr && make -C tools` builds native kptools.
`python3 checks/test_preset_upgrade.py tools/kptools` tests legacy and enlarged
KP2026 headers, exact unpatch round trips, false-positive magic, truncated presets,
invalid embedded-item lengths/counts, unterminated banners and tiny images.

The CI workflow builds the ARM64 core, Android arm64 tools/CLI and demo KPMs.
Real-device boot-image patch/repatch/unpatch tests and Android CLI checks must be
recorded against the actual artifact commit. Compiling and offline image checks
alone do not establish successful boot or runtime KPM behavior on every device.
