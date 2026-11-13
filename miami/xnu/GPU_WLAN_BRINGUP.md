# MIAMI GPU and WLAN: evidence and current limitations

The current XNU display path provides a framebuffer; it does not establish
Adreno acceleration, Metal, WLAN initialization, scanning, or association.
Do not infer these capabilities from a successful display or USB network test.

## Device-specific evidence

The tool miami/tools/inspect_hardware_fdt.py accepts a user-supplied MIAMI
device tree and outputs only selected GPU and WLAN resources and the input
file's SHA-256. It does not touch physical hardware. The previously captured
recovery FDT on this device (SHA-256
e53dc66ef08ebc6bc43750c714b77f91b6235fef3e189416e710f9cd142f2103)
identifies qcom,adreno-gpu-a619-holi with chip ID 0x06010901. Its GPU node
names four register ranges, an interrupt, six clocks and a GPU SMMU; it also
names a615_zap firmware. These properties are a starting point, not proof
that the resources are safe to access with the present power and clock state.

The locally supplied stock package's radio.img contains a NON-HLOS sparse
image. After read-only extraction on the host, that image contains
a615_zap.mdt and a615_zap.b00 through b02, plus wlanmdsp.mbn and multiple
board-specific WLAN files. The extracted proprietary firmware remains local.
The original image's presence does not establish that the currently running
phone has the same firmware version, nor does it establish trust acceptance.

The [MIAMI community kernel's pinned A619 table](https://github.com/Motorola-Miami/android_kernel_motorola_sm6375/blob/5104f0a1b52f273844a8fa4116b6aed4e6f303e3/drivers/gpu/msm/adreno-gpulist.h)
distinguishes the holi-specific A619 entry from the generic A619 entry. The
holi entry names a630_sqe.fw and a615_zap and uses a619_holi-specific GPU
operations. The generic entry's a619_gmu.bin must not be assumed to apply to
the holi entry. This reference tree is not verified to be the exact kernel
revision of the user's installed Motorola build. The SQE firmware has not yet
been located or validated in the local stock package.

The same tree describes qcom,icnss, its memory resource, interrupt list and
IOMMU association. Its smmu_iova_ipa range is IOVA, not a physical register
mapping. A Bluetooth node names WCN3990, but that alone does not prove the
exact WLAN silicon on this unit. Establish the WLAN identity and firmware from
the stock Android driver/firmware evidence before selecting a Wi-Fi driver.
The upstream [SM6375 device tree](https://android.googlesource.com/kernel/common/+/2bd5059c6cc04b02073d4d9f57137ab74e1d8e7a/arch/arm64/boot/dts/qcom/sm6375.dtsi)
is a useful cross-reference, not a substitute for the unit's running tree.

## Reference projects and boundaries

The primary reference [ios-sweet](https://github.com/dipa-studio/ios-sweet)
reports CPU rendering and no Wi-Fi driver. The complementary
[ios-topaz](https://github.com/MakrSas/ios-topaz) describes an Adreno 610
implementation with Mesa and separate WLAN/modem work. Its
[GPU patch](https://github.com/MakrSas/ios-topaz/blob/e4772911e116ab4ab6c4ac1f38e6106fefe8b483/xnu/patches/0901-topaz-0108-Adreno-610-GPU-TopazGpuW-recipe-behind-da.patch)
is an architecture reference, not a validated driver for MIAMI's A619.
Compare MMIO resources, SMMU, power domains, clocks, firmware and interrupt
handling before reusing any component, and retain its provenance and license.

The next implementation must establish the MIAMI-specific power, clock, SMMU,
and firmware interfaces before GPU register access or command submission.
Wi-Fi work similarly requires device-specific firmware and boot-path evidence.
The Android partitions must remain untouched during these investigations.
